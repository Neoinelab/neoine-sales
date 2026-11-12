# 연동 설정(AD 서버·저장 위치)   (feature 코드: IN, 상태: 확정(2026-11-09 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/domain/directory/{settings,rules,host,errors}.py`, `domain/storage/{path,settings}.py`, `domain/auth/credentials.py`의 `Password`, `application/directory/{get_settings,test_settings,update_settings,verify_settings,credentials,errors}.py`, `application/storage/{get_settings,test_settings,update_settings,probe}.py`, `application/auth/mode.py`, `application/ports/{directory,secret_cipher,file_storage}.py`, `web/routers/settings_{directory,storage}.py`, `web/schemas/{settings_directory,auth_directory,storage}.py`, `web/error_handlers.py`, `infra/db/{directory,storage}_settings_repository.py`, `infra/storage/_io.py`, `frontend/src/features/admin/integrations/**`, `shared/directory/**`, `gateway/http/{settings.ts,mappers/settings.ts}`, `data/settings.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 테스트·Fake가 어긋나는 곳은 계획 `artifacts/10-analysis/in-plan.md`의 확인 필요 질문으로 남겼고, 이 문서는 서버 코드를 따릅니다.

## 1. 개요

- 목적: admin이 로그인에 쓰는 AD(LDAP) 서버 접속 설정과, 첨부 파일을 두는 서버 저장 위치를 확인하고 바꾼다. AD 설정은 저장 전에 실제 AD로 확인하고(Base DN 자동 탐색 + 요청 admin 인증), 바인드 비밀번호는 암호화해 저장하고 어떤 응답에도 내보내지 않는다.
- 사용자(역할): `admin`만. `sales`·`user`·미인증은 쓸 수 없다.
- 범위
  - AD 설정 조회·연결 테스트·저장(처음 등록 포함), 접속 정보 7칸의 값 규칙, 바인드 비밀번호 유지·재입력 규칙, Base DN 자동 탐색, 현재 admin 비밀번호 확인과 시도 제한 연계, revision 낙관적 잠금, 바인드 비밀번호 암호화 저장·응답 마스크, local 모드 거부
  - 저장 위치 조회·쓰기 테스트·변경, 경로 값 규칙(`StoragePath`)과 쓰기 확인
  - 화면 Admin > 외부연동(`/admin/integrations`)의 AD 섹션·저장 위치 섹션, AD 입력 칸 공용 컴포넌트(`DirectoryFields`·`directoryForm`)와 AD 오류 문구(`shared/directory/messages.ts`)
- 범위 밖(다른 feature)
  - 최초 설정 마법사의 AD 단계·저장 위치 단계(`/auth/setup/directory`·`/auth/setup/storage*`)와 인증 방식 선택 → SU. 단 SU는 이 문서의 값 규칙(IN-R2~IN-R8, IN-R11, IN-R12, IN-R23, IN-R24)과 공용 입력 칸(IN-R31)을 가리킨다
  - 로그인(search-then-bind)·대체 로그인·admin AD 경고 팝업·시도 제한의 횟수·잠금 시간·문구·`/auth/config` 응답 → AU. 인증 방식(`ad`/`local`) 판정 → SU·AU
  - 첨부 업로드·다운로드와 저장 위치가 없을 때의 503 `storage-unavailable` → AT·LC
  - 암호화 키 설정(`APP_SETTINGS_ENCRYPTION_KEY` 필수·형식) → PL-R25·PL-R26
  - 판정 순서·CSRF·오류 형식 공통 → PL-R4·PL-R9·PL-R10
  - 경쟁·동시성 테스트(사용자 제시 없음)
- 관련 화면·메뉴: Admin 서브 메뉴 "외부연동"(`/admin/integrations`, PL-R35). 화면 제목(h2) "외부연동"

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| AD 설정 | `directory_settings`의 단일 행(id=1). 접속 정보 + 암호화된 바인드 비밀번호 + Base DN + revision |
| 접속 정보 | 호스트(`host`)·포트(`port`)·보안 연결(`security`)·바인드 계정(`bind_account`)·사용자 필터(`user_filter`)·연결 제한 시간(`connect_timeout_seconds`) |
| 입력 칸 7개 | 접속 정보 6개 + 바인드 비밀번호(`bind_password`) |
| 엔드포인트·계정 | 접속 정보 중 `host`·`port`·`security`·`bind_account` 네 값. 바인드 비밀번호 유지 여부를 판단한다 |
| 바인드 계정 | AD를 검색할 서비스 계정(DN·UPN·`DOMAIN\name` 형식 모두 텍스트로 받음) |
| 현재 admin 비밀번호 | 요청한 admin 본인의 AD 비밀번호(`password`). 새 설정으로 이 admin이 인증되는지 확인하는 데만 쓰고 저장하지 않는다 |
| Base DN | AD RootDSE의 `defaultNamingContext`. 입력받지 않고 저장·테스트 때 서비스 계정으로 찾는다 |
| 확인(verify) | 후보 설정으로 Base DN 탐색 → 현재 admin 검색·바인드 순서로 실제 AD에 묻는 일 |
| 단계(stage) | 확인이 실패한 곳: `connect`·`tls`·`service_bind`·`base_dn`·`search`·`bind` |
| revision | AD 설정 버전. 처음 1, 저장할 때마다 +1. 화면은 "설정 버전" |
| 마스크 | 화면이 저장된 바인드 비밀번호 자리에 보이는 고정 문자열 `********` |
| local 모드 | 인증 방식이 '앱에서 직접 관리'(`local`)인 시스템(판정은 SU·AU) |
| 저장 위치 | `storage_settings` 단일 행(id=1)의 서버 절대 경로 |
| 쓰기 확인 | 경로(없으면 상위까지 생성)에 확인용 파일을 썼다 지워 쓸 수 있는지 보는 일 |

### 2.2 데이터 모델

`directory_settings`(단일 행)

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | smallint PK | CHECK `id = 1` | 단일 행 |
| revision | integer | CHECK `revision >= 1` | 낙관적 잠금 |
| host | varchar(253) | | 정규화된 호스트(IN-R2) |
| port | integer | CHECK 1~65535 | |
| security | varchar(16) | CHECK `none`·`ssl`·`starttls` | |
| bind_account | varchar(256) | | |
| bind_password_encrypted | text | | 바인드 비밀번호의 암호문 토큰(IN-R15). 평문 컬럼 없음 |
| base_dn | varchar(512) | | 찾은 Base DN |
| user_filter | varchar(512) | | |
| connect_timeout_seconds | smallint | CHECK 1~30 | |
| updated_at | timestamptz | | 마지막 저장 시각(서버 시계) |
| updated_by_user_id | bigint NULL | FK `users.id` RESTRICT, 인덱스 | 마지막 저장 admin. 최초 설정(SU)으로 만든 행은 NULL |

`storage_settings`(단일 행)

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | smallint PK | CHECK `id = 1` | 단일 행 |
| path | varchar(1024) | | 정규화된 절대 경로 |
| updated_at | timestamptz | | |
| updated_by_user_id | bigint NULL | FK `users.id` RESTRICT, 인덱스 | 최초 설정으로 저장했으면 NULL |

- 도메인: `SecurityMode`(`none`·`ssl`·`starttls`), `DirectoryConnection`(생성 시 전 필드 검증), `DirectorySettings`(접속 정보 + `Password`, repr에 비밀번호 없음), `DirectorySettingsDraft`(바인드 비밀번호 `None` = 유지 요청), `StoredDirectorySettings`(`sealed_bind_password: SealedSecret` 등), `StoragePath`(정규화된 경로 값 객체), `StoredStorageSettings`.
- 고정 값(입력 아님): 수신 제한 시간 10초, 표시 이름 속성 `displayName`, 메일 속성 `mail`.
- Port: `DirectoryAuthenticator.discover_base_dn(settings)`·`authenticate(settings, base_dn, login_id, password)`, `SecretCipher.seal`·`unseal`(풀 수 없으면 `SecretDecryptionError`), `FileStorage.check_writable(root)`, `DirectorySettingsRepository.get`·`save(..., expected_revision, updated_by, now)`, `StorageSettingsRepository.get`·`save(path, updated_by, now)`.
- 마이그레이션 없음(두 테이블은 기준선 리비전에 있음, SC).

### 2.3 비즈니스 규칙

AD 접속 정보 값 규칙(SU의 AD 단계도 같은 규칙)
- **IN-R1** AD 설정은 시스템에 하나다. 입력은 7칸(`host`, `port`, `security`, `bind_account`, `bind_password`, `user_filter`, `connect_timeout_seconds`)이고 `connect_timeout_seconds`를 생략하면 5다. Base DN·서버 URL 목록·바인드 템플릿·속성 이름·수신 제한 시간·CA 인증서는 입력이 아니다.
- **IN-R2** `host`는 호스트 이름·IPv4·IPv6 리터럴 하나이며 소문자로 맞춰 저장한다(앞뒤 공백은 지우지 않는다). 호스트 이름은 1~253자이고 점으로 나눈 각 조각이 `[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?`여야 한다. 조각이 모두 숫자면 IPv4로 읽고, `:`가 있으면 대괄호 없는 IPv6로 읽어 표준 표기로 바꾼다. scheme(`ldaps://`)·포트(`:636`)·경로가 붙은 값은 거절한다. 문구는 `host: ` 뒤에 "호스트는 1~253자여야 합니다" / "호스트 이름 형식이 올바르지 않습니다(주소·포트·경로 없이 이름만 입력)" / "IPv4 주소 형식이 올바르지 않습니다" / "IPv6 주소 형식이 올바르지 않습니다(대괄호 없이 입력)".
- **IN-R3** `port`는 1~65535 정수("port은(는) 1~65535 사이여야 합니다"). `security`는 `none`(평문 LDAP)·`ssl`(LDAPS)·`starttls` 셋 중 하나다. 기본 포트는 `none` 389, `ssl` 636, `starttls` 389이며 화면이 쓴다(서버는 포트를 바꾸지 않는다).
- **IN-R4** `bind_account`는 1~256자, 제어문자 없음("bind_account은(는) 비어 있을 수 없습니다" / "bind_account은(는) 256자를 넘을 수 없습니다" / "bind_account에는 제어문자를 쓸 수 없습니다").
- **IN-R5** `user_filter`는 1~512자, 제어문자 없음, `{login_id}`가 정확히 한 번 있고 그 밖의 중괄호가 없으며("user_filter에는 {login_id}가 정확히 한 번 있어야 하고 다른 중괄호는 쓸 수 없습니다"), `(`로 시작해 바깥 괄호가 맨 끝에서 닫히고 짝이 맞아야 한다("user_filter은(는) 괄호로 감싸야 하고 괄호 짝이 맞아야 합니다").
- **IN-R6** `connect_timeout_seconds`는 1~30 정수("connect_timeout_seconds은(는) 1~30 사이여야 합니다").
- **IN-R7** 값 규칙(IN-R2~IN-R6, IN-R8) 위반은 422 `invalid-value`이고 문구에 영문 필드 이름이 들어간다. 요청 형식 위반은 422 `request-validation`이다: 모르는 필드·폐지된 필드(`base_dn`, `server_urls`, `bind_template`, `ca_pem` 등), 필수 필드 누락, `port`·`connect_timeout_seconds`가 JSON 정수가 아님(문자열 `"636"`·실수·불리언 거절), `security`가 셋 밖, `expected_revision`이 1 미만·정수 아님. 값 위반이 있으면 AD를 부르지 않고 아무것도 저장하지 않는다.

바인드 비밀번호
- **IN-R8** 바인드 비밀번호 값은 `Password` 규칙을 따르고 앞뒤 공백을 지우지 않는다: NUL 없음, 공백만이 아님, 256자 이하. 위반 문구는 `bind_password: ` 뒤에 "비밀번호에는 NUL 문자를 쓸 수 없습니다" / "비밀번호는 비어 있을 수 없습니다" / "비밀번호는 256자를 넘을 수 없습니다". 빈 문자열은 '유지'가 아니라 값 위반이다.
- **IN-R9** 저장·연결 테스트에서 `bind_password`를 생략하거나 `null`로 보내면 '저장된 값 유지' 요청이다. 유지는 다음을 모두 만족할 때만 되고, 아니면 AD를 부르기 전에 422 `invalid-value`다: ① 저장된 설정이 있다(없으면 "bind_password: 바인드 비밀번호를 입력하세요") ② 엔드포인트·계정(정규화한 `host`, `port`, `security`, `bind_account`)이 저장 값과 모두 같다(아니면 "bind_password: 서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다") ③ 저장된 비밀번호를 풀 수 있다(아니면 "bind_password: 저장된 비밀번호를 읽을 수 없습니다. 다시 입력하세요"). `user_filter`·`connect_timeout_seconds`만 바꾸면 유지된다. 새 비밀번호를 보내면 저장 값을 읽을 수 없어도 그 값을 쓴다.

현재 admin 비밀번호와 확인
- **IN-R10** 저장·연결 테스트는 현재 admin 비밀번호(`password`)가 필요하다. 없거나 `null`이면 Base DN 탐색 전에 422 `invalid-value` "AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다"다. 값은 `Password` 규칙(IN-R8과 같은 문구, 접두어 없음)을 따르고 위반은 AD를 부르지 않고 422 `invalid-value`다. 예외 계정(예전 개발용 아이디 포함) 없이 모든 admin에게 같다.
- **IN-R11** 확인은 후보 설정(IN-R9로 완성한 바인드 비밀번호 포함)으로 다음 순서를 한다: ① 연결(+TLS) → 서비스 계정 바인드 → RootDSE `defaultNamingContext`로 Base DN 찾기 ② 요청 admin의 로그인 아이디로 사용자 검색(`user_filter`) → 찾은 DN과 현재 admin 비밀번호로 바인드(search-then-bind). ①이 실패하면 ②를 하지 않는다. 실패 단계와 서버 문구는 2.8 표이며, AD 원인 문구·주소·비밀번호는 응답에 싣지 않는다. 서버 인증서는 검증하지 않는다(`ssl`·`starttls`도 암호화만, `none`은 평문 — 받아들인 위험).
- **IN-R12** Base DN은 입력받지 않는다. 저장 때 찾은 값을 함께 저장하고(1~512자, 제어문자 없음), 테스트 때는 찾은 값을 결과로 돌려주기만 한다. 저장된 Base DN은 다음 로그인에 그대로 쓰이고 로그인 때 다시 찾지 않는다(AU).
- **IN-R13** 현재 admin 바인드는 로그인 시도 제한(AU)과 같은 계정+IP 카운터를 쓴다: 바인드 전에 한도를 확인해 잠겨 있으면 429 `too-many-attempts`이고 admin 바인드를 하지 않는다(Base DN 탐색은 이미 했을 수 있다). 비밀번호 거절·검색 0건(`InvalidCredentialsError`)은 실패 1회로 남고, 연결·TLS 등 통신 실패와 성공은 횟수를 남기지 않는다. Base DN 탐색 실패는 카운터에 영향이 없다.

