# 플랫폼 공통   (feature 코드: PL, 상태: 확정(2026-11-09 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/main.py`, `app/web/{security,permissions,error_handlers,request_info}.py`, `app/web/routers/{health,responses}.py`, `app/web/schemas/{ids,common}.py`, `app/domain/auth/principal.py`, `app/config/**`, `backend/scripts/export_openapi.py`, `frontend/src/App.tsx`, `features/auth/Require*.tsx`, `shared/ui/Layout.tsx`, `features/admin/AdminLayout.tsx`, `shared/model/permissions.ts`, `shared/api/{client,problem}.ts`, `gateway/http/request.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다.
>
> 2026-11-09 사용자 결정: **경로별 역할 허용 여부는 각 feature 문서 2.5가 정본**이고, PL은 "모든 경로가 권한 표에 있다", 역할 3종 공통 규칙, HTTP 관례, OpenAPI 계약, 화면 접근 가드만 맡습니다. 하네스·배포 도구 테스트는 feature 대상이 아닙니다.

## 1. 개요

- 목적: 모든 API와 화면이 같은 방식으로 인증·권한을 판정하고, 같은 형식으로 오류를 돌려주고, 같은 계약 파일(`backend/openapi.json`)을 공유하게 한다. 다른 feature 문서는 이 문서의 규칙 번호(`PL-R번호`)를 가리킨다.
- 사용자(역할): `admin`, `sales`, `user`(로그인한 사용자), 미인증 방문자, 운영자(상태 확인), 개발자(새 API 추가·설정).
- 범위
  - 역할 3종의 권한 묶음, 경로 분류와 역할 가드, 판정 순서, "모든 경로가 권한 표에 있다" 검사
  - CSRF 헤더 검사, Problem(`application/problem+json`) 오류 형식과 도메인 오류 매핑, 404·405, 요청 형식 오류(422)
  - id 경로·본문·쿼리 파라미터 형식, NUL 문자 입력의 공통 처리(500 금지)
  - `/healthz`·`/readyz`, API 문서 노출, CORS
  - `openapi.json` 드리프트와 공통 문서화 규칙(401·403·422, id 표기, 비밀번호 필드 없음)
  - 프로파일 설정 선택·검증(`app.config`)
  - 화면: 라우트 가드(`RequireAuth`·`RequireWrite`·`RequireAdmin`), 라우트 리다이렉트, 상단 메뉴, Admin 레이아웃, 화면의 역할 판단 함수, 요청 공통 헤더, API 오류 정규화·문구
- 범위 밖(다른 feature)
  - 각 경로의 역할 허용 여부와 도메인 권한(본인·Owner 판정 등) → 소유 feature 2.5
  - 세션 발급·만료·로그인·로그아웃·시도 제한(429)·`/auth/me` 응답 → AU, 최초 설정과 "설정 필요 시 `/setup`으로" → SU, 사용자 아이콘 메뉴·`/me` → ME
  - 응답 시각 표기(`ServerDateTime`)·서버 시계 동기 → TM, 스케줄러 설정(`scheduler_enabled`·간격) → FC, 로그인 시도 제한 설정 → AU
  - 각 오류 type의 구체 문구(예: `storage-unavailable`, `invalid-report`, 칸별 NUL 문구) → 소유 feature 2.8
  - feature별 OpenAPI 필드 검사(사용자 응답 필드, AD 요청 필드, Deal 경로·태그, 연락처 409 등) → 해당 feature
  - 하네스 도구·배포 스크립트·compose 설정 검사(`test_forwarded_ips_policy` 등) → feature 아님
  - 처리되지 않은 예외(500)의 응답 형식 → 정의하지 않음(현재 FastAPI 기본값)
- 관련 화면·메뉴: 상단 바(브랜드·주 메뉴·사용자 메뉴 자리), Admin 공통 틀, 모든 보호 화면의 진입 가드

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 역할 | `admin`·`sales`·`user` 셋. 사용자 행의 `role` |
| 권한 | `read`·`write`·`administer`. 역할이 가진 권한 묶음(PL-R1)으로 판정한다 |
| 보호 경로 | 로그인(세션 쿠키)이 필요한 경로. 공개 경로가 아닌 모든 `/api/v1/**` 경로 |
| 공개 경로 | 로그인 없이 부르는 경로: `/healthz`, `/readyz`, `/api/v1/auth/config`, `/api/v1/auth/login`, `/api/v1/auth/logout`, `/api/v1/auth/setup/**` |
| 상태 변경 메서드 | `GET`·`HEAD`·`OPTIONS`가 아닌 메서드(`POST`·`PUT`·`PATCH`·`DELETE`) |
| 역할 가드 | 라우터가 경로에 거는 권한 검사. 업무 쓰기 가드(`require_write`)와 관리자 가드(`require_admin`) 두 가지 |
| 도메인 권한 | 유스케이스·도메인이 대상마다 판정하는 권한(본인 Action만 수정 등). 소유 feature가 정한다 |
| 권한 표 | (메서드, 경로 템플릿) → 허용 역할 집합(또는 공개)의 표. 각 feature 2.5의 합본이며 테스트 데이터로 둔다 |
| Problem | RFC 9457 `application/problem+json` 오류 본문 |
| kind | Problem `type`의 마지막 조각(예: `forbidden`) |
| 계약 파일 | 저장소에 커밋된 `backend/openapi.json` |
| 프로파일 | 실행 환경 `local`·`dev`·`product` |

### 2.2 데이터 모델

PL은 저장 데이터가 없다. 관련 값 정의:

- `Role`(StrEnum): `admin`, `sales`, `user`. `Permission`(StrEnum): `read`, `write`, `administer`.
- `Principal`: `user_id`, `subject`(로그인 아이디), `email`, `name`, `role`. `can(permission)`은 역할의 권한 묶음을 따른다.
- id 타입(`app/web/schemas/ids.py`, 상한 `MAX_ID` = 2^53−1 = 9,007,199,254,740,991): `PathId`(경로, 정수 1~MAX_ID), `BodyId`(본문, `StrictInt` 1~MAX_ID), `QueryId`(쿼리, 정수 1~MAX_ID, 문자열 `"7"`은 7로 받음).
- `Problem`(문서용 스키마): `type`, `title`, `status`, `detail`, `instance`, `errors`(선택, 객체 목록).
- 설정(`Settings`, 접두어 `APP_`): 2.3의 PL-R24~PL-R28.

### 2.3 비즈니스 규칙

역할과 권한 표
- **PL-R1** 역할은 3개이고 권한 묶음은 다음과 같다: `admin` = `read`·`write`·`administer`, `sales` = `read`·`write`, `user` = `read`. 화면도 같은 판단을 한다(PL-R36).
- **PL-R2** 모든 경로는 다음 분류 중 하나에 속한다(어느 경로가 어느 분류인지는 소유 feature 2.5가 정한다).

  | 분류 | 허용 | 역할 가드 |
  | --- | --- | --- |
  | 공개 | 로그인 없이 누구나 | 없음 |
  | 로그인한 모든 역할(내 정보 계열: `/auth/me`, `/me/**`) | admin·sales·user | 없음 |
  | 업무 조회 | admin·sales·user | 없음(조회 메서드) |
  | 저장 리포트(`/reports`, `/reports/{id}/**`) | admin·sales·user | 없음(대상별 권한은 RS 도메인 판정) |
  | 업무 쓰기 | admin·sales | 업무 쓰기 가드 |
  | 관리자 전용 | admin | 관리자 가드(또는 소유 feature가 정한 도메인 판정, 예: LC-R15) |

  `POST /reports/query`는 POST지만 저장하지 않는 조회라 업무 조회로 분류한다(역할 가드 없음).
- **PL-R3** 앱이 공개한 엔드포인트(OpenAPI 경로 중 `/healthz`, `/readyz`, `/api/v1/**`의 모든 (메서드, 경로 템플릿))는 권한 표에 정확히 한 번 있고, 권한 표에는 앱에 없는 엔드포인트가 없다. 새 엔드포인트를 추가하면 소유 feature 2.5와 권한 표에 한 줄을 함께 더한다. 권한 표의 관리자 전용 행은 admin만, 업무 쓰기 행은 user를 포함하지 않는다.

판정 순서
- **PL-R4** 보호 경로의 판정 순서는 다음과 같다(앞 단계에서 거절되면 뒤 단계는 하지 않는다): ① 미인증 401 → ② CSRF 403 `csrf`(상태 변경 메서드만) → ③ 역할 가드 403 `forbidden` → ④ 요청 형식 422 `request-validation`(경로·쿼리·본문, id 형식 포함) → ⑤ 대상 없음 404 → ⑥ 도메인 권한 403 → ⑦ 상태 충돌 409. 소유 feature가 예외를 정할 수 있다(예: LC-R15 계약 삭제는 ⑥이 ⑤보다 먼저). 공개 경로 중 CSRF를 거는 경로(PL-R9)는 CSRF가 맨 먼저다.
- **PL-R5** 보호 경로에 세션이 없거나 쓸 수 없으면(쿠키 없음·만료·무효·사용자 없음·퇴사 — 판정 세부는 AU) 401 `unauthenticated`, `detail` = "로그인이 필요합니다"다. 미인증이면 CSRF 헤더 유무와 무관하게 401이다.
- **PL-R6** 업무 쓰기 가드가 걸린 경로(업무 라우터의 상태 변경 메서드 전부)는 `write` 권한이 필요하다. `user`는 403 `forbidden`, `detail` = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이며, 요청 본문·id 형식 검증과 대상 존재 확인보다 먼저 거절된다. 역할 가드가 없는 경로(저장 리포트, `POST /reports/query`, 내 정보 계열)는 `user`도 이 가드에 막히지 않는다.
- **PL-R7** 관리자 가드가 걸린 경로는 `administer` 권한이 필요하다. `sales`·`user`는 403 `forbidden`, `detail` = "관리자 권한이 필요합니다"이며 본문 검증보다 먼저 거절된다. 관리자 가드와 업무 쓰기 가드가 함께 걸린 경로는 관리자 가드가 먼저다. 관리자 전용을 도메인 판정으로 하는 경로(LC-R15)는 소유 feature 문구를 쓰며, 그 경우 `sales` 거절 문구에도 "관리자"가 들어간다("계약 삭제는 관리자만 할 수 있습니다."). 관리자 전용 경로의 거절 문구는 모두 "관리자"를 포함하거나(admin 가드·도메인 판정) 읽기 전용 문구다(user가 업무 쓰기 가드에 먼저 막힌 경우).
- **PL-R8** 허용된 역할은 역할 가드에 막히지 않는다: 허용 역할로 부르면 401·403(역할 가드)이 아닌 응답(성공, 422, 404, 409 등 그 경로 feature의 결과)이 온다.

