# Deal 목록·검색   (feature 코드: DL, 상태: 확정(2026-11-13 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/web/routers/deals.py`의 `GET ""`·`/updated-periods`·`/years`, `app/web/schemas/{deal.py(DealSearchParams),deal_response.py(DealRowResponse·row_page),deal_years.py,updated_period.py,period_params.py}`, `app/application/deal/{list_deals,deal_years,updated_periods}.py`, `app/application/ports/{deal_repository.py(DealQuery·DealSort·SortOrder),deal_outcome_filter.py,pagination.py}`, `app/application/ports/deal_action_repository.py`의 `NextActionStatusFilter`, `app/domain/deal/{period,updated_period}.py`, `app/domain/common/validation.py`, `app/infra/db/{deal_search,deal_list_order,like}.py`, `frontend/src/features/deals/list/*`, `shared/model/{dealListMemory,quarterSet,forecastKeys,updatedPeriod,periodChoice,yearOptions,vendorFilter,nextActionStatus}.ts`, `shared/ui/useDealListPath.ts`, `data/{deals,dealYears}.ts`, `gateway/http/deals.ts`, `test/fake/gateway/dealsRead.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트가 어긋나는 점은 계획(`artifacts/10-analysis/dl-plan.md`)의 확인 필요 질문으로 분리했습니다.

## 1. 개요

- 목적: 로그인한 모든 사용자가 Deal을 조건으로 찾아 한 페이지씩 보고, 정렬하고, 행을 펼쳐 요약을 보거나 상세로 이동한다. sales·admin은 목록에서 Status·Forecast·금액·Expected Close를 바로 고치기 시작할 수 있다. 목록 조건은 URL에 있고 사용자·탭별로 기억되어 상세에 다녀와도 같은 목록으로 돌아온다.
- 사용자(역할): admin·sales(조회 + 목록 인라인 편집 진입·Deal 등록 링크), user(조회만).
- 범위
  - 화면 `/deals`: 필터 바(키워드·담당자·Vendor·Solution·Status·Forecast 다중 선택·Next Action 상태·연도·Quarter 다중 선택·월·최종 업데이트 기간·내 딜만·기한초과·미업데이트), 조건 없는 진입의 기본 조건, 정렬 머리글, 페이지, 빈 상태, 빠른 보기(Quick View), 인라인 편집 진입과 목록 편집기, 조건 기억(목록으로 돌아가는 모든 링크)
  - API `GET /deals`(조건 해석·정렬·페이지), `GET /deals/years`, `GET /deals/updated-periods`
  - Deal 조건 해석 한 곳(`deal_search.conditions`) — FC·DSH 집계가 같은 해석을 쓴다(DL-R15)
  - 연도 선택지 규칙(`selectableYears`) — 범위 규칙은 Deals 목록·Dashboard·Forecast 공용, '전체' 항목은 Deal 목록에만 있다(DL-R24)
- 범위 밖(다른 feature)
  - 목록 인라인 편집의 서버 적용(`POST /deals/{code}/changes`)과 Status⇄Forecast 동기화 대화상자 → DD, Won 이탈 시 라이선스 계약 처리 대화상자 → LC
  - 기한초과·미업데이트 판정식(RK-R3~R5), `risk` 값(RK-R6), 경고 범례·배지·행 색(RK-R15·R16), `last_updated_on`(RK-R2)·Next Action 기준 행(RK-R1)·`status_changed_on`(RK-R9)·`status_days`(RK-R10) 계산 → RK (DL은 그 값을 조건·정렬·표시에 쓴다)
  - Deal 상세(`GET /deals/{code}`, `partner_history`)·삭제·삭제 영향, `/deals/{code}` 경로의 code 해석(예: 폐지된 `/deals/facets`가 404인 것) → DD
  - Deal 등록·수정 폼과 행 필드(이름·금액·연락처 등)의 값 규칙 → DE, 라이선스 계약 필드(`license_contract_count`·`has_issued_license_contract`) → LC
  - Dashboard·Forecast 화면에서 목록으로 보내는 주소 만들기(Drill-down) → DSH·FC (도착한 주소의 해석은 DL-R20)
  - Next Action 상태 변경·Actions 탭 검색(`upcoming` 프리셋 사용 포함) → NA
  - 공통 권한 판정·CSRF·Problem 형식·id 쿼리 형식·NUL 공통 원칙·화면 가드·상단 메뉴 → PL(PL-R2, PL-R4, PL-R5, PL-R10~R12, PL-R15, PL-R16, PL-R29, PL-R34, PL-R36, PL-R37, PL-R39)
  - 업무 날짜·업무일 경계·개월 이동·상대 시각 표기·`useToday` → TM(TM-R4~R6, TM-R12, TM-R14, TM-R15), 날짜 입력·다중 선택·페이저·정렬 머리글 공통 컴포넌트 자체 → UI(날짜 입력 UI-R1~R11, 다중 선택 UI-R22~R24, 페이저 UI-R30, 정렬 머리글 UI-R32)
- 관련 화면·메뉴: 상단 메뉴 "Deals"(PL-R34, 링크 주소는 DL-R31), 로그인 뒤 첫 화면(`/` → `/deals`, PL-R32).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 목록 조건 | `GET /deals`의 쿼리 파라미터 묶음(서버 `DealQuery`). 화면에서는 URL 쿼리 키(DL-R20) |
| 업무 날짜(오늘) | 서버 OS 시간대의 오늘(TM-R4). 화면은 서버 동기 시계(`useToday`, TM-R12) |
| Expected Close | Deal의 `revenue_date`. 연도·분기·월 조건의 기준 |
| 최종 업데이트 | 행의 `last_updated_on`(모든 Action 중 가장 늦은 수행일, 없으면 Deal 등록일, Deal 수정은 반영 안 함 — RK-R2) |
| 기준 행 | Next Action이 있는 가장 최근 Action(RK-R1). Next Action 상태 조건과 Next Action 칸의 기준 |
| 활성 파트너 | 해제되지 않은 파트너 링크의 연락처(Deal당 최대 1개, DE) |
| 기본 조건 주소 | 조건이 하나도 없는 `/deals`를 대신하는 주소: 로그인 사용자가 sales면 `/deals?year=all&mine=1`, admin·user면 `/deals?year=all`(연도 전체, 정렬은 기본 최종 업데이트 최신순 — DL-R19) |
| 조건 기억 | 사용자별 sessionStorage에 마지막으로 본 목록 쿼리를 저장해 "목록으로" 링크가 쓰는 것 |
| 빠른 보기 | 행 아래로 펼치는 요약(Quick View) |
| 자연 방향 | 정렬하지 않던 열을 처음 누를 때의 방향(금액·최종 업데이트는 내림차순, 나머지는 오름차순) |

### 2.2 데이터 모델

DL은 테이블을 소유하지 않는다. 읽는 값: `deals`(소유 DE), `contacts`(CT), `deal_partners`(DE), `vendors`·`codes`(CL·CD, 정렬에 `codes.sort_order`·필터에 `codes.outcome`), `users`(US, 담당자 정렬), `deal_actions`(AC, 최종 업데이트·기준 행), `alert_settings`(RK-R11, 경고 필터 기준), `license_contracts`(LC, 행의 계약 필드).

조건 모델(`DealQuery`, 서버 정본)

| 필드 | 형식 | 뜻 |
| --- | --- | --- |
| `keyword` | str ≤100 또는 없음 | DL-R4 |
| `owner_user_id` | id 또는 없음 | DL-R5(`mine`이 채움) |
| `vendor_id` | id 또는 없음 | DL-R6 |
| `solution` | str ≤200(트림 후) 또는 없음 | DL-R6 |
| `status_key` | str ≤50 또는 없음 | DL-R7 |
| `forecast_keys` | 문자열 집합(비지 않음) 또는 없음 | DL-R8 |
| `forecast_outcome` | `open`·`won`·`lost`·`not_lost` 또는 없음 | DL-R8 |
| `year` | 1900~9999 또는 없음 | DL-R9 |
| `quarters` | {1~4}의 부분집합(정규화 뒤 1~3개) 또는 없음 | DL-R9 |
| `month` | 1~12 또는 없음 | DL-R9 |
| `updated_from`·`updated_to` | 날짜(1900-01-01~2999-12-31) 또는 없음 | DL-R10 |
| `next_action_status` | `open`·`done`·`not_done`·`closed` 또는 없음 | DL-R11 |
| `overdue`·`stale` | bool(기본 false) | DL-R12 |
| `sort`·`order` | DL-R13 값(기본 `last_updated_at`·`desc`) | DL-R13 |
| `offset`·`limit` | 0 이상·1~200(기본 0·20) | DL-R2 |

### 2.3 비즈니스 규칙

목록 API (`GET /deals`)
- **DL-R1** 로그인한 모든 역할이 조회한다. 응답은 200 `{items, total, offset, limit}`: `items`는 한 페이지의 행(DL-R14), `total`은 페이지와 무관한 조건 일치 전체 건수, `offset`·`limit`은 요청 값(없으면 기본값)이다. 끝을 넘은 페이지는 `items`가 비고 `total`은 그대로다. Deal이 없거나 조건에 맞는 Deal이 없으면 `items` `[]`, `total` 0이다. 서버는 요청마다 시계를 한 번 읽어 업무 날짜(TM-R4)를 정하고, 그 날짜를 연도 채움(DL-R9)과 경고 필터·행 `risk`(DL-R12)에 함께 쓴다.
- **DL-R2** 페이지: `offset`은 0 이상 정수(기본 0), `limit`은 1~200 정수(기본 20)다. 범위 밖·정수 아님은 422 `request-validation`이다. 필터와 정렬 뒤에 `offset`·`limit`을 적용한다.
- **DL-R3** 모든 조건은 AND로 결합한다. 쿼리는 2.6에 적힌 키만 받는다: 모르는 키와 폐지된 키(`stage`, `customer_id`, `owner`(이름), `vendor`(이름), `solution_id`, `revenue_from`, `revenue_to`, `bant_budget`·`bant_authority`·`bant_need`·`bant_timeline` 등 `bant_*`, `sortBy`, `direction`)는 조용히 무시하지 않고 422 `request-validation`이다. 판정 순서: 미인증 401(PL-R5) → 형식 422 `request-validation`(모든 쿼리 형식·범위, PL-R12) → 값 422 `invalid-value`(① 최종 업데이트 날짜 범위 `updated_from` → `updated_to` ② 기간 역전 ③ 분기·월 동시 선택 ④ 키워드 NUL ⑤ Solution NUL) → 결과. 어느 오류도 `detail`에 DB 문구가 없다(PL-R16).
- **DL-R4** 키워드(`keyword`): 원문 길이가 100자를 넘으면 422 `request-validation`(앞뒤 공백도 센다). NUL 문자가 있으면 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다". 앞뒤 공백을 지우고 공백뿐이면 조건 없음이다. Deal Name·Deal code·고객 회사명·**활성** 파트너 회사명 중 하나에 대소문자 무시로 부분 일치하면 맞는다. 해제된(비활성) 파트너·담당자 이름·Vendor 이름·Solution은 찾지 않는다. `%`·`_`·`\`는 글자 그대로다.
- **DL-R5** 담당자: `owner_user_id`는 담당자(Owner) id가 정확히 같은 Deal이다(퇴사한 담당자 포함). 형식은 쿼리 id(PL-R15). `mine=true`면 요청한 사용자가 Owner인 Deal만이며 `owner_user_id`보다 우선한다(함께 보내면 `owner_user_id`는 무시). `mine`이 false거나 없으면 담당자 조건은 `owner_user_id`뿐이다. `mine`에 불리언이 아닌 값(예: `maybe`)은 422 `request-validation`이다.
- **DL-R6** Vendor·Solution: `vendor_id`는 Vendor id가 같은 Deal이고, 없는 id는 오류 없이 0건이다(정수가 아니면 422 `request-validation`, 예: `vendor_id=SAP`). `solution`은 앞뒤 공백을 지우고 공백뿐이면 조건 없음이며, Solution 텍스트에 대소문자 무시로 부분 일치한다(`%`·`_`는 글자 그대로). 지운 뒤 200자는 되고 201자 이상이면 422 `request-validation`, NUL은 422 `invalid-value` "Solution에는 NUL 문자를 쓸 수 없습니다". Vendor와 Solution은 서로 독립이며 함께 주면 AND다.
- **DL-R7** Status: `status_key`는 Status key가 같은 Deal이다. 없는 key는 오류 없이 0건이다. 51자 이상은 422 `request-validation`.
- **DL-R8** Forecast: `forecast_key`는 반복 파라미터다(`?forecast_key=a&forecast_key=b`). 보낸 key 중 하나와 같은 Deal(OR)이고, 같은 key를 여러 번 보내면 한 번과 같다. 각 key는 50자 이하, 개수는 100개 이하이며 넘으면 422 `request-validation`. 없는 key나 빈 문자열 key는 오류 없이 어느 Deal과도 맞지 않는다(함께 보낸 다른 key는 그대로 맞는다). 콤마는 구분자가 아니라 key의 일부다. `forecast_outcome`은 Deal의 Forecast 코드 `outcome`으로 거른다: `open`·`won`·`lost`는 그 outcome, `not_lost`는 `open`과 `won`. admin이 추가한 코드도 그 outcome을 따른다(CD). `forecast_key`와 함께 주면 AND다. 다른 값은 422 `request-validation`. (화면은 `forecast_outcome`을 보내지 않는다 — DL-R20.)
- **DL-R9** 연도·분기·월(Expected Close 기준, 양끝 포함)
  - `year`는 1900~9999(밖은 422 `request-validation`)이고 그 해 1월 1일~12월 31일이다.
  - `quarter`는 반복 파라미터로 1~4, 최대 4개다(값이 1~4 밖이거나 5개 이상이면 422 `request-validation`, 오류 문구 항목 "분기는 1~4 중에서 선택하세요."). 같은 분기를 여러 번 보내면 한 번과 같다. 고른 분기 중 하나에 속하면 맞는다(OR, 예: Q1·Q3이면 Q2는 제외). 분기는 첫날·마지막 날을 포함하고 이웃 분기·다른 해의 같은 분기는 제외한다. 분기를 하나도 보내지 않거나 네 개 모두 보내면 분기 조건이 없다.
  - `month`는 1~12(밖은 422 `request-validation`)이고 그 달 1일~말일이다(윤년 2월은 29일까지).
  - 분기(정규화 뒤 1~3개)와 월을 함께 보내면 422 `invalid-value` "Quarter와 월은 함께 선택할 수 없습니다.". 네 분기 + 월은 월만 고른 것과 같다.
  - 연도 없이 분기나 월만 보내면 서버 업무 날짜(TM-R4)의 올해로 채운다(예: 업무 날짜가 2027-01-01이면 2027년). 연도를 보내면 그 연도를 쓴다.
