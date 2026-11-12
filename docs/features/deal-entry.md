# Deal 등록·수정   (feature 코드: DE, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/application/deal/{register_deal,update_deal,validation,form,inputs,contact_draft,bant_choice,code_issuer}.py`, `app/domain/deal/{values,policy,code,errors,entities}.py`, `app/domain/contact/draft.py`, `app/web/routers/deals.py`의 `POST ""`·`PATCH /{code}`, `app/web/schemas/deal.py`, `app/infra/db/models_deal.py`, `frontend/src/features/deals/form/*.tsx·formState.ts`, `shared/ui/UserSelect.tsx`, `gateway/http/deals.ts`의 `create`·`update`, `gateway/http/mappers/deal.ts`의 요청 변환, `test/fake/gateway/{dealsWrite,dealValidation}.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트가 어긋나는 점은 계획(`artifacts/10-analysis/de-plan.md`)의 확인 필요 질문으로 분리했습니다.

## 1. 개요

- 목적: 영업(sales)과 admin이 Deal을 등록하고 폼으로 수정한다. 등록 때 Deal code를 발급하고, 필드 값·Owner 자격·Vendor·Solution·BANT 선택·고객/파트너 연락처를 검증·해석해 한 트랜잭션에 저장한다.
- 사용자(역할): sales·admin(등록·수정). user는 읽기 전용이라 둘 다 할 수 없다.
- 범위
  - 화면 `/deals/new`(Deal 등록)·`/deals/:dealCode/edit`(Deal 수정) 공용 폼
  - API `POST /deals`(등록), `PATCH /deals/{code}`(폼 저장)
  - 요청 형식, 필드 값 규칙과 검증 순서, Deal code 발급, Owner 자격, Vendor 선택, Solution 텍스트, BANT 선택 저장 결과·롤백, 고객/파트너 연락처 입력(`ContactDraft`)의 해석·병합(`merge_same_person`)·파트너 링크 교체, 등록·수정의 저장 결과(이력이 남는지, 수정 시각)
- 범위 밖(다른 feature)
  - Status·Forecast 동기화 불변식과 동기화 대화상자·단일 변경 `/deals/{code}/changes`, Deal History 항목 형식(분류·대상·이전·이후 문구, 정렬·조회), Deal 상세 응답의 필드 구성(`DealDetailResponse`), 삭제 → DD
  - Won 진입 때 미발급 계약 생성, Won 이탈 확인·`delete_license_contracts`, 발급 계약이 있으면 Won 이탈 금지 → LC(LC-R6~R9)
  - `status_changed_at`(Status 진입 시각)·`status_days`·경고·최종 업데이트 → RK
  - 목록 행·목록 필터(Vendor·Solution 등) → DL
  - `{id}`/`{name}` 선택 형식과 해석 규칙(CL-R12~R16), Label 이름 규칙(CL-R1), Vendor 이름 변경의 효과(CL-R9) → CL
  - 연락처 값 규칙(CT-R2~R6), 같은 사람 판정(CT-R7), 연락처 변경 이력(CT-R10), 연락처 선택기 `ContactPicker`(CT-R22) → CT
  - Owner 후보 목록 `/user-options`(US-R20)·`UserRef`(US-R12)·퇴사 처리(US-R17) → US
  - 공통 권한 판정·CSRF·Problem 형식·id 본문 형식·NUL 공통 규칙·라우트 가드·오류 문구 표시·게이트웨이 오류 변환 → PL(PL-R6, PL-R9, PL-R13, PL-R15, PL-R16, PL-R30, PL-R37, PL-R39)
  - 업무 날짜 계산 → TM(TM-R4), 날짜 입력·금액 입력·콤보박스 컴포넌트 자체 → UI(날짜 입력 UI-R1~R11, 금액 입력 UI-R12~R16, 콤보박스 UI-R18~R21)
- 관련 화면·메뉴: Deals 목록의 "+ Deal 등록"(DL), Deal 상세의 수정 진입(DD) → `/deals/new`, `/deals/:dealCode/edit`(가드 PL-R30).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| Deal code | Deal의 업무 키 `YYYYMMDD-XXXX`(등록 업무 날짜 8자리 + `-` + 영문 대문자·숫자 4자리). API 경로와 응답의 식별자이며 바꿀 수 없다. 내부 id는 응답에 없다 |
| Owner | Deal 담당 영업. `owner_user_id`(users FK RESTRICT) |
| 폼 저장 | `PATCH /deals/{code}`. 보낸 필드만 반영하는 수정 |
| 반영 후 값 | 등록은 입력 그대로, 수정은 현재 Deal 위에 보낸 필드를 덮어쓴 값. 값 규칙은 반영 후 값으로 판정한다 |
| 보낸 필드(`provided`) | PATCH 본문에 키가 있는 필드(값이 null이어도 보낸 것). `quote`·`poc`는 하위 두 값을, `bant`는 네 구분 전체를 보낸 것으로 본다 |
| ContactDraft | Deal 폼의 고객·파트너 입력 `{contact_id?, company, name, title?, email?, phone?}`. `contact_id`가 있으면 "고른 연락처", 없으면 "직접 입력" |
| 고른 연락처 | `contact_id`로 지정한 기존 연락처. 입력값으로 통째로 갱신된다 |
| 같은 사람 | 직접 입력한 ContactDraft와 CT-R7 규칙으로 같은 것으로 판정된 기존 연락처 |
| 병합 | 같은 사람으로 판정된 연락처에 직접 입력을 합치는 규칙(DE-R13) |
| 파트너 링크 | Deal–파트너 연락처 연결. 활성(해제 시각 없음)은 Deal당 최대 1건이고 해제된 링크는 지우지 않는다 |
| 레거시 빈 Solution | Solution 필수화 전에 만들어져 `solution`이 `''`인 Deal |

### 2.2 데이터 모델

`deals`(PK `id BIGINT` identity, SC-R11)

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `deal_code` | varchar, UNIQUE, CHECK `^[0-9]{8}-[A-Z0-9]{4}$` | Deal code |
| `name` | varchar(200) | Deal Name(앞뒤 공백 제거 값) |
| `owner_user_id` | BIGINT, FK `users.id` RESTRICT, 인덱스 | Owner |
| `vendor_id` | BIGINT null, FK `vendors.id` RESTRICT, 인덱스 | Vendor(선택 안 함 = NULL) |
| `solution` | varchar(200) NOT NULL | Solution 자유 텍스트(레거시 `''` 허용) |
| `users` | integer, CHECK `users >= 0` | Users count(견적 단위 사용자 수) |
| `status_kind`·`status_key`, `forecast_kind`·`forecast_key` | 복합 FK `codes(kind, key)` RESTRICT, CHECK `(status_key = 'contract_completed') = (forecast_key = 'won')` | Status·Forecast(동기화 불변식은 DD) |
| `revenue_amount` | bigint, CHECK 1~2^53−1 | 매출금액(원) |
| `revenue_date` | date | Expected Close(Won이면 실제 매출일) |
| `customer_id` | BIGINT, FK `contacts.id` RESTRICT | 고객 연락처 |
| `quote_submitted`·`quote_submitted_date` | varchar(3) null CHECK `YES`/`NO`, date null | 견적 제출 여부·제출일(조합 검사 없음) |
| `poc_state`·`poc_completed_date` | varchar(3) null CHECK `YES`/`ING`/`NO`, date null | POC 상태·완료일(조합 검사 없음) |
| `procurement` | varchar(500), 기본 `''` | 구매절차 |
| `status_changed_at` | timestamptz | RK 소유 |
| `created_at`·`updated_at` | timestamptz | 등록·수정 시각 |

`deal_partners`: `deal_id`(FK CASCADE), `contact_id`(FK), `linked_at`, `unlinked_at`(null = 활성, CHECK `unlinked_at >= linked_at`). `deal_bant_labels`: PK (`deal_id`, `category`), `label_id`, 복합 FK (`label_id`, `category`) → `bant_labels`(구분이 맞는 Label만, CL 2.2).

- 엔티티·값: `Deal`(`create`·`revise`·`replace_partner`·`touch`·`snapshot`), `DealDetails`, `RevenueAmount`, `Quote`, `Poc`, `BantSelection`, `DealCode`(`issue`·`parse_or_none`), `PartnerLink`, `ContactDetails`, `merge_same_person`.
- 유스케이스: `RegisterDeal(uow_factory, clock, suffix_source)`, `UpdateDeal(uow_factory, clock, storage)`. 공용 단계: `validate_form` → `resolve_contacts`(계획 후 반영) → `resolve_bant` → (등록) `add_with_issued_code` / (수정) `revise`·`replace_partner`·`diff_deal`.
- Port: `DealRepository`(`get(code, for_update)`·`exists`·`add`·`update`·`get_item`), `UserRepository`(`get`·`lock_assignable`), `VendorRepository.get`, `CodeRepository.list(kind)`, `ContactRepository`(`get(for_update)`·`lock_identity`·`same_identity`·`add`·`update`), `BantLabelRepository`(`list(for_update)`·`add`), `DealCodeSuffixSource.next_suffix`, `IdAllocator`, `Clock`, `FileStorage`(수정 뒤 LC 폴더 정리).

### 2.3 비즈니스 규칙

권한
- **DE-R1** 등록 `POST /deals`과 수정 `PATCH /deals/{code}`는 sales·admin만 한다(업무 쓰기 가드 PL-R6: user는 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)", 본문 검증·대상 확인보다 먼저; 미인증 401이 그보다 먼저). 수정은 Owner와 무관하다: sales는 다른 사람이 Owner인 Deal도 수정할 수 있다(삭제 권한과 다름 — DD, 계획 Q1). user가 BANT에 새 이름을 보내도 403이라 Label이 생기지 않는다.

Deal code
- **DE-R2** 등록하면 서버가 code를 발급한다: 날짜 = 등록 요청 서버 시각의 업무 날짜(서버 OS 로컬 시간대의 달력 날짜, TM-R4 — UTC 날짜와 다를 수 있다), 끝 4자리 = `DealCodeSuffixSource`가 주는 영문 대문자·숫자 4자. 이미 있는 code면 다시 뽑는다(저장 전 확인, 저장 때의 유일성 위반도 같은 방식으로 재시도). 전체 10번까지 시도하고 10번째에 성공할 수 있다. 10번 모두 겹치면 409 `invalid-state` "Deal code를 발급하지 못했습니다. 다시 시도하세요."이고 아무것도 저장하지 않는다. 요청 본문으로 code를 정할 수 없고(모르는 필드 422) 수정으로 바꿀 수도 없다.

요청 형식
- **DE-R3** 요청 형식은 유스케이스 전에 판정하고 위반은 422 `request-validation`이다(모르는 필드는 모든 본문·하위 객체에서 거부).
  - 등록 필수 키: `name`(문자열), `owner_user_id`(JSON 정수 1~2^53−1, PL-R15), `solution`(문자열, null 불가), `users`(JSON 정수, null·문자열 불가), `status_key`·`forecast_key`(문자열), `revenue_amount`(JSON 정수), `revenue_date`(`YYYY-MM-DD` 또는 null — 키는 필수), `customer`(ContactDraft 객체). 선택 키와 기본값: `vendor_id`(정수 또는 null, 기본 null), `partner`(ContactDraft 또는 null, 기본 null), `quote`(`{submitted: "YES"|"NO"|null, submitted_date: date|null}`, 기본 둘 다 null), `poc`(`{state: "YES"|"ING"|"NO"|null, completed_date}`, 기본 둘 다 null), `procurement`(문자열, 기본 `""`), `bant`(`{budget, authority, need, timeline}` 각 `CatalogChoiceRequest` 또는 null, 빠진 구분 = null, 기본 모두 null).
  - ContactDraft: `company`·`name` 키 필수(문자열, 값 판정은 DE-R11), `contact_id`(JSON 정수 또는 null), `title`·`email`·`phone`(문자열 또는 null, 생략 = null).
  - 수정 본문: 모든 키 선택. 키의 타입은 등록과 같고 null을 허용하되 `quote`·`poc`·`bant`는 null이면 422("<이름>은 null일 수 없습니다"). `delete_license_contracts`(불리언, 기본 false)는 LC 소유이며 폼 필드가 아니다.
  - 예전 필드는 모르는 필드다: `vendor`(텍스트), `solution_id`, BANT의 Label id 값 그대로(객체가 아님, CL-R12).
  - 형식 위반 예: 금액 `"많이"`, 날짜 `"30/06/2026"`, `owner_user_id` `"x"`, `users` `"10"`·null·누락, `solution` 누락·null·숫자, 모르는 키 `extra`.

필드 값
- **DE-R4** 필드 값 규칙(위반은 모두 422 `invalid-value`, `detail` = 아래 문구, 칸 위치 `errors`는 싣지 않음). 텍스트는 NUL 문자가 있으면(공백으로 감싸도) "<칸>에는 NUL 문자를 쓸 수 없습니다"(PL-R16).

  | 필드 | 규칙 | 위반 문구 |
  | --- | --- | --- |
  | Deal Name | NUL → 앞뒤 공백 제거 → 비면 거절 → 200자(코드 포인트) 초과 거절. 저장은 제거한 값 | "Deal Name을 입력하세요." / "Deal Name은 200자 이내로 입력하세요." / NUL 칸 이름 "Deal Name" |
  | Vendor | DE-R7 | "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요." |
  | Solution | DE-R8 | "Solution을 입력하세요." / "Solution은 200자 이내로 입력하세요." / NUL 칸 이름 "Solution" |
  | Owner | DE-R6 | "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요." / "Owner는 재직 중인 영업 담당자여야 합니다." |
  | 매출금액 | 정수 1 이상 2^53−1(9,007,199,254,740,991) 이하(원) | "매출금액은 1원 이상의 정수로 입력하세요." |
  | Expected Close | null이면 거절. 과거·미래 모두 허용 | "Expected Close를 입력하세요." |
  | Users count | null이면 필수 문구, 정수 0 이상 2,147,483,647 이하 | "Users count를 입력하세요." / "Users count는 0 이상의 정수로 입력하세요." |
  | Status | `status` 종류 코드 중 그 key가 있어야 한다(빈 문자열 포함 없는 key는 거절) | "Status를 선택하세요." |
  | Forecast | `forecast` 종류 코드 중 그 key가 있어야 한다 | "Forecast를 선택하세요." |
  | Status·Forecast 조합 | 동기화 불변식(계약완료 ⇔ Won, 규칙은 DD) | "Status와 Forecast의 동기화가 맞지 않습니다." |
  | BANT | DE-R10 | CL-R1(Label 문구)·CL-R14 |
  | 구매절차 | NUL → 앞뒤 공백 제거 → 500자 초과 거절. 빈 값 허용. 저장은 제거한 값 | "구매절차는 500자 이내로 입력하세요." / NUL 칸 이름 "구매절차" |
  | 견적·POC | 여부와 날짜의 조합을 검사하지 않는다(어떤 조합도 저장) | — |
  | 고객·파트너 | DE-R11 | DE-R11 |

