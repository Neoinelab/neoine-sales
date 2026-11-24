# 최초 설정   (feature 코드: SU, 상태: 확정(2026-11-24 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/web/routers/auth_setup.py`, `web/schemas/{auth,auth_directory,storage,password_field}.py`, `web/error_handlers.py`, `application/auth/{auth_status,mode,messages,setup_auth_mode,setup_directory,setup_storage,setup_admin,setup_first_admin,setup_first_local_admin,credential_check}.py`, `application/directory/errors.py`, `application/storage/probe.py`, `domain/auth/{mode,credentials,password_policy}.py`, `domain/storage/path.py`, `domain/user/{profile,retired_login_ids}.py`, `frontend/src/features/setup/**`, `features/auth/LoginPage.tsx`, `data/setup.ts`, `gateway/http/setup.ts`, `shared/directory/{messages,directoryForm}.ts`)이며 문구·type·상태 코드는 서버 코드에서 그대로 옮겼습니다. 테스트용 Fake 게이트웨이(`frontend/src/test/fake/gateway/auth.ts`)가 서버와 다르게 동작하는 곳은 서버를 따랐습니다(계획 `artifacts/10-analysis/su-plan.md` 확인 필요 질문 Q1~Q3).

## 1. 개요

- 목적: 처음 설치한 시스템에 관리자가 아무도 없을 때, 로그인 없이 ① 인증 방식(AD 연동이면 AD 서버 등록까지) → ② 파일 저장 위치 → ③ 첫 관리자(admin) 등록을 차례로 마치게 한다. 첫 admin이 생기면 최초 설정은 닫히고 그 사람은 바로 로그인된다.
- 사용자(역할): 미인증 방문자(설치 담당자). 재직 admin이 한 명이라도 있으면 아무도 쓸 수 없다.
- 범위
  - `PUT /auth/setup/auth-mode`, `PUT /auth/setup/directory`, `POST /auth/setup/directory/test`, `PUT /auth/setup/storage`, `POST /auth/setup/storage/test`, `POST /auth/setup`
  - `GET /auth/config` 응답 중 최초 설정 진행 상태(`needs_directory_setup`·`needs_storage_setup`·`needs_admin_setup`·`auth_mode`)의 의미와 유효 인증 방식 판정
  - 화면: `/setup`(단계 표시, 인증 방식 선택, AD 서버 연결 테스트·등록 폼, 저장 위치·쓰기 테스트, 관리자 등록), 로그인 화면이 최초 설정이 필요할 때 `/setup`으로 보내는 동작
- 범위 밖(다른 feature)
  - `/auth/config` 경로 자체와 `directory_login`, 세션 쿠키 속성, 로그인 시도 제한의 횟수·잠금 시간·문구(429), 로그인·대체 로그인 → AU
  - AD 접속 정보 7칸의 값 규칙(IN-R1~IN-R8), Base DN 자동 탐색(IN-R11 ①·IN-R12), 바인드 비밀번호 암호화(IN-R15), AD 설정 응답 모양(IN-R16), 저장 경로 값 규칙(IN-R23), 쓰기 확인(IN-R24), AD 입력 칸 공용 컴포넌트(IN-R31) → IN. 설정 뒤 AD·저장 위치 변경(`/settings/directory*`·`/settings/storage*`) → IN
  - 첨부 파일 저장·다운로드 → AT·LC
  - 이메일·전화번호 형식 값 규칙 → US(사용자 관리). 이 문서는 문구만 적는다
  - CSRF 헤더(`/auth/setup/**` 포함) → PL-R9, problem+json 형식 → PL, 공개 경로 목록 → PL 2.1
  - 경쟁·동시성(동시에 두 사람이 첫 admin 등록) 테스트
- 관련 화면·메뉴: 메뉴 없음. `/setup`(공개 화면, PL-R32), `/login`

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 재직 admin | `role = admin`이고 퇴사 처리(`deleted_at`)되지 않은 사용자. 퇴사한 admin과 `sales`·`user`는 세지 않는다 |
| 설정 닫힘 | 재직 admin이 1명 이상인 상태. 모든 최초 설정 경로가 거절된다 |
| 인증 방식 | `ad`(회사 AD 계정으로 로그인) 또는 `local`(앱이 계정·비밀번호를 직접 관리). 시스템 전역에 하나(`auth_settings` 단일 행) |
| 유효 인증 방식 | 저장된 방식, 없으면 SU-R3으로 정한 값(`ad` 또는 미선택 `null`) |
| AD 단계 완료 | 유효 방식이 `local`이거나, `ad`이고 AD 설정 행(`directory_settings`)이 있음 |
| 진행 상태 | `/auth/config`의 `needs_directory_setup`·`needs_storage_setup`·`needs_admin_setup`·`auth_mode` |
| 쓰기 확인 | IN-R24(경로가 없으면 상위까지 만들고 흔적 없이 쓰기를 시험) |
| 시도 제한 | 로그인과 같은 계정·IP별 실패 횟수 제한(`LoginThrottle`, 규칙 정본은 AU). 최초 설정에서는 AD 방식 admin 등록에만 쓴다 |

### 2.2 데이터 모델

새 테이블 없음. 최초 설정이 쓰는 기존 테이블(컬럼·제약의 정본은 각 소유 feature와 SC 기준선):

| 테이블 | 최초 설정이 쓰는 내용 |
| --- | --- |
| `auth_settings`(단일 행) | `mode`(`ad`·`local`), `updated_at`. 방식 선택·AD 설정 등록 때 덮어쓴다 |
| `directory_settings`(단일 행, IN) | 접속 정보, 암호화한 바인드 비밀번호, 찾은 `base_dn`, `revision`(1부터 저장마다 +1), `updated_at`, `updated_by = NULL`(최초 설정이 저장) |
| `storage_settings`(단일 행, IN) | 정규화한 `path`, `updated_at`, `updated_by = NULL` |
| `users` | 첫 admin 1행: `role = admin`, 마지막 로그인 시각 기록. AD는 이름·이메일을 AD 값으로, 전화는 AD 값이 있을 때만 AD 값으로(AU-R8a), local은 입력값(전화 포함)으로 |
| `user_password_hashes` | 첫 admin 비밀번호의 scrypt 해시(AD·local 모두, 원문은 어디에도 저장하지 않음) |
| `auth_sessions` | 첫 admin의 새 세션(AU) |

요청·응답 모델(web): `AuthModeRequest{mode}`, `DirectorySettingsRequest`(접속 정보 6칸 + `bind_password`), `StorageSettingsRequest{path}`, `SetupAdminRequest{login_id, password, display_name?, email?, phone?}`, 응답 `DirectorySettingsResponse`(IN-R16), AD 연결 테스트 결과 `DirectoryTestResultResponse{success, stage, message, base_dn}`(IN-R18과 같은 스키마), `StorageSettingsResponse{path, updated_at, updated_by}`(IN-R22), `PrincipalResponse{user_id, subject, email, name, role}`. 모든 요청 모델은 모르는 필드를 거부한다(422 `request-validation`).

### 2.3 비즈니스 규칙

공통
- **SU-R1** 최초 설정은 ① 인증 방식(AD 연동이면 AD 서버 등록) → ② 파일 저장 위치 → ③ 첫 admin 등록 순서다. 모든 `/auth/setup/**` 경로는 로그인 없이 부를 수 있고(세션을 읽지도 요구하지도 않음), 상태 변경 요청이라 CSRF 헤더가 필요하다(PL-R9). 첫 admin 등록이 성공하기 전까지 앞 단계는 몇 번이든 다시 저장해 덮어쓸 수 있다.
- **SU-R2** 설정 닫힘: 재직 admin이 1명 이상이면 여섯 경로 모두 409 `invalid-state`, `detail` = "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"다. 거절되면 AD를 부르지 않고 디스크·DB에 아무것도 쓰지 않는다. AD·저장 위치 설정 행이 지워져 있어도 재직 admin이 있으면 닫혀 있다. 퇴사한 admin만 있거나 admin이 아닌 사용자만 있으면 열려 있다. 판정 위치:
  - 방식 선택·저장 위치 등록·쓰기 테스트: 요청 형식(422 `request-validation`) 다음 가장 먼저(선행 단계·경로 형식·쓰기 확인보다 먼저)
  - AD 서버 등록·AD 연결 테스트: 요청 형식과 칸 값 검사(SU-R6·SU-R20) 다음, AD 확인보다 먼저
  - 첫 admin 등록: 입력 검사(빈 비밀번호, AD 방식 프로필 필드, 아이디 형식, 예약 아이디, local 비밀번호 정책·프로필)와 AD 방식의 시도 제한 확인(429) 다음, 선행 단계 확인·AD 인증보다 먼저(SU-R12·R13)
- **SU-R3** 유효 인증 방식: `auth_settings`에 값이 있으면 그 값이다. 없으면 재직 admin이 있거나 AD 설정 행이 있는 기존 시스템은 `ad`, 둘 다 없으면 미선택(`null`)이다. 저장된 `local`은 남아 있는 AD 설정 행보다 우선한다.

진행 상태
- **SU-R4** `GET /auth/config`(로그인 없이, AU 소유 경로)의 진행 상태는 다음과 같다(admin = 재직 admin 있음).
  - `auth_mode` = 유효 인증 방식(`"ad"`·`"local"`·`null`)
  - `needs_directory_setup` = admin 없음 그리고 AD 단계 미완료
  - `needs_storage_setup` = admin 없음 그리고 저장 위치 행 없음
  - `needs_admin_setup` = admin 없음 그리고 저장 위치 행 있음 그리고 AD 단계 완료
  - 따라서 admin이 있으면 셋 다 `false`, admin이 없으면 셋 중 하나 이상이 `true`다. 새 시스템은 `auth_mode: null, needs_directory_setup: true, needs_storage_setup: true, needs_admin_setup: false`다.

① 인증 방식
- **SU-R5** `PUT /auth/setup/auth-mode` `{mode}`: 설정이 열려 있으면 방식을 저장(덮어쓰기)하고 204(본문 없음)다. `mode`는 `"ad"`·`"local"`만 받고 그 밖(대문자, 다른 값, 누락, 추가 필드)은 422 `request-validation`이며 방식은 바뀌지 않는다. `local`을 골라도 저장된 AD 설정 행은 지우지 않는다(쓰이지 않을 뿐). `ad`를 고르면 AD 설정 행이 있을 때만 AD 단계가 완료다. 닫혀 있으면 SU-R2.
- **SU-R6** `PUT /auth/setup/directory`(AD 서버 등록): 판정 순서는 요청 형식·칸 값 → 닫힘(SU-R2) → AD 확인 → (닫힘 재확인) → 저장이다.
  - 본문은 IN-R1의 7칸이고 값 규칙·문구·`request-validation` 구분은 IN-R2~IN-R8을 따른다(위반이면 AD를 부르지 않음). 최초 설정에는 '저장된 값 유지'가 없어 `bind_password`가 없거나 `null`이면 422 `request-validation`이다. 현재 admin 비밀번호(`password`)·`expected_revision`은 받지 않는다(보내면 422 `request-validation`).
  - 확인은 IN-R11 ①(연결·TLS → 서비스 계정 바인드 → Base DN 탐색)까지만 하고 사용자 인증(IN-R11 ②)과 시도 제한은 하지 않는다. 저장되는 Base DN은 AD가 알려 준 값이다(IN-R12).
  - 확인이 실패하면 422 `directory-verification-failed`, 본문에 `stage`(`connect`·`tls`·`service_bind`·`base_dn`, 단계 정보가 없으면 `connect`)와 단계별 서버 문구(2.8)를 담는다. AD가 준 원인 문구와 비밀번호는 응답에 없다. 아무것도 저장하지 않고 인증 방식도 기록하지 않으며 이전에 저장한 AD 설정은 그대로다.
  - 성공하면 AD 설정을 저장(처음이면 `revision` 1, 덮어쓰면 +1, `updated_by` NULL, 바인드 비밀번호는 IN-R15로 암호화)하고, 같은 트랜잭션에서 인증 방식을 `ad`로 기록한다(앞서 `local`을 골랐어도 `ad`로 바뀐다). 응답 200 `DirectorySettingsResponse`(IN-R16, `bind_credential_status: "ok"`, `updated_by: null`).
- **SU-R20** `POST /auth/setup/directory/test`(AD 연결 테스트): AD 서버를 등록하기 전에 입력값으로 연결만 확인한다. 판정 순서는 요청 형식·칸 값 → 닫힘(SU-R2) → AD 확인이다.
  - 본문은 SU-R6과 같은 `DirectorySettingsRequest`(IN-R1의 7칸)이고 값 규칙·문구·`request-validation` 구분은 IN-R2~IN-R8을 따른다(위반이면 AD를 부르지 않음). `bind_password`가 없거나 `null`이면 422 `request-validation`, 현재 admin 비밀번호(`password`)·`expected_revision`을 보내면 422 `request-validation`이다.
  - 확인은 SU-R6과 같이 IN-R11 ①(연결·TLS → 서비스 계정 바인드 → Base DN 탐색)까지만 하고 사용자 인증(IN-R11 ②)과 시도 제한은 하지 않는다.
  - 아무것도 저장하지 않는다: AD 설정 행(접속 정보·암호문·Base DN·revision), 인증 방식(`auth_settings`), 진행 상태가 그대로다. 인증 방식이 미선택이거나 `local`이어도, AD 설정이 이미 저장되어 있어도 테스트할 수 있고 저장된 값을 쓰거나 바꾸지 않는다(입력한 7칸만 쓴다).
  - 확인이 성공하면 200 `{"success": true, "stage": null, "message": "AD 설정을 확인했습니다", "base_dn": <찾은 값>}`, 확인이 실패하면 오류가 아니라 200 `{"success": false, "stage": <단계, 단계 정보가 없으면 "connect">, "message": <2.8 단계별 서버 문구>, "base_dn": null}`이다(IN-R18과 같은 응답 모양). AD가 준 원인 문구와 비밀번호는 응답에 없다. 형식·값 위반(422)과 닫힘(409)은 결과가 아니라 오류 응답이다.
  - 호출 횟수·빈도 제한은 두지 않는다(SU-R6과 같음). 그래서 이 경로는 저장 없이 반복 탐색에 쓸 수 있고 응답에 찾은 Base DN이 들어간다. 설정이 열려 있는 동안만 가능하며 SU-R6의 수용 위험(임의 호스트로 LDAP 연결 시도)과 같은 범위로 받아들인다(2026-11-23 사용자 결정).
  - 서버는 테스트 결과를 기억하지 않는다. AD 서버 등록(SU-R6)은 테스트 여부와 무관하게 같은 확인을 다시 하고 저장한다. "테스트 성공 뒤에만 등록"은 화면 규칙(SU-R17)이다.

