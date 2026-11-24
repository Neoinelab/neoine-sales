# 내 정보   (feature 코드: ME, 상태: 확정(2026-11-24 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/web/routers/me.py`, `web/schemas/{me,profile_changes,password_field}.py`, `web/error_handlers.py`, `application/account/{get_my_profile,update_my_profile,change_my_password}.py`, `application/user/profile_edit.py`, `application/auth/{messages,throttle,mode}.py`, `domain/user/{profile,entities,messages}.py`, `domain/auth/{credentials,password_policy,errors}.py`, `domain/common/{contact,validation}.py`, `frontend/src/shared/ui/{UserMenu,Layout}.tsx`, `features/account/{MyProfilePage,ProfileForm,PasswordForm}.tsx`, `data/me.ts`, `gateway/http/{me.ts,mappers/user.ts}`)와 이전 계획 `artifacts/10-analysis/local-accounts-plan.md`(2026-11-02 사용자 결정 Q1~Q8)입니다. 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake 게이트웨이 문구가 다른 곳은 코드(backend)를 따랐습니다(계획 `artifacts/10-analysis/me-plan.md`의 확인 필요 질문 참고).

## 1. 개요

- 목적: 로그인한 사용자가 상단 바의 사용자 메뉴에서 자기 정보를 보고, 아이디·역할을 뺀 자기 정보(이름·이메일·전화)와 비밀번호(앱 계정 모드)를 스스로 고친다.
- 사용자(역할): 로그인한 모든 역할(`admin`·`sales`·`user`). 조회 전용 `user`도 자기 정보는 고칠 수 있다.
- 범위
  - 상단 바 오른쪽 사용자 아이콘 메뉴(이름(역할), 내 정보, 로그아웃 항목)
  - `/me` 화면(기본 정보 카드, 비밀번호 변경 카드)
  - `GET /api/v1/me/profile`, `PATCH /api/v1/me/profile`, `PUT /api/v1/me/password`
  - 내 정보 HTTP 게이트웨이(`gateway.me`)와 데이터 훅(`useMyProfile`·`useUpdateMyProfile`·`useChangeMyPassword`)
- 범위 밖(다른 feature)
  - 인증 방식(`ad`/`local`)을 고르고 저장하는 일 → SU. 이 문서는 저장된 방식을 읽기만 한다
  - 로그인·세션 발급·요청마다 활성·역할 재확인·`/auth/me` 응답·로그아웃 동작·로그인 시도 제한 정책(한도·잠금 시간) → AU
  - admin이 다른 사용자의 정보 수정·비밀번호 재설정 → US (프로필 값 검증 규칙은 이 문서와 같은 코드를 공유한다: ME-R6·ME-R7)
  - 라우트 가드(`RequireAuth`)·CSRF 헤더·Problem 형식·NUL 공통 처리·전체 경로 권한 표 → PL(PL-R2·PL-R6·PL-R16·PL-R29·PL-R33)
  - 경쟁·동시성(확인하는 사이 퇴사·비밀번호 변경) 테스트 → 만들지 않음(규칙만 ME-R13에 적음)
- 관련 화면·메뉴: 상단 바 오른쪽 사용자 아이콘(`aria-label="사용자 메뉴"`), `/me`(제목 "내 정보"). 주 메뉴 항목은 없다.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 내 정보 | 로그인한 사용자 자신의 사용자 행(`users`)의 아이디·역할·이름·이메일·전화 |
| 인증 방식(모드) | 시스템 전역 하나: `local`(앱에서 계정을 직접 관리) 또는 `ad`(AD 연동). 저장 행이 없으면 기존 시스템(admin 또는 AD 설정이 있음)은 `ad`로 본다(`current_mode`, SU 소유). 이 문서에서 "AD 모드"는 `ad` 또는 미선택을 뜻한다 |
| 수정 가능 여부(`editable`) | 항목별로 고칠 수 있는지 서버가 알려 주는 값(`display_name`·`email`·`phone`·`password`) |
| PATCH 의미 | 보낸 키만 바꾸고, 보내지 않은 키는 그대로, `null`(또는 빈 값)은 비운다 |
| 현재 세션 | 비밀번호 변경 요청의 세션 쿠키(`SESSION_COOKIE`) 토큰에 해당하는 세션 |
| 시도 제한 | 로그인과 같은 `LoginThrottle` 카운터(아이디별·IP별 실패 수, AU 소유) |

### 2.2 데이터 모델

새 테이블·컬럼 없음, 마이그레이션 없음. 읽고 쓰는 저장 데이터:

- `users`: `display_name`(최대 200자, NULL 가능), `email`(NULL 가능), `phone`(NULL 가능), `login_id`·`role`(읽기만), `deleted_at`(퇴사 여부, 읽기만), `updated_at`(값이 바뀔 때만 갱신).
- `user_password_hashes`: 사용자별 비밀번호 해시 1행(scrypt, AU·US·SU와 공유). 비밀번호 변경이 덮어쓴다.
- `auth_sessions`: 비밀번호 변경 성공 시 같은 사용자의 현재 세션이 아닌 행을 지운다.
- `login_failures`: 현재 비밀번호 확인의 실패 카운터(AU와 공유).
- `auth_settings`: 인증 방식(읽기만).

값 정의:

- `MyProfile`(application, frozen): `user`, `mode`(실효 방식, 없으면 `ad`), `can_edit_name_email`(= `mode == local`), `can_change_password`(= `mode == local`).
- `ProfileChanges`(domain, frozen): `display_name`·`email`·`phone` 각각 `UNSET`(보내지 않음) | `None`(비움) | 문자열.
- `MyProfileResponse`(web): `id: int`, `login_id: str`, `role: "admin"|"sales"|"user"`, `display_name: str|null`, `email: str|null`, `phone: str|null`, `auth_mode: "ad"|"local"`, `editable: {display_name: bool, email: bool, phone: bool, password: bool}`(네 키 모두 required).
- `MyProfileRequest`(web, 알 수 없는 키 금지): `display_name?: str|null`, `email?: str|null`, `phone?: str|null`(모두 선택).
- `MyPasswordRequest`(web, 알 수 없는 키 금지): `current_password: SecretStr`(최대 256자), `new_password: SecretStr`(최대 256자), 둘 다 필수.
- 프런트 `MyProfile`(`shared/model/types.ts`): `{ id, loginId, role, name /* display_name ?? login_id */, email, phone, authMode, editable: { name, email, phone, password } }`, `ProfileChange`: `{ name?: string, email?: string|null, phone?: string|null }`.

### 2.3 비즈니스 규칙

사용자 메뉴(frontend)
- **ME-R1** 로그인 후 공통 레이아웃의 상단 바 오른쪽에 사용자 아이콘 버튼(`aria-label="사용자 메뉴"`, `aria-haspopup="menu"`, 닫힘이면 `aria-expanded="false"`, svg 아이콘)이 모든 역할에게 보인다. 이름 텍스트와 로그아웃 버튼을 상단 바에 따로 두지 않는다. 버튼을 누르면 메뉴(`role="menu"`, `aria-label="사용자"`)가 열리고 첫 항목에 포커스가 가며, 메뉴에는 위에서부터 `<이름> (<역할>)` 문구(`/auth/me`의 이름과 역할 값 그대로, 예: `김영업 (sales)`)와 메뉴 항목(`role="menuitem"`) `내 정보`, `로그아웃` 두 개가 이 순서로 있다. Esc를 누르면 닫히고 포커스가 아이콘 버튼으로 돌아간다. 메뉴 바깥을 누르거나 아이콘을 다시 누르면 닫힌다. `내 정보`는 `/me`로 이동하고 `로그아웃`은 로그아웃(AU) 뒤 `/login`으로 이동하며, 항목을 고르면 메뉴가 닫히고 열려 있던 모바일 상단 메뉴도 접힌다. 모바일 메뉴(`메뉴 열기`)를 연 상태에서도 같은 메뉴를 쓴다.

내 정보 조회
- **ME-R2** `/me` 화면과 `/me/**` API는 로그인한 모든 역할이 쓴다(PL-R2 "로그인한 모든 역할" 분류, 업무 쓰기 가드 없음 PL-R6). 로그인하지 않으면 API는 401 `unauthenticated`, 화면은 `/login`으로 간다(PL-R29).
- **ME-R3** `GET /api/v1/me/profile`은 요청자 자신의 행을 200 `MyProfileResponse`(키는 정확히 `id`·`login_id`·`role`·`display_name`·`email`·`phone`·`auth_mode`·`editable`)로 준다. `auth_mode`는 실효 인증 방식(저장 행이 없으면 `ad`)이다. `editable`은 local 모드면 네 값 모두 `true`, AD 모드면 `phone`만 `true`이고 `display_name`·`email`·`password`는 `false`다. 응답에 비밀번호·해시는 없다.