- **DE-R5** 검증 순서(앞에서 걸리면 뒤는 보지 않는다): ① 요청 형식(DE-R3) → (수정만) ② 없는 Deal 404(DE-R19) → ③ Deal Name → ④ Vendor → ⑤ Solution → ⑥ Owner → ⑦ 매출금액 → ⑧ Expected Close → ⑨ Users count → ⑩ Status 존재 → ⑪ Forecast 존재 → ⑫ 동기화 → ⑬ BANT 판정 → ⑭ 구매절차 → ⑮ 고객 필수(회사명 → 담당자명) → ⑯ 파트너 필수 → ⑰ 고객 연락처 형식(CT-R6 ②~⑦) → ⑱ 파트너 연락처 형식 → ⑲ 고른 연락처·같은 사람 판정(고객 → 파트너, 404·409, DE-R12) → 저장. 수정에서 ④⑤⑥⑩⑪⑫⑬⑮~⑲는 **그 필드를 보낸 경우에만** 하고, ③⑦⑧⑨⑭는 반영 후 값으로 항상 한다. 등록은 모두 한다(④는 `vendor_id`가 null이 아닐 때).

Owner
- **DE-R6** Owner는 재직 중인 sales여야 한다: 퇴사자면(역할과 무관) 퇴사 문구가 먼저, 그 밖에 없는 사용자·admin·user면 "Owner는 재직 중인 영업 담당자여야 합니다."이다. 등록은 항상, 수정은 `owner_user_id`를 보내면 **현재와 같은 값이어도** 다시 검사한다(그래서 Owner가 퇴사한 Deal은 Owner를 바꿔야 Owner를 보내는 폼 저장이 된다). 보내지 않으면 검사하지 않아 퇴사한 Owner·역할이 바뀐 Owner의 Deal도 다른 필드를 수정할 수 있고 Owner는 그대로 남는다. PATCH의 `owner_user_id: null`도 "Owner는 재직 중인 영업 담당자여야 합니다."다. admin은 다른 sales를 Owner로 지정해 등록할 수 있고 이력의 변경자는 admin이다. 판정 때 재직 Owner 행을 잠가 퇴사 처리와 직렬화한다.

Vendor·Solution
- **DE-R7** Vendor는 등록된 목록의 id(`vendor_id`)로만 고른다(이름으로 만들 수 없음, CL-R17). null = 선택 안 함이고 Vendor 없이 등록·수정할 수 있다. 보낸 id가 없으면 422 "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."이며 이 판정은 Solution 판정보다 먼저다. 응답의 `vendor`는 `{id, name}` 또는 null이다(이름은 현재 Vendor 이름, CL-R9). 수정에서 `vendor_id: null`은 Vendor를 비운다.
- **DE-R8** Solution은 Vendor와 무관한 필수 자유 텍스트다: NUL → 앞뒤 공백 제거 → 비면 "Solution을 입력하세요." → 200자(코드 포인트) 초과 "Solution은 200자 이내로 입력하세요.". 대소문자·한글은 입력 그대로 저장한다. 등록은 항상 검사한다. 수정은 보낸 경우만 검사하고 null·`""`·공백뿐이면 거절(지울 수 없음), 생략하면 그대로다. Vendor를 바꾸거나 비워도 Solution은 그대로다. 대소문자만 바꾼 값은 변경이고, 앞뒤 공백만 다른 값은 변경이 아니다.

Status·Forecast
- **DE-R9** 폼의 Status·Forecast는 코드 존재(DE-R4)와 동기화 불변식(DD)을 반영 후 값으로 지켜야 하며, 계약완료/Won으로 닫거나 되돌릴 때는 두 값을 함께 보내야 한다(한 쪽만 보내면 동기화 문구 422, 규칙과 케이스는 DD). 처음부터 계약완료/Won으로 등록할 수 있다(그때 계약 생성은 LC-R7). 수정에서 Status·Forecast를 하나도 보내지 않으면 코드·동기화를 검사하지 않는다.

BANT
- **DE-R10** BANT 저장 결과(선택 해석은 CL-R12~R15):
  - 등록은 `bant`의 구분마다 `{id}`·`{name}`·null을 섞어 보낼 수 있고 빠진 구분과 `bant` 생략은 선택 안 함이다. 응답 `bant`는 `{budget, authority, need, timeline}` 각 Label id 또는 null이다.
  - 수정에서 `bant`를 보내면 네 구분을 **통째로** 그 값으로 바꾼다(빠진 구분 = 선택 안 함). 같은 Label을 `{id}`나 대소문자만 다른 `{name}`으로 다시 보내면 그 구분은 바뀌지 않는다. 바뀐 구분만 이력이 남는다(형식 DD). `bant`를 보내지 않으면 Label을 검사·생성하지 않고 선택은 그대로다.
  - BANT 판정은 동기화 다음, 구매절차 앞이다(DE-R5 ⑬). 새 Label은 모든 검증과 연락처 판정을 통과한 뒤 같은 트랜잭션에서 만들어지므로, 등록·수정이 어디서든 실패하면 새 Label도 남지 않는다(DE-R15).

고객·파트너
- **DE-R11** ContactDraft 값 규칙: 고객은 필수다 — 회사명이 `""`이면 "고객 회사명을 입력하세요.", 담당자명이 `""`이면 "고객 담당자명을 입력하세요.". 파트너는 선택이지만 보냈다면 회사명·담당자명 중 하나라도 `""`이면 "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.". 그다음 고객, 파트너 순으로 연락처 값 규칙(CT-R2~R6의 문구·순서: 공백 문자 → 이메일 → 전화 → 회사명 → 담당자명 → 직급)을 적용한다. 직급은 앞뒤 공백을 지우고 빈 값은 없음, 빈 이메일·전화(`""`)는 없음(null)이다. 수정에서 `customer: null`을 보내면 빈 입력으로 보아 "고객 회사명을 입력하세요."다.
- **DE-R12** 연락처 해석(고객 → 파트너 순으로 모두 판정한 뒤 반영 — 판정에서 실패하면 아무 연락처도 바뀌지 않는다):
  - 고른 연락처(`contact_id`): 그 연락처가 없거나 종류가 다르면(파트너를 고객으로 고름 등) 404 `not-found` "연락처를 찾을 수 없습니다.". 입력값을 그 연락처의 새 값으로 쓴다(병합 없음 — 빈 직급·이메일·전화는 지운다). 바꾼 값이 같은 종류의 **다른** 연락처와 같은 사람(CT-R7)이면 409 `already-exists` "이미 등록된 연락처입니다.". 값이 실제로 바뀌면 연락처를 갱신하고 CT-R10대로 그 연락처를 참조하는 모든 Deal(비활성 파트너 링크 포함, 수정 중인 이 Deal 포함)에 연락처 이력을 남기고 그 Deal들의 `updated_at`을 서버 시각으로 바꾼다. 값이 같으면 아무것도 바뀌지 않는다.
  - 직접 입력(`contact_id` 없음): 같은 종류에서 같은 사람(CT-R7)을 찾으면 그 연락처를 쓰고 입력을 병합한다(DE-R13). 병합 결과가 기존 값과 다르면 위와 같이 갱신·이력을 남긴다. 같은 사람이 없으면 새 연락처를 만든다(새 id, 이력 없음). 이메일이 다르면 다른 사람이고, 고객과 파트너는 같은 회사명·담당자명이어도 별개다.
  - 등록하는 새 Deal은 아직 연락처를 참조하지 않으므로 연락처 이력을 받지 않는다(등록 이력 1건뿐).
- **DE-R13** 병합(`merge_same_person`): 회사명·담당자명은 기존 표기를 유지하고, 직급은 입력이 비어 있지 않으면 입력 값 아니면 기존 값, 이메일·전화는 입력이 null이 아니면 입력 값 아니면 기존 값이다. 즉 빈 입력은 기존 값을 지우지 않고, 기존에 없던 값은 입력으로 채운다.
- **DE-R14** 파트너 링크: 등록 때 파트너가 있으면 활성 링크 1건(`linked_at` = 서버 시각)이 생기고 없으면 링크가 없다. 수정에서 `partner`를 보내면 그 연락처로 활성 파트너를 바꾼다 — 다른 연락처면 기존 활성 링크에 `unlinked_at`(서버 시각)을 남기고(지우지 않음) 새 활성 링크를 만든다. 활성 링크는 항상 최대 1건이다. `partner: null`이면 활성 링크만 해제한다. 현재 활성 파트너와 같은 연락처면(고른 연락처의 값만 바꾼 경우 포함) 링크는 그대로다. `partner`를 보내지 않으면 그대로다. 파트너가 없던 Deal에 처음 추가할 수 있다. 바뀐 파트너·고객은 이력이 남는다(형식 DD).

원자성·결과
- **DE-R15** 등록·수정은 한 트랜잭션이다: 어떤 검증·판정·발급 실패든 Deal·연락처(새로 만들거나 고친 것)·새 BANT Label·이력·파트너 링크·계약이 하나도 저장되지 않고 커밋되지 않는다.
- **DE-R16** 등록 결과: 201, `Location: /api/v1/deals/<code>`, 본문은 Deal 상세 응답(필드 구성 DD — 내부 id 필드가 없고 `owner_user_id`·연락처 id는 JSON 정수). `created_at` = `updated_at` = 서버 시각, 등록 이력 1건(분류 created, 변경자 = 요청자, 형식 DD), Status 진입 시각 = 등록 시각(RK). Won으로 등록하면 같은 트랜잭션에서 LC-R7. 저장된 Deal은 상세·목록에 바로 나온다.
- **DE-R17** 수정 본문의 의미: 보낸 필드만 반영한다. 보낸 null의 의미 — `vendor_id` = Vendor 비움, `partner` = 활성 파트너 해제, `procurement` = 빈 값, `name` = "Deal Name을 입력하세요.", `solution` = "Solution을 입력하세요.", `users` = "Users count를 입력하세요.", `revenue_amount` = 금액 문구, `revenue_date` = "Expected Close를 입력하세요.", `status_key`·`forecast_key` = "Status를 선택하세요."·"Forecast를 선택하세요.", `owner_user_id` = "Owner는 재직 중인 영업 담당자여야 합니다.", `customer` = "고객 회사명을 입력하세요.", `quote`·`poc`·`bant` = 422 `request-validation`. `quote`·`poc`를 보내면 하위 두 값을 모두 보낸 것으로 본다(`{}` = 둘 다 비움). 빈 본문 `{}`은 아무것도 바꾸지 않는 200이다.
- **DE-R18** 수정 결과: 200과 Deal 상세 응답. 반영 전후를 비교해 바뀐 필드마다 이력이 남는다(분류·대상·문구·순서는 DD). 바뀐 것이 없고 이 Deal이 연락처 변경 이력(DE-R12)도 받지 않았으면 이력도 없고 `updated_at`도 그대로다. 그렇지 않으면 `updated_at` = 서버 시각이다. 계약완료/Won으로 닫힌 Deal도 잠기지 않고 수정된다. Won 진입·이탈의 계약 처리는 같은 트랜잭션에서 LC-R6~R9, 지운 계약 폴더는 커밋 뒤 정리(LC-R26).
- **DE-R19** 수정 대상: 경로 `{code}`가 형식에 맞지 않거나 없는 Deal이면 404 `not-found` "Deal을 찾을 수 없습니다."(둘 다 같은 문구)다. 요청 형식 422가 이보다 먼저이고, 값 규칙 422는 이보다 나중이다.
- **DE-R20** 레거시 빈 Solution Deal: Solution을 보내지 않는 수정(이름·Users count·Vendor·금액·Expected Close 등)은 성공하고 Solution은 `''` 그대로다. Solution을 보내면 DE-R8대로 검사하므로 빈 값은 거절되고 실제 값으로 채울 수 있다.

