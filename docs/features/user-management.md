# 사용자 관리   (feature 코드: US, 상태: 확정(2026-11-20 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/web/routers/{users,user_options}.py`, `app/web/schemas/{user,user_ref,profile_changes,password_field}.py`, `app/application/user/*.py`, `app/domain/user/*.py`, `app/domain/auth/{credentials,password_policy}.py`, `app/domain/common/{contact,validation}.py`, `app/infra/db/{user_repository,user_links}.py`, `frontend/src/features/admin/users/*.tsx`, `data/users.ts`, `gateway/http/users.ts`, `gateway/http/mappers/user.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 화면·테스트가 어긋나는 점은 계획(`artifacts/10-analysis/us-plan.md`)의 확인 필요 질문으로 분리했습니다.
>
> 2026-11-13 변경(2026-11-13 사용자 확인, 구현 완료): 사용자의 **등록자**(`users.created_by_user_id`와 FK·인덱스, 응답 `created_by`, 화면 '등록자' 열)와 **퇴사 사유**(`users.delete_reason`과 CHECK 2개, `UserDeleteReason`, `DELETE`의 `reason` 쿼리, 응답 `delete_reason`, 화면 '퇴사 사유' 열)를 없앤다. 등록자는 더 이상 연결이 아니다. 마이그레이션은 SC-R21. 계획은 `artifacts/10-analysis/01-plan.md`.

## 1. 개요

- 목적: admin이 로그인할 수 있는 계정(AD 연동 또는 앱에서 직접 관리)을 등록하고, 역할·연락처를 바꾸고, 비밀번호를 재설정하고, 삭제(연결된 데이터가 있으면 퇴사 처리)한다. 다른 화면이 사용자를 고를 때 쓰는 선택 목록(`/user-options`)과 응답 속 사용자 표시 참조(`UserRef`)도 이 feature가 정한다.
- 사용자(역할): admin(관리 전부), sales·user(선택 목록 조회만).
- 범위
  - Admin > 사용자 관리 화면(`/admin/users`): 목록·상태 필터·등록·정보 수정·비밀번호 재설정·역할 변경·삭제
  - API `GET·POST /users`, `PATCH·DELETE /users/{user_id}`, `PUT /users/{user_id}/role`, `PUT /users/{user_id}/password`, `GET /user-options`
  - 사용자 아이디 형식·예약 아이디 등록 거부, 재직자 중복 판정, 퇴사 처리와 물리 삭제 판정, 마지막 admin 보호, 새 비밀번호 정책(US-R6)
  - 사용자 표시 참조 `UserRef`(이름·퇴사 표기·역할)
- 범위 밖(다른 feature)
  - 로그인·세션 발급·요청마다 활성·역할 재확인, 첫 로그인 때 AD 값으로 이름·이메일 덮어쓰기, 예약 아이디 로그인 거부, 비밀번호 해시 저장 형식(scrypt) → AU
  - 최초 설정의 첫 admin 등록·인증 방식 선택(`auth_settings`) → SU, AD 서버 설정 → IN
  - 본인 정보·본인 비밀번호 변경(`/me`) → ME
  - Owner 자격(sales만 새 Deal의 Owner) → DE, 각 화면의 사용자 선택 UI 사용(담당자 필터 등) → 소유 feature
  - 공통 권한 판정·CSRF·Problem 형식·id 경로 형식·Admin 화면 가드 → PL(PL-R4~R7, PL-R9~R12, PL-R15, PL-R23, PL-R31, PL-R35~R39)
  - users 컬럼 제거 마이그레이션의 리비전 규칙(upgrade·downgrade·하위 호환) → SC(SC-R21)
- 관련 화면·메뉴: Admin > 사용자 관리(`/admin/users`, Admin 서브 메뉴 "사용자 관리"). 옛 주소 `/users`는 PL-R32.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 아이디(login_id) | 로그인 아이디. AD 모드에서는 AD 계정 이름, local 모드에서는 앱 계정 이름. 정규화(앞뒤 공백 제거·소문자) 뒤 값으로 저장·비교한다 |
| 인증 방식 | 시스템 전역 하나: `ad`(AD 연동) 또는 `local`(앱에서 직접 관리). 저장 행이 없고 admin이나 AD 설정이 있는 기존 시스템은 `ad`로 본다(판정은 SU·AU) |
| 재직자 | `deleted_at`이 없는 사용자 행 |
| 퇴사자 | 퇴사 처리된 행(`deleted_at`이 있음). 불변 기록이며 복구하지 않는다. 퇴사 사유는 기록하지 않는다(2026-11-13) |
| 퇴사 처리 | 삭제 요청 시 다른 데이터가 그 사용자를 가리키면 행을 남기고 퇴사로 표시하는 것 |
| 물리 삭제 | 삭제 요청 시 가리키는 데이터가 없어 행을 지우는 것 |
| 연결(링크) | 다른 테이블에서 `users.id`를 FK로 가리키는 행. 세션(`auth_sessions`)·비밀번호 해시(`user_password_hashes`)는 연결이 아니다. 사용자 행은 등록자를 기록하지 않으므로(2026-11-13) 다른 사용자를 등록한 것은 연결이 아니다 |
| 표시 이름 | `display_name`. 없으면 화면·참조는 아이디를 이름으로 쓴다 |
| 사용자 참조(UserRef) | 다른 응답이 사용자를 가리킬 때의 공통 형태 `{id, name, resigned, label, role}` |
| 선택 목록 | `/user-options`. 사용자 선택 UI용 후보 전체(페이지 없음) |

### 2.2 데이터 모델

`users`(PK `id` BIGINT identity — SC 공통 규칙)

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `login_id` | varchar(64), 인덱스 `lower(login_id)`(유니크 아님) | 정규화된 아이디. 재직자 중복은 앱이 roster 잠금 안에서 확인한다(US-R3) |
| `role` | varchar(20), CHECK `admin`·`sales`·`user` | 역할(PL-R1) |
| `display_name` | varchar(200) null | 표시 이름 |
| `email` | varchar(254) null | 소문자 이메일 |
| `phone` | varchar(40) null | 전화번호(입력 그대로, 앞뒤 공백 제거) |
| `created_at`, `updated_at` | timestamptz | 등록·마지막 변경 시각(`updated_at`은 응답에 없음) |
| `last_login_at` | timestamptz null | 마지막 로그인 시각(AU가 기록) |
| `deleted_at` | timestamptz null | 퇴사 시각. 값이 있으면 퇴사자다 |

- 2026-11-13 제거: `created_by_user_id`(FK `fk_users_created_by_user_id_users`, 인덱스 `ix_users_created_by_user_id`)와 `delete_reason`(CHECK `ck_users_delete_reason_valid`·`ck_users_deleted_pair`). 그래서 `users` 테이블에는 `users`를 가리키는 FK가 없고 `deleted_at`에 걸린 CHECK도 없다. 마이그레이션은 SC-R21이다. 퇴사 사유는 항상 `resigned`였고 `deleted_at`과 짝이었으므로(CHECK 2개가 보장) 지워도 정보가 사라지지 않는다. 등록자 값은 사라지며, 이것은 데이터 삭제 금지 규칙(SC-R8)에 대해 사용자가 승인한 contract다.
- 관련 테이블: `user_password_hashes`(users FK CASCADE, AU 소유 — 등록·재설정·삭제 때 이 feature가 쓰거나 지운다), `auth_sessions`(AU 소유 — 재설정·삭제 때 대상 행을 지운다).
- 연결로 세는 FK(현재 17종): `deals.owner_user_id`, `deal_history.changed_by_user_id`, `deal_actions.actor_user_id`, `directory_settings.updated_by_user_id`, `bant_labels.created_by_user_id`, `action_types.created_by_user_id`, `storage_settings.updated_by_user_id`, `deal_attachments.uploaded_by_user_id`, `alert_settings.updated_by_user_id`, `forecast_snapshot_cells.owner_user_id`, `reports.owner_user_id`, `reports.updated_by_user_id`, `partner_meetings.created_by_user_id`, `license_contracts.created_by_user_id`, `license_contracts.updated_by_user_id`, `license_contract_attachments.uploaded_by_user_id`, `deal_comments.author_user_id`(Comment 작성자). 연결 판정은 ORM 메타데이터에서 users를 가리키는 모든 FK(세션·해시 제외)를 모으므로 새 FK가 생기면 자동으로 포함된다.
- 값 객체: `UserStatusFilter`(`active`·`resigned`·`all`), `DeleteOutcome`(`deleted`·`resigned`), `ProfileChanges`(보내지 않은 칸 = 그대로, null = 비움). `UserDeleteReason`은 2026-11-13에 없앴다.

### 2.3 비즈니스 규칙

등록
- **US-R1** 아이디는 앞뒤 공백을 지우고 소문자로 바꾼 값이 ASCII이며 정규식 `[a-z0-9][a-z0-9._-]{0,63}`(1~64자, 첫 글자는 영문 소문자·숫자)에 맞아야 한다. 아니면 422 `invalid-value` "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다"이고 저장하지 않는다. 대문자는 소문자로 바뀌어 저장된다.
- **US-R2** 예약 아이디 `dev-admin`·`dev-sales`·`dev-user`(정규화 값이 정확히 같을 때)는 등록할 수 없다: 422 `invalid-value` "개발 로그인 전용 아이디는 등록할 수 없습니다: <정규화 아이디>". 그 밖의 `dev-`로 시작하는 아이디는 일반 아이디다. (예약 아이디의 로그인 거부는 AU.)
- **US-R3** 정규화한 아이디가 같은 재직자가 이미 있으면 409 `already-exists` "이미 존재하는 사용자입니다: <정규화 아이디>"이고 사용자 수는 그대로다. 퇴사자나 물리 삭제된 사용자의 아이디는 다시 등록할 수 있고, 다시 등록하면 **항상 새 행(새 id)** 이 생기며 기존 퇴사 행과 그 행을 가리키는 이력은 그대로 남는다. 같은 아이디의 퇴사 행은 여러 개 있을 수 있고 재직 행은 최대 하나다.
- **US-R4** AD 모드 등록: 비밀번호를 받지 않는다(보내면 422 `invalid-value` "AD 연동에서는 비밀번호를 입력하지 않습니다."). 표시 이름·이메일·전화는 선택이다. 아이디가 AD에 있는지 묻지 않는다(디렉터리 호출 없음). 비밀번호 해시를 저장하지 않는다. 등록 때 준 이름은 첫 로그인 전까지 보이고, 로그인하면 AD 값으로 덮어쓴다(AU).
- **US-R5** local 모드 등록: 비밀번호와 이름이 필수다. 비밀번호가 없으면(키 없음·null) 422 `invalid-value` "비밀번호를 입력하세요.", 이름이 없거나 공백뿐이면 422 `invalid-value` "이름은(는) 비어 있을 수 없습니다". 비밀번호는 US-R6을 통과해야 하며, 해시를 사용자 행과 같은 트랜잭션에 저장한다(해시 계산은 트랜잭션 밖). 등록된 사용자는 그 비밀번호로 로그인할 수 있다(AU).
- **US-R6** 새 비밀번호 정책(등록·재설정 공통. SU 첫 admin·ME 비밀번호 변경도 같은 정책을 쓴다): ① 공백만이거나 빈 값이면 422 `invalid-value` "비밀번호는 비어 있을 수 없습니다", NUL 문자가 있으면 "비밀번호에는 NUL 문자를 쓸 수 없습니다" ② 257자 이상이면 422 `request-validation`(256자는 허용) ③ 8자 미만이면 "비밀번호는 8자 이상이어야 합니다" ④ 앞뒤 공백을 지우고 소문자로 바꾼 값이 아이디와 같으면 "비밀번호는 아이디와 같을 수 없습니다". ①·③·④는 422 `invalid-value`이고 `errors` = `[{"location": ["password"], "message": <문구>}]`이다. 비밀번호 원문은 앞뒤 공백을 지우지 않고 그대로 해시한다. 조합 규칙·만료는 없다.
- **US-R7** 프로필 값(등록·정보 수정 공통). 자르지 않고 거절하며 모두 422 `invalid-value`(칸 위치 `errors` 없음):
  - 이름: 앞뒤 공백 제거, 최대 200자. 필수인 경우(local) 문구는 "이름은(는) 비어 있을 수 없습니다"·"이름은(는) 200자를 넘을 수 없습니다"·"이름에는 NUL 문자를 쓸 수 없습니다". 선택인 경우(AD 등록) 빈 값·공백뿐·null은 이름 없음이고 문구의 칸 이름은 "표시 이름"이다("표시 이름은(는) 200자를 넘을 수 없습니다", "표시 이름에는 NUL 문자를 쓸 수 없습니다").
  - 이메일: 빈 값·공백뿐·null은 없음. 앞뒤 공백 제거·소문자, 254자 이하, `^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$`. 아니면 "이메일 형식이 올바르지 않습니다.", NUL은 "이메일에는 NUL 문자를 쓸 수 없습니다".
  - 전화: 빈 값·공백뿐·null은 없음. 앞뒤 공백 제거, 40자 이하, 문자는 숫자·`+`·`-`·공백·괄호만, 숫자 7~15개. 아니면 "전화번호 형식이 올바르지 않습니다.", NUL은 "전화번호에는 NUL 문자를 쓸 수 없습니다".
- **US-R8** 등록 결과: 201, `Location: /api/v1/users/<id>`, 본문 `UserResponse`. `created_at` = 서버 시각, `last_login_at` = null, `status` = `active`. 누가 등록했는지는 기록하지 않는다(2026-11-13). 요청한 admin의 행이 요청 처리 중에 지워졌는지는 등록이 따로 확인하지 않는다(요청마다의 활성 확인은 AU, 확인 필요 Q1).
- **US-R9** 등록 판정 순서: ① 요청 형식 422 `request-validation`(`login_id`·`role` 누락, `role`이 3값이 아님·null, `login_id`가 문자열이 아님, 모르는 필드, 비밀번호 257자 이상) ② 비밀번호 빈 값·NUL 422(위치 `password`) ③ 아이디 형식(US-R1) ④ 예약 아이디(US-R2) ⑤ 프로필 값(US-R7, local은 이름 필수) ⑥ 모드별 비밀번호(US-R4·US-R5, 정책 US-R6) ⑦ 재직자 중복 409(US-R3).

목록
- **US-R10** `GET /users`는 admin 전용이다. `status`는 `active`(기본, 재직자만)·`resigned`(퇴사자만)·`all`(둘 다)이고, 정렬은 등록 시각·id 오름차순이다. `offset` 0 이상(기본 0), `limit` 1~200(기본 50). 범위 밖 값이나 다른 `status`는 422 `request-validation`. 응답은 `{items, offset, limit}`(전체 개수 없음)이고 `offset`·`limit`은 요청 값을 되돌린다.
- **US-R11** 목록 항목(`UserResponse`) 필드는 정확히 `id`, `login_id`, `role`, `display_name`, `email`, `phone`, `created_at`, `last_login_at`(로그인한 적 없으면 null), `status`(`active`·`resigned`), `deleted_at`(재직자면 null) 10개다. `created_by`·`delete_reason`은 없다(2026-11-13 제거). 비밀번호·해시 관련 값은 어떤 응답에도 없다(PL-R23). 등록·역할 변경·정보 수정 응답도 같은 형태다.
- **US-R12** 사용자 참조(`UserRef`): `name` = 표시 이름(없거나 빈 값이면 아이디), `resigned` = 퇴사 여부, `label` = 퇴사자면 `<name>(퇴사)` 아니면 `<name>`, `role` = 현재 역할(퇴사자도 자기 역할). 아이디 필드는 없다. 다른 feature 응답의 사용자 필드(BANT Label·Action 유형의 `created_by`, Deal Owner 등)도 이 형태이며 퇴사자도 가리킨다.

역할 변경
- **US-R13** `PUT /users/{user_id}/role` 본문 `{role}`(admin 전용). 판정 순서: 없는 id 404 `not-found` "사용자을(를) 찾을 수 없습니다: <id>" → 퇴사자 409 `invalid-state` "이미 퇴사 처리된 사용자입니다" → 자기 자신 409 "자기 자신의 역할은 바꿀 수 없습니다." → 대상이 admin이고 새 역할이 admin이 아니며 재직 admin이 1명 이하면 409 "마지막 관리자의 역할은 바꿀 수 없습니다.". 지금과 같은 역할이면 200으로 대상을 그대로 돌려주고 저장하지 않는다(`updated_at` 그대로). 바뀌면 200 `UserResponse`이고 저장된 `updated_at`이 서버 시각이 된다. 대상의 세션은 유지되고 바뀐 역할은 그 사용자의 다음 요청부터 적용된다(요청마다 역할 재확인은 AU). 역할 변경 이력은 남기지 않는다. `role` 누락·3값 밖·모르는 필드는 422 `request-validation`.

