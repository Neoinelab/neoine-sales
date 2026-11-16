# 선택 목록: BANT Label·Action 유형·Vendor   (feature 코드: CL, 상태: 확정(2026-11-16 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/domain/{bant,action_type,vendor}/*.py`, `app/application/choice.py`, `app/application/{bant,action_type,vendor}/*.py`, `app/application/deal/bant_choice.py`, `app/application/deal_action/type_choice.py`, `app/web/routers/{bant_labels,action_types,vendors}.py`, `app/web/schemas/{bant_label,action_type,vendor,choice}.py`, `app/infra/db/{bant_label_repository,action_type_repository,vendor_repository,models_catalog,deal_aggregates}.py`, `frontend/src/features/admin/deal-management/{LabelManager,LabelCategoryCard,ActionTypeManager,VendorManager,InlineNameEdit}.tsx`, `data/{labels,actionTypes,vendors}.ts`, `gateway/http/{labels,actionTypes,vendors}.ts`, `gateway/http/mappers/{label,actionType,vendor}.ts`, `shared/model/catalogChoice.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트가 어긋나는 점은 계획(`artifacts/10-analysis/cl-plan.md`)의 확인 필요 질문으로 분리했습니다.
>
> 2026-11-16 변경(초안, 사용자 확인 대기): Deal의 Solution을 Product로 이름 변경(화면 문구, API 필드·쿼리 `product`, Reports key `deal.product`, DB 컬럼 `deals.product`). 영향 규칙·케이스는 5장.

## 1. 개요

- 목적: Deal과 Action이 고르는 선택지 세 가지 — BANT Label(구분별), Action 유형, Vendor — 를 관리하고, Deal·Action 요청이 선택지를 `{id}`(있는 항목) 또는 `{name}`(찾거나 새로 만들 이름)으로 고르는 규칙(`CatalogChoice`)을 정한다.
- 사용자(역할): 모든 역할(목록 조회), sales·admin(BANT Label·Action 유형 등록), admin(이름 변경·삭제, Vendor 등록).
- 범위
  - Admin > Deal 관리(`/admin/deal`)의 "BANT Label"·"Action 유형"·"Vendor" 탭 화면
  - API `GET·POST /bant-labels`, `PATCH·DELETE /bant-labels/{label_id}`, `GET·POST /action-types`, `PATCH·DELETE /action-types/{type_id}`, `GET·POST /vendors`, `PATCH·DELETE /vendors/{vendor_id}`
  - 이름 규칙(정규화·길이·NUL·대소문자 무시 고유성), 사용 수(`usage_count`), 사용 중 삭제 거부, 이름 변경이 참조하는 응답에 미치는 효과
  - 선택 요청 형식 `CatalogChoiceRequest`(`{id}` 또는 `{name}`)와 그 해석(`choose_action_type`, `check_bant`·`resolve_bant`), 화면의 입력 → 선택 변환(`toChoice`)
- 범위 밖(다른 feature)
  - Deal 등록·수정에서 BANT·Vendor를 저장한 결과(Deal 응답의 `bant`·`vendor`, 저장 실패 시 새 Label이 남지 않음, 검증 순서, `bant`를 보내지 않은 PATCH, Deal의 `vendor_id` 검증 "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.") → DE. 목록 Vendor 필터 → DL
  - Action 등록·수정에서 유형을 저장한 결과(저장 실패 시 새 유형이 남지 않음, 없는 Deal 404가 유형 오류보다 먼저, 진행사항 오류와의 순서, History 문구) → AC
  - Deal History의 BANT·Vendor 항목 문구 → DD
  - 기본 시드 값(Label 23·유형 8)과 빈 DB에 시드가 들어가는지 → SC(SC-R3)
  - Status·Forecast 코드 탭, Deal 관리 화면의 탭 틀(기본 탭 `status`) → CD, 경고 기준 탭 → RK
  - 만든 사람(`created_by_user_id`)이 있는 사용자를 지우면 퇴사 처리 → US(US-R17)
  - 공통 권한 판정·CSRF·Problem 형식·id 경로/본문 형식·NUL 공통 규칙·Admin 화면 가드·오류 문구 표시 → PL(PL-R4~R8, PL-R9~R16, PL-R31, PL-R35~R39)
- 관련 화면·메뉴: Admin > Deal 관리(`/admin/deal`, PL-R35)의 탭 "BANT Label"(`?tab=label`), "Action 유형"(`?tab=action-type`), "Vendor"(`?tab=vendor`).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 선택 목록(카탈로그) | Deal·Action이 고르는 항목 목록. 이 feature는 BANT Label·Action 유형·Vendor 세 가지 |
| BANT 구분 | `budget`·`authority`·`need`·`timeline`(화면 이름 Budget·Authority·Need·Timeline). 이 선언 순서가 표시 순서다 |
| BANT Label | 구분 하나에 속한 선택지. 점수가 없고 구분과 이름만 가진다 |
| Action 유형 | Action의 분류 선택지(예: 통화, 미팅) |
| Vendor | Deal이 고르는 제조사. Product(2026-11-16 전 이름 Solution)는 Vendor와 무관한 Deal의 자유 텍스트다(DE) |
| 기본 항목 | 기준선 마이그레이션이 넣은 Label·유형(`is_default` true, `default_order` 있음, 만든 사람 없음). Vendor에는 기본 항목이 없다 |
| 직접 만든 항목 | 사용자가 만든 Label·유형(`is_default` false, 만든 사람 = 만든 사용자) |
| 사용 수(`usage_count`) | Label: 그 Label을 선택한 Deal 수, 유형: 그 유형을 쓰는 Action 수, Vendor: 그 Vendor를 고른 Deal 수 |
| 선택(`CatalogChoice`) | 요청이 항목을 고르는 형식. `{"id": <정수>}`(있는 항목) 또는 `{"name": <문자열>}`(대소문자 무시로 찾고, 없으면 새로 만들 이름) 중 정확히 하나 |
| 정규화 이름 | NUL 검사 뒤 앞뒤 공백을 지운 이름(CL-R1). 저장·비교는 이 값으로 한다 |

### 2.2 데이터 모델

모든 PK는 `id BIGINT` identity(SC-R11). 시각 컬럼 `created_at`·`updated_at`(timestamptz, NOT NULL).

`bant_labels`

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `category` | varchar(20), CHECK 4값 | BANT 구분 |
| `name` | varchar(50) | 정규화 이름 |
| `is_default` | boolean | 기본 Label 여부 |
| `default_order` | integer null, CHECK `is_default = (default_order is not null)` | 구분 안 기본 순서(1부터) |
| `created_by_user_id` | BIGINT null, FK `users.id` RESTRICT, 인덱스 | 만든 사람(기본 Label은 NULL) |
| 제약 | UNIQUE (`id`, `category`), 유니크 인덱스 `uq_bant_labels_category_name_lower` (`category`, `lower(name)`) | Deal의 BANT 선택이 복합 FK(`deal_bant_labels` → (`label_id`, `category`), `fk_deal_bant_labels_label`)로 구분이 맞는 Label만 가리킨다 |

`action_types`

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `name` | varchar(50) | 정규화 이름 |
| `is_default`, `default_order` | boolean, integer null, CHECK `is_default = (default_order is not null)` | 기본 유형과 순서(1~8) |
| `created_by_user_id` | BIGINT null, FK `users.id` RESTRICT, 인덱스 | 만든 사람 |
| 제약 | 유니크 인덱스 `uq_action_types_name_lower` (`lower(name)`) | 전체에서 대소문자 무시 고유. `deal_actions.action_type_id`가 FK RESTRICT(`fk_deal_actions_action_type_id_action_types`)로 가리킨다 |

`vendors`

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `name` | varchar(100) | 정규화 이름 |
| 제약 | 유니크 인덱스 `uq_vendors_name_lower` (`lower(name)`) | 전체에서 대소문자 무시 고유. `deals.vendor_id`가 FK RESTRICT(`fk_deals_vendor_id_vendors`)로 가리킨다 |

- 기본 시드 값(Label 23개·유형 8개, 순서·이름)은 SC 2.2와 SC-R3이 정본이다. 테스트용 Fake 시드(`backend/tests/fakes/catalog_seed.py`, `tests/factories_action_type.py`)가 같은 값을 쓴다.
- 엔티티: `BantLabel`·`ActionType`·`Vendor`(`AuditedEntity`, `create`·`rename`·`ensure_deletable`). `ActionType.ref` = `ActionTypeRef(id, name)`(Action이 가리키는 표시용 참조, 저장은 id만).
- 값: `CatalogChoice(id, name)`(application, 정확히 하나), DTO `LabelUsage`·`ActionTypeUsage`·`VendorUsage`(항목 + 사용 수).
- Port: `BantLabelRepository`(`list(category?, for_update)`·`get`·`add`·`update`·`delete`), `ActionTypeRepository`(`list(for_update)`·`get`·`add`·`update`·`delete`), `VendorRepository`(`list(for_update)`·`get(for_update)`·`add`·`update`·`delete`), 사용 수 `DealRepository.count_by_bant_label`·`count_by_vendor`, `DealActionRepository.count_by_action_type`.

### 2.3 비즈니스 규칙

이름
- **CL-R1** 이름 정규화(등록·이름 변경·`{name}` 선택 공통): ① NUL 문자(`\x00`)가 있으면(공백으로 감싸도) 422 `invalid-value` "<칸>에는 NUL 문자를 쓸 수 없습니다" ② 앞뒤 공백을 지운다 ③ 비었으면 422 `invalid-value` 필수 문구 ④ 지운 뒤 길이(유니코드 코드 포인트 수, 이모지 하나 = 1자)가 한도를 넘으면 422 `invalid-value` 길이 문구. 판정 순서는 ①→③→④이고 자르지 않고 거절한다.

  | 목록 | 한도 | NUL 칸 이름 | 필수 문구 | 길이 문구 |
  | --- | --- | --- | --- | --- |
  | BANT Label | 50 | "Label 이름" | Label 이름을 입력하세요. | Label 이름은 50자 이내로 입력하세요. |
  | Action 유형 | 50 | "유형" | 유형을 입력하세요. | 유형은 50자 이내로 입력하세요. |
  | Vendor | 100 | "Vendor 이름" | Vendor 이름을 입력하세요. | Vendor 이름은 100자 이내로 입력하세요. |
- **CL-R2** 이름 고유성: 정규화 이름을 소문자로 바꿔 비교한다. 범위는 BANT Label = **같은 구분 안**(다른 구분의 같은 이름은 허용), Action 유형 = 전체(기본 유형 포함), Vendor = 전체. 겹치면 409 `already-exists`이고 문구는 Label "같은 구분에 이미 있는 Label 이름입니다.", 유형 "이미 있는 유형 이름입니다.", Vendor "이미 있는 Vendor 이름입니다."이다. 이름 변경은 자기 자신을 빼고 비교하므로 자기 이름의 대소문자만 바꿀 수 있다. 저장되는 철자는 입력한 철자(정규화 뒤)다. DB 유니크 인덱스도 같은 규칙을 지키고, 위반은 같은 409로 바뀐다.

조회
- **CL-R3** 목록(`GET /bant-labels`, `GET /action-types`, `GET /vendors`)은 로그인한 모든 역할이 부르고(업무 조회, PL-R2) 페이지·필터 없이 전부를 배열로 돌려준다. 정렬: Label = 구분 선언 순(Budget→Authority→Need→Timeline) → 구분 안 기본 Label(`default_order` 순) → 직접 만든 Label(소문자 이름의 코드 포인트 순, 같으면 id 순). 유형 = 기본 유형(`default_order` 순) → 직접 만든 유형(소문자 이름 코드 포인트 순·id 순). Vendor = 소문자 이름 코드 포인트 순·id 순(예: "Oracle", "Sap Korea", "zeta"). 새 시스템의 목록은 기본 Label 23개(구분별 7·6·5·5)·기본 유형 8개(SC-R3 값)이고 Vendor는 빈 배열이다.
- **CL-R4** 사용 수: Label = `deal_bant_labels`에서 그 Label을 가리키는 Deal 수, 유형 = 그 유형을 쓰는 Action 수, Vendor = `vendor_id`가 그 Vendor인 Deal 수(Product 텍스트만 같은 Deal은 세지 않음). 쓰는 것이 없으면 0이다. 목록·이름 변경 응답에 실린다(등록 응답은 항상 0).
- **CL-R5** 응답 필드(정확히 이 키들): `BantLabelResponse` = `id`, `category`, `name`, `is_default`, `created_by`(UserRef 또는 null — 기본 Label은 null, 퇴사자도 가리킴, US-R12), `created_at`, `updated_at`, `usage_count`. `ActionTypeResponse` = `id`, `name`, `is_default`, `created_by`, `created_at`, `updated_at`, `usage_count`. `VendorResponse` = `id`, `name`, `usage_count`, `created_at`, `updated_at`(`solutions`·`is_default`·`created_by` 없음). id는 JSON 정수이고 나중에 만든 항목의 id가 더 크다. 시각 표기는 TM.

등록
- **CL-R6** BANT Label 등록 `POST /bant-labels` `{category, name}`, Action 유형 등록 `POST /action-types` `{name}`: sales·admin(user는 업무 쓰기 가드 403, PL-R6). 판정 순서: 요청 형식 422 `request-validation`(필드 누락, 모르는 구분, 문자열이 아닌 이름, 모르는 필드) → 이름 422(CL-R1) → 중복 409(CL-R2, 같은 구분·전체 목록을 잠근 채 판단). 성공하면 201, `Location: /api/v1/bant-labels/<id>`(유형은 `/api/v1/action-types/<id>`), 본문은 `is_default` false, `created_by` = 요청자, `created_at` = `updated_at` = 서버 시각, `usage_count` 0이다. 만든 Label·유형은 목록의 직접 만든 항목 자리(CL-R3)에 나온다. 요청자 행이 그 사이 사라졌으면 422 `invalid-reference` "참조하는 사용자이(가) 없습니다: <id>"이고 저장하지 않는다.
- **CL-R7** Vendor 등록 `POST /vendors` `{name}`: admin만(sales·user는 관리자 가드 403 "관리자 권한이 필요합니다", PL-R7). 판정 순서와 결과는 CL-R6과 같되 만든 사람을 기록하지 않는다. 201, `Location: /api/v1/vendors/<id>`, `usage_count` 0.