CSRF
- **PL-R9** 상태 변경 메서드 요청은 `X-Requested-With` 헤더가 있고 값이 비어 있지 않아야 한다. 없거나 빈 값이면 403 `csrf`, `detail` = "요청 헤더(X-Requested-With)가 필요합니다"다. 적용 범위: 모든 업무 라우터(로그인 검사 뒤), `POST /auth/login`, `POST /auth/logout`, `/auth/setup/**` 전부. 조회 메서드는 헤더 없이 된다. 헤더 값의 내용은 검사하지 않는다.

오류 형식
- **PL-R10** 오류 응답은 `Content-Type: application/problem+json`이고 본문은 `type`(= `https://neoine-sales.example/problems/<kind>`), `title`(kind별 고정 제목, 2.8), `status`(HTTP 상태와 같은 수), `detail`(문구), `instance`(요청 경로, 쿼리 제외)를 가진다. 일부 kind는 `errors`(목록)나 `stage`를 더 싣는다.
- **PL-R11** 도메인 오류는 다음 순서로 처음 맞는 항목으로 바뀌고 `detail`은 오류 메시지 그대로다: `AuthenticationError` 401 `unauthenticated` → `TooManyAttemptsError` 429 `too-many-attempts` → `AccessDeniedError` 403 `forbidden` → `NotFoundError` 404 `not-found` → `AttachmentNameTakenError` 409 `file-exists` → `AlreadyExistsError` 409 `already-exists` → `InvalidReferenceError` 422 `invalid-reference` → `InvalidValueError` 422 `invalid-value` → `InvalidStateError` 409 `invalid-state` → 그 밖의 `DomainError` 400 `domain-error`. 전용 핸들러가 있는 오류(2.8 표)는 그 핸들러가 먼저다.
- **PL-R12** 요청 형식 오류(경로·쿼리·본문 파라미터 검증 실패)는 422 `request-validation`, `detail` = "요청 형식이 올바르지 않습니다", `errors` = 검증 오류 목록(각 항목의 `type`·`loc`·`msg`; 입력값 `input`·`ctx`·`url`은 싣지 않는다)이다.
- **PL-R13** 없는 경로는 404, 경로에 없는 메서드는 405이고 둘 다 Problem(kind `http-error`, `detail`은 상태 문구 그대로 "Not Found"·"Method Not Allowed")이다. HTTP 예외가 실은 헤더(예: `Allow`)는 응답에 그대로 붙는다.
- **PL-R14** 내부 원인(접속 주소·DB 드라이버 문구·서버 응답)은 응답에 싣지 않는다: `not-ready`·`directory-unavailable`·`report-timeout`은 고정 문구(2.8)이고 원인은 서버 로그에만 남는다. 도메인 오류가 아닌 예외의 메시지는 Problem `detail`이 되지 않는다.

id·입력 형식
- **PL-R15** id 경로 파라미터는 1 이상 2^53−1 이하의 정수다. 정수가 아닌 값(`abc`, `1.5`, UUID, `0x10`, `1e3`)과 범위 밖 값(`0`, `-1`, 2^53, 2^63)은 유스케이스까지 가지 않고 422 `request-validation`이다(500이 아니다). 상한값(2^53−1)은 유스케이스까지 가고, 없는 id면 그 feature의 404다. 본문 id는 JSON 정수만 받는다(문자열·불리언·실수는 422 `request-validation`). 쿼리 id는 문자열 정수(`"7"`)를 받는다. Deal은 id 대신 `{code}` 경로를 쓴다(형식은 DE·DD).
- **PL-R16** 텍스트 입력의 NUL 문자(`\x00`)는 500이 아니라 422다: 텍스트 칸·검색어는 소유 feature 검증에 따라 422 `invalid-value`(문구는 소유 feature 2.8), 정수 등 형식이 정해진 칸은 422 `request-validation`. 어느 경우도 `detail`에 DB 드라이버·SQL 문구(`asyncpg`, `sqlalchemy`, `postgres`, `dbapierror`, `0x00`)가 나오지 않는다.

상태 확인·문서·CORS
- **PL-R17** `GET /healthz`는 공개이며 항상 200 `{"status": "ok"}`다(문서 노출 설정·DB와 무관). `GET /readyz`는 공개이며 의존 자원 확인(`check_ready`, DB 등)이 되면 200 `{"status": "ready"}`, 안 되면 503 `not-ready` "서비스가 아직 요청을 받을 수 없습니다"이고 원인(접속 정보 등)은 응답에 없다.
- **PL-R18** API 문서(`/docs`, `/redoc`, `/openapi.json`)는 설정 `enable_docs`가 true일 때만 열리고(로그인 불필요) false면 셋 다 404다. 기본값은 local·dev true, product false(product는 true를 거부, PL-R26).
- **PL-R19** CORS는 설정 `cors_allowed_origins`의 출처만 허용한다(자격 증명 포함, 모든 메서드·헤더). 허용 출처의 사전 요청(OPTIONS)은 200이고 `Access-Control-Allow-Origin`에 그 출처가 돌아온다. 목록에 없는 출처에는 이 헤더가 없다.

OpenAPI 계약
- **PL-R20** 계약 파일 `backend/openapi.json`은 앱이 만드는 계약(`create_app(...).openapi()`, local 설정·Fake 유스케이스·`enable_docs` true)과 항상 같다. API를 바꾸면 `uv run python scripts/export_openapi.py`로 다시 만들고 프런트엔드는 `pnpm gen:api`로 타입을 다시 생성해 함께 커밋한다.
- **PL-R21** 공통 문서화: `/api/v1/auth/**`를 뺀 모든 `/api/v1` 엔드포인트는 401 응답을 문서화하고, 파라미터나 요청 본문이 있으면 422도 문서화한다. 보호 경로 전부(내 정보 계열 포함)는 401을 문서화한다. 업무 쓰기·관리자 전용 엔드포인트는 403 응답을 `Problem` 스키마로 문서화한다. 모든 역할이 쓰는 업무 조회 엔드포인트는 403을 문서화하지 않는다.
- **PL-R22** 계약에 `"format": "uuid"`가 없다. id 이름(`id`, `user_id`, `owner_user_id`, `contact_id`, `vendor_id`, `action_type_id`, `actor_user_id`, `created_by_user_id`, `action_id`, `attachment_id`, `type_id`, `code_id`, `label_id`, `ordered_ids`)의 속성·파라미터는 정수(또는 정수 배열, null 허용)이고, id 경로 파라미터는 `minimum` 1·`maximum` 2^53−1을 문서화한다.
- **PL-R23** 어떤 응답 스키마(참조하는 하위 스키마 포함)에도 이름에 `password`가 들어간 값 필드가 없다(바꿀 수 있는지를 알리는 boolean 플래그는 예외). 요청의 비밀번호 칸 표기(`format: password`, `writeOnly`)는 소유 feature(AU·SU·IN·US·ME)가 정한다.

설정(프로파일)
- **PL-R24** 프로파일은 `APP_PROFILE`(`local`·`dev`·`product`, 환경변수 또는 env 파일)로 고르고 없으면 `local`이다. 다른 값이면 기동 즉시 실패한다. 읽을 env 파일은 `APP_ENV_FILE`(현재 디렉터리 기준 경로)이고 없으면 `.env`다. `APP_ENV_FILE`로 지정한 파일이 없으면 "APP_ENV_FILE로 지정한 env 파일이 없습니다: <경로>"로 실패한다. 환경변수는 항상 파일보다 우선한다. 변수 이름은 `APP_` 접두어이며 알 수 없는 변수는 무시한다(예: 폐지된 `APP_DEV_LOGIN_ENABLED`, 예전 OIDC 변수).
- **PL-R25** 모든 프로파일에서 `APP_DATABASE_URL`(PostgreSQL DSN), `APP_JWT_SECRET`, `APP_SETTINGS_ENCRYPTION_KEY`가 필수이며 없으면 기동이 실패한다. 암호화 키는 URL-safe base64(`A-Za-z0-9_-`, 끝 `=` 패딩)로 인코딩한 32바이트여야 하고 아니면 "Fernet 키 형식(URL-safe base64로 인코딩한 32바이트)이어야 합니다"로 실패한다. `APP_REDIS_URL`은 선택이며 주면 Redis DSN이어야 한다.
- **PL-R26** product는 다음을 모두 만족해야 기동하고, 하나라도 어기면 어긴 항목 문구를 "; "로 이어 실패한다: debug·enable_docs·db_echo 꺼짐("debug/enable_docs/db_echo는 product에서 꺼야 합니다"), cookie_secure true("cookie_secure는 true여야 합니다"), CORS에 `*` 없음("CORS에 '*'를 허용할 수 없습니다"), jwt_secret 32자 이상("jwt_secret은 32자 이상이어야 합니다"), 암호화 키를 풀었을 때 `.env.example`의 예시 키와 같은 바이트가 아님("settings_encryption_key에 예시 키를 쓸 수 없습니다"), sentry_dsn 있음("sentry_dsn이 필요합니다"). local·dev는 예시 키를 허용한다.
- **PL-R27** 비밀 값(jwt_secret, 암호화 키, sentry_dsn)은 설정 객체의 표현(repr)과 검증 오류 문구에 나오지 않는다.
- **PL-R28** 프로파일 기본값: local은 debug·문서 노출 켬, 로그 DEBUG·console, cookie_secure false, db_echo true, DB 풀 5, workers 1. dev는 문서 노출 켬, 로그 DEBUG·json, debug false, Sentry 추적 비율 1.0. product는 문서 꺼짐, 로그 INFO·json, cookie_secure true, workers 4, 추적 비율 0.1. 공통 기본: 세션 유지 8시간, DB 풀 10. (스케줄러 기본값은 FC, 로그인 시도 제한 기본값은 AU.)