정보 수정
- **US-R14** `PATCH /users/{user_id}` 본문 `{display_name?, email?, phone?}`(admin 전용, PATCH: 보낸 키만 바꾸고 null·빈 값은 비운다). 아이디·역할·비밀번호 등 다른 키는 422 `request-validation`. 판정 순서: AD 모드에서 `display_name`이나 `email` 키를 보내면(값과 무관) 409 `invalid-state` "AD 연동 사용자의 이름·이메일은 AD에서 관리합니다." → 없는 id 404 → 퇴사자 409 "이미 퇴사 처리된 사용자입니다" → 값 검증 422(US-R7, local은 이름을 비울 수 없음 "이름은(는) 비어 있을 수 없습니다"). 모든 값을 검증한 뒤에 적용한다. 바뀐 값이 없으면 저장하지 않고 200(`updated_at` 그대로). AD 모드는 전화만 고칠 수 있다. 대상이 요청자 자신이어도 API는 거절하지 않는다(화면은 본인 행에 버튼을 두지 않음, US-R23).

비밀번호 재설정
- **US-R15** `PUT /users/{user_id}/password` 본문 `{password}`(admin 전용). 판정 순서: 비밀번호 빈 값·NUL 422(위치 `password`)·257자 이상 422 `request-validation` → local 모드가 아니면 409 `invalid-state` "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."(없는 id여도) → 없는 id 404 → 퇴사자 409 "이미 퇴사 처리된 사용자입니다" → 자기 자신 409 "자기 자신의 비밀번호는 내 정보에서 바꾸세요." → 정책 422(US-R6 ③④, 위치 `password`). 성공하면 204(본문 없음): 대상의 해시를 새 값으로 저장(없던 사용자도 새로 생김)하고 **대상의 세션을 모두 지운다**. 다른 사용자의 세션·해시는 그대로다. 다음 로그인 때 변경을 강제하지 않는다. 실패하면 해시·세션이 바뀌지 않는다.

삭제·퇴사
- **US-R16** `DELETE /users/{user_id}`(admin 전용)는 쿼리 파라미터를 받지 않는다. 어떤 쿼리 파라미터든(2026-11-13에 없앤 `reason` 포함, 값과 무관) 보내면 422 `request-validation`이고 사용자는 그대로다(없앤 파라미터를 조용히 무시하지 않음 — DL-047·PA-029와 같은 방침, 확인 필요 Q2). 판정 순서: 쿼리 422 → 없는 id(물리 삭제된 id 포함) 404 → 이미 퇴사자 409 `invalid-state` "이미 퇴사 처리된 사용자입니다" → 자기 자신 409 "자기 자신은 삭제할 수 없습니다"(연결 유무와 무관, 요청자 세션 유지) → 대상이 admin이고 재직 admin이 1명 이하면 409 "마지막 관리자는 삭제할 수 없습니다". 관리자 가드 403(2.5)은 쿼리 검사보다 먼저다.
- **US-R17** 대상에 연결(2.2의 17종)이 하나라도 있으면 퇴사 처리한다: 행·연결은 남고 `deleted_at` = 서버 시각, 응답 200 `{"outcome": "resigned"}`. 연결이 없으면 행을 지우고 200 `{"outcome": "deleted"}`이며 어떤 `status` 목록에도 나오지 않는다. 연결 확인 뒤 물리 삭제가 FK에 막히면 퇴사 처리로 바꾼다(결과 `resigned`). 다른 사용자를 등록한 것은 연결이 아니다: 다른 연결이 없는 admin은 그가 등록한 사용자가 남아 있어도 물리 삭제되고, 그 사용자들은 재직 그대로다(2026-11-13).
- **US-R18** 삭제·퇴사 어느 쪽이든 대상의 세션 행과 비밀번호 해시를 모두 지운다. 그래서 그 사용자의 기존 세션은 다음 요청부터 401이고 다시 로그인할 수 없다(퇴사자 로그인 거부는 AU). 퇴사 행은 불변이다: 역할 변경·정보 수정·비밀번호 재설정·재삭제는 409 "이미 퇴사 처리된 사용자입니다"이고 복구 API는 없다. 사용자를 지워도 최초 설정이 다시 열리지 않는다(SU).
- **US-R19** 마지막 admin 판정의 "재직 admin 수"는 퇴사한 admin을 세지 않는다. API로는 요청자 자신이 재직 admin이므로 보통 자기 자신 규칙(US-R13·US-R16)에 먼저 걸리고, 이 규칙은 그 밖의 경우를 막는 방어 규칙이다.

선택 목록
- **US-R20** `GET /user-options`는 로그인한 모든 역할이 부른다(역할 가드 없음). 쿼리: `include_resigned`(불리언, 기본 false = 재직자만), `keyword`(최대 100자), `role`(`admin`·`sales`·`user`, 없으면 모든 역할). 모르는 파라미터(`limit`·`offset` 포함)·형식 오류는 422 `request-validation`. 응답은 `{items: UserOption[]}`로 조건에 맞는 사용자 **전부**(페이지 없음, 200명 초과도 전부)를 등록 시각·id 순으로 돌려준다. `keyword`는 화면 이름(표시 이름, 없거나 빈 값이면 아이디)의 부분 일치이고 대소문자를 무시하며 `%`·`_`는 글자로 취급한다. 표시 이름이 있는 사용자는 아이디로 찾아지지 않는다. 항목(`UserOption`)은 UserRef(`id`·`name`·`resigned`·`label`·`role`)에 `login_id`(문자열, null 아님)를 더한 것이다(2026-11-20, 사용자 결정 — Deals 목록 담당자 후보 `이름 (아이디)` 표시, DL-R40).
- `login_id`는 재직·퇴사와 역할에 관계없이 모든 항목에 항상 있다.
- 이 경로는 로그인한 모든 역할(admin·sales·user)이 부르므로, 로그인한 사용자는 누구나 다른 사용자의 로그인 아이디를 볼 수 있다(사용자 수용 2026-11-20).
- 이메일 필드는 계속 없다.
- `keyword`는 여전히 화면 이름만 찾는다. 아이디로는 찾지 않는다.
- 다른 응답 속 UserRef(Deal 담당자·작성자 등)에는 `login_id`가 없다.
- 다른 화면의 사용자 선택 상자(Deal 등록 Owner, Dashboard·Forecast·계약·파트너 Activity·Actions 검색·Reports) 표시는 바꾸지 않는다. 계속 이름, 퇴사자는 `이름(퇴사)`다. 조건은 모두 AND다.
- **US-R21** 사용자 한 명을 읽거나 통째로 바꾸는 API는 없다: `GET`·`PUT`·`POST /users/{user_id}`는 405다(정보 수정은 `PATCH`, US-R14).

화면(frontend, `/admin/users`, 가드 PL-R31)
- **US-R22** 화면 틀: 제목(h2) "사용자 관리", 인증 방식(`/auth/config`의 `auth_mode`)을 읽은 뒤 등록 폼(US-R24), "상태" 선택(재직·퇴사·전체, 기본 재직 — 고르면 그 `status`로 다시 조회), 사용자 표. 표 머리글 9칸: 아이디, 역할, 이름, 이메일, 전화번호, 등록일, 마지막 로그인, 퇴사 일시, 작업(화면 읽기 전용 이름). '등록자'·'퇴사 사유' 열은 없다(2026-11-13). 칸 값: 역할은 `admin`·`sales`·`user` 그대로, 이름은 퇴사자면 `이름(퇴사)`, 없는 값은 `-`, 시각은 TM 표기. 빈 목록 행은 9칸을 차지한다. 목록·설정을 읽는 동안 "불러오는 중…". 빈 목록이면 "등록된 사용자가 없습니다."(퇴사 필터는 "퇴사한 사용자가 없습니다.").
- **US-R23** 행 작업 버튼은 **재직자이고 로그인한 admin 본인이 아닌 행**에만 있다: "정보 수정", (local 모드만) "재설정"(접근 이름 "비밀번호 재설정"), "역할 변경", "삭제". 퇴사 행·본인 행에는 버튼이 없다. AD 모드 화면에는 "비밀번호"라는 글자·칸·버튼이 없다.
- **US-R24** 등록 폼(form 이름 "사용자 등록", 제목 "사용자 등록", 버튼 "추가"): 칸은 AD 모드 "AD 아이디"·이름·이메일·전화번호·역할, local 모드 "아이디"·비밀번호·비밀번호 확인·이름·이메일·전화번호·역할. 역할 기본값 sales. 요청 전 검사: 아이디나 이름이 비었으면(local은 비밀번호도) 요청 없이 "AD 아이디와 이름을 입력하세요."(AD)·"아이디, 비밀번호, 이름을 입력하세요."(local), local에서 비밀번호와 확인이 다르면 "비밀번호 확인이 일치하지 않습니다.". 아이디·이름·이메일·전화는 앞뒤 공백을 지워 보내고 빈 이메일·전화는 보내지 않는다. 성공하면 모든 칸을 비우고 목록을 다시 읽는다(별도 알림 없음). 서버가 거절하면 서버 문구를 폼 위에 보이고 비밀번호·확인 칸만 비운다(다른 입력은 유지). 오류 `errors[].location`의 첫 조각이 `login_id`·`password`·`display_name`·`email`·`phone`이면 그 칸을 오류로 표시한다. 입력한 비밀번호는 요청이 끝나면 요청 캐시에 남지 않는다.
- **US-R25** 정보 수정 대화상자(제목 "정보 수정"): 안내 "<아이디> 사용자의 정보를 고칩니다. 아이디와 역할은 여기서 바꿀 수 없습니다.", 칸 이름·이메일·전화번호에 현재 값(없으면 빈 칸). AD 모드는 이름·이메일 칸을 비활성으로 두고 "이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다."를 보인다. 바뀐 칸만 보내며(앞뒤 공백 제거, 비운 이메일·전화는 null) 바뀐 칸이 없으면 "저장"이 비활성이다. 성공하면 닫고 목록을 다시 읽는다. 실패하면 대화상자 안에 서버 문구를 보이고 열어 둔다. "취소"는 요청 없이 닫는다.
- **US-R26** 비밀번호 재설정 대화상자(제목 "비밀번호 재설정", local 모드만): 안내 "<아이디> (<이름>) 사용자의 비밀번호를 새로 정합니다."·"재설정하면 그 사용자의 로그인이 모두 종료됩니다. 새 비밀번호는 직접 전달하세요.", 칸 "새 비밀번호"·"새 비밀번호 확인", 버튼 "재설정". 두 칸이 다르면 요청 없이 "새 비밀번호 확인이 일치하지 않습니다.". 성공하면 닫고 페이지 알림 "<아이디> 사용자의 비밀번호가 재설정되었습니다. 그 사용자의 로그인은 모두 종료됩니다.". 실패하면 서버 문구를 보이고 두 칸을 비우며 열어 둔다(`password` 위치 오류는 새 비밀번호 칸 표시). 비밀번호는 요청 캐시에 남지 않는다.
- **US-R27** 역할 변경 대화상자(제목 "역할 변경", 버튼 "변경"): 안내 "<아이디> (<이름>) 사용자의 역할을 바꿉니다."·"바뀐 역할은 그 사용자의 다음 요청부터 적용됩니다(다시 로그인할 필요 없음).", "역할" 선택지 admin·sales·user(현재 역할 선택). 현재와 같은 역할이면 "변경"이 비활성이다. 지금 sales인 사용자에게 다른 역할을 고르면 "sales가 아니면 새 Deal의 Owner로 지정할 수 없습니다. 이미 Owner인 Deal은 그대로 남습니다."를 보인다. 성공하면 닫고 알림 "<아이디> 사용자의 역할이 <이전>에서 <새 역할>(으)로 바뀌었습니다."를 보이며 역할 칸이 바뀐다. 실패하면 닫고 페이지 오류 배너에 서버 문구를 보인다. "취소"는 요청 없이 닫는다.
- **US-R28** 삭제 확인 대화상자(제목 "사용자 삭제", 위험 버튼 "삭제"): "<아이디> (<이름>) 사용자를 삭제할까요?"·"연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다."·"로그인 세션은 모두 종료됩니다.". 성공하면 결과에 따라 알림 "<아이디> 사용자가 퇴사 처리되었습니다." 또는 "<아이디> 사용자가 삭제되었습니다."를 보이고 목록을 다시 읽는다. 실패하면 대화상자를 닫고 페이지 오류 배너에 서버 문구를 보인다. "취소"는 요청 없이 닫는다.
- **US-R29** 페이지 알림·오류: 목록·설정·삭제·역할 변경 오류는 페이지 오류 배너 하나에 보인다(문구 PL-R37). 새 작업(삭제·역할 변경·정보 수정·재설정 시작)을 하면 이전 성공 알림을 지운다. 알림은 닫을 수 있다.
- **US-R30** 캐시 갱신: 등록 성공 뒤 사용자 목록·선택 목록을, 역할 변경·삭제·정보 수정 성공 뒤 사용자 목록·선택 목록·Deal·Forecast 조회를 다시 읽게 한다. 재설정은 캐시를 바꾸지 않는다.
- **US-R31** 게이트웨이(`gateway/http/users.ts`): 목록은 `limit=200`으로 가득 찬 페이지가 오는 동안 `offset`을 늘려 이어 읽고(최대 50페이지) 덜 찬 페이지에서 멈춘다. 선택 목록은 요청 한 번이며 `limit`·`offset`을 보내지 않고, `include_resigned`(기본 false)와 `role`(있을 때만)을 보낸다. 등록 본문은 `login_id`·`role`·`display_name`과, 값이 있을 때만 `password`·`email`·`phone`. 정보 수정은 준 키만 `PATCH`(null은 비움), 재설정은 `PUT …/password`(204), 역할 변경은 `PUT …/role`, 삭제는 쿼리 없이 `DELETE /users/{id}`이고 결과(`deleted`·`resigned`)를 돌려준다. 응답 변환: 화면 이름 = `display_name ?? login_id`, 퇴사 시각 = `deleted_at`, UserRef의 `role`은 서버 값 그대로, 선택 목록 항목의 `login_id` → `loginId`(2026-11-20), `resigned` → 상태 `resigned`. 화면 모델 `User`에는 등록자·퇴사 사유 필드가 없다(2026-11-13).

### 2.4 상태와 전이

| 현재 | 행동 | 다음 | 조건 |
| --- | --- | --- | --- |
| (없음) | 등록 | 재직 | US-R1~R9 |
| 재직 | 역할 변경·정보 수정·재설정 | 재직 | US-R13~R15 |
| 재직 | 삭제 | 퇴사(행 남음) | 연결 있음(US-R17) |
| 재직 | 삭제 | (없음, 물리 삭제) | 연결 없음(다른 사용자를 등록한 것은 연결 아님) |
| 퇴사 | 모든 변경·삭제 | — | 409(US-R18) |
| 퇴사·(없음) | 같은 아이디 등록 | 새 행 재직 | US-R3 |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /users`(목록) | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| `POST /users`, `PATCH /users/{id}`, `PUT /users/{id}/role`, `PUT /users/{id}/password`, `DELETE /users/{id}` | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능(자기 자신 제한: US-R13·R15·R16) |
| `GET /user-options` | 401 | 가능 | 가능 | 가능 |
| 화면 `/admin/users` | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

`/users*`는 관리자 가드(PL-R7, "관리자 권한이 필요합니다")와 CSRF(PL-R9)가 걸린다. `/user-options`는 업무 조회(PL-R2)다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/users` | query `status`(`active`·`resigned`·`all`, 기본 `active`), `offset`(≥0), `limit`(1~200, 기본 50) | 200 `Page[UserResponse]` `{items, offset, limit}` | 422 |
| POST `/users` | `UserRequest` `{login_id: str, role: Role, display_name?: str\|null, email?: str\|null, phone?: str\|null, password?: str\|null(≤256)}` | 201 `UserResponse` + `Location` | 409 `already-exists`, 422 `invalid-value`·`request-validation` |
| PATCH `/users/{user_id}` | `UserProfileRequest` `{display_name?, email?, phone?}`(모두 nullable) | 200 `UserResponse` | 404, 409 `invalid-state`, 422 |
| PUT `/users/{user_id}/role` | `UserRoleRequest` `{role}` | 200 `UserResponse` | 404, 409 `invalid-state`, 422 |
| PUT `/users/{user_id}/password` | `UserPasswordRequest` `{password: str(≤256)}` | 204 | 404, 409 `invalid-state`, 422 |
| DELETE `/users/{user_id}` | 쿼리 없음(어떤 쿼리든 422 `request-validation`) | 200 `DeleteUserResponse` `{outcome: "deleted"\|"resigned"}` | 404, 409 `invalid-state`, 422 |
| GET `/user-options` | query `include_resigned`(bool, 기본 false), `keyword`(≤100), `role` | 200 `UserOptionPage` `{items: UserOption[]}`(UserRef + `login_id: string`, 2026-11-20 하위 호환 추가) | 422 |
| GET·PUT·POST `/users/{user_id}` | — | — | 405 |