이름 변경
- **CL-R8** 이름 변경 `PATCH /bant-labels/{label_id}`·`PATCH /action-types/{type_id}`·`PATCH /vendors/{vendor_id}` 본문 `{name}`: admin만(sales·user 403 "관리자 권한이 필요합니다" — 관리자 가드가 먼저라 user도 같은 문구, 대상 id 조회보다 먼저). 판정 순서: 요청 형식 422 → 이름 422(CL-R1, **없는 id여도 이름 오류가 먼저**) → 없는 id 404 `not-found` → 중복 409(CL-R2). 성공하면 200과 바뀐 항목(사용 수 포함)이다. 기본 항목도 바꿀 수 있고 바꿔도 `is_default`·`default_order`(목록 자리)·`category`·`created_by`는 그대로다. 같은 이름을 다시 보내도 저장하고 `updated_at`이 서버 시각으로 바뀐다(무변경 판정 없음). 실패하면 이름이 바뀌지 않는다.
- **CL-R9** 이름 변경의 효과: Deal·Action은 항목을 id로 가리키므로 바꾼 이름이 곧바로 보인다 — Action 응답의 `action_type.name`, 그 Vendor를 쓰는 모든 Deal 응답(상세·목록)의 `vendor.name`, 화면이 Label id로 찾는 BANT 이름. 이미 남은 Deal History·Action History 문구는 그때의 이름 그대로이고 다시 쓰지 않는다(History 형식은 DD·AC).

삭제
- **CL-R10** 삭제 `DELETE /bant-labels/{label_id}`·`/action-types/{type_id}`·`/vendors/{vendor_id}`: admin만(sales·user 403 "관리자 권한이 필요합니다", 자기가 만든 Label·유형도 마찬가지). 판정 순서: 없는 id 404 → 사용 중 409 `invalid-state` → 204(물리 삭제). 사용 중 문구는 실제 건수를 담는다: "사용 중인 Label은 삭제할 수 없습니다. (Deal <n>건)", "사용 중인 유형은 삭제할 수 없습니다. (Action <n>건)", "사용 중인 Vendor는 삭제할 수 없습니다. (Deal <n>건)". 사용 수 집계가 놓친 연결이 있어도 FK RESTRICT가 삭제를 막고 그때 다시 센 실제 건수(최소 1)로 같은 409를 낸다. 기본 항목도 쓰이지 않으면 지울 수 있고 다시 시드되지 않는다. 쓰던 Deal·Action이 모두 지워지면 삭제할 수 있고, 지운 항목의 이름은 다시 등록할 수 있다. 다른 항목의 사용 수는 판정에 영향을 주지 않는다.
- **CL-R11** Label·유형의 `created_by_user_id`는 users FK RESTRICT라 그 사용자를 지우면 물리 삭제 대신 퇴사 처리가 되고 Label·유형과 만든 사람 표시는 남는다(규칙은 US-R17, 케이스는 US-058).

선택(`CatalogChoice`)
- **CL-R12** 선택 요청 형식(`CatalogChoiceRequest`, Deal 요청의 `bant.<구분>`과 Action 요청의 `action_type`): JSON 객체 `{"id": <정수>}` 또는 `{"name": <문자열>}` 중 정확히 하나. 둘 다 있거나 둘 다 없음, 문자열·정수 값 그대로(객체 아님), id가 JSON 정수가 아님(문자열·불리언·실수) 또는 1~2^53−1 밖(PL-R15), name이 문자열이 아님, 모르는 키는 모두 422 `request-validation`이다(Deal 등록·수정, Action 등록·수정 모두). 빈 문자열 `""`도 이름으로 받아 CL-R1이 판정한다. 이 형식 판정은 유스케이스까지 가지 않는다.
- **CL-R13** Action 유형 선택 해석(`choose_action_type`): `{id}`가 있는 유형이면 그 유형(`{id, name}` = 저장된 이름)이고, 없는 id면 422 `invalid-value` "선택한 유형이 없습니다. 목록에서 다시 선택하세요."이다. `{name}`은 CL-R1(유형 문구)로 정규화한 뒤 전체 유형에서 대소문자 무시로 **완전히 같은** 것(부분 일치 아님)을 찾아 쓰고(돌려주는 이름은 저장된 철자, 기본 유형 포함), 없으면 같은 작업 단위에서 새 유형을 만든다(CL-R15).
- **CL-R14** BANT 선택 해석(`check_bant` → `resolve_bant`): 구분마다 null(또는 키 없음) = 선택 안 함, `{id}` = 그 구분의 Label이어야 하며 다른 구분의 Label이거나 없는 id면 422 `invalid-value` "BANT Label이 올바르지 않습니다."(이 판정은 요청이 `bant`를 보낸 경우에 한다 — 보내지 않은 PATCH는 DE). `{name}`은 CL-R1(Label 문구)로 정규화한 뒤 **같은 구분**에서 대소문자 무시로 완전히 같은 Label을 찾아 쓰고, 없으면 그 구분에 새 Label을 만든다(다른 구분에만 있는 같은 이름은 쓰지 않는다). 여러 구분에 새 이름을 보내면 구분마다 하나씩 만든다. 판정 단계는 읽기만 하고 새 Label은 Deal 검증이 모두 끝난 뒤에 만든다.
- **CL-R15** 이름으로 새로 만든 항목은 직접 만든 항목이다: `is_default` false, `created_by` = 요청자, 시각 = 서버 시각, 새 정수 id, 목록에서 CL-R3 자리. 같은 작업 단위(트랜잭션) 안에서 만들고 커밋은 그 Deal·Action 저장 유스케이스가 한다 — 그래서 저장이 실패하면 새 항목도 남지 않는다(결과 검증은 DE·AC). 한 번 만든 이름은 다음 선택에서 재사용된다(새로 만들지 않음).
- **CL-R16** 화면의 입력 → 선택 변환(`toChoice(text, options)`): 앞뒤 공백을 지운 입력이 비면 null(선택 안 함), 선택지 중 이름이 대소문자 무시로 같은 것이 있으면 `{id}`(JSON 숫자), 없으면(부분 일치 포함) 지운 이름으로 `{name}`이다. 선택지가 비어 있으면 항상 `{name}`.

Vendor
- **CL-R17** Vendor에는 Solution 관리가 없다(여기의 Solution은 2026-10-22에 폐지된 Vendor 소속 관리 목록이고, Deal의 자유 텍스트는 2026-11-16부터 Product — DE): 예전 Solution 관리 경로(`POST /vendors/{vendor_id}/solutions`, `PATCH`·`DELETE /vendors/{vendor_id}/solutions/{id}`)는 없는 경로라 404(PL-R13)이고, OpenAPI에 Solution 경로·스키마가 없으며 Vendor 응답에 `solutions`가 없다. Deal은 Vendor를 목록 id(`vendor_id`)로만 고른다(`CatalogChoice`가 아님, 이름으로 새 Vendor를 만들 수 없음 — DE).

화면(frontend, `/admin/deal`, 가드 PL-R31)
- **CL-R18** 탭: Deal 관리 화면의 탭 "BANT Label"·"Action 유형"·"Vendor"는 각각 `?tab=label`·`?tab=action-type`·`?tab=vendor`로 열리고 선택된 탭으로 표시된다. 탭을 누르면 그 탭이 열리고 주소가 이 값으로 바뀐다(이력 교체). 탭 순서는 Status 코드, Forecast 코드, BANT Label, Action 유형, Vendor, 경고 기준이다(탭 틀·기본 탭은 CD).
- **CL-R19** BANT Label 탭: 안내 "구분마다 같은 이름은 만들 수 없습니다(대소문자 구분 없음). 사용 중인 Label은 이름을 바꿀 수 있지만 삭제할 수 없습니다.", 목록을 읽는 동안 "불러오는 중…". 구분마다 카드 하나(제목 h3 = Budget·Authority·Need·Timeline, 표 이름 "<구분> Label 목록"), 머리글 이름·사용·만든 사용자·시각·작업. 행: 이름(기본 Label은 "기본" 배지), 사용 "Deal <n>건", 만든 사람 "<이름>(퇴사자면 `(퇴사)`) · <만든 시각>" 또는 "시스템"(만든 사람 없음), 버튼 "이름 수정"·"삭제". 구분에 Label이 없으면 "등록된 Label이 없습니다.". 카드 아래 추가 폼(폼 이름 "<구분> Label 추가", 칸 "새 Label 이름", 버튼 "추가")은 입력값을 그대로 그 구분으로 보낸다(정규화는 서버). 성공하면 입력을 비우고, 실패하면 입력을 남긴다.
- **CL-R20** Action 유형 탭: 안내 "같은 이름은 만들 수 없습니다(대소문자 구분 없음). 사용 중인 유형은 이름을 바꿀 수 있지만 삭제할 수 없습니다.", 카드(이름 "Action 유형") 안 표 "Action 유형 목록"(머리글 이름·사용·만든 사용자·시각·작업), 행은 CL-R19와 같되 사용은 "Action <n>건", 비면 "등록된 유형이 없습니다.". 추가 폼 이름 "Action 유형 추가", 칸 "새 유형 이름", 버튼 "추가".
- **CL-R21** Vendor 탭: 안내 "Vendor 이름은 대소문자 구분 없이 중복될 수 없습니다. 사용 중인 Vendor는 이름을 바꿀 수 있지만 삭제할 수 없습니다.", 단일 표 "Vendor 목록"(머리글 이름·사용·작업, 만든 사람·기본 배지 없음), 사용 "Deal <n>건". Vendor가 없으면 "등록된 Vendor가 없습니다."를 보이고 빈 표 머리글도 남는다. 추가 폼(폼 이름 "Vendor 추가", 칸 "새 Vendor 이름", 버튼 "Vendor 추가")은 목록을 읽는 중·실패해도 보인다. Solution 관련 칸·버튼·문구는 없다.
- **CL-R22** 세 탭 공통 동작: "이름 수정"을 누르면 그 행의 이름 칸이 입력(접근 이름 "Label 이름"·"유형 이름"·"Vendor 이름", 현재 이름이 채워짐, 바로 입력 가능)과 "저장"·"취소"로 바뀌고 그 행의 "이름 수정"은 비활성이다. Enter·"저장"은 입력값으로 이름 변경을 요청하고 성공하면 입력을 닫는다. Esc·"취소"는 요청 없이 닫는다. "삭제"는 확인 대화상자(위험 버튼 "삭제")를 연다 — 제목·문구는 Label "Label 삭제"·"'<이름>' Label을 삭제할까요? 사용 중인 Label은 삭제할 수 없습니다.", 유형 "유형 삭제"·"'<이름>' 유형을 삭제할까요? 사용 중인 유형은 삭제할 수 없습니다.", Vendor "Vendor 삭제"·"'<이름>' Vendor를 삭제할까요?". 확인하면 삭제를 요청하고 성공·실패와 무관하게 대화상자를 닫는다. "취소"는 요청 없이 닫는다. 등록·이름 변경·삭제가 거절되면 서버 문구(PL-R37)를 탭 위 오류 배너에 보이고 항목은 그대로다(이름 수정 입력은 열린 채). 새 작업(추가·저장·삭제 확인·이름 수정 시작)을 하면 이전 오류를 지운다. 목록을 읽지 못하면 같은 배너에 보인다. 요청이 진행 중이면 "추가"·"저장"·"삭제" 버튼이 비활성이다. 서버가 거절할 행동도 화면은 숨기지 않는다(admin만 이 화면에 온다, PL-R31).
- **CL-R23** 캐시 갱신: 등록·삭제 성공 뒤 그 목록을, 이름 변경 성공 뒤 그 목록과 이름을 보여 주는 조회 — Label·Vendor는 Deal 조회(`keys.deals`), 유형은 Action 조회(`['actions']`) — 를 다시 읽게 한다.
- **CL-R24** 게이트웨이(`gateway/http/{labels,actionTypes,vendors}.ts`): 목록 `GET`, 등록 `POST`(Label `{category, name}`, 유형·Vendor `{name}`), 이름 변경 `PATCH …/{id}` `{name}`, 삭제 `DELETE …/{id}`(204면 성공). 이름은 화면 입력 그대로 보낸다. 409는 화면 kind `conflict`(서버 문구 그대로)로 던진다(PL-R39). 응답 변환: Label → `{id, category, name, isDefault, createdBy, createdAt, usageCount}`(`updated_at` 버림), 유형 → `{id, name, isDefault, createdBy, usageCount, createdAt, updatedAt}`, Vendor → `{id, name, usageCount}`(시각 버림). `created_by`가 null이면 `createdBy` null, 아니면 UserRef 변환(US-R31).

### 2.4 상태와 전이

| 현재 | 행동 | 다음 | 조건 |
| --- | --- | --- | --- |
| (없음) | 등록 또는 `{name}` 선택 | 직접 만든 항목(사용 0) | CL-R6·R7·R15 |
| 기본·직접 만든 항목 | 이름 변경 | 같은 항목(이름만 바뀜) | CL-R8 |
| 사용 수 0 | 삭제 | (없음, 물리 삭제) | CL-R10 |
| 사용 수 ≥ 1 | 삭제 | 그대로(409) | CL-R10 |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /bant-labels`, `GET /action-types`, `GET /vendors` | 401 | 가능 | 가능 | 가능 |
| `POST /bant-labels`, `POST /action-types` | 401 | 403 읽기 전용 문구 | 가능 | 가능 |
| `PATCH·DELETE /bant-labels/{label_id}`, `PATCH·DELETE /action-types/{type_id}` | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| `POST /vendors`, `PATCH·DELETE /vendors/{vendor_id}` | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| 이름으로 새 Label·유형 만들기(Deal·Action 저장 안에서) | 401 | 403(Deal·Action 쓰기 거절) | 가능 | 가능 |
| 화면 `/admin/deal?tab=label·action-type·vendor` | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

모든 경로는 업무 라우터(로그인·CSRF PL-R9, 쓰기 가드 PL-R6)이고 이름 변경·삭제와 Vendor 쓰기는 관리자 가드(PL-R7)가 더해진다. 읽기 전용 문구 = "이 작업을 할 권한이 없습니다(읽기 전용 계정)", 관리자 문구 = "관리자 권한이 필요합니다".

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/bant-labels` | — | 200 `BantLabelResponse[]` | 401 |
| POST `/bant-labels` | `BantLabelCreateRequest` `{category: "budget"\|"authority"\|"need"\|"timeline", name: str}` | 201 `BantLabelResponse` + `Location` | 403, 409 `already-exists`, 422 `invalid-value`·`request-validation`·`invalid-reference` |
| PATCH `/bant-labels/{label_id}` | `BantLabelRenameRequest` `{name: str}` | 200 `BantLabelResponse` | 403, 404, 409 `already-exists`, 422 |
| DELETE `/bant-labels/{label_id}` | — | 204 | 403, 404, 409 `invalid-state`, 422(id 형식) |
| GET `/action-types` | — | 200 `ActionTypeResponse[]` | 401 |
| POST `/action-types` | `ActionTypeNameRequest` `{name: str}` | 201 `ActionTypeResponse` + `Location` | 403, 409, 422 |
| PATCH `/action-types/{type_id}` | `ActionTypeNameRequest` | 200 `ActionTypeResponse` | 403, 404, 409, 422 |
| DELETE `/action-types/{type_id}` | — | 204 | 403, 404, 409 `invalid-state`, 422 |
| GET `/vendors` | — | 200 `VendorResponse[]` | 401 |
| POST `/vendors` | `VendorNameRequest` `{name: str}` | 201 `VendorResponse` + `Location` | 403, 409, 422 |
| PATCH `/vendors/{vendor_id}` | `VendorNameRequest` | 200 `VendorResponse` | 403, 404, 409, 422 |
| DELETE `/vendors/{vendor_id}` | — | 204 | 403, 404, 409 `invalid-state`, 422 |
| (Deal·Action 요청 안) `CatalogChoiceRequest` | `{id: int(1~2^53−1)}` 또는 `{name: str}` | — | 422 `request-validation`(CL-R12), 422 `invalid-value`(CL-R13·R14) |