화면(frontend, `/deals/new`·`/deals/:dealCode/edit`, 가드 PL-R30)
- **DE-R21** 화면 틀: 제목 h1 "Deal 등록"(등록)·"Deal 수정"(수정). 로그인 사용자 정보를 읽는 동안, 수정은 Deal과 BANT Label 목록 조회가 끝날(성공·실패) 때까지 "불러오는 중…"을 보인다(Label 목록이 다시 조회되어도 폼을 닫지 않음). 수정할 Deal을 읽지 못하면(없는 code 등) 오류 배너(서버 문구, PL-R37)와 링크 "목록으로"(기억한 Deals 목록 주소)를 보인다.
- **DE-R22** 배치: 타일 순서 "Deal 정보" → "고객" → "파트너" → "BANT"(상세와 같은 순서). Deal 정보 칸 순서: Deal Name(넓은 칸, 필수) → (수정만) Deal code 읽기 전용 행 → Owner → Status → Forecast → 금액(단위:원)(필수, 안내 "원 단위 정수(예: 1억 원 = 100,000,000)") → Expected Close(필수, 날짜 입력, 안내 "Won이면 실제 매출일") → Vendor → Solution(필수) → Users count(필수, 안내 "견적 단위 사용자 수") → 견적(행 하나에 "견적 제출여부" 선택 "선택 안 함"/YES/NO + "견적 제출일" 날짜) → POC(행 하나에 "POC 여부" 선택 "선택 안 함"/YES/ING/NO + "POC 완료일" 날짜) → 구매절차(한 줄 입력) → "통화: KRW(고정)" 안내. 각 칸의 라벨·입력·오류 문구는 같은 행에 있다. Status·Forecast 선택지는 코드 목록 전체(기본 시드 Status 7·Forecast 6, CD)다.
- **DE-R23** 초기값: 등록은 Owner = 로그인 사용자가 sales면 자기 id, 아니면(admin) 빈 값, Status = 기회발굴(`prospecting`), Forecast = Pipeline(`pipeline`), Vendor 선택 안 함, 나머지(Solution·Users count·금액·날짜·고객·파트너·BANT·견적·POC·구매절차) 빈 값. 수정은 Deal의 모든 값(금액은 콤마 표기, 고객·활성 파트너는 고른 연락처로, BANT는 현재 Label 이름, 레거시 빈 Solution은 빈 칸)을 채운다.
- **DE-R24** Owner 선택: 후보는 "선택하세요" + 재직 sales 전체(`/user-options?role=sales`, US-R20)이고 표시는 `UserRef` 라벨(US-R12)이다. 수정 중인 Deal의 현재 Owner가 후보에 없으면(퇴사·역할 변경) 그 사람을 추가로 보이되 퇴사자는 고를 수 없게(비활성) 보인다.
- **DE-R25** Vendor·Solution 칸: Vendor는 "선택 안 함" + 등록된 Vendor 전체 선택 상자이고 폼에서 Vendor를 만들거나 Solution 목록을 고를 수 없다. Solution은 Vendor 없이도 입력할 수 있는 필수 텍스트 칸이며 Vendor를 바꿔도 입력한 Solution은 그대로다. 수정 중 Vendor 목록을 아직 받지 못했거나 받지 못하면 Vendor는 현재 이름의 읽기 전용 행으로 보이고(선택 안 함 선택지를 보이지 않음), 실패면 오류 배너를 보이며, 저장 때 원래 Vendor id를 그대로 보낸다. Solution 칸은 그동안에도 입력할 수 있다.
- **DE-R26** 저장 전 화면 검증(위반이 있으면 요청을 보내지 않고 모든 문구를 칸 아래에 한꺼번에 보이며 문서 순서상 첫 잘못된 칸으로 포커스): Deal Name 공백뿐 "Deal Name을 입력하세요." / Owner 미선택 "Owner를 선택하세요.", 현재 퇴사 Owner를 그대로 두면 퇴사 문구 / Solution 공백뿐 "Solution을 입력하세요." / Users count 비면 "Users count를 입력하세요.", 숫자만이 아니면(음수·소수 포함) "Users count는 0 이상의 정수로 입력하세요." / 고객 회사명·담당자명 빈 값 "고객 회사명을 입력하세요."·"고객 담당자명을 입력하세요.", 그 밖의 연락처 공백·형식 문구(CT-R21) / 파트너 칸에 무엇이든 입력했으면 회사명·담당자명 중 빈 것이 있을 때 "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."와 형식 문구, 아무것도 입력하지 않으면 묻지 않음 / 금액 "매출금액은 1원 이상의 정수를 입력하세요."(0·빈 값·형식), 2^53−1 초과 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요."(금액 판정·문구 정본 UI-R13·UI-R14) / Expected Close 비면 "Expected Close를 입력하세요.", 덜 쳤거나 없는 날짜면 날짜 문구(UI-R7) / 견적일·POC 완료일은 비어도 되지만 틀린 날짜면 날짜 문구 / BANT 칸의 앞뒤 공백 제거 값이 50자(코드 포인트) 초과면 그 칸에만 "Label 이름은 50자 이내로 입력하세요.". 이름·Solution·구매절차의 길이 상한, Users count 상한, 그 밖의 규칙은 서버 문구로 판정한다.
- **DE-R27** BANT 칸: 구분마다(Budget·Authority·Need·Timeline 순) 텍스트 콤보박스 하나(선택 상자·"새 Label" 버튼·이름 수정·삭제 기능 없음, 자리표시 문구 없음). 포커스하면 그 구분 Label만 후보로, 입력하면 그 구분에서 입력을 포함하는 Label만 후보로 보이며, 고르면 칸에 이름이 채워진다(Deal 관리에서 만든 Label도 후보). 입력(앞뒤 공백 제거, 대소문자 무시)이 그 구분 Label 이름과 같지 않으면 안내 "목록에 없는 Label입니다. 저장하면 새 Label로 추가됩니다."를 보인다(빈 칸·목록에 있는 이름·다른 구분에만 있는 이름은 기준이 아님 — 다른 구분 이름이면 안내가 보인다). 저장 때 칸마다 CL-R16대로 null·`{id}`·`{name}`으로 보낸다. 수정 폼은 현재 Label 이름을 채우고(못 찾거나 선택 안 함이면 빈 칸), 사용자가 건드리지 않은 칸은 원래 `{id}`(없으면 null)를 그대로 보낸다(폼을 연 뒤 Label 이름이 바뀌어도 새 Label을 만들지 않음, 늦게 도착한 Label 목록·바뀐 이름은 건드리지 않은 칸에 다시 채움). Label 목록을 읽지 못하면 BANT 칸을 비활성으로 두고 오류 배너를 보이며 저장 때 `bant`를 보내지 않아 기존 선택을 지킨다.
- **DE-R28** 고객·파트너 타일은 연락처 선택기(`ContactPicker`, CT-R22)를 쓴다. 고객 안내 "회사명을 고르거나 직접 입력한 뒤 담당자를 고르면 직급·이메일·전화가 채워집니다. 고치면 연락처 정보도 함께 갱신됩니다.". 파트너 타일: 아무것도 입력하지 않았고 제거 중도 아니면 안내 "파트너가 없으면 비워 두세요. 입력을 시작하면 회사명과 담당자명이 모두 필요합니다.", 입력이 있으면 버튼 "파트너 제거"(누르면 파트너 칸을 비움). 수정 중 활성 파트너가 있는데 다른 사람을 입력하면 "기존 활성 파트너(<회사명> <담당자명>)는 이력으로 남고 비활성이 됩니다.", 파트너 칸을 비우면 "저장하면 기존 활성 파트너(<회사명> <담당자명>)가 제거되고 이력으로 남습니다."를 보인다. 같은 연락처를 고른 경우와 `contact_id` 없이 회사명·담당자명을 대소문자 무시로 같게 입력한 경우는 교체가 아니다.
- **DE-R29** Status·Forecast 선택을 바꾸면 동기화 대화상자(규칙·문구는 DD)가 뜨고, 확정하면 함께 바뀐 값과 매출 확정값(금액·Expected Close)을 **폼에만** 반영하고 "아직 저장되지 않았다"는 동기화 안내를 보인다(닫기 가능). 대화상자를 취소하면 이전 값 그대로다. 저장할 때 다른 필드와 함께 보낸다.
- **DE-R30** 저장: 화면 검증(DE-R26) 통과 뒤 — 등록은 입력을 요청 값으로 바꿔(DE-R31) `create`, 성공하면 `/deals/<code>`로 이동하며 알림 "Deal <code>이(가) 등록되었습니다."를 넘긴다. 수정은 Won 이탈이면 저장 직전에 계약 처리 확인을 묻고(LC, 취소하면 폼 그대로) 폼 전체를 PATCH로 보내며(Label 목록 실패면 `bant` 제외, DE-R27), 성공하면 `/deals/<code>`로 이동하며 알림 "저장되었습니다."를 넘긴다(알림 표시는 DD). 저장 중에는 버튼이 "저장 중…"이고 저장·취소 버튼이 비활성이다. 실패하면 폼 아래 오류 배너에 서버 문구(PL-R37)를 보이고 폼에 머문다. "취소"는 요청 없이 등록이면 기억한 Deals 목록 주소로, 수정이면 그 Deal 상세로 간다.
- **DE-R31** 요청 값 변환: Deal Name·Solution·구매절차는 앞뒤 공백 제거, Owner·Vendor id는 JSON 숫자(Vendor 선택 안 함 = null), Users count는 숫자, 금액은 콤마를 뺀 숫자, Expected Close 빈 값은 null(서버 문구가 판정), 견적·POC는 선택 안 함·빈 날짜 = null, 고객·파트너는 직급 앞뒤 공백 제거(빈 직급 = null), 빈 이메일·전화 = null, 파트너 칸이 비면 등록은 `partner: null`, 수정은 원래 활성 파트너가 있었으면 `partner: null`(제거) 없었으면 `partner` 키를 보내지 않는다. 게이트웨이는 snake_case 본문으로 `POST /api/v1/deals`·`PATCH /api/v1/deals/{code}`를 보내고(수정은 준 필드만 — Vendor만·Solution만 바꾼 patch는 그 키만, `partner: null` 유지, `quote`·`poc`는 하위 키로), `solution_id`·Label id 값 그대로를 보내지 않으며, 응답 상세를 화면 값으로 바꾼다(DD).

### 2.4 상태와 전이

| 대상 | 현재 | 행동 | 다음 | 조건 |
| --- | --- | --- | --- | --- |
| Deal | (없음) | 등록 | 저장된 Deal(code 발급, 등록 이력 1건) | DE-R2, DE-R16 |
| Deal | 저장됨 | 폼 저장(값 변경) | 같은 code, 바뀐 필드·이력·`updated_at` | DE-R17, DE-R18 |
| Deal | 저장됨 | 폼 저장(변경 없음) | 그대로(이력·시각 그대로) | DE-R18 |
| 파트너 링크 | 활성 | 다른 파트너로 교체 / `partner: null` | 해제(`unlinked_at`) + (교체면) 새 활성 | DE-R14 |
| 연락처 | 기존 | 고른 연락처 값 변경 / 같은 사람 병합 결과 다름 | 갱신 + 참조 Deal에 이력 | DE-R12, DE-R13, CT-R10 |
| BANT Label | (없음) | 새 이름 선택 후 저장 성공 | 직접 만든 Label | DE-R10, CL-R15 |

Status·Forecast의 전이는 DD, 계약 상태는 LC.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `POST /deals` | 401 | 403 읽기 전용 문구 | 가능(Owner는 재직 sales) | 가능(Owner는 재직 sales) |
| `PATCH /deals/{code}` | 401 | 403 읽기 전용 문구 | 가능(모든 Deal) | 가능(모든 Deal) |
| 화면 `/deals/new`, `/deals/:dealCode/edit` | `/login`으로 | `/deals`로(PL-R30) | 열림 | 열림 |

두 경로 모두 업무 라우터(로그인·CSRF PL-R9, 쓰기 가드 PL-R6)이고 역할 가드는 없다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| POST `/deals` | `DealCreateRequest`(DE-R3) | 201 `DealDetailResponse`(DD) + `Location: /api/v1/deals/<code>` | 401, 403, 404 `not-found`(연락처), 409 `already-exists`(연락처)·`invalid-state`(code 발급), 422 `invalid-value`·`request-validation` |
| PATCH `/deals/{code}` | `DealPatchRequest`(DE-R3, DE-R17) | 200 `DealDetailResponse` | 401, 403, 404 `not-found`(Deal·연락처), 409 `already-exists`(연락처)·`invalid-state`(LC-R8), 422 |

- 등록 본문 예: `{"name":"ERP 구축","owner_user_id":7,"vendor_id":null,"solution":"S/4HANA","users":250,"status_key":"prospecting","forecast_key":"pipeline","revenue_amount":150000000,"revenue_date":"2026-06-30","customer":{"company":"네오인","name":"김철수","title":"팀장","email":"kim@neoine.example","phone":"010-1234-5678"},"partner":null,"quote":{"submitted":"YES","submitted_date":"2026-10-01"},"poc":{"state":"ING","completed_date":null},"procurement":"조달청 입찰","bant":{"budget":{"id":3},"authority":{"name":"신규 결재선"},"need":null}}`
- 경로 `{code}`는 문자열이고 형식 판정은 DE-R19(PL-R15의 id 규칙이 아님). 공통 401·403·CSRF·Problem 형식은 PL.

### 2.7 화면 동작

DE-R21~DE-R31.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 요청 형식 위반(DE-R3) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(`errors[]` 포함) |
| 필드 값 위반(DE-R4) | 422 `invalid-value` | DE-R4 표의 문구 |
| 고객 회사명·담당자명 빈 값 | 422 `invalid-value` | 고객 회사명을 입력하세요. / 고객 담당자명을 입력하세요. |
| 파트너 반쪽 입력 | 422 `invalid-value` | 파트너를 입력하면 회사명과 담당자명이 모두 필요합니다. |
| 연락처 형식 | 422 `invalid-value` | CT-R2~R5 문구(예: 공백은 입력할 수 없습니다. / 이메일 형식이 올바르지 않습니다.) |
| BANT 선택 | 422 `invalid-value` | BANT Label이 올바르지 않습니다. / Label 이름 문구(CL-R1) |
| 고른 연락처 없음·종류 다름 | 404 `not-found` | 연락처를 찾을 수 없습니다. |
| 고른 연락처가 다른 사람과 겹침 | 409 `already-exists` | 이미 등록된 연락처입니다. |
| Deal code 10회 충돌 | 409 `invalid-state` | Deal code를 발급하지 못했습니다. 다시 시도하세요. |
| 수정 대상 없음·code 형식 틀림 | 404 `not-found` | Deal을 찾을 수 없습니다. |
| user의 등록·수정 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |

화면 문구: DE-R21~DE-R30. 화면 금액 문구는 "정수를"(서버는 "정수로", 계획 Q2).

## 3. Business use case

### DE-UC1 Deal 등록
- 행위자: sales·admin
- 사전 조건: 로그인, 등록된 Status·Forecast 코드, (선택) Vendor·Label
- 기본 흐름: `/deals/new` → 기본값 확인(DE-R23) → 값 입력·고객 선택 또는 입력 → 저장 → 화면 검증(DE-R26) → `POST /deals` → 서버 검증(DE-R3~R11, 순서 DE-R5) → 연락처 해석(DE-R12·R13) → 새 Label 생성(DE-R10) → code 발급(DE-R2) → 저장·등록 이력(DE-R16) → 상세로 이동·알림(DE-R30)
- 대안: admin이 다른 sales를 Owner로 지정, 처음부터 Won으로 등록(LC-R7), 파트너 없이 등록, Vendor 없이 등록
- 예외: 화면 검증 위반(요청 없음), 형식 422, 값 422, 연락처 404·409, code 발급 409, user 403 — 모두 아무것도 저장되지 않음(DE-R15)
- 결과: code가 발급된 Deal, 필요하면 새 연락처·Label, 등록 이력 1건

### DE-UC2 Deal 폼 수정
- 행위자: sales·admin
- 사전 조건: 수정할 Deal이 있다
- 기본 흐름: `/deals/:dealCode/edit` → 현재 값 채움(DE-R23) → 값 변경 → 저장 → (Won 이탈이면 LC 확인) → `PATCH /deals/{code}` → 보낸 필드 검증(DE-R5) → 연락처·BANT 반영 → 바뀐 필드 이력·`updated_at`(DE-R18) → 상세로 이동·알림
- 대안: 바뀐 것 없음(이력·시각 그대로), Owner 퇴사 Deal의 다른 필드 수정(Owner 미전송), 레거시 빈 Solution Deal 수정(DE-R20), 종결 Deal 수정·되돌리기(DD)
- 예외: 없는 code 404, 값 422(퇴사 Owner 재전송 포함), 연락처 404·409, user 403 — 아무것도 바뀌지 않음
- 결과: 바뀐 필드와 이력