- `UserResponse`·`UserRef` 필드는 US-R11·US-R12. 공통 오류(401·403·CSRF·id 형식 422)는 PL. 모든 본문은 모르는 필드를 거부한다(422 `request-validation`).
- 2026-11-13 호환 깨짐(사용자 승인, 클라이언트는 이 저장소 프런트뿐): `UserResponse`에서 `created_by`·`delete_reason` 제거, OpenAPI 스키마 `UserDeleteReason` 제거, `DELETE /users/{user_id}`의 `reason` 쿼리 제거(보내면 422), `POST /users`의 401(요청자 행 없음) 응답 제거.

### 2.7 화면 동작

US-R22~US-R31.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 아이디 형식 | 422 `invalid-value` | 로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다 |
| 예약 아이디 | 422 `invalid-value` | 개발 로그인 전용 아이디는 등록할 수 없습니다: <아이디> |
| 재직자 중복 | 409 `already-exists` | 이미 존재하는 사용자입니다: <아이디> |
| AD 모드 등록에 비밀번호 | 422 `invalid-value` | AD 연동에서는 비밀번호를 입력하지 않습니다. |
| local 모드 등록에 비밀번호 없음 | 422 `invalid-value` | 비밀번호를 입력하세요. |
| 비밀번호 빈 값 / NUL | 422 `invalid-value` + `errors[{location:["password"]}]` | 비밀번호는 비어 있을 수 없습니다 / 비밀번호에는 NUL 문자를 쓸 수 없습니다 |
| 비밀번호 8자 미만 / 아이디와 같음 | 422 `invalid-value` + `errors[{location:["password"]}]` | 비밀번호는 8자 이상이어야 합니다 / 비밀번호는 아이디와 같을 수 없습니다 |
| 이름(필수) 빈 값 / 200자 초과 / NUL | 422 `invalid-value` | 이름은(는) 비어 있을 수 없습니다 / 이름은(는) 200자를 넘을 수 없습니다 / 이름에는 NUL 문자를 쓸 수 없습니다 |
| 이름(AD 등록, 선택) 200자 초과 / NUL | 422 `invalid-value` | 표시 이름은(는) 200자를 넘을 수 없습니다 / 표시 이름에는 NUL 문자를 쓸 수 없습니다 |
| 이메일 | 422 `invalid-value` | 이메일 형식이 올바르지 않습니다. / 이메일에는 NUL 문자를 쓸 수 없습니다 |
| 전화 | 422 `invalid-value` | 전화번호 형식이 올바르지 않습니다. / 전화번호에는 NUL 문자를 쓸 수 없습니다 |
| 사용자 삭제에 쿼리 파라미터 | 422 `request-validation` | (요청 형식 오류 공통 문구, PL) |
| 없는 사용자 | 404 `not-found` | 사용자을(를) 찾을 수 없습니다: <id> |
| 퇴사자 변경·재삭제 | 409 `invalid-state` | 이미 퇴사 처리된 사용자입니다 |
| 자기 자신 삭제 | 409 `invalid-state` | 자기 자신은 삭제할 수 없습니다 |
| 마지막 admin 삭제 | 409 `invalid-state` | 마지막 관리자는 삭제할 수 없습니다 |
| 자기 자신 역할 변경 | 409 `invalid-state` | 자기 자신의 역할은 바꿀 수 없습니다. |
| 마지막 admin 강등 | 409 `invalid-state` | 마지막 관리자의 역할은 바꿀 수 없습니다. |
| AD 모드 이름·이메일 수정 | 409 `invalid-state` | AD 연동 사용자의 이름·이메일은 AD에서 관리합니다. |
| AD 모드 비밀번호 재설정 | 409 `invalid-state` | 앱에서 계정을 직접 관리할 때만 쓸 수 있습니다. |
| 자기 자신 비밀번호 재설정 | 409 `invalid-state` | 자기 자신의 비밀번호는 내 정보에서 바꾸세요. |

화면 문구: US-R22~US-R28(요청 전 검사 문구, 알림, 대화상자 안내). 서버 문구 표시는 PL-R37.

## 3. Business use case

### US-UC1 사용자 목록 보기
- 행위자: admin
- 사전 조건: admin으로 로그인, `/admin/users`
- 기본 흐름: 화면이 인증 방식과 재직자 목록을 읽어 표로 보인다(US-R10~R12, US-R22·R23)
- 대안: "상태"로 퇴사·전체를 고른다
- 예외: 목록을 읽지 못하면 오류 배너, 빈 목록이면 빈 메시지
- 결과: 상태별 사용자와 행 작업 버튼

### US-UC2 AD 계정 등록
- 행위자: admin
- 사전 조건: 인증 방식 `ad`
- 기본 흐름: AD 아이디·이름·(이메일·전화)·역할 입력 → 추가 → 201, 목록에 행 추가(US-R1~R4, R7~R9, R24)
- 대안: 이름 없이 API로 등록(화면은 이름 필수)
- 예외: 형식·예약 아이디 422, 비밀번호를 보냄 422, 재직자 중복 409
- 결과: 재직 사용자. 첫 AD 로그인 때 이름·이메일이 AD 값이 된다(AU). 등록한 admin은 기록되지 않는다

### US-UC3 앱 계정 등록(local)
- 행위자: admin
- 사전 조건: 인증 방식 `local`
- 기본 흐름: 아이디·비밀번호·확인·이름·(이메일·전화)·역할 → 추가 → 201, 해시 저장(US-R5·R6)
- 예외: 비밀번호 없음·약함·확인 불일치(화면), 이름 없음 422, 중복 409
- 결과: 그 비밀번호로 로그인할 수 있는 재직 사용자

### US-UC4 역할 변경
- 행위자: admin
- 사전 조건: 대상이 재직자이고 본인이 아님
- 기본 흐름: 역할 변경 → 새 역할 선택 → 변경 → 200(US-R13, R27)
- 대안: 같은 역할이면 변경 불가(화면)·무변경 200(API)
- 예외: 자기 자신·퇴사자·마지막 admin 강등 409, 없는 id 404
- 결과: 대상의 다음 요청부터 새 권한(세션 유지)

### US-UC5 사용자 정보 수정
- 행위자: admin
- 기본 흐름: 정보 수정 → 바뀐 칸 저장 → 200(US-R14, R25)
- 대안: AD 모드는 전화만
- 예외: AD 이름·이메일 409, 퇴사자 409, 값 오류 422, 없는 id 404
- 결과: 바뀐 프로필(아이디·역할 그대로)

### US-UC6 비밀번호 재설정
- 행위자: admin
- 사전 조건: local 모드, 대상이 다른 재직자
- 기본 흐름: 재설정 → 새 비밀번호·확인 → 204(US-R15, R26)
- 예외: AD 모드·자기 자신·퇴사자 409, 약한 비밀번호 422, 없는 id 404, 확인 불일치(화면)
- 결과: 대상의 로그인이 모두 끝나고 새 비밀번호로만 들어간다

### US-UC7 사용자 삭제(퇴사 처리)
- 행위자: admin
- 기본 흐름: 삭제 → 확인 → 연결 있으면 퇴사 처리, 없으면 물리 삭제(US-R16~R19, R28)
- 대안: 다른 사용자를 등록했을 뿐 다른 연결이 없는 사용자는 물리 삭제된다(US-R17)
- 예외: 자기 자신·이미 퇴사·마지막 admin 409, 없는 id 404, 쿼리 파라미터를 보냄 422
- 결과: 대상의 세션·해시가 지워지고 로그인할 수 없다. 퇴사자는 이력과 함께 남는다

