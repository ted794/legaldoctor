# 배포 안내

리걸닥터를 기존 웹사이트의 하위 경로(예: `https://example.com/legaldoctor/`)로 올리는 방법임. 기존 서비스와 섞이지 않게 별도 계정과 별도 프로세스로 띄우고 앞단 nginx에서 경로만 연결함.

두 가지 방식이 있음. 서버에 Docker가 없으면 방식 A(systemd)를 권함. 운영 서버에 Docker를 새로 깔면 방화벽 규칙이 바뀌어 기존 서비스에 영향을 줄 수 있음. 아래 방식 A는 실제 운영 서버(Ubuntu 22.04) 설치에서 확인한 순서임(2026.11.14).

## 준비물

- Ubuntu 서버, sudo 권한
- Python 3.11 이상. Ubuntu 22.04 기본은 3.10이고, apt의 `python3.11`은 출시 전 버전(3.11.0 rc1)일 수 있음. 아래처럼 uv로 정식 버전을 리걸닥터 폴더 안에 따로 설치하는 것을 권함(시스템 Python은 건드리지 않음). deadsnakes PPA도 됨
- Liner API 키(운영용 계정에서 발급. 대회 지급 키는 대회 개발용으로만 씀)
- 앞단 nginx
- 저장소가 비공개면 서버에서 `git clone`이 되지 않음. 아래 1번처럼 git bundle로 옮기거나 읽기 전용 배포 키(deploy key)를 둠

## 방식 A. systemd(Docker 없이)

1. 전용 계정과 코드
   ```bash
   sudo useradd --system --no-create-home --home-dir /srv/legaldoctor --shell /usr/sbin/nologin legaldoctor
   sudo mkdir -p /srv/legaldoctor && sudo chown legaldoctor:legaldoctor /srv/legaldoctor
   ```
   - 공개 저장소이거나 배포 키가 있을 때: `sudo -u legaldoctor git clone <저장소 주소> /srv/legaldoctor` (빈 폴더여야 clone이 됨)
   - 비공개 저장소이고 서버에 GitHub 자격이 없을 때: 로컬에서 `git bundle create legaldoctor.bundle main` → `scp legaldoctor.bundle <서버>:/tmp/` → 서버에서 `sudo -u legaldoctor git clone /tmp/legaldoctor.bundle /srv/legaldoctor && rm /tmp/legaldoctor.bundle`
2. Python과 가상환경(uv로 3.11 정식 버전을 폴더 안에 설치)
   ```bash
   sudo mkdir -p /opt/uv && curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/opt/uv sh
   sudo -u legaldoctor env HOME=/srv/legaldoctor UV_PYTHON_INSTALL_DIR=/srv/legaldoctor/.python /opt/uv/uv venv --python 3.11 /srv/legaldoctor/.venv
   sudo -u legaldoctor env HOME=/srv/legaldoctor /srv/legaldoctor/.venv/bin/python -m ensurepip
   sudo -u legaldoctor env HOME=/srv/legaldoctor /srv/legaldoctor/.venv/bin/pip install -e /srv/legaldoctor
   ```
   - 서버에서 생기는 폴더는 git 추적에서 뺌: `printf '.python/\n.cache/\n.local/\n' | sudo -u legaldoctor tee -a /srv/legaldoctor/.git/info/exclude`
3. 키 파일(서비스 계정 소유, 권한 600. 다른 서비스의 .env와 섞지 않음)
   ```bash
   sudo -u legaldoctor cp /srv/legaldoctor/.env.example /srv/legaldoctor/.env
   sudo -u legaldoctor chmod 600 /srv/legaldoctor/.env
   sudo -u legaldoctor nano /srv/legaldoctor/.env   # LINER_API_KEY 입력, LAW_OC는 선택, LD_OPERATOR·LD_CONTACT는 개인정보 안내에 보일 운영자·문의처, LD_NAV는 상단 확장 서비스 메뉴(JSON 목록. 예: [{"label":"서비스 이름","url":"https://...","note":"준비 중"}]. 없으면 개념 이름 3개가 '준비 중'으로 보임. url은 https 주소 또는 리걸닥터 안 페이지 network만 받음), LD_PUBLIC_URL은 공개 주소(https로 시작. 링크 미리보기(OG) 이미지·주소를 절대 주소로 바꾸는 데 씀)
   ```
   키는 서버 터미널에서 직접 입력함. 대화창이나 다른 세션으로 주고받지 않음
4. 서비스 등록과 실행
   ```bash
   sudo cp /srv/legaldoctor/deploy/legaldoctor.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now legaldoctor
   curl -s http://127.0.0.1:8100/ | head -3      # 서버 안에서 확인
   ```
5. nginx
   - 바꾸기 전에 사이트 설정 파일을 백업함
   - `deploy/nginx-legaldoctor.conf` 맨 위 주석의 `limit_req_zone` 한 줄을 http 블록 쪽 설정 파일(예: `/etc/nginx/conf.d/legaldoctor_rate.conf`)에 둠
   - 같은 파일의 `location` 두 개를 **도메인 본 주소(apex) server 블록 한 곳에만**, 기존 `location /` 보다 앞에 넣음. 와일드카드 서브도메인용 server 블록에는 넣지 않음(서브도메인에서는 열리지 않게)
   - `sudo nginx -t && sudo systemctl reload nginx`