### DE-UC3 Deal 화면에서 고객·파트너 연락처 고르기·고치기
- 행위자: sales·admin(DE-UC1·UC2 안에서)
- 기본 흐름: 회사·담당자를 고르거나 직접 입력(CT-R22) → 저장 → 고른 연락처는 입력값으로 갱신, 직접 입력은 같은 사람이면 병합·재사용, 없으면 새로 만듦(DE-R12·R13) → 값이 바뀌면 참조 Deal마다 연락처 이력(CT-R10)
- 대안: 파트너 교체·제거·추가(DE-R14)
- 예외: 다른 종류·없는 연락처 404, 다른 사람과 겹침 409, 형식 422
- 결과: Deal의 고객·활성 파트너와 갱신된 연락처

### DE-UC4 BANT 고르기·새 Label 입력
- 행위자: sales·admin(DE-UC1·UC2 안에서)
- 기본 흐름: 구분별 콤보박스에서 고르거나 이름 입력(DE-R27) → 저장 → `{id}`/`{name}`/null(CL-R16) → 저장 성공 때만 새 Label 생성(DE-R10)
- 예외: 50자 초과(화면), 다른 구분 id·이름 규칙 422, 뒤의 검증 실패(Label 남지 않음)
- 결과: 구분별 선택과 (필요하면) 새 직접 만든 Label

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), PARK(sales), VIEWER(user). "기본 Deal"은 KIM이 Owner인 "ERP 구축", Solution "S/4HANA", Users count 10, 기회발굴/Pipeline, 금액 150,000,000, Expected Close 2026-06-30, 고객 "네오인 김철수(팀장, kim@neoine.example, 010-1234-5678)", 파트너 없음, BANT 없음이다. 별도 언급이 없으면 기본 시드(코드·Label 23개, Vendor 없음) 상태다. backend 케이스는 Fake UoW·Fake 시계·Fake code 소스를 쓰는 유스케이스·web 단위 테스트, frontend 케이스는 Fake 게이트웨이를 쓰는 Vitest다. 이력 문구 형식은 DD가 검증하고 여기서는 이력이 남는지·건수·대상만 본다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| DE-001 | sales가 새 고객·파트너와 함께 등록하면 201·Location·발급 code와 입력한 값이 저장된다 | DE-R16, DE-R12, DE-R14, DE-UC1 | backend | `application/test_register_deal.py`, `web/test_deal_routes.py` |
| DE-002 | admin이 등록하면 Owner는 지정한 sales이고 이력의 변경자는 admin이다 | DE-R6, DE-R16, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-003 | 등록하면 등록 이력 1건(변경자 = 요청자)이 남고 등록·수정 시각이 서버 시각이다 | DE-R16, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-004 | code는 등록 시각의 서버 로컬 업무 날짜와 code 소스의 4자리다 | DE-R2, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-005 | 이미 있는 code가 나오면 다시 뽑고 10번째 시도까지 성공할 수 있다 | DE-R2, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-006 | code가 10번 연속 겹치면 409이고 아무것도 저장되지 않는다 | DE-R2, DE-R15, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-007 | 경계값(금액 1·2^53−1, Users count 0·2,147,483,647, 이름·Solution 200자, 구매절차 500자)은 등록된다 | DE-R4, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-008 | 필드 값 위반은 각자의 문구로 422 invalid-value이고 저장되지 않는다 | DE-R4, DE-R15, DE-UC1 | backend | `application/test_register_deal_validation.py`, `web/test_deal_request_schemas.py` |
| DE-009 | 여러 값이 틀리면 정해진 순서의 첫 문구만 나온다 | DE-R5, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-010 | 형식이 틀린 등록 본문은 422 request-validation이고 저장되지 않는다 | DE-R3, DE-UC1 | backend | `web/test_deal_request_schemas.py`, `web/test_deal_routes.py` |
| DE-011 | Deal Name·Solution·구매절차의 NUL 문자는 서버 오류 없이 422 invalid-value다 | DE-R4, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-012 | admin·user·없는 사용자를 Owner로 지정하면 "Owner는 재직 중인 영업 담당자여야 합니다."다 | DE-R6, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-013 | 퇴사한 sales를 Owner로 지정하면 퇴사 문구다 | DE-R6, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-014 | Vendor id로 등록하면 응답 vendor가 {id, name}이고 Vendor 없이도 등록된다 | DE-R7, DE-UC1 | backend | `application/test_register_deal.py`, `application/test_register_deal_validation.py`, `web/test_deal_request_schemas.py` |
| DE-015 | 없는 Vendor id는 422이고 201자 Solution보다 먼저 판정된다 | DE-R7, DE-R5, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-016 | Solution은 앞뒤 공백만 지우고 대소문자·한글은 그대로 저장된다 | DE-R8, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-017 | 비었거나 공백뿐·201자 Solution 등록은 422이고 Owner보다 먼저 판정된다 | DE-R8, DE-R5, DE-UC1 | backend | `application/test_legacy_empty_solution_deal.py`, `application/test_register_deal.py`, `application/test_register_deal_validation.py`, `web/test_deal_request_schemas.py` |
| DE-018 | Status·Forecast 코드가 없거나 동기화가 맞지 않는 등록은 422다 | DE-R9, DE-R4, DE-UC1 | backend | `application/test_register_deal_validation.py` |
| DE-019 | 처음부터 계약완료/Won으로 실제 금액과 함께 등록할 수 있다 | DE-R9, DE-UC1 | backend | `application/test_register_deal.py` |
| DE-020 | BANT는 구분마다 {id}·{name}·null을 섞어 저장하고 빠진 구분은 선택 안 함이다 | DE-R10, DE-UC4 | backend | `application/test_register_deal.py`, `application/test_register_deal_bant.py` |
| DE-021 | BANT 뒤의 검증(구매절차·연락처 형식)에서 실패하면 새 Label도 Deal도 남지 않는다 | DE-R10, DE-R15, DE-UC4 | backend | `application/test_register_deal_bant.py` |
| DE-022 | BANT는 동기화 다음, 구매절차 앞에서 판정된다 | DE-R5, DE-R10, DE-UC4 | backend | `application/test_register_deal_bant.py`, `application/test_register_deal_validation.py` |
| DE-023 | 고객 회사명·담당자명이 비거나 파트너가 반쪽이면 Deal 폼 문구로 422이고 새 고객도 남지 않는다 | DE-R11, DE-R15, DE-UC3 | backend | `application/test_register_deal_validation.py` |
| DE-024 | 고객 입력에 연락처 형식 규칙(공백·이메일·전화)이 적용된다 | DE-R11, DE-UC3 | backend | `application/test_register_deal_validation.py` |
| DE-025 | 새 고객·파트너 입력은 새 연락처가 되고 파트너는 활성 링크 1건이며 파트너가 없으면 링크가 없다 | DE-R12, DE-R14, DE-UC3 | backend | `application/test_deal_contact_draft.py`, `application/test_register_deal.py` |
| DE-026 | 같은 사람을 다시 입력하면 기존 연락처를 쓰고 빈 직급·이메일·전화는 기존 값을 지우지 않는다 | DE-R12, DE-R13, DE-UC3 | backend | `application/test_deal_contact_draft.py`, `application/test_register_deal.py` |
| DE-027 | 같은 사람의 연락처에 없던 값은 입력으로 채워지고 그 연락처의 Deal에 이력이 남는다 | DE-R13, DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-028 | 같은 회사·이름이라도 이메일이 다르면 새 연락처다 | DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-029 | 같은 이름의 파트너는 같은 고객이 아니다 | DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-030 | 고른 연락처의 값을 고쳐 등록하면 연락처가 갱신되고 그것을 쓰는 다른 Deal(비활성 파트너 링크 포함)에 이력과 수정 시각이 남는다 | DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-031 | 고른 연락처를 값 그대로 쓰면 연락처와 다른 Deal이 바뀌지 않는다 | DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-032 | 다른 종류이거나 없는 연락처를 고르면 404이고 Deal이 만들어지지 않는다 | DE-R12, DE-R15, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-033 | 고른 연락처를 이미 있는 다른 사람으로 바꾸면 409이고 아무것도 바뀌지 않는다 | DE-R12, DE-R15, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-034 | 값 오류로 등록이 실패하면 고른 연락처도 바뀌지 않는다 | DE-R15, DE-R12, DE-UC3 | backend | `application/test_deal_contact_draft.py` |
| DE-035 | user는 등록할 수 없고(403, 새 Label도 없음) 미인증은 401이다 | DE-R1, DE-UC1 | backend | `web/test_deal_routes.py` |
| DE-036 | 보낸 필드만 바뀌고 200이며 바뀐 필드마다 이력, 수정 시각은 서버 시각이다 | DE-R17, DE-R18, DE-UC2 | backend | `application/test_update_deal.py`, `web/test_deal_routes.py` |
| DE-037 | 같은 값만 보내면 이력이 없고 수정 시각도 그대로다 | DE-R18, DE-UC2 | backend | `application/test_update_deal.py`, `web/test_deal_routes.py` |
| DE-038 | Users count를 null·-1로 고치면 422이고 0으로는 고칠 수 있다 | DE-R17, DE-R4, DE-UC2 | backend | `application/test_update_deal.py` |
| DE-039 | Users count를 보내지 않는 수정은 값이 그대로다 | DE-R17, DE-UC2 | backend | `application/test_update_deal.py` |
| DE-040 | 보낸 필드가 틀리면 422이고 Deal·이력이 그대로이며 정해진 순서의 첫 문구다 | DE-R5, DE-R15, DE-UC2 | backend | `application/test_update_deal.py`, `application/test_update_deal_partner_and_customer.py` |
| DE-041 | 없는 code와 형식이 틀린 code의 수정은 같은 404다 | DE-R19, DE-UC2 | backend | `application/test_update_deal.py`, `web/test_deal_routes.py` |
| DE-042 | user는 수정할 수 없고(403) 미인증은 401이다 | DE-R1, DE-UC2 | backend | `web/test_deal_routes.py` |
| DE-043 | sales는 다른 sales가 Owner인 Deal도 수정할 수 있다 | DE-R1, DE-UC2 | backend | `application/test_update_deal.py` |
| DE-044 | 퇴사한 Owner를 같은 값으로 다시 보내면 퇴사 문구 422다 | DE-R6, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-045 | Owner를 보내지 않으면 퇴사한 Owner의 Deal도 다른 필드를 수정할 수 있다 | DE-R6, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-046 | 퇴사한 Owner를 재직 sales로 바꾸면 저장되고 Owner 이력이 남는다 | DE-R6, DE-R18, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-047 | admin·user를 Owner로 바꾸려 하면 422이고 Owner는 그대로다 | DE-R6, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-048 | 역할이 sales에서 바뀐 Owner의 Deal은 Owner가 그대로이고 Owner를 보내지 않는 수정은 된다 | DE-R6, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-049 | Vendor를 처음 고르거나 바꾸거나 비우면 Solution은 그대로이고 Vendor 이력만 남는다 | DE-R7, DE-R8, DE-UC2 | backend | `application/test_update_deal_solution.py`, `application/test_update_deal_vendor.py`, `web/test_deal_request_schemas.py` |
| DE-050 | 없는 Vendor id로 고치면 422이고 Vendor는 그대로다 | DE-R7, DE-UC2 | backend | `application/test_update_deal_vendor.py` |
| DE-051 | Solution을 바꾸면 공백을 지워 저장하고 대소문자만 바꿔도 이력이 남으며 공백만 다르면 남지 않는다 | DE-R8, DE-R18, DE-UC2 | backend | `application/test_update_deal_solution.py` |
| DE-052 | Solution을 null·빈 값·공백·201자로 고치면 422이고 그대로다 | DE-R8, DE-UC2 | backend | `application/test_update_deal_solution.py` |
| DE-053 | Solution을 보내지 않으면 그대로이고 Vendor 없는 Deal에도 나중에 입력할 수 있다 | DE-R8, DE-UC2 | backend | `application/test_update_deal_solution.py`, `web/test_deal_request_schemas.py` |
| DE-054 | 레거시 빈 Solution Deal은 Solution 없는 수정이 되고 빈 Solution을 보내면 422다 | DE-R20, DE-UC2 | backend | `application/test_legacy_empty_solution_deal.py` |
| DE-055 | 수정에서 없는 Status·Forecast 코드를 보내면 422다 | DE-R9, DE-R4, DE-UC2 | backend | `application/test_update_deal_owner_and_sync.py` |
| DE-056 | 수정에서 새 BANT 이름을 보내면 Label이 생기고 그 구분 이력이 남는다 | DE-R10, DE-UC4 | backend | `application/test_update_deal_bant_choice.py`, `web/test_deal_request_schemas.py` |
| DE-057 | 같은 Label을 id나 대소문자만 다른 이름으로 보내면 변경·이력·새 Label이 없다 | DE-R10, DE-UC4 | backend | `application/test_update_deal_bant_choice.py` |
| DE-058 | 바뀐 구분만 이력이 남고 null로 보낸 구분은 선택 안 함이 된다 | DE-R10, DE-UC4 | backend | `application/test_update_deal_bant_choice.py`, `application/test_update_deal_partner_and_customer.py` |
| DE-059 | bant를 보내지 않는 수정은 Label을 검사·생성하지 않고 선택을 그대로 둔다 | DE-R10, DE-UC2 | backend | `application/test_update_deal_bant_choice.py` |
| DE-060 | 수정이 BANT 뒤 검증에서 실패하면 새 Label도 Deal 변경도 없다 | DE-R10, DE-R15, DE-UC4 | backend | `application/test_update_deal_bant_choice.py` |
| DE-061 | 수정에서 다른 구분 Label id를 보내면 422이고 아무것도 바뀌지 않는다 | DE-R10, DE-R15, DE-UC4 | backend | `application/test_update_deal_bant_choice.py`, `application/test_update_deal_partner_and_customer.py` |
| DE-062 | 견적·POC는 어떤 조합도 저장되고 quote·poc·bant를 null로 보내면 422 request-validation이다 | DE-R4, DE-R17, DE-UC2 | backend | `application/test_update_deal.py`, `web/test_deal_routes.py` |
| DE-063 | 파트너를 다른 사람으로 바꾸면 이전 링크가 해제 시각과 함께 남고 활성은 1건이다 | DE-R14, DE-UC3 | backend | `application/test_update_deal_partner_and_customer.py` |
| DE-064 | partner를 null로 보내면 활성 링크만 해제된다 | DE-R14, DE-UC3 | backend | `application/test_update_deal_partner_and_customer.py`, `web/test_deal_request_schemas.py` |
| DE-065 | 같은 파트너를 다시 보내거나 보내지 않으면 변화가 없다 | DE-R14, DE-UC3 | backend | `application/test_update_deal_partner_and_customer.py`, `web/test_deal_request_schemas.py` |
| DE-066 | 파트너가 없던 Deal에 처음 추가하면 활성 링크가 생기고 이력이 남는다 | DE-R14, DE-UC3 | backend | `application/test_update_deal_partner_and_customer.py` |
| DE-067 | 고객을 다른 사람으로 바꾸면 고객 변경 이력이 남는다 | DE-R12, DE-R18, DE-UC3 | backend | `application/test_update_deal_contact_picking.py`, `application/test_update_deal_partner_and_customer.py` |
| DE-068 | 자기 Deal의 고객·활성 파트너를 골라 값을 고치면 자기 Deal을 포함한 모든 참조 Deal에 연락처 이력이 남고 링크는 그대로다 | DE-R12, DE-R14, DE-R18, DE-UC3 | backend | `application/test_update_deal_contact_picking.py` |
| DE-069 | 수정에서 고른 연락처를 값 그대로 보내면 이력·수정 시각 변화가 없다 | DE-R12, DE-R18, DE-UC3 | backend | `application/test_update_deal_contact_picking.py` |
| DE-070 | 수정에서 다른 종류·없는 연락처는 404, 다른 사람과 겹치면 409이고 아무것도 바뀌지 않는다 | DE-R12, DE-R15, DE-UC3 | backend | `application/test_update_deal_contact_picking.py` |
| DE-071 | 수정에서 customer를 null로 보내면 "고객 회사명을 입력하세요."다 | DE-R11, DE-R17, DE-UC2 | backend | `application/test_update_deal.py` |
| DE-072 | 형식이 틀린 수정 본문은 422 request-validation이고 Deal은 그대로다 | DE-R3, DE-R17, DE-UC2 | backend | `web/test_deal_request_schemas.py`, `web/test_deal_routes.py` |
| DE-073 | 화면: 등록 폼은 로그인 sales를 Owner로, 기회발굴·Pipeline으로, 나머지는 비운 채 시작한다 | DE-R23, DE-R21, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-074 | 화면: Owner 후보는 재직 sales만이고 admin이 열면 Owner가 비어 있다 | DE-R24, DE-R23, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx` |
| DE-075 | 화면: Status 7개·Forecast 6개 선택지가 모두 있다 | DE-R22, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx` |
| DE-076 | 화면: 타일·칸이 상세 순서로 놓이고 수정 폼에만 읽기 전용 Deal code가 있다 | DE-R22, DE-UC1, DE-UC2 | frontend | `features/deals/form/DealFormLayout.test.tsx` |
| DE-077 | 화면: 빈 폼을 저장하면 필수 문구를 한꺼번에 보이고 첫 잘못된 칸으로 포커스하며 요청하지 않는다 | DE-R26, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-078 | 화면: 금액은 콤마로 보이고 입력값 그대로 저장되며 0·상한 초과는 막고 상한은 허용한다 | DE-R26, DE-R31, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-079 | 화면: Owner 미선택·Users count 빈칸·음수는 막고 Users count 0은 저장한다 | DE-R26, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-080 | 화면: Expected Close는 yyyymmdd로 입력해 저장되고 틀린 날짜는 막으며 빈 견적일은 날짜 없음이다 | DE-R26, DE-R31, DE-UC1 | frontend | `features/deals/form/DealFormPage.dateInput.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-081 | 화면: 파트너 입력을 시작하면 회사명·담당자명이 모두 필요하고 비워 두면 묻지 않는다 | DE-R26, DE-R28, DE-UC3 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-082 | 화면: 고객 회사명의 공백과 이메일 형식을 저장 때 알린다 | DE-R26, DE-R28, DE-UC3 | frontend | `features/deals/form/DealFormPage.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-083 | 화면: 담당자를 골라 채운 뒤 저장하면 새 Deal이 목록에 나온다 | DE-R28, DE-R30, DE-UC3 | frontend | `features/deals/form/DealFormPage.test.tsx` |
| DE-084 | 화면: 폼에서 고른 고객의 이메일을 고치면 공유 연락처가 갱신된다 | DE-R28, DE-R12, DE-UC3 | frontend | `features/deals/form/DealFormPage.test.tsx` |
| DE-085 | 화면: 새로 입력한 고객과 목록에서 고른 BANT로 등록된다 | DE-R27, DE-R30, DE-UC1 | frontend | `features/deals/form/DealFormPage.test.tsx` |
| DE-086 | 화면: Vendor는 선택 안 함 + 등록된 Vendor이고 Solution은 Vendor 없이 입력하는 필수 칸이며 Vendor를 바꿔도 그대로다 | DE-R25, DE-UC1 | frontend | `features/deals/form/DealFormPage.vendor.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-087 | 화면: Solution이 비면 요청 없이 문구를 보이고 다른 필수 문구와 함께 나온다 | DE-R26, DE-UC1 | frontend | `features/deals/form/DealFormPage.vendor.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-088 | 화면: Solution은 공백을 지우고 고른 Vendor id와 함께, 또는 Vendor 없이 저장된다 | DE-R25, DE-R31, DE-UC1 | frontend | `features/deals/form/DealFormPage.vendor.test.tsx` |
| DE-089 | 화면: 201자 Solution은 서버 문구를 배너에 보인다 | DE-R30, DE-R8, DE-UC1 | frontend | `features/deals/form/DealFormPage.vendor.test.tsx` |
| DE-090 | 화면: 수정 폼은 Vendor·Solution을 채우고 Solution 변경을 저장하며 비우면 저장하지 않는다 | DE-R25, DE-R26, DE-UC2 | frontend | `features/deals/form/DealFormPage.vendor.test.tsx` |
| DE-091 | 화면: 수정 중 Vendor 목록이 없으면 현재 Vendor를 읽기 전용으로 보이고 원래 id로 저장한다 | DE-R25, DE-UC2 | frontend | `features/deals/form/DealFormPage.vendorLoad.test.tsx` |
| DE-092 | 화면: BANT는 구분별 텍스트 콤보박스 4개이고 새 Label 버튼·선택 상자·이름 수정·삭제가 없다 | DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormLayout.test.tsx`, `features/deals/form/DealFormPage.bant.test.tsx` |
| DE-093 | 화면: BANT 후보는 그 구분 Label만, 입력하면 부분 일치로 좁혀지고 고르면 채워진다 | DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx` |
| DE-094 | 화면: 목록에 없는 BANT 이름이면 새 Label 안내를 보인다 | DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx` |
| DE-095 | 화면: 50자를 넘는 BANT 이름은 그 칸에만 문구를 보이고 저장을 막으며 50자는 된다 | DE-R26, DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-096 | 화면: BANT 빈칸은 선택 안 함, 고른 이름은 id, 없는 이름은 그 구분의 새 Label로 저장된다 | DE-R27, DE-R31, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-097 | 화면: 뒤의 검증이 실패하면 서버 문구를 보이고 새 Label은 생기지 않는다 | DE-R30, DE-R10, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx` |
| DE-098 | 화면: 수정 폼 BANT는 현재 이름으로 채워지고 건드리지 않은 칸은 원래 id, 비운 칸은 선택 안 함, 바꾼 칸은 이름으로 저장된다 | DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-099 | 화면: Label 목록을 못 읽거나 다시 읽는 중이거나 이름이 바뀌어도 수정 저장이 기존 BANT 선택을 지킨다 | DE-R27, DE-UC4 | frontend | `features/deals/form/DealFormPage.bant.test.tsx`, `features/deals/form/DealFormPage.bantRecovery.test.tsx` |
| DE-100 | 화면: 수정 폼은 모든 값을 채우고 저장하면 상세로 가며 "저장되었습니다."를 보인다 | DE-R23, DE-R30, DE-UC2 | frontend | `features/deals/NoticeFlow.test.tsx`, `features/deals/form/DealFormPage.edit.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-101 | 화면: 다른 파트너를 입력하면 교체 안내 후 저장되고 "파트너 제거"로 활성 파트너를 제거한다 | DE-R28, DE-R31, DE-UC3 | frontend | `features/deals/form/DealFormPage.edit.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-102 | 화면: 퇴사한 Owner는 보이지만 다른 Owner를 고를 때까지 저장되지 않는다 | DE-R24, DE-R26, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-103 | 화면: 종결된 Deal도 수정 폼으로 저장된다 | DE-R30, DE-R18, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx` |
| DE-104 | 화면: 저장이 실패하면 서버 문구를 보이고 폼에 머문다 | DE-R30, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx` |
| DE-105 | 화면: 없는 code의 수정 화면은 오류 문구와 "목록으로"를 보인다 | DE-R21, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx` |
| DE-106 | 화면: 취소하면 등록은 목록으로, 수정은 상세로 간다 | DE-R30, DE-UC1, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx`, `features/deals/form/DealFormPage.test.tsx` |
| DE-107 | 화면: Status·Forecast 변경은 동기화 대화상자의 결과를 폼에만 반영하고 저장 때 보낸다 | DE-R29, DE-UC1, DE-UC2 | frontend | `features/deals/form/DealFormPage.edit.test.tsx` |
| DE-108 | 화면: 등록하면 상세로 가며 새 code가 든 등록 알림을 보인다 | DE-R30, DE-UC1 | frontend | `features/deals/NoticeFlow.test.tsx` |
| DE-109 | 화면: 300원 같은 작은 금액은 그대로 보이고 이름만 바꿔도 유지되며 비운 금액은 거절된다 | DE-R26, DE-R31, DE-UC2 | frontend | `features/deals/form/DealFormPage.smallAmount.test.tsx`, `features/deals/form/formState.test.ts` |
| DE-110 | 화면: 폼 입력을 요청 값으로 바꾼다(공백 제거·숫자·null·파트너 생략/제거) | DE-R31, DE-UC1, DE-UC2 | frontend | `features/deals/form/formState.test.ts` |
| DE-111 | 게이트웨이: 등록은 snake_case 본문(빈 직급·없는 파트너·빈 Expected Close는 null, BANT 선택 객체)으로 보내고 201 상세를 읽는다 | DE-R31, DE-UC1 | frontend | `gateway/http/deals.test.ts`, `gateway/http/mappers/deal.test.ts` |
| DE-112 | 게이트웨이: 수정은 준 필드만 보내고 partner null을 유지한다 | DE-R31, DE-UC2 | frontend | `gateway/http/deals.test.ts`, `gateway/http/mappers/deal.test.ts` |