- **DL-R10** 최종 업데이트 기간: `updated_from`·`updated_to`는 `YYYY-MM-DD` 날짜다(형식이 틀리거나 시각이 붙은 값은 422 `request-validation`). 행의 최종 업데이트일(RK-R2)이 `from` 이상 `to` 이하이면 맞는다(날짜 비교) — 양끝 날짜를 포함하고, 한쪽만 주면 그 쪽만 제한한다. 그래서 오래된 Deal도 최근 Action이 있으면 기간에 들어오고, Deal을 수정하기만 해서는 들어오지 않는다. 날짜는 1900-01-01~2999-12-31이어야 하며 밖이면 422 `invalid-value` "updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(`updated_to`도 같은 형식). 시작이 끝보다 늦으면 422 `invalid-value` "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다". 시작과 끝이 같은 날은 그 하루다.
- **DL-R11** Next Action 상태: `next_action_status`는 기준 행(RK-R1)의 상태로 거른다: `open`·`done`·`not_done`은 그 상태, `closed`는 `done`과 `not_done`. 조건이 있으면 Next Action이 없는 Deal은 제외되고, 조건이 없으면 모든 Deal이 나온다. 다른 값(`notDone`·`DONE`·`all`·빈 값 등)은 422 `request-validation`. `total`도 같은 조건으로 센다.
- **DL-R12** 경고 필터: `overdue=true`면 기한초과 Deal만, `stale=true`면 미업데이트 Deal만, 둘 다 켜면 어느 하나라도 해당하는 Deal(OR)이다. 어떤 Deal이 해당하는지는 RK 판정식(RK-R3~R5, RK-R8)이며(종결 Deal 제외 포함), 판정 기준(업무 날짜·저장된 미업데이트 기준일)은 같은 요청의 행 `risk`와 같다(RK-R7). 다른 조건과는 AND이고 `total`도 그 결과다. `false`·`0`이나 생략은 조건 없음, 불리언이 아닌 값(`abc`·`2` 등)은 422 `request-validation`.
- **DL-R13** 정렬: `sort`는 `name`·`revenue_amount`·`revenue_date`·`last_updated_at`·`status`·`owner`·`customer`·`partner`·`vendor`·`forecast` 10개, `order`는 `asc`·`desc`(소문자)이고 기본은 `last_updated_at` `desc`다. 값 이름은 호환을 위해 그대로 두지만 정렬 대상은 최종 업데이트일 `last_updated_on`이고, 같은 날이면 아래 동률 규칙에 따라 Deal code 오름차순이다. 그 밖의 값(`revenueAmount`, `stage`, `DESC`, `up` 등)은 422 `request-validation`. 텍스트 키(Deal Name·담당자·고객 회사·파트너 회사·Vendor 이름)는 소문자로 바꾼 코드 포인트 순이다(대소문자만 다른 값은 같은 값, 한글은 음절 코드 순). 담당자 키는 표시 이름(비었으면 로그인 아이디)이며 퇴사자도 이름으로 정렬된다. `partner`는 활성 파트너 회사명이다. `status`·`forecast`는 그 코드의 **현재** 순서(CD)이며 순서를 바꾸면 결과도 바뀐다. 파트너·Vendor가 없는 Deal은 방향과 무관하게 맨 뒤다. 정렬 값이 같으면 방향과 무관하게 Deal code 오름차순이다. 그래서 같은 조건의 다음 페이지는 앞 페이지에 빠짐·겹침 없이 이어진다.
- **DL-R14** 행(`DealRowResponse`)의 필드는 정확히 `code`, `name`, `owner_user_id`, `owner`(UserRef — 역할 포함), `vendor`(`{id, name}` 또는 null), `solution`, `users`, `status_key`, `forecast_key`, `revenue_amount`, `revenue_date`, `customer`(연락처), `active_partner`(연락처 또는 null), `partner_links`, `quote`(`submitted`·`submitted_date`), `poc`(`state`·`completed_date`), `procurement`, `bant`(`budget`·`authority`·`need`·`timeline` Label id 또는 null), `next_action`(`{text, due_date, status}` 또는 null), `last_updated_on`(날짜), `risk`, `status_changed_on`(날짜), `status_days`, `license_contract_count`, `has_issued_license_contract`, `created_at`, `updated_at`이다. 상세 응답은 이 필드 + `partner_history`(DD)다. 각 필드의 값 규칙은 소유 feature(DE·RK(RK-R1·R2·R6·R9·R10)·LC)를 따른다.
- **DL-R15** Deal 조건 해석(DL-R4~R12)은 서버의 한 곳(`deal_search.conditions`)에만 있고, Forecast 실시간 집계(FC)와 Dashboard 집계(DSH)가 같은 해석을 쓴다. 그래서 같은 조건이면 목록 `total`과 그 집계의 건수가 같다(검증은 FC·DSH).

연도 기준·기간 프리셋
- **DL-R16** `GET /deals/years`(로그인한 모든 역할)는 200 `{"earliest_year": <연도|null>}`(키는 이것 하나)이다. 모든 Deal 중 Expected Close가 가장 이른 Deal의 연도이고 Deal이 없으면 null이다. Deal 삭제·Expected Close 수정을 바로 반영한다(마지막 Deal을 지우면 다시 null). 이 경로는 Deal code로 해석되지 않는다. 읽기만 한다.
- **DL-R17** `GET /deals/updated-periods`(로그인한 모든 역할, DB를 쓰지 않음)는 200 `{today, periods, upcoming}`이다. `today`는 서버 업무 날짜(TM-R4), `periods`는 `[{key, from, to}]` 5개를 이 순서로: `2w`(오늘−14일~오늘), `1m`·`2m`·`3m`·`6m`(n개월 전 같은 날~오늘, TM-R6). `upcoming`은 `[{key, from, to}]` 2개: `1m`·`2m`(오늘~n개월 뒤 같은 날). 그 달에 그 날이 없으면 그 달 말일이다(예: 2026-03-31의 `1m` 시작 2026-02-28, `6m` 시작 2025-09-30, 2026-01-31의 upcoming `1m` 끝 2026-02-28, `2m` 끝 2026-03-31). 날짜는 요청할 때마다 서버 시계로 다시 계산한다(자정이 지나면 `today`가 바뀐다). 이 경로는 Deal code로 해석되지 않는다. (`upcoming`을 쓰는 화면은 NA.)

화면 (frontend, `/deals`, 가드 PL-R29)
- **DL-R18** 화면 틀: 제목(h1) "Deals", `canWrite`(admin·sales, PL-R36)면 "+ Deal 등록" 링크(`/deals/new`). 필터 바(DL-R21) 아래에 경고 범례(RK-R16), 페이지 알림(인라인 저장 알림 등), 목록 오류 배너(PL-R37)를 보인다. 처음 읽는 동안 "불러오는 중…". 응답이 오면 "총 N건". `total`이 0이면 활성 필터(DL-R20)가 있을 때 "조건에 맞는 Deal이 없습니다.", 없을 때 "등록된 Deal이 없습니다.". `total`>0인데 그 페이지가 비면 "N페이지에는 Deal이 없습니다." + "첫 페이지로" 버튼(누르면 1페이지). 한 페이지 20건이고 `total`>0이면 페이저를 보인다. 조건을 바꿔 다시 읽는 동안에는 이전 표를 그대로 보인다(빈 화면으로 깜빡이지 않음).
- **DL-R19** 기본 조건: 필터 키(DL-R20의 15개) 중 값이 있는 키가 하나도 없는 주소(빈 값·공백 값은 없는 것으로 봄)는 기본 조건으로 **이력을 교체**해 바꾼다. 기본 조건은 로그인 사용자가 sales면 `?year=all&mine=1`(연도 전체 + 내 딜만, 2026-11-12 사용자 요청), admin·user면 `?year=all`(연도·Quarter 전체)다(연도 전체 기본은 2026-11-13 사용자 요청 — 그 전에는 올해) — admin·user는 Owner가 될 수 없어(DE-R6) 내 딜만이면 항상 빈 목록이기 때문이다. 정렬 키가 없으므로 기본 정렬은 최종 업데이트 최신순(DL-R13 `last_updated_at` `desc`)이다. 이때 `sort`·`order`는 이어받고 `page`·모르는 키는 버린다. 첫 렌더부터 기본 조건으로 조회하므로 sales의 `mine` 없는 기본 조회 요청은 나가지 않는다. 루트(`/`)·로그인 직후·기억이 없을 때의 상단 메뉴·상세의 목록 링크 등 모든 진입이 같다. 조건이 하나라도 있는 주소는 바꾸지 않고 내 딜만을 더하지도 않는다: Dashboard·Forecast Drill-down 주소, `year=all`만 있는 주소, 기억된 조건(DL-R31)으로 연 주소가 모두 그렇다.
- **DL-R20** URL 쿼리 키와 해석(URL이 정본이고 잘못된 값은 오류 없이 무시한다)
  - 필터 키 15개: `q`(키워드), `owner`, `vendor`, `solution`, `status`, `forecast`, `year`, `quarter`, `month`, `updated_from`, `updated_to`, `mine`, `next_status`, `overdue`, `stale`. 그 밖에 `sort`, `order`, `page`.
  - `q`·`status`·`solution`은 앞뒤 공백을 지운 값(비면 없음). `solution`이 지운 뒤 200자를 넘으면 무시한다.
  - `owner`·`vendor`는 1~2^53−1 정수 id만(예전 UUID·이름 값은 무시). `vendor`는 DL-R26도 따른다.
  - `forecast`는 콤마로 구분한 key 목록이다. 각 항목은 `^[a-z][a-z0-9_]{0,49}$`일 때만 쓰고 정렬·중복 제거한다. 서로 다른 key가 100개를 넘으면 조건 전체를 무시한다. 형식은 맞지만 코드에 없는 key는 그대로 보낸다(서버가 0건). 예전 단일 값(`forecast=won`)은 key 하나다.
  - `year`는 1 이상 정수면 그 연도, `all`이나 없음은 연도 '전체'(보내지 않음).
  - `quarter`는 콤마로 구분한 1~4 목록(형식이 틀린 항목은 버림, 오름차순·중복 제거). 네 개 모두면 화면에는 그대로 보이지만 분기 조건은 보내지 않는다. 예전 단일 값(`quarter=3`)은 분기 하나다.
  - `month`는 월 선택지(DL-R23)에 있을 때만 쓴다. 월을 쓰면 분기는 보내지 않고, 아니면 분기 목록을 보낸다(분기와 월을 함께 보내지 않는다).
  - `updated_from`·`updated_to`는 실제 달력 날짜(`YYYY-MM-DD`, 예: 윤년 아닌 해 02-29는 무시)만 쓴다. 역전된 범위는 그대로 보낸다(서버 422, DL-R25).
  - `mine`·`overdue`·`stale`은 값이 `1`일 때만 켜짐(`yes` 등은 무시). `next_status`는 `open`·`done`·`not_done`·`closed`만(그 밖은 '전체').
  - `sort`는 화면 정렬 키(`name`·`revenueAmount`·`revenueDate`·`lastUpdatedAt`·`statusKey`·`owner`·`customer`·`partner`·`vendor`·`forecastKey`)일 때만 쓰고, `order`가 `asc`·`desc`가 아니면 그 열의 자연 방향이다. `page`는 1 이상 정수(아니면 1).
  - 예전 키(`from`·`to`(Expected Close 기간), `outcome`, `budget`·`authority`·`need`·`timeline`)는 조건에 쓰지 않고 활성 필터로도 세지 않는다.
  - 활성 필터 = 15개 키 중 값이 있는 키(`year=all`은 제외). 빈 목록 문구(DL-R18)를 가른다.
- **DL-R21** 필터 바(`search` 역할 폼 "Deal 필터"): 칸 순서 키워드, 담당자(퇴사자 포함 사용자 선택), Vendor, Solution, Status(전체 + Status 코드 이름), Forecast(DL-R22), Next Action 상태(전체·Open·종료(수행)·종료(미수행)·종료(전체)), 연도(DL-R24), Quarter·월(DL-R23), 최종 업데이트(DL-R25). 마지막 줄 "빠른 조건" 묶음: 체크박스 "내 딜만"·"기한초과"·"미업데이트"와 버튼 "검색"·"초기화"(오른쪽 끝). 목록 필터 칸 위에 필터 관련 오류 배너(연도·Vendor·기간 프리셋 조회 실패)를 보인다. BANT Label 필터는 없다.
  - 키워드·Solution은 "검색" 버튼이나 Enter로만 URL(`q`·`solution`)에 반영한다(앞뒤 공백 제거, 비우면 키 삭제). URL이 바깥에서 바뀌면(초기화·뒤로 가기) 입력란도 따라간다. 나머지 칸·체크박스는 바꾸는 즉시 URL에 반영한다. 체크박스는 켜면 `1`, 끄면 키를 지운다.
  - 조건이 바뀌면 `page`를 지워 1페이지로 간다(페이저로 페이지만 바꿀 때만 유지, `page=1`은 쓰지 않음).
  - 사용자가 마지막 조건을 지워 조건이 하나도 남지 않으면 기본 연도를 되살리지 않고 `year=all`(연도 전체)로 남긴다.
  - "초기화"는 기본 조건(DL-R19: sales `?year=all&mine=1`, admin·user `?year=all`)으로 바꾸고(새 이력, 정렬도 지움) 모든 칸을 비운다(sales는 "내 딜만"만 체크된 상태). 그 조건이 기억된다(DL-R31).
  - sales가 기본 조건에서 "내 딜만"을 끄면 다른 체크박스와 같이 `mine` 키를 지운다(`mine=0` 같은 값을 쓰지 않는다). `year`가 남아 조건 없는 주소가 아니므로 기본 조건으로 되돌아가지 않고, 그 주소가 기억된다.
  - URL의 값으로 모든 칸(키워드·Solution 입력란, 선택, 체크)을 복원한다.
