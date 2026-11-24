# 로그인·세션   (feature 코드: AU, 상태: 확정(2026-11-24 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/web/routers/{auth,auth_login}.py`, `web/schemas/auth.py`, `web/security.py`, `web/request_info.py`, `web/error_handlers.py`, `application/auth/{password_login,directory_login,local_login,fallback_login,credential_check,active_user,throttle,issue_session,authenticate,logout,auth_status,mode,messages,warning_stage,tokens}.py`, `domain/auth/{credentials,session,login_failure,password_hash,mode,principal,errors}.py`, `domain/user/{entities,retired_login_ids}.py`, `application/ports/{directory,password_hasher}.py`, `infra/auth/ldap.py`, `infra/crypto/scrypt_hasher.py`, `container_auth.py`, `config/base.py`, `frontend/src/features/auth/{LoginPage,DirectoryWarningDialog}.tsx`, `data/auth.ts`, `gateway/http/{auth.ts,mappers/user.ts}`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 서버 코드와 frontend Fake 게이트웨이가 다른 곳은 서버 코드를 정본으로 삼았고 질문으로 남겼습니다(계획 `artifacts/10-analysis/au-plan.md` Q1).

## 1. 개요

- 목적: 등록된 사용자만 아이디·비밀번호로 로그인해 서버 세션을 받고, 모든 요청에서 그 세션과 사용자 상태(재직·역할)를 다시 확인한다. AD가 답하지 못할 때도 예전에 AD로 로그인한 사용자는 저장된 비밀번호 해시로 들어올 수 있게 하고, admin에게는 그 사실을 알린다.
- 사용자(역할): 미인증 방문자(로그인), `admin`·`sales`·`user`(세션·내 정보·로그아웃), admin(AD 경고 팝업).
- 범위
  - `POST /api/v1/auth/login`(AD 로그인·대체 로그인·앱 계정(local) 로그인), 예약 아이디 거부, 로그인 시도 제한(429)
  - AD 사용자 비밀번호 바인드 이름(검색한 DN 또는 `<아이디>@<도메인>`)과 그 도메인 환경변수 `APP_AD_LOGIN_DOMAIN`(AU-R7a)
  - 세션 발급·쿠키, 요청마다 세션·활성·역할 재확인(`Authenticate`), `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/config` 응답과 인증 방식 판정(effective mode)
  - 비밀번호 해시(scrypt) 형식과 비밀 비노출
  - 화면: `/login`, admin AD 경고 팝업, 로그아웃 훅(`useLogout`), 인증 게이트웨이
- 범위 밖(다른 feature)
  - 최초 설정 단계 진행(`/auth/setup/*`)과 "설정이 필요하면 `/login`이 `/setup`으로 보낸다" → SU
  - AD 설정 저장·연결 테스트·Base DN 탐색·바인드 비밀번호 암호화/마스크·`bind_credential_status` → IN
  - 사용자 등록·퇴사/삭제·역할 변경·비밀번호 재설정(세션 종료 포함)·예약 아이디 등록 거부 → US
  - 사용자 아이콘 메뉴(로그아웃 버튼 자리·이름(역할) 표시), 내 비밀번호 변경 → ME
  - 미인증 401·CSRF 403·판정 순서·오류 형식·보호 화면 가드 → PL(PL-R4·R5·R9·R10·R29), 첫 서버 시각 동기 → TM
  - 프록시 신뢰 대역(`X-Forwarded-For`) 설정 → 배포 도구(feature 아님)
  - 경쟁·동시성 테스트(사용자가 제시하지 않음)
- 관련 화면·메뉴: `/login`, 로그인 직후 첫 보호 화면의 "AD 연결 경고" 대화상자

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 인증 방식 | 시스템 전역 하나. `ad`(AD 연동) 또는 `local`(앱이 계정을 직접 관리). 단일 행 `auth_settings`에 저장 |
| effective mode | 실제로 쓰는 인증 방식(AU-R22). 저장값이 없을 때의 판정 포함 |
| 로그인 아이디 | `LoginId`. 앞뒤 공백 제거·소문자로 정규화한 값 |
| AD 로그인 | 서비스 계정 search-then-bind로 AD가 비밀번호를 확인하는 로그인 |
| 사용자 바인드 이름 | AD가 사용자 비밀번호를 확인할 때 쓰는 바인드 계정 이름. 도메인 없음이면 검색한 항목의 DN, 도메인 있음이면 `<로그인 아이디>@<도메인>`(UPN 형식, AU-R7a) |
| 도메인(바인드) | 환경변수 `APP_AD_LOGIN_DOMAIN`을 정리한 값(예 `neoine.co.kr`). 없거나 비면 '도메인 없음' |
| 대체 로그인 | AD가 답할 수 없을 때만 저장된 비밀번호 해시로 하는 로그인(AD 모드 전용) |
| 앱 계정 로그인 | local 모드에서 저장된 해시로만 하는 로그인 |
| 경고 단계 | 대체 로그인으로 넘어간 이유(`DirectoryWarningStage`, AU-R10 표) |
| 공통 실패 | 401 `unauthenticated` "아이디 또는 비밀번호가 올바르지 않습니다" |
| 선점 | 로그인 시도 전에 아이디·IP 카운터를 1회씩 미리 올려 두는 일(AU-R14) |
| 세션 토큰 | 브라우저 쿠키 `neoine_session`의 값. 서버는 SHA-256 해시만 저장 |
| 재직 사용자 | `users.deleted_at`이 비어 있는 행 |

### 2.2 데이터 모델

테이블(컬럼·제약의 정본은 스키마 테스트 `tests/unit/infra/schema/`, 기준선은 SC):

- `auth_sessions`: `id`(bigint PK), `user_id`(users FK), `token_hash`(SHA-256 hex, 유니크), `created_at`, `expires_at`, `revoked_at`(NULL 가능). 도메인 `AuthSession`: `expires_at > created_at`, 시각은 시간대 필수, `is_active(now)` = 폐기 안 됨 그리고 `now < expires_at`, 두 번 폐기하면 `InvalidStateError` "이미 폐기된 세션입니다".
- `login_failures`: `key`(PK, HMAC-SHA256 hex), `failures`, `window_started_at`, `locked_until`(NULL 가능). 도메인 `FailureCounter`·`FailurePolicy(max_failures, window, lock_duration)`.
- `user_password_hashes`: `user_id`(PK, users FK CASCADE), `password_hash`(`PasswordHash`: 비어 있지 않음, NUL 없음, 512자 이하), 저장 시각. 사용자 삭제 시 함께 삭제(US).
- `auth_settings`: 단일 행 `mode`(`ad`·`local`), `updated_at`. 쓰기는 SU.
- `users`(US 소유)에서 AU가 쓰는 값: `login_id`, `role`, `display_name`, `email`, `phone`, `last_login_at`, `deleted_at`.

값 객체·DTO:
- `LoginId`: 정규화 뒤 `[a-z0-9][a-z0-9._-]{0,63}`(ASCII). `Password`: NUL 없음, 공백만이 아님, 256자 이하, strip하지 않음, repr은 `Password(***)`.
- `Principal`: `user_id`, `subject`(로그인 아이디), `email`(소문자, 없으면 null), `name`(비면 subject, 200자로 자름), `role`.
- `LoginOutcome`: `session`(`IssuedSession`: token, expires_at, principal), `directory_warning`(`DirectoryWarning(stage, message)` 또는 None).
- `AuthStatus`: `directory_configured`, `storage_configured`, `needs_directory_setup`, `needs_storage_setup`, `needs_admin_setup`, `auth_mode`.
- 설정(`APP_` 접두어): `session_ttl_hours`(기본 8), `login_max_failures_per_account`(5), `login_max_failures_per_ip`(30), `login_failure_window_minutes`(15), `login_lock_minutes`(15), 모두 1 이상. `cookie_secure`(PL-R28). `ad_login_domain`(`APP_AD_LOGIN_DOMAIN`, 선택, 기본 없음, 형식은 AU-R7a).
- 프런트 `Me`: `{ id, loginId, name, role }`, `LoginResult`: `{ me, directoryWarning: { stage, message } | null }`, `AuthConfig`: `{ authMode: 'ad' | 'local' | null, needsSetup: boolean }`.

### 2.3 비즈니스 규칙