### DE-001 sales가 새 고객·파트너와 함께 등록하면 201·Location·발급 code와 입력한 값이 저장된다
- Given KIM(sales) 로그인, Vendor "SAP" 등록, 업무 날짜 2026-10-15
- When `POST /deals` 기본 Deal 값 + Vendor SAP, Solution "S/4HANA", Users count 250, 파트너 "한빛파트너스 이영희", 견적 YES(2026-10-01), POC ING, 구매절차 "조달청 입찰"
- Then 201이고 `Location`이 `/api/v1/deals/<code>`, code가 `20261015-`로 시작한다. 응답 `name` "ERP 구축", `users` 250, `vendor` `{id, name:"SAP"}`, `solution` "S/4HANA", `revenue_amount` 150000000(JSON 정수), 기회발굴/Pipeline, `owner.role` sales, 고객 회사 "네오인", 활성 파트너 "한빛파트너스"·활성 링크 1건, `quote`·`procurement`가 보낸 값이고 응답에 내부 `id` 필드가 없으며 `owner_user_id`·`customer.id`는 정수다. 저장은 1번 커밋된다

### DE-002 admin이 등록하면 Owner는 지정한 sales이고 이력의 변경자는 admin이다
- Given PARK(sales)이 있고 ROOT(admin) 로그인
- When ROOT가 `owner_user_id` = PARK로 등록한다
- Then 201, Owner는 PARK(역할 sales)이고 등록 이력의 변경자는 ROOT(admin)다

### DE-003 등록하면 등록 이력 1건(변경자 = 요청자)이 남고 등록·수정 시각이 서버 시각이다
- Given 시계 2026-10-15 10:00(+09:00)
- When KIM이 기본 Deal을 등록한다
- Then 그 Deal의 이력은 등록 1건뿐이고 변경자는 KIM, 시각은 서버 시각이다. 응답 `created_at` = `updated_at` = 서버 시각이다

### DE-004 code는 등록 시각의 서버 로컬 업무 날짜와 code 소스의 4자리다
- Given code 소스가 "AB12"를 주고, 서버 로컬 시간대가 Asia/Seoul일 때 시각 2026-10-15T15:30Z(로컬 10-16 00:30) / 2026-10-15T14:59Z, UTC일 때 2026-10-15T15:30Z / 2026-10-16T00:00Z
- When 각 시각에 등록한다
- Then code는 각각 `20261016-AB12`, `20261015-AB12`, `20261015-AB12`, `20261016-AB12`다

### DE-005 이미 있는 code가 나오면 다시 뽑고 10번째 시도까지 성공할 수 있다
- Given 같은 날 code `…-AAAA`인 Deal이 있고 code 소스가 "AAAA"를 9번 준 뒤 "BBBB"를 준다
- When 등록한다
- Then 201이고 code 끝이 "BBBB"다(10번째 시도). 다른 경우 "AAAA" 한 번 뒤 "CCCC"면 "CCCC"다

### DE-006 code가 10번 연속 겹치면 409이고 아무것도 저장되지 않는다
- Given code 소스가 이미 있는 code의 끝 4자리만 계속 준다
- When 등록한다
- Then 409 `invalid-state` "Deal code를 발급하지 못했습니다. 다시 시도하세요."이고 Deal·연락처·이력이 저장되지 않으며 커밋이 없다

### DE-007 경계값은 등록된다
- When 기본 Deal 값에서 각각 금액 1 / 2^53−1, Users count 0 / 1 / 2,147,483,647, Deal Name 200자, 구매절차 500자, Solution 200자, Expected Close 2026-12-31로 등록한다
- Then 모두 201이고 응답 `users`·금액이 보낸 값이다

### DE-008 필드 값 위반은 각자의 문구로 422 invalid-value이고 저장되지 않는다
- When 기본 Deal 값에서 하나씩 바꿔 등록한다: 이름 "  " / 201자, 금액 0 / -5 / 2^53, Expected Close null, Users count -1 / 2,147,483,648, Status "" / "unknown_status", Forecast "no_such", 구매절차 501자
- Then 각각 422 `invalid-value`와 "Deal Name을 입력하세요." / "Deal Name은 200자 이내로 입력하세요." / "매출금액은 1원 이상의 정수로 입력하세요."(3건) / "Expected Close를 입력하세요." / "Users count는 0 이상의 정수로 입력하세요."(2건) / "Status를 선택하세요."(2건) / "Forecast를 선택하세요." / "구매절차는 500자 이내로 입력하세요."이고 Deal 수는 0이다