- **DL-R22** Forecast 다중 선택: 버튼 "Forecast"가 패널을 열고 Forecast 코드를 현재 코드 순서로 체크박스로 보인다(+ "전체" 버튼, Escape로 닫으면 포커스가 버튼으로 돌아간다). 체크하면 URL `forecast`에 정렬된 key를 콤마로 쓴다(누른 순서와 무관하게 같은 URL, 하나면 단일 값). 모두 끄거나 "전체"를 누르면 키를 지운다. 버튼 요약: 선택 없음 "전체", 하나면 그 코드 이름(코드에 없으면 key), 전부면 "모두 선택", outcome이 lost가 아닌 코드 전부면 "Lost 제외", open 코드 전부면 "Open 전체", 그 밖은 "N개 선택".
- **DL-R23** Quarter·월: Quarter는 Q1~Q4 체크박스와 "전체" 버튼이며 연도와 무관하게 언제나 쓸 수 있다. 체크하면 URL `quarter`에 오름차순 콤마(하나면 단일 값), 넷 다 체크해도 눌린 상태와 URL을 유지하고 요약은 "전체", 마지막 하나를 끄거나 "전체"를 누르면 키를 지운다. 요약은 "전체" 또는 "Q1, Q3". 월 선택지는 고른 분기(넷 다·없음이면 12달)의 월 합집합이고 "전체"가 첫 항목이다. 분기를 바꿀 때 보이던 월이 새 선택지에 있으면 유지하고 없으면 지운다. 선택지 밖이라 숨어 있던 월은 분기를 바꾸거나 "전체"를 누르면 지운다. "전체"(분기 해제)는 보이던 월을 유지한다. 연도가 전체일 때 분기를 고르면 Quarter 아래에, 분기 없이 월만 고르면 월 아래에 "연도가 전체이면 올해(YYYY) 기준입니다."를 보인다(접근성 설명으로 연결). 연도를 고르면 안내가 사라진다.
- **DL-R24** 연도 선택지(범위 규칙은 Deals 목록·Dashboard·Forecast 공용이고 "전체"는 Deal 목록에만 있다 — Dashboard DSH-R16·Forecast FC-R26은 "전체" 없이 범위만 쓴다): Deal 목록은 "전체"(값 `all`, 첫 항목) + `min(earliest_year, 올해)`부터 올해+1까지 연속 오름차순. Deal이 없거나 연도 기준을 읽는 동안·실패하면 올해·내년만이고, 실패하면 오류 배너를 보이되 목록은 그대로 조회된다. 읽기가 끝나면 선택을 바꾸지 않고 선택지만 넓힌다. URL 연도가 선택지 밖의 양의 정수면 한 번만 더해 선택된 상태로 보인다. 내년보다 뒤의 Deal이 있어도 그 연도는 선택지에 없다. 연도 '전체'는 서버에 연도를 보내지 않는다.
- **DL-R25** 최종 업데이트 기간: 선택 상자 "최종 업데이트"는 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정(7개)이고 서버 프리셋(DL-R17)에 없는 키는 비활성이다. 프리셋을 고르면 캐시를 쓰지 않고 프리셋을 서버에 다시 물어 그 `from`·`to`를 URL `updated_from`·`updated_to`에 쓴다(늦게 온 이전 응답은 버린다). 다시 묻기가 실패하면 URL은 그대로 두고 오류 배너를 보인다. "전체"는 두 키를 지운다. "직접 지정"은 URL을 바꾸지 않고 "시작일"·"종료일" 날짜 칸(`DateInput`, UI-R6)을 현재 URL 날짜로 채워 보인다. 날짜 칸은 비었거나 올바른 날짜가 될 때만 URL을 바꾼다(`yyyymmdd` 입력은 ISO로, 덜 쳤거나 없는 날짜는 URL을 바꾸지 않고 칸이 문구를 보인다). 시작만 넣어도 조회된다. 역전된 범위는 서버 문구(DL-R10)를 목록 오류 배너로 보인다. 표시: URL 날짜가 오늘의 프리셋과 정확히 같으면 그 프리셋, 둘 다 없으면 전체, 그 밖(한쪽만 있음 포함)은 직접 지정. 프리셋을 읽지 못해도 URL 날짜로 조회한다. 뒤로 가기로 URL 날짜가 바뀌면 직접 지정 칸을 닫고 이 표시 규칙을 따른다.
- **DL-R26** Vendor 선택: 선택지 값은 Vendor id, 표시는 이름이다. Vendor 목록을 읽은 뒤 URL `vendor`가 목록에 없는 id면 선택은 "전체"로 보이고 조회에도 보내지 않는다(표시 = 조회 조건). 목록을 읽는 동안·실패하면 URL id를 조회에 쓰고 선택지에 "선택한 Vendor" 하나를 더해 선택된 상태로 보인다(실패하면 오류 배너). Solution 텍스트 조건은 Vendor와 무관하게 유지된다(Vendor를 바꿔도 Solution은 남고, Solution만 검색해도 Vendor를 채우지 않는다).
- **DL-R27** 정렬 머리글: 13열 중 Next Action·Due·Next Action 상태를 뺀 10열이 정렬 버튼이다(DL-R28 순서). 정렬 중인 열에만 방향 표시와 `aria-sort`가 있다. 지금 정렬하지 않는 열을 누르면 그 열의 자연 방향(금액·최종 업데이트 내림차순, 나머지 오름차순)으로 시작하고, 같은 열을 다시 누르면 방향을 바꾼다. 정렬을 바꾸면 1페이지로 간다. 정렬이 없는 주소는 최종 업데이트 내림차순(머리글에 표시)이다. URL의 정렬 값으로 머리글 표시를 복원한다. 행 순서는 서버 순서(DL-R13) 그대로다.
- **DL-R28** 표 열(13개, 이 순서): Deal, 담당자, 고객사, 파트너사, Vendor, Status, Forecast, 금액(단위:원), Expected Close, Next Action, Due, Next Action 상태, 최종 업데이트. 칸 값: Deal = 빠른 보기 토글 + 이름 링크(`/deals/<code>`) + 경고 배지(RK-R15); 담당자 = 이름(퇴사자는 "이름(퇴사)"); 고객사 = 고객 회사명; 파트너사 = 활성 파트너 회사명, 없으면 "—"; Vendor = 이름, 없으면 "—"; Status·Forecast = 코드 배지; 금액 = 원 단위 콤마; Expected Close = 날짜; Next Action = 기준 행 내용이 링크(`/deals/<code>?tab=actions`, 링크 안에는 내용만)이고 Due = 기한(기한초과면 강조, RK-R16), Next Action 상태 = 라벨(Open·종료(수행)·종료(미수행)); Next Action이 없으면 세 칸 모두 "—"이고 링크가 없다; 최종 업데이트 = 상대 일수(RK-R16), 마우스를 올리면 `YYYY-MM-DD`. Deal code는 화면 글자·접근성 이름·title 어디에도 보이지 않고 링크 주소에만 있다(키워드로 code를 검색하는 것은 된다). BANT 열·Status 체류 일수는 목록에 없다.
- **DL-R29** 빠른 보기: Deal 칸의 토글 버튼(접근성 이름 "<Deal 이름> 빠른 보기", `aria-expanded`)을 누르면 행 아래에 13열 너비로 펼친다(다시 누르면 접는다). 항목: 견적(`<제출 여부> (<날짜>)`, 없으면 "—"), POC(같은 형식), 고객 담당자(이름·직급·이메일·전화 중 있는 값을 " · "로), 파트너 영업대표(같은 형식, 없으면 "파트너 없음"), Budget·Authority·Need·Timeline(고른 Label 이름, 고르지 않았으면 "—", Label 목록을 읽는 동안 "불러오는 중…", 실패하면 "불러오지 못함"), Users count(0도 "0", 천 단위 콤마), 구매절차(없으면 "—"), 링크 "상세 보기"(`/deals/<code>`). 목록은 빠른 보기를 열기 전에는 BANT Label 목록을 읽지 않는다(그래서 Label 조회 실패가 목록에 보이지 않는다).
- **DL-R30** 인라인 편집 진입(목록 편집기): `canWrite`일 때만 Status·Forecast·금액·Expected Close 4칸이 버튼(접근성 이름 "<Deal 이름> <열 이름> 편집", 열 이름은 Status·Forecast·금액(단위:원)·Expected Close)이고, user에게는 값만 보인다. Deal 이름·담당자·Vendor 등 다른 칸은 편집할 수 없다. 버튼을 누르면 그 칸이 편집기가 되고 입력란에 포커스가 간다(저장·취소 버튼 없음).
  - Status·Forecast: 선택 상자에서 고르는 순간 저장 요청을 시작한다. 같은 값이면 요청 없이 닫는다. 바꾸지 않고 포커스가 나가면 원래 값으로 닫는다. (동기화 대화상자·서버 적용은 DD, Won 이탈 계약 처리는 LC.)
  - 금액: 원 단위 콤마 값으로 시작한다. Enter나 포커스 이동(blur)에 저장하고 글자마다 저장하지 않는다. Esc는 입력을 버리고 원래 값으로 닫는다. 형식이 틀리면 칸 아래 `alert`로 금액 입력 문구(DE)를 보이고 편집을 유지한다. 값이 원래와 같으면 요청하지 않는다(1,000원 미만 차이도 다른 값으로 저장).
  - Expected Close: 날짜 입력(`DateInput`, UI-R6·UI-R9)에서 고르거나 `yyyymmdd`를 다 치는 순간 저장한다. 덜 친 동안은 저장하지 않고 문구도 없다. 없는 날짜에 Enter면 날짜 칸 문구를 보이고 편집을 유지한다. 비우면 "Expected Close를 입력하세요."를 보이고 편집을 유지한다. 텍스트 칸과 달력 버튼 사이 이동으로는 닫히지 않고, 편집 영역 밖으로 포커스가 나가면 저장 없이 닫는다(덜 친 값도 오류 없이 버린다).
  - 저장에 성공하면 편집기를 닫고 칸 옆에 ✓ 표시를 2.5초 보이며 페이지 알림을 보인다: 함께 바뀐 값이 있으면 "<Deal 이름>: <서버 알림>", 없으면 Status·Forecast "<Deal 이름>: Status가 '<코드 이름>'(으)로 변경되었습니다."(조사는 이름에 맞춤), 금액 "<Deal 이름>: 금액(단위:원)이 '<콤마 값>'(으)로 변경되었습니다.", Expected Close "<Deal 이름>: Expected Close가 '<날짜>'(으)로 변경되었습니다.". 실패하면 편집기 안에 서버 문구(없으면 "저장하지 못했습니다.")를 보이고 다시 시도할 수 있다. 편집을 마치면 포커스가 그 칸의 편집 버튼으로 돌아온다.
- **DL-R31** 조건 기억: 목록이 보일 때마다 로그인 사용자의 마지막 목록 쿼리를 sessionStorage 키 `deals.listSearch:<사용자 id>`에 저장한다(탭·사용자별, 새로고침해도 유지). 저장 전에 아는 키(필터 15개 + `sort`·`order`·`page`)만 남기고 `owner`·`vendor`는 정수 id일 때만 남긴다(그 밖의 값은 검증하지 않음). 남은 것이 없으면 항목을 지운다. 저장소를 쓸 수 없으면 기억만 포기한다. "목록으로" 경로는 상단 메뉴 Deals, 상세의 목록 링크, Deal 삭제 뒤 이동(알림은 한 번만), 새 Deal 폼의 취소, 상세·수정 화면의 오류 화면 링크가 쓰며 기억된 쿼리로 `/deals?…`(없으면 `/deals` → DL-R19)다. 목록 화면 안에서는 기억 대신 지금 URL을 바로 쓴다(조건·정렬·페이지를 바꾸면 메뉴 링크가 즉시 따라감). 다른 사용자는 이전 사용자의 조건을 물려받지 않는다. 예전 키(BANT·`outcome`·`from`·`to`)는 복원하지 않는다. (수정 폼의 취소는 상세로 돌아간다 — DE.)
- **DL-R32** 게이트웨이(`gateway/http/deals.ts`): `list`는 정한 조건만 snake_case 쿼리로 보낸다(`keyword`, `owner_user_id`, `vendor_id`, `solution`, `status_key`, `forecast_key`(key마다 반복), `forecast_outcome`, `year`, `quarter`(분기마다 반복), `month`, `updated_from`, `updated_to`, `mine`(true일 때만), `overdue`·`stale`(true일 때만), `next_action_status`(`notDone` → `not_done`), `sort`(화면 키 → 서버 값: `revenueAmount`→`revenue_amount`, `revenueDate`→`revenue_date`, `lastUpdatedAt`→`last_updated_at`, `statusKey`→`status`, `forecastKey`→`forecast`, 나머지 같음), `order`, `offset`, `limit`). 조건이 없으면 쿼리 없이 `GET /deals`다. id는 정수로 보낸다. 폐지된 파라미터(`bant_*`, `vendor`, `solution_id`, `revenue_from`·`revenue_to`, 단일 `forecast_key` 필드 등)는 보내지 않는다. 응답은 행을 camelCase로 바꾸고 `total`·`offset`·`limit`을 그대로 준다. `years`는 `earliest_year` → `earliestYear`(null 유지), `updatedPeriods`는 `today`와 아는 키(`periods` 5개·`upcoming` 2개)만 `{key, from, to}`로 남긴다. 오류는 PL-R39.

### 2.4 상태와 전이

해당 없음(조회 feature). 화면의 조건 상태는 URL이다: 조건 없는 주소 → (DL-R19 교체) → `year=all`(sales는 `&mine=1`) → (사용자 변경) → 임의 조건 → (마지막 조건 삭제) → `year=all` / (초기화) → `year=all`(sales는 `&mine=1`).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /deals`, `GET /deals/years`, `GET /deals/updated-periods` | 401 | 가능 | 가능 | 가능 |
| 화면 `/deals` 목록·빠른 보기·조건 기억 | `/login`으로 | 가능 | 가능 | 가능 |
| "+ Deal 등록" 링크·인라인 편집 진입 | — | 숨김 | 보임 | 보임 |

세 경로는 업무 조회(PL-R2)라 역할 가드·CSRF가 없다. `mine`은 요청자 기준이다(DL-R5). 인라인 편집의 서버 권한은 DD(`POST /deals/{code}/changes`, 업무 쓰기 PL-R6).

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/deals` | query `keyword?`(≤100), `owner_user_id?`(id), `mine?`(bool, 기본 false), `vendor_id?`(id), `solution?`(트림 후 ≤200), `status_key?`(≤50), `forecast_key?`(반복, 각 ≤50, ≤100개), `forecast_outcome?`(`open`·`won`·`lost`·`not_lost`), `year?`(1900~9999), `quarter?`(반복, 1~4, ≤4개), `month?`(1~12), `updated_from?`·`updated_to?`(date), `overdue?`·`stale?`(bool, 기본 false), `next_action_status?`(`open`·`done`·`not_done`·`closed`), `sort?`(DL-R13, 기본 `last_updated_at`), `order?`(`asc`·`desc`, 기본 `desc`), `offset?`(≥0, 기본 0), `limit?`(1~200, 기본 20) | 200 `CountedPage[DealRowResponse]` `{items, total, offset, limit}` | 401, 422 `request-validation`·`invalid-value` |
| GET `/deals/years` | — | 200 `{earliest_year: int\|null}` | 401 |
| GET `/deals/updated-periods` | — | 200 `{today: date, periods: [{key: "2w"\|"1m"\|"2m"\|"3m"\|"6m", from: date, to: date}], upcoming: [{key: "1m"\|"2m", from: date, to: date}]}` | 401 |

- openapi: `forecast_key`·`quarter`는 배열 파라미터(`quarter` 항목 1~4 문서화), `overdue`·`stale`은 기본 false인 boolean, `sort`는 10개 값 enum, `solution`은 maxLength 200 문서화, `bant_*` 파라미터는 없다. `earliest_year`는 nullable 정수, 프리셋 항목 키는 `from`·`to`. 공통 오류 문서화는 PL-R21.

### 2.7 화면 동작

DL-R18~DL-R32.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 모르는·폐지 파라미터, 형식·범위 밖 값(페이지, id, 키워드 101자, Solution 201자, key 51자·101개, 분기·월·연도 범위, 분기 5개, 날짜 형식, 정렬, 불리언, enum) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12, 분기 항목 msg "분기는 1~4 중에서 선택하세요.") |
| 키워드 NUL | 422 `invalid-value` | 검색어에는 NUL 문자를 쓸 수 없습니다 |
| Solution NUL | 422 `invalid-value` | Solution에는 NUL 문자를 쓸 수 없습니다 |
| 분기와 월 동시 | 422 `invalid-value` | Quarter와 월은 함께 선택할 수 없습니다. |
| 최종 업데이트 날짜 범위 밖 | 422 `invalid-value` | updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다 (`updated_to`도 같은 형식) |
| 최종 업데이트 기간 역전 | 422 `invalid-value` | 최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다 |
| 미인증 | 401 `unauthenticated` | 로그인이 필요합니다(PL-R5) |

화면 문구: "총 N건", "조건에 맞는 Deal이 없습니다.", "등록된 Deal이 없습니다.", "N페이지에는 Deal이 없습니다."·"첫 페이지로", "불러오는 중…", "연도가 전체이면 올해(YYYY) 기준입니다.", "선택한 Vendor", "파트너 없음", "불러오지 못함", "상세 보기", "Expected Close를 입력하세요.", "저장하지 못했습니다.", 인라인 저장 알림(DL-R30). 서버 문구 표시는 PL-R37.

## 3. Business use case