② 파일 저장 위치
- **SU-R7** `PUT /auth/setup/storage` `{path}`: 판정 순서는 닫힘(SU-R2) → 유효 방식 미선택이면 409 `invalid-state` "먼저 인증 방식을 고르세요." → 방식이 `ad`인데 AD 설정 행이 없으면 409 `invalid-state` "먼저 AD 서버를 등록하세요" → 경로 값 규칙(IN-R23) → 쓰기 확인(IN-R24) → (닫힘 재확인) → 저장이다. 앞에서 거절되면 디스크를 건드리지 않는다(예: 방식 미선택이면 상대 경로여도 409). `local`이면 AD 설정 없이 저장할 수 있고, 방식 행이 없어도 AD 설정 행이 있으면(유효 방식 `ad`) 저장할 수 있다. 성공하면 정규화한 경로를 저장(덮어쓰기, `updated_by` NULL)하고 200 `{path, updated_at, updated_by: null}`이다. 쓰기 확인이 실패한 덮어쓰기는 이전 경로를 그대로 둔다. `path`가 없거나 문자열이 아니거나 추가 필드가 있으면 422 `request-validation`.
- **SU-R8** `POST /auth/setup/storage/test` `{path}`(쓰기 테스트): 닫힘(SU-R2) → 경로 값 규칙(IN-R23) → 쓰기 확인(IN-R24)만 하고 204(본문 없음)다. 저장하지 않고(저장 위치 단계는 열린 채, 이미 저장된 경로는 그대로), 인증 방식·AD 설정 여부를 보지 않는다.

③ 첫 admin 등록(`POST /auth/setup`)
- **SU-R9** 공통: 유효 방식이 `local`이면 SU-R10, 그 밖(`ad`·미선택)이면 SU-R11 흐름이다. 공통 결과는 다음과 같다.
  - 예약 아이디 `dev-admin`·`dev-sales`·`dev-user`(정규화 값 정확히 일치, 대소문자 무시)는 422 `invalid-value` "개발 로그인 전용 아이디는 등록할 수 없습니다: <정규화한 아이디>"이고 AD를 부르지 않고 시도 제한에 세지 않으며 설정은 열린 채다. `dev-qa` 같은 다른 `dev-` 아이디는 일반 아이디다.
  - 같은 아이디의 재직 사용자가 이미 있으면(둘 이상이어도) 409 `already-exists` "이미 존재하는 사용자입니다: <아이디>"이고 기존 사용자를 admin으로 올리지 않는다.
  - 성공하면 `role = admin` 사용자를 만들고(마지막 로그인 시각 = 지금), 비밀번호의 scrypt 해시를 저장하고, 세션을 발급해 세션 쿠키를 심는다(쿠키 속성은 AU). 응답 200 `PrincipalResponse{user_id, subject(아이디), email, name, role: "admin"}`. 이후 설정은 닫힌다(SU-R2). `login_id`가 128자를 넘거나 `password`가 256자를 넘으면 422 `request-validation`.
- **SU-R10** local 흐름(판정 순서): 웹 계층에서 비밀번호가 비었거나 공백뿐이거나 NUL이면 422 `invalid-value` + `errors[password]` → 아이디 형식(앞뒤 공백 제거·소문자화 뒤 영문 소문자·숫자로 시작, 영문 소문자·숫자·`.`·`_`·`-` 64자 이하, 위반은 422 `invalid-value` "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다") → 예약 아이디 → 비밀번호 정책 → 프로필 → 닫힘 → 저장 위치 없음 409 `invalid-state` "파일 저장 위치를 먼저 설정하세요." → 해시 계산(트랜잭션 밖) → 방식이 여전히 `local`인지 재확인(아니면 409 `invalid-state` "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.") → 닫힘 재확인 → 중복 아이디 → 등록.
  - 비밀번호 정책: 8자 미만이면 "비밀번호는 8자 이상이어야 합니다", 앞뒤 공백을 지우고 소문자로 바꾼 값이 아이디와 같으면 "비밀번호는 아이디와 같을 수 없습니다". 둘 다 422 `invalid-value`이고 본문 `errors` = `[{"location":["password"],"message":<문구>}]`이다. 8자는 허용한다(조합 규칙 없음).
  - 프로필: `display_name` 필수(앞뒤 공백 제거, 비었으면 "이름은(는) 비어 있을 수 없습니다", 200자 초과면 "이름은(는) 200자를 넘을 수 없습니다"), `email`·`phone` 선택(빈 값·공백은 없음으로 저장, 형식이 틀리면 "이메일 형식이 올바르지 않습니다." / "전화번호 형식이 올바르지 않습니다."). 모두 422 `invalid-value`(`errors` 없음).
  - AD를 부르지 않고 시도 제한도 쓰지 않는다(실패해도 횟수에 남지 않음). 이름·이메일·전화는 입력값으로 저장한다.
- **SU-R11** AD 흐름(판정 순서): 웹 계층에서 비밀번호가 비었거나 공백뿐이거나 NUL이면 401 `unauthenticated` "아이디 또는 비밀번호가 올바르지 않습니다"(AD 호출·시도 제한 집계 없음) → 이름·이메일·전화 중 하나라도 보냈으면 422 `invalid-value` "AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다)."(AD 호출 없음) → 아이디 형식 위반은 401 같은 문구(AD로 보내지 않음) → 예약 아이디 → 시도 제한 확인(초과면 429, AU) → 닫힘 → AD 설정 없음 409 `invalid-state` "먼저 AD 서버를 등록하세요" → 저장 위치 없음 409 "파일 저장 위치를 먼저 설정하세요." → 저장된 바인드 비밀번호 복호화 → AD 인증(서비스 계정 검색 후 사용자 바인드) → 해시 계산 → 방식이 local로 바뀌었으면 409 `invalid-state` "AD 연동 모드에서만 쓸 수 있습니다." → 닫힘 재확인 → 중복 아이디 → 등록.
  - 시도 제한 집계: 비밀번호가 틀리거나 사용자를 찾지 못하면(0건) 401 "아이디 또는 비밀번호가 올바르지 않습니다"이고 실패 1회로 남는다. 닫힘·선행 단계 409와 AD 장애·복호화 불가 503은 실패로 남지 않는다(선점 해제). 성공하면 그 계정·IP의 실패 횟수를 지운다.
  - AD 장애(연결·TLS·서비스 계정 바인드·Base DN·검색 2건 이상·알 수 없는 통신 실패)와 저장된 바인드 비밀번호 복호화 불가는 503 `directory-unavailable` "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"이며 원인 문구를 싣지 않는다. 최초 설정에서는 저장된 비밀번호 해시로 대신 인증하지 않는다(대체 로그인은 AU 로그인에만).
  - 성공하면 이름·이메일은 AD가 준 값(`displayName`·`mail`)으로, 전화번호는 AD 값(`mobile`, 비었으면 `telephoneNumber`, 규칙 AU-R8a)이 있으면 그 값으로 저장하고(없으면 비어 있음), 입력한 비밀번호의 해시를 저장한다(이후 AU 대체 로그인에 쓰임). 비밀번호가 틀린 시도는 해시를 저장하지 않는다.
- **SU-R12** 비밀번호 비노출: 첫 admin 비밀번호와 바인드 비밀번호는 어떤 응답 본문(성공·401·422, AD 연결 테스트 결과 포함)에도, 로그에도 나오지 않는다. 비밀번호 원문은 어느 테이블에도 저장하지 않는다.

화면(frontend)
- **SU-R13** HTTP 게이트웨이 `setup`(`gateway/http/setup.ts`):
  - `status()`는 `GET /api/v1/auth/config`를 읽어 `{authMode: auth_mode ?? null, directoryDone: !needs_directory_setup, storageDone: !needs_storage_setup, adminDone: !(needs_directory_setup || needs_storage_setup || needs_admin_setup)}`를 돌려준다(`auth_mode`가 없는 응답은 `null`).
  - `chooseAuthMode(mode)` = `PUT /api/v1/auth/setup/auth-mode {mode}`, `saveDirectory(input)` = `PUT …/setup/directory`에 7칸(`host, port, security, bind_account, bind_password, user_filter, connect_timeout_seconds`, 비밀번호가 없으면 `""`), `testDirectory(input)` = `POST …/setup/directory/test`에 `saveDirectory`와 같은 7칸을 보내고, 응답이 `success: true`면 `{baseDn: base_dn}`을 돌려주며 `success: false`면 `ApiError` 422 kind `directory-verification-failed`(문구 = 서버 `message`, `stage` 유지)로 바꿔 던진다(IN-R35와 같은 변환), `saveStorage(path)` = `PUT …/setup/storage {path}`(응답 본문은 버림), `testStorage(path)` = `POST …/setup/storage/test {path}`, `registerAdmin(loginId, password, profile?)` = `POST …/setup`에 `{login_id, password}`, profile이 있으면 `display_name`과 값이 있는 `email`·`phone`만 더 보내고, 응답을 `Me{id, loginId, name, role}`로 바꿔 돌려준다. 서버 오류는 상태·`kind`·서버 `detail` 그대로 `ApiError`로 넘긴다(`directory-verification-failed`는 `stage` 포함).
  - `auth.config()`의 `needsSetup`은 세 `needs_*` 중 하나라도 `true`면 `true`다.
- **SU-R14** 진입: 로그인 화면은 `needsSetup`이면 항상 `/setup`으로 바꾼다(이력 교체). 따라서 설정이 필요한 시스템에서 로그인하지 않은 방문자가 보호 화면을 열면 `/login`(PL-R29)을 거쳐 `/setup`으로 간다. `/setup`은 상태를 읽는 동안 "불러오는 중…", 읽기 실패면 제목 "최초 설정"과 오류 배너(서버 문구), `adminDone`이면(관리자 등록 진행 중이 아닐 때) `/login`으로 바꾼다(로그인한 admin도 `/setup`에 머물지 않음).
- **SU-R15** 단계 결정과 표시: 화면은 서버 상태로 정한다 — `authMode`가 `null`이면 인증 방식 선택, `directoryDone`이 아니면 AD 서버 등록 폼, `storageDone`이 아니면 저장 위치, 그 밖은 관리자 등록. 사용자가 "AD 연동"을 누르거나 "인증 방식 다시 선택"을 누른 것만 화면 상태로 덮어쓴다. 제목 "최초 설정", 안내 "처음 한 번만 필요한 설정입니다. 순서대로 진행하세요.", 단계 목록(`aria-label="설정 단계"`) "1. 인증 방식"·"2. 파일 저장 위치"·"3. 관리자 등록" 중 현재 단계에 `aria-current="step"`, 끝난 단계에 "완료" 표시(1단계 완료 = 방식 선택됨 그리고 `directoryDone`).
- **SU-R16** 인증 방식 화면(제목 "인증 방식"): 버튼 "AD 연동"은 서버를 부르지 않고 AD 서버 등록 폼을 연다(방식은 AD 서버를 저장할 때 기록됨). 버튼 "앱에서 직접 관리"는 `chooseAuthMode('local')`을 부르고 성공하면 서버 상태대로 다음 단계(저장 위치)로 간다. 실패하면 서버 문구를 보이고 선택 화면에 머문다. 요청 중에는 두 버튼이 비활성이다.
- **SU-R17** AD 서버 등록 폼(제목 "AD 서버 등록", 안내 "로그인에 사용할 회사 AD 서버를 등록합니다."): 입력 칸과 기본값은 IN-R30의 공용 칸(새 폼: 보안 연결 `ssl`, 포트 636, 사용자 검색 필터 `(&(objectClass=user)(sAMAccountName={login_id}))`, 연결 제한 시간 5, 바인드 비밀번호 빈 값)이다. 버튼은 "인증 방식 다시 선택"·"연결 테스트"·"AD 서버 등록"(주 버튼, 폼 제출) 순서다.
  - 연결 테스트: "연결 테스트"를 누르면, 바인드 비밀번호가 비었거나 공백뿐일 때 서버를 부르지 않고 "바인드 비밀번호를 입력하세요"를 보인다(IN-R32와 같은 검사). 아니면 `testDirectory(입력 7칸)`을 부른다. 성공하면 성공 알림 "연결 테스트에 성공했습니다. Base DN: <찾은 값>"을 보이고 '테스트 성공' 상태가 된다. 실패하면 아래 문구 규칙으로 오류를 보이고 입력값(바인드 비밀번호 포함)을 유지하며 '테스트 성공'이 아니다.
  - 등록 버튼 활성: "AD 서버 등록"은 '테스트 성공' 상태이고 요청 중이 아닐 때만 활성이다. '테스트 성공'이 아닐 때는 비활성이고 버튼 근처에 안내 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다."를 보인다('테스트 성공'이면 숨김). '테스트 성공'이 아닐 때 폼 제출(입력 칸에서 Enter 포함)은 아무 요청도 보내지 않는다.
  - 무효화: '테스트 성공' 뒤 7칸 중 하나라도 바뀌면(같은 값으로 되돌려도, 보안 연결 변경으로 포트가 자동으로 바뀌어도) 성공 알림이 사라지고 '테스트 성공'이 풀려 등록이 다시 비활성이 된다. 성공 알림의 닫기는 알림만 숨기고 '테스트 성공'은 유지한다.
  - 등록: 활성 상태에서 "AD 서버 등록"을 누르면 테스트한 7칸 그대로 `saveDirectory`를 부른다(서버는 SU-R6으로 다시 확인한다). 성공하면 서버 상태대로 다음 단계로 간다. 실패하면 아래 문구 규칙으로 오류를 보이고 입력값을 유지하며 폼에 머물고, '테스트 성공'을 풀어 등록을 비활성으로 한다(다시 연결 테스트해야 등록할 수 있음).
  - 공통: 한 동작(테스트·등록)을 시작하면 이전 결과(성공 알림·오류)를 지운다. 요청 중에는 "연결 테스트"·"AD 서버 등록"이 모두 비활성이다. 입력한 바인드 비밀번호는 테스트 뒤에도 칸에 남긴다(등록에 다시 쓴다). 비밀번호가 든 요청 값은 쿼리 캐시에 남기지 않는다(테스트·등록 모두 `gcTime: 0`).
  - 문구 규칙: 서버 거절이 `directory-verification-failed`면 단계별 화면 문구(2.8, 모르는 단계는 서버 문구), 429면 "시도가 너무 많습니다. 잠시 후 다시 시도하세요.", 그 밖은 서버 문구.
  - "인증 방식 다시 선택"은 선택 화면으로 간다. 다시 "AD 연동"으로 열면 기본값의 새 폼이고 '테스트 성공'이 아니다.