로그인 입력
- **AU-R1** `POST /auth/login` 본문은 `login_id`(문자열, 최대 128자)와 `password`(문자열, 최대 256자) 둘 다 필수이고 다른 필드는 받지 않는다. 필드 누락·모르는 필드·길이 초과·타입 오류는 422 `request-validation`이며(PL-R12) 입력값을 응답에 되돌리지 않는다. 이 422는 시도 횟수에 세지 않는다. CSRF 헤더가 필요하다(PL-R9, PL-014).
- **AU-R2** 아이디는 앞뒤 공백을 지우고 소문자로 바꾼 뒤 판정한다(`" Kim "`과 `kim`은 같은 사용자). 정규화한 값이 형식(`[a-z0-9][a-z0-9._-]{0,63}`, ASCII)에 맞지 않으면(빈 값, 65~128자, 한글, `*`·`(`·`)`·`\`·`,`·`=`·공백 등) 공통 실패 401이고 AD·해시를 부르지 않으며 시도 횟수에 세지 않는다.
- **AU-R3** 비밀번호가 빈 값·공백만·NUL 포함이면 공통 실패 401이고 AD·해시를 부르지 않으며 시도 횟수에 세지 않는다(인증 방식 무관). 비밀번호는 앞뒤 공백을 지우지 않는다.
- **AU-R4** 인증 실패는 원인과 무관하게 같은 응답이다: 401 `unauthenticated`, `detail` = "아이디 또는 비밀번호가 올바르지 않습니다"(마침표 없음), 세션 쿠키 없음. 해당 원인: 형식 오류(AU-R2·R3), 미등록, 퇴사, AD 비밀번호 거절, AD 검색 0건, 재직 행 중복, 예약 아이디, local의 해시 없음·불일치, 로그인 처리 중 사용자 삭제. (예외: 대체 로그인 실패는 AU-R10의 409·503.)
- **AU-R5** 예약 아이디 `dev-admin`·`dev-sales`·`dev-user`(정규화 값이 정확히 일치)는 인증 방식과 무관하게 AD·해시를 거치지 않고 공통 실패 401이며 실패 1회로 센다(잠겨 있으면 429). `dev-qa` 같은 다른 `dev-` 아이디는 일반 아이디다. 예약 아이디 등록 거부는 US.
- **AU-R6** effective mode(AU-R22)가 `local`이면 앱 계정 로그인(AU-R12), 그 밖(`ad` 또는 미선택)이면 AD 로그인(AU-R7)으로 처리한다. local 로그인은 성공·실패 모두 AD를 한 번도 부르지 않는다. ad 모드에서 AD가 응답하면 저장 해시가 맞아도 AD 판정을 따른다.

AD 로그인과 대체 로그인
- **AU-R7** AD 로그인은 매 로그인마다 DB의 현재 AD 설정(복호화한 바인드 비밀번호)과 저장된 Base DN으로 한다: 연결(+TLS) → 서비스 계정 바인드 → 사용자 필터의 `{login_id}` 자리에 이스케이프한 아이디를 넣어 Base DN 아래 검색(최대 2건, 이름·이메일·전화는 이 검색 결과에서 읽음) → 검색이 정확히 1건이면 새 연결에서 사용자 바인드 이름(AU-R7a)과 사용자 비밀번호로 바인드. 서비스 계정 바인드 이름(`bind_account`)은 도메인 설정과 무관하게 IN에서 저장한 값 그대로다. 아이디는 DN에 넣지 않는다. 서버 인증서는 검증하지 않는다(IN). AD 설정(DB)을 바꾸면 서버 재시작 없이 다음 로그인부터 새 설정을 쓴다.
- **AU-R7a** 사용자 바인드 이름(2026-11-24): 환경변수 `APP_AD_LOGIN_DOMAIN`(선택, 모든 프로파일 같은 규칙)을 서버 기동 때 한 번 읽는다(값을 바꾸면 재시작해야 적용된다).
  - 값 정리: 앞뒤 공백을 지우고 소문자로 바꾼다. 변수가 없거나 정리한 값이 빈 문자열이면 '도메인 없음'이다.
  - 형식: 정리한 값은 ASCII 영문·숫자·`-`로 된 라벨(1~63자, `-`로 시작하거나 끝나지 않음)을 `.`으로 이은 253자 이하 문자열이어야 한다(예 `neoine.co.kr`, 라벨 하나인 `corp`도 허용). `@`로 시작(`@neoine.co.kr`)하거나 `@`를 포함, 중간 공백·제어문자, 빈 라벨(`neoine..co.kr`, 끝 `.`), 한글 등 비 ASCII, 254자 이상이면 기동이 실패한다. 오류 문구는 "ad_login_domain은 도메인 형식(예: neoine.co.kr)이어야 합니다"이고 입력값을 싣지 않는다.
  - 도메인 없음: 사용자 바인드 이름 = 검색으로 찾은 항목의 DN(기존 동작).
  - 받아들인 위험(2026-11-24 사용자 결정, 코드 리뷰 Major): 검색으로 찾은 항목과 `<아이디>@<도메인>`으로 바인드되는 AD 사용자가 같은 사람인지는 확인하지 않는다. AD에서 한 사람의 `sAMAccountName`(사용자 필터가 보는 값)과 다른 사람의 UPN 앞부분이 같으면 뒤쪽 사람이 자기 비밀번호로 그 아이디로 로그인해 앱의 그 계정(역할 포함)을 쓸 수 있다. 사용자는 "계정 이름은 유일하다"는 이유로 받아들였다 — AD 운영자는 `sAMAccountName`과 UPN 앞부분을 같게 관리해야 한다. 같은 사용자라도 UPN 접미사가 `APP_AD_LOGIN_DOMAIN`과 다른 별칭 사용자는 바인드가 거절되어 401이 된다.
  - 받아들인 위험(잠금): 도메인 값이 실제 AD와 다르면 모든 AD 로그인이 401이 되고(대체 로그인·admin 경고 없음) 실패가 쌓여 계정이 429로 잠길 수 있다. 값을 바꾼 뒤에는 Admin 외부연동의 연결 테스트로 확인한다.
  - 도메인 있음: 사용자 바인드 이름 = `<정규화한 로그인 아이디(AU-R2)>@<도메인>`(예: 아이디 `" KIM "`, 환경변수 `" NEOINE.co.kr "` → `kim@neoine.co.kr`). 검색 결과의 DN이나 속성(`userPrincipalName` 등)으로 만들지 않는다. 검색(필터·Base DN·최대 2건, 0건은 공통 실패, 2건 이상은 `search`)과 프로필 읽기(AU-R8·AU-R8a)는 도메인과 무관하게 같고, 검색이 정확히 1건일 때만 바인드한다.
  - 아이디 형식(AU-R2 `[a-z0-9][a-z0-9._-]{0,63}`)이 `@`·`,`·`=`·`\`·공백을 허용하지 않으므로 바인드 이름에 다른 도메인이나 DN 조각을 끼워 넣을 수 없다. 바인드 이름은 LDAP 필터가 아니므로 필터 이스케이프를 하지 않는다.
  - 바인드 결과 판정은 바인드 이름과 무관하게 같다: 거절 코드(49·50·53)는 공통 실패 401(AU-R9, 대체 로그인 없음), 그 밖의 결과 코드는 AD가 답할 수 없는 경우(AU-R10 `unknown`)다. 따라서 도메인 값이 실제 AD와 맞지 않으면 모든 AD 로그인이 401이 되고 대체 로그인·admin 경고도 없다(운영자는 Admin > 외부연동 연결 테스트의 `bind` 단계 실패로 확인, IN-R11).
  - 같은 규칙을 로그인(AU-R7), 연결 테스트·AD 설정 저장의 현재 admin 확인(IN-R11 ②), 최초 설정의 AD 첫 admin 등록(SU-R11)이 모두 쓴다(모두 같은 `DirectoryAuthenticator.authenticate`). Base DN 탐색(IN-R11 ①)과 서비스 계정 바인드는 도메인과 무관하다.
  - 바인드 이름은 응답·로그·예외 문구에 쓰지 않는다(로그의 아이디는 AU-R23의 짧은 해시만).
- **AU-R8** AD 인증이 성공하면 같은 아이디의 재직 사용자 행이 정확히 하나일 때만 로그인된다. 미등록·퇴사 → 공통 실패. 재직 행이 둘 이상 → 공통 실패, 어느 행도 바꾸지 않고 해시도 저장하지 않으며 경고 로그(건수와 아이디의 짧은 해시만)를 남긴다. 퇴사 행과 재직 행이 함께 있으면 재직 행으로 로그인한다. 성공하면 같은 트랜잭션에서 `last_login_at` = 지금, 표시 이름·이메일을 AD 값으로 덮어쓰고(이름: NUL 제거·trim, 비면 비움, 200자 초과면 200자로 자름 / 이메일: 비었거나 254자 초과거나 `@`가 없으면 비움), AD에 전화번호가 있으면 전화번호도 덮어쓰며(AU-R8a), 그 비밀번호의 새 해시(새 솔트)를 저장한다(기존 해시 덮어씀). 역할은 users 행의 값이다. 실패한 로그인은 해시를 만들거나 바꾸지 않는다.
- **AU-R8a** 전화번호의 AD 값(2026-11-24): AD 로그인의 사용자 검색은 `displayName`·`mail`과 함께 `mobile`·`telephoneNumber`를 읽는다(속성 값이 여럿이면 첫 값). 앞뒤 공백을 지운 `mobile`이 비어 있지 않으면 그 값을, 비었거나 없으면 `telephoneNumber`를 AD 전화번호로 쓴다(`mobile`이 있으면 형식과 무관하게 `mobile`). 고른 값은 NUL 문자를 지우고 앞뒤 공백을 지운 뒤 40자(`users.phone` 길이)를 넘으면 앞 40자로 자르고 끝 공백을 지워 저장한다. 앱의 전화번호 형식 규칙(ME-R6·US-R7의 `PhoneNumber`)으로 거르지 않으므로 숫자·기호 형식이 달라도 그대로 저장된다. 두 속성이 모두 없거나 비었으면(서비스 계정이 읽지 못한 경우 포함, NUL을 지운 뒤 비는 경우 포함) **기존 전화번호를 그대로 둔다**(이름·이메일의 "비면 비움"과 다름). AD 값이 있으면 앱에서 입력·수정해 둔 전화번호(ME-R7·US-R4·US-R14)도 그 로그인 때 AD 값으로 바뀐다. 대체 로그인(AU-R10)과 앱 계정 로그인(AU-R12)은 전화번호를 바꾸지 않는다.
- **AU-R9** AD가 응답해 거절하면(사용자 비밀번호 바인드 거부, 검색 0건) 공통 실패 401이고 대체 로그인을 하지 않는다(저장 해시와 같은 비밀번호여도 401).
- **AU-R10** 대체 로그인은 AD가 답할 수 없을 때만 한다. 경고 단계와 원래 오류:

  | 상황 | 경고 단계 | 대체 실패 시 응답 |
  | --- | --- | --- |
  | AD 설정 행 없음(AD를 부르지 않음) | `not_configured` | 409 `invalid-state` "AD 서버가 아직 등록되지 않았습니다" |
  | 연결 실패·타임아웃 | `connect` | 503 `directory-unavailable` |
  | TLS(SSL/StartTLS) 실패 | `tls` | 503 |
  | 서비스 계정 바인드 실패 | `service_bind` | 503 |
  | Base DN 오류(RootDSE·검색 결과 코드가 성공 아님) | `base_dn` | 503 |
  | 사용자 필터 검색 2건 이상 | `search` | 503 |
  | 저장된 바인드 비밀번호 복호화 실패 | `credential_unreadable` | 503 |
  | 그 밖의 통신 실패(단계 정보 없음) | `unknown` | 503 |

  재직 사용자이고 저장 해시가 비밀번호와 맞으면 세션을 발급하고 `last_login_at`만 갱신한다(이름·이메일·전화·해시는 그대로). 경고 로그 "AD 대체 로그인 stage=<단계> login_id_hash=<짧은 해시>"를 남긴다. 미등록·퇴사·해시 없음·불일치·재직 행 중복이면 위 표의 원래 오류로 응답하고(어느 경우든 같은 응답이라 아이디 존재·해시 보유 여부가 드러나지 않는다) 실패 1회로 센다. 사용자·해시가 없어도 같은 비용의 검증(더미 계산)을 한다. 503의 `detail`은 원인과 무관하게 고정 문구 "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"이고 원인은 응답에 없다(PL-R14).
- **AU-R11** 대체 로그인으로 들어온 사용자가 admin이면 응답 `directory_warning` = `{stage, message}`(문구는 2.8 표), admin이 아니면 null이다. AD 로그인과 앱 계정 로그인은 항상 null이다.

앱 계정(local) 로그인
- **AU-R12** local 모드는 저장된 해시로만 인증한다. 재직 사용자이고 해시가 맞으면 세션을 발급하고 `last_login_at`만 갱신한다(이름·이메일·전화는 그대로). 없는 아이디·퇴사·해시 없음·불일치·재직 행 중복은 모두 공통 실패이고 같은 비용의 검증(더미 계산)을 한다. 경고는 없다. 시도 제한은 AD와 같은 카운터를 쓴다.

비밀번호 해시
- **AU-R13** 새 해시는 `scrypt$ln=17,r=8,p=1$<salt>$<hash>`(salt 16바이트, hash 32바이트, base64 패딩 없음)이고 같은 비밀번호도 매번 솔트가 다르다. 검증은 저장된 문자열의 파라미터로 다시 계산한다(예전 `ln=14` 해시도 검증됨). 파라미터가 범위(ln 10~20, r 1~16, p 1~4, salt 8~64바이트, hash 16~64바이트) 밖이거나 형식이 틀리면 계산하지 않고 불일치다. 저장 해시가 없으면 기본 비용으로 더미 계산을 한 뒤 불일치다. 계산은 이벤트 루프 밖 스레드에서 한다.

시도 제한
- **AU-R14** 로그인 실패는 아이디별·IP별 두 카운터로 센다. 기본값: 아이디 5회, IP 30회, 창 15분, 잠금 15분(설정 2.2, 각 1 이상이고 0 이하면 기동 실패). 형식 검사(AU-R1~R3)를 통과한 로그인은 AD·해시 검증 전에 두 카운터를 1회씩 선점한다. 어느 카운터든 잠겨 있으면 429 `too-many-attempts` "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"이고 AD·해시를 부르지 않는다(올바른 비밀번호도 429). 없는 아이디도 같은 방식으로 센다. 카운터는 DB에 있어 여러 서버 인스턴스가 공유한다. IP는 요청의 접속 주소(`request.client.host`, 없으면 `unknown`)다.
- **AU-R15** 집계: 로그인 성공(AD·대체·local)은 그 아이디 카운터를 지우고 IP 선점 1회를 되돌린다(성공은 IP 한도를 쓰지 않는다). 실패(AU-R4의 401, AU-R10의 409·503, AU-R5)는 선점이 실패 1회로 남는다. 실패가 한도에 이르면 그 시각 + 잠금 시간까지 잠기고, 잠금 끝 시각이 되면 풀린다(그 시각 직전까지 잠김). 창 시작부터 창 길이 이상 지났거나 잠금이 풀린 뒤의 다음 실패는 1부터 다시 센다. 카운터 키는 `HMAC-SHA256(jwt_secret, "acct:<정규화 아이디>")`·`HMAC-SHA256(jwt_secret, "ip:<접속 주소>")`이며 원본 아이디·IP는 저장하지 않는다.

세션
- **AU-R16** 로그인에 성공하면 256비트 난수 토큰을 만들고 DB에는 그 SHA-256 해시만 저장한다. 만료 = 발급 시각 + `session_ttl_hours`. 응답에 쿠키 `neoine_session=<토큰>`을 `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age`=TTL초로 심고 `cookie_secure`가 true면 `Secure`를 붙인다. 다른 쿠키(폐지된 `neoine_login` 등)는 심지 않는다. 발급 직전 사용자가 삭제되었으면 공통 실패 401이다. 세션은 요청으로 연장되지 않는다(만료 시각 고정).
- **AU-R17** 로그인 성공 응답은 200 `LoginResponse` `{user_id, subject, email, name, role, directory_warning}`이다(값은 users 행 기준 `Principal`, `name`은 비면 subject).
- **AU-R18** 보호 경로의 요청마다 쿠키 토큰의 해시로 세션을 찾는다. 쿠키 없음·빈 값·발급한 적 없는 토큰·만료(지금 ≥ 만료 시각)·폐기·사용자 행 없음·퇴사면 401 `unauthenticated` "로그인이 필요합니다"(PL-R5)다. 역할·이름·이메일은 매 요청 users 행에서 다시 읽으므로 역할 변경·퇴사·삭제는 기존 세션의 다음 요청부터 반영된다. 세션은 users 행 id를 가리키므로 같은 아이디로 다시 등록해도 이전 세션은 살아나지 않는다.
- **AU-R19** `GET /auth/me`는 로그인한 모든 역할에게 200 `PrincipalResponse` `{user_id, subject, email, name, role}`(키는 정확히 이 다섯)를 준다.
- **AU-R20** `POST /auth/logout`은 로그인 없이 부를 수 있고(CSRF 헤더는 필요, PL-R9) 항상 204다. 응답은 `neoine_session` 쿠키를 지운다(만료된 Set-Cookie, `Path=/`, `Secure`는 `cookie_secure`). 쿠키가 유효한 세션이면 폐기 시각을 기록해 이후 그 토큰은 401이다. 쿠키 없음·모르는 토큰·이미 폐기된 토큰이면 아무것도 바꾸지 않고 204다.

인증 설정 조회
- **AU-R21** `GET /auth/config`는 공개이고 200 `{directory_login, needs_directory_setup, needs_storage_setup, needs_admin_setup, auth_mode}`(키는 정확히 이 다섯, `dev_login`·OIDC 값 없음)다. 재직 admin 있음 = A, AD 설정 행 있음 = D, 저장 위치 설정 있음 = S, mode = effective mode(AU-R22), AD 단계 완료 = `mode == local` 또는 (`mode == ad` 그리고 D)일 때: `directory_login` = D, `needs_directory_setup` = not A and not AD 단계 완료, `needs_storage_setup` = not A and not S, `needs_admin_setup` = not A and S and AD 단계 완료, `auth_mode` = mode(`"ad"`·`"local"`·null). 단계 진행 자체는 SU.
- **AU-R22** effective mode: `auth_settings` 행이 있으면 그 값, 없으면 재직 admin이나 AD 설정 행이 있으면(인증 방식 도입 전부터 쓰던 시스템) `ad`, 둘 다 없으면 미선택(null). 로그인(AU-R6)·설정 조회(AU-R21)와 SU·IN·US·ME의 모드 검사가 이 규칙을 쓴다.

비밀 비노출·폐지 경로·계약
- **AU-R23** 비밀번호 원문은 어떤 응답·로그·예외 문구·DB 행(users, auth_sessions, login_failures, user_password_hashes)에도 남지 않는다. 해시 값과 세션 토큰 원문은 로그에 쓰지 않는다. 로그에 아이디가 필요하면 짧은 해시만 쓴다. openapi의 로그인 요청 `password`는 `format: password`, `writeOnly: true`이고 로그인 응답에 비밀번호 필드가 없다(PL-R23).
- **AU-R24** 폐지된 경로는 없다: `POST /auth/dev-login`은 404이고 세션 쿠키를 만들지 않으며, openapi에 그 경로와 `DevLoginRequest` 스키마가 없다. 예전 OIDC 흐름의 `GET /auth/login`(로그인은 POST만 있음)은 404 또는 405, `GET /auth/callback`은 404이며 둘 다 `Location` 헤더 없이 어디로도 리다이렉트하지 않는다.
- **AU-R25** openapi에 `POST /auth/login`은 200과 401·409·422·429·503(Problem), `GET /auth/me`는 401을 문서화한다.

화면(frontend)
- **AU-R26** 로그인 화면 `/login`(공개, PL-R32): 이미 로그인했으면(`/auth/me` 성공) `/`로 바꾼다(결국 Deals 목록). 인증 설정을 읽는 동안 "불러오는 중…"만 보인다. 설정이 최초 설정 필요를 알리면 `/setup`으로 보낸다(SU). 그 밖에는 제목 "neoine-sales", 오류 배너, 폼(라벨 "아이디" `autocomplete="username"`, "비밀번호" `type=password` `autocomplete="current-password"`), 버튼은 "로그인" 하나다. 빠른 로그인 영역·역할 버튼·"아무 비밀번호" 안내·최초 설정 링크가 없다. 인증 설정을 읽지 못해도 폼은 보이고 배너에 그 오류 문구(PL-R37)가 보인다.
- **AU-R27** 제출(버튼 또는 Enter): 아이디는 앞뒤 공백을 지워, 비밀번호는 그대로 보낸다. 화면은 빈 칸을 따로 검사하지 않는다(서버 판정, Q1). 요청 중에는 "로그인" 버튼이 비활성이다. 성공하면 내 정보 캐시를 응답 사용자로 바꾸고 `/`로 간다. 실패하면 배너(`role="alert"`)에 서버 문구를 보이고 비밀번호 칸만 비우며(아이디 유지) `/login`에 머문다. 입력한 비밀번호는 요청 캐시(mutation)에 남지 않는다.
- **AU-R28** AD 경고 팝업: 로그인 응답의 `directory_warning`이 있으면 로그인 직후 첫 보호 화면에 대화상자 "AD 연결 경고"와 서버 `message`를 그대로 보인다. 버튼 "닫기"는 닫고, "외부연동 설정으로 이동"은 닫고 `/admin/integrations`로 간다. 닫거나 이동한 뒤에는 화면을 옮겨도 다시 보이지 않는다. 경고는 메모리(쿼리 캐시)에만 두고 브라우저 저장소(localStorage·sessionStorage)에 남기지 않는다. 로그인 없이 연 세션(새로고침 등)에는 보이지 않고, 로그아웃하면 지워지며, 경고 없이 다시 로그인하면 이전 경고는 보이지 않는다.
- **AU-R29** 로그아웃(`useLogout`): `POST /auth/logout`이 성공하면 쿼리 캐시 전체를 비우고(내 정보·경고 포함) 호출한 화면이 `/login`으로 보낸다. 이후 내 정보 조회는 401이다. 로그아웃 버튼의 자리는 ME.
- **AU-R30** 인증 게이트웨이: `me()`는 `GET /auth/me`를 `{id: user_id, loginId: subject, name, role}`로 바꾼다(email은 쓰지 않음). `login()`은 같은 사용자와 `directoryWarning`(`directory_warning`이 null이거나 키가 없으면 null)을 돌려준다. `logout()`은 204를 성공으로 본다. `config()`는 `{authMode: auth_mode ?? null, needsSetup: needs_directory_setup || needs_storage_setup || needs_admin_setup}`다. 실패는 PL-R39대로 `ApiError`(401은 kind `unauthorized`, 문구는 서버 `detail`)다. Fake 게이트웨이도 같은 계약을 따른다(Q1).

### 2.4 상태와 전이

세션(`auth_sessions` 행)

| 상태 | 들어오는 조건 | 나가는 조건 |
| --- | --- | --- |
| 활성 | 로그인 성공(AU-R16) | 만료 시각 도달 → 만료, 로그아웃 → 폐기 |
| 만료 | 지금 ≥ `expires_at` | 없음(행은 남음) |
| 폐기 | 로그아웃(AU-R20). 비밀번호 재설정·변경에 의한 종료는 US·ME | 없음 |

활성 세션이라도 사용자가 퇴사·삭제되면 인증은 실패한다(AU-R18).

로그인 카운터(키마다)

| 상태 | 조건 | 다음 |
| --- | --- | --- |
| 없음/0 | 성공 뒤(아이디 키 삭제) | 실패 → 1 |
| 1~(한도−1) | 창 안의 실패 | 실패 → +1, 창 경과 뒤 실패 → 1 |
| 잠김 | 실패가 한도 도달 | 잠금 끝 시각에 풀림 → 다음 실패는 1 |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `POST /auth/login` | 가능(공개) | 가능 | 가능 | 가능 |
| `POST /auth/logout` | 가능(공개, 204) | 가능 | 가능 | 가능 |
| `GET /auth/config` | 가능(공개) | 가능 | 가능 | 가능 |
| `GET /auth/me` | 401 | 가능 | 가능 | 가능 |
| AD 경고(`directory_warning`) 받기 | — | 받지 않음 | 받지 않음 | 대체 로그인일 때 받음 |
| 화면 `/login` | 열림 | `/`로 | `/`로 | `/`로 |

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| POST `/auth/login` | `X-Requested-With`, 본문 `{"login_id": "kim", "password": "…"}` | 200 `LoginResponse` + `Set-Cookie: neoine_session=…; HttpOnly; Max-Age=28800; Path=/; SameSite=lax[; Secure]` | 401 `unauthenticated`, 403 `csrf`, 409 `invalid-state`, 422 `request-validation`, 429 `too-many-attempts`, 503 `directory-unavailable` |
| POST `/auth/logout` | `X-Requested-With`, 쿠키(선택) | 204 + 쿠키 삭제 | 403 `csrf` |
| GET `/auth/me` | 쿠키 | 200 `PrincipalResponse` | 401 `unauthenticated` |
| GET `/auth/config` | — | 200 `AuthConfigResponse` | — |

- `LoginResponse` 예: `{"user_id": 3, "subject": "root", "email": "root@example.com", "name": "최관리", "role": "admin", "directory_warning": {"stage": "connect", "message": "AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. 호스트·포트·방화벽을 확인하세요."}}`. `directory_warning`은 항상 키가 있고 값은 객체 또는 null. `stage` enum: `not_configured`, `connect`, `tls`, `service_bind`, `base_dn`, `search`, `credential_unreadable`, `unknown`.
- `AuthConfigResponse` 예: `{"directory_login": true, "needs_directory_setup": false, "needs_storage_setup": false, "needs_admin_setup": false, "auth_mode": "ad"}`.
- 라우터: `routers/auth_login.py`(login), `routers/auth.py`(config·logout·me). 유스케이스: `PasswordLogin`(→ `DirectoryLogin`·`FallbackLogin`·`LocalLogin`), `IssueSession`, `Authenticate`, `Logout`, `GetAuthStatus`. Port: `DirectoryAuthenticator`, `PasswordHasher`, `SecretCipher`, `Clock`, UoW 저장소(`sessions`, `login_failures`, `password_hashes`, `users`, `directory_settings`, `storage_settings`, `auth_settings`). 새 오류 type 없음.

### 2.7 화면 동작

AU-R26~AU-R30. 보호 화면 가드·401 시 `/login` 이동은 PL-R29, 첫 서버 시각 동기는 TM-R11, `/login` → `/setup`은 SU, 사용자 메뉴와 "이름 (역할)" 표시는 ME.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구 |
| --- | --- | --- |
| 인증 실패(AU-R4) | 401 `unauthenticated` | 아이디 또는 비밀번호가 올바르지 않습니다 |
| 세션 없음·만료·폐기·퇴사 | 401 `unauthenticated` | 로그인이 필요합니다 |
| 잠김 | 429 `too-many-attempts` (title Too Many Attempts) | 로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요 |
| AD 설정 없음 + 대체 실패 | 409 `invalid-state` (title Invalid State) | AD 서버가 아직 등록되지 않았습니다 |
| AD 불가 + 대체 실패 | 503 `directory-unavailable` (title Directory Unavailable) | 인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요 |
| 본문 형식 | 422 `request-validation` | 요청 형식이 올바르지 않습니다 (+ `errors`, 입력값 없음) |

admin 경고 문구(`directory_warning.message`):

| stage | message |
| --- | --- |
| `not_configured` | AD 설정이 없어 이전에 로그인한 비밀번호로 로그인했습니다. Admin > 외부연동에서 AD 설정을 등록하세요. |
| `connect` | AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. 호스트·포트·방화벽을 확인하세요. |
| `tls` | AD 보안 연결(SSL/StartTLS)을 맺지 못해 이전에 로그인한 비밀번호로 로그인했습니다. 보안 연결 방식과 포트를 확인하세요. |
| `service_bind` | 바인드 계정으로 AD에 로그인하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. 바인드 계정과 비밀번호를 확인하세요. |
| `base_dn` | AD 검색 기준(Base DN)으로 사용자를 찾지 못해 이전에 로그인한 비밀번호로 로그인했습니다. AD 설정을 다시 저장하세요. |
| `search` | 사용자 필터에 맞는 AD 사용자가 둘 이상이라 이전에 로그인한 비밀번호로 로그인했습니다. 사용자 필터를 확인하세요. |
| `credential_unreadable` | 저장된 바인드 비밀번호를 읽을 수 없어(암호화 키 변경 여부 확인) 이전에 로그인한 비밀번호로 로그인했습니다. 외부연동에서 바인드 비밀번호를 다시 입력하세요. |
| `unknown` | AD 서버와 통신하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. AD 설정과 서버 상태를 확인하세요. |

화면 문구: 대화상자 제목 "AD 연결 경고", 버튼 "닫기"·"외부연동 설정으로 이동", 로딩 "불러오는 중…", 실패 배너는 서버 `detail`(PL-R37).

## 3. Business use case

### AU-UC1 AD 로그인
- 행위자: 등록된 사용자(AD 계정 보유)
- 사전 조건: effective mode가 `ad`(또는 미선택), AD 설정 저장됨, 계정이 잠기지 않음
- 기본 흐름: 아이디·비밀번호 제출 → 형식 검사 → 시도 선점 → AD search-then-bind(사용자 바인드 이름 AU-R7a) → 재직 행 확인 → 프로필·로그인 시각·해시 갱신 → 세션 발급·쿠키 → 200(AU-R1~R8, R14~R17)
- 대안: AD가 답하지 못하면 AU-UC2
- 예외: 형식 오류·미등록·퇴사·AD 거절·중복 행·예약 아이디 → 401(AU-R4), 잠김 → 429
- 결과: 세션 쿠키, 사용자 정보, `directory_warning` null

### AU-UC2 AD 장애 중 대체 로그인
- 행위자: 예전에 AD로 로그인한 적이 있는 사용자
- 사전 조건: AD 설정 없음 또는 AD가 답하지 못함(AU-R10 표)
- 기본 흐름: AU-UC1에서 AD 단계가 실패 → 저장 해시 검증 → 로그인 시각만 갱신 → 세션 발급 → 200, admin이면 경고(AU-R10·R11)
- 예외: 해시 없음·불일치·미등록·퇴사 → 409(설정 없음) 또는 503, 실패 1회
- 결과: admin은 경고 단계·문구를 받는다

### AU-UC3 앱 계정(local) 로그인
- 행위자: local 모드의 등록된 사용자
- 사전 조건: effective mode가 `local`
- 기본 흐름: 제출 → 형식 검사 → 시도 선점 → 저장 해시 검증 → 로그인 시각 갱신 → 세션 발급 → 200(AU-R12)
- 예외: 401(공통), 429
- 결과: 세션 쿠키, 경고 없음, AD 호출 없음

### AU-UC4 로그인 시도 제한
- 행위자: 로그인하려는 사람(공격자 포함)
- 기본 흐름: 실패가 아이디 5회·IP 30회에 이르면 잠금 15분(AU-R14·R15)
- 대안: 성공하면 아이디 카운터 삭제, 창이 지나면 다시 셈
- 결과: 잠금 중에는 올바른 비밀번호도 429, AD·해시 호출 없음

### AU-UC5 요청마다 세션 확인
- 행위자: 로그인한 사용자(모든 보호 요청)
- 기본 흐름: 쿠키 토큰 → 세션 조회 → 활성·재직 확인 → users 행의 역할로 Principal(AU-R18)
- 예외: 없음·만료·폐기·퇴사·삭제 → 401
- 결과: 역할 변경·퇴사가 다음 요청에 반영

### AU-UC6 로그아웃
- 행위자: 로그인한 사용자(또는 세션이 없는 방문자)
- 기본 흐름: `POST /auth/logout` → 세션 폐기 → 쿠키 삭제 → 204 → 화면은 캐시를 비우고 `/login`(AU-R20·R29)
- 대안: 세션이 없거나 이미 폐기 → 204, 변화 없음
- 결과: 이후 그 토큰은 401

### AU-UC7 내 정보·인증 설정 조회
- 행위자: 로그인한 사용자(내 정보), 누구나(인증 설정)
- 기본 흐름: `GET /auth/me`(AU-R19), `GET /auth/config`(AU-R21·R22)
- 결과: 화면이 로그인 상태·역할과 최초 설정 필요 여부를 안다

### AU-UC8 로그인 화면 사용과 admin AD 경고 확인
- 행위자: 미인증 방문자, admin
- 기본 흐름: `/login` 열기 → 폼 입력 → 성공 시 `/` → (대체 로그인 admin이면) "AD 연결 경고" 대화상자 → 닫기 또는 외부연동으로 이동(AU-R26~R28)
- 예외: 실패 문구·비밀번호 칸 비움, 설정 읽기 실패 배너
- 결과: 경고는 한 번만 보이고 브라우저에 남지 않는다

## 4. BDD 테스트 케이스

등장 인물: root(admin), kim(sales), viewer(user), old(퇴사자), nobody(미등록). "AD 대역"은 `DirectoryAuthenticator` Fake, "해시"는 `PasswordHasher` Fake(또는 scrypt), 시계는 `FixedClock`. 따로 적지 않으면 effective mode는 `ad`, AD 설정은 저장되어 있고 AD 대역은 정상 응답한다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| AU-001 | 등록된 사용자가 AD 비밀번호로 로그인하면 200과 HttpOnly·Lax 세션 쿠키를 받는다 | AU-R7, AU-R8, AU-R16, AU-R17, AU-UC1 | backend | `web/test_auth_login_routes.py::test_login_returns_200_with_an_http_only_lax_session_cookie`<br>`application/test_directory_login.py::test_login_issues_session_for_registered_user`<br>`application/test_directory_login.py::test_a_directory_login_carries_no_directory_warning` |
| AU-002 | cookie_secure가 켜져 있으면 세션 쿠키에 Secure가 붙는다 | AU-R16, AU-UC1 | backend | `web/test_auth_login_routes.py::test_login_cookie_is_secure_when_the_deployment_requires_it` |
| AU-003 | 로그인 응답은 세션 쿠키 말고 다른 쿠키를 심지 않는다 | AU-R16, AU-UC1 | backend | `web/test_auth_login_routes.py::test_login_sets_no_cookie_other_than_the_session_cookie` |
| AU-004 | 앞뒤 공백·대문자가 섞인 아이디도 같은 사용자로 로그인된다 | AU-R2, AU-UC1 | backend | `application/test_directory_login.py::test_login_id_is_normalized_before_lookup` |
| AU-005 | AD 로그인에 성공하면 최근 로그인 시각과 AD의 이름·이메일이 남는다 | AU-R8, AU-UC1 | backend | `application/test_directory_login.py::test_login_updates_last_login_and_profile`<br>`application/test_directory_login.py::test_login_overwrites_profile_with_the_latest_directory_values` |
| AU-006 | AD의 긴 이름은 200자로 자르고 형식이 틀린 이메일은 비운다 | AU-R8, AU-UC1 | backend | `application/test_login_input_rules.py::test_login_truncates_a_long_directory_name_to_200_chars`<br>`application/test_login_input_rules.py::test_login_clears_a_malformed_directory_email`<br>`application/test_directory_login.py::test_login_succeeds_when_the_directory_display_name_is_256_chars` |
| AU-007 | AD 로그인에 성공할 때마다 새 솔트의 해시로 덮어쓴다 | AU-R8, AU-R13, AU-UC1 | backend | `application/test_directory_login.py::test_successful_directory_login_saves_new_password_hash`<br>`application/test_directory_login.py::test_hash_follows_the_latest_directory_password` |
| AU-008 | 로그인한 사용자의 역할과 id는 users 행의 값이다 | AU-R8, AU-R17, AU-UC1 | backend | `application/test_directory_login.py::test_login_principal_carries_the_users_row_id`<br>`application/test_directory_login.py::test_login_role_comes_from_the_users_table` |
| AU-009 | 퇴사 행과 재직 행이 함께 있으면 재직 행으로 로그인된다 | AU-R8, AU-UC1 | backend | `application/test_directory_login.py::test_login_after_reregistration_uses_the_new_row_not_the_resigned_one` |
| AU-010 | AD에는 있지만 등록되지 않은 아이디는 401이고 해시를 만들지 않는다 | AU-R8, AU-R4, AU-UC1 | backend | `application/test_directory_login.py::test_login_failures_share_one_message_and_issue_no_session`<br>`application/test_directory_login.py::test_login_of_an_unregistered_user_saves_no_hash` |
| AU-011 | 퇴사한 사용자는 AD 계정이 있어도 401이다 | AU-R8, AU-R4, AU-UC1 | backend | `application/test_directory_login.py::test_login_failures_share_one_message_and_issue_no_session` |
| AU-012 | 같은 아이디의 재직 행이 둘이면 401이고 아무것도 바꾸지 않는다 | AU-R8, AU-R4, AU-UC1 | backend | `application/test_directory_login_ambiguous.py::test_login_with_duplicate_active_rows_fails_with_the_common_message`<br>`application/test_directory_login_ambiguous.py::test_login_with_duplicate_active_rows_logs_a_warning_without_secrets`<br>`application/test_directory_login_ambiguous.py::test_login_with_duplicate_active_rows_updates_neither_row`<br>`application/test_directory_login_ambiguous.py::test_login_with_duplicate_active_rows_saves_no_hash` |
| AU-013 | AD가 비밀번호를 거절하면 저장 해시가 맞아도 401이고 대체 로그인하지 않는다 | AU-R9, AU-R6, AU-UC1 | backend | `application/test_directory_login.py::test_rejected_password_gets_401_even_when_hash_matches`<br>`application/test_directory_login.py::test_failed_directory_login_saves_no_hash` |
| AU-014 | AD 검색에 사용자가 없으면 401이고 실패 1회로 센다 | AU-R9, AU-R15, AU-UC1 | backend | `application/test_directory_login.py::test_rejected_password_gets_401_even_when_hash_matches` |
| AU-015 | AD 로그인은 매번 DB의 현재 설정·Base DN·복호화한 바인드 비밀번호를 쓴다 | AU-R7, AU-UC1 | backend | `application/test_directory_login.py::test_login_passes_stored_base_dn_and_unsealed_password`<br>`application/test_directory_login.py::test_login_uses_the_current_settings_each_time` |
| AU-016 | 형식이 틀린 아이디는 401이고 AD를 부르지 않으며 시도에 세지 않는다 | AU-R2, AU-R4, AU-R15, AU-UC1 | backend | `application/test_login_input_rules.py::test_malformed_login_id_is_the_common_failure_and_is_not_counted`<br>`application/test_directory_login.py::test_login_failures_share_one_message_and_issue_no_session` |
| AU-017 | 빈 값·공백·NUL 비밀번호는 401이고 AD를 부르지 않는다 | AU-R3, AU-R4, AU-UC1 | backend | `web/test_auth_login_routes.py::test_empty_blank_or_nul_password_is_the_common_401_and_is_not_counted` |
| AU-018 | 필드가 빠졌거나 모르는 필드가 있는 로그인 본문은 422다 | AU-R1, AU-UC1 | backend | `web/test_auth_login_routes.py::test_login_body_with_missing_or_unknown_fields_is_422` |
| AU-019 | 너무 긴 아이디·비밀번호는 422이고 입력값을 되돌리지 않으며 상한 길이는 통과한다 | AU-R1, AU-UC1 | backend | `web/test_auth_login_routes.py::test_oversized_login_values_are_422_without_echoing_them`<br>`web/test_auth_login_routes.py::test_login_values_at_the_upper_length_limit_pass_validation` |
| AU-020 | 예약 아이디 셋은 AD에 계정이 있어도 401이고 AD를 부르지 않는다 | AU-R5, AU-UC1, AU-UC3 | backend | `application/test_password_login_retired_ids.py::test_retired_dev_login_id_is_rejected_without_calling_the_directory`<br>`application/test_password_login_retired_ids.py::test_retired_dev_login_id_is_rejected_in_local_mode` |
| AU-021 | 예약 셋이 아닌 dev- 아이디는 일반 흐름으로 로그인된다 | AU-R5, AU-UC1 | backend | `application/test_password_login_retired_ids.py::test_other_ids_can_still_sign_in_in_local_mode`<br>`application/test_password_login_retired_ids.py::test_other_dev_prefixed_id_follows_the_normal_directory_flow` |
| AU-022 | AD 연결이 안 되어도 해시가 있는 sales는 경고 없이 들어온다 | AU-R10, AU-R11, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_login_succeeds_for_each_unavailable_stage`<br>`application/test_directory_login_fallback.py::test_non_admin_fallback_login_has_no_warning` |
| AU-023 | admin의 대체 로그인 응답에는 실패 단계와 그 단계의 안내 문구가 있다 | AU-R10, AU-R11, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_admin_fallback_login_returns_directory_warning`<br>`application/test_fallback_warning.py::test_warning_stages_have_the_documented_values`<br>`application/test_fallback_warning.py::test_warning_stage_follows_the_directory_error_stage`<br>`application/test_fallback_warning.py::test_unreadable_credential_error_is_its_own_stage`<br>`application/test_fallback_warning.py::test_every_stage_has_a_distinct_popup_message`<br>`application/test_fallback_warning.py::test_messages_point_to_what_the_admin_should_check`<br>`application/test_fallback_warning.py::test_fallback_messages_match_the_documented_texts` |
| AU-024 | AD 설정이 없어도 해시가 있는 admin은 not_configured 경고와 함께 들어온다 | AU-R10, AU-R11, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_admin_fallback_login_returns_directory_warning` |
| AU-025 | admin이 아닌 사용자의 대체 로그인에는 경고가 없다 | AU-R11, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_non_admin_fallback_login_has_no_warning` |
| AU-026 | 대체 로그인은 해시·프로필을 바꾸지 않고 로그인 시각과 경고 로그만 남긴다 | AU-R10, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_login_succeeds_for_each_unavailable_stage`<br>`application/test_directory_login_fallback.py::test_fallback_login_logs_a_warning_with_stage_and_hashed_login_id_only` |
| AU-027 | AD가 돌아오면 다음 로그인은 AD를 거치고 해시가 새로 저장된다 | AU-R10, AU-R8, AU-UC2 | backend | `application/test_login_session_lifecycle.py::test_login_after_the_directory_recovers_goes_through_it_and_refreshes_the_hash`<br>`application/test_directory_login_fallback.py::test_fallback_never_runs_when_the_directory_answers` |
| AU-028 | AD 장애 중 틀린 비밀번호는 503 고정 문구이고 실패 1회로 센다 | AU-R10, AU-R15, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_a_wrong_password_never_falls_back_when_the_directory_is_down`<br>`application/test_directory_login_fallback.py::test_fallback_failure_returns_original_error_and_counts_failure` |
| AU-029 | AD 장애 중 해시 없는 사용자와 미등록 아이디는 같은 503을 받는다 | AU-R10, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_failure_returns_original_error_and_counts_failure`<br>`application/test_directory_login_fallback.py::test_fallback_without_hash_still_runs_verify` |
| AU-030 | AD 장애 중 퇴사한 사용자는 저장 해시로도 들어올 수 없다 | AU-R10, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_failure_returns_original_error_and_counts_failure` |
| AU-031 | AD 설정도 해시도 없으면 409이고 AD를 부르지 않으며 실패 1회다 | AU-R10, AU-R15, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_without_a_configuration_fails_with_the_not_configured_message`<br>`application/test_directory_login.py::test_login_without_directory_settings_and_without_a_hash_is_rejected_and_counted` |
| AU-032 | 바인드 비밀번호를 풀 수 없고 해시도 없으면 503이다 | AU-R10, AU-UC2 | backend | `application/test_directory_login_fallback.py::test_fallback_failure_with_an_unreadable_credential_is_the_unreadable_error` |
| AU-033 | AD 장애 원인이 달라도 503 문구는 같고 원인을 드러내지 않는다 | AU-R10, AU-UC2 | backend | `web/test_auth_login_routes.py::test_directory_outage_without_a_stored_hash_is_503_with_a_fixed_message` |
| AU-034 | 대체 로그인에 성공하면 앞서 쌓인 아이디 실패 횟수가 지워진다 | AU-R15, AU-UC2, AU-UC4 | backend | `application/test_directory_login_fallback.py::test_fallback_login_clears_failures_counted_before` |
| AU-035 | local 모드 사용자는 자기 비밀번호로 로그인하고 경고·프로필 변경이 없다 | AU-R12, AU-R6, AU-UC3 | backend | `application/test_local_login.py::test_local_login_with_right_password_returns_the_principal_and_records_login`<br>`application/test_local_login.py::test_local_login_keeps_the_stored_profile`<br>`application/test_local_login.py::test_password_login_in_local_mode_issues_a_session_without_a_warning` |
| AU-036 | local 모드의 틀린 비밀번호·없는 아이디·해시 없음은 같은 401이다 | AU-R12, AU-R4, AU-UC3 | backend | `application/test_local_login.py::test_local_login_wrong_password_is_login_failed_and_does_not_record_login`<br>`application/test_local_login.py::test_local_login_unknown_id_verifies_dummy_and_fails_alike`<br>`application/test_local_login.py::test_local_login_without_hash_fails_with_the_same_cost`<br>`application/test_local_login.py::test_password_login_wrong_password_counts_one_failure`<br>`application/test_local_login.py::test_password_login_unknown_id_counts_and_fails_alike` |
| AU-037 | local 모드의 퇴사자는 올바른 비밀번호로도 401이다 | AU-R12, AU-UC3 | backend | `application/test_local_login.py::test_local_login_resigned_user_fails_with_the_same_cost` |
| AU-038 | local 모드에서 같은 아이디의 재직 행이 둘이면 401이다 | AU-R12, AU-UC3 | backend | `application/test_local_login.py::test_local_login_ambiguous_login_id_fails` |
| AU-039 | local 모드 로그인은 성공이든 실패든 AD를 부르지 않는다 | AU-R6, AU-R12, AU-UC3 | backend | `application/test_local_login.py::test_password_login_in_local_mode_never_calls_directory` |
| AU-040 | 인증 방식 행이 없고 admin이 있는 시스템은 AD 로그인으로 처리한다 | AU-R6, AU-R22, AU-UC1 | backend | `application/test_local_login.py::test_password_login_without_mode_row_and_admin_uses_directory`<br>`application/test_auth_status_modes.py::test_auth_status_without_mode_row_but_with_admin_reports_ad` |
| AU-041 | ad 모드에서 AD가 응답하면 local 방식 해시가 맞아도 AD 판정을 따른다 | AU-R6, AU-R9, AU-UC1 | backend | `application/test_local_login.py::test_password_login_in_ad_mode_rejects_a_local_style_hash_when_the_directory_answers` |
| AU-042 | 한 아이디가 5번 실패하면 올바른 비밀번호도 429이고 AD·해시를 부르지 않는다 | AU-R14, AU-UC4 | backend | `application/test_auth_throttle.py::test_account_is_locked_after_the_limit_without_calling_the_directory`<br>`application/test_local_login.py::test_password_login_locked_account_is_429_without_verifying` |
| AU-043 | 한도보다 한 번 적게 실패하면 잠기지 않는다 | AU-R14, AU-UC4 | backend | `application/test_auth_throttle.py::test_failures_below_the_limit_do_not_lock` |
| AU-044 | 잠금은 그 아이디에만 걸린다 | AU-R14, AU-UC4 | backend | `application/test_auth_throttle.py::test_lock_applies_to_that_account_only` |
| AU-045 | 잠금은 잠금 시간이 정확히 지나면 풀린다 | AU-R15, AU-UC4 | backend | `application/test_auth_throttle.py::test_lock_ends_exactly_after_the_lock_duration`<br>`application/test_local_login.py::test_password_login_lock_ends_after_the_lock_duration` |
| AU-046 | 실패 창이 지나면 실패 횟수를 처음부터 다시 센다 | AU-R15, AU-UC4 | backend | `application/test_auth_throttle.py::test_failure_window_expiry_restarts_the_count` |
| AU-047 | 로그인 성공은 아이디 카운터를 지우고 IP 한도를 쓰지 않는다 | AU-R15, AU-UC4 | backend | `application/test_auth_throttle.py::test_success_clears_the_account_counter`<br>`application/test_auth_throttle.py::test_successful_logins_do_not_consume_the_ip_limit`<br>`application/test_local_login.py::test_password_login_success_clears_the_account_counter` |
| AU-048 | 한 IP에서 서로 다른 아이디로 30번 실패하면 다른 아이디도 429다 | AU-R14, AU-UC4 | backend | `application/test_auth_throttle.py::test_ip_is_locked_after_its_limit_across_different_accounts` |
| AU-049 | 없는 아이디도 같은 방식으로 제한된다 | AU-R14, AU-UC4 | backend | `application/test_auth_throttle.py::test_unknown_login_ids_are_throttled_the_same_way`<br>`application/test_auth_throttle.py::test_unregistered_directory_user_counts_as_a_failure`<br>`application/test_local_login.py` |
| AU-050 | 실패 카운터 키는 비밀 기반 해시이고 다른 서버 인스턴스와 공유된다 | AU-R14, AU-R15, AU-R23, AU-UC4 | backend | `application/test_auth_throttle.py::test_counter_keys_are_keyed_hashes_not_raw_values`<br>`application/test_auth_throttle.py::test_failure_counters_are_shared_between_app_instances` |
| AU-051 | AD 장애 중 대체 실패가 한도에 이르면 올바른 비밀번호도 429다 | AU-R14, AU-R10, AU-UC4 | backend | `application/test_auth_throttle.py::test_directory_outage_without_a_stored_hash_counts_toward_the_limit`<br>`application/test_directory_login_fallback.py::test_fallback_login_is_blocked_while_locked` |
| AU-052 | 시도 제한 기본값은 5·30·15분·15분이고 1 미만은 거부된다 | AU-R14, AU-UC4 | backend | `test_settings_login.py::test_login_throttle_defaults_match_the_plan`<br>`test_settings_login.py::test_login_throttle_values_reject_out_of_range_input`<br>`test_settings_login.py::test_login_throttle_values_accept_the_minimum` |
| AU-053 | 발급한 세션은 만료 전까지 인증되고 만료 시각부터 401이다 | AU-R16, AU-R18, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_token_authenticates_the_registered_user_until_it_expires`<br>`domain/test_auth.py::TestAuthSession::test_is_active_until_it_expires` |
| AU-054 | 저장소에는 토큰 해시만 있고 토큰은 매번 다르다 | AU-R16, AU-R23, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_only_the_hash_of_the_token_is_stored`<br>`application/test_authenticate_use_case.py::test_tokens_are_unique` |
| AU-055 | 쿠키가 없거나 발급한 적 없는 토큰이면 401이다 | AU-R18, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_missing_or_unknown_token_is_unauthenticated` |
| AU-056 | users 행의 역할·이름이 바뀌면 기존 세션의 다음 요청에 반영된다 | AU-R18, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_role_is_read_from_the_users_table_on_every_request`<br>`application/test_authenticate_use_case.py::test_profile_comes_from_the_users_table` |
| AU-057 | 퇴사·삭제된 사용자의 세션은 다음 요청부터 401이고 다시 로그인할 수도 없다 | AU-R18, AU-R8, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_physically_deleted_users_session_is_rejected_from_the_next_request`<br>`application/test_authenticate_use_case.py::test_resigned_users_token_is_rejected_even_if_the_session_row_survives`<br>`application/test_login_session_lifecycle.py::test_deleted_user_cannot_log_in_again_and_the_old_session_is_dead` |
| AU-058 | 같은 아이디로 다시 등록해도 이전 세션은 401이고 새 사용자는 새로 로그인한다 | AU-R18, AU-UC5 | backend | `application/test_authenticate_use_case.py::test_a_new_active_row_with_the_same_login_id_does_not_revive_the_old_token`<br>`application/test_login_session_lifecycle.py::test_reregistered_login_id_logs_in_as_the_new_row_while_the_old_session_stays_dead` |
| AU-059 | 내 정보는 세 역할 모두 자기 users 행의 다섯 값을 받는다 | AU-R19, AU-UC7 | backend | `web/test_auth_login_routes.py::test_me_returns_the_five_values_of_the_users_row_for_every_role` |
| AU-060 | 로그아웃하면 세션이 폐기되고 쿠키가 지워져 이후 요청은 401이다 | AU-R20, AU-UC6 | backend | `application/test_authenticate_use_case.py::test_logout_revokes_the_session`<br>`web/test_auth_login_routes.py::test_logout_revokes_the_session_and_clears_the_cookie` |
| AU-061 | 세션이 없거나 모르는·폐기된 토큰으로 로그아웃해도 204이고 무해하다 | AU-R20, AU-UC6 | backend | `application/test_authenticate_use_case.py::test_logout_is_idempotent_for_missing_sessions`<br>`application/test_authenticate_use_case.py::test_revoking_twice_is_harmless`<br>`web/test_auth_login_routes.py::test_logout_without_a_usable_session_is_a_harmless_204`<br>`domain/test_auth.py` |
| AU-062 | 인증 설정 조회는 로그인 없이 200이고 키는 정확히 다섯이다 | AU-R21, AU-UC7 | backend | `web/test_auth_login_routes.py::test_auth_config_is_public_with_exactly_the_five_keys`<br>`web/test_auth_routes_dev_login_removed.py::test_auth_config_has_exactly_the_setup_keys` |
| AU-063 | 인증 설정의 단계 값과 auth_mode는 설정 상태에 따라 정해진다 | AU-R21, AU-R22, AU-UC7 | backend | `application/test_auth_status_modes.py::test_auth_status_without_mode_needs_directory_step`<br>`application/test_auth_status_modes.py::test_auth_status_local_mode_skips_directory_step`<br>`application/test_auth_status_modes.py::test_auth_status_local_mode_with_storage_needs_admin`<br>`application/test_auth_status_modes.py::test_auth_status_ad_mode_without_directory_needs_directory`<br>`application/test_auth_status_modes.py::test_auth_status_ad_mode_with_directory_and_storage_needs_admin`<br>`application/test_auth_status_modes.py::test_auth_status_closes_every_step_once_an_admin_exists`<br>`application/test_auth_status_modes.py::test_auth_status_without_mode_row_but_with_admin_reports_ad`<br>`application/test_auth_status_modes.py::test_auth_status_without_mode_row_but_with_directory_reports_ad`<br>`application/test_auth_status_modes.py::test_auth_status_stored_local_mode_beats_a_leftover_directory_row`<br>`application/test_auth_status_storage.py::test_auth_status_flags_follow_the_three_setup_conditions` |
| AU-064 | 폐지된 개발용 로그인·OIDC 경로는 없다 | AU-R24 | backend | `web/test_auth_routes_dev_login_removed.py::test_post_dev_login_is_not_found`<br>`web/test_auth_login_routes.py::test_retired_dev_login_and_oidc_routes_do_not_exist`<br>`web/test_auth_login_routes.py::test_openapi_has_no_dev_login_path_or_schema` |
| AU-065 | 로그인 성공·실패·장애 어디에도 비밀번호 원문이 응답·로그·테이블에 없다 | AU-R23, AU-UC1, AU-UC2 | backend | `web/test_auth_login_routes.py::test_password_never_appears_in_responses_or_logs`<br>`application/test_directory_login.py::test_login_failure_exception_never_contains_the_password`<br>`application/test_directory_login.py::test_login_passes_the_password_only_to_the_directory`<br>`application/test_directory_login.py::test_login_password_never_reaches_stored_rows_in_plain_text`<br>`application/test_directory_login_fallback.py` |
| AU-066 | openapi는 로그인 오류 응답과 비밀번호 칸 표기를 문서화한다 | AU-R25, AU-R23 | backend | `web/test_auth_login_routes.py::test_openapi_documents_the_login_errors_and_the_password_field` |
| AU-067 | 화면: 로그인 화면은 아이디·비밀번호 폼과 로그인 버튼만 보인다 | AU-R26, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > shows the id and password form, no quick login and no any-password guidance`<br>`features/auth/LoginPage.config.test.tsx > shows no quick login area, only the id and password form`<br>`features/auth/LoginPage.config.test.tsx > asks the browser for the right autofill on the login fields`<br>`features/auth/LoginPage.config.test.tsx > never says any password works` |
| AU-068 | 화면: 인증 설정을 읽는 동안 불러오는 중을 보인다 | AU-R26, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > shows only the loading text while the auth config is being read` |
| AU-069 | 화면: 인증 설정을 읽지 못해도 폼과 오류 문구가 보인다 | AU-R26, AU-UC8 | frontend | `features/auth/LoginPage.config.test.tsx > still shows the form and the reason when the config cannot be read` |
| AU-070 | 화면: 이미 로그인했으면 로그인 화면에서 Deals 목록으로 간다 | AU-R26, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > goes to the main page when already signed in` |
| AU-071 | 화면: 로그인에 성공하면 Deals 목록으로 가고 내 정보가 갱신된다 | AU-R27, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > moves to the deals list and refreshes the user after a successful login` |
| AU-072 | 화면: 로그인에 실패하면 서버 문구를 보이고 비밀번호만 비운다 | AU-R27, AU-R4, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > shows the server message for a failed login and clears only the password` |
| AU-073 | 화면: 빈 칸으로 제출해도 서버 판정 문구를 보인다 | AU-R27, AU-R3, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > shows the server verdict for empty fields instead of checking them on the screen`<br>`features/auth/LoginPage.test.tsx > shows the same server verdict when only the id is filled` |
| AU-074 | 화면: 퇴사자 로그인도 같은 실패 문구다 | AU-R27, AU-R4, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > refuses a resigned user with the same message as any other failure` |
| AU-075 | 화면: 아이디 앞뒤 공백을 지워 보낸다 | AU-R27, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > trims the surrounding spaces of the id but sends the password as typed` |
| AU-076 | 화면: 요청 중에는 로그인 버튼이 비활성이다 | AU-R27, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > disables the login button while the request is in flight` |
| AU-077 | 화면: 입력한 비밀번호는 요청 캐시에 남지 않는다 | AU-R27, AU-R23, AU-UC8 | frontend | `features/auth/LoginPage.test.tsx > does not keep the typed password in the mutation cache, on success or failure` |
| AU-078 | 화면: 대체 로그인한 admin에게 로그인 직후 AD 연결 경고를 보인다 | AU-R28, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > shows the server message in a dialog on the first page after login`<br>`features/auth/DirectoryWarningDialog.test.tsx > shows the message of whichever stage the server reports` |
| AU-079 | 화면: 경고에서 외부연동 설정으로 이동하면 다시 보이지 않는다 | AU-R28, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > goes to the integrations page and does not come back after the move` |
| AU-080 | 화면: 경고를 닫으면 화면을 옮겨도 다시 보이지 않는다 | AU-R28, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > closes with the close button and does not show again while moving around` |
| AU-081 | 화면: 경고 없는 로그인이나 로그인 없이 연 세션에는 경고가 없다 | AU-R28, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > shows no dialog when the login response has no warning`<br>`features/auth/DirectoryWarningDialog.test.tsx > shows no dialog when the session was not created by a login with a warning` |
| AU-082 | 화면: 로그아웃하면 경고가 지워지고 다음 로그인의 경고만 보인다 | AU-R28, AU-R29, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > forgets a dismissed warning on logout so the next warning login shows it again`<br>`features/auth/DirectoryWarningDialog.test.tsx > does not show the previous warning after logging in again without one` |
| AU-083 | 화면: 경고는 브라우저 저장소에 남지 않는다 | AU-R28, AU-UC8 | frontend | `features/auth/DirectoryWarningDialog.test.tsx > keeps the warning out of the browser storage` |
| AU-084 | 로그아웃 훅은 캐시를 모두 비우고 이후 내 정보는 401이다 | AU-R29, AU-UC6 | frontend | `data/hooks.test.tsx > useLogout은 쿼리 캐시를 모두 비우고 이후 useMe는 401이다` |
| AU-085 | 게이트웨이: 내 정보와 로그인 응답을 화면 사용자로 바꾸고 경고를 옮긴다 | AU-R30, AU-UC7 | frontend | `gateway/http/auth.test.ts > me reads GET /auth/me and renames user_id and subject`<br>`gateway/http/auth.test.ts > login posts the credentials and returns the signed-in user without a warning`<br>`gateway/http/auth.test.ts > login maps the admin directory warning of a fallback login`<br>`gateway/http/auth.test.ts > login keeps the %s warning stage`<br>`gateway/http/auth.test.ts > login treats a response without the warning key as no warning` |
| AU-086 | 게이트웨이: 로그인 실패 401은 unauthorized와 서버 문구다 | AU-R30, AU-UC8 | frontend | `gateway/http/auth.test.ts > shows the server message and the unauthorized kind for wrong credentials` |
| AU-087 | 게이트웨이: 로그아웃은 204를 성공으로 보고 인증 설정은 설정 필요 여부와 방식으로 바뀐다 | AU-R30, AU-UC6, AU-UC7 | frontend | `gateway/http/auth.test.ts > logout posts to /auth/logout and accepts 204`<br>`gateway/http/auth.test.ts > config exposes only the setup state and auth mode, no quick login`<br>`gateway/http/auth.test.ts > config exposes auth_mode=%s as authMode`<br>`gateway/http/auth.test.ts > config treats a response without auth_mode as no choice yet` |
| AU-088 | 로그인 전 내 정보 훅은 401이고 로그인 훅 성공 뒤 내 정보·권한이 갱신된다 | AU-R27, AU-R30, AU-UC8 | frontend | `data/hooks.test.tsx > 로그인 전에는 useMe가 401 ApiError, usePermissions는 모두 false다`<br>`data/hooks.test.tsx > useLogin 성공 후 useMe와 usePermissions가 갱신된다`<br>`data/hooks.test.tsx > useLogin은 비밀번호가 든 변수를 mutation 캐시에 남기지 않고, 실패는 ApiError로 reject한다` |
| AU-089 | AD 로그인에 성공하면 앱에서 입력해 둔 전화번호를 AD의 mobile 값으로 형식과 무관하게 덮어쓴다 | AU-R8, AU-R8a, AU-UC1 | backend | `application/test_directory_login.py::test_login_overwrites_the_phone_with_the_directory_mobile` |
| AU-090 | AD의 mobile이 없거나 비었으면 telephoneNumber로 덮어쓴다 | AU-R8a, AU-UC1 | backend | `application/test_login_input_rules.py::test_login_uses_the_telephone_number_when_the_mobile_is_blank`<br>`infra/test_ldap_authenticator_phone.py::test_directory_phone_is_mobile_then_telephone_number` |
| AU-091 | AD에 전화번호가 없으면 저장된 전화번호를 그대로 둔다 | AU-R8a, AU-UC1 | backend | `application/test_directory_login.py::test_login_keeps_the_stored_phone_when_the_directory_has_none` |
| AU-092 | AD 전화번호는 NUL·앞뒤 공백을 지우고 40자를 넘으면 40자로 자른다 | AU-R8a, AU-UC1 | backend | `application/test_login_input_rules.py::test_login_cleans_and_truncates_the_directory_phone` |
| AU-093 | 도메인이 설정되어 있으면 사용자 비밀번호 바인드는 아이디@도메인으로 하고 검색·프로필은 그대로다 | AU-R7, AU-R7a, AU-UC1 | backend | `infra/test_ldap_authenticator_upn.py::test_user_bind_uses_login_id_at_domain_when_a_domain_is_set` |
| AU-094 | 도메인 환경변수가 없거나 비어 있으면 찾은 항목의 DN으로 바인드한다 | AU-R7a, AU-UC1 | backend | `infra/test_ldap_authenticator_upn.py::test_user_bind_uses_the_found_dn_without_a_domain`<br>`test_settings_ad_login_domain.py::test_missing_or_blank_domain_means_no_domain` |
| AU-095 | 도메인이 있어도 검색 0건은 사용자 바인드 없이 자격 증명 오류, 2건 이상은 search 단계 오류다 | AU-R7a, AU-R9, AU-R10, AU-UC1, AU-UC2 | backend | `infra/test_ldap_authenticator_upn.py::test_search_outcomes_are_unchanged_with_a_domain` |
| AU-096 | 도메인 바인드를 AD가 거절하면 자격 증명 오류, 그 밖의 결과 코드는 AD 불가다 | AU-R7a, AU-R9, AU-R10, AU-UC1, AU-UC2 | backend | `infra/test_ldap_authenticator_upn.py::test_domain_bind_rejection_is_invalid_credentials_and_other_codes_are_unavailable` |
| AU-097 | 바인드 이름은 정규화한 아이디와 공백 제거·소문자로 정리한 도메인으로 만든다 | AU-R2, AU-R7a, AU-UC1 | backend | `infra/test_ldap_authenticator_upn.py::test_domain_bind_name_uses_the_normalized_login_id`<br>`test_settings_ad_login_domain.py::test_domain_is_trimmed_and_lowercased` |
| AU-098 | 도메인 형식이 틀리면 기동이 실패하고 오류에 값이 나오지 않는다 | AU-R7a | backend | `test_settings_ad_login_domain.py::test_malformed_domain_fails_startup_without_echoing_it`<br>`test_settings_ad_login_domain.py::test_well_formed_domains_are_accepted` |
| AU-099 | 조립된 앱의 LDAP 어댑터는 설정의 도메인을 쓰고 로그인·AD 설정 확인·첫 admin 등록이 같은 어댑터를 쓴다 | AU-R7a, AU-UC1 | backend | `test_container_auth.py::test_container_builds_the_ldap_adapter_with_the_configured_login_domain` |
| AU-100 | 도메인이 있어도 DN·도메인 주입을 노린 아이디로는 사용자 바인드를 하지 않는다 | AU-R7a, AU-R2, AU-UC1 | backend | `infra/test_ldap_authenticator_upn.py::test_hostile_login_id_never_reaches_a_domain_bind` |

### AU-001 등록된 사용자가 AD 비밀번호로 로그인하면 200과 HttpOnly·Lax 세션 쿠키를 받는다
- Given kim(sales)이 재직 사용자로 등록되어 있고 AD 대역이 kim의 비밀번호를 받아들인다
- When `POST /api/v1/auth/login` `{"login_id": "kim", "password": "pw-kim"}`(CSRF 헤더 포함)
- Then 200이고 본문은 `user_id`(kim 행 id)·`subject` "kim"·`name`·`email`·`role` "sales"·`directory_warning` null이며, `Set-Cookie`가 `neoine_session`을 `HttpOnly`, `SameSite=lax`, `Path=/`, `Max-Age=28800`(TTL 8시간)으로 심는다. 그 쿠키로 `GET /api/v1/auth/me`가 200이다

### AU-002 cookie_secure가 켜져 있으면 세션 쿠키에 Secure가 붙는다
- Given `cookie_secure` = true인 앱이고 kim이 등록되어 있다
- When kim이 로그인한다
- Then `neoine_session` 쿠키에 `Secure`가 있다(false인 앱에서는 없다)

### AU-003 로그인 응답은 세션 쿠키 말고 다른 쿠키를 심지 않는다
- Given kim이 등록되어 있다
- When kim이 로그인한다
- Then 응답의 `Set-Cookie`는 `neoine_session` 하나뿐이고 `neoine_login`은 없다

### AU-004 앞뒤 공백·대문자가 섞인 아이디도 같은 사용자로 로그인된다
- Given kim이 등록되어 있다
- When `login_id`를 `"  KIM "`으로 로그인한다
- Then 200이고 `subject`는 "kim"이며 AD 대역은 "kim"으로 불렸다

### AU-005 AD 로그인에 성공하면 최근 로그인 시각과 AD의 이름·이메일이 남는다
- Given kim 행의 이름이 "예전이름", 이메일이 비어 있고 AD 대역이 이름 "김영업", 이메일 "Kim@Example.com"을 준다. 시계는 `2026-11-09T01:00:00Z`
- When kim이 로그인한다
- Then kim 행의 `last_login_at`은 `2026-11-09T01:00:00Z`, 이름은 "김영업"이고 응답 `name`은 "김영업", `email`은 "kim@example.com"이다

### AU-006 AD의 긴 이름은 200자로 자르고 형식이 틀린 이메일은 비운다
- Given AD 대역이 256자 이름과 `@`가 없는 이메일 "kim.example.com"을 준다
- When kim이 로그인한다
- Then 200이고 저장된 이름은 앞 200자, 이메일은 비어 있다(로그인은 막히지 않는다)

### AU-007 AD 로그인에 성공할 때마다 새 솔트의 해시로 덮어쓴다
- Given kim의 저장 해시가 없다
- When kim이 같은 비밀번호로 두 번 로그인한다
- Then 첫 로그인 뒤 해시가 하나 생기고, 두 번째 로그인 뒤 해시 값이 첫 값과 다르며(새 솔트) 둘 다 그 비밀번호로 검증된다. kim의 해시 행은 하나다

### AU-008 로그인한 사용자의 역할과 id는 users 행의 값이다
- Given viewer 행의 역할이 `user`이고 AD 대역은 역할 정보를 주지 않는다
- When viewer가 로그인한다
- Then 응답 `role`은 "user", `user_id`는 viewer 행 id다

### AU-009 퇴사 행과 재직 행이 함께 있으면 재직 행으로 로그인된다
- Given "park" 아이디로 퇴사 행(역할 user)과 그 뒤 다시 등록한 재직 행(역할 sales)이 있다
- When park이 로그인한다
- Then 200이고 `user_id`는 재직 행 id, `role`은 "sales"이며 퇴사 행은 바뀌지 않는다

### AU-010 AD에는 있지만 등록되지 않은 아이디는 401이고 해시를 만들지 않는다
- Given AD 대역은 "nobody"의 비밀번호를 받아들이지만 users에 nobody 행이 없다
- When nobody가 로그인한다
- Then 401 `unauthenticated` "아이디 또는 비밀번호가 올바르지 않습니다"이고 세션 쿠키·세션 행·해시 행이 없다

### AU-011 퇴사한 사용자는 AD 계정이 있어도 401이다
- Given old는 퇴사 처리되었고 AD 대역은 old의 비밀번호를 받아들인다
- When old가 로그인한다
- Then AU-010과 같은 401이고 old 행은 바뀌지 않는다

### AU-012 같은 아이디의 재직 행이 둘이면 401이고 아무것도 바꾸지 않는다
- Given "dup" 아이디의 재직 행이 둘이고 AD 대역은 dup을 받아들인다
- When dup이 로그인한다
- Then 공통 401이고 두 행의 `last_login_at`·이름이 그대로이며 해시가 저장되지 않는다. 경고 로그에는 건수 2와 아이디의 짧은 해시만 있고 "dup" 원문과 비밀번호는 없다. 다른 사용자 kim의 로그인은 계속 된다

### AU-013 AD가 비밀번호를 거절하면 저장 해시가 맞아도 401이고 대체 로그인하지 않는다
- Given kim의 저장 해시가 "old-pw"이고 AD 대역은 "old-pw"를 거절한다(비밀번호가 바뀜)
- When kim이 "old-pw"로 로그인한다
- Then 공통 401이고 세션이 없으며 해시는 바뀌지 않는다

### AU-014 AD 검색에 사용자가 없으면 401이고 실패 1회로 센다
- Given AD 대역이 kim 검색 결과 0건(InvalidCredentials, stage search)을 낸다
- When kim이 로그인한다
- Then 공통 401이고 kim 아이디 카운터의 실패는 1이다

### AU-015 AD 로그인은 매번 DB의 현재 설정·Base DN·복호화한 바인드 비밀번호를 쓴다
- Given AD 설정(호스트 A, Base DN `DC=a,DC=local`, 암호화한 바인드 비밀번호 "bind-1")으로 kim이 한 번 로그인했다
- When 설정을 호스트 B, Base DN `DC=b,DC=local`, 바인드 비밀번호 "bind-2"로 바꾼 뒤 kim이 다시 로그인한다
- Then 두 번째 AD 대역 호출은 호스트 B 설정, Base DN `DC=b,DC=local`, 복호화한 "bind-2"를 받는다(앱 재시작 없음)

### AU-016 형식이 틀린 아이디는 401이고 AD를 부르지 않으며 시도에 세지 않는다
- When 아이디 `""`, `"   "`, `"김영업"`, `"kim*"`, `"a)(uid=*"`, 65자 아이디로 각각 로그인한다
- Then 모두 공통 401이고 AD 대역 호출은 0회이며 실패 카운터가 생기지 않는다

### AU-017 빈 값·공백·NUL 비밀번호는 401이고 AD를 부르지 않는다
- Given kim이 등록되어 있다
- When 비밀번호 `""`, `"   "`, `"pw\u0000x"`로 각각 로그인한다
- Then 모두 공통 401이고 AD 대역 호출은 0회다. local 모드에서도 같다

### AU-018 필드가 빠졌거나 모르는 필드가 있는 로그인 본문은 422다
- When 본문 `{}`, `{"login_id": "kim"}`, `{"password": "x"}`, `{"login_id": "kim", "password": "x", "role": "admin"}`로 각각 로그인한다
- Then 모두 422 `request-validation`이고 세션 쿠키가 없다

### AU-019 너무 긴 아이디·비밀번호는 422이고 입력값을 되돌리지 않으며 상한 길이는 통과한다
- When 129자 아이디, 257자 비밀번호로 각각 로그인한다
- Then 422 `request-validation`이고 응답 본문에 보낸 값과 `input` 항목이 없다. 128자 아이디는 422가 아니라 401(AU-R2), 256자 비밀번호는 422가 아니다(AD 판정)

### AU-020 예약 아이디 셋은 AD에 계정이 있어도 401이고 AD를 부르지 않는다
- Given AD 대역이 어떤 비밀번호든 받아들인다
- When `dev-admin`, `DEV-SALES`, ` dev-user `로 각각 로그인한다(ad 모드와 local 모드 각각)
- Then 모두 공통 401이고 AD 대역·해시 검증 호출은 0회이며 각 아이디의 실패 카운터는 1이다

### AU-021 예약 셋이 아닌 dev- 아이디는 일반 흐름으로 로그인된다
- Given `dev-qa` 재직 행이 등록되어 있다
- When `dev-qa`로 로그인한다(ad 모드는 AD 대역 승인, local 모드는 저장 해시 일치)
- Then 200이다

### AU-022 AD 연결이 안 되어도 해시가 있는 sales는 경고 없이 들어온다
- Given kim의 저장 해시가 "pw-kim"이고 AD 대역이 연결 실패(stage connect)를 낸다
- When kim이 "pw-kim"으로 로그인한다
- Then 200이고 세션 쿠키가 있으며 `directory_warning`은 null이다

### AU-023 admin의 대체 로그인 응답에는 실패 단계와 그 단계의 안내 문구가 있다
- Given root(admin)의 저장 해시가 있고, AD 대역이 단계 connect·tls·service_bind·base_dn·search(2건 이상)·단계 없음 중 하나로 실패하거나 바인드 비밀번호 복호화가 실패한다
- When root가 그 비밀번호로 로그인한다
- Then 200이고 `directory_warning.stage`는 각각 `connect`·`tls`·`service_bind`·`base_dn`·`search`·`unknown`·`credential_unreadable`, `message`는 2.8 표의 그 단계 문구다(여덟 단계 문구는 서로 다르다)

### AU-024 AD 설정이 없어도 해시가 있는 admin은 not_configured 경고와 함께 들어온다
- Given AD 설정 행이 없고 root의 저장 해시가 있다
- When root가 로그인한다
- Then 200, `directory_warning` = `{"stage": "not_configured", "message": "AD 설정이 없어 이전에 로그인한 비밀번호로 로그인했습니다. Admin > 외부연동에서 AD 설정을 등록하세요."}`이고 AD 대역 호출은 0회다

### AU-025 admin이 아닌 사용자의 대체 로그인에는 경고가 없다
- Given AD 설정이 없고 kim(sales)·viewer(user)의 저장 해시가 있다
- When 각자 로그인한다
- Then 둘 다 200이고 `directory_warning`은 null이다

### AU-026 대체 로그인은 해시·프로필을 바꾸지 않고 로그인 시각과 경고 로그만 남긴다
- Given kim의 이름 "김영업", 전화 "02-123-4567", 저장 해시 H, AD 대역 연결 실패, 시계 `2026-11-09T02:00:00Z`
- When kim이 로그인한다
- Then kim 행의 `last_login_at`만 `2026-11-09T02:00:00Z`로 바뀌고 이름·이메일·전화 "02-123-4567"·해시 H는 그대로다. 경고 로그 "AD 대체 로그인 stage=connect login_id_hash=…"가 하나 있고 "kim" 원문·비밀번호·해시 값은 없다

### AU-027 AD가 돌아오면 다음 로그인은 AD를 거치고 해시가 새로 저장된다
- Given kim이 AD 장애 중 대체 로그인했다(해시 H)
- When AD 대역이 정상으로 돌아온 뒤 kim이 로그인한다
- Then 200, `directory_warning` null이고 AD 대역이 불렸으며 kim의 해시는 H와 다른 새 값이다

### AU-028 AD 장애 중 틀린 비밀번호는 503 고정 문구이고 실패 1회로 센다
- Given kim의 저장 해시가 "pw-kim"이고 AD 대역이 연결 실패를 낸다
- When kim이 "wrong"으로 로그인한다
- Then 503 `directory-unavailable` "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"이고 세션 쿠키가 없으며 kim 카운터의 실패는 1이다

### AU-029 AD 장애 중 해시 없는 사용자와 미등록 아이디는 같은 503을 받는다
- Given AD 대역이 연결 실패를 내고 viewer는 저장 해시가 없으며 nobody는 등록되지 않았다
- When viewer와 nobody가 각각 로그인한다
- Then 두 응답의 상태·type·detail이 같은 503이고 둘 다 해시 검증이 한 번씩(더미 계산) 불렸으며 실패 1회씩이다

### AU-030 AD 장애 중 퇴사한 사용자는 저장 해시로도 들어올 수 없다
- Given old는 퇴사했고 AD 대역이 연결 실패를 낸다
- When old가 예전 비밀번호로 로그인한다
- Then 503이고 세션이 없다

### AU-031 AD 설정도 해시도 없으면 409이고 AD를 부르지 않으며 실패 1회다
- Given AD 설정 행이 없고 kim의 저장 해시가 없다
- When kim이 로그인한다
- Then 409 `invalid-state` "AD 서버가 아직 등록되지 않았습니다"이고 AD 대역 호출은 0회, kim 카운터 실패는 1이다

### AU-032 바인드 비밀번호를 풀 수 없고 해시도 없으면 503이다
- Given 저장된 바인드 비밀번호를 현재 키로 복호화할 수 없고 kim의 저장 해시가 없다
- When kim이 로그인한다
- Then 503 `directory-unavailable`(고정 문구)이고 AD 대역 호출은 0회다

### AU-033 AD 장애 원인이 달라도 503 문구는 같고 원인을 드러내지 않는다
- Given AD 대역이 "ldap://10.0.0.5:389 connection refused" 같은 원인 문구로 연결 실패, 또는 TLS 실패를 낸다(해시 없음)
- When kim이 로그인한다
- Then 두 경우 모두 같은 503 `detail`이고 응답 본문에 주소·포트·원인 문구가 없다

### AU-034 대체 로그인에 성공하면 앞서 쌓인 아이디 실패 횟수가 지워진다
- Given AD 장애 중 kim이 틀린 비밀번호로 3번 실패했다
- When kim이 올바른 비밀번호로 대체 로그인한다
- Then 200이고 kim 아이디 카운터가 없다(다음 실패는 1부터)

### AU-035 local 모드 사용자는 자기 비밀번호로 로그인하고 경고·프로필 변경이 없다
- Given 인증 방식이 local이고 kim(이름 "김영업", 전화 "010-1234-5678")의 해시가 "pw-kim-1"이다
- When kim이 "pw-kim-1"로 로그인한다
- Then 200, 세션 쿠키, `directory_warning` null이고 kim 행은 `last_login_at`만 바뀐다

### AU-036 local 모드의 틀린 비밀번호·없는 아이디·해시 없음은 같은 401이다
- Given 인증 방식이 local이고 kim의 해시가 있으며 viewer는 해시가 없다
- When kim이 틀린 비밀번호로, nobody가, viewer가 각각 로그인한다
- Then 세 응답 모두 공통 401(같은 문구)이고 쿠키가 없으며 세 경우 모두 해시 검증이 한 번씩 불렸다(없는 아이디·해시 없음은 더미 계산). 각 아이디 카운터는 1이다

### AU-037 local 모드의 퇴사자는 올바른 비밀번호로도 401이다
- Given 인증 방식이 local이고 old는 퇴사했다
- When old가 예전 비밀번호로 로그인한다
- Then 공통 401이다

### AU-038 local 모드에서 같은 아이디의 재직 행이 둘이면 401이다
- Given 인증 방식이 local이고 "dup" 재직 행이 둘이다
- When dup이 로그인한다
- Then 공통 401이고 두 행 모두 바뀌지 않는다

### AU-039 local 모드 로그인은 성공이든 실패든 AD를 부르지 않는다
- Given 인증 방식이 local이고 AD 설정 행이 남아 있다
- When kim이 올바른 비밀번호로, 틀린 비밀번호로 로그인한다
- Then AD 대역 호출은 0회다

### AU-040 인증 방식 행이 없고 admin이 있는 시스템은 AD 로그인으로 처리한다
- Given `auth_settings` 행이 없고 재직 admin(root)이 있다
- When kim이 로그인한다
- Then AD 대역이 불리고 그 판정대로 결과가 난다

### AU-041 ad 모드에서 AD가 응답하면 local 방식 해시가 맞아도 AD 판정을 따른다
- Given 인증 방식이 ad이고 kim의 저장 해시가 "pw"와 맞으며 AD 대역은 "pw"를 거절한다
- When kim이 "pw"로 로그인한다
- Then 공통 401이다

### AU-042 한 아이디가 5번 실패하면 올바른 비밀번호도 429이고 AD·해시를 부르지 않는다
- Given 기본 제한(아이디 5회)이고 kim이 틀린 비밀번호로 5번 실패했다(ad 모드·local 모드 각각)
- When kim이 올바른 비밀번호로 로그인한다
- Then 429 `too-many-attempts` "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"이고 이 요청에서 AD 대역·해시 검증 호출은 0회다

### AU-043 한도보다 한 번 적게 실패하면 잠기지 않는다
- Given kim이 4번 실패했다
- When kim이 올바른 비밀번호로 로그인한다
- Then 200이다

### AU-044 잠금은 그 아이디에만 걸린다
- Given kim이 5번 실패해 잠겼다(같은 IP)
- When viewer가 같은 IP에서 로그인한다
- Then 200이다

### AU-045 잠금은 잠금 시간이 정확히 지나면 풀린다
- Given 시계 `10:00:00`에 kim의 5번째 실패로 잠겼다(잠금 15분)
- When `10:14:59`와 `10:15:00`에 각각 올바른 비밀번호로 로그인한다
- Then 앞은 429, 뒤는 200이다

### AU-046 실패 창이 지나면 실패 횟수를 처음부터 다시 센다
- Given kim이 `10:00`부터 4번 실패했다(창 15분)
- When `10:15:00`에 한 번 더 실패한다
- Then kim 카운터의 실패는 1이고 잠기지 않는다

### AU-047 로그인 성공은 아이디 카운터를 지우고 IP 한도를 쓰지 않는다
- Given IP 한도 30이고 kim이 같은 IP에서 2번 실패했다
- When kim이 성공하고, 이어서 같은 IP에서 kim이 31번 연달아 로그인에 성공한다
- Then 첫 성공 뒤 kim 아이디 카운터가 없고 31번 모두 200이다(성공은 IP 카운터를 늘리지 않는다)

### AU-048 한 IP에서 서로 다른 아이디로 30번 실패하면 다른 아이디도 429다
- Given 한 IP에서 서로 다른 아이디 30개로 각각 1번씩 실패했다
- When 같은 IP에서 kim이 올바른 비밀번호로 로그인한다
- Then 429이고 다른 IP에서의 kim 로그인은 200이다

### AU-049 없는 아이디도 같은 방식으로 제한된다
- Given nobody(미등록)로 5번 실패했다
- When nobody로 다시 로그인한다
- Then 429다(401이 아니다)

### AU-050 실패 카운터 키는 비밀 기반 해시이고 다른 서버 인스턴스와 공유된다
- Given 같은 저장소를 쓰는 앱 인스턴스 A·B가 있다
- When A에서 kim이 5번 실패한 뒤 B에서 kim이 로그인한다
- Then B에서 429다. 저장된 키는 64자리 16진수이고 "kim"·IP 문자열을 포함하지 않으며, 비밀(`jwt_secret`)이 다르면 키가 다르다

### AU-051 AD 장애 중 대체 실패가 한도에 이르면 올바른 비밀번호도 429다
- Given AD 대역이 연결 실패를 내고 kim이 틀린 비밀번호로 5번 실패했다(각 503)
- When kim이 올바른 비밀번호로 로그인한다
- Then 429이고 해시 검증 호출이 없다

### AU-052 시도 제한 기본값은 5·30·15분·15분이고 1 미만은 거부된다
- When 설정을 기본값으로, 그리고 `APP_LOGIN_MAX_FAILURES_PER_ACCOUNT=0` 등 0 값으로, 1 값으로 읽는다
- Then 기본값은 아이디 5, IP 30, 창 15분, 잠금 15분이고 0 값은 설정 검증 실패, 1은 통과한다

### AU-053 발급한 세션은 만료 전까지 인증되고 만료 시각부터 401이다
- Given 시계 `09:00`에 kim이 로그인했다(TTL 8시간)
- When `16:59:59`와 `17:00:00`에 그 쿠키로 `GET /auth/me`를 부른다
- Then 앞은 200, 뒤는 401 "로그인이 필요합니다"다

### AU-054 저장소에는 토큰 해시만 있고 토큰은 매번 다르다
- When kim이 두 번 로그인한다
- Then 두 쿠키 토큰이 다르고, 세션 행의 `token_hash`는 각 토큰의 SHA-256 16진수이며 토큰 원문은 어느 행에도 없다

### AU-055 쿠키가 없거나 발급한 적 없는 토큰이면 401이다
- When 쿠키 없이, 빈 쿠키로, `neoine_session=never-issued`로 각각 `GET /auth/me`를 부른다
- Then 모두 401 `unauthenticated` "로그인이 필요합니다"다

### AU-056 users 행의 역할·이름이 바뀌면 기존 세션의 다음 요청에 반영된다
- Given kim(sales)이 로그인해 있다
- When kim 행의 역할을 user로, 이름을 "김조회"로 바꾼 뒤 같은 쿠키로 `GET /auth/me`를 부른다
- Then `role`은 "user", `name`은 "김조회"다(다시 로그인하지 않음)

### AU-057 퇴사·삭제된 사용자의 세션은 다음 요청부터 401이고 다시 로그인할 수도 없다
- Given kim과 viewer가 로그인해 있다
- When kim을 퇴사 처리하고 viewer 행을 지운 뒤 각자의 쿠키로 `GET /auth/me`를 부르고, 둘이 다시 로그인한다(AD는 승인)
- Then `/auth/me`는 둘 다 401, 재로그인은 둘 다 공통 401이다

### AU-058 같은 아이디로 다시 등록해도 이전 세션은 401이고 새 사용자는 새로 로그인한다
- Given kim이 로그인해 쿠키 C1을 받은 뒤 퇴사 처리되었고 같은 아이디 "kim"이 새 행으로 다시 등록되었다
- When C1으로 `GET /auth/me`를 부르고, kim이 새로 로그인한다
- Then C1은 401이고, 새 로그인은 200이며 `user_id`는 새 행 id다

### AU-059 내 정보는 세 역할 모두 자기 users 행의 다섯 값을 받는다
- Given root(admin)·kim(sales)·viewer(user)가 각각 로그인했다
- When 각자 `GET /api/v1/auth/me`를 부른다
- Then 200이고 키는 `user_id`·`subject`·`email`·`name`·`role` 다섯뿐이며 값은 각자의 행(역할 admin·sales·user)이다

### AU-060 로그아웃하면 세션이 폐기되고 쿠키가 지워져 이후 요청은 401이다
- Given admin·sales·user 중 하나로 로그인해 쿠키 C를 가졌다
- When `POST /api/v1/auth/logout`(CSRF 헤더, 쿠키 C)
- Then 204이고 응답이 `neoine_session`을 만료시키며(`Max-Age=0` 또는 지난 만료일), 세션 행의 `revoked_at`이 기록되고, 이후 C로 `GET /auth/me`는 401이다

### AU-061 세션이 없거나 모르는·폐기된 토큰으로 로그아웃해도 204이고 무해하다
- When 쿠키 없이, 모르는 토큰으로, 이미 로그아웃한 토큰으로 각각 로그아웃한다
- Then 모두 204이고 세션 행은 바뀌지 않는다(이미 폐기된 세션의 `revoked_at`은 처음 값 그대로)

### AU-062 인증 설정 조회는 로그인 없이 200이고 키는 정확히 다섯이다
- When 로그인하지 않고 `GET /api/v1/auth/config`를 부른다
- Then 200이고 키는 `directory_login`·`needs_directory_setup`·`needs_storage_setup`·`needs_admin_setup`·`auth_mode` 다섯뿐이다(`dev_login`·OIDC 키 없음)

### AU-063 인증 설정의 단계 값과 auth_mode는 설정 상태에 따라 정해진다
- Given 다음 상태 각각이다: (a) 아무것도 없음 (b) 방식 local만 고름 (c) 방식 ad만 고름 (d) ad + AD 설정 (e) ad + AD 설정 + 저장 위치 (f) local + 저장 위치 (g) 방식 행 없이 재직 admin과 AD 설정·저장 위치 있음
- When `GET /auth/config`를 부른다
- Then `(directory_login, needs_directory_setup, needs_storage_setup, needs_admin_setup, auth_mode)`는 (a) (false, true, true, false, null) (b) (false, false, true, false, "local") (c) (false, true, true, false, "ad") (d) (true, false, true, false, "ad") (e) (true, false, false, true, "ad") (f) (false, false, false, true, "local") (g) (true, false, false, false, "ad")다

### AU-064 폐지된 개발용 로그인·OIDC 경로는 없다
- When `POST /api/v1/auth/dev-login`(본문 `{"role": "admin"|"sales"|"user"}`), `GET /api/v1/auth/login?code=c`, `GET /api/v1/auth/callback?code=c`를 부르고 openapi를 만든다
- Then dev-login은 404이고 세션 쿠키가 없다. `GET /auth/login`은 404 또는 405, `GET /auth/callback`은 404이고 둘 다 `Location` 헤더가 없다. openapi에 `/api/v1/auth/dev-login` 경로와 `DevLoginRequest` 스키마가 없다

### AU-065 로그인 성공·실패·장애 어디에도 비밀번호 원문이 응답·로그·테이블에 없다
- Given 고유한 비밀번호 문자열 P(예: `"S3cr3t-P@ss"`)를 쓴다
- When P로 성공 로그인, 틀린 로그인, 422(너무 긴 아이디와 함께), AD 장애 중 대체 성공·실패 로그인을 한다
- Then 응답은 차례로 200·401·422·200·503이고, 모든 응답 본문·헤더, 수집한 로그(DEBUG 포함), 예외 문구, users·auth_sessions·login_failures·user_password_hashes의 모든 값에 P가 없다(해시 행에는 `scrypt$`로 시작하는 값만 있다)

### AU-066 openapi는 로그인 오류 응답과 비밀번호 칸 표기를 문서화한다
- When 앱의 openapi를 만든다
- Then `POST /api/v1/auth/login`은 200·401·409·422·429·503 응답이 있고 오류는 `Problem` 스키마이며, `LoginRequest.password`는 `format: password`·`writeOnly: true`·`maxLength: 256`, `login_id`는 `maxLength: 128`이다. `GET /api/v1/auth/me`는 401이 있다

### AU-067 화면: 로그인 화면은 아이디·비밀번호 폼과 로그인 버튼만 보인다
- Given 로그인하지 않았고 최초 설정이 끝났다
- When `/login`을 연다
- Then "아이디"(autocomplete `username`)·"비밀번호"(autocomplete `current-password`) 칸과 버튼 "로그인" 하나만 있고, "빠른 로그인" 영역·역할 버튼·시드 사용자 이름·"아무 비밀번호" 안내·최초 설정 링크가 없다

### AU-068 화면: 인증 설정을 읽는 동안 불러오는 중을 보인다
- Given 인증 설정 응답이 아직 오지 않았다
- When `/login`을 연다
- Then "불러오는 중…"만 보이고 "아이디" 칸은 없으며, 응답이 오면 폼이 보인다

### AU-069 화면: 인증 설정을 읽지 못해도 폼과 오류 문구가 보인다
- Given 인증 설정 조회가 문구 M의 `ApiError`로 실패한다
- When `/login`을 연다
- Then `role="alert"`에 M이 보이고 "로그인" 버튼과 두 칸이 보인다

### AU-070 화면: 이미 로그인했으면 로그인 화면에서 Deals 목록으로 간다
- Given kim(sales)이 로그인해 있다
- When `/login`을 연다
- Then Deals 목록 주소로 바뀐다

### AU-071 화면: 로그인에 성공하면 Deals 목록으로 가고 내 정보가 갱신된다
- Given 로그인하지 않았다
- When `/login`에서 kim의 아이디·비밀번호를 넣고 "로그인"을 누른다
- Then Deals 목록 주소로 바뀌고 사용자 메뉴를 열면 "김영업 (sales)"이 보인다

### AU-072 화면: 로그인에 실패하면 서버 문구를 보이고 비밀번호만 비운다
- Given 서버가 401 "아이디 또는 비밀번호가 올바르지 않습니다"로 답한다
- When "nobody"·"secret"으로 로그인한다
- Then `role="alert"`에 "아이디 또는 비밀번호가 올바르지 않습니다"가 보이고 비밀번호 칸은 비며 아이디 칸은 "nobody", 주소는 `/login`이다

### AU-073 화면: 빈 칸으로 제출해도 서버 판정 문구를 보인다
- Given 서버(Fake)가 빈 아이디·빈 비밀번호를 공통 401로 답한다
- When 두 칸을 비운 채, 그리고 아이디만 넣고 "로그인"을 누른다
- Then 로그인 요청이 가고 배너에 "아이디 또는 비밀번호가 올바르지 않습니다"가 보이며 주소는 `/login`이다

### AU-074 화면: 퇴사자 로그인도 같은 실패 문구다
- Given old는 퇴사했다
- When old의 아이디·비밀번호로 로그인한다
- Then 배너 문구는 AU-072와 같고 주소는 `/login`이다

### AU-075 화면: 아이디 앞뒤 공백을 지워 보낸다
- When 아이디 칸에 `"  kim  "`, 비밀번호 `" pw "`를 넣고 로그인한다
- Then 게이트웨이 로그인 호출 인자는 `("kim", " pw ")`다

### AU-076 화면: 요청 중에는 로그인 버튼이 비활성이다
- Given 로그인 응답이 아직 오지 않는다
- When "로그인"을 누른다
- Then 응답이 올 때까지 "로그인" 버튼이 비활성이다

### AU-077 화면: 입력한 비밀번호는 요청 캐시에 남지 않는다
- When "pw-secret-1"로 실패한 뒤 "pw-secret-2"로 성공한다
- Then 쿼리 클라이언트의 mutation 캐시 어느 변수에도 "pw-secret-1"·"pw-secret-2"가 없다

### AU-078 화면: 대체 로그인한 admin에게 로그인 직후 AD 연결 경고를 보인다
- Given 로그인 응답이 `directory_warning` `{stage: "connect", message: "AD 서버에 연결하지 못해 …"}`를 싣는다(root)
- When `/login`에서 로그인한다
- Then 첫 화면(Deals 목록)에 대화상자 "AD 연결 경고"가 열리고 본문이 서버 `message`와 같다. `credential_unreadable` 등 다른 단계면 그 단계의 서버 문구다

### AU-079 화면: 경고에서 외부연동 설정으로 이동하면 다시 보이지 않는다
- Given AU-078의 대화상자가 열려 있다
- When "외부연동 설정으로 이동"을 누른다
- Then 주소가 `/admin/integrations`이고 대화상자가 없으며, 다른 화면으로 옮겼다 돌아와도 다시 열리지 않는다

### AU-080 화면: 경고를 닫으면 화면을 옮겨도 다시 보이지 않는다
- Given AU-078의 대화상자가 열려 있다
- When "닫기"를 누르고 Dashboard·Deals로 이동한다
- Then 대화상자는 다시 열리지 않는다

### AU-081 화면: 경고 없는 로그인이나 로그인 없이 연 세션에는 경고가 없다
- When 경고 없는 응답으로 로그인하거나, 이미 로그인한 세션으로 `/deals`를 바로 연다
- Then "AD 연결 경고" 대화상자가 없다

### AU-082 화면: 로그아웃하면 경고가 지워지고 다음 로그인의 경고만 보인다
- Given 경고와 함께 로그인해 경고를 닫았다
- When 로그아웃한 뒤 (a) 경고를 싣는 응답으로 다시 로그인하거나 (b) 경고 없는 응답으로 다시 로그인한다
- Then (a)는 대화상자가 다시 열리고 (b)는 열리지 않는다

### AU-083 화면: 경고는 브라우저 저장소에 남지 않는다
- Given 경고와 함께 로그인해 대화상자가 열렸다
- When localStorage·sessionStorage 내용을 읽는다
- Then 경고 문구·단계가 어디에도 없다

### AU-084 로그아웃 훅은 캐시를 모두 비우고 이후 내 정보는 401이다
- Given kim이 로그인해 내 정보·다른 조회가 캐시에 있다
- When `useLogout`을 실행한다
- Then 성공하고 쿼리 캐시가 비며, 이어 `useMe`는 401 `ApiError`다

### AU-085 게이트웨이: 내 정보와 로그인 응답을 화면 사용자로 바꾸고 경고를 옮긴다
- Given 서버가 `GET /auth/me`에 `{user_id: 7, subject: "kim", email: "kim@x.com", name: "김영업", role: "sales"}`, `POST /auth/login`에 같은 사용자 + `directory_warning`(null, 객체, 또는 키 없음)을 준다
- When HTTP 게이트웨이의 `me()`와 `login("kim", "pw")`를 부른다
- Then `me()`는 `{id: 7, loginId: "kim", name: "김영업", role: "sales"}`, `login()`은 같은 `me`와 `directoryWarning`(객체면 `{stage, message}`, null·키 없음이면 null)이며 요청 본문은 `{login_id: "kim", password: "pw"}`다

### AU-086 게이트웨이: 로그인 실패 401은 unauthorized와 서버 문구다
- Given 서버가 401 `unauthenticated` "아이디 또는 비밀번호가 올바르지 않습니다"로 답한다
- When `login()`을 부른다
- Then `ApiError` 상태 401, kind `unauthorized`, 문구는 서버 `detail` 그대로로 reject된다

### AU-087 게이트웨이: 로그아웃은 204를 성공으로 보고 인증 설정은 설정 필요 여부와 방식으로 바뀐다
- Given 서버가 로그아웃에 204, 인증 설정에 단계 값 조합과 `auth_mode`("ad", "local", null, 또는 키 없음)를 준다
- When `logout()`과 `config()`를 부른다
- Then `logout()`은 `POST /api/v1/auth/logout`을 부르고 성공하며, `config()`는 `needsSetup` = 세 단계 값 중 하나라도 true, `authMode` = 값(없으면 null)이고 그 밖의 키를 내지 않는다

### AU-088 로그인 전 내 정보 훅은 401이고 로그인 훅 성공 뒤 내 정보·권한이 갱신된다
- Given 로그인하지 않았다
- When `useMe`·`usePermissions`를 읽고, `useLogin`으로 kim이 로그인한 뒤 다시 읽는다
- Then 처음은 `useMe` 401 `ApiError`, 권한 role null·모두 false이고, 로그인 뒤 `useMe`는 kim, `canWrite` true·`isAdmin` false다. 실패한 `useLogin`은 `ApiError`로 reject한다

### AU-089 AD 로그인에 성공하면 앱에서 입력해 둔 전화번호를 AD의 mobile 값으로 형식과 무관하게 덮어쓴다
- Given 인증 방식 `ad`이고 kim 행의 전화가 "02-111-2222"(앱에서 입력)이다. AD 대역은 경우마다 (a) mobile " 010-1234-5678 "·telephoneNumber "02-123-4567", (b) mobile "010.1234.5678 내선 12"(앱 형식 규칙 밖)·telephoneNumber "02-123-4567"을 준다
- When 경우마다 kim이 맞는 비밀번호로 로그인한다
- Then 모두 200이고 kim 행의 전화는 (a) "010-1234-5678"(앞뒤 공백 제거), (b) "010.1234.5678 내선 12"다. 이름·이메일도 AD 값으로 바뀐다

### AU-090 AD의 mobile이 없거나 비었으면 telephoneNumber로 덮어쓴다
- Given kim 행의 전화가 "02-111-2222"이고, AD 대역이 경우마다 (a) mobile 없음·telephoneNumber "02-123-4567", (b) mobile "   "(공백만)·telephoneNumber "+82 2-123-4567"을 준다
- When 경우마다 kim이 로그인한다
- Then 모두 200이고 저장된 전화는 (a) "02-123-4567", (b) "+82 2-123-4567"이다

### AU-091 AD에 전화번호가 없으면 저장된 전화번호를 그대로 둔다
- Given kim 행의 전화가 "02-111-2222"(admin이 등록 때 넣은 값)이고, AD 대역이 경우마다 (a) 두 속성을 주지 않는다(서비스 계정이 읽지 못한 경우와 같음), (b) mobile ""·telephoneNumber "  "를 준다. 이름 "김영업"·이메일은 AD가 준다
- When 경우마다 kim이 로그인한다
- Then 모두 200이고 세션이 발급되며 kim 행의 전화는 "02-111-2222" 그대로이고, 이름·이메일은 AD 값으로 바뀐다. 전화가 비어 있던 사용자 lee는 같은 조건에서 계속 비어 있다(null)

### AU-092 AD 전화번호는 NUL·앞뒤 공백을 지우고 40자를 넘으면 40자로 자른다
- Given AD 대역이 mobile 없이 telephoneNumber로 경우마다 NUL이 섞인 "010-1234\u0000-5678", 정확히 40자인 값, 앞 40자의 끝이 공백인 45자 값을 준다
- When 경우마다 kim이 로그인한다
- Then 모두 200이고 저장된 전화는 NUL을 뺀 "010-1234-5678", 40자 값 그대로, 45자 값의 앞 40자에서 끝 공백을 지운 값이다

### AU-093 도메인이 설정되어 있으면 사용자 비밀번호 바인드는 아이디@도메인으로 하고 검색·프로필은 그대로다
- Given LDAP 어댑터가 도메인 `neoine.co.kr`로 만들어졌고, 모의 AD에 `cn=kim,ou=users,dc=corp,dc=test` 항목(sAMAccountName kim, 이름 "김영업", 메일 "kim@corp.test")이 있으며, `kim@neoine.co.kr` 바인드가 비밀번호 "Correct-Horse-1"을 받아들인다
- When kim이 그 비밀번호로 인증한다
- Then 결과는 아이디 "kim"·이름 "김영업"·메일 "kim@corp.test"인 사용자다. 연결은 두 번 만들어지는데 첫째는 서비스 계정(`bind_account`·바인드 비밀번호), 둘째는 `kim@neoine.co.kr`과 사용자 비밀번호이고, 검색은 서비스 계정 연결에서 저장된 Base DN·필터 값 kim으로 1번이다. 찾은 항목의 DN으로 바인드하지 않고 두 연결 모두 닫힌다

### AU-094 도메인 환경변수가 없거나 비어 있으면 찾은 항목의 DN으로 바인드한다
- Given 경우마다 `APP_AD_LOGIN_DOMAIN`이 (a) 없다, (b) 빈 문자열이다, (c) "   "(공백만)이다
- When 설정을 읽고, 도메인 없이 만든 어댑터로 kim이 인증한다
- Then 세 경우 모두 설정의 `ad_login_domain`은 없음(None)이고, 사용자 바인드 이름은 `cn=kim,ou=users,dc=corp,dc=test`이며 인증이 성공한다

### AU-095 도메인이 있어도 검색 0건은 사용자 바인드 없이 자격 증명 오류, 2건 이상은 search 단계 오류다
- Given 도메인 `neoine.co.kr`인 어댑터. (a) 아이디 nobody는 필터에 맞는 항목이 없다, (b) 필터가 `(|(cn={login_id})(objectClass=user))`라 항목이 2건 이상 걸린다
- When 각각 인증한다
- Then (a) `InvalidCredentialsError`(stage `search`)이고 (b) `DirectoryMisconfiguredError`(stage `search`)이며, 두 경우 모두 서비스 계정 연결 하나만 만들어지고 사용자 바인드(`…@neoine.co.kr`)는 없다. 로그인 결과는 (a) 공통 실패 401(AU-R9), (b) 대체 로그인 대상(AU-R10 `search`)이다

### AU-096 도메인 바인드를 AD가 거절하면 자격 증명 오류, 그 밖의 결과 코드는 AD 불가다
- Given 도메인 `neoine.co.kr`인 어댑터와 kim 항목. `kim@neoine.co.kr` 바인드 결과 코드가 경우마다 49, 50, 53, 51, 52이고 서비스 계정 바인드는 성공한다
- When kim이 인증한다
- Then 49·50·53은 `InvalidCredentialsError`(stage `bind`), 51·52는 `DirectoryUnavailableError`(stage `bind`)다. 어느 경우든 예외 문구에 바인드 이름·비밀번호가 없다

### AU-097 바인드 이름은 정규화한 아이디와 공백 제거·소문자로 정리한 도메인으로 만든다
- Given `APP_AD_LOGIN_DOMAIN` = "  NEOINE.Co.KR "
- When 설정을 읽고, 그 값(`neoine.co.kr`)으로 만든 어댑터에 아이디 " KIM "으로 인증한다
- Then 설정의 `ad_login_domain`은 "neoine.co.kr"이고 사용자 바인드 이름은 "kim@neoine.co.kr"이다

### AU-098 도메인 형식이 틀리면 기동이 실패하고 오류에 값이 나오지 않는다
- Given 프로파일 local·dev·product 각각에서 `APP_AD_LOGIN_DOMAIN`이 경우마다 "@neoine.co.kr", "kim@neoine.co.kr", "neoine .co.kr", "neoine..co.kr", "neoine.co.kr.", "-neoine.co.kr", "neoine-.co.kr", "네오인.kr", 제어문자가 든 "neo\u0001ine.kr", 64자 라벨이 든 값, 전체 254자 값이다
- When 설정을 읽는다
- Then 모두 검증 오류이고 문구에 "ad_login_domain은 도메인 형식(예: neoine.co.kr)이어야 합니다"가 있으며 오류 문자열에 입력값이 없다. 같은 조건에서 "neoine.co.kr", "corp", "a-b.example.com", 63자 라벨이 든 값, 전체 253자 값은 통과하고 정리한 값이 그대로 남는다

### AU-099 조립된 앱의 LDAP 어댑터는 설정의 도메인을 쓰고 로그인·AD 설정 확인·첫 admin 등록이 같은 어댑터를 쓴다
- Given `ad_login_domain`이 "neoine.co.kr"인 설정과 없는 설정
- When 디렉터리를 주입하지 않고 `Container`를 각각 만든다
- Then `container.directory`는 `LdapDirectoryAuthenticator`이고 사용자 바인드 도메인이 각각 "neoine.co.kr"·없음이다. 로그인·AD 설정 확인·첫 admin 등록 유스케이스가 받는 디렉터리 Port가 이 같은 객체다

### AU-100 도메인이 있어도 DN·도메인 주입을 노린 아이디로는 사용자 바인드를 하지 않는다
- Given 도메인 `neoine.co.kr`인 어댑터. `LoginId` 검증을 건너뛴 아이디가 경우마다 "x,ou=admins+cn=y", "kim@evil.test"다
- When 그 아이디로 인증한다
- Then 모두 `InvalidCredentialsError`이고 만들어진 연결은 서비스 계정 하나뿐이며 사용자 바인드는 없다(검색 필터에서 이스케이프된 값이 어느 항목에도 맞지 않음). 정상 경로에서는 AU-R2 형식 검사가 이런 아이디를 AD에 보내기 전에 막는다(AU-016)

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(초안): 구현된 로그인·세션·대체 로그인 동작을 정본 명세로 옮김. 규칙 AU-R1~R30, use case AU-UC1~UC8, BDD 케이스 AU-001~AU-088 | AU-001~AU-088(신규) |
| 2026-11-24 | 확정(2026-11-24 사용자 확인): AD 로그인 때 AD 전화번호가 있으면 덮어씀(사용자 요청·결정 2026-11-24: `mobile`이 비지 않으면 형식과 무관하게 `mobile`, 아니면 `telephoneNumber`. 앱 형식 규칙으로 거르지 않음, NUL·앞뒤 공백 제거·40자 초과 자름. AD에 값이 없으면 기존 값 유지. 앱에서의 전화 수정은 그대로 허용). AU-R8 변경, AU-R8a 신설, AU-R10 문구(대체 로그인은 전화도 그대로), 2.2. 마이그레이션·API 변경 없음. AD 값이 있는 사용자는 앱에서 고친 전화번호가 다음 AD 로그인 때 AD 값으로 바뀜(사용자 수용) | 신규 AU-089~AU-092. 변경 AU-026(전화 그대로 단언 추가) |
| 2026-11-24 | 확정(2026-11-24 사용자 확인): AD 사용자 비밀번호 바인드를 `<아이디>@<도메인>`으로(사용자 요청 2026-11-24, 결정: 서비스 계정 검색·프로필 읽기·사용자 필터·정확히 1건 확인은 그대로, 사용자 비밀번호 바인드 이름만 바꿈, 도메인 환경변수가 없거나 비면 기존 DN 바인드). 새 환경변수 `APP_AD_LOGIN_DOMAIN`(선택). AU-R7 변경, AU-R7a 신설, 1장 범위·2.1 용어·2.2 설정·AU-UC1 갱신. API·DB·마이그레이션 변경 없음. 도메인 값이 실제 AD와 맞지 않으면 모든 AD 로그인이 401(대체 로그인 없음) | 신규 AU-093~AU-100. 기존 케이스 변경 없음(도메인 없음이 기본값이라 AU-001~AU-092 그대로) |