### DL-UC1 목록 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, `/deals`(또는 `/`, 메뉴 Deals)
- 기본 흐름: 조건이 없으면 연도 전체 Deal 목록(sales는 내 딜만)으로 바뀌어 최종 업데이트 최신순 20건을 보인다(DL-R19, R1, R18, R28)
- 대안: 페이저로 다음 페이지, 끝을 넘은 페이지에서 "첫 페이지로"
- 예외: 목록을 읽지 못하면 오류 배너, 결과가 없으면 빈 문구
- 결과: 조건에 맞는 Deal 한 페이지와 전체 건수

### DL-UC2 조건으로 찾기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 필터 칸을 고르거나 키워드·Solution을 입력해 검색 → URL이 바뀌고 1페이지부터 다시 조회(DL-R3~R12, R20~R26)
- 대안: 초기화, 마지막 조건 삭제(연도 전체), Dashboard·Forecast에서 조건이 담긴 주소로 들어옴(DSH·FC)
- 예외: 잘못된 URL 값은 무시, 서버 422는 오류 배너(기간 역전 등), 연도·Vendor·프리셋 조회 실패는 필터 오류 배너
- 결과: 모든 조건을 AND로 만족하는 Deal

### DL-UC3 정렬하기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 머리글을 누름 → 자연 방향으로 정렬, 다시 누르면 반대 방향(DL-R13, R27)
- 결과: 서버 정렬 순서(동률은 code 순)의 1페이지

### DL-UC4 행 요약 보기·상세로 이동
- 행위자: 로그인한 모든 역할
- 기본 흐름: 빠른 보기를 펼쳐 견적·POC·담당자·BANT 등을 본다 → "상세 보기"나 이름 링크로 상세, Next Action 링크로 Actions 탭(DL-R28, R29)
- 결과: 상세 화면(DD)으로 이동하고 목록 조건은 기억된다(DL-R31)

### DL-UC5 목록에서 바로 고치기
- 행위자: sales·admin
- 기본 흐름: Status·Forecast·금액·Expected Close 칸을 눌러 값을 바꾼다 → 즉시 저장 → 알림과 ✓(DL-R30)
- 대안: Esc·포커스 이동으로 취소, 같은 값은 요청 없음, 동기화·Won 이탈 대화상자(DD·LC)
- 예외: 형식이 틀린 값은 편집 유지, 서버 실패 문구
- 결과: 바뀐 Deal 값(서버 적용은 DD)

### DL-UC6 같은 목록으로 돌아오기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 목록 → 상세·수정·삭제·오류 화면 → 목록 링크·상단 메뉴 → 마지막 조건·정렬·페이지의 목록(DL-R31)
- 대안: 다른 사용자로 로그인하면 기억 없음 → 기본 조건
- 결과: 같은 조건의 목록