화면(frontend)
- **PL-R29** 보호 화면(아래 PL-R33 표)은 `RequireAuth` 안에 있다. 내 정보(`/auth/me`)를 읽는 동안 "불러오는 중…"을 보이고, 401이면 `/login`으로 바꾼다(이력 교체). 401이 아닌 오류면 오류 배너만 보이고 공통 레이아웃을 그리지 않는다. 성공하면 서버 시각 동기(TM) 뒤 공통 레이아웃(상단 바 + 화면)을 그린다. 최초 설정이 필요할 때 `/login`이 `/setup`으로 보내는 동작은 SU 규칙이다.
- **PL-R30** Deal 등록·수정 화면(`/deals/new`, `/deals/:dealCode/edit`)은 `RequireWrite` 안에 있다. `canWrite`가 아니면(user) Deals 목록(`/deals`)으로 바꾼다.
- **PL-R31** Admin 화면(`/admin/**`)은 `RequireAdmin` 안에 있다. admin이 아니면 Deals 목록으로 바꾸고 Admin 틀을 그리지 않는다.
- **PL-R32** 라우트: `/login`·`/setup`은 가드 없는 공개 화면이다. `/`는 `/deals`로, `/admin`은 `/admin/users`로 바꾼다. 옛 주소 `/users` → `/admin/users`, `/settings` → `/admin/integrations`. 정의되지 않은 주소(예: 폐지된 `/customers`, `/partners`, `/actions`)는 `/`로 보내 결국 Deals 목록이 된다(목록의 기본 조건 주소는 DL). 라우트는 `App.tsx` 한 곳에서만 정의한다.
- **PL-R33** 보호 화면과 화면 가드:

  | 화면 | 가드 | 열 수 있는 역할 |
  | --- | --- | --- |
  | `/deals`, `/deals/:dealCode`, `/contracts`, `/partner-activities`, `/dashboard`, `/forecast`, `/reports`, `/reports/new`, `/reports/:id`, `/reports/:id/edit`, `/me` | RequireAuth | 모든 역할 |
  | `/deals/new`, `/deals/:dealCode/edit` | RequireAuth + RequireWrite | admin·sales |
  | `/admin/users`, `/admin/deal`, `/admin/contacts`, `/admin/integrations` | RequireAuth + RequireAdmin | admin |

  화면 안의 버튼 노출·대상별 권한은 소유 feature 2.7이다.
- **PL-R34** 상단 바: 브랜드는 프런트엔드 정적 자산 `frontend/public/images/salesX.png`를 웹 경로 `/images/salesX.png`로 표시하고 홈(`/`) 링크로 동작한다. OS 직접 실행 환경에서는 Nginx가 정적 파일을 따로 처리하지 않고 이 경로를 포함한 모든 프런트 요청을 Vite로 프록시하며, Vite가 `public` 자산을 응답한다. "NEOINE 영업관리" 문구는 표시하지 않는다. 주 메뉴(`navigation` 이름 "주 메뉴")는 모든 역할에 Deals(`/deals`, 실제 링크는 기억된 목록 주소 — DL), 계약관리(`/contracts`), 파트너 Activity(`/partner-activities`), Dashboard(`/dashboard`), Forecast(`/forecast`), Reports(`/reports`) 순서 6개이고 admin에게만 맨 끝에 Admin(`/admin`)을 더한다. 좁은 화면의 `메뉴 열기` 버튼은 메뉴를 펼치고(`aria-expanded`) 메뉴 항목을 고르면 닫힌다. 사용자 메뉴는 ME다.
- **PL-R35** Admin 틀: 제목(h1) "Admin > Settings", 왼쪽 서브 메뉴(`navigation` 이름 "Admin 메뉴") 4개 — 사용자 관리(`/admin/users`), Deal 관리(`/admin/deal`), contacts 관리(`/admin/contacts`), 외부연동(`/admin/integrations`). 현재 화면의 서브 메뉴는 `aria-current="page"`이고 누르면 그 화면으로 간다.
- **PL-R36** 화면의 역할 판단 함수(`shared/model/permissions.ts`): `canWrite` = admin·sales, `isAdmin`·`canAccessAdmin`·`canManageMasterData` = admin, `visibleMenu` = PL-R34 순서. 화면은 이 함수로 버튼·메뉴를 숨기지만 정본 판정은 서버다(화면이 숨겨도 서버가 PL-R6·R7로 거절한다). 대상별 판단 함수(`canDeleteDeal`, `canEditAction`, `canDeleteAttachment`, `canEditMeeting`, 리포트 함수, `canBeOwner`)는 소유 feature 규칙이다.
- **PL-R37** 화면의 API 오류 문구(`ApiError`): Problem이면 `detail`을 그대로 쓰고, `errors`에 `loc` 배열이 있는 항목이 있으면 `<detail> — <loc의 첫 조각을 뺀 경로를 .으로 이음>: <msg>`(여러 개는 ", ")를 붙인다. `loc`가 없는 항목은 건너뛴다(오류를 던지지 않는다). Problem이 아닌 403은 "이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.", 그 밖의 Problem이 아닌 실패는 "요청에 실패했습니다 (<상태>)"다. `ApiError`가 아닌 오류를 문구로 바꾸면 "네트워크 오류가 발생했습니다. 잠시 후 다시 시도하세요."다. `errorFields`는 `errors[].location`의 첫 조각(문자열)만 모은다(칸 강조용, 문구는 다시 만들지 않는다).
- **PL-R38** 화면의 모든 API 요청은 쿠키를 함께 보내고(`credentials: 'include'`) `X-Requested-With: neoine-web` 헤더를 붙인다.
- **PL-R39** 게이트웨이(`gateway/http/request.ts`)는 실패를 모두 `ApiError`로 던진다: 서버 kind를 화면 kind로 바꾼다(`invalid-value`·`request-validation`·`invalid-reference` → `validation`, `already-exists`·`invalid-state` → `conflict`, `unauthenticated` → `unauthorized`, 나머지는 그대로). 서버에 닿지 못하면 상태 0, 문구 "서버에 연결할 수 없습니다."(네트워크 오류 원문 숨김). 본문이 있어야 하는 성공 응답에 본문이 없으면 상태 502, 문구 "서버 응답을 해석할 수 없습니다.". 204는 본문 없이 성공이다.

### 2.4 상태와 전이

없음(판정 순서는 PL-R4).

### 2.5 권한

경로별 허용 역할은 각 feature 2.5가 정본이다. PL이 정하는 공통 판정:

| 상황 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| 공개 경로 | 가능 | 가능 | 가능 | 가능 |
| 로그인한 모든 역할 경로·업무 조회·저장 리포트 | 401 | 가능 | 가능 | 가능 |
| 업무 쓰기 경로 | 401 | 403 읽기 전용(본문·존재 검사 전) | 가능 | 가능 |
| 관리자 전용 경로 | 401 | 403(관리자 문구 또는 읽기 전용 문구) | 403(문구에 "관리자") | 가능 |
| 상태 변경 메서드에 CSRF 헤더 없음 | 401(로그인 검사가 먼저) | 403 `csrf` | 403 `csrf` | 403 `csrf` |
| 화면: 보호 화면 | `/login`으로 | 열림 | 열림 | 열림 |
| 화면: Deal 등록·수정 | `/login`으로 | `/deals`로 | 열림 | 열림 |
| 화면: Admin | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