내 정보 수정
- **ME-R4** `PATCH /api/v1/me/profile`은 PATCH 의미다: 본문에 있는 키만 바꾸고, 없는 키는 그대로이며, `null`은 그 값을 비운다. 빈 본문 `{}`이나 지금 값과 같은 값만 보내면 아무것도 저장하지 않고(`updated_at` 그대로) 200으로 현재 내 정보를 준다. 성공하면 200으로 바뀐 뒤의 `MyProfileResponse`(ME-R3와 같은 모양)를 준다.
- **ME-R5** 본문 키는 `display_name`·`email`·`phone`만 허용한다. `login_id`·`role`·`id`·`password` 등 다른 키가 있거나 값이 문자열·`null`이 아니면 422 `request-validation`("요청 형식이 올바르지 않습니다")이고 아무것도 바뀌지 않는다. 아이디·역할은 이 경로로 바꿀 수 없다.
- **ME-R6** 값 검증과 정규화(모든 값을 검증한 뒤에 한꺼번에 적용하므로 하나라도 틀리면 아무것도 바뀌지 않는다). 위반은 422 `invalid-value`이며 `detail`은 아래 문구, `errors` 목록은 없다.
  - 이름(`display_name`, local 모드에서만 고칠 수 있음): 앞뒤 공백을 지운다. 비울 수 없다(`""`·공백만·`null` 모두 "이름은(는) 비어 있을 수 없습니다"). 최대 200자("이름은(는) 200자를 넘을 수 없습니다"). NUL 문자는 "이름에는 NUL 문자를 쓸 수 없습니다".
  - 이메일(`email`): `null`·빈 문자열·공백만은 비움(NULL). 앞뒤 공백을 지우고 소문자로 바꾼다. 형식(`로컬@도메인.최상위`, 공백 없음, 최대 254자)이 틀리면 "이메일 형식이 올바르지 않습니다.". NUL 문자는 "이메일에는 NUL 문자를 쓸 수 없습니다".
  - 전화(`phone`): `null`·빈 문자열·공백만은 비움(NULL). 앞뒤 공백을 지운다. 숫자·`+`·`-`·공백·괄호만, 최대 40자, 숫자 7~15개가 아니면 "전화번호 형식이 올바르지 않습니다.". NUL 문자는 "전화번호에는 NUL 문자를 쓸 수 없습니다".
- **ME-R7** AD 모드에서는 이름·이메일이 AD 값이라 고칠 수 없다. 본문에 `display_name`이나 `email` 키가 있으면(값이 `null`이어도, 지금 값과 같아도) 값 검증보다 먼저 409 `invalid-state` "AD 연동 사용자의 이름·이메일은 AD에서 관리합니다."이고 아무것도 바뀌지 않는다. `phone`만 보내면 ME-R6 규칙으로 고친다. 단 AD에 그 사용자의 전화번호가 있으면 다음 AD 로그인 때 AD 값으로 덮어써진다(AU-R8a, AD에 값이 없으면 앱에서 고친 값이 남는다).
- **ME-R8** 수정 대상은 요청자 자신의 행뿐이다. 다른 사용자의 행, 요청자의 아이디·역할은 바뀌지 않는다. 대상 행이 퇴사 처리된 상태면 409 `invalid-state` "이미 퇴사 처리된 사용자입니다"다(판정 순서: 본문 형식 422 → AD 모드 409 → 퇴사 409 → 값 검증 422). 바뀐 이름은 다음 요청의 `/auth/me` 이름부터 보인다(이름 표시 규칙은 AU).

비밀번호 변경
- **ME-R9** `PUT /api/v1/me/password`는 local 모드에서만 쓸 수 있다. AD 모드면 409 `invalid-state` "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."이고 시도 제한 카운터·비밀번호·세션은 그대로다.
- **ME-R10** 판정 순서: ① 본문 형식(키 누락·`null`·257자 이상·알 수 없는 키) → 422 `request-validation` ② `current_password`, `new_password` 순으로 빈 값(공백만 포함)·NUL 문자 → 422 `invalid-value`, `errors: [{"location": ["<필드 이름>"], "message": …}]`("비밀번호는 비어 있을 수 없습니다", "비밀번호에는 NUL 문자를 쓸 수 없습니다") ③ 인증 방식(ME-R9) → 409 ④ 새 비밀번호 정책(ME-R11) → 422 위치 `new_password` ⑤ 시도 제한 잠금 → 429 ⑥ 현재 비밀번호 확인(ME-R12) → 422 위치 `current_password` ⑦ 저장(ME-R13). ①~④에서 거절되면 시도 제한 카운터를 건드리지 않는다.
- **ME-R11** 새 비밀번호 정책: 8자 이상 256자 이하(원문 길이, 앞뒤 공백도 센다), 앞뒤 공백을 지우고 소문자로 바꾼 값이 로그인 아이디와 같으면 거부, 조합 규칙·만료 없음. 위반은 422 `invalid-value`, `errors[0].location = ["new_password"]`, 문구 "비밀번호는 8자 이상이어야 합니다" / "비밀번호는 아이디와 같을 수 없습니다"(마침표 없음). 길이를 먼저 본다.
- **ME-R12** 현재 비밀번호 확인은 로그인과 같은 시도 제한(`LoginThrottle`, 아이디별·IP별 카운터 AU-R14, 집계 AU-R15)을 쓴다. 확인 전에 계정·IP 시도를 1회씩 선점하고(잠겨 있으면 확인 없이 429 `too-many-attempts` "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"), 틀리면 그 선점이 실패 1회로 남아 422 `invalid-value` "현재 비밀번호가 올바르지 않습니다.", `errors[0].location = ["current_password"]`다(401이 아니며 세션은 유지된다). 저장된 해시가 없는 사용자는 같은 계산 비용 뒤 "틀림"과 같다. 맞으면 계정 실패 카운터를 지우고 IP 선점을 되돌린다. 실패 카운터는 로그인과 공유하므로 여기서 한도를 넘으면 로그인도 잠기고 그 반대도 같다.
- **ME-R13** 성공하면 새 해시를 저장하고 204(본문 없음)를 준다. 이후 새 비밀번호로만 로그인되고 이전 비밀번호는 401이다. 요청 쿠키의 세션(현재 세션)은 유지하고 같은 사용자의 다른 세션은 모두 끝낸다(그 세션의 다음 요청은 401). 다른 사용자의 세션은 그대로다. 확인과 해시 계산은 DB 트랜잭션 밖에서 하고, 저장 직전에 사용자가 퇴사했거나 그 사이 비밀번호 해시가 바뀌었으면 401 `unauthenticated` "로그인이 필요합니다"로 저장하지 않는다(경쟁 상황이라 테스트하지 않음).
- **ME-R14** 비밀번호는 요청에만 싣는다. 요청 모델은 마스킹 값(`SecretStr`, repr에 원문이 없음)이고 openapi에서 두 필드는 `format: password`, `writeOnly: true`, `maxLength: 256`이다. 어떤 응답에도 비밀번호·해시가 없다.

API 문서
- **ME-R15** openapi: `/api/v1/me/profile`은 `get`·`patch`, `/api/v1/me/password`는 `put`만 있다. 문서화된 응답은 `GET /me/profile` 200·401, `PATCH /me/profile` 200·401·409·422, `PUT /me/password` 204(본문 없음)·401·409·422·429다. `PATCH` 요청 스키마의 속성은 `display_name`·`email`·`phone`이고 required가 없다. `GET`·`PATCH`의 200 응답은 같은 스키마를 가리키며 `id`는 `integer`, `editable`의 네 속성은 모두 `boolean`·required다.

화면(frontend)
- **ME-R16** `/me` 화면(`MyProfilePage`): 내 정보를 읽는 동안 "불러오는 중…", 실패하면 제목 "내 정보"와 오류 배너(서버 `detail`)만 보인다. 성공하면 제목 "내 정보", 기본 정보 카드(`aria-label="기본 정보"`), 그리고 `editable.password`가 `true`일 때만 비밀번호 변경 카드를 보인다.
- **ME-R17** 기본 정보 카드(`ProfileForm`): 아이디·역할은 읽기 전용 칸(`readonly`)으로 보인다. 이름(서버 이름이 없으면 아이디)·이메일·전화번호 칸은 `editable`이 `false`면 비활성이고, 이름을 고칠 수 없으면(AD 모드) "이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다." 안내를 보인다. 저장할 때 각 칸 값의 앞뒤 공백을 지워 서버 값과 비교하고, **고칠 수 있고 바뀐 칸만** 보낸다(이메일·전화를 비우면 `null`, 이름을 비우면 빈 문자열을 그대로 보내 서버가 거절한다). 바뀐 칸이 없거나 요청 중이면 "저장" 버튼이 비활성이다. 성공하면 칸을 서버 응답 값으로 다시 채우고 "저장했습니다." 안내(닫기 가능, 칸을 고치면 사라짐)를 보이며, 내 정보 캐시를 응답으로 채우고 상단 바 이름(`/auth/me`)·사용자 목록·Deal·Forecast 조회를 새로 읽게 한다(사용자 메뉴에 새 이름이 보임). 실패하면 오류 배너(`role="alert"`)에 서버 `detail`을 그대로 보이고 입력한 값을 유지하며 성공 안내는 없다.
- **ME-R18** 비밀번호 변경 카드(`PasswordForm`, `aria-label="비밀번호 변경"`): "현재 비밀번호"(`autocomplete="current-password"`), "새 비밀번호"·"새 비밀번호 확인"(`autocomplete="new-password"`) 세 칸 모두 `type="password"`이고 버튼은 "비밀번호 변경"(요청 중 비활성)이다. 새 비밀번호와 확인이 다르면 요청을 보내지 않고 `role="alert"`로 "새 비밀번호 확인이 일치하지 않습니다."를 보인다(칸 값은 유지). 길이 등 정책은 화면에서 미리 검사하지 않고 서버 문구를 보인다. 성공하면 세 칸을 비우고 "비밀번호를 바꿨습니다. 다른 기기의 로그인이 종료되었습니다." 안내를 보인다. 실패하면 세 칸을 비우고 오류 배너에 서버 `detail`을 보이며, 서버 `errors[].location`이 `current_password`·`new_password`면 그 칸을 오류 표시한다. 성공·실패 모두 끝나는 즉시 mutation을 비워 입력한 비밀번호가 쿼리 캐시(mutation 변수)에 남지 않는다.
- **ME-R19** HTTP 게이트웨이(`createMeHttp`): `profile()`은 `GET /api/v1/me/profile`을 ME-R3 응답에서 프런트 `MyProfile`로 바꾼다(`display_name` → `name`, 없으면 `login_id`; `editable.display_name` → `editable.name`). `updateProfile(change)`는 `PATCH /api/v1/me/profile`에 준 키만 `display_name`·`email`·`phone`으로 실어 보내고(`null`은 그대로 `null`, `id`·`login_id`·`role`은 보내지 않음) 응답을 같은 방식으로 바꾼다. `changePassword(current, next)`는 `PUT /api/v1/me/password`에 `{current_password, new_password}`를 보내고 204면 `undefined`로 끝난다. 서버 오류는 상태 코드와 `detail`을 그대로 가진 `ApiError`로 넘긴다(409 → `conflict`, 422 → `validation`, 429 → `too-many-attempts`; 현재 비밀번호 틀림 422는 로그아웃으로 다루지 않는다). Fake 게이트웨이도 같은 판정(모드별 수정 가능 여부, PATCH 의미, AD 409, 정책 422, 현재 비밀번호 422)을 따른다.