저장(PUT)
- **IN-R14** 저장 요청은 `expected_revision` 키가 필수다. `null`은 '설정이 없을 때 새로 만들기'이고 설정이 이미 있으면 409 `invalid-state`, 정수는 '그 버전 고치기'이고 설정이 없으면 404 `not-found`, 저장된 revision과 다르면 409 `invalid-state`다(409 문구 "설정이 다른 곳에서 바뀌었습니다. 새로고침 후 다시 시도하세요"). 이 확인은 AD를 부르기 전에 하고, 저장 순간에 한 번 더 한다(그 사이 바뀌었으면 같은 409). 확인(IN-R11)이 성공해야 저장하며 실패하면 422 `directory-verification-failed`(+`stage`)이고 기존 설정은 그대로(새로 만드는 경우 행이 생기지 않음)다. 저장하면 접속 정보·암호문·찾은 Base DN을 쓰고 revision은 새로 만들면 1, 고치면 +1, `updated_by` = 요청 admin, `updated_at` = 서버 시계다. 응답은 저장 결과(IN-R16)이며 이후 GET과 같다.
- **IN-R15** 바인드 비밀번호는 `SecretCipher`(Fernet, 키 `APP_SETTINGS_ENCRYPTION_KEY`, PL-R25)로 암호화한 토큰만 저장한다. 새 비밀번호로 저장하면 토큰이 새 값으로 바뀌고, 유지하면 저장된 값을 풀어 다시 암호화해 저장한다(풀었을 때 같은 비밀번호). 평문 비밀번호·현재 admin 비밀번호는 어떤 테이블·응답(성공·오류)·로그에도 남지 않고, 암호문도 응답·로그에 나오지 않는다. 저장된 토큰을 풀 수 없으면(키 변경·손상) 로그에 값 없는 경고만 남긴다.
- **IN-R16** AD 설정 응답(`DirectorySettingsResponse`)은 `host`, `port`, `security`, `bind_account`, `bind_credential_status`, `user_filter`, `connect_timeout_seconds`, `base_dn`, `revision`, `updated_at`(서버 오프셋, TM-R8), `updated_by`(UserRef 또는 null)만 가진다. 비밀번호·암호문 필드는 어떤 형태로도 없다. `bind_credential_status`는 저장된 비밀번호를 풀 수 있으면 `ok`, 없으면 `unreadable`이다.
- **IN-R17** AD 설정 저장은 이미 열린 세션(요청 admin·다른 사용자)을 끊지 않는다. 저장 직후 `/auth/config`의 `directory_login`은 true이고(AU), 다음 AD 로그인은 저장된 접속 정보·Base DN·비밀번호를 쓴다.

연결 테스트(POST /test)
- **IN-R18** 연결 테스트는 저장하지 않는다(저장된 행·revision·암호문이 그대로). 확인이 성공하면 200 `{"success": true, "stage": null, "message": "AD 설정을 확인했습니다", "base_dn": <찾은 값>}`, 확인이 실패하면 오류가 아니라 200 `{"success": false, "stage": <단계>, "message": <2.8 서버 문구>, "base_dn": null}`이다. 값 위반·유지 불가·비밀번호 없음(422), 시도 제한(429), local 모드(409)는 결과가 아니라 오류 응답이다. 요청에 `expected_revision`은 없다(보내면 422 `request-validation`).

조회(GET)
- **IN-R19** 저장된 AD 설정이 없으면 GET은 404 `not-found` "AD 설정을(를) 찾을 수 없습니다: directory"다.

local 모드
- **IN-R20** local 모드에서는 AD 설정 저장·연결 테스트가 409 `invalid-state` "AD 연동 모드에서만 쓸 수 있습니다."이고 AD를 부르지 않으며 남아 있는 행도 바뀌지 않는다. 이 검사는 요청 형식·값 검사(IN-R7·IN-R8) 뒤, revision 확인(IN-R14) 앞이다. GET은 막지 않는다(설정이 없으면 IN-R19의 404). 저장 위치는 모드와 무관하게 쓸 수 있다(IN-R27).

OpenAPI 계약
- **IN-R21** 계약: `/api/v1/settings/directory`는 GET·PUT, `/directory/test`는 POST만 공개한다. 저장 요청 속성은 입력 7칸 + `password` + `expected_revision`(required에 `expected_revision`, `bind_password`는 required 아님), 테스트 요청은 입력 7칸 + `password`(`expected_revision` 없음). `bind_password`·`password`는 `format: password`·`writeOnly: true`다. 테스트 결과 스키마는 `success`·`stage`·`message`·`base_dn` 넷이다. 응답 스키마는 IN-R16이고 `bind_credential_status` enum은 `ok`·`unreadable`이다. 문서화된 오류: GET 404, PUT·test 404·409·422·429(+ PL-R21의 401·403).

저장 위치
- **IN-R22** 저장 위치는 시스템에 하나다(`path`, `updated_at`, `updated_by`). 최초 설정(SU)으로 저장한 행의 `updated_by`는 null이다. 응답(`StorageSettingsResponse`)은 `path`·`updated_at`(서버 오프셋)·`updated_by`(UserRef 또는 null) 셋이다.
- **IN-R23** 경로 값 규칙(`StoragePath.parse`, SU의 저장 위치 단계도 같음): ① NUL이 있으면 다른 규칙보다 먼저 "저장 경로에는 NUL 문자를 쓸 수 없습니다" ② 앞뒤 공백을 지운다 ③ `/`로 시작하지 않으면(빈 값 포함) "절대 경로를 입력하세요." ④ 빈 조각과 `.` 조각을 지우고, `..` 조각이 있으면 "절대 경로를 입력하세요." ⑤ `/` + 남은 조각을 `/`로 이은 값이 정규화 경로(끝 슬래시 없음, 루트는 `/`) ⑥ 정규화 경로가 1024자(바이트가 아니라 문자 수) 초과면 "저장 경로는 1024자 이내로 입력하세요.". 모두 422 `invalid-value`이고 쓰기 확인 전에 거절한다. 정규화는 멱등이다. 요청 스키마는 `path`(필수 문자열)만 받고 길이 제한을 두지 않는다(빈 값·긴 값은 도메인 문구가 나간다). `path` 누락·문자열 아님·모르는 필드는 422 `request-validation`.
- **IN-R24** 쓰기 확인: 정규화 경로가 없으면 상위까지 디렉터리를 만들고(이미 있는 디렉터리를 지우지 않음), 확인용 파일을 썼다 지운다(파일 흔적 없음, 만든 디렉터리는 남음). 디렉터리가 아니거나 만들거나 쓸 수 없으면 422 `invalid-value` "해당 위치에 쓸 수 없습니다."이고 OS 오류·경로 같은 원인은 응답에 없다(서버 로그만).
- **IN-R25** 저장 위치 변경(PUT)은 경로 규칙·쓰기 확인을 통과해야 저장하며, 실패하면 기존 위치가 그대로다. 저장은 단일 행 upsert이고 revision 잠금이 없다(마지막 저장이 이김). 저장된 위치가 없어도 처음 등록할 수 있다. `updated_by` = 요청 admin, `updated_at` = 서버 시계. 기존 위치의 파일은 옮기거나 복사하지 않는다(관리자가 수작업). 응답은 저장 결과이며 이후 GET과 같다.
- **IN-R26** 쓰기 테스트(POST /test)는 경로 규칙·쓰기 확인만 하고 저장하지 않는다(저장된 위치가 없어도 된다). 성공은 204(본문 없음), 실패는 IN-R23·IN-R24의 422다.
- **IN-R27** 저장된 위치가 없으면 GET은 404 `not-found` "파일 저장 위치을(를) 찾을 수 없습니다: storage"다. 저장 위치 API는 local 모드에서도 같다. 계약: `/settings/storage`는 GET·PUT, `/storage/test`는 POST만, 요청은 `path` 하나, 테스트 204는 본문 없음, 문서화된 오류는 GET 404·PUT 422·test 422(+ PL-R21).

화면(frontend, `/admin/integrations`)
- **IN-R28** 외부연동 화면은 인증 설정(`/auth/config`)을 읽는 동안 "불러오는 중…", 실패하면 오류 배너다. `authMode`가 `local`이면 AD 섹션 대신 "로그인 방식" 카드("이 시스템은 앱에서 계정을 직접 관리합니다. AD(LDAP) 서버 설정은 사용하지 않습니다." + "계정과 비밀번호는 사용자 관리에서 만들고 고칩니다.")를 보이고 AD 설정을 서버에 요청하지 않는다. AD 모드면 AD 섹션을 보이고 안내 카드는 없다. 저장 위치 섹션은 두 모드 모두 보인다.
- **IN-R29** AD 섹션(제목 "AD(LDAP) 서버 설정"): 설정이 있으면 머리에 "마지막 수정: <저장자 표시 | -> · <formatDateTime(updated_at)>"와 "설정 버전 <revision>"을, 폼 아래에 읽기 전용 텍스트 "Base DN(AD에서 자동 확인): <base_dn>"을 보인다(입력 칸 아님). GET이 404면 "없음"으로 보고 "AD 서버가 아직 설정되지 않았습니다. 아래에서 등록하세요."와 빈 등록 폼(최초 설정 링크 아님)을 보인다. 그 밖의 조회 실패는 AD 오류 문구(IN-R34)로 배너를 보인다.
- **IN-R30** AD 입력 칸(공용 `DirectoryFields`, SU도 사용)은 정확히 7개다: 호스트, 포트(number), 보안 연결(선택: 없음/SSL/StartTLS), 바인드 계정, 바인드 비밀번호(password, `autocomplete="new-password"`), 사용자 검색 필터, 연결 제한 시간(초)(number). 나머지 칸은 `autocomplete="off"`. 새 폼 기본값은 SSL·636·`(&(objectClass=user)(sAMAccountName={login_id}))`·5·빈 비밀번호. 보안 연결을 바꾸면 포트가 비었거나 이전 방식의 기본 포트일 때만 새 방식의 기본 포트로 바꾸고 직접 쓴 포트는 둔다. 보안 연결 아래 경고: 없음 "보안 연결 없음: 비밀번호가 암호화되지 않은 채 전송됩니다. 신뢰하는 내부망에서만 쓰세요.", SSL "SSL: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.", StartTLS "StartTLS: 연결은 암호화되지만 서버 인증서를 검증하지 않습니다.".
- **IN-R31** 바인드 비밀번호 칸(저장된 설정이 있을 때): 처음엔 마스크 `********`를 보이고 손대지 않으면 요청에서 `bind_password` 키를 빼서 보낸다(유지). 칸에 포커스하면 마스크를 비우고, 입력 없이 떠나면 마스크로 돌아간다. 입력한 값은 마스크와 같은 글자여도 새 비밀번호로 보낸다(문자열 비교로 판단하지 않음). 엔드포인트·계정 4칸 중 하나를 바꾸면(아직 비밀번호를 입력하지 않았을 때) 칸을 비우고 "서버나 바인드 계정을 바꿨으므로 비밀번호를 다시 입력하세요."를 보이며, 입력 전에 저장된 값으로 되돌리면 마스크로 돌아간다. 사용자 필터·연결 제한 시간만 바꾸면 마스크가 유지된다. `bind_credential_status`가 `unreadable`이면 빈 칸과 "저장된 바인드 비밀번호를 읽을 수 없습니다. 다시 입력하세요."를 보인다. 유지 상태에서는 "그대로 두면 저장된 비밀번호를 씁니다."를 보인다. 요청이 끝나면(성공·실패) 입력한 바인드 비밀번호를 화면에서 지운다(유지 가능한 상태면 마스크, 아니면 빈 칸).
- **IN-R32** 화면 검증은 하나뿐이다: 보내야 하는 바인드 비밀번호(새 폼, 직접 입력 중, 다시 입력 요구, 읽을 수 없음)가 비었거나 공백뿐이면 요청 없이 "바인드 비밀번호를 입력하세요"를 보인다. 나머지 값 검증은 서버 문구를 보인다.
- **IN-R33** 현재 admin 비밀번호 칸: 라벨 "현재 관리자 비밀번호(새 설정으로 인증을 확인합니다)", password 형식, `autocomplete="current-password"`, 안내 "현재 관리자(본인) 비밀번호를 입력하세요.". 비어 있으면 `null`을 보낸다(서버가 IN-R10으로 거절). 요청이 끝나면(성공·실패) 칸을 비운다. 비밀번호가 든 요청 값은 쿼리 캐시에 남기지 않는다(`gcTime: 0`).
- **IN-R34** 버튼 "연결 테스트"·"저장"(요청 중에는 둘 다 비활성). 새 동작을 시작하면 이전 결과 알림을 지운다. 연결 테스트 성공은 "연결 테스트에 성공했습니다." + " Base DN: <찾은 값>", 저장 성공은 "저장했습니다"이고 폼을 저장 결과로 다시 채운다(설정 버전·마지막 수정 갱신). 저장 요청의 `expected_revision`은 화면이 읽은 revision(설정이 없었으면 `null`)이다. 실패 알림 문구(`directoryErrorMessage`): `directory-verification-failed`면 단계별 화면 문구(2.8, 모르는 단계면 서버 문구), 429면 "시도가 너무 많습니다. 잠시 후 다시 시도하세요.", 그 밖은 PL-R37 문구(서버 `detail`).
- **IN-R35** 게이트웨이: AD·저장 위치 GET이 404면 오류가 아니라 `null`(그 밖의 실패는 그대로 던짐). 연결 테스트 응답이 `success: false`면 `ApiError` 422 kind `directory-verification-failed`(문구 = 서버 `message`, `stage` 유지)로 바꿔 화면이 한 경로로 다루게 한다. 저장·테스트 본문은 입력 7칸(유지면 `bind_password` 키 없음) + `password`(+ 저장은 `expected_revision`)뿐이다. 저장 위치 테스트는 204를 성공으로 받는다.
- **IN-R36** 저장 위치 섹션(제목 "파일 저장 위치", 안내 "첨부 파일이 저장되는 서버 디렉터리입니다."): 저장된 위치가 있으면 "현재 위치: <path>"와 "마지막 수정: <저장자 | -> · <시각>", 없으면 "아직 저장 위치가 설정되지 않았습니다."를 보이고, 늘 "위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다. 기존 파일은 자동으로 옮겨지지 않습니다."를 보인다. 폼(`aria-label` "파일 저장 위치 변경")은 "저장 경로" 칸(저장된 경로로 시작)과 안내 "서버의 절대 경로를 입력하세요. 예: /var/lib/neoine-sales/files", 버튼 "쓰기 테스트"·"저장"이다. 쓰기 테스트 성공은 "쓰기 테스트에 성공했습니다.", 저장 성공은 "저장했습니다"이고 현재 위치가 서버가 정규화한 경로로 바뀐다. 실패는 서버 문구를 그대로 보인다. 화면은 경로를 미리 검증하지 않는다.