- 응답 필드는 CL-R5. 모든 본문은 모르는 필드를 거부한다(422 `request-validation`). 경로 id 형식·공통 401·403·CSRF는 PL. 한 항목을 읽는 `GET …/{id}`는 없다(`Location`이 가리키는 경로에 GET이 없음, 계획 Q2).

### 2.7 화면 동작

CL-R16, CL-R18~CL-R24.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| Label 이름 비었음 / 51자 이상 / NUL | 422 `invalid-value` | Label 이름을 입력하세요. / Label 이름은 50자 이내로 입력하세요. / Label 이름에는 NUL 문자를 쓸 수 없습니다 |
| 유형 이름 비었음 / 51자 이상 / NUL | 422 `invalid-value` | 유형을 입력하세요. / 유형은 50자 이내로 입력하세요. / 유형에는 NUL 문자를 쓸 수 없습니다 |
| Vendor 이름 비었음 / 101자 이상 / NUL | 422 `invalid-value` | Vendor 이름을 입력하세요. / Vendor 이름은 100자 이내로 입력하세요. / Vendor 이름에는 NUL 문자를 쓸 수 없습니다 |
| 이름 중복 | 409 `already-exists` | 같은 구분에 이미 있는 Label 이름입니다. / 이미 있는 유형 이름입니다. / 이미 있는 Vendor 이름입니다. |
| 없는 항목(이름 변경·삭제) | 404 `not-found` | BANT Label을(를) 찾을 수 없습니다: <id> / Action 유형을(를) 찾을 수 없습니다: <id> / Vendor을(를) 찾을 수 없습니다: <id> |
| 사용 중 삭제 | 409 `invalid-state` | 사용 중인 Label은 삭제할 수 없습니다. (Deal <n>건) / 사용 중인 유형은 삭제할 수 없습니다. (Action <n>건) / 사용 중인 Vendor는 삭제할 수 없습니다. (Deal <n>건) |
| 선택 형식 위반 | 422 `request-validation` | 요청 형식이 올바르지 않습니다(`errors[].msg`에 "id와 name 중 하나만 보내세요." 포함 가능) |
| 없는 유형 id 선택 | 422 `invalid-value` | 선택한 유형이 없습니다. 목록에서 다시 선택하세요. |
| 다른 구분·없는 Label id 선택 | 422 `invalid-value` | BANT Label이 올바르지 않습니다. |
| 등록 요청자 행 없음 | 422 `invalid-reference` | 참조하는 사용자이(가) 없습니다: <id> |

화면 문구: CL-R19~CL-R22. 서버 문구 표시는 PL-R37.

## 3. Business use case

### CL-UC1 선택 목록 보기
- 행위자: 로그인한 모든 역할(Deal·Action 입력 화면의 선택지), admin(관리 화면)
- 사전 조건: 로그인
- 기본 흐름: 목록 API가 정해진 순서와 사용 수로 전부를 돌려준다(CL-R3~R5) → admin 화면은 탭별 표로 보인다(CL-R18~R21)
- 예외: 목록을 읽지 못하면 오류 배너
- 결과: 기본·직접 만든 항목과 사용 수

### CL-UC2 BANT Label·Action 유형 등록
- 행위자: sales·admin(화면은 admin)
- 기본 흐름: 이름(Label은 구분도) 입력 → 추가 → 201, 목록의 직접 만든 자리에 나타남(CL-R1·R2·R6, CL-R19·R20)
- 예외: user 403, 이름 규칙 422, 중복 409, 형식 422
- 결과: 만든 사람이 기록된 직접 만든 항목

### CL-UC3 Vendor 등록
- 행위자: admin
- 기본 흐름: 이름 입력 → Vendor 추가 → 201(CL-R1·R2·R7, CL-R21)
- 예외: sales·user 403, 이름 규칙 422, 중복 409
- 결과: 사용 0인 Vendor

### CL-UC4 이름 변경
- 행위자: admin
- 기본 흐름: 이름 수정 → 새 이름 저장 → 200(CL-R8, CL-R22) → Deal·Action 응답에 새 이름(CL-R9)
- 대안: 기본 항목·사용 중 항목도 가능, 자기 이름의 대소문자만 변경 가능
- 예외: 이름 규칙 422, 없는 id 404, 중복 409, sales·user 403, 취소(요청 없음)
- 결과: 같은 id·자리, 새 이름. 이미 남은 History는 그대로

### CL-UC5 삭제
- 행위자: admin
- 기본 흐름: 삭제 → 확인 → 쓰이지 않으면 204(CL-R10, CL-R22)
- 예외: 사용 중 409(건수), 없는 id 404, sales·user 403, 확인 취소(요청 없음)
- 결과: 물리 삭제. 그 이름은 다시 등록할 수 있다

