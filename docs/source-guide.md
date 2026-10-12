# neoine-sales 소스 구조 가이드

현재 구현된 소스가 무엇인지, 파일이 어디에 있고 무슨 뜻인지, 어떻게 빌드·배포하는지를 한 곳에 정리한 문서입니다.
규칙의 정본은 [개발 가이드](dev-guide.html), AI 하네스는 [하네스 가이드](harness-guide.html)입니다. 이 문서는 "지도" 역할만 합니다.

## 1. 한눈에 보기

영업 파이프라인 웹 앱입니다. 고객·파트너·딜(영업 기회)과 딜 활동 이력을 기록·검색하고, 딜을 8단계 파이프라인으로 관리합니다.

| 영역 | 기술 |
| --- | --- |
| 백엔드 | Python 3.14, FastAPI, SQLAlchemy 2(async) + asyncpg, Alembic, ldap3, pydantic-settings, structlog |
| 프런트엔드 | React 19, TypeScript 5.9, Vite, React Router, TanStack Query, openapi-fetch, Vitest |
| DB | PostgreSQL (DB명 `neoinesales`) |
| 인증 | AD(LDAP) 아이디·비밀번호 → 서버 세션(HttpOnly 쿠키). 로컬은 개발용 로그인 |
| 권한 | 역할 3종: `admin`(전부 + 사용자 관리·AD 설정), `sales`(업무 전부), `user`(조회만) |
| 패키지 | 백엔드 uv, 프런트엔드 pnpm(corepack) |
| CI/CD | Jenkins(Multibranch) → 릴리스 번들(tar.gz) → SSH로 서버에 `deploy.sh` 실행 |
| 서버 | on-prem Linux, Nginx(정적 파일 + `/api` 프록시) + systemd(`neoine-sales-api`), 컨테이너 없음 |

최상위 구조:

```
backend/     FastAPI 백엔드 (uv 관리)
frontend/    React 프런트엔드 (pnpm 관리)
infra/       릴리스 번들 스크립트, 서버 구성·배포 자산
docs/        개발 가이드, 하네스 가이드, 이 문서
Jenkinsfile  CI/CD 파이프라인
CLAUDE.md    AI 에이전트(Claude Code) 작업 규칙
.claude/     에이전트·스킬·훅·권한 설정
artifacts/   에이전트 실행 산출물(Git 제외)
```

## 2. 백엔드 (`backend/`)

### 2.1 아키텍처: 4계층 + 의존성 역전

```
web   ──┐
        ├──▶ application ──▶ domain      (화살표 = import 방향)
infra ──┘
```

| 계층 | 책임 | 하지 않는 일 |
| --- | --- | --- |
| `domain` | 엔티티·값 객체·도메인 규칙. 순수 파이썬 | 프레임워크·DB·설정 import 금지 |
| `application` | 유스케이스(1파일 1유스케이스)와 **Port(Protocol)** 소유 | `infra`·`web`·sqlalchemy·fastapi import 금지 |
| `infra` | Port 구현(PostgreSQL 저장소, LDAP, 시계) | 비즈니스 규칙 판단 금지 |
| `web` | HTTP ↔ 유스케이스 변환, 권한 적용, 오류 매핑 | SQL·트랜잭션·규칙 금지 |
| `container*.py` | 조립 지점(Composition Root). 유일하게 모든 계층을 import | - |

계층 위반은 `import-linter`(`pyproject.toml`의 `[tool.importlinter]`)가 막습니다. 파일은 300줄 이하(`scripts/check_file_length.py`).

### 2.2 `backend/` 최상위 파일