### 2.6 API 계약

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/healthz` | — | 200 `{"status": "ok"}` | — |
| GET `/readyz` | — | 200 `{"status": "ready"}` | 503 `not-ready` |
| GET `/docs`, `/redoc`, `/openapi.json` | — | 200(문서 노출 켬) | 404(문서 노출 끔) |
| 모든 보호 경로 | 세션 쿠키 `neoine_session`, 상태 변경 메서드는 `X-Requested-With` | 경로별(소유 feature) | 401 `unauthenticated`, 403 `csrf`, 403 `forbidden`, 422 `request-validation` + 경로별 |
| 없는 경로 / 없는 메서드 | — | — | 404 / 405 `http-error` |

- 오류 본문은 PL-R10 형식, 오류 매핑은 PL-R11·2.8.
- id 경로 파라미터 `PathId`(1~2^53−1), 본문 `BodyId`, 쿼리 `QueryId`(PL-R15).
- 계약 파일 갱신 절차는 PL-R20.

### 2.7 화면 동작

PL-R29~PL-R39. 화면은 `App.tsx`의 라우트와 세 가드만으로 접근을 막고, 서버 403·401은 각 화면이 PL-R37 문구로 보인다(401을 받은 보호 화면은 내 정보 재조회 결과에 따라 `/login`으로 간다).

### 2.8 오류와 메시지

| 상황 | 상태·kind | title | detail(문구) |
| --- | --- | --- | --- |
| 미인증 | 401 `unauthenticated` | Unauthenticated | 로그인이 필요합니다 |
| CSRF 헤더 없음 | 403 `csrf` | CSRF Check Failed | 요청 헤더(X-Requested-With)가 필요합니다 |
| user의 업무 쓰기 | 403 `forbidden` | Forbidden | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |
| admin 아닌 사용자의 관리자 경로 | 403 `forbidden` | Forbidden | 관리자 권한이 필요합니다 |
| 요청 형식 | 422 `request-validation` | Request Validation Failed | 요청 형식이 올바르지 않습니다 (+ `errors`) |
| 없는 경로 / 메서드 | 404 / 405 `http-error` | HTTP Error | Not Found / Method Not Allowed |
| 준비 안 됨 | 503 `not-ready` | Service Not Ready | 서비스가 아직 요청을 받을 수 없습니다 |
| 도메인 오류(PL-R11) | 401·429·403·404·409·422·400 | Unauthenticated, Too Many Attempts, Forbidden, Not Found, File Exists, Already Exists, Invalid Reference, Invalid Value, Invalid State, Domain Error | 오류 메시지 그대로(소유 feature) |

전용 핸들러(구체 문구는 소유 feature): `directory-verification-failed` 422 + `stage`(IN·SU), `directory-unavailable` 503 고정 문구 "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"(AU·IN), `storage-unavailable` 503(AT·LC·IN), `report-timeout` 503 고정 문구(RQ), `invalid-report` 422 + `errors[{location, code, message}]`(RQ·RS·RC), 파트너 미팅 일괄 입력 `invalid-value` 422 + `errors[{location, message}]`(PA), 칸 오류(`InvalidFieldError`·약한 비밀번호·현재 비밀번호 틀림) `invalid-value` 422 + `errors[{location, message}]`(AU·US·ME). 그 밖의 kind 제목: Invalid Report, Report Timeout, Directory Unavailable, Directory Verification Failed, Storage Unavailable.

화면 문구: PL-R37·PL-R39.

## 3. Business use case

### PL-UC1 보호 API 호출과 권한 판정
- 행위자: 미인증 방문자, admin·sales·user
- 사전 조건: 경로가 권한 표에 있다(PL-R3)
- 기본 흐름: 요청 → 세션 확인 → (상태 변경이면) CSRF 확인 → 역할 가드 → 요청 형식 → 유스케이스(PL-R4)
- 대안: 역할 가드가 없는 경로는 user도 통과(PL-R6)
- 예외: 미인증 401, CSRF 403, 역할 403, 형식 422(PL-R5~R9, R12, R15)
- 결과: 허용 역할은 그 feature의 결과를 받고, 아니면 판정 순서상 첫 거절을 받는다

### PL-UC2 새 API 추가 시 계약 유지
- 행위자: 개발자
- 기본 흐름: 라우터 추가 → 소유 feature 2.5와 권한 표에 행 추가 → `export_openapi.py`·`pnpm gen:api` → 커밋(PL-R3·R20·R21)
- 예외: 권한 표에 없거나 계약 파일이 다르면 테스트가 실패한다
- 결과: 모든 경로가 표에 있고 계약 파일이 앱과 같다

### PL-UC3 오류 응답 받기
- 행위자: 화면(게이트웨이), API 호출자
- 기본 흐름: 서버가 Problem을 돌려준다(PL-R10~R16) → 게이트웨이가 `ApiError`로 정규화(PL-R39) → 화면이 문구를 보인다(PL-R37)
- 예외: 서버에 닿지 못함·Problem이 아닌 본문·빈 성공 본문
- 결과: 사용자는 서버 문구 또는 고정 문구를 본다. 내부 원인은 보이지 않는다(PL-R14)

### PL-UC4 운영자의 상태 확인
- 행위자: 운영자(로그인 없음), 컨테이너 헬스체크
- 기본 흐름: `/healthz`·`/readyz`를 부른다(PL-R17)
- 예외: 의존 자원 실패 → 503 `not-ready`, 원인 비노출
- 결과: 생존·준비 여부

### PL-UC5 서버 기동 시 설정 검증
- 행위자: 운영자·개발자(서버 시작)
- 기본 흐름: 프로파일·env 파일 선택 → 필수 값·형식 → product 안전 검사(PL-R24~R28)
- 예외: 잘못된 프로파일, 없는 env 파일, 필수 값 없음, 키 형식 오류, product 위험 설정 → 기동 실패(비밀 값 미출력)
- 결과: 검증된 설정으로 앱이 뜬다. 문서 노출·CORS·쿠키 보안은 설정을 따른다(PL-R18·R19)

### PL-UC6 화면 진입과 메뉴
- 행위자: 미인증 방문자, admin·sales·user
- 기본 흐름: 주소를 연다 → 가드 판정(PL-R29~R33) → 상단 메뉴·Admin 틀(PL-R34·R35)
- 대안: 옛 주소·없는 주소는 리다이렉트(PL-R32)
- 예외: 미인증 `/login`, 권한 없음 `/deals`, 내 정보 오류 배너
- 결과: 역할에 맞는 화면과 메뉴

## 4. BDD 테스트 케이스

요청자 예시: BOSS(admin), KIM(sales), VIEWER(user), 익명(로그인 안 함). "권한 표"는 각 feature 2.5의 합본 테스트 데이터다. 경로 템플릿의 id 자리는 형식은 맞지만 없는 값(Deal은 `20260101-ZZZZ`)으로 채운다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| PL-001 | 역할 3종은 정해진 권한 묶음만 가진다 | PL-R1, PL-UC1 | backend | `domain/test_role_permissions.py::test_role_has_exactly_three_members`<br>`domain/test_role_permissions.py::test_role_allows_exactly_the_permissions_in_the_matrix`<br>`domain/test_role_permissions.py::test_principal_can_follows_its_role` |
| PL-002 | 앱이 공개한 모든 엔드포인트가 권한 표에 있고 표에만 있는 엔드포인트는 없다 | PL-R3, PL-UC2 | backend | `web/test_permission_matrix.py::test_permission_table_covers_every_endpoint_of_the_app` |
| PL-003 | 로그인하지 않고 보호 경로를 부르면 모두 401이다 | PL-R5, PL-R4, PL-UC1 | backend | `web/test_permission_matrix.py::test_anonymous_requests_to_protected_routes_are_all_401` |
| PL-004 | 허용된 역할은 어느 보호 경로에서도 역할 가드에 막히지 않는다 | PL-R8, PL-R2, PL-UC1 | backend | `web/test_permission_matrix.py::test_allowed_roles_are_never_stopped_by_the_role_guard` |
| PL-005 | user가 업무 쓰기 경로를 부르면 읽기 전용 403이다 | PL-R6, PL-UC1 | backend | `web/test_permission_matrix.py::test_user_on_business_write_routes_gets_the_read_only_403` |
| PL-006 | user의 쓰기 거절은 본문 검증·존재 확인보다 먼저다 | PL-R6, PL-R4, PL-UC1 | backend | `web/test_permission_matrix.py::test_user_write_rejection_comes_before_body_validation_and_lookup` |
| PL-007 | admin이 아닌 사용자가 관리자 전용 경로를 부르면 403이다 | PL-R7, PL-UC1 | backend | `web/test_permission_matrix.py::test_non_admins_on_admin_only_routes_get_403` |
| PL-008 | sales의 관리자 경로 거절은 본문 검증보다 먼저이고 문구에 "관리자"가 있다 | PL-R7, PL-R4, PL-UC1 | backend | `web/test_permission_matrix.py::test_sales_admin_route_rejection_comes_before_body_validation` |
| PL-009 | 역할 가드가 없는 쓰기 경로는 user도 403이 아니다 | PL-R6, PL-R2, PL-UC1 | backend | `web/test_permission_matrix.py::test_write_routes_without_a_role_guard_do_not_reject_user` |
| PL-010 | 미인증 요청은 CSRF 헤더가 없어도 401이 먼저다 | PL-R4, PL-R5, PL-R9, PL-UC1 | backend | `web/test_csrf_rule.py::test_unauthenticated_request_is_401_even_without_the_csrf_header` |
| PL-011 | 로그인한 사용자의 상태 변경 요청에 CSRF 헤더가 없으면 403 csrf다 | PL-R9, PL-UC1 | backend | `web/test_csrf_rule.py::test_signed_in_state_change_without_the_csrf_header_is_403_and_stores_nothing` |
| PL-012 | CSRF 헤더 값이 비어 있으면 헤더가 없는 것과 같다 | PL-R9, PL-UC1 | backend | `web/test_csrf_rule.py::test_empty_csrf_header_value_is_the_same_as_no_header` |
| PL-013 | 조회 요청은 CSRF 헤더 없이도 된다 | PL-R9, PL-UC1 | backend | `web/test_csrf_rule.py::test_read_requests_do_not_need_the_csrf_header` |
| PL-014 | 공개 인증 경로(로그인·로그아웃·최초 설정)도 CSRF 헤더가 필요하다 | PL-R9, PL-R4, PL-UC1 | backend | `web/test_csrf_rule.py::test_public_auth_routes_also_need_the_csrf_header` |
| PL-015 | CSRF 검사는 역할 가드보다 먼저다 | PL-R4, PL-R9, PL-UC1 | backend | `web/test_csrf_rule.py::test_csrf_check_comes_before_the_role_guard` |
| PL-016 | 오류 응답은 Problem 형식이고 instance는 요청 경로다 | PL-R10, PL-UC3 | backend | `web/test_http_conventions.py::test_error_response_is_a_problem_with_the_request_path_as_instance` |
| PL-017 | 도메인 오류는 종류별 상태·kind·문구로 바뀐다 | PL-R11, PL-UC3 | backend | `web/test_domain_error_mapping.py::test_domain_errors_become_problems_by_their_kind` |
| PL-018 | 요청 형식 오류는 공통 문구와 오류 목록을 주고 입력값을 되돌리지 않는다 | PL-R12, PL-UC3 | backend | `web/test_http_conventions.py::test_request_validation_error_lists_errors_without_echoing_the_input` |
| PL-019 | 없는 경로는 404 Problem이다 | PL-R13, PL-UC3 | backend | `web/test_http_conventions.py::test_unknown_route_is_a_404_problem` |
| PL-020 | 허용되지 않은 메서드는 405 Problem이다 | PL-R13, PL-UC3 | backend | `web/test_http_conventions.py::test_wrong_method_is_a_405_problem` |
| PL-021 | 정수가 아닌 id 경로 값은 422다 | PL-R15, PL-UC1 | backend | `web/test_id_params.py::test_a_non_integer_path_id_is_a_request_validation_error` |
| PL-022 | 0·음수·상한 초과 id 경로 값은 500이 아니라 422다 | PL-R15, PL-UC1 | backend | `web/test_id_params.py::test_zero_negative_and_too_large_path_ids_are_rejected_not_500` |
| PL-023 | 상한 id(2^53−1)는 유스케이스까지 가서 404다 | PL-R15, PL-UC1 | backend | `web/test_id_params.py::test_the_largest_allowed_path_id_reaches_the_use_case` |
| PL-024 | 본문 id는 JSON 정수만 받는다 | PL-R15, PL-UC1 | backend | `web/test_body_id.py::test_a_body_id_that_is_not_a_json_integer_in_range_is_422`<br>`web/test_body_id.py::test_the_largest_body_id_passes_the_format_check` |
| PL-025 | 텍스트 검색어·등록 본문의 NUL 문자는 500이 아니라 422 invalid-value다 | PL-R16, PL-R14, PL-UC3 | backend | `web/test_nul_input.py::test_nul_in_a_search_keyword_or_a_registration_body_is_422_invalid_value` |
| PL-026 | 정수 칸의 NUL 문자는 422 request-validation이다 | PL-R16, PL-UC3 | backend | `web/test_nul_input.py::test_nul_in_an_integer_filter_is_422_request_validation` |
| PL-027 | 생존 확인은 로그인 없이 200 ok다 | PL-R17, PL-UC4 | backend | `web/test_health_routes.py::test_liveness_answers_200_ok_without_login` |
| PL-028 | 의존 자원이 응답하면 준비 확인은 200 ready다 | PL-R17, PL-UC4 | backend | `web/test_health_routes.py::test_readiness_is_200_ready_when_the_dependency_answers`<br>`infra/test_readiness_database.py::test_readiness_is_200_ready_when_the_real_database_answers` |
| PL-029 | 의존 자원이 실패하면 준비 확인은 503이고 원인을 감춘다 | PL-R17, PL-R14, PL-UC4 | backend | `web/test_health_routes.py::test_readiness_is_503_and_hides_the_cause_when_the_dependency_fails`<br>`infra/test_readiness_database.py::test_readiness_is_503_without_leaking_the_cause_when_the_database_is_down` |
| PL-030 | 문서 노출이 켜져 있으면 API 문서와 계약을 열 수 있다 | PL-R18, PL-UC5 | backend | `web/test_http_conventions.py::test_docs_and_contract_are_open_when_docs_are_enabled` |
| PL-031 | 문서 노출이 꺼져 있으면 문서 경로는 404이고 생존 확인은 그대로다 | PL-R18, PL-R17, PL-UC5 | backend | `web/test_http_conventions.py::test_docs_are_hidden_when_disabled_but_liveness_stays` |
| PL-032 | 허용된 출처의 CORS 사전 요청은 허용된다 | PL-R19, PL-UC5 | backend | `web/test_http_conventions.py::test_cors_preflight_from_an_allowed_origin_is_allowed` |
| PL-033 | 허용되지 않은 출처에는 CORS 허용 헤더가 없다 | PL-R19, PL-UC5 | backend | `web/test_http_conventions.py::test_cors_preflight_from_another_origin_has_no_allow_header` |
| PL-034 | 커밋된 계약 파일은 앱이 만드는 계약과 같다 | PL-R20, PL-UC2 | backend | `web/test_openapi_contract.py::test_committed_openapi_matches_the_application_contract` |
| PL-035 | 인증 API를 뺀 모든 엔드포인트가 401과(입력이 있으면) 422를 문서화한다 | PL-R21, PL-UC2 | backend | `web/test_openapi_contract.py::test_every_endpoint_except_auth_documents_401_and_422_when_it_has_input` |
| PL-036 | 보호 경로는 모두 401을 문서화한다 | PL-R21, PL-UC2 | backend | `web/test_openapi_contract.py::test_every_protected_route_documents_401` |
| PL-037 | 업무 쓰기·관리자 전용 엔드포인트는 403을 Problem 스키마로 문서화한다 | PL-R21, PL-UC2 | backend | `web/test_openapi_contract.py::test_write_and_admin_endpoints_document_403_with_the_problem_schema` |
| PL-038 | 모든 역할이 쓰는 조회 엔드포인트는 403을 문서화하지 않는다 | PL-R21, PL-UC2 | backend | `web/test_openapi_contract.py::test_read_endpoints_for_every_role_do_not_document_403` |
| PL-039 | 계약의 id는 정수이고 uuid 표기가 없으며 경로 id는 범위를 문서화한다 | PL-R22, PL-UC2 | backend | `web/test_openapi_ids.py::test_the_contract_has_no_uuid_format`<br>`web/test_openapi_ids.py::test_every_id_property_is_an_integer`<br>`web/test_openapi_ids.py::test_every_id_path_and_query_parameter_is_an_integer`<br>`web/test_openapi_ids.py::test_id_path_parameters_document_the_allowed_range` |
| PL-040 | 어떤 응답 스키마에도 비밀번호 값 필드가 없다 | PL-R23, PL-UC2 | backend | `web/test_openapi_contract.py::test_no_response_schema_has_a_password_value_field` |
| PL-041 | 프로파일을 정하지 않으면 local이고 잘못된 프로파일은 즉시 실패한다 | PL-R24, PL-UC5 | backend | `test_settings.py::test_defaults_to_local_profile_when_profile_is_not_set`<br>`test_settings.py::test_unknown_profile_fails_fast`<br>`test_settings.py::test_profile_can_be_read_from_dotenv_file` |
| PL-042 | APP_ENV_FILE로 env 파일을 고르고 없는 파일이면 경로를 알리며 실패하고 환경변수가 이긴다 | PL-R24, PL-UC5 | backend | `test_settings_env_file.py::test_dotenv_is_read_when_env_file_is_not_set`<br>`test_settings_env_file.py::test_env_file_variable_selects_the_file_and_ignores_dotenv`<br>`test_settings_env_file.py::test_missing_env_file_fails_with_its_path_in_the_message`<br>`test_settings_env_file.py::test_profile_environment_variable_wins_over_env_file_profile` |
| PL-043 | 알 수 없는 옛 변수는 무시한다 | PL-R24, PL-UC5 | backend | `test_settings.py::test_dev_login_variable_is_ignored_in_every_profile`<br>`test_settings.py::test_settings_have_no_oidc_fields_or_properties`<br>`test_settings.py::test_oidc_variables_left_in_the_environment_are_ignored`<br>`test_settings.py::test_oidc_variables_in_a_dotenv_file_are_ignored` |
| PL-044 | 필수 값이 없으면 모든 프로파일에서 기동이 실패한다 | PL-R25, PL-UC5 | backend | `test_settings.py::test_missing_required_variable_fails_in_every_profile`<br>`test_settings.py::test_redis_is_not_required`<br>`test_settings.py::test_redis_url_is_parsed_when_given`<br>`test_settings.py::test_invalid_redis_url_is_rejected`<br>`test_settings_encryption_key.py::test_missing_encryption_key_fails_in_every_profile` |
| PL-045 | 형식이 틀린 암호화 키는 값을 보이지 않고 실패한다 | PL-R25, PL-R27, PL-UC5 | backend | `test_settings_encryption_key.py::test_the_jwt_secret_is_not_reused_as_the_encryption_key`<br>`test_settings_encryption_key.py::test_malformed_encryption_key_fails_without_echoing_the_value`<br>`test_settings_encryption_key.py::test_example_key_with_a_stray_character_is_a_format_error` |
| PL-046 | 안전한 product 설정은 통과한다 | PL-R26, PL-UC5 | backend | `test_settings.py::test_product_accepts_valid_settings`<br>`test_settings.py::test_product_starts_without_any_login_variables` |
| PL-047 | 위험한 product 설정은 어긴 항목을 알리며 거부된다 | PL-R26, PL-UC5 | backend | `test_settings.py::test_product_rejects_unsafe_settings`<br>`test_settings.py::test_product_requires_sentry_dsn` |
| PL-048 | 예시 암호화 키는 local·dev에서만 쓸 수 있다 | PL-R26, PL-UC5 | backend | `test_settings_encryption_key.py::test_product_rejects_example_encryption_key`<br>`test_settings_encryption_key.py::test_local_and_dev_accept_the_example_key`<br>`test_settings_encryption_key.py::test_product_compares_the_example_key_by_decoded_bytes`<br>`test_settings_encryption_key.py::test_example_key_constant_matches_env_example` |
| PL-049 | 비밀 값은 설정 표현에 나오지 않는다 | PL-R27, PL-UC5 | backend | `test_settings.py::test_secret_values_are_not_exposed_in_repr`<br>`test_settings.py::test_every_secret_stays_out_of_the_product_settings_text`<br>`test_settings_encryption_key.py::test_a_valid_key_is_accepted_and_kept_secret` |
| PL-050 | 프로파일마다 정해진 기본값을 쓴다 | PL-R28, PL-UC5 | backend | `test_settings.py::test_each_profile_has_its_documented_defaults`<br>`test_settings.py::test_dev_profile_uses_json_logs_and_debug_off`<br>`test_settings.py::test_session_ttl_default_and_secrets_stay_hidden` |
| PL-051 | 화면: 로그인하지 않은 방문자는 보호 화면에서 로그인 화면으로 간다 | PL-R29, PL-UC6 | frontend | `App.test.tsx > 로그인하지 않은 방문자가 /deals를 열면 로그인 화면으로 간다`<br>`features/auth/RequireAuth.setup.test.tsx > 로그인하지 않은 방문자가 %s를 열면 최초 설정이 끝난 뒤에는 로그인 화면으로 간다` |
| PL-052 | 화면: 내 정보 조회가 401이 아닌 오류면 오류 배너만 보이고 레이아웃이 없다 | PL-R29, PL-UC6 | frontend | `features/auth/RequireAuth.error.test.tsx > shows only an error banner for %s and keeps the address` |
| PL-053 | 화면: 첫 주소(/)는 Deals 목록으로 간다 | PL-R32, PL-UC6 | frontend | `App.test.tsx > /는 Deals 목록으로 간다` |
| PL-054 | 화면: 정의되지 않은 주소와 폐지된 주소는 Deals 목록으로 간다 | PL-R32, PL-UC6 | frontend | `App.test.tsx > 폐지된 주소 %s는 Deals 목록으로 간다` |
| PL-055 | 화면: 옛 사용자 관리·설정 주소는 Admin 새 주소로 간다 | PL-R32, PL-UC6 | frontend | `App.test.tsx > 옛 주소 %s는 admin에게 %s로 이동한다` |
| PL-056 | 화면: sales·user는 Admin 화면에서 Deals 목록으로 간다 | PL-R31, PL-UC6 | frontend | `App.test.tsx > %s는 Admin 화면에서 Deals 목록으로 간다`<br>`features/admin/AdminLayout.test.tsx > sends a %s user away from every Admin page (T-ADMIN-14)` |
| PL-057 | 화면: admin이 /admin을 열면 사용자 관리로 간다 | PL-R31, PL-R32, PL-UC6 | frontend | `App.test.tsx > admin이 /admin을 열면 사용자 관리로 간다` |
| PL-058 | 화면: Deal 등록·수정 화면은 sales·admin만 열고 user는 Deals 목록으로 간다 | PL-R30, PL-UC6 | frontend | `App.test.tsx > Deal 등록·수정 화면은 sales와 admin만 열 수 있다` |
| PL-059 | 화면: Deal 상세·Forecast·Dashboard는 모든 역할이 연다 | PL-R33, PL-UC6 | frontend | `App.test.tsx > %s는 Deal 상세·Forecast·Dashboard를 열 수 있다` |
| PL-060 | 화면: sales·user의 주 메뉴는 6개이고 Admin이 없다 | PL-R34, PL-UC6 | frontend | `App.test.tsx > %s의 주 메뉴는 여섯 개이고 Admin이 없다` |
| PL-061 | 화면: admin의 주 메뉴는 끝에 Admin이 더해진다 | PL-R34, PL-UC6 | frontend | `App.test.tsx > admin의 주 메뉴는 끝에 Admin이 더해진다` |
| PL-062 | 화면: 주 메뉴를 누르면 그 화면으로 간다 | PL-R34, PL-UC6 | frontend | `App.test.tsx > 주 메뉴를 누르면 그 화면으로 간다` |
| PL-063 | 화면: Admin 틀은 제목과 서브 메뉴 4개를 보인다 | PL-R35, PL-UC6 | frontend | `features/admin/AdminLayout.test.tsx > shows the title and the four sub menus` |
| PL-064 | 화면: Admin 서브 메뉴는 현재 화면을 표시하고 누르면 이동한다 | PL-R35, PL-UC6 | frontend | `features/admin/AdminLayout.test.tsx > marks the current sub menu and shows its page at %s`<br>`features/admin/AdminLayout.test.tsx > moves between pages with the sub menu` |
| PL-065 | 화면: 역할 판단 함수는 쓰기·관리자·메뉴를 역할대로 판단한다 | PL-R36, PL-R1, PL-UC6 | frontend | `shared/model/permissions.test.ts > 쓰기와 관리자와 메뉴` |
| PL-066 | 화면: 모든 API 요청은 CSRF 헤더와 쿠키를 보낸다 | PL-R38, PL-R9, PL-UC3 | frontend | `gateway/http/request.test.ts > sends the CSRF header and credentials on every request` |
| PL-067 | 화면: 서버 Problem의 문구와 칸 오류를 그대로 보인다 | PL-R37, PL-UC3 | frontend | `shared/api/problem.test.ts > lists field errors of a request validation problem without the body prefix`<br>`shared/api/problem.test.ts > shows the server detail of a 403 forbidden problem`<br>`gateway/http/request.test.ts > throws an ApiError with the gateway kind and the server detail`<br>`gateway/http/request.test.ts > keeps the field errors of a request validation problem in the message` |
| PL-068 | 화면: Problem이 아닌 실패는 상태에 맞는 고정 문구를 보인다 | PL-R37, PL-R39, PL-UC3 | frontend | `shared/api/problem.test.ts > falls back to a generic message when the body is not a problem document`<br>`shared/api/problem.test.ts > explains a 403 without a problem document as missing permission instead of a status code`<br>`gateway/http/request.test.ts > gives a readable message when the failure body is not a problem document` |
| PL-069 | 화면: 서버에 닿지 못하면 네트워크 원문 대신 고정 문구를 보인다 | PL-R39, PL-R37, PL-UC3 | frontend | `shared/api/problem.test.ts > hides unexpected error details`<br>`gateway/http/request.test.ts > explains an unreachable server instead of leaking the network error` |
| PL-070 | 화면: 모양이 다른 오류 항목은 건너뛰고 칸 위치만 모은다 | PL-R37, PL-UC3 | frontend | `shared/api/problem.test.ts > ignores error items without loc instead of throwing`<br>`shared/api/problem.test.ts > still lists the items that do have loc next to ones that do not`<br>`shared/api/problem.test.ts > collects the first string part of each location and skips items of another shape` |
| PL-071 | 화면: 서버 오류 종류를 화면 종류로 정규화한다 | PL-R39, PL-UC3 | frontend | `gateway/http/request.test.ts > maps %s to %s`<br>`gateway/http/request.test.ts > status %i %s becomes kind %s`<br>`gateway/http/request.test.ts > keeps the stage of a directory verification failure` |
| PL-072 | 화면: 본문이 있어야 할 성공 응답에 본문이 없으면 해석 불가 오류다 | PL-R39, PL-UC3 | frontend | `gateway/http/request.test.ts > turns a success response without a body into an unreadable-response error`<br>`gateway/http/request.test.ts > resolves for a 204 without a body` |
| PL-073 | 화면: 보호 화면 상단의 브랜드 문구를 salesX 로고 이미지로 대체한다 | PL-R34, PL-UC6 | frontend | `shared/ui/Layout.menu.test.tsx > 상단 브랜드는 salesX 로고 이미지로 홈에 연결된다` |

### PL-001 역할 3종은 정해진 권한 묶음만 가진다
- When 역할 `admin`·`sales`·`user`마다 `read`·`write`·`administer` 권한을 물어본다
- Then admin은 셋 다, sales는 `read`·`write`만, user는 `read`만 허용되고 역할 값은 정확히 세 개다. 같은 역할의 `Principal.can`도 같은 답을 한다

### PL-002 앱이 공개한 모든 엔드포인트가 권한 표에 있고 표에만 있는 엔드포인트는 없다
- Given 앱이 만든 OpenAPI 계약
- When `/healthz`·`/readyz`·`/api/v1/**`의 (메서드, 경로) 집합을 권한 표의 키와 비교한다
- Then 두 집합이 같다(표에 없는 엔드포인트 0개, 앱에 없는 표 행 0개). 표의 관리자 전용 행은 admin만, 업무 쓰기 행에는 user가 없다

### PL-003 로그인하지 않고 보호 경로를 부르면 모두 401이다
- Given 익명(세션 쿠키 없음, CSRF 헤더 있음)
- When 권한 표의 보호 경로를 하나씩 빈 본문(`POST`·`PUT`·`PATCH`는 `{}`)으로 부른다
- Then 모두 401 Problem, kind `unauthenticated`, `detail` "로그인이 필요합니다"다

### PL-004 허용된 역할은 어느 보호 경로에서도 역할 가드에 막히지 않는다
- Given 권한 표에서 그 경로를 허용하는 역할로 로그인
- When 경로를 없는 id와 빈 본문으로 부른다
- Then 응답이 401도 403도 아니다(예: 404, 422, 200)

### PL-005 user가 업무 쓰기 경로를 부르면 읽기 전용 403이다
- Given VIEWER(user)
- When 권한 표의 업무 쓰기 경로를 하나씩 부른다
- Then 모두 403 Problem, kind `forbidden`, `detail` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"다

### PL-006 user의 쓰기 거절은 본문 검증·존재 확인보다 먼저다
- Given VIEWER
- When 업무 쓰기 경로를 형식이 틀린 본문(`{"unexpected": ["garbage"]}`, DELETE는 본문 없음)과 없는 id로 부른다
- Then 422·404가 아니라 403 `forbidden`이다

### PL-007 admin이 아닌 사용자가 관리자 전용 경로를 부르면 403이다
- Given KIM(sales), VIEWER(user)
- When 각자 권한 표의 관리자 전용 경로를 하나씩 부른다
- Then 모두 403 Problem, kind `forbidden`이다. 문구는 "관리자 권한이 필요합니다"(관리자 가드), 소유 feature의 도메인 문구(예: sales의 계약 삭제 "계약 삭제는 관리자만 할 수 있습니다."), 또는 user가 업무 쓰기 가드에 먼저 막힌 경우 읽기 전용 문구다

### PL-008 sales의 관리자 경로 거절은 본문 검증보다 먼저이고 문구에 "관리자"가 있다
- Given KIM(sales)
- When 관리자 전용 경로를 형식이 틀린 본문으로 부른다
- Then 422가 아니라 403 `forbidden`이고 `detail`에 "관리자"가 들어 있다

### PL-009 역할 가드가 없는 쓰기 경로는 user도 403이 아니다
- Given VIEWER
- When 저장 리포트 쓰기(`POST /reports` 등), `POST /reports/query`, `PATCH /me/profile`을 부른다
- Then 역할 가드의 403이 아니다(유효한 리포트 조회 요청이면 200, 빈 본문이면 422 등 그 feature의 결과)

### PL-010 미인증 요청은 CSRF 헤더가 없어도 401이 먼저다
- Given 익명, CSRF 헤더 없음
- When 업무 쓰기 경로(예: `POST /api/v1/deals`)를 부른다
- Then 403 `csrf`가 아니라 401 `unauthenticated`다

### PL-011 로그인한 사용자의 상태 변경 요청에 CSRF 헤더가 없으면 403 csrf다
- Given KIM(sales) 또는 BOSS(admin)로 로그인, CSRF 헤더 없음
- When 상태 변경 요청(예: 연락처 등록·저장 리포트 생성·삭제·사용자 등록)을 보낸다
- Then 403 Problem, kind `csrf`, `detail` "요청 헤더(X-Requested-With)가 필요합니다"이고 아무것도 저장되지 않는다

### PL-012 CSRF 헤더 값이 비어 있으면 헤더가 없는 것과 같다
- Given CSRF 헤더 `X-Requested-With: ""`
- When 상태 변경 요청을 보낸다(예: `PUT /auth/setup/auth-mode`)
- Then 403 `csrf`다

### PL-013 조회 요청은 CSRF 헤더 없이도 된다
- Given KIM으로 로그인, CSRF 헤더 없음
- When 조회 요청(예: `GET /api/v1/contacts/companies?kind=customer`)을 보낸다
- Then 200이다

### PL-014 공개 인증 경로(로그인·로그아웃·최초 설정)도 CSRF 헤더가 필요하다
- Given 익명, CSRF 헤더 없음
- When `POST /auth/login`, `POST /auth/logout`, `/auth/setup/**`의 각 단계를 부른다
- Then 모두 403 `csrf`이고 외부(AD) 호출·저장이 없다

### PL-015 CSRF 검사는 역할 가드보다 먼저다
- Given VIEWER로 로그인, CSRF 헤더 없음
- When 업무 쓰기 경로를 부른다
- Then kind가 `forbidden`이 아니라 `csrf`인 403이다

### PL-016 오류 응답은 Problem 형식이고 instance는 요청 경로다
- Given KIM
- When 없는 Deal(`GET /api/v1/deals/20260101-ZZZZ`)을 조회한다
- Then `Content-Type`이 `application/problem+json`이고 본문에 `type`(`https://neoine-sales.example/problems/not-found`)·`title`·`status`(404)·`detail`·`instance`(`/api/v1/deals/20260101-ZZZZ`)가 있다

### PL-017 도메인 오류는 종류별 상태·kind·문구로 바뀐다
- Given 유스케이스가 PL-R11의 각 도메인 오류를 던지도록 한 앱
- When 그 경로를 부른다
- Then 오류마다 PL-R11의 상태와 kind, 2.8의 title이고 `detail`은 오류 메시지 그대로다(분류되지 않은 `DomainError`는 400 `domain-error`)

### PL-018 요청 형식 오류는 공통 문구와 오류 목록을 주고 입력값을 되돌리지 않는다
- Given KIM
- When 필수 칸이 빠지고 다른 칸에 표시용 문자열(예: `"SECRET-INPUT"`)을 잘못된 타입으로 넣은 본문을 보낸다
- Then 422 `request-validation`, `detail` "요청 형식이 올바르지 않습니다", `errors`의 각 항목은 `loc`·`msg`·`type`을 가지고 `input`·`ctx`·`url`이 없으며 응답 어디에도 `"SECRET-INPUT"`이 없다

### PL-019 없는 경로는 404 Problem이다
- Given KIM
- When `GET /api/v1/nothing-here`
- Then 404, `Content-Type` problem+json, `status` 404, kind `http-error`

### PL-020 허용되지 않은 메서드는 405 Problem이다
- Given KIM
- When `PATCH /api/v1/users`
- Then 405, problem+json, kind `http-error`

### PL-021 정수가 아닌 id 경로 값은 422다
- Given id 경로 파라미터를 가진 모든 경로(권한이 있는 역할)
- When id 자리에 `abc`·`1.5`·UUID·`0x10`·`1e3`을 넣어 부른다
- Then 모두 422 `request-validation`이다

### PL-022 0·음수·상한 초과 id 경로 값은 500이 아니라 422다
- Given 같은 경로들
- When id 자리에 `0`·`-1`·2^53·`9223372036854775808`을 넣는다
- Then 모두 422 `request-validation`이다

### PL-023 상한 id(2^53−1)는 유스케이스까지 가서 404다
- Given 같은 경로들, 그런 id의 대상은 없음
- When id 자리에 `9007199254740991`을 넣는다
- Then 422가 아니라 그 경로의 404 `not-found`다

### PL-024 본문 id는 JSON 정수만 받는다
- Given 본문에 id를 받는 요청(예: 선택 목록 `{id}`)
- When id에 문자열 `"7"`, 불리언, 실수, 0, 2^53을 넣는다
- Then 모두 422 `request-validation`이다

### PL-025 텍스트 검색어·등록 본문의 NUL 문자는 500이 아니라 422 invalid-value다
- Given KIM
- When Deal 목록 `keyword=a\x00b`로 검색하거나 Deal명에 NUL을 넣어 등록한다
- Then 422 `invalid-value`이고 `detail`에 `asyncpg`·`sqlalchemy`·`postgres`·`dbapierror`·`0x00`이 없다(실제 PostgreSQL에서도 같다)

### PL-026 정수 칸의 NUL 문자는 422 request-validation이다
- Given KIM
- When Deal 목록 `owner_user_id=a\x00b`로 검색한다
- Then 422 `request-validation`이다

### PL-027 생존 확인은 로그인 없이 200 ok다
- Given 익명
- When `GET /healthz`
- Then 200 `{"status": "ok"}`

### PL-028 의존 자원이 응답하면 준비 확인은 200 ready다
- Given 의존 자원(DB) 확인이 성공하는 앱
- When `GET /readyz`
- Then 200 `{"status": "ready"}`

### PL-029 의존 자원이 실패하면 준비 확인은 503이고 원인을 감춘다
- Given 의존 자원 확인이 접속 정보(비밀번호·호스트·`postgresql`)를 담은 예외로 실패하는 앱
- When `GET /readyz`
- Then 503 `not-ready` "서비스가 아직 요청을 받을 수 없습니다"이고 응답에 비밀번호·`postgresql`·호스트 주소가 없다

### PL-030 문서 노출이 켜져 있으면 API 문서와 계약을 열 수 있다
- Given `enable_docs` true
- When `/docs`, `/openapi.json`을 연다
- Then 각각 200이다

### PL-031 문서 노출이 꺼져 있으면 문서 경로는 404이고 생존 확인은 그대로다
- Given `enable_docs` false
- When `/docs`, `/redoc`, `/openapi.json`, `/healthz`를 연다
- Then 문서 세 경로는 404, `/healthz`는 200이다

### PL-032 허용된 출처의 CORS 사전 요청은 허용된다
- Given `cors_allowed_origins` = [`http://localhost:5173`]
- When 그 출처로 `OPTIONS /api/v1/users`(요청 메서드 POST) 사전 요청을 보낸다
- Then 200이고 `Access-Control-Allow-Origin`이 `http://localhost:5173`이다

### PL-033 허용되지 않은 출처에는 CORS 허용 헤더가 없다
- Given 같은 설정
- When `https://evil.example` 출처로 사전 요청을 보낸다
- Then `Access-Control-Allow-Origin` 헤더가 없다

### PL-034 커밋된 계약 파일은 앱이 만드는 계약과 같다
- Given 커밋된 `backend/openapi.json`
- When 앱 계약(PL-R20의 조립)과 비교한다
- Then 둘이 같다. 다르면 "`uv run python scripts/export_openapi.py`로 갱신" 안내와 함께 실패한다

### PL-035 인증 API를 뺀 모든 엔드포인트가 401과(입력이 있으면) 422를 문서화한다
- Given 앱 계약
- When `/api/v1/auth/**`를 뺀 `/api/v1` 엔드포인트의 응답 목록을 본다
- Then 모두 `401`이 있고, 파라미터나 요청 본문이 있는 엔드포인트는 `422`도 있다

### PL-036 보호 경로는 모두 401을 문서화한다
- Given 앱 계약과 권한 표
- When 권한 표의 보호 경로(내 정보 계열 포함) 응답 목록을 본다
- Then 모두 `401`이 있다

### PL-037 업무 쓰기·관리자 전용 엔드포인트는 403을 Problem 스키마로 문서화한다
- Given 앱 계약과 권한 표
- When 업무 쓰기·관리자 전용 엔드포인트의 `403` 응답을 본다
- Then 있고 그 스키마가 `#/components/schemas/Problem`이다

### PL-038 모든 역할이 쓰는 조회 엔드포인트는 403을 문서화하지 않는다
- Given 앱 계약과 권한 표
- When 업무 조회 엔드포인트의 응답 목록을 본다
- Then `403`이 없다

### PL-039 계약의 id는 정수이고 uuid 표기가 없으며 경로 id는 범위를 문서화한다
- Given 앱 계약과 커밋된 계약 파일 각각
- When id 이름(PL-R22)의 속성·파라미터와 경로 id 파라미터를 본다
- Then `"format": "uuid"`가 없고 id는 정수(또는 정수 배열, null 허용)이며 경로 id는 모두 `minimum` 1·`maximum` 9007199254740991이다

### PL-040 어떤 응답 스키마에도 비밀번호 값 필드가 없다
- Given 앱 계약
- When 응답이 참조하는 모든 스키마(중첩 포함)의 속성 이름을 본다
- Then 이름에 `password`가 들어간 속성은 boolean 플래그뿐이다

### PL-041 프로파일을 정하지 않으면 local이고 잘못된 프로파일은 즉시 실패한다
- When `APP_PROFILE` 없이 / env 파일에 `APP_PROFILE=dev`를 두고 / `APP_PROFILE=staging`으로 설정을 읽는다
- Then 각각 local 설정 / dev 설정 / 검증 오류로 실패한다

### PL-042 APP_ENV_FILE로 env 파일을 고르고 없는 파일이면 경로를 알리며 실패하고 환경변수가 이긴다
- When `APP_ENV_FILE` 없이 / 다른 파일을 지정해 / 없는 파일을 지정해 / 파일과 환경변수에 다른 `APP_PROFILE`을 두고 설정을 읽는다
- Then `.env`를 읽는다 / 지정 파일만 읽고 `.env`는 무시한다 / "APP_ENV_FILE로 지정한 env 파일이 없습니다: <경로>"로 실패한다 / 환경변수의 프로파일을 쓴다

### PL-043 알 수 없는 옛 변수는 무시한다
- Given 환경변수나 env 파일에 `APP_DEV_LOGIN_ENABLED`, 예전 OIDC 변수
- When 각 프로파일 설정을 읽는다
- Then 오류 없이 읽히고 설정에 해당 필드가 없다

### PL-044 필수 값이 없으면 모든 프로파일에서 기동이 실패한다
- When `APP_DATABASE_URL`·`APP_JWT_SECRET`·`APP_SETTINGS_ENCRYPTION_KEY` 중 하나를 빼고 각 프로파일 설정을 읽는다
- Then 검증 오류로 실패한다. `APP_REDIS_URL`은 없어도 되고, 주면 형식이 틀릴 때 실패한다

### PL-045 형식이 틀린 암호화 키는 값을 보이지 않고 실패한다
- When 32바이트가 아니거나 URL-safe base64가 아닌(예: 예시 키 중간에 `.`을 끼움) 암호화 키로 설정을 읽는다
- Then "Fernet 키 형식(URL-safe base64로 인코딩한 32바이트)이어야 합니다"로 실패하고 오류 문구에 입력한 키 값이 없다. jwt_secret을 암호화 키로 대신 쓰지 않는다

### PL-046 안전한 product 설정은 통과한다
- Given debug·docs·db_echo 꺼짐, cookie_secure true, CORS 목록에 `*` 없음, 32자 이상 jwt_secret, 예시가 아닌 암호화 키, sentry_dsn
- When product 설정을 읽는다
- Then 통과한다(로그인 관련 변수가 없어도 된다)

### PL-047 위험한 product 설정은 어긴 항목을 알리며 거부된다
- When product에서 debug true / enable_docs true / db_echo true / cookie_secure false / CORS `*` / 31자 jwt_secret / sentry_dsn 없음 중 하나로 설정을 읽는다
- Then 해당 항목 문구(PL-R26)를 담은 검증 오류로 실패한다

### PL-048 예시 암호화 키는 local·dev에서만 쓸 수 있다
- Given `.env.example`의 예시 키, 그리고 문자열은 다르지만 풀면 같은 바이트가 되는 변형
- When local·dev·product 설정을 읽는다
- Then local·dev는 통과, product는 두 표기 모두 "settings_encryption_key"를 담은 검증 오류로 실패하고 오류에 키 값이 없다. 코드의 예시 키 상수는 `.env.example`의 값과 같다

### PL-049 비밀 값은 설정 표현에 나오지 않는다
- Given jwt_secret·암호화 키를 넣은 설정
- When 설정 객체를 문자열로 바꾼다
- Then 비밀 값이 나오지 않는다

### PL-050 프로파일마다 정해진 기본값을 쓴다
- When 값을 주지 않고 local·dev·product 설정을 읽는다
- Then PL-R28의 기본값(예: local 문서 켬·cookie_secure false, dev 로그 json·debug false, 세션 8시간)이다

### PL-051 화면: 로그인하지 않은 방문자는 보호 화면에서 로그인 화면으로 간다
- Given 로그인하지 않음, 최초 설정은 끝남
- When `/deals`, `/dashboard`, `/admin/users`를 연다
- Then 주소가 `/login`이 된다

### PL-052 화면: 내 정보 조회가 401이 아닌 오류면 오류 배너만 보이고 레이아웃이 없다
- Given 내 정보 조회가 500(또는 네트워크 오류)으로 실패
- When `/deals`를 연다
- Then 오류 배너가 보이고 주 메뉴(`navigation` "주 메뉴")가 없으며 주소는 `/login`으로 바뀌지 않는다

### PL-053 화면: 첫 주소(/)는 Deals 목록으로 간다
- Given KIM
- When `/`를 연다
- Then Deals 목록 주소(기본 조건 포함)가 된다

### PL-054 화면: 정의되지 않은 주소와 폐지된 주소는 Deals 목록으로 간다
- Given 로그인
- When `/customers`, `/partners`, `/actions`, `/nowhere`를 연다
- Then 각각 Deals 목록 주소가 된다

### PL-055 화면: 옛 사용자 관리·설정 주소는 Admin 새 주소로 간다
- Given BOSS
- When `/users`, `/settings`를 연다
- Then 각각 `/admin/users`, `/admin/integrations`가 된다

### PL-056 화면: sales·user는 Admin 화면에서 Deals 목록으로 간다
- Given KIM 또는 VIEWER
- When `/admin/users`, `/admin/contacts`를 연다
- Then Deals 목록 주소가 되고 Admin 메뉴가 보이지 않는다

### PL-057 화면: admin이 /admin을 열면 사용자 관리로 간다
- Given BOSS
- When `/admin`을 연다
- Then 주소가 `/admin/users`다

### PL-058 화면: Deal 등록·수정 화면은 sales·admin만 열고 user는 Deals 목록으로 간다
- When KIM이 `/deals/new`, BOSS가 `/deals/20261001-AB12/edit`, VIEWER가 두 주소를 연다
- Then KIM·BOSS는 그 주소에 머물고 VIEWER는 Deals 목록 주소가 된다

### PL-059 화면: Deal 상세·Forecast·Dashboard는 모든 역할이 연다
- Given admin·sales·user 각각
- When `/deals/20261001-AB12`, `/forecast`, `/dashboard`를 연다
- Then 주소가 그대로이고 화면이 보인다

### PL-060 화면: sales·user의 주 메뉴는 6개이고 Admin이 없다
- Given KIM 또는 VIEWER
- When 아무 보호 화면을 연다
- Then 주 메뉴 링크가 순서대로 Deals, 계약관리(`/contracts`), 파트너 Activity, Dashboard, Forecast, Reports다

### PL-061 화면: admin의 주 메뉴는 끝에 Admin이 더해진다
- Given BOSS
- When 아무 보호 화면을 연다
- Then 주 메뉴가 위 6개 + Admin이다

### PL-062 화면: 주 메뉴를 누르면 그 화면으로 간다
- Given BOSS
- When Forecast, Admin을 차례로 누른다
- Then 주소가 `/forecast`, `/admin/users`가 된다

### PL-063 화면: Admin 틀은 제목과 서브 메뉴 4개를 보인다
- Given BOSS
- When `/admin/users`를 연다
- Then h1 "Admin > Settings"와 "Admin 메뉴"의 링크 사용자 관리, Deal 관리, contacts 관리, 외부연동이 순서대로 보인다

### PL-064 화면: Admin 서브 메뉴는 현재 화면을 표시하고 누르면 이동한다
- Given BOSS
- When 네 Admin 주소를 각각 열고, `/admin/users`에서 외부연동을 누른다
- Then 연 주소의 서브 메뉴가 `aria-current="page"`이고 그 화면 제목(h2)이 보이며, 누르면 `/admin/integrations`가 된다

### PL-065 화면: 역할 판단 함수는 쓰기·관리자·메뉴를 역할대로 판단한다
- When `canWrite`·`isAdmin`·`canAccessAdmin`·`canManageMasterData`·`visibleMenu`를 admin·sales·user·없음으로 부른다
- Then `canWrite`는 admin·sales만, 나머지 관리자 함수는 admin만 true이고 `visibleMenu`는 PL-R34의 목록이다

### PL-066 화면: 모든 API 요청은 CSRF 헤더와 쿠키를 보낸다
- When 생성된 API 클라이언트로 요청한다
- Then 요청에 `X-Requested-With: neoine-web`가 있고 `credentials`가 `include`다

### PL-067 화면: 서버 Problem의 문구와 칸 오류를 그대로 보인다
- Given 서버가 409 `already-exists` "같은 이름의 코드가 이미 있습니다." 또는 422 `request-validation` + `errors: [{loc: ["body","name"], msg: "Field required"}]`를 준다
- When 화면이 그 오류를 문구로 바꾼다
- Then 각각 "같은 이름의 코드가 이미 있습니다.", "요청 형식이 올바르지 않습니다 — name: Field required"다. 403 `forbidden`은 서버 `detail`을 그대로 보인다

### PL-068 화면: Problem이 아닌 실패는 상태에 맞는 고정 문구를 보인다
- Given 서버가 Problem이 아닌 본문으로 403 또는 502를 준다
- When 화면이 문구로 바꾼다
- Then 403은 "이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.", 502는 "요청에 실패했습니다 (502)"다

### PL-069 화면: 서버에 닿지 못하면 네트워크 원문 대신 고정 문구를 보인다
- Given 요청이 네트워크 오류로 실패 / `ApiError`가 아닌 예외
- When 화면이 문구로 바꾼다
- Then 상태 0의 "서버에 연결할 수 없습니다." / "네트워크 오류가 발생했습니다. 잠시 후 다시 시도하세요."이고 원래 오류 문구는 보이지 않는다

### PL-070 화면: 모양이 다른 오류 항목은 건너뛰고 칸 위치만 모은다
- Given `errors`에 `loc`가 없는 항목(예: `{location, code, message}`)과 `loc`가 있는 항목이 섞인 Problem
- When 문구를 만들고 `errorFields`를 부른다
- Then 오류 없이 `loc`가 있는 항목만 문구에 붙고, `errorFields`는 `location`의 첫 문자열 조각 목록이다

### PL-071 화면: 서버 오류 종류를 화면 종류로 정규화한다
- When 서버 kind `invalid-value`·`request-validation`·`invalid-reference`·`already-exists`·`invalid-state`·`unauthenticated`·`not-found`·`forbidden`·`directory-verification-failed`의 오류를 받는다
- Then 화면 kind가 각각 `validation`·`validation`·`validation`·`conflict`·`conflict`·`unauthorized`·`not-found`·`forbidden`·`directory-verification-failed`이고 `stage`가 있으면 유지된다

### PL-072 화면: 본문이 있어야 할 성공 응답에 본문이 없으면 해석 불가 오류다
- Given 서버가 본문 없는 성공 응답을 준다(본문이 있어야 하는 요청)
- When 게이트웨이가 결과를 푼다
- Then 상태 502, 문구 "서버 응답을 해석할 수 없습니다."의 `ApiError`다. 본문 없는 204 요청은 성공으로 끝난다

### PL-073 화면: 보호 화면 상단의 브랜드 문구를 salesX 로고 이미지로 대체한다
- Given 로그인한 사용자가 보호 화면을 연다
- When 상단 브랜드 영역을 본다
- Then 접근 가능한 이름 "salesX"인 로고 이미지가 `/images/salesX.png`에서 로드되어 홈(`/`) 링크 안에 보이고 "NEOINE 영업관리" 문구는 없다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-26 | 사용자 요청: 보호 화면 상단의 "NEOINE 영업관리" 문구를 salesX 로고 이미지로 대체 | PL-073(신규) |
| 2026-11-26 | OS 직접 실행 환경의 Nginx → Vite 전체 프록시 구조와 salesX 정적 자산 제공 경로 명시 | PL-073 |
| 2026-11-09 | 최초 작성(초안): 구현된 플랫폼 공통 동작을 정본 명세로 옮김. 규칙 PL-R1~R39, use case PL-UC1~UC6, BDD 케이스 PL-001~PL-072 | PL-001~PL-072(신규) |