### 2.4 상태와 전이

AD 설정 행

| 현재 | 행동 | 조건 | 결과 |
| --- | --- | --- | --- |
| 없음 | PUT `expected_revision: null` | 확인 성공 | 있음(revision 1) |
| 없음 | PUT `expected_revision: n` | — | 404, 없음 유지 |
| 있음(revision r) | PUT `expected_revision: r` | 확인 성공 | 있음(revision r+1) |
| 있음 | PUT `null` 또는 `≠ r` | — | 409, 그대로 |
| 무엇이든 | POST test | — | 그대로 |
| 무엇이든(local 모드) | PUT·POST test | — | 409, 그대로 |

저장 위치 행: 없음 → PUT 성공 → 있음, 있음 → PUT 성공 → 있음(새 경로). 테스트는 상태를 바꾸지 않는다.

### 2.5 권한

| 행동(경로) | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| GET `/settings/directory` | 401 | 403 | 403 | 가능 |
| PUT `/settings/directory` | 401 | 403 | 403 | 가능(+ 현재 admin 비밀번호) |
| POST `/settings/directory/test` | 401 | 403 | 403 | 가능(+ 현재 admin 비밀번호) |
| GET `/settings/storage` | 401 | 403 | 403 | 가능 |
| PUT `/settings/storage` | 401 | 403 | 403 | 가능 |
| POST `/settings/storage/test` | 401 | 403 | 403 | 가능 |
| 화면 `/admin/integrations` | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