### 2.4 상태와 전이

상태 전이 없음(사용자 행의 퇴사 상태 전이는 US). 사용자 메뉴는 닫힘 ↔ 열림(아이콘 클릭 / Esc·바깥 클릭·아이콘 재클릭·항목 선택)뿐이다.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /me/profile` | 401 | 가능 | 가능 | 가능 |
| `PATCH /me/profile` | 401 | 가능(자기 행만) | 가능(자기 행만) | 가능(자기 행만) |
| `PUT /me/password` | 401 | local 모드면 가능, AD 모드 409 | 같음 | 같음 |
| 화면 `/me`, 사용자 메뉴 | `/login`으로 | 가능 | 가능 | 가능 |

- 세 경로 모두 업무 쓰기 가드가 없어 `user`도 403이 아니다(PL-R6). 상태 변경 메서드의 CSRF 헤더 검사는 PL 공통이다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/me/profile` | — | 200 `MyProfileResponse` | 401 `unauthenticated` |
| PATCH `/me/profile` | `MyProfileRequest` `{"display_name":"김새이름","phone":"010-9999-8888"}` | 200 `MyProfileResponse` | 401 `unauthenticated`, 409 `invalid-state`(AD 모드 이름·이메일, 퇴사), 422 `invalid-value`(값), 422 `request-validation`(키·형식) |
| PUT `/me/password` | `MyPasswordRequest` `{"current_password":"…","new_password":"…"}` | 204 본문 없음 | 401 `unauthenticated`, 409 `invalid-state`(AD 모드), 422 `invalid-value` + `errors[{location:["current_password"|"new_password"]}]`, 422 `request-validation`, 429 `too-many-attempts` |

응답 예:

```json
{"id": 7, "login_id": "kim", "role": "sales", "display_name": "김영업",
 "email": "kim@corp.test", "phone": "02-123-4567", "auth_mode": "local",
 "editable": {"display_name": true, "email": true, "phone": true, "password": true}}
```

- 라우터: `APIRouter(prefix="/api/v1/me", tags=["me"])`(업무 쓰기 가드 없는 일반 라우터, 로그인 가드 `CurrentUser`). 유스케이스 `GetMyProfile(uow_factory)`, `UpdateMyProfile(uow_factory, clock)`(admin 정보 수정과 공유하는 `apply_profile_changes`), `ChangeMyPassword(AuthDeps)`. 조립 `provider.get_my_profile()`·`update_my_profile()`·`change_my_password()`.
- 오류 매핑: `WeakPasswordError`는 라우터가 위치 `new_password`로 바꾸고(전역 기본 위치는 `password`), `WrongCurrentPasswordError`는 위치 `current_password`, 빈 값·NUL은 `InvalidFieldError`(해당 필드 위치)다. 새 오류 type 없음.

### 2.7 화면 동작

ME-R1, ME-R16~ME-R19. 라우트 `/me`는 `RequireAuth` 안에 있다(PL-R29·PL-R33). 화면 문구:

| 위치 | 문구 |
| --- | --- |
| 사용자 메뉴 | `<이름> (<역할>)`, `내 정보`, `로그아웃` |
| 제목·카드 | `내 정보`, `기본 정보`, `비밀번호 변경` |
| 칸 | `아이디`, `역할`, `이름`, `이메일`, `전화번호`, `현재 비밀번호`, `새 비밀번호`, `새 비밀번호 확인` |
| 버튼 | `저장`, `비밀번호 변경` |
| 안내 | `이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다.`, `저장했습니다.`, `비밀번호를 바꿨습니다. 다른 기기의 로그인이 종료되었습니다.` |
| 화면 검증 | `새 비밀번호 확인이 일치하지 않습니다.` |
| 로딩 | `불러오는 중…` |

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구(`detail`) | `errors[].location` |
| --- | --- | --- | --- |
| 로그인하지 않음 | 401 `unauthenticated` | 인증 가드 문구(AU) | — |
| PATCH 본문에 허용되지 않은 키·잘못된 값 형식 | 422 `request-validation` | 요청 형식이 올바르지 않습니다 | pydantic 위치 |
| 이름 비움(local) | 422 `invalid-value` | 이름은(는) 비어 있을 수 없습니다 | 없음 |
| 이름 200자 초과 | 422 `invalid-value` | 이름은(는) 200자를 넘을 수 없습니다 | 없음 |
| 이메일 형식 | 422 `invalid-value` | 이메일 형식이 올바르지 않습니다. | 없음 |
| 전화 형식 | 422 `invalid-value` | 전화번호 형식이 올바르지 않습니다. | 없음 |
| 이름·이메일·전화의 NUL | 422 `invalid-value` | 이름에는 / 이메일에는 / 전화번호에는 NUL 문자를 쓸 수 없습니다 | 없음 |
| AD 모드 이름·이메일 수정 | 409 `invalid-state` | AD 연동 사용자의 이름·이메일은 AD에서 관리합니다. | — |
| 퇴사 처리된 행 수정 | 409 `invalid-state` | 이미 퇴사 처리된 사용자입니다 | — |
| 비밀번호 본문 형식(누락·null·257자 이상·알 수 없는 키) | 422 `request-validation` | 요청 형식이 올바르지 않습니다 | pydantic 위치 |
| 비밀번호 빈 값(공백만) | 422 `invalid-value` | 비밀번호는 비어 있을 수 없습니다 | `current_password` 또는 `new_password` |
| 비밀번호 NUL | 422 `invalid-value` | 비밀번호에는 NUL 문자를 쓸 수 없습니다 | 같음 |
| AD 모드 비밀번호 변경 | 409 `invalid-state` | 앱에서 계정을 직접 관리할 때만 쓸 수 있습니다. | — |
| 새 비밀번호 8자 미만 | 422 `invalid-value` | 비밀번호는 8자 이상이어야 합니다 | `new_password` |
| 새 비밀번호 = 아이디 | 422 `invalid-value` | 비밀번호는 아이디와 같을 수 없습니다 | `new_password` |
| 시도 제한 잠김 | 429 `too-many-attempts` | 로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요 | — |
| 현재 비밀번호 틀림(해시 없음 포함) | 422 `invalid-value` | 현재 비밀번호가 올바르지 않습니다. | `current_password` |
| 확인 중 퇴사·비밀번호 변경(경쟁) | 401 `unauthenticated` | 로그인이 필요합니다 | — |
| 화면: 새 비밀번호 확인 불일치 | (요청 없음) | 새 비밀번호 확인이 일치하지 않습니다. | — |

## 3. Business use case

### ME-UC1 사용자 메뉴 사용
- 행위자: 로그인한 사용자(모든 역할)
- 사전 조건: 로그인 후 공통 레이아웃이 보임
- 기본 흐름: 상단 바 사용자 아이콘을 누른다 → 메뉴에 이름(역할)과 `내 정보`·`로그아웃`이 보인다 → `내 정보`를 고르면 `/me`로 이동하고 메뉴가 닫힌다(ME-R1)
- 대안 흐름: `로그아웃`을 고르면 로그아웃 뒤 `/login`. Esc·바깥 클릭·아이콘 재클릭으로 닫는다. 모바일 메뉴 안에서도 같다
- 결과: 내 정보 화면 또는 로그인 화면

