import pandas as pd
from flask import Flask, request, send_file, render_template, jsonify, session, Response
from dotenv import load_dotenv
import os
import io
import csv
import time
from powernad.API.RelKwdStat import RelKwdStat
from concurrent.futures import ThreadPoolExecutor

# .env 파일에서 환경 변수 로드
load_dotenv()

# 네이버 검색광고 API 정보 불러오기
BASE_URL = "https://api.searchad.naver.com"
API_KEY = os.getenv('NAVER_API_KEY')
SECRET_KEY = os.getenv('NAVER_SECRET_KEY')
CUSTOMER_ID = os.getenv('NAVER_CUSTOMER_ID')

# 환경 변수 누락 시 오류 처리
if not API_KEY or not SECRET_KEY or not CUSTOMER_ID:
    raise EnvironmentError("NAVER_API_KEY, NAVER_SECRET_KEY, and NAVER_CUSTOMER_ID must be set in the environment variables.")

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 기본 페이지 렌더링
@app.route('/')
def index():
    return render_template('index.html')

# 키워드를 배치로 묶는 함수
def batch_keywords(keywords, batch_size):
    for i in range(0, len(keywords), batch_size):
        yield keywords[i:i + batch_size]

# 네이버 검색광고 API 호출 함수 (키워드 배치 처리)
def get_keyword_data(keyword_batch):
    rel = RelKwdStat(BASE_URL, API_KEY, SECRET_KEY, CUSTOMER_ID)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # hintKeywords에 키워드 리스트를 쉼표로 구분하여 전달
            hint_keywords = ','.join(keyword_batch)
            kwdDataList = rel.get_rel_kwd_stat_list(
                siteId=None,
                biztpId=None,
                hintKeywords=hint_keywords,
                event=None,
                month=None,
                showDetail='1'
            )
            if kwdDataList:
                # 입력한 키워드와 정확히 일치하는 결과만 필터링
                filtered_data = []
                for keyword in keyword_batch:
                    for data in kwdDataList:
                        if getattr(data, 'relKeyword', '').lower() == keyword.lower():
                            filtered_data.append(data)
                            break  # 일치하는 데이터가 있으면 다음 키워드로 넘어감
                return filtered_data
            else:
                print(f"No data returned for keywords '{keyword_batch}'")
                return []
        except Exception as e:
            print(f"Error fetching data for keywords '{keyword_batch}' on attempt {attempt + 1}: {e}")
            time.sleep(1)  # 잠시 대기 후 재시도
    return []

# 키워드 검색량 확인 API 엔드포인트
@app.route('/search', methods=['POST'])
def search_keywords():
    file = request.files.get('keyword-file')
    if not file:
        return jsonify({'csvAvailable': False}), 400

    # 키워드 파일 읽기
    try:
        keywords = file.read().decode('utf-8').splitlines()
    except Exception as e:
        return jsonify({'csvAvailable': False, 'error': str(e)}), 400

    if not keywords:
        return jsonify({'csvAvailable': False}), 400

    # 결과 저장을 위한 리스트
    results = []

    # 키워드를 5개씩 묶어서 배치 생성
    keyword_batches = list(batch_keywords(keywords, 5))

    # 멀티스레딩을 사용해 키워드 배치 데이터 병렬 처리
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_batch = {executor.submit(get_keyword_data, batch): batch for batch in keyword_batches}
        for future in future_to_batch:
            batch = future_to_batch[future]
            try:
                kwdDataList = future.result()
                if kwdDataList:
                    for data in kwdDataList:
                        if hasattr(data, 'relKeyword'):
                            results.append([
                                data.relKeyword,
                                data.monthlyPcQcCnt if hasattr(data, 'monthlyPcQcCnt') else '<10',
                                data.monthlyMobileQcCnt if hasattr(data, 'monthlyMobileQcCnt') else '<10',
                                data.monthlyAvePcClkCnt if hasattr(data, 'monthlyAvePcClkCnt') else 0,
                                data.monthlyAveMobileClkCnt if hasattr(data, 'monthlyAveMobileClkCnt') else 0,
                                data.monthlyAvePcCtr if hasattr(data, 'monthlyAvePcCtr') else 0,
                                data.monthlyAveMobileCtr if hasattr(data, 'monthlyAveMobileCtr') else 0,
                                data.plAvgDepth if hasattr(data, 'plAvgDepth') else 0,
                                data.compIdx if hasattr(data, 'compIdx') else 'low'
                            ])
                else:
                    print(f"No valid data for keyword batch: {batch}")
            except Exception as e:
                print(f"Error processing keyword batch '{batch}': {e}")

    if not results:
        return jsonify({'csvAvailable': False}), 500

    # 결과를 세션에 저장하여 CSV 다운로드 시 사용
    session['results'] = results

    # 결과를 DataFrame으로 변환하고 HTML 테이블로 렌더링
    df = pd.DataFrame(results, columns=[
        '키워드', '월간 PC 검색량', '월간 모바일 검색량', '월간 평균 PC 클릭 수',
        '월간 평균 모바일 클릭 수', 'PC 클릭률', '모바일 클릭률', '평균 광고 노출 깊이', '경쟁 지수'
    ])
    table_html = df.to_html(classes='table table-striped', index=False)

    return render_template('results.html', table_html=table_html, csvAvailable=True)

# CSV 다운로드 엔드포인트 (스트리밍 방식)
@app.route('/download_csv', methods=['GET'])
def download_csv():
    results = session.get('results')
    if not results:
        return "No data available.", 404

    def generate():
        yield '\ufeff'  # UTF-8 with BOM
        header = [
            '키워드', '월간 PC 검색량', '월간 모바일 검색량', '월간 평균 PC 클릭 수',
            '월간 평균 모바일 클릭 수', 'PC 클릭률', '모바일 클릭률', '평균 광고 노출 깊이', '경쟁 지수'
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for row in results:
            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return Response(generate(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename="keyword_search_results.csv"'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
