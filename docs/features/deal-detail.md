# Deal 상세·변경 적용·이력·삭제   (feature 코드: DD, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/domain/deal/{code,entities,policy,errors,history,sync,sync_state,sync_plan,sync_finalize}.py`, `app/application/deal/{get_deal,apply_change,sync_change,history_writer,list_deal_history,deletion_impact,delete_deal}.py`, `app/web/routers/deals.py`, `app/web/schemas/{deal_change,deal_response}.py`, `app/infra/db/{deal_history_repository,deal_aggregates}.py`, `frontend/src/features/deals/detail/{DealDetailPage,DealTitle,SummaryBar,DealIdentityRows,DealFacts,InfoCards,BantCard,ContactCards,InlineContactBlock,ContactSession,contactInline,InlineEdit,HistoryTab,DeleteDealDialog,detailHelpers}.tsx|ts`, `shared/sync/{useSyncedChange,RevenueDialog,ChoiceDialog}.tsx`, `shared/model/{sync,history,permissions}.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 화면·테스트·Fake가 어긋나는 점은 계획(`artifacts/10-analysis/dd-plan.md`)의 확인 필요 질문으로 분리했습니다.

## 1. 개요

- 목적: 한 Deal을 열어 현재 값을 보고, 값을 그 자리에서 고치고(Status·Forecast는 동기화 규칙을 지키며), 무엇이 언제 누구에 의해 바뀌었는지(Deal History) 보고, 필요하면 Deal을 지운다.
- 사용자(역할): 조회는 로그인한 모든 역할(admin·sales·user), 값 변경은 sales·admin(Owner 여부와 무관), 삭제는 Owner 본인 sales와 admin.
- 범위
  - 화면 `/deals/:dealCode`: 머리(Deal 이름·목록·삭제), 탭 3개 틀, Deal 정보 타일(요약 값·인라인 수정), 고객·파트너·BANT 카드와 인라인 수정, Deal History 탭, 삭제 확인 대화상자
  - API `GET /deals/{code}`, `POST /deals/{code}/changes`, `GET /deals/{code}/history`, `GET /deals/{code}/deletion-impact`, `DELETE /deals/{code}`
  - Status·Forecast 동기화 규칙(불변식과 단일 변경 계획·확정) — 모든 Deal 저장 경로가 이 규칙을 쓴다
  - Deal History 기록 형식(등록 항목, Deal 필드 변경 diff의 순서·대상·표기·자르기)과 목록
  - Deal code 경로 파라미터 형식 판정, 폐지된 Deal 경로
- 범위 밖(다른 feature)
  - Deal 등록·폼 수정(`POST /deals`, `PATCH /deals/{code}`)의 필드 검증·Owner 자격·Vendor·Solution·BANT 선택·연락처 연결과 Deal code 발급 → DE. 이 문서의 인라인 수정은 화면 동작만 정하고, 저장은 `PATCH`(DE)로 한다. 폼 저장의 동기화 불변식(DD-R5)과 이력 diff(DD-R20·R21)는 DD가 정하고 DE가 번호로 가리킨다
  - Actions 탭(Action 목록·등록·수정·삭제, Action 등록의 Status·Forecast 두 단계 변경 `finalize_sequence`) → AC, Next Action 상태·Action 검색 → NA. Action·Next Action 이력 항목의 문구 → AC·NA
  - 첨부 패널, 첨부 이력 항목 문구, 첨부 행 삭제 영향 건수의 계산(교체·삭제 반영) → AT
  - Won 진입·이탈 계약 처리, `delete_license_contracts`, Deal 응답의 `license_contract_count`·`has_issued_license_contract`, 삭제 영향의 `license_contract_count`, 삭제 확인 대화상자의 계약 건수, Deal 삭제 시 계약·계약 폴더 삭제 → LC(LC-R6~R9, LC-R20, LC-R26, LC-R37)
  - Deal 응답의 `risk`·`status_changed_at`·`status_days`·`last_updated_at`·`next_action`(파생 값)과 그 표시("N일째", 경고 배지, 최종 업데이트 상대 시각) → RK
  - 연락처 수정이 남기는 `contact` 이력(CT-R10), 연락처 선택기(`ContactPicker`) 규칙 → CT
  - 목록으로 돌아가는 주소(조건 기억) → DL, 공통 날짜 입력 `DateInput`·금액 입력 → UI(UI-R1~R11, UI-R12~R15), 서버 시각 표기 → TM
  - 공통 권한 판정·CSRF·Problem 형식·화면 오류 문구 → PL(PL-R1, PL-R4~R6, PL-R9~R13, PL-R36~R39)
- 관련 화면·메뉴: Deals 목록에서 Deal을 열면 `/deals/<code>`(주 메뉴 Deals, PL-R34). 보호 화면(`RequireAuth`, PL-R29).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| Deal code | Deal의 업무 키 `YYYYMMDD-XXXX`(업무 날짜 8자리, `-`, 영문 대문자·숫자 4자리). API 경로의 `{code}` |
| 계약완료 / Won | Status key `contract_completed` / Forecast key `won`(잠금 코드, CD-R3). 이름이 바뀌어도 key로 판정한다 |
| Lost | Forecast key `lost` |
| 종결(closing) | Status를 계약완료로 또는 Forecast를 Won으로 바꾸는 변경. 두 값이 함께 바뀌고 실제 매출금액·매출일이 필요하다 |
| 되돌림(reopen) | Won·Lost·계약완료에서 벗어나는 변경. 함께 둘 값을 골라야 한다 |
| 단일 변경 | `POST /deals/{code}/changes` 한 번에 값 하나(Status, Forecast, 금액, Expected Close)를 바꾸는 요청 |
| resolution | 단일 변경에서 화면이 사용자에게 물어 얻은 답(매출금액·매출일, 함께 바꿀 Status·Forecast) |
| 함께 바뀐 값(co_changed) | 사용자가 직접 바꾸지 않았지만 동기화 규칙 때문에 함께 바뀐 필드 |
| Deal History | Deal의 변경 기록. 항목 = 구분(category)·대상(target)·변경 전·변경 후·변경 시각·변경자 |
| Expected Close | Deal의 `revenue_date`. 종결 때 입력한 매출일이 여기에 저장된다 |

### 2.2 데이터 모델

- `deals`(PK `id` BIGINT identity, `deal_code` UNIQUE): 이 문서가 읽고 바꾸는 열 — `status_key`·`forecast_key`(codes 복합 FK RESTRICT, CD 2.2), `revenue_amount`(CHECK `1 ~ 2^53−1`), `revenue_date`, `updated_at`. CHECK `won_sync` = `(status_key = 'contract_completed') = (forecast_key = 'won')`. 나머지 열과 제약은 DE.
- `deal_partner_links`: Deal–파트너 연락처 연결(`contact_id`, `linked_at`, `unlinked_at`; 활성 = `unlinked_at` NULL, 활성은 최대 1건). 해제해도 지우지 않는다.
- `deal_history`(PK `id` BIGINT identity, `deal_id` FK → deals CASCADE): `changed_at`(timestamptz), `changed_by`(users FK RESTRICT), `category`(아래 12값), `target`(최대 300자), `before`·`after`(각 최대 1000자).
- 값 객체: `DealCode`(형식 위), `SyncState(status_key, forecast_key)`, `CoChange(field, before, after)`, `SyncResolution(revenue_amount, revenue_date, status_key, forecast_key)`, `HistoryDraft(category, target, before, after)`(만들 때 자르기 DD-R20), `HistoryCategory` 12값 `created`·`status`·`forecast`·`amount`·`expectedClose`·`owner`·`partner`·`contact`·`bant`·`action`·`attachment`·`other`.
- Deal을 지우면 `deal_id`로 연결된 자식 행(이력·Action·첨부 메타·파트너 링크·BANT 선택·라이선스 계약)이 DB CASCADE로 함께 지워진다. 연락처·Label·코드·Vendor·사용자·파트너 미팅은 Deal을 가리키지 않거나 RESTRICT 대상이 아니므로 남는다.

### 2.3 비즈니스 규칙

Deal code·조회
- **DD-R1** 경로의 `{code}`는 정규식 `[0-9]{8}-[A-Z0-9]{4}`에 **전체가** 맞아야 한다(소문자, UUID, `not-a-code`, 끝 줄바꿈이 붙은 값은 형식이 틀림). 형식이 틀린 code는 422가 아니라 **없는 Deal과 같은 404** `not-found` "Deal을 찾을 수 없습니다."다. 이 판정은 상세·단일 변경·이력·삭제 영향·삭제 모두 같다.
- **DD-R2** `GET /deals/{code}`는 로그인한 모든 역할이 부른다. 200 `DealDetailResponse` 필드는 정확히 `code`, `name`, `owner_user_id`, `owner`, `vendor`(`{id, name}` 또는 null), `solution`, `users`, `status_key`, `forecast_key`, `revenue_amount`(JSON 정수), `revenue_date`(YYYY-MM-DD), `customer`(연락처), `active_partner`(연락처 또는 null), `partner_links`, `quote`(`submitted`·`submitted_date`), `poc`(`state`·`completed_date`), `procurement`, `bant`(`budget`·`authority`·`need`·`timeline` = Label id 또는 null), `next_action`, `last_updated_at`, `risk`, `status_changed_at`, `status_days`, `license_contract_count`, `has_issued_license_contract`, `created_at`, `updated_at`, `partner_history`다. 폐지된 필드 `stage`·`id`·`customer_id`·`partner_id`·`revenue_currency`·`registered_by`는 없다. 파생 값의 뜻은 RK, 계약 필드는 LC-R20, 연락처 모양은 CT, 시각 표기는 TM.
- **DD-R3** `owner`는 `UserRef`(`id`, `name`, `resigned`, `label`, `role`)다. Owner가 퇴사했어도 그 사용자로 돌아오고 `resigned` true, `label` "<이름>(퇴사)"다.
- **DD-R4** `partner_links`는 그 Deal의 모든 파트너 링크(활성·해제)이고 각 항목은 `contact_id`·`active`·`linked_at`·`unlinked_at`이다. `active_partner`는 활성 링크의 연락처(없으면 null)다. `partner_history`는 모든 링크를 연락처 객체와 함께 **최근 연결 순**(`linked_at` 내림차순, 같으면 나중에 추가된 링크가 먼저)으로 준다. 교체된 파트너는 `active` false와 `unlinked_at`을 가진 채 남는다.

Status·Forecast 동기화
- **DD-R5** 불변식: Status가 계약완료이면 Forecast는 Won이고, Forecast가 Won이면 Status는 계약완료다(둘 다 아니어도 된다). Deal을 저장하는 모든 경로(등록·폼 수정 DE, 단일 변경, Action 등록 AC)의 최종 값이 이를 어기면 422 `invalid-value` "Status와 Forecast의 동기화가 맞지 않습니다."이고 아무것도 바뀌지 않는다. 폼 수정에서 종결·되돌림은 두 값을 **함께** 보내야 하며(한쪽만 보내면 이 422), 두 값을 함께 보낸 폼 저장은 함께 변경 표기 없이 Status·Forecast 이력이 각각 남는다. 종결된 Deal도 계속 수정할 수 있고(잠금 없음), 되돌려도 금액·Expected Close는 그대로다. 판정은 key로 하며 코드 이름과 무관하다.
- **DD-R6** 단일 변경 계획(변경 전 값 기준, 위에서부터 첫 일치):

  | 요청 | 변경 전 | 결과 |
  | --- | --- | --- |
  | 같은 값으로 바꿈 | — | 변경 없음(DD-R14) |
  | Status → 계약완료 | — | 종결: Forecast도 Won, 매출 필요(DD-R7) |
  | Forecast → Won | (Lost 포함) | 종결: Status도 계약완료, 매출 필요(DD-R7) |
  | Status → 다른 값 | Status 계약완료 | Forecast 선택 필요: 선택지 = Won을 뺀 Forecast(코드 순서) (DD-R8) |
  | Forecast → Won 아닌 값(Lost 포함) | Forecast Won | Status 선택 필요: 선택지 = 계약완료를 뺀 Status(코드 순서), 기본값 없음 (DD-R8) |
  | Forecast → Won 아닌 값 | Forecast Lost | Status 선택 필요: 선택지 같음, 기본값 = 현재 Status (DD-R8) |
  | 그 밖 | — | 독립 변경: 요청한 값만 바뀐다(예: Won이 아닌 Deal을 Lost로 바꾸면 Status 그대로) |

- **DD-R7** 종결의 답: `resolution.revenue_amount`가 1 이상 2^53−1 이하 정수이고 `resolution.revenue_date`가 있어야 한다. 하나라도 없거나 금액이 범위 밖이면 422 `invalid-value` "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."이고 아무것도 바뀌지 않는다(이력도 없음). 통과하면 Status = 계약완료, Forecast = Won, 금액 = 매출금액, Expected Close = 매출일이 된다. 함께 바뀐 값은 사용자가 요청하지 않은 쪽 하나(값이 실제로 바뀐 경우만)이고 알림은 "Status가 '<계약완료 이름>'로, Forecast가 '<Won 이름>'으로 함께 변경되었습니다."(조사는 이름 끝 글자에 맞춘 `로`/`으로`)다.
- **DD-R8** 선택의 답: 고른 key(`resolution.status_key` 또는 `forecast_key`)가 선택지에 있어야 한다. 없거나 선택지 밖(예: Status 선택에 계약완료, Forecast 선택에 Won)이면 422 `invalid-value` "함께 바꿀 값을 선택하세요."이고 아무것도 바뀌지 않는다. 고른 값이 현재 값과 다르면 함께 바뀐 값 1건과 알림 "Status가 '<이름>'(로|으로) 함께 변경되었습니다." 또는 "Forecast가 '<이름>'(로|으로) 함께 변경되었습니다."이고, 같으면(Lost 되돌림에서 현재 Status를 그대로 고름) 함께 바뀐 값 없음·알림 null이다. 되돌림은 금액·Expected Close를 바꾸지 않는다.
- **DD-R9** 독립 변경은 `resolution`을 무시한다(보내도 오류 없음, 함께 바뀐 값 없음, 알림 null).
- **DD-R10** 규칙은 key로 동작하고 선택지 순서는 코드 목록의 현재 순서(CD-R5)다. 알림·이력의 이름은 변경 시점의 코드 이름이다(이름을 바꾼 뒤에도 같은 규칙, 새 이름으로 표기).

단일 변경 API
- **DD-R11** `POST /deals/{code}/changes` 본문 `{change: {field, value}, resolution?, delete_license_contracts?}`. `field`·`value`: `status_key`·`forecast_key` = 문자열, `revenue_amount` = JSON 정수(StrictInt — 문자열·실수·불리언 거부), `revenue_date` = 날짜(`YYYY-MM-DD`). 이 네 값 외의 `field`(예: `users`), 형식이 틀린 `value`(빈 문자열 날짜 포함), `change` 누락, 모르는 키, `resolution`의 형식 오류(`revenue_amount` 정수 아님, 모르는 키)는 422 `request-validation`이다. `resolution` 키 `revenue_amount`·`revenue_date`·`status_key`·`forecast_key`는 모두 선택(null 가능)이고 `resolution` 자체도 생략·null 가능하다. `delete_license_contracts`는 LC-R9.
- **DD-R12** `status_key`·`forecast_key` 변경의 값이 코드 목록에 없는 key면 422 `invalid-value` "존재하지 않는 코드입니다."이고 아무것도 바뀌지 않는다(동기화 판정보다 먼저).
- **DD-R13** 금액 변경: 1 이상 2^53−1 이하가 아니면(0, -1, 2^53) 422 `invalid-value` "매출금액은 1원 이상의 정수로 입력하세요."이고 금액은 그대로다(1과 2^53−1은 허용). Expected Close 변경: 그 날짜를 저장한다. 두 변경 모두 Status·Forecast를 건드리지 않고, 종결된 Deal에서도 된다.
- **DD-R14** 성공은 200 `{deal: DealDetailResponse, co_changed: [{field, from, to}], notice}`(키 정확히 셋, `field`는 `status_key`·`forecast_key`)이고 `deal`은 변경 뒤 값이다. 값이 실제로 바뀌면 `updated_at` = 서버 시각이고 바뀐 필드마다 이력(DD-R20)이 남는다. 값이 그대로면(같은 값 변경, 같은 금액) 200이지만 이력도 `updated_at` 변경도 없고 `co_changed` 빈 목록·`notice` null이다. Deal 변경·이력·계약 처리(LC)는 한 트랜잭션이다.
- **DD-R15** 단일 변경은 sales·admin이 **모든** Deal에 할 수 있다(Owner 검사 없음, 퇴사한 Owner의 Deal 포함). 이력의 변경자는 요청자다. user는 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(PL-R6), 미인증 401. 판정 순서: 401 → CSRF 403 → 역할 403 → 요청 형식 422 → 없는 Deal 404 → 없는 코드 422(DD-R12) → 금액(DD-R13)·동기화(DD-R7·R8) 422 → 계약 409(LC-R8).
- **DD-R16** 폐지된 Deal 경로는 없다: `GET`·`PUT`·`DELETE /deals/<UUID>`, `GET /deals/by-code/<code>`, `POST /deals/<UUID>/stage`, `GET /deals/<UUID>/stage-changes`, `GET /deals/pipeline`은 404 또는 405다(UUID·`pipeline`은 형식이 틀린 code라 404, `PUT /deals/{code}`는 405 — PL-R13).