- 여섯 경로 모두 관리자 가드(`admin_router`)이며 sales·user는 403 `forbidden` "관리자 권한이 필요합니다"(PL-R7), 본문 검증보다 먼저다. PUT·POST는 CSRF 헤더가 필요하다(PL-R9).
- 판정 순서(PL-R4에 더해): 미인증 401 → CSRF 403 → 관리자 가드 403 → 요청 형식 422 `request-validation` → 값 규칙 422 `invalid-value`(바인드 비밀번호 → 접속 정보 → 현재 admin 비밀번호 형식) → local 모드 409 → (PUT) revision 404/409 → 바인드 비밀번호 유지 판정 422 → 현재 admin 비밀번호 없음 422 → Base DN 탐색 → 시도 제한 429 → admin 바인드 → (PUT) 확인 실패 422 / 저장 시 revision 409.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/settings/directory` | — | 200 `DirectorySettingsResponse` | 404 `not-found` |
| PUT `/settings/directory` | `DirectorySettingsUpdateRequest` `{host, port, security, bind_account, bind_password?, user_filter, connect_timeout_seconds?(=5), password?, expected_revision(필수, null 가능)}` | 200 `DirectorySettingsResponse` | 422 `request-validation`·`invalid-value`·`directory-verification-failed`(+`stage`), 404 `not-found`, 409 `invalid-state`, 429 `too-many-attempts` |
| POST `/settings/directory/test` | `DirectorySettingsTestRequest` `{host, port, security, bind_account, bind_password?, user_filter, connect_timeout_seconds?, password?}` | 200 `DirectoryTestResultResponse` `{success, stage, message, base_dn}` | 422 `request-validation`·`invalid-value`, 409 `invalid-state`, 429 `too-many-attempts` |
| GET `/settings/storage` | — | 200 `StorageSettingsResponse` `{path, updated_at, updated_by}` | 404 `not-found` |
| PUT `/settings/storage` | `StorageSettingsRequest` `{path}` | 200 `StorageSettingsResponse` | 422 `request-validation`·`invalid-value` |
| POST `/settings/storage/test` | `StorageSettingsRequest` `{path}` | 204 | 422 `request-validation`·`invalid-value` |

- 예: 저장 성공 `{"host":"dc1.corp.example","port":636,"security":"ssl","bind_account":"CN=svc-ldap,OU=Service,DC=corp,DC=example","bind_credential_status":"ok","user_filter":"(&(objectClass=user)(sAMAccountName={login_id}))","connect_timeout_seconds":5,"base_dn":"DC=corp,DC=example","revision":2,"updated_at":"2026-11-09T10:00:00+09:00","updated_by":{...UserRef}}`.
- `directory-verification-failed` 본문: Problem(PL-R10) + `stage`(단계 문자열), `detail` = 2.8 서버 문구.
- 모든 경로 공통: 401 `unauthenticated`, 403 `csrf`·`forbidden`(PL).

### 2.7 화면 동작

IN-R28~IN-R36. 화면 접근 가드·Admin 서브 메뉴는 PL-R31·PL-R35.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구(서버 `detail`) |
| --- | --- | --- |
| AD 설정 없음(GET, 정수 revision 저장) | 404 `not-found` | AD 설정을(를) 찾을 수 없습니다: directory |
| revision 충돌·이미 있음 | 409 `invalid-state` | 설정이 다른 곳에서 바뀌었습니다. 새로고침 후 다시 시도하세요 |
| local 모드 저장·테스트 | 409 `invalid-state` | AD 연동 모드에서만 쓸 수 있습니다. |
| 현재 admin 비밀번호 없음 | 422 `invalid-value` | AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다 |
| 바인드 비밀번호 필요·재입력·읽기 불가 | 422 `invalid-value` | IN-R9 문구 |
| 접속 정보·비밀번호 값 위반 | 422 `invalid-value` | IN-R2~IN-R8, IN-R10 문구 |
| 시도 제한 | 429 `too-many-attempts` | AU 문구 |
| 저장 위치 없음(GET) | 404 `not-found` | 파일 저장 위치을(를) 찾을 수 없습니다: storage |
| 경로 위반 | 422 `invalid-value` | 저장 경로에는 NUL 문자를 쓸 수 없습니다 / 절대 경로를 입력하세요. / 저장 경로는 1024자 이내로 입력하세요. |
| 쓸 수 없는 위치 | 422 `invalid-value` | 해당 위치에 쓸 수 없습니다. |

확인 단계별 문구(PUT 422 `detail`·test 결과 `message`는 서버 문구, 화면 알림은 화면 문구)

| stage | 서버 문구 | 화면 문구 |
| --- | --- | --- |
| `connect` | AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요 | AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요. |
| `tls` | TLS 연결에 실패했습니다. 보안 연결(SSL/StartTLS) 방식과 포트를 확인하세요 | SSL/StartTLS 연결을 맺지 못했습니다. 보안 연결 방식과 포트가 서버 설정과 맞는지 확인하세요. |
| `service_bind` | 바인드 계정으로 AD에 로그인하지 못했습니다. 계정과 비밀번호를 확인하세요 | 바인드 계정으로 AD에 로그인하지 못했습니다. 바인드 계정과 바인드 비밀번호를 확인하세요. |
| `base_dn` | AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. 바인드 계정 권한을 확인하세요 | AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. AD 서버 설정과 바인드 계정의 조회 권한을 확인하세요. |
| `search` | 사용자 조회에 실패했습니다. 사용자 필터를 확인하세요 | 사용자 검색에 실패했습니다. 사용자 필터와 바인드 계정의 검색 권한을 확인하세요. |
| `bind` | AD 인증에 실패했습니다. 관리자 비밀번호를 확인하세요 | 입력한 관리자 비밀번호로 AD에 로그인하지 못했습니다. 관리자 비밀번호를 확인하세요. |
| 그 밖 | AD 설정을 확인하지 못했습니다 | 서버 문구 그대로 |

화면 고정 문구: "연결 테스트에 성공했습니다.", "저장했습니다", "쓰기 테스트에 성공했습니다.", "바인드 비밀번호를 입력하세요", "시도가 너무 많습니다. 잠시 후 다시 시도하세요.", "AD 서버가 아직 설정되지 않았습니다. 아래에서 등록하세요.", "아직 저장 위치가 설정되지 않았습니다.".

## 3. Business use case

### IN-UC1 AD 설정 조회
- 행위자: admin
- 사전 조건: 로그인, AD 모드
- 기본 흐름: 외부연동 화면을 연다 → GET → 접속 정보·Base DN·설정 버전·마지막 수정·비밀번호 마스크를 본다(IN-R16, IN-R29, IN-R31)
- 대안: 설정 없음 → 등록 폼(IN-R19, IN-R29). 저장 비밀번호를 풀 수 없음 → `unreadable`과 재입력 안내
- 예외: sales·user 403, 미인증 401
- 결과: 비밀번호 없는 현재 설정

### IN-UC2 AD 연결 테스트
- 행위자: admin
- 사전 조건: AD 모드
- 기본 흐름: 입력 칸을 고치고 현재 admin 비밀번호 입력 → "연결 테스트" → 값 검사 → 바인드 비밀번호 완성 → Base DN 탐색 → admin 검색·바인드 → 성공 결과와 Base DN(IN-R9~IN-R11, IN-R18)
- 대안: 확인 실패 → 200 실패 결과(단계·문구), 화면은 단계 문구
- 예외: 값 위반·유지 불가·비밀번호 없음 422, 시도 제한 429, local 모드 409
- 결과: 아무것도 저장되지 않음

### IN-UC3 AD 설정 저장
- 행위자: admin
- 사전 조건: AD 설정 있음, 화면이 읽은 revision
- 기본 흐름: 입력·현재 admin 비밀번호 → "저장" → revision 확인 → 확인(IN-R11) → 암호화 저장 → revision+1·저장자·시각 갱신(IN-R14, IN-R15)
- 대안: 바인드 비밀번호 유지(IN-R9)
- 예외: 낡은 revision 409, 확인 실패 422(+stage, 저장 안 함), 시도 제한 429, local 모드 409
- 결과: 새 설정, 기존 세션 유지, 다음 로그인부터 적용(IN-R17)

### IN-UC4 AD 설정 처음 등록
- 행위자: admin(설정이 없어 대체 로그인 등으로 들어온 admin 포함)
- 사전 조건: AD 모드, AD 설정 없음
- 기본 흐름: 등록 폼 → 7칸(바인드 비밀번호 필수)과 현재 admin 비밀번호 → `expected_revision: null`로 저장 → 확인 → revision 1(IN-R14)
- 예외: 바인드 비밀번호 생략 422, 그 사이 설정이 생기면 409, 확인 실패 422(행 없음)
- 결과: AD 설정 생성

### IN-UC5 local 모드의 연동 설정
- 행위자: admin
- 사전 조건: local 모드
- 기본 흐름: 외부연동 화면 → AD 섹션 대신 안내, AD 설정 조회 없음, 저장 위치는 그대로(IN-R28)
- 예외: API로 AD 저장·테스트 → 409(IN-R20)
- 결과: AD를 건드리지 않는다

### IN-UC6 저장 위치 확인·쓰기 테스트
- 행위자: admin
- 기본 흐름: 현재 위치·마지막 수정을 본다 → 경로 입력 → "쓰기 테스트" → 204 → 성공 문구(IN-R22, IN-R26, IN-R36)
- 예외: 경로 위반·쓸 수 없음 422, 위치 없음이면 GET 404(화면은 "아직 … 설정되지 않았습니다.")
- 결과: 저장 안 함

### IN-UC7 저장 위치 변경
- 행위자: admin
- 기본 흐름: 경로 입력 → "저장" → 경로 정규화 → 쓰기 확인(없으면 디렉터리 생성) → upsert → 현재 위치 갱신(IN-R23~IN-R25)
- 대안: 위치가 없던 시스템에서 처음 등록
- 예외: 경로 위반·쓸 수 없음 422(기존 위치 유지)
- 결과: 새 위치에 이후 첨부가 저장됨(AT·LC), 기존 파일은 그대로

## 4. BDD 테스트 케이스

요청자 예시: BOSS(admin, 로그인 아이디 `boss`), KIM(sales), VIEWER(user). 서버 케이스의 AD는 Fake `DirectoryAuthenticator`(Base DN `DC=corp,DC=example`, 단계별 실패 주입), 암호화는 Fake `SecretCipher`, 파일은 Fake `FileStorage`(쓸 수 없는 경로 주입)다. 저장된 AD 설정 예: `dc1.corp.example`·636·`ssl`·`CN=svc-ldap,…`·바인드 비밀번호 `svc-pass`·revision 1.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| IN-001 | admin이 AD 설정을 조회하면 접속 정보·Base DN·revision·저장자가 나오고 비밀번호는 없다 | IN-R16, IN-UC1 | backend | `application/test_directory_settings_get_and_check.py::test_get_settings_returns_the_stored_row_and_a_readable_credential`<br>`web/test_directory_schemas.py::test_settings_response_has_the_documented_fields_and_no_password`<br>`web/test_directory_settings_routes.py::test_admin_reads_the_settings_with_the_documented_keys_and_no_secret` |
| IN-002 | 저장된 바인드 비밀번호를 풀 수 없으면 조회 결과는 unreadable이다 | IN-R16, IN-R15, IN-UC1 | backend | `application/test_directory_settings_get_and_check.py::test_get_settings_reports_unreadable_credential` |
| IN-003 | AD 설정이 없으면 조회는 404다 | IN-R19, IN-UC1 | backend | `application/test_directory_settings_get_and_check.py::test_get_settings_without_a_row_is_not_found`<br>`web/test_directory_settings_routes.py::test_reading_without_saved_settings_is_404_with_the_fixed_message` |
| IN-004 | 연결 테스트가 성공하면 찾은 Base DN을 돌려주고 아무것도 저장하지 않는다 | IN-R18, IN-R11, IN-R12, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_discovers_base_dn_then_authenticates_the_admin`<br>`application/test_directory_settings_get_and_check.py::test_test_settings_never_saves` |
| IN-005 | 틀린 admin 비밀번호의 연결 테스트는 오류가 아니라 bind 단계 실패 결과다 | IN-R18, IN-R11, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_reports_a_wrong_password_as_a_bind_failure_result`<br>`web/test_directory_settings_routes.py::test_a_wrong_admin_password_test_is_a_200_bind_failure_without_the_password` |
| IN-006 | 연결 테스트는 실패한 단계를 그 단계 문구로 알린다 | IN-R11, IN-R18, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_reports_each_failure_stage_without_raising`<br>`web/test_directory_settings_routes.py::test_the_connection_test_reports_each_failed_stage_with_its_server_message` |
| IN-007 | Base DN을 찾지 못하면 admin 인증을 하지 않는다 | IN-R11, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_does_not_authenticate_when_base_dn_discovery_fails` |
| IN-008 | 바인드 비밀번호를 생략하거나 null로 보내면 저장된 비밀번호를 쓴다 | IN-R9, IN-UC2, IN-UC3 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_without_bind_password_uses_the_stored_one`<br>`application/test_directory_settings_update.py::test_update_without_bind_password_reuses_stored_password` |
| IN-009 | 새 바인드 비밀번호로 연결 테스트해도 저장된 비밀번호는 그대로다 | IN-R9, IN-R18, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_with_a_new_bind_password_leaves_the_stored_one_untouched` |
| IN-010 | 엔드포인트·계정을 바꾸고 바인드 비밀번호를 생략하면 AD를 부르기 전에 422다 | IN-R9, IN-UC2, IN-UC3 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_without_bind_password_after_host_change_is_rejected_before_ad`<br>`application/test_directory_settings_get_and_check.py::test_a_host_that_differs_only_in_case_keeps_the_stored_bind_password`<br>`application/test_directory_settings_update.py::test_update_without_bind_password_after_host_change_is_rejected_before_contacting_ad` |
| IN-011 | 사용자 필터·연결 제한 시간만 바꾸면 바인드 비밀번호가 유지된다 | IN-R9, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_without_bind_password_reuses_stored_password` |
| IN-012 | AD 설정이 없을 때 바인드 비밀번호를 생략하면 422다 | IN-R9, IN-UC4 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_without_bind_password_and_no_stored_settings_is_rejected`<br>`application/test_directory_settings_update.py::test_update_with_null_revision_without_bind_password_is_rejected` |
| IN-013 | 저장된 비밀번호를 풀 수 없으면 생략은 422이고 새 비밀번호는 통과한다 | IN-R9, IN-UC3 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_without_bind_password_and_unreadable_stored_one_is_rejected`<br>`application/test_directory_settings_get_and_check.py::test_test_settings_with_a_new_password_works_when_the_stored_one_is_unreadable`<br>`application/test_directory_settings_update.py::test_update_with_unreadable_stored_password_needs_a_new_one` |
| IN-014 | 현재 admin 비밀번호 없이 저장·테스트하면 탐색 전에 422다 | IN-R10, IN-UC2, IN-UC3 | backend | `application/test_directory_settings_get_and_check.py::test_test_settings_without_an_admin_password_is_invalid_and_skips_the_admin_bind`<br>`application/test_directory_settings_get_and_check.py::test_a_test_without_the_admin_password_is_rejected_even_for_a_retired_dev_id`<br>`application/test_directory_settings_update.py::test_update_requires_a_password_from_a_directory_admin`<br>`application/test_directory_settings_update.py::test_a_missing_password_is_rejected_before_any_discovery` |
| IN-015 | 형식이 틀린 현재 admin 비밀번호는 AD를 부르지 않고 422다 | IN-R10, IN-UC3 | backend | `web/test_directory_settings_routes.py::test_a_malformed_admin_password_is_422_and_never_reaches_the_directory` |
| IN-016 | 형식이 틀린 접속 정보는 필드 이름이 든 422이고 AD를 부르지 않으며 아무것도 바뀌지 않는다 | IN-R7, IN-R2~IN-R6, IN-UC3 | backend | `web/test_directory_schemas.py::test_value_violations_are_domain_errors_naming_the_field`<br>`web/test_directory_settings_routes.py::test_a_malformed_connection_value_is_422_naming_the_field_and_changes_nothing` |
| IN-017 | 호스트는 이름·IPv4·IPv6만 받아 소문자로 맞추고 URL·포트·경로는 거절한다 | IN-R2 | backend | `domain/test_directory_host.py::test_host_names_and_ip_literals_are_accepted_and_lowercased`<br>`domain/test_directory_host.py::test_urls_ports_paths_and_malformed_hosts_are_rejected_with_the_field_name`<br>`domain/test_directory_host.py::test_the_longest_valid_hostname_is_accepted`<br>`domain/test_directory_settings.py::test_connection_rejects_a_host_with_scheme_or_port_naming_the_field` |
| IN-018 | 사용자 필터는 {login_id} 한 번과 바깥 괄호 짝을 요구한다 | IN-R5 | backend | `domain/test_directory_settings.py::test_user_filter_rules_are_kept`<br>`domain/test_directory_settings.py::test_valid_filters_are_accepted`<br>`domain/test_directory_settings.py::test_user_filter_length_limit_is_512` |
| IN-019 | 포트·연결 제한 시간·바인드 계정의 경계값 | IN-R3, IN-R4, IN-R6 | backend | `domain/test_directory_settings.py::test_valid_connection_keeps_normalized_host_and_default_timeout`<br>`domain/test_directory_settings.py::test_port_outside_range_is_rejected_with_field_name`<br>`domain/test_directory_settings.py::test_connect_timeout_outside_1_to_30_is_rejected`<br>`domain/test_directory_settings.py::test_bind_account_accepts_dn_upn_and_domain_forms`<br>`domain/test_directory_settings.py::test_bind_account_empty_too_long_or_control_char_is_rejected` |
| IN-020 | 빈 문자열·공백만·NUL·257자 바인드 비밀번호는 유지가 아니라 422다 | IN-R8, IN-UC3 | backend | `domain/test_directory_settings.py::test_bind_password_errors_name_the_field`<br>`domain/test_directory_settings.py::test_bind_password_of_accepts_the_longest_value_and_keeps_spaces`<br>`web/test_directory_schemas.py::test_an_empty_bind_password_is_a_value_violation_not_keep` |
| IN-021 | 폐지된 필드·모르는 필드·필수 누락·타입 오류는 422 request-validation이다 | IN-R7, IN-R18 | backend | `web/test_directory_schemas.py::test_old_fields_are_rejected_as_unknown`<br>`web/test_directory_schemas.py::test_old_fields_are_rejected_by_the_update_request`<br>`web/test_directory_schemas.py::test_security_must_be_none_ssl_or_starttls`<br>`web/test_directory_schemas.py::test_numbers_must_be_strict_integers`<br>`web/test_directory_schemas.py::test_test_request_has_no_expected_revision`<br>`web/test_directory_schemas.py::test_update_request_rejects_an_invalid_revision`<br>`web/test_directory_schemas.py::test_update_request_requires_the_revision_key`<br>`web/test_directory_settings_routes.py::test_a_malformed_request_shape_is_422_request_validation_and_never_reaches_the_directory`<br>`web/test_directory_settings_routes.py::test_a_connection_test_with_an_expected_revision_is_422_request_validation` |
| IN-022 | admin이 자기 비밀번호로 저장하면 새 설정·Base DN·저장자가 기록되고 revision이 오른다 | IN-R14, IN-R12, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_verifies_the_actor_with_the_discovered_base_dn_then_saves`<br>`web/test_directory_settings_routes.py::test_saving_returns_the_stored_result_with_server_offset_time` |
| IN-023 | 저장할 때마다 revision이 1씩 오른다 | IN-R14, IN-UC3 | backend | `application/test_directory_settings_update.py::test_each_save_raises_the_revision_by_one` |
| IN-024 | 이미 바뀐 revision으로 저장하면 AD를 부르지 않고 409다 | IN-R14, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_with_a_stale_revision_conflicts_without_calling_the_directory`<br>`domain/test_directory_stored_settings.py::test_conflict_error_is_an_invalid_state_error_with_refresh_guidance` |
| IN-025 | 설정이 있는데 null revision으로 저장하면 409다 | IN-R14, IN-UC4 | backend | `application/test_directory_settings_update.py::test_update_with_null_revision_conflicts_when_settings_exist` |
| IN-026 | 설정이 없는데 정수 revision으로 저장하면 404다 | IN-R14, IN-UC4 | backend | `application/test_directory_settings_update.py::test_update_with_an_integer_revision_is_not_found_when_settings_are_missing` |
| IN-027 | 설정이 없을 때 null revision으로 저장하면 revision 1로 만들어진다 | IN-R14, IN-UC4 | backend | `application/test_directory_settings_update.py::test_update_with_null_revision_creates_settings_when_missing` |
| IN-028 | 확인이 단계별로 실패하면 저장은 422와 그 단계이고 설정은 그대로다 | IN-R14, IN-R11, IN-UC3, IN-UC4 | backend | `application/test_directory_settings_update.py::test_update_verification_failure_saves_nothing_and_reports_the_stage`<br>`application/test_directory_settings_update.py::test_failed_creation_leaves_no_row_behind`<br>`web/test_directory_settings_routes.py::test_a_failed_verification_on_save_is_422_with_the_stage_and_keeps_the_settings` |
| IN-029 | 틀린 admin 비밀번호로 저장하면 bind 단계 422이고 실패 1회가 남는다 | IN-R13, IN-R14, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_with_a_wrong_password_keeps_the_old_settings`<br>`application/test_directory_settings_update.py::test_update_bind_failure_adds_one_failure_to_the_admins_counter` |
| IN-030 | 실패 한도를 채운 admin의 저장·테스트는 429이고 admin 바인드를 하지 않는다 | IN-R13, IN-UC2, IN-UC3 | backend | `application/test_directory_settings_get_and_check.py::test_bind_failures_count_toward_the_admins_attempt_limit`<br>`application/test_directory_settings_update.py::test_update_is_refused_while_the_admin_is_locked_out` |
| IN-031 | 연결 실패는 시도 제한 횟수에 들어가지 않는다 | IN-R13, IN-UC2 | backend | `application/test_directory_settings_get_and_check.py::test_connection_failures_do_not_count_toward_the_attempt_limit` |
| IN-032 | 바인드 비밀번호는 평문이 아니라 풀면 원래 값이 되는 암호문으로 저장된다 | IN-R15, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_verifies_the_actor_with_the_discovered_base_dn_then_saves` |
| IN-033 | 새 바인드 비밀번호로 저장하면 암호문이 새 값으로 바뀐다 | IN-R15, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_with_a_new_password_replaces_the_stored_one` |
| IN-034 | 저장·테스트·조회의 성공·오류 응답과 로그에 비밀번호와 암호문이 없다 | IN-R15, IN-R16, IN-UC2, IN-UC3 | backend | `application/test_directory_credentials.py::test_unseal_settings_failure_raises_unavailable_and_logs_a_warning_without_values`<br>`web/test_directory_settings_routes.py::test_no_response_or_log_carries_the_passwords_or_the_ciphertext` |
| IN-035 | AD 설정을 저장해도 이미 열린 세션은 유지된다 | IN-R17, IN-UC3 | backend | `application/test_directory_settings_update.py::test_update_keeps_existing_sessions_alive` |
| IN-036 | 저장 결과는 조회와 같고 다음 로그인은 저장된 Base DN·비밀번호를 쓴다 | IN-R17, IN-R12, IN-UC3 | backend | `application/test_directory_settings_update.py::test_the_next_login_uses_the_saved_base_dn_and_bind_password` |
| IN-037 | local 모드에서 AD 설정을 저장하면 409이고 AD를 부르지 않으며 행은 그대로다 | IN-R20, IN-UC5 | backend | `application/test_directory_settings_local_mode.py::test_update_directory_settings_in_local_mode_is_invalid_state`<br>`application/test_directory_settings_local_mode.py::test_update_directory_settings_in_local_mode_keeps_an_old_row_unchanged` |
| IN-038 | local 모드에서 연결 테스트도 409다 | IN-R20, IN-UC5 | backend | `application/test_directory_settings_local_mode.py::test_test_directory_settings_in_local_mode_is_invalid_state` |
| IN-039 | local 모드에서 AD 설정 조회는 설정이 없으면 404다 | IN-R20, IN-R19, IN-UC5 | backend | `application/test_directory_settings_local_mode.py::test_get_directory_settings_in_local_mode_is_still_not_found` |
| IN-040 | 연동 설정 6개 경로는 admin만 쓰고 sales·user는 본문 검사 전에 403, 미인증은 401이다 | 2.5, IN-UC1, IN-UC6 | backend | `web/test_directory_settings_routes.py::test_only_admin_may_use_the_six_integration_routes`<br>`web/test_storage_routes.py::test_sales_cannot_use_the_storage_settings_even_with_a_bad_body`<br>`web/test_storage_routes.py::test_anonymous_callers_get_401_on_the_storage_settings` |
| IN-041 | 연동 설정 변경·테스트 요청은 CSRF 헤더가 없으면 403이고 아무것도 바뀌지 않는다 | 2.5, IN-UC3, IN-UC7 | backend | `web/test_directory_settings_routes.py::test_changes_without_the_csrf_header_are_403_and_change_nothing` |
| IN-042 | AD 설정 API 계약은 입력 7칸·비밀번호 표기·revision·결과 필드를 문서화한다 | IN-R21 | backend | `web/test_directory_openapi.py::test_directory_settings_paths_expose_only_the_planned_methods`<br>`web/test_directory_openapi.py::test_update_and_test_requests_take_the_seven_fields_the_password_and_the_revision`<br>`web/test_directory_openapi.py::test_bind_password_and_password_are_masked_write_only_secrets`<br>`web/test_directory_openapi.py::test_response_hides_the_password_and_the_result_has_four_fields`<br>`web/test_directory_openapi.py::test_documented_responses_of_the_settings_routes`<br>`web/test_directory_openapi.py::test_documented_responses_of_the_connection_test`<br>`web/test_directory_schemas.py::test_test_result_response_carries_the_discovered_base_dn` |
| IN-043 | admin이 저장 위치를 조회하면 최초 설정에서 저장한 경로가 나오고 저장자는 비어 있다 | IN-R22, IN-UC6 | backend | `application/test_storage_settings.py::test_get_storage_settings_returns_the_saved_settings`<br>`web/test_storage_routes.py::test_admin_reads_the_saved_settings` |
| IN-044 | 저장 위치가 없으면 조회는 404다 | IN-R27, IN-UC6 | backend | `application/test_storage_settings.py::test_get_storage_settings_without_a_saved_path_is_not_found`<br>`web/test_storage_routes.py::test_reading_without_saved_settings_is_404_not_found` |
| IN-045 | admin이 저장 위치를 바꾸면 새 경로·저장자·서버 시각이 기록되고 다시 조회된다 | IN-R25, IN-R22, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_records_the_actor_and_the_time`<br>`web/test_storage_routes.py::test_admin_update_records_the_admin_as_the_saver`<br>`web/test_storage_routes.py::test_admin_update_records_the_server_clock_with_its_offset` |
| IN-046 | 경로는 앞뒤 공백·중복 슬래시·점 조각·끝 슬래시를 정리해 저장한다 | IN-R23, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_normalizes_the_path`<br>`domain/test_storage_path.py::test_parse_trims_and_normalizes_slashes`<br>`domain/test_storage_path.py::test_parse_is_idempotent_on_its_own_output` |
| IN-047 | 절대 경로가 아니거나 ..가 있는 경로는 쓰기 확인 전에 422이고 기존 위치는 그대로다 | IN-R23, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_rejects_a_malformed_path_without_probing`<br>`domain/test_storage_path.py::test_the_messages_are_the_fixed_user_facing_sentences`<br>`domain/test_storage_path.py::test_parse_rejects_empty_relative_and_dot_dot_paths` |
| IN-048 | 정규화한 경로는 1024자까지 받고 1025자는 422다 | IN-R23, IN-UC7 | backend | `domain/test_storage_path.py::test_the_messages_are_the_fixed_user_facing_sentences`<br>`domain/test_storage_path.py::test_parse_accepts_exactly_the_maximum_length`<br>`domain/test_storage_path.py::test_parse_rejects_one_character_over_the_maximum_length`<br>`domain/test_storage_path.py::test_the_length_is_measured_in_characters_not_bytes`<br>`domain/test_storage_path.py::test_the_length_is_measured_after_normalization` |
| IN-049 | NUL이 든 경로는 다른 규칙보다 먼저 422다 | IN-R23, IN-UC7 | backend | `domain/test_storage_path.py::test_the_messages_are_the_fixed_user_facing_sentences`<br>`domain/test_storage_path.py::test_parse_rejects_nul_characters_before_any_other_rule` |
| IN-050 | 쓸 수 없는 위치는 원인 없는 고정 문구 422이고 기존 위치는 그대로다 | IN-R24, IN-R25, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_rejects_an_unwritable_path_and_keeps_the_old_one`<br>`application/test_storage_settings.py::test_ensure_writable_does_not_leak_the_storage_error_text`<br>`web/test_storage_routes.py::test_admin_update_with_an_unwritable_path_is_422_and_keeps_the_old_path` |
| IN-051 | 새 위치 디렉터리가 없으면 만들고 확인용 파일은 남기지 않는다 | IN-R24, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_creates_the_missing_directory` |
| IN-052 | 위치를 바꿔도 기존 파일은 옮기거나 복사하지 않는다 | IN-R25, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_does_not_move_existing_files` |
| IN-053 | 저장 위치가 없는 시스템에서도 admin이 처음 등록할 수 있다 | IN-R25, IN-UC7 | backend | `application/test_storage_settings.py::test_update_storage_settings_works_when_no_path_was_saved_yet` |
| IN-054 | 쓰기 테스트는 204이고 아무것도 저장하지 않는다 | IN-R26, IN-UC6 | backend | `application/test_storage_settings.py::test_storage_settings_test_saves_nothing`<br>`application/test_storage_settings.py::test_storage_settings_test_succeeds_for_a_writable_path_even_without_saved_settings`<br>`web/test_storage_routes.py::test_admin_write_test_is_204_and_saves_nothing` |
| IN-055 | 쓸 수 없는 위치·형식이 틀린 경로의 쓰기 테스트는 422다 | IN-R26, IN-R23, IN-R24, IN-UC6 | backend | `application/test_storage_settings.py::test_storage_settings_test_rejects_an_unwritable_path`<br>`application/test_storage_settings.py::test_storage_settings_test_rejects_a_malformed_path` |
| IN-056 | 저장 위치 요청은 path 하나만 받고 길이·빈 값은 도메인 문구로 거절한다 | IN-R23, IN-UC7 | backend | `application/test_storage_settings.py::test_empty_and_overlong_paths_are_refused_with_the_domain_message`<br>`web/test_storage_requests.py::test_an_overlong_path_is_left_to_the_domain_not_the_schema`<br>`web/test_storage_requests.py::test_an_empty_path_is_left_to_the_domain_not_the_schema`<br>`web/test_storage_requests.py::test_the_json_schema_has_no_length_constraint_so_the_domain_message_is_returned`<br>`web/test_storage_requests.py::test_path_is_required`<br>`web/test_storage_requests.py::test_path_must_be_a_string`<br>`web/test_storage_requests.py::test_unknown_fields_are_rejected`<br>`web/test_storage_routes.py::test_a_malformed_storage_request_is_422_request_validation`<br>`web/test_storage_routes.py::test_an_empty_or_overlong_storage_path_is_422_with_the_domain_message` |
| IN-057 | local 모드에서도 저장 위치를 그대로 조회·변경한다 | IN-R27, IN-R20, IN-UC5 | backend | `application/test_storage_settings.py::test_storage_settings_are_readable_and_changeable_in_local_mode` |
| IN-058 | 저장 위치 API 계약은 경로·메서드·204·요청·응답 필드를 문서화한다 | IN-R27, IN-R22 | backend | `web/test_storage_openapi.py::test_storage_settings_paths_and_methods`<br>`web/test_storage_openapi.py::test_documented_success_and_problem_responses`<br>`web/test_storage_openapi.py::test_write_test_endpoints_have_no_response_body`<br>`web/test_storage_openapi.py::test_request_schema_takes_only_a_path`<br>`web/test_storage_openapi.py::test_response_schema_has_path_time_and_a_nullable_saver` |
| IN-059 | 화면: AD 모드에서 저장된 설정을 폼에 보이고 Base DN은 읽기 전용 텍스트, 비밀번호는 마스크다 | IN-R29, IN-R31, IN-UC1 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > AD 모드에서 저장된 설정을 폼에 보이고 Base DN은 읽기 전용 텍스트, 비밀번호는 마스크로 보인다`<br>`shared/directory/DirectoryFields.test.tsx > shows the saved values and a fixed mask in the password field`<br>`shared/directory/DirectoryFields.test.tsx > shows the discovered Base DN as read-only text, not as an input` |
| IN-060 | 화면: 마지막 수정자·시각과 설정 버전을 보인다 | IN-R29, IN-UC1 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 마지막 수정자·시각과 설정 버전을 보인다` |
| IN-061 | 화면: AD 설정을 불러오지 못하면 문구 배너를 보인다 | IN-R29, IN-UC1 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > AD 설정을 불러오지 못하면 서버 문구의 오류 배너를 보이고 AD 폼은 없다` |
| IN-062 | 화면: 저장하면 저장했습니다와 함께 설정 버전·마지막 수정이 바뀐다 | IN-R34, IN-UC3 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 저장하면 저장했습니다와 함께 설정 버전·마지막 수정이 바뀐다` |
| IN-063 | 화면: 저장·테스트는 현재 admin 비밀번호와 읽은 revision을 보내고, 비면 null을 보낸다 | IN-R33, IN-R34, IN-UC3 | frontend | `features/admin/integrations/DirectoryPassword.test.tsx > 현재 관리자 비밀번호를 password 형식의 빈 칸과 안내 문구로 요구하고 개발용 로그인 문구가 없다`<br>`features/admin/integrations/DirectoryPassword.test.tsx > 저장하면 입력한 현재 관리자 비밀번호와 읽은 설정 버전을 보낸다`<br>`features/admin/integrations/DirectoryPassword.test.tsx > 연결 테스트도 현재 관리자 비밀번호를 보내고 저장하지 않는다`<br>`features/admin/integrations/DirectoryPassword.test.tsx > 비밀번호 칸을 비운 채 누르면 null을 보내고 서버의 비밀번호 필요 문구를 보인다` |
| IN-064 | 화면: 요청이 끝나면 성공·실패 모두 비밀번호 칸들을 비운다 | IN-R31, IN-R33, IN-UC3 | frontend | `features/admin/integrations/DirectoryPassword.test.tsx > 요청이 끝나면 성공이든 실패든 현재 관리자 비밀번호 칸을 비운다`<br>`shared/directory/DirectoryFields.test.tsx > goes back to the mask after a successful save and never shows the typed password`<br>`shared/directory/DirectoryFields.test.tsx > goes back to the mask after a failed test too` |
| IN-065 | 화면: 연결 테스트는 저장하지 않고 찾은 Base DN을 보인다 | IN-R34, IN-UC2 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 연결 테스트는 저장하지 않고 찾은 Base DN을 보인다` |
| IN-066 | 화면: 연결 테스트가 실패하면 실패 단계 안내를 보인다 | IN-R34, IN-UC2 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 연결 테스트가 실패하면 실패 단계 안내를 오류 알림으로 보인다` |
| IN-067 | 화면: 다음 동작을 시작하면 이전 결과를 지운다 | IN-R34, IN-UC2 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 다음 동작을 시작하면 새 요청이 끝나기 전에 이전 결과 알림이 사라진다` |
| IN-068 | 화면: 서버의 값 오류 문구를 그대로 보인다 | IN-R34, IN-R32, IN-UC3 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 서버의 값 오류 문구를 화면이 미리 막지 않고 그대로 보인다`<br>`features/admin/integrations/IntegrationsPage.test.tsx > 현재 admin 비밀번호 없이 저장하면 서버의 비밀번호 필요 문구를 보인다` |
| IN-069 | 화면: AD 입력 칸은 정확히 7개이고 폐지된 칸이 없으며 새 폼 기본값은 SSL·636·기본 필터·5초다 | IN-R30, IN-UC4 | frontend | `features/admin/integrations/IntegrationsPage.fields.test.tsx > 입력 칸은 7개와 현재 관리자 비밀번호 칸뿐이고 폐지된 칸이 없으며 새 폼 기본값을 보인다`<br>`shared/directory/DirectoryFields.test.tsx > has the seven inputs plus the admin password confirmation, and none of the removed ones` |
| IN-070 | 화면: 보안 연결을 바꾸면 기본 포트로 바꾸고 직접 쓴 포트는 둔다 | IN-R30 | frontend | `features/admin/integrations/IntegrationsPage.fields.test.tsx > 보안 연결을 바꾸면 기본 포트로 바꾸고 직접 쓴 포트는 둔다` |
| IN-071 | 화면: 보안 연결마다 암호화·인증서 경고를 보인다 | IN-R30 | frontend | `features/admin/integrations/IntegrationsPage.fields.test.tsx > 보안 연결마다 암호화·인증서 경고를 보이고 평문 경고는 없음일 때만 보인다` |
| IN-072 | 화면: 손대지 않은 마스크는 바인드 비밀번호를 보내지 않고 입력한 값은 마스크 글자여도 보낸다 | IN-R31, IN-R35, IN-UC3 | frontend | `features/admin/integrations/IntegrationsPage.fields.test.tsx > 포커스하면 마스크를 비우고 입력 없이 떠나면 마스크로 돌아간다`<br>`shared/directory/DirectoryFields.test.tsx > sends null for the bind password while the mask is untouched`<br>`shared/directory/DirectoryFields.test.tsx > clears the mask when the field is used and sends what is typed`<br>`shared/directory/DirectoryFields.test.tsx > treats a typed mask text as the new password (no string comparison)` |
| IN-073 | 화면: 엔드포인트·계정을 바꾸면 비밀번호 재입력을 요구하고 되돌리면 마스크로 돌아간다 | IN-R31, IN-R32, IN-UC3 | frontend | `shared/directory/DirectoryFields.test.tsx > clears the mask and asks to retype when the %s changes`<br>`shared/directory/DirectoryFields.test.tsx > refuses to save without a new password after the change`<br>`shared/directory/DirectoryFields.test.tsx > saves once the new password is typed`<br>`shared/directory/DirectoryFields.test.tsx > drops the notice when the value is changed back to the saved one before typing` |
| IN-074 | 화면: 사용자 필터·연결 제한 시간만 바꾸면 마스크가 유지된다 | IN-R31, IN-UC3 | frontend | `shared/directory/DirectoryFields.test.tsx > sends null for the bind password while the mask is untouched`<br>`shared/directory/DirectoryFields.test.tsx > keeps the mask when only the user filter or the timeout changes` |
| IN-075 | 화면: 저장된 비밀번호를 읽을 수 없으면 빈 칸과 안내를 보이고 입력 없이는 보내지 않는다 | IN-R31, IN-R32, IN-UC3 | frontend | `features/admin/integrations/IntegrationsPage.fields.test.tsx > 읽을 수 없는 비밀번호는 입력 없이 연결 테스트해도 요청을 보내지 않는다`<br>`shared/directory/DirectoryFields.test.tsx > shows an empty password field and explains that it has to be typed again`<br>`shared/directory/DirectoryFields.test.tsx > refuses to save or test with nothing typed`<br>`shared/directory/DirectoryFields.test.tsx > saves normally once a new password is typed`<br>`shared/directory/DirectoryFields.test.tsx > does not show the notice for a readable credential` |
| IN-076 | 화면: 설정이 없으면 등록 폼을 보이고 바인드 비밀번호 없이는 보내지 않으며 null revision으로 만든다 | IN-R29, IN-R32, IN-UC4 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 설정이 없으면 안내 문구와 등록 폼을 보이고 최초 설정 링크는 없다`<br>`features/admin/integrations/IntegrationsPage.test.tsx > 바인드 비밀번호 없이는 요청을 보내지 않고 입력을 요구한다`<br>`features/admin/integrations/IntegrationsPage.test.tsx > 바인드 비밀번호와 현재 admin 비밀번호를 넣으면 null revision으로 만들어 설정 버전 1을 보인다` |
| IN-077 | 화면: local 모드는 AD 섹션 대신 안내를 보이고 AD 설정을 요청하지 않으며 저장 위치는 그대로다 | IN-R28, IN-UC5 | frontend | `features/admin/integrations/IntegrationsPage.local.test.tsx > AD 설정 섹션 대신 로그인 방식 안내 카드를 보인다`<br>`features/admin/integrations/IntegrationsPage.local.test.tsx > AD 설정을 서버에 요청하지 않는다`<br>`features/admin/integrations/IntegrationsPage.local.test.tsx > 파일 저장 위치 섹션은 그대로 보인다`<br>`features/admin/integrations/IntegrationsPage.local.test.tsx > AD 모드에서는 안내 카드가 없고 AD 섹션이 보인다` |
| IN-078 | 화면: 비밀번호 칸과 AD 칸의 자동 완성 속성 | IN-R30, IN-R33 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 현재 관리자 비밀번호 칸은 current-password, 바인드 비밀번호 칸은 new-password, 나머지 AD 칸은 off다` |
| IN-079 | 화면: AD 오류 문구는 단계별 안내, 모르는 단계는 서버 문구, 429는 시도 문구다 | IN-R34, IN-UC2 | frontend | `shared/directory/messages.test.ts > explains the %s stage with what to check`<br>`shared/directory/messages.test.ts > has a distinct message for each of the six stages`<br>`shared/directory/messages.test.ts > no longer mentions the removed CA certificate or bind template`<br>`shared/directory/messages.test.ts > returns undefined for an unknown or missing stage`<br>`shared/directory/messages.test.ts > shows the %s stage explanation for a failed verification`<br>`shared/directory/messages.test.ts > falls back to the server message when the stage is unknown`<br>`shared/directory/messages.test.ts > explains a too-many-attempts response`<br>`shared/directory/messages.test.ts > shows the server message of other problems such as a missing bind password` |
| IN-080 | 게이트웨이: AD·저장 위치 조회의 404는 null이고 다른 실패는 그대로다 | IN-R35, IN-UC1, IN-UC6 | frontend | `gateway/http/mappers/settings.test.ts > converts the response to camelCase and keeps the read-only Base DN`<br>`gateway/http/settings.test.ts > getDirectory maps the stored settings to camelCase with the read-only Base DN and credential status`<br>`gateway/http/settings.test.ts > getDirectory keeps the unreadable credential status`<br>`gateway/http/settings.test.ts > getDirectory returns null when nothing is registered (404)`<br>`gateway/http/settings.test.ts > getDirectory still reports other failures such as 403`<br>`gateway/http/settings.test.ts > getStorage maps the stored location to camelCase with who changed it`<br>`gateway/http/settings.test.ts > getStorage keeps updatedBy null when the location was registered by the first setup`<br>`gateway/http/settings.test.ts > getStorage returns null when nothing is registered (404)`<br>`gateway/http/settings.test.ts > getStorage still reports other failures such as 403` |
| IN-081 | 게이트웨이: 연결 테스트의 실패 결과는 단계를 가진 422 오류가 된다 | IN-R35, IN-UC2 | frontend | `gateway/http/settings.test.ts > testDirectory posts the settings with the password and resolves with the discovered Base DN`<br>`gateway/http/settings.test.ts > testDirectory turns success=false into a 422 directory-verification-failed with the stage`<br>`gateway/http/settings.test.ts > testDirectory keeps the %s stage of a failed result`<br>`gateway/http/settings.test.ts > testDirectory also accepts the server answering with the problem document` |
| IN-082 | 게이트웨이: 저장·테스트 본문은 입력 7칸과 비밀번호·revision뿐이고 유지면 bind_password 키가 없다 | IN-R35, IN-UC3 | frontend | `gateway/http/mappers/settings.test.ts > converts the seven fields to the snake_case request`<br>`gateway/http/mappers/settings.test.ts > leaves the bind_password key out when the stored password is kept`<br>`gateway/http/mappers/settings.test.ts > never sends the removed fields`<br>`gateway/http/settings.test.ts > saveDirectory puts the settings with the admin password and the expected revision`<br>`gateway/http/settings.test.ts > saveDirectory sends a null admin password when it was left empty`<br>`gateway/http/settings.test.ts > saveDirectory leaves the bind_password key out when the stored password is kept (null)`<br>`gateway/http/settings.test.ts > saveDirectory sends a null expected revision to create the first settings`<br>`gateway/http/settings.test.ts > saveDirectory sends only the seven input fields plus password and revision`<br>`gateway/http/settings.test.ts > testDirectory posts the settings with the password and resolves with the discovered Base DN`<br>`gateway/http/settings.test.ts > testDirectory leaves the bind_password key out when the stored password is kept`<br>`gateway/http/settings.test.ts > saveStorage puts the path and returns the saved location`<br>`gateway/http/settings.test.ts > testStorage posts the path and resolves on 204 without saving` |
| IN-083 | 화면: 저장 위치 섹션은 현재 위치·마지막 수정·수동 이동 안내·예시를 보인다 | IN-R36, IN-UC6 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 저장 위치 섹션은 현재 위치·마지막 수정·수동 이동 안내·예시를 보인다`<br>`features/admin/integrations/IntegrationsPage.test.tsx > 저장 위치가 없으면 설정되지 않았다는 안내와 빈 경로 칸을 보인다`<br>`features/admin/integrations/StorageSection.test.tsx > 운영 기본 위치를 입력 예시로 보이고 개발용 예시는 보이지 않는다` |
| IN-084 | 화면: 저장 위치를 저장하면 서버가 정규화한 경로가 현재 위치가 된다 | IN-R36, IN-UC7 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 저장 위치를 저장하면 서버가 정규화한 경로가 현재 위치가 된다`<br>`features/admin/integrations/StorageSection.test.tsx > 저장한 뒤에는 서버가 정규화한 경로를 현재 위치로 보인다` |
| IN-085 | 화면: 경로 오류는 서버 문구로 보인다 | IN-R36, IN-R23, IN-UC7 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 상대 경로를 저장하면 서버의 절대 경로 문구가 보이고 현재 위치는 그대로다`<br>`features/admin/integrations/StorageSection.test.tsx > 상위 조각(..)이 든 경로는 서버의 절대 경로 문구로 거절되고 현재 위치는 그대로다`<br>`features/admin/integrations/StorageSection.test.tsx > 정규화 뒤 1025자 경로는 서버의 길이 문구로 거절된다` |
| IN-086 | 화면: 쓰기 테스트는 저장하지 않고 성공·실패를 알린다 | IN-R36, IN-R26, IN-UC6 | frontend | `features/admin/integrations/IntegrationsPage.test.tsx > 쓰기 테스트는 저장하지 않고 성공을 알린다`<br>`features/admin/integrations/IntegrationsPage.test.tsx > 쓸 수 없는 경로의 쓰기 테스트는 저장하지 않고 서버 문구를 보인다` |

### IN-001 admin이 AD 설정을 조회하면 접속 정보·Base DN·revision·저장자가 나오고 비밀번호는 없다
- Given 예시 AD 설정이 BOSS 저장으로 revision 1이다
- When BOSS가 `GET /api/v1/settings/directory`를 부른다
- Then 200이고 본문 키는 IN-R16의 11개뿐이며 `bind_credential_status`는 `ok`, `base_dn`은 `DC=corp,DC=example`, `updated_by`는 BOSS이고, `svc-pass`·암호문·`password`가 든 키는 없다

### IN-002 저장된 바인드 비밀번호를 풀 수 없으면 조회 결과는 unreadable이다
- Given 저장된 암호문을 Fake 암호기가 풀 수 없다(키 변경)
- When BOSS가 AD 설정을 조회한다
- Then 200이고 `bind_credential_status`는 `unreadable`이며 나머지 값은 그대로다

### IN-003 AD 설정이 없으면 조회는 404다
- Given AD 설정 행이 없다
- When BOSS가 AD 설정을 조회한다
- Then 404 `not-found`, `detail` "AD 설정을(를) 찾을 수 없습니다: directory"다

### IN-004 연결 테스트가 성공하면 찾은 Base DN을 돌려주고 아무것도 저장하지 않는다
- Given 예시 AD 설정(revision 1)이 있고 Fake AD는 BOSS를 `boss-pass`로 인증한다
- When BOSS가 호스트를 `dc2.corp.example`, 바인드 비밀번호 `new-pass`, `password` `boss-pass`로 연결 테스트한다
- Then 200 `{"success": true, "stage": null, "message": "AD 설정을 확인했습니다", "base_dn": "DC=corp,DC=example"}`이고, AD에는 Base DN 탐색 → BOSS 인증 순서로 갔으며, 저장된 행(호스트·revision 1·암호문·저장자·시각)은 테스트 전과 같다

### IN-005 틀린 admin 비밀번호의 연결 테스트는 오류가 아니라 bind 단계 실패 결과다
- Given 예시 AD 설정이 있다
- When BOSS가 `password` `wrong-pass`로 연결 테스트한다
- Then 200 `success: false`, `stage: "bind"`, `message` "AD 인증에 실패했습니다. 관리자 비밀번호를 확인하세요", `base_dn: null`이고 본문에 `wrong-pass`가 없다

### IN-006 연결 테스트는 실패한 단계를 그 단계 문구로 알린다
- Given Fake AD가 `connect`·`tls`·`service_bind`·`base_dn`(탐색 중) 또는 `search`·`bind`(인증 중) 단계에서 실패하도록 정했다
- When BOSS가 연결 테스트한다
- Then 각각 200 `success: false`이고 `stage`는 그 단계, `message`는 2.8의 서버 문구이며 AD 원인 문구는 없다

### IN-007 Base DN을 찾지 못하면 admin 인증을 하지 않는다
- Given Fake AD의 Base DN 탐색이 `service_bind`에서 실패한다
- When BOSS가 연결 테스트한다
- Then 결과 `stage`는 `service_bind`이고 Fake AD의 인증 호출은 0회다

### IN-008 바인드 비밀번호를 생략하거나 null로 보내면 저장된 비밀번호를 쓴다
- Given 예시 AD 설정(바인드 비밀번호 `svc-pass`)이 있다
- When BOSS가 같은 접속 정보로 `bind_password`를 생략(또는 `null`)하고 연결 테스트·저장한다
- Then AD 탐색에 쓰인 바인드 비밀번호는 `svc-pass`이고, 저장한 경우 암호문을 풀면 여전히 `svc-pass`다

### IN-009 새 바인드 비밀번호로 연결 테스트해도 저장된 비밀번호는 그대로다
- Given 예시 AD 설정이 있다
- When BOSS가 `bind_password` `new-pass`로 연결 테스트한다
- Then AD 탐색에 `new-pass`가 쓰이고, 저장된 암호문을 풀면 `svc-pass`이며 응답에 `new-pass`가 없다

### IN-010 엔드포인트·계정을 바꾸고 바인드 비밀번호를 생략하면 AD를 부르기 전에 422다
- Given 예시 AD 설정이 있다
- When BOSS가 `host`·`port`·`security`·`bind_account` 중 하나만 바꾸고 `bind_password` 없이 저장(또는 연결 테스트)한다
- Then 422 `invalid-value` "bind_password: 서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다"이고 Fake AD 호출은 0회, 저장된 행은 그대로다. 호스트를 대문자로만 바꾼 값(`DC1.corp.example`)은 같은 엔드포인트로 보아 통과한다

### IN-011 사용자 필터·연결 제한 시간만 바꾸면 바인드 비밀번호가 유지된다
- Given 예시 AD 설정이 있다
- When BOSS가 `user_filter`를 `(&(objectClass=person)(uid={login_id}))`, `connect_timeout_seconds`를 10으로 바꾸고 `bind_password` 없이 저장한다
- Then 200이고 새 필터·10초가 저장되며 암호문을 풀면 `svc-pass`다

### IN-012 AD 설정이 없을 때 바인드 비밀번호를 생략하면 422다
- Given AD 설정이 없다
- When BOSS가 `expected_revision: null`로 `bind_password`를 생략(또는 `null`)해 저장하거나 연결 테스트한다
- Then 422 `invalid-value` "bind_password: 바인드 비밀번호를 입력하세요"이고 AD를 부르지 않으며 행이 생기지 않는다

### IN-013 저장된 비밀번호를 풀 수 없으면 생략은 422이고 새 비밀번호는 통과한다
- Given 예시 AD 설정의 암호문을 풀 수 없다
- When BOSS가 `bind_password` 없이 저장한다
- Then 422 `invalid-value` "bind_password: 저장된 비밀번호를 읽을 수 없습니다. 다시 입력하세요"이고, 이어서 `bind_password` `new-pass`로 저장하면 200이며 조회 결과 `bind_credential_status`는 `ok`다

### IN-014 현재 admin 비밀번호 없이 저장·테스트하면 탐색 전에 422다
- Given 예시 AD 설정이 있다
- When BOSS가 `password`를 생략(또는 `null`)하고 저장 또는 연결 테스트한다
- Then 422 `invalid-value` "AD 설정을 확인하려면 현재 관리자의 비밀번호가 필요합니다"이고 Fake AD의 탐색·인증 호출은 0회이며 설정은 그대로다

### IN-015 형식이 틀린 현재 admin 비밀번호는 AD를 부르지 않고 422다
- When BOSS가 `password`를 `""`, `"   "`, NUL이 든 값, 257자 값으로 저장한다
- Then 각각 422 `invalid-value`("비밀번호는 비어 있을 수 없습니다" / "비밀번호에는 NUL 문자를 쓸 수 없습니다" / "비밀번호는 256자를 넘을 수 없습니다")이고 AD를 부르지 않는다

### IN-016 형식이 틀린 접속 정보는 필드 이름이 든 422이고 AD를 부르지 않으며 아무것도 바뀌지 않는다
- Given 예시 AD 설정이 있다
- When BOSS가 `port` 0, `bind_account` 빈 값, `user_filter` `(uid=x)`, `connect_timeout_seconds` 31, `host` `ldaps://dc1` 중 하나로 저장(또는 연결 테스트)한다
- Then 422 `invalid-value`이고 `detail`에 해당 필드 이름(`port`·`bind_account`·`user_filter`·`connect_timeout_seconds`·`host`)이 있으며 AD 호출 0회, 저장된 행은 그대로다

