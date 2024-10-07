document.getElementById('search-form').addEventListener('submit', function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    fetch('/search', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.csvAvailable) {
            // 검색 결과를 페이지에 표시
            document.getElementById('results').innerHTML = data.html;
            // CSV 다운로드 버튼 보이기
            document.getElementById('download-button').style.display = 'block';
        } else {
            document.getElementById('results').innerHTML = "<p>결과를 찾을 수 없습니다. 키워드를 확인해 주세요.</p>";
            document.getElementById('download-button').style.display = 'none';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('results').innerHTML = "<p>오류가 발생했습니다. 다시 시도해 주세요.</p>";
        document.getElementById('download-button').style.display = 'none';
    });
});