### ME-UC2 내 정보 조회
- 행위자: 로그인한 사용자(모든 역할)
- 사전 조건: 로그인 세션
- 기본 흐름: `/me`를 연다 → `GET /me/profile` → 아이디·역할(읽기 전용)과 이름·이메일·전화, 모드별 수정 가능 칸, local 모드면 비밀번호 변경 카드를 본다(ME-R2·ME-R3·ME-R16·ME-R17)
- 예외 흐름: 로그인하지 않았으면 401·`/login`. 조회 실패면 오류 배너
- 결과: 자기 정보와 항목별 수정 가능 여부

### ME-UC3 내 정보 수정
- 행위자: 로그인한 사용자(모든 역할)
- 사전 조건: 로그인 세션, `/me` 화면
- 기본 흐름: 고칠 수 있는 칸을 바꾸고 "저장" → 바뀐 칸만 `PATCH /me/profile` → 200 → 칸이 응답 값으로 바뀌고 "저장했습니다.", 사용자 메뉴에 새 이름(ME-R4·ME-R6·ME-R17)
- 대안 흐름: 이메일·전화를 비우면 `null`로 비운다. AD 모드는 전화만 고칠 수 있다(ME-R7)
- 예외 흐름: 형식 오류 422 `invalid-value`, 허용되지 않은 키 422 `request-validation`, AD 모드 이름·이메일 409, 퇴사 행 409 — 화면은 서버 문구를 보이고 입력을 유지한다
- 결과: 자기 행의 이름·이메일·전화만 바뀌고 아이디·역할·다른 사용자는 그대로