- **SU-R18** 저장 위치 화면(제목 "파일 저장 위치"): 안내 "Deal 첨부 파일이 저장될 서버의 절대 경로를 입력합니다. 예: /var/lib/neoine-sales/files"와 "나중에 Admin > Settings > 외부연동에서 바꿀 수 있습니다. 위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다.", 칸 "저장 경로"(처음 빈 값, 화면은 경로를 미리 검증하지 않음). "쓰기 테스트"가 성공하면 성공 알림 "쓰기 테스트에 성공했습니다."를 보이고 저장하지 않으며 단계에 머문다. "저장 위치 등록"이 성공하면 관리자 등록으로 간다. 어느 쪽이든 실패하면 서버 문구(SU-R17과 같은 문구 규칙)를 보이고 입력을 유지한다. 한쪽을 실행하면 다른 쪽의 이전 결과(알림·오류)를 지우고, 요청 중에는 두 버튼이 비활성이다. "인증 방식 다시 선택"은 선택 화면으로 간다.
- **SU-R19** 관리자 등록 화면(제목 "관리자 등록"):
  - AD(방식이 `local`이 아님): 안내 "처음 등록하는 AD 계정이 관리자가 됩니다.", 칸 "AD 아이디"·"비밀번호"(`autocomplete="current-password"`). 입력한 그대로 `registerAdmin(loginId, password)`를 부른다(프로필 없음).
  - local: 안내 "처음 등록하는 계정이 관리자가 됩니다. 아이디와 비밀번호는 이 앱에서 직접 관리합니다.", 칸 "아이디"·"비밀번호"(`new-password`)·"비밀번호 확인"·"이름"·"이메일"·"전화번호". 비밀번호와 확인이 둘 다 비었으면 "비밀번호를 입력하세요.", 서로 다르면(비밀번호만 빈 경우 포함) "비밀번호 확인이 일치하지 않습니다."를 보이고 서버를 부르지 않는다. 아이디·이름·이메일·전화는 앞뒤 공백을 지워 보내고 빈 이메일·전화는 `null`이다.
  - 성공하면 그 admin으로 로그인된 상태가 되어 `/`(Deals 기본 목록)로 간다(이력 교체). 실패하면 서버 문구를 보이고 비밀번호(local은 확인까지) 칸을 비우며 다른 입력은 유지하고 단계에 머문다. 서버 `errors[].location`이 가리킨 칸(`login_id`·`password`·`display_name`·`email`·`phone`)은 잘못된 칸으로 표시한다. 요청 값은 쿼리 캐시에 남기지 않는다(`gcTime: 0`). "인증 방식 다시 선택"은 선택 화면으로 간다.

### 2.4 상태와 전이

설정 진행(서버, admin = 재직 admin)

| 상태 | auth_mode | needs_directory | needs_storage | needs_admin | 다음 |
| --- | --- | --- | --- | --- | --- |
| 새 시스템 | null | true | true(저장 위치 없음) | false | 방식 local 선택 / AD 서버 등록(→ ad) |
| ad, AD 설정 없음 | ad | true | 저장 위치 유무 | false | AD 서버 등록 |
| AD 단계 완료, 저장 위치 없음 | ad·local | false | true | false | 저장 위치 등록 |
| 관리자만 남음 | ad·local | false | false | true | 첫 admin 등록 |
| 닫힘 | 유효 방식 | false | false | false | (최초 설정 불가, 변경은 IN) |

admin이 생기기 전에는 어느 상태에서든 방식 선택·AD 서버 등록·저장 위치 등록으로 앞 단계를 다시 바꿀 수 있다(SU-R1).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin | 비고 |
| --- | --- | --- | --- | --- | --- |
| `PUT /auth/setup/auth-mode`·`/directory`·`/storage`, `POST /auth/setup/directory/test`·`/auth/setup/storage/test`·`/auth/setup` | 가능(설정이 열려 있을 때) | 같음 | 같음 | 같음 | 세션을 보지 않는다. 재직 admin이 있으면 누구든 409(SU-R2) |
| `/setup` 화면 | 가능 | 같음 | 같음 | 같음 | 설정이 끝났으면 `/login`으로(SU-R14) |

### 2.6 API 계약 (`/api/v1`, 모두 공개 경로·CSRF 헤더 필요)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| PUT `/auth/setup/auth-mode` | `{"mode":"ad"|"local"}` | 204 | 409 `invalid-state`(닫힘), 422 `request-validation` |
| PUT `/auth/setup/directory` | `DirectorySettingsRequest`(7칸) | 200 `DirectorySettingsResponse` | 409 `invalid-state`(닫힘), 422 `request-validation`·`invalid-value`·`directory-verification-failed`(+`stage`) |
| POST `/auth/setup/directory/test` | `DirectorySettingsRequest`(7칸, PUT과 같음) | 200 `DirectoryTestResultResponse` `{success, stage, message, base_dn}`(확인 실패도 200 `success: false`) | 409 `invalid-state`(닫힘), 422 `request-validation`·`invalid-value` |
| PUT `/auth/setup/storage` | `{"path":string}` | 200 `{path, updated_at, updated_by:null}` | 409 `invalid-state`(닫힘·방식 미선택·AD 먼저), 422 `request-validation`·`invalid-value` |
| POST `/auth/setup/storage/test` | `{"path":string}` | 204 | 409 `invalid-state`(닫힘), 422 `request-validation`·`invalid-value` |
| POST `/auth/setup` | `{"login_id","password","display_name"?,"email"?,"phone"?}` | 200 `PrincipalResponse` + 세션 쿠키 | 401 `unauthenticated`, 409 `invalid-state`·`already-exists`, 422 `request-validation`·`invalid-value`(+`errors` 비밀번호), 429 `too-many-attempts`, 503 `directory-unavailable` |
| GET `/auth/config`(AU 경로) | — | 200, 진행 상태는 SU-R4 | — |

- 라우터: `web/routers/auth_setup.py`(`APIRouter(prefix="/api/v1/auth", dependencies=[require_csrf_header])`). 유스케이스: `ChooseSetupAuthMode`, `RegisterSetupDirectory`, `TestSetupDirectory`, `RegisterSetupStorage`, `TestSetupStorage`, `SetupAdmin`(→ `SetupFirstLocalAdmin`·`SetupFirstAdmin`), 진행 상태 `GetAuthStatus`.
- openapi: 여섯 경로가 문서화되고(연결 테스트 응답은 `DirectoryTestResultResponse`, 요청은 PUT과 같은 `DirectorySettingsRequest`), `AuthModeRequest`의 속성은 `mode` 하나, `SetupAdminRequest`의 `display_name`·`email`·`phone`은 선택, 오류 응답은 위 표의 상태 코드다. 새 오류 type 없음.

### 2.7 화면 동작

SU-R13~SU-R19.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구(`detail`) |
| --- | --- | --- |
| 설정 닫힘(재직 admin 있음) | 409 `invalid-state` | 이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다 |
| 저장 위치: 방식 미선택 | 409 `invalid-state` | 먼저 인증 방식을 고르세요. |
| 저장 위치·AD 방식 admin: AD 설정 없음 | 409 `invalid-state` | 먼저 AD 서버를 등록하세요 |
| admin: 저장 위치 없음 | 409 `invalid-state` | 파일 저장 위치를 먼저 설정하세요. |
| local admin 등록 중 방식이 바뀜 | 409 `invalid-state` | 앱에서 계정을 직접 관리할 때만 쓸 수 있습니다. |
| AD admin 등록 중 방식이 local로 바뀜 | 409 `invalid-state` | AD 연동 모드에서만 쓸 수 있습니다. |
| 같은 아이디의 재직 사용자 | 409 `already-exists` | 이미 존재하는 사용자입니다: <아이디> |
| 예약 아이디 | 422 `invalid-value` | 개발 로그인 전용 아이디는 등록할 수 없습니다: <아이디> |
| local 아이디 형식 | 422 `invalid-value` | 로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다 |
| local 비밀번호 빈 값·공백 / NUL | 422 `invalid-value` + `errors[password]` | 비밀번호는 비어 있을 수 없습니다 / 비밀번호에는 NUL 문자를 쓸 수 없습니다 |
| local 비밀번호 정책 | 422 `invalid-value` + `errors[password]` | 비밀번호는 8자 이상이어야 합니다 / 비밀번호는 아이디와 같을 수 없습니다 |
| local 이름 | 422 `invalid-value` | 이름은(는) 비어 있을 수 없습니다 / 이름은(는) 200자를 넘을 수 없습니다 |
| local 이메일·전화 형식 | 422 `invalid-value` | 이메일 형식이 올바르지 않습니다. / 전화번호 형식이 올바르지 않습니다. |
| AD 방식에 프로필 필드 | 422 `invalid-value` | AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다). |
| AD 방식 비밀번호 빈 값·틀림, 아이디 형식, 사용자 0건 | 401 `unauthenticated` | 아이디 또는 비밀번호가 올바르지 않습니다 |
| AD 장애·바인드 비밀번호 복호화 불가 | 503 `directory-unavailable` | 인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요 |
| 시도 제한 초과 | 429 `too-many-attempts` | AU 문구 |
| 저장 경로·쓰기 확인 | 422 `invalid-value` | IN-R23·IN-R24 문구("절대 경로를 입력하세요." 등, "해당 위치에 쓸 수 없습니다.") |
| AD 칸 값 | 422 `invalid-value` | IN-R2~IN-R8 문구 |
| AD 확인 실패 `connect` | 422 `directory-verification-failed` | AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요 |
| AD 확인 실패 `tls` | 같음 | TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요 |
| AD 확인 실패 `service_bind` | 같음 | 바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요 |
| AD 확인 실패 `base_dn` | 같음 | AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요 |
| AD 연결 테스트 성공(결과 `message`) | 200 `success: true` | AD 설정을 확인했습니다 |
| AD 연결 테스트 확인 실패(결과 `message`) | 200 `success: false` + `stage` | 위 `connect`·`tls`·`service_bind`·`base_dn` 단계 문구와 같음 |
| 요청 형식(모르는 필드·타입·누락) | 422 `request-validation` | 요청 형식이 올바르지 않습니다 |

화면 문구(frontend, 서버 `detail` 대신 보임): `directory-verification-failed`의 단계별 문구는 IN 2.8의 화면 문구와 같다(`shared/directory/messages.ts`, 예: `connect` "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요.", 모르는 단계는 서버 문구), 429 "시도가 너무 많습니다. 잠시 후 다시 시도하세요."(AD 폼·저장 위치), 화면 검사 "바인드 비밀번호를 입력하세요", "비밀번호를 입력하세요.", "비밀번호 확인이 일치하지 않습니다.", 성공 알림 "쓰기 테스트에 성공했습니다."·"연결 테스트에 성공했습니다. Base DN: <찾은 값>", AD 폼 안내 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다.".

## 3. Business use case

### SU-UC1 설정 진행 상태 확인
- 행위자: 방문자(화면), 시스템
- 기본 흐름: `GET /auth/config`로 진행 상태를 읽어(SU-R4) 화면이 단계를 정한다(SU-R13·R15). 로그인 화면은 설정이 필요하면 `/setup`으로 보낸다(SU-R14)
- 결과: 남은 단계가 보인다. 설정이 끝났으면 `/setup`은 `/login`으로 간다

### SU-UC2 인증 방식 선택
- 행위자: 설치 담당자
- 사전 조건: 재직 admin 없음
- 기본 흐름: "앱에서 직접 관리" → `PUT /auth/setup/auth-mode {local}` → 저장 위치 단계(SU-R5·R16)
- 대안: "AD 연동" → 서버 호출 없이 AD 서버 등록 폼(SU-UC3). admin 전이면 언제든 다시 고를 수 있다
- 예외: 닫힘 409, 잘못된 방식 422
- 결과: 유효 방식이 정해지고 AD 단계 완료 여부가 바뀐다

### SU-UC3 AD 서버 등록
- 행위자: 설치 담당자
- 사전 조건: 재직 admin 없음
- 기본 흐름: 접속 정보 6칸 + 바인드 비밀번호 입력 → "연결 테스트"(서비스 계정 바인드·Base DN 탐색, 저장 없음, 찾은 Base DN 표시, SU-R20) → 성공하면 "AD 서버 등록" 활성 → 등록(서버가 다시 확인) → 저장·방식 `ad` 기록 → 저장 위치 단계(SU-R6·R17)
- 대안: 테스트 성공 뒤 입력을 바꾸면 등록이 다시 꺼져 다시 테스트한다. admin 전 다시 저장하면 덮어쓴다(revision +1)
- 예외: 빈 바인드 비밀번호(화면, 요청 없음), 칸 값 422, 테스트 확인 실패(200 `success: false`, 등록 비활성 유지), 등록 확인 실패 422 `directory-verification-failed`(저장 없음, 다시 테스트 필요), 닫힘 409
- 결과: AD 설정 행과 `auth_settings = ad`

### SU-UC4 파일 저장 위치 등록과 쓰기 테스트
- 행위자: 설치 담당자
- 사전 조건: 재직 admin 없음, (등록은) 방식 선택됨·AD 방식이면 AD 설정 있음
- 기본 흐름: 경로 입력 → (선택) 쓰기 테스트 204 → 등록(경로 규칙·쓰기 확인 뒤 저장) → 관리자 등록 단계(SU-R7·R8·R18)
- 예외: 선행 단계 409, 경로·쓰기 실패 422(이전 값 유지), 닫힘 409
- 결과: 정규화한 저장 경로

### SU-UC5 첫 admin 등록(AD 연동)
- 행위자: 설치 담당자(AD 계정 보유)
- 사전 조건: 재직 admin 없음, AD 설정·저장 위치 있음
- 기본 흐름: AD 아이디·비밀번호 → AD 인증 → admin 등록(AD 이름·이메일, 해시 저장) → 세션 발급 → `/`(SU-R9·R11·R19)
- 예외: 빈 비밀번호·틀린 비밀번호 401(틀림만 실패 집계), 프로필 필드 422, 예약 아이디 422, 선행 단계 409, 중복 아이디 409, AD 장애 503, 시도 초과 429, 닫힘 409
- 결과: 첫 admin이 로그인되고 최초 설정이 닫힌다

### SU-UC6 첫 admin 등록(앱에서 직접 관리)
- 행위자: 설치 담당자
- 사전 조건: 재직 admin 없음, 방식 local, 저장 위치 있음
- 기본 흐름: 아이디·비밀번호·확인·이름(·이메일·전화) → 화면 검사 → 서버 검사 → admin 등록(해시 저장) → 세션 발급 → `/`(SU-R9·R10·R19)
- 예외: 화면 검사(빈 비밀번호·확인 불일치), 아이디·비밀번호 정책·프로필 422, 예약 아이디 422, 저장 위치 없음 409, 중복 409, 닫힘 409
- 결과: 첫 admin이 로그인되고 최초 설정이 닫힌다

