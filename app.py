from flask import Flask, render_template, request

app = Flask(__name__)

# 기본 페이지
@app.route('/')
def home():
    return render_template('index.html')

# 새로운 라우트 추가
@app.route('/results')
def results():
    return render_template('results.html')

# 폼 데이터를 처리하는 예제
@app.route('/search', methods=['POST'])
def search():
    keyword = request.form['keyword']
    # 여기서 검색 결과를 처리하는 로직을 추가할 수 있습니다
    return f"Search results for: {keyword}"

if __name__ == '__main__':
    app.run()
