import pandas as pd
from flask import Flask, request, send_file, render_template, jsonify, session
from dotenv import load_dotenv
import os
import io
from powernad.API.RelKwdStat import RelKwdStat

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

# 네이버 검색광고 API 호출 함수
def get_keyword_data(keyword):
    rel = RelKwdStat(BASE_URL, API_KEY, SECRET_KEY, CUSTOMER_ID)
    try:
        kwdDataList = rel.get_rel_kwd_stat_list(siteId=None, biztpId=None, hintKeywords=keyword, event=None, month=None, showDetail='1')
        if kwdDataList:
            # 입력한 키워드와 정확히 일치하는 결과만 필터링
            filtered_data = [data for data in kwdDataList if getattr(data, 'relKeyword', '').lower() == keyword.lower()]
            print(f"Filtered data for keyword '{keyword}': {filtered_data}")
            return filtered_data
        else:
            print(f"No data returned for keyword '{keyword}'")
    except Exception as e:
        print(f"Error fetching data for keyword '{keyword}': {e}")
    return None

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
    for keyword in keywords:
        kwdDataList = get_keyword_data(keyword)
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
                    print(f"Incomplete data for keyword '{keyword}': {data}")
        else:
            print(f"No valid data for keyword: {keyword}")

    if not results:
        return jsonify({'csvAvailable': False}), 500

    # 결과를 DataFrame으로 변환하고 CSV 파일로 저장
    df = pd.DataFrame(results, columns=[
        '키워드', '월간 PC 검색량', '월간 모바일 검색량', '월간 평균 PC 클릭 수',
        '월간 평균 모바일 클릭 수', 'PC 클릭률', '모바일 클릭률', '평균 광고 노출 깊이', '경쟁 지수'
    ])
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)

    # CSV 내용을 임시 파일로 저장
    session['csv_data'] = output.getvalue()

    # 결과를 HTML 형식으로 변환
    table_html = df.to_html(classes='table table-striped', index=False)

    return render_template('results.html', table_html=table_html, csvAvailable=True)

# CSV 다운로드 엔드포인트
@app.route('/download_csv', methods=['GET'])
def download_csv():
    csv_data = session.get('csv_data')
    if not csv_data:
        return "No CSV data available.", 404

    return send_file(io.BytesIO(csv_data.encode('utf-8-sig')),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='keyword_search_results.csv')

if __name__ == '__main__':
    app.run(debug=False)