### SU-UC7 설정이 닫힌 뒤의 시도
- 행위자: 누구나(미인증 포함)
- 사전 조건: 재직 admin 있음
- 기본 흐름: 어떤 최초 설정 경로를 불러도 409 "이미 관리자가 등록되어…"(SU-R2), 화면은 `/login`으로(SU-R14)
- 결과: 설정·사용자·방식이 바뀌지 않고 AD를 부르지 않는다

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| SU-001 | 새 시스템은 방식 미선택이고 AD·저장 위치 단계가 필요하며 관리자 단계는 아직이다 | SU-R4, SU-R3, SU-UC1 | backend | `application/test_setup_progress.py::test_new_system_has_no_mode_and_needs_directory_and_storage`<br>`web/test_setup_routes.py::test_config_of_a_new_system_is_unselected_with_directory_and_storage_needed` |
| SU-002 | local을 고르면 AD 단계가 없어지고 저장 위치를 저장하면 관리자 단계만 남는다 | SU-R4, SU-R5, SU-UC1 | backend | `application/test_setup_progress.py::test_choosing_local_drops_the_directory_step_and_storage_leaves_only_admin` |
| SU-003 | ad 방식에서 AD 설정이 없으면 AD 단계가, AD·저장 위치가 있으면 관리자 단계만 남는다 | SU-R4, SU-UC1 | backend | `application/test_setup_progress.py::test_ad_mode_needs_directory_until_directory_and_storage_exist` |
| SU-004 | 재직 admin이 있으면 설정 행이 없어도 진행 상태는 모두 끝남이다 | SU-R4, SU-R2, SU-UC1 | backend | `application/test_setup_progress.py::test_every_step_is_done_once_an_admin_exists_even_without_setting_rows`<br>`web/test_setup_routes.py::test_config_with_an_admin_and_no_setting_rows_is_all_done_and_ad` |
| SU-005 | 퇴사한 admin이나 admin이 아닌 사용자만 있으면 설정은 열려 있다 | SU-R2, SU-R4, SU-UC1 | backend | `application/test_setup_progress.py::test_resigned_admin_or_non_admins_leave_the_setup_open` |
| SU-006 | 방식 행이 없는 기존 시스템은 ad이고 저장된 local은 남은 AD 설정보다 우선한다 | SU-R3, SU-UC1 | backend | `application/test_setup_progress.py::test_a_legacy_system_with_an_admin_and_no_mode_row_is_ad`<br>`application/test_setup_progress.py::test_a_legacy_system_with_only_a_directory_row_is_ad_and_needs_no_directory`<br>`application/test_setup_progress.py::test_stored_local_beats_a_leftover_directory_row` |
| SU-007 | admin 전에는 인증 방식을 고르고 다시 바꿀 수 있다 | SU-R5, SU-UC2 | backend | `application/test_setup_auth_mode_cases.py::test_the_mode_can_be_chosen_and_changed_before_the_first_admin` |
| SU-008 | local을 골라도 저장된 AD 설정은 지워지지 않는다 | SU-R5, SU-UC2 | backend | `application/test_setup_auth_mode_cases.py::test_choosing_local_keeps_the_saved_directory_settings` |
| SU-009 | admin이 생긴 뒤 방식 선택은 409이고 방식은 그대로다 | SU-R2, SU-R5, SU-UC7 | backend | `application/test_setup_auth_mode_cases.py::test_choosing_a_mode_after_the_first_admin_is_closed_and_keeps_the_mode` |
| SU-010 | 알 수 없는 인증 방식은 422 request-validation이다 | SU-R5, SU-UC2 | backend | `web/test_setup_routes.py::test_an_unknown_auth_mode_is_a_request_validation_error` |
| SU-011 | AD 서버를 등록하면 찾은 Base DN과 함께 저장되고 방식이 ad가 된다 | SU-R6, SU-UC3 | backend | `application/test_setup_directory_cases.py::test_registering_the_directory_stores_the_found_base_dn_and_records_ad` |
| SU-012 | admin 전에는 AD 서버를 다시 저장해 덮어쓰고 local을 골랐어도 ad로 바뀐다 | SU-R6, SU-R1, SU-UC3 | backend | `application/test_setup_directory_cases.py::test_registering_again_overwrites_and_switches_local_to_ad` |
| SU-013 | AD 확인이 단계별로 실패하면 422와 단계만 알리고 아무것도 저장하지 않는다 | SU-R6, SU-UC3 | backend | `application/test_setup_directory_cases.py::test_a_failed_check_reports_only_the_stage_and_saves_nothing` |
| SU-014 | 형식이 틀린 AD 서버 입력은 422이고 AD를 부르지 않는다 | SU-R6, SU-UC3 | backend | `web/test_setup_routes.py::test_a_malformed_directory_body_is_rejected_without_calling_the_directory`<br>`web/test_setup_routes.py::test_a_missing_bind_password_is_a_request_validation_error` |
| SU-015 | 저장 위치를 등록하면 정규화한 경로가 저장되고 관리자 단계가 남는다 | SU-R7, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_registering_normalizes_the_path_creates_it_and_leaves_no_probe_file` |
| SU-016 | admin 전에는 저장 위치를 덮어쓸 수 있고 실패한 덮어쓰기는 이전 경로를 남긴다 | SU-R7, SU-R1, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_a_failed_overwrite_keeps_the_previous_path` |
| SU-017 | 방식 미선택이나 AD 방식의 AD 미등록이면 저장 위치는 경로 검사 전에 409다 | SU-R7, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_registering_without_a_mode_is_auth_mode_first_before_any_path_check`<br>`application/test_setup_storage_cases.py::test_registering_in_ad_mode_without_a_directory_is_directory_first`<br>`application/test_setup_storage_cases.py::test_registering_in_local_mode_needs_no_directory`<br>`application/test_setup_storage_cases.py::test_registering_with_only_a_directory_row_works` |
| SU-018 | 형식이 틀린 저장 경로는 422이고 디스크를 건드리지 않는다 | SU-R7, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_a_malformed_path_is_invalid_value_and_never_touches_the_disk` |
| SU-019 | 쓸 수 없는 위치는 고정 문구의 422이고 저장되지 않는다 | SU-R7, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_an_unwritable_location_has_a_fixed_message_and_saves_nothing` |
| SU-020 | 저장 위치 본문 형식이 틀리면 422 request-validation이다 | SU-R7, SU-UC4 | backend | `web/test_setup_routes.py::test_a_malformed_storage_body_is_a_request_validation_error` |
| SU-021 | 쓰기 테스트는 204이고 저장하지 않으며 방식·AD 설정 없이도 된다 | SU-R8, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_the_write_test_saves_nothing_and_needs_no_mode_or_directory`<br>`application/test_setup_storage_cases.py::test_the_write_test_keeps_an_already_saved_path` |
| SU-022 | 쓰기 테스트도 경로·쓰기 실패를 같은 문구의 422로 알린다 | SU-R8, SU-UC4 | backend | `application/test_setup_storage_cases.py::test_the_write_test_rejects_a_malformed_path_like_registration`<br>`application/test_setup_storage_cases.py::test_the_write_test_rejects_an_unwritable_location` |
| SU-023 | AD 계정으로 확인된 사람이 첫 admin이 되어 로그인된다 | SU-R9, SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_an_ad_verified_account_becomes_the_first_admin_and_is_signed_in` |
| SU-024 | AD 비밀번호가 틀리면 401이고 아무도 등록되지 않으며 실패 1회가 남는다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_a_wrong_password_is_a_401_that_registers_nobody_and_counts_one_failure` |
| SU-025 | AD 방식의 빈 비밀번호와 형식이 틀린 아이디는 AD에 보내지 않고 401이다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_a_malformed_login_id_is_a_401_that_never_reaches_the_directory`<br>`web/test_setup_routes.py::test_a_blank_or_nul_password_in_ad_mode_is_401_and_never_reaches_the_directory` |
| SU-026 | AD 장애와 바인드 비밀번호 복호화 불가는 503이고 해시로 대신하지 않으며 실패로 세지 않는다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_a_directory_outage_is_raised_without_fallback_and_not_counted`<br>`web/test_setup_routes.py::test_a_directory_outage_is_a_503_without_the_cause` |
| SU-027 | 첫 admin 등록이 5번 실패하면 올바른 비밀번호도 429이고 AD를 부르지 않는다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_after_five_failures_even_the_right_password_is_throttled_without_a_directory_call` |
| SU-028 | AD 서버나 저장 위치가 없으면 첫 admin 등록은 409이고 AD를 부르지 않으며 실패로 세지 않는다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_a_missing_prerequisite_is_a_409_that_skips_the_directory_and_the_counter` |
| SU-029 | 같은 아이디의 재직 사용자가 있으면 첫 admin 등록은 409 already-exists이고 승격하지 않는다 | SU-R9, SU-UC5, SU-UC6 | backend | `application/test_setup_ad_admin_cases.py::test_an_existing_active_login_id_is_already_exists_and_is_not_promoted`<br>`application/test_setup_local_admin_cases.py::test_an_existing_active_login_id_is_already_exists_in_local_mode` |
| SU-030 | AD 방식에 이름·이메일·전화를 보내면 422이고 AD를 부르지 않는다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_profile_fields_in_ad_mode_are_invalid_and_never_reach_the_directory` |
| SU-031 | 해시 계산 중 인증 방식이 바뀌었으면 첫 admin 등록은 409이고 아무도 등록되지 않는다 | SU-R10, SU-R11, SU-UC5, SU-UC6 | backend | `application/test_setup_ad_admin_cases.py::test_a_mode_switched_to_local_during_the_directory_check_is_a_409`<br>`application/test_setup_local_admin_cases.py::test_a_mode_switched_to_ad_during_hashing_is_a_409` |
| SU-032 | local 방식에서 입력한 아이디·비밀번호·이름으로 첫 admin이 만들어지고 로그인된다 | SU-R9, SU-R10, SU-UC6 | backend | `application/test_setup_local_admin_cases.py::test_local_input_creates_the_first_admin_and_signs_in`<br>`application/test_setup_local_admin_cases.py::test_omitted_email_and_phone_are_stored_as_none` |
| SU-033 | local 비밀번호가 8자 미만이거나 아이디와 같으면 password 칸 422이다(8자는 허용) | SU-R10, SU-UC6 | backend | `application/test_setup_local_admin_cases.py::test_a_weak_password_is_rejected_and_the_setup_stays_open`<br>`application/test_setup_local_admin_cases.py::test_an_eight_character_password_is_allowed`<br>`web/test_setup_routes.py::test_a_weak_local_password_is_422_on_the_password_field` |
| SU-034 | local 방식의 빈·공백·NUL 비밀번호는 401이 아니라 password 칸 422다 | SU-R10, SU-UC6 | backend | `web/test_setup_routes.py::test_a_blank_or_nul_local_password_is_422_on_the_password_field_not_401` |
| SU-035 | local 이름이 없거나 길거나 이메일·전화 형식이 틀리면 422이고 설정은 열린 채다 | SU-R10, SU-UC6 | backend | `application/test_setup_local_admin_cases.py::test_an_invalid_profile_is_rejected_and_the_setup_stays_open` |
| SU-036 | local 아이디는 소문자로 맞추고 형식이 틀리면 422다 | SU-R10, SU-UC6 | backend | `application/test_setup_local_admin_cases.py::test_the_login_id_is_trimmed_and_lowercased`<br>`application/test_setup_local_admin_cases.py::test_a_malformed_login_id_is_rejected` |
| SU-037 | local 방식에서 저장 위치가 없으면 첫 admin 등록은 409이고 시도 제한을 쓰지 않는다 | SU-R10, SU-UC6 | backend | `application/test_setup_local_admin_cases.py::test_without_a_storage_path_the_registration_is_storage_first_and_uses_no_counter` |
| SU-038 | 예약 아이디로는 두 방식 모두 첫 admin을 만들 수 없고 이후 일반 계정으로는 된다 | SU-R9, SU-UC5, SU-UC6 | backend | `application/test_setup_ad_admin_cases.py::test_reserved_ids_are_rejected_in_ad_mode_and_a_normal_account_still_works`<br>`application/test_setup_ad_admin_cases.py::test_a_dev_prefixed_id_that_is_not_reserved_is_an_ordinary_account`<br>`application/test_setup_local_admin_cases.py::test_reserved_ids_are_rejected_in_local_mode_and_a_normal_account_still_works` |
| SU-039 | 재직 admin이 있으면 모든 최초 설정 경로가 409이고 AD를 부르지 않으며 바뀌는 것이 없다 | SU-R2, SU-UC7 | backend | `application/test_setup_closed_cases.py::test_every_setup_operation_is_closed_and_changes_nothing`<br>`application/test_setup_closed_cases.py::test_every_setup_operation_stays_closed_when_the_setting_rows_are_gone`<br>`application/test_setup_closed_cases.py::test_the_local_first_admin_registration_is_closed_too` |
| SU-040 | 최초 설정 경로는 로그인 없이 쓸 수 있다 | SU-R1, SU-UC3, SU-UC4 | backend | `web/test_setup_routes.py::test_the_setup_routes_work_without_a_session` |
| SU-041 | 첫 admin·바인드 비밀번호는 응답과 로그 어디에도 나오지 않는다 | SU-R12, SU-UC3, SU-UC5 | backend | `web/test_setup_routes.py::test_neither_password_appears_in_any_response_or_log` |
| SU-042 | openapi에 최초 설정 경로와 요청 모양이 문서화된다 | SU-R5, SU-R9 | backend | `web/test_setup_routes.py::test_openapi_documents_the_six_setup_routes_and_their_request_shapes`<br>`web/test_setup_routes.py::test_openapi_setup_directory_request_takes_the_seven_fields_with_a_masked_password` |
| SU-043 | HTTP 게이트웨이는 진행 상태를 세 단계 완료 여부와 방식으로 바꾼다 | SU-R13, SU-UC1 | frontend | `gateway/http/setup.cases.test.ts > maps needs_directory=%s needs_storage=%s needs_admin=%s auth_mode=%s to the step flags and needsSetup`<br>`gateway/http/setup.cases.test.ts > reads the progress from GET /api/v1/auth/config` |
| SU-044 | HTTP 게이트웨이는 각 단계를 정해진 경로·본문으로 보낸다 | SU-R13, SU-UC2, SU-UC3, SU-UC4, SU-UC5, SU-UC6 | frontend | `gateway/http/setup.cases.test.ts > sends each step to its path with its body` |
| SU-045 | HTTP 게이트웨이는 서버 거절을 상태·문구·단계 그대로 넘긴다 | SU-R13, SU-UC3, SU-UC4, SU-UC5, SU-UC6 | frontend | `gateway/http/setup.cases.test.ts > %s rejects with the server status, kind and message (%s %s)`<br>`gateway/http/setup.cases.test.ts > keeps the failed stage of a directory verification error` |
| SU-046 | 최초 설정이 필요하면 로그인 화면과 보호 화면 방문은 /setup으로 간다 | SU-R14, SU-UC1 | frontend | `features/setup/SetupFlow.cases.test.tsx > sends an anonymous visitor of %s to /setup while the setup is needed` |
| SU-047 | 설정이 끝난 시스템의 /setup은 로그인 화면으로 가고 상태를 못 읽으면 오류를 보인다 | SU-R14, SU-UC7 | frontend | `features/setup/SetupFlow.cases.test.tsx > sends an anonymous visitor of a finished AD system from /setup to the login page`<br>`features/setup/SetupFlow.cases.test.tsx > sends an anonymous visitor of a finished local system from /setup to the login page`<br>`features/setup/SetupFlow.cases.test.tsx > does not keep a signed-in admin on /setup`<br>`features/setup/SetupFlow.cases.test.tsx > shows the server message as an alert when the status cannot be read` |
| SU-048 | 새 시스템의 /setup은 인증 방식 선택과 세 단계 표시로 시작한다 | SU-R15, SU-R16, SU-UC2 | frontend | `features/setup/SetupFlow.cases.test.tsx > starts with the auth mode choice and the three step labels` |
| SU-049 | "앱에서 직접 관리"를 누르면 서버에 기록하고 AD 폼 없이 저장 위치 단계로 간다 | SU-R16, SU-UC2 | frontend | `features/setup/SetupFlow.cases.test.tsx > records local on the server and moves to the storage step without an AD form` |
| SU-050 | 방식 선택이 거절되면 서버 문구를 보이고 선택 화면에 머문다 | SU-R16, SU-UC2, SU-UC7 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows the server message and stays on the choice when choosing fails (%s)` |
| SU-051 | "AD 연동"은 서버를 부르지 않고 기본값이 채워진 AD 폼을 열고 되돌아갈 수 있다 | SU-R16, SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > opens the AD form with defaults without calling the server and can go back` |
| SU-052 | 연결 테스트에 성공한 AD 폼을 등록하면 7칸을 보내고 1단계 완료와 함께 저장 위치 단계로 간다 | SU-R17, SU-R15, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > sends the seven inputs and moves to the storage step with step 1 done` |
| SU-053 | 바인드 비밀번호가 비면 연결 테스트도 서버를 부르지 않고 입력을 요구한다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > asks for the bind password without calling the server` |
| SU-054 | 연결 테스트 뒤 등록이 거절되면 문구를 보이고 입력을 유지하며 다시 테스트해야 등록할 수 있다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows the server message for an invalid value and keeps the input`<br>`features/setup/SetupFlow.cases.test.tsx > explains the %s stage of a verification failure and keeps the input` |
| SU-055 | 화면 단계는 서버 진행 상태를 따른다 | SU-R15, SU-UC1 | frontend | `features/setup/SetupFlow.cases.test.tsx > opens the AD form directly when the mode is ad but no AD server exists`<br>`features/setup/SetupFlow.cases.test.tsx > opens the storage step directly when the AD server exists but the location does not`<br>`features/setup/SetupFlow.cases.test.tsx > skips the storage step when the location already exists, even after going back` |
| SU-056 | 저장 위치 단계는 안내를 보이고 잘못된 경로는 서버 문구로 거절하며 입력을 유지한다 | SU-R18, SU-UC4 | frontend | `features/setup/SetupFlow.cases.test.tsx > explains the location and starts with an empty path`<br>`features/setup/SetupFlow.cases.test.tsx > rejects the path %j with the server message and keeps the input` |
| SU-057 | 쓰기 테스트는 성공 알림만 보이고 저장하지 않으며 다시 하면 이전 결과를 지운다 | SU-R18, SU-UC4 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows only a success notice for the write test and does not save`<br>`features/setup/SetupFlow.cases.test.tsx > shows the server message for an unwritable location and clears it on the next run` |
| SU-058 | 저장 위치를 등록해야 관리자 등록 단계가 열린다 | SU-R18, SU-R15, SU-UC4 | frontend | `features/setup/SetupFlow.cases.test.tsx > opens the admin step only after the location is registered` |
| SU-059 | "인증 방식 다시 선택"으로 선택 화면에 돌아가 AD로 바꿀 수 있다 | SU-R15, SU-R16, SU-UC2 | frontend | `features/setup/SetupFlow.cases.test.tsx > goes back from the storage step and switches to AD`<br>`features/setup/SetupFlow.cases.test.tsx > goes back from the local admin step and switches to AD, ending at the admin step` |
| SU-060 | AD 방식 관리자 등록이 성공하면 그 admin으로 로그인되어 Deals로 간다 | SU-R19, SU-UC5 | frontend | `features/setup/SetupFlow.cases.test.tsx > signs in as the new AD admin and moves to the deals list` |
| SU-061 | 관리자 등록이 거절되면 서버 문구를 보이고 비밀번호를 지운다 | SU-R19, SU-UC5, SU-UC6 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows the login failure message and clears the password`<br>`features/setup/SetupFlow.cases.test.tsx > refuses an id that already belongs to an active user instead of promoting it` |
| SU-062 | local 방식 관리자 등록은 프로필 칸을 받고 성공하면 그 admin으로 로그인된다 | SU-R19, SU-UC6 | frontend | `features/setup/SetupFlow.cases.test.tsx > registers the local admin with the profile and signs in`<br>`features/setup/SetupFlow.cases.test.tsx > sends an empty email and phone as null` |
| SU-063 | local 방식에서 비밀번호가 비거나 확인과 다르면 서버를 부르지 않는다 | SU-R19, SU-UC6 | frontend | `features/setup/SetupFlow.cases.test.tsx > does not call the server when %s` |
| SU-064 | local 방식 서버 거절은 문구를 보이고 두 비밀번호 칸을 비우며 다른 입력은 유지한다 | SU-R19, SU-UC6 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows the weak password message, clears both password fields, keeps the rest and flags the field`<br>`features/setup/SetupFlow.cases.test.tsx > shows the name message from the server and keeps the other inputs` |
| SU-065 | 연결 테스트가 성공하면 찾은 Base DN을 돌려주고 아무것도 저장하지 않는다 | SU-R20, SU-UC3 | backend | `application/test_setup_directory_test_cases.py::test_a_successful_test_returns_the_found_base_dn_and_saves_nothing`<br>`web/test_setup_directory_test_routes.py::test_a_successful_test_is_200_with_the_base_dn_and_stores_nothing` |
| SU-066 | 연결 테스트 확인이 단계별로 실패하면 200 실패 결과로 단계와 서버 문구만 알리고 저장하지 않는다 | SU-R20, SU-UC3 | backend | `application/test_setup_directory_test_cases.py::test_a_failed_check_is_a_failure_result_with_the_stage_message_only`<br>`web/test_setup_directory_test_routes.py::test_a_failed_check_is_200_with_the_stage_message_and_no_leak` |
| SU-067 | 저장된 AD 설정이나 고른 방식이 있어도 연결 테스트는 그것을 쓰거나 바꾸지 않는다 | SU-R20, SU-R1, SU-UC3 | backend | `application/test_setup_directory_test_cases.py::test_a_stored_directory_setting_is_neither_used_nor_changed`<br>`application/test_setup_directory_test_cases.py::test_a_chosen_local_mode_is_kept_when_testing`<br>`web/test_setup_directory_test_routes.py::test_a_stored_directory_or_chosen_mode_is_left_as_it_was` |
| SU-068 | 형식이 틀린 연결 테스트 입력은 422이고 AD를 부르지 않는다 | SU-R20, SU-UC3 | backend | `web/test_setup_directory_test_routes.py::test_a_malformed_test_body_is_422_without_calling_the_directory`<br>`web/test_setup_directory_test_routes.py::test_a_missing_bind_password_is_a_request_validation_error_for_the_test`<br>`web/test_setup_directory_test_routes.py::test_a_malformed_body_is_422_even_when_setup_is_closed` |
| SU-069 | 설정이 닫혔으면 연결 테스트는 409이고 AD를 부르지 않는다 | SU-R2, SU-R20, SU-UC7 | backend | `application/test_setup_directory_test_cases.py::test_a_closed_setup_is_409_and_never_calls_the_directory`<br>`web/test_setup_directory_test_routes.py::test_a_closed_setup_is_409_and_the_directory_is_not_called` |
| SU-070 | 연결 테스트는 로그인 없이 되고 바인드 비밀번호는 응답·로그에 나오지 않는다 | SU-R1, SU-R12, SU-R20 | backend | `web/test_setup_directory_test_routes.py::test_the_test_route_works_without_a_session_and_requires_the_csrf_header`<br>`web/test_setup_directory_test_routes.py::test_the_bind_password_never_appears_in_a_response_or_log` |
| SU-071 | openapi에 연결 테스트 경로와 요청·응답 모양이 문서화된다 | SU-R20 | backend | `web/test_setup_directory_test_routes.py::test_openapi_documents_the_directory_test_route_and_its_shapes` |
| SU-072 | HTTP 게이트웨이는 연결 테스트를 정해진 경로로 보내고 실패 결과를 확인 실패 오류로 바꾼다 | SU-R13, SU-UC3 | frontend | `gateway/http/setup.cases.test.ts > posts the seven inputs to the test path and resolves with the found base DN`<br>`gateway/http/setup.cases.test.ts > turns a 200 failure result into a directory-verification-failed error with its stage`<br>`gateway/http/setup.cases.test.ts > rejects with the server 409 message when the setup is closed` |
| SU-073 | AD 폼의 등록 버튼은 처음엔 꺼져 있고 연결 테스트에 성공하면 Base DN과 함께 켜진다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > keeps register disabled until the connection test succeeds and then shows the base DN` |
| SU-074 | 연결 테스트 성공 뒤 입력을 바꾸면 성공이 풀리고 등록이 다시 꺼진다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > invalidates the success when the input changes: %s`<br>`features/setup/SetupFlow.cases.test.tsx > only hides the notice when it is closed, keeping register enabled` |
| SU-075 | 연결 테스트가 실패하면 문구를 보이고 입력을 유지하며 등록은 꺼진 채다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > shows the %s stage message when the connection test fails and keeps register disabled`<br>`features/setup/SetupFlow.cases.test.tsx > shows the server message for %s and keeps register disabled`<br>`features/setup/SetupFlow.cases.test.tsx > clears an earlier success when a later test fails` |
| SU-076 | 연결 테스트·등록 요청 중에는 두 버튼이 모두 꺼진다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > disables both buttons while the connection test is pending and enables them on success`<br>`features/setup/SetupFlow.cases.test.tsx > disables both buttons while the registration is pending` |
| SU-077 | 연결 테스트에 성공하지 않았으면 Enter로 제출해도 요청이 없다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > sends no request when Enter is pressed before the connection test succeeded` |
| SU-078 | 연결 테스트 응답을 기다리는 동안 입력을 바꾸면 늦게 온 성공이 등록 버튼을 켜지 않는다 | SU-R17, SU-UC3 | frontend | `features/setup/SetupFlow.cases.test.tsx > ignores a late success of the previous input after the input changed` |
| SU-079 | AD 계정으로 확인된 첫 admin에는 AD의 전화번호가 있으면 저장된다 | SU-R11, SU-UC5 | backend | `application/test_setup_ad_admin_cases.py::test_the_first_ad_admin_gets_the_directory_phone` |