### DE-009 여러 값이 틀리면 정해진 순서의 첫 문구만 나온다
- Given 위반 목록(DE-R5 순서): 이름 공백 → 없는 Vendor → Solution 공백 → 201자 Solution → 퇴사 Owner → 금액 0 → Expected Close null → Users count -1 → Status "" → Forecast "" → 계약완료/Pipeline → 다른 구분 Label id → 구매절차 501자 → 고객 회사명 "" → 고객 담당자명 "" → 파트너 반쪽 → 고객 이메일 "bad"
- When 목록의 k번째와 그 뒤 모든 위반을 함께 넣어 등록한다(k = 1…17), 또 k번째 위반만 넣어 등록한다
- Then 두 경우 모두 k번째 위반의 문구가 나온다(예: 이름·금액·Users count가 함께 틀리면 "Deal Name을 입력하세요.")

### DE-010 형식이 틀린 등록 본문은 422 request-validation이고 저장되지 않는다
- When 기본 본문에서 하나씩: 금액 `"많이"`, Expected Close `"30/06/2026"`, `owner_user_id` `"x"`, 모르는 키 `extra`, `users` null / `"10"` / 키 없음, `solution` 키 없음 / null / 12, 예전 `vendor` "SAP", `solution_id` 1, BANT 값이 Label id 숫자 그대로, `quote.submitted` "MAYBE"
- Then 모두 422 `request-validation`이고 Deal 수는 0이다

### DE-011 Deal Name·Solution·구매절차의 NUL 문자는 서버 오류 없이 422 invalid-value다
- When 이름 "ERP\x00", Solution "IT\x00DR", 구매절차 "조달\x00"로 각각 등록한다
- Then 각각 422 `invalid-value` "Deal Name에는 NUL 문자를 쓸 수 없습니다" / "Solution에는 NUL 문자를 쓸 수 없습니다" / "구매절차에는 NUL 문자를 쓸 수 없습니다"이고 `detail`에 DB 문구가 없으며 저장되지 않는다

### DE-012 admin·user·없는 사용자를 Owner로 지정하면 "Owner는 재직 중인 영업 담당자여야 합니다."다
- Given 재직 admin "boss", 재직 user "viewer"
- When KIM이 Owner를 각각 boss, viewer, 없는 id로 등록한다
- Then 각각 422 `invalid-value` "Owner는 재직 중인 영업 담당자여야 합니다."이고 저장되지 않는다

### DE-013 퇴사한 sales를 Owner로 지정하면 퇴사 문구다
- Given PARK(sales)이 퇴사 처리됨
- When KIM이 Owner = PARK로 등록한다
- Then 422 "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."

### DE-014 Vendor id로 등록하면 응답 vendor가 {id, name}이고 Vendor 없이도 등록된다
- Given Vendor "SAP"
- When `vendor_id` = SAP, Solution "ITDR"로 등록하고, 또 `vendor_id` 없이 등록한다
- Then 첫째 응답·상세 `vendor` = `{id: SAP, name: "SAP"}`, `solution` "ITDR"이고 둘째는 `vendor` null이다

### DE-015 없는 Vendor id는 422이고 201자 Solution보다 먼저 판정된다
- When 없는 `vendor_id`로 등록하고, 또 없는 `vendor_id` + 201자 Solution으로 등록한다
- Then 둘 다 422 "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."이고 Deal 수는 0이다

### DE-016 Solution은 앞뒤 공백만 지우고 대소문자·한글은 그대로 저장된다
- When Solution "  ITDR  "로, 또 "itDR 통합 보안"으로 등록한다
- Then 저장·응답 Solution은 "ITDR", "itDR 통합 보안"이다

### DE-017 비었거나 공백뿐·201자 Solution 등록은 422이고 Owner보다 먼저 판정된다
- When Solution "" / "   " / 201자로 등록하고, 또 201자 Solution + 퇴사 Owner로 등록한다
- Then "Solution을 입력하세요."(2건) / "Solution은 200자 이내로 입력하세요."(2건) 422이고 저장되지 않는다

### DE-018 Status·Forecast 코드가 없거나 동기화가 맞지 않는 등록은 422다
- When Status "contract_completed" + Forecast "pipeline", Status "prospecting" + Forecast "won"으로 등록한다
- Then 둘 다 422 "Status와 Forecast의 동기화가 맞지 않습니다."이고 저장되지 않는다

### DE-019 처음부터 계약완료/Won으로 실제 금액과 함께 등록할 수 있다
- When Status 계약완료, Forecast Won, 금액 777, Expected Close 2026-09-01로 등록한다
- Then 201이고 그 값이 저장된다(계약 생성은 LC 케이스)

### DE-020 BANT는 구분마다 {id}·{name}·null을 섞어 저장하고 빠진 구분은 선택 안 함이다
- Given budget Label "풀 예산 확보"
- When `bant` = `{budget:{id:풀 예산 확보}, authority:null, need:{name:"신규 필요"}}`(timeline 키 없음)로 등록하고, 또 `bant: {}`로 등록한다
- Then 첫째 응답 `bant`는 budget = 그 id, authority·timeline null, need = 새 Label "신규 필요"의 id이고, 둘째는 네 구분 모두 null이다

### DE-021 BANT 뒤의 검증에서 실패하면 새 Label도 Deal도 남지 않는다
- When need `{name:"신규 필요"}` + 구매절차 501자로 등록하고, 또 need `{name:"신규 필요"}` + 고객 이메일 "bad"로 등록한다
- Then 둘 다 422이고 Label은 기본 23개 그대로, Deal 수 0이다

### DE-022 BANT는 동기화 다음, 구매절차 앞에서 판정된다
- When need `{name:"   "}` + 계약완료/Pipeline으로 등록하고, 또 need `{name:"   "}` + 구매절차 501자로 등록한다
- Then 첫째는 "Status와 Forecast의 동기화가 맞지 않습니다.", 둘째는 "Label 이름을 입력하세요."다

### DE-023 고객 회사명·담당자명이 비거나 파트너가 반쪽이면 Deal 폼 문구로 422이고 새 고객도 남지 않는다
- When 고객 회사명 "", 고객 담당자명 "", 새 고객 "새고객" + 파트너 회사명·담당자명 ""로 각각 등록한다
- Then "고객 회사명을 입력하세요." / "고객 담당자명을 입력하세요." / "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."이고 연락처·Deal이 하나도 생기지 않는다

### DE-024 고객 입력에 연락처 형식 규칙이 적용된다
- When 고객 회사명 "네 오인", 담당자명 "김 철수", 이메일 "no-at-sign", 전화 "abc"로 각각 등록한다
- Then "공백은 입력할 수 없습니다."(2건) / "이메일 형식이 올바르지 않습니다." / "전화번호 형식이 올바르지 않습니다."이고 저장되지 않는다

### DE-025 새 고객·파트너 입력은 새 연락처가 되고 파트너는 활성 링크 1건이며 파트너가 없으면 링크가 없다
- When 새 고객과 새 파트너로 등록하고, 또 파트너 없이 등록한다
- Then 첫째는 고객(customer)·파트너(partner) 연락처가 새로 생기고(새 정수 id, 고객 id < 파트너 id) 활성 파트너 링크 1건(`linked_at` = 서버 시각)이다. 둘째는 파트너 링크가 없다

### DE-026 같은 사람을 다시 입력하면 기존 연락처를 쓰고 빈 직급·이메일·전화는 기존 값을 지우지 않는다
- Given 기본 Deal로 고객 "네오인 김철수(팀장, kim@neoine.example, 010-1234-5678)"가 있다
- When `contact_id` 없이 "네오인 김철수"(직급·이메일·전화 없음)로 두 번째 Deal을 등록한다
- Then 두 Deal의 고객 id가 같고 연락처는 직급 "팀장", 이메일·전화가 그대로다. 두 Deal의 code는 다르다

### DE-027 같은 사람의 연락처에 없던 값은 입력으로 채워지고 그 연락처의 Deal에 이력이 남는다
- Given 이메일이 없는 고객 "네오인 김철수"를 쓰는 Deal A
- When `contact_id` 없이 같은 회사·이름 + 전화 "02-111-2222"로 Deal B를 등록한다
- Then B의 고객은 같은 연락처이고 연락처 전화가 채워지며 A에 연락처 이력 1건이 남는다(B는 등록 이력뿐)

### DE-028 같은 회사·이름이라도 이메일이 다르면 새 연락처다
- When 기본 고객과 같은 회사·이름 + 이메일 "other@neoine.example"로 등록한다
- Then 새 고객 연락처가 생기고 기존 연락처는 그대로다

### DE-029 같은 이름의 파트너는 같은 고객이 아니다
- Given 파트너 "네오인 김철수"
- When 고객 "네오인 김철수"로 등록한다
- Then 고객용 새 연락처가 생긴다

### DE-030 고른 연락처의 값을 고쳐 등록하면 연락처가 갱신되고 그것을 쓰는 다른 Deal에 이력과 수정 시각이 남는다
- Given 같은 고객을 쓰는 Deal A·B, 파트너 "한빛파트너스 이영희"를 쓰다 다른 파트너로 교체해 비활성 링크만 남은 Deal C, 1시간 경과
- When 고객 `contact_id` = A의 고객, 직급 "이사"로 Deal D를 등록하고, 또 파트너 `contact_id` = 이영희, 전화 "02-999-8888"로 Deal E를 등록한다
- Then D의 고객 id = A의 고객 id, 직급 "이사"이고 A·B에 고객 연락처 이력 1건씩, 수정 시각이 서버 시각으로 바뀐다. C에도 파트너 연락처 이력 1건이 남는다. D·E의 이력은 등록 1건뿐이다

### DE-031 고른 연락처를 값 그대로 쓰면 연락처와 다른 Deal이 바뀌지 않는다
- Given Deal A, 1시간 경과
- When A의 고객을 `contact_id`와 현재 값 그대로 골라 등록한다
- Then 201이고 A의 이력은 그대로, A의 수정 시각도 그대로, 연락처 `updated_at`도 그대로다

### DE-032 다른 종류이거나 없는 연락처를 고르면 404이고 Deal이 만들어지지 않는다
- Given 파트너가 있는 Deal A
- When A의 파트너를 고객 `contact_id`로 골라 등록하고, 또 없는 `contact_id`로 등록한다
- Then 둘 다 404 `not-found` "연락처를 찾을 수 없습니다."이고 Deal은 A 하나뿐이다

### DE-033 고른 연락처를 이미 있는 다른 사람으로 바꾸면 409이고 아무것도 바뀌지 않는다
- Given 고객 "네오인 김철수"의 Deal A, 고객 "네오인 박영희(park@neoine.example)"의 Deal B
- When A의 고객을 골라 담당자명 "박영희", 이메일 "park@neoine.example"로 바꿔 등록한다
- Then 409 `already-exists` "이미 등록된 연락처입니다."이고 A의 고객 값과 이력이 그대로다

### DE-034 값 오류로 등록이 실패하면 고른 연락처도 바뀌지 않는다
- Given Deal A
- When A의 고객을 골라 직급 "이사"로 바꾸고 금액 0으로 등록한다
- Then 422이고 연락처 직급은 "팀장" 그대로, A의 이력도 그대로이며 커밋이 없다

### DE-035 user는 등록할 수 없고 미인증은 401이다
- When VIEWER(user)가 BANT need `{name:"신규 필요"}`로 등록하고, 로그아웃한 방문자가 `POST /deals` `{}`를 보낸다
- Then VIEWER는 403 `forbidden`(읽기 전용 문구)이고 Label은 23개 그대로, 방문자는 401 `unauthenticated`다

### DE-036 보낸 필드만 바뀌고 200이며 바뀐 필드마다 이력, 수정 시각은 서버 시각이다
- Given Vendor "Oracle", 기본 Deal, 1시간 경과
- When `PATCH` 이름 "확장 프로젝트", 금액 1,870,000,000, Expected Close 2026-12-31, Vendor Oracle, Users count 20, Status 가격협상
- Then 200이고 그 값들이 바뀌며 Solution "S/4HANA" 등 나머지는 그대로다. 이력은 Status·금액·Expected Close·Deal Name·Vendor·Users count 6건(변경자 KIM)이고 `updated_at`은 서버 시각이다

### DE-037 같은 값만 보내면 이력이 없고 수정 시각도 그대로다
- Given Vendor SAP의 기본 Deal, 1시간 경과
- When 이름 "ERP 구축", 금액 150,000,000, Vendor SAP를 보낸다
- Then 200, 이력 0건, `updated_at` 그대로다

### DE-038 Users count를 null·-1로 고치면 422이고 0으로는 고칠 수 있다
- Given Users count 10인 Deal
- When `users: null`, `users: -1`, `users: 0`을 차례로 보낸다
- Then null은 "Users count를 입력하세요.", -1은 "Users count는 0 이상의 정수로 입력하세요."로 422이고 값·이력이 그대로다. 0은 200이고 0이 저장되며 Users count 이력 1건이 남는다

### DE-039 Users count를 보내지 않는 수정은 값이 그대로다
- Given Users count 10인 Deal
- When 이름만 "B"로 보낸다
- Then 200이고 `users`는 10이다

### DE-040 보낸 필드가 틀리면 422이고 Deal·이력이 그대로이며 정해진 순서의 첫 문구다
- When 이름 "" + 금액 0을 보내고, 또 이름 "" + `users: null`을 보내고, 또 금액 0 + 구매절차 501자를 보낸다
- Then 각각 "Deal Name을 입력하세요." / "Deal Name을 입력하세요." / "매출금액은 1원 이상의 정수로 입력하세요."이고 Deal·이력이 그대로다

### DE-041 없는 code와 형식이 틀린 code의 수정은 같은 404다
- When `PATCH /deals/20260101-ZZZZ`(없음)과 `PATCH /deals/not-a-code`에 이름 "B"를 보낸다
- Then 둘 다 404 `not-found` "Deal을 찾을 수 없습니다."다

### DE-042 user는 수정할 수 없고 미인증은 401이다
- Given 기본 Deal
- When VIEWER가 이름 "B"를 보내고, 로그아웃한 방문자가 같은 요청을 보낸다
- Then 403 `forbidden`, 401 `unauthenticated`이고 Deal은 그대로다

### DE-043 sales는 다른 sales가 Owner인 Deal도 수정할 수 있다
- Given PARK이 Owner인 Deal
- When KIM이 이름 "B"를 보낸다
- Then 200이고 이름이 바뀌며 이력의 변경자는 KIM, Owner는 PARK 그대로다

### DE-044 퇴사한 Owner를 같은 값으로 다시 보내면 퇴사 문구 422다
- Given PARK이 Owner인 Deal, PARK 퇴사
- When KIM이 `owner_user_id` = PARK을 보낸다
- Then 422 "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."이고 Deal은 그대로다