Deal History
- **DD-R17** `GET /deals/{code}/history?category=<값>`은 로그인한 모든 역할이 부른다. Deal이 없으면 404(DD-R1). 응답은 `HistoryEntryResponse[]` — 필드 `id`, `deal_code`, `at`, `by`(UserRef, 퇴사자도 `resigned` true로), `category`, `target`, `before`, `after` — 이고 순서는 `at` 내림차순, 같으면 `id` 내림차순(나중에 기록한 것이 위)이다. `category`를 주면 그 구분만 돌려준다. `category`가 12값(2.2)이 아니면 422 `request-validation`. 페이지 없이 전부 돌려준다.
- **DD-R18** 이력을 쓰는 곳과 문구 소유: Deal 등록(DD-R19), Deal 필드 변경 diff(DD-R20·R21 — 폼 수정 DE, 단일 변경, Action 등록의 Status·Forecast 변경 AC가 같은 함수를 씀), 연락처 수정(CT-R10), Action·Next Action(AC·NA), 첨부(AT). 이 문서는 등록 항목과 Deal 필드 diff의 형식, 저장 형식(DD-R20 자르기), 목록(DD-R17)을 정한다.
- **DD-R19** Deal을 등록하면 구분 `created`, 대상 "Deal 등록", 변경 전 "", 변경 후 "Deal 등록" 항목 1건이 등록자·등록 시각으로 남는다.
- **DD-R20** Deal 필드 diff: 변경 전후 값을 비교해 **바뀐 필드마다 1건**, 바뀐 것이 없으면 0건이다. 순서는 고정 — Status, Forecast, 금액, Expected Close, Owner, 파트너, 고객 연락처, BANT(Budget·Authority·Need·Timeline), Deal Name, Vendor, Solution, Users count, 견적, POC, 구매절차. 한 번의 저장에서 나온 항목은 같은 변경 시각·변경자를 가지며 Deal `updated_at`이 같은 시각이 되고 같은 트랜잭션에 저장된다. 저장할 때 대상은 300자, 변경 전·후는 각 1000자(유니코드 코드 포인트 수)를 넘으면 앞부분 299자·999자 + "…"로 자른다.
- **DD-R21** diff 항목의 구분·대상·표기:

  | 필드 | 구분 | 대상 | 값 표기 |
  | --- | --- | --- | --- |
  | Status | `status` | Status | 코드 이름. 함께 바뀐 경우 변경 후 = "<이름> (Forecast <Forecast 이름>와/과 함께 변경)" |
  | Forecast | `forecast` | Forecast | 코드 이름. 함께 바뀐 경우 변경 후 = "<이름> (Status <Status 이름>와/과 함께 변경)" |
  | 금액 | `amount` | 금액(단위:원) | 원 콤마 숫자(반올림 없음, 예: 150,000,000) |
  | Expected Close | `expectedClose` | Expected Close | YYYY-MM-DD |
  | Owner | `owner` | Owner | 사용자 표기(퇴사자 "<이름>(퇴사)") |
  | 파트너 | `partner` | 파트너 | 활성 파트너 "<회사> <담당자>", 없으면 "없음" |
  | 고객 연락처 | `contact` | 고객 연락처 | "<회사> <담당자>" |
  | BANT | `bant` | BANT Label: <Budget·Authority·Need·Timeline> | Label 이름, 없으면 "선택 안 함" |
  | Deal Name | `other` | Deal Name | 그대로 |
  | Vendor | `other` | Vendor | Vendor 이름, 없으면 "선택 안 함" |
  | Solution | `other` | Solution | 그대로(빈 값은 "-") |
  | Users count | `other` | Users count | 숫자(0 포함) |
  | 견적 | `other` | 견적 | "<YES|NO|->[ (<제출일>)]" |
  | POC | `other` | POC | "<YES|ING|NO|->[ (<완료일>)]" |
  | 구매절차 | `other` | 구매절차 | 그대로(빈 값은 "-") |

  "함께 변경" 표기는 단일 변경·Action 등록에서 함께 바뀐 쪽에만 붙고, 폼 저장(두 값을 직접 보냄)에는 붙지 않는다. 대소문자만 바뀐 텍스트도 바뀐 것이다.

삭제 영향·삭제
- **DD-R22** `GET /deals/{code}/deletion-impact`는 로그인한 모든 역할이 부른다. 200 `{history_count, action_count, attachment_count, license_contract_count}` — 그 Deal의 이력 수(등록 항목 포함), Action 수, 첨부 수(계산 세부 AT), 계약 수(LC-R20)이며 다른 Deal의 건수는 섞이지 않는다. 없는 Deal 404(DD-R1).
- **DD-R23** `DELETE /deals/{code}?confirm_code=<입력값>`: `confirm_code` 쿼리는 필수이고 없으면 422 `request-validation`이다. 성공하면 204(본문 없음).
- **DD-R24** 삭제 판정 순서: user는 역할 가드 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(PL-R6) → `confirm_code` 누락 422 → 없는 Deal·형식이 틀린 code 404 → 삭제 권한(admin은 모든 Deal, sales는 자기가 Owner인 Deal만) 아니면 403 `forbidden` "본인 Deal 또는 admin만 삭제할 수 있습니다." → `confirm_code`가 Deal code와 **정확히**(대소문자 포함) 같지 않으면 422 `invalid-value` "Deal code가 일치하지 않습니다.". 거절되면 아무것도 지우지 않는다. 권한 판정이 확인 code보다 먼저라 다른 영업은 code가 틀려도 403이다.
- **DD-R25** 삭제는 물리 삭제다. Deal과 그 이력·Action·첨부 행·파트너 링크·BANT 선택(·라이선스 계약, LC)이 함께 지워진다. 연락처·BANT Label·코드·Vendor·사용자·파트너 미팅 기록(PA)은 남고, 남은 연락처·Label로 다시 Deal을 등록할 수 있다. 다른 Deal의 데이터는 그대로다.
- **DD-R26** 커밋한 뒤 운영 로그(INFO) 한 줄 `deal deleted code=<code> by=<사용자 id> at=<서버 시각 ISO>`를 남긴다(거절되면 없음). 저장 위치(IN)가 설정돼 있으면 커밋 뒤 `<저장 위치>/<deal code>` 폴더를 지우고(다른 Deal 폴더·저장 위치 루트는 남음, 계약 폴더는 LC-R26), 지우지 못하면 WARNING `deal files cleanup failed code=<code>`만 남기고 요청은 성공(204)이다. 저장 위치가 없으면 파일을 건드리지 않는다. 거절되거나 커밋이 실패하면 Deal과 파일 모두 남는다.

화면(frontend, `/deals/:dealCode`)
- **DD-R27** 화면 틀: 머리에 Deal 이름(h1)과 "← 목록" 링크(목록 주소는 DL), 쓰기 권한이 있으면 "삭제" 버튼(접근 이름 "Deal 삭제"). 그 아래 탭 목록(이름 "상세 탭") 3개 "Deal 상세", "Actions", "Deal History" 순서이고 기본은 "Deal 상세"다. 주소 `?tab=actions`·`?tab=history`로 탭을 열고, 모르는 값이면 Deal 상세다. 탭을 고르면 주소의 `tab`을 바꾸고 Deal 상세로 오면 `tab`을 지운다. Deal 상세 탭에만 Deal 정보 타일·고객·파트너·BANT 카드·첨부 패널(AT)이 있다. 알림(성공 문구, 닫기 가능, 다른 화면에서 `state.notice`로 넘어온 문구 포함)은 탭 패널 맨 위에 보인다. 읽는 동안 "불러오는 중…", Deal을 읽지 못하면(404 등) 서버 문구 오류 배너와 "Deal 목록으로" 링크만 보인다.
- **DD-R28** Deal 정보 타일(제목 h2 "Deal 정보") 행 순서: Deal code(읽기 전용 글자), Owner, Status(배지 + "N일째" — RK), Forecast(배지), 금액(단위:원), Expected Close, Next Action(텍스트·"Due <날짜>"·상태, 없으면 "없음", 경고 배지 — RK·NA), 최종 업데이트(상대 시각 — RK), Vendor(없으면 "—"), Solution, Users count, 견적(제출/미제출 + " (<날짜>)"), POC("<YES|ING|NO> · <완료|진행 중|하지 않음>" + 날짜), 구매절차(없으면 "—"), 등록일. Forecast 결과가 `won`이면 "Won으로 종결된 Deal입니다. 매출금액과 매출일은 확정 값이며, 필요하면 계속 수정할 수 있습니다.", `lost`면 "Lost로 종결된 Deal입니다. Forecast를 바꾸면 다시 진행 중으로 되돌릴 수 있습니다."를 보인다.
- **DD-R29** 카드: Deal 정보 아래 고객(h2 "고객")·파트너(h2 "파트너")·BANT(h2 "BANT") 순서. 고객·파트너 카드는 회사·담당자·직급·이메일·전화 5행(값 없으면 "—"), 파트너가 없으면 같은 5행이 모두 "—"이고 "파트너 없음" 같은 글자는 없다. 해제된 파트너가 있으면 접힌 "이전 파트너 이력 (N)" 안에 "<회사> <담당자> (<연결일> ~ <해제일>)"로 보인다. BANT 카드는 Budget·Authority·Need·Timeline 4행(Label 이름, 없으면 "—").
- **DD-R30** 역할별 화면: `canWrite`(admin·sales, PL-R36)면 값마다 클릭 편집 버튼(접근 이름 "<항목> 수정", 제목은 title "Deal 이름 수정")이 있고 별도 "수정" 링크는 없다. user는 같은 값을 글자로만 보고 편집 버튼·삭제 버튼·연락처 입력 버튼이 없다. 삭제 버튼은 `canDeleteDeal`(admin은 모두, sales는 자기가 Owner인 Deal만, user는 불가)일 때 활성이고, 아니면 비활성 + title "본인 Deal 또는 admin만 삭제할 수 있습니다."다(편집은 그대로 가능).
- **DD-R31** 인라인 편집 공통(`InlineEdit`): 값 버튼을 누르거나 Enter·Space로 편집을 열면 입력기에 포커스가 간다. 선택형(select, 자동완성 후보 선택)은 고르는 순간 저장하고, 입력형(텍스트·숫자·날짜·자동완성 직접 입력)은 Enter 또는 편집 영역 밖으로 포커스가 나갈 때 저장한다. 값이 그대로면 요청 없이 닫는다. Esc는 입력을 버리고 닫는다. 저장·검증 실패는 입력기 아래 오류 배너(PL-R37)로 보이고 편집을 유지한다(다시 고쳐 재시도). 저장 성공이면 닫고 알림을 보인다. 날짜 칸은 `DateInput`(넘기는 값 UI-R6, 달력 UI-R9)이며 덜 쳤거나 틀린 날짜는 저장하지 않고, 달력 버튼·숨은 날짜 칸으로 포커스가 옮겨 가는 것은 저장으로 보지 않는다.
- **DD-R32** 필드별 인라인 저장(`PATCH`, 검증 정본 DE): Deal 이름 — 앞뒤 공백 제거, 비면 "Deal Name을 입력하세요."(요청 없음), 알림 "Deal 이름이 변경되었습니다.". Owner — 사용자 선택(재직 sales 후보, 퇴사한 현재 Owner는 후보에 없음), 알림 "Owner가 변경되었습니다.". Vendor — "선택 안 함" + 등록 Vendor 목록, `vendor_id`만 보냄(Solution 유지), 같은 값이면 요청 없음, 알림 "Vendor가 변경되었습니다.". Solution — 공백 제거 뒤 비면 "Solution을 입력하세요.", `solution`만 보냄, 알림 "Solution이 변경되었습니다.". Users count — 비면 "Users count를 입력하세요.", 숫자만이 아니면 "Users count는 0 이상의 정수로 입력하세요."(0 허용), 알림 "Users count가 변경되었습니다.". 견적 제출여부(선택 안 함·YES·NO)·제출일, POC 여부(선택 안 함·YES·ING·NO)·완료일은 각각 따로 고치고 나머지 짝 값은 그대로 보내며 알림 "견적 제출여부/견적 제출일/POC 여부/POC 완료일이 변경되었습니다.". 구매절차 — 공백 제거, 알림 "구매절차가 변경되었습니다.". 서버 거절(예: 이름 50자 초과)은 서버 문구로 보인다.
- **DD-R33** BANT 인라인: 값을 누르면 그 구분 Label만 후보인 자동완성 입력(현재 Label 이름으로 시작, "새 Label" 같은 항목 없음)이 열린다. 후보를 고르면 즉시, 직접 입력은 Enter·포커스 이동으로 저장한다. 입력 → 선택 변환은 CL-R16(이름이 같은 Label이 있으면 그 id, 없으면 이름으로 보내 서버가 새 Label을 만듦, 비우면 선택 안 함). 요청은 4구분 모두를 보내되 다른 구분은 현재 선택 `{id}`(또는 null) 그대로다. 선택이 그대로면 요청 없음. 알림 "BANT <구분> Label이 변경되었습니다.".
- **DD-R34** 연락처 인라인(고객·파트너 카드): 회사명 버튼(접근 이름 "<고객|파트너> 회사명 수정")은 연락처 편집 세션(그룹 "<고객|파트너> 연락처 편집")을 연다 — 회사 자동완성(부분·대소문자 무시) → 다른 기존 회사를 고르면 담당자를 비우고 담당자 목록을 연다 → 담당자를 고르면 연락 정보를 채워 즉시 저장. 목록에 없는 회사를 입력하면 담당자 정보를 모두 비우고 "신규 <고객사|파트너>입니다. 담당자 정보를 입력하세요."를 보인다. 직접 입력은 Enter(회사명 칸에서는 담당자명 칸으로 이동)·세션 밖 포커스 이동으로 저장하고, 회사명·담당자명이 비면 저장하지 않고 칸 오류를 보인다. Esc는 세션 전체를 버린다. 담당자명 칸은 같은 회사 담당자 자동완성(고르면 그 연락 정보, 새 이름이면 직급·이메일·전화를 비운 신규 담당자). 직급·이메일·전화는 한 칸씩 고치며 형식 오류(예: 이메일)는 그 칸 문구로 막는다. 회사명·담당자명·이메일·전화에는 공백을 넣을 수 없어 입력 중 지우고 안내한다(CT 규칙). 그 연락처를 쓰는 Deal이 2건 이상이면 "이 연락처는 N개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다."를 보인다. 알림: 고객 "고객 연락처가 저장되었습니다.", 파트너 칸 수정 "파트너 연락처가 저장되었습니다.".
- **DD-R35** 파트너 추가·교체·제거: 파트너가 없으면 5행의 "—" 버튼(접근 이름 "파트너 <항목> 입력") 어느 것이든 세션을 열고 안내 "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.", 저장하면 "파트너가 추가되었습니다.". 파트너가 있을 때 회사명 세션의 안내는 "기존 활성 파트너(<회사> <담당자>)는 이력으로 남고 비활성이 됩니다."이고 다른 회사·담당자로 저장하면 "파트너가 교체되었습니다.". "파트너 제거" 버튼은 확인 대화상자(제목 "파트너 제거", 문구 "파트너 <회사> <담당자>을(를) 제거합니다. 제거한 파트너는 이전 파트너 이력에 남습니다.", 위험 버튼 "제거")를 거쳐 `partner: null`을 보내고 "파트너가 제거되었습니다."를 보인다. 실패하면 대화상자를 닫고 오류 배너를 보인다.
- **DD-R36** Status·Forecast 인라인(Deal 정보 타일): 선택 상자에서 다른 값을 고르면 화면이 서버와 같은 계획 함수(`planChange`, DD-R6)로 판단한다. 독립 변경은 바로 단일 변경을 보낸다. 종결이면 "매출 확정" 대화상자 — 안내 "Status가 '<계약완료 이름>'로, Forecast가 '<Won 이름>'으로 함께 변경됩니다. 실제 매출금액과 매출일을 입력해야 저장할 수 있습니다.", 칸 "매출금액(단위:원, 실제 값)"(현재 금액으로 미리 채움)·"매출일(실제 값)"(현재 Expected Close로 미리 채움, yyyymmdd 입력 가능), 금액이 유효하고 날짜가 맞을 때만 "확정"이 켜진다. 되돌림이면 "함께 바꿀 값 선택" 대화상자 — 라디오 선택지(코드 이름, Won 이탈은 계약완료 제외·기본 없음, Lost 되살리기는 현재 Status 기본, 계약완료 이탈은 Won 제외), 고르기 전에는 "확인"이 꺼져 있다. Won 이탈 안내 "Forecast를 '<값>'(으)로 바꾸면 <Won 이름> 상태가 해제되어 Status를 <계약완료 이름>(으)로 둘 수 없습니다. 어떤 Status로 바꿀까요?", Lost 이탈 "Forecast를 '<값>'(으)로 바꾸면 <Lost 이름> 상태가 해제됩니다. Status를 어떤 값으로 둘까요?", 계약완료 이탈 "Status를 '<값>'(으)로 바꾸면 <계약완료 이름>이/가 해제됩니다. Forecast를 어떤 값으로 바꿀까요?". "취소"·Esc는 아무것도 보내지 않고 값이 그대로다. 확정 뒤(Won 이탈이면 계약 처리 확인 LC를 거쳐) 단일 변경을 `resolution`과 함께 보내고, 알림은 서버 `notice`, 없으면 "<Status|Forecast>가 '<이름>'(으)로 변경되었습니다."다. Status 편집을 Esc·포커스 이동으로 닫으면 아무것도 바꾸지 않는다.
- **DD-R37** 금액·Expected Close 인라인: 금액 편집은 현재 원 값(콤마 포함, 반올림 없음)으로 시작하고 입력 중 콤마를 붙인다. 숫자가 아니거나 비면 "매출금액은 1원 이상의 정수를 입력하세요.", 2^53−1을 넘으면 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요."로 막는다(요청 없음). 같은 금액이면 요청 없이 닫는다. 저장 알림 "금액이 변경되었습니다.". Expected Close는 비우면 "Expected Close를 입력하세요."(요청 없음), 저장 알림 "Expected Close가 변경되었습니다.". 둘 다 단일 변경으로 보내며 이력에 남는다.
- **DD-R38** Deal History 탭: 툴바에 "변경 대상" 선택(전체 + 12구분 이름: Deal 등록·Status·Forecast·금액·Expected Close·Owner·파트너·고객 연락처·BANT Label·Action·첨부 파일·기타)과 안내 "Action 수정·삭제와 첨부 파일 변경도 이 이력에 기록됩니다.". 표(이름 "Deal History") 머리글 변경 시각·변경자·변경 대상·변경 전·변경 후, 서버 순서(최신순) 그대로, 변경자는 사용자 표기(퇴사자 "<이름>(퇴사)"), 빈 변경 전·후는 "—". 20행씩 페이지(페이저)이고 필터를 바꾸면 첫 페이지로 간다. 결과가 없으면 "변경 이력이 없습니다.". 읽기 전용(편집 버튼 없음).
- **DD-R39** 삭제 확인 대화상자(제목 "Deal 삭제"): 문구 "삭제하면 Deal History <N>건, Action <N>건, 첨부 파일 <N>개, 라이선스 계약 <N>건과 파일 저장 디렉터리가 함께 삭제되며 복구할 수 없습니다."(건수를 읽기 전에는 "삭제 대상 건수를 확인하는 중입니다. 삭제하면 Deal History, Action, 첨부 파일, 라이선스 계약이 함께 삭제되며 복구할 수 없습니다.", 파트너 미팅은 언급하지 않음), "계속하려면 Deal code <code>를 입력하세요."와 칸 "Deal code 확인". 입력이 Deal code와 정확히 같을 때만 위험 버튼 "삭제"가 켜지고, 입력이 있는데 다르면 "Deal code가 일치하지 않습니다."를 보인다(소문자 불가). 삭제가 성공하면 즉시 상세를 떠나 목록 주소로 가며 알림 "Deal <code>이(가) 삭제되었습니다."를 넘긴다. 실패하면 서버 문구 오류 배너를 대화상자 안에 보인다. "취소"·Esc는 요청 없이 닫는다.
- **DD-R40** 게이트웨이(`gateway/http`): `deals.get` = `GET /deals/{code}`(파트너 이력 포함 상세로 변환), `deals.impact` = `GET /deals/{code}/deletion-impact`(`historyCount`·`actionCount`·`attachmentCount`·`licenseContractCount`), `history.list` = `GET /deals/{code}/history`(구분이 없으면 쿼리 없이, 있으면 `category` 그대로, 서버 순서 유지), `deals.applyChange` = `POST /deals/{code}/changes`(필드 `statusKey`·`forecastKey`·`revenueAmount`·`revenueDate` → snake_case, resolution 답 → snake_case, 응답 `co_changed` → `coChanged[{field, from, to}]`, `notice`), `deals.remove` = `DELETE /deals/{code}?confirm_code=<입력 그대로>`(204 성공). 오류는 PL-R39로 바꾼다.