### SU-001 새 시스템은 방식 미선택이고 AD·저장 위치 단계가 필요하며 관리자 단계는 아직이다
- Given 사용자·방식·AD 설정·저장 위치가 하나도 없다
- When 진행 상태를 조회한다(`GET /auth/config`)
- Then 200이고 `auth_mode: null, needs_directory_setup: true, needs_storage_setup: true, needs_admin_setup: false`다

### SU-002 local을 고르면 AD 단계가 없어지고 저장 위치를 저장하면 관리자 단계만 남는다
- Given 새 시스템에서 방식 `local`을 골랐다(AD 설정은 없다)
- When 진행 상태를 조회하고, 저장 위치 `/data/files`를 저장한 뒤 다시 조회한다
- Then 처음은 `auth_mode: "local", needs_directory_setup: false, needs_storage_setup: true, needs_admin_setup: false`, 다음은 `needs_storage_setup: false, needs_admin_setup: true`다

### SU-003 ad 방식에서 AD 설정이 없으면 AD 단계가, AD·저장 위치가 있으면 관리자 단계만 남는다
- Given 방식 `ad`가 저장되어 있고 AD 설정이 없다
- When 진행 상태를 조회하고, AD 설정과 저장 위치를 저장한 뒤 다시 조회한다
- Then 처음은 `needs_directory_setup: true, needs_admin_setup: false`, 다음은 `needs_directory_setup: false, needs_storage_setup: false, needs_admin_setup: true`다

### SU-004 재직 admin이 있으면 설정 행이 없어도 진행 상태는 모두 끝남이다
- Given 재직 admin이 있고 AD 설정·저장 위치 행이 없다(로그아웃 상태)
- When 진행 상태를 조회한다
- Then `needs_directory_setup`·`needs_storage_setup`·`needs_admin_setup`이 모두 `false`이고 `auth_mode`는 `"ad"`다(`directory_login`은 `false`)

### SU-005 퇴사한 admin이나 admin이 아닌 사용자만 있으면 설정은 열려 있다
- Given 퇴사 처리된 admin 1명과 재직 `sales`·`user`만 있고 설정 행이 없다
- When 진행 상태를 조회하고 인증 방식 `local`을 고른다
- Then `needs_directory_setup: true, needs_storage_setup: true`이고 방식 선택은 204다

### SU-006 방식 행이 없는 기존 시스템은 ad이고 저장된 local은 남은 AD 설정보다 우선한다
- Given (가) 방식 행 없이 재직 admin만 있다 / (나) 방식 행·admin 없이 AD 설정 행만 있다 / (다) 방식 `local`이 저장되어 있고 AD 설정 행도 남아 있다
- When 각각 진행 상태를 조회한다
- Then (가)·(나)는 `auth_mode: "ad"`(나는 `needs_directory_setup: false`), (다)는 `auth_mode: "local"`이다

### SU-007 admin 전에는 인증 방식을 고르고 다시 바꿀 수 있다
- Given 재직 admin이 없다
- When `local`을 고르고 이어서 `ad`를 고른다
- Then 두 번 모두 204이고 저장된 방식은 `ad`다

### SU-008 local을 골라도 저장된 AD 설정은 지워지지 않는다
- Given admin 없이 AD 설정이 저장되어 있다
- When 인증 방식 `local`을 고른다
- Then 204이고 AD 설정 행은 그대로이며 유효 방식은 `local`이다

### SU-009 admin이 생긴 뒤 방식 선택은 409이고 방식은 그대로다
- Given 재직 admin이 있고 방식은 `ad`다
- When `local` 또는 `ad`를 고른다
- Then 409 `invalid-state`, `detail` "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"이고 방식은 `ad` 그대로다

### SU-010 알 수 없는 인증 방식은 422 request-validation이다
- When `{"mode":"oidc"}`, `{"mode":"AD"}`, `{}`, `{"mode":"local","x":1}`로 방식을 고른다
- Then 모두 422 `request-validation`이고 방식은 바뀌지 않는다