### US-UC8 사용자 선택 목록 조회
- 행위자: 로그인한 모든 역할(화면의 사용자 선택 UI)
- 기본 흐름: `GET /user-options`(조건) → 조건에 맞는 UserOption(UserRef + `login_id`) 전부(US-R20, R12)
- 예외: 잘못된 파라미터 422
- 결과: 이메일 없이 이름·로그인 아이디(`login_id`)·퇴사 표기·역할을 가진 후보 목록(2026-11-20: 아이디 포함으로 변경)

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin, 로그인한 본인), BOSS(다른 admin), KIM(sales), VIEWER(user). 별도 언급이 없으면 인증 방식은 `ad`다. backend 케이스는 Fake UoW·Fake 해시·Fake 디렉터리를 쓰는 유스케이스·web 단위 테스트, frontend 케이스는 Fake 게이트웨이를 쓰는 Vitest다. 2026-11-13 변경 케이스의 "테스트 위치"는 바뀌기 전 위치이며 test-engineer가 고쳐 채운다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| US-001 | AD 모드에서 아이디·역할로 등록하면 201과 Location·사용자가 돌아오고 본문에 등록자·퇴사 사유가 없다 | US-R8, US-R11, US-R4, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_stores_the_chosen_role`<br>`application/test_user_register_list.py::test_register_user_by_another_admin_stores_no_creator_and_leaves_no_link`<br>`web/test_user_routes.py::test_register_returns_201_with_location_and_the_documented_body` |
| US-002 | 아이디의 앞뒤 공백과 대문자는 정규화되어 저장된다 | US-R1, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_normalizes_the_login_id` |
| US-003 | 64자 아이디는 등록된다 | US-R1, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_accepts_a_64_character_login_id` |
| US-004 | 형식에 맞지 않거나 65자인 아이디는 422이고 저장되지 않는다 | US-R1, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_rejects_a_malformed_login_id` |
| US-005 | 예약 아이디 세 개는 대소문자와 무관하게 등록할 수 없다 | US-R2, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_local_rejects_a_reserved_login_id`<br>`application/test_user_register_list.py::test_register_user_rejects_the_reserved_dev_login_ids` |
| US-006 | 예약 아이디가 아닌 dev- 아이디는 등록된다 | US-R2, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_accepts_a_dev_prefixed_login_id_that_is_not_reserved` |
| US-007 | 재직 중인 아이디는 대소문자·공백이 달라도 409이고 퇴사 행이 있어도 마찬가지다 | US-R3, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_local_rejects_a_duplicate_active_login_id`<br>`application/test_user_register_list.py::test_register_user_rejects_an_active_duplicate`<br>`application/test_user_register_list.py::test_duplicate_active_login_id_is_rejected_without_adding_a_user`<br>`application/test_user_reregister.py::test_register_conflicts_with_an_active_user_even_if_older_rows_resigned`<br>`application/test_user_reregister.py::test_second_sequential_registration_of_the_same_login_id_conflicts` |
| US-008 | 퇴사한 아이디를 다시 등록하면 새 행이 생기고 퇴사 행은 그대로다 | US-R3, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_local_allows_a_resigned_login_id_to_register_again`<br>`application/test_user_reregister.py::test_register_after_resignation_creates_a_new_user_with_a_new_id`<br>`application/test_user_reregister.py::test_old_row_stays_resigned_and_unchanged_after_reregistration`<br>`application/test_user_reregister.py::test_history_stays_attached_to_the_resigned_row_not_the_new_one`<br>`domain/test_user_resign.py::test_registering_the_same_login_id_again_creates_a_new_row_with_a_new_id` |
| US-009 | 물리 삭제된 아이디는 다시 등록되고 새 id를 받는다 | US-R3, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_allows_a_login_id_whose_user_was_physically_deleted` |
| US-010 | 등록은 AD에 계정이 있는지 묻지 않는다 | US-R4, US-UC2 | backend | `application/test_user_register_list.py::test_register_user_does_not_ask_the_directory` |
| US-011 | AD 모드에서 비밀번호를 보내면 422이고 저장되지 않는다 | US-R4, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_ad_rejects_password`<br>`web/test_local_user_routes.py::test_ad_registration_with_a_password_is_422` |
| US-012 | AD 모드 등록의 이름은 선택이고 주면 첫 로그인 전에도 보인다 | US-R4, US-R7, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_ad_accepts_phone_and_email_and_stores_no_hash`<br>`application/test_user_register_display_name.py::test_register_user_stores_the_given_display_name`<br>`application/test_user_register_display_name.py::test_list_users_shows_the_registered_display_name_before_the_first_login`<br>`application/test_user_register_display_name.py::test_register_user_without_a_usable_display_name_stores_none`<br>`application/test_user_register_display_name.py::test_register_user_default_display_name_is_none`<br>`domain/test_user_register_display_name.py::test_register_with_a_display_name_keeps_it_before_any_login`<br>`domain/test_user_register_display_name.py::test_register_without_a_usable_display_name_leaves_it_unset`<br>`web/test_user_request_schema.py::test_display_name_is_optional_and_defaults_to_none`<br>`web/test_user_request_schema.py::test_display_name_accepts_null` |
| US-013 | 이름은 앞뒤 공백이 지워지고 200자까지 저장된다 | US-R7, US-UC2 | backend | `application/test_user_register_display_name.py::test_register_user_trims_the_display_name`<br>`application/test_user_register_display_name.py::test_register_user_accepts_a_display_name_of_name_max`<br>`domain/test_user_register_display_name.py::test_register_trims_surrounding_whitespace_of_the_display_name`<br>`domain/test_user_register_display_name.py::test_register_accepts_a_display_name_of_exactly_name_max`<br>`domain/test_user_register_display_name.py::test_register_accepts_name_max_after_trimming_the_padding` |
| US-014 | 200자를 넘거나 NUL이 든 이름은 잘리지 않고 422로 거절된다 | US-R7, US-UC2 | backend | `application/test_user_register_display_name.py::test_register_user_rejects_an_invalid_display_name_and_stores_nothing`<br>`domain/test_user_register_display_name.py::test_register_rejects_a_display_name_longer_than_name_max_instead_of_truncating`<br>`domain/test_user_register_display_name.py::test_register_rejects_a_display_name_containing_nul` |
| US-015 | 형식이 틀린 이메일·전화는 422이고 경계 안의 값은 저장된다 | US-R7, US-UC2 | backend | `application/test_register_user_local.py::test_register_user_local_rejects_invalid_email_or_phone`<br>`application/test_register_user_local.py::test_register_user_ad_rejects_an_invalid_phone`<br>`domain/test_user_register_contacts.py::test_register_normalizes_email_and_phone`<br>`domain/test_user_register_contacts.py::test_register_rejects_an_invalid_email`<br>`domain/test_user_register_contacts.py::test_register_rejects_an_email_over_254_chars`<br>`domain/test_user_register_contacts.py::test_register_rejects_an_invalid_phone`<br>`domain/test_user_register_contacts.py::test_register_accepts_a_phone_of_exactly_40_chars_and_rejects_41` |
| US-016 | 필수 값 누락·잘못된 역할·모르는 필드·너무 긴 비밀번호는 422 request-validation이다 | US-R9, US-R6, US-UC2 | backend | `web/test_local_user_routes.py::test_registration_password_must_be_a_string`<br>`web/test_user_request_schema.py::test_display_name_rejects_a_non_string`<br>`web/test_user_request_schema.py::test_unknown_fields_are_still_rejected`<br>`web/test_user_routes.py::test_register_with_an_invalid_body_is_422_request_validation` |
| US-017 | local 모드에서 비밀번호·이름으로 등록한 사용자는 그 비밀번호로 로그인된다 | US-R5, US-UC3 | backend | `application/test_register_user_local.py::test_register_user_local_saves_user_profile_and_hash`<br>`application/test_register_user_local.py::test_registered_local_user_can_sign_in_with_the_password`<br>`web/test_local_user_routes.py::test_admin_registers_a_local_user_who_can_sign_in` |
| US-018 | local 모드에서 비밀번호 없이 등록하면 422이다 | US-R5, US-UC3 | backend | `application/test_register_user_local.py::test_register_user_local_requires_password`<br>`web/test_local_user_routes.py::test_local_registration_without_a_password_is_422` |
| US-019 | local 모드에서 이름 없이 등록하면 422이다 | US-R5, US-R7, US-UC3 | backend | `application/test_register_user_local.py::test_register_user_local_requires_display_name`<br>`web/test_local_user_routes.py::test_local_registration_without_a_display_name_is_422` |
| US-020 | local 모드에서 8자 미만이거나 아이디와 같은 비밀번호는 422(위치 password)이고 8자는 된다 | US-R6, US-UC3 | backend | `application/test_register_user_local.py::test_register_user_local_rejects_a_weak_password_and_stores_nothing`<br>`application/test_register_user_local.py::test_register_user_local_accepts_an_eight_character_password`<br>`web/test_local_user_routes.py::test_local_registration_with_a_weak_password_is_422_on_the_password` |
| US-021 | 빈 값·NUL 비밀번호는 422(위치 password)다 | US-R6, US-UC3 | backend | `web/test_user_routes.py::test_register_with_an_empty_or_nul_password_is_422_on_the_password` |
| US-022 | 폐기(2026-11-13): 요청한 admin의 행이 없어졌으면 등록은 401이고 저장되지 않는다 — 등록자 FK가 없어져 판정 근거가 사라짐(확인 필요 Q1) | US-R8 | backend | - |
| US-023 | 기본 목록은 재직자만 등록 순서로 보인다 | US-R10, US-UC1 | backend | `application/test_user_list_status.py::test_list_users_defaults_to_active_users_only`<br>`application/test_user_register_list.py::test_list_users_returns_only_active_users_in_creation_order`<br>`web/test_user_routes.py::test_list_status_filter_selects_active_resigned_or_everyone` |
| US-024 | status=resigned는 퇴사자만 퇴사 시각과 함께 보인다 | US-R10, US-R11, US-UC1 | backend | `application/test_user_list_status.py::test_list_users_status_resigned_returns_only_resigned_users`<br>`web/test_user_routes.py::test_list_status_filter_selects_active_resigned_or_everyone` |
| US-025 | status=all은 재직자와 퇴사자를 등록 순서로 모두 보이고 같은 아이디의 행도 따로 보인다 | US-R10, US-UC1 | backend | `application/test_user_list_status.py::test_list_users_status_all_returns_everyone_in_creation_order`<br>`application/test_user_list_status.py::test_resigned_rows_with_the_same_login_id_are_listed_separately`<br>`web/test_user_routes.py::test_list_status_filter_selects_active_resigned_or_everyone` |
| US-026 | 모든 상태에서 offset·limit으로 한 페이지를 받고 그 값이 되돌아온다 | US-R10, US-UC1 | backend | `application/test_user_list_status.py::test_status_all_applies_offset_and_limit`<br>`application/test_user_register_list.py::test_list_users_pages_with_offset_and_limit`<br>`web/test_user_routes.py::test_list_returns_the_requested_offset_and_limit_with_one_page` |
| US-027 | 범위 밖 페이지 값이나 알 수 없는 상태 값은 422다 | US-R10, US-UC1 | backend | `application/test_user_list_status.py::test_list_users_rejects_out_of_range_paging_for_every_status`<br>`application/test_user_register_list.py::test_list_users_rejects_out_of_range_paging`<br>`web/test_user_routes.py::test_list_with_out_of_range_paging_or_unknown_status_is_422` |
| US-028 | 목록 항목은 문서화된 10개 필드만 담고 등록자·퇴사 사유·비밀번호 관련 값이 없다 | US-R11, US-UC1 | backend | `web/test_user_routes.py::test_list_items_carry_only_the_documented_fields_and_no_password_values` |
| US-029 | 로그인한 사용자는 마지막 로그인 시각이 있고 안 한 사용자는 null이다 | US-R11, US-UC1 | backend | `application/test_user_register_list.py::test_list_users_exposes_the_last_login_time`<br>`web/test_user_routes.py::test_list_shows_last_login_for_signed_in_users_and_null_for_the_others` |
| US-030 | 폐기(2026-11-13): 퇴사한 admin이 등록한 사용자의 등록자는 "(퇴사)"로 표시된다 — 응답에서 등록자를 없앰 | US-R12 | backend | - |
| US-031 | admin이 다른 사용자의 역할을 바꾸면 200이고 새 역할·수정 시각이 저장되며 세션은 유지된다 | US-R13, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_saves_new_role`<br>`application/test_user_change_role.py::test_change_user_role_touches_updated_at_with_the_clock`<br>`application/test_user_change_role.py::test_change_user_role_keeps_sessions_of_the_target`<br>`domain/test_user_change_role.py::test_change_role_to_another_role_updates_role_and_touches`<br>`web/test_user_role_routes.py::test_admin_changes_the_role_and_gets_the_documented_user_body`<br>`web/test_user_role_routes.py::test_the_changed_role_is_visible_in_the_user_list` |
| US-032 | 바뀐 역할은 대상의 다음 요청부터 적용된다 | US-R13, US-UC4 | backend | `application/test_user_change_role.py::test_authenticate_returns_new_role_after_change`<br>`web/test_user_role_routes.py::test_the_targets_existing_session_sees_the_new_role_on_its_next_request` |
| US-033 | 재직 admin이 둘이면 다른 admin을 강등할 수 있다 | US-R13, US-R19, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_allows_demoting_an_admin_while_another_remains`<br>`domain/test_user_role_policy.py::test_demoting_an_admin_is_allowed_while_another_admin_remains` |
| US-034 | 자기 자신의 역할은 바꿀 수 없다 | US-R13, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_refuses_oneself`<br>`domain/test_user_role_policy.py::test_role_change_of_oneself_is_rejected`<br>`domain/test_user_role_policy.py::test_self_check_precedes_the_last_admin_check`<br>`web/test_user_role_routes.py::test_changing_ones_own_role_is_a_409_with_the_documented_message` |
| US-035 | 재직 admin이 하나뿐이면 그 admin을 강등할 수 없고 퇴사한 admin은 세지 않는다 | US-R13, US-R19, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_refuses_demoting_the_last_admin`<br>`application/test_user_change_role.py::test_change_user_role_counts_only_active_admins`<br>`domain/test_user_role_policy.py::test_demoting_the_last_active_admin_is_rejected` |
| US-036 | 퇴사자의 역할은 바꿀 수 없다 | US-R13, US-R18, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_refuses_resigned_user`<br>`domain/test_user_change_role.py::test_change_role_of_resigned_user_raises_invalid_state`<br>`domain/test_user_role_policy.py::test_role_change_of_resigned_user_is_rejected_first`<br>`web/test_user_role_routes.py::test_a_resigned_user_is_a_409` |
| US-037 | 지금과 같은 역할을 보내면 200이고 아무것도 저장하지 않는다 | US-R13, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_with_same_role_does_not_write`<br>`domain/test_user_change_role.py::test_change_role_to_same_role_returns_false_without_touch`<br>`web/test_user_role_routes.py::test_same_role_returns_the_user_unchanged` |
| US-038 | 없는 사용자의 역할 변경은 404다 | US-R13, US-UC4 | backend | `application/test_user_change_role.py::test_change_user_role_with_unknown_id_is_not_found`<br>`web/test_user_role_routes.py::test_an_unknown_user_is_a_404` |
| US-039 | role이 없거나 3값 밖이거나 모르는 필드가 있으면 422이고 역할은 그대로다 | US-R13, US-UC4 | backend | `web/test_user_role_routes.py::test_an_invalid_body_is_a_422` |
| US-040 | local 모드에서 admin이 이름·이메일·전화를 고치면 반영되고 아이디·역할은 그대로다 | US-R14, US-UC5 | backend | `application/test_update_user_profile.py::test_admin_updates_profile_in_local_mode`<br>`domain/test_user_profile_change.py::test_change_profile_normalizes_email_and_phone`<br>`domain/test_user_profile_change.py::test_every_field_is_editable_in_local_mode`<br>`web/test_local_user_routes.py::test_admin_edits_name_email_and_phone` |
| US-041 | 보낸 칸만 바뀌고 null은 그 칸을 비운다 | US-R14, US-UC5 | backend | `application/test_update_user_profile.py::test_unset_fields_are_kept_and_none_clears`<br>`domain/test_user_profile_change.py::test_change_profile_updates_only_the_given_fields_and_touches_the_row`<br>`domain/test_user_profile_change.py::test_change_profile_clears_email_with_none`<br>`domain/test_user_profile_change.py::test_change_profile_clears_phone_with_a_blank_string`<br>`web/test_local_user_routes.py::test_patch_omitted_keys_are_kept_and_null_clears` |
| US-042 | 바뀐 값이 없으면 200이고 저장하지 않는다 | US-R14, US-UC5 | backend | `application/test_update_user_profile.py::test_update_without_effective_changes_does_not_commit`<br>`domain/test_user_profile_change.py::test_change_profile_without_changes_returns_false_and_leaves_updated_at`<br>`domain/test_user_profile_change.py::test_change_profile_with_equal_values_returns_false`<br>`web/test_local_user_routes.py::test_patch_with_an_empty_body_changes_nothing` |
| US-043 | local 모드에서 이름을 비우면 422이고 이름은 그대로다 | US-R14, US-R7, US-UC5 | backend | `application/test_update_user_profile.py::test_blank_name_in_local_mode_is_invalid_value`<br>`domain/test_user_profile_change.py::test_change_profile_blank_name_when_required_is_rejected`<br>`web/test_local_user_routes.py::test_patch_invalid_values_are_422_invalid_value` |
| US-044 | 형식이 틀린 이메일·전화로 고치면 422이고 아무 칸도 바뀌지 않는다 | US-R14, US-R7, US-UC5 | backend | `application/test_update_user_profile.py::test_invalid_email_or_phone_is_invalid_value`<br>`domain/test_user_profile_change.py::test_change_profile_invalid_value_is_rejected_and_nothing_changes`<br>`web/test_local_user_routes.py::test_patch_invalid_values_are_422_invalid_value` |
| US-045 | AD 모드에서는 이름·이메일 수정이 409이고 전화는 고칠 수 있다 | US-R14, US-UC5 | backend | `application/test_update_user_profile.py::test_admin_name_or_email_edit_in_ad_mode_is_invalid_state`<br>`application/test_update_user_profile.py::test_admin_edits_only_the_phone_in_ad_mode`<br>`domain/test_user_profile_change.py::test_profile_name_or_email_edit_in_ad_mode_is_invalid_state`<br>`domain/test_user_profile_change.py::test_phone_edit_in_ad_mode_is_allowed`<br>`web/test_local_user_routes.py::test_patch_name_or_email_in_ad_mode_is_409`<br>`web/test_local_user_routes.py::test_patch_phone_in_ad_mode_is_allowed` |
| US-046 | 퇴사자의 정보는 고칠 수 없다 | US-R14, US-R18, US-UC5 | backend | `application/test_update_user_profile.py::test_update_of_a_resigned_user_is_invalid_state`<br>`domain/test_user_profile_change.py::test_change_profile_on_resigned_user_is_invalid_state`<br>`domain/test_user_profile_change.py::test_change_profile_on_resigned_user_without_changes_is_still_invalid_state`<br>`web/test_local_user_routes.py::test_patch_a_resigned_user_is_409` |
| US-047 | 없는 사용자의 정보 수정은 404다 | US-R14, US-UC5 | backend | `application/test_update_user_profile.py::test_update_of_an_unknown_user_is_not_found`<br>`web/test_local_user_routes.py::test_patch_an_unknown_user_is_404` |
| US-048 | 정보 수정 본문에 아이디·역할·비밀번호를 보내면 422다 | US-R14, US-UC5 | backend | `web/test_local_user_routes.py::test_patch_cannot_carry_login_id_role_or_password` |
| US-049 | 비밀번호를 재설정하면 204이고 대상의 세션이 모두 끝나며 새 비밀번호로만 로그인된다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_saves_hash_and_ends_target_sessions`<br>`application/test_reset_user_password.py::test_reset_password_then_the_target_signs_in_with_the_new_password_only`<br>`web/test_local_user_routes.py::test_admin_resets_a_password_ends_sessions_and_the_new_password_works` |
| US-050 | 재설정해도 다른 사용자의 세션·비밀번호는 그대로다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_leaves_other_users_sessions_and_hashes` |
| US-051 | 해시가 없던 사용자도 재설정하면 해시가 생긴다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_creates_a_hash_for_a_user_without_one` |
| US-052 | AD 모드(모드 행이 없는 기존 시스템 포함)에서는 재설정이 409다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_in_ad_mode_is_invalid_state`<br>`application/test_reset_user_password.py::test_reset_password_without_a_mode_row_in_a_legacy_system_is_invalid_state`<br>`web/test_local_user_routes.py::test_reset_password_in_ad_mode_is_409` |
| US-053 | 자기 자신의 비밀번호는 재설정할 수 없다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_of_self_is_invalid_state`<br>`web/test_local_user_routes.py::test_reset_password_of_self_is_409` |
| US-054 | 퇴사자의 비밀번호는 재설정할 수 없다 | US-R15, US-R18, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_of_resigned_user_is_invalid_state`<br>`web/test_local_user_routes.py::test_reset_password_of_a_resigned_user_is_409` |
| US-055 | 약한 비밀번호로 재설정하면 422(위치 password)이고 기존 비밀번호·세션이 그대로다 | US-R15, US-R6, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_weak_password_is_invalid_value_and_changes_nothing`<br>`web/test_local_user_routes.py::test_reset_password_weak_is_422_on_the_password_field` |
| US-056 | 없는 사용자의 재설정은 404다 | US-R15, US-UC6 | backend | `application/test_reset_user_password.py::test_reset_password_unknown_user_is_not_found`<br>`web/test_local_user_routes.py::test_reset_password_of_an_unknown_user_is_404` |
| US-057 | 연결이 없는 사용자를 삭제하면 deleted이고 어떤 목록에도 없으며 세션·해시도 지워진다 | US-R17, US-R18, US-UC7 | backend | `application/test_user_delete.py::test_delete_user_without_links_removes_the_row_physically`<br>`application/test_user_delete.py::test_delete_user_removes_every_session_row_of_that_user_only`<br>`application/test_user_delete_password_hash.py::test_a_user_with_only_a_password_hash_is_deleted_physically_and_the_hash_goes` |
| US-058 | 연결이 하나라도 있으면 삭제는 퇴사 처리가 되고 행·연결은 남으며 세션·해시는 지워진다 | US-R17, US-R18, US-UC7 | backend | `application/test_user_delete_password_hash.py::test_resigning_a_linked_user_removes_the_password_hash_too`<br>`application/test_user_resign_delete.py::test_delete_user_with_any_reference_resigns_instead_of_deleting`<br>`application/test_user_resign_delete.py::test_resigning_still_deletes_the_users_session_rows`<br>`application/test_user_resign_delete.py::test_resigned_user_keeps_the_references_that_pointed_to_him`<br>`domain/test_user_resign.py::test_resign_keeps_identity_and_profile_for_history`<br>`application/test_bant_label_delete.py`<br>`domain/test_user_resign.py::test_resign_marks_only_deleted_at`<br>`domain/test_user_resign.py::test_resign_takes_no_reason_argument`<br>`application/test_user_resign_delete.py::test_registering_another_user_is_not_one_of_the_seventeen_links` |
| US-059 | 폐기(2026-11-13): 자기 자신만 등록자로 가리키는 사용자는 연결이 없어 물리 삭제된다 — 등록자를 기록하지 않음. 대신 US-112 | US-R17 | backend | - |
| US-060 | 퇴사 처리된 사용자는 기본 목록에서 빠지고 퇴사 목록에 보인다 | US-R17, US-R10, US-UC7 | backend | `application/test_user_resign_delete.py::test_resigned_user_leaves_the_default_list_and_shows_in_the_resigned_list` |
| US-061 | 삭제·퇴사된 사용자의 기존 세션은 다음 요청부터 401이고 다시 로그인할 수 없다 | US-R18, US-UC7 | backend | `application/test_user_delete.py::test_deleting_a_user_blocks_the_session_immediately`<br>`application/test_user_resign_delete.py::test_resigned_user_cannot_log_in_even_with_a_surviving_session`<br>`application/test_user_resign_delete.py::test_deleted_or_resigned_local_user_cannot_sign_in_again` |
| US-062 | 폐기(2026-11-13): reason=resigned는 받고 알 수 없는 reason은 422이며 사용자는 그대로다 — `reason` 쿼리를 없앰. 대신 US-113 | US-R16 | backend | - |
| US-063 | 이미 퇴사한 사용자를 다시 삭제하면 409다 | US-R16, US-R18, US-UC7 | backend | `application/test_user_resign_delete.py::test_resigned_user_cannot_be_deleted_again`<br>`domain/test_user_resign.py::test_resign_twice_is_rejected_and_keeps_the_first_time` |
| US-064 | 없는 id나 이미 물리 삭제된 사용자의 삭제는 404다 | US-R16, US-UC7 | backend | `application/test_user_delete.py::test_delete_user_with_unknown_id_is_not_found`<br>`application/test_user_delete.py::test_physically_deleted_user_is_not_found_the_second_time`<br>`application/test_user_delete.py::test_a_user_deleted_before_the_call_is_not_found` |
| US-065 | admin은 연결 유무와 무관하게 자기 자신을 삭제할 수 없고 세션은 유지된다 | US-R16, US-UC7 | backend | `application/test_user_delete.py::test_delete_user_refuses_to_delete_oneself`<br>`application/test_user_resign_delete.py::test_self_protection_also_applies_to_the_resign_branch`<br>`domain/test_user_policy.py::test_cannot_delete_self` |
| US-066 | 재직 admin이 하나뿐이면 그 admin을 삭제할 수 없고 퇴사한 admin은 세지 않는다 | US-R16, US-R19, US-UC7 | backend | `application/test_user_delete.py::test_delete_user_refuses_the_last_active_admin`<br>`application/test_user_delete.py::test_admin_count_drops_after_an_admin_is_deleted`<br>`application/test_user_resign_delete.py::test_last_admin_protection_also_applies_to_the_resign_branch`<br>`application/test_user_resign_delete.py::test_a_resigned_admin_is_not_counted_as_an_active_admin`<br>`domain/test_user_policy.py::test_cannot_delete_last_admin` |
| US-067 | 재직 admin이 둘이면 다른 admin을 삭제할 수 있다 | US-R16, US-R19, US-UC7 | backend | `application/test_user_delete.py::test_delete_user_allows_removing_an_admin_while_another_remains`<br>`domain/test_user_policy.py::test_can_delete_admin_when_another_admin_remains` |
| US-068 | 모든 역할이 사용자 선택 목록을 읽는다 | US-R20, US-UC8 | backend | `web/test_user_options_routes.py::test_every_signed_in_role_reads_the_user_options` |
| US-069 | 선택 목록 항목은 id·name·resigned·label·role·login_id만 담고 이메일이 없다 | US-R20, US-R12, US-UC8 | backend | `application/test_user_options.py::test_options_carry_the_login_id_of_each_user`<br>`application/test_user_options.py::test_options_name_falls_back_to_login_id_before_first_login`<br>`application/test_user_options.py::test_options_expose_no_email`<br>`application/test_user_options.py::test_options_carry_the_role_of_each_user`<br>`domain/test_user_ref.py::test_label_is_the_name_for_an_active_user`<br>`domain/test_user_ref.py::test_user_ref_of_an_active_user_uses_display_name`<br>`domain/test_user_ref.py::test_user_ref_has_only_id_name_resigned_and_role_fields_and_no_login_id`<br>`domain/test_user_ref.py::test_user_ref_carries_the_role_of_the_user`<br>`domain/test_user_ref.py::test_user_ref_name_falls_back_to_login_id_without_display_name`<br>`web/test_user_options_routes.py::test_option_items_carry_exactly_id_name_resigned_label_role_and_login_id`<br>`web/test_user_ref_schema.py::test_serialized_fields_are_exactly_id_name_resigned_label_and_role` |
| US-070 | 선택 목록은 기본이 재직자이고 include_resigned면 퇴사자를 "(퇴사)"와 함께 더한다 | US-R20, US-R12, US-UC8 | backend | `application/test_user_options.py::test_options_default_to_active_users_with_labels`<br>`application/test_user_options.py::test_options_include_resigned_users_with_the_resigned_label`<br>`domain/test_user_ref.py::test_label_adds_resigned_suffix_for_a_resigned_user`<br>`domain/test_user_ref.py::test_user_ref_of_a_resigned_user_still_carries_the_role`<br>`domain/test_user_ref.py::test_user_ref_of_a_resigned_user_is_flagged_and_labelled`<br>`web/test_user_options_routes.py::test_options_hide_resigned_users_unless_include_resigned_is_true`<br>`web/test_user_ref_schema.py::test_from_domain_of_a_resigned_user_keeps_the_role_and_label` |
| US-071 | keyword는 화면 이름을 대소문자 무시로 찾고 표시 이름이 있는 사용자는 아이디로 찾지 않는다 | US-R20, US-UC8 | backend | `application/test_user_options.py::test_options_keyword_matches_the_display_name_ignoring_case`<br>`application/test_user_options.py::test_options_keyword_does_not_match_the_login_id_of_a_user_with_a_display_name`<br>`application/test_user_options.py::test_options_keyword_matches_the_login_id_only_as_the_fallback_name`<br>`web/test_user_options_routes.py::test_options_filter_by_keyword_and_role_over_http` |
| US-072 | role 필터는 그 역할만 돌려주고 include_resigned·keyword와 함께 쓸 수 있다 | US-R20, US-UC8 | backend | `application/test_user_options.py::test_options_filter_by_role_returns_only_active_users_of_that_role`<br>`application/test_user_options.py::test_options_filter_by_role_with_resigned_includes_resigned_users_of_that_role`<br>`application/test_user_options.py::test_options_without_role_keep_returning_every_role`<br>`application/test_user_options.py::test_options_filter_by_role_combines_with_keyword`<br>`web/test_user_options_routes.py::test_options_filter_by_keyword_and_role_over_http` |
| US-073 | 선택 목록은 페이지 없이 조건에 맞는 사용자를 전부 돌려준다 | US-R20, US-UC8 | backend | `application/test_user_options.py::test_options_return_every_matching_user_beyond_the_old_200_cap` |
| US-074 | 선택 목록의 잘못된 파라미터·모르는 파라미터는 422다 | US-R20, US-UC8 | backend | `application/test_user_options.py::test_options_no_longer_accept_a_limit`<br>`web/test_user_options_routes.py::test_options_with_an_invalid_or_unknown_parameter_are_422` |
| US-075 | admin이 아니면 사용자 관리 API는 403이고 대상은 바뀌지 않는다 | 2.5, US-UC1, US-UC4~UC7 | backend | `web/test_local_user_routes.py::test_non_admins_cannot_register_local_users`<br>`web/test_local_user_routes.py::test_patch_by_non_admins_is_403_before_body_validation`<br>`web/test_local_user_routes.py::test_reset_password_by_non_admins_is_403_before_body_validation`<br>`web/test_user_role_routes.py::test_non_admins_get_403_and_nothing_changes`<br>`web/test_user_routes.py::test_non_admins_get_403_on_every_user_management_api_and_nothing_changes` |
| US-076 | 사용자 한 명을 읽거나 통째로 바꾸는 API는 없다 | US-R21 | backend | `web/test_user_routes.py::test_a_single_user_resource_has_no_read_or_replace_api` |
| US-077 | 화면: 목록은 기본으로 재직자만 보인다 | US-R22, US-UC1 | frontend | `features/admin/users/UsersPage.test.tsx > lists active users by default and hides the resigned one` |
| US-078 | 화면: 표는 9칸 머리글과 값을 보이고 등록자·퇴사 사유 열이 없으며 없는 값은 "-"다 | US-R22, US-UC1 | frontend | `features/admin/users/UsersPage.profile.test.tsx > lists the email and phone columns and "-" for a missing value`<br>`features/admin/users/UsersPage.profile.test.tsx > shows a saved phone on the row`<br>`features/admin/users/UsersPage.test.tsx > lists id, role, name, created and last login without creator or reason columns`<br>`features/admin/users/UsersPage.test.tsx > shows "-" for resignation columns of active users` |
| US-079 | 화면: 상태 선택은 재직·퇴사·전체이고 퇴사를 고르면 퇴사자만 보인다 | US-R22, US-UC1 | frontend | `features/admin/users/UsersPage.test.tsx > offers 재직, 퇴사 and 전체 and can list only the resigned` |
| US-080 | 화면: 퇴사 행은 "이름(퇴사)"·퇴사 일시를 보이고 작업 버튼이 없다 | US-R22, US-R23, US-UC1 | frontend | `features/admin/users/UsersPage.profile.test.tsx > does not offer 정보 수정 on a resigned user`<br>`features/admin/users/UsersPage.test.tsx > shows a resigned row with 이름(퇴사), the resignation time, and no delete button`<br>`features/admin/users/UsersPage.test.tsx > shows 역할 변경 only on active rows other than the signed-in admin` |
| US-081 | 화면: 사용자가 없으면 빈 메시지를 보인다 | US-R22, US-UC1 | frontend | `features/admin/users/UsersPage.test.tsx > shows the empty message when there are no users` |
| US-082 | 화면: 목록을 읽지 못하면 서버 문구를 오류로 보인다 | US-R29, US-UC1 | frontend | `features/admin/users/UsersPage.test.tsx > shows the message when the list cannot be loaded` |
| US-083 | 화면: 본인 행에는 작업 버튼이 없고 다른 재직 행에는 정보 수정·역할 변경·삭제가 있다 | US-R23, US-UC1 | frontend | `features/admin/users/UsersPage.profile.test.tsx > offers 정보 수정 on other users but not on the signed-in admin row`<br>`features/admin/users/UsersPage.test.tsx > hides the delete button on the row of the signed-in admin (last admin and self protection)`<br>`features/admin/users/UsersPage.test.tsx > shows 역할 변경 only on active rows other than the signed-in admin` |
| US-084 | 화면: AD 모드에는 비밀번호 칸·재설정 버튼이 없고 아이디 칸 이름이 "AD 아이디"다 | US-R23, US-R24, US-UC2 | frontend | `features/admin/users/AddUserForm.local.test.tsx > keeps the AD id label and adds optional email and phone but no password`<br>`features/admin/users/UsersPage.profile.test.tsx > is not offered in AD mode`<br>`features/admin/users/UsersPage.test.tsx > has no password column, field or reset button in AD mode` |
| US-085 | 화면: local 모드는 다른 재직 행에 비밀번호 재설정 버튼을 둔다 | US-R23, US-UC6 | frontend | `features/admin/users/UsersPage.profile.test.tsx > offers 비밀번호 재설정 on other users in local mode but not on the admin row` |
| US-086 | 화면: AD 아이디를 고른 역할로 등록하면 목록에 행이 생기고 폼이 비며 역할 기본값은 sales다 | US-R24, US-UC2 | frontend | `features/admin/users/AddUserForm.local.test.tsx > registers without a password and passes the phone`<br>`features/admin/users/UsersPage.test.tsx > registers an AD id with the chosen role and refreshes the list`<br>`features/admin/users/UsersPage.test.tsx > defaults the role to sales` |
| US-087 | 화면: 필수 칸이 비면 요청하지 않고 모드별 문구를 보인다 | US-R24, US-UC2, US-UC3 | frontend | `features/admin/users/AddUserForm.local.test.tsx > blocks missing id, password or name with a message instead of sending a request`<br>`features/admin/users/UsersPage.test.tsx > blocks empty input with a message instead of sending a request` |
| US-088 | 화면: local 등록에서 비밀번호 확인이 다르면 요청하지 않는다 | US-R24, US-UC3 | frontend | `features/admin/users/AddUserForm.local.test.tsx > does not send a request when the confirmation differs` |
| US-089 | 화면: local 등록은 비밀번호·프로필을 보내고 빈 이메일·전화는 보내지 않으며 성공하면 폼을 비운다 | US-R24, US-UC3 | frontend | `features/admin/users/AddUserForm.local.test.tsx > registers the user with the password and profile, lists the phone and clears the form`<br>`features/admin/users/AddUserForm.local.test.tsx > sends empty email and phone as null` |
| US-090 | 화면: 등록이 거절되면 서버 문구를 보이고 비밀번호 칸만 비운다 | US-R24, US-UC2, US-UC3 | frontend | `features/admin/users/AddUserForm.local.test.tsx > shows the server message for a weak password, keeps the other input and clears the passwords`<br>`features/admin/users/AddUserForm.local.test.tsx > shows the server message when the id is already in use`<br>`features/admin/users/UsersPage.test.tsx > shows the server message and keeps the input when the id already exists` |
| US-091 | 화면: 입력한 비밀번호는 성공·실패 뒤 요청 캐시에 남지 않는다 | US-R24, US-R26, US-UC3, US-UC6 | frontend | `features/admin/users/AddUserForm.local.test.tsx > does not keep the typed passwords in the mutation cache, on success or failure` |
| US-092 | 화면: 정보 수정은 현재 값을 채우고 바뀐 칸만 저장하며 바뀐 게 없으면 저장할 수 없다 | US-R25, US-UC5 | frontend | `features/admin/users/UsersPage.profile.test.tsx > opens a dialog filled with the current values`<br>`features/admin/users/UsersPage.profile.test.tsx > saves only the changed fields, closes the dialog and refreshes the row`<br>`features/admin/users/UsersPage.profile.test.tsx > keeps the save button disabled until something changes` |
| US-093 | 화면: 정보 수정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다 | US-R25, US-UC5 | frontend | `features/admin/users/UsersPage.profile.test.tsx > shows the server message and keeps the dialog open for an invalid email` |
| US-094 | 화면: 정보 수정 취소는 요청하지 않는다 | US-R25, US-UC5 | frontend | `features/admin/users/UsersPage.profile.test.tsx > cancels without calling the server` |
| US-095 | 화면: AD 모드 정보 수정은 이름·이메일을 막고 전화만 보낸다 | US-R25, US-UC5 | frontend | `features/admin/users/UsersPage.profile.test.tsx > lets the admin edit only the phone in AD mode` |
| US-096 | 화면: 비밀번호를 재설정하면 대화상자가 닫히고 로그인 종료 안내가 보인다 | US-R26, US-UC6 | frontend | `features/admin/users/UsersPage.profile.test.tsx > resets the password, closes the dialog and says the sessions of that user ended` |
| US-097 | 화면: 새 비밀번호 확인이 다르면 요청하지 않는다 | US-R26, US-UC6 | frontend | `features/admin/users/UsersPage.profile.test.tsx > does not submit when the confirmation differs` |
| US-098 | 화면: 재설정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다 | US-R26, US-UC6 | frontend | `features/admin/users/UsersPage.profile.test.tsx > shows the server message for a weak password and keeps the dialog open` |
| US-099 | 화면: 역할 변경 대화상자는 현재 역할을 고른 채 열리고 다른 역할을 골라야 변경할 수 있다 | US-R27, US-UC4 | frontend | `features/admin/users/UsersPage.test.tsx > opens a dialog with the current role selected and the 변경 button disabled`<br>`features/admin/users/UsersPage.test.tsx > offers admin, sales and user`<br>`features/admin/users/UsersPage.test.tsx > enables 변경 only for a different role` |
| US-100 | 화면: 역할을 바꾸면 대화상자가 닫히고 알림과 역할 칸이 바뀐다 | US-R27, US-UC4 | frontend | `features/admin/users/UsersPage.test.tsx > changes the role, closes the dialog, announces it and updates the role cell`<br>`features/admin/users/UsersPage.test.tsx > sends the user id and the chosen role to the gateway` |
| US-101 | 화면: 역할 변경 취소는 요청하지 않는다 | US-R27, US-UC4 | frontend | `features/admin/users/UsersPage.test.tsx > does nothing when the dialog is cancelled` |
| US-102 | 화면: 역할 변경이 거절되면 대화상자를 닫고 오류 배너를 보이며 이전 알림을 지운다 | US-R27, US-R29, US-UC4 | frontend | `features/admin/users/UsersPage.test.tsx > shows the server message in the page error banner when the change is refused`<br>`features/admin/users/UsersPage.test.tsx > clears the previous result message when the next change fails` |
| US-103 | 화면: sales를 다른 역할로 고르면 Owner 안내를 보인다 | US-R27, US-UC4 | frontend | `features/admin/users/UsersPage.test.tsx > warns about owner eligibility when a sales user is moved to another role`<br>`features/admin/users/UsersPage.test.tsx > does not warn when the user was not sales or stays sales` |
| US-104 | 화면: 삭제 확인을 취소하면 요청하지 않는다 | US-R28, US-UC7 | frontend | `features/admin/users/UsersPage.test.tsx > does nothing when the confirmation is declined` |
| US-105 | 화면: 삭제 결과에 따라 퇴사 처리·삭제 알림을 보이고 목록에서 뺀다 | US-R28, US-UC7 | frontend | `features/admin/users/UsersPage.test.tsx > says the user was processed as resigned when data was linked`<br>`features/admin/users/UsersPage.test.tsx > says the user was deleted when nothing was linked` |
| US-106 | 화면: 삭제가 거절되면 대화상자를 닫고 오류 배너를 보이며 이전 알림을 지운다 | US-R28, US-R29, US-UC7 | frontend | `features/admin/users/UsersPage.test.tsx > shows the server message and closes the dialog when deletion is refused`<br>`features/admin/users/UsersPage.test.tsx > clears the previous result message when the next delete fails` |
| US-107 | 화면: 등록·삭제·역할 변경 뒤 사용자 선택 목록과 Deal 목록을 다시 읽게 한다 | US-R30, US-UC2, US-UC4, US-UC7 | frontend | `features/admin/users/UsersPage.test.tsx > invalidates user-options after adding a user`<br>`features/admin/users/UsersPage.test.tsx > invalidates user-options after deleting a user`<br>`features/admin/users/UsersPage.test.tsx > invalidates user-options and the deal lists after a role change`<br>`features/admin/users/UsersPage.test.tsx > drops the changed user from the sales owner options` |
| US-108 | 게이트웨이: 목록은 가득 찬 페이지가 오는 동안 이어 읽는다 | US-R31, US-UC1 | frontend | `gateway/http/users.test.ts > list reads GET /users with the status and the maximum page size`<br>`gateway/http/users.test.ts > list keeps reading the next page while a full page comes back` |
| US-109 | 게이트웨이: 선택 목록은 한 번 요청하고 페이지 값을 보내지 않는다 | US-R31, US-UC8 | frontend | `gateway/http/users.test.ts > options reads GET /user-options and includes resigned users on request`<br>`gateway/http/users.test.ts > options with a role sends it as the role query`<br>`gateway/http/users.test.ts > options without a role does not send the role query`<br>`gateway/http/users.test.ts > options with a role reads one request that carries the role and no offset`<br>`gateway/http/users.test.ts > options never sends an offset, because the server does not know it`<br>`gateway/http/users.test.ts > options returns every user of a single request without sending a limit` |
| US-110 | 게이트웨이: 응답의 이름·퇴사 시각·역할을 화면 값으로 바꾸고 등록자·퇴사 사유는 만들지 않는다 | US-R31, US-UC1, US-UC8 | frontend | `gateway/http/mappers/user.test.ts > marks a resigned user, keeping the plain name (the screens add the suffix)`<br>`gateway/http/mappers/user.test.ts > marks an active user`<br>`gateway/http/mappers/user.test.ts > uses the server role %s as is (no placeholder)`<br>`gateway/http/mappers/user.test.ts > keeps the role of a resigned user`<br>`gateway/http/users.test.ts > list reads GET /users with the status and the maximum page size`<br>`gateway/http/users.test.ts > shows the login id when the user has no display name yet`<br>`gateway/http/users.test.ts > maps a resigned user with the resign time and no reason`<br>`gateway/http/users.test.ts > options maps the server role of each user, resigned ones included`<br>`gateway/http/users.test.ts > maps the phone of a user`<br>`gateway/http/mappers/user.test.ts > maps a user without a creator or a resign reason` |
| US-111 | 게이트웨이: 등록·수정·재설정·역할 변경·삭제 요청을 계약대로 보낸다 | US-R31, US-UC2~UC7 | frontend | `gateway/http/users.test.ts > create sends the name as display_name`<br>`gateway/http/users.test.ts > create sends the password, email and phone of a local user`<br>`gateway/http/users.test.ts > create leaves out the password, an empty email and an empty phone`<br>`gateway/http/users.test.ts > create shows the server message for a weak password`<br>`gateway/http/users.test.ts > create shows the server message for a duplicate login id`<br>`gateway/http/users.test.ts > remove returns the outcome %s`<br>`gateway/http/users.test.ts > remove shows the server message for deleting yourself`<br>`gateway/http/users.test.ts > changeRole sends PUT /users/{id}/role with the role body and maps the user`<br>`gateway/http/users.test.ts > changeRole shows the %s answer %s with the server message`<br>`gateway/http/users.test.ts > update sends PATCH /users/{id} with only the given fields and maps the user`<br>`gateway/http/users.test.ts > update sends null to clear a field and nothing for an omitted one`<br>`gateway/http/users.test.ts > update shows the %s answer %s with the server message`<br>`gateway/http/users.test.ts > resetPassword sends PUT /users/{id}/password and resolves on 204`<br>`gateway/http/users.test.ts > resetPassword shows the %s answer %s with the server message` |
| US-112 | 다른 사용자를 등록한 admin도 다른 연결이 없으면 물리 삭제되고 그가 등록한 사용자는 재직 그대로다 | US-R17, US-UC7 | backend | `application/test_user_resign_delete.py::test_an_admin_who_only_registered_another_user_is_deleted_physically`<br>`repositories/test_user_links_contract.py::test_other_user_rows_never_make_a_user_linked`<br>`web/test_user_routes.py::test_delete_of_an_admin_who_registered_another_user_keeps_that_user_active` |
| US-113 | 사용자 삭제에 쿼리 파라미터(없앤 reason 포함)를 보내면 422이고 사용자는 그대로다 | US-R16, US-UC7 | backend | `web/test_user_routes.py::test_delete_with_any_query_parameter_is_422_and_keeps_the_user`<br>`web/test_user_routes.py::test_delete_without_a_query_reports_deleted_after_the_query_was_refused` |
| US-114 | API 계약(OpenAPI)의 UserResponse에 created_by·delete_reason이 없고 사용자 삭제에 쿼리 파라미터가 없다 | US-R11, US-R16, 2.6 | backend | `web/test_openapi_documented_shapes.py::test_user_response_has_exactly_the_documented_fields_and_no_password`<br>`web/test_openapi_documented_shapes.py::test_user_delete_documents_the_outcome_no_query_and_errors` |
| US-115 | 선택 목록은 재직·퇴사·모든 역할 항목에 login_id를 항상 주고 keyword는 아이디로 찾지 않는다 | US-R20, US-UC8 | backend | `application/test_user_options.py`, `web/test_user_options_routes.py`, `repositories/test_user_options_login_id_contract.py` |
| US-116 | API 계약(OpenAPI)의 선택 목록 항목은 UserOption(UserRef + 필수 login_id)이고 UserRef는 그대로다 | US-R20, 2.6 | backend | `web/test_openapi_documented_shapes.py` |
| US-117 | 게이트웨이: 선택 목록의 login_id를 loginId로 바꾼다 | US-R31, US-UC8 | frontend | `gateway/http/users.test.ts` |