### 2.4 상태와 전이

Status·Forecast 조합의 상태(불변식 DD-R5를 지키는 것만 존재):

| 현재 | 행동(단일 변경) | 다음 | 필요한 답 |
| --- | --- | --- | --- |
| 진행(계약완료 아님, Won·Lost 아님) | Status → 계약완료 또는 Forecast → Won | 종결(계약완료 + Won) | 매출금액·매출일 |
| 진행 | Forecast → Lost | Lost(Status 그대로) | 없음 |
| 진행 | 그 밖 Status·Forecast 변경 | 진행 | 없음 |
| 종결 | Forecast → Won 아닌 값(Lost 포함) | 진행 또는 Lost | Status(계약완료 제외, 기본 없음) |
| 종결 | Status → 계약완료 아닌 값 | 진행 또는 Lost | Forecast(Won 제외) |
| Lost | Forecast → Won | 종결 | 매출금액·매출일 |
| Lost | Forecast → Won 아닌 값 | 진행 | Status(계약완료 제외, 기본 = 현재) |
| Lost | Status → 계약완료 | 종결 | 매출금액·매출일 |
| Lost | Status → 그 밖 값 | Lost | 없음 |
| (모든 상태) | 삭제 | (없음) | 확인 code |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /deals/{code}`, `GET /deals/{code}/history`, `GET /deals/{code}/deletion-impact` | 401 | 가능 | 가능 | 가능 |
| `POST /deals/{code}/changes` | 401 | 403 읽기 전용 문구 | 모든 Deal 가능 | 모든 Deal 가능 |
| `DELETE /deals/{code}` | 401 | 403 읽기 전용 문구 | 자기가 Owner인 Deal만(아니면 403 "본인 Deal 또는 admin만 삭제할 수 있습니다.") | 모든 Deal 가능 |
| 화면 `/deals/:dealCode` 보기 | `/login`으로 | 보기만(편집·삭제 버튼 없음) | 편집 가능, 삭제는 본인 Deal만 활성 | 편집·삭제 가능 |

상세·이력·삭제 영향은 업무 조회, 단일 변경·삭제는 업무 쓰기(PL-R2, PL-R6, CSRF PL-R9)다. 거절된 요청은 아무것도 바꾸지 않는다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/deals/{code}` | — | 200 `DealDetailResponse`(DD-R2) | 401, 404 |
| POST `/deals/{code}/changes` | `DealChangeRequest` `{change: CodeChange\|AmountChange\|DateChange, resolution?: ResolutionRequest\|null, delete_license_contracts?: bool}` | 200 `DealChangeResponse` `{deal, co_changed: [{field, from, to}], notice: str\|null}` | 401, 403, 404, 409 `invalid-state`(LC-R8), 422 `invalid-value`·`request-validation` |
| GET `/deals/{code}/history` | query `category?`(12값) | 200 `HistoryEntryResponse[]` | 401, 404, 422 |
| GET `/deals/{code}/deletion-impact` | — | 200 `DeletionImpactResponse` `{history_count, action_count, attachment_count, license_contract_count}` | 401, 404 |
| DELETE `/deals/{code}` | query `confirm_code`(필수) | 204 | 401, 403, 404, 422 `invalid-value`·`request-validation` |

- `CodeChange` = `{field: "status_key"|"forecast_key", value: str}`, `AmountChange` = `{field: "revenue_amount", value: int}`, `DateChange` = `{field: "revenue_date", value: date}`(`field`로 구분). `ResolutionRequest` = `{revenue_amount?: int|null, revenue_date?: date|null, status_key?: str|null, forecast_key?: str|null}`. 모든 본문은 모르는 필드를 거부한다.
- `{code}` 형식은 DD-R1(형식 오류도 404).

### 2.7 화면 동작

DD-R27~DD-R40.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 없는 Deal·형식이 틀린 code | 404 `not-found` | Deal을 찾을 수 없습니다. |
| Status·Forecast 불일치(폼 저장 등) | 422 `invalid-value` | Status와 Forecast의 동기화가 맞지 않습니다. |
| 종결인데 매출금액·매출일 없음·틀림 | 422 `invalid-value` | Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다. |
| 되돌림인데 함께 바꿀 값 없음·선택지 밖 | 422 `invalid-value` | 함께 바꿀 값을 선택하세요. |
| 없는 Status·Forecast key | 422 `invalid-value` | 존재하지 않는 코드입니다. |
| 금액 범위 밖 | 422 `invalid-value` | 매출금액은 1원 이상의 정수로 입력하세요. |
| 요청 형식 오류(필드·형식·모르는 키·`confirm_code` 누락·`category` 값) | 422 `request-validation` | 요청 형식이 올바르지 않습니다 |
| user의 변경·삭제 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |
| 다른 Owner Deal 삭제(sales) | 403 `forbidden` | 본인 Deal 또는 admin만 삭제할 수 있습니다. |
| 삭제 확인 code 불일치 | 422 `invalid-value` | Deal code가 일치하지 않습니다. |
| 발급 계약 있는 Deal의 Won 이탈 | 409 `invalid-state` | LC-R8 문구 |

화면 문구: DD-R27~DD-R39. 서버 문구 표시는 PL-R37.

## 3. Business use case

### DD-UC1 Deal 상세 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, Deal 목록 등에서 Deal을 고름
- 기본 흐름: `/deals/<code>` → `GET /deals/{code}` → Deal 정보 타일·카드·첨부를 Deal 상세 탭에 보인다(DD-R2~R4, DD-R27~R30)
- 대안: 주소 `?tab=actions`·`?tab=history`로 다른 탭을 바로 연다
- 예외: 없는 Deal·형식이 틀린 code → 오류 배너와 "Deal 목록으로"(DD-R1)
- 결과: 현재 값, 퇴사 Owner 표기, 활성·이전 파트너가 보인다

### DD-UC2 값 하나를 그 자리에서 고치기
- 행위자: sales·admin
- 사전 조건: Deal 상세 탭
- 기본 흐름: 값 클릭 → 입력·선택 → 저장(선택 즉시 또는 Enter·포커스 이동) → 성공 알림, 이력 기록(DD-R31~R35, 저장 규칙 DE, 이력 DD-R20·R21)
- 대안: Esc로 취소, 같은 값이면 요청 없음
- 예외: 화면 검증 문구 또는 서버 거절 문구를 보이고 편집 유지
- 결과: 그 값만 바뀌고 이력 1건(BANT·연락처는 해당 규칙)

### DD-UC3 Status·Forecast 바꾸기(동기화 포함)
- 행위자: sales·admin
- 사전 조건: Deal 상세 탭(또는 목록 인라인 — 화면은 DL, API는 이 문서)
- 기본 흐름: Status·Forecast 선택 → 계획 판단 → (필요하면 매출 확정·함께 바꿀 값 선택 대화상자) → `POST /deals/{code}/changes` → 200, 알림(DD-R5~R15, DD-R36)
- 대안: 독립 변경은 대화상자 없이 바로 저장, 같은 값은 변경 없음
- 예외: 매출 없음·선택 없음 422, 없는 코드 422, 발급 계약 있는 Won 이탈 409(LC), user 403, 없는 Deal 404
- 결과: 불변식을 지킨 새 Status·Forecast, 함께 바뀐 값 표기가 붙은 이력

### DD-UC4 금액·Expected Close 바꾸기
- 행위자: sales·admin
- 기본 흐름: 금액 또는 Expected Close 클릭 → 입력 → 저장 → 단일 변경 200, 알림, 이력(DD-R13, DD-R37)
- 예외: 금액 범위 밖 422(화면은 미리 막음), 빈 Expected Close는 화면이 막음
- 결과: 그 값만 바뀌고 Status·Forecast는 그대로

### DD-UC5 Deal History 보기
- 행위자: 로그인한 모든 역할
- 기본 흐름: Deal History 탭 → `GET /deals/{code}/history` → 최신순 표, 20건씩(DD-R17, DD-R38)
- 대안: 변경 대상으로 거른다
- 예외: 없는 Deal 404, 잘못된 구분 422
- 결과: 누가 언제 무엇을 어떻게 바꿨는지