| 파일 | 의미 |
| --- | --- |
| `pyproject.toml` | 의존성, ruff·mypy·pytest·import-linter 설정의 **정본** |
| `uv.lock`, `.python-version` | 잠긴 의존성, Python 버전(3.14) |
| `.env.example` | 필요한 환경변수 이름 예시(실제 `.env`는 Git 제외, 읽지도 쓰지도 않음) |
| `alembic.ini`, `alembic/` | DB 마이그레이션. `versions/`에 리비전 6개(세션, 고객·파트너·딜, 딜 활동, 딜 단계, 딜 소유자, 사용자·로그인 실패·AD 설정) |
| `openapi.json` | API 계약 파일. 코드와 다르면 테스트가 실패(드리프트 검사), 프런트 타입의 원본 |
| `scripts/run_gates.py` | 전체 품질 게이트 실행(결과: `artifacts/30-review/gate.md`) |
| `scripts/check_file_length.py` | 파일 300줄 제한 검사 |
| `scripts/export_openapi.py` | `openapi.json` 생성 |

### 2.3 `src/app/` 진입점·설정·조립

| 파일 | 의미 |
| --- | --- |
| `main.py` | FastAPI 앱 팩토리 `create_app()`. 라우터 등록, CORS, 오류 처리기. `uvicorn app.main:app` |
| `config/base.py` | `Settings`: `APP_` 접두어 환경변수 필드(DB URL, 쿠키, 세션 TTL, 로그인 시도 제한 등) |
| `config/profiles.py` | 프로파일별 기본값과 안전 검증. `LocalSettings`/`DevSettings`/`ProductSettings`. product는 debug·docs 끄기, `cookie_secure`, JWT 비밀 32자 이상, Sentry DSN 필수. `dev_login`은 local에서만 허용 |
| `config/__init__.py` | `get_settings()`: `APP_PROFILE`로 프로파일을 골라 설정을 읽는 유일한 진입점 |
| `container.py` | 업무(고객·파트너·딜·활동) 유스케이스 조립. DB 엔진·세션 팩토리 소유 |
| `container_auth.py` | 인증 유스케이스(로그인, 최초 설정, 로그아웃, 개발 로그인) 조립 |
| `container_admin.py` | admin 기능(사용자 관리, AD 설정) 조립 |

### 2.4 `domain/` — 비즈니스 규칙

| 폴더 | 내용 |
| --- | --- |
| `common/` | 공통 엔티티 기반, 오류, 검증(`required_text` 등, NUL 문자 거부), 연락처, 금액 값 객체 |
| `customer/`, `partner/` | 고객·파트너 엔티티, 값 객체, 오류 |
| `deal/` | 딜 엔티티, `stage.py`(8단계: 기회발굴→제품소개→POC준비→POC완료→기술평가→가격협상→계약완료, 실주), `pipeline.py`(단계별 요약), 값 객체. 실주로 바꿀 때 사유 필수 |
| `deal_action/` | 딜 활동(영업 활동 기록) 엔티티 |
| `auth/` | `principal.py`(Role·Permission·Principal), `credentials.py`(LoginId·Password, 비밀번호는 로그에 마스킹), `session.py`, `login_failure.py`(시도 제한 카운터) |
| `user/` | 사용자 엔티티(소프트 삭제, 마지막 로그인 시각), `policy.py`(자기 자신·마지막 admin 삭제 금지) |
| `directory/` | AD 설정 값 객체(`settings.py`), LDAP URL·필터 규칙 검증(평문 LDAP 금지, `{login_id}` 템플릿) |

### 2.5 `application/` — 유스케이스와 Port

- `ports/`: 외부와 통신하는 인터페이스. 저장소(`*_repository.py`), `unit_of_work.py`(트랜잭션 경계), `directory.py`(AD 인증기), `clock.py`, `pagination.py`
- 업무 폴더 `customer/`, `partner/`, `deal/`, `deal_action/`: 등록·조회·수정·삭제·검색 유스케이스. `deal/`에는 `change_stage.py`(단계 변경과 이력), `get_pipeline.py`
- `auth/`: `directory_login.py`(AD 로그인), `authenticate.py`(요청마다 활성 사용자·역할 확인), `throttle.py`(로그인 시도 제한), `setup_directory.py`·`setup_first_admin.py`(최초 2단계 설정), `dev_login.py`, `logout.py`, `issue_session.py`, `tokens.py`
- `user/`: `register_user.py`, `delete_user.py`, `list_users.py`
- `directory/`: AD 설정 조회·연결 테스트·변경(`get_settings`, `test_settings`, `update_settings`, `verify_settings`)

