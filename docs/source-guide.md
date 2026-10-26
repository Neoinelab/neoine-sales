# neoine-sales 소스 구조 가이드

현재 구현된 소스가 무엇인지, 파일이 어디에 있고 무슨 뜻인지, 어떻게 빌드·배포하는지를 한 곳에 정리한 문서입니다.
규칙의 정본은 [개발 가이드](dev-guide.html), 요구사항과 구현 단계는 [PRD](prd.html), AI 하네스는 [하네스 가이드](harness-guide.html)입니다. 이 문서는 "지도" 역할만 합니다.

## 1. 한눈에 보기

영업 Deal 관리 웹 앱입니다. Deal(영업 기회)을 Status·Forecast·BANT·연락처(고객·파트너)와 함께 기록하고, Deal별 Action(진행사항·Next Action)·첨부 파일·변경 이력을 관리합니다. 미업데이트·기한 초과 Deal은 서버가 경고(Risk)로 계산합니다. PRD의 P0~P6, P8까지 구현했고(Forecast는 P6, Dashboard는 P4·2026-10-23) Reports(P7)만 메뉴만 있고 "준비 중"입니다.

| 영역 | 기술 |
| --- | --- |
| 백엔드 | Python 3.14, FastAPI, SQLAlchemy 2(async) + asyncpg, Alembic, ldap3, pydantic-settings, structlog |
| 프런트엔드 | React 19, TypeScript, Vite, React Router, TanStack Query v5, openapi-fetch, Chart.js 4.5.1 + react-chartjs-2 5.3.1(Dashboard 차트), Vitest |
| DB | PostgreSQL (DB명 `neoinesales`) |
| 인증 | AD(LDAP) 아이디·비밀번호 → 서버 세션(HttpOnly 쿠키). local·dev는 개발용 빠른 로그인(기본 켜짐, product는 불가) |
| 권한 | 역할 3종: `admin`(전부 + Admin 메뉴), `sales`(업무 쓰기), `user`(조회만) |
| 파일 | 첨부 파일은 서버 로컬 디스크. 저장 위치는 최초 설정·Admin에서 등록(DB 저장), 서버는 `/var/lib/neoine-sales`를 준비 |
| 패키지 | 백엔드 uv, 프런트엔드 pnpm(corepack) |
| CI/CD | Jenkins(Multibranch) → 릴리스 번들(tar.gz) → SSH로 서버에 `deploy.sh` 실행 |
| 서버 | on-prem Linux, Nginx(정적 파일 + `/api` 프록시) + systemd(`neoine-sales-api`), 컨테이너 없음 |

최상위 구조:

```
backend/     FastAPI 백엔드 (uv 관리)
frontend/    React 프런트엔드 (pnpm 관리)
infra/       릴리스 번들 스크립트, 서버 구성·배포 자산
docs/        개발 가이드, PRD, 하네스 가이드, 이 문서
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
| `infra` | Port 구현(PostgreSQL 저장소, LDAP, 로컬 파일 저장소, 시계, Deal code 발급) | 비즈니스 규칙 판단 금지 |
| `web` | HTTP ↔ 유스케이스 변환, 권한 적용, 오류 매핑 | SQL·트랜잭션·규칙 금지 |
| `container*.py` | 조립 지점(Composition Root). 유일하게 모든 계층을 import | - |

계층 위반은 `import-linter`(`pyproject.toml`의 `[tool.importlinter]`)가 막습니다. 파일은 300줄 이하(`scripts/check_file_length.py`).

### 2.2 `backend/` 최상위 파일

| 파일 | 의미 |
| --- | --- |
| `pyproject.toml` | 의존성, ruff·mypy·pytest·import-linter 설정의 **정본** |
| `uv.lock`, `.python-version` | 잠긴 의존성, Python 버전(3.14) |
| `.env.example` | 필요한 환경변수 이름 예시(실제 `.env`는 Git 제외, 읽지도 쓰지도 않음) |
| `alembic.ini`, `alembic/` | DB 마이그레이션. `versions/`에 리비전 22개, head는 `d4b8f6a2c013`(Solution 자유 텍스트, 2026-10-22). P0 이후는 단계별 단일 스키마 마이그레이션(코드·BANT Label → 연락처 → Deal 모델 v2 → Action 스냅숏 → 첨부 → 경고 기준 → Vendor·Solution → Action 유형 → Next Action 상태 → Deal users 필수 → bigint id(전체 초기화) → Forecast 스냅숏 → Solution 관리 목록 폐지·Deal Solution 필수 텍스트) |
| `openapi.json` | API 계약 파일. 코드와 다르면 테스트가 실패(드리프트 검사), 프런트 타입의 원본 |
| `scripts/run_gates.py` | 품질 게이트 6종 실행(기본은 단위 테스트만, `--full`이면 functional 포함). 결과: `artifacts/30-review/gate.md` |
| `scripts/check_file_length.py` | 파일 300줄 제한 검사 |
| `scripts/export_openapi.py` | `openapi.json` 생성 |

### 2.3 `src/app/` 진입점·설정·조립

| 파일 | 의미 |
| --- | --- |
| `main.py` | FastAPI 앱 팩토리 `create_app()`. 라우터 등록, CORS, 오류 처리기. `uvicorn app.main:app` |
| `config/base.py` | `Settings`: `APP_` 접두어 환경변수 필드(DB URL, 쿠키, 세션 TTL, 로그인 시도 제한 등) |
| `config/profiles.py` | 프로파일별 기본값과 안전 검증. `LocalSettings`/`DevSettings`/`ProductSettings`. product는 debug·docs 끄기, `cookie_secure`, JWT 비밀 32자 이상, Sentry DSN 필수. `dev_login`은 local·dev 기본 켜짐, product에서만 거부 |
| `config/__init__.py` | `get_settings()`: `APP_PROFILE`로 프로파일을 골라 설정을 읽는 유일한 진입점 |
| `container.py` | Composition Root. DB 엔진·세션 팩토리·시계를 소유하고 Deal·Action·연락처·경고 기준 유스케이스를 조립 |
| `container_auth.py` | 인증 유스케이스(로그인, 최초 설정, 로그아웃, 개발 로그인) 조립 |
| `container_admin.py` | admin 기능(사용자 관리, AD 설정) 조립 |
| `container_catalog.py` | 코드(Status·Forecast), BANT Label, Action 유형, Vendor 유스케이스 조립 |
| `container_action_type.py` | `Container`가 상속하는 Action 유형 유스케이스 위임 mixin(`container.py` 길이 분리) |
| `container_vendor.py` | `Container`가 상속하는 Vendor 유스케이스 위임 mixin(`container.py` 길이 분리) |
| `container_storage.py` | 저장 위치 설정과 첨부 유스케이스 조립(FileStorage 하나를 공유) |
| `container_dashboard.py` | `Container`가 상속하는 Dashboard 유스케이스(`GetDashboardSummary`) 조립 mixin(`DashboardUseCases`) |
| `container_time.py` | `Container`가 상속하는 서버 시각 유스케이스(`GetServerTime`, 기존 `Clock` 주입) 조립 mixin(`TimeUseCases`) |

### 2.4 `domain/` — 비즈니스 규칙

| 폴더 | 내용 |
| --- | --- |
| `common/` | 공통 엔티티 기반, 오류, 검증(`required_text` 등, NUL 문자 거부), 업무 날짜·업무 시각(`business_date.py`: `business_date`, `business_time`(같은 순간을 OS 로컬 오프셋으로), OS 로컬 시간대), 금액·원화 표기, 한국어 조사 |
| `deal/` | Deal 엔티티와 값 객체(금액, 견적, POC, BANT 선택), Deal code(`YYYYMMDD-XXXX`), Status·Forecast 동기화(`sync*.py`, `contract_completed` ⇔ `won`), 변경 이력 diff(`history.py`), 연/분기 기간, Owner 자격·삭제 권한(`policy.py`), 경고(`risk.py`: 기한 초과·미업데이트, Won/Lost 제외)와 Status 체류 일수 |
| `deal_action/` | Action(진행사항·Next Action·Due Date·Memo, Status/Forecast 스냅숏) 엔티티, 이력, 수정·삭제 권한(admin 전부, sales 본인만) |
| `contact/` | 연락처(고객·파트너) 엔티티·값 객체, 같은 사람 판정(`identity.py`), 입력 초안 병합(`draft.py`) |
| `code/` | Status·Forecast 코드 카탈로그(이름 정규화·중복·key 생성·순서 규칙) |
| `vendor/` | Vendor(Aggregate Root) 엔티티, 이름 규칙(앞뒤 공백 제거, 100자 이내, 대소문자 무시 전역 중복 금지), 사용 중 삭제 거부. ~~소속 Solution(1:N) 엔티티~~는 2026-10-22 변경으로 삭제 — Solution은 Deal의 필수 텍스트(`deal/values.py`의 `check_solution`, 200자 이내, Vendor와 독립) |
| `bant/` | BANT Label(카테고리별 선택지) 엔티티와 규칙(`find_label`: 대소문자 무시 이름 찾기) |
| `action_type/` | Action 유형 카탈로그(기본 8개 시드, 이름 1~50자·대소문자 무시 중복 금지, 사용 중 삭제 거부), `ActionTypeRef(id, name)` |
| `attachment/` | 첨부 파일 엔티티, 파일 이름·확장자 보안 규칙(`values.py`), 이력, 삭제·교체 권한 |
| `storage/` | 저장 위치 설정과 경로 값 객체(절대 POSIX 경로 검증·정규화) |
| `alert/` | 경고 기준 설정(미업데이트 기준 일수 1~365, 기본 14) |
| `dashboard/` | Dashboard 집계 조립 규칙: `status_pipeline.py`(Status 코드 순서대로 건수·금액, 없는 Status는 0), `quarter_closing.py`(Q1~Q4 × Forecast 열, Lost 제외, 분기 Open 합계·합계). Forecast 셀 계산은 `forecast/summary.py`의 `tally_row`를 함께 씀. 분기 판정은 `deal/period.py`의 `quarter_of` |
| `auth/` | `principal.py`(Role·Permission·Principal), `credentials.py`(LoginId·Password, 비밀번호는 로그에 마스킹), `session.py`, `login_failure.py`(시도 제한 카운터) |
| `user/` | 사용자 엔티티(연결이 있으면 퇴사 처리·없으면 물리 삭제, `UserRef` 표시 라벨과 역할, 마지막 로그인 시각), `policy.py`(자기 자신·마지막 admin 삭제 금지) |
| `directory/` | AD 설정 값 객체(`settings.py`), LDAP URL·필터 규칙 검증(평문 LDAP 금지, `{login_id}` 템플릿) |

### 2.5 `application/` — 유스케이스와 Port

- `ports/`: 외부와 통신하는 인터페이스. 저장소(`*_repository.py`: Deal·Deal 이력·Action·연락처·코드·BANT Label·Action 유형·Vendor·첨부·사용자·세션·로그인 실패·AD 설정·저장 위치 설정·경고 기준), `dashboard_repository.py`(`DashboardTallyRepository`: Status별·분기별 집계, `uow.dashboard`), `deal_outcome_filter.py`(`ForecastOutcomeFilter`: Deal 목록 `forecast_outcome` 필터 값), `unit_of_work.py`(트랜잭션 경계), `file_storage.py`(파일 저장), `deal_code_source.py`(Deal code 발급), `directory.py`(AD 인증기), `clock.py`, `pagination.py`
- `deal/`: 등록·조회·목록·수정·삭제와 삭제 영향(`deletion-impact`), 단일 변경 적용(`apply_change.py`·`sync_change.py`: Status·Forecast 동기화 확인), 변경 이력 기록·조회, 화면용 뷰(`views.py`: 서버가 `risk`·`status_days` 계산)
- `deal_action/`: Deal별 Action 등록·조회·수정·삭제(수행일시·담당자는 서버가 채움)
- `contact/`: 연락처 등록·수정·삭제·검색, 회사 목록·회사별 연락처, 사용처 확인
- `vendor/`: Vendor 목록(사용 수 포함)·등록·이름 변경·삭제(Deal이 쓰면 거부). Solution 유스케이스(`register_solution`·`rename_solution`·`delete_solution`)는 2026-10-22에 삭제
- `choice.py`: 카탈로그 선택(`CatalogChoice`: `{id}` 또는 `{name}` 중 하나). 없는 이름은 검증 통과 뒤 같은 트랜잭션에서 생성(Action 유형은 `deal_action/type_choice.py`, BANT는 `deal/bant_choice.py`)
- `action_type/`: Action 유형 목록(사용 수 포함)·등록·이름 변경·삭제(사용 중이면 거부)
- `code/`, `bant/`: 코드 등록·이름 변경·순서 변경·삭제(사용 중이면 거부)와 사용 현황, BANT Label 관리
- `attachment/`: 업로드·목록·다운로드·삭제, 저장 실패 시 정리(`storage_cleanup.py`)
- `storage/`, `alert/`, `directory/`: 저장 위치·경고 기준·AD 설정의 조회·확인·변경
- `dashboard/`: `criteria.py`(`DashboardCriteria`: Dashboard 숫자마다의 조건을 `DealQuery`로 정의하는 단일 출처, Drill-down URL과 1:1), `get_summary.py`(`GetDashboardSummary`: Forecast·Status·분기·주의 타일을 한 UoW에서 집계), `views.py`(응답 뷰)
- `auth/`: `directory_login.py`(AD 로그인), `authenticate.py`(요청마다 활성 사용자·역할 확인), `throttle.py`(로그인 시도 제한), `setup_directory.py`·`setup_storage.py`·`setup_first_admin.py`(최초 설정 3단계), `auth_status.py`, `dev_login.py`, `logout.py`, `issue_session.py`, `tokens.py`
- `time/`: `get_server_time.py`(`GetServerTime`·`ServerTimeView`: `Clock`을 한 번 읽어 서버 OS 로컬 오프셋 `now`와 업무 날짜 `today`를 돌려줌, DB 미사용, `GET /api/v1/time`)
- `user/`: 사용자 등록·삭제·목록(페이징), 사용자 선택 후보(`list_user_options.py`), 참조 해석

### 2.6 `infra/` — Port 구현체

| 파일 | 의미 |
| --- | --- |
| `db/base.py`, `db/models*.py` | SQLAlchemy 선언 베이스와 ORM 모델(`models_deal`·`models_contact`·`models_catalog`·`models_attachment`·`models_alert`·`models_auth` 등 영역별 분리) |
| `db/*_repository.py` | 각 저장소 Port의 PostgreSQL 구현. Deal은 `deal_mapping.py`(행 ↔ 엔티티), `deal_children.py`(파트너·BANT 자식 행), `deal_search.py`(목록 검색·필터), `deal_aggregates.py`(최근 Action 등 파생 값)로 나뉨. `deal_search.conditions`는 Deal 목록·Forecast·Dashboard 집계가 함께 쓰는 WHERE(Forecast 구분 `forecast_outcome` 조건 포함) |
| `db/dashboard_tally.py` | `DashboardTallyRepository` 구현(`SqlDashboardTallyRepository`). `deal_search.conditions` 재사용, 분기는 월별 group 후 파이썬에서 합산 |
| `db/unit_of_work.py` | 트랜잭션 단위 구현 |
| `db/like.py` | 키워드 검색용 LIKE 이스케이프 |
| `deal_code_source.py` | Deal code 발급 Port 구현 |
| `storage/local_file_storage.py` | FileStorage Port의 로컬 디스크 구현(`<root>/<deal_code>/<key>`, I/O는 스레드에서) |
| `auth/ldap.py`, `auth/ldap_errors.py` | ldap3 기반 AD 인증·연결 확인. 서버 URL을 순서대로 시도, 서버별 타임아웃, TLS 검증 필수, 사용자 본인 계정으로 바인드 |
| `system_clock.py` | `Clock` Port 구현 |

### 2.7 `web/` — HTTP 계층

| 파일/폴더 | 의미 |
| --- | --- |
| `routers/` | 엔드포인트. `deals.py`, `deal_actions.py`, `attachments.py`·`attachment_items.py`, `contacts.py`, `codes.py`, `bant_labels.py`, `action_types.py`, `vendors.py`, `alert_settings.py`, `forecast.py`, `dashboard.py`, `time.py`(`GET /api/v1/time`, 로그인 사용자), `users.py`, `user_options.py`, `settings_directory.py`, `settings_storage.py`, `auth*.py`(로그인·로그아웃·상태·최초 설정), `health.py`(`/healthz`, `/readyz`) |
| `schemas/` | 요청·응답 Pydantic 모델. 응답 시각 필드는 `server_datetime.py`의 `ServerDateTime`(서버 OS 로컬 오프셋으로 직렬화, 같은 순간·openapi 스키마 동일)을 쓰고 맨 `datetime`은 쓰지 않음(단위 테스트가 검사). `time.py`는 `ServerTimeResponse{now, today}` |
| `permissions.py` | `BusinessRouter`(sales 이상만 쓰기)와 `admin_router`(admin 전용)로 권한을 라우터 등록 시점에 적용 |
| `security.py` | 쿠키 세션 확인(`require_login`), CSRF 헤더(`X-Requested-With`) 검사 |
| `error_handlers.py` | 도메인 오류 → HTTP 상태·`application/problem+json` 매핑(400/401/403/404/409/422/429/503) |
| `content_disposition.py` | 첨부 다운로드의 파일 이름 헤더(RFC 5987) |
| `use_case_provider.py`, `dependencies.py`, `request_info.py` | 유스케이스 주입 규약, 의존성, 클라이언트 IP 등 |

주요 API(접두어 `/api/v1/`):

| 영역 | 경로 |
| --- | --- |
| Deal | `/deals`(목록·등록), `/deals/{code}`(조회·수정·삭제), `/deals/{code}/changes`(Status·Forecast 단일 변경), `/deals/{code}/history`, `/deals/{code}/deletion-impact` |
| Action | `/deals/{code}/actions`, `/deal-actions/{action_id}` |
| 첨부 | `/deals/{code}/attachments`, `/attachments/{id}`, `/attachments/{id}/download` |
| 카탈로그 | `/codes`, `/codes/order`, `/codes/usage`, `/bant-labels`, `/action-types`, `/vendors`(Solution 경로 `/vendors/{id}/solutions…` 3개는 2026-10-22 폐지. 조회는 로그인 사용자. 쓰기는 admin, 단 `/bant-labels`·`/action-types` 추가는 sales도 가능) |
| 연락처 | `/contacts`, `/contacts/companies`, `/contacts/by-company` |
| 설정(admin) | `/users`, `/settings/directory`, `/settings/storage`, `/alert-settings`(조회는 로그인 사용자 모두) |
| 인증 | `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/config`, `/auth/dev-login`, `/auth/setup/*` |
| Forecast·Dashboard | `/forecast/summary`, `/forecast/snapshots`, `/forecast/snapshots/{period}/summary`, `/dashboard/summary`(조회 전용, 로그인 사용자 모두) |
| 기타 | `/user-options`(사용자 선택 후보) |

전체 목록은 `openapi.json` 또는 local의 `/docs`를 봅니다.

### 2.8 테스트 (`backend/tests/`)

테스트는 두 종류뿐입니다(규칙은 개발 가이드 13장).

| 폴더 | 내용 |
| --- | --- |
| `unit/` | **단위 테스트**: 함수·클래스 하나. domain·application(Fake Port 사용), infra(Repository 계약·스키마·LDAP 어댑터, 실제 PostgreSQL 임시 DB), web, 설정, 훅·게이트 스크립트 |
| `functional/` | **functional test**: feature 하나의 end-to-end. 실제 Container와 PostgreSQL 임시 DB 위에서 HTTP API를 호출하고 BDD 형식(Given–When–Then)으로 씀. step 함수는 `functional/steps/`, AD는 Fake 디렉터리, 시계는 고정 시계(`api.clock`) |
| `e2e/` | 전 구간 NUL 문자 거부 점검(구 층에서 남은 것) |
| `fakes/`, `support/`, `factories*.py` | Fake 저장소·UoW·스택(Dashboard 집계 Fake는 `fakes/dashboard.py`), DB·시드·LDAP mock 도우미, 데이터 팩토리 |

개발 중에는 단위 테스트만 실행합니다(`run_gates.py` 기본값). functional을 포함한 전체는 Jenkins Verify 단계가 실행하고, 로컬 전체 실행은 `run_gates.py --full`입니다. 테스트 함수명은 영문 ASCII. CI에서는 `REQUIRE_INTEGRATION_DB=1`로 DB 없이 건너뛰지 못하게 합니다.

### 2.9 인증·권한 흐름 요약

1. 최초 접속 시 admin이 없으면 `/setup`: ① AD 서버 등록(연결 확인 후 DB 저장) → ② 첨부 파일 저장 위치 등록(쓰기 확인) → ③ AD 아이디·비밀번호로 첫 admin 등록(성공 시 자동 로그인). admin이 생기면 영구히 닫힙니다.
2. 이후 로그인: AD 바인드로 비밀번호 검증 → 앱에 등록된 활성 사용자만 세션 쿠키 발급. 실패 사유는 구분하지 않음(401), AD 장애는 503, 시도 제한은 429.
3. 요청마다 users 테이블에서 활성 여부와 역할을 다시 읽어 즉시 반영. user 역할은 조회만(쓰기 403). Action·첨부의 수정·삭제는 작성자 본인 또는 admin만.
4. admin은 Admin 메뉴에서 사용자(AD 계정 id + 역할) 추가·삭제, Deal 관리(Status·Forecast 코드, BANT Label, Action 유형, Vendor, 경고 기준), 연락처 관리, 연동 설정(AD 서버, 저장 위치)을 합니다.

## 3. 프런트엔드 (`frontend/`)

화면은 `data/*` 훅만 쓰고, 훅은 `gateway`를 통해 서버를 호출합니다. 앱에는 실제 HTTP 게이트웨이만 있고, 테스트는 같은 계약의 Fake로 바꿔 끼웁니다.

```
features/*  화면 ──▶ data/*  TanStack Query 훅 ──▶ gateway  (http 구현, 테스트에선 test/fake)
                         └──▶ shared/model  도메인 규칙·타입(서버와 같은 규칙)
```

| 파일/폴더 | 의미 |
| --- | --- |
| `package.json` | 스크립트(`dev`, `build`, `lint`, `typecheck`, `test`, `gen:api`)와 pnpm 버전 고정 |
| `vite.config.ts` | 개발 서버(5173), `/api`를 8000번으로 프록시, Vitest(jsdom, `src/test/setup.ts`) 설정 |
| `eslint.config.js`, `tsconfig.json` | 린트·타입 설정 |
| `src/main.tsx`, `src/App.tsx` | 진입점, 라우팅. `/login`·`/setup`은 인증 밖, `/deals/new`·`/deals/:code/edit`는 쓰기 권한, `/admin/*`는 admin 전용 |
| `src/gateway/` | 게이트웨이 진입점(`index.ts`: `gateway`·`clock`(서버 동기 시계)), 앱 시계 `clock.ts`(`createServerClock`: `/api/v1/time`으로 동기, 왕복 지연 절반 보정, 서버 오프셋으로 표기. 브라우저 시계를 읽는 유일한 파일, T-ARCH-03), 계약 타입(`types.ts`, `contract/*.contract.ts`), 실제 서버 구현 `http/`(영역별 호출, 서버 시각 `time.ts`과 `mappers/`의 응답 → 화면 모델 변환, 미구현 API 501 처리 `unsupported.ts`) |
| `src/data/` | 영역별 TanStack Query 훅(`deals`, `actions`, `attachments`, `contacts`, `codes`, `labels`, `alerts`, `users`, `settings`, `setup`, `auth`, `history`, `forecast`, `dashboard`, `time`(`useServerTimeSync`: 30분 주기·30분 경과 후 포커스 재동기) 등)과 쿼리 키(`queryKeys.ts`, Dashboard 키는 `forecast` 아래) |
| `src/shared/api/` | openapi-fetch 클라이언트(`client.ts`, `X-Requested-With` 헤더 포함), **생성 파일** `schema.d.ts`(`pnpm gen:api`), 오류 응답 해석(`problem.ts`) |
| `src/shared/model/` | 화면 모델 타입과 규칙: 권한, 경고 표시(`risk.ts`, 값은 서버 `risk` 사용), 기간, 금액, 파일 이름 규칙, 연락처 규칙, Status·Forecast 동기화, 목록 조건 기억(`dealListMemory.ts`) |
| `src/shared/ui/` | 공통 UI(레이아웃·메뉴, 모달, 탭, 콤보박스, 페이저, 배지, 검색창, "준비 중" 화면), 목록 복귀 경로 훅(`useDealListPath.ts`) |
| `src/shared/sync/`, `shared/contact/`, `shared/directory/` | Status·Forecast 동기화 확인 대화상자, 연락처 선택기, AD 설정 입력 필드 |
| `src/features/deals/list/` | Deals 목록(13열: Next Action·Due·Next Action 상태 분리, BANT 열은 2026-10-23 폐지되어 `bantSummary.ts` 삭제), 필터·키워드(“Forecast 구분” URL `outcome` 포함), Quick View, 경고 범례 |
| `src/features/deals/detail/` | Deal 상세: 요약 바(Status 체류 "N일째"), 정보·연락처·BANT 카드와 인라인 수정, Actions·History 탭, 첨부 패널, 삭제 |
| `src/features/deals/form/` | Deal 등록·수정 폼 |
| `src/features/admin/` | Admin 레이아웃과 탭: `users/`, `deal-management/`(Status·Forecast 코드, BANT Label, Action 유형, Vendor, 경고 기준), `contacts/`, `integrations/`(AD 서버, 저장 위치) |
| `src/features/auth/`, `features/setup/` | 로그인(local·dev는 역할별 빠른 로그인 3개), `RequireAuth`(로그인 확인 뒤 서버 시각 첫 동기 전에는 “불러오는 중…”)·`RequireWrite`·`RequireAdmin`, 최초 설정 마법사(AD → 저장 위치 → admin) |
| `src/features/dashboard/` | Dashboard 화면: `DashboardPage.tsx`(Status·Forecast 탭, `App.tsx`가 `React.lazy`로 별도 청크 로드), `DashboardFilters.tsx`, `dashboardParams.ts`(URL ↔ 필터), `drillDown.ts`(Deal 목록 이동 주소의 단일 출처), `Tiles.tsx`, `StatusTab.tsx`·`StatusChart.tsx`, `ForecastTab.tsx`·`QuarterChart.tsx`, `chartSetup.ts`(Chart.js 필요한 요소만 등록), `dashboard.css`. 게이트웨이는 `gateway/http/dashboard.ts`, 계약 `gateway/contract/dashboard.contract.ts`, Fake `test/fake/gateway/dashboard.ts` |
| `src/features/forecast/`, `features/placeholder/` | Forecast 화면(서버가 501이면 "준비 중"), Reports 자리 화면 |
| `src/test/` | 테스트 설정(`setup.ts`가 `vi.mock('../gateway')`로 Fake 주입, `vi.mock('react-chartjs-2')`로 `chartMock.tsx` 주입 — jsdom에 canvas가 없음), 테스트 전용 Fake 게이트웨이와 시드(`fake/`), 픽스처(`fixtures/`), 앱 렌더 도우미. 각 `*.test.ts(x)`는 대상 옆에 위치 |

화면의 지금·오늘은 `data/today`의 `useToday()`(서버 동기 시계)로만 읽고, 시각 표시는 `shared/format.ts`(`formatDateTime`·`formatStamp`·`formatDate`·`formatRelativeTime`)가 서버 문자열의 오프셋 그대로 보입니다(브라우저 시간대 미사용, `src/test/architecture.test.ts`의 T-ARCH-03이 검사).

`user` 역할에는 쓰기 UI를 숨기지만 최종 판단은 서버가 합니다. Deals 목록의 검색 조건은 사용자별로 탭 세션(sessionStorage)에 기억해 상세·폼·메뉴에서 돌아올 때 복원합니다.

## 4. 인프라 (`infra/`)

| 파일 | 의미 |
| --- | --- |
| `build_release.sh` | 릴리스 번들 `build/neoine-sales-<tag>.tar.gz` 생성 |
| `server/bootstrap.sh` | 서버당 최초 1회(root, 다시 실행해도 안전). `neoine` 계정, 디렉터리(첨부 저장용 `/var/lib/neoine-sales` 포함), uv·Python, systemd·Nginx·sudoers 설치, `.env` 뼈대 |
| `server/deploy.sh` | 배포 본체(멱등, 실패 시 롤백) |
| `server/systemd/neoine-sales-api.service` | Uvicorn 서비스(127.0.0.1:8000, 하드닝, 쓰기 허용은 `ReadWritePaths=/var/lib/neoine-sales`만) |
| `server/nginx/neoine-sales.conf` | 80→443 리다이렉트, 정적 파일 서빙, `/api` 프록시, 보안 헤더. 첨부 업로드 경로만 본문 101MB·타임아웃 300초 |
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

처음 접속하면 최초 설정 3단계(AD 서버 → 저장 위치 → admin)를 거칩니다. local·dev 프로파일은 로그인 화면의 빠른 로그인(관리자/영업/조회자)을 쓸 수 있습니다. 프런트 개발 서버도 항상 실제 백엔드를 호출하므로(목업 모드 없음) 백엔드를 함께 띄웁니다. corepack 서명 오류가 나면 `COREPACK_INTEGRITY_KEYS=0`을 앞에 붙입니다.

### 5.2 검증(게이트)

```bash
cd backend && uv run python scripts/run_gates.py     # ruff, format, mypy, import-linter, 파일 길이, pytest(단위만)
cd backend && uv run python scripts/run_gates.py --full   # functional 포함 전체(필요할 때만, 수 분 소요)
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

`cd backend && uv run alembic revision --autogenerate -m "..."` → 검토 → `uv run alembic upgrade head`. **local·dev는 자동 적용**(로컬 `./scripts/start-backend.sh --profile local|dev`가 시작 전에 `alembic upgrade head` 실행), **product만 사람 승인 후** `deploy.sh`가 적용합니다. product에서는 앱과 함께 배포되고 롤백은 코드만 되돌리므로 원칙은 하위 호환(expand/contract)입니다. 다만 개발 단계라 보존할 업무 데이터가 없어 P0~P3은 사용자 결정으로 예외(구 테이블 drop, 구 앱과 같은 DB 공존 불가, 앱과 같은 배포 전제)로 작성했습니다(`CLAUDE.md` 변경 이력). 운영 데이터가 생기면 이 예외는 끝납니다. local·dev의 `downgrade`/`stamp`는 확인 없이 실행할 수 있고(2026-10-20), product 대상 alembic 명령은 하네스가 거부합니다.

### 5.5 릴리스 번들 만들기

`pnpm build`로 `frontend/dist`를 만든 뒤 `infra/build_release.sh <tag>`를 실행합니다. 번들에는 `backend/{src,alembic,alembic.ini,pyproject.toml,uv.lock}`, `frontend/dist`, `infra/server`, `VERSION`이 들어갑니다(테스트·개발 생성물 제외). 서버는 번들로 `uv sync --locked --no-dev`만 하므로 서버에서 빌드하지 않습니다.

## 6. CI/CD (`Jenkinsfile`)

Multibranch 파이프라인입니다. 모든 브랜치·PR은 검증만 하고, `main`에서만 번들 생성과 product 배포(사람 승인 후)를 합니다. dev 자동 배포(`Deploy: Dev`)는 2026-10-20에 제거했습니다. dev DB는 로컬 `start-backend.sh --profile dev`로 쓰고, dev 서버가 필요하면 사람이 `deploy.sh dev`로 수동 배포합니다. 이 서버는 개발용 로그인이 기본으로 켜지므로(비밀번호 없이 admin) 여러 사람이 접근하는 서버라면 서버 `.env`에 `APP_DEV_LOGIN_ENABLED=false`를 넣습니다.

| 단계 | 대상 | 내용 |
| --- | --- | --- |
| Verify (병렬) | 모든 브랜치 | **Backend**: `uv sync --locked`, ruff, format, mypy, lint-imports, 파일 길이, pytest(+커버리지, JUnit). **Infra scripts**: `bash -n`, `test_deploy.sh`. **Frontend**: `pnpm install --frozen-lockfile`, lint, typecheck, test, build(결과 stash) |
| Contract & Security | 모든 브랜치 | `openapi.json`·`schema.d.ts`가 코드와 같은지 `git diff --exit-code`, `pnpm audit`, `pip-audit`, `trivy`(CRITICAL/HIGH), `gitleaks` |
| Package | main | `build_release.sh`로 tar.gz 생성·보관(아티팩트 fingerprint) |
| Deploy: Product | main | `release-managers`의 **수동 승인(input)** 후, 번들과 `deploy.sh`를 SSH/scp로 전달해 운영 서버를 **한 대씩 순차 배포**(한 대라도 실패하면 중단, 마이그레이션 적용) |

환경변수: `RELEASE_TAG`(커밋 12자), `TEST_DATABASE_ADMIN_URL`(CI용 PostgreSQL), `REQUIRE_INTEGRATION_DB=1`. 호스트 이름·자격 증명 ID(`deploy-ssh-product`)·승인 그룹은 **예시 값**이므로 실제 환경에 맞게 바꿔야 합니다. 실패 시 메일을 보냅니다.

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
| 실행 | 개발 서버 2개 | 로컬 `start-backend.sh --profile dev`(또는 수동 배포한 서버의 Nginx + systemd) | Nginx + systemd (여러 대 순차) |
| 설정 위치 | `backend/.env` | 로컬 `backend/.env.dev`(`APP_ENV_FILE`) / 서버 `/opt/neoine-sales/.env` | 서버 `/opt/neoine-sales/.env` |
| 로그인 | AD + 개발용 로그인(기본 켜짐) | AD + 개발용 로그인(기본 켜짐) | AD만(개발용 로그인 켤 수 없음) |
| API 문서(`/docs`) | 열림 | 열림 | 닫힘 |
| 마이그레이션 | 시작 스크립트가 자동 | 시작 스크립트가 자동(수동 서버 배포 시 `deploy.sh dev`) | 승인 후 배포 시 |
| 쿠키 Secure | 끔(http) | 켬 | 켬(강제) |

### 6.3 운영 필수 절차와 주의

- **배포 직후 즉시 최초 설정 3단계(AD 서버 → 저장 위치 → admin)를 마칩니다.** 설정되지 않은 상태로 방치하면 먼저 접속한 사람이 admin이 되거나 악의적인 LDAP 서버가 등록될 수 있습니다(위험 수용, 완화책 없음).
- 앱 서버에서 AD로 나가는 방화벽(LDAPS 636 또는 389+StartTLS)을 미리 엽니다.
- AD 설정을 바꾸기 전에 현재 값을 따로 기록합니다(변경 이력 없음).
- `infra/server/**`가 바뀐 릴리스(systemd·Nginx·저장 디렉터리)는 서버에서 `bootstrap.sh`를 다시 실행하고 `nginx -t`로 확인합니다. `deploy.sh`는 이 파일들을 설치하지 않습니다.
- 업무 날짜(Deal code 날짜, 경고·체류 일수)와 화면에 보이는 날짜·시각(응답 시각의 오프셋, 앱 시계)은 서버 OS 로컬 시간대를 따르므로 서버 시간대를 업무 시간대(예: `Asia/Seoul`)로 맞춥니다(`timedatectl`로 확인). 서버 시간대가 화면 표시 시간대도 됩니다.
- 첨부 파일은 DB 밖(저장 위치 디렉터리)에 있으므로 DB와 함께 백업합니다.
- Nginx 뒤에서는 IP별 로그인 제한이 프록시 주소에 걸릴 수 있습니다(`X-Forwarded-For` 신뢰 정책 미정).

## 7. AI 하네스 (`.claude/`, `CLAUDE.md`)

- `CLAUDE.md`: 필수 규칙 요약, 검증 명령, 구현 순서, 변경 이력.
- `.claude/agents/`: `feature-planner` → `test-engineer` → `core-engineer` → `infra-engineer` → `web-engineer` → `frontend-engineer` → `quality-gate` → `code-reviewer`. 로직 구현은 이 순서로 각 역할이 담당하고 메인 세션은 조율만 합니다.
- `.claude/skills/`: `layer-architecture-rules`, `tdd-python-testing`, `config-and-secrets`(작업 전에 읽는 규칙).
- `.claude/hooks/`: `guard.py`(`.env`·`uv.lock` 접근 차단, product 대상 alembic 차단), `post_edit.py`(편집 후 자동 포맷).
- `.claude/settings.json`: 권한 규칙(사용자 소유, 임의 변경 금지).
- `artifacts/`: 계획·테스트·구현·게이트·리뷰 산출물(Git 제외).

## 8. 현재 한계와 미결정 사항

- Reports(PRD P7)는 미구현입니다. 메뉴와 경로만 있고 "준비 중"을 보여 줍니다. Dashboard 차트의 실제 그리기는 테스트에서 mock하므로 사람이 브라우저에서 확인합니다.
- 실제 AD(LDAPS 인증서 검증, StartTLS, 여러 DC 전환, 잠금 임계치)는 mock으로만 검증했습니다.
- 서버 시간대 설정과 첨부 저장 디렉터리 백업은 운영 절차로만 보장합니다(앱이 검사하지 않음).
- Jenkinsfile의 호스트·자격 증명·승인 그룹은 예시 값입니다.
- Nginx의 도메인·인증서 경로(`sales.internal.example.com`)는 예시 값입니다.