### DD-UC6 Deal 삭제
- 행위자: Owner 본인 sales, admin
- 사전 조건: 삭제 버튼 활성(DD-R30)
- 기본 흐름: 삭제 → 영향 건수 확인(`GET /deletion-impact`) → Deal code 입력 → 삭제(`DELETE ?confirm_code=`) → 204 → 목록으로 이동, 알림(DD-R22~R26, DD-R39)
- 대안: 취소·Esc
- 예외: 다른 영업 403, user 403, code 불일치 422, 없는 Deal 404
- 결과: Deal과 이력·Action·첨부·파트너 링크·BANT 선택(·계약)이 지워지고 연락처·Label·파트너 미팅은 남는다

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales, Owner), LEE(sales, Owner 아님), VIEWER(user). 기본 Deal 예: Status 기회발굴(prospecting)·Forecast Pipeline, 금액 150,000,000, Expected Close 2026-06-30. 종결 Deal 예: 계약완료·Won, 금액 777, Expected Close 2026-09-01. 매출 답 예: 900,000,000·2026-10-20. backend 케이스는 기본 코드(CD-R2)를 넣은 Fake UoW로 유스케이스를 부르는 단위 테스트(application·domain)와, Fake 유스케이스로 라우터를 부르는 web 단위 테스트다. frontend 케이스는 Fake 게이트웨이(시드 Deal·코드·사용자)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| DD-001 | 어떤 역할이든 Deal 상세를 읽으면 문서화된 필드와 Owner·고객·파트너가 돌아온다 | DD-R2, DD-UC1 | backend | `application/test_get_deal.py::test_the_view_has_the_deal_owner_customer_and_partner_contacts`<br>`web/test_deal_detail_routes.py::test_every_role_reads_the_detail_with_the_documented_fields` |
| DD-002 | 상세 응답에는 폐지된 필드가 없다 | DD-R2 | backend | `web/test_deal_detail_routes.py::test_the_detail_and_registration_responses_have_no_retired_fields` |
| DD-003 | 퇴사한 Owner의 Deal도 Owner가 퇴사 표기로 돌아온다 | DD-R3, DD-UC1 | backend | `application/test_get_deal.py::test_the_owner_of_a_resigned_user_is_still_resolved` |
| DD-004 | 교체된 파트너는 비활성 링크와 파트너 이력에 남고 이력은 최근 연결 순이다 | DD-R4, DD-UC1 | backend | `application/test_get_deal.py::test_the_partner_contacts_include_replaced_partners` |
| DD-005 | 없는 code와 형식이 틀린 code의 상세는 같은 404다 | DD-R1, DD-UC1 | backend | `application/test_get_deal.py::test_an_unknown_or_malformed_code_is_not_found`<br>`web/test_deal_detail_routes.py::test_an_unknown_or_malformed_code_detail_is_the_same_404` |
| DD-006 | Deal code는 8자리-대문자·숫자 4자리 전체가 맞을 때만 형식이 맞다 | DD-R1 | backend | `domain/test_deal_code.py` |
| DD-007 | 폐지된 Deal 경로는 404 또는 405다 | DD-R16 | backend | `web/test_deal_detail_routes.py::test_a_retired_deal_route_is_gone` |
| DD-008 | 계약완료와 Won은 함께이거나 둘 다 아니어야 일관적이다 | DD-R5 | backend | `domain/test_deal_entity.py::test_an_inconsistent_status_and_forecast_is_rejected`<br>`domain/test_deal_sync_consistency.py` |
| DD-009 | 폼 저장에서 계약완료·Won 중 한쪽만 보내면 동기화 문구의 422이고 값이 그대로다 | DD-R5 | backend | `application/test_update_deal_owner_and_sync.py::test_closing_requires_both_values_together`<br>`application/test_update_deal_owner_and_sync.py::test_reopening_requires_both_values_together`<br>`domain/test_deal_entity.py::test_an_inconsistent_final_sync_is_rejected_and_nothing_changes` |
| DD-010 | 폼 저장으로 두 값을 함께 보내면 종결되고 Status·Forecast 이력이 함께 변경 표기 없이 남는다 | DD-R5, DD-R21 | backend | `application/test_update_deal_owner_and_sync.py::test_closing_with_both_values_is_logged_without_a_co_change_note`<br>`domain/test_deal_history_diff.py::test_closing_a_deal_records_status_then_forecast_without_a_co_change_note` |
| DD-011 | 종결된 Deal도 폼으로 수정되고 되돌려도 금액·Expected Close는 그대로다 | DD-R5 | backend | `application/test_update_deal_owner_and_sync.py::test_a_closed_deal_can_still_be_edited_and_reopened_keeping_amount_and_date`<br>`domain/test_deal_entity.py::test_closing_and_reopening_keeps_the_amount_and_the_date` |
| DD-012 | 계약완료로 바꾸면서 매출을 주지 않으면 422이고 값·이력이 그대로다 | DD-R7, DD-UC3 | backend | `application/test_apply_deal_change.py::test_closing_without_a_valid_amount_and_date_is_rejected_and_changes_nothing`<br>`domain/test_deal_sync_finalize.py::test_closing_without_a_valid_amount_and_date_is_rejected` |
| DD-013 | 계약완료로 바꾸면 Forecast도 Won이 되고 매출이 저장되며 이력 4건과 알림이 생긴다 | DD-R6, DD-R7, DD-R14, DD-R21, DD-UC3 | backend | `application/test_apply_deal_change.py::test_status_to_contract_completed_also_sets_won_and_saves_the_revenue`<br>`application/test_apply_deal_change.py::test_the_history_marks_the_value_that_changed_together`<br>`domain/test_deal_sync_finalize.py::test_closing_applies_both_values_the_revenue_and_reports_the_co_change`<br>`domain/test_deal_sync_plan.py::test_status_to_contract_completed_also_sets_won_and_needs_revenue`<br>`web/test_deal_detail_routes.py::test_a_single_change_returns_exactly_the_documented_keys` |
| DD-014 | Won으로 바꾸면 Status도 계약완료가 되고 이력의 Status에 함께 변경이 표기된다 | DD-R6, DD-R7, DD-R21, DD-UC3 | backend | `application/test_apply_deal_change.py::test_forecast_to_won_also_sets_contract_completed_and_saves_the_revenue`<br>`application/test_apply_deal_change.py::test_the_history_from_the_forecast_side_marks_the_status`<br>`domain/test_deal_sync_finalize.py::test_closing_from_the_forecast_side_reports_the_status_as_the_co_change`<br>`domain/test_deal_sync_plan.py::test_forecast_to_won_also_sets_contract_completed_and_needs_revenue` |
| DD-015 | Lost에서 Won으로 바꾸는 것도 종결이라 매출이 필요하다 | DD-R6, DD-R7, DD-UC3 | backend | `application/test_apply_deal_change.py::test_lost_to_won_is_a_closing_too`<br>`domain/test_deal_sync_plan.py::test_lost_to_won_needs_revenue_too` |
| DD-016 | 종결 답의 금액이 0·음수·2^53이면 매출 문구의 422다 | DD-R7, DD-UC3 | backend | `application/test_apply_deal_change.py::test_closing_without_a_valid_amount_and_date_is_rejected_and_changes_nothing`<br>`domain/test_deal_sync_finalize.py::test_closing_without_a_valid_amount_and_date_is_rejected` |
| DD-017 | Won에서 다른 Forecast로 가려면 계약완료가 아닌 Status를 골라야 하고 금액·매출일은 그대로다 | DD-R6, DD-R8, DD-UC3 | backend | `application/test_apply_deal_change.py::test_leaving_won_needs_a_status_other_than_contract_completed`<br>`application/test_apply_deal_change.py::test_leaving_won_changes_the_chosen_status_and_keeps_amount_and_date`<br>`domain/test_deal_sync_finalize.py::test_reopening_a_won_deal_requires_a_status_from_the_options`<br>`domain/test_deal_sync_finalize.py::test_reopening_a_won_deal_changes_the_status_together`<br>`domain/test_deal_sync_plan.py::test_leaving_won_asks_for_a_status_without_a_default` |
| DD-018 | Won에서 Lost로 가도 Status를 기본값 없이 골라야 한다 | DD-R6, DD-UC3 | backend | `domain/test_deal_sync_plan.py::test_won_to_lost_also_asks_for_a_status` |
| DD-019 | 계약완료에서 이전 단계로 가려면 Won이 아닌 Forecast를 골라야 한다 | DD-R6, DD-R8, DD-UC3 | backend | `application/test_apply_deal_change.py::test_leaving_contract_completed_needs_a_forecast_other_than_won`<br>`application/test_apply_deal_change.py::test_leaving_contract_completed_changes_the_chosen_forecast`<br>`domain/test_deal_sync_finalize.py::test_leaving_contract_completed_requires_a_forecast_other_than_won`<br>`domain/test_deal_sync_finalize.py::test_leaving_contract_completed_changes_the_forecast_together`<br>`domain/test_deal_sync_plan.py::test_leaving_contract_completed_asks_for_a_forecast_without_won` |
| DD-020 | Lost에서 되돌리면 Status를 묻되 기본은 현재 Status이고 그대로 고르면 함께 바뀐 값이 없다 | DD-R6, DD-R8, DD-UC3 | backend | `application/test_apply_deal_change.py::test_leaving_lost_asks_for_a_status_but_the_current_one_is_a_valid_answer`<br>`domain/test_deal_sync_finalize.py::test_picking_the_current_status_again_when_leaving_lost_changes_nothing_together`<br>`domain/test_deal_sync_plan.py::test_leaving_lost_asks_for_a_status_defaulting_to_the_current_one` |
| DD-021 | Won이 아닌 Deal을 Lost로 바꾸면 Status는 그대로이고 함께 바뀐 값·알림이 없다 | DD-R6, DD-R9, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_forecast_to_lost_keeps_the_status`<br>`domain/test_deal_sync_plan.py::test_forecast_to_lost_keeps_the_status`<br>`domain/test_deal_sync_plan.py::test_other_changes_are_independent` |
| DD-022 | 독립 변경은 함께 보낸 답을 무시한다 | DD-R9, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_a_plain_status_change_ignores_a_resolution`<br>`domain/test_deal_sync_finalize.py::test_an_independent_change_ignores_the_resolution` |
| DD-023 | 같은 값으로 바꾸면 200이지만 이력과 수정 시각이 그대로다 | DD-R14, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_the_same_value_changes_nothing_and_keeps_the_update_time`<br>`application/test_apply_deal_change_values.py::test_the_same_amount_changes_nothing`<br>`domain/test_deal_sync_finalize.py::test_the_same_value_changes_nothing`<br>`domain/test_deal_sync_plan.py::test_the_same_value_is_an_independent_change_with_an_empty_patch` |
| DD-024 | 실제로 바꾸면 수정 시각이 서버 시각이 되고 응답 Deal에 새 값이 있다 | DD-R14, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_a_real_change_moves_the_update_time_to_now`<br>`application/test_apply_deal_change_independent.py::test_the_result_view_has_the_new_values` |
| DD-025 | 선택지는 코드 목록 순서이고 이름을 바꾼 코드도 key로 같은 규칙이며 알림은 새 이름이다 | DD-R6, DD-R10 | backend | `domain/test_deal_sync_finalize.py::test_the_notice_uses_the_current_code_names_and_their_josa`<br>`domain/test_deal_sync_plan.py::test_the_status_options_follow_the_catalog_order`<br>`domain/test_deal_sync_plan.py::test_renamed_codes_do_not_change_the_rules_because_they_work_on_keys` |
| DD-026 | 없는 Status·Forecast key로 바꾸면 422 "존재하지 않는 코드입니다."이고 값이 그대로다 | DD-R12, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_an_unknown_code_is_rejected` |
| DD-027 | 금액을 바꾸면 저장되고 이력에 원 콤마 숫자로 남는다 | DD-R13, DD-R21, DD-UC4 | backend | `application/test_apply_deal_change_values.py::test_changing_the_amount_saves_it_and_logs_the_formatted_amounts`<br>`application/test_apply_deal_change_values.py::test_a_single_change_succeeds_on_a_legacy_deal_whose_solution_is_empty`<br>`domain/test_deal_history_diff.py::test_amount_is_written_in_won_under_unit_target`<br>`domain/test_deal_history_diff.py::test_small_amount_change_is_recorded_without_rounding` |
| DD-028 | 금액 0·-1·2^53은 422이고 1과 2^53−1은 저장된다 | DD-R13, DD-UC4 | backend | `application/test_apply_deal_change_values.py::test_an_invalid_amount_is_rejected_and_nothing_changes`<br>`application/test_apply_deal_change_values.py::test_the_amount_boundaries_are_accepted`<br>`web/test_deal_change_request.py::test_amount_range_is_left_to_the_domain` |
| DD-029 | Expected Close를 바꾸면 저장되고 이력에 YYYY-MM-DD로 남는다 | DD-R13, DD-R21, DD-UC4 | backend | `application/test_apply_deal_change_values.py::test_changing_the_expected_close_saves_it_and_logs_the_dates`<br>`domain/test_deal_history_diff.py::test_expected_close_is_written_as_an_iso_date` |
| DD-030 | 종결된 Deal도 금액·Expected Close를 하나씩 바꿀 수 있고 Status·Forecast는 그대로다 | DD-R13, DD-UC4 | backend | `application/test_apply_deal_change_values.py::test_a_closed_deal_can_change_its_amount_and_date` |
| DD-031 | 단일 변경 요청 형식이 틀리면 422 request-validation이다 | DD-R11 | backend | `web/test_deal_change_request.py`<br>`web/test_deal_detail_routes.py::test_a_malformed_single_change_request_is_a_422_request_validation`<br>`web/test_deal_detail_routes.py::test_users_cannot_be_changed_through_a_single_change` |
| DD-032 | Owner가 아닌 영업도, 퇴사한 Owner의 Deal도 바꿀 수 있고 이력 변경자는 요청자다 | DD-R15, DD-UC3 | backend | `application/test_apply_deal_change_independent.py::test_a_deal_of_a_resigned_owner_can_still_be_changed`<br>`application/test_apply_deal_change_independent.py::test_another_sales_user_may_change_the_deal_and_is_the_history_author` |
| DD-033 | user의 단일 변경은 403, 미인증은 401이다 | DD-R15 | backend | `web/test_deal_detail_routes.py::test_a_read_only_user_and_an_anonymous_visitor_cannot_change_a_deal`<br>`web/test_deal_detail_routes.py::test_an_anonymous_visitor_is_unauthenticated_on_every_deal_route` |
| DD-034 | 없는 Deal·형식이 틀린 code의 단일 변경은 404다 | DD-R1, DD-R15 | backend | `application/test_apply_deal_change_independent.py::test_an_unknown_or_malformed_code_is_not_found`<br>`web/test_deal_detail_routes.py::test_a_single_change_of_an_unknown_deal_is_not_found` |
| DD-035 | 이력은 최신순이고 같은 시각이면 나중에 기록한 것이 위다 | DD-R17, DD-UC5 | backend | `application/test_list_deal_history.py::test_entries_are_listed_newest_first`<br>`application/test_list_deal_history.py::test_entries_of_the_same_moment_show_the_later_record_first`<br>`repositories/test_deal_history_repository_contract.py::test_entries_are_listed_newest_first`<br>`repositories/test_deal_history_repository_contract.py::test_entries_of_the_same_moment_show_the_later_saved_one_first` |
| DD-036 | 구분을 주면 그 구분의 이력만 돌려준다 | DD-R17, DD-UC5 | backend | `application/test_list_deal_history.py::test_the_category_filter_keeps_only_that_category`<br>`repositories/test_deal_history_repository_contract.py::test_the_category_filter_keeps_only_that_category` |
| DD-037 | 이력 항목에는 변경자가 있고 퇴사자도 퇴사 표기로 나온다 | DD-R17, DD-UC5 | backend | `application/test_list_deal_history.py::test_each_entry_carries_its_author`<br>`application/test_list_deal_history.py::test_the_author_of_a_resigned_user_is_still_shown`<br>`repositories/test_deal_history_repository_contract.py::test_a_resigned_author_keeps_the_entry` |
| DD-038 | 없는 Deal의 이력은 404, 모르는 구분은 422다 | DD-R1, DD-R17, DD-UC5 | backend | `application/test_list_deal_history.py::test_an_unknown_deal_is_not_found`<br>`web/test_deal_detail_routes.py::test_the_history_of_an_unknown_deal_is_not_found`<br>`web/test_deal_detail_routes.py::test_an_unknown_history_category_is_a_422_request_validation` |
| DD-039 | 어떤 역할이든 이력을 읽는다 | DD-R17, DD-UC5 | backend | `web/test_deal_detail_routes.py::test_every_role_reads_the_history` |
| DD-040 | 이력 구분은 정확히 12값이다 | DD-R17 | backend | `domain/test_deal_history_values.py::test_history_categories_are_exactly_the_twelve_frontend_values`<br>`domain/test_deal_history_values.py::test_each_frontend_category_value_is_a_member` |
| DD-041 | Deal을 등록하면 "Deal 등록" 이력 1건이 남는다 | DD-R19 | backend | `domain/test_deal_history_values.py::test_created_history_is_the_registration_entry`, `application/test_register_deal.py` |
| DD-042 | 바뀐 것이 없으면 이력이 없고 바뀐 필드마다 고정 순서로 1건씩 남는다 | DD-R20 | backend | `domain/test_deal_history_diff.py` |
| DD-043 | Owner·파트너·고객 연락처 이력은 사용자·연락처 표기로 남는다 | DD-R21 | backend | `domain/test_deal_history_diff.py` |
| DD-044 | BANT 이력은 구분마다 1건이고 비우면 "선택 안 함"이다 | DD-R21 | backend | `domain/test_deal_history_diff.py::test_bant_changes_are_written_per_category_in_category_order`<br>`domain/test_deal_history_diff.py::test_clearing_a_bant_label_is_written_as_not_selected` |
| DD-045 | 기타 필드 이력은 필드 이름이 대상이고 정해진 표기로 남는다 | DD-R21 | backend | `domain/test_deal_history_diff.py` |
| DD-046 | 긴 대상·값은 300자·1000자로 잘리고 말줄임표가 붙는다 | DD-R20 | backend | `domain/test_deal_history_values.py::test_a_long_target_is_clipped_to_300_code_points_with_an_ellipsis`<br>`domain/test_deal_history_values.py::test_long_before_and_after_values_are_clipped_to_1000_code_points` |
| DD-047 | 삭제 영향은 그 Deal의 이력·Action·첨부·계약 건수다 | DD-R22, DD-UC6 | backend | `application/test_deal_deletion_impact.py::test_the_impact_counts_the_history_and_actions_that_would_be_deleted`<br>`application/test_deal_deletion_impact.py::test_the_impact_counts_history_actions_attachments_and_contracts_only`<br>`repositories/test_deal_deletion_impact_contract.py`<br>`web/test_deal_detail_routes.py::test_the_deletion_impact_is_readable_by_every_role_and_has_four_counts`<br>`web/test_deal_detail_routes.py::test_an_anonymous_visitor_is_unauthenticated_on_every_deal_route` |
| DD-048 | 새 Deal의 삭제 영향은 등록 이력 1건뿐이고 다른 Deal 건수는 섞이지 않는다 | DD-R22, DD-UC6 | backend | `application/test_deal_deletion_impact.py::test_a_new_deal_has_only_its_registration_entry`<br>`application/test_deal_deletion_impact.py::test_the_impact_of_another_deal_is_not_counted`<br>`repositories/test_deal_deletion_impact_contract.py::test_other_deals_are_not_counted` |
| DD-049 | 없는 Deal·형식이 틀린 code의 삭제 영향은 404다 | DD-R1, DD-R22 | backend | `application/test_deal_deletion_impact.py::test_the_impact_of_an_unknown_or_malformed_code_is_not_found`<br>`repositories/test_deal_deletion_impact_contract.py::test_an_unknown_deal_is_not_found`<br>`web/test_deal_detail_routes.py::test_the_deletion_impact_of_an_unknown_deal_is_not_found` |
| DD-050 | Owner 영업이 code를 정확히 입력하면 204이고 Deal이 사라진다 | DD-R23, DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_the_owner_deletes_with_the_matching_code`<br>`application/test_delete_deal.py::test_the_deletion_is_committed`<br>`domain/test_deal_entity.py::test_the_owner_sales_user_can_delete`<br>`domain/test_deal_entity.py::test_the_confirmation_code_must_match_exactly`<br>`domain/test_deal_policy.py::test_sales_can_delete_only_a_deal_they_own`<br>`repositories/test_deal_repository_delete_contract.py::test_deleting_removes_the_deal_and_frees_the_code`<br>`web/test_deal_detail_routes.py::test_the_owner_deletes_the_deal_with_the_matching_code` |
| DD-051 | admin은 다른 Owner의 Deal도 지운다 | DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_an_admin_deletes_a_deal_of_another_owner`<br>`domain/test_deal_entity.py::test_admin_can_delete_a_deal_of_another_owner`<br>`domain/test_deal_policy.py::test_admin_can_delete_any_deal`<br>`web/test_deal_detail_routes.py::test_an_admin_deletes_a_deal_of_another_owner` |
| DD-052 | 다른 영업은 확인 code가 틀려도 403이 먼저이고 Deal은 남는다 | DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_another_sales_user_is_forbidden_even_with_a_wrong_confirmation`<br>`domain/test_deal_entity.py::test_another_sales_user_is_forbidden`<br>`domain/test_deal_policy.py::test_sales_can_delete_only_a_deal_they_own`<br>`web/test_deal_detail_routes.py::test_another_sales_user_is_forbidden_before_the_confirmation_code_is_checked` |
| DD-053 | user의 삭제는 읽기 전용 문구의 403이고 Deal은 남는다 | DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_a_read_only_user_is_forbidden`<br>`domain/test_deal_entity.py::test_a_read_only_user_is_forbidden_even_with_the_owners_id`<br>`domain/test_deal_policy.py::test_a_read_only_user_can_never_delete_even_the_same_id`<br>`web/test_deal_detail_routes.py::test_a_read_only_user_cannot_delete_and_the_deal_stays` |
| DD-054 | 확인 code가 정확히 같지 않으면 422이고 Deal은 남는다 | DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_a_wrong_confirmation_is_rejected_and_nothing_is_deleted`<br>`application/test_delete_deal.py::test_the_confirmation_is_compared_exactly`<br>`domain/test_deal_entity.py::test_a_different_confirmation_text_is_rejected`<br>`domain/test_deal_entity.py::test_a_mismatch_is_a_value_error_for_the_422_mapping`<br>`web/test_deal_detail_routes.py::test_a_mismatched_confirmation_code_is_a_422_and_the_deal_stays` |
| DD-055 | confirm_code가 없으면 422 request-validation이다 | DD-R23, DD-UC6 | backend | `web/test_deal_detail_routes.py::test_the_confirmation_code_query_is_required` |
| DD-056 | 없는 Deal·형식이 틀린 code는 확인 code가 틀려도 404다 | DD-R1, DD-R24, DD-UC6 | backend | `application/test_delete_deal.py::test_an_unknown_deal_is_not_found_before_anything_else`<br>`application/test_delete_deal.py::test_a_malformed_code_is_not_found`<br>`web/test_deal_detail_routes.py::test_deleting_an_unknown_deal_is_not_found_even_with_a_wrong_confirmation` |
| DD-057 | 삭제하면 이력·Action·파트너 링크가 함께 지워지고 연락처·Label·사용자·파트너 미팅은 남아 다시 쓸 수 있다 | DD-R25, DD-UC6 | backend | `application/test_delete_deal.py`<br>`repositories/test_deal_repository_delete_contract.py::test_history_actions_links_and_labels_go_with_the_deal`<br>`repositories/test_deal_repository_delete_contract.py::test_contacts_labels_and_users_stay` |
| DD-058 | 삭제해도 다른 Deal의 데이터는 그대로다 | DD-R25, DD-UC6 | backend | `application/test_delete_deal.py::test_other_deals_are_untouched`<br>`repositories/test_deal_repository_delete_contract.py::test_other_deals_and_their_data_are_untouched` |
| DD-059 | 삭제는 커밋 뒤 운영 로그 한 줄을 남기고 거절되면 남기지 않는다 | DD-R26, DD-UC6 | backend | `application/test_delete_deal.py::test_one_info_line_with_code_user_and_time_is_written_after_the_commit`<br>`application/test_delete_deal.py::test_nothing_is_logged_when_the_deletion_is_refused` |
| DD-060 | 저장 위치가 있으면 커밋 뒤 그 Deal 폴더만 지우고 없으면 파일을 건드리지 않는다 | DD-R26, DD-UC6 | backend | `application/test_delete_deal_attachments.py` |
| DD-061 | 폴더를 지우지 못해도 Deal은 지워지고, 거절·커밋 실패면 Deal과 파일이 남는다 | DD-R26, DD-UC6 | backend | `application/test_delete_deal_attachments.py` |
| DD-062 | 화면: 머리 아래 탭 3개가 순서대로 있고 Deal 상세 탭에서 시작한다 | DD-R27, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx > has three tabs in order and starts on Deal 상세`<br>`features/deals/detail/DealDetailPage.test.tsx > keeps the header above every tab with the tab list right below it` |
| DD-063 | 화면: 고른 탭이 주소에 남고 Deal 상세로 오면 tab이 지워지며 모르는 값은 Deal 상세다 | DD-R27, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx` |
| DD-064 | 화면: Deal 정보·카드·첨부는 Deal 상세 탭에만 있다 | DD-R27, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx` |
| DD-065 | 화면: 없는 Deal은 서버 문구와 "Deal 목록으로" 링크를 보인다 | DD-R27, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx > shows the not found message with a way back` |
| DD-066 | 화면: Deal 정보 타일은 정해진 순서로 code·Owner·요약 값·항목을 보인다 | DD-R28, DD-UC1 | frontend | `features/deals/detail/DealDetailLayout.test.tsx`<br>`features/deals/detail/DealDetailPage.test.tsx > shows the latest status, forecast, amount, expected close and next action in the summary bar`<br>`features/deals/detail/DealDetailPage.test.tsx > shows the deal code and the owner inside the deal info tile` |
| DD-067 | 화면: Won·Lost로 종결된 Deal에 종결 안내를 보인다 | DD-R28, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx > marks a won deal as closed and a lost deal as lost`<br>`features/deals/detail/DealDetailPage.test.tsx > marks a lost deal` |
| DD-068 | 화면: 고객·파트너·BANT 카드가 순서대로 있고 파트너가 없으면 "—"만, 이전 파트너는 접혀 있다 | DD-R29, DD-UC1 | frontend | `features/deals/detail/DealDetailLayout.test.tsx`<br>`features/deals/detail/DealDetailPage.test.tsx` |
| DD-069 | 화면: 퇴사한 Owner는 "이름(퇴사)"로 보인다 | DD-R3, DD-R28, DD-UC1 | frontend | `features/deals/detail/DealDetailPage.test.tsx > shows a resigned owner as 이름(퇴사)` |
| DD-070 | 화면: Owner 영업에게는 값 클릭 편집과 켜진 삭제 버튼이 있고 수정 링크는 없다 | DD-R30, DD-UC2 | frontend | `features/deals/detail/DealDetailLayout.test.tsx > keeps the header to the deal name and the list and delete buttons`<br>`features/deals/detail/DealDetailPage.test.tsx > gives the owner click-to-edit fields and a delete button, with no edit link`<br>`features/deals/detail/InlineEdit.test.tsx > has no edit link, no tile edit buttons and no editor pieces on the detail page for a writer`<br>`features/deals/detail/InlineEdit.test.tsx > gives a writer a click-to-edit button on every field value` |
| DD-071 | 화면: Owner가 아닌 영업은 삭제가 꺼져 이유가 보이지만 편집은 된다 | DD-R30, DD-UC6 | frontend | `features/deals/detail/DealDetailPage.test.tsx > disables delete with a reason for a sales user who is not the owner, but keeps edit`<br>`features/deals/detail/DeleteDealDialog.test.tsx > rejects a sales user deleting someone else s deal directly through the gateway (403)` |
| DD-072 | 화면: admin은 남의 Deal도 삭제 버튼이 켜져 있다 | DD-R30, DD-UC6 | frontend | `features/deals/detail/DealDetailPage.test.tsx > lets admin delete anyone s deal`<br>`features/deals/detail/DeleteDealDialog.test.tsx > lets admin delete a deal owned by someone else` |
| DD-073 | 화면: user는 값만 보고 편집·삭제·입력 버튼이 없다 | DD-R30, DD-UC1 | frontend | `features/deals/detail/DealDetailLayout.test.tsx > shows the owner as plain text for a viewer`<br>`features/deals/detail/DealDetailLayout.test.tsx > wraps every read-only value of a viewer in the same box as the edit button`<br>`features/deals/detail/DealDetailPage.test.tsx > shows a viewer the deal without any write control`<br>`features/deals/detail/DealDetailPage.vendor.test.tsx > shows the names as plain text without edit buttons for a viewer`<br>`features/deals/detail/InlineEdit.test.tsx > shows a viewer the same values without any click-to-edit control`<br>`features/deals/detail/InlineEdit.test.tsx > does not offer the editor to a viewer` |
| DD-074 | 화면 규칙: Deal 삭제 권한은 admin 전체, sales 본인, user 불가다 | DD-R30 | frontend | `shared/model/permissions.test.ts > Deal 삭제: admin 전체, sales 본인, user 불가` |
| DD-075 | 화면: 값 편집은 클릭·Enter·Space로 열리고 Enter로 저장하면 알림이 보인다 | DD-R31, DD-R32, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx > opens the editor with the keyboard (Enter and Space) and focuses the input`<br>`features/deals/detail/InlineEdit.test.tsx > saves the deal name with Enter and shows the success notice` |
| DD-076 | 화면: Esc는 입력을 버리고 원래 값을 보인다 | DD-R31, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx > discards the typed value with Escape and shows the original value (no buttons)` |
| DD-077 | 화면: 포커스가 나가면 바뀐 값은 저장되고 그대로면 요청이 없다 | DD-R31, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx > saves a typed value when focus leaves the input, and does nothing when it is unchanged` |
| DD-078 | 화면: 화면 검증·서버 거절이면 문구를 보이고 편집이 유지된다 | DD-R31, DD-R32, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx > keeps the editor open with the message when validation fails on Enter`<br>`features/deals/detail/InlineEdit.test.tsx > shows the server message for a name over 50 characters and keeps the editor open` |
| DD-079 | 화면: Owner는 재직 영업 중에서 고르고 퇴사한 Owner는 후보에 없다 | DD-R32, DD-UC2 | frontend | `features/deals/detail/DealDetailLayout.test.tsx > edits the owner in place inside the deal info tile`<br>`features/deals/detail/InlineEdit.test.tsx > lets the writer pick another sales owner and never offers the resigned one` |
| DD-080 | 화면: Vendor는 선택으로 Vendor만, Solution은 텍스트로 Solution만 보내고 빈 Solution은 막는다 | DD-R32, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.vendor.test.tsx`<br>`features/deals/detail/InlineEdit.test.tsx > edits Vendor with a select and Solution as a free text input`<br>`features/deals/detail/InlineEdit.test.tsx > does not save an empty Solution and keeps the shown value` |
| DD-081 | 화면: Users count는 0 이상 정수만 저장하고 빈 값은 막는다 | DD-R32, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx` |
| DD-082 | 화면: 견적·POC·구매절차를 각각 그 자리에서 고친다 | DD-R32, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx > edits the quote, the POC and the procurement in place` |
| DD-083 | 화면: 날짜 칸은 yyyymmdd를 저장하고 틀리거나 덜 친 날짜와 달력 버튼 이동은 저장하지 않는다 | DD-R31, DD-UC2 | frontend | `features/deals/detail/InlineEdit.dateInput.test.tsx` |
| DD-084 | 화면: BANT는 그 구분 Label 후보만 보이는 자동완성이고 후보를 고르면 바로 저장된다 | DD-R33, DD-UC2 | frontend | `features/deals/detail/InlineEdit.test.tsx` |
| DD-085 | 화면: BANT에 새 이름을 입력하면 Enter·포커스 이동으로 그 구분에 새 Label이 저장되고 같은 이름은 기존 Label을 쓴다 | DD-R33, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.test.tsx > saves a typed new BANT label with Enter and selects it`<br>`features/deals/detail/InlineEdit.test.tsx` |
| DD-086 | 화면: BANT 하나를 바꾸면 다른 구분은 그대로 보내고 비우면 선택 안 함, 그대로면 요청이 없다 | DD-R33, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.test.tsx > lets a writer clear a BANT label with the autocomplete and records it in the history`<br>`features/deals/detail/InlineEdit.test.tsx` |
| DD-087 | 화면: 고객 회사명을 누르면 회사 목록이 열리고 다른 회사를 고르면 담당자를 골라 연락 정보가 채워진다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/DealDetailLayout.test.tsx > shows the contact edit session as label rows with short visible labels`<br>`features/deals/detail/InlineContact.test.tsx > opens the company list on click and filters it by partial, case-insensitive text`<br>`features/deals/detail/InlineContact.test.tsx > clears the person and opens the person list when another existing company is picked, then fills the contact info` |
| DD-088 | 화면: 목록에 없는 회사는 신규로 안내되고 담당자명이 필요하다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx > treats a typed unknown company as new: clears every contact field, explains it and needs a person name` |
| DD-089 | 화면: Esc로 연락처 편집 전체를 버리면 이전 연락처가 남는다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx > discards the whole contact edit with Escape and keeps the old contact` |
| DD-090 | 화면: 회사·담당자·이메일·전화에는 공백을 넣을 수 없다는 안내가 나온다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx > blocks spaces in company, person, email and phone and tells the user` |
| DD-091 | 화면: 같은 회사의 다른 담당자를 고르거나 새 담당자를 입력한다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx > picks another existing person of the same company from the list and fills the contact info`<br>`features/deals/detail/InlineContact.test.tsx > takes a typed new person of the same company with empty contact info` |
| DD-092 | 화면: 직급·이메일·전화를 직접 고치고 틀린 이메일은 막는다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.test.tsx > edits the customer contact with the contact picker and keeps the other fields`<br>`features/deals/detail/InlineContact.test.tsx > edits title, email and phone directly and rejects a bad email` |
| DD-093 | 화면: 여러 Deal이 쓰는 연락처를 고칠 때 함께 바뀐다고 안내한다 | DD-R34, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx > tells that a shared contact is changed for every deal using it` |
| DD-094 | 화면: 파트너가 없으면 빈 값을 눌러 파트너를 추가한다(user는 버튼 없음) | DD-R35, DD-UC2 | frontend | `features/deals/detail/InlineContact.test.tsx` |
| DD-095 | 화면: 파트너를 교체하면 기존 파트너가 비활성이 된다는 안내 뒤 교체된다 | DD-R35, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.test.tsx > replaces the partner after warning that the current one becomes inactive`<br>`features/deals/detail/InlineContact.test.tsx > replaces the partner by clicking the company and picking another existing company and person` |
| DD-096 | 화면: 파트너 제거는 확인 뒤에만 된다 | DD-R35, DD-UC2 | frontend | `features/deals/detail/DealDetailPage.test.tsx > removes the active partner`<br>`features/deals/detail/InlineContact.test.tsx > removes the active partner only after a confirmation` |
| DD-097 | 화면: 동기화가 필요 없는 Forecast 변경은 바로 저장되고 알림이 보인다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > changes the forecast right away when no sync is needed and tells the user`<br>`shared/sync/useSyncedChange.test.tsx > applies an independent change without any dialog` |
| DD-098 | 화면: 계약완료로 바꾸면 매출 확정을 묻고 확정하면 Forecast도 Won이 된다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > asks for the revenue before moving to 계약완료 and then changes forecast to Won too`<br>`shared/sync/useSyncedChange.test.tsx` |
| DD-099 | 화면: 매출 확정 대화상자는 금액·날짜가 맞을 때만 확정이 켜지고 취소하면 값이 그대로다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > keeps the old values when the revenue dialog is cancelled`<br>`shared/sync/useSyncedChange.test.tsx` |
| DD-100 | 화면: Won에서 벗어나면 계약완료를 뺀 Status를 기본값 없이 묻는다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > asks which status to use when a won deal leaves Won, with no default and 계약완료 excluded`<br>`shared/sync/useSyncedChange.test.tsx > asks for a Status after leaving Won: disabled until chosen, then applies` |
| DD-101 | 화면: 계약완료에서 이전 단계로 가면 Won을 뺀 Forecast를 묻는다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > asks which forecast to use when a contract-completed deal goes back to an earlier status`<br>`shared/sync/useSyncedChange.test.tsx > lists Forecast names for askForecast and cancels without change` |
| DD-102 | 화면: Lost를 되살리면 현재 Status를 기본으로 묻는다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > asks for a status when reviving a lost deal, defaulting to the current status`<br>`shared/sync/useSyncedChange.test.tsx > preselects the default and labels with Forecast names for askForecast` |
| DD-103 | 화면: Status 편집을 Esc·포커스 이동으로 닫으면 아무것도 묻거나 바꾸지 않는다 | DD-R36, DD-UC3 | frontend | `features/deals/detail/SummaryBar.test.tsx > closes the status editor with Escape or by leaving it, without changing anything or asking` |
| DD-104 | 화면: 금액은 원 값으로 시작해 콤마를 붙이며 저장하고 빈 값·상한 초과·무변경은 보내지 않는다 | DD-R37, DD-UC4 | frontend | `features/deals/detail/SummaryBar.amountKeep.test.tsx > starts with the exact won value and sends no change when confirmed as is`<br>`features/deals/detail/SummaryBar.amountKeep.test.tsx > saves the typed won value as is when it differs by less than a thousand`<br>`features/deals/detail/SummaryBar.test.tsx` |
| DD-105 | 화면: Expected Close를 바꾸면 저장되고 이력에 남는다 | DD-R37, DD-UC4 | frontend | `features/deals/detail/SummaryBar.test.tsx > saves a new Expected Close`<br>`features/deals/detail/SummaryBar.test.tsx > records the change in the deal history` |
| DD-106 | 화면: 이력 표는 변경 시각·변경자·대상·전·후를 최신순으로 보이고 퇴사자를 표기한다 | DD-R38, DD-UC5 | frontend | `features/deals/detail/HistoryTab.test.tsx > shows when, who, what, before and after, newest first`<br>`features/deals/detail/HistoryTab.test.tsx > shows a resigned user as 이름(퇴사)` |
| DD-107 | 화면: 변경 대상으로 거르고 결과가 없으면 안내한다 | DD-R38, DD-UC5 | frontend | `features/deals/detail/HistoryTab.test.tsx > filters by the change target`<br>`features/deals/detail/HistoryTab.test.tsx > tells there is no history for a filter without results` |
| DD-108 | 화면: 이력은 읽기 전용이고 20행씩 페이지로 나뉜다 | DD-R38, DD-UC5 | frontend | `features/deals/detail/HistoryTab.test.tsx > is read only and paginates by 20 rows` |
| DD-109 | 화면: 삭제 확인은 함께 지워지는 건수를 알리고 Deal code 입력을 요구한다 | DD-R39, DD-UC6 | frontend | `features/deals/detail/DeleteDealDialog.test.tsx > states what is deleted together, with the counts and without partner meetings, and asks for the deal code`<br>`features/deals/detail/DeleteDealDialog.test.tsx > shows the same text without partner meetings while the counts are loading` |
| DD-110 | 화면: 정확한 code를 입력하기 전에는 삭제가 꺼져 있고 불일치·소문자는 안내한다 | DD-R39, DD-UC6 | frontend | `features/deals/detail/DeleteDealDialog.test.tsx > keeps 삭제 disabled until the exact code is typed and explains a mismatch`<br>`features/deals/detail/DeleteDealDialog.test.tsx > does not accept the code in lower case` |
| DD-111 | 화면: 삭제하면 상세를 바로 떠나 목록에서 알림을 보이고 이력·Action·첨부도 사라진다 | DD-R39, DD-R25, DD-UC6 | frontend | `features/deals/detail/DeleteDealDialog.test.tsx > deletes the deal with its history, actions and attachments and goes back to the list`<br>`features/deals/detail/DeleteDealDialog.test.tsx > leaves the detail screen right after deleting so no stale deal is shown` |
| DD-112 | 화면: 취소·Esc는 삭제하지 않는다 | DD-R39, DD-UC6 | frontend | `features/deals/detail/DeleteDealDialog.test.tsx > closes with cancel or Escape without deleting` |
| DD-113 | 화면: Deal을 지워도 파트너 미팅 기록은 남는다 | DD-R25, DD-UC6 | frontend | `features/deals/detail/DeleteDealDialog.test.tsx > keeps the partner meetings when the deal is deleted` |
| DD-114 | 화면 규칙: 동기화 계획·확정 함수가 서버와 같은 규칙표·문구를 따른다 | DD-R5~DD-R10, DD-R36 | frontend | `shared/model/sync.test.ts` |
| DD-115 | 화면 규칙: 이력 diff 함수가 서버와 같은 순서·대상·표기를 만든다 | DD-R20, DD-R21 | frontend | `shared/model/history.test.ts` |
| DD-116 | 게이트웨이: 상세·삭제 영향·이력·단일 변경·삭제를 계약대로 보내고 응답·오류를 바꾼다 | DD-R40 | frontend | `gateway/http/deals.test.ts`<br>`gateway/http/history.test.ts`<br>`gateway/http/mappers/history.test.ts` |
| DD-117 | Fake 게이트웨이는 서버와 같은 규칙·문구로 변경·삭제·이력 요청에 답한다 | DD-R5~DD-R8, DD-R12~DD-R14, DD-R17, DD-R20, DD-R24, DD-R25 | frontend | `test/fake/gateway/deals.change.test.ts`<br>`test/fake/gateway/deals.read.test.ts > 없는 code는 404`<br>`test/fake/gateway/deals.read.test.ts > impact는 연쇄 삭제 건수와 목록 건수가 같다`<br>`test/fake/gateway/deals.remove.test.ts`<br>`test/fake/gateway/history.test.ts`<br>`test/fake/gateway/historyLog.test.ts` |