### 2.6 `infra/` — Port 구현체

| 파일 | 의미 |
| --- | --- |
| `db/base.py`, `db/models.py`, `db/models_auth.py` | SQLAlchemy 선언 베이스와 ORM 모델(고객·파트너·딜·활동·세션·사용자 등) |
| `db/*_repository.py` | 각 저장소 Port의 PostgreSQL 구현 |
| `db/unit_of_work.py` | 트랜잭션 단위 구현 |
| `db/like.py` | 키워드 검색용 LIKE 이스케이프 |
| `auth/ldap.py`, `auth/ldap_errors.py` | ldap3 기반 AD 인증·연결 확인. 서버 URL을 순서대로 시도, 서버별 타임아웃, TLS 검증 필수, 사용자 본인 계정으로 바인드 |
| `system_clock.py` | `Clock` Port 구현 |

### 2.7 `web/` — HTTP 계층

| 파일/폴더 | 의미 |
| --- | --- |
| `routers/` | 엔드포인트. `auth*.py`(로그인·로그아웃·상태·최초 설정), `users.py`, `settings_directory.py`, `customers.py`, `partners.py`, `deals.py`, `deal_stages.py`, `deal_actions.py`, `health.py`(`/healthz`, `/readyz`) |
| `schemas/` | 요청·응답 Pydantic 모델 |
| `permissions.py` | `BusinessRouter`(sales 이상만 쓰기)와 `admin_router`(admin 전용)로 권한을 라우터 등록 시점에 적용 |
| `security.py` | 쿠키 세션 확인(`require_login`), CSRF 헤더(`X-Requested-With`) 검사 |
| `error_handlers.py` | 도메인 오류 → HTTP 상태·`application/problem+json` 매핑(401/403/409/422/429/503) |
| `use_case_provider.py`, `dependencies.py`, `request_info.py` | 유스케이스 주입 규약, 의존성, 클라이언트 IP 등 |

주요 API 접두어는 `/api/v1/` 입니다. 전체 목록은 `openapi.json` 또는 local의 `/docs`를 봅니다.

### 2.8 테스트 (`backend/tests/`)

| 폴더 | 내용 |
| --- | --- |
| `unit/` | domain·application(Fake Port 사용), infra(LDAP mock), web, 설정, 훅·게이트 스크립트 |
| `contracts/` | 같은 계약 테스트를 Fake와 실제 구현 양쪽에 실행 |
| `integration/` | 실제 PostgreSQL 임시 DB(마이그레이션, 행 잠금, 동시성) |
| `e2e/` | ASGI로 전 구간 호출. `permission_table.py`(엔드포인트×역할 표)와 열거 테스트가 새 엔드포인트의 권한 누락을 잡음 |
| `fakes/`, `support/`, `factories*.py` | Fake 저장소·스택, LDAP mock, 시드, 데이터 팩토리 |

테스트 함수명은 영문 ASCII(`test_<상황>_<기대결과>`). CI에서는 `REQUIRE_INTEGRATION_DB=1`로 DB 없이 건너뛰지 못하게 합니다.

### 2.9 인증·권한 흐름 요약

1. 최초 접속 시 admin이 없으면 `/setup`: ① AD 서버 등록(연결 확인 후 DB 저장) → ② AD 아이디·비밀번호로 첫 admin 등록(성공 시 자동 로그인). admin이 생기면 영구히 닫힙니다.
2. 이후 로그인: AD 바인드로 비밀번호 검증 → 앱에 등록된 활성 사용자만 세션 쿠키 발급. 실패 사유는 구분하지 않음(401), AD 장애는 503, 시도 제한은 429.
3. 요청마다 users 테이블에서 활성 여부와 역할을 다시 읽어 즉시 반영. user 역할은 조회만(쓰기 403).
4. admin은 사용자(AD 계정 id + 역할)를 추가·삭제만 하고 수정은 없음. AD 서버 설정은 설정 메뉴에서 변경.