### DL-UC7 선택지 기준 읽기
- 행위자: 로그인한 모든 역할의 화면(Deals 목록·Dashboard·Forecast·Actions 탭)
- 기본 흐름: 연도 기준(`/deals/years`)과 기간 프리셋(`/deals/updated-periods`)을 읽어 선택지를 만든다(DL-R16, R17, R24, R25)
- 예외: 읽지 못하면 올해·내년만, 프리셋 비활성과 오류 배너
- 결과: 서버 날짜 기준 선택지

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), PARK(sales), VIEWER(user). 서버 업무 날짜 예: 2026-10-15(Asia/Seoul). backend 케이스는 Fake UoW(Deal·연락처·코드·사용자·Vendor·Action·경고 기준 Fake)를 쓰는 유스케이스 단위 테스트와 FakeUseCases + TestClient를 쓰는 web 단위 테스트, frontend 케이스는 Fake 게이트웨이를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| DL-001 | 조건 없이 조회하면 offset 0·limit 20의 페이지가 최종 업데이트 최신순으로 온다 | DL-R1, DL-R2, DL-R13, DL-UC1 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-002 | total은 페이지와 무관하고 끝을 넘은 페이지는 비며 Deal이 없으면 []·0이다 | DL-R1, DL-UC1 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-003 | 모든 역할이 목록을 보고 미인증은 401이다 | DL-R1, DL-UC1 | backend | `web/test_deal_list_http_cases.py` |
| DL-004 | limit 1·200은 되고 0·201·offset −1은 422 request-validation이다 | DL-R2, DL-UC1 | backend | `web/test_deal_list_http_cases.py` |
| DL-005 | 키워드는 Deal Name·code·고객 회사·활성 파트너 회사를 대소문자 무시로 찾는다 | DL-R4, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-006 | 키워드는 비활성 파트너·담당자 이름·Vendor·Solution을 찾지 않는다 | DL-R4, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-007 | 키워드의 앞뒤 공백은 지우고 공백뿐이면 조건 없음이며 %·_는 글자 그대로다 | DL-R4, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-008 | 키워드 100자는 되고 101자는 422 request-validation이다 | DL-R4, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-009 | 키워드에 NUL이 있으면 500이 아니라 422 invalid-value다 | DL-R4, DL-R3, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-010 | owner_user_id는 담당자가 정확히 같은 Deal(퇴사자 포함)이고 형식이 틀리면 422다 | DL-R5, DL-UC2 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-011 | mine=true는 요청자 Deal만이고 owner_user_id보다 우선하며 불리언이 아니면 422다 | DL-R5, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-012 | vendor_id는 그 Vendor의 Deal이고 없는 id는 0건, 정수가 아니면 422다 | DL-R6, DL-UC2 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-013 | solution은 트림한 텍스트의 대소문자 무시 부분 일치이고 와일드카드는 글자이며 Vendor와 AND다 | DL-R6, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-014 | solution은 트림 후 200자까지 되고 201자는 422 request-validation, NUL은 invalid-value다 | DL-R6, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-015 | status_key는 같은 Status의 Deal이고 없는 key는 0건, 51자는 422다 | DL-R7, DL-UC2 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-016 | forecast_key를 하나 또는 여러 번 보내면 그중 하나인 Deal이고 중복은 한 번이다 | DL-R8, DL-UC2 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-017 | 모르는·빈 forecast_key는 오류 없이 일치가 없고 콤마는 key의 일부다 | DL-R8, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-018 | forecast_key 50자·100개는 되고 51자·101개는 422다 | DL-R8, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-019 | forecast_outcome은 코드 outcome으로 거르고 not_lost는 open·won이며 추가한 Open 코드도 들어간다 | DL-R8, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-020 | forecast_outcome은 forecast_key와 AND이고 모르는 값은 422다 | DL-R8, DL-UC2 | backend | `application/test_deal_list_search_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-021 | year만 주면 그 해 1월 1일~12월 31일 Deal이다 | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-022 | year+quarter는 그 분기 첫날·마지막 날을 포함하고 이웃 분기·다른 해는 뺀다 | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-023 | 여러 분기는 OR이고 떨어진 분기 사이는 빠지며 중복은 한 번이다 | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-024 | 네 분기를 모두 보내면 분기 조건이 없는 것과 같다 | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-025 | 연도 없는 분기는 서버 업무 날짜의 올해 분기다(새해 경계 포함) | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-026 | year+month는 그 달 1일~말일(윤년 2월 29일)이고 month만은 올해 그 달이다 | DL-R9, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-027 | 분기와 월을 함께 보내면 422 invalid-value이고 네 분기+월은 월만 고른 것이다 | DL-R9, DL-R3, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-028 | 분기 1~4 밖·5개, 월 1~12 밖, 연도 1900~9999 밖은 422 request-validation이다 | DL-R9, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-029 | 최종 업데이트 기간은 양끝 날짜를 포함하고 한쪽만 줄 수 있다 | DL-R10, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-030 | 최종 업데이트 기간은 최종 업데이트일을 날짜로 비교한다 | DL-R10, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py`, `web/test_deal_list_openapi.py` |
| DL-031 | 최근 Action은 오래된 Deal을 기간에 넣고 Deal 수정은 넣지 않는다 | DL-R10, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-032 | 기간 역전·1900~2999 밖 날짜는 422 invalid-value, 양끝 날짜는 되고 형식이 틀리면 request-validation이다 | DL-R10, DL-R3, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py`, `web/test_deal_list_http_cases.py` |
| DL-033 | next_action_status는 기준 행 상태로 거르고 total도 같다 | DL-R11, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py`, `gateway/contract/actionsStatus.contract.ts` |
| DL-034 | closed는 종료(수행)·종료(미수행)이고 Next Action 없는 Deal은 빠지며 조건이 없으면 모두 나온다 | DL-R11, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-035 | 허용하지 않는 next_action_status는 422다 | DL-R11, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-036 | overdue만·stale만 켜면 해당 Deal만 나오고 판정 기준은 행 risk와 같다 | DL-R12, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-037 | overdue·stale을 함께 켜면 OR이고 다른 조건과는 AND다 | DL-R12, DL-UC2 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-038 | overdue·stale의 false·0은 조건 없음이고 불리언이 아니면 422다 | DL-R12, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-039 | 여러 조건은 모두 AND이고 total은 필터 뒤 전체 건수다 | DL-R3, DL-R1, DL-UC2 | backend | `application/test_deal_list_search_cases.py` |
| DL-040 | 정렬 10개 기준마다 오름·내림차순 결과가 기대한 순서다 | DL-R13, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-041 | 정렬 값이 같으면 방향과 무관하게 code 오름차순이고 대소문자만 다른 이름은 같은 값이다 | DL-R13, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-042 | 파트너·Vendor 정렬에서 값이 없는 Deal은 방향과 무관하게 맨 뒤다 | DL-R13, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-043 | Status·Forecast 정렬은 코드의 현재 순서를 따른다 | DL-R13, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-044 | 담당자 정렬은 표시 이름(없으면 아이디) 대소문자 무시이고 퇴사자도 이름으로 정렬된다 | DL-R13, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-045 | 정렬한 목록의 다음 페이지는 앞 페이지에 이어지고 total은 같다 | DL-R13, DL-R2, DL-UC3 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-046 | 화이트리스트 밖 sort·order는 422다 | DL-R13, DL-UC3 | backend | `web/test_deal_list_http_cases.py` |
| DL-047 | 모르는 파라미터와 폐지된 파라미터는 조용히 무시하지 않고 422다 | DL-R3, DL-UC2 | backend | `web/test_deal_list_http_cases.py` |
| DL-048 | 행은 문서화된 필드를 갖고 담당자 역할·고객·활성 파트너·Vendor 참조가 담긴다 | DL-R14, DL-UC1 | backend | `web/test_deal_list_http_cases.py` |
| DL-049 | 연도 기준은 가장 이른 Expected Close 연도이고 Deal이 없으면 null이다 | DL-R16, DL-UC7 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-050 | 연도 기준은 Deal 삭제·Expected Close 수정을 바로 반영한다 | DL-R16, DL-UC7 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-051 | 모든 역할이 연도 기준을 읽고 경로는 Deal code가 아니며 미인증은 401이다 | DL-R16, DL-UC7 | backend | `web/test_deal_list_http_cases.py` |
| DL-052 | 기간 프리셋은 서버 업무 날짜의 today·과거 5개·향후 2개이고 시계를 따른다 | DL-R17, DL-UC7 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-053 | 그 날이 없는 달의 프리셋 경계는 말일이다 | DL-R17, DL-UC7 | backend | `application/test_deal_list_period_sort_cases.py` |
| DL-054 | 모든 역할이 기간 프리셋을 읽고 경로는 Deal code가 아니며 미인증은 401이다 | DL-R17, DL-UC7 | backend | `web/test_deal_list_http_cases.py` |
| DL-055 | admin의 조건 없는 주소는 연도 전체 기본 조건으로 바뀌고 최종 업데이트 최신순으로 조회한다 | DL-R19, DL-UC1 | frontend | `features/deals/list/DealsPage.defaults.test.tsx` |
| DL-056 | 기본 조건은 정렬을 이어받고 page·모르는 키를 버리며 이력에 남기지 않는다 | DL-R19, DL-UC1 | frontend | `features/deals/list/DealsPage.defaults.test.tsx` |
| DL-057 | 루트·로그인 직후·기억 없는 메뉴·기억 없는 상세 목록 링크 모두 기본 조건이다 | DL-R19, DL-R31, DL-UC1 | frontend | `features/deals/list/DealsPage.defaults.test.tsx` |
| DL-058 | 표는 13열을 순서대로 보이고 칸 값 규칙을 따른다 | DL-R28, DL-UC1 | frontend | `features/deals/list/DealsPage.columns.test.tsx`, `features/deals/list/DealsPage.nextActionLink.test.tsx`, `features/deals/list/DealsPage.test.tsx`, `features/deals/list/DealsPage.today.test.tsx` |
| DL-059 | Next Action 세 칸은 Actions 탭 링크·Due·상태 라벨이고 없으면 모두 '—'다 | DL-R28, DL-UC4 | frontend | `features/deals/list/DealsPage.columns.test.tsx`, `features/deals/list/DealsPage.nextActionLink.test.tsx`, `features/deals/list/DealsPage.nextActionStatus.test.tsx` |
| DL-060 | 목록에는 Deal code 글자가 없지만 code로 검색할 수 있다 | DL-R28, DL-R4, DL-UC2 | frontend | `features/deals/list/DealsPage.code.test.tsx` |
| DL-061 | 한 페이지 20건과 페이저, "총 N건"을 보인다 | DL-R18, DL-UC1 | frontend | `features/deals/list/DealsPage.test.tsx` |
| DL-062 | 빈 목록은 조건 유무에 따라 다른 문구이고 끝을 넘은 페이지는 첫 페이지로 버튼을 준다 | DL-R18, DL-UC1 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.riskFilter.test.tsx` |
| DL-063 | 다음 조건을 읽는 동안 이전 표를 유지하고 목록 오류는 배너로 보인다 | DL-R18, DL-UC1 | frontend | `features/deals/list/DealsPage.keepPrevious.test.tsx` |
| DL-064 | user에게는 Deal 등록 링크와 편집 버튼이 없다 | DL-R18, DL-R30, DL-UC1 | frontend | `features/deals/list/DealsPage.inline.test.tsx`, `features/deals/list/DealsPage.test.tsx` |
| DL-065 | 키워드·Solution은 검색 버튼·Enter로만 URL에 반영되고 비우면 지워진다 | DL-R21, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-066 | 담당자(퇴사자 포함)·Vendor·Status·내 딜만은 바꾸는 즉시 반영된다 | DL-R21, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-067 | 목록에 없는 Vendor id는 전체로 보이고 보내지 않으며 Vendor를 못 읽는 동안은 URL id를 쓴다 | DL-R26, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.vendorLoadError.test.tsx`, `features/deals/list/DealsPage.vendorMismatch.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-068 | 조건을 바꾸면 1페이지로 돌아간다 | DL-R21, DL-UC2 | frontend | `features/deals/list/DealsPage.forecastMulti.test.tsx`, `features/deals/list/DealsPage.quarterMulti.test.tsx` |
| DL-069 | 마지막 조건을 지우면 기본 연도가 아니라 연도 전체로 남는다 | DL-R21, DL-UC2 | frontend | `features/deals/list/DealsPage.defaults.test.tsx`, `features/deals/list/DealsPage.forecastMulti.test.tsx` |
| DL-070 | 초기화는 연도 전체 기본 조건으로 새 이력을 만들고 모든 칸을 비운다 | DL-R21, DL-UC2 | frontend | `features/deals/list/DealsPage.defaults.test.tsx`, `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.riskFilter.test.tsx` |
| DL-071 | URL 조건으로 모든 칸을 복원한다 | DL-R20, DL-R21, DL-UC6 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-072 | URL의 잘못된 값·예전 키는 조회에 쓰지 않고 활성 필터로도 세지 않는다 | DL-R20, DL-UC2 | frontend | `features/deals/list/DealsPage.bant.test.tsx`, `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.nextActionStatus.test.tsx`, `features/deals/list/DealsPage.noOutcome.test.tsx`, `features/deals/list/DealsPage.riskFilter.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-073 | Forecast 다중 선택은 정렬된 key를 콤마로 URL에 쓰고 전체로 지운다 | DL-R22, DL-UC2 | frontend | `features/deals/list/DealsPage.forecastMulti.test.tsx` |
| DL-074 | Forecast 버튼 요약은 선택에 따라 전체·이름·모두 선택·Lost 제외·Open 전체·N개 선택이다 | DL-R22, DL-UC2 | frontend | `features/deals/list/DealsPage.forecastMulti.test.tsx` |
| DL-075 | URL forecast는 예전 단일 값을 읽고 틀린 항목은 버리며 100개를 넘으면 조건 전체를 무시한다 | DL-R20, DL-R22, DL-UC2 | frontend | `features/deals/list/DealsPage.forecastMulti.test.tsx` |
| DL-076 | Quarter 다중 선택은 오름차순 목록을 URL에 쓰고 넷 다 눌러도 유지하되 분기 조건은 보내지 않는다 | DL-R23, DL-R20, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.quarterMulti.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-077 | 연도가 전체일 때 분기나 월을 고르면 올해 기준 안내를 보인다 | DL-R23, DL-UC2 | frontend | `features/deals/list/DealsPage.period.test.tsx`, `features/deals/list/DealsPage.quarterMulti.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-078 | 월 선택지는 고른 분기들의 월이고 그 안의 월이면 월만, 아니면 분기만 보낸다 | DL-R23, DL-R20, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.period.test.tsx`, `features/deals/list/DealsPage.quarterMulti.test.tsx`, `features/deals/list/DealsPage.vendorQuarter.test.tsx` |
| DL-079 | 분기를 바꾸면 새 선택지에 있는 월은 유지하고 없는 월·숨은 월은 지운다 | DL-R23, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.period.test.tsx`, `features/deals/list/DealsPage.quarterMulti.test.tsx` |
| DL-080 | 연도 선택지는 전체 + 가장 이른 연도~내년이고 URL 연도를 한 번 더한다 | DL-R24, DL-UC7 | frontend | `features/deals/list/DealsPage.today.test.tsx`, `features/deals/list/DealsPage.yearOptions.test.tsx` |
| DL-081 | 연도 기준을 읽는 동안·실패하면 올해·내년만 보이고 실패는 배너지만 목록은 나온다 | DL-R24, DL-UC7 | frontend | `features/deals/list/DealsPage.yearOptions.test.tsx` |
| DL-082 | 연도 전체는 서버에 연도를 보내지 않고 상세 왕복·메뉴에서 복원된다 | DL-R24, DL-R20, DL-UC6 | frontend | `features/deals/list/DealsPage.defaults.test.tsx`, `features/deals/list/DealsPage.yearOptions.test.tsx` |
| DL-083 | Next Action 상태 선택은 5개이고 URL next_status로 반영·복원된다 | DL-R21, DL-R20, DL-UC2 | frontend | `features/deals/list/DealsPage.nextActionStatus.test.tsx` |
| DL-084 | 기한초과·미업데이트 체크는 overdue=1·stale=1로 반영되고 둘 다 켜면 어느 하나라도 해당한다 | DL-R21, DL-R12, DL-UC2 | frontend | `features/deals/list/DealsPage.riskFilter.test.tsx` |
| DL-085 | 최종 업데이트 프리셋은 서버에 다시 물은 날짜를 URL에 쓰고 실패하면 URL을 두고 오류를 보인다 | DL-R25, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx` |
| DL-086 | 직접 지정은 URL을 바꾸지 않고 날짜 칸을 열며 올바른 날짜일 때만 반영한다 | DL-R25, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx` |
| DL-087 | 역전된 직접 지정 기간은 서버 문구를 배너로 보인다 | DL-R25, DL-R10, DL-UC2 | frontend | `features/deals/list/DealsPage.filters.test.tsx` |
| DL-088 | URL 날짜는 프리셋·직접 지정·전체로 표시되고 뒤로 가기를 따른다 | DL-R25, DL-UC6 | frontend | `features/deals/list/DealsPage.filters.test.tsx` |
| DL-089 | 정렬 머리글은 10열이고 자연 방향으로 시작해 다시 누르면 뒤집히며 1페이지로 간다 | DL-R27, DL-UC3 | frontend | `features/deals/list/DealsPage.bant.test.tsx`, `features/deals/list/DealsPage.columns.test.tsx`, `features/deals/list/DealsPage.filters.test.tsx`, `features/deals/list/DealsPage.sort.test.tsx` |
| DL-090 | 정렬을 바꾸면 행이 서버 순서대로 보이고 파트너 없는 Deal은 끝에 있다 | DL-R27, DL-R13, DL-UC3 | frontend | `features/deals/list/DealsPage.sort.test.tsx` |
| DL-091 | 빠른 보기는 행 아래 13열 너비로 견적·POC·담당자·파트너·Users·구매절차를 보인다 | DL-R29, DL-UC4 | frontend | `features/deals/list/DealsPage.columns.test.tsx`, `features/deals/list/DealsPage.test.tsx`, `features/deals/list/QuickView.users.test.tsx` |
| DL-092 | 빠른 보기의 BANT는 Label 이름·로딩·실패·'—'를 보이고 목록은 Label을 미리 읽지 않는다 | DL-R29, DL-UC4 | frontend | `features/deals/list/DealsPage.columns.test.tsx`, `features/deals/list/QuickView.bant.test.tsx` |
| DL-093 | sales는 4칸만 편집할 수 있고 Status·Forecast는 고르는 즉시 저장되어 알림이 뜬다 | DL-R30, DL-UC5 | frontend | `features/deals/list/DealsPage.inline.test.tsx`, `features/deals/list/DealsPage.test.tsx` |
| DL-094 | 목록 금액 편집은 Enter·blur에 저장하고 Esc는 버리며 틀린 값·같은 값은 저장하지 않는다 | DL-R30, DL-UC5 | frontend | `features/deals/list/DealsPage.amountKeep.test.tsx`, `features/deals/list/DealsPage.inline.test.tsx` |
| DL-095 | 목록 Expected Close 편집은 완성된 날짜에 저장하고 덜 친·없는·빈 날짜는 저장하지 않는다 | DL-R30, DL-UC5 | frontend | `features/deals/list/DealsPage.inline.test.tsx` |
| DL-096 | 상세·빠른 보기·편집을 다녀와도 같은 조건·정렬·페이지의 목록으로 돌아온다 | DL-R31, DL-UC6 | frontend | `features/deals/list/DealsPage.forecastMulti.test.tsx`, `features/deals/list/DealsPage.memory.test.tsx` |
| DL-097 | 상단 메뉴 Deals는 기억된 목록이고 목록 안에서는 지금 URL을 바로 따른다 | DL-R31, DL-UC6 | frontend | `features/deals/list/DealsPage.memory.test.tsx` |
| DL-098 | 기억은 사용자별·새로고침 유지이고 아는 키만 남긴다 | DL-R31, DL-UC6 | frontend | `features/deals/list/DealsPage.memory.test.tsx` |
| DL-099 | 삭제 뒤·새 Deal 취소·오류 화면 링크는 기억된 목록으로 간다 | DL-R31, DL-UC6 | frontend | `features/deals/list/DealsPage.memory.test.tsx` |
| DL-100 | 게이트웨이는 목록 조건을 서버 쿼리로 바꾸고 연도·프리셋 응답을 화면 모양으로 바꾼다 | DL-R32 | frontend | `gateway/http/deals.test.ts` |
| DL-101 | sales의 조건 없는 진입은 연도 전체 + 내 딜만 기본 조건이고 mine 없는 요청은 나가지 않는다 | DL-R19, DL-UC1 | frontend | `features/deals/list/DealsPage.defaultMine.test.tsx`, `features/deals/list/listQuery.test.ts` |
| DL-102 | sales의 초기화는 연도 전체 + 내 딜만으로 돌아가고 그 조건이 기억된다 | DL-R21, DL-R19, DL-UC2 | frontend | `features/deals/list/DealsPage.defaultMine.test.tsx` |
| DL-103 | sales가 내 딜만을 끄면 mine이 지워지고 기본 조건으로 되돌아가지 않는다 | DL-R21, DL-R31, DL-UC2 | frontend | `features/deals/list/DealsPage.defaultMine.test.tsx` |
| DL-104 | 조건이 있는 주소(Drill-down·year=all·담당자)와 기억된 조건에는 내 딜만을 더하지 않는다 | DL-R19, DL-R31, DL-UC6 | frontend | `features/deals/list/DealsPage.defaultMine.test.tsx` |
| DL-105 | user의 기본 조건은 연도 전체이고 담당 Deal이 없는 sales는 빈 조건 문구를 본다 | DL-R19, DL-R18, DL-UC1 | frontend | `features/deals/list/DealsPage.defaultMine.test.tsx` |
| DL-106 | 최종 업데이트일이 같은 Deal은 정렬 방향과 무관하게 Deal code 오름차순이다 | DL-R13, DL-UC1 | backend | `application/test_deal_list_period_sort_cases.py`, `repositories/test_deal_sort_contract.py`, `web/test_deal_list_openapi.py` |
### DL-001 조건 없이 조회하면 offset 0·limit 20의 페이지가 최종 업데이트 최신순으로 온다
- Given KIM이 Deal "첫째"·"둘째"·"셋째"를 하루 간격으로(각각 다른 날) 등록했고 Action은 없다
- When 조건 없이 목록을 조회한다
- Then 200 `{items, total: 3, offset: 0, limit: 20}`이고 순서는 셋째·둘째·첫째, 각 행의 `last_updated_on`은 등록일과 같다

### DL-002 total은 페이지와 무관하고 끝을 넘은 페이지는 비며 Deal이 없으면 []·0이다
- Given Deal 5건(그리고 별도로 Deal이 하나도 없는 상태)
- When `offset=3&limit=1`, `offset=10`으로 조회한다(빈 상태에서는 조건 없이 조회한다)
- Then 첫 요청은 항목 1건·`total` 5, 둘째는 `items` `[]`·`total` 5, 빈 상태는 `items` `[]`·`total` 0이다

### DL-003 모든 역할이 목록을 보고 미인증은 401이다
- Given Deal 1건
- When ROOT·KIM·VIEWER가 각각, 그리고 로그인하지 않은 채 목록을 조회한다
- Then 세 역할은 200이고 미인증은 401 `unauthenticated`다

### DL-004 limit 1·200은 되고 0·201·offset −1은 422 request-validation이다
- Given 로그인한 KIM
- When `limit=1`, `limit=200`, `limit=0`, `limit=201`, `offset=-1`로 조회한다
- Then 앞의 둘은 200, 나머지는 422 `request-validation`이다

### DL-005 키워드는 Deal Name·code·고객 회사·활성 파트너 회사를 대소문자 무시로 찾는다
- Given Deal "ErP 구축", 고객 "한빛은행"의 Deal, 활성 파트너 "코어테크"의 Deal
- When 키워드 "erp", "한빛", "코어테크", 첫 Deal code의 소문자 일부로 각각 조회한다
- Then 각각 해당 Deal 하나만 나온다

### DL-006 키워드는 비활성 파트너·담당자 이름·Vendor·Solution을 찾지 않는다
- Given 파트너를 "에이원"에서 "대한"으로 바꾼 Deal, Vendor "SpecialVendor"·Solution "MFA"인 Deal, 담당자 이름 "박영업"
- When 키워드 "에이원", "SpecialVendor", "MFA", "박영업"으로 조회한다
- Then 모두 0건이다

### DL-007 키워드의 앞뒤 공백은 지우고 공백뿐이면 조건 없음이며 %·_는 글자 그대로다
- Given Deal "50% 할인"·"5000 할인"·"A_B 과제"·"AXB 과제"
- When 키워드 "  50%  ", "   ", "A_B"로 조회한다
- Then "  50%  "는 "50% 할인"만, "   "는 4건 모두, "A_B"는 "A_B 과제"만 나온다

### DL-008 키워드 100자는 되고 101자는 422 request-validation이다
- Given 로그인한 KIM
- When 키워드 "a"×100, "a"×101로 조회한다
- Then 100자는 200, 101자는 422 `request-validation`이다

### DL-009 키워드에 NUL이 있으면 500이 아니라 422 invalid-value다
- Given 로그인한 KIM
- When 키워드 "a\x00b"로 조회한다
- Then 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다"이고 `detail`에 DB 문구가 없다

### DL-010 owner_user_id는 담당자가 정확히 같은 Deal(퇴사자 포함)이고 형식이 틀리면 422다
- Given KIM의 Deal 1건, 퇴사한 PARK의 Deal 1건
- When `owner_user_id`=PARK의 id, `owner_user_id=not-an-id`로 조회한다
- Then PARK의 Deal만 나오고, 형식이 틀린 값은 422 `request-validation`이다

### DL-011 mine=true는 요청자 Deal만이고 owner_user_id보다 우선하며 불리언이 아니면 422다
- Given KIM의 Deal "앨리스 딜", PARK의 Deal "밥 딜", PARK로 로그인
- When `mine=true`, `mine=true&owner_user_id=<KIM id>`, 조건 없이, `mine=maybe`로 조회한다
- Then 앞의 둘은 "밥 딜"만, 조건 없이는 두 건, `mine=maybe`는 422 `request-validation`이다

### DL-012 vendor_id는 그 Vendor의 Deal이고 없는 id는 0건, 정수가 아니면 422다
- Given Vendor SAP·Oracle의 Deal 각 1건
- When `vendor_id`=SAP id, 없는 id, `vendor_id=SAP`로 조회한다
- Then SAP Deal만, 0건(200), 422 `request-validation`이다

### DL-013 solution은 트림한 텍스트의 대소문자 무시 부분 일치이고 와일드카드는 글자이며 Vendor와 AND다
- Given Solution "ITDR"·"ITDR Plus"·"MFA"·"50%_off"인 Deal(앞의 둘은 Vendor SAP, "ITDR Plus"만 Vendor Oracle로 바꾼 경우 포함)
- When `solution=" itdr "`, `solution="   "`, `solution="%_"`, `vendor_id=SAP&solution=itdr`로 조회한다
- Then 각각 ITDR 계열 둘, 전부, "50%_off"만, SAP이면서 ITDR인 Deal만 나온다

### DL-014 solution은 트림 후 200자까지 되고 201자는 422 request-validation, NUL은 invalid-value다
- Given 로그인한 KIM
- When `solution`을 "a"×200(앞뒤 공백 포함), "a"×201, "a\x00b"로 조회한다
- Then 200, 422 `request-validation`, 422 `invalid-value` "Solution에는 NUL 문자를 쓸 수 없습니다"다

### DL-015 status_key는 같은 Status의 Deal이고 없는 key는 0건, 51자는 422다
- Given Status `introduction`·`prospecting` Deal 각 1건
- When `status_key=introduction`, `status_key=no_such_status`, `status_key`="a"×51로 조회한다
- Then `introduction` Deal만, 200·0건, 422 `request-validation`이다

### DL-016 forecast_key를 하나 또는 여러 번 보내면 그중 하나인 Deal이고 중복은 한 번이다
- Given Forecast마다 Deal 1건
- When `forecast_key=a`, `forecast_key=a&forecast_key=b`, `forecast_key=a&forecast_key=a`로 조회한다
- Then 각각 a의 Deal, a·b의 Deal(total 2), a의 Deal(total 1)이다

### DL-017 모르는·빈 forecast_key는 오류 없이 일치가 없고 콤마는 key의 일부다
- Given Forecast a·b의 Deal
- When `forecast_key=a&forecast_key=nope`, `forecast_key=`(빈 값), `forecast_key=a,b`로 조회한다
- Then a의 Deal만, 0건, 0건(“a,b”라는 key 하나)이고 모두 200이다

### DL-018 forecast_key 50자·100개는 되고 51자·101개는 422다
- Given 로그인한 KIM
- When 50자 key, 서로 다른 key 100개, 51자 key가 섞인 요청, key 101개로 조회한다
- Then 앞의 둘은 200, 뒤의 둘은 422 `request-validation`이다

### DL-019 forecast_outcome은 코드 outcome으로 거르고 not_lost는 open·won이며 추가한 Open 코드도 들어간다
- Given outcome open·won·lost Forecast의 Deal과 admin이 추가한 open 코드의 Deal
- When `forecast_outcome`을 `open`, `won`, `lost`, `not_lost`로 각각 조회한다
- Then open은 기본 open·추가 코드 Deal, won은 won Deal, lost는 lost Deal, not_lost는 lost를 뺀 모든 Deal이고 total도 같다

### DL-020 forecast_outcome은 forecast_key와 AND이고 모르는 값은 422다
- Given 위와 같은 Deal
- When `forecast_outcome=open&forecast_key=<won key>`, `forecast_outcome=foo`로 조회한다
- Then 0건, 422 `request-validation`이다

### DL-021 year만 주면 그 해 1월 1일~12월 31일 Deal이다
- Given Expected Close 2025-12-31·2026-01-01·2026-12-31·2027-01-01인 Deal
- When `year=2026`으로 조회한다
- Then 2026-01-01·2026-12-31 Deal만 나온다

### DL-022 year+quarter는 그 분기 첫날·마지막 날을 포함하고 이웃 분기·다른 해는 뺀다
- Given Expected Close 2026-03-31·2026-04-01·2026-06-30·2026-07-01·2025-05-01인 Deal
- When `year=2026&quarter=2`로 조회한다
- Then 2026-04-01·2026-06-30 Deal만 나온다

### DL-023 여러 분기는 OR이고 떨어진 분기 사이는 빠지며 중복은 한 번이다
- Given 2026년 각 분기 첫날·마지막 날 Deal
- When `year=2026&quarter=1&quarter=3`, `year=2026&quarter=2&quarter=2`로 조회한다
- Then 첫 요청은 Q1·Q3 Deal만(Q2 제외), 둘째는 Q2 Deal만이다

### DL-024 네 분기를 모두 보내면 분기 조건이 없는 것과 같다
- Given 2026년 각 분기 Deal과 2025년 Deal
- When `year=2026&quarter=1&quarter=2&quarter=3&quarter=4`로 조회한다
- Then `year=2026`과 같은 결과다

### DL-025 연도 없는 분기는 서버 업무 날짜의 올해 분기다(새해 경계 포함)
- Given 업무 날짜 2026-10-15, 2026-05-01·2025-05-01 Deal (별도로 서버 시각 2026-12-31T15:00Z = 업무 날짜 2027-01-01)
- When `quarter=2`로 조회한다
- Then 2026-05-01 Deal만 나오고, 업무 날짜가 2027-01-01이면 2027년 Q2로 거른다

### DL-026 year+month는 그 달 1일~말일(윤년 2월 29일)이고 month만은 올해 그 달이다
- Given 2028-02-01·2028-02-29·2028-03-01, 2026-06-01·2025-06-15 Deal, 업무 날짜 2026-10-15
- When `year=2028&month=2`, `month=6`으로 조회한다
- Then 2028-02-01·2028-02-29 Deal, 2026-06-01 Deal이다

### DL-027 분기와 월을 함께 보내면 422 invalid-value이고 네 분기+월은 월만 고른 것이다
- Given 2026-06 Deal
- When `year=2026&quarter=2&month=6`, `year=2026&quarter=1&quarter=2&quarter=3&quarter=4&month=6`으로 조회한다
- Then 첫 요청은 422 `invalid-value` "Quarter와 월은 함께 선택할 수 없습니다.", 둘째는 200으로 6월 Deal이다

### DL-028 분기 1~4 밖·5개, 월 1~12 밖, 연도 1900~9999 밖은 422 request-validation이다
- Given 로그인한 KIM
- When `quarter=0`, `quarter=5`, quarter 값 5개, `month=0`, `month=13`, `year=1899`, `year=10000`으로 조회한다
- Then 모두 422 `request-validation`이다(연도 1900·9999, quarter 4개는 200)

### DL-029 최종 업데이트 기간은 양끝 날짜를 포함하고 한쪽만 줄 수 있다
- Given 업무 날짜 2026-10-15 정오에 등록한 Deal(Action 없음)
- When `updated_from=updated_to=2026-10-15`, `updated_from=2026-10-16`, `updated_to=2026-10-14`, `updated_from=2026-10-12`만, `updated_to=2026-10-18`만으로 조회한다
- Then 1건, 0건, 0건, 1건, 1건이다

### DL-030 최종 업데이트 기간은 최종 업데이트일을 날짜로 비교한다
- Given 최종 업데이트일이 2026-06-30, 2026-07-01, 2026-06-01, 2026-05-31인 Deal이 하나씩 있다
- When `updated_from=2026-06-01&updated_to=2026-06-30`으로 조회한다
- Then 첫째·셋째만 나온다

### DL-031 최근 Action은 오래된 Deal을 기간에 넣고 Deal 수정은 넣지 않는다
- Given 30일 전에 등록한 Deal A·B, 오늘 A에 Action을 남기고 B는 이름만 수정했다
- When 최근 14일 기간으로 조회한다
- Then A만 나온다

### DL-032 기간 역전·1900~2999 밖 날짜는 422 invalid-value, 양끝 날짜는 되고 형식이 틀리면 request-validation이다
- Given 로그인한 KIM
- When `updated_from=2026-07-01&updated_to=2026-06-30`, `updated_from=1899-12-31`, `updated_to=3000-01-01`, `updated_from=1900-01-01`, `updated_to=2999-12-31`, `updated_from=2026/06/01`, `updated_from=2026-06-01T10:00:00`으로 조회한다
- Then 첫째 "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다", 둘째 "updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다", 셋째 "updated_to은(는) …"(모두 `invalid-value`), 넷째·다섯째 200, 나머지 `request-validation`이다

### DL-033 next_action_status는 기준 행 상태로 거르고 total도 같다
- Given 기준 행이 done(뒤에 진행사항만 있는 Action) A, 기준 행 open B, 진행사항만 C, Action 없는 D
- When `next_action_status=done`, `open`으로 조회한다
- Then done은 A만, open은 B만이고 total도 1이다

### DL-034 closed는 종료(수행)·종료(미수행)이고 Next Action 없는 Deal은 빠지며 조건이 없으면 모두 나온다
- Given 위의 A·B·C·D와 기준 행 not_done인 E
- When `next_action_status=closed`, 조건 없이 조회한다
- Then closed는 A·E, 조건 없으면 A~E 모두다

### DL-035 허용하지 않는 next_action_status는 422다
- Given 로그인한 KIM
- When `next_action_status`를 `notDone`, `DONE`, `all`, 빈 값, `close`로 조회한다
- Then 모두 422 `request-validation`이다

### DL-036 overdue만·stale만 켜면 해당 Deal만 나오고 판정 기준은 행 risk와 같다
- Given RK 판정(RK-R3~R5)으로 기한초과만·미업데이트만·둘 다·정상·Lost(기한 지남) Deal, 저장된 미업데이트 기준 21일
- When `overdue=true`, `stale=true`로 조회한다
- Then overdue는 기한초과만·둘 다(Lost 제외), stale은 미업데이트만·둘 다이고 total이 같으며 각 행의 `risk`가 필터 판정과 일치한다(21일 기준)

### DL-037 overdue·stale을 함께 켜면 OR이고 다른 조건과는 AND다
- Given 위와 같은 Deal, 그중 이름에 "ERP"가 있는 것은 기한초과만 Deal
- When `overdue=true&stale=true`, `overdue=true&stale=true&keyword=erp`로 조회한다
- Then 첫째는 셋(기한초과만·미업데이트만·둘 다), 둘째는 ERP Deal만이고 total도 1이다

### DL-038 overdue·stale의 false·0은 조건 없음이고 불리언이 아니면 422다
- Given Deal 여러 건
- When `overdue=false&stale=0`, `overdue=abc`, `stale=2`로 조회한다
- Then 첫째는 모든 Deal, 나머지는 422 `request-validation`이다

### DL-039 여러 조건은 모두 AND이고 total은 필터 뒤 전체 건수다
- Given 이름 "ERP"·Vendor SAP·Status introduction·오늘 등록한 Deal 1건과 한 조건씩만 다른 Deal 4건(30일 전 등록, Oracle, prospecting, 이름 CRM)
- When `keyword=erp&owner_user_id=<KIM>&vendor_id=<SAP>&status_key=introduction&updated_from=<14일 전>&updated_to=<오늘>&limit=1`로 조회한다
- Then 맞는 1건만 나오고 total 1이다

### DL-040 정렬 10개 기준마다 오름·내림차순 결과가 기대한 순서다
- Given 이름·금액·Expected Close·Status·담당자·고객·파트너·Vendor·Forecast·최종 업데이트가 정렬마다 다른 순서가 되는 Deal 3건
- When `sort`를 10개 값 각각, `order`를 `asc`·`desc`로 조회한다
- Then 오름차순은 기대한 순서, 내림차순은 그 역순이다

### DL-041 정렬 값이 같으면 방향과 무관하게 code 오름차순이고 대소문자만 다른 이름은 같은 값이다
- Given 모든 값이 같은 Deal 4건, 이름 "alpha"·"ALPHA"인 Deal 2건
- When `sort`를 name·revenue_amount·revenue_date·status로 `asc`·`desc` 각각 조회한다
- Then 동률인 Deal은 언제나 code 오름차순이다

### DL-042 파트너·Vendor 정렬에서 값이 없는 Deal은 방향과 무관하게 맨 뒤다
- Given 파트너·Vendor가 bravo·없음·alpha·없음인 Deal 1~4
- When `sort=partner`·`vendor`를 `asc`·`desc`로 조회한다
- Then 값이 있는 Deal(asc: alpha, bravo / desc: bravo, alpha) 뒤에 값 없는 Deal 2·4가 code 순으로 온다

### DL-043 Status·Forecast 정렬은 코드의 현재 순서를 따른다
- Given Status가 서로 다른 Deal 3건
- When `sort=status&order=asc`로 조회하고, admin이 Status 순서를 바꾼 뒤 다시 조회한다(Forecast도 같게)
- Then 결과가 각 시점의 코드 순서를 따른다

### DL-044 담당자 정렬은 표시 이름(없으면 아이디) 대소문자 무시이고 퇴사자도 이름으로 정렬된다
- Given 표시 이름 "bob"·"Alice"인 담당자, 표시 이름이 빈 아이디 "carol", 퇴사한 "Dave"의 Deal
- When `sort=owner&order=asc`로 조회한다
- Then Alice·bob·carol·Dave 순이다

### DL-045 정렬한 목록의 다음 페이지는 앞 페이지에 이어지고 total은 같다
- Given Deal 3건
- When `sort=name&order=asc`로 `offset=0&limit=2`, `offset=2&limit=2`를 조회한다(담당자 정렬도 같게)
- Then 두 페이지를 이으면 전체 정렬 순서와 같고 두 total은 3이다

### DL-046 화이트리스트 밖 sort·order는 422다
- Given 로그인한 KIM
- When `sort=revenueAmount`, `sort=stage`, `sort=name; drop table deals`, `order=up`, `order=DESC`로 조회한다
- Then 모두 422 `request-validation`이다

### DL-047 모르는 파라미터와 폐지된 파라미터는 조용히 무시하지 않고 422다
- Given 로그인한 KIM
- When `stage=lost`, `customer_id=x`, `owner=박영업`, `vendor=SAP`, `solution_id=1`, `revenue_from=2026-06-01`, `revenue_to=2026-06-30`, `bant_budget=1`, `sortBy=name`, `unknown=x`로 각각 조회한다
- Then 모두 422 `request-validation`이다

### DL-048 행은 문서화된 필드를 갖고 담당자 역할·고객·활성 파트너·Vendor 참조가 담긴다
- Given KIM이 고객 "네오인", 파트너를 한 번 교체, Vendor SAP로 등록한 Deal
- When 목록을 조회한다
- Then 행의 키는 DL-R14 목록과 정확히 같고 `partner_history`가 없으며, `owner.role` "sales", `customer.company` "네오인", `active_partner`는 새 파트너, `vendor`는 `{id, name: "SAP"}`이다

### DL-049 연도 기준은 가장 이른 Expected Close 연도이고 Deal이 없으면 null이다
- Given Deal이 없는 상태와 Expected Close 2024-05-01·2019-12-31·2027-01-01 Deal이 있는 상태
- When 각 상태에서 `GET /deals/years`를 부른다
- Then `{"earliest_year": null}`, `{"earliest_year": 2019}`이다

### DL-050 연도 기준은 Deal 삭제·Expected Close 수정을 바로 반영한다
- Given 2019·2024년 Deal
- When 2019년 Deal을 삭제한 뒤 조회하고, 남은 Deal의 Expected Close를 2021-02-03으로 고친 뒤 조회하고, 마지막 Deal을 삭제한 뒤 조회한다
- Then 2024, 2021, null이다

### DL-051 모든 역할이 연도 기준을 읽고 경로는 Deal code가 아니며 미인증은 401이다
- Given 2023·2026년 Deal
- When ROOT·KIM·VIEWER와 미인증이 `GET /deals/years`를 부른다
- Then 세 역할은 200 `{"earliest_year": 2023}`(키는 그 하나, Deal 404 아님), 미인증은 401이다

### DL-052 기간 프리셋은 서버 업무 날짜의 today·과거 5개·향후 2개이고 시계를 따른다
- Given 서버 업무 날짜 2026-10-15
- When `GET /deals/updated-periods`를 부르고, 자정을 지난 뒤 다시 부른다
- Then `today` 2026-10-15, `periods`는 `2w`(2026-10-01~10-15)·`1m`(09-15~)·`2m`(08-15~)·`3m`(07-15~)·`6m`(04-15~) 순, `upcoming`은 `1m`(10-15~11-15)·`2m`(10-15~12-15)이고, 자정 뒤에는 `today`가 2026-10-16으로 바뀐다

### DL-053 그 날이 없는 달의 프리셋 경계는 말일이다
- Given 서버 업무 날짜 2026-03-31(별도로 2026-01-31)
- When 기간 프리셋을 부른다
- Then 3/31이면 `2w` 시작 2026-03-17, `1m` 시작 2026-02-28, `6m` 시작 2025-09-30이고, 1/31이면 upcoming `1m` 끝 2026-02-28, `2m` 끝 2026-03-31이다

### DL-054 모든 역할이 기간 프리셋을 읽고 경로는 Deal code가 아니며 미인증은 401이다
- Given 로그인한 ROOT·KIM·VIEWER와 미인증 요청자
- When `GET /deals/updated-periods`를 부른다
- Then 세 역할은 200이고 항목 키는 `key`·`from`·`to`이며 Deal 404가 아니고, 미인증은 401이다

### DL-055 admin의 조건 없는 주소는 연도 전체 기본 조건으로 바뀌고 최종 업데이트 최신순으로 조회한다
- Given ROOT(admin) 로그인, 앱 시계 2026-10-15, Expected Close 연도가 서로 다른(2026·2027년) Deal(최종 업데이트일이 서로 다름)
- When `/deals`를 연다
- Then 주소가 `/deals?year=all`이 되고 연도 선택은 "전체"이며, 목록 요청은 처음부터 모두 연도·분기 없고 정렬은 지정하지 않거나 `lastUpdatedAt`·`desc`(지정하지 않으면 서버 기본 DL-R13)이며, 모든 연도 Deal이 최종 업데이트 최신순으로 보이며 "최종 업데이트" 머리글이 내림차순 표시다

### DL-056 기본 조건은 정렬을 이어받고 page·모르는 키를 버리며 이력에 남기지 않는다
- Given 앱 시계 2026-10-15
- When `/deals?sort=owner&order=desc&page=3&foo=1`(필터 키 없음)과 `/deals?q=&status=%20`을 연다
- Then 앞은 `/deals?year=all&sort=owner&order=desc`, 뒤는 `/deals?year=all`이 되고, 뒤로 가기를 해도 조건 없는 주소로 돌아가지 않는다

### DL-057 루트·로그인 직후·기억 없는 메뉴·기억 없는 상세 목록 링크 모두 기본 조건이다
- Given 조건 기억이 없거나 예전 `outcome`만 기억된 사용자
- When `/`로 들어오고, 로그인하고, 상단 메뉴 Deals를 누르고, 상세의 목록 링크를 누른다
- Then 모두 `/deals?year=all` 목록이 된다

### DL-058 표는 13열을 순서대로 보이고 칸 값 규칙을 따른다
- Given 파트너·Vendor 없는 Deal, 퇴사 담당자의 Deal, 금액 120,000,000원 Deal
- When 목록을 연다
- Then 머리글이 Deal·담당자·고객사·파트너사·Vendor·Status·Forecast·금액(단위:원)·Expected Close·Next Action·Due·Next Action 상태·최종 업데이트 순이고, 파트너사·Vendor 칸은 "—", 담당자는 "이름(퇴사)", 금액은 "120,000,000", 최종 업데이트는 앱 시계의 오늘 기준 상대 일수(title은 YYYY-MM-DD)이며 BANT 열이 없다

### DL-059 Next Action 세 칸은 Actions 탭 링크·Due·상태 라벨이고 없으면 모두 '—'다
- Given 기준 행이 "견적 재제출"(Due 2026-10-20, Open)인 Deal과 Action 없는 Deal
- When 목록에서 Next Action 링크를 누르고(키보드 Enter 포함) Deal 이름 링크도 누른다
- Then 링크 안에는 내용만, Due·"Open"은 별도 칸이고 링크는 `/deals/<code>?tab=actions`로 Actions 탭을 연다; 이름 링크는 `/deals/<code>`; Action 없는 Deal은 세 칸이 "—"이고 링크가 없다

### DL-060 목록에는 Deal code 글자가 없지만 code로 검색할 수 있다
- Given Deal 여러 건
- When 목록을 열고, 한 Deal code로 키워드 검색한다
- Then 화면 글자·접근성 이름·title 어디에도 code가 없고 행 링크 주소에만 있으며, 검색 결과는 그 Deal이다

### DL-061 한 페이지 20건과 페이저, "총 N건"을 보인다
- Given 올해 Deal 24건
- When 목록을 열고 페이저로 2페이지로 간다
- Then 1페이지 20행·"총 24건", 2페이지 4행이고 URL에 `page=2`가 있다

### DL-062 빈 목록은 조건 유무에 따라 다른 문구이고 끝을 넘은 페이지는 첫 페이지로 버튼을 준다
- Given Deal이 없는 Fake와 Deal이 있는 Fake
- When `/deals?year=all`(Deal 없음), 맞는 Deal이 없는 키워드, `/deals?year=2026&page=9`를 연다
- Then "등록된 Deal이 없습니다.", "조건에 맞는 Deal이 없습니다.", "9페이지에는 Deal이 없습니다."와 "첫 페이지로"(누르면 1페이지)다

### DL-063 다음 조건을 읽는 동안 이전 표를 유지하고 목록 오류는 배너로 보인다
- Given 목록이 보이는 상태에서 다음 조회 응답을 늦춘 Fake(또는 실패하는 Fake)
- When 조건을 바꾼다
- Then 응답이 올 때까지 이전 표가 그대로 있고, 실패하면 서버 문구의 오류 배너가 보인다

### DL-064 user에게는 Deal 등록 링크와 편집 버튼이 없다
- Given VIEWER로 로그인
- When 목록을 연다
- Then "+ Deal 등록"과 "… 편집" 버튼이 없고 Status·금액 등은 값으로만 보인다(sales는 둘 다 보인다)

### DL-065 키워드·Solution은 검색 버튼·Enter로만 URL에 반영되고 비우면 지워진다
- Given 목록 화면
- When 키워드 "한빛"을 입력만 하고, "검색"을 누르고, Solution " ITDR "를 입력해 Enter, 다시 Solution을 비우고 검색한다
- Then 입력만으로는 URL이 그대로이고, 검색 뒤 `q=한빛`, Enter 뒤 `solution=ITDR`(키워드와 함께 한 번에 반영), 비우고 검색하면 `solution`이 없다

### DL-066 담당자(퇴사자 포함)·Vendor·Status·내 딜만은 바꾸는 즉시 반영된다
- Given 퇴사한 담당자가 있는 Fake
- When 담당자 선택지를 열고 담당자·Vendor·Status를 고르고 "내 딜만"을 켰다 끈다
- Then 담당자 선택지에 퇴사자가 있고, 고를 때마다 URL(`owner`·`vendor`·`status`·`mine=1`)과 목록이 즉시 바뀌며 끄면 `mine`이 지워진다

### DL-067 목록에 없는 Vendor id는 전체로 보이고 보내지 않으며 Vendor를 못 읽는 동안은 URL id를 쓴다
- Given URL `vendor=999`(없는 id)와 `solution=ITDR`, 별도로 Vendor 조회가 실패하는 Fake
- When 목록을 연다
- Then 정상 Fake에서는 Vendor가 "전체", 요청에 `vendorId` 없음, Solution은 유지된다; 실패 Fake에서는 Vendor 칸 근처 오류 배너, 선택 "선택한 Vendor", 요청에 그 id가 있다; Vendor 선택지 값은 id·표시는 이름이다

### DL-068 조건을 바꾸면 1페이지로 돌아간다
- Given `/deals?year=2026&page=2`
- When Forecast·Quarter·Next Action 상태·기한초과 중 하나를 바꾼다
- Then URL에서 `page`가 지워진다

### DL-069 마지막 조건을 지우면 기본 연도가 아니라 연도 전체로 남는다
- Given `/deals?forecast=won`(유일한 조건)
- When Forecast "전체"를 누르거나 체크를 끈다
- Then URL이 `/deals?year=all`이 되고 연도 선택은 "전체", 요청에 연도가 없다

### DL-070 초기화는 연도 전체 기본 조건으로 새 이력을 만들고 모든 칸을 비운다
- Given 여러 조건·정렬·직접 지정 기간이 있는 목록
- When "초기화"를 누른다
- Then URL이 `/deals?year=all`(정렬 없음 = 최종 업데이트 최신순)이고 연도는 "전체", 나머지 칸·체크가 비며, 뒤로 가기로 이전 조건에 돌아갈 수 있고, 그 조건이 기억된다

### DL-071 URL 조건으로 모든 칸을 복원한다
- Given 모든 필터 키가 있는 주소
- When 목록을 연다
- Then 키워드·Solution 입력란, 담당자·Vendor·Status·Forecast·Next Action 상태·연도·Quarter·월·최종 업데이트 선택, 세 체크박스가 URL 값으로 보인다

### DL-072 URL의 잘못된 값·예전 키는 조회에 쓰지 않고 활성 필터로도 세지 않는다
- Given `owner=<UUID>`, `vendor=SAP`, `updated_from=2026-02-30`, `overdue=yes`, `next_status=bad`, 201자 `solution`, 예전 `budget=1`·`outcome=open`·`from`·`to`
- When 목록을 연다
- Then 그 값들은 요청에 없고 체크·선택은 '전체'/꺼짐이며, 다른 조건이 없으면 빈 문구는 "등록된 Deal이 없습니다." 기준으로 판정된다(예전 키는 활성 필터가 아님)

### DL-073 Forecast 다중 선택은 정렬된 key를 콤마로 URL에 쓰고 전체로 지운다
- Given Forecast 코드 여러 개
- When "Forecast"를 열고 두 코드를 서로 다른 순서로 체크하고, 하나를 끄고, "전체"를 누르고, Escape로 닫는다
- Then 선택지는 코드 순서, URL은 순서와 무관하게 `forecast=a,b`(하나면 `forecast=a`), 해당 Deal만 보이며, "전체"는 키를 지우고 Escape는 패널을 닫고 포커스를 버튼으로 돌린다

### DL-074 Forecast 버튼 요약은 선택에 따라 전체·이름·모두 선택·Lost 제외·Open 전체·N개 선택이다
- Given Forecast 코드(open 여럿, won, lost)
- When 선택 없음, 하나, 전부, lost 뺀 전부, open 전부, 그 밖의 두 개를 고른다
- Then 요약이 "전체", 코드 이름, "모두 선택", "Lost 제외", "Open 전체", "2개 선택"이다

### DL-075 URL forecast는 예전 단일 값을 읽고 틀린 항목은 버리며 100개를 넘으면 조건 전체를 무시한다
- Given `forecast=won`, `forecast=won,BAD,a-b`, 코드에 없는 형식 맞는 key, 서로 다른 key 101개
- When 목록을 연다
- Then 첫째는 won 하나 체크, 둘째는 won만 사용, 셋째는 그 key를 보내고 요약에만 보이며, 넷째는 Forecast 조건을 보내지 않는다

### DL-076 Quarter 다중 선택은 오름차순 목록을 URL에 쓰고 넷 다 눌러도 유지하되 분기 조건은 보내지 않는다
- Given 목록 화면
- When Q3, Q1을 차례로 체크하고, Q3을 끄고, 네 개를 모두 체크하고, "전체"를 누른다
- Then URL `quarter=1,3` → `quarter=1` → `quarter=1,2,3,4`(넷 다 눌림·요약 "전체"·요청에 분기 없음·그 해 전체 목록) → `quarter` 없음이고, 예전 `quarter=3` 주소는 Q3 하나, 형식이 틀린 항목은 버린다

### DL-077 연도가 전체일 때 분기나 월을 고르면 올해 기준 안내를 보인다
- Given 앱 시계 2026년, 연도 "전체"
- When Q4를 체크하고(별도로 분기 없이 월 6을 고르고), 그다음 연도 2026을 고른다
- Then Quarter(또는 월) 아래 "연도가 전체이면 올해(2026) 기준입니다."가 접근성 설명으로 연결되어 보이고 2026년 Q4 Deal이 나오며, 연도를 고르면 안내가 사라지고 분기는 유지된다

### DL-078 월 선택지는 고른 분기들의 월이고 그 안의 월이면 월만, 아니면 분기만 보낸다
- Given `quarter=1,3`
- When 월 선택지를 보고 2월을 고르고, 별도로 `quarter=2&month=8` 주소를 연다
- Then 선택지는 전체·1·2·3·7·8·9월, 2월을 고르면 요청은 월 2만(분기 없음)·분기 체크는 유지, `quarter=2&month=8`은 월 "전체"로 보이고 분기 2만 보낸다

### DL-079 분기를 바꾸면 새 선택지에 있는 월은 유지하고 없는 월·숨은 월은 지운다
- Given `quarter=1&month=2`, 별도로 `quarter=2&month=8`(숨은 월)
- When Q3을 더 체크하고, Q1을 끄고, "전체"를 누른다(숨은 월 주소에서도 "전체"와 Q3 체크를 한다)
- Then Q3 추가 뒤 월 2 유지, Q1을 끄면 월 삭제, 보이던 월은 "전체" 뒤에도 유지, 숨은 월은 분기를 바꾸거나 "전체"를 누르면 지워진다

### DL-080 연도 선택지는 전체 + 가장 이른 연도~내년이고 URL 연도를 한 번 더한다
- Given 앱 시계 2026년, 가장 이른 Expected Close 2023년(그리고 2029년 Deal), URL `year=2030`, 별도로 Deal 없음
- When 연도 선택지를 본다
- Then 전체·2023·2024·2025·2026·2027·2030(선택됨)이고 2028·2029는 없으며, URL 연도가 이미 있으면 한 번만, Deal이 없으면 전체·2026·2027이다

### DL-081 연도 기준을 읽는 동안·실패하면 올해·내년만 보이고 실패는 배너지만 목록은 나온다
- Given 연도 기준 응답이 늦는 Fake와 실패하는 Fake
- When 목록을 연다
- Then 늦는 동안 전체·2026·2027이고 응답 뒤 선택은 그대로 선택지만 넓어지며, 실패하면 오류 배너가 보이고 목록 행은 나온다

### DL-082 연도 전체는 서버에 연도를 보내지 않고 상세 왕복·메뉴에서 복원된다
- Given `/deals?year=all`
- When 목록을 보고 상세에 갔다 목록 링크로, 다른 메뉴에 갔다 상단 메뉴 Deals로 돌아온다
- Then 요청에 연도가 없고, 돌아와도 연도 "전체"(`year=all`)다

### DL-083 Next Action 상태 선택은 5개이고 URL next_status로 반영·복원된다
- Given `/deals?year=2026&page=2`
- When "Next Action 상태" 선택지를 보고 "종료(미수행)"을 고르고, 다시 연 주소의 값을 보고, 초기화한다
- Then 선택지는 전체·Open·종료(수행)·종료(미수행)·종료(전체), URL `next_status=not_done`·`page` 삭제·해당 Deal만, 복원 시 "종료(미수행)", 초기화하면 "전체"다

### DL-084 기한초과·미업데이트 체크는 overdue=1·stale=1로 반영되고 둘 다 켜면 어느 하나라도 해당한다
- Given RK 판정(RK-R3~R6)이 서로 다른 Deal들
- When "기한초과"만, "미업데이트"만, 둘 다 켜고, 다시 끄고, `overdue=1&stale=1` 주소를 열고, 초기화한다
- Then 기본은 꺼짐, 각각 해당 Deal만, 둘 다면 어느 하나라도 해당하는 Deal, 끄면 키 삭제·전체 목록, 주소로 체크 복원, 초기화하면 꺼진다; 다른 조건(키워드)과는 AND다

### DL-085 최종 업데이트 프리셋은 서버에 다시 물은 날짜를 URL에 쓰고 실패하면 URL을 두고 오류를 보인다
- Given 앱 시계 2026-10-15, `/deals?year=all&page=2`
- When "최종 업데이트"에서 "최근 2주"를 고르고(그 사이 서버 날짜가 바뀐 Fake 포함), 프리셋 다시 묻기가 실패하는 Fake에서 "최근 3개월"을 고른다
- Then 선택지는 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정이고, URL은 서버가 새로 준 `updated_from=2026-10-01&updated_to=2026-10-15`(페이지 삭제)이며, 실패하면 URL은 그대로·오류 배너다

### DL-086 직접 지정은 URL을 바꾸지 않고 날짜 칸을 열며 올바른 날짜일 때만 반영한다
- Given 프리셋 "최근 2주"가 적용된 목록(그리고 "전체" 상태)
- When "직접 지정"을 고르고, 시작일에 `20261001`을 치고, 덜 친 `202610`과 없는 날짜 `2026-02-30`을 넣고, 시작일만 남긴 채 지운다
- Then 직접 지정은 URL을 바꾸지 않고 시작일·종료일을 프리셋 날짜로 채워 보이며("전체"에서는 빈 칸), `20261001`은 `updated_from=2026-10-01`, 덜 친·없는 날짜는 URL 변화 없이 칸을 떠난 뒤 문구, 시작만으로 조회되고 지우면 키가 삭제된다

### DL-087 역전된 직접 지정 기간은 서버 문구를 배너로 보인다
- Given 직접 지정 상태
- When 시작일 2026-10-10, 종료일 2026-10-01을 넣는다
- Then 목록 오류 배너에 "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"가 보인다

### DL-088 URL 날짜는 프리셋·직접 지정·전체로 표시되고 뒤로 가기를 따른다
- Given 오늘의 2주 프리셋과 같은 날짜, 프리셋과 다른 날짜, 한쪽만 있는 날짜, 날짜 없음 주소, 프리셋 조회가 실패하는 Fake
- When 각 주소를 열고, 직접 지정 상태에서 뒤로 가기로 날짜가 없어지거나 프리셋 날짜로 돌아가게 한다
- Then "최근 2주", "직접 지정"(날짜 칸 표시), "직접 지정", "전체"로 보이고, 프리셋 실패 때도 URL 날짜로 조회하며, 뒤로 가기 뒤에는 각각 "전체"(날짜 칸 숨김)·"최근 2주"다

### DL-089 정렬 머리글은 10열이고 자연 방향으로 시작해 다시 누르면 뒤집히며 1페이지로 간다
- Given `/deals?year=2026&page=2`
- When 머리글을 보고 "Expected Close"를 두 번, "금액(단위:원)"을 한 번 누르고, `sort=owner&order=desc` 주소를 연다
- Then Next Action·Due·Next Action 상태를 뺀 10개가 정렬 버튼이고 기본은 "최종 업데이트" 내림차순 표시, Expected Close는 asc → desc, 금액은 desc로 시작, 정렬 중인 열에만 `aria-sort`가 있고 `page`가 지워지며, 주소의 담당자 내림차순이 머리글에 복원된다

### DL-090 정렬을 바꾸면 행이 서버 순서대로 보이고 파트너 없는 Deal은 끝에 있다
- Given 파트너가 있는 Deal과 없는 Deal
- When "파트너사"를 오름차순·내림차순으로 정렬한다
- Then 행 순서가 게이트웨이가 준 순서와 같고 파트너 없는 Deal은 두 방향 모두 마지막이다

### DL-091 빠른 보기는 행 아래 13열 너비로 견적·POC·담당자·파트너·Users·구매절차를 보인다
- Given 견적·POC·파트너가 있는 Deal, 파트너가 없고 Users 0인 Deal
- When 각 행의 "<이름> 빠른 보기"를 누른다
- Then 13열을 차지하는 행에 견적·POC("값 (날짜)"), 고객 담당자·파트너 영업대표(" · " 연결), Users count, 구매절차, "상세 보기" 링크가 보이고, 파트너 없는 Deal은 "파트너 없음", Users는 "0"이며 다시 누르면 접힌다

### DL-092 빠른 보기의 BANT는 Label 이름·로딩·실패·'—'를 보이고 목록은 Label을 미리 읽지 않는다
- Given Budget Label을 고른 Deal, Label 목록 응답이 늦거나 실패하는 Fake
- When 목록만 보고, 빠른 보기를 연다
- Then 목록만 볼 때는 Label 조회가 없고 실패 안내도 없으며, 빠른 보기에서 Budget은 Label 이름(늦으면 "불러오는 중…", 실패면 "불러오지 못함"), 고르지 않은 구분은 로딩 중에도 "—"다

### DL-093 sales는 4칸만 편집할 수 있고 Status·Forecast는 고르는 즉시 저장되어 알림이 뜬다
- Given KIM으로 로그인한 목록
- When 편집 버튼을 세고, "<이름> Forecast 편집"을 눌러 다른 값을 고르고, Status도 바꾸고, 다른 Status 칸은 바꾸지 않고 포커스를 옮긴다
- Then 편집 버튼은 Status·Forecast·금액·Expected Close 4개뿐(이름·담당자·Vendor 없음), 편집 중 저장·취소 버튼이 없고, 고르는 즉시 저장되어 "<이름>: Forecast가 '<이름>'(으)로 변경되었습니다." 알림과 ✓가 보이며, 바꾸지 않은 칸은 요청 없이 원래 값으로 닫힌다

### DL-094 목록 금액 편집은 Enter·blur에 저장하고 Esc는 버리며 틀린 값·같은 값은 저장하지 않는다
- Given 금액 120,000,000원 Deal
- When 금액 편집을 열어 원래 값 확인, 값을 바꿔 Enter, 다시 바꿔 다른 곳 클릭, 바꾼 뒤 Esc, "abc" 입력 후 Enter, 바꾸지 않고 Enter, 999원 차이 값으로 Enter를 한다
- Then 시작 값은 "120,000,000", Enter·blur는 저장(글자마다 저장 안 함)·알림 "…금액(단위:원)이 '…'(으)로 변경되었습니다.", Esc는 원래 값, 틀린 값은 금액 문구를 보이며 편집 유지·저장 없음, 같은 값은 요청과 History 없음, 999원 차이는 그 값 그대로 저장된다

### DL-095 목록 Expected Close 편집은 완성된 날짜에 저장하고 덜 친·없는·빈 날짜는 저장하지 않는다
- Given Expected Close 2026-10-31 Deal
- When 달력으로 날짜를 고르고, `20261130`을 다 치고, `202611`까지만 치고, 없는 날짜에서 Enter, 비우고, 텍스트 칸에서 달력 버튼으로 Tab한 뒤 밖으로 Tab한다
- Then 앞의 둘은 즉시 저장, 덜 친 동안은 저장·문구 없음, 없는 날짜는 문구와 편집 유지, 비우면 "Expected Close를 입력하세요."와 편집 유지, 달력 버튼으로의 Tab은 닫히지 않고 밖으로 나가면 원래 값으로 닫힌다

### DL-096 상세·빠른 보기·편집을 다녀와도 같은 조건·정렬·페이지의 목록으로 돌아온다
- Given `/deals?status=a&sort=owner&order=desc&page=2&overdue=1&quarter=3&updated_from=…&updated_to=…`
- When 행 이름으로 상세에 가서 목록 링크를 누르고, 빠른 보기의 "상세 보기"로 갔다 돌아오고, 상세 → 수정 → 저장 → 상세 → 목록 링크로 돌아오고, 브라우저 뒤로 가기를 한다
- Then 매번 같은 주소(조건·정렬·페이지)의 목록이다

### DL-097 상단 메뉴 Deals는 기억된 목록이고 목록 안에서는 지금 URL을 바로 따른다
- Given 목록에서 조건을 고른 뒤 다른 메뉴로 간 사용자
- When 상단 메뉴 Deals를 누르고, 목록 안에서 필터·정렬·페이지를 바꾸며 메뉴 링크 주소를 보고, 초기화한다
- Then 메뉴는 기억된 목록을 열고, 목록 안에서는 메뉴 주소가 바꿀 때마다 즉시 지금 URL이 되며, 초기화 직후에는 기본 조건 주소다

### DL-098 기억은 사용자별·새로고침 유지이고 아는 키만 남긴다
- Given KIM이 `?status=a&foo=1&owner=<UUID>&budget=1&outcome=open&from=2026-01-01`로 목록을 본 상태
- When 새로고침 뒤 메뉴로 돌아오고, 로그아웃 후 PARK으로 로그인해 메뉴를 누른다
- Then KIM은 `/deals?status=a`(모르는 키·UUID owner·예전 키 제거)로 돌아오고 PARK은 기본 조건 목록이다

### DL-099 삭제 뒤·새 Deal 취소·오류 화면 링크는 기억된 목록으로 간다
- Given 조건이 기억된 KIM
- When 상세에서 Deal을 삭제하고, 새 Deal 폼에서 취소하고, 없는 Deal의 상세·수정 오류 화면에서 목록 링크를 누른다(수정 폼의 취소도 누른다)
- Then 삭제 뒤에는 기억된 목록에 삭제 알림이 한 번만 보이고, 새 폼 취소·오류 화면 링크는 기억된 목록이며, 수정 폼 취소는 상세로 돌아간다

### DL-100 게이트웨이는 목록 조건을 서버 쿼리로 바꾸고 연도·프리셋 응답을 화면 모양으로 바꾼다
- Given HTTP 게이트웨이와 가짜 서버 응답
- When 조건 없이, 모든 조건을 넣어(Forecast key 2개·분기 2개·`notDone`·정렬 `statusKey`), `mine`·`overdue`·`stale` false로 목록을 조회하고, 연도 기준(null 포함)과 모르는 키가 섞인 프리셋을 읽는다
- Then 조건 없으면 쿼리 없는 `GET /deals`, 모든 조건은 snake_case·`forecast_key`·`quarter` 반복·`not_done`·`sort=status`·정수 id로 가고 false인 불리언·`bant_*`·폐지 파라미터는 없으며, 응답은 `{items, total, offset, limit}`, 연도는 `earliestYear`(null 유지), 프리셋은 `today`와 아는 키만 남는다

### DL-101 sales의 조건 없는 진입은 연도 전체 + 내 딜만 기본 조건이고 mine 없는 요청은 나가지 않는다
- Given KIM(sales) 로그인, 조건 기억 없음, 앱 시계 2026-10-15, KIM·PARK의 2026년 Deal과 KIM의 2025년 Deal
- When `/deals`를 연다(루트·로그인 직후·기억 없는 상단 메뉴·기억 없는 상세 목록 링크도 같다)
- Then 주소가 `/deals?year=all&mine=1`이 되고(이력 교체, 뒤로 가기로 조건 없는 주소에 돌아가지 않음) 연도는 "전체", "내 딜만"이 체크되며, 목록 요청은 처음부터 모두 연도 없이 `mine: true`이고 KIM의 2025·2026년 Deal만 보인다

### DL-102 sales의 초기화는 연도 전체 + 내 딜만으로 돌아가고 그 조건이 기억된다
- Given KIM이 `/deals?status=a&owner=<PARK id>&sort=owner&order=asc`를 보고 있다
- When "초기화"를 누른다
- Then URL이 `/deals?year=all&mine=1`(새 이력, 정렬 없음)이고 연도는 "전체", "내 딜만"만 체크되며 나머지 칸이 비고, 상단 메뉴 Deals 주소도 같다

### DL-103 sales가 내 딜만을 끄면 mine이 지워지고 기본 조건으로 되돌아가지 않는다
- Given KIM이 기본 조건 `/deals?year=all&mine=1`을 보고 있다
- When "내 딜만" 체크를 끈다
- Then URL이 `/deals?year=all`(`mine` 키 없음)이 되고 KIM·PARK의 모든 연도 Deal이 보이며, 상세에 갔다 목록 링크·상단 메뉴로 돌아와도 `/deals?year=all`이다

### DL-104 조건이 있는 주소(Drill-down·year=all·담당자)와 기억된 조건에는 내 딜만을 더하지 않는다
- Given KIM(sales) 로그인, 기억된 조건 `?status=a`
- When Dashboard Drill-down 주소 `/deals?year=2026&quarter=3&forecast=best%2Ccommit`, `/deals?year=all`, `/deals?owner=<PARK id>`를 각각 열고, 상단 메뉴 Deals를 누른다
- Then 세 주소는 그대로이고 목록 요청에 `mine`이 없으며, 메뉴는 `/deals?status=a`다

### DL-105 user의 기본 조건은 연도 전체이고 담당 Deal이 없는 sales는 빈 조건 문구를 본다
- Given VIEWER(user)와, 담당 Deal이 없는 sales LEE(둘 다 조건 기억 없음), 2026년 Deal이 있다
- When 각자 `/deals`를 연다
- Then VIEWER는 `/deals?year=all`이고 "내 딜만"이 꺼진 채 모든 연도의 Deal이 보인다. LEE는 `/deals?year=all&mine=1`이고 "조건에 맞는 Deal이 없습니다."다

### DL-106 최종 업데이트일이 같은 Deal은 정렬 방향과 무관하게 Deal code 오름차순이다
- Given 최종 업데이트일이 모두 2026-11-13인 Deal 세 건(code 순서 D-1 < D-2 < D-3)을 D-2, D-1, D-3 순서로 등록했다
- When `sort=last_updated_at`으로 `order=desc`와 `order=asc`를 각각 조회한다
- Then 두 결과 모두 D-1, D-2, D-3 순서다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 최초 작성(구현된 동작을 정본으로 옮김, 초안) | DL-001~DL-100 |
| 2026-11-11 | 문구 정리(사용자 결정 F2, FC·DSH 문서화): DL-R24와 1장 범위에서 연도 선택지 "공용"은 범위 규칙만이고 "전체"는 Deal 목록에만 있음을 명시(Dashboard DSH-R16·Forecast FC-R26). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체(1장, DL-R25, 인라인 Expected Close). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-12 | 사용자 요청 "Deal 목록에서 디폴트는 내딜만": DL-R19 기본 조건을 역할별로(sales `year=<올해>&mine=1`, admin·user `year=<올해>`), DL-R21 초기화·내 딜만 끄기, 2.1·2.4·DL-UC1 갱신. 조건 있는 주소·Drill-down·기억된 조건은 그대로. 서버(`mine`, DL-R5)·API 변경 없음, **운영 코드 변경 필요**(frontend) | 변경: DL-055·DL-056·DL-057·DL-070(Given을 admin으로 한정). 신규: DL-101~DL-105. 영향: 기본 역할 sales로 조건 없는 `/deals`를 여는 기존 화면 테스트 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 최종 업데이트를 날짜 `last_updated_on`으로, 응답에 `status_changed_on`. 변경 규칙: DL-R10 날짜 비교, DL-R13 정렬 대상·동률, DL-R14 응답 키, DL-R28 상대 일수. 정렬 값 이름 `last_updated_at`과 화면 키 `lastUpdatedAt`은 유지 | 신규 DL-106. 변경 DL-001, DL-030, DL-058 |
| 2026-11-13 | 사용자 요청 "Deals 검색 조건 연도 기본은 전체, 기본 정렬은 최종 업데이트 최신순": DL-R19 기본 조건을 sales `year=all&mine=1`, admin·user `year=all`로, DL-R21 초기화, 2.1·2.4·상태 흐름·DL-UC1 갱신. 기본 정렬(DL-R13 `last_updated_at` `desc`)은 이미 구현되어 있어 규칙 변경 없이 명시만. 조건 있는 주소·Drill-down·기억된 조건은 그대로. 서버·API 변경 없음, **운영 코드 변경 필요**(frontend `defaultListParams`) | 변경: DL-055(기본 정렬 확인 추가)·DL-056·DL-057·DL-070·DL-101·DL-102·DL-103·DL-105. 영향: 기본 조건 주소 `year=2026`을 기대하는 기존 화면 테스트(quarterMulti·period·yearOptions·forecastMulti·vendorQuarter·memory 등)와 UI-056 |