### DD-001 어떤 역할이든 Deal 상세를 읽으면 문서화된 필드와 Owner·고객·파트너가 돌아온다
- Given KIM이 Owner이고 고객·활성 파트너가 있는 Deal
- When ROOT·KIM·VIEWER가 각각 `GET /deals/{code}`를 부른다
- Then 모두 200이고 키 집합이 DD-R2 목록과 같으며 `owner.id` = KIM, `customer`·`active_partner`가 그 연락처, `revenue_amount`는 JSON 정수다

### DD-002 상세 응답에는 폐지된 필드가 없다
- When Deal 상세(그리고 등록 응답)를 받는다
- Then `stage`·`id`·`customer_id`·`partner_id`·`revenue_currency`·`registered_by` 키가 없고 `code`·`status_key`·`forecast_key`가 있다

### DD-003 퇴사한 Owner의 Deal도 Owner가 퇴사 표기로 돌아온다
- Given Owner PARK가 퇴사 처리된 Deal
- When 상세를 읽는다
- Then `owner.id` = PARK, `owner.resigned` true, `owner.label` "<PARK 이름>(퇴사)"다

### DD-004 교체된 파트너는 비활성 링크와 파트너 이력에 남고 이력은 최근 연결 순이다
- Given 파트너 A로 등록한 뒤 파트너 B로 교체한 Deal
- When 상세를 읽는다
- Then `active_partner` = B, `partner_links` 2건(A는 `active` false·`unlinked_at` 있음), `partner_history`는 [B(활성), A(비활성)] 순서이고 각 항목에 연락처 객체가 있다