## 3. 프런트엔드 (`frontend/`)

| 파일 | 의미 |
| --- | --- |
| `package.json` | 스크립트(`dev`, `build`, `lint`, `typecheck`, `test`, `gen:api`)와 pnpm 버전 고정 |
| `vite.config.ts` | 개발 서버(5173), `/api`를 8000번으로 프록시, Vitest(jsdom) 설정 |
| `eslint.config.js`, `tsconfig.json` | 린트·타입 설정 |
| `src/main.tsx`, `src/App.tsx` | 진입점, 라우팅(`/setup`은 인증 밖, `/users`·`/settings`는 admin 전용) |
| `src/shared/api/client.ts` | openapi-fetch 클라이언트(`X-Requested-With` 헤더 포함) |
| `src/shared/api/schema.d.ts` | **생성 파일**. `pnpm gen:api`로 `openapi.json`에서 만든 API 타입 |
| `src/shared/api/problem.ts` | 오류 응답(problem+json) 해석과 사용자 메시지 |
| `src/shared/ui/`, `format.ts`, `constants.ts` | 공통 UI(레이아웃, 폼 필드, 페이저, 검색창), 포맷터 |
| `src/shared/directory/` | AD 설정 입력 필드·검증(최초 설정과 설정 화면이 공유) |
| `src/features/auth/` | 로그인 화면, `RequireAuth`·`RequireAdmin`, 권한 훅 `usePermissions` |
| `src/features/setup/` | 최초 설정 마법사(AD 서버 → admin) |
| `src/features/users/`, `features/settings/` | admin 전용 사용자 관리, AD 설정 |
| `src/features/deals/` | 딜 목록·상세, 파이프라인 요약, 단계 변경·이력, 필터 |
| `src/features/customers/`, `partners/`, `actions/` | 고객·파트너 화면, 활동 검색 |
| `src/test/` | 테스트 유틸·픽스처. 각 `*.test.tsx`는 대상 옆에 위치 |

`user` 역할에는 쓰기 UI를 숨기지만 최종 판단은 서버가 합니다. 서버 상태는 TanStack Query로 관리합니다.

## 4. 인프라 (`infra/`)

| 파일 | 의미 |
| --- | --- |
| `build_release.sh` | 릴리스 번들 `build/neoine-sales-<tag>.tar.gz` 생성 |
| `server/bootstrap.sh` | 서버당 최초 1회(root). `neoine` 계정, 디렉터리, uv·Python, systemd·Nginx·sudoers 설치, `.env` 뼈대 |
| `server/deploy.sh` | 배포 본체(멱등, 실패 시 롤백) |
| `server/systemd/neoine-sales-api.service` | Uvicorn 서비스(127.0.0.1:8000, 하드닝) |
| `server/nginx/neoine-sales.conf` | 80→443 리다이렉트, 정적 파일 서빙, `/api` 프록시, 보안 헤더 |
| `server/sudoers/neoine-sales` | `neoine` 계정이 서비스 재시작만 할 수 있게 허용 |
| `server/config/config.{dev,product}.json` | 프런트 런타임 설정(비밀 없음, `/config.json`으로 제공) |
| `server/tests/test_deploy.sh` | deploy.sh 시나리오 9개 테스트 |

서버 디렉터리 구성(`/opt/neoine-sales`): `incoming/`(받은 번들), `releases/<tag>/`(릴리스), `current`(현재 릴리스 심볼릭 링크), `shared/config.json`, `.env`(비밀, 서버에서만 관리).

## 5. 개발·빌드

### 5.1 로컬 실행

```bash
cp backend/.env.example backend/.env       # DB 비밀번호 등 입력
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000 --app-dir src   # 터미널 1
cd frontend && corepack pnpm install && corepack pnpm dev        # 터미널 2 (http://localhost:5173)
```

