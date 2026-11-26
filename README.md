# neoine-sales

Python(FastAPI) 백엔드와 React 프런트엔드로 만든 영업 파이프라인 웹 애플리케이션입니다.
고객·파트너·딜과 딜 활동 이력을 기록하고 검색합니다.

## 로컬에서 웹앱 띄우기 (profile: local)

### 1. 준비물

- PostgreSQL이 실행 중이어야 합니다. DB 이름은 `neoinesales`, 계정은 `neoine`(`CREATEDB` 권한 필요)입니다.
  만드는 방법은 [개발 가이드 3.4절](docs/dev-guide.html)을 참고하세요.
- [uv](https://docs.astral.sh/uv/), Node.js, corepack(pnpm)

### 2. 처음 한 번만

**스크립트(권장, macOS·리눅스 공용)**: `./scripts/setup.sh`(dev 프로파일은 `--profile dev`)가 uv·Node.js·corepack 설치, 의존성, `backend/.env` 생성(비밀 `APP_JWT_SECRET`·`APP_SETTINGS_ENCRYPTION_KEY`는 무작위 생성, 값은 출력하지 않음), 마이그레이션까지 합니다. 처음 실행하면 `APP_DATABASE_URL`의 `CHANGE_ME`를 채우라고 안내하고 종료 코드 3으로 멈추므로, 채운 뒤 다시 실행합니다. product 서버 준비(`--profile product`)는 [개발 가이드 16.8절](docs/dev-guide.html)을 보세요.

수동으로 할 때:

```bash
# 환경 파일 만들기 (backend/.env는 git에 올라가지 않습니다)
cp backend/.env.example backend/.env
# backend/.env의 APP_DATABASE_URL에서 CHANGE_ME를 실제 DB 비밀번호로 바꿉니다.
# 비밀번호의 특수문자는 URL 인코딩합니다 (예: ! -> %21, @ -> %40).
# APP_PROFILE을 적지 않으면 local이 기본입니다.

# 의존성 설치
cd backend && uv sync && cd ..
cd frontend && corepack pnpm install && cd ..

# DB 스키마 적용
cd backend && uv run alembic upgrade head && cd ..
```

corepack 서명 오류(`Cannot find matching keyid`)가 나면 pnpm 명령 앞에 `COREPACK_INTEGRITY_KEYS=0`을 붙입니다.

### 3. 실행

스크립트로 띄우면 백그라운드(nohup)로 실행되어 터미널을 닫아도 계속 돕니다.
로그는 `logs/backend.log`·`logs/frontend.log`에 이어 쓰고, 종료는 `kill $(cat logs/backend.pid)`·`kill $(cat logs/frontend.pid)`입니다.

```bash
./scripts/start-backend.sh      # 시작 전에 alembic upgrade head 실행(--skip-migrate로 생략, --profile dev 가능)
./scripts/start-frontend.sh     # 모든 주소에서 접속 허용(다른 PC: http://<서버 IP>:5173, --host localhost면 이 PC만)
tail -f logs/backend.log        # 로그 보기
```

재시작은 대상 TCP 포트의 모든 리스너에 기본 SIGTERM을 보냅니다. 첫 인자로 `now`를 주면
SIGKILL을 보냅니다. 포트가 닫힌 뒤에만 기존 시작 스크립트를 실행하며, 종료 대기는 최대 1분입니다.
포트 확인에는 `lsof`가 필요합니다. 시작 옵션은 재시작 스크립트에도 전달할 수 있습니다.

```bash
./scripts/restart-backend.sh --profile dev
./scripts/restart-frontend.sh now --host localhost
```

직접 띄우려면(터미널 2개, 종료 Ctrl+C):

```bash
# 터미널 1: 백엔드 (8000번 포트)
cd backend
uv run uvicorn app.main:app --reload --port 8000 --app-dir src
```

```bash
# 터미널 2: 프런트엔드 (5173번 포트)
cd frontend
corepack pnpm dev
```

### 4. 접속

| 주소 | 용도 |
| --- | --- |
| http://localhost:5173 | 웹앱 (`/api` 요청은 8000번 포트로 자동 전달됩니다) |
| http://localhost:8000/docs | API 문서 (local 프로파일에서만 열림) |
| http://localhost:8000/readyz | 백엔드와 DB 연결 상태 |

OS에 직접 설치한 서버에서 Nginx를 앞에 둘 때는 `/images/**` 같은 정적 파일을 포함한 모든 프런트 요청을 Vite(`http://127.0.0.1:5173`)로 프록시합니다. Vite가 `frontend/public`의 파일을 같은 경로로 제공하고 `/api/**`는 FastAPI(`http://localhost:8000`)로 다시 프록시하므로, Nginx에 정적 파일용 `alias`나 별도 `/images/` 규칙을 두지 않습니다. Nginx가 전달하는 서비스 도메인은 `frontend/vite.config.ts`의 `allowedHosts`에 등록되어 있어야 합니다.

개발용 자동 로그인은 없습니다(2026-11-03 제거). 최초 설정이 안 된 DB로 접속하면 **반드시 `/setup`의 최초 설정**을 거칩니다. AD 서버 없이 로컬에서 개발하려면 인증 방식에서 **앱에서 직접 관리(local)**를 고르고 저장 위치 → admin 아이디·비밀번호를 등록하면 그 계정으로 자동 로그인됩니다. sales·user 계정은 admin이 사용자 관리에서 만듭니다(user는 조회만 가능하고, 사용자 관리·설정 메뉴는 admin에게만 보입니다). 예전 개발용 로그인 아이디 `dev-admin`·`dev-sales`·`dev-user`는 예약되어 등록할 수 없습니다.

처음 접속하면 `/setup`에서 먼저 **인증 방식**(AD 연동 / 앱에서 직접 관리)을 고르고, AD 연동이면 **① AD 서버 등록 → ② 첨부 파일 저장 위치 → ③ admin 등록(AD 아이디·비밀번호)**, 앱에서 직접 관리하면 **저장 위치 → admin 아이디·비밀번호·이름 등록**을 차례로 하고, 성공하면 자동 로그인됩니다. AD 서버 정보는 환경변수가 아니라 DB에 저장되며 이후 admin이 설정 메뉴에서 바꿉니다. 로컬에서 실제 AD 로그인을 시험하려면 앱 서버에서 AD에 접근할 수 있어야 합니다.

### 막힐 때

| 증상 | 확인할 것 |
| --- | --- |
| 백엔드가 `Field required`로 기동하지 않음 | `backend/.env`에 `APP_DATABASE_URL`, `APP_JWT_SECRET`, `APP_SETTINGS_ENCRYPTION_KEY`가 있는지. 암호화 키는 `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`로 만들어 넣습니다(형식이 틀려도 기동 실패) |
| `/readyz`가 503 | DB가 떠 있는지, `APP_DATABASE_URL`의 DB 이름·계정·비밀번호가 맞는지 |
| 로그인 화면 대신 `/setup`이 열림 | 최초 설정이 안 된 DB입니다. 인증 방식을 고르고 설정을 마칩니다 |
| `start-backend.sh`·`setup.sh`가 `Can't locate revision …`으로 멈춤 | 마이그레이션 이력이 2026-11-05에 최초 버전 1개(`00c3126aa926`)로 통합되어, 그보다 오래된 리비전에 머문 local·dev DB는 올릴 수 없습니다. 그 DB를 지우고(데이터 사라짐) 빈 DB를 다시 만든 뒤 `./scripts/start-backend.sh --profile local`(또는 `dev`)을 실행하면 최초 버전이 적용되고, 화면의 `/setup`에서 최초 설정을 합니다. 리비전은 `backend/`에서 `uv run alembic current`(dev는 `APP_PROFILE=dev APP_ENV_FILE=.env.dev` 앞에 붙임)로 확인합니다 |
| 실제 AD로 로그인하고 싶음 | `/setup`에서 AD 서버(호스트·포트·보안 연결·바인드 계정·비밀번호·사용자 필터·연결 제한 시간, Base DN은 자동)와 admin을 등록합니다. 값은 AD 관리자에게 받습니다 |
| AD 장애 중 로그인 / "AD 연결 경고" 팝업 | AD 설정이 없거나 AD에 접속할 수 없으면 이전에 로그인에 성공한 비밀번호로 들어갈 수 있고, admin에게는 원인 팝업이 뜹니다. 외부연동 설정에서 AD 설정을 확인하세요 |
| 로그인이 계속 401 | AD 아이디가 앱에 등록되어 있는지(admin이 사용자 관리에서 추가), 아이디·비밀번호가 맞는지. 실패 사유는 보안상 구분해서 알려 주지 않습니다 |
| 로그인이 429 | 짧은 시간에 여러 번 실패해 잠겼습니다. 15분 뒤 다시 시도하세요 |

## 검증

```bash
# 백엔드: ruff, format, mypy, import-linter, 파일 길이, pytest 한 번에
cd backend && uv run python scripts/run_gates.py

# 프런트엔드
cd frontend && corepack pnpm typecheck && corepack pnpm lint && corepack pnpm test && corepack pnpm build
```

백엔드 API를 바꾸면 계약 파일과 프런트엔드 타입을 다시 생성해 함께 커밋합니다.

```bash
cd backend && uv run python scripts/export_openapi.py   # backend/openapi.json
cd frontend && corepack pnpm gen:api                    # src/shared/api/schema.d.ts
```

## 운영(product) 배포 방식

화면과 API가 **하나의 주소**로 제공됩니다. product는 서버 1대에서 **docker compose**로 돌고(2026-11-02 전환),
`web`(nginx: TLS 종료, 빌드된 `frontend/dist` 서빙, `/api` 프록시), `api`(Uvicorn), `db`(PostgreSQL 18) 컨테이너가 상시 실행되며
마이그레이션은 배포 때 `migrate` 컨테이너가 한 번 실행합니다. 프런트엔드용 Node 서버는 없습니다.
Jenkins가 `main` 머지 시 api·web 이미지를 만들어 사내 레지스트리(`REGISTRY`)에 push하고, 사람이 승인하면 서버(`PRODUCT_HOST`)에서
`infra/docker/deploy.sh`가 pull → 설정 검증 → DB 덤프 → 마이그레이션 → 전환 → 헬스체크를 합니다(실패하면 이전 이미지로 자동 롤백).
서버 준비는 `scripts/setup.sh --profile product`(리눅스, Docker Engine + Compose v2 필요, 준비까지만)로 합니다. dev 서버는 두지 않습니다.
월말 Forecast 스냅숏은 앱이 스스로 만듭니다(별도 cron·timer 없음).
자세한 내용은 [개발 가이드 14·16장](docs/dev-guide.html)과 `infra/docker/`를 보세요.

## 구조

```
backend/    FastAPI (domain / application / infra / web 4계층, uv 관리)
frontend/   React + TypeScript (Vite)
scripts/    setup.sh(설치: 개발 PC·product 서버 준비), start-backend.sh·start-frontend.sh, tests/(셸 테스트)
infra/      docker/(compose.yaml, deploy.sh, build_images.sh, web 이미지), server/lib/env_secrets.sh(비밀 생성 공용 함수)
docs/       dev-guide.html (개발 가이드), harness-guide.html (AI 하네스 가이드)
Jenkinsfile CI 파이프라인
```

규칙의 정본은 [개발 가이드](docs/dev-guide.html)와 `backend/pyproject.toml`입니다.
AI 에이전트(Claude Code)로 개발하는 방법은 `CLAUDE.md`와 [하네스 가이드](docs/harness-guide.html)를 보세요.