### DE-045 Owner를 보내지 않으면 퇴사한 Owner의 Deal도 다른 필드를 수정할 수 있다
- Given PARK이 Owner인 Deal, PARK 퇴사
- When KIM이 이름만 "이름만 수정"으로 보낸다
- Then 200이고 Owner는 PARK, `owner.resigned` true다

### DE-046 퇴사한 Owner를 재직 sales로 바꾸면 저장되고 Owner 이력이 남는다
- Given PARK이 Owner인 Deal, PARK 퇴사
- When KIM이 `owner_user_id` = KIM을 보낸다
- Then 200, Owner는 KIM이고 Owner 이력 1건이 남는다(문구 DD)

### DE-047 admin·user를 Owner로 바꾸려 하면 422이고 Owner는 그대로다
- Given 기본 Deal, admin "boss"
- When `owner_user_id` = boss, 또 `owner_user_id: null`을 보낸다
- Then 둘 다 422 "Owner는 재직 중인 영업 담당자여야 합니다."이고 Owner는 KIM 그대로다

### DE-048 역할이 sales에서 바뀐 Owner의 Deal은 Owner가 그대로이고 Owner를 보내지 않는 수정은 된다
- Given KIM이 Owner인 Deal, admin이 KIM의 역할을 user로 바꿈
- When PARK이 그 Deal의 이름을 고치고, 또 `owner_user_id` = KIM을 보낸다
- Then 이름 수정은 200이고 Owner는 KIM 그대로(상세·목록에서도 KIM)다. KIM을 보낸 요청은 422 "Owner는 재직 중인 영업 담당자여야 합니다."다(후보 목록에서 빠지는 것은 US-072)

### DE-049 Vendor를 처음 고르거나 바꾸거나 비우면 Solution은 그대로이고 Vendor 이력만 남는다
- Given Vendor SAP·Oracle, Solution "ITDR"인 Vendor 없는 Deal
- When `vendor_id` = SAP, 다음에 Oracle, 다음에 null을 보낸다
- Then 각 응답 `vendor`는 SAP, Oracle, null이고 Solution은 계속 "ITDR"이며 이력은 매번 Vendor 1건뿐이다(같은 Vendor를 다시 보내면 이력 없음)

### DE-050 없는 Vendor id로 고치면 422이고 Vendor는 그대로다
- Given Vendor SAP인 Deal
- When 없는 `vendor_id`를 보낸다
- Then 422 "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."이고 Vendor는 SAP다

### DE-051 Solution을 바꾸면 공백을 지워 저장하고 대소문자만 바꿔도 이력이 남으며 공백만 다르면 남지 않는다
- Given Solution "itdr"인 Deal
- When " itdr "를 보내고, 다음에 "ITDR"을 보낸다
- Then 첫째는 200·이력 없음, 둘째는 Solution "ITDR"과 Solution 이력 1건이다

### DE-052 Solution을 null·빈 값·공백·201자로 고치면 422이고 그대로다
- Given Solution "ITDR"인 Deal
- When `solution` null / "" / "   " / 201자를 보낸다
- Then 앞의 셋은 "Solution을 입력하세요.", 201자는 "Solution은 200자 이내로 입력하세요." 422이고 Solution·이력이 그대로다

### DE-053 Solution을 보내지 않으면 그대로이고 Vendor 없는 Deal에도 나중에 입력할 수 있다
- Given Solution "ITDR"인 Deal과 Vendor 없는 Deal
- When 첫째에 이름만 보내고, 둘째에 Solution "MFA"를 보낸다
- Then 첫째 Solution "ITDR" 그대로, 둘째는 Vendor null·Solution "MFA"다

### DE-054 레거시 빈 Solution Deal은 Solution 없는 수정이 되고 빈 Solution을 보내면 422다
- Given Solution이 `''`인 Deal
- When Users count 7과 이름 "수정한 이름", Vendor만, 금액·Expected Close만 각각 보내고, 또 Solution "  "을, 또 Solution "ITDR"을 보낸다
- Then 앞의 세 요청은 200이고 Solution은 `''` 그대로다. "  "은 422 "Solution을 입력하세요."이고 `''` 그대로다. "ITDR"은 200이고 채워진다

### DE-055 수정에서 없는 Status·Forecast 코드를 보내면 422다
- When Status "unknown"을, 또 Forecast "unknown"을 보낸다
- Then "Status를 선택하세요.", "Forecast를 선택하세요." 422이고 그대로다

### DE-056 수정에서 새 BANT 이름을 보내면 Label이 생기고 그 구분 이력이 남는다
- When `bant` = `{budget:{name:"신규 예산"}}`을 보낸다
- Then 200, budget 구분에 KIM이 만든 Label "신규 예산"이 생기고 Deal이 가리키며 BANT Budget 이력 1건(이후 값 "신규 예산")이 남는다

### DE-057 같은 Label을 id나 대소문자만 다른 이름으로 보내면 변경·이력·새 Label이 없다
- Given authority "CEO 보고 완료"를 고른 Deal
- When `bant` = `{authority:{id}}`, 다음에 `{authority:{name:"ceo 보고 완료"}}`를 보낸다
- Then 둘 다 200, 이력 0건, Label 수 그대로다

### DE-058 바뀐 구분만 이력이 남고 null로 보낸 구분은 선택 안 함이 된다
- Given budget "풀 예산 확보"를 고른 Deal
- When `bant` = `{budget:{id:풀 예산 확보}, timeline:{name:"신규 일정"}}`, 다음에 네 구분 모두 null을 보낸다
- Then 첫째 이력은 Timeline 1건뿐이다. 둘째 뒤 네 구분 모두 선택 안 함이고 Budget·Timeline 이력이 1건씩 더 남는다

### DE-059 bant를 보내지 않는 수정은 Label을 검사·생성하지 않고 선택을 그대로 둔다
- Given budget을 고른 Deal
- When 이름만 보낸다
- Then BANT 선택은 그대로이고 Label 조회·생성이 없다

### DE-060 수정이 BANT 뒤 검증에서 실패하면 새 Label도 Deal 변경도 없다
- When `bant` need `{name:"신규 필요"}` + 구매절차 501자를 보낸다
- Then 422, Label 23개 그대로, BANT·이력 그대로다

### DE-061 수정에서 다른 구분 Label id를 보내면 422이고 아무것도 바뀌지 않는다
- When `bant` = `{budget:{id: need의 "모름"}}`과 이름 "B"를 함께 보낸다
- Then 422 "BANT Label이 올바르지 않습니다."이고 이름·BANT·이력이 그대로다

### DE-062 견적·POC는 어떤 조합도 저장되고 quote·poc·bant를 null로 보내면 422 request-validation이다
- When 견적 NO + 제출일 있음, POC 선택 안 함 + 완료일 있음으로 등록하고, 수정에서 `quote: null`, `poc: null`, `bant: null`을 각각 보내고, `quote: {}`를 보낸다
- Then 등록은 201로 그대로 저장된다. null 셋은 422 `request-validation`이고 그대로다. `quote: {}`는 200이고 견적 여부·제출일이 모두 비워진다

### DE-063 파트너를 다른 사람으로 바꾸면 이전 링크가 해제 시각과 함께 남고 활성은 1건이다
- Given 파트너 "코어테크 민지훈"인 Deal, 1분 경과
- When `partner` = "에이원 표성호"(새 입력)를 보낸다
- Then 200, 활성 파트너는 에이원이고 파트너 이력 순서는 에이원(활성)·코어테크(비활성, `unlinked_at` 있음), 활성 링크는 1건이며 파트너 이력 1건이 남는다

### DE-064 partner를 null로 보내면 활성 링크만 해제된다
- Given 파트너가 있는 Deal
- When `partner: null`을 보낸다
- Then 200, `active_partner` null, 링크 1건은 비활성으로 남고 파트너 이력 1건이 남는다

### DE-065 같은 파트너를 다시 보내거나 보내지 않으면 변화가 없다
- Given 파트너가 있는 Deal
- When 활성 파트너를 `contact_id`와 같은 값으로 보내고, 다음에 이름만 같은 값으로 보낸다
- Then 이력 0건, 링크 1건 그대로다

### DE-066 파트너가 없던 Deal에 처음 추가하면 활성 링크가 생기고 이력이 남는다
- Given 파트너 없는 Deal
- When `partner` = 새 파트너를 보낸다
- Then 활성 링크 1건과 파트너 이력 1건(이전 값 "없음", 문구 DD)이 남는다

### DE-067 고객을 다른 사람으로 바꾸면 고객 변경 이력이 남는다
- When `customer` = "대한상사 오세훈"(새 입력)을 보낸다
- Then 고객이 새 연락처로 바뀌고 고객 변경 이력 1건이 남는다. 이전 고객 연락처는 그대로다

### DE-068 자기 Deal의 고객·활성 파트너를 골라 값을 고치면 모든 참조 Deal에 연락처 이력이 남고 링크는 그대로다
- Given 같은 고객을 쓰는 Deal A·B, 파트너 "한빛파트너스 이영희"인 Deal C, 1시간 경과
- When A에 고객 `contact_id` + 직급 "이사"를 보내고, C에 파트너 `contact_id` + 직급 "부장"을 보낸다
- Then A 응답 고객 직급 "이사", A·B에 고객 연락처 이력 1건씩이고 A의 `updated_at`이 서버 시각이다. C는 파트너 연락처 이력 1건이고 파트너 링크는 1건 그대로다(파트너 변경 이력 없음)

### DE-069 수정에서 고른 연락처를 값 그대로 보내면 이력·수정 시각 변화가 없다
- Given 기본 Deal, 1시간 경과
- When 고객을 `contact_id`와 현재 값 그대로 보낸다
- Then 200, 이력 0건, `updated_at` 그대로다

### DE-070 수정에서 다른 종류·없는 연락처는 404, 다른 사람과 겹치면 409이고 아무것도 바뀌지 않는다
- Given 파트너가 있는 Deal A, 고객 "네오인 박영희(이메일 없음)"의 Deal B
- When A에 파트너 연락처를 고객 `contact_id`로, 없는 `contact_id`로, A의 고객을 골라 담당자명 "박영희"·이메일 없음으로 각각 보낸다
- Then "연락처를 찾을 수 없습니다." 404(2건), "이미 등록된 연락처입니다." 409이고 A의 이력·연락처가 그대로다

### DE-071 수정에서 customer를 null로 보내면 "고객 회사명을 입력하세요."다
- When `customer: null`을 보낸다
- Then 422 `invalid-value` "고객 회사명을 입력하세요."이고 고객은 그대로다

### DE-072 형식이 틀린 수정 본문은 422 request-validation이고 Deal은 그대로다
- When `solution_id: 1`, `solution: 12`, `vendor_id: "x"`, 모르는 키, `code: "20260101-AAAA"`, `delete_license_contracts: "yes"`를 각각 보낸다
- Then 모두 422 `request-validation`이고 Deal은 그대로다

### DE-073 화면: 등록 폼은 로그인 sales를 Owner로, 기회발굴·Pipeline으로, 나머지는 비운 채 시작한다
- Given KIM 로그인
- When `/deals/new`를 연다
- Then 제목 "Deal 등록", Owner는 KIM, Status 기회발굴, Forecast Pipeline, Vendor "선택 안 함", Solution·Users count·금액·Expected Close·고객·파트너·BANT 네 칸이 비어 있다(BANT 자리표시 문구 없음)

### DE-074 화면: Owner 후보는 재직 sales만이고 admin이 열면 Owner가 비어 있다
- Given 재직 sales KIM·PARK, 퇴사 sales, admin ROOT, user VIEWER
- When KIM과 ROOT가 등록 폼을 연다
- Then Owner 선택지는 "선택하세요", KIM, PARK뿐이다. ROOT의 폼은 Owner가 "선택하세요"다

### DE-075 화면: Status 7개·Forecast 6개 선택지가 모두 있다
- When 등록 폼을 연다
- Then Status 선택지 7개, Forecast 선택지 6개가 코드 순서로 있다

### DE-076 화면: 타일·칸이 상세 순서로 놓이고 수정 폼에만 읽기 전용 Deal code가 있다
- When 등록 폼과 수정 폼을 연다
- Then 타일은 Deal 정보·고객·파트너·BANT 순, Deal 정보 칸은 DE-R22 순서, Users count는 필수 표시(선택 문구 없음), 견적·POC는 라벨 하나에 두 입력, 구매절차는 한 줄 입력, 통화 안내가 Deal 정보 안에 있다. 등록 폼엔 Deal code가 없고 수정 폼엔 code가 읽기 전용 값으로 있다. 오류 문구는 그 칸의 행 안에 보인다

### DE-077 화면: 빈 폼을 저장하면 필수 문구를 한꺼번에 보이고 첫 잘못된 칸으로 포커스하며 요청하지 않는다
- Given admin이 연 빈 등록 폼
- When "저장"을 누른다
- Then Deal Name·Owner·Solution·Users count·고객 회사명·담당자명·금액·Expected Close 문구가 함께 보이고 Deal Name 칸에 포커스가 가며 등록 요청이 없다

### DE-078 화면: 금액은 콤마로 보이고 입력값 그대로 저장되며 0·상한 초과는 막고 상한은 허용한다
- When 금액에 "150000000", "0", "9007199254740992", "9007199254740991"을 각각 넣고 저장한다
- Then 첫째는 "150,000,000"으로 보이고 150000000으로 저장되며 안내 "원 단위 정수(예: 1억 원 = 100,000,000)"가 있다. 0은 "매출금액은 1원 이상의 정수를 입력하세요.", 2^53은 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요."로 저장을 막고, 2^53−1은 상한 문구 없이 저장된다

### DE-079 화면: Owner 미선택·Users count 빈칸·음수는 막고 Users count 0은 저장한다
- When Owner 없이, Users count 빈칸으로, "-1"로, "0"으로 각각 저장한다
- Then "Owner를 선택하세요.", "Users count를 입력하세요."(요청 없음), "Users count는 0 이상의 정수로 입력하세요."가 보이고, 0은 저장되어 `users` 0이 보내진다

### DE-080 화면: Expected Close는 yyyymmdd로 입력해 저장되고 틀린 날짜는 막으며 빈 견적일은 날짜 없음이다
- When Expected Close "20261231" 입력 후 저장, "20260231" 입력 후 저장, 빈칸 저장, 견적일 "2026" 일부 입력 후 저장, POC 완료일 틀린 날짜 저장, 견적일 빈칸 저장
- Then 첫째는 "2026-12-31"로 저장, 없는 날짜·일부 입력·틀린 POC 날짜는 날짜 문구로 저장을 막고 주소가 `/deals/new`에 머물며, 빈 Expected Close는 "Expected Close를 입력하세요.", 빈 견적일은 `submitted_date` null로 저장된다