### IN-017 호스트는 이름·IPv4·IPv6만 받아 소문자로 맞추고 URL·포트·경로는 거절한다
- When `DC1.Corp.Example`, `10.0.0.5`, `FE80::1`, 253자 이름, 그리고 `ldaps://dc1`, `dc1:636`, `dc1/path`, `[fe80::1]`, `-dc1`, `999.1.1.1`, 빈 값, 254자 이름으로 접속 정보를 만든다
- Then 앞의 넷은 `dc1.corp.example`, `10.0.0.5`, `fe80::1`, 그대로로 받아지고 뒤의 값들은 `host: `로 시작하는 IN-R2 문구로 거절된다

### IN-018 사용자 필터는 {login_id} 한 번과 바깥 괄호 짝을 요구한다
- When `user_filter`로 `(&(objectClass=user)(sAMAccountName={login_id}))`, `(uid={login_id})`, `(uid=x)`, `(uid={login_id})(cn={login_id})`, `(uid={login_id}{x})`, `uid={login_id}`, `(uid={login_id}`, `(a)(uid={login_id})`, 513자 값, 제어문자가 든 값을 쓴다
- Then 앞의 둘은 받고, 나머지는 각각 `{login_id}` 문구·괄호 문구·길이 문구·제어문자 문구로 거절된다