### CL-UC6 Deal·Action 입력에서 이름 또는 id로 고르기
- 행위자: sales·admin(Deal 등록·수정, Action 등록·수정)
- 기본 흐름: 화면이 입력을 `{id}`/`{name}`/null로 바꾼다(CL-R16) → 서버가 형식을 확인하고(CL-R12) 있는 항목을 찾거나 새로 만든다(CL-R13~R15)
- 예외: 형식 위반 422 `request-validation`, 없는 유형 id·다른 구분 Label id 422, 이름 규칙 422
- 결과: 고른 항목(또는 새 직접 만든 항목). 저장 결과·실패 시 롤백은 DE·AC

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), VIEWER(user). 별도 언급이 없으면 기본 시드(Label 23·유형 8, Vendor 없음) 상태다. backend 케이스는 Fake UoW·Fake 시계를 쓰는 유스케이스·web 단위 테스트, frontend 케이스는 Fake 게이트웨이를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| CL-001 | 모든 역할이 Label 목록을 보면 기본 23개가 구분·시드 순서로 문서의 필드와 함께 나온다 | CL-R3, CL-R5, CL-UC1 | backend | `application/test_bant_label_use_cases.py::test_list_labels_returns_the_23_defaults_in_seed_order`<br>`web/test_bant_label_routes.py::test_every_role_lists_the_23_defaults_in_seed_order_with_the_documented_keys` |
| CL-002 | 직접 만든 Label은 그 구분의 기본 Label 뒤에 소문자 이름 코드 포인트 순으로 나온다 | CL-R3, CL-UC1 | backend | `application/test_bant_label_use_cases.py::test_list_labels_puts_custom_labels_after_defaults_sorted_by_name`<br>`web/test_bant_label_routes.py::test_custom_labels_follow_the_defaults_of_their_category_in_lower_name_order` |
| CL-003 | Label의 사용 수는 그 Label을 선택한 Deal 수이고 안 쓰면 0이다 | CL-R4, CL-UC1 | backend | `application/test_bant_label_use_cases.py::test_list_labels_reports_usage_counts_per_label`<br>`application/test_code_label_usage.py::test_label_usage_counts_the_deals_that_selected_it`<br>`web/test_bant_label_routes.py::test_usage_count_is_the_number_of_deals_that_selected_the_label` |
| CL-004 | sales·admin이 Label을 만들면 201·Location이고 이름은 정규화되며 만든 사람이 기록된다 | CL-R6, CL-R1, CL-UC2 | backend | `application/test_bant_label_use_cases.py::test_register_label_records_the_creator_and_is_not_default`<br>`application/test_bant_label_use_cases.py::test_register_label_trims_the_name`<br>`web/test_bant_label_routes.py::test_create_returns_201_with_location_the_trimmed_name_and_the_creator` |
| CL-005 | user가 Label을 만들면 읽기 전용 403이고 저장되지 않는다 | CL-R6, CL-UC2 | backend | `web/test_bant_label_route_permissions.py::test_user_cannot_create_a_label_and_nothing_is_saved` |
| CL-006 | 같은 구분에 대소문자·공백만 다른 Label 이름은 409다 | CL-R2, CL-UC2 | backend | `application/test_bant_label_use_cases.py::test_register_label_with_a_duplicate_name_in_the_category_conflicts`<br>`web/test_bant_label_routes.py::test_a_name_that_differs_only_in_case_or_spaces_in_the_category_is_409` |
| CL-007 | 다른 구분에 있는 이름으로는 Label을 만들 수 있다 | CL-R2, CL-UC2 | backend | `application/test_bant_label_use_cases.py::test_register_label_allows_the_same_name_in_another_category`<br>`web/test_bant_label_routes.py::test_the_same_name_may_be_created_in_another_category` |
| CL-008 | 비었거나 공백뿐인 Label 이름은 422이고 저장되지 않는다 | CL-R1, CL-UC2 | backend | `application/test_bant_label_use_cases.py::test_register_label_with_a_blank_name_stores_nothing`<br>`web/test_bant_label_routes.py::test_a_blank_name_is_422_and_nothing_is_saved` |
| CL-009 | Label 이름은 50자(코드 포인트)까지 되고 51자는 422다 | CL-R1, CL-UC2 | backend | `application/test_bant_label_use_cases.py::test_register_label_with_a_51_code_point_name_stores_nothing`<br>`application/test_bant_label_use_cases.py::test_register_label_accepts_a_50_code_point_name`<br>`web/test_bant_label_routes.py::test_the_name_limit_is_50_code_points` |
| CL-010 | NUL 문자가 든 Label 이름은 등록·이름 변경 모두 422이고 바뀌지 않는다 | CL-R1, CL-UC2, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_register_label_with_a_nul_name_stores_nothing`<br>`application/test_bant_label_use_cases.py::test_rename_label_with_a_nul_name_keeps_the_name`<br>`web/test_bant_label_routes.py::test_a_nul_in_the_name_is_422_on_create_and_on_rename` |
| CL-011 | 모르는 구분·이름 누락·모르는 필드로 Label을 만들면 422 request-validation이다 | CL-R6, CL-UC2 | backend | `web/test_bant_label_routes.py::test_a_malformed_create_body_is_request_validation` |
| CL-012 | admin이 기본 Label 이름을 바꾸면 같은 id·구분·기본 표시·자리가 유지된다 | CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_label_changes_the_name_and_keeps_the_rest`<br>`web/test_bant_label_routes.py::test_rename_of_a_default_label_keeps_the_id_category_default_flag_and_position` |
| CL-013 | 다른 사람이 만든 Label 이름을 바꿔도 만든 사람은 그대로이고 응답에 사용 수가 있다 | CL-R8, CL-R4, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_a_label_made_by_someone_else_keeps_the_creator_and_reports_usage`<br>`web/test_bant_label_routes.py::test_rename_of_someone_elses_label_keeps_the_creator_and_reports_usage` |
| CL-014 | Label 자기 이름의 대소문자만 바꾸는 것은 허용된다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_label_to_the_same_name_in_another_case_is_allowed`<br>`web/test_bant_label_routes.py::test_renaming_only_the_case_of_its_own_name_is_allowed` |
| CL-015 | 같은 구분 다른 Label의 이름으로 바꾸면 409이고 이름은 그대로다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_label_to_another_labels_name_conflicts_and_keeps_the_name`<br>`web/test_bant_label_routes.py::test_rename_to_another_labels_name_in_the_category_is_409_and_keeps_the_name` |
| CL-016 | 다른 구분에만 있는 이름으로는 Label 이름을 바꿀 수 있다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_label_to_a_name_that_exists_only_in_another_category_is_allowed`<br>`web/test_bant_label_routes.py::test_rename_to_a_name_that_exists_only_in_another_category_is_allowed` |
| CL-017 | 잘못된 이름으로 Label 이름을 바꾸면 422이고 없는 id여도 이름 오류가 먼저다 | CL-R1, CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_label_with_an_invalid_name_keeps_the_name`<br>`application/test_bant_label_use_cases.py::test_rename_a_missing_label_with_an_invalid_name_reports_the_name_first`<br>`web/test_bant_label_routes.py::test_an_invalid_new_name_is_422_and_beats_a_missing_id` |
| CL-018 | 없는 Label의 이름을 바꾸면 404다 | CL-R8, CL-UC4 | backend | `application/test_bant_label_use_cases.py::test_rename_missing_label_raises_not_found`<br>`web/test_bant_label_routes.py::test_rename_of_a_missing_label_is_404` |
| CL-019 | 쓰이지 않는 Label은 기본이든 남이 만든 것이든 삭제되고 그 Label만 사라진다 | CL-R10, CL-UC5 | backend | `application/test_bant_label_delete.py::test_delete_unused_label_removes_only_that_label`<br>`application/test_bant_label_delete.py::test_delete_label_ignores_usage_of_other_labels`<br>`application/test_code_label_usage.py::test_an_unused_label_is_deleted_even_when_other_labels_are_used`<br>`web/test_bant_label_routes.py::test_unused_labels_are_deleted_whether_default_or_made_by_someone_else` |
| CL-020 | 사용 중인 Label을 지우면 409(실제 Deal 수)이고 Label과 Deal 선택이 그대로다 | CL-R10, CL-UC5 | backend | `application/test_bant_label_delete.py::test_delete_label_in_use_raises_with_the_count_and_keeps_the_row`<br>`application/test_code_label_usage.py::test_a_label_in_use_cannot_be_deleted_and_the_message_has_the_real_count`<br>`web/test_bant_label_routes.py::test_deleting_a_used_label_is_409_with_the_real_deal_count_and_keeps_it` |
| CL-021 | 사용 수 집계가 놓친 연결도 삭제를 막고 실제 건수로 409다 | CL-R10, CL-UC5 | backend | `application/test_code_label_usage.py::test_a_label_connection_missed_by_the_count_is_caught_as_in_use_with_the_real_count` |
| CL-022 | Label을 선택한 Deal이 모두 지워지면 Label을 삭제할 수 있다 | CL-R10, CL-UC5 | backend | `application/test_bant_label_delete.py::test_label_becomes_deletable_after_the_deals_that_chose_it_are_deleted` |
| CL-023 | 없는 Label을 삭제하면 404다 | CL-R10, CL-UC5 | backend | `application/test_bant_label_delete.py::test_delete_missing_label_raises_not_found`<br>`web/test_bant_label_routes.py::test_deleting_a_missing_label_is_404` |
| CL-024 | sales·user는 Label 이름 변경·삭제가 관리자 403이다(자기가 만든 Label 포함) | CL-R8, CL-R10, CL-UC4, CL-UC5 | backend | `web/test_bant_label_route_permissions.py::test_sales_and_user_cannot_rename_or_delete_even_their_own_label` |
| CL-025 | 모든 역할이 유형 목록을 보면 기본 8개가 시드 순서로 만든 사람 없이 나온다 | CL-R3, CL-R5, CL-UC1 | backend | `application/test_list_action_types.py::test_list_returns_the_eight_defaults_in_seed_order_without_creators`<br>`web/test_action_type_route_permissions.py::test_every_role_may_list_action_types`<br>`web/test_action_type_routes.py::test_list_returns_the_defaults_in_order_with_the_documented_keys`<br>`web/test_action_type_routes.py::test_action_type_ids_are_json_integers` |
| CL-026 | 직접 만든 유형은 기본 유형 뒤에 소문자 이름 코드 포인트 순·id 순으로 나온다 | CL-R3, CL-UC1 | backend | `application/test_list_action_types.py::test_list_puts_custom_types_after_defaults_sorted_by_lower_name`<br>`web/test_action_type_routes.py::test_custom_types_follow_the_defaults_in_lower_name_order` |
| CL-027 | 유형의 사용 수는 그 유형을 쓰는 Action 수다 | CL-R4, CL-UC1 | backend | `application/test_list_action_types.py::test_list_reports_how_many_actions_use_each_type`<br>`web/test_action_type_routes.py::test_list_reports_how_many_actions_use_each_type` |
| CL-028 | sales·admin이 유형을 만들면 201·Location이고 정규화된 이름·만든 사람으로 목록 끝에 나온다 | CL-R6, CL-R1, CL-UC2 | backend | `application/test_register_action_type.py::test_register_records_the_creator_and_is_not_default`<br>`application/test_register_action_type.py::test_register_commits_the_new_type`<br>`application/test_register_action_type.py::test_register_trims_the_name`<br>`web/test_action_type_routes.py::test_create_returns_201_with_location_and_the_creator`<br>`web/test_action_type_routes.py::test_the_created_type_is_listed_afterwards` |
| CL-029 | user가 유형을 만들면 읽기 전용 403이고 저장되지 않는다 | CL-R6, CL-UC2 | backend | `web/test_action_type_route_permissions.py::test_user_cannot_create_a_type_and_nothing_is_saved` |
| CL-030 | 기존·기본 유형과 대소문자·공백만 다른 이름은 409다 | CL-R2, CL-UC2 | backend | `application/test_register_action_type.py::test_register_a_name_equal_to_an_existing_one_ignoring_case_conflicts`<br>`application/test_register_action_type.py::test_register_a_seeded_default_name_conflicts`<br>`web/test_action_type_routes.py::test_a_duplicate_name_ignoring_case_is_409`<br>`web/test_action_type_routes.py::test_the_name_of_a_seeded_default_is_taken` |
| CL-031 | 유형 이름은 공백뿐이면 필수 문구, 51자면 길이 문구로 422이고 50자는 된다 | CL-R1, CL-UC2 | backend | `application/test_register_action_type.py::test_register_an_invalid_name_stores_nothing`<br>`application/test_register_action_type.py::test_register_accepts_a_50_code_point_name`<br>`web/test_action_type_routes.py::test_invalid_names_are_422_with_the_domain_message`<br>`web/test_action_type_routes.py::test_a_50_character_name_is_accepted` |
| CL-032 | NUL 문자가 든 유형 이름은 422이고 저장되지 않는다 | CL-R1, CL-UC2 | backend | `application/test_register_action_type.py::test_register_rejects_nul`<br>`web/test_action_type_routes.py::test_a_nul_in_the_name_is_422` |
| CL-033 | 이름 누락·모르는 필드로 유형을 만들면 422 request-validation이다 | CL-R6, CL-UC2 | backend | `web/test_action_type_routes.py::test_a_malformed_body_is_request_validation` |
| CL-034 | admin이 기본 유형 이름을 바꾸면 자리·기본 표시가 유지되고 사용 수가 함께 온다 | CL-R8, CL-R4, CL-UC4 | backend | `application/test_rename_action_type.py::test_rename_a_default_type_keeps_its_default_flag_and_order`<br>`application/test_rename_action_type.py::test_rename_commits_once`<br>`application/test_rename_action_type.py::test_rename_reports_the_usage_count_of_the_type`<br>`web/test_action_type_routes.py::test_rename_returns_the_renamed_default_type`<br>`web/test_action_type_routes.py::test_rename_reports_the_usage_count` |
| CL-035 | 유형 자기 이름의 대소문자만 바꾸는 것은 허용된다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_rename_action_type.py::test_rename_only_the_case_of_its_own_name_is_allowed`<br>`web/test_action_type_routes.py::test_renaming_only_the_case_of_its_own_name_is_allowed` |
| CL-036 | 다른 유형의 이름으로 바꾸면 409이고 이름은 그대로다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_rename_action_type.py::test_rename_to_another_types_name_ignoring_case_conflicts_and_keeps_the_name`<br>`web/test_action_type_routes.py::test_rename_to_another_types_name_ignoring_case_is_409` |
| CL-037 | 공백뿐이거나 51자인 새 유형 이름은 422이고 이름은 그대로다 | CL-R1, CL-R8, CL-UC4 | backend | `application/test_rename_action_type.py::test_rename_to_an_invalid_name_keeps_the_name`<br>`web/test_action_type_routes.py::test_rename_with_a_blank_name_is_422_and_with_an_unknown_id_is_404` |
| CL-038 | 없는 유형의 이름 변경·삭제는 404다 | CL-R8, CL-R10, CL-UC4, CL-UC5 | backend | `application/test_delete_action_type.py::test_delete_a_missing_type_is_not_found`<br>`application/test_rename_action_type.py::test_rename_a_missing_type_is_not_found`<br>`web/test_action_type_routes.py::test_rename_with_a_blank_name_is_422_and_with_an_unknown_id_is_404`<br>`web/test_action_type_routes.py::test_delete_an_unknown_id_is_404` |
| CL-039 | 유형 이름을 바꾸면 Action 응답은 새 이름이고 이미 남은 History는 그대로다 | CL-R9, CL-UC4 | backend | `application/test_rename_action_type.py::test_a_rename_is_visible_on_the_actions_that_use_the_type`<br>`application/test_rename_action_type.py::test_a_rename_does_not_rewrite_the_history_that_is_already_written` |
| CL-040 | 쓰이지 않는 유형은 기본 유형이어도 삭제되고 그 유형만 사라진다 | CL-R10, CL-UC5 | backend | `application/test_delete_action_type.py::test_delete_an_unused_default_type_removes_only_that_type`<br>`application/test_delete_action_type.py::test_delete_ignores_the_usage_of_other_types`<br>`web/test_action_type_routes.py::test_delete_an_unused_type_is_204_and_the_type_disappears` |
| CL-041 | 사용 중인 유형을 지우면 409(실제 Action 수)이고 유형은 남는다 | CL-R10, CL-UC5 | backend | `application/test_delete_action_type.py::test_delete_a_used_type_is_refused_with_the_action_count_and_keeps_the_row`<br>`web/test_action_type_routes.py::test_delete_a_used_type_is_409_with_the_count_and_keeps_the_type` |
| CL-042 | 유형을 쓰던 Action이 모두 지워지면 유형을 삭제할 수 있다 | CL-R10, CL-UC5 | backend | `application/test_delete_action_type.py::test_a_type_becomes_deletable_after_its_actions_are_deleted` |
| CL-043 | 지운 유형의 이름은 다시 만들 수 있다 | CL-R10, CL-R2, CL-UC2 | backend | `application/test_delete_action_type.py::test_the_name_of_a_deleted_type_can_be_registered_again` |
| CL-044 | sales·user는 유형 이름 변경·삭제가 관리자 403이고 권한 판정이 id 조회보다 먼저다 | CL-R8, CL-R10, CL-UC4, CL-UC5 | backend | `web/test_action_type_route_permissions.py::test_sales_cannot_rename_or_delete_and_gets_the_admin_required_message`<br>`web/test_action_type_route_permissions.py::test_user_cannot_rename_or_delete`<br>`web/test_action_type_route_permissions.py::test_the_permission_is_checked_before_the_id_is_looked_up` |
| CL-045 | 모든 역할이 Vendor 목록을 보면 소문자 이름순으로 문서의 필드만 나오고 빈 시스템은 빈 배열이다 | CL-R3, CL-R5, CL-UC1 | backend | `application/test_vendor_use_cases.py::test_list_vendors_returns_usage_without_solutions`<br>`application/test_vendor_use_cases.py::test_list_vendors_of_an_empty_system_is_empty`<br>`web/test_vendor_routes.py::test_list_vendors_response_has_no_solutions_field`<br>`web/test_vendor_routes.py::test_list_orders_vendors_by_lower_name`<br>`web/test_vendor_routes.py::test_every_role_may_list_vendors` |
| CL-046 | Vendor 사용 수는 그 Vendor를 고른 Deal 수이고 Product 텍스트만 같은 Deal은 세지 않는다 | CL-R4, CL-UC1 | backend | `application/test_vendor_use_cases.py::test_list_vendors_does_not_count_deals_that_only_share_the_product_text` |
| CL-047 | admin이 Vendor를 만들면 201·Location·사용 0이고 나중 Vendor의 id가 더 크다 | CL-R7, CL-R1, CL-R5, CL-UC3 | backend | `application/test_vendor_use_cases.py::test_register_vendor_returns_it_with_zero_usage`<br>`application/test_vendor_use_cases.py::test_register_vendor_gives_a_later_vendor_a_larger_id`<br>`web/test_vendor_routes.py::test_create_vendor_returns_201_with_location_and_the_documented_body`<br>`web/test_vendor_routes.py::test_vendor_ids_are_json_integers` |
| CL-048 | sales·user는 Vendor 등록·이름 변경·삭제가 관리자 403이고 그대로다 | CL-R7, CL-R8, CL-R10, CL-UC3 | backend | `web/test_vendor_route_permissions.py::test_sales_and_user_cannot_change_vendors_and_nothing_is_saved`<br>`web/test_vendor_route_permissions.py::test_sales_gets_the_admin_required_message` |
| CL-049 | 대소문자만 다른 Vendor 이름은 409다 | CL-R2, CL-UC3 | backend | `application/test_vendor_use_cases.py::test_register_vendor_with_existing_name_ignoring_case_is_rejected`<br>`web/test_vendor_routes.py::test_duplicate_vendor_name_ignoring_case_is_409` |
| CL-050 | Vendor 이름은 공백뿐이면 422, 100자(코드 포인트, 공백 제거 뒤)는 되고 101자는 422다 | CL-R1, CL-UC3 | backend | `application/test_vendor_use_cases.py::test_register_vendor_with_an_invalid_name_stores_nothing`<br>`application/test_vendor_use_cases.py::test_register_vendor_accepts_a_100_code_point_name_after_trimming`<br>`web/test_vendor_routes.py::test_invalid_vendor_names_are_422_with_the_domain_message`<br>`web/test_vendor_routes.py::test_the_vendor_name_limit_is_accepted` |
| CL-051 | NUL 문자가 든 Vendor 이름은 422다 | CL-R1, CL-UC3 | backend | `application/test_vendor_use_cases.py::test_register_vendor_with_a_nul_name_stores_nothing`<br>`web/test_vendor_routes.py::test_a_nul_in_the_name_is_422` |
| CL-052 | 이름 누락·모르는 필드로 Vendor를 만들면 422 request-validation이다 | CL-R7, CL-UC3 | backend | `web/test_vendor_routes.py::test_a_malformed_body_is_request_validation` |
| CL-053 | admin이 Vendor 이름을 바꾸면 200과 사용 수가 오고 목록 순서가 새 이름을 따른다 | CL-R8, CL-R3, CL-UC4 | backend | `application/test_vendor_use_cases.py::test_rename_vendor_returns_usage_count`<br>`application/test_vendor_use_cases.py::test_rename_vendor_moves_it_in_the_list_order_to_follow_the_new_name`<br>`web/test_vendor_routes.py::test_rename_vendor_returns_the_renamed_vendor` |
| CL-054 | Vendor 자기 이름의 대소문자만 바꾸는 것은 허용된다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_vendor_use_cases.py::test_rename_vendor_to_its_own_name_in_other_case_is_allowed`<br>`web/test_vendor_routes.py::test_renaming_to_its_own_name_in_other_case_is_allowed` |
| CL-055 | 다른 Vendor의 이름으로 바꾸면 409이고 이름은 그대로다 | CL-R2, CL-R8, CL-UC4 | backend | `application/test_vendor_use_cases.py::test_rename_vendor_to_another_vendors_name_is_rejected` |
| CL-056 | 공백뿐인 새 Vendor 이름은 422다 | CL-R1, CL-R8, CL-UC4 | backend | `application/test_vendor_use_cases.py::test_rename_vendor_with_a_blank_name_is_rejected` |
| CL-057 | 없는 Vendor의 이름 변경·삭제는 404다 | CL-R8, CL-R10, CL-UC4, CL-UC5 | backend | `application/test_vendor_delete.py::test_delete_missing_vendor_raises_not_found`<br>`application/test_vendor_use_cases.py::test_rename_missing_vendor_is_not_found`<br>`web/test_vendor_routes.py::test_delete_missing_vendor_is_404` |
| CL-058 | Vendor 이름을 바꾸면 그 Vendor를 쓰는 모든 Deal 응답에 새 이름이 나오고 History는 그대로다 | CL-R9, CL-UC4 | backend | `application/test_update_deal_vendor.py::test_renamed_vendor_shows_new_name_on_deal_and_keeps_old_history` |
| CL-059 | 쓰이지 않는 Vendor는 삭제되고 다른 Vendor의 사용은 영향이 없다 | CL-R10, CL-UC5 | backend | `application/test_vendor_delete.py::test_delete_unused_vendor_removes_it`<br>`application/test_vendor_delete.py::test_delete_vendor_ignores_usage_of_other_vendors`<br>`web/test_vendor_routes.py::test_delete_vendor_is_204_and_removes_it` |
| CL-060 | 사용 중인 Vendor를 지우면 409(실제 Deal 수)이고 Vendor는 남는다 | CL-R10, CL-UC5 | backend | `application/test_vendor_delete.py::test_delete_used_vendor_is_rejected_with_count` |
| CL-061 | Vendor를 쓰던 Deal이 지워지면 Vendor를 삭제할 수 있다 | CL-R10, CL-UC5 | backend | `application/test_vendor_delete.py::test_vendor_becomes_deletable_after_the_deals_that_chose_it_are_deleted` |
| CL-062 | Solution 관리 경로는 404이고 계약·응답·도메인에 Solution 관리가 없다 | CL-R17 | backend | `application/test_vendor_delete.py::test_solution_use_cases_are_gone`<br>`web/test_vendor_openapi.py::test_openapi_has_no_solution_paths_or_schemas`<br>`web/test_vendor_openapi.py::test_vendor_response_has_usage_and_no_solutions`<br>`web/test_vendor_routes.py::test_solution_routes_are_not_found`<br>`features/admin/deal-management/VendorManager.test.tsx > has no solution controls at all` |
| CL-063 | 선택이 id·name 중 정확히 하나가 아니거나 객체가 아니면 422 request-validation이다 | CL-R12, CL-UC6 | backend | `application/test_catalog_choice.py::test_choice_with_only_an_id_is_accepted`<br>`application/test_catalog_choice.py::test_choice_with_only_a_name_is_accepted`<br>`application/test_catalog_choice.py::test_choice_requires_exactly_one_of_id_and_name_when_both_are_given`<br>`application/test_catalog_choice.py::test_choice_requires_exactly_one_of_id_and_name_when_neither_is_given`<br>`web/test_catalog_choice_request.py::test_accepts_id_or_name`<br>`web/test_catalog_choice_request.py::test_rejects_both_or_neither`<br>`web/test_catalog_choice_request.py::test_rejects_plain_string`<br>`web/test_catalog_choice_request.py::test_rejects_a_malformed_id_and_a_non_string_name`<br>`web/test_catalog_choice_request.py::test_rejects_unknown_properties`<br>`web/test_catalog_choice_request.py::test_every_request_that_takes_a_choice_rejects_a_malformed_one`<br>`web/test_catalog_choice_request.py::test_every_request_that_takes_a_choice_accepts_an_id_or_a_name` |
| CL-064 | 선택 id는 범위 안 JSON 정수만 받는다 | CL-R12, CL-UC6 | backend | `web/test_catalog_choice_request.py::test_the_id_may_be_sent_as_a_json_integer`<br>`web/test_catalog_choice_request.py::test_the_largest_allowed_id_is_accepted`<br>`web/test_catalog_choice_request.py::test_choice_id_must_be_a_json_integer`<br>`web/test_catalog_choice_request.py::test_rejects_a_malformed_id_and_a_non_string_name` |
| CL-065 | 빈 문자열 name도 이름으로 받아 이름 규칙이 판정한다 | CL-R12, CL-R1, CL-UC6 | backend | `application/test_catalog_choice.py::test_an_empty_name_is_still_a_name_and_is_judged_by_the_name_rule_later`<br>`web/test_catalog_choice_request.py::test_an_empty_name_is_a_name_and_is_left_to_the_domain` |
| CL-066 | 있는 유형 id를 고르면 그 유형이 쓰이고 새 유형은 없다 | CL-R13, CL-UC6 | backend | `application/test_deal_action_type_choice.py::test_type_by_id_is_used` |
| CL-067 | 없는 유형 id를 고르면 422 "선택한 유형이 없습니다…"다 | CL-R13, CL-UC6 | backend | `application/test_deal_action_type_choice.py::test_unknown_type_id_is_rejected_and_stores_nothing` |
| CL-068 | 기존·기본 유형과 대소문자·공백만 다른 이름은 그 유형(저장된 철자)을 쓴다 | CL-R13, CL-UC6 | backend | `application/test_deal_action_type_choice.py::test_type_name_reuses_existing_ignoring_case`<br>`application/test_deal_action_type_choice.py::test_type_name_of_a_seeded_default_reuses_it` |
| CL-069 | 없는 유형 이름이면 요청자가 만든 새 유형이 생기고 다음 선택에서 재사용된다 | CL-R13, CL-R15, CL-UC6 | backend | `application/test_deal_action_type_choice.py::test_unknown_type_name_creates_a_type_by_the_actor`<br>`application/test_deal_action_type_choice.py::test_a_new_type_name_gets_an_allocated_id_and_is_referenced_by_the_action`<br>`application/test_deal_action_type_choice.py::test_two_new_type_names_get_increasing_ids`<br>`application/test_deal_action_type_choice.py::test_the_created_type_is_reused_by_the_next_registration` |
| CL-070 | 이름으로 고른 유형도 유형 이름 규칙(공백·51자·NUL 422, 50자 허용)을 따른다 | CL-R1, CL-R13, CL-UC6 | backend | `application/test_deal_action_type_choice.py::test_type_name_rules_apply_to_a_requested_name`<br>`application/test_deal_action_type_choice.py::test_a_50_code_point_type_name_is_accepted`<br>`application/test_deal_action_type_choice.py::test_nul_in_a_requested_type_name_is_rejected` |
| CL-071 | 그 구분의 Label id를 고르면 그 Label이 쓰인다 | CL-R14, CL-UC6 | backend | `application/test_deal_bant_choice.py::test_bant_by_id_is_kept` |
| CL-072 | 다른 구분의 Label id나 없는 id를 고르면 422 "BANT Label이 올바르지 않습니다."다 | CL-R14, CL-UC6 | backend | `application/test_deal_bant_choice.py::test_bant_id_of_another_category_is_rejected_and_stores_nothing`<br>`application/test_deal_bant_choice.py::test_an_unknown_bant_id_is_rejected_without_creating_a_label` |
| CL-073 | 같은 구분 Label과 대소문자만 다른 이름은 그 Label을 쓴다 | CL-R14, CL-UC6 | backend | `application/test_deal_bant_choice.py::test_bant_name_reuses_label_in_same_category_ignoring_case` |
| CL-074 | 같은 구분에 없는 이름은 그 구분에 요청자가 만든 새 Label이 되고 다른 구분의 같은 이름은 쓰지 않는다 | CL-R14, CL-R15, CL-UC6 | backend | `application/test_deal_bant_choice.py::test_bant_name_creates_label_in_that_category_by_the_actor`<br>`application/test_deal_bant_choice.py::test_a_new_label_name_gets_an_allocated_id`<br>`application/test_deal_bant_choice.py::test_same_name_in_another_category_creates_a_new_label`<br>`application/test_deal_bant_choice.py::test_new_names_in_several_categories_create_one_label_each`<br>`application/test_deal_bant_choice.py::test_a_created_label_is_reused_by_the_next_deal` |
| CL-075 | 이름으로 고른 BANT도 Label 이름 규칙(공백·51자·NUL 422, 50자 허용)을 따른다 | CL-R1, CL-R14, CL-UC6 | backend | `application/test_deal_bant_choice.py::test_blank_or_long_bant_name_is_rejected_with_label_messages`<br>`application/test_deal_bant_choice.py::test_a_50_code_point_bant_name_is_accepted`<br>`application/test_deal_bant_choice.py::test_nul_in_a_bant_name_is_rejected` |
| CL-076 | 화면: 입력을 null·{id}·{name}으로 바꾼다 | CL-R16, CL-UC6 | frontend | `shared/model/catalogChoice.test.ts > returns null for a blank text`<br>`shared/model/catalogChoice.test.ts > returns the id of the option with the same name`<br>`shared/model/catalogChoice.test.ts > sends catalog ids as JSON numbers`<br>`shared/model/catalogChoice.test.ts > returns the id for a case-insensitive match and ignores surrounding spaces`<br>`shared/model/catalogChoice.test.ts > returns the trimmed name when no option has the same name`<br>`shared/model/catalogChoice.test.ts > does not treat a partial match as the same option`<br>`shared/model/catalogChoice.test.ts > returns a name when there are no options at all` |
| CL-077 | 화면: BANT Label·Action 유형·Vendor 탭이 ?tab= 주소로 열리고 누르면 주소가 바뀐다 | CL-R18, CL-UC1 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > is the tab right after BANT Label, opened by ?tab=action-type`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > switches to the tab by clicking it and keeps ?tab=action-type in the address`<br>`features/admin/deal-management/LabelManager.test.tsx > opens at ?tab=label as the selected tab right after the code tabs`<br>`features/admin/deal-management/LabelManager.test.tsx > switches to the tab by clicking it and keeps ?tab=label in the address`<br>`features/admin/deal-management/VendorManager.test.tsx > is named Vendor, opens at ?tab=vendor and is selected`<br>`features/admin/deal-management/VendorManager.test.tsx > is reached from the tab list and keeps the choice in the URL` |
| CL-078 | 화면: BANT 탭은 구분별 카드에 기본 배지·사용 Deal 수·만든 사람을 보인다 | CL-R19, CL-UC1 | frontend | `features/admin/deal-management/LabelManager.test.tsx > shows one section per BANT category with its default labels`<br>`features/admin/deal-management/LabelManager.test.tsx > marks default labels and shows the usage count and who created them`<br>`features/admin/deal-management/LabelManager.test.tsx > shows the creator and time of a label made by a user` |
| CL-079 | 화면: BANT Label을 추가하면 그 구분에 나타나고 입력이 비며 다른 구분의 같은 이름도 된다 | CL-R19, CL-UC2 | frontend | `features/admin/deal-management/LabelManager.test.tsx > adds a label and clears the input`<br>`features/admin/deal-management/LabelManager.test.tsx > lets the same name exist in a different category` |
| CL-080 | 화면: BANT Label 추가가 거절되면 서버 문구를 배너에 보인다 | CL-R19, CL-R22, CL-UC2 | frontend | `features/admin/deal-management/LabelManager.test.tsx > rejects a duplicate name in the same category regardless of case`<br>`features/admin/deal-management/LabelManager.test.tsx > shows the server messages for an empty and a too long name` |
| CL-081 | 화면: BANT Label 이름을 바꾸고(사용 중 포함) 중복이면 배너를 보인다 | CL-R22, CL-UC4 | frontend | `features/admin/deal-management/LabelManager.test.tsx > renames a label, including one in use`<br>`features/admin/deal-management/LabelManager.test.tsx > rejects renaming to a name that already exists in the category` |
| CL-082 | 화면: BANT Label 삭제는 확인 뒤에만 하고 사용 중이면 건수 문구를 보인다 | CL-R22, CL-UC5 | frontend | `features/admin/deal-management/LabelManager.test.tsx > deletes an unused label after confirmation`<br>`features/admin/deal-management/LabelManager.test.tsx > keeps the label when the confirmation is declined`<br>`features/admin/deal-management/LabelManager.test.tsx > refuses to delete a label that deals use and says how many` |
| CL-083 | 화면: Action 유형 탭은 안내·기본 순서·배지·사용 Action 수·만든 사람을 보인다 | CL-R20, CL-UC1 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > shows the guide sentence`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > lists the default types in order, marked as default, with the usage count`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > shows the creator of a type made by a user` |
| CL-084 | 화면: 유형을 추가하면 기본 뒤에 나타나고 입력이 비며 거절은 서버 문구로 보인다 | CL-R20, CL-R22, CL-UC2 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > adds a type, shows it after the defaults and clears the input`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > rejects a duplicate ignoring case with the server message in the error banner`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > shows the server messages for an empty name and a name over 50 characters` |
| CL-085 | 화면: 유형 이름 수정은 저장·대소문자만 변경·중복 거절·취소가 된다 | CL-R22, CL-UC4 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > renames a default type that actions use`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > allows changing only the case of its own name`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > refuses a name that another type has and shows the server message`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > cancels the rename without changing the name` |
| CL-086 | 화면: 유형 삭제는 확인 뒤에만 하고 사용 중이면 건수 문구, 쓰지 않게 되면 삭제된다 | CL-R22, CL-UC5 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > asks with the type name and deletes an unused type`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > keeps the type when the confirmation is declined`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > shows the 409 message with the count when the type is in use and keeps the type`<br>`features/admin/deal-management/ActionTypeManager.test.tsx > can delete a default type once no action uses it` |
| CL-087 | 화면: Vendor 탭은 안내·이름순 단일 표·사용 Deal 수를 보이고 Solution 컨트롤이 없으며 빈 시스템을 안내한다 | CL-R21, CL-R17, CL-UC1 | frontend | `features/admin/deal-management/VendorManager.test.tsx > explains the naming and deletion rules without mentioning solutions`<br>`features/admin/deal-management/VendorManager.test.tsx > lists vendors in a single table in name order with the number of deals using each`<br>`features/admin/deal-management/VendorManager.test.tsx > has no solution controls at all`<br>`features/admin/deal-management/VendorManager.test.tsx > says so on a system without any vendor` |
| CL-088 | 화면: Vendor를 추가하면 사용 0으로 나타나고 입력이 비며 이름 수정이 된다 | CL-R21, CL-R22, CL-UC3, CL-UC4 | frontend | `features/admin/deal-management/VendorManager.test.tsx > adds a vendor, shows it with zero deals and clears the input`<br>`features/admin/deal-management/VendorManager.test.tsx > renames a vendor in place, including one that deals use`<br>`features/admin/deal-management/VendorManager.test.tsx > shows the server message for the vendor name "%s"` |
| CL-089 | 화면: Vendor 삭제는 확인 뒤에만 하고 사용 중이면 서버 문구를 보이고 남는다 | CL-R22, CL-UC5 | frontend | `features/admin/deal-management/VendorManager.test.tsx > confirms with a plain message that does not mention solutions`<br>`features/admin/deal-management/VendorManager.test.tsx > deletes an unused vendor after confirmation`<br>`features/admin/deal-management/VendorManager.test.tsx > keeps the vendor when the confirmation is declined`<br>`features/admin/deal-management/VendorManager.test.tsx > shows the server message in the error banner when a deal uses the vendor and keeps it` |
| CL-090 | 화면: sales는 Label·유형을 만들 수 있지만 이름 변경·삭제는 403이고 관리 화면은 admin만 연다 | CL-R6, CL-R8, CL-R10 | frontend | `features/admin/deal-management/ActionTypeManager.test.tsx > lets only the admin reach the admin page, so sales cannot rename or delete (403 at the gateway)`<br>`features/admin/deal-management/LabelManager.test.tsx > lets sales create a label through the gateway but not rename or remove it`<br>`test/fake/gateway/actionTypes.test.ts > sales creates a trimmed type with the creator, the user role is refused`<br>`test/fake/gateway/actionTypes.test.ts > only the admin renames or deletes, including a default type`<br>`test/fake/gateway/master.test.ts > T-LABEL-04 sales·user의 rename/remove는 403, user의 create도 403` |
| CL-091 | 게이트웨이: 세 목록의 조회·등록·이름 변경·삭제를 계약대로 보내고 사용 중 거절을 conflict로 던진다 | CL-R24 | frontend | `gateway/http/actionTypes.test.ts > list reads GET /action-types and maps default and custom types in the server order`<br>`gateway/http/actionTypes.test.ts > create posts only the name`<br>`gateway/http/actionTypes.test.ts > create failure %i "%s" keeps the server message`<br>`gateway/http/actionTypes.test.ts > rename patches the name of that type`<br>`gateway/http/actionTypes.test.ts > remove deletes and accepts 204`<br>`gateway/http/actionTypes.test.ts > remove maps the in-use refusal to a conflict with the count`<br>`gateway/http/labels.test.ts > list reads GET /bant-labels and maps default and custom labels`<br>`gateway/http/labels.test.ts > create posts the category and the name`<br>`gateway/http/labels.test.ts > create failure %i "%s" keeps the server message`<br>`gateway/http/labels.test.ts > rename patches the name`<br>`gateway/http/labels.test.ts > remove deletes and accepts 204`<br>`gateway/http/labels.test.ts > remove maps the in-use refusal to a conflict`<br>`gateway/http/vendors.test.ts > list reads GET /vendors and maps the vendors without solutions`<br>`gateway/http/vendors.test.ts > create posts the name`<br>`gateway/http/vendors.test.ts > rename patches the name of the vendor`<br>`gateway/http/vendors.test.ts > remove deletes and accepts 204`<br>`gateway/http/vendors.test.ts > has no solution management calls`<br>`gateway/http/vendors.test.ts > failure %i "%s" keeps the server message` |
| CL-092 | 게이트웨이: 응답을 화면 값으로 바꾼다(만든 사람·사용 수·시각) | CL-R24 | frontend | `gateway/http/actionTypes.test.ts > list reads GET /action-types and maps default and custom types in the server order`<br>`gateway/http/labels.test.ts > list reads GET /bant-labels and maps default and custom labels`<br>`gateway/http/mappers/actionType.test.ts > maps a default type (no creator) with its usage count and both times`<br>`gateway/http/mappers/actionType.test.ts > maps the creator of a custom type to a user reference`<br>`gateway/http/mappers/label.test.ts > maps the creator and drops updated_at`<br>`gateway/http/mappers/vendor.test.ts > maps the usage count and drops the timestamps`<br>`gateway/http/mappers/vendor.test.ts > has no solution list`<br>`gateway/http/vendors.test.ts > list reads GET /vendors and maps the vendors without solutions` |
| CL-093 | 화면: 등록·이름 변경·삭제 성공 뒤 목록과 이름을 보여 주는 조회를 다시 읽게 한다 | CL-R23 | frontend | `data/catalogs.test.tsx > Label 등록 성공 뒤 Label 목록이 무효화되고 Deal 조회는 그대로다`<br>`data/catalogs.test.tsx > Label 이름 변경 성공 뒤 Label 목록과 Deal 조회가 무효화된다`<br>`data/catalogs.test.tsx > Label 삭제 성공 뒤 Label 목록이 무효화된다`<br>`data/catalogs.test.tsx > 유형 등록 성공 뒤 유형 목록이 무효화되고 Action 조회는 그대로다`<br>`data/catalogs.test.tsx > 유형 이름 변경 성공 뒤 유형 목록과 Action 조회가 무효화된다`<br>`data/catalogs.test.tsx > 유형 삭제 성공 뒤 유형 목록이 무효화된다`<br>`data/catalogs.test.tsx > Vendor 등록 성공 뒤 Vendor 목록이 무효화되고 Deal 조회는 그대로다`<br>`data/catalogs.test.tsx > Vendor 이름 변경 성공 뒤 Vendor 목록과 Deal 조회가 무효화된다`<br>`data/catalogs.test.tsx > Vendor 삭제 성공 뒤 Vendor 목록이 무효화된다`<br>`features/deals/detail/ActionForm.type.test.tsx > offers a type created after the page was opened`<br>`features/deals/detail/ActionForm.type.test.tsx > shows the renamed type in the table and the search after loading again` |

### CL-001 모든 역할이 Label 목록을 보면 기본 23개가 구분·시드 순서로 문서의 필드와 함께 나온다
- Given 기본 시드 상태
- When admin·sales·user가 각각 `GET /bant-labels`
- Then 200이고 구분 순서 Budget(7)→Authority(6)→Need(5)→Timeline(5)로 SC 2.2의 이름이 시드 순서대로 나온다. 모든 항목의 키는 정확히 CL-R5이고 `is_default` true, `created_by` null, `usage_count` 0이다

### CL-002 직접 만든 Label은 그 구분의 기본 Label 뒤에 소문자 이름 코드 포인트 순으로 나온다
- Given need 구분에 "나중에", "Zeta", "alpha"를 이 순서로 만들었다
- When `GET /bant-labels`
- Then need 구분은 기본 5개 뒤에 "alpha", "Zeta", "나중에" 순이다

### CL-003 Label의 사용 수는 그 Label을 선택한 Deal 수이고 안 쓰면 0이다
- Given budget "풀 예산 확보"를 Deal 2건이, need "CISO 지시"를 Deal 1건이 선택했고 BANT가 없는 Deal도 1건 있다
- When 목록을 읽는다
- Then "풀 예산 확보" 2, "CISO 지시" 1, 나머지 Label은 0이다

### CL-004 sales·admin이 Label을 만들면 201·Location이고 이름은 정규화되며 만든 사람이 기록된다
- Given KIM(sales)으로 로그인(admin으로도 같은 결과)
- When `POST /bant-labels` `{"category": "need", "name": "  규제 대응  "}`
- Then 201, `Location: /api/v1/bant-labels/<새 id>`, 본문 `category` "need", `name` "규제 대응", `is_default` false, `usage_count` 0, `created_by.id` = KIM, `created_at` = `updated_at` = 서버 시각이다

### CL-005 user가 Label을 만들면 읽기 전용 403이고 저장되지 않는다
- Given VIEWER로 로그인
- When `POST /bant-labels` `{"category": "need", "name": "규제 대응"}`
- Then 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 Label은 23개 그대로다

### CL-006 같은 구분에 대소문자·공백만 다른 Label 이름은 409다
- When authority에 "CEO 보고 완료", "ceo 보고 완료", " Ceo 보고 완료 "로 각각 만든다
- Then 모두 409 `already-exists` "같은 구분에 이미 있는 Label 이름입니다."이고 Label은 23개 그대로다

### CL-007 다른 구분에 있는 이름으로는 Label을 만들 수 있다
- Given "모름"은 authority·need에만 있다
- When budget에 "모름"을 만든다
- Then 201이고 budget 목록은 기본 7개 뒤에 "모름"이 있다

### CL-008 비었거나 공백뿐인 Label 이름은 422이고 저장되지 않는다
- When need에 이름 ""와 "   "로 각각 만든다
- Then 모두 422 `invalid-value` "Label 이름을 입력하세요."이고 Label은 23개 그대로다

### CL-009 Label 이름은 50자(코드 포인트)까지 되고 51자는 422다
- When need에 "😀"×50으로 만들고, 다시 "😀"×51로 만든다
- Then 첫 요청은 201이고 이름이 그대로 저장된다. 둘째는 422 `invalid-value` "Label 이름은 50자 이내로 입력하세요."이고 저장되지 않는다

### CL-010 NUL 문자가 든 Label 이름은 등록·이름 변경 모두 422이고 바뀌지 않는다
- Given budget 첫 기본 Label "단독 예산 확보"
- When "a\x00b", "\x00", "name\x00"으로 need에 만들고, 같은 값으로 "단독 예산 확보"의 이름을 바꾼다
- Then 모두 422 `invalid-value` "Label 이름에는 NUL 문자를 쓸 수 없습니다"이고 Label은 23개, budget 이름은 그대로다

### CL-011 모르는 구분·이름 누락·모르는 필드로 Label을 만들면 422 request-validation이다
- When `{"category": "money", "name": "x"}`, `{"category": "need"}`, `{"category": "need", "name": "x", "score": 1}`로 각각 만든다
- Then 모두 422 `request-validation`이고 Label은 23개 그대로다

### CL-012 admin이 기본 Label 이름을 바꾸면 같은 id·구분·기본 표시·자리가 유지된다
- Given ROOT로 로그인, budget "예산 없음"의 id
- When `PATCH /bant-labels/<id>` `{"name": "  예산 미확보  "}`
- Then 200, 본문 `id` 같음, `category` "budget", `name` "예산 미확보", `is_default` true, `updated_at` = 서버 시각이다. budget 목록은 "예산 없음" 자리에 "예산 미확보"가 있다

### CL-013 다른 사람이 만든 Label 이름을 바꿔도 만든 사람은 그대로이고 응답에 사용 수가 있다
- Given KIM이 need "규제 대응"을 만들었고 Deal 1건이 그것을 선택했다
- When ROOT가 "컴플라이언스 대응"으로 바꾼다
- Then 200, `name` "컴플라이언스 대응", `is_default` false, `created_by`는 KIM 그대로, `usage_count` 1이다

### CL-014 Label 자기 이름의 대소문자만 바꾸는 것은 허용된다
- When authority "CEO 보고 완료"를 "ceo 보고 완료"로 바꾼다
- Then 200이고 이름은 "ceo 보고 완료"다

### CL-015 같은 구분 다른 Label의 이름으로 바꾸면 409이고 이름은 그대로다
- When authority "CISO 보고 완료"를 "ceo 보고 완료"로 바꾼다
- Then 409 `already-exists` "같은 구분에 이미 있는 Label 이름입니다."이고 "CISO 보고 완료"가 그대로 있다

### CL-016 다른 구분에만 있는 이름으로는 Label 이름을 바꿀 수 있다
- When budget "미확인"을 "모름"(authority·need에만 있음)으로 바꾼다
- Then 200, `category` "budget", `name` "모름"이다

### CL-017 잘못된 이름으로 Label 이름을 바꾸면 422이고 없는 id여도 이름 오류가 먼저다
- When budget "예산 없음"을 "   "와 "가"×51로 각각 바꾸고, 없는 id를 "   "로 바꾼다
- Then 각각 422 "Label 이름을 입력하세요.", 422 "Label 이름은 50자 이내로 입력하세요.", 422 "Label 이름을 입력하세요."(404 아님)이고 "예산 없음"은 그대로다

### CL-018 없는 Label의 이름을 바꾸면 404다
- When 없는 id 999로 `{"name": "아무거나"}`를 보낸다
- Then 404 `not-found` "BANT Label을(를) 찾을 수 없습니다: 999"다

### CL-019 쓰이지 않는 Label은 기본이든 남이 만든 것이든 삭제되고 그 Label만 사라진다
- Given 기본 "예산 없음"과 KIM이 만든 need "규제 대응"은 쓰이지 않고, 다른 Label "풀 예산 확보"는 Deal이 쓴다
- When ROOT가 두 Label을 각각 `DELETE`
- Then 둘 다 204이고 목록에서 그 둘만 사라지며 "풀 예산 확보"는 남는다

### CL-020 사용 중인 Label을 지우면 409(실제 Deal 수)이고 Label과 Deal 선택이 그대로다
- Given budget "풀 예산 확보"를 Deal 2건이 선택했다
- When ROOT가 그 Label을 삭제한다
- Then 409 `invalid-state` "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"이고 Label은 남고 사용 수 2, 두 Deal의 budget 선택은 그대로다

### CL-021 사용 수 집계가 놓친 연결도 삭제를 막고 실제 건수로 409다
- Given 사용 수 집계에는 0으로 보이지만 Deal 1건이 그 Label을 가리키고 있다(Fake가 집계를 비우고 연결만 남김)
- When ROOT가 그 Label을 삭제한다
- Then 409 `invalid-state` "사용 중인 Label은 삭제할 수 없습니다. (Deal 1건)"이고 Label은 남는다

### CL-022 Label을 선택한 Deal이 모두 지워지면 Label을 삭제할 수 있다
- Given budget "풀 예산 확보"를 선택한 Deal 1건이 있었고 그 Deal을 삭제했다
- When ROOT가 그 Label을 삭제한다
- Then 204이고 목록에서 사라진다

### CL-023 없는 Label을 삭제하면 404다
- When ROOT가 없는 id 999를 삭제한다
- Then 404 `not-found` "BANT Label을(를) 찾을 수 없습니다: 999"다

### CL-024 sales·user는 Label 이름 변경·삭제가 관리자 403이다(자기가 만든 Label 포함)
- Given KIM이 need "규제 대응"을 만들었다
- When KIM과 VIEWER가 기본 "예산 없음"과 "규제 대응"의 이름 변경·삭제를 각각 요청한다
- Then 모두 403 `forbidden` "관리자 권한이 필요합니다"이고 두 Label은 그대로다

### CL-025 모든 역할이 유형 목록을 보면 기본 8개가 시드 순서로 만든 사람 없이 나온다
- When admin·sales·user가 각각 `GET /action-types`
- Then 200이고 "통화, 미팅, 이메일, 데모, 제안, 협상, 계약, 기타" 순 8개, 키는 정확히 CL-R5, id는 JSON 정수, `is_default` true, `created_by` null이다

### CL-026 직접 만든 유형은 기본 유형 뒤에 소문자 이름 코드 포인트 순·id 순으로 나온다
- Given "나중에", "가장 먼저", "Zeta", "alpha"를 이 순서로 만들었다
- When 목록을 읽는다
- Then 기본 8개 뒤에 "alpha", "Zeta", "가장 먼저", "나중에" 순이다

### CL-027 유형의 사용 수는 그 유형을 쓰는 Action 수다
- Given "미팅" Action 2건, "데모" Action 1건
- When 목록을 읽는다
- Then "미팅" 2, "데모" 1, "통화" 0이다

### CL-028 sales·admin이 유형을 만들면 201·Location이고 정규화된 이름·만든 사람으로 목록 끝에 나온다
- Given KIM(sales)으로 로그인(admin으로도 같은 결과)
- When `POST /action-types` `{"name": "  웨비나  "}`
- Then 201, `Location: /api/v1/action-types/<새 id>`, `name` "웨비나", `is_default` false, `usage_count` 0, `created_by.id` = KIM이고 목록은 기본 8개 뒤에 "웨비나"다. 커밋은 한 번이다

### CL-029 user가 유형을 만들면 읽기 전용 403이고 저장되지 않는다
- When VIEWER가 "웨비나"를 만든다
- Then 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 유형은 8개다

### CL-030 기존·기본 유형과 대소문자·공백만 다른 이름은 409다
- Given "Demo"를 만들었다
- When "demo", " DEMO ", "미팅", " 미팅 "으로 각각 만든다
- Then 모두 409 `already-exists` "이미 있는 유형 이름입니다."이고 유형은 9개 그대로다

### CL-031 유형 이름은 공백뿐이면 필수 문구, 51자면 길이 문구로 422이고 50자는 된다
- When "", "   ", "가"×51, "가"×50으로 각각 만든다
- Then 앞 둘은 422 `invalid-value` "유형을 입력하세요.", "가"×51은 422 "유형은 50자 이내로 입력하세요."이고 저장되지 않는다. "가"×50은 201이다. 앞뒤 공백을 지운 뒤 길이를 세며, 공백뿐인 긴 값도 필수 문구가 먼저다

### CL-032 NUL 문자가 든 유형 이름은 422이고 저장되지 않는다
- When "웨\x00비나"와 " \x00 "으로 각각 만든다
- Then 모두 422 `invalid-value` "유형에는 NUL 문자를 쓸 수 없습니다"이고 유형은 8개다

### CL-033 이름 누락·모르는 필드로 유형을 만들면 422 request-validation이다
- When `{}`, `{"name": 1}`, `{"name": "x", "order": 1}`로 각각 만든다
- Then 모두 422 `request-validation`이고 유형은 8개다

### CL-034 admin이 기본 유형 이름을 바꾸면 자리·기본 표시가 유지되고 사용 수가 함께 온다
- Given "미팅" Action 2건
- When ROOT가 "미팅"을 "  회의  "로 바꾼다
- Then 200, `id` 같음, `name` "회의", `is_default` true, `usage_count` 2, `updated_at` = 서버 시각이고 목록은 "통화, 회의, 이메일, …" 순이다. 커밋은 한 번이다

### CL-035 유형 자기 이름의 대소문자만 바꾸는 것은 허용된다
- Given "Webinar"를 만들었다
- When "WEBINAR"로 바꾼다
- Then 200, 이름 "WEBINAR"다

### CL-036 다른 유형의 이름으로 바꾸면 409이고 이름은 그대로다
- Given "Webinar"를 만들었다
- When "데모"를 "webinar"로 바꾼다
- Then 409 `already-exists` "이미 있는 유형 이름입니다."이고 "데모"는 그대로다

### CL-037 공백뿐이거나 51자인 새 유형 이름은 422이고 이름은 그대로다
- When "데모"를 "   "와 "가"×51로 각각 바꾼다
- Then 각각 422 "유형을 입력하세요.", 422 "유형은 50자 이내로 입력하세요."이고 목록은 기본 8개 그대로다

### CL-038 없는 유형의 이름 변경·삭제는 404다
- When ROOT가 없는 id 999의 이름을 "무엇"으로 바꾸고, 999를 삭제한다
- Then 둘 다 404 `not-found` "Action 유형을(를) 찾을 수 없습니다: 999"다

### CL-039 유형 이름을 바꾸면 Action 응답은 새 이름이고 이미 남은 History는 그대로다
- Given "미팅" 유형으로 등록한 Action과 그 등록 History("등록: 미팅 · …")가 있다
- When ROOT가 "미팅"을 "회의"로 바꾼다
- Then 그 Action 응답의 `action_type`은 같은 id에 `name` "회의"이고 History 문구는 "등록: 미팅 · …" 그대로다

### CL-040 쓰이지 않는 유형은 기본 유형이어도 삭제되고 그 유형만 사라진다
- Given "데모"는 쓰이지 않고 "미팅"은 Action이 쓴다
- When ROOT가 "데모"를 삭제한다
- Then 204이고 목록은 "데모"만 빠진 7개다

### CL-041 사용 중인 유형을 지우면 409(실제 Action 수)이고 유형은 남는다
- Given "미팅" Action 2건
- When ROOT가 "미팅"을 삭제한다
- Then 409 `invalid-state` "사용 중인 유형은 삭제할 수 없습니다. (Action 2건)"이고 "미팅"은 사용 수 2로 남는다

### CL-042 유형을 쓰던 Action이 모두 지워지면 유형을 삭제할 수 있다
- Given "미팅" Action 1건이 있었고 그 Action을 삭제했다
- When ROOT가 "미팅"을 삭제한다
- Then 204다

### CL-043 지운 유형의 이름은 다시 만들 수 있다
- Given "웨비나"를 만들고 삭제했다
- When "웨비나"를 다시 만든다
- Then 201이고 예전과 다른 id다

### CL-044 sales·user는 유형 이름 변경·삭제가 관리자 403이고 권한 판정이 id 조회보다 먼저다
- When KIM과 VIEWER가 "데모"의 이름을 "시연"으로 바꾸고 "데모"를 삭제하며, 없는 id 999에도 같은 요청을 한다
- Then 모두 403 `forbidden` "관리자 권한이 필요합니다"(없는 id도 404가 아님)이고 목록은 기본 8개 그대로다

### CL-045 모든 역할이 Vendor 목록을 보면 소문자 이름순으로 문서의 필드만 나오고 빈 시스템은 빈 배열이다
- Given Vendor가 없는 상태에서 목록을 한 번 읽고, 그 뒤 "zeta", "Oracle", "Sap Korea"를 만들었다
- When admin·sales·user가 각각 `GET /vendors`
- Then 처음은 `[]`이고, 뒤에는 200 "Oracle", "Sap Korea", "zeta" 순이며 각 항목 키는 정확히 `id`·`name`·`usage_count`·`created_at`·`updated_at`(`solutions` 없음), id는 JSON 정수다

### CL-046 Vendor 사용 수는 그 Vendor를 고른 Deal 수이고 Product 텍스트만 같은 Deal은 세지 않는다
- Given Vendor "SAP"를 고른 Deal 2건, Vendor "Oracle"을 고르고 Product "SAP"을 쓴 Deal 1건, "Oracle"을 고른 다른 Deal 1건
- When 목록을 읽는다
- Then "SAP" 2, "Oracle" 2다

### CL-047 admin이 Vendor를 만들면 201·Location·사용 0이고 나중 Vendor의 id가 더 크다
- Given ROOT로 로그인
- When `POST /vendors` `{"name": "  SAP  "}`, 이어서 `{"name": "Oracle"}`
- Then 둘 다 201, `Location: /api/v1/vendors/<id>`, 첫 본문은 `name` "SAP", `usage_count` 0, 키는 CL-R5이고 1 ≤ SAP id < Oracle id다

### CL-048 sales·user는 Vendor 등록·이름 변경·삭제가 관리자 403이고 그대로다
- Given Vendor "SAP"
- When KIM과 VIEWER가 "X" 등록, "SAP" 이름 변경, "SAP" 삭제를 각각 요청한다
- Then 모두 403 `forbidden` "관리자 권한이 필요합니다"이고 목록은 "SAP" 하나다

### CL-049 대소문자만 다른 Vendor 이름은 409다
- Given Vendor "SAP"
- When "sap"으로 만든다
- Then 409 `already-exists` "이미 있는 Vendor 이름입니다."이고 목록은 "SAP" 하나다

### CL-050 Vendor 이름은 공백뿐이면 422, 100자(코드 포인트, 공백 제거 뒤)는 되고 101자는 422다
- When "   ", "a"×101, "a"×100, "  " + "a"×100 + "  "으로 각각 만든다
- Then "   "은 422 `invalid-value` "Vendor 이름을 입력하세요.", "a"×101은 422 "Vendor 이름은 100자 이내로 입력하세요."이고 저장되지 않는다. "a"×100은 201이고, 공백을 둘러싼 100자는 중복이라 409다

### CL-051 NUL 문자가 든 Vendor 이름은 422다
- When "a\x00b"로 만든다
- Then 422 `invalid-value` "Vendor 이름에는 NUL 문자를 쓸 수 없습니다"이고 목록은 비어 있다

### CL-052 이름 누락·모르는 필드로 Vendor를 만들면 422 request-validation이다
- When `{}`, `{"name": "SAP", "solutions": []}`로 각각 만든다
- Then 모두 422 `request-validation`이고 목록은 비어 있다

### CL-053 admin이 Vendor 이름을 바꾸면 200과 사용 수가 오고 목록 순서가 새 이름을 따른다
- Given "zeta", "Oracle", "sap"이 있고 "sap"을 Deal 1건이 쓴다
- When ROOT가 "sap"을 "Sap Korea"로 바꾼다
- Then 200, 키는 CL-R5, `name` "Sap Korea", `usage_count` 1, `id` 같음, `updated_at` = 서버 시각이고 목록은 "Oracle", "Sap Korea", "zeta" 순이다

### CL-054 Vendor 자기 이름의 대소문자만 바꾸는 것은 허용된다
- Given Vendor "Sap"
- When "SAP"으로 바꾼다
- Then 200이고 목록은 "SAP" 하나다

### CL-055 다른 Vendor의 이름으로 바꾸면 409이고 이름은 그대로다
- Given "SAP", "Oracle"
- When "SAP"을 "ORACLE"로 바꾼다
- Then 409 `already-exists` "이미 있는 Vendor 이름입니다."이고 목록은 "Oracle", "SAP" 그대로다

### CL-056 공백뿐인 새 Vendor 이름은 422다
- Given "SAP"
- When "SAP"을 "   "으로 바꾼다
- Then 422 `invalid-value` "Vendor 이름을 입력하세요."이고 이름은 "SAP" 그대로다

### CL-057 없는 Vendor의 이름 변경·삭제는 404다
- When ROOT가 없는 id 999의 이름을 "X"로 바꾸고, 999를 삭제한다
- Then 둘 다 404 `not-found` "Vendor을(를) 찾을 수 없습니다: 999"다

### CL-058 Vendor 이름을 바꾸면 그 Vendor를 쓰는 모든 Deal 응답에 새 이름이 나오고 History는 그대로다
- Given Deal A는 수정으로 Vendor "SAP"를 골라 History("Vendor: 선택 안 함 → SAP")가 있고, Deal B는 등록 때 "SAP"를 골랐다
- When ROOT가 "SAP"을 "SAP Korea"로 바꾼다
- Then 응답 `usage_count` 2이고, Deal 목록·A·B 상세의 `vendor`는 `{id: SAP id, name: "SAP Korea"}`이며 A의 History는 "선택 안 함 → SAP" 그대로다

### CL-059 쓰이지 않는 Vendor는 삭제되고 다른 Vendor의 사용은 영향이 없다
- Given "SAP"은 쓰이지 않고 "Oracle"은 Deal 3건이 쓴다
- When ROOT가 "SAP"을 삭제한다
- Then 204이고 목록은 "Oracle"만 남는다

### CL-060 사용 중인 Vendor를 지우면 409(실제 Deal 수)이고 Vendor는 남는다
- Given "SAP"을 Deal 2건이 쓴다
- When ROOT가 "SAP"을 삭제한다
- Then 409 `invalid-state` "사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)"이고 "SAP"은 사용 수 2로 남는다

### CL-061 Vendor를 쓰던 Deal이 지워지면 Vendor를 삭제할 수 있다
- Given "SAP"을 쓰던 Deal 1건을 삭제했다
- When ROOT가 "SAP"을 삭제한다
- Then 204다

### CL-062 Solution 관리 경로는 404이고 계약·응답·도메인에 Solution 관리가 없다
- Given Vendor "SAP"
- When ROOT가 `POST /vendors/<id>/solutions`, `PATCH /vendors/<id>/solutions/1`, `DELETE /vendors/<id>/solutions/1`을 부르고 OpenAPI 계약을 읽는다
- Then 세 요청은 모두 404이고 "SAP"은 그대로다. 계약의 Vendor 경로는 `/vendors`(GET·POST)와 `/vendors/{vendor_id}`(PATCH·DELETE)뿐이고 Solution 경로·스키마와 `VendorResponse.solutions`가 없다. Vendor 엔티티·유스케이스에 Solution 멤버·유스케이스·오류 형식이 없다

### CL-063 선택이 id·name 중 정확히 하나가 아니거나 객체가 아니면 422 request-validation이다
- Given KIM으로 로그인, Deal 하나
- When Deal 등록과 Deal 수정의 `bant.budget`, Action 등록의 `action_type`에 `{}`, `{"id": 999, "name": "x"}`, `"풀 예산 확보"`(문자열), `3`(정수 그대로), `{"id": 1, "extra": 1}`, `{"name": 1}`을 각각 보낸다
- Then 모두 422 `request-validation`이고 Deal·Action·Label·유형은 바뀌지 않는다

### CL-064 선택 id는 범위 안 JSON 정수만 받는다
- When `action_type`에 `{"id": "7"}`, `{"id": true}`, `{"id": 7.0}`, `{"id": 0}`, `{"id": 2^53}`과 `{"id": 2^53−1}`을 보낸다
- Then 앞 다섯은 422 `request-validation`이고, `{"id": 2^53−1}`은 형식 검사를 통과해 유스케이스에 이른다(없는 유형이면 CL-067)

### CL-065 빈 문자열 name도 이름으로 받아 이름 규칙이 판정한다
- When `action_type` `{"name": ""}`, `bant.need` `{"name": ""}`를 보낸다
- Then 형식 오류가 아니라 각각 422 `invalid-value` "유형을 입력하세요.", "Label 이름을 입력하세요."다

### CL-066 있는 유형 id를 고르면 그 유형이 쓰이고 새 유형은 없다
- Given "데모"의 id
- When Action을 `action_type` `{"id": <데모 id>}`로 등록한다
- Then Action의 `action_type`은 `{id: <데모 id>, name: "데모"}`이고 유형은 8개다

### CL-067 없는 유형 id를 고르면 422 "선택한 유형이 없습니다…"다
- When Action을 `action_type` `{"id": 999}`로 등록(또는 수정)한다
- Then 422 `invalid-value` "선택한 유형이 없습니다. 목록에서 다시 선택하세요."이고 유형은 8개다

### CL-068 기존·기본 유형과 대소문자·공백만 다른 이름은 그 유형(저장된 철자)을 쓴다
- Given "Demo2"를 만들었다
- When Action을 `{"name": " demo2 "}`로, 또 다른 Action을 `{"name": "  미팅 "}`으로 등록한다
- Then 각각 `{id: Demo2 id, name: "Demo2"}`, `{id: 미팅 id, name: "미팅"}`이고 새 유형은 생기지 않는다(9개). "미" 같은 부분 일치는 같은 유형이 아니다

### CL-069 없는 유형 이름이면 요청자가 만든 새 유형이 생기고 다음 선택에서 재사용된다
- Given KIM으로 로그인
- When Action을 `{"name": "  웨비나  "}`로 등록하고, 이어서 `{"name": "웨비나"}`로 하나 더 등록한다
- Then 첫 등록에서 정수 id의 새 유형 "웨비나"(`is_default` false, `created_by` = KIM)가 목록 끝에 생기고 Action이 그 id를 가리킨다. 둘째 등록은 같은 id를 쓰며 유형은 9개, "웨비나" 사용 수는 2다. 두 새 이름을 차례로 만들면 나중 것의 id가 더 크다

### CL-070 이름으로 고른 유형도 유형 이름 규칙(공백·51자·NUL 422, 50자 허용)을 따른다
- When Action을 `{"name": "   "}`, `{"name": "가"×51}`, `{"name": "웨\x00비나"}`, `{"name": "가"×50}`으로 각각 등록한다
- Then 앞 셋은 422 `invalid-value`("유형을 입력하세요.", "유형은 50자 이내로 입력하세요.", "유형에는 NUL 문자를 쓸 수 없습니다")이고 새 유형이 없다. 50자는 성공한다

### CL-071 그 구분의 Label id를 고르면 그 Label이 쓰인다
- Given budget "풀 예산 확보"의 id
- When Deal을 `bant.budget` `{"id": <그 id>}`로 등록한다
- Then Deal의 budget 선택이 그 id이고 Label은 23개다

### CL-072 다른 구분의 Label id나 없는 id를 고르면 422 "BANT Label이 올바르지 않습니다."다
- Given need "모름"의 id
- When Deal을 `bant.budget`(또는 `authority`) `{"id": <need 모름 id>}`로, 또 `{"id": 999}`로 등록한다
- Then 모두 422 `invalid-value` "BANT Label이 올바르지 않습니다."이고 새 Label도 Deal도 없다

### CL-073 같은 구분 Label과 대소문자만 다른 이름은 그 Label을 쓴다
- When Deal을 `bant.authority` `{"name": "ceo 보고 완료"}`로 등록한다
- Then authority 선택은 기본 "CEO 보고 완료"의 id이고 Label은 23개다

### CL-074 같은 구분에 없는 이름은 그 구분에 요청자가 만든 새 Label이 되고 다른 구분의 같은 이름은 쓰지 않는다
- Given KIM으로 로그인
- When Deal을 `bant` `{"authority": {"name": "  신규 결재선  "}, "budget": {"name": "모름"}, "need": {"name": "신규 필요"}}`로 등록하고, 다음 Deal을 `bant.authority` `{"name": "신규 결재선"}`으로 등록한다
- Then authority "신규 결재선", budget "모름"(authority·need의 "모름"과 다른 새 Label), need "신규 필요"가 구분마다 하나씩 새로 생기고(`is_default` false, `created_by` = KIM, 정수 id) Deal이 그 id들을 가리킨다. 다음 Deal은 같은 "신규 결재선" id를 쓰고 Label은 26개다

### CL-075 이름으로 고른 BANT도 Label 이름 규칙(공백·51자·NUL 422, 50자 허용)을 따른다
- When Deal을 `bant.need` `{"name": "   "}`, `{"name": "가"×51}`, `{"name": "신\x00규"}`, `{"name": "가"×50}`으로 각각 등록한다
- Then 앞 셋은 422 `invalid-value`("Label 이름을 입력하세요.", "Label 이름은 50자 이내로 입력하세요.", "Label 이름에는 NUL 문자를 쓸 수 없습니다")이고 새 Label이 없다. 50자는 성공한다

### CL-076 화면: 입력을 null·{id}·{name}으로 바꾼다
- Given 선택지 `[{id: 1, name: "미팅"}, {id: 2, name: "Demo"}]`
- When `toChoice`에 "", "   ", "미팅", "  demo ", "DEMO", "  웨비나  ", "미"를 넣고, 빈 선택지로 "미팅"을 넣는다
- Then 각각 null, null, `{id: 1}`(JSON `{"id":1}`), `{id: 2}`, `{id: 2}`, `{name: "웨비나"}`, `{name: "미"}`, `{name: "미팅"}`이다

### CL-077 화면: BANT Label·Action 유형·Vendor 탭이 ?tab= 주소로 열리고 누르면 주소가 바뀐다
- Given admin으로 로그인
- When `/admin/deal?tab=action-type`, `?tab=vendor`, `?tab=label`로 각각 열고, 기본 탭에서 "Action 유형"·"Vendor" 탭을 누른다
- Then 각 주소에서 그 탭이 선택되어 그 화면이 보이고 "Action 유형" 탭은 "BANT Label" 탭 바로 다음이다. 탭을 누르면 그 화면이 열리고 주소가 `?tab=action-type`·`?tab=vendor`가 된다

### CL-078 화면: BANT 탭은 구분별 카드에 기본 배지·사용 Deal 수·만든 사람을 보인다
- Given Fake 시드(기본 Label, 일부는 Deal이 사용)와 KIM이 만든 Label 하나
- When BANT Label 탭을 연다
- Then 안내 문구(CL-R19)와 Budget·Authority·Need·Timeline 카드 4개가 있고 각 카드에 그 구분 기본 Label이 "기본" 배지와 "Deal <n>건", 만든 사람 "시스템"으로 보인다. KIM이 만든 Label은 "<KIM 이름> · <만든 시각>"이다

### CL-079 화면: BANT Label을 추가하면 그 구분에 나타나고 입력이 비며 다른 구분의 같은 이름도 된다
- When Need 카드의 "새 Label 이름"에 "규제 대응"을 넣고 "추가", Budget 카드에 "모름"을 넣고 "추가"
- Then 각 구분 표에 새 Label이 "Deal 0건"으로 나타나고 입력 칸이 비며 오류 배너가 없다

### CL-080 화면: BANT Label 추가가 거절되면 서버 문구를 배너에 보인다
- When Authority 카드에 "ceo 보고 완료", 빈 이름, 51자 이름으로 각각 추가한다
- Then 배너에 각각 "같은 구분에 이미 있는 Label 이름입니다.", "Label 이름을 입력하세요.", "Label 이름은 50자 이내로 입력하세요."가 보이고 Label은 늘지 않으며 입력은 남는다

### CL-081 화면: BANT Label 이름을 바꾸고(사용 중 포함) 중복이면 배너를 보인다
- Given Deal이 쓰는 Label
- When 그 행의 "이름 수정" → "Label 이름" 칸을 새 이름으로 바꿔 "저장"하고, 다른 행을 같은 구분의 기존 이름(대소문자만 다름)으로 저장한다
- Then 첫 행은 입력이 닫히고 새 이름이 보인다. 둘째는 배너에 "같은 구분에 이미 있는 Label 이름입니다."가 보이고 입력이 열린 채 이름은 그대로다

### CL-082 화면: BANT Label 삭제는 확인 뒤에만 하고 사용 중이면 건수 문구를 보인다
- When 쓰이지 않는 Label의 "삭제" → 대화상자 "삭제", 다른 Label의 "삭제" → "취소", Deal이 쓰는 Label의 "삭제" → "삭제"
- Then 대화상자 문구는 "'<이름>' Label을 삭제할까요? 사용 중인 Label은 삭제할 수 없습니다."이고, 첫 Label은 사라지고, 취소한 Label은 남으며(요청 없음), 사용 중 Label은 배너에 "사용 중인 Label은 삭제할 수 없습니다. (Deal <n>건)"이 보이고 남는다. 대화상자는 닫힌다

### CL-083 화면: Action 유형 탭은 안내·기본 순서·배지·사용 Action 수·만든 사람을 보인다
- Given Fake 시드와 KIM이 만든 유형 하나
- When Action 유형 탭을 연다
- Then 안내 문구(CL-R20)가 보이고 표 "Action 유형 목록"에 기본 유형이 시드 순서로 "기본" 배지·"Action <n>건"·"시스템"과 함께, KIM의 유형은 "<KIM 이름> · <만든 시각>"으로 보인다

### CL-084 화면: 유형을 추가하면 기본 뒤에 나타나고 입력이 비며 거절은 서버 문구로 보인다
- When "새 유형 이름"에 "웨비나" 추가, 이어서 "DEMO2"(기존 "Demo2"), 빈 이름, 51자 이름 추가
- Then "웨비나"는 기본 유형 뒤에 "Action 0건"으로 나타나고 입력이 빈다. 나머지는 배너에 각각 "이미 있는 유형 이름입니다.", "유형을 입력하세요.", "유형은 50자 이내로 입력하세요."가 보이고 목록은 그대로다

### CL-085 화면: 유형 이름 수정은 저장·대소문자만 변경·중복 거절·취소가 된다
- When Action이 쓰는 기본 유형 "미팅"을 "회의"로 저장, 만든 "Webinar"를 "WEBINAR"로 저장, "데모"를 "통화"로 저장, 다른 행에서 이름을 바꾼 뒤 Esc(또는 "취소")
- Then "회의"·"WEBINAR"는 저장되어 입력이 닫히고, "통화"는 배너 "이미 있는 유형 이름입니다."와 함께 그대로이며, 취소한 행은 요청 없이 원래 이름이다

### CL-086 화면: 유형 삭제는 확인 뒤에만 하고 사용 중이면 건수 문구, 쓰지 않게 되면 삭제된다
- When 쓰이지 않는 유형 "삭제" → "삭제", 다른 유형 "삭제" → "취소", Action이 쓰는 "협상" "삭제" → "삭제", 그 Action을 지운 뒤 다시 "협상" 삭제
- Then 대화상자 문구는 "'<이름>' 유형을 삭제할까요? 사용 중인 유형은 삭제할 수 없습니다."이고, 첫 유형은 사라지고, 취소한 유형은 남으며, "협상"은 처음엔 배너 "사용 중인 유형은 삭제할 수 없습니다. (Action <n>건)"과 함께 남고 Action을 지운 뒤에는 사라진다

### CL-087 화면: Vendor 탭은 안내·이름순 단일 표·사용 Deal 수를 보이고 Solution 컨트롤이 없으며 빈 시스템을 안내한다
- Given Vendor 여럿(일부는 Deal이 사용), 또 Vendor가 없는 Fake
- When Vendor 탭을 연다
- Then 안내 문구(CL-R21, Solution 언급 없음)와 표 "Vendor 목록" 하나에 Vendor가 이름순으로 "Deal <n>건"과 함께 보이고 Solution 칸·버튼이 없다. Vendor가 없으면 "등록된 Vendor가 없습니다."가 보인다

### CL-088 화면: Vendor를 추가하면 사용 0으로 나타나고 입력이 비며 이름 수정이 된다
- When "새 Vendor 이름"에 "Okta2"를 넣고 "Vendor 추가", 이어서 Deal이 쓰는 Vendor를 "이름 수정"으로 새 이름 저장
- Then 새 Vendor가 "Deal 0건"으로 이름순 자리에 나타나고 입력이 빈다. 수정한 Vendor는 같은 자리(새 이름 순)에 새 이름으로 보이고 사용 수는 그대로다

### CL-089 화면: Vendor 삭제는 확인 뒤에만 하고 사용 중이면 서버 문구를 보이고 남는다
- When 쓰이지 않는 Vendor "삭제" → "삭제", 다른 Vendor "삭제" → "취소", Deal이 쓰는 Vendor "삭제" → "삭제"
- Then 대화상자 문구는 "'<이름>' Vendor를 삭제할까요?"이고, 첫 Vendor는 사라지고, 취소한 Vendor는 남으며, 사용 중 Vendor는 배너 "사용 중인 Vendor는 삭제할 수 없습니다. (Deal <n>건)"과 함께 남는다

### CL-090 화면: sales는 Label·유형을 만들 수 있지만 이름 변경·삭제는 403이고 관리 화면은 admin만 연다
- Given sales로 로그인한 Fake 게이트웨이
- When Label·유형을 만들고, 이름 변경·삭제를 부르고, `/admin/deal?tab=action-type`을 연다
- Then 생성은 성공하고 이름 변경·삭제는 403으로 거절되며 항목은 그대로다. 화면은 Deals 목록으로 바뀐다(PL-R31)

### CL-091 게이트웨이: 세 목록의 조회·등록·이름 변경·삭제를 계약대로 보내고 사용 중 거절을 conflict로 던진다
- When HTTP 게이트웨이로 `labels`·`actionTypes`·`vendors`의 `list`·`create`·`rename`·`remove`를 부른다
- Then 요청은 `GET /api/v1/bant-labels`·`POST` `{category, name}`·`PATCH /api/v1/bant-labels/{id}` `{name}`·`DELETE`(유형은 `/action-types`, `{name}`만; Vendor는 `/vendors`, `{name}`)이고 204 삭제는 성공이다. 서버가 409 사용 중이면 kind `conflict`와 서버 문구(건수 포함)로 실패한다. Vendor 게이트웨이에 Solution 관리 함수가 없고 앱 게이트웨이는 실제 HTTP 어댑터를 쓴다

### CL-092 게이트웨이: 응답을 화면 값으로 바꾼다(만든 사람·사용 수·시각)
- When 기본 항목(`created_by` null)과 직접 만든 항목 응답을 변환한다
- Then Label은 `{id, category, name, isDefault, createdBy, createdAt, usageCount}`(`updated_at` 없음), 유형은 `createdAt`·`updatedAt`을 모두 갖고, Vendor는 `{id, name, usageCount}`(시각·`solutions` 없음)다. `created_by` null은 `createdBy` null, 있으면 UserRef(US-R31)다

### CL-093 화면: 등록·이름 변경·삭제 성공 뒤 목록과 이름을 보여 주는 조회를 다시 읽게 한다
- Given 세 탭 화면과 Label·유형·Vendor·Deal·Action 조회 캐시
- When 각 탭에서 등록, 이름 변경, 삭제가 성공한다
- Then 등록·삭제 뒤에는 그 목록만, 이름 변경 뒤에는 그 목록과 함께 Label·Vendor는 Deal 조회, 유형은 Action 조회가 다시 읽힌다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 초안: 구현된 동작을 문서화(CL-R1~R24, CL-UC1~UC6, CL-001~CL-093) | CL-001~CL-093 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): Deal Vendor 필수(DE-R7)로 CL-046 Given을 바꿈. 사용 수 규칙·Vendor 삭제 거부(사용 중 409)는 그대로 | 변경 CL-046 |
| 2026-11-16 | 초안(사용자 확인 대기): Deal Solution → Product 이름 변경(DE)에 따라 용어·CL-R4 표기, CL-R17에 폐지된 "Solution 관리"와 Deal Product 구분 문장. 동작 그대로 | 변경(표기): CL-046 |