### ME-UC4 비밀번호 변경
- 행위자: 로그인한 사용자(모든 역할, local 모드)
- 사전 조건: 로그인 세션, local 모드
- 기본 흐름: 현재·새·확인 비밀번호를 넣고 "비밀번호 변경" → `PUT /me/password` → 정책 확인 → 시도 제한 선점 → 현재 비밀번호 확인 → 저장 → 204 → 칸을 비우고 안내, 다른 기기 세션 종료(ME-R9~ME-R13·ME-R18)
- 대안 흐름: 확인 칸이 다르면 화면이 요청 없이 막는다
- 예외 흐름: AD 모드 409, 빈 값·약한 새 비밀번호 422(위치), 현재 비밀번호 틀림 422(실패 1회, 세션 유지), 잠김 429, 본문 형식 422 `request-validation`
- 결과: 새 비밀번호로만 로그인, 현재 세션 유지·다른 세션 종료

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| ME-001 | local 사용자는 내 정보와 모든 항목 수정 가능 여부를 받는다 | ME-R3, ME-UC2 | backend | `web/test_me_routes.py::test_every_role_sees_its_own_profile_with_editable_flags`<br>`application/test_my_profile.py::test_my_profile_editable_flags_in_local_mode`<br>`application/test_my_profile.py::test_my_profile_shows_phone_and_email_or_none` |
| ME-002 | AD 모드 사용자는 전화만 수정 가능하다는 표시를 받는다 | ME-R3, ME-UC2 | backend | `web/test_me_routes.py::test_ad_user_profile_flags_allow_only_the_phone`<br>`application/test_my_profile.py::test_my_profile_editable_flags_in_ad_mode` |
| ME-003 | 인증 방식 행이 없는 기존 시스템은 AD 모드로 본다 | ME-R3, ME-UC2 | backend | `application/test_my_profile.py::test_my_profile_without_a_mode_row_in_a_legacy_system_is_ad` |
| ME-004 | 세 역할 모두(user 포함) 내 정보를 보고 고칠 수 있다 | ME-R2, ME-UC2, ME-UC3 | backend | `web/test_me_routes.py::test_every_role_sees_its_own_profile_with_editable_flags`<br>`web/test_me_routes.py::test_read_only_role_can_edit_own_profile` |
| ME-005 | 로그인하지 않으면 내 정보 세 경로가 401이다 | ME-R2, ME-UC2, ME-UC3, ME-UC4 | backend | `web/test_me_routes.py::test_profile_without_login_is_401`<br>`web/test_me_routes.py::test_patch_profile_without_login_is_401`<br>`web/test_me_routes.py::test_change_password_without_login_is_401` |
| ME-006 | 이름·전화를 고치면 응답과 다음 /auth/me에 새 값이 보인다 | ME-R4, ME-R8, ME-UC3 | backend | `web/test_me_routes.py::test_user_updates_name_and_me_shows_it`<br>`application/test_my_profile.py::test_update_my_profile_name_is_visible_to_the_next_authentication` |
| ME-007 | 수정은 자기 행만 바꾸고 아이디·역할·다른 사용자는 그대로다 | ME-R8, ME-UC3 | backend | `application/test_my_profile.py::test_update_my_profile_changes_own_row_only` |
| ME-008 | 보내지 않은 키는 그대로이고 null은 값을 비운다 | ME-R4, ME-UC3 | backend | `web/test_me_routes.py::test_patch_null_clears_email_and_phone_and_omitted_keys_stay`<br>`application/test_my_profile.py::test_update_my_profile_clears_email_and_phone_with_none` |
| ME-009 | 빈 본문이나 같은 값은 저장하지 않고 현재 정보를 준다 | ME-R4, ME-UC3 | backend | `web/test_me_routes.py::test_patch_with_an_empty_body_changes_nothing`<br>`application/test_my_profile.py::test_update_my_profile_with_no_change_or_same_values_keeps_updated_at` |
| ME-010 | 형식이 틀린 이메일·전화는 422 invalid-value이고 값이 바뀌지 않는다 | ME-R6, ME-UC3 | backend | `web/test_me_routes.py::test_invalid_email_or_phone_is_422_invalid_value_and_changes_nothing`<br>`application/test_my_profile.py::test_update_my_profile_invalid_email_is_invalid_value` |
| ME-011 | local 모드에서 이름을 비우거나 200자를 넘기면 422 invalid-value다 | ME-R6, ME-UC3 | backend | `web/test_me_routes.py::test_blank_or_too_long_name_is_422_invalid_value_and_changes_nothing`<br>`application/test_my_profile.py::test_update_my_profile_blank_name_in_local_mode_is_invalid_value` |
| ME-012 | 본문에 login_id·role 등 다른 키가 있으면 422 request-validation이다 | ME-R5, ME-UC3 | backend | `web/test_me_routes.py::test_extra_keys_such_as_login_id_or_role_are_422_request_validation` |
| ME-013 | AD 모드에서 이름·이메일을 고치려 하면 409 invalid-state다 | ME-R7, ME-UC3 | backend | `web/test_me_routes.py::test_ad_user_name_or_email_edit_is_409`<br>`application/test_my_profile.py::test_update_my_profile_name_or_email_in_ad_mode_is_invalid_state` |
| ME-014 | AD 모드에서도 전화는 고칠 수 있다 | ME-R7, ME-UC3 | backend | `web/test_me_routes.py::test_ad_user_can_edit_only_phone`<br>`application/test_my_profile.py::test_update_my_profile_phone_only_in_ad_mode` |
| ME-015 | 퇴사 처리된 행의 정보 수정은 409 invalid-state다 | ME-R8, ME-UC3 | backend | `application/test_my_profile.py::test_update_my_profile_of_a_resigned_actor_is_rejected` |
| ME-016 | 이름·이메일·전화는 정규화해 저장하고 경계값을 받아들인다 | ME-R6, ME-UC3 | backend | `web/test_me_routes.py::test_profile_values_are_normalized_and_boundaries_are_accepted`<br>`application/test_my_profile.py::test_update_my_profile_normalizes_values_and_accepts_the_boundaries` |
| ME-017 | 비밀번호를 바꾸면 204이고 새 비밀번호로만 로그인된다 | ME-R13, ME-UC4 | backend | `web/test_me_routes.py::test_changing_password_is_204_and_the_new_password_signs_in`<br>`application/test_change_my_password.py::test_change_my_password_new_password_signs_in_and_old_does_not` |
| ME-018 | 비밀번호를 바꾸면 현재 세션은 남고 같은 사용자의 다른 세션만 끝난다 | ME-R13, ME-UC4 | backend | `web/test_me_routes.py::test_changing_password_ends_other_sessions_only`<br>`application/test_change_my_password.py::test_change_my_password_success_keeps_current_session_and_ends_others`<br>`application/test_change_my_password.py::test_change_my_password_does_not_touch_other_users_sessions` |
| ME-019 | 유지하는 세션은 요청 쿠키의 세션이다 | ME-R13, ME-UC4 | backend | `web/test_me_routes.py::test_the_session_token_is_matched_by_the_request_cookie`<br>`application/test_change_my_password.py::test_the_session_to_keep_is_the_one_whose_token_was_given` |
| ME-020 | 현재 비밀번호가 틀리면 422(위치 current_password)이고 실패 1회로 센다 | ME-R12, ME-R10, ME-UC4 | backend | `web/test_me_routes.py::test_wrong_current_password_is_422_on_the_current_password_and_counted`<br>`web/test_me_routes.py::test_wrong_current_password_keeps_the_session_and_does_not_log_out`<br>`application/test_change_my_password.py::test_change_my_password_wrong_current_is_invalid_value_and_counted` |
| ME-021 | 실패 한도를 넘으면 맞는 현재 비밀번호여도 확인 없이 429다 | ME-R12, ME-UC4 | backend | `web/test_me_routes.py::test_repeated_wrong_current_passwords_lock_with_429`<br>`application/test_change_my_password.py::test_change_my_password_locked_is_too_many_attempts_without_verifying` |
| ME-022 | 현재 비밀번호 실패는 로그인과 같은 카운터를 쓴다 | ME-R12, ME-UC4 | backend | `application/test_change_my_password.py::test_change_my_password_failures_are_shared_with_login` |
| ME-023 | 비밀번호 변경에 성공하면 계정 실패 카운터가 지워진다 | ME-R12, ME-UC4 | backend | `application/test_change_my_password.py::test_change_my_password_success_clears_the_account_counter` |
| ME-024 | 8자 미만 새 비밀번호는 422(위치 new_password)이고 실패로 세지 않는다 | ME-R11, ME-R10, ME-UC4 | backend | `web/test_me_routes.py::test_weak_new_password_is_422_on_the_new_password`<br>`application/test_change_my_password.py::test_change_my_password_weak_new_password_is_invalid_value_and_not_counted` |
| ME-025 | 아이디와 같은 새 비밀번호는 대소문자·앞뒤 공백을 무시하고 거절한다 | ME-R11, ME-UC4 | backend | `application/test_change_my_password.py::test_change_my_password_new_equal_to_login_id_is_invalid_value` |
| ME-026 | 정확히 8자·256자 새 비밀번호는 받아들인다 | ME-R11, ME-R10, ME-UC4 | backend | `web/test_me_routes.py::test_new_password_of_exactly_the_minimum_or_maximum_length_is_accepted`<br>`application/test_change_my_password.py::test_change_my_password_accepts_exactly_the_minimum_and_maximum_length` |
| ME-027 | AD 모드에서 비밀번호를 바꾸려 하면 409 invalid-state다 | ME-R9, ME-UC4 | backend | `web/test_me_routes.py::test_ad_user_cannot_change_the_password`<br>`application/test_change_my_password.py::test_change_my_password_in_ad_mode_is_invalid_state` |
| ME-028 | 저장된 해시가 없는 사용자는 현재 비밀번호 틀림과 같다 | ME-R12, ME-UC4 | backend | `application/test_change_my_password.py::test_change_my_password_for_a_user_without_a_hash_is_wrong_current` |
| ME-029 | 비밀번호 본문 형식 오류는 422 request-validation이다 | ME-R10, ME-UC4 | backend | `web/test_me_routes.py::test_invalid_password_body_is_422_request_validation` |
| ME-030 | 빈 현재·새 비밀번호는 422 invalid-value이고 위치가 그 칸이다 | ME-R10, ME-UC4 | backend | `web/test_me_routes.py::test_blank_current_or_new_password_is_422_on_that_field` |
| ME-031 | openapi에 내 정보 경로·응답·요청 스키마와 비밀번호 필드 표기가 문서화된다 | ME-R15, ME-R14 | backend | `web/test_local_account_openapi.py::test_new_paths_and_methods`<br>`web/test_local_account_openapi.py::test_documented_success_and_problem_responses`<br>`web/test_local_account_openapi.py::test_the_no_content_responses_have_no_body`<br>`web/test_local_account_openapi.py::test_the_profile_patch_requests_take_only_the_three_fields`<br>`web/test_local_account_openapi.py::test_password_requests_are_masked_write_only_secrets`<br>`web/test_local_account_openapi.py::test_my_profile_response_shape`<br>`web/test_local_account_openapi.py::test_both_profile_endpoints_return_the_same_response_schema` |
| ME-032 | 상단 바에는 사용자 아이콘 버튼만 있고 메뉴는 닫혀 있다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > shows an icon button instead of the plain name text and logout button` |
| ME-033 | 사용자 메뉴를 열면 이름(역할)과 내 정보·로그아웃이 순서대로 보인다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > opens a menu with the name (role), 내 정보 and 로그아웃` |
| ME-034 | 사용자 메뉴는 Esc·바깥 클릭·아이콘 재클릭으로 닫힌다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > closes with Escape and gives the focus back to the icon button`<br>`shared/ui/Layout.userMenu.test.tsx > closes when the user clicks outside the menu`<br>`shared/ui/Layout.userMenu.test.tsx > toggles closed when the icon button is pressed again` |
| ME-035 | 내 정보를 고르면 /me로 이동하고 메뉴가 닫힌다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > moves to /me from 내 정보 and closes the menu` |
| ME-036 | 로그아웃을 고르면 /login으로 간다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > keeps logging out working from the menu` |
| ME-037 | 세 역할 모두, 모바일 메뉴 안에서도 사용자 메뉴를 쓴다 | ME-R1, ME-UC1 | frontend | `shared/ui/Layout.userMenu.test.tsx > is available to the %s role`<br>`shared/ui/Layout.userMenu.test.tsx > also works inside the opened mobile menu` |
| ME-038 | 내 정보 화면은 아이디·역할을 읽기 전용으로, 이름·이메일·전화를 편집 칸으로 보인다 | ME-R16, ME-R17, ME-UC2 | frontend | `features/account/MyProfilePage.test.tsx > shows the id and role read-only and the editable profile`<br>`features/account/MyProfilePage.test.tsx > is open to the %s role` |
| ME-039 | 로그인하지 않고 /me를 열면 로그인 화면으로 간다 | ME-R2, ME-UC2 | frontend | `features/account/MyProfilePage.test.tsx > redirects a visitor who is not signed in to the login page` |
| ME-040 | 내 정보 조회가 실패하면 제목과 오류 배너만 보인다 | ME-R16, ME-UC2 | frontend | `features/account/MyProfilePage.test.tsx > shows only the title and an error banner when the profile cannot be read` |
| ME-041 | 바뀐 칸이 없으면 저장 버튼이 비활성이다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > keeps the save button disabled until something changes` |
| ME-042 | 바뀐 칸만 보내고 저장했습니다 안내를 보인다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > saves only the changed fields and shows a notice` |
| ME-043 | 이메일·전화를 비우면 null을 보낸다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > clears the email by sending null` |
| ME-044 | 저장 뒤 사용자 메뉴에 새 이름이 보인다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > shows the new name in the user menu after saving` |
| ME-045 | 서버가 거절하면 서버 문구를 보이고 입력을 유지한다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > shows the server message for an invalid value and keeps the typed input`<br>`features/account/MyProfilePage.test.tsx > refuses a blank name with the server message` |
| ME-046 | AD 모드에서는 이름·이메일이 비활성이고 안내와 함께 전화만 저장한다 | ME-R17, ME-UC3 | frontend | `features/account/MyProfilePage.test.tsx > lets the user edit only the phone and explains that name and email come from AD` |
| ME-047 | AD 모드에서는 비밀번호 변경 카드가 없다 | ME-R16, ME-UC2 | frontend | `features/account/MyProfilePage.test.tsx > has no password section` |
| ME-048 | local 모드 비밀번호 변경 카드는 세 개의 비밀번호 칸을 가진다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > shows the section with three password fields in local mode` |
| ME-049 | 비밀번호를 바꾸면 칸을 비우고 다른 기기 로그인 종료를 알린다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > changes the password, clears the fields and says other devices were signed out` |
| ME-050 | 새 비밀번호 확인이 다르면 요청하지 않고 문구를 보인다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > does not submit when the confirmation differs` |
| ME-051 | 현재 비밀번호가 틀리면 서버 문구를 보이고 칸을 비운다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > shows the wrong current password message next to the form and clears the secrets` |
| ME-052 | 시도 제한에 걸리면 잠금 문구를 보인다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > shows the lock message when too many attempts were made` |
| ME-053 | 약한 새 비밀번호는 서버 문구를 보인다 | ME-R18, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > shows the server message for a weak new password` |
| ME-054 | 입력한 비밀번호가 mutation 캐시에 남지 않는다 | ME-R18, ME-R14, ME-UC4 | frontend | `features/account/MyProfilePage.test.tsx > does not keep the typed passwords in the mutation cache` |
| ME-055 | 게이트웨이 profile은 GET /me/profile을 화면 모델로 바꾼다 | ME-R19, ME-UC2 | frontend | `gateway/http/me.test.ts > profile reads GET /me/profile and renames the fields`<br>`gateway/http/me.test.ts > profile maps an AD user: only the phone is editable`<br>`gateway/http/me.test.ts > profile uses the login id when the user has no display name`<br>`gateway/http/me.test.ts > profile shows the server message when not signed in`<br>`test/fake/gateway/me.test.ts > shows the %s profile with every field editable in local mode`<br>`test/fake/gateway/me.test.ts > allows only the phone in AD mode and no password change`<br>`test/fake/gateway/me.test.ts > needs a session` |
| ME-056 | 게이트웨이 updateProfile은 준 키만 PATCH로 보내고 서버 오류를 그대로 넘긴다 | ME-R19, ME-UC3 | frontend | `gateway/http/me.test.ts > updateProfile sends PATCH /me/profile with only the given fields and returns the profile`<br>`gateway/http/me.test.ts > updateProfile sends null to clear a field`<br>`gateway/http/me.test.ts > updateProfile never sends the id or the role`<br>`gateway/http/me.test.ts > updateProfile shows the %s answer %s with the server message`<br>`test/fake/gateway/me.test.ts > changes the own name, email and phone, and auth.me shows the new name`<br>`test/fake/gateway/me.test.ts > never changes the id or the role`<br>`test/fake/gateway/me.test.ts > keeps omitted fields and clears a field given as null`<br>`test/fake/gateway/me.test.ts > rejects %s with 422 and changes nothing`<br>`test/fake/gateway/me.test.ts > refuses %j in AD mode with 409`<br>`test/fake/gateway/me.test.ts > lets the phone be changed in AD mode`<br>`test/fake/gateway/me.test.ts > lets a read-only user edit the own profile`<br>`test/fake/gateway/me.test.ts > needs a session` |
| ME-057 | 게이트웨이 changePassword는 PUT /me/password를 보내고 204면 끝난다 | ME-R19, ME-UC4 | frontend | `gateway/http/me.test.ts > changePassword sends PUT /me/password with both passwords and resolves on 204`<br>`gateway/http/me.test.ts > changePassword reports a wrong current password as a validation error, not as a sign-out`<br>`gateway/http/me.test.ts > changePassword shows the %s answer %s with the server message`<br>`test/fake/gateway/me.test.ts > checks the current password, sets the new one and keeps the session`<br>`test/fake/gateway/me.test.ts > rejects a wrong current password with 422 (not 401) and keeps the old password`<br>`test/fake/gateway/me.test.ts > rejects the weak new password %s with 422`<br>`test/fake/gateway/me.test.ts > rejects a 257 character new password as a malformed request`<br>`test/fake/gateway/me.test.ts > refuses in AD mode with 409`<br>`test/fake/gateway/me.test.ts > needs a session` |