### US-001 AD 모드에서 아이디·역할로 등록하면 201과 Location·사용자가 돌아오고 본문에 등록자·퇴사 사유가 없다
- Given ROOT로 로그인, 인증 방식 `ad`
- When `POST /users` `{"login_id": "kim", "role": "sales"}`(역할마다 `admin`·`sales`·`user`)
- Then 201, `Location: /api/v1/users/<새 id>`, 본문은 `login_id` "kim", 요청한 역할, `status` "active", `last_login_at`·`deleted_at` null이고 `created_by`·`delete_reason` 키가 없다. 기본 목록 끝에 kim이 있다

### US-002 아이디의 앞뒤 공백과 대문자는 정규화되어 저장된다
- Given ROOT로 로그인
- When `login_id` "  Kim.Lee_01  "로 등록한다
- Then 201이고 `login_id`는 "kim.lee_01"이다

### US-003 64자 아이디는 등록된다
- When `login_id` = "a"×64로 등록한다
- Then 201이다

### US-004 형식에 맞지 않거나 65자인 아이디는 422이고 저장되지 않는다
- When `login_id`를 "a"×65, "김영업", "kim lee", ".kim", "-kim", "kim@corp", "kim/x"로 각각 등록한다
- Then 모두 422 `invalid-value` "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다"이고 사용자 수는 그대로다