### DD-005 없는 code와 형식이 틀린 code의 상세는 같은 404다
- When `GET /deals/20260101-ZZZZ`(없음), `GET /deals/not-a-code`, `GET /deals/20260101-abcd`(소문자)
- Then 모두 404 `not-found` "Deal을 찾을 수 없습니다."다(422가 아니다)

### DD-006 Deal code는 8자리-대문자·숫자 4자리 전체가 맞을 때만 형식이 맞다
- When `20261015-A1B2`, `20261015-0000`과 `20261015-a1b2`, `2026101-A1B2`, `20261015A1B2`, `20261015-A1B2\n`, UUID를 각각 해석한다
- Then 앞의 둘만 Deal code이고 나머지는 "없음"(`parse_or_none` → None)이다

### DD-007 폐지된 Deal 경로는 404 또는 405다
- Given ROOT로 로그인
- When `GET`·`PUT`·`DELETE /deals/<UUID>`, `GET /deals/by-code/20260101-AAAA`, `POST /deals/<UUID>/stage`, `GET /deals/<UUID>/stage-changes`, `GET /deals/pipeline`을 부른다(본문이 있어도)
- Then 각각 404 또는 405다

### DD-008 계약완료와 Won은 함께이거나 둘 다 아니어야 일관적이다
- When (계약완료, Won), (기회발굴, Pipeline), (계약완료, Commit), (가격협상, Won)의 일관성을 판정한다
- Then 앞의 둘은 일관, 뒤의 둘은 불일치이고 불일치 판정은 422 `invalid-value` "Status와 Forecast의 동기화가 맞지 않습니다."가 된다

### DD-009 폼 저장에서 계약완료·Won 중 한쪽만 보내면 동기화 문구의 422이고 값이 그대로다
- Given 기회발굴·Pipeline Deal
- When 폼 수정으로 `{status_key: "contract_completed"}`만, `{forecast_key: "won"}`만 각각 보낸다
- Then 둘 다 422 `invalid-value` "Status와 Forecast의 동기화가 맞지 않습니다."이고 Status·Forecast·이력이 그대로다

### DD-010 폼 저장으로 두 값을 함께 보내면 종결되고 Status·Forecast 이력이 함께 변경 표기 없이 남는다
- Given 기회발굴·Pipeline Deal
- When 폼 수정으로 `{status_key: "contract_completed", forecast_key: "won"}`을 보낸다
- Then 200, 이력이 [(status, "Status", "기회발굴", "계약완료"), (forecast, "Forecast", "Pipeline", "Won")]이다(괄호 표기 없음)

### DD-011 종결된 Deal도 폼으로 수정되고 되돌려도 금액·Expected Close는 그대로다
- Given 종결 Deal(금액 777, Expected Close 2026-09-01)
- When 이름만 바꾸고, 이어서 `{status_key: "price_negotiation", forecast_key: "commit"}`으로 되돌린다
- Then 둘 다 200이고 되돌린 뒤 (금액, Expected Close) = (777, 2026-09-01), (Status, Forecast) = (가격협상, Commit)이다

### DD-012 계약완료로 바꾸면서 매출을 주지 않으면 422이고 값·이력이 그대로다
- Given 기본 Deal
- When `change {status_key: contract_completed}`를 resolution 없이 보낸다
- Then 422 `invalid-value` "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."이고 Status·Forecast가 그대로이며 등록 외 이력이 없다

### DD-013 계약완료로 바꾸면 Forecast도 Won이 되고 매출이 저장되며 이력 4건과 알림이 생긴다
- Given 기본 Deal
- When `change {status_key: contract_completed}`, `resolution {revenue_amount: 900000000, revenue_date: 2026-10-20}`
- Then 200, 응답 키 {deal, co_changed, notice}, deal (계약완료, Won, 900000000, 2026-10-20), `co_changed` [(forecast_key, pipeline, won)], `notice` "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."이고 이력이 [(status, Status, 기회발굴, 계약완료), (forecast, Forecast, Pipeline, "Won (Status 계약완료와 함께 변경)"), (amount, 금액(단위:원), 150,000,000, 900,000,000), (expectedClose, Expected Close, 2026-06-30, 2026-10-20)]이다

### DD-014 Won으로 바꾸면 Status도 계약완료가 되고 이력의 Status에 함께 변경이 표기된다
- Given 기본 Deal
- When `change {forecast_key: won}`과 매출 답을 보낸다
- Then 200, `co_changed` [(status_key, prospecting, contract_completed)], 같은 알림이고 이력에 (Status, "계약완료 (Forecast Won과 함께 변경)")가 있다

### DD-015 Lost에서 Won으로 바꾸는 것도 종결이라 매출이 필요하다
- Given Forecast Lost Deal
- When 매출 답 없이 Forecast를 Won으로, 이어서 매출 답과 함께 보낸다
- Then 첫 요청은 매출 문구 422, 두 번째는 200이고 (계약완료, Won)이 된다

### DD-016 종결 답의 금액이 0·음수·2^53이면 매출 문구의 422다
- When 계약완료로 바꾸며 `revenue_amount` 0, -1, 2^53(매출일 있음)과 매출일 없이 각각 보낸다
- Then 모두 422 "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."이고 아무것도 바뀌지 않는다

### DD-017 Won에서 다른 Forecast로 가려면 계약완료가 아닌 Status를 골라야 하고 금액·매출일은 그대로다
- Given 종결 Deal(777, 2026-09-01)
- When Forecast를 Commit으로 (a) 답 없이 (b) `status_key: contract_completed` (c) `status_key: poc_completed`로 보낸다
- Then (a)(b) 422 "함께 바꿀 값을 선택하세요."이고 값 그대로, (c) 200, (POC완료, Commit, 777, 2026-09-01), `co_changed` [(status_key, contract_completed, poc_completed)], 알림 "Status가 'POC완료'로 함께 변경되었습니다."다

### DD-018 Won에서 Lost로 가도 Status를 기본값 없이 골라야 한다
- Given 종결 Deal
- When Forecast를 Lost로 바꾸는 계획을 세운다
- Then Status 선택이 필요하고 선택지는 계약완료를 뺀 Status 6개(코드 순서), 기본값은 없다

### DD-019 계약완료에서 이전 단계로 가려면 Won이 아닌 Forecast를 골라야 한다
- Given 종결 Deal
- When Status를 POC완료로 (a) 답 없이 (b) `forecast_key: won` (c) `forecast_key: best`로 보낸다
- Then (a)(b) 422 선택 문구, (c) 200, (POC완료, Best), `co_changed` [(forecast_key, won, best)], 알림 "Forecast가 'Best'로 함께 변경되었습니다."다

### DD-020 Lost에서 되돌리면 Status를 묻되 기본은 현재 Status이고 그대로 고르면 함께 바뀐 값이 없다
- Given 가격협상·Lost Deal
- When Forecast를 Commit으로 (a) 답 없이 (b) `status_key: price_negotiation`(현재 값)으로 보낸다
- Then 계획의 기본 Status는 가격협상, (a) 422 선택 문구, (b) 200, (가격협상, Commit), `co_changed` [], 알림 null이다

### DD-021 Won이 아닌 Deal을 Lost로 바꾸면 Status는 그대로이고 함께 바뀐 값·알림이 없다
- Given 가격협상·Pipeline Deal
- When Forecast를 Lost로 바꾼다
- Then 200, (가격협상, Lost), `co_changed` [], `notice` null, 이력 [(forecast, Forecast, Pipeline, Lost)]다

### DD-022 독립 변경은 함께 보낸 답을 무시한다
- Given 기본 Deal
- When Status를 제품소개로 바꾸며 `resolution {status_key: "poc_completed", revenue_amount: 1, revenue_date: 2026-01-01}`을 함께 보낸다
- Then 200, Status 제품소개, Forecast·금액·Expected Close 그대로, `co_changed` []다

### DD-023 같은 값으로 바꾸면 200이지만 이력과 수정 시각이 그대로다
- Given 기본 Deal, 시계를 10분 앞으로
- When Forecast를 Pipeline(현재 값)으로, 금액을 현재 금액으로 각각 보낸다
- Then 둘 다 200, `co_changed` [], `notice` null이고 이력이 늘지 않으며 `updated_at`이 그대로다

### DD-024 실제로 바꾸면 수정 시각이 서버 시각이 되고 응답 Deal에 새 값이 있다
- Given 기본 Deal, 시계를 10분 앞으로
- When Forecast를 Best로 바꾼다
- Then 응답 `deal.forecast_key` "best", 저장된 `updated_at` = 그 서버 시각이다

### DD-025 선택지는 코드 목록 순서이고 이름을 바꾼 코드도 key로 같은 규칙이며 알림은 새 이름이다
- Given 계약완료 이름을 "수주 완료", Won 이름을 "수주"로 바꾸고 Status 순서를 바꿔 둔다
- When 기본 Deal을 계약완료로 매출 답과 함께 바꾸고, 종결 Deal의 Forecast를 Commit으로 바꾸는 계획을 세운다
- Then 종결이 같은 규칙으로 되고 알림은 "Status가 '수주 완료'로, Forecast가 '수주'로 함께 변경되었습니다."이며 Status 선택지는 바꾼 순서다

### DD-026 없는 Status·Forecast key로 바꾸면 422 "존재하지 않는 코드입니다."이고 값이 그대로다
- When `status_key: no_such_code`, `forecast_key: no_such_code`로 각각 보낸다
- Then 422 `invalid-value` "존재하지 않는 코드입니다."이고 (기회발굴, Pipeline) 그대로다

