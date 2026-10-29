# neoine-sales

Python(FastAPI) 백엔드와 React 프런트엔드로 만든 영업 파이프라인 웹 애플리케이션입니다.
고객·파트너·딜과 딜 활동 이력을 기록하고 검색합니다.

## 로컬에서 웹앱 띄우기 (profile: local)

### 1. 준비물

- PostgreSQL이 실행 중이어야 합니다. DB 이름은 `neoinesales`, 계정은 `neoine`(`CREATEDB` 권한 필요)입니다.
  만드는 방법은 [개발 가이드 3.4절](docs/dev-guide.html)을 참고하세요.
- [uv](https://docs.astral.sh/uv/), Node.js, corepack(pnpm)

### 2. 처음 한 번만

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

로그인 화면에서 **개발용 로그인**으로 역할(admin, sales, user)을 골라 들어갑니다.
로컬에서는 `APP_DEV_LOGIN_ENABLED`가 기본으로 켜져 있어 AD 서버가 필요 없습니다.
이 기능은 local 프로파일에서만 켤 수 있고, dev·product에서 켜면 서버가 기동되지 않습니다.
(user는 조회만 가능하고, 사용자 관리·설정 메뉴는 admin에게만 보입니다.)

실제 AD 로그인은 앱 화면에서 설정합니다. 처음 접속하면 `/setup`에서 **① AD 서버 등록 → ② 첨부 파일 저장 위치 → ③ admin 등록(AD 아이디·비밀번호)** 을 차례로 하고, 성공하면 자동 로그인됩니다. AD 서버 정보는 환경변수가 아니라 DB에 저장되며 이후 admin이 설정 메뉴에서 바꿉니다. 로컬에서 실제 AD 로그인을 시험하려면 앱 서버에서 AD에 접근할 수 있어야 합니다.

### 막힐 때

| 증상 | 확인할 것 |
| --- | --- |
| 백엔드가 `Field required`로 기동하지 않음 | `backend/.env`에 `APP_DATABASE_URL`, `APP_JWT_SECRET`, `APP_SETTINGS_ENCRYPTION_KEY`가 있는지. 암호화 키는 `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`로 만들어 넣습니다(형식이 틀려도 기동 실패) |
| `/readyz`가 503 | DB가 떠 있는지, `APP_DATABASE_URL`의 DB 이름·계정·비밀번호가 맞는지 |
| 로그인 화면에 개발용 로그인이 없음 | 백엔드가 떠 있는지, `APP_DEV_LOGIN_ENABLED`를 끄지 않았는지 |
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

화면과 API가 **하나의 주소**로 제공됩니다. 프런트엔드는 정적 파일(`frontend/dist`)로 빌드되어 릴리스 번들에 함께 들어가고,
서버의 Nginx가 정적 파일을 직접 서빙하면서 `/api`만 백엔드(Uvicorn, 127.0.0.1:8000)로 넘깁니다.
서버에서 실행되는 것은 백엔드(systemd 서비스 `neoine-sales-api`)와 Nginx뿐이며 프런트엔드용 Node 서버는 없습니다.
Jenkins가 `main` 머지 시 번들을 만들어 dev에 자동 배포하고, 승인 후 product에 한 대씩 순차 배포합니다(실패하면 이전 릴리스로 자동 롤백).
자세한 내용은 [개발 가이드 16장](docs/dev-guide.html)과 `infra/server/`를 보세요.

## 구조

```
backend/    FastAPI (domain / application / infra / web 4계층, uv 관리)
frontend/   React + TypeScript (Vite)
infra/      릴리스 번들 스크립트, 서버 구성·배포 자산(infra/server: systemd, Nginx, deploy.sh, bootstrap.sh)
docs/       dev-guide.html (개발 가이드), harness-guide.html (AI 하네스 가이드)
Jenkinsfile CI 파이프라인
```

규칙의 정본은 [개발 가이드](docs/dev-guide.html)와 `backend/pyproject.toml`입니다.
AI 에이전트(Claude Code)로 개발하는 방법은 `CLAUDE.md`와 [하네스 가이드](docs/harness-guide.html)를 보세요.