### US-005 예약 아이디 세 개는 대소문자와 무관하게 등록할 수 없다
- When `dev-admin`, `DEV-Sales`, ` dev-user `로 각각 등록한다
- Then 모두 422 `invalid-value` "개발 로그인 전용 아이디는 등록할 수 없습니다: <정규화 아이디>"이고 저장되지 않는다

### US-006 예약 아이디가 아닌 dev- 아이디는 등록된다
- When `dev-qa`로 등록한다
- Then 201이다

### US-007 재직 중인 아이디는 대소문자·공백이 달라도 409이고 퇴사 행이 있어도 마찬가지다
- Given 재직 kim이 있다(같은 아이디의 퇴사 행도 하나 있다)
- When `login_id` " KIM "으로 등록한다
- Then 409 `already-exists` "이미 존재하는 사용자입니다: kim"이고 kim 행은 재직 1개·퇴사 1개 그대로다

### US-008 퇴사한 아이디를 다시 등록하면 새 행이 생기고 퇴사 행은 그대로다
- Given kim이 연결이 있어 퇴사 처리됐다
- When kim을 user 역할로 다시 등록한다
- Then 201, 새 id(퇴사 행 id와 다름)이고, `status=all` 목록에 kim이 두 행 있다. 퇴사 행은 퇴사 시각·역할이 그대로이고 퇴사 행을 가리키던 이력도 계속 그 행을 가리킨다

### US-009 물리 삭제된 아이디는 다시 등록되고 새 id를 받는다
- Given 연결 없는 kim을 삭제해 `deleted`가 됐다
- When kim을 다시 등록한다
- Then 201이고 예전 id와 다른 id다

### US-010 등록은 AD에 계정이 있는지 묻지 않는다
- Given Fake 디렉터리에 "ghost" 계정이 없다
- When ghost를 등록한다
- Then 201이고 디렉터리 호출 수가 늘지 않는다

### US-011 AD 모드에서 비밀번호를 보내면 422이고 저장되지 않는다
- When `{"login_id": "kim", "role": "user", "password": "pw-12345678"}`로 등록한다
- Then 422 `invalid-value` "AD 연동에서는 비밀번호를 입력하지 않습니다."이고 사용자·해시가 생기지 않는다

### US-012 AD 모드 등록의 이름은 선택이고 주면 첫 로그인 전에도 보인다
- When `display_name`을 "김영업", 생략, null, "", "   "으로 각각 등록한다
- Then 모두 201이다. "김영업"이면 응답·목록의 `display_name`이 "김영업"이고 `last_login_at`은 null, 나머지는 `display_name` null이다. 어느 경우도 비밀번호 해시가 저장되지 않는다

### US-013 이름은 앞뒤 공백이 지워지고 200자까지 저장된다
- When `display_name` "  김영업  ", 그리고 "가"×200으로 각각 등록한다
- Then 201이고 각각 "김영업", 200자 그대로 저장된다

### US-014 200자를 넘거나 NUL이 든 이름은 잘리지 않고 422로 거절된다
- When `display_name` "가"×201, "김\x00영업"으로 각각 등록한다
- Then 422 `invalid-value` "표시 이름은(는) 200자를 넘을 수 없습니다" / "표시 이름에는 NUL 문자를 쓸 수 없습니다"이고 등록되지 않는다

### US-015 형식이 틀린 이메일·전화는 422이고 경계 안의 값은 저장된다
- When 이메일 "kim", "kim@corp", "a b@corp.com"; 전화 "123456"(숫자 6개), "1234567890123456"(16개), "010-1234-abcd", 41자 값으로 각각 등록한다
- Then 이메일은 "이메일 형식이 올바르지 않습니다.", 전화는 "전화번호 형식이 올바르지 않습니다."인 422 `invalid-value`이고 등록되지 않는다. 이메일 " Kim@Corp.COM "은 "kim@corp.com", 전화 "1234567"(7개)·"+82 (10) 1234-5678"은 그대로 저장된다

### US-016 필수 값 누락·잘못된 역할·모르는 필드·너무 긴 비밀번호는 422 request-validation이다
- When 본문 `{}`, `{"login_id": "kim"}`, `{"role": "user"}`, `{"login_id": "kim", "role": "superuser"}`, `{"login_id": "kim", "role": null}`, `{"login_id": 7, "role": "user"}`, `{"login_id": "kim", "role": "user", "nickname": "김"}`, 비밀번호 257자로 각각 등록한다
- Then 모두 422 `request-validation`이고 사용자 수는 그대로다

### US-017 local 모드에서 비밀번호·이름으로 등록한 사용자는 그 비밀번호로 로그인된다
- Given 인증 방식 `local`, ROOT로 로그인
- When `{"login_id": "kim", "role": "sales", "password": "kim-pass-1", "display_name": "김영업", "email": "kim@corp.com", "phone": "010-1234-5678"}`로 등록한다
- Then 201이고 응답에 이름·이메일·전화가 있다. kim의 해시가 저장되고 kim은 "kim-pass-1"로 로그인된다

### US-018 local 모드에서 비밀번호 없이 등록하면 422이다
- Given 인증 방식 `local`
- When 비밀번호 없이(키 생략, null) 등록한다
- Then 422 `invalid-value` "비밀번호를 입력하세요."이고 사용자가 생기지 않는다

### US-019 local 모드에서 이름 없이 등록하면 422이다
- Given 인증 방식 `local`
- When 이름 없이(생략, "   ") 비밀번호를 주고 등록한다
- Then 422 `invalid-value` "이름은(는) 비어 있을 수 없습니다"이고 사용자·해시가 생기지 않는다

### US-020 local 모드에서 8자 미만이거나 아이디와 같은 비밀번호는 422(위치 password)이고 8자는 된다
- Given 인증 방식 `local`, 아이디 "kimsales1"
- When 비밀번호 "1234567"(7자), " KIMSALES1 "로 각각 등록한다
- Then 422 `invalid-value`, `errors` = `[{"location": ["password"], ...}]`, 문구 "비밀번호는 8자 이상이어야 합니다" / "비밀번호는 아이디와 같을 수 없습니다"이고 저장되지 않는다. 비밀번호 "12345678"(8자)은 201이다

### US-021 빈 값·NUL 비밀번호는 422(위치 password)다
- Given 인증 방식 `local`
- When 비밀번호 "", "   ", "pass\x00word"로 각각 등록한다
- Then 422 `invalid-value`, 위치 `["password"]`, "비밀번호는 비어 있을 수 없습니다" / "비밀번호에는 NUL 문자를 쓸 수 없습니다"이고 저장되지 않는다

### US-022 (폐기 2026-11-13)
- 등록자 FK(`fk_users_created_by_user_id_users`)가 없어져 "요청한 admin의 행이 사라지면 401"을 판정할 근거가 없다. 대체 케이스 없음(확인 필요 Q1에서 '401 유지'를 고르면 새 번호로 다시 만든다).

### US-023 기본 목록은 재직자만 등록 순서로 보인다
- Given root, kim, lee 순서로 등록, lee는 퇴사 처리, park은 물리 삭제
- When `GET /users`
- Then `login_id` 순서가 ["root", "kim"]이다

### US-024 status=resigned는 퇴사자만 퇴사 시각과 함께 보인다
- Given kim 재직, lee 퇴사
- When `GET /users?status=resigned`
- Then 항목은 lee 하나이고 `status` "resigned", `deleted_at` = 퇴사 시각이며 `delete_reason` 키가 없다

### US-025 status=all은 재직자와 퇴사자를 등록 순서로 모두 보이고 같은 아이디의 행도 따로 보인다
- Given root, kim(퇴사), lee, kim(재등록) 순서
- When `GET /users?status=all`
- Then 네 행이 등록 순서로 나오고 kim은 퇴사 행과 재직 행으로 따로 보인다

### US-026 모든 상태에서 offset·limit으로 한 페이지를 받고 그 값이 되돌아온다
- Given 사용자 5명(그중 퇴사 2명)
- When `status`가 `active`·`all`일 때 `offset=1&limit=2`로 조회한다
- Then 등록 순서의 2·3번째 항목만 오고 응답 `offset` 1, `limit` 2다. 쿼리를 주지 않으면 `offset` 0, `limit` 50이다

### US-027 범위 밖 페이지 값이나 알 수 없는 상태 값은 422다
- When `offset=-1`, `limit=0`, `limit=201`, `status=deleted`, `status=ACTIVE`로 각각 조회한다
- Then 모두 422 `request-validation`이다. `limit=200`은 200이다

### US-028 목록 항목은 문서화된 10개 필드만 담고 등록자·퇴사 사유·비밀번호 관련 값이 없다
- Given local 모드에서 비밀번호로 등록한 kim, 퇴사한 lee
- When `GET /users?status=all`
- Then 각 항목의 키 집합이 정확히 US-R11의 10개(`id`, `login_id`, `role`, `display_name`, `email`, `phone`, `created_at`, `last_login_at`, `status`, `deleted_at`)이고 `created_by`·`delete_reason` 키가 없으며, 어떤 키·값에도 비밀번호·해시가 없다

### US-029 로그인한 사용자는 마지막 로그인 시각이 있고 안 한 사용자는 null이다
- Given kim은 로그인한 적이 있고 lee는 없다
- When `GET /users`
- Then kim의 `last_login_at`은 로그인 시각, lee는 null이다

### US-030 (폐기 2026-11-13)
- 응답에서 등록자(`created_by`)를 없애 "퇴사한 등록자의 (퇴사) 표기"를 볼 곳이 없다. 대체 케이스 없음(`(퇴사)` 표기 자체는 US-070이 검증).

### US-031 admin이 다른 사용자의 역할을 바꾸면 200이고 새 역할·수정 시각이 저장되며 세션은 유지된다
- Given ROOT로 로그인, KIM(sales)은 로그인 세션이 있다
- When `PUT /users/{KIM}/role` `{"role": "user"}`
- Then 200이고 응답과 목록의 KIM `role`이 "user"다. 저장된 KIM의 수정 시각(`updated_at`)이 시계 시각이고, KIM의 세션 행은 그대로 있다