### DD-027 금액을 바꾸면 저장되고 이력에 원 콤마 숫자로 남는다
- When 금액을 1,870,000,000으로 바꾼다
- Then 200, 응답 금액 1870000000, `co_changed` [], 이력 [(amount, "금액(단위:원)", "150,000,000", "1,870,000,000")]다. 1원 차이 변경도 반올림 없이 남는다

### DD-028 금액 0·-1·2^53은 422이고 1과 2^53−1은 저장된다
- When 금액을 0, -1, 2^53, 1, 2^53−1로 각각 바꾼다
- Then 앞의 셋은 422 `invalid-value` "매출금액은 1원 이상의 정수로 입력하세요."이고 금액 150000000 그대로, 뒤의 둘은 200이다

### DD-029 Expected Close를 바꾸면 저장되고 이력에 YYYY-MM-DD로 남는다
- When Expected Close를 2026-12-31로 바꾼다
- Then 200, 응답 `revenue_date` "2026-12-31", 이력 [(expectedClose, "Expected Close", "2026-06-30", "2026-12-31")]다

### DD-030 종결된 Deal도 금액·Expected Close를 하나씩 바꿀 수 있고 Status·Forecast는 그대로다
- Given 종결 Deal
- When 금액, 이어서 Expected Close를 바꾼다
- Then 둘 다 200이고 (계약완료, Won) 그대로다

### DD-031 단일 변경 요청 형식이 틀리면 422 request-validation이다
- When 본문을 (a) `change {field: "users", value: 5}` (b) `revenue_amount`에 "100"·1.5·true (c) `revenue_date`에 ""·"2026-13-01" (d) `change` 없음 (e) 모르는 최상위 키 (f) `resolution {revenue_amount: "1"}`·모르는 키 (g) `delete_license_contracts: "yes"`로 보낸다
- Then 모두 422 `request-validation`이고 유스케이스를 부르지 않는다. `resolution` 생략·null·일부 키만은 받아들인다

### DD-032 Owner가 아닌 영업도, 퇴사한 Owner의 Deal도 바꿀 수 있고 이력 변경자는 요청자다
- Given KIM이 Owner인 Deal, PARK가 Owner였다가 퇴사한 Deal
- When LEE가 두 Deal의 Forecast를 Best로 바꾼다
- Then 둘 다 200이고 각 Deal의 최신 이력 변경자는 LEE다

### DD-033 user의 단일 변경은 403, 미인증은 401이다
- When VIEWER가, 로그인하지 않은 요청이 Forecast 변경을 보낸다
- Then 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)", 401 `unauthenticated`이고 값은 그대로다

### DD-034 없는 Deal·형식이 틀린 code의 단일 변경은 404다
- When `20260101-ZZZZ`, `not-a-code`에 Forecast 변경을 보낸다
- Then 404 `not-found` "Deal을 찾을 수 없습니다."다

### DD-035 이력은 최신순이고 같은 시각이면 나중에 기록한 것이 위다
- Given 등록 뒤 시간을 두고 두 번 바꾼 Deal과, 한 번의 저장으로 두 항목이 같은 시각에 남은 Deal
- When `GET /deals/{code}/history`
- Then 최신 변경이 맨 위이고 같은 시각의 두 항목은 나중에 저장된 항목이 위이며 등록 항목이 맨 아래다

### DD-036 구분을 주면 그 구분의 이력만 돌려준다
- Given Status·금액을 바꾼 Deal
- When `category=status`로 읽는다
- Then Status 항목만 돌아온다

### DD-037 이력 항목에는 변경자가 있고 퇴사자도 퇴사 표기로 나온다
- Given KIM이 바꾼 뒤 KIM이 퇴사 처리된 Deal
- When 이력을 읽는다
- Then 각 항목의 `by`가 변경자이고 KIM 항목의 `by.resigned` true다. 항목 필드는 `id`·`deal_code`·`at`·`by`·`category`·`target`·`before`·`after`다

### DD-038 없는 Deal의 이력은 404, 모르는 구분은 422다
- When `20260101-ZZZZ`·`not-a-code`의 이력, 있는 Deal의 `category=nope` 이력을 읽는다
- Then 404 "Deal을 찾을 수 없습니다.", 422 `request-validation`이다

### DD-039 어떤 역할이든 이력을 읽는다
- When ROOT·KIM·VIEWER가 이력과 삭제 영향을 읽는다
- Then 모두 200이다

### DD-040 이력 구분은 정확히 12값이다
- When 이력 구분 값 목록을 본다
- Then `created`·`status`·`forecast`·`amount`·`expectedClose`·`owner`·`partner`·`contact`·`bant`·`action`·`attachment`·`other` 12개이고 화면 구분 값과 같다

### DD-041 Deal을 등록하면 "Deal 등록" 이력 1건이 남는다
- When KIM이 Deal을 등록한다
- Then 이력은 (created, "Deal 등록", "", "Deal 등록") 1건이고 변경자 KIM, 시각 = 등록 시각이다

### DD-042 바뀐 것이 없으면 이력이 없고 바뀐 필드마다 고정 순서로 1건씩 남는다
- When 같은 스냅숏을 비교하고, 이어서 Status·금액·Owner·BANT Budget·Deal Name·구매절차를 한 번에 바꾼 스냅숏을 비교한다
- Then 앞은 0건, 뒤는 Status → 금액 → Owner → BANT Label: Budget → Deal Name → 구매절차 순 6건이고 모든 항목의 전·후가 다르다

### DD-043 Owner·파트너·고객 연락처 이력은 사용자·연락처 표기로 남는다
- When Owner를 퇴사한 PARK에서 KIM으로, 파트너를 없음→A→B→없음으로, 고객 연락처를 C에서 D로 바꾼다
- Then (owner, Owner, "<PARK>(퇴사)", "<KIM>"), (partner, 파트너, "없음", "<A 회사> <A 이름>") … ("<B …>", "없음"), (contact, 고객 연락처, "<C 회사> <C 이름>", "<D …>")다

### DD-044 BANT 이력은 구분마다 1건이고 비우면 "선택 안 함"이다
- When Budget·Need를 바꾸고 Timeline을 비운다
- Then 구분 순서대로 (bant, "BANT Label: Budget", …), (bant, "BANT Label: Need", …), (bant, "BANT Label: Timeline", "<이전 Label>", "선택 안 함")이다

### DD-045 기타 필드 이력은 필드 이름이 대상이고 정해진 표기로 남는다
- When Deal Name, Vendor(없음→Oracle, Oracle→없음), Solution(대소문자만 변경, 앞뒤 공백 차이만), Users count(10→0), 견적(→YES·2026-10-01), POC(→ING), 구매절차를 바꾼다
- Then 구분 `other`, 대상 = 필드 이름이고 Vendor "선택 안 함"↔"Oracle", Solution 대소문자 변경은 남고 공백 차이만은 남지 않으며, Users "10"→"0", 견적 "-"→"YES (2026-10-01)", POC "-"→"ING"다. Vendor만 바꾸면 Solution 항목은 없다

### DD-046 긴 대상·값은 300자·1000자로 잘리고 말줄임표가 붙는다
- When 대상 301자, 변경 전 1001자, 변경 후 1000자인 항목을 만든다
- Then 대상은 299자 + "…"(300자), 변경 전은 999자 + "…", 변경 후는 그대로이고 이모지는 한 글자로 세어 쪼개지지 않는다

### DD-047 삭제 영향은 그 Deal의 이력·Action·첨부·계약 건수다
- Given 이력 3건(등록 포함)·Action 2건·첨부 1개·계약 1건이 있는 Deal
- When `GET /deals/{code}/deletion-impact`
- Then `{history_count: 3, action_count: 2, attachment_count: 1, license_contract_count: 1}`이고 키는 정확히 이 넷이다

### DD-048 새 Deal의 삭제 영향은 등록 이력 1건뿐이고 다른 Deal 건수는 섞이지 않는다
- Given 새 Deal X와 Action·이력이 많은 다른 Deal Y
- When X의 삭제 영향을 읽는다
- Then (1, 0, 0, 0)이다

### DD-049 없는 Deal·형식이 틀린 code의 삭제 영향은 404다
- When `20260101-ZZZZ`, `not-a-code`의 삭제 영향을 읽는다
- Then 404 "Deal을 찾을 수 없습니다."다

### DD-050 Owner 영업이 code를 정확히 입력하면 204이고 Deal이 사라진다
- Given KIM이 Owner인 Deal
- When KIM이 `DELETE /deals/{code}?confirm_code=<code>`
- Then 204(본문 없음), 이후 상세는 404, 그 Deal의 이력 조회도 404이고 Deal 수가 하나 준다. 삭제는 커밋된다

### DD-051 admin은 다른 Owner의 Deal도 지운다
- When ROOT가 KIM의 Deal을 정확한 code로 지운다(퇴사한 Owner의 Deal 포함)
- Then 204이고 Deal이 사라진다

### DD-052 다른 영업은 확인 code가 틀려도 403이 먼저이고 Deal은 남는다
- When LEE가 KIM의 Deal을 `confirm_code=wrong`, 정확한 code로 각각 지운다
- Then 둘 다 403 `forbidden` "본인 Deal 또는 admin만 삭제할 수 있습니다."이고 Deal이 남는다

### DD-053 user의 삭제는 읽기 전용 문구의 403이고 Deal은 남는다
- When VIEWER가 정확한 code로 지운다
- Then 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 Deal이 남는다

### DD-054 확인 code가 정확히 같지 않으면 422이고 Deal은 남는다
- When KIM이 `wrong`, 다른 Deal code, 마지막 글자를 뺀 code, 끝에 X를 붙인 code, 소문자 code로 각각 지운다
- Then 모두 422 `invalid-value` "Deal code가 일치하지 않습니다."이고 Deal이 남는다

### DD-055 confirm_code가 없으면 422 request-validation이다
- When KIM이 `DELETE /deals/{code}`(쿼리 없음)
- Then 422 `request-validation`이고 Deal이 남는다

### DD-056 없는 Deal·형식이 틀린 code는 확인 code가 틀려도 404다
- When KIM이 `20260101-ZZZZ`, `not-a-code`를 `confirm_code=wrong`으로 지운다
- Then 404 "Deal을 찾을 수 없습니다."다

### DD-057 삭제하면 이력·Action·파트너 링크가 함께 지워지고 연락처·Label·사용자·파트너 미팅은 남아 다시 쓸 수 있다
- Given 고객·파트너·BANT Budget Label·Action 1건이 있는 Deal과 그 파트너 회사의 파트너 미팅 기록
- When Deal을 지운다
- Then 그 Deal의 이력·Action은 조회되지 않고(Action 404), 연락처·Label·Owner 사용자·파트너 미팅은 남으며, 같은 고객·파트너·Label로 새 Deal을 등록하면 같은 연락처 id와 Label이 쓰인다

### DD-058 삭제해도 다른 Deal의 데이터는 그대로다
- Given Action·이력이 있는 Deal X·Y
- When X를 지운다
- Then Y와 그 Action·이력은 그대로다

### DD-059 삭제는 커밋 뒤 운영 로그 한 줄을 남기고 거절되면 남기지 않는다
- When KIM이 자기 Deal을 지우고, 다른 요청에서 LEE의 거절된 삭제와 code 불일치 삭제가 일어난다
- Then 성공 삭제는 INFO 로그 "deal deleted code=<code> by=<KIM id> at=<서버 시각>" 한 줄이고 거절된 요청은 로그가 없다

### DD-060 저장 위치가 있으면 커밋 뒤 그 Deal 폴더만 지우고 없으면 파일을 건드리지 않는다
- Given 저장 위치에 Deal X·Y 폴더와 파일이 있다
- When X를 지운다(그리고 저장 위치 설정이 없는 상태에서 다른 Deal을 지운다)
- Then X 폴더만 사라지고 Y 폴더·저장 위치 루트는 남는다. 저장 위치가 없으면 파일 삭제 요청이 없다. 파일이 없는 Deal도 문제없이 지워진다

### DD-061 폴더를 지우지 못해도 Deal은 지워지고, 거절·커밋 실패면 Deal과 파일이 남는다
- Given 폴더 삭제가 실패하도록 한 저장소, 커밋이 실패하도록 한 UoW
- When 각각 Deal을 지우고, 권한 없는 사용자가 지운다
- Then 폴더 삭제 실패는 204(경고 로그)이고 Deal이 없다. 커밋 실패와 권한 거절은 Deal과 폴더가 남는다

### DD-062 화면: 머리 아래 탭 3개가 순서대로 있고 Deal 상세 탭에서 시작한다
- When Deal 상세를 연다
- Then 머리에 Deal 이름(h1)·"← 목록"·"Deal 삭제"가 있고 바로 아래 탭 "Deal 상세", "Actions", "Deal History"가 순서대로 있으며 Deal 상세가 선택돼 있다(Dashboard와 같은 강조 탭 모양)

### DD-063 화면: 고른 탭이 주소에 남고 Deal 상세로 오면 tab이 지워지며 모르는 값은 Deal 상세다
- When Actions 탭, Deal History 탭, 다시 Deal 상세 탭을 고르고, `?tab=nope`으로 연다
- Then 주소가 `?tab=actions`, `?tab=history`, `tab` 없음 순이고 `?tab=nope`은 Deal 상세 탭이다

### DD-064 화면: Deal 정보·카드·첨부는 Deal 상세 탭에만 있다
- When 세 탭을 차례로 연다
- Then Deal 정보 타일·고객·파트너·BANT 카드·첨부는 Deal 상세 탭에만 보이고 머리는 모든 탭 위에 있다

### DD-065 화면: 없는 Deal은 서버 문구와 "Deal 목록으로" 링크를 보인다
- When `/deals/20000101-ZZZZ`를 연다
- Then 경고에 "Deal을 찾을 수 없습니다."와 링크 "Deal 목록으로"(`/deals`)가 있다

### DD-066 화면: Deal 정보 타일은 정해진 순서로 code·Owner·요약 값·항목을 보인다
- When 시드 Deal 상세를 연다
- Then 타일(h2 "Deal 정보")의 항목이 DD-R28 순서이고 Deal code는 편집 버튼 없는 글자, 최신 Status·Forecast·금액·Expected Close·Next Action이 보인다. Owner·code는 머리에 없다

### DD-067 화면: Won·Lost로 종결된 Deal에 종결 안내를 보인다
- When Won Deal과 Lost Deal을 연다
- Then 각각 Won 종결 안내, Lost 종결 안내 문구(DD-R28)가 보인다

### DD-068 화면: 고객·파트너·BANT 카드가 순서대로 있고 파트너가 없으면 "—"만, 이전 파트너는 접혀 있다
- When 파트너를 교체한 Deal과 파트너가 없는 Deal을 연다
- Then 카드 순서 고객·파트너·BANT, 고객 카드에 직급·이메일·전화, 활성 파트너만 보이고 이전 파트너는 접힌 "이전 파트너 이력 (1)" 안에 있다. 파트너 없는 Deal은 5행 모두 "—"이고 "파트너 없음" 글자는 없다. BANT 카드에 4 Label이 보인다

### DD-069 화면: 퇴사한 Owner는 "이름(퇴사)"로 보인다
- When 퇴사한 Owner의 Deal을 연다
- Then Owner 값이 "<이름>(퇴사)"다

### DD-070 화면: Owner 영업에게는 값 클릭 편집과 켜진 삭제 버튼이 있고 수정 링크는 없다
- Given KIM으로 로그인
- When KIM의 Deal을 연다
- Then 모든 값에 "<항목> 수정" 버튼(이름은 title "Deal 이름 수정")이 있고 "Deal 삭제"가 켜져 있으며 "수정" 링크·카드 편집 버튼이 없다. "← 목록"은 `/deals`다

### DD-071 화면: Owner가 아닌 영업은 삭제가 꺼져 이유가 보이지만 편집은 된다
- When LEE가 KIM의 Deal을 연다
- Then "Deal 삭제"가 꺼져 있고 title "본인 Deal 또는 admin만 삭제할 수 있습니다."이며 "Deal 이름 수정"은 있다

### DD-072 화면: admin은 남의 Deal도 삭제 버튼이 켜져 있다
- When ROOT가 KIM의 Deal을 연다
- Then "Deal 삭제"가 켜져 있다

### DD-073 화면: user는 값만 보고 편집·삭제·입력 버튼이 없다
- When VIEWER가 Deal을 연다
- Then "Deal 삭제", "<항목> 수정", "고객 회사명 수정", Status 선택, "Action 추가" 버튼이 없고 값(예: BANT Label, Status 이름)은 글자로 보인다

### DD-074 화면 규칙: Deal 삭제 권한은 admin 전체, sales 본인, user 불가다
- When `canDeleteDeal`을 (admin, 남의 Deal), (sales, 자기 Deal), (sales, 남의 Deal), (user, 자기 id와 같은 Owner)로 판정한다
- Then 참, 참, 거짓, 거짓이다