### DE-081 화면: 파트너 입력을 시작하면 회사명·담당자명이 모두 필요하고 비워 두면 묻지 않는다
- When 파트너 직급만 입력하고 저장하고, 또 파트너를 비워 두고 저장한다
- Then 첫째는 "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."로 막고, 둘째는 파트너 문구가 없다

### DE-082 화면: 고객 회사명의 공백과 이메일 형식을 저장 때 알린다
- When 고객 회사명에 공백을 넣고, 또 이메일 "bad"를 넣고 저장한다
- Then 공백 안내(CT-R22)와 "이메일 형식이 올바르지 않습니다."가 보이고 요청이 없다

### DE-083 화면: 담당자를 골라 채운 뒤 저장하면 새 Deal이 목록에 나온다
- Given 고객 연락처 "네오인 김철수"
- When 회사·담당자를 골라 직급·이메일·전화가 채워지고 나머지 필수값을 넣어 저장한다
- Then 상세로 이동하고 Deals 목록에 새 Deal이 나오며 고객은 고른 연락처다

### DE-084 화면: 폼에서 고른 고객의 이메일을 고치면 공유 연락처가 갱신된다
- Given 고객 "네오인 김철수"를 쓰는 다른 Deal
- When 같은 고객을 골라 이메일을 고쳐 저장한다
- Then 연락처의 이메일이 바뀌어 다른 Deal에서도 새 이메일이 보인다

### DE-085 화면: 새로 입력한 고객과 목록에서 고른 BANT로 등록된다
- When 새 고객을 직접 입력하고 Budget에서 "풀 예산 확보"를 골라 저장한다
- Then 새 고객 연락처와 그 Label이 선택된 Deal이 등록된다

### DE-086 화면: Vendor는 선택 안 함 + 등록된 Vendor이고 Solution은 Vendor 없이 입력하는 필수 칸이며 Vendor를 바꿔도 그대로다
- Given Vendor SAP·Oracle
- When 등록 폼을 열고 Solution "ITDR"을 입력한 뒤 Vendor를 SAP에서 Oracle로 바꾼다
- Then Vendor 선택지는 "선택 안 함", SAP, Oracle이고 Solution은 Vendor 없이도 입력할 수 있는 필수 칸이며 Vendor를 바꿔도 "ITDR"이다. Vendor를 만드는 버튼·Solution 목록이 없다

### DE-087 화면: Solution이 비면 요청 없이 문구를 보이고 다른 필수 문구와 함께 나온다
- When Solution만 비우고 저장하고, 또 빈 폼을 저장한다
- Then "Solution을 입력하세요."가 보이고 요청이 없다. 빈 폼에서는 다른 필수 문구와 함께 보인다

### DE-088 화면: Solution은 공백을 지우고 고른 Vendor id와 함께, 또는 Vendor 없이 저장된다
- When Vendor SAP + Solution "  ITDR  ", 또 Vendor 선택 안 함 + Solution "MFA"로 저장한다
- Then 요청은 `vendorId` = SAP id(숫자)·`solution` "ITDR", 그리고 `vendorId` null·`solution` "MFA"다

### DE-089 화면: 201자 Solution은 서버 문구를 배너에 보인다
- When Solution 201자로 저장한다
- Then 폼 아래 배너에 "Solution은 200자 이내로 입력하세요."가 보이고 `/deals/new`에 머문다

### DE-090 화면: 수정 폼은 Vendor·Solution을 채우고 Solution 변경을 저장하며 비우면 저장하지 않는다
- Given Vendor SAP·Solution "ITDR"인 Deal
- When 수정 폼을 열어 Vendor를 Oracle로 바꾸고, Solution을 "MFA"로 바꿔 저장하고, 또 Solution을 비워 저장한다
- Then 처음에 SAP·"ITDR"이 채워지고 Vendor를 바꿔도 Solution은 그대로다. "MFA"는 저장된다. 빈 Solution은 "Solution을 입력하세요."로 요청 없이 막힌다

### DE-091 화면: 수정 중 Vendor 목록이 없으면 현재 Vendor를 읽기 전용으로 보이고 원래 id로 저장한다
- Given Vendor SAP인 Deal, Vendor 목록 조회가 실패한다(또는 아직 응답 전이다)
- When 수정 폼을 열고 Solution을 고쳐 저장한다
- Then Vendor는 "SAP" 읽기 전용 값이고 "선택 안 함" 선택지가 없으며 실패면 오류 배너가 보인다(로딩 중이면 배너 없음). Solution은 입력할 수 있고 저장 요청의 `vendorId`는 원래 SAP id다

### DE-092 화면: BANT는 구분별 텍스트 콤보박스 4개이고 새 Label 버튼·선택 상자·이름 수정·삭제가 없다
- When 등록 폼을 연다
- Then BANT 타일에 이름이 Budget·Authority·Need·Timeline인 콤보박스 4개가 이 순서로 각자 행에 있고 "새 Label" 버튼·이름 입력·선택 상자·이름 수정·삭제 수단이 없다

### DE-093 화면: BANT 후보는 그 구분 Label만, 입력하면 부분 일치로 좁혀지고 고르면 채워진다
- Given Deal 관리에서 need에 "신규 니즈"를 만들었다
- When Need 칸에 포커스하고, "니즈"를 입력하고, 후보 하나를 고른다
- Then 처음엔 need Label만(만든 "신규 니즈" 포함) 보이고, 입력하면 "니즈"를 포함하는 것만 남으며, 고르면 칸에 그 이름이 채워진다

### DE-094 화면: 목록에 없는 BANT 이름이면 새 Label 안내를 보인다
- When Budget에 없는 이름, 있는 이름, 빈칸, authority에만 있는 이름을 각각 입력한다
- Then 없는 이름과 다른 구분에만 있는 이름에서만 "목록에 없는 Label입니다. 저장하면 새 Label로 추가됩니다."가 보인다

### DE-095 화면: 50자를 넘는 BANT 이름은 그 칸에만 문구를 보이고 저장을 막으며 50자는 된다
- When Need에 51자를 넣고 저장하고, 또 50자(앞뒤 공백 포함 입력)를 넣고 저장한다
- Then 51자는 Need 칸에만 "Label 이름은 50자 이내로 입력하세요."가 보이고 요청이 없다. 50자는 저장된다

### DE-096 화면: BANT 빈칸은 선택 안 함, 고른 이름은 id, 없는 이름은 그 구분의 새 Label로 저장된다
- When Budget 비움, Authority " " (공백만), Need에 있는 Label 이름을 공백만 다르게, Timeline에 새 이름을 넣어 저장하고, 또 두 구분에 같은 새 이름을 넣어 저장한다
- Then 요청 `bant`는 budget·authority null, need `{id}`, timeline `{name}`이고 timeline에 새 Label이 생긴다. 같은 새 이름은 구분마다 하나씩 생긴다

### DE-097 화면: 뒤의 검증이 실패하면 서버 문구를 보이고 새 Label은 생기지 않는다
- When Need에 새 이름 + 서버가 거절하는 구매절차 501자로 저장한다
- Then 배너에 "구매절차는 500자 이내로 입력하세요."가 보이고 Label 목록에 새 이름이 없다

### DE-098 화면: 수정 폼 BANT는 현재 이름으로 채워지고 건드리지 않은 칸은 원래 id, 비운 칸은 선택 안 함, 바꾼 칸은 이름으로 저장된다
- Given budget·need를 고른 Deal
- When 수정 폼을 열어 그대로 저장하고, 또 Budget을 비우고 Need를 새 이름으로 바꿔 저장한다
- Then 처음 Budget·Need에 현재 이름, 나머지 빈칸이다. 그대로 저장하면 `{id}` 둘·null 둘을 보내고 BANT 이력이 없다. 둘째는 budget null, need `{name}`이고 Budget·Need 이력이 남는다

### DE-099 화면: Label 목록을 못 읽거나 다시 읽는 중이거나 이름이 바뀌어도 수정 저장이 기존 BANT 선택을 지킨다
- Given BANT 네 구분을 고른 Deal
- When ① Label 목록 조회가 실패한 채 수정 폼을 열어 이름만 바꿔 저장, ② Label 목록을 다시 읽는 중에 저장, ③ 폼을 연 뒤 admin이 고른 Label 이름을 바꾸고 저장
- Then ①은 BANT 칸이 비활성이고 배너가 보이며 요청에 `bant`가 없다. ②③은 원래 `{id}` 넷을 보내고 새 Label·BANT 이력이 없다

### DE-100 화면: 수정 폼은 모든 값을 채우고 저장하면 상세로 가며 "저장되었습니다."를 보인다
- Given 모든 칸에 값이 있는 Deal
- When 수정 폼을 열고 이름을 바꿔 저장한다
- Then 제목 "Deal 수정"이고 모든 칸이 Deal 값으로 채워져 있었으며, 저장 뒤 `/deals/<code>`로 가고 "저장되었습니다." 알림이 보인다

### DE-101 화면: 다른 파트너를 입력하면 교체 안내 후 저장되고 "파트너 제거"로 활성 파트너를 제거한다
- Given 활성 파트너 "코어테크 민지훈"인 Deal
- When 파트너를 다른 사람으로 입력해 저장하고, 또 "파트너 제거"를 눌러 저장한다
- Then 첫째는 "기존 활성 파트너(코어테크 민지훈)는 이력으로 남고 비활성이 됩니다."가 보이고 새 파트너로 저장된다. 둘째는 "저장하면 기존 활성 파트너(코어테크 민지훈)가 제거되고 이력으로 남습니다."가 보이고 `partner: null`이 보내진다. 같은 연락처를 고르거나 회사·이름을 대소문자만 다르게 다시 입력하면 교체 안내가 없다

### DE-102 화면: 퇴사한 Owner는 보이지만 다른 Owner를 고를 때까지 저장되지 않는다
- Given Owner가 퇴사한 Deal
- When 수정 폼을 열어 그대로 저장하고, 다음에 KIM을 골라 저장한다
- Then Owner 칸에 "<이름>(퇴사)"가 고를 수 없는 선택지로 보이고 처음 저장은 퇴사 문구로 막힌다. KIM으로 바꾸면 저장된다

### DE-103 화면: 종결된 Deal도 수정 폼으로 저장된다
- Given 계약완료/Won Deal
- When 수정 폼에서 이름만 바꿔 저장한다
- Then 저장되고 상세로 간다

### DE-104 화면: 저장이 실패하면 서버 문구를 보이고 폼에 머문다
- Given 서버가 수정을 422로 거절한다
- When 저장한다
- Then 배너에 서버 문구가 보이고 수정 주소에 머물며 "저장" 버튼을 다시 누를 수 있다

### DE-105 화면: 없는 code의 수정 화면은 오류 문구와 "목록으로"를 보인다
- When `/deals/20260101-ZZZZ/edit`을 연다
- Then "Deal을 찾을 수 없습니다." 배너와 "목록으로" 링크가 보이고 폼이 없다

### DE-106 화면: 취소하면 등록은 목록으로, 수정은 상세로 간다
- When 등록 폼과 수정 폼에서 "취소"를 누른다
- Then 요청 없이 등록은 Deals 목록, 수정은 `/deals/<code>`로 간다

### DE-107 화면: Status·Forecast 변경은 동기화 대화상자의 결과를 폼에만 반영하고 저장 때 보낸다
- Given 기회발굴/Pipeline 수정 폼
- When Status를 계약완료로 고르고 매출 대화상자에 금액·날짜를 확정하고, 또 대화상자를 취소하고, Won Deal에서 Forecast를 다른 값으로 고르고, 새 Deal 등록 폼에서 Forecast Won을 고른 뒤 저장한다
- Then 확정하면 Forecast가 Won, 금액·Expected Close가 확정값으로 폼에 들어가고 저장 전 안내가 보이며 요청은 없다. 취소하면 Status가 그대로다. Won에서 벗어나면 Status를 고르라고 묻는다. 새 Deal도 매출을 묻는다. 저장하면 동기화된 값이 저장되어 목록에 보인다

### DE-108 화면: 등록하면 상세로 가며 새 code가 든 등록 알림을 보인다
- When 등록 폼을 채워 저장한다
- Then `/deals/<code>`로 가고 "Deal <code>이(가) 등록되었습니다." 알림이 보인다

### DE-109 화면: 300원 같은 작은 금액은 그대로 보이고 이름만 바꿔도 유지되며 비운 금액은 거절된다
- Given 금액 300인 Deal
- When 수정 폼에서 이름만 바꿔 저장하고, 또 금액을 비우고 저장한다
- Then 금액 칸은 "300"이고 300이 그대로 저장된다. 빈 금액은 금액 문구로 막힌다

### DE-110 화면: 폼 입력을 요청 값으로 바꾼다
- When 폼 상태(앞뒤 공백 있는 이름·Solution·구매절차, 문자열 Owner·Vendor id, 금액 "1,000", 빈 직급·이메일, 빈 파트너)를 등록·수정 요청으로 바꾼다
- Then 공백이 지워지고 id·금액·Users count는 숫자, 빈 Vendor·견적·POC·이메일·전화는 null, 빈 파트너는 등록 `partner: null`이다. 수정은 원래 활성 파트너가 있었으면 `partner: null`, 없었으면 `partner` 키가 없고, 다른 사람을 입력하면 그 ContactDraft다

### DE-111 게이트웨이: 등록은 snake_case 본문으로 보내고 201 상세를 읽는다
- When 게이트웨이 `create`로 Deal 입력(빈 직급, 파트너 없음, 빈 Expected Close, BANT 선택 객체 포함)을 보낸다
- Then `POST /api/v1/deals` 본문은 snake_case이고 `title` null, `partner` null, `revenue_date` null, `bant`는 구분마다 `{id}`(JSON 숫자)·`{name}`·null이며 `solution`은 텍스트, `solution_id`는 없다. 201 응답은 상세 화면 값으로 바뀐다

### DE-112 게이트웨이: 수정은 준 필드만 보내고 partner null을 유지한다
- When 게이트웨이 `update`로 이름만, Vendor만, Solution만, `vendorId: null`, `partner: null`, 견적·POC·BANT 포함 patch를 각각 보낸다
- Then `PATCH /api/v1/deals/{code}` 본문은 준 키만 담는다(Vendor만이면 `vendor_id`만, Solution만이면 `solution`만), `vendor_id: null`·`partner: null`이 그대로 있고, 견적·POC는 `quote{submitted, submitted_date}`·`poc{state, completed_date}`, BANT는 있을 때만 선택 객체이며 빈 Expected Close는 null이다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 초안: 구현된 동작을 문서화(DE-R1~R31, DE-UC1~UC4, DE-001~DE-112) | DE-001~DE-112 |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체, DE-R26 금액 문구에 정본 번호(UI-R13·UI-R14)를 덧붙임(문구 변경 없음). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