### SU-011 AD 서버를 등록하면 찾은 Base DN과 함께 저장되고 방식이 ad가 된다
- Given 새 시스템이고 AD가 Base DN `dc=found,dc=test`를 알려 준다
- When 호스트 `dc1.corp.test`, 포트 636, `ssl`, 바인드 계정, 바인드 비밀번호, 사용자 필터, 연결 제한 시간 5로 AD 서버를 등록한다
- Then 200이고 본문 키는 IN-R16의 11개뿐, `base_dn` = `dc=found,dc=test`, `revision` 1, `updated_by` null, `bind_credential_status` "ok"이며 바인드 비밀번호는 본문에 없다. AD는 Base DN 탐색만 1회 받았고 사용자 인증은 받지 않았다. 저장된 비밀번호는 암호화 값이고, 방식은 `ad`, 진행 상태는 `needs_directory_setup: false, needs_storage_setup: true`다

### SU-012 admin 전에는 AD 서버를 다시 저장해 덮어쓰고 local을 골랐어도 ad로 바뀐다
- Given AD 서버가 한 번 등록되었다(또는 방식 `local`을 골라 두었다)
- When 호스트 `dc2.corp.test`로 다시 등록하고 AD가 `dc=other,dc=test`를 알려 준다
- Then 200, `revision` 2(처음 등록이었다면 1), `host` `dc2.corp.test`, `base_dn` `dc=other,dc=test`이고 방식은 `ad`다

### SU-013 AD 확인이 단계별로 실패하면 422와 단계만 알리고 아무것도 저장하지 않는다
- Given AD 확인이 `connect`·`tls`(연결 불가) 또는 `service_bind`·`base_dn`(설정 오류) 단계에서 원인 문구 "internal-ldap-server-banner"와 함께 실패한다(단계 정보가 없는 실패 포함)
- When AD 서버를 등록한다
- Then 422 `directory-verification-failed`, 본문 `stage`는 그 단계(단계 없으면 `connect`)이고 `detail`은 2.8의 단계 문구이며 원인 문구·바인드 비밀번호는 응답에 없다. AD 설정·방식은 저장되지 않고, 앞서 저장한 AD 설정이 있었다면 그대로다

### SU-014 형식이 틀린 AD 서버 입력은 422이고 AD를 부르지 않는다
- When 다음 본문으로 AD 서버를 등록한다(각각): `host` 빈 값, `port` 0·`"636"`(문자열), `security` `"tls"`, `bind_password` 빈 값·NUL 포함, `bind_password` 누락·`null`, 폐지된 옛 필드(`server_urls`) 추가, `password`(현재 admin 비밀번호) 추가
- Then 칸 값 위반은 422 `invalid-value`(문구에 그 필드 이름), 타입·누락·`null`·옛 필드·모르는 필드·enum 위반은 422 `request-validation`이고, AD 확인은 0회이며 진행 상태는 그대로다(칸별 전체 경계값은 IN 케이스)

### SU-015 저장 위치를 등록하면 정규화한 경로가 저장되고 관리자 단계가 남는다
- Given AD 서버가 등록되었고 `<임시 폴더>/new/nested` 디렉터리는 아직 없다
- When 저장 위치 `"  //<임시 폴더>//new/./nested/  "`를 등록한다
- Then 200 `{path: "<임시 폴더>/new/nested", updated_at, updated_by: null}`이고, 디렉터리가 상위까지 만들어졌으며 확인용 파일은 남지 않았다. 진행 상태는 `needs_storage_setup: false, needs_admin_setup: true`다

### SU-016 admin 전에는 저장 위치를 덮어쓸 수 있고 실패한 덮어쓰기는 이전 경로를 남긴다
- Given 저장 위치 `/data/first`가 등록되었다
- When `/data/second`로 등록하고, 이어서 쓸 수 없는 위치로 등록한다
- Then 첫 요청은 200이고 저장값은 `/data/second`, 둘째 요청은 422 "해당 위치에 쓸 수 없습니다."이며 저장값은 `/data/second` 그대로다

### SU-017 방식 미선택이나 AD 방식의 AD 미등록이면 저장 위치는 경로 검사 전에 409다
- Given (가) 방식을 고르지 않았다 / (나) 방식 `ad`이고 AD 설정이 없다 / (다) 방식 `local`이고 AD 설정이 없다 / (라) 방식 행 없이 AD 설정만 있다
- When `/data/x`와 `relative`로 저장 위치를 등록한다
- Then (가)는 둘 다 409 "먼저 인증 방식을 고르세요.", (나)는 둘 다 409 "먼저 AD 서버를 등록하세요"이며 쓰기 확인은 일어나지 않는다. (다)·(라)는 `/data/x` 등록이 200이다

### SU-018 형식이 틀린 저장 경로는 422이고 디스크를 건드리지 않는다
- Given 저장 위치를 등록할 수 있는 상태다
- When 경로 `""`, `"data/files"`, `"/data/../etc"`, `"/" + "a"×1024`, `"/data/\u0000x"`로 등록한다
- Then 앞의 셋은 422 `invalid-value` "절대 경로를 입력하세요.", 1025자는 "저장 경로는 1024자 이내로 입력하세요.", NUL은 "저장 경로에는 NUL 문자를 쓸 수 없습니다"(IN-R23)이고 쓰기 확인은 0회, 저장값은 없다

### SU-019 쓸 수 없는 위치는 고정 문구의 422이고 저장되지 않는다
- Given 저장 위치를 등록할 수 있는 상태이고 쓰기 확인이 OS 오류("Permission denied: /secret")로 실패한다
- When 그 경로로 등록한다
- Then 422 `invalid-value` "해당 위치에 쓸 수 없습니다."이고 응답에 OS 오류·경로가 없으며 저장값은 없다

### SU-020 저장 위치 본문 형식이 틀리면 422 request-validation이다
- When `{}`, `{"path": 1}`, `{"path":"/x","extra":1}`로 저장 위치를 등록한다
- Then 모두 422 `request-validation`이고 저장값은 없다

### SU-021 쓰기 테스트는 204이고 저장하지 않으며 방식·AD 설정 없이도 된다
- Given 방식·AD 설정이 없다(또는 저장 위치 `/data/saved`가 이미 있다)
- When `/data/test`로 쓰기 테스트를 한다
- Then 204(본문 없음)이고 저장 위치는 저장되지 않았으며(이미 있던 경우 `/data/saved` 그대로), 진행 상태의 `needs_storage_setup`은 바뀌지 않는다

### SU-022 쓰기 테스트도 경로·쓰기 실패를 같은 문구의 422로 알린다
- When `relative`·`""`·`/x/../y`, 쓸 수 없는 위치로 쓰기 테스트를 한다
- Then 앞의 셋은 422 "절대 경로를 입력하세요.", 쓸 수 없는 위치는 422 "해당 위치에 쓸 수 없습니다."다

### SU-023 AD 계정으로 확인된 사람이 첫 admin이 되어 로그인된다
- Given AD 서버·저장 위치가 등록되었고 AD 계정 `kim`(표시 이름 "김관리", 메일 `kim@corp.test`)이 있다
- When `{login_id:"kim", password:<맞는 비밀번호>}`로 첫 admin을 등록한다
- Then 200 `{subject:"kim", name:"김관리", email:"kim@corp.test", role:"admin"}`와 세션 쿠키가 오고, `kim`은 admin이며 비밀번호 해시가 저장되었다. AD 인증은 저장된 설정(복호화한 바인드 비밀번호·Base DN)으로 1회이고, 진행 상태는 셋 다 `false`, `directory_login: true`, 그 계정·IP의 실패 횟수는 0이다

### SU-024 AD 비밀번호가 틀리면 401이고 아무도 등록되지 않으며 실패 1회가 남는다
- Given AD 서버·저장 위치가 등록되었고 AD 계정 `kim`이 있다
- When 틀린 비밀번호로(또는 AD에 없는 아이디로) 첫 admin을 등록한다
- Then 401 `unauthenticated` "아이디 또는 비밀번호가 올바르지 않습니다"이고 쿠키가 없으며 사용자·해시가 생기지 않고 `needs_admin_setup: true` 그대로이며 실패 1회가 남는다

### SU-025 AD 방식의 빈 비밀번호와 형식이 틀린 아이디는 AD에 보내지 않고 401이다
- Given AD 서버·저장 위치가 등록되었다
- When 비밀번호 `""`·`"   "`·`"pw\u0000x"`, 또는 아이디 `"bad id!"`로 첫 admin을 등록한다
- Then 모두 401 "아이디 또는 비밀번호가 올바르지 않습니다"이고 AD 호출은 0회다

### SU-026 AD 장애와 바인드 비밀번호 복호화 불가는 503이고 해시로 대신하지 않으며 실패로 세지 않는다
- Given AD 서버·저장 위치가 등록되었고 같은 아이디의 해시가 있더라도, AD 인증이 TLS 단계 장애(원인 "internal-ldap-server-banner")로 실패한다 / 저장된 바인드 비밀번호를 복호화할 수 없다
- When 첫 admin을 등록한다
- Then 503 `directory-unavailable` "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"이고 원인 문구가 없으며, 사용자는 등록되지 않고 실패 횟수는 늘지 않는다

### SU-027 첫 admin 등록이 5번 실패하면 올바른 비밀번호도 429이고 AD를 부르지 않는다
- Given AD 서버·저장 위치가 등록되었고 `kim`으로 틀린 비밀번호 등록이 5번 실패했다
- When 맞는 비밀번호로 `kim` 첫 admin을 등록한다
- Then 429 `too-many-attempts`이고 AD 호출은 늘지 않는다

### SU-028 AD 서버나 저장 위치가 없으면 첫 admin 등록은 409이고 AD를 부르지 않으며 실패로 세지 않는다
- Given (가) 방식·AD 설정이 없다 / (나) 저장 위치는 있고 AD 설정이 없다 / (다) AD 설정은 있고 저장 위치가 없다
- When AD 계정 `kim`으로 첫 admin을 등록한다
- Then (가)·(나)는 409 `invalid-state` "먼저 AD 서버를 등록하세요", (다)는 409 "파일 저장 위치를 먼저 설정하세요."이고 AD 호출 0회, 사용자 없음, 실패 횟수 0이다

### SU-029 같은 아이디의 재직 사용자가 있으면 첫 admin 등록은 409 already-exists이고 승격하지 않는다
- Given 재직 `sales` 사용자 `kim`이 있고(admin 없음) AD 서버·저장 위치가 등록되었으며 AD 계정 `kim`이 있다 / local 방식에 저장 위치가 있고 재직 사용자 `kim`이 있다
- When `kim`으로 첫 admin을 등록한다
- Then 409 `already-exists` "이미 존재하는 사용자입니다: kim"이고 `kim`의 역할은 `sales` 그대로이며 설정은 열린 채다

### SU-030 AD 방식에 이름·이메일·전화를 보내면 422이고 AD를 부르지 않는다
- Given AD 서버·저장 위치가 등록되었다
- When `display_name`·`email`·`phone` 중 하나를 넣어 첫 admin을 등록한다
- Then 422 `invalid-value` "AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다)."이고 AD 호출 0회다

### SU-031 해시 계산 중 인증 방식이 바뀌었으면 첫 admin 등록은 409이고 아무도 등록되지 않는다
- Given local 방식 등록에서 해시 계산 뒤 방식이 `ad`로 바뀌어 있다 / AD 방식 등록에서 AD 인증 뒤 방식이 `local`로 바뀌어 있다
- When 등록이 저장 단계에 이른다
- Then 각각 409 "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다." / "AD 연동 모드에서만 쓸 수 있습니다."이고 사용자·해시가 생기지 않는다

### SU-032 local 방식에서 입력한 아이디·비밀번호·이름으로 첫 admin이 만들어지고 로그인된다
- Given 방식 `local`, 저장 위치가 등록되었다
- When `{login_id:"boss", password:"Passw0rd-ok", display_name:"보스", email:"boss@corp.test", phone:"02-123-4567"}`로 첫 admin을 등록한다(또는 `email`·`phone` 없이)
- Then 200 `{subject:"boss", name:"보스", email:"boss@corp.test", role:"admin"}`와 세션 쿠키가 오고, 사용자 전화는 `02-123-4567`(생략하면 이메일·전화 null), 해시가 저장되며 AD 호출·시도 제한 기록은 없다. 진행 상태는 셋 다 `false`다

### SU-033 local 비밀번호가 8자 미만이거나 아이디와 같으면 password 칸 422이다(8자는 허용)
- Given 방식 `local`, 저장 위치가 등록되었다
- When 아이디 `boss`에 비밀번호 `"short7!"`(7자), `"  BOSS  "`(8자, 앞뒤 공백), `"Passw0rd"`(8자)로 각각 등록한다
- Then 7자는 422 `invalid-value` "비밀번호는 8자 이상이어야 합니다", `"  BOSS  "`는 "비밀번호는 아이디와 같을 수 없습니다"이고 둘 다 `errors` = `[{"location":["password"], …}]`이며 설정은 열린 채다. `"Passw0rd"`는 200이다

### SU-034 local 방식의 빈·공백·NUL 비밀번호는 401이 아니라 password 칸 422다
- Given 방식 `local`, 저장 위치가 등록되었다
- When 비밀번호 `""`·`"   "`·`"pw\u0000xxxxxx"`로 등록한다
- Then 422 `invalid-value`, `errors[0].location` = `["password"]`, 문구는 "비밀번호는 비어 있을 수 없습니다"(NUL은 "비밀번호에는 NUL 문자를 쓸 수 없습니다")다

### SU-035 local 이름이 없거나 길거나 이메일·전화 형식이 틀리면 422이고 설정은 열린 채다
- Given 방식 `local`, 저장 위치가 등록되었다
- When `display_name` 없음·`"   "`·201자, `email` `"not-mail"`, `phone` `"abc"`로 각각 등록한다
- Then 422 `invalid-value` "이름은(는) 비어 있을 수 없습니다" / "이름은(는) 200자를 넘을 수 없습니다" / "이메일 형식이 올바르지 않습니다." / "전화번호 형식이 올바르지 않습니다."이고 사용자가 생기지 않으며 `needs_admin_setup: true` 그대로다

### SU-036 local 아이디는 소문자로 맞추고 형식이 틀리면 422다
- Given 방식 `local`, 저장 위치가 등록되었다
- When 아이디 `" Boss "`로 등록하고, 다시 처음 상태에서 `"bad id!"`·`"-boss"`·65자 아이디로 등록한다
- Then 첫 등록 사용자의 아이디는 `boss`이고, 나머지는 422 `invalid-value` "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다"다

### SU-037 local 방식에서 저장 위치가 없으면 첫 admin 등록은 409이고 시도 제한을 쓰지 않는다
- Given 방식 `local`이고 저장 위치가 없다
- When 올바른 입력으로 첫 admin을 등록한다
- Then 409 `invalid-state` "파일 저장 위치를 먼저 설정하세요."이고 사용자가 없으며 시도 제한 기록이 없다