### IN-019 포트·연결 제한 시간·바인드 계정의 경계값
- When `port` 0·1·65535·65536, `connect_timeout_seconds` 0·1·30·31, `bind_account` 256자·257자·`CN=svc,OU=x`·`svc@corp.example`·`CORP\svc`로 접속 정보를 만든다
- Then 1·65535, 1·30, 256자와 세 계정 형식은 받고, 0·65536, 0·31, 257자는 IN-R3·IN-R6·IN-R4 문구로 거절된다. 생략한 `connect_timeout_seconds`는 5다

### IN-020 빈 문자열·공백만·NUL·257자 바인드 비밀번호는 유지가 아니라 422다
- Given 예시 AD 설정이 있다
- When BOSS가 `bind_password`를 `""`, `"   "`, NUL이 든 값, 257자 값으로 저장한다
- Then 각각 422 `invalid-value`이고 문구는 `bind_password: `로 시작하며 AD를 부르지 않는다. 앞뒤 공백이 있는 256자 값은 공백을 지우지 않고 그대로 받는다

### IN-021 폐지된 필드·모르는 필드·필수 누락·타입 오류는 422 request-validation이다
- When BOSS가 저장 본문에 `base_dn`·`server_urls`·`bind_template`·`ca_pem`·`foo`를 더하거나, `host`를 빼거나, `expected_revision` 키를 빼거나, `port`를 `"636"`·`636.0`·`true`로, `security`를 `"tls"`로, `expected_revision`을 0·`"1"`로 보낸다. 또 연결 테스트 본문에 `expected_revision`을 넣는다
- Then 모두 422 `request-validation`이고 AD를 부르지 않는다