### US-032 바뀐 역할은 대상의 다음 요청부터 적용된다
- Given KIM(sales)·VIEWER(user)가 로그인해 있다
- When ROOT가 KIM을 user로, VIEWER를 admin으로 바꾼다
- Then 같은 세션으로 KIM의 다음 업무 쓰기 요청은 403이고 VIEWER의 다음 `GET /users`는 200이다(재로그인 없음)

### US-033 재직 admin이 둘이면 다른 admin을 강등할 수 있다
- Given ROOT·BOSS가 재직 admin
- When ROOT가 BOSS를 sales로 바꾼다
- Then 200이고 BOSS는 sales다

### US-034 자기 자신의 역할은 바꿀 수 없다
- Given ROOT·BOSS가 재직 admin
- When ROOT가 자기 역할을 sales로(그리고 admin 그대로로) 바꾼다
- Then 둘 다 409 `invalid-state` "자기 자신의 역할은 바꿀 수 없습니다."이고 역할은 그대로다

### US-035 재직 admin이 하나뿐이면 그 admin을 강등할 수 없고 퇴사한 admin은 세지 않는다
- Given 재직 admin은 BOSS 하나이고 퇴사한 admin이 하나 있다. 요청자 id는 BOSS와 다르다(유스케이스 Fake)
- When BOSS를 sales로 바꾼다
- Then 409 `invalid-state` "마지막 관리자의 역할은 바꿀 수 없습니다."이고 BOSS는 admin이다. BOSS를 admin으로 보내는 요청은 409가 아니다

### US-036 퇴사자의 역할은 바꿀 수 없다
- Given lee가 퇴사 처리됐다
- When lee의 역할을 admin으로 바꾼다
- Then 409 `invalid-state` "이미 퇴사 처리된 사용자입니다"이고 역할은 그대로다

### US-037 지금과 같은 역할을 보내면 200이고 아무것도 저장하지 않는다
- Given KIM(sales)
- When `{"role": "sales"}`를 보낸다
- Then 200, 응답이 변경 전과 같고 저장된 수정 시각이 바뀌지 않으며 커밋이 없다

### US-038 없는 사용자의 역할 변경은 404다
- When 없는 id로 역할을 바꾼다
- Then 404 `not-found` "사용자을(를) 찾을 수 없습니다: <id>"다

### US-039 role이 없거나 3값 밖이거나 모르는 필드가 있으면 422이고 역할은 그대로다
- When 본문 `{}`, `{"role": "owner"}`, `{"role": null}`, `{"role": "user", "extra": 1}`
- Then 모두 422 `request-validation`이고 대상 역할은 그대로다

### US-040 local 모드에서 admin이 이름·이메일·전화를 고치면 반영되고 아이디·역할은 그대로다
- Given 인증 방식 `local`, KIM(sales, 이름 "김영업")
- When `PATCH /users/{KIM}` `{"display_name": "김영업2", "email": "kim2@corp.com", "phone": "010-9999-0000"}`
- Then 200, 응답·목록의 세 값이 바뀌고 `login_id`·`role`은 그대로다

### US-041 보낸 칸만 바뀌고 null은 그 칸을 비운다
- Given KIM에 이메일·전화가 있다
- When `{"phone": null}`을 보낸다
- Then 전화만 null이 되고 이름·이메일은 그대로다

### US-042 바뀐 값이 없으면 200이고 저장하지 않는다
- When `{}` 또는 현재와 같은 전화를 보낸다
- Then 200이고 저장된 수정 시각이 바뀌지 않으며 커밋이 없다

### US-043 local 모드에서 이름을 비우면 422이고 이름은 그대로다
- Given 인증 방식 `local`
- When `{"display_name": "   "}`(그리고 null)을 보낸다
- Then 422 `invalid-value` "이름은(는) 비어 있을 수 없습니다"이고 이름은 그대로다

### US-044 형식이 틀린 이메일·전화로 고치면 422이고 아무 칸도 바뀌지 않는다
- Given 인증 방식 `local`
- When `{"display_name": "새이름", "email": "kim"}`, `{"phone": "12"}`를 보낸다
- Then 422 `invalid-value`(이메일·전화 문구)이고 이름도 바뀌지 않는다

### US-045 AD 모드에서는 이름·이메일 수정이 409이고 전화는 고칠 수 있다
- Given 인증 방식 `ad`
- When `{"display_name": "새이름"}`, `{"email": null}`, 그리고 `{"phone": "010-1111-2222"}`를 보낸다
- Then 앞의 둘은 409 `invalid-state` "AD 연동 사용자의 이름·이메일은 AD에서 관리합니다."이고 바뀌지 않는다. 전화는 200으로 바뀐다

### US-046 퇴사자의 정보는 고칠 수 없다
- Given lee 퇴사
- When lee의 전화를 고친다
- Then 409 `invalid-state` "이미 퇴사 처리된 사용자입니다"다

### US-047 없는 사용자의 정보 수정은 404다
- When 없는 id에 `{"phone": "010-1111-2222"}`
- Then 404 `not-found`다

### US-048 정보 수정 본문에 아이디·역할·비밀번호를 보내면 422다
- When `{"login_id": "x"}`, `{"role": "admin"}`, `{"password": "new-pass-1"}`
- Then 모두 422 `request-validation`이고 대상은 그대로다

### US-049 비밀번호를 재설정하면 204이고 대상의 세션이 모두 끝나며 새 비밀번호로만 로그인된다
- Given 인증 방식 `local`, KIM이 세션 두 개를 가지고 옛 비밀번호가 있다
- When `PUT /users/{KIM}/password` `{"password": "new-pass-9"}`
- Then 204, KIM의 세션 행이 모두 없고, KIM은 "new-pass-9"로 로그인되며 옛 비밀번호로는 로그인되지 않는다

### US-050 재설정해도 다른 사용자의 세션·비밀번호는 그대로다
- Given LEE도 세션·해시가 있다
- When KIM의 비밀번호를 재설정한다
- Then LEE의 세션·해시는 그대로다

### US-051 해시가 없던 사용자도 재설정하면 해시가 생긴다
- Given 인증 방식 `local`, KIM의 해시가 없다
- When KIM의 비밀번호를 재설정한다
- Then 204이고 KIM의 해시가 저장된다

### US-052 AD 모드(모드 행이 없는 기존 시스템 포함)에서는 재설정이 409다
- Given 인증 방식 `ad`(또는 모드 행 없이 재직 admin이 있는 시스템)
- When KIM의 비밀번호를 재설정한다(없는 id여도)
- Then 409 `invalid-state` "앱에서 계정을 직접 관리할 때만 쓸 수 있습니다."이고 해시·세션은 그대로다

### US-053 자기 자신의 비밀번호는 재설정할 수 없다
- Given 인증 방식 `local`, ROOT로 로그인
- When ROOT 자신의 비밀번호를 재설정한다
- Then 409 `invalid-state` "자기 자신의 비밀번호는 내 정보에서 바꾸세요."이고 기존 비밀번호로 계속 로그인된다

### US-054 퇴사자의 비밀번호는 재설정할 수 없다
- Given 인증 방식 `local`, lee 퇴사
- When lee의 비밀번호를 재설정한다
- Then 409 `invalid-state` "이미 퇴사 처리된 사용자입니다"다

### US-055 약한 비밀번호로 재설정하면 422(위치 password)이고 기존 비밀번호·세션이 그대로다
- Given 인증 방식 `local`, KIM(아이디 "kimsales1") 세션 있음
- When 비밀번호 "short", "KIMSALES1", ""로 각각 재설정한다
- Then 422 `invalid-value`, 위치 `["password"]`(US-R6 문구)이고 KIM은 기존 비밀번호로 로그인되며 세션이 남아 있다

### US-056 없는 사용자의 재설정은 404다
- Given 인증 방식 `local`
- When 없는 id의 비밀번호를 재설정한다
- Then 404 `not-found`다

### US-057 연결이 없는 사용자를 삭제하면 deleted이고 어떤 목록에도 없으며 세션·해시도 지워진다
- Given KIM이 로그인한 적이 있어 세션·해시가 있고 다른 연결은 없다
- When `DELETE /users/{KIM}`
- Then 200 `{"outcome": "deleted"}`, `status=all` 목록에 KIM이 없고 KIM의 세션·해시 행이 없다. 다른 사용자의 세션·해시는 그대로다

### US-058 연결이 하나라도 있으면 삭제는 퇴사 처리가 되고 행·연결은 남으며 세션·해시는 지워진다
- Given KIM에게 연결 종류(2.2의 17종) 중 하나만 있다(종류마다 따로)
- When KIM을 삭제한다
- Then 200 `{"outcome": "resigned"}`, KIM 행은 `deleted_at` = 시계 시각으로 남고 연결 행은 KIM을 계속 가리키며, KIM의 세션·해시 행은 없다

### US-059 (폐기 2026-11-13)
- 사용자 행이 등록자를 기록하지 않아 "자기 자신만 등록자로 가리키는" 상태가 없다. 대체 케이스 US-112.

### US-060 퇴사 처리된 사용자는 기본 목록에서 빠지고 퇴사 목록에 보인다
- Given KIM이 Deal Owner라서 삭제가 퇴사 처리됐다
- When 기본 목록과 `status=resigned` 목록을 본다
- Then 기본 목록에 KIM이 없고 퇴사 목록에 KIM이 있다

### US-061 삭제·퇴사된 사용자의 기존 세션은 다음 요청부터 401이고 다시 로그인할 수 없다
- Given KIM이 로그인해 세션이 있고 AD 비밀번호도 맞다(퇴사 처리되는 경우와 물리 삭제되는 경우 각각)
- When ROOT가 KIM을 삭제한 뒤 KIM이 그 세션으로 업무 조회를 부르고, 다시 로그인한다
- Then 업무 조회는 401, 로그인도 401이다. 같은 아이디로 다시 등록돼도 옛 세션은 계속 401이다

### US-062 (폐기 2026-11-13)
- `DELETE /users/{user_id}`의 `reason` 쿼리를 없앴다. 대체 케이스 US-113.

### US-063 이미 퇴사한 사용자를 다시 삭제하면 409다
- Given lee 퇴사
- When lee를 삭제한다
- Then 409 `invalid-state` "이미 퇴사 처리된 사용자입니다"다

### US-064 없는 id나 이미 물리 삭제된 사용자의 삭제는 404다
- When 없는 id, 그리고 방금 `deleted`된 id를 삭제한다
- Then 둘 다 404 `not-found`다

### US-065 admin은 연결 유무와 무관하게 자기 자신을 삭제할 수 없고 세션은 유지된다
- Given ROOT·BOSS가 재직 admin, ROOT에게 연결이 있거나 없다(각각)
- When ROOT가 자기 자신을 삭제한다
- Then 409 `invalid-state` "자기 자신은 삭제할 수 없습니다"이고 ROOT의 `GET /auth/me`는 200이다

### US-066 재직 admin이 하나뿐이면 그 admin을 삭제할 수 없고 퇴사한 admin은 세지 않는다
- Given 재직 admin은 BOSS 하나, 퇴사한 admin이 하나 있다. 요청자 id는 BOSS와 다르다(유스케이스 Fake)
- When BOSS를 삭제한다
- Then 409 `invalid-state` "마지막 관리자는 삭제할 수 없습니다"이고 BOSS·세션이 그대로다

### US-067 재직 admin이 둘이면 다른 admin을 삭제할 수 있다
- Given ROOT·BOSS 재직 admin, BOSS 연결 없음
- When ROOT가 BOSS를 삭제한다
- Then 200 `deleted`이고 재직 admin 수는 1이다

### US-068 모든 역할이 사용자 선택 목록을 읽는다
- Given admin·sales·user 각각으로 로그인
- When `GET /user-options`
- Then 모두 200이다

### US-069 선택 목록 항목은 id·name·resigned·label·role·login_id만 담고 이메일이 없다
- Given kim(표시 이름 "김영업", 이메일 있음), lee(표시 이름 없음)
- When `GET /user-options`
- Then
  - 각 항목 키는 정확히 `id`·`name`·`resigned`·`label`·`role`·`login_id`다.
  - kim의 `login_id`는 "kim", lee의 `name`·`login_id`는 모두 "lee"다.
  - 응답 어디에도 kim의 이메일이 없다.
  - Deal 응답의 `owner`(UserRef)에는 `login_id`가 없다.

### US-070 선택 목록은 기본이 재직자이고 include_resigned면 퇴사자를 "(퇴사)"와 함께 더한다
- Given hong·kim 재직, gone 퇴사(이름 "고원")
- When 기본으로, 그리고 `include_resigned=true`로 조회한다
- Then 기본은 hong·kim만, 뒤에는 gone이 `resigned` true·`label` "고원(퇴사)"·자기 `role`과 함께 더해진다

### US-071 keyword는 화면 이름을 대소문자 무시로 찾고 표시 이름이 있는 사용자는 아이디로 찾지 않는다
- Given kim(표시 이름 "김영업"), young(표시 이름 "Kim Young"), lee(표시 이름 없음), gone(퇴사, 표시 이름 "Kim Gone")
- When `keyword=kim`, `keyword=YOUNG`, `keyword=lee`, `keyword=kim&include_resigned=true`로 조회한다
- Then 각각 [young], [young], [lee], [young, gone]이다(아이디가 "kim"인 사용자는 표시 이름 "김영업"에 "kim"이 없어 나오지 않는다)

### US-072 role 필터는 그 역할만 돌려주고 include_resigned·keyword와 함께 쓸 수 있다
- Given admin root, sales hong(표시 이름 "홍길동")·kim(표시 이름 "김영업")·old(퇴사 sales), user lee
- When `role=sales`, `role=sales&include_resigned=true`, `role=admin`, `role=user`, `role=sales&keyword=홍`, role 없음
- Then 각각 [hong, kim], [hong, kim, old], [root], [lee], [hong], 재직자 전체이고 모든 항목에 `role`이 있다

### US-073 선택 목록은 페이지 없이 조건에 맞는 사용자를 전부 돌려준다
- Given 재직 사용자 201명
- When `GET /user-options`
- Then 항목이 201개다

### US-074 선택 목록의 잘못된 파라미터·모르는 파라미터는 422다
- When `limit=10`, `offset=0`, `foo=1`, `role=owner`, `include_resigned=maybe`, `keyword`=101자
- Then 모두 422 `request-validation`이다

### US-075 admin이 아니면 사용자 관리 API는 403이고 대상은 바뀌지 않는다
- Given KIM(sales), VIEWER(user)로 각각 로그인
- When `GET /users`, `POST /users`, `PATCH /users/{id}`, `PUT /users/{id}/role`, `PUT /users/{id}/password`, `DELETE /users/{id}`를 부른다
- Then 모두 403 `forbidden` "관리자 권한이 필요합니다"이고 대상 사용자의 역할·프로필·해시·세션은 그대로다

### US-076 사용자 한 명을 읽거나 통째로 바꾸는 API는 없다
- Given ROOT로 로그인
- When `GET`·`PUT`·`POST /users/{id}`를 부른다
- Then 모두 405다

### US-077 화면: 목록은 기본으로 재직자만 보인다
- Given admin으로 `/admin/users`, Fake에 재직 6명·퇴사 1명
- When 화면이 열린다
- Then 재직 6명의 아이디 칸이 보이고 퇴사자는 없다

### US-078 화면: 표는 9칸 머리글과 값을 보이고 등록자·퇴사 사유 열이 없으며 없는 값은 "-"다
- When 화면이 열린다
- Then 머리글 아이디·역할·이름·이메일·전화번호·등록일·마지막 로그인·퇴사 일시가 보이고 "등록자"·"퇴사 사유" 머리글은 없다. kim 행에 "sales"·"김영업"이 있으며 전화·퇴사 일시 칸이 "-"다

### US-079 화면: 상태 선택은 재직·퇴사·전체이고 퇴사를 고르면 퇴사자만 보인다
- When "상태"에서 "퇴사"를 고른다
- Then 선택지가 ["재직", "퇴사", "전체"]이고 퇴사자만 보인다

### US-080 화면: 퇴사 행은 "이름(퇴사)"·퇴사 일시를 보이고 작업 버튼이 없다
- When "전체"를 고른다
- Then 퇴사 행 이름이 "<이름>(퇴사)", 퇴사 일시 칸에 퇴사 시각이 보이며 정보 수정·재설정·역할 변경·삭제 버튼이 없다

### US-081 화면: 사용자가 없으면 빈 메시지를 보인다
- Given 목록이 비어 있다
- When 화면이 열린다(그리고 "퇴사"를 고른다)
- Then "등록된 사용자가 없습니다."(퇴사 필터는 "퇴사한 사용자가 없습니다.")가 보인다

### US-082 화면: 목록을 읽지 못하면 서버 문구를 오류로 보인다
- Given 목록 조회가 서버 오류를 던진다
- When 화면이 열린다
- Then 경고 영역에 서버 문구가 보인다