### SU-038 예약 아이디로는 두 방식 모두 첫 admin을 만들 수 없고 이후 일반 계정으로는 된다
- Given AD 방식(AD 서버·저장 위치 등록) 또는 local 방식(저장 위치 등록)이다
- When 아이디 `dev-admin`·`DEV-SALES`·`dev-user`로 첫 admin을 등록하고, 이어서 일반 계정 `kim`으로 등록한다
- Then 예약 아이디는 422 `invalid-value` "개발 로그인 전용 아이디는 등록할 수 없습니다: <정규화한 아이디>"(예: `dev-sales`)이고 AD 호출 0회·실패 횟수 0·설정은 열린 채다. `kim` 등록은 200이다. `dev-qa`는 예약 아이디가 아니다

### SU-039 재직 admin이 있으면 모든 최초 설정 경로가 409이고 AD를 부르지 않으며 바뀌는 것이 없다
- Given 재직 admin이 있다(최초 설정으로 만든 경우와, AD·저장 위치 설정 행이 지워진 경우 포함), 로그아웃 상태다
- When 올바른 AD 서버 등록, 저장 위치 등록(형식이 틀린 경로 포함), 쓰기 테스트(형식이 틀린 경로 포함), 첫 admin 등록(AD 계정 `mallory`, 또는 올바른 local 입력)을 각각 부른다
- Then 모두 409 `invalid-state` "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"이고 AD 확인·인증 호출이 없으며, AD 설정·저장 위치·사용자(`mallory` 없음)가 바뀌지 않고 진행 상태는 셋 다 `false`다

### SU-040 최초 설정 경로는 로그인 없이 쓸 수 있다
- Given 로그인하지 않았다(세션 쿠키 없음)
- When AD 서버 등록, 저장 위치 등록을 부른다
- Then 각각 200이고 요청 뒤에도 호출자는 익명이다(`/auth/me` 401)

### SU-041 첫 admin·바인드 비밀번호는 응답과 로그 어디에도 나오지 않는다
- Given 로그를 DEBUG까지 모으고 AD 서버·저장 위치가 등록되었다
- When 같은 비밀번호로 첫 admin 등록을 오답(401)·검증 오류(422)·성공(200)으로 보내고, 바인드 비밀번호로 AD 서버 등록(성공·확인 실패)을 보낸다
- Then 상태 코드는 순서대로 401·422·200이고, 어느 응답 본문과 로그에도 두 비밀번호가 없다

### SU-042 openapi에 최초 설정 경로와 요청 모양이 문서화된다
- When 앱의 openapi 문서를 만든다
- Then `PUT /auth/setup/auth-mode`·`/directory`·`/storage`, `POST /auth/setup/storage/test`·`/auth/setup`이 있고, `AuthModeRequest`의 속성은 `mode` 하나(`ad`·`local`), `SetupAdminRequest`의 `display_name`·`email`·`phone`은 required가 아니며, 저장 위치 두 경로의 응답 코드는 409·422를 포함한다

### SU-043 HTTP 게이트웨이는 진행 상태를 세 단계 완료 여부와 방식으로 바꾼다
- Given `/auth/config` 응답의 `needs_directory_setup`·`needs_storage_setup`·`needs_admin_setup`·`auth_mode`가 (t,t,f,ad), (t,f,f,ad), (f,t,f,ad), (f,f,t,ad), (f,f,f,ad), (t,t,f,null), (f,t,f,local), (f,f,f,local), `auth_mode` 키 없음 중 하나다
- When `setup.status()`를 부른다
- Then `GET /api/v1/auth/config`를 부르고 `directoryDone = !needs_directory_setup`, `storageDone = !needs_storage_setup`, `adminDone`은 셋 다 `false`일 때만 `true`, `authMode`는 응답 값(키가 없으면 `null`)이다. `auth.config().needsSetup`은 셋 중 하나라도 `true`면 `true`다

### SU-044 HTTP 게이트웨이는 각 단계를 정해진 경로·본문으로 보낸다
- When `chooseAuthMode('local')`, `saveDirectory(7칸 입력)`, `saveStorage('/var/lib/neoine-sales/files')`, `testStorage('/data/files')`, `registerAdmin('root','pw')`, `registerAdmin('boss','Passw0rd-ok',{name:'보스', email:'boss@corp.test', phone:'02-123-4567'})`, `registerAdmin('boss','Passw0rd-ok',{name:'보스', email:null, phone:null})`를 부른다
- Then 각각 `PUT /api/v1/auth/setup/auth-mode {mode:"local"}`(204 → undefined), `PUT …/setup/directory`에 snake_case 7키, `PUT …/setup/storage {path}`(→ undefined), `POST …/setup/storage/test {path}`(204 → undefined), `POST …/setup {login_id:"root", password:"pw"}`(→ `{id, loginId, name, role:"admin"}`), 프로필 3키 포함 본문, `{login_id, password, display_name}`만 있는 본문이다

### SU-045 HTTP 게이트웨이는 서버 거절을 상태·문구·단계 그대로 넘긴다
- Given 서버가 409 `invalid-state`("이미 관리자가…", "먼저 인증 방식을 고르세요.", "먼저 AD 서버를 등록하세요", "파일 저장 위치를 먼저 설정하세요."), 422 `invalid-value`("해당 위치에 쓸 수 없습니다.", "절대 경로를 입력하세요."), 422 `directory-verification-failed`(`stage: service_bind`)로 답한다
- When 해당 게이트웨이 함수를 부른다
- Then `ApiError`로 reject되고 상태·`kind`(`conflict`·`validation`·`directory-verification-failed`)·서버 문구, 확인 실패는 `stage`가 그대로다

### SU-046 최초 설정이 필요하면 로그인 화면과 보호 화면 방문은 /setup으로 간다
- Given 최초 설정이 끝나지 않았고 로그인하지 않았다
- When `/login`, `/deals`, `/admin/users`를 연다
- Then 주소가 `/setup`이 된다

### SU-047 설정이 끝난 시스템의 /setup은 로그인 화면으로 가고 상태를 못 읽으면 오류를 보인다
- Given (가) 최초 설정이 끝났고 로그인하지 않았다 / (나) admin으로 로그인했다 / (다) local로 설정이 끝났다 / (라) 진행 상태 조회가 401 "로그인이 필요합니다."로 실패한다
- When `/setup`을 연다
- Then (가)·(다)는 `/login`으로 가고 AD 폼이 보이지 않으며, (나)는 `/setup`에 머물지 않고, (라)는 "로그인이 필요합니다."가 `role="alert"`로 보인다

### SU-048 새 시스템의 /setup은 인증 방식 선택과 세 단계 표시로 시작한다
- Given 최초 설정이 처음 상태다
- When `/setup`을 연다
- Then 제목 "인증 방식"과 버튼 "AD 연동"·"앱에서 직접 관리"가 보이고, 단계 목록은 "1. 인증 방식"·"2. 파일 저장 위치"·"3. 관리자 등록"이며 1단계에 `aria-current="step"`, "저장 경로"·"AD 아이디" 칸은 없다

### SU-049 "앱에서 직접 관리"를 누르면 서버에 기록하고 AD 폼 없이 저장 위치 단계로 간다
- Given 인증 방식 선택 화면이다
- When "앱에서 직접 관리"를 누른다
- Then 방식 선택 요청이 `local`로 1회 가고, 제목 "파일 저장 위치"가 보이며 AD 서버 폼은 나오지 않는다. 1단계는 "완료"다

### SU-050 방식 선택이 거절되면 서버 문구를 보이고 선택 화면에 머문다
- Given 방식 선택 요청이 409 "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"(또는 다른 오류)로 실패한다
- When "앱에서 직접 관리"를 누른다
- Then 그 문구가 `role="alert"`로 보이고 제목 "인증 방식"에 머문다

### SU-051 "AD 연동"은 서버를 부르지 않고 기본값이 채워진 AD 폼을 열고 되돌아갈 수 있다
- Given 인증 방식 선택 화면이다
- When "AD 연동"을 누르고, 이어서 "인증 방식 다시 선택"을 누른다
- Then 방식 선택 요청 없이 제목 "AD 서버 등록"이 보이고 보안 연결 `ssl`, 포트 636, 사용자 검색 필터 `(&(objectClass=user)(sAMAccountName={login_id}))`, 연결 제한 시간 5, 바인드 비밀번호 빈 값이며 서버 URL·StartTLS·CA 인증서·바인드 템플릿·Base DN·속성·응답 제한 시간 칸은 없다. 되돌리면 제목 "인증 방식"이 보인다

### SU-052 연결 테스트에 성공한 AD 폼을 등록하면 7칸을 보내고 1단계 완료와 함께 저장 위치 단계로 간다
- Given AD 서버 등록 폼에 호스트 `dc1.corp.test`, 보안 연결 `starttls`(포트 389), 바인드 계정, 바인드 비밀번호, 필터, 제한 시간 5를 넣고 "연결 테스트"에 성공했다
- When "AD 서버 등록"을 누른다
- Then 테스트 요청과 저장 요청이 각각 1회, 둘 다 `{host, port: 389, security: "starttls", bindAccount, bindPassword, userFilter, connectTimeoutSeconds: 5}`로 가고, 제목 "파일 저장 위치"가 보이며 1단계는 "완료", 2단계가 현재 단계다

### SU-053 바인드 비밀번호가 비면 연결 테스트도 서버를 부르지 않고 입력을 요구한다
- Given AD 서버 등록 폼에서 바인드 비밀번호만 비웠다
- When "연결 테스트"를 누른다
- Then "바인드 비밀번호를 입력하세요"가 `role="alert"`로 보이고 테스트·저장 요청은 없으며, "AD 서버 등록"은 비활성인 채 폼에 머문다

### SU-054 연결 테스트 뒤 등록이 거절되면 문구를 보이고 입력을 유지하며 다시 테스트해야 등록할 수 있다
- Given AD 서버 등록 폼을 채워 "연결 테스트"에 성공했다
- When "AD 서버 등록"을 눌렀는데 서버가 422 `invalid-value`(호스트 오류)로 거절하거나, 422 `directory-verification-failed`(`stage` `connect`·`service_bind`·`base_dn`, `detail` "서버 문구")로 거절한다
- Then 앞의 경우 서버 문구가, 뒤의 경우 단계별 화면 문구(예: "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요.")가 `role="alert"`로 보이고, 바인드 계정·바인드 비밀번호 등 입력값이 그대로이며 제목 "AD 서버 등록"에 머문다. 성공 알림은 사라지고 "AD 서버 등록"은 비활성이며 안내 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다."가 보인다

### SU-055 화면 단계는 서버 진행 상태를 따른다
- Given (가) 방식 `ad`인데 AD 설정이 없다 / (나) AD 서버는 등록되었고 저장 위치가 없다 / (다) 저장 위치는 이미 있고 방식을 고르지 않았다
- When `/setup`을 연다(다는 "AD 연동"을 눌러 AD 서버를 저장하고, 이어서 "인증 방식 다시 선택"으로 돌아갔다가 다시 AD 서버를 저장한다)
- Then (가)는 곧바로 "AD 서버 등록", (나)는 곧바로 "파일 저장 위치"가 열리고, (다)는 처음부터 2단계가 "완료"이며 AD 서버를 저장하면 저장 위치를 묻지 않고 "관리자 등록"으로 간다(되돌아갔다 와도 같다)

### SU-056 저장 위치 단계는 안내를 보이고 잘못된 경로는 서버 문구로 거절하며 입력을 유지한다
- Given 저장 위치 단계다
- When 화면을 보고, `data/files`·빈 값·`/x/../y`·`/readonly/files`로 각각 "저장 위치 등록"을 누른다
- Then 안내 "예: /var/lib/neoine-sales/files"와 "위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다"가 보이고 "저장 경로"는 처음 빈 값이다. 앞의 셋은 "절대 경로를 입력하세요.", `/readonly/files`는 "해당 위치에 쓸 수 없습니다."가 `role="alert"`로 보이며 입력값이 그대로이고 제목 "파일 저장 위치"에 머문다

### SU-057 쓰기 테스트는 성공 알림만 보이고 저장하지 않으며 다시 하면 이전 결과를 지운다
- Given 저장 위치 단계에 경로를 넣었다
- When "쓰기 테스트"를 누르고(성공 또는 쓸 수 없는 위치), 이어서 다시 누른다
- Then 성공하면 "쓰기 테스트에 성공했습니다."가 보이고 저장 요청은 없으며 단계에 머문다. 실패하면 서버 문구("해당 위치에 쓸 수 없습니다.")가 보이고 입력이 그대로다. 다시 누르면 이전 알림·오류가 사라진 뒤 새 결과가 보인다

### SU-058 저장 위치를 등록해야 관리자 등록 단계가 열린다
- Given AD 서버를 저장해 저장 위치 단계에 있다
- When 화면을 보고, 이어서 `/data/neoine-sales/files`로 "저장 위치 등록"을 누른다
- Then 처음에는 "AD 아이디" 칸이 없고, 등록 뒤 제목 "관리자 등록"이 보이며 2단계는 "완료"다

### SU-059 "인증 방식 다시 선택"으로 선택 화면에 돌아가 AD로 바꿀 수 있다
- Given local을 골라(또는 AD 서버를 저장해) 저장 위치 단계에 있다 / local 관리자 등록 단계에 있다
- When "인증 방식 다시 선택"을 누르고 "AD 연동"으로 AD 서버(호스트 `dc2.corp.test`)를 저장한다
- Then 제목 "인증 방식"이 보였다가 "AD 서버 등록"을 거쳐 "파일 저장 위치"(저장 위치가 이미 있으면 "관리자 등록")로 간다

### SU-060 AD 방식 관리자 등록이 성공하면 그 admin으로 로그인되어 Deals로 간다
- Given AD 방식으로 1·2단계를 마쳐 관리자 등록 단계다
- When 화면을 보고, "AD 아이디" `boss`, "비밀번호" `secret`으로 "관리자 등록"을 누른다
- Then "처음 등록하는 AD 계정이 관리자가 됩니다."와 "AD 아이디"·"비밀번호"(`type=password`, `autocomplete=current-password`) 칸이 보이고, 등록하면 주소가 Deals 기본 목록이 되며 메뉴 "Admin"과 사용자 메뉴 "boss (admin)"이 보인다

### SU-061 관리자 등록이 거절되면 서버 문구를 보이고 비밀번호를 지운다
- Given AD 방식 관리자 등록 단계이고 등록 요청이 401 "아이디 또는 비밀번호가 올바르지 않습니다"(또는 409 `already-exists` "이미 존재하는 사용자입니다: kim")로 실패한다
- When `boss`·`secret`으로 "관리자 등록"을 누른다
- Then 그 문구가 `role="alert"`로 보이고 "비밀번호"는 빈 값, "AD 아이디"는 `boss` 그대로이며 제목 "관리자 등록"에 머문다