### IN-022 admin이 자기 비밀번호로 저장하면 새 설정·Base DN·저장자가 기록되고 revision이 오른다
- Given 예시 AD 설정(revision 1, 저장자 없음)이 있고 서버 시계가 `2026-11-09T01:00:00Z`다
- When BOSS가 호스트 `dc2.corp.example`, 바인드 비밀번호 `new-pass`, `password` `boss-pass`, `expected_revision` 1로 저장한다
- Then 200이고 응답과 이후 조회 모두 호스트 `dc2.corp.example`, `base_dn` `DC=corp,DC=example`, `revision` 2, `updated_by` BOSS, `updated_at` `2026-11-09T10:00:00+09:00`이다. AD 인증은 BOSS 로그인 아이디 `boss`와 찾은 Base DN으로 했다

### IN-023 저장할 때마다 revision이 1씩 오른다
- Given 예시 AD 설정이 revision 1이다
- When BOSS가 받은 revision으로 두 번 연속 저장한다
- Then revision은 2, 3이다

### IN-024 이미 바뀐 revision으로 저장하면 AD를 부르지 않고 409다
- Given AD 설정이 revision 2다
- When BOSS가 `expected_revision` 1로 저장한다
- Then 409 `invalid-state` "설정이 다른 곳에서 바뀌었습니다. 새로고침 후 다시 시도하세요"이고 AD 탐색·인증 0회, 설정은 그대로다

### IN-025 설정이 있는데 null revision으로 저장하면 409다
- Given 예시 AD 설정이 있다
- When BOSS가 `expected_revision: null`로 저장한다
- Then 409 `invalid-state`이고 설정은 그대로다

### IN-026 설정이 없는데 정수 revision으로 저장하면 404다
- Given AD 설정이 없다
- When BOSS가 `expected_revision` 1로 저장한다
- Then 404 `not-found` "AD 설정을(를) 찾을 수 없습니다: directory"이고 행이 생기지 않는다

### IN-027 설정이 없을 때 null revision으로 저장하면 revision 1로 만들어진다
- Given AD 설정이 없고 BOSS는 대체 로그인으로 들어왔다
- When BOSS가 7칸(바인드 비밀번호 포함)과 `password`, `expected_revision: null`로 저장한다
- Then 200이고 revision 1, `updated_by` BOSS, 찾은 Base DN이 저장된다

### IN-028 확인이 단계별로 실패하면 저장은 422와 그 단계이고 설정은 그대로다
- Given 예시 AD 설정(또는 설정 없음)이 있고 Fake AD가 `connect`·`tls`·`service_bind`·`base_dn`·`search`·`bind` 중 한 단계에서 실패한다
- When BOSS가 저장한다
- Then 422 `directory-verification-failed`, 본문 `stage`는 그 단계, `detail`은 2.8 서버 문구이고, 기존 설정은 그대로(설정이 없었으면 행이 생기지 않음)다

### IN-029 틀린 admin 비밀번호로 저장하면 bind 단계 422이고 실패 1회가 남는다
- Given 예시 AD 설정이 있다
- When BOSS가 `password` `wrong-pass`로 저장한다
- Then 422 `directory-verification-failed` `stage: "bind"`이고 응답에 `wrong-pass`가 없으며 설정은 그대로, BOSS의 시도 제한 실패 횟수가 1 늘었다

### IN-030 실패 한도를 채운 admin의 저장·테스트는 429이고 admin 바인드를 하지 않는다
- Given BOSS가 틀린 비밀번호 저장으로 계정 실패 한도(AU)를 채웠다
- When BOSS가 올바른 비밀번호로 저장(또는 연결 테스트)한다
- Then 429 `too-many-attempts`이고 Fake AD의 인증 호출 수는 늘지 않으며 설정은 그대로다

### IN-031 연결 실패는 시도 제한 횟수에 들어가지 않는다
- Given Fake AD 인증이 `connect` 단계(통신 실패)로 실패한다
- When BOSS가 한도보다 많이 연결 테스트한다
- Then 매번 `stage: "connect"` 결과이고 429가 나오지 않으며 BOSS의 실패 횟수는 0이다

### IN-032 바인드 비밀번호는 평문이 아니라 풀면 원래 값이 되는 암호문으로 저장된다
- When BOSS가 바인드 비밀번호 `new-pass`로 저장한다
- Then 저장된 행의 비밀번호 값은 `new-pass`가 아닌 암호문이고 같은 암호기로 풀면 `new-pass`다

### IN-033 새 바인드 비밀번호로 저장하면 암호문이 새 값으로 바뀐다
- Given 예시 AD 설정(암호문 A)이 있다
- When BOSS가 바인드 비밀번호 `next-pass`로 저장한다
- Then 암호문은 A가 아니고 풀면 `next-pass`다

### IN-034 저장·테스트·조회의 성공·오류 응답과 로그에 비밀번호와 암호문이 없다
- Given 예시 AD 설정이 있다
- When BOSS가 새 바인드 비밀번호·admin 비밀번호로 저장 성공, 확인 실패 저장, 연결 테스트 성공·실패, 값 위반 요청, 조회를 한다
- Then 모든 응답 본문과 그동안의 로그 기록에 입력한 두 비밀번호와 저장된 암호문 문자열이 없다. 암호문을 풀 수 없는 설정으로 쓰면 로그에는 값 없는 경고만 남는다

### IN-035 AD 설정을 저장해도 이미 열린 세션은 유지된다
- Given BOSS와 KIM이 로그인해 세션이 있다
- When BOSS가 AD 설정을 저장한다
- Then BOSS·KIM의 세션은 모두 유효해 `GET /auth/me`가 200이다

### IN-036 저장 결과는 조회와 같고 다음 로그인은 저장된 Base DN·비밀번호를 쓴다
- Given BOSS가 바인드 비밀번호 `new-pass`로 저장해 Base DN `DC=corp,DC=example`이 저장되었다
- When KIM이 AD 로그인한다
- Then 조회 결과는 저장 응답과 같고 `/auth/config`의 `directory_login`은 true이며, KIM 로그인의 AD 인증은 저장된 Base DN·`new-pass`로 했고 Base DN 탐색은 다시 하지 않았다

### IN-037 local 모드에서 AD 설정을 저장하면 409이고 AD를 부르지 않으며 행은 그대로다
- Given 인증 방식이 local이고(예전 AD 설정 행이 남아 있을 수 있음)
- When BOSS가 올바른 본문으로 AD 설정을 저장한다
- Then 409 `invalid-state` "AD 연동 모드에서만 쓸 수 있습니다."이고 AD 호출 0회, 행은 그대로다

### IN-038 local 모드에서 연결 테스트도 409다
- Given 인증 방식이 local이다
- When BOSS가 연결 테스트한다
- Then 409 `invalid-state` "AD 연동 모드에서만 쓸 수 있습니다."이고 AD 호출 0회다

### IN-039 local 모드에서 AD 설정 조회는 설정이 없으면 404다
- Given 인증 방식이 local이고 AD 설정이 없다
- When BOSS가 AD 설정을 조회한다
- Then 409가 아니라 404 `not-found`다

### IN-040 연동 설정 6개 경로는 admin만 쓰고 sales·user는 본문 검사 전에 403, 미인증은 401이다
- When KIM(sales)·VIEWER(user)가 2.5의 6개 경로를 (형식이 틀린 본문으로도) 부르고, 로그인하지 않은 방문자가 같은 경로를 부른다
- Then sales·user는 모두 403 `forbidden` "관리자 권한이 필요합니다"이고 저장된 값은 그대로이며, 미인증은 모두 401이다

### IN-041 연동 설정 변경·테스트 요청은 CSRF 헤더가 없으면 403이고 아무것도 바뀌지 않는다
- Given BOSS가 로그인했다
- When `X-Requested-With` 없이 AD 저장·연결 테스트·저장 위치 변경을 부른다
- Then 모두 403 `csrf`이고 AD 호출 0회, AD 설정·저장 위치는 그대로다

### IN-042 AD 설정 API 계약은 입력 7칸·비밀번호 표기·revision·결과 필드를 문서화한다
- When 앱의 openapi 문서를 만든다
- Then IN-R21대로다: 경로별 메서드, 저장 요청 속성 = 7칸+`password`+`expected_revision`(required에 `expected_revision`, `bind_password` 아님), 테스트 요청 = 7칸+`password`, `bind_password`·`password`는 `format: password`·`writeOnly`, 응답에 `password`가 든 속성 없음·`bind_credential_status` enum `ok`·`unreadable`, 테스트 결과 속성 4개, 문서화된 오류 상태

### IN-043 admin이 저장 위치를 조회하면 최초 설정에서 저장한 경로가 나오고 저장자는 비어 있다
- Given 최초 설정으로 `/var/lib/neoine-sales/files`가 저장되었다
- When BOSS가 `GET /api/v1/settings/storage`를 부른다
- Then 200 `{path: "/var/lib/neoine-sales/files", updated_at, updated_by: null}`이다

### IN-044 저장 위치가 없으면 조회는 404다
- Given 저장 위치 행이 없다
- When BOSS가 저장 위치를 조회한다
- Then 404 `not-found` "파일 저장 위치을(를) 찾을 수 없습니다: storage"다

### IN-045 admin이 저장 위치를 바꾸면 새 경로·저장자·서버 시각이 기록되고 다시 조회된다
- Given 저장 위치가 `/data/a`이고 서버 시계가 `2026-11-09T01:00:00Z`다
- When BOSS가 `{"path": "/data/b"}`로 `PUT /api/v1/settings/storage`를 부른다
- Then 200이고 응답과 이후 조회 모두 `path` `/data/b`, `updated_by` BOSS, `updated_at` `2026-11-09T10:00:00+09:00`이다

### IN-046 경로는 앞뒤 공백·중복 슬래시·점 조각·끝 슬래시를 정리해 저장한다
- When BOSS가 `"  /data//files/./x/  "`, `"/"`, `"///"`로 저장한다
- Then 저장된 경로는 각각 `/data/files/x`, `/`, `/`이고, 정규화한 값을 다시 넣어도 같다

### IN-047 절대 경로가 아니거나 ..가 있는 경로는 쓰기 확인 전에 422이고 기존 위치는 그대로다
- Given 저장 위치가 `/data/a`다
- When BOSS가 `""`, `"   "`, `"relative/path"`, `"./files"`, `"/a/../b"`, `"/.."`로 저장한다
- Then 모두 422 `invalid-value` "절대 경로를 입력하세요."이고 쓰기 확인 호출 0회, 저장 위치는 `/data/a`다

### IN-048 정규화한 경로는 1024자까지 받고 1025자는 422다
- When BOSS가 정규화 뒤 1024자인 경로, 1025자인 경로, 한글로 1024자(바이트는 더 큼)인 경로, 중복 슬래시를 빼면 1024자인 1030자 입력으로 저장한다
- Then 1024자·한글 1024자·정리 후 1024자는 받고, 1025자는 422 `invalid-value` "저장 경로는 1024자 이내로 입력하세요."다

### IN-049 NUL이 든 경로는 다른 규칙보다 먼저 422다
- When BOSS가 `"/data/\u0000x"`, `"rel\u0000"`(상대 경로이기도 함)로 저장한다
- Then 둘 다 422 `invalid-value` "저장 경로에는 NUL 문자를 쓸 수 없습니다"다

### IN-050 쓸 수 없는 위치는 원인 없는 고정 문구 422이고 기존 위치는 그대로다
- Given 저장 위치가 `/data/a`이고 Fake 저장소가 `/readonly/x` 쓰기를 OS 오류("Permission denied: /readonly/x")로 실패시킨다
- When BOSS가 `/readonly/x`로 저장한다
- Then 422 `invalid-value` "해당 위치에 쓸 수 없습니다."이고 `detail`에 OS 오류 문구·경로가 없으며 저장 위치는 `/data/a`다

### IN-051 새 위치 디렉터리가 없으면 만들고 확인용 파일은 남기지 않는다
- Given `/tmp/x/new/files` 디렉터리가 없다
- When BOSS가 그 경로로 저장한다
- Then 200이고 디렉터리가 생겼으며 그 안에 파일이 하나도 없다

### IN-052 위치를 바꿔도 기존 파일은 옮기거나 복사하지 않는다
- Given `/data/a`에 첨부 파일이 있다
- When BOSS가 저장 위치를 `/data/b`로 바꾼다
- Then `/data/a`의 파일은 그대로이고 `/data/b`에는 파일이 없다

### IN-053 저장 위치가 없는 시스템에서도 admin이 처음 등록할 수 있다
- Given 저장 위치 행이 없다
- When BOSS가 `/data/a`로 저장한다
- Then 200이고 조회 결과 `path` `/data/a`, `updated_by` BOSS다

### IN-054 쓰기 테스트는 204이고 아무것도 저장하지 않는다
- Given 저장 위치가 `/data/a`다(또는 없다)
- When BOSS가 `{"path": "/data/b"}`로 `POST /api/v1/settings/storage/test`를 부른다
- Then 204(본문 없음)이고 저장 위치는 `/data/a` 그대로(없었으면 여전히 없음)다

### IN-055 쓸 수 없는 위치·형식이 틀린 경로의 쓰기 테스트는 422다
- When BOSS가 `/readonly/x`, `relative`, `/x/../y`로 쓰기 테스트한다
- Then 각각 422 `invalid-value` "해당 위치에 쓸 수 없습니다.", "절대 경로를 입력하세요.", "절대 경로를 입력하세요."이고 형식 오류는 쓰기 확인을 하지 않는다

### IN-056 저장 위치 요청은 path 하나만 받고 길이·빈 값은 도메인 문구로 거절한다
- When BOSS가 `{}`, `{"path": 1}`, `{"path": null}`, `{"path": "/a", "x": 1}`, 그리고 `{"path": ""}`, 2000자 경로로 저장한다
- Then 앞의 넷은 422 `request-validation`, 뒤의 둘은 422 `invalid-value`(각각 "절대 경로를 입력하세요.", "저장 경로는 1024자 이내로 입력하세요.")다