### ME-001 local 사용자는 내 정보와 모든 항목 수정 가능 여부를 받는다
- Given local 모드이고 sales 사용자 kim(이름 "김영업", 이메일 `kim@corp.test`, 전화 `02-123-4567`)으로 로그인했다
- When `GET /api/v1/me/profile`을 부른다
- Then 200이고 본문 키는 정확히 `id`·`login_id`·`role`·`display_name`·`email`·`phone`·`auth_mode`·`editable`이며, `id`는 정수, 값은 `kim`·`sales`·`김영업`·`kim@corp.test`·`02-123-4567`·`local`, `editable`은 `{display_name: true, email: true, phone: true, password: true}`이고 본문에 비밀번호 문자열이 없다

### ME-002 AD 모드 사용자는 전화만 수정 가능하다는 표시를 받는다
- Given AD 모드이고 sales 사용자 kim으로 로그인했다
- When `GET /api/v1/me/profile`을 부른다
- Then `auth_mode`는 `ad`이고 `editable`은 `{display_name: false, email: false, phone: true, password: false}`다

### ME-003 인증 방식 행이 없는 기존 시스템은 AD 모드로 본다
- Given 인증 방식 행이 없고 재직 admin이 있는 시스템에서 kim으로 로그인했다
- When 내 정보를 조회한다
- Then `auth_mode`는 `ad`이고 이름·이메일·비밀번호 수정은 불가로 표시된다

### ME-004 세 역할 모두(user 포함) 내 정보를 보고 고칠 수 있다
- Given local 모드이고 admin, sales, user 중 하나로 로그인했다
- When `GET /api/v1/me/profile`을 부르고 `PATCH /api/v1/me/profile` `{"phone": "010-1111-2222"}`를 보낸다
- Then 세 역할 모두 둘 다 200이고(403 아님) 조회 `role`은 그 역할, 수정 응답 `phone`은 `010-1111-2222`다

### ME-005 로그인하지 않으면 내 정보 세 경로가 401이다
- Given 로그인하지 않았다
- When `GET /me/profile`, `PATCH /me/profile` `{}`, `PUT /me/password`를 각각 부른다
- Then 모두 401 `unauthenticated`(problem+json)이고 여전히 미인증 상태다

### ME-006 이름·전화를 고치면 응답과 다음 /auth/me에 새 값이 보인다
- Given local 모드이고 kim(이름 "김영업", 이메일 `kim@corp.test`)으로 로그인했다
- When `PATCH /api/v1/me/profile` `{"display_name": "김새이름", "phone": "010-9999-8888"}`을 보낸다
- Then 200이고 응답 키는 ME-001과 같으며 `display_name` "김새이름", `phone` `010-9999-8888`, `email`은 그대로 `kim@corp.test`이고, 이어서 부른 `GET /auth/me`의 `name`은 "김새이름"이다

### ME-007 수정은 자기 행만 바꾸고 아이디·역할·다른 사용자는 그대로다
- Given local 모드이고 kim(sales)과 lee(이름 "이영업", 전화 없음)가 있으며 kim으로 로그인했다
- When kim이 이름 "김새이름"·전화 `010-9999-8888`로 고친다
- Then 저장된 lee는 이름 "이영업"·전화 없음 그대로이고, kim의 아이디는 `kim`, 역할은 `sales` 그대로다

### ME-008 보내지 않은 키는 그대로이고 null은 값을 비운다
- Given local 모드이고 kim(이름 "김영업", 이메일 `kim@corp.test`, 전화 `02-123-4567`)으로 로그인했다
- When `{"email": null}`을 보내고, 따로 `{"email": null, "phone": null}`을 보낸다
- Then 앞의 응답은 이름 "김영업"·이메일 `null`·전화 `02-123-4567`이고, 뒤의 응답은 이름 "김영업"·이메일 `null`·전화 `null`이다

### ME-009 빈 본문이나 같은 값은 저장하지 않고 현재 정보를 준다
- Given local 모드이고 kim으로 로그인했다
- When `PATCH /api/v1/me/profile` `{}`를 보내고, 따로 지금과 같은 전화 값만 보낸다
- Then 둘 다 200이고 응답은 직전 `GET /me/profile`과 같으며, 저장소의 kim `updated_at`은 바뀌지 않는다

### ME-010 형식이 틀린 이메일·전화는 422 invalid-value이고 값이 바뀌지 않는다
- Given local 모드이고 kim(이메일 `kim@corp.test`)으로 로그인했다
- When `{"email": "not-an-email"}`(또는 `"abc"`), `{"phone": "12"}`를 각각 보낸다
- Then 각각 422 `invalid-value`이고 `detail`은 "이메일 형식이 올바르지 않습니다." / "전화번호 형식이 올바르지 않습니다."이며, 다시 조회한 이메일은 `kim@corp.test`, 이름은 "김영업" 그대로다

### ME-011 local 모드에서 이름을 비우거나 200자를 넘기면 422 invalid-value다
- Given local 모드이고 kim(이름 "김영업")으로 로그인했다
- When `{"display_name": ""}`, `{"display_name": " "}`, `{"display_name": null}`, `{"display_name": "가"×201}`을 각각 보낸다
- Then 모두 422 `invalid-value`이고(앞의 셋은 "이름은(는) 비어 있을 수 없습니다", 마지막은 "이름은(는) 200자를 넘을 수 없습니다") 다시 조회한 이름은 "김영업"이다

### ME-012 본문에 login_id·role 등 다른 키가 있으면 422 request-validation이다
- Given local 모드이고 sales 사용자 kim으로 로그인했다
- When `{"login_id": "x"}`, `{"role": "admin"}`, `{"id": 1}`, `{"password": "x"}`, `{"unknown": 1}`, `{"login_id": "other", "role": "admin"}`을 각각 보낸다
- Then 모두 422 `request-validation`이고 다시 조회한 아이디·역할은 `kim`·`sales`다

### ME-013 AD 모드에서 이름·이메일을 고치려 하면 409 invalid-state다
- Given AD 모드이고 kim(이름 "김영업")으로 로그인했다
- When `{"display_name": "새 이름"}`, `{"email": "a@b.co"}`, `{"email": "abc"}`를 각각 보낸다
- Then 모두 409 `invalid-state` "AD 연동 사용자의 이름·이메일은 AD에서 관리합니다."이고(형식이 틀린 이메일도 422가 아니라 409) 이름·이메일은 그대로다

### ME-014 AD 모드에서도 전화는 고칠 수 있다
- Given AD 모드이고 kim으로 로그인했다
- When `{"phone": "010-1111-2222"}`를 보낸다
- Then 200이고 `phone`은 `010-1111-2222`, `auth_mode`는 `ad`, `editable`은 전화만 `true`다

### ME-015 퇴사 처리된 행의 정보 수정은 409 invalid-state다
- Given local 모드이고 퇴사 처리된 사용자 gone의 로그인 주체가 있다(유스케이스 직접 호출)
- When gone이 전화 `02-123-4567`로 고친다
- Then `InvalidStateError` "이미 퇴사 처리된 사용자입니다"이고 값은 바뀌지 않는다

### ME-016 이름·이메일·전화는 정규화해 저장하고 경계값을 받아들인다
- Given local 모드이고 kim으로 로그인했다
- When `{"display_name": "  김새이름  ", "email": "  Kim@Corp.TEST ", "phone": " 02-123-4567 "}`을 보내고, 따로 `{"display_name": "가"×200, "email": "   ", "phone": "1234567"}`을 보낸다
- Then 앞의 응답은 이름 "김새이름", 이메일 `kim@corp.test`, 전화 `02-123-4567`이고, 뒤의 응답은 이름이 200자 그대로, 이메일 `null`, 전화 `1234567`이다

