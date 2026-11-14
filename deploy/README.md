# 배포 안내

리걸닥터를 기존 웹사이트의 하위 경로(예: `https://example.com/legaldoctor/`)로 올리는 방법임. 다른 서비스와 섞이지 않게 Docker 컨테이너 하나로 띄움.

## 준비물

- Docker와 Docker Compose가 있는 리눅스 서버
- Liner API 키(운영용 계정에서 발급. 대회 지급 키는 대회 개발용으로만 씀)
- 앞단 웹서버(nginx 기준 예시)

## 순서

1. 저장소를 서버에 받음: `git clone <저장소 주소> legaldoctor && cd legaldoctor`
2. 키 파일을 만듦: `cp .env.example .env` 후 `LINER_API_KEY`를 채움. `LAW_OC`는 선택(국가법령정보 공동활용에 이 서버 IP를 등록해야 통과함. 비워 두면 법령 웹 원문을 읽음)
3. 컨테이너를 띄움: `docker compose up -d --build`
4. 서버 안에서 확인: `curl -s http://127.0.0.1:8100/ | head -5`
5. nginx 설정: `deploy/nginx-legaldoctor.conf`의 두 `location` 블록을 사이트 `server { }` 안에 넣고 `sudo nginx -t && sudo systemctl reload nginx`
6. 브라우저에서 `https://<도메인>/legaldoctor/` 확인

## 운영

- 갱신: `git pull && docker compose up -d --build`
- 로그: `docker compose logs -f legaldoctor`
- 중지: `docker compose down`
- 업로드한 자료는 저장하지 않음(세션 메모리에서만 씀). 법령 캐시만 `law_cache` 볼륨에 남음
- 세션을 메모리에 두므로 컨테이너는 하나(워커 하나)로 띄움