local 프로파일은 로그인 화면에서 개발용 로그인(admin/sales/user)을 쓸 수 있습니다. corepack 서명 오류가 나면 `COREPACK_INTEGRITY_KEYS=0`을 앞에 붙입니다.

### 5.2 검증(게이트)

```bash
cd backend && uv run python scripts/run_gates.py     # ruff, format, mypy, import-linter, 파일 길이, pytest
cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build
bash infra/server/tests/test_deploy.sh               # 배포 스크립트 테스트
```

### 5.3 API 계약 갱신

백엔드 API를 바꾸면 반드시 함께 갱신하고 커밋합니다.

```bash
cd backend && uv run python scripts/export_openapi.py   # backend/openapi.json
cd frontend && pnpm gen:api                              # src/shared/api/schema.d.ts
```

### 5.4 마이그레이션

`cd backend && uv run alembic revision --autogenerate -m "..."` → 검토 → `uv run alembic upgrade head`. **local·dev는 자동 적용, product만 사람 승인 후** `deploy.sh`가 적용합니다. dev에 자동 적용되므로 항상 하위 호환(expand/contract)으로 씁니다. `downgrade`/`stamp`는 사용자 확인이 필요합니다.

### 5.5 릴리스 번들 만들기

`pnpm build`로 `frontend/dist`를 만든 뒤 `infra/build_release.sh <tag>`를 실행합니다. 번들에는 `backend/{src,alembic,alembic.ini,pyproject.toml,uv.lock}`, `frontend/dist`, `infra/server`, `VERSION`이 들어갑니다(테스트·개발 생성물 제외). 서버는 번들로 `uv sync --locked --no-dev`만 하므로 서버에서 빌드하지 않습니다.

## 6. CI/CD (`Jenkinsfile`)

Multibranch 파이프라인입니다. 모든 브랜치·PR은 검증만 하고, `main`에서만 번들 생성과 배포를 합니다.

| 단계 | 대상 | 내용 |
| --- | --- | --- |
| Verify (병렬) | 모든 브랜치 | **Backend**: `uv sync --locked`, ruff, format, mypy, lint-imports, 파일 길이, pytest(+커버리지, JUnit). **Infra scripts**: `bash -n`, `test_deploy.sh`. **Frontend**: `pnpm install --frozen-lockfile`, lint, typecheck, test, build(결과 stash) |
| Contract & Security | 모든 브랜치 | `openapi.json`·`schema.d.ts`가 코드와 같은지 `git diff --exit-code`, `pnpm audit`, `pip-audit`, `trivy`(CRITICAL/HIGH), `gitleaks` |
| Package | main | `build_release.sh`로 tar.gz 생성·보관(아티팩트 fingerprint) |
| Deploy: Dev | main | 번들과 `deploy.sh`를 SSH/scp로 dev 서버에 전달해 실행 → `/readyz` 확인. **마이그레이션 자동 적용** |
| Deploy: Product | main | `release-managers`의 **수동 승인(input)** 후, 운영 서버를 **한 대씩 순차 배포**(한 대라도 실패하면 중단) |

환경변수: `RELEASE_TAG`(커밋 12자), `TEST_DATABASE_ADMIN_URL`(CI용 PostgreSQL), `REQUIRE_INTEGRATION_DB=1`. 호스트 이름·자격 증명 ID(`deploy-ssh-dev`, `deploy-ssh-product`)·승인 그룹은 **예시 값**이므로 실제 환경에 맞게 바꿔야 합니다. 실패 시 메일을 보냅니다.

### 6.1 `deploy.sh <dev|product> <tag>` 동작