### ME-017 비밀번호를 바꾸면 204이고 새 비밀번호로만 로그인된다
- Given local 모드이고 kim(현재 비밀번호 P)으로 로그인했다
- When `PUT /api/v1/me/password` `{"current_password": P, "new_password": "Fresh-passw0rd"}`를 보낸다
- Then 204이고 본문이 비어 있으며 지금 세션의 `GET /auth/me`는 200이고, 새로 로그인하면 `Fresh-passw0rd`는 200, P는 401이다

### ME-018 비밀번호를 바꾸면 현재 세션은 남고 같은 사용자의 다른 세션만 끝난다
- Given local 모드이고 kim의 세션 셋(현재·다른 둘)과 lee의 세션 하나가 있다
- When kim이 현재 세션으로 비밀번호를 바꾼다
- Then kim의 현재 세션은 살아 있고(`/auth/me` 200, 이름 그대로), kim의 다른 두 세션은 끝나(다음 요청 401) lee의 세션은 그대로 살아 있다

### ME-019 유지하는 세션은 요청 쿠키의 세션이다
- Given local 모드이고 kim의 세션 A·B가 있다
- When 세션 B의 쿠키로 비밀번호를 바꾼다
- Then 세션 저장소에 B는 남고 A는 지워진다

### ME-020 현재 비밀번호가 틀리면 422(위치 current_password)이고 실패 1회로 센다
- Given local 모드이고 kim(다른 세션 하나 더 있음)으로 로그인했다
- When 현재 비밀번호를 `wrong-pass-1`로 비밀번호 변경을 요청한다
- Then 422 `invalid-value` "현재 비밀번호가 올바르지 않습니다."이고 `errors`의 위치는 `[["current_password"]]`이며, kim 계정 실패 수는 1, 저장된 해시는 이전 비밀번호 그대로, 지금 세션의 `/auth/me`는 200, 다른 세션도 살아 있다

### ME-021 실패 한도를 넘으면 맞는 현재 비밀번호여도 확인 없이 429다
- Given local 모드이고 kim이 현재 비밀번호를 계정 한도만큼 틀렸다
- When 맞는 현재 비밀번호로 다시 요청한다
- Then 429 `too-many-attempts` "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"이고 비밀번호 확인 계산은 더 일어나지 않으며 해시는 이전 그대로다

### ME-022 현재 비밀번호 실패는 로그인과 같은 카운터를 쓴다
- Given local 모드이고 kim이 비밀번호 변경에서 현재 비밀번호를 계정 한도만큼 틀렸다
- When kim이 맞는 비밀번호로 로그인한다
- Then 로그인은 `TooManyAttemptsError`(429)다

### ME-023 비밀번호 변경에 성공하면 계정 실패 카운터가 지워진다
- Given local 모드이고 kim이 현재 비밀번호를 한 번 틀려 계정 실패 수가 1이다
- When 맞는 현재 비밀번호로 비밀번호를 바꾼다
- Then kim 계정 실패 카운터가 없다

### ME-024 8자 미만 새 비밀번호는 422(위치 new_password)이고 실패로 세지 않는다
- Given local 모드이고 kim으로 로그인했다
- When 맞는 현재 비밀번호와 새 비밀번호 `short7!`, `1234567`, `kim`을 각각 보낸다
- Then 모두 422 `invalid-value` "비밀번호는 8자 이상이어야 합니다"이고 `errors` 위치는 `[["new_password"]]`이며, 실패 카운터가 없고, 이전 비밀번호로 계속 로그인된다

### ME-025 아이디와 같은 새 비밀번호는 대소문자·앞뒤 공백을 무시하고 거절한다
- Given local 모드이고 아이디 `kim.lee1` 사용자로 로그인했다
- When 새 비밀번호 `Kim.Lee1`(그리고 ` kim.lee1 `)로 바꾸려 한다
- Then 422 `invalid-value` "비밀번호는 아이디와 같을 수 없습니다"이고 위치는 `new_password`다

### ME-026 정확히 8자·256자 새 비밀번호는 받아들인다
- Given local 모드이고 kim으로 로그인했다
- When 새 비밀번호를 정확히 8자(`abcd1234`), 따로 정확히 256자로 바꾼다
- Then 둘 다 204이고 그 새 비밀번호로 로그인된다

### ME-027 AD 모드에서 비밀번호를 바꾸려 하면 409 invalid-state다
- Given AD 모드이고 kim(세션 둘)으로 로그인했다
- When 비밀번호 변경을 요청한다
- Then 409 `invalid-state` "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."이고 kim의 다른 세션은 살아 있다

### ME-028 저장된 해시가 없는 사용자는 현재 비밀번호 틀림과 같다
- Given local 모드이고 비밀번호 해시가 없는 kim으로 로그인했다
- When 아무 현재 비밀번호로 비밀번호 변경을 요청한다
- Then 422 "현재 비밀번호가 올바르지 않습니다."(`WrongCurrentPasswordError`)다

### ME-029 비밀번호 본문 형식 오류는 422 request-validation이다
- Given local 모드이고 kim으로 로그인했다
- When `{}`, 현재 비밀번호만, 새 비밀번호만, `current_password: null`, 257자 새 비밀번호(또는 257자 현재 비밀번호), 알 수 없는 키 `extra`가 있는 본문을 각각 보낸다
- Then 모두 422 `request-validation`이다

### ME-030 빈 현재·새 비밀번호는 422 invalid-value이고 위치가 그 칸이다
- Given local 모드이고 kim으로 로그인했다
- When `current_password`를 `""`(또는 공백만)로, 따로 `new_password`를 `""`로 보낸다
- Then 각각 422 `invalid-value` "비밀번호는 비어 있을 수 없습니다"이고 `errors` 위치는 `[["current_password"]]` / `[["new_password"]]`이며 실패 카운터는 없다

### ME-031 openapi에 내 정보 경로·응답·요청 스키마와 비밀번호 필드 표기가 문서화된다
- When 앱의 openapi 문서를 만든다
- Then ME-R15의 경로·메서드·응답 코드가 있고 `PUT /me/password` 204에는 `content`가 없으며, `PATCH /me/profile` 요청 속성은 `display_name`·`email`·`phone`(required 없음), `GET`·`PATCH` 200은 같은 스키마이고 `id`는 integer, `editable` 네 속성은 boolean·required이며, `current_password`·`new_password`는 `format: password`, `writeOnly: true`, `maxLength: 256`이다

### ME-032 상단 바에는 사용자 아이콘 버튼만 있고 메뉴는 닫혀 있다
- Given sales로 로그인했다
- When `/deals`를 연다
- Then "사용자 메뉴" 버튼은 `aria-haspopup="menu"`·`aria-expanded="false"`이고 svg 아이콘을 가지며, 메뉴와 "로그아웃" 버튼은 보이지 않는다

### ME-033 사용자 메뉴를 열면 이름(역할)과 내 정보·로그아웃이 순서대로 보인다
- Given sales 사용자 "김영업"으로 로그인해 `/deals`에 있다
- When "사용자 메뉴" 버튼을 누른다
- Then 버튼은 `aria-expanded="true"`이고 메뉴에 "김영업 (sales)"가 보이며 메뉴 항목은 `["내 정보", "로그아웃"]` 순서다

### ME-034 사용자 메뉴는 Esc·바깥 클릭·아이콘 재클릭으로 닫힌다
- Given 사용자 메뉴가 열려 있다
- When Esc를 누르거나, 주 메뉴(바깥)를 누르거나, 아이콘 버튼을 다시 누른다
- Then 메뉴가 닫히고, Esc의 경우 포커스가 "사용자 메뉴" 버튼에 있다

### ME-035 내 정보를 고르면 /me로 이동하고 메뉴가 닫힌다
- Given `/deals`에서 사용자 메뉴가 열려 있다
- When "내 정보" 항목을 누른다
- Then 주소가 `/me`가 되고 메뉴가 닫히며 제목 "내 정보"가 보인다

### ME-036 로그아웃을 고르면 /login으로 간다
- Given `/deals`에서 사용자 메뉴가 열려 있다
- When "로그아웃" 항목을 누른다
- Then 주소가 `/login`이 된다

### ME-037 세 역할 모두, 모바일 메뉴 안에서도 사용자 메뉴를 쓴다
- Given admin, sales, user 중 하나로 로그인했다(또는 sales로 "메뉴 열기"를 눌러 모바일 메뉴를 열었다)
- When `/deals`를 열고(모바일이면 사용자 메뉴를 연다)
- Then 세 역할 모두 "사용자 메뉴" 버튼이 있고, 모바일 메뉴 안에서 연 사용자 메뉴에 "내 정보" 항목이 있다