6. 확인
   - `https://<도메인>/legaldoctor/` 200, `/legaldoctor/privacy` 200, `/legaldoctor` 는 301
   - 기존 사이트 첫 화면과 서브도메인이 그대로인지, 서브도메인의 `/legaldoctor/`는 열리지 않는지(404)
   - 분석이나 검진을 한 건 실제로 돌려 키·업로드(30MB)·긴 응답(최대 10분)이 앞단 nginx 뒤에서 되는지 확인. 실패하면 `sudo journalctl -u legaldoctor -n 50 --no-pager`

로그: `sudo journalctl -u legaldoctor -f`

### 다시 배포(코드 갱신)

1. 서버 쪽 작업 폴더가 깨끗한지 확인: `sudo -u legaldoctor git -C /srv/legaldoctor status --porcelain` 결과가 0줄
2. 코드 받기
   - clone이 되는 경우: `sudo -u legaldoctor git -C /srv/legaldoctor pull`
   - 비공개 저장소(번들): 로컬에서 `git bundle create legaldoctor.bundle main` → scp → 서버에서 `sudo -u legaldoctor git -C /srv/legaldoctor pull /tmp/legaldoctor.bundle main && rm /tmp/legaldoctor.bundle`
3. 의존성이 바뀌었으면: `sudo -u legaldoctor env HOME=/srv/legaldoctor /srv/legaldoctor/.venv/bin/pip install -e /srv/legaldoctor`
4. `sudo systemctl restart legaldoctor` (메모리에 있던 진행 중 세션은 사라짐)

### 최신 동향 미리 받기와 매주 새로 고침

사인 튜토리얼의 최신 동향(Liner Search)은 저장된 결과를 바로 보여 주고 7일이 지나면 뒤에서 새로 고칩니다. 배포 직후 한 번, 이후 매주 한 번 28개 사인을 미리 받아 둡니다(약 6분).

```bash
sudo -u legaldoctor env HOME=/srv/legaldoctor /srv/legaldoctor/.venv/bin/python -m legaldoctor.web.warm_news   # 지금 한 번
# 매주 월요일 04:00(서버 시간) 자동 실행: legaldoctor 사용자 crontab에 한 줄 추가
( sudo -u legaldoctor crontab -l 2>/dev/null | grep -v warm_news; echo '0 4 * * 1 cd /srv/legaldoctor && HOME=/srv/legaldoctor .venv/bin/python -m legaldoctor.web.warm_news >> /srv/legaldoctor/data/law_cache/_news/warm.log 2>&1' ) | sudo -u legaldoctor crontab -
```

### 되돌리기

```bash
sudo cp -p <백업한 사이트 설정> /etc/nginx/sites-available/<사이트>
sudo rm -f /etc/nginx/conf.d/legaldoctor_rate.conf
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl disable --now legaldoctor
```

## 방식 B. Docker

1. `git clone <저장소 주소> legaldoctor && cd legaldoctor` (비공개 저장소면 방식 A 1번의 번들 방법)
2. `cp .env.example .env` 후 `LINER_API_KEY` 입력
3. `docker compose up -d --build` (서버 안 127.0.0.1:8100)
4. nginx는 방식 A의 5번과 같음

## 운영 메모

- 화면의 API 호출은 모두 상대 경로(`api/...`)라 `/legaldoctor/` 아래에서 동작함. 화면 코드에 절대 경로(`/api/...`)를 넣으면 요청이 같은 도메인의 다른 서비스로 가서 깨짐
- 남용 방지: 앱 안에 IP별 시간당 한도(분석·검진 6회, 케어 계획·재검진 12회, 자료 읽기·스무고개·실행 상담 60회)와 서버 전체 하루 분석·검진·케어 한도(150회)가 있음. `.env`에 `LD_HEAVY_PER_HOUR`, `LD_CARE_PER_HOUR`, `LD_LIGHT_PER_HOUR`, `LD_HEAVY_PER_DAY`로 바꿈. 데모·운영자 PC는 `LD_RATE_EXEMPT=IP1,IP2`로 시간당 한도에서 뺌(하루 한도는 그대로). 한도는 서비스를 재시작하면 0부터 다시 셈. 진단 1건 Liner Model 비용은 약 $0.24~0.34(2026.11 실측)
- 법령 Open API(`LAW_OC`)를 쓰려면 open.law.go.kr에 서버 공인 IP를 등록함. 비워 두면 법령 웹 원문과 `data/law_cache`로 동작함
- 업로드 자료는 저장하지 않음(세션 메모리에서만 씀). 법령 캐시만 `data/law_cache`에 남음
- 세션을 메모리에 두므로 워커는 하나로 띄움
- 같은 도메인의 다른 서비스와 개인정보 처리방침이 다르면 리걸닥터용 고지를 따로 둘 것(리걸닥터는 `/legaldoctor/privacy` 제공)
