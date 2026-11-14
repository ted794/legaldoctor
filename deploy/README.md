# 배포 안내

리걸닥터를 기존 웹사이트의 하위 경로(예: `https://example.com/legaldoctor/`)로 올리는 방법임. 기존 서비스와 섞이지 않게 별도 계정과 별도 프로세스로 띄우고 앞단 nginx에서 경로만 연결함.

두 가지 방식이 있음. 서버에 Docker가 없으면 방식 A(systemd)를 권함. 운영 서버에 Docker를 새로 깔면 방화벽 규칙이 바뀌어 기존 서비스에 영향을 줄 수 있음.

## 준비물

- Ubuntu 서버, sudo 권한
- Python 3.11 이상
- Liner API 키(운영용 계정에서 발급. 대회 지급 키는 대회 개발용으로만 씀)
- 앞단 nginx

## 방식 A. systemd(Docker 없이)

1. 전용 계정과 코드
   ```bash
   sudo useradd --system --create-home --home-dir /srv/legaldoctor --shell /usr/sbin/nologin legaldoctor
   sudo -u legaldoctor git clone <저장소 주소> /srv/legaldoctor
   ```
2. 가상환경과 설치
   ```bash
   sudo -u legaldoctor python3 -m venv /srv/legaldoctor/.venv
   sudo -u legaldoctor /srv/legaldoctor/.venv/bin/pip install -e /srv/legaldoctor
   ```
3. 키 파일(서비스 계정 소유, 권한 600. 다른 서비스의 .env와 섞지 않음)
   ```bash
   sudo -u legaldoctor cp /srv/legaldoctor/.env.example /srv/legaldoctor/.env
   sudo -u legaldoctor chmod 600 /srv/legaldoctor/.env
   sudo -u legaldoctor nano /srv/legaldoctor/.env   # LINER_API_KEY 입력, LAW_OC는 선택
   ```
4. 서비스 등록과 실행
   ```bash
   sudo cp /srv/legaldoctor/deploy/legaldoctor.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now legaldoctor
   curl -s http://127.0.0.1:8100/ | head -3      # 서버 안에서 확인
   ```
5. nginx
   - `deploy/nginx-legaldoctor.conf` 맨 위 주석의 `limit_req_zone` 한 줄을 http 블록 쪽 설정 파일에 둠
   - 같은 파일의 `location` 두 개를 사이트 `server { }` 안, 기존 `location /` 보다 앞에 넣음
   - `sudo nginx -t && sudo systemctl reload nginx`
6. 확인: `https://<도메인>/legaldoctor/` 가 열리는지, 기존 사이트 첫 화면과 다른 경로가 그대로인지

갱신: `sudo -u legaldoctor git -C /srv/legaldoctor pull && sudo systemctl restart legaldoctor`
로그: `sudo journalctl -u legaldoctor -f`

## 방식 B. Docker

1. `git clone <저장소 주소> legaldoctor && cd legaldoctor`
2. `cp .env.example .env` 후 `LINER_API_KEY` 입력
3. `docker compose up -d --build` (서버 안 127.0.0.1:8100)
4. nginx는 방식 A의 5번과 같음

## 운영 메모

- 남용 방지: 앱 안에 IP별 시간당 한도(분석·검진 6회, 자료 읽기·스무고개 60회)와 서버 전체 하루 분석·검진 한도(150회)가 있음. `.env`에 `LD_HEAVY_PER_HOUR`, `LD_LIGHT_PER_HOUR`, `LD_HEAVY_PER_DAY`로 바꿈. 진단 1건 Liner Model 비용은 약 $0.24~0.34(2026.11 실측)
- 업로드 자료는 저장하지 않음(세션 메모리에서만 씀). 법령 캐시만 `data/law_cache`에 남음
- 세션을 메모리에 두므로 워커는 하나로 띄움. 재시작하면 진행 중인 세션은 사라짐
- 같은 도메인의 다른 서비스와 개인정보 처리방침이 다르면 리걸닥터용 고지를 따로 둘 것