1. 입력 검증: 환경 이름, 태그 형식, 서버 `.env`의 `APP_PROFILE`이 대상 환경과 같은지(dev 설정이 product에 올라가는 사고 방지), 번들 존재.
2. 번들 풀기 → `uv sync --locked --no-dev` → `get_settings()`로 **설정 사전 검증**(필수 변수 누락·product 안전 조건 위반이면 전환 전에 중단).
3. 프런트 런타임 설정(`config.<env>.json`)을 `shared/config.json`으로 설치.
4. `alembic upgrade head` (실패하면 전환 전 중단).
5. `current` 심볼릭 링크를 원자적으로 교체하고 `systemctl restart neoine-sales-api`.
6. `/readyz`를 재시도하며 확인. 성공하면 오래된 릴리스 정리(최근 5개 + 현재 + 직전), **실패하면 직전 릴리스로 롤백**(코드만 되돌리므로 마이그레이션은 하위 호환이어야 함).

같은 태그로 다시 실행해도 안전합니다(멱등).

### 6.2 환경별 차이

| 항목 | local | dev | product |
| --- | --- | --- | --- |
| 실행 | 개발 서버 2개 | Nginx + systemd | Nginx + systemd (여러 대 순차) |
| 설정 위치 | `backend/.env` | 서버 `/opt/neoine-sales/.env` | 서버 `/opt/neoine-sales/.env` |
| 로그인 | 개발용 로그인 가능 | AD만 | AD만 |
| API 문서(`/docs`) | 열림 | 열림 | 닫힘 |
| 마이그레이션 | 수동/자동 | 배포 시 자동 | 승인 후 배포 시 |
| 쿠키 Secure | 끔(http) | 켬 | 켬(강제) |

### 6.3 운영 필수 절차와 주의

- **배포 직후 즉시 AD 서버와 admin을 등록**합니다. 설정되지 않은 상태로 방치하면 먼저 접속한 사람이 admin이 되거나 악의적인 LDAP 서버가 등록될 수 있습니다(위험 수용, 완화책 없음).
- 앱 서버에서 AD로 나가는 방화벽(LDAPS 636 또는 389+StartTLS)을 미리 엽니다.
- AD 설정을 바꾸기 전에 현재 값을 따로 기록합니다(변경 이력 없음).
- 이번 버전 배포 직후 기존 사용자는 로그인할 수 없고 최초 admin 등록부터 다시 합니다. 롤백이 필요하면 `role='user'` 세션 정리와, 서버 `.env`의 `APP_OIDC_*` 유지가 필요합니다.
- Nginx 뒤에서는 IP별 로그인 제한이 프록시 주소에 걸릴 수 있습니다(`X-Forwarded-For` 신뢰 정책 미정).

## 7. AI 하네스 (`.claude/`, `CLAUDE.md`)

- `CLAUDE.md`: 필수 규칙 요약, 검증 명령, 구현 순서, 변경 이력.
- `.claude/agents/`: `feature-planner` → `test-engineer` → `core-engineer` → `infra-engineer` → `web-engineer` → `frontend-engineer` → `quality-gate` → `code-reviewer`. 로직 구현은 이 순서로 각 역할이 담당하고 메인 세션은 조율만 합니다.
- `.claude/skills/`: `layer-architecture-rules`, `tdd-python-testing`, `config-and-secrets`(작업 전에 읽는 규칙).
- `.claude/hooks/`: `guard.py`(`.env`·`uv.lock` 접근 차단, product 대상 alembic 차단), `post_edit.py`(편집 후 자동 포맷).
- `.claude/settings.json`: 권한 규칙(사용자 소유, 임의 변경 금지).
- `artifacts/`: 계획·테스트·구현·게이트·리뷰 산출물(Git 제외).

## 8. 현재 한계와 미결정 사항

- 실제 AD(LDAPS 인증서 검증, StartTLS, 여러 DC 전환, 잠금 임계치)는 mock으로만 검증했습니다.
- 사용자 목록은 최대 50건(페이징 없음).
- `pyjwt`, `httpx`는 런타임에서 더 이상 쓰이지 않는 의존성이며 제거는 승인 대기입니다.
- Jenkinsfile의 호스트·자격 증명·승인 그룹은 예시 값입니다.
- Nginx의 도메인·인증서 경로(`sales.internal.example.com`)는 예시 값입니다.