### SU-062 local 방식 관리자 등록은 프로필 칸을 받고 성공하면 그 admin으로 로그인된다
- Given local 방식으로 저장 위치까지 마쳐 관리자 등록 단계다
- When 화면을 보고, 아이디 `boss`, 비밀번호·확인 `Passw0rd-ok`, 이름 `보스`, 이메일 `boss@corp.test`, 전화 `02-123-4567`로 등록한다(또는 이메일·전화를 비운다)
- Then "아이디"·"비밀번호"(`new-password`)·"비밀번호 확인"·"이름"·"이메일"·"전화번호" 칸이 있고 "AD 아이디"는 없다. 등록 요청은 1회 `('boss','Passw0rd-ok',{name:'보스', email:'boss@corp.test', phone:'02-123-4567'})`(비우면 `email: null, phone: null`)이고 AD 서버 저장 요청은 없으며, Deals 기본 목록으로 가고 사용자 메뉴에 "보스 (admin)"이 보인다

### SU-063 local 방식에서 비밀번호가 비거나 확인과 다르면 서버를 부르지 않는다
- Given local 관리자 등록 단계에 아이디·이름을 넣었다
- When (가) 비밀번호·확인을 둘 다 비우고 / (나) 비밀번호만 비우고 확인에 `Passw0rd-ok`를 넣고 / (다) 확인을 `Passw0rd-no`로 넣고 "관리자 등록"을 누른다
- Then (가)는 "비밀번호를 입력하세요.", (나)·(다)는 "비밀번호 확인이 일치하지 않습니다."가 `role="alert"`로 보이고 등록 요청은 없으며 단계에 머문다

### SU-064 local 방식 서버 거절은 문구를 보이고 두 비밀번호 칸을 비우며 다른 입력은 유지한다
- Given local 관리자 등록 단계이고 서버가 422 "비밀번호는 8자 이상이어야 합니다"(`errors[password]`) 또는 "이름은(는) 비어 있을 수 없습니다"로 거절한다
- When 비밀번호 `short7!`(또는 이름 없이)로 등록한다
- Then 그 문구가 `role="alert"`로 보이고 "비밀번호"·"비밀번호 확인"은 빈 값, "아이디" `boss`·"이름"은 그대로이며 제목 "관리자 등록"에 머문다. 비밀번호 오류면 "비밀번호" 칸이 잘못된 칸으로 표시된다

### SU-065 연결 테스트가 성공하면 찾은 Base DN을 돌려주고 아무것도 저장하지 않는다
- Given 새 시스템이다(방식 미선택, AD 설정·저장 위치 없음). AD는 Base DN `dc=found,dc=test`를 알려 준다
- When 호스트 `dc1.corp.test`, 포트 636, `ssl`, 바인드 계정, 바인드 비밀번호, 사용자 필터, 연결 제한 시간 5로 AD 연결 테스트를 한다(`POST /auth/setup/directory/test`)
- Then 200 `{"success": true, "stage": null, "message": "AD 설정을 확인했습니다", "base_dn": "dc=found,dc=test"}`이다. AD는 Base DN 탐색만 1회 받았고 사용자 인증은 받지 않았다. AD 설정 행은 없고 방식은 미선택이며 진행 상태는 `auth_mode: null, needs_directory_setup: true, needs_storage_setup: true`다

### SU-066 연결 테스트 확인이 단계별로 실패하면 200 실패 결과로 단계와 서버 문구만 알리고 저장하지 않는다
- Given AD 확인이 `connect`·`tls`·`service_bind`·`base_dn` 단계에서 원인 문구 "internal-ldap-detail"로 실패한다(각각), 또는 단계 정보 없이 실패한다
- When AD 연결 테스트를 한다
- Then 200 `success: false`, `stage`는 그 단계(단계 정보가 없으면 `connect`), `message`는 2.8의 그 단계 서버 문구, `base_dn: null`이다. 응답에 "internal-ldap-detail"과 바인드 비밀번호가 없고, AD 설정·방식은 저장되지 않는다

### SU-067 저장된 AD 설정이나 고른 방식이 있어도 연결 테스트는 그것을 쓰거나 바꾸지 않는다
- Given (가) AD 서버(호스트 `dc1.corp.test`)가 revision 1로 등록되어 있다 / (나) 방식 `local`을 골라 두었다(AD 설정 없음)
- When 호스트 `dc2.corp.test`와 새 바인드 비밀번호로 AD 연결 테스트를 한다(확인 성공)
- Then 둘 다 200 `success: true`이고 AD는 `dc2.corp.test` 입력값으로 확인되었다. (가) 저장된 설정은 호스트 `dc1.corp.test`·revision 1·같은 암호문이고 방식은 `ad`다. (나) 방식은 `local`, AD 설정 행은 없고 `needs_directory_setup: false` 그대로다

### SU-068 형식이 틀린 연결 테스트 입력은 422이고 AD를 부르지 않는다
- When 다음 본문으로 AD 연결 테스트를 한다(각각): `host` 빈 값, `port` 0·`"636"`(문자열), `security` `"tls"`, `bind_password` 빈 값·NUL 포함, `bind_password` 누락·`null`, 폐지된 옛 필드(`server_urls`) 추가, `password`(현재 admin 비밀번호) 추가, `expected_revision` 추가
- Then 칸 값 위반은 422 `invalid-value`(문구에 그 필드 이름), 타입·누락·`null`·옛 필드·모르는 필드·enum 위반은 422 `request-validation`이고 AD 확인은 0회다(칸별 전체 경계값은 IN 케이스)

### SU-069 설정이 닫혔으면 연결 테스트는 409이고 AD를 부르지 않는다
- Given 재직 admin이 있다(AD 설정 행이 지워진 경우 포함), 로그아웃 상태다
- When 올바른 입력으로 AD 연결 테스트를 한다
- Then 409 `invalid-state` "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"이고 AD 확인 호출이 없다

### SU-070 연결 테스트는 로그인 없이 되고 바인드 비밀번호는 응답·로그에 나오지 않는다
- Given 로그인하지 않았다(세션 쿠키 없음), 로그를 DEBUG까지 모은다
- When 바인드 비밀번호를 넣어 AD 연결 테스트를 성공·확인 실패로 각각 보낸다
- Then 둘 다 200이고 요청 뒤에도 호출자는 익명이다(`/auth/me` 401). 어느 응답 본문과 로그에도 바인드 비밀번호가 없다. CSRF 헤더가 없으면 403 `csrf`다(PL-R9)

### SU-071 openapi에 연결 테스트 경로와 요청·응답 모양이 문서화된다
- When 앱의 openapi 문서를 만든다
- Then `/api/v1/auth/setup/directory/test`에는 `post`만 있고, 요청 스키마는 `DirectorySettingsRequest`(7칸, `bind_password` required·`format: password`·`writeOnly`), 200 응답은 `DirectoryTestResultResponse`(`success`·`stage`·`message`·`base_dn`), 문서화된 오류 코드는 409·422다

### SU-072 HTTP 게이트웨이는 연결 테스트를 정해진 경로로 보내고 실패 결과를 확인 실패 오류로 바꾼다
- Given 서버가 (가) 200 `{success: true, stage: null, message: "AD 설정을 확인했습니다", base_dn: "dc=found,dc=test"}` / (나) 200 `{success: false, stage: "service_bind", message: "서버 문구", base_dn: null}` / (다) 409 `invalid-state` "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"로 답한다
- When `setup.testDirectory(7칸 입력)`을 부른다
- Then 요청은 `POST /api/v1/auth/setup/directory/test`에 `saveDirectory`와 같은 snake_case 7키다. (가)는 `{baseDn: "dc=found,dc=test"}`로 resolve, (나)는 `ApiError` 422 kind `directory-verification-failed`·문구 "서버 문구"·`stage` `service_bind`로 reject, (다)는 `ApiError` 409 kind `conflict`·서버 문구로 reject된다

### SU-073 AD 폼의 등록 버튼은 처음엔 꺼져 있고 연결 테스트에 성공하면 Base DN과 함께 켜진다
- Given "AD 연동"으로 AD 서버 등록 폼을 열고 호스트·바인드 계정·바인드 비밀번호를 넣었다(Fake는 Base DN `dc=found,dc=test`를 돌려준다)
- When "연결 테스트"를 누른다
- Then 누르기 전에는 "AD 서버 등록"이 비활성이고 안내 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다."가 보인다. 누른 뒤에는 테스트 요청이 입력 7칸으로 1회 가고 저장 요청은 없으며, "연결 테스트에 성공했습니다. Base DN: dc=found,dc=test"가 보이고 안내가 사라지며 "AD 서버 등록"이 활성이다. 제목 "AD 서버 등록"에 머물고 바인드 비밀번호 칸 값은 그대로다

### SU-074 연결 테스트 성공 뒤 입력을 바꾸면 성공이 풀리고 등록이 다시 꺼진다
- Given AD 서버 등록 폼을 채워 "연결 테스트"에 성공했다
- When (가) 호스트에 한 글자를 더한다 / (나) 보안 연결을 `starttls`로 바꾼다(포트 자동 변경) / (다) 바인드 비밀번호를 바꾼다 / (라) 호스트에 한 글자를 더했다가 지워 원래 값으로 되돌린다 / (마) 성공 알림의 닫기를 누른다
- Then (가)~(라)는 성공 알림이 사라지고 "AD 서버 등록"이 비활성이며 안내 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다."가 다시 보인다. 이어서 다시 "연결 테스트"에 성공하면 등록이 활성이 된다. (마)는 알림만 사라지고 "AD 서버 등록"은 활성이다

### SU-075 연결 테스트가 실패하면 문구를 보이고 입력을 유지하며 등록은 꺼진 채다
- Given AD 서버 등록 폼을 채웠다(또는 한 번 성공한 뒤 호스트를 바꿨다). 테스트가 (가) 확인 실패(`stage` `connect`·`tls`·`service_bind`·`base_dn`) / (나) 422 `invalid-value`(호스트 오류) / (다) 409 "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"로 실패한다
- When "연결 테스트"를 누른다
- Then (가)는 단계별 화면 문구(예: `connect` "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요."), (나)·(다)는 서버 문구가 `role="alert"`로 보인다. 입력값(바인드 비밀번호 포함)이 그대로이고 성공 알림은 없으며 "AD 서버 등록"은 비활성이고 저장 요청은 없다

### SU-076 연결 테스트·등록 요청 중에는 두 버튼이 모두 꺼진다
- Given AD 서버 등록 폼을 채웠고, (가) 테스트 응답을 / (나) 테스트 성공 뒤 등록 응답을 Fake가 아직 돌려주지 않는다
- When (가) "연결 테스트"를 / (나) "AD 서버 등록"을 누른다
- Then 응답이 오기 전까지 "연결 테스트"와 "AD 서버 등록"이 모두 비활성이다. (가)의 응답이 성공으로 오면 두 버튼이 모두 활성이 된다

### SU-077 연결 테스트에 성공하지 않았으면 Enter로 제출해도 요청이 없다
- Given AD 서버 등록 폼을 모두 채웠고 연결 테스트는 하지 않았다
- When 호스트 칸에서 Enter를 누른다
- Then 테스트·저장 요청이 없고 제목 "AD 서버 등록"에 머문다

### SU-078 연결 테스트 응답을 기다리는 동안 입력을 바꾸면 늦게 온 성공이 등록 버튼을 켜지 않는다
- Given "AD 서버 등록" 폼에 7칸을 채우고 "연결 테스트"를 눌러 서버 응답이 늦다
- When 응답이 오기 전에 입력 칸 하나(예: 호스트)를 바꾸고, 그 뒤 예전 입력에 대한 성공 응답이 도착한다
- Then 성공 알림과 Base DN이 보이지 않고 "AD 서버 등록"은 꺼진 채이며 "연결 테스트에 성공해야 AD 서버를 등록할 수 있습니다." 안내가 보인다. 바뀐 입력으로 "연결 테스트"를 다시 눌러 성공해야 등록이 켜진다

### SU-079 AD 계정으로 확인된 첫 admin에는 AD의 전화번호가 있으면 저장된다
- Given AD 서버·저장 위치가 등록된 새 시스템이고, 경우마다 AD 계정 `kim`(mobile 없음, telephoneNumber "02-123-4567") 또는 `lee`(두 속성 모두 없음)가 있다
- When 경우마다 `{login_id, password:<맞는 비밀번호>}`로 첫 admin을 등록한다
- Then 둘 다 200이고 kim 행의 전화는 "02-123-4567", lee 행의 전화는 비어 있다(null)

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(초안): 구현된 최초 설정 동작을 정본 명세로 옮김. 규칙 SU-R1~R19, use case SU-UC1~UC7, BDD 케이스 SU-001~SU-064. AD 칸 값·Base DN·암호화·경로·쓰기 확인 규칙은 IN 번호로 가리킴. Fake 게이트웨이와 서버가 다른 곳(AD 방식 기존 사용자 승격, 빈 아이디·비밀번호 문구, 중복·이름·비밀번호 문구)은 서버 기준으로 적고 확인 필요 질문으로 남김 | SU-001~SU-064(신규) |
| 2026-11-13 | US 변경(users 등록자 컬럼 삭제, 2026-11-13 사용자 확인)에 맞춰 첫 admin의 `created_by` = 자기 자신 문구 삭제(데이터 모델 표·SU 규칙·SU-023). 동작은 등록자 기록이 없어지는 것 외 불변 | 변경: SU-023 |
| 2026-11-23 | AD 서버 등록 전 연결 테스트(사용자 요청 2026-11-23, 확정 2026-11-23 사용자 확인: 최초 설정만 적용·호출 횟수 제한 없음): 새 공개 경로 `POST /auth/setup/directory/test`(저장 없음, Base DN 탐색까지, 결과는 IN-R18과 같은 200 `success` 모양) 규칙 SU-R20 추가, AD 폼은 연결 테스트 성공 뒤 입력이 그대로일 때만 등록 활성(SU-R17 교체, 공용 칸 참조를 IN-R30으로 정정), SU-R2·R12·R13·2.5·2.6·2.8·SU-UC3 갱신. 서버 PUT 규칙(SU-R6)은 불변 | 신규: SU-065~SU-077. 변경: SU-052·SU-053·SU-054. 절차 영향(테스트 코드만, 등록 전에 연결 테스트): SU-055·SU-059. 경로 목록 영향 확인: SU-042 |
| 2026-11-24 | 확정(2026-11-24 사용자 확인): AD 첫 admin 등록 때 AD 전화번호(AU-R8a)가 있으면 저장(사용자 결정 2026-11-24). 2.2 users 행·SU-R11 하위 항목 변경. AD 방식에 프로필 필드를 보내면 422인 규칙은 그대로 | 신규 SU-079 |