### DD-075 화면: 값 편집은 클릭·Enter·Space로 열리고 Enter로 저장하면 알림이 보인다
- When "Deal 이름 수정"에 Enter(또는 Space)를 눌러 열고 새 이름을 입력해 Enter
- Then 입력기에 포커스가 가고, 저장 뒤 h1이 새 이름, 알림 "Deal 이름이 변경되었습니다."다

### DD-076 화면: Esc는 입력을 버리고 원래 값을 보인다
- When 이름 편집에서 다른 값을 입력하고 Esc
- Then 저장 요청 없이 원래 이름이 보이고 입력기·버튼이 없다

### DD-077 화면: 포커스가 나가면 바뀐 값은 저장되고 그대로면 요청이 없다
- When 구매절차를 바꾼 뒤 포커스를 옮기고, 다시 열어 그대로 포커스를 옮긴다
- Then 첫 번째는 저장·알림, 두 번째는 요청 없이 닫힌다

### DD-078 화면: 화면 검증·서버 거절이면 문구를 보이고 편집이 유지된다
- When 이름을 비워 Enter, 51자 이름을 Enter로 저장한다
- Then 각각 "Deal Name을 입력하세요."(요청 없음), 서버 문구가 입력기 아래에 보이고 편집이 열린 채다

### DD-079 화면: Owner는 재직 영업 중에서 고르고 퇴사한 Owner는 후보에 없다
- When Owner를 눌러 다른 영업을 고른다(퇴사한 Owner의 Deal 포함)
- Then 후보는 재직 sales뿐이고 고르면 저장되어 "Owner가 변경되었습니다."가 보인다

### DD-080 화면: Vendor는 선택으로 Vendor만, Solution은 텍스트로 Solution만 보내고 빈 Solution은 막는다
- When Vendor 선택(선택 안 함 + 등록 Vendor, 현재 값 선택됨)에서 다른 Vendor를 고르고, Solution을 고치고, Solution을 비운다
- Then Vendor 요청은 `vendorId`만, Solution 요청은 `solution`만 보내고 각 이력이 남는다. 같은 Vendor·같은 Solution이면 요청이 없다. 빈 Solution은 "Solution을 입력하세요."로 막고 값이 그대로다. Vendor 없는 Deal은 "—"이고 Solution을 고칠 수 있다

### DD-081 화면: Users count는 0 이상 정수만 저장하고 빈 값은 막는다
- When Users count를 25, 0, ""로 저장한다
- Then 25·0은 저장되어 "0"이 보이고, 빈 값은 "Users count를 입력하세요."로 막는다

### DD-082 화면: 견적·POC·구매절차를 각각 그 자리에서 고친다
- When 견적 제출여부를 YES로, 견적 제출일을 입력하고, POC 여부를 ING로, 구매절차를 바꾼다
- Then 각각 저장되고 짝 값은 그대로이며 표시가 "제출 (<날짜>)", "ING · 진행 중"으로 바뀐다

### DD-083 화면: 날짜 칸은 yyyymmdd를 저장하고 틀리거나 덜 친 날짜와 달력 버튼 이동은 저장하지 않는다
- When Expected Close에 "20261231" Enter, "20261332" Enter, "2026" Enter, 달력 버튼으로 포커스 이동을 각각 한다
- Then 첫 번째만 2026-12-31로 저장되고 나머지는 저장 요청 없이 편집이 유지된다(틀린 날짜는 칸 문구)

### DD-084 화면: BANT는 그 구분 Label 후보만 보이는 자동완성이고 후보를 고르면 바로 저장된다
- When Budget 값을 눌러 후보를 고른다
- Then 입력이 현재 Label 이름으로 시작하고 후보는 Budget Label뿐("새 Label" 항목 없음), 고르는 순간 저장되어 "BANT Budget Label이 변경되었습니다."와 이력이 남는다

### DD-085 화면: BANT에 새 이름을 입력하면 Enter·포커스 이동으로 그 구분에 새 Label이 저장되고 같은 이름은 기존 Label을 쓴다
- When Budget에 없는 이름을 입력해 Enter, Need에 없는 이름을 입력해 포커스 이동, Authority에 기존 Label 이름을 대소문자만 바꿔 입력해 Enter
- Then 앞의 둘은 그 구분에 새 Label이 생겨 선택되고, 세 번째는 기존 Label id로 저장된다(새 Label 없음)

### DD-086 화면: BANT 하나를 바꾸면 다른 구분은 그대로 보내고 비우면 선택 안 함, 그대로면 요청이 없다
- When Need만 바꾸고, Timeline 입력을 비워 확정하고, Budget을 같은 Label로 확정한다
- Then 첫 요청의 다른 세 구분은 현재 `{id}`(또는 null) 그대로, 두 번째는 Timeline null("—", 이력 "선택 안 함"), 세 번째는 요청이 없다

### DD-087 화면: 고객 회사명을 누르면 회사 목록이 열리고 다른 회사를 고르면 담당자를 골라 연락 정보가 채워진다
- When "고객 회사명 수정"을 눌러 일부·대소문자 다른 글자로 거르고 다른 기존 회사를 고른 뒤 담당자를 고른다
- Then 회사 목록이 부분·대소문자 무시로 걸러지고, 회사를 고르면 담당자가 비워지며 담당자 목록이 열리고, 담당자를 고르면 연락 정보가 채워져 저장되고 "고객 연락처가 저장되었습니다."다

### DD-088 화면: 목록에 없는 회사는 신규로 안내되고 담당자명이 필요하다
- When 회사명에 없는 회사를 입력하고 담당자명 없이 저장하려 한다
- Then 담당자 칸이 모두 비고 "신규 고객사입니다. 담당자 정보를 입력하세요."가 보이며 담당자명 칸 오류로 저장되지 않는다

### DD-089 화면: Esc로 연락처 편집 전체를 버리면 이전 연락처가 남는다
- When 세션에서 회사·담당자를 바꾼 뒤 Esc
- Then 요청 없이 이전 연락처가 보인다

### DD-090 화면: 회사·담당자·이메일·전화에는 공백을 넣을 수 없다는 안내가 나온다
- When 회사명·담당자명·이메일·전화에 공백을 친다
- Then 공백이 지워지고 공백 안내 문구(CT)가 보인다. 직급은 공백을 허용한다

### DD-091 화면: 같은 회사의 다른 담당자를 고르거나 새 담당자를 입력한다
- When 담당자명 자동완성에서 같은 회사의 다른 담당자를 고르고, 다른 때 목록에 없는 이름을 입력해 Enter
- Then 고른 담당자의 연락 정보로 저장되고, 새 이름은 직급·이메일·전화가 빈 신규 담당자로 저장된다

### DD-092 화면: 직급·이메일·전화를 직접 고치고 틀린 이메일은 막는다
- When 직급, 전화를 고치고, 이메일에 "bad@"를 입력해 Enter
- Then 직급·전화는 저장되고 틀린 이메일은 그 칸 문구로 막혀 요청이 없다

### DD-093 화면: 여러 Deal이 쓰는 연락처를 고칠 때 함께 바뀐다고 안내한다
- Given 고객 연락처를 쓰는 Deal이 2건
- When 그 고객의 직급을 편집한다
- Then "이 연락처는 2개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다."가 보인다

### DD-094 화면: 파트너가 없으면 빈 값을 눌러 파트너를 추가한다(user는 버튼 없음)
- When 파트너 없는 Deal에서 "파트너 회사 입력"(또는 다른 "—")을 눌러 회사·담당자를 저장한다
- Then 안내 "파트너를 입력하면 회사명과 담당자명이 모두 필요합니다."가 보였고 저장 뒤 "파트너가 추가되었습니다."다. VIEWER에게는 "—"만 있고 버튼이 없다

### DD-095 화면: 파트너를 교체하면 기존 파트너가 비활성이 된다는 안내 뒤 교체된다
- When 파트너 회사명을 눌러 다른 기존 회사·담당자를 고른다
- Then 안내 "기존 활성 파트너(<회사> <담당자>)는 이력으로 남고 비활성이 됩니다."가 보였고 "파트너가 교체되었습니다." 뒤 이전 파트너가 접힌 이력에 있다

### DD-096 화면: 파트너 제거는 확인 뒤에만 된다
- When "파트너 제거"를 누르고 대화상자에서 "제거"
- Then 대화상자 문구가 DD-R35이고 확인 뒤에만 파트너가 사라지며 "파트너가 제거되었습니다."다

### DD-097 화면: 동기화가 필요 없는 Forecast 변경은 바로 저장되고 알림이 보인다
- When Forecast 선택에서 Best를 고른다
- Then 대화상자 없이 저장되어 배지가 Best이고 알림 "Forecast가 'Best'(으)로 변경되었습니다."다

### DD-098 화면: 계약완료로 바꾸면 매출 확정을 묻고 확정하면 Forecast도 Won이 된다
- When Status에서 계약완료를 고르고 매출 확정 대화상자에서 확정한다
- Then 대화상자에 안내 문구와 현재 금액·Expected Close가 미리 채워져 있고, 확정 뒤 Status 계약완료·Forecast Won·서버 알림 "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다."다

### DD-099 화면: 매출 확정 대화상자는 금액·날짜가 맞을 때만 확정이 켜지고 취소하면 값이 그대로다
- When 금액을 비우거나 날짜를 틀리게·덜 입력하고, 날짜를 yyyymmdd로 입력하고, 취소한다
- Then 금액·날짜가 유효할 때만 "확정"이 켜지고(yyyymmdd는 ISO 날짜로 확정), 취소하면 요청이 없고 Status·Forecast가 그대로다

### DD-100 화면: Won에서 벗어나면 계약완료를 뺀 Status를 기본값 없이 묻는다
- Given Won Deal
- When Forecast를 Commit으로 고른다
- Then "함께 바꿀 값 선택" 대화상자에 Won 이탈 안내와 계약완료가 빠진 Status 라디오가 있고, 고르기 전 "확인"이 꺼져 있으며 고른 뒤 확인하면 두 값이 바뀐다

### DD-101 화면: 계약완료에서 이전 단계로 가면 Won을 뺀 Forecast를 묻는다
- Given 종결 Deal
- When Status를 POC완료로 고른다
- Then 대화상자에 Won이 빠진 Forecast 이름 라디오가 있고 고른 값으로 두 값이 바뀐다

### DD-102 화면: Lost를 되살리면 현재 Status를 기본으로 묻는다
- Given Lost Deal
- When Forecast를 Commit으로 고른다
- Then 대화상자의 현재 Status 라디오가 미리 선택돼 있고 "확인"이 켜져 있다

### DD-103 화면: Status 편집을 Esc·포커스 이동으로 닫으면 아무것도 묻거나 바꾸지 않는다
- When Status 편집을 열고 Esc, 다시 열고 포커스를 다른 곳으로 옮긴다
- Then 대화상자·요청 없이 원래 Status가 보인다

### DD-104 화면: 금액은 원 값으로 시작해 콤마를 붙이며 저장하고 빈 값·상한 초과·무변경은 보내지 않는다
- When 금액 편집을 열고(시작값 확인), "350000000"을 입력해 Enter, 빈 값 Enter, "9007199254740992" Enter, 원래 값 그대로 Enter
- Then 시작값은 원 콤마 값이고 입력 중 "350,000,000"으로 보이며 저장 뒤 "금액이 변경되었습니다.", 빈 값은 "매출금액은 1원 이상의 정수를 입력하세요.", 상한 초과는 "매출금액은 9,007,199,254,740,991원 이하로 입력하세요."(편집 유지), 무변경은 요청이 없다. 1,000원 미만 차이도 그대로 저장된다. 머리글은 "금액(단위:원)"이다

### DD-105 화면: Expected Close를 바꾸면 저장되고 이력에 남는다
- When Expected Close를 새 날짜로 저장하고 Deal History 탭을 연다
- Then "Expected Close가 변경되었습니다."이고 이력에 Expected Close 변경 행이 있다

### DD-106 화면: 이력 표는 변경 시각·변경자·대상·전·후를 최신순으로 보이고 퇴사자를 표기한다
- When Deal History 탭을 연다
- Then 표 "Deal History" 머리글 5개와 서버 순서(최신순) 행이 보이고 퇴사한 변경자는 "<이름>(퇴사)", 빈 변경 전은 "—"다

### DD-107 화면: 변경 대상으로 거르고 결과가 없으면 안내한다
- When "변경 대상"에서 Status, 결과가 없는 구분을 고른다
- Then Status 행만 보이고, 없는 구분이면 "변경 이력이 없습니다."다

### DD-108 화면: 이력은 읽기 전용이고 20행씩 페이지로 나뉜다
- Given 이력 25건인 Deal
- When Deal History 탭을 연다
- Then 첫 페이지 20행, 다음 페이지 5행이고 편집 버튼이 없다

### DD-109 화면: 삭제 확인은 함께 지워지는 건수를 알리고 Deal code 입력을 요구한다
- When "Deal 삭제"를 누른다
- Then 대화상자 "Deal 삭제"에 DD-R39 건수 문구(파트너 미팅 언급 없음)와 "계속하려면 Deal code <code>를 입력하세요."가 있다. 건수를 읽는 동안은 건수 없는 같은 안내다

### DD-110 화면: 정확한 code를 입력하기 전에는 삭제가 꺼져 있고 불일치·소문자는 안내한다
- When 아무것도 안 넣고, 다른 값, 소문자 code, 정확한 code를 차례로 입력한다
- Then 정확한 code일 때만 "삭제"가 켜지고, 다른 값·소문자일 때 "Deal code가 일치하지 않습니다."가 보인다

### DD-111 화면: 삭제하면 상세를 바로 떠나 목록에서 알림을 보이고 이력·Action·첨부도 사라진다
- When 정확한 code를 넣고 "삭제"
- Then 상세(오래된 Deal)를 다시 그리지 않고 목록으로 가서 "Deal <code>이(가) 삭제되었습니다."가 보이며 그 Deal의 이력·Action·첨부가 Fake 저장소에 없다

### DD-112 화면: 취소·Esc는 삭제하지 않는다
- When 대화상자에서 "취소", 다시 열어 Esc
- Then 삭제 요청이 없고 상세가 그대로다

### DD-113 화면: Deal을 지워도 파트너 미팅 기록은 남는다
- Given 파트너 회사의 미팅 기록이 있는 Deal
- When Deal을 지운다
- Then 파트너 Activity의 그 미팅 기록이 남는다

### DD-114 화면 규칙: 동기화 계획·확정 함수가 서버와 같은 규칙표·문구를 따른다
- When `planChange`·`finalizePlan`으로 DD-013~DD-025의 각 상황을 판정한다
- Then 계획 종류·선택지·기본값·함께 바뀐 값·알림·거절 문구("Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.", "함께 바꿀 값을 선택하세요.")가 서버와 같고 `isSyncConsistent`가 DD-008과 같다

### DD-115 화면 규칙: 이력 diff 함수가 서버와 같은 순서·대상·표기를 만든다
- When `diffDeal`로 DD-042~DD-045의 변경을 비교한다
- Then 서버와 같은 항목 순서·구분·대상·표기("금액(단위:원)" 원 콤마, 파트너 "없음", 함께 변경 표기, Vendor·Solution 규칙)다

### DD-116 게이트웨이: 상세·삭제 영향·이력·단일 변경·삭제를 계약대로 보내고 응답·오류를 바꾼다
- When `deals.get`·`deals.impact`·`history.list`(구분 없음·있음)·`deals.applyChange`(답 포함)·`deals.remove`(다른 code 포함)를 부른다
- Then DD-R40 경로·쿼리·본문(snake_case)으로 보내고 응답을 camelCase(`coChanged`, `notice`, 네 건수)로 바꾸며 404·422는 서버 문구의 오류, 204는 성공이다

### DD-117 Fake 게이트웨이는 서버와 같은 규칙·문구로 변경·삭제·이력 요청에 답한다
- When Fake 게이트웨이로 단일 변경(독립·종결·되돌림·없는 코드·금액·같은 값), 삭제(권한·확인 code·연쇄 삭제), 이력 목록(순서·구분·404)을 부른다
- Then 결과·문구·상태 코드가 DD-R5~R8, DD-R12~R14, DD-R17, DD-R20, DD-R24, DD-R25와 같다(어긋남은 계획 Q1·Q2 결정에 따름)

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 최초 작성(초안): 구현된 Deal 상세·단일 변경·동기화·이력·삭제 동작을 정본 명세로 옮김. 규칙 DD-R1~R40, use case DD-UC1~UC6, BDD 케이스 DD-001~DD-117 | DD-001~DD-117(신규) |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체(1장, DD-R31). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