### ME-038 내 정보 화면은 아이디·역할을 읽기 전용으로, 이름·이메일·전화를 편집 칸으로 보인다
- Given local 모드이고 admin, sales, user 중 하나(sales는 kim "김영업")로 로그인했다
- When `/me`를 연다
- Then 아이디 칸 `kim`·역할 칸 `sales`는 `readonly`이고, 이름 칸 "김영업"·이메일·전화번호 칸은 활성이며 "저장" 버튼이 있다(세 역할 모두)

### ME-039 로그인하지 않고 /me를 열면 로그인 화면으로 간다
- Given 로그인하지 않았다
- When `/me`를 연다
- Then 주소가 `/login`이 된다

### ME-040 내 정보 조회가 실패하면 제목과 오류 배너만 보인다
- Given 로그인했고 내 정보 조회가 500 "내 정보를 불러오지 못했습니다."로 실패한다
- When `/me`를 연다
- Then 제목 "내 정보"와 `role="alert"`의 "내 정보를 불러오지 못했습니다."가 보이고 기본 정보·비밀번호 변경 카드는 없다

### ME-041 바뀐 칸이 없으면 저장 버튼이 비활성이다
- Given local 모드로 `/me`를 열었다
- When 아무것도 고치지 않았다가 전화번호에 `02-123-4567`을 입력한다
- Then 처음에는 "저장"이 비활성이고 입력 뒤에는 활성이다

### ME-042 바뀐 칸만 보내고 저장했습니다 안내를 보인다
- Given local 모드로 `/me`를 열었다
- When 이름을 "김새이름"으로 바꾸고 전화번호에 `010-9999-8888`을 넣어 "저장"을 누른다
- Then "저장했습니다."가 보이고, 저장 요청은 한 번 `{name: "김새이름", phone: "010-9999-8888"}`(이메일 없음)로 갔으며, 내 정보 조회 결과의 이름은 "김새이름"이다

### ME-043 이메일·전화를 비우면 null을 보낸다
- Given local 모드로 `/me`를 열었다(이메일 있음)
- When 이메일 칸을 비우고 "저장"을 누른다
- Then "저장했습니다."가 보이고 저장 요청은 `{email: null}`이며 내 정보의 이메일은 `null`이다

### ME-044 저장 뒤 사용자 메뉴에 새 이름이 보인다
- Given local 모드 sales로 `/me`에서 이름을 "김새이름"으로 저장했다
- When 사용자 메뉴를 연다
- Then "김새이름 (sales)"가 보인다

### ME-045 서버가 거절하면 서버 문구를 보이고 입력을 유지한다
- Given local 모드로 `/me`를 열었다
- When 이메일을 `not-an-email`로 바꿔 저장하고, 따로 이름을 비워 저장한다
- Then 앞의 경우 `role="alert"`에 "이메일 형식이 올바르지 않습니다."가 보이고 이메일 칸은 `not-an-email` 그대로이며 "저장했습니다."는 없고, 뒤의 경우 경고에 서버의 이름 문구가 보인다

### ME-046 AD 모드에서는 이름·이메일이 비활성이고 안내와 함께 전화만 저장한다
- Given AD 모드로 `/me`를 열었다
- When 전화번호에 `010-1111-2222`를 넣어 "저장"을 누른다
- Then 이름·이메일 칸은 비활성, 전화번호 칸은 활성이고 "이름·이메일은 AD에서 관리합니다" 안내가 보이며, "저장했습니다."와 함께 저장 요청은 `{phone: "010-1111-2222"}`다

### ME-047 AD 모드에서는 비밀번호 변경 카드가 없다
- Given AD 모드로 로그인했다
- When `/me`를 연다
- Then "비밀번호 변경" 제목과 "현재 비밀번호" 칸이 없다

### ME-048 local 모드 비밀번호 변경 카드는 세 개의 비밀번호 칸을 가진다
- Given local 모드로 로그인했다
- When `/me`를 연다
- Then "비밀번호 변경" 제목이 있고 "현재 비밀번호"·"새 비밀번호"·"새 비밀번호 확인"은 모두 `type="password"`이며, 현재 칸은 `autocomplete="current-password"`, 새 칸은 `autocomplete="new-password"`다

### ME-049 비밀번호를 바꾸면 칸을 비우고 다른 기기 로그인 종료를 알린다
- Given local 모드로 `/me`를 열었다
- When 현재 비밀번호(시드 값), 새 비밀번호·확인 `Fresh-passw0rd`를 넣고 "비밀번호 변경"을 누른다
- Then "다른 기기의 로그인이 종료되었습니다" 안내가 보이고, 변경 요청은 (시드 값, `Fresh-passw0rd`)로 갔으며 세 칸이 모두 비어 있다

### ME-050 새 비밀번호 확인이 다르면 요청하지 않고 문구를 보인다
- Given local 모드로 `/me`를 열었다
- When 새 비밀번호 `Fresh-passw0rd`, 확인 `Fresh-passw0rX`를 넣고 "비밀번호 변경"을 누른다
- Then `role="alert"`에 "새 비밀번호 확인이 일치하지 않습니다."가 보이고 변경 요청은 가지 않았다

### ME-051 현재 비밀번호가 틀리면 서버 문구를 보이고 칸을 비운다
- Given local 모드로 `/me`를 열었고 변경 요청이 422 "현재 비밀번호가 올바르지 않습니다."로 거절된다
- When 비밀번호 칸을 채워 "비밀번호 변경"을 누른다
- Then "현재 비밀번호가 올바르지 않습니다."가 보이고 현재·새 비밀번호 칸이 비어 있으며 성공 안내는 없다

### ME-052 시도 제한에 걸리면 잠금 문구를 보인다
- Given local 모드로 `/me`를 열었고 변경 요청이 429 "로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요"로 거절된다
- When 비밀번호 칸을 채워 "비밀번호 변경"을 누른다
- Then `role="alert"`에 "로그인 시도가 너무 많습니다"가 보인다

### ME-053 약한 새 비밀번호는 서버 문구를 보인다
- Given local 모드로 `/me`를 열었다
- When 새 비밀번호·확인을 `short7!`로 넣고 "비밀번호 변경"을 누른다
- Then `role="alert"`에 "비밀번호는 8자 이상이어야 합니다"가 보인다

### ME-054 입력한 비밀번호가 mutation 캐시에 남지 않는다
- Given local 모드로 `/me`에서 비밀번호를 `Fresh-passw0rd`로 바꿨다
- When 쿼리 클라이언트의 mutation 캐시 변수 전체를 문자열로 만든다
- Then 그 문자열에 `Fresh-passw0rd`도 이전(시드) 비밀번호도 없다

### ME-055 게이트웨이 profile은 GET /me/profile을 화면 모델로 바꾼다
- Given 서버가 local 사용자(이름 있음), AD 사용자(`editable` 전화만), 이름이 없는 사용자, 401 중 하나를 준다
- When HTTP 게이트웨이 `profile()`을 부른다
- Then `GET /api/v1/me/profile`을 부르고 `{id, loginId, role, name, email, phone, authMode, editable{name,email,phone,password}}`로 바꾸며, 이름이 없으면 `name`은 아이디, AD면 `editable`은 전화만 `true`, 401이면 서버 문구의 `ApiError`로 reject한다. Fake 게이트웨이도 local 세 역할·AD 모드·세션 없음(401)에서 같은 모양을 준다

### ME-056 게이트웨이 updateProfile은 준 키만 PATCH로 보내고 서버 오류를 그대로 넘긴다
- Given 서버가 내 정보 응답 또는 409 `invalid-state`·422 `invalid-value`·422 `request-validation` 중 하나를 준다
- When `updateProfile({name, phone})`, `updateProfile({email: null})`을 부른다
- Then `PATCH /api/v1/me/profile` 본문에는 준 키만 `display_name`·`phone`(또는 `email: null`)으로 실리고 `login_id`·`role`·`id`는 없으며, 오류는 상태·`detail`을 그대로 가진 `ApiError`(409 `conflict`, 422 `validation`)다. Fake 게이트웨이도 PATCH 의미, AD 모드 이름·이메일 409, 전화 허용, 아이디·역할 불변, user 역할 허용, 세션 없음 401을 따른다

### ME-057 게이트웨이 changePassword는 PUT /me/password를 보내고 204면 끝난다
- Given 서버가 204 또는 422(현재 비밀번호 틀림·약한 비밀번호)·409·429 중 하나를 준다
- When `changePassword('old-password-1', 'Fresh-passw0rd')`를 부른다
- Then `PUT /api/v1/me/password` 본문은 `{current_password, new_password}`이고 204면 `undefined`로 끝나며, 오류는 상태·`detail`을 그대로 가진 `ApiError`(422 `validation` — 로그아웃 아님, 409 `conflict`, 429 `too-many-attempts`)다. Fake 게이트웨이도 현재 비밀번호 확인·새 비밀번호 저장·세션 유지, 틀림 422, 약한 비밀번호 422, AD 모드 409, 세션 없음 401을 따른다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(초안): 구현된 내 정보 동작을 정본 명세로 옮김. 규칙 ME-R1~R19, use case ME-UC1~UC4, BDD 케이스 ME-001~ME-057 | ME-001~ME-057(신규) |
| 2026-11-24 | 확정(2026-11-24 사용자 확인): ME-R7에 AD 전화번호 덮어쓰기 안내 추가(AU-R8a). 동작·API·화면 그대로 | 없음 |