### US-083 화면: 본인 행에는 작업 버튼이 없고 다른 재직 행에는 정보 수정·역할 변경·삭제가 있다
- Given root로 로그인
- When 화면이 열린다
- Then root 행에는 버튼이 없고 kim 행에는 "정보 수정"·"역할 변경"·"삭제"가 있다

### US-084 화면: AD 모드에는 비밀번호 칸·재설정 버튼이 없고 아이디 칸 이름이 "AD 아이디"다
- Given 인증 방식 `ad`
- When 화면이 열린다
- Then "비밀번호" 글자·칸·"비밀번호 재설정" 버튼이 없고 등록 폼의 아이디 칸 이름은 "AD 아이디"다

### US-085 화면: local 모드는 다른 재직 행에 비밀번호 재설정 버튼을 둔다
- Given 인증 방식 `local`, root로 로그인
- When 화면이 열린다
- Then kim 행에 "비밀번호 재설정" 버튼이 있고 root 행에는 없다

### US-086 화면: AD 아이디를 고른 역할로 등록하면 목록에 행이 생기고 폼이 비며 역할 기본값은 sales다
- Given 등록 폼의 역할 칸이 "sales"다
- When AD 아이디 "newbie", 이름 "신입영업", 역할 user로 "추가"를 누른다
- Then newbie 행(역할 user, 이름 신입영업)이 보이고 AD 아이디·이름 칸이 빈다

### US-087 화면: 필수 칸이 비면 요청하지 않고 모드별 문구를 보인다
- When AD 모드에서 빈 폼으로, local 모드에서 아이디·비밀번호·이름 중 하나가 빈 채로 "추가"를 누른다
- Then 등록 요청이 없고 "AD 아이디와 이름을 입력하세요." / "아이디, 비밀번호, 이름을 입력하세요."가 보인다

### US-088 화면: local 등록에서 비밀번호 확인이 다르면 요청하지 않는다
- Given local 모드
- When 비밀번호와 확인을 다르게 입력하고 "추가"를 누른다
- Then 등록 요청이 없고 "비밀번호 확인이 일치하지 않습니다."가 보인다

### US-089 화면: local 등록은 비밀번호·프로필을 보내고 빈 이메일·전화는 보내지 않으며 성공하면 폼을 비운다
- Given local 모드, 칸 아이디·비밀번호·비밀번호 확인·이름·이메일·전화번호·역할이 있다
- When 모든 칸을 채워(그리고 이메일·전화를 비워) 등록한다
- Then 게이트웨이에 아이디·역할·이름·비밀번호(와 이메일·전화)가 가고 빈 이메일·전화는 null로 넘어가 요청 본문에서 빠진다. 새 행에 전화가 보이고 폼이 빈다. 그 사용자는 그 비밀번호로 로그인된다

### US-090 화면: 등록이 거절되면 서버 문구를 보이고 비밀번호 칸만 비운다
- Given 서버가 약한 비밀번호(위치 password) 또는 중복 아이디로 거절한다
- When 등록한다
- Then 서버 문구가 보이고 비밀번호·확인 칸은 비고 아이디·이름 칸은 입력이 남는다. 위치가 `password`면 비밀번호 칸이 오류로 표시된다

### US-091 화면: 입력한 비밀번호는 성공·실패 뒤 요청 캐시에 남지 않는다
- Given local 모드
- When 등록(성공·실패)과 비밀번호 재설정(성공·실패)을 한다
- Then 요청 캐시 어디에도 입력한 비밀번호 문자열이 없다

### US-092 화면: 정보 수정은 현재 값을 채우고 바뀐 칸만 저장하며 바뀐 게 없으면 저장할 수 없다
- Given local 모드, kim 행의 "정보 수정"을 누른다
- When 대화상자가 열리고 전화만 바꿔 "저장"을 누른다
- Then 열릴 때 이름·이메일·전화가 현재 값이고 "저장"이 비활성이다. 저장하면 게이트웨이에 전화만 가고 대화상자가 닫히며 행의 전화가 바뀐다

### US-093 화면: 정보 수정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다
- Given 서버가 이메일 형식 오류로 거절한다
- When 잘못된 이메일로 저장한다
- Then 대화상자 안에 서버 문구가 보이고 대화상자가 열려 있다

### US-094 화면: 정보 수정 취소는 요청하지 않는다
- When 값을 바꾼 뒤 "취소"를 누른다
- Then 대화상자가 닫히고 수정 요청이 없다

### US-095 화면: AD 모드 정보 수정은 이름·이메일을 막고 전화만 보낸다
- Given AD 모드
- When "정보 수정"을 열고 전화를 바꿔 저장한다
- Then 이름·이메일 칸이 비활성이고 "이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다."가 보이며 게이트웨이에는 전화만 간다

### US-096 화면: 비밀번호를 재설정하면 대화상자가 닫히고 로그인 종료 안내가 보인다
- Given local 모드
- When kim의 "비밀번호 재설정"에서 같은 새 비밀번호를 두 번 넣고 "재설정"을 누른다
- Then 대화상자가 닫히고 "kim 사용자의 비밀번호가 재설정되었습니다. 그 사용자의 로그인은 모두 종료됩니다."가 보인다

### US-097 화면: 새 비밀번호 확인이 다르면 요청하지 않는다
- When 두 칸을 다르게 넣고 "재설정"을 누른다
- Then 요청이 없고 "새 비밀번호 확인이 일치하지 않습니다."가 보인다

### US-098 화면: 재설정이 거절되면 서버 문구를 보이고 대화상자를 열어 둔다
- Given 서버가 약한 비밀번호로 거절한다
- When 재설정한다
- Then 서버 문구가 보이고 두 칸이 비며 대화상자가 열려 있다

### US-099 화면: 역할 변경 대화상자는 현재 역할을 고른 채 열리고 다른 역할을 골라야 변경할 수 있다
- When kim(sales)의 "역할 변경"을 누르고 역할을 user, 다시 sales로 고른다
- Then 대화상자에 "kim (김영업)"과 "다음 요청부터 적용" 안내가 있고 선택지는 [admin, sales, user]다. 처음과 sales로 돌아왔을 때 "변경"이 비활성, user일 때 활성이다

### US-100 화면: 역할을 바꾸면 대화상자가 닫히고 알림과 역할 칸이 바뀐다
- When kim을 user로 바꿔 "변경"을 누른다
- Then 게이트웨이에 (kim id, "user")가 한 번 가고, 대화상자가 닫히며 "kim 사용자의 역할이 sales에서 user(으)로 바뀌었습니다."가 보이고 kim 행 역할이 user다

### US-101 화면: 역할 변경 취소는 요청하지 않는다
- When 역할을 고른 뒤 "취소"를 누른다
- Then 대화상자가 닫히고 요청이 없으며 역할 칸은 그대로다

### US-102 화면: 역할 변경이 거절되면 대화상자를 닫고 오류 배너를 보이며 이전 알림을 지운다
- Given 직전에 다른 사용자의 역할 변경 알림이 보인다. 서버가 거절한다
- When 역할을 바꾼다
- Then 대화상자가 닫히고 오류 배너에 서버 문구가 보이며 성공 알림은 사라지고 역할 칸은 그대로다

### US-103 화면: sales를 다른 역할로 고르면 Owner 안내를 보인다
- When kim(sales)의 역할을 user로 고른다. han(user)의 역할을 sales·admin으로 고른다
- Then kim에게는 "sales가 아니면 새 Deal의 Owner로 지정할 수 없습니다. 이미 Owner인 Deal은 그대로 남습니다."가 보이고 han에게는 보이지 않는다

### US-104 화면: 삭제 확인을 취소하면 요청하지 않는다
- When kim의 "삭제"를 누르고 대화상자 "사용자 삭제"에서 "취소"를 누른다
- Then 대화상자에 "연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다."가 있었고, 닫힌 뒤 삭제 요청이 없으며 kim이 그대로 보인다

### US-105 화면: 삭제 결과에 따라 퇴사 처리·삭제 알림을 보이고 목록에서 뺀다
- Given kim은 연결이 있고 방금 등록한 temp는 없다
- When 각각 삭제를 확인한다
- Then "kim 사용자가 퇴사 처리되었습니다."·"temp 사용자가 삭제되었습니다."가 보이고 두 행이 기본 목록에서 사라진다. "퇴사"를 고르면 "김영업(퇴사)"이 보인다

### US-106 화면: 삭제가 거절되면 대화상자를 닫고 오류 배너를 보이며 이전 알림을 지운다
- Given 직전 삭제의 성공 알림이 보인다. 서버가 다음 삭제를 거절한다
- When 삭제를 확인한다
- Then 대화상자가 닫히고 오류 배너에 서버 문구가 보이며 성공 알림이 사라진다

### US-107 화면: 등록·삭제·역할 변경 뒤 사용자 선택 목록과 Deal 목록을 다시 읽게 한다
- Given 사용자 선택 목록(role=sales)과 Deal 목록이 캐시에 있다
- When 사용자를 등록하고, 삭제하고, 역할을 바꾼다(각각)
- Then 각 작업 뒤 선택 목록이 무효화되고 역할 변경 뒤에는 Deal 목록도 무효화된다. 역할 변경 뒤 sales 선택 목록에 바뀐 사용자가 없다

### US-108 게이트웨이: 목록은 가득 찬 페이지가 오는 동안 이어 읽는다
- Given 서버가 첫 페이지 200개, 둘째 페이지 3개를 준다
- When 목록을 읽는다
- Then 요청은 `status`·`limit=200`으로 두 번(둘째는 `offset=200`)이고 203명을 돌려준다

### US-109 게이트웨이: 선택 목록은 한 번 요청하고 페이지 값을 보내지 않는다
- When `options({})`, `options({includeResigned: true, role: 'sales'})`를 부른다
- Then 각각 요청 하나이고 `limit`·`offset`이 없으며 `include_resigned`는 false/true, `role`은 둘째에만 있다. 응답 항목을 모두 돌려준다

### US-110 게이트웨이: 응답의 이름·퇴사 시각·역할을 화면 값으로 바꾸고 등록자·퇴사 사유는 만들지 않는다
- Given 표시 이름 없는 사용자, 퇴사 사용자(`deleted_at` 있음), 역할별 UserRef
- When 응답을 변환한다
- Then 이름은 아이디로, 퇴사자는 퇴사 시각을, UserRef는 서버 역할 그대로와 상태 `resigned`/`active`를 갖는다. 전화도 옮겨진다. 변환한 사용자에 등록자(`createdBy`)·퇴사 사유(`resignReason`) 키가 없다

### US-111 게이트웨이: 등록·수정·재설정·역할 변경·삭제 요청을 계약대로 보낸다
- When 등록(local·AD), 정보 수정(일부 키·null), 재설정, 역할 변경, 삭제를 부른다
- Then 등록은 `display_name`을 싣고 비밀번호·이메일·전화는 값이 있을 때만 싣는다. 수정은 `PATCH /users/{id}`에 준 키만(null 포함), 재설정은 `PUT /users/{id}/password`이고 204에 끝나며, 역할 변경은 `PUT /users/{id}/role` `{role}`, 삭제는 쿼리 없는 `DELETE /users/{id}`이고 `outcome`을 돌려준다. 서버 거절(약한 비밀번호·중복·자기 삭제)은 서버 문구의 오류다

### US-112 다른 사용자를 등록한 admin도 다른 연결이 없으면 물리 삭제되고 그가 등록한 사용자는 재직 그대로다
- Given ROOT·BOSS가 재직 admin이고, BOSS가 KIM을 등록했다. BOSS에게는 2.2의 연결 17종이 하나도 없다
- When ROOT가 BOSS를 삭제한다
- Then 200 `{"outcome": "deleted"}`이고 `status=all` 목록에 BOSS가 없다. KIM은 재직 그대로이고 KIM의 응답은 삭제 전과 같다

### US-113 사용자 삭제에 쿼리 파라미터(없앤 reason 포함)를 보내면 422이고 사용자는 그대로다
- Given ROOT로 로그인, KIM은 연결 없는 재직 sales다
- When `DELETE /users/{KIM}?reason=resigned`, `?reason=fired`, `?foo=1`을 각각 보낸다
- Then 모두 422 `request-validation`이고 KIM은 재직 그대로이며 세션·해시도 그대로다. 이어서 쿼리 없이 `DELETE /users/{KIM}`을 보내면 200 `{"outcome": "deleted"}`다

### US-114 API 계약(OpenAPI)의 UserResponse에 created_by·delete_reason이 없고 사용자 삭제에 쿼리 파라미터가 없다
- When 앱이 만든 OpenAPI 문서를 읽는다
- Then `UserResponse`의 속성은 US-R11의 10개이고 `created_by`·`delete_reason`이 없으며 `UserDeleteReason` 스키마가 없다. `DELETE /api/v1/users/{user_id}`의 파라미터는 경로 `user_id` 하나다

### US-115 선택 목록은 재직·퇴사·모든 역할 항목에 login_id를 항상 주고 keyword는 아이디로 찾지 않는다
- Given 다음 사용자
  - 재직 sales kim1·kim2(표시 이름 모두 "김영업")
  - 재직 admin root(표시 이름 "관리자")
  - 퇴사 sales old(표시 이름 "박영업")
  - 재직 user lee(표시 이름 없음)
- When 조건 없이, `include_resigned=true`로, `keyword=kim`으로 각각 조회한다
- Then
  - 조건 없음: 재직자 네 명의 `login_id`가 각각 "kim1"·"kim2"·"root"·"lee"다.
  - `include_resigned=true`: old도 `login_id` "old"와 `label` "박영업(퇴사)"를 가진다.
  - `keyword=kim`: 0건이다(표시 이름에 "kim"이 없고 아이디로는 찾지 않는다).

### US-116 API 계약(OpenAPI)의 선택 목록 항목은 UserOption(UserRef + 필수 login_id)이고 UserRef는 그대로다
- Given 앱의 openapi 문서
- When `GET /user-options` 200 응답 스키마와 `UserRef` 스키마를 본다
- Then 항목 스키마에는 `UserRef`의 다섯 필드와 `login_id`(string, 필수, null 불가)가 있다. `UserRef`에는 `login_id`가 없다

### US-117 게이트웨이: 선택 목록의 login_id를 loginId로 바꾼다
- Given `/user-options`가 `login_id` "kim1"인 항목을 돌려주는 fetch
- When `users.options({includeResigned: true})`를 부른다
- Then 결과 항목의 `loginId`는 "kim1"이고 다른 필드 변환은 그대로다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(초안): 구현된 사용자 관리 동작을 정본 명세로 옮김. 규칙 US-R1~R31, use case US-UC1~UC8, BDD 케이스 US-001~US-111 | US-001~US-111(신규) |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 등록자·퇴사 사유 제거(사용자 요청·결정 D1~D3). `users.created_by_user_id`(FK·인덱스)·`delete_reason`(CHECK 2개) 컬럼 제거(SC-R21), 등록자는 연결이 아님(연결 17→16종), `UserResponse`의 `created_by`·`delete_reason`·`UserDeleteReason` 제거, `DELETE`의 `reason` 쿼리 제거(보내면 422, Q2), 등록 401(요청자 행 없음) 제거(Q1), 화면 '등록자'·'퇴사 사유' 열 제거(11→9칸). 규칙 변경: 2.1 퇴사자·연결, 2.2, US-R8, US-R11, US-R12(문구), US-R16, US-R17, US-R22, US-R31, 2.4, 2.6, 2.8, US-UC2·UC7 | 신규 US-112~US-114. 변경 US-001, US-008, US-024, US-028, US-058, US-078, US-080, US-086, US-110, US-111. 폐기 US-022, US-030, US-059, US-062 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): CM 확정: Memo → Comment 엔티티 분리. 사용자 연결 종류 16→17종(`deal_comments.author_user_id` "Comment 작성자", 2.2·US-R17). CM-041이 Comment 연결을 검증 | 변경 US-058(연결 종류 수), US-112(문구) |
| 2026-11-20 | 확정(2026-11-20 사용자 확인): Deals 목록 담당자 후보를 `이름 (로그인 아이디)`로 보이기로 함(사용자 결정, DL-R40).<br>바뀐 규칙: US-R20(선택 목록 항목 `UserOption` = UserRef + `login_id`, 모든 항목에 항상 포함, keyword는 계속 이름만), 2.6, US-R31.<br>**API 하위 호환 추가**(응답 필드 추가). 아이디 비노출 원칙을 이 경로에서 폐지하므로 로그인한 모든 역할이 다른 사용자의 로그인 아이디를 볼 수 있다(사용자 수용).<br>다른 화면의 사용자 선택 표시는 그대로이고 마이그레이션은 없다 | 신규 US-115~US-117. 변경 US-069(키 집합) |
