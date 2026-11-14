# 스타트업 리걸닥터 웹 서비스 이미지
# 데이터(data/: 사례 DB, 법령 캐시, 검진 데이터)를 코드와 함께 담는다. 키는 이미지에 넣지 않고 실행 때 .env로 받는다
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY legaldoctor ./legaldoctor
COPY data ./data
# 편집 모드 설치: 패키지가 /app/data를 그대로 읽게 함
RUN pip install --no-cache-dir -e .

RUN useradd --create-home --uid 10001 app && chown -R app /app/data
USER app

EXPOSE 8000
CMD ["legaldoctor", "web", "--host", "0.0.0.0", "--port", "8000"]