### IN-057 local 모드에서도 저장 위치를 그대로 조회·변경한다
- Given 인증 방식이 local이고 저장 위치가 `/data/a`다
- When BOSS가 저장 위치를 조회하고 `/data/b`로 바꾼다
- Then 조회 200, 변경 200이다

### IN-058 저장 위치 API 계약은 경로·메서드·204·요청·응답 필드를 문서화한다
- When 앱의 openapi 문서를 만든다
- Then IN-R27대로다: `/settings/storage` GET·PUT, `/storage/test` POST, 테스트 204에 본문 스키마 없음, 요청 속성 `path` 하나, 응답 속성 `path`·`updated_at`·`updated_by`(nullable), 문서화된 오류 상태

### IN-059 화면: AD 모드에서 저장된 설정을 폼에 보이고 Base DN은 읽기 전용 텍스트, 비밀번호는 마스크다
- Given AD 모드이고 예시 AD 설정이 있다
- When BOSS가 `/admin/integrations`를 연다
- Then 7칸에 저장 값이 보이고, 바인드 비밀번호 칸 값은 `********`, "Base DN(AD에서 자동 확인): DC=corp,DC=example"은 입력 칸이 아닌 텍스트다

### IN-060 화면: 마지막 수정자·시각과 설정 버전을 보인다
- Given AD 설정을 BOSS가 저장했고 revision 3이다
- When 외부연동 화면을 연다
- Then "마지막 수정: <BOSS 표시> · <formatDateTime(updated_at)>"과 "설정 버전 3"이 보인다

### IN-061 화면: AD 설정을 불러오지 못하면 문구 배너를 보인다
- Given AD 설정 조회가 500 Problem("설정을 불러오지 못했습니다")으로 실패한다
- When 외부연동 화면을 연다
- Then 그 문구의 오류 배너가 보이고 AD 폼은 없다

### IN-062 화면: 저장하면 저장했습니다와 함께 설정 버전·마지막 수정이 바뀐다
- Given 예시 AD 설정(revision 1)이 보인다
- When 현재 admin 비밀번호를 넣고 "저장"을 누른다
- Then "저장했습니다"가 보이고 "설정 버전 2"와 새 마지막 수정이 보인다

### IN-063 화면: 저장·테스트는 현재 admin 비밀번호와 읽은 revision을 보내고, 비면 null을 보낸다
- Given 예시 AD 설정(revision 1)이 보인다
- When 현재 admin 비밀번호 `boss-pass`로 "저장"·"연결 테스트"를 누르고, 비밀번호 칸을 비운 채 한 번 더 "저장"을 누른다
- Then 저장 요청에는 `password: "boss-pass"`, `expected_revision: 1`, 테스트 요청에는 `password: "boss-pass"`가 실리고(테스트는 저장하지 않음), 빈 칸일 때는 `password: null`이다. 현재 admin 비밀번호 칸은 password 형식이고 안내 "현재 관리자(본인) 비밀번호를 입력하세요."가 보인다

### IN-064 화면: 요청이 끝나면 성공·실패 모두 비밀번호 칸들을 비운다
- Given 바인드 비밀번호와 현재 admin 비밀번호를 입력했다
- When 저장이 성공하거나 연결 테스트가 실패한다
- Then 현재 admin 비밀번호 칸은 비고, 바인드 비밀번호 칸은 마스크(유지 가능한 상태)로 돌아가 입력한 값이 화면에 남지 않는다

### IN-065 화면: 연결 테스트는 저장하지 않고 찾은 Base DN을 보인다
- Given 예시 AD 설정이 보인다
- When 호스트를 바꾸고 바인드 비밀번호·현재 admin 비밀번호를 넣어 "연결 테스트"를 누른다
- Then "연결 테스트에 성공했습니다. Base DN: DC=corp,DC=example"이 보이고 설정 버전은 그대로다

### IN-066 화면: 연결 테스트가 실패하면 실패 단계 안내를 보인다
- Given 연결 테스트 결과가 `success: false, stage: "connect"`다
- When "연결 테스트"를 누른다
- Then "AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요."가 오류 알림으로 보인다

### IN-067 화면: 다음 동작을 시작하면 이전 결과를 지운다
- Given 이전 연결 테스트의 실패 알림이 보인다
- When 다시 "연결 테스트"(또는 "저장")를 누른다
- Then 새 요청이 끝나기 전에 이전 알림이 사라진다

### IN-068 화면: 서버의 값 오류 문구를 그대로 보인다
- Given 저장 요청이 422 `invalid-value` "user_filter은(는) 괄호로 감싸야 하고 괄호 짝이 맞아야 합니다"로 실패한다
- When "저장"을 누른다
- Then 그 문구가 오류 알림으로 보인다(화면이 미리 막지 않는다)

### IN-069 화면: AD 입력 칸은 정확히 7개이고 폐지된 칸이 없으며 새 폼 기본값은 SSL·636·기본 필터·5초다
- Given AD 설정이 없다
- When 외부연동 화면의 등록 폼을 본다
- Then 입력 칸은 호스트·포트·보안 연결·바인드 계정·바인드 비밀번호·사용자 검색 필터·연결 제한 시간(초)뿐이고(Base DN·서버 URL·바인드 템플릿·CA 인증서 칸 없음), 보안 연결 선택지는 없음·SSL·StartTLS, 기본값은 SSL·636·`(&(objectClass=user)(sAMAccountName={login_id}))`·5·빈 비밀번호다. 설정이 있을 때도 7칸 + 현재 admin 비밀번호 칸뿐이다

### IN-070 화면: 보안 연결을 바꾸면 기본 포트로 바꾸고 직접 쓴 포트는 둔다
- When SSL(636)에서 StartTLS로, 포트를 비운 뒤 없음으로, 포트를 10636으로 쓴 뒤 StartTLS로 바꾼다
- Then 포트는 389, 389, 10636이다

### IN-071 화면: 보안 연결마다 암호화·인증서 경고를 보인다
- When 보안 연결을 없음, SSL, StartTLS로 고른다
- Then 각각 IN-R30의 세 경고 문구가 보이고, 평문 경고는 없음일 때만 보인다

### IN-072 화면: 손대지 않은 마스크는 바인드 비밀번호를 보내지 않고 입력한 값은 마스크 글자여도 보낸다
- Given 예시 AD 설정이 보인다
- When 바인드 비밀번호 칸을 건드리지 않고 저장하고, 다음엔 칸에 포커스해 `********`를 직접 입력해 저장한다
- Then 첫 요청 본문에는 `bind_password` 키가 없고, 포커스하면 칸이 비며, 두 번째 요청은 `bind_password: "********"`를 보낸다. 입력 없이 칸을 떠나면 마스크로 돌아간다

### IN-073 화면: 엔드포인트·계정을 바꾸면 비밀번호 재입력을 요구하고 되돌리면 마스크로 돌아간다
- Given 예시 AD 설정이 보인다
- When 호스트를 `dc2.corp.example`로 바꾸고 바인드 비밀번호 없이 "저장"을 누른 뒤, 호스트를 원래 값으로 되돌린다
- Then 바꾼 순간 칸이 비고 "서버나 바인드 계정을 바꿨으므로 비밀번호를 다시 입력하세요."가 보이며, 저장은 요청 없이 "바인드 비밀번호를 입력하세요"로 막히고, 되돌리면 마스크와 "그대로 두면 저장된 비밀번호를 씁니다."로 돌아간다. 새 비밀번호를 입력하면 저장 요청이 간다

### IN-074 화면: 사용자 필터·연결 제한 시간만 바꾸면 마스크가 유지된다
- Given 예시 AD 설정이 보인다
- When 사용자 검색 필터와 연결 제한 시간만 바꿔 저장한다
- Then 바인드 비밀번호 칸은 계속 마스크이고 요청에 `bind_password` 키가 없다

### IN-075 화면: 저장된 비밀번호를 읽을 수 없으면 빈 칸과 안내를 보이고 입력 없이는 보내지 않는다
- Given AD 설정의 `bind_credential_status`가 `unreadable`이다
- When 외부연동 화면에서 바인드 비밀번호 없이 "저장"·"연결 테스트"를 누르고, 이어서 새 비밀번호를 넣어 저장한다
- Then 칸은 비어 있고 "저장된 바인드 비밀번호를 읽을 수 없습니다. 다시 입력하세요."가 보이며, 앞의 둘은 요청 없이 "바인드 비밀번호를 입력하세요"이고 새 비밀번호로는 저장된다. 읽을 수 있는 설정에는 이 안내가 없다

### IN-076 화면: 설정이 없으면 등록 폼을 보이고 바인드 비밀번호 없이는 보내지 않으며 null revision으로 만든다
- Given AD 모드이고 AD 설정이 없다(GET 404)
- When 외부연동 화면을 열고, 바인드 비밀번호 없이 "저장"을 누른 뒤, 바인드 비밀번호·현재 admin 비밀번호를 넣고 "저장"을 누른다
- Then "AD 서버가 아직 설정되지 않았습니다. 아래에서 등록하세요."와 등록 폼(최초 설정 링크 아님)이 보이고, 첫 시도는 요청 없이 "바인드 비밀번호를 입력하세요", 두 번째는 `expected_revision: null`과 `password`로 요청해 "저장했습니다"와 "설정 버전 1"이 보인다

### IN-077 화면: local 모드는 AD 섹션 대신 안내를 보이고 AD 설정을 요청하지 않으며 저장 위치는 그대로다
- Given 인증 방식이 local이다
- When BOSS가 외부연동 화면을 연다
- Then "로그인 방식" 안내 카드가 보이고 "AD(LDAP) 서버 설정" 섹션은 없으며 AD 설정 조회 요청은 0회이고, 파일 저장 위치 섹션은 보인다. AD 모드에서는 안내 카드가 없고 AD 섹션이 보인다

### IN-078 화면: 비밀번호 칸과 AD 칸의 자동 완성 속성
- When 외부연동 화면의 AD 폼을 본다
- Then 현재 admin 비밀번호 칸은 `autocomplete="current-password"`, 바인드 비밀번호 칸은 `type=password`·`autocomplete="new-password"`, 나머지 AD 칸은 `autocomplete="off"`다

### IN-079 화면: AD 오류 문구는 단계별 안내, 모르는 단계는 서버 문구, 429는 시도 문구다
- When `directoryErrorMessage`에 여섯 단계의 `directory-verification-failed` 오류, 모르는 단계의 같은 오류(`detail` "X"), 429 오류, 422 `invalid-value`("bind_password: 바인드 비밀번호를 입력하세요")를 넣는다
- Then 각각 2.8 화면 문구 여섯 개(서로 다름, CA 인증서·바인드 템플릿 언급 없음), "X", "시도가 너무 많습니다. 잠시 후 다시 시도하세요.", 서버 문구다

### IN-080 게이트웨이: AD·저장 위치 조회의 404는 null이고 다른 실패는 그대로다
- Given 서버가 GET `/settings/directory`·`/settings/storage`에 404 또는 403을 준다
- When HTTP 게이트웨이로 조회한다
- Then 404는 `null`로 끝나고 403은 `ApiError` 403으로 reject된다. 200이면 camelCase 값(`bindCredentialStatus`, 읽기 전용 `baseDn`, 저장자 `updatedBy` 또는 null)을 돌려준다

### IN-081 게이트웨이: 연결 테스트의 실패 결과는 단계를 가진 422 오류가 된다
- Given 서버가 `POST /settings/directory/test`에 200 `{success: false, stage: "search", message: "사용자 조회에 실패했습니다. 사용자 필터를 확인하세요", base_dn: null}`을 준다
- When HTTP 게이트웨이로 연결 테스트한다
- Then `ApiError` 422, kind `directory-verification-failed`, `stage` `search`, 문구 = 서버 `message`로 reject된다. `success: true`면 `{baseDn}`으로 끝나고, 서버가 422 Problem을 주어도 같은 kind로 받는다

### IN-082 게이트웨이: 저장·테스트 본문은 입력 7칸과 비밀번호·revision뿐이고 유지면 bind_password 키가 없다
- When HTTP 게이트웨이로 바인드 비밀번호 `null`(유지)과 `"p"`로 저장·테스트한다
- Then 저장 본문 키는 `host`·`port`·`security`·`bind_account`·(`bind_password`)·`user_filter`·`connect_timeout_seconds`·`password`·`expected_revision`뿐이고, 테스트 본문은 `expected_revision`이 없으며, 유지일 때는 `bind_password` 키 자체가 없다. 저장 위치 저장은 `{path}`를 PUT하고, 쓰기 테스트는 `{path}`를 POST해 204로 끝난다

### IN-083 화면: 저장 위치 섹션은 현재 위치·마지막 수정·수동 이동 안내·예시를 보인다
- Given 저장 위치가 `/data/a`이고 최초 설정으로 저장되었다(저장자 없음)
- When 외부연동 화면을 연다
- Then "현재 위치: /data/a", "마지막 수정: - · <시각>", 수동 이동 안내, "저장 경로" 칸 값 `/data/a`, 예시 "예: /var/lib/neoine-sales/files"가 보인다. 위치가 없으면 "아직 저장 위치가 설정되지 않았습니다."와 빈 칸이 보인다

### IN-084 화면: 저장 위치를 저장하면 서버가 정규화한 경로가 현재 위치가 된다
- When 저장 경로에 `" /data//b/ "`를 넣고 "저장"을 누른다
- Then "저장했습니다"와 "현재 위치: /data/b"가 보인다

### IN-085 화면: 경로 오류는 서버 문구로 보인다
- When 저장 경로에 `relative/path`, `/a/../b`, 정규화 뒤 1025자 경로를 넣고 "저장"을 누른다
- Then 각각 "절대 경로를 입력하세요.", "절대 경로를 입력하세요.", "저장 경로는 1024자 이내로 입력하세요."가 오류 알림으로 보이고 현재 위치는 그대로다

### IN-086 화면: 쓰기 테스트는 저장하지 않고 성공·실패를 알린다
- Given 저장 위치가 `/data/a`다
- When 저장 경로에 `/data/b`를 넣고 "쓰기 테스트"를 누르고, 이어서 쓸 수 없는 경로로 "쓰기 테스트"를 누른다
- Then 첫 번째는 "쓰기 테스트에 성공했습니다."이고 현재 위치는 `/data/a` 그대로, 두 번째는 "해당 위치에 쓸 수 없습니다."다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(초안): 구현된 AD 서버·저장 위치 설정 동작을 정본 명세로 옮김. 규칙 IN-R1~R36, use case IN-UC1~UC7, BDD 케이스 IN-001~IN-086 | IN-001~IN-086(신규) |
