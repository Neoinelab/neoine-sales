# Dashboard   (feature 코드: DSH, 상태: 확정(2026-11-16 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`backend/src/app/web/routers/dashboard.py`, `app/web/schemas/{dashboard.py,period_params.py}`, `app/application/dashboard/{criteria,get_summary,views}.py`, `app/application/ports/dashboard_repository.py`, `app/domain/dashboard/{status_pipeline,quarter_closing}.py`, `app/domain/forecast/{summary,period}.py`의 Dashboard가 쓰는 부분, `app/infra/db/dashboard_tally.py`, `frontend/src/features/dashboard/*`, `data/dashboard.ts`, `gateway/http/dashboard.ts`, `shared/model/forecastKeys.ts`의 `forecastSetsOf`, `test/fake/gateway/dashboard.ts`)와 `docs/user-guide.html` 14장이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트·다른 문서가 어긋나던 점은 2026-11-11 사용자 결정으로 정리했습니다: Fake 게이트웨이는 서버 동작에 맞추고(DSH-R29), Dashboard 연도 선택지에는 '전체'가 없으며(DSH-R16, DL-R24), FC는 규칙 번호로 가리킵니다. 결정 목록은 계획(`artifacts/10-analysis/dsh-plan.md`)에 있습니다.

## 1. 개요

- 목적: 로그인한 모든 사용자가 Pipeline이 Status별로 얼마나 있는지(Status 탭), Expected Close 기준으로 언제 얼마가 Closing될지(Forecast 탭)를 한 화면에서 보고, 숫자를 눌러 그 숫자를 만든 Deal 목록으로 바로 이동한다(Drill-down). 이 화면에서 바꿀 수 있는 값은 없다.
- 사용자(역할): admin·sales·user 모두 같은 화면·같은 숫자(역할에 따른 범위 제한 없음).
- 범위
  - 화면 `/dashboard`: Status·Forecast 탭, 탭별 검색 조건(연도·Quarter 다중 토글·담당자·Vendor)과 URL, Forecast 타일, 전체 Status Pipeline(막대 + 표), 주의 필요 Deal 타일, Quarter Closing Forecast(누적 막대 + 표), Closing Attention 타일, 빈 상태·로딩·오류
  - API `GET /dashboard/summary`(조건 해석·집계·응답 모양)
  - Drill-down 주소 만들기(`drillDown.ts`)와 "Dashboard 숫자 = 같은 조건 Deal 목록 원장" 정합성
  - 게이트웨이 `gateway/http/dashboard.ts`, 요약 조회 훅 `data/dashboard.ts`
- 범위 밖(다른 feature)
  - 이동한 Deal 목록이 주소를 해석·표시·기억하는 방식 → DL(DL-R19, DL-R20, DL-R22, DL-R23, DL-R31). Deal 조건 해석 한 곳(`deal_search.conditions`) 자체 → DL-R15, 연·분기 기간 정의 → DL-R9
  - 기한초과·미업데이트 판정식과 경고 기준 → RK(RK-R3~R5, RK-R11), 경고 기준 저장 뒤 캐시 무효화 → RK-R20
  - `/forecast` 화면·`/forecast/summary`·스냅숏·스케줄러 → FC(실시간 요약 FC-R1~R9, 스냅숏 FC-R10~R18, 스케줄러 FC-R19~R23, 화면 FC-R24~R35). Dashboard Forecast 타일·분기 행은 FC 실시간 요약 합계 행(FC-R4~R6)과 같은 값이어야 한다 — DSH-R6, DSH-R8
  - Status·Forecast 코드의 순서·이름·outcome → CD(CD-R4, CD-R5), Vendor 관리 → CL(CL-R3, CL-R7~R10), 담당자 선택지 `/user-options` → US-R20
  - 업무 날짜·응답 시각 오프셋·앱 시계 → TM(TM-R4, TM-R8, TM-R12), 연도 선택지 범위 규칙 → DL-R24(Dashboard는 '전체'가 없다 — DSH-R16)
  - 공통 권한 분류·401·422 형식·쿼리 id·화면 가드·상단 메뉴·오류 문구·게이트웨이 오류 → PL(PL-R2, PL-R5, PL-R12, PL-R15, PL-R21, PL-R33, PL-R34, PL-R37, PL-R39)
- 관련 화면·메뉴: 상단 메뉴 "Dashboard"(`/dashboard`, PL-R34). 로그인 뒤 첫 화면은 Deals다(PL-R32).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 기간 | Deal의 Expected Close(`revenue_date`)가 속한 연도·분기. 양끝 날짜 포함(DL-R9) |
| 고른 분기 | 요청 `quarter`를 정규화한 분기 집합(중복 제거, 없음·넷 다 = 분기 조건 없음) |
| Forecast 열 | Forecast 코드 중 outcome이 `lost`가 아닌 코드(코드 순서). 타일·분기 표의 열 |
| Open 합계 | outcome이 `open`인 Forecast 열의 합(Won·Lost 제외) |
| Lost 제외 | outcome이 `open` 또는 `won`인 Deal |
| 주의 타일 | 기한초과·미업데이트·이번 달/이번 분기 Expected Close 건수. 기간을 따르지 않는다 |
| 원장 | 같은 조건으로 조회한 Deal 목록(`GET /deals`)의 `total`과 `revenue_amount` 합 |
| Drill-down | 숫자를 눌러 그 숫자를 만든 조건이 담긴 `/deals?…`로 이동하는 것 |
| 활성 탭 조건 | URL의 `<활성 탭>.*` 키로 정한 연도·Quarter·담당자·Vendor |
| Open 집합·Lost 제외 집합 | 응답 Forecast 열에서 만든 key 목록(오름차순): outcome `open` / outcome `open`·`won` |

### 2.2 데이터 모델

DSH는 테이블을 소유하지 않는다. 읽는 값: `deals`(DE-R4, `revenue_date`·`revenue_amount`·`status_key`·`forecast_key`·`owner_user_id`·`vendor_id`), `codes`(CD-R1·CD-R5, 순서·이름·outcome), `deal_actions`(AC-R2의 Action 값, 기한초과·미업데이트 판정의 Next Action 기준 행·최종 업데이트 — RK-R1, RK-R2), `alert_settings`(RK-R11).

서버 조건 모델 `DashboardCriteria`(application, 각 숫자의 조건 정의 단일 출처): `period`(`ForecastPeriod`: `year` 1900~9999 + 고른 분기 집합 또는 없음, 월은 쓰지 않음), `owner_user_id`, `vendor_id`. 숫자마다 만드는 Deal 목록 조건(`DealQuery`)은 DSH-R11 표와 같다. 집계 Port는 `DashboardTallyRepository.tally_by_status(DealQuery)`(Status별 건수·금액)와 `tally_by_quarter(DealQuery)`(연 단위 질의 전용, 분기×Forecast key별, Lost 포함)이고 Forecast 타일은 FC의 `ForecastTallyRepository.tally`(FC-R5)를 같이 쓴다.

### 2.3 비즈니스 규칙

요약 API (`GET /dashboard/summary`)
- **DSH-R1** 로그인한 모든 역할이 조회한다(업무 조회, PL-R2). 미인증은 401 `unauthenticated`(PL-R5). 읽기만 하며 아무것도 저장하지 않는다. 응답 숫자는 역할과 무관하게 같다(다른 담당자의 Deal도 센다).
- **DSH-R2** 쿼리는 정확히 네 키다: `year`(필수, 1900~9999 정수), `quarter`(반복 파라미터, 각 1~4, 최대 4개), `owner_user_id`·`vendor_id`(선택, 쿼리 id — PL-R15). `year` 누락·정수 아님·범위 밖, `quarter`가 정수 아님·1~4 밖·5개 이상, id 형식 오류, 그 밖의 키(`month`, `vendor`, `forecast_key` 등 모르는 키 전부)는 422 `request-validation`(PL-R12; `quarter` 항목 오류 msg "분기는 1~4 중에서 선택하세요.", 위치 `quarter`)이다. 같은 분기를 여러 번 보내면 한 번과 같고, 분기를 보내지 않거나 네 개 모두 보내면 분기 조건이 없다. 없는 담당자·Vendor id는 오류 없이 해당 Deal이 0건이다.
- **DSH-R3** 응답 200의 최상위 키는 정확히 `as_of`, `today`, `period`, `forecasts`, `statuses`, `quarters`, `attention`이다. 서버는 요청마다 시계를 한 번 읽어 `as_of`(그 시각, 서버 오프셋 표기 TM-R8)와 `today`(업무 날짜 `YYYY-MM-DD`, TM-R4)를 정하고, 같은 `today`와 저장된 경고 기준으로 주의 타일을 센다.
- **DSH-R4** `period`는 `{year, quarter, quarters, from, to}`다. `quarters`는 고른 분기 오름차순(분기 조건이 없으면 `[]`), `quarter`는 고른 분기가 정확히 하나일 때 그 값이고 아니면 `null`이다. `from`·`to`는 분기 조건이 없으면 `<year>-01-01`·`<year>-12-31`, 있으면 가장 이른 고른 분기의 첫날·가장 늦은 고른 분기의 마지막 날이다(예: Q1·Q3 → `2026-01-01`·`2026-09-30`, 사이의 Q2는 범위에 보이지만 집계에서는 빠진다 — DSH-R5).
- **DSH-R5** 기간 조건: Deal의 Expected Close가 `year` 안이고, 고른 분기가 있으면 그중 하나에 속해야 한다(OR, 양끝 날짜 포함, DL-R9와 같은 해석). 12-31은 그 해 Q4, 01-01은 다음 해 Q1, 03-31은 Q1, 04-01은 Q2다. Deal 조건은 Deal 목록과 같은 해석 한 곳을 쓴다(DL-R15). 담당자·Vendor 조건은 Owner id·Vendor id 일치이고 함께 주면 AND다.
- **DSH-R6** `forecasts`는 `{columns, cells, open_total}`이다. `columns`는 Forecast 코드 중 outcome이 `lost`가 아닌 코드를 코드 순서(CD-R5)로 `{key, name, outcome, order}`이며 admin이 추가한 코드(outcome `open`, CD-R4)도 들어가고 이름을 바꾸면 새 이름이다. `cells`는 `columns`와 같은 순서의 `{key, count, amount}`이고 Deal이 없는 열은 0·0이다. 대상 Deal은 기간(DSH-R5, 고른 분기 포함)·담당자·Vendor 조건이다. `open_total`은 outcome `open` 열 셀의 합(Won 제외)이다. 같은 조건의 Forecast 실시간 요약 합계 행(FC-R4~R6, 조건 해석 FC-R3)과 열·셀·Open 합계가 같다.
- **DSH-R7** `statuses`는 `{items, total}`이다. `items`는 모든 Status 코드를 코드 순서로 `{key, name, order, count, amount}`이고 Deal이 없는 Status도 0·0으로 있다. 대상은 DSH-R6과 같은 조건(기간·고른 분기·담당자·Vendor)이면서 Forecast outcome이 `lost`가 아닌 Deal이다(Won(계약완료) 포함, Lost 제외). `total`은 `items`의 합이다.
- **DSH-R8** `quarters`는 고른 분기와 무관하게 항상 Q1~Q4 네 행이고 각 행은 `{quarter, from, to, cells, open_total, total}`이다. 대상은 `year` 전체·담당자·Vendor 조건이다. `from`·`to`는 그 분기의 첫날·마지막 날, `cells`는 DSH-R6 `columns`와 같은 순서(Lost 열·Lost Deal 없음, 0 포함), `open_total`은 outcome `open` 셀의 합, `total`은 `open_total` + Won 셀이다. 각 분기 행은 같은 연도·그 분기·담당자·Vendor의 Forecast 실시간 요약 합계 행(FC-R4~R6)과 같다.
- **DSH-R9** `attention.stale_days`는 저장된 경고 기준(RK-R11, 저장한 적이 없으면 14)이다. `attention.overdue`·`attention.stale`은 **기간을 무시하고** 담당자·Vendor 조건만 적용한 Deal 중 기한초과·미업데이트인 Deal 수다(판정은 RK-R3~R5, 같은 요청의 업무 날짜·경고 기준). 그래서 같은 담당자·Vendor의 Deal 목록 `overdue=true`·`stale=true` `total`(DL-R12)과 같다.
- **DSH-R10** `attention.closing_this_month`는 `{year, month, count}`, `attention.closing_this_quarter`는 `{year, quarter, count}`이다. 연·월·분기는 업무 날짜(DSH-R3)의 것이고(12-31이면 그 해 12월·Q4, 01-01이면 새해 1월·Q1), `count`는 Expected Close가 그 달·그 분기인 **Forecast outcome `open`** Deal(Won·Lost 제외) 중 담당자·Vendor 조건에 맞는 수다. 요청의 연도·고른 분기는 무시한다.
- **DSH-R11** 정합성: 응답의 모든 숫자는 아래 조건의 Deal 목록 원장(건수와 `revenue_amount` 합)과 같다. 조건 정의는 서버 `DashboardCriteria` 한 곳이고, 화면 Drill-down 주소(DSH-R25)도 같은 Deal을 고른다(outcome 대신 응답 Forecast 열로 만든 key 집합을 보내도 결과가 같다 — admin이 추가한 Open 코드 포함).

  | 숫자 | 같은 Deal 목록 조건 |
  | --- | --- |
  | `forecasts.cells[k]` | `year`·고른 분기·담당자·Vendor + `forecast_key=k` |
  | `forecasts.open_total` | 같은 기간·담당자·Vendor + outcome `open`(Open 집합) |
  | `statuses.items[s]` | 같은 기간·담당자·Vendor + `status_key=s` + Lost 제외 |
  | `statuses.total` | 같은 기간·담당자·Vendor + Lost 제외 |
  | `attention.overdue` / `stale` | 담당자·Vendor + `overdue=true` / `stale=true` |
  | `closing_this_month` | 업무 날짜의 연·월 + 담당자·Vendor + outcome `open` (건수만) |
  | `closing_this_quarter` | 업무 날짜의 연·분기 + 담당자·Vendor + outcome `open` (건수만) |
  | `quarters[q].cells[k]` | `year`·분기 q·담당자·Vendor + `forecast_key=k` |
  | `quarters[q].open_total` / `total` | `year`·분기 q·담당자·Vendor + outcome `open` / Lost 제외 |
- **DSH-R12** 금액(`amount`)은 해당 Deal `revenue_amount`(원)의 합 그대로이고 반올림·단위 변환이 없다. 32비트를 넘는 합도 정확하다. 건수(`count`)는 Deal 수다.

화면 (frontend, `/dashboard`, 가드 PL-R33: 로그인한 모든 역할)
- **DSH-R13** 화면 틀: 제목(h1) "Dashboard", 바로 아래 탭 목록(이름 "Dashboard 보기", 강조 탭 모양 `tabs-prominent`) "Status"·"Forecast" 두 개. 필터 바·오류 배너·안내·내용은 활성 탭 패널 안에 있다. 쓰기 동작은 없다. 예전 "준비 중" 화면 문구는 어디에도 없다. 화면 코드는 지연 로딩된다.
- **DSH-R14** URL 읽기: `tab`이 `forecast`면 Forecast 탭, 그 밖의 값·없음은 Status 탭이다(대소문자 구분, `FORECAST`·`reports`·빈 값은 Status). 탭마다 키 `<탭>.year`·`<탭>.quarter`·`<탭>.owner`·`<탭>.vendor`(탭 = `status`·`forecast`)를 따로 읽는다.
  - `year`는 4자리 숫자이고 1900 이상일 때만 쓰고, 아니면 올해(앱 시계, TM-R12)다. 요약 응답의 `today`로 기본 연도를 정하지 않는다.
  - `quarter`는 콤마로 구분한 1~4 목록(형식이 틀린 항목은 버림, 오름차순·중복 제거, 넷 다면 넷 다 그대로)이다.
  - `owner`·`vendor`는 1~2^53−1 정수 id만 쓰고(`abc`·`0`·`-3`·UUID는 무시 = 전체) 그 밖은 없음이다.
  - 하위 호환: 접두사 없는 예전 키 `year`·`owner`·`vendor`는 두 탭 모두에, `quarter`는 Status 탭에만 쓴다. 같은 탭의 접두사 키가 있으면 그 값이 정본이고(틀린 값이라도 예전 키로 대체하지 않는다) 예전 키는 무시한다. 예전 Selected Quarter 키 `sq`와 Forecast 화면의 키(`month`·기준 시점 등)는 읽지 않는다.
  - 주소를 여는 것만으로는 URL을 바꾸지 않는다.
- **DSH-R15** URL 쓰기: 조건이나 탭을 바꾸면 URL을 `tab`, 두 탭의 `<탭>.year`(기본값이어도 항상), 값이 있는 `<탭>.quarter`(오름차순 콤마, 넷 다 누른 상태면 `1,2,3,4`)·`<탭>.owner`·`<탭>.vendor`(10진 정수)로 다시 쓴다(키 순서 고정: `tab`, status.*, forecast.*). 접두사 없는 예전 키와 `sq`는 쓰지 않는다. 조건 변경은 **활성 탭의 조건만** 바꾸고 다른 탭 조건은 그대로다. 탭을 바꾸면 그 탭의 마지막 조건이 보인다. Dashboard 조건은 따로 기억하지 않는다(메뉴 링크는 `/dashboard`라 다시 들어오면 기본값).
- **DSH-R16** 필터 바(폼 이름 "Dashboard 필터", 두 탭 같은 칸, 값은 URL이 가진다): 순서 연도, Quarter, 담당자, Vendor. 월 칸은 없다.
  - 연도: 선택 상자 "연도". 선택지는 DL-R24의 범위 규칙(가장 이른 Expected Close 연도와 올해 중 작은 값 ~ 내년 연속, 읽는 동안·실패·Deal 없음은 올해·내년, URL 연도가 범위 밖이면 더해 선택된 상태)이되 **'전체' 항목이 없다**('전체'는 Deal 목록에만 있다 — DL-R24, 2026-11-11 결정). 연도 기준 조회가 실패하면 필터 안에 오류 배너를 보이고 요약 조회는 계속된다.
  - Quarter: 이름 "Quarter"인 버튼 묶음 Q1~Q4(토글, `aria-pressed`). 여러 개를 함께 누를 수 있고 누른 순서와 무관하게 URL에는 오름차순이다. 넷 다 눌러도 눌린 상태·URL을 유지하지만 조회·Drill-down에는 분기를 넣지 않는다(= 전체). 넷 중 하나를 끄면 나머지 셋으로 조회한다.
  - 담당자: 선택 상자 "담당자" — "전체" + 사용자 선택지(퇴사자 포함, "이름(퇴사)", US-R20).
  - Vendor: 선택 상자 "Vendor" — "전체" + Vendor 이름(값은 id). Vendor 목록을 읽은 뒤 URL id가 목록에 없으면 "전체"로 보이고 조회·Drill-down에서도 뺀다(표시 = 조건, 활성 탭만 판정). 목록을 읽는 동안·실패하면 URL id를 조회에 쓰고 선택지에 "선택한 Vendor" 하나를 더해 선택된 상태로 보인다(실패하면 필터 안 오류 배너).
- **DSH-R17** 조회: 활성 탭 조건만으로 요약을 조회한다(`year`, 정규화한 분기, 담당자, Vendor). 비활성 탭은 조회하지 않는다. 같은 조건은 같은 캐시라 탭을 오가거나 두 탭 조건이 같으면 다시 요청하지 않고, 이미 본 조건으로 돌아가면 캐시를 쓴다. 조건을 바꾸면 새 응답이 올 때까지 이전 숫자를 그대로 보이면서 "불러오는 중…"(`status`)을 보이고 Drill-down을 막는다(DSH-R26). 실패하면 오류 배너(PL-R37)를 보이고 재시도하지 않으며 필터는 계속 쓸 수 있다(501도 같은 오류 배너, "준비 중" 문구 없음). Deal·코드·사용자·Action 변경과 경고 기준 저장(RK-R20) 뒤에는 요약 캐시를 갱신한다.
- **DSH-R18** 안내와 빈 상태: 응답이 있으면 "기간은 Expected Close 기준이며 금액 단위는 원입니다. 기준일 <응답 today>"를 보인다. Forecast 타일 건수 합이 0이고, Status 탭은 `statuses.total` 건수가 0, Forecast 탭은 보이는 분기 행(DSH-R22)의 합계·셀 건수가 모두 0이면 "조건에 맞는 Deal이 없습니다."를 보인다(주의 타일은 판단에 넣지 않는다). 빈 상태에서도 타일·표·차트는 0으로 그대로 보인다.
- **DSH-R19** Forecast 타일(두 탭 공통, 영역 이름 "Forecast 구분별 금액(단위:원)"): outcome `open` 열을 코드 순서로, 이어서 "Open 합계", 마지막에 Won 열. Won 타일 제목은 "<코드 이름> (<기간>)"이고 기간은 응답 `period.quarters`가 있으면 "2026 Q1, Q3", 없으면 "2026"이다(넷 다 누른 상태도 "2026"). 타일마다 "N건"과 금액(원 단위 콤마)을 보인다. Lost 타일은 없다. 이름은 서버가 준 코드 이름이다(admin이 추가·이름 변경한 코드 포함).
- **DSH-R20** Status 탭: Forecast 타일 → 패널 "전체 Status Pipeline"(h2, 안내 "Lost를 제외한 Deal입니다. 막대나 표의 이름을 누르면 해당 Deal 목록으로 이동합니다.") → 주의 필요 Deal 타일 순서.
  - 막대 차트(`img`, 접근성 이름 "Status별 Deal 금액(단위:원) 막대 차트. 같은 값이 아래 표에 있습니다."): Status마다 막대 하나(코드 순서, Deal 없는 Status는 높이 0), 가로축 라벨 "<이름> (N건)", 막대 높이는 금액(원), 데이터셋 하나 "금액(단위:원)", 범례 없음, 세로축 제목 "금액(단위:원)"·눈금은 "18.7억"·"5,000만"처럼 단축, 툴팁 "금액(단위:원): <원 콤마>"(단축 없음). Forecast 탭에는 그리지 않는다.
  - 표(이름 "Status별 건수와 금액"): 열 Status, 건수, 금액(단위:원). 행은 코드 순서이고 이름이 링크, 건수 "N건", 금액 원 콤마. 맨 아래 "합계" 행(링크)은 응답 `statuses.total`이다.
- **DSH-R21** 주의 필요 Deal 타일(Status 탭, 영역 이름 "주의 필요 Deal"): "기한초과", "<stale_days>일 이상 미업데이트", "이번 분기(<year> Q<quarter>) Expected Close" 세 개, 각 "N건"(0건도 보임). 값과 연·분기는 응답 그대로다(브라우저 날짜를 쓰지 않음). 고른 분기를 바꿔도 숫자·링크가 같다.
- **DSH-R22** Forecast 탭: Forecast 타일 → 패널 "Quarter Closing Forecast"(h2, 안내 "Expected Close가 속한 분기별 Forecast 구분 금액입니다(Lost 제외). 고른 분기만 보이며, 고르지 않으면 4개 분기를 모두 보입니다.") → Closing Attention 순서. **보이는 분기 행**은 활성 탭의 정규화한 고른 분기(오름차순)이고 분기 조건이 없으면(없음·넷 다) Q1~Q4 모두다.
  - 누적 막대 차트(`img`, 접근성 이름 "분기별 Forecast 구분 금액(단위:원) 누적 막대 차트. 같은 값이 아래 표에 있습니다."): 가로축은 보이는 분기 "Q1"…, 데이터셋은 Forecast 열(코드 순서, Lost 없음, 이름 = 코드 이름, 열마다 다른 색), 값은 그 분기 셀 금액, 가로·세로 모두 누적, 범례 아래, 세로축 제목·눈금은 DSH-R20과 같고 툴팁 "<코드 이름>: <원 콤마>". 어떤 막대도 흐리게 하거나 강조하지 않는다.
  - 표(이름 "분기별 Forecast 구분 금액", 캡션 "셀 값: 건수 · 금액(단위:원)"): 열 분기, Forecast 열 이름들, "Open 합계", "합계". 행은 보이는 분기(행 머리 "Q1" 등, 링크 아님), 칸은 "N건 · <원 콤마>" 링크.
  - 예전 Selected Quarter 영역(제목·버튼 묶음·문구)은 없다.
- **DSH-R23** Closing Attention(Forecast 탭, 영역 이름 "Closing Attention"): "이번 달(<month>월) Expected Close", "이번 분기(<year> Q<quarter>) Expected Close", "<stale_days>일 이상 미업데이트" 세 개, 각 "N건". 기한초과 타일은 없다. 값은 응답 그대로다.
- **DSH-R24** 금액 표시: 타일·표·툴팁은 원 단위 콤마 전체 값이고, 차트 세로축 눈금만 억·만 단축이다.
- **DSH-R25** Drill-down 주소(모두 `drillDown.ts` 한 곳): `/deals?` + 쿼리 키를 `year`, `quarter`, `month`, `owner`, `vendor`, `status`, `forecast`, `overdue`, `stale` 순서로 쓴다. `sort`·`order`·`page`·`outcome`은 넣지 않는다. 범위(scope)는 활성 탭의 연도·정규화한 분기(오름차순 콤마, 없으면 키 없음)·담당자·**표시 기준** Vendor(DSH-R16)다. Open 집합·Lost 제외 집합은 응답 Forecast 열로 만든 key를 오름차순 콤마로 `forecast`에 쓴다.

  | 누른 곳 | 주소의 조건 |
  | --- | --- |
  | Forecast 타일(Open 코드·Won) | 연도·고른 분기·담당자·Vendor + `forecast=<그 key>` |
  | Open 합계 타일 | 연도·고른 분기·담당자·Vendor + Open 집합 |
  | Status 막대·표 행 | 연도·고른 분기·담당자·Vendor + `status=<key>` + Lost 제외 집합 |
  | Status 표 합계 | 연도·고른 분기·담당자·Vendor + Lost 제외 집합 |
  | 기한초과 / 미업데이트 타일 | 담당자·Vendor + `overdue=1` / `stale=1`(연도·분기·Forecast 없음) |
  | 이번 분기 Expected Close | 응답의 연·분기 + 담당자·Vendor + Open 집합 |
  | 이번 달 Expected Close | 응답의 연·월(`month`) + 담당자·Vendor + Open 집합 |
  | 분기 막대 조각·표 Forecast 칸 | 연도·**그 분기 하나**·담당자·Vendor + `forecast=<그 key>`(고른 분기는 따르지 않음) |
  | 분기 표 Open 합계 칸 | 연도·그 분기 하나·담당자·Vendor + Open 집합 |
  | 분기 표 합계 칸 | 연도·그 분기 하나·담당자·Vendor + Lost 제외 집합 |

  보낼 집합이 비면(예: Open 코드가 없음) 그 숫자는 주소를 만들지 않고 링크 없이 글자로 보인다. Won만 있어도 Lost 제외 집합은 비지 않는다.
- **DSH-R26** 누를 수 있는 곳: 타일 전체, Status 표 이름·합계, Status 막대, 분기 표의 숫자 칸, 분기 막대 조각, 주의·Closing Attention 타일. Status 표의 건수·금액 칸과 분기 표의 분기 이름은 누를 수 없다. 막대를 누르면 그 행·칸 링크와 같은 주소로 이동하고, 막대가 아닌 곳을 누르면 아무 일도 없다. 막대 위에서만 손가락 커서다. 표 링크는 키보드(Tab·Enter)로 쓸 수 있다. 이전 응답을 보이는 동안(DSH-R17)에는 모든 링크가 글자로 바뀌고 막대 클릭도 무시한다.
- **DSH-R27** 이동 결과: 이동한 Deal 목록은 그 주소의 조건만으로 조회되고(DL-R20, 이전 정렬·페이지 없음 → 기본 정렬 1페이지) 필터 바에 같은 값이 보이며, 목록의 "총 N건"과 금액 합은 누른 숫자와 같다(DSH-R11). 목록 조건 기억은 이 조건으로 바뀌어(DL-R31) 이후 상단 메뉴 Deals가 이 조건을 연다. Dashboard를 보기만 해서는 목록 기억이 바뀌지 않는다. 브라우저 뒤로 가기는 같은 탭·조건의 Dashboard로 돌아온다.
- **DSH-R28** 게이트웨이(`gateway/http/dashboard.ts`): `summary(query)`는 `GET /dashboard/summary`에 `year`, 분기마다 반복하는 `quarter`(목록이 비면 키 없음), 있을 때만 `owner_user_id`·`vendor_id`(정수)를 보내고 월은 보내지 않는다. 응답을 camelCase로 바꾼다: `asOf`, `today`, `period{year, quarter, quarters, from, to}`, `forecast{columns(outcome은 `won` 아니면 `open`), cells(key별 Record, 열에 있는데 목록에 없는 key는 0·0), openTotal}`, `statuses{items(서버 순서), total}`, `quarters[{quarter, from, to, cells(Record), openTotal, total}]`, `attention{staleDays, overdue, stale, closingThisMonth, closingThisQuarter}`. `period.quarters`나 분기 행 번호가 1~4 밖이면 형식이 틀린 응답(502 "서버 응답을 해석할 수 없습니다.", PL-R39)이다. 오류는 PL-R39로 `ApiError`가 된다(422 `request-validation`은 kind `validation`, 401은 `unauthorized`).
- **DSH-R29** Fake 게이트웨이(`test/fake/gateway/dashboard.ts`)는 요약 조건 해석·집계에서 서버와 같은 규칙을 따른다. 서버와 달랐던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**: 범위 밖 연도·분기는 서버와 같은 422 `request-validation`(게이트웨이 kind `validation`, detail "요청 형식이 올바르지 않습니다", DSH-R2)이고 Fake 고유 detail("연도는 1900~9999 중에서 입력하세요."·"분기는 1~4 중에서 선택하세요.")을 쓰지 않는다. 화면은 이런 값을 보내지 않는다(DSH-R14). 검증은 BDD 밖 Fake 자체 테스트(`test/fake/gateway/dashboard.test.ts`)가 한다.

### 2.4 상태와 전이

해당 없음(조회 feature). 화면 조건 상태는 URL이다: 조건 없는 `/dashboard` → 두 탭 올해·분기 없음·담당자/Vendor 전체(URL은 그대로) → (조건·탭 변경) → `tab` + 두 탭 키를 모두 쓴 주소.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /dashboard/summary` | 401 | 가능 | 가능 | 가능 |
| 화면 `/dashboard`·Drill-down | `/login`으로 | 가능 | 가능 | 가능 |

업무 조회(PL-R2)라 역할 가드·CSRF가 없다. 역할에 따라 숫자가 달라지지 않는다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/dashboard/summary` | query `year`(필수, 1900~9999), `quarter?`(반복, 1~4, ≤4개), `owner_user_id?`(id), `vendor_id?`(id). 그 밖의 키 금지 | 200 `DashboardSummaryResponse` | 401 `unauthenticated`, 422 `request-validation` |

`DashboardSummaryResponse`:
```
{
  "as_of": "2026-10-23T12:00:00+09:00",
  "today": "2026-10-23",
  "period": {"year": 2026, "quarter": null, "quarters": [1, 3], "from": "2026-01-01", "to": "2026-09-30"},
  "forecasts": {
    "columns": [{"key": "pipeline", "name": "Pipeline", "outcome": "open", "order": 1}, …, {"key": "won", "name": "Won", "outcome": "won", "order": 5}],
    "cells": [{"key": "pipeline", "count": 1, "amount": 100}, …],
    "open_total": {"count": 2, "amount": 300}
  },
  "statuses": {"items": [{"key": "prospecting", "name": "기회발굴", "order": 1, "count": 2, "amount": 150}, …], "total": {"count": 4, "amount": 650}},
  "quarters": [{"quarter": 1, "from": "2026-01-01", "to": "2026-03-31", "cells": [...], "open_total": {...}, "total": {...}}, … Q4],
  "attention": {"stale_days": 14, "overdue": 0, "stale": 0,
                "closing_this_month": {"year": 2026, "month": 10, "count": 1},
                "closing_this_quarter": {"year": 2026, "quarter": 4, "count": 3}}
}
```
- openapi: 경로는 GET만, 파라미터 이름은 정확히 `year`·`quarter`·`owner_user_id`·`vendor_id`, `quarter`는 정수 배열(항목 1~4 문서화, 최대 4개), `DashboardPeriodResponse.quarters`는 필수 정수 배열. 공통 오류 문서화는 PL-R21.

### 2.7 화면 동작

DSH-R13~DSH-R29.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| `year` 누락·형식·범위 밖, `quarter` 형식·범위 밖·5개 이상, id 형식, 모르는 키(`month` 포함) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12, 분기 항목 msg "분기는 1~4 중에서 선택하세요.") |
| 미인증 | 401 `unauthenticated` | 로그인이 필요합니다(PL-R5) |
| 응답 형식 오류(화면) | 502 | 서버 응답을 해석할 수 없습니다.(PL-R39) |

화면 문구: "Dashboard", "Status", "Forecast", "불러오는 중…", "기간은 Expected Close 기준이며 금액 단위는 원입니다. 기준일 YYYY-MM-DD", "조건에 맞는 Deal이 없습니다.", "전체 Status Pipeline", "Quarter Closing Forecast", "Open 합계", "합계", "기한초과", "N일 이상 미업데이트", "이번 분기(YYYY QN) Expected Close", "이번 달(N월) Expected Close", "선택한 Vendor", 패널 안내 문구(DSH-R20·R22). 서버 오류 문구 표시는 PL-R37.

## 3. Business use case

### DSH-UC1 Status별 Pipeline 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, `/dashboard`(메뉴 Dashboard)
- 기본 흐름: Status 탭이 올해 조건으로 열린다 → Forecast 타일, 전체 Status Pipeline 막대·표, 주의 필요 Deal 타일을 본다(DSH-R1~R7, R9, R10, R13, R18~R21)
- 대안: 조건을 바꾼다(DSH-UC3), 숫자를 누른다(DSH-UC4)
- 예외: 조회 실패면 오류 배너, Deal이 없으면 빈 상태 문구와 0
- 결과: 고른 기간·담당자·Vendor의 Status별 건수·금액(Lost 제외)과 기간과 무관한 주의 건수

### DSH-UC2 분기별 Closing 전망 보기
- 행위자: 로그인한 모든 역할
- 기본 흐름: Forecast 탭을 고른다 → 고른 분기 합계 타일, 분기별 누적 막대·표, Closing Attention 타일을 본다(DSH-R6, R8, R10, R22, R23)
- 대안: 분기를 고르면 고른 분기 행만 보인다
- 결과: 연도의 분기별 Forecast 구분 금액(Lost 제외)과 이번 달·분기 Expected Close 건수

### DSH-UC3 조건 바꾸기
- 행위자: 로그인한 모든 역할
- 기본 흐름: 활성 탭에서 연도·Quarter·담당자·Vendor를 바꾼다 → URL이 바뀌고 그 탭 조건으로 다시 조회한다(DSH-R2, R5, R14~R17)
- 대안: 탭을 바꾸면 그 탭의 마지막 조건, 예전 주소·공유 주소로 들어옴, 넷 다 눌러 전체
- 예외: 틀린 URL 값은 무시, 목록에 없는 Vendor는 전체, 연도·Vendor 목록 실패는 필터 오류 배너
- 결과: 활성 탭 조건의 숫자(다른 탭 조건은 그대로)

### DSH-UC4 숫자에서 Deal 목록으로 이동(Drill-down)
- 행위자: 로그인한 모든 역할
- 기본 흐름: 타일·막대·표 숫자를 누른다 → 그 숫자의 조건이 담긴 Deals 목록이 열린다(DSH-R11, R25~R27)
- 대안: 차트 막대를 누른다, 뒤로 가기로 Dashboard에 돌아온다
- 예외: 응답을 기다리는 동안·보낼 Forecast 집합이 없으면 누를 수 없다
- 결과: 목록 "총 N건"·금액 합이 누른 숫자와 같고 그 조건이 목록 기억이 된다

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), LEE(sales), VIEWER(user). backend 케이스의 서버 업무 날짜는 2026-10-23(Asia/Seoul, 이번 달 10월·이번 분기 Q4)이고 Fake UoW(Deal·코드·사용자·Vendor·Action·경고 기준·Dashboard 집계 Fake)를 쓰는 유스케이스 단위 테스트, 또는 FakeUseCases + HTTP 클라이언트를 쓰는 web 단위 테스트다. frontend 케이스는 Fake 게이트웨이(앱 시계 2026-10-15, 올해 2026·10월·Q4)를 쓰는 Vitest다. 기본 Forecast 열은 Pipeline·Best·Most Likely·Commit(Open)·Won, Lost는 열이 아니다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| DSH-001 | 모든 역할이 요약을 읽고 미인증은 401이다 | DSH-R1, DSH-UC1 | backend | `web/test_dashboard_routes.py` |
| DSH-002 | year 누락·문자·1899·10000은 422이고 1900·9999는 된다 | DSH-R2, DSH-UC3 | backend | `web/test_dashboard_routes.py`, `web/test_dashboard_params.py` |
| DSH-003 | 분기 0·5·문자·5개, 모르는 키(month·vendor), 문자 id는 422 request-validation이다 | DSH-R2, DSH-UC3 | backend | `web/test_dashboard_routes.py`, `web/test_dashboard_params.py` |
| DSH-004 | 응답은 일곱 키이고 as_of·today는 서버 시계의 시각·업무 날짜다 | DSH-R3, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py` |
| DSH-005 | 연만 주면 period는 quarter null·quarters []·연 전체이고 분기 하나면 그 분기다 | DSH-R4, DSH-UC3 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py` |
| DSH-006 | 여러 분기는 오름차순 quarters와 첫 분기~마지막 분기 범위이고 넷 다·빈 목록·중복은 정규화된다 | DSH-R4, DSH-R2, DSH-UC3 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py`, `web/test_dashboard_params.py` |
| DSH-007 | Forecast 열은 Lost를 뺀 코드 순서이고 추가한 Open 코드가 열과 Open 합계에 든다 | DSH-R6, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py`, `domain/test_dashboard_quarter_closing.py` |
| DSH-008 | Forecast 타일은 같은 조건 Forecast 실시간 합계 행과 같다 | DSH-R6, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-009 | Q1·Q3를 고르면 타일과 Status는 두 분기 Deal만 센다 | DSH-R5, DSH-R6, DSH-R7, DSH-UC3 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-010 | Status 항목은 모든 Status 코드를 순서대로 담고 Deal이 없으면 0이다 | DSH-R7, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py`, `domain/test_dashboard_status_pipeline.py` |
| DSH-011 | Status는 Lost를 빼고 Won을 넣으며 합계는 항목의 합이다 | DSH-R7, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py`, `domain/test_dashboard_status_pipeline.py` |
| DSH-012 | Status는 연도·분기·담당자·Vendor를 따르고 기간 밖 Deal은 빠진다 | DSH-R7, DSH-R5, DSH-UC3 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-013 | 기간 경계는 Expected Close 양끝 포함이다(12-31·01-01·03-31·04-01) | DSH-R5, DSH-UC3 | backend | `application/test_get_dashboard_summary.py`, `domain/test_deal_quarter_of.py` |
| DSH-014 | 분기 행은 고른 분기와 무관하게 Q1~Q4이고 합계는 Open + Won, Lost는 없다 | DSH-R8, DSH-UC2 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py`, `application/test_dashboard_criteria.py`, `domain/test_dashboard_quarter_closing.py` |
| DSH-015 | 분기 행은 담당자·Vendor를 따르고 각 분기가 그 분기 Forecast 합계 행과 같다 | DSH-R8, DSH-UC2 | backend | `application/test_get_dashboard_summary.py` |
| DSH-016 | 기한초과·미업데이트 수는 기간을 무시하고 담당자·Vendor만 따르며 종결 Deal은 빠진다 | DSH-R9, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-017 | stale_days는 저장한 경고 기준이고 없으면 14이며 14일째부터 미업데이트다 | DSH-R9, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `web/test_dashboard_routes.py` |
| DSH-018 | 이번 달·이번 분기 Expected Close는 업무 날짜의 Open Deal만 세고 고른 기간을 무시한다 | DSH-R10, DSH-UC2 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-019 | 업무 날짜가 12-31이면 12월·Q4, 01-01이면 새해 1월·Q1이다 | DSH-R10, DSH-UC2 | backend | `application/test_get_dashboard_summary.py`, `application/test_dashboard_criteria.py` |
| DSH-020 | 이번 달·이번 분기 Expected Close는 담당자·Vendor를 따른다 | DSH-R10, DSH-UC2 | backend | `application/test_get_dashboard_summary.py` |
| DSH-021 | Deal이 없으면 모든 숫자가 0이다 | DSH-R6, DSH-R7, DSH-R8, DSH-R9, DSH-R10, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `domain/test_dashboard_status_pipeline.py` |
| DSH-022 | 조건 조합마다 모든 숫자가 같은 조건 Deal 목록 원장과 같다 | DSH-R11, DSH-UC4 | backend | `application/test_get_dashboard_summary_ledger.py` |
| DSH-023 | Open 합계·Lost 제외 합계는 응답 Forecast 열로 만든 key 집합 목록 total과 같다 | DSH-R11, DSH-UC4 | backend | `application/test_dashboard_criteria.py`, `application/test_get_dashboard_summary_ledger.py` |
| DSH-024 | 금액은 원 합계 그대로이고 32비트를 넘어도 정확하다 | DSH-R12, DSH-UC1 | backend | `application/test_get_dashboard_summary.py`, `repositories/test_dashboard_tally_contract.py` |
| DSH-025 | /dashboard는 모든 역할에게 제목과 Status·Forecast 탭을 보이고 미인증은 로그인으로 간다 | DSH-R13, DSH-UC1 | frontend | `features/dashboard/DashboardPage.test.tsx`, `App.test.tsx`, `features/dashboard/DashboardPage.layout.test.tsx`, `test/crossScreen.test.tsx` |
| DSH-026 | tab=forecast면 Forecast 탭이고 모르는 tab 값은 Status 탭이다 | DSH-R14, DSH-UC1 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/dashboardParams.test.ts` |
| DSH-027 | 조건 없이 열면 두 탭이 앱 시계 올해·분기 없음·전체이고 연도만 조회한다 | DSH-R14, DSH-R16, DSH-R17, DSH-UC1 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/DashboardPage.reviewFollowUp.test.tsx`, `features/dashboard/DashboardPage.serverTime.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx` 외 1건 |
| DSH-028 | 조건은 탭마다 따로이고 탭을 오가도 각 탭 조건이 남는다 | DSH-R15, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx`, `features/dashboard/dashboardParams.test.ts` |
| DSH-029 | 조건을 바꾸면 tab·두 연도·값 있는 접두사 키만 URL에 쓰고 새로고침하면 복원된다 | DSH-R15, DSH-R14, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx`, `features/dashboard/dashboardParams.test.ts` |
| DSH-030 | 예전 주소는 year·owner·vendor를 두 탭에, quarter를 Status 탭에만 쓰고 sq는 무시한다 | DSH-R14, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.forecast.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx`, `features/dashboard/QuarterChart.test.tsx` 외 1건 |
| DSH-031 | 틀린 URL 연도·담당자·Vendor·분기 값은 무시된다 | DSH-R14, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/dashboardParams.test.ts` |
| DSH-032 | 필터 바는 두 탭 모두 연도·Quarter·담당자(퇴사자 포함)·Vendor이고 월이 없다 | DSH-R16, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx` |
| DSH-033 | 연도 선택지는 가장 이른 연도~내년이고 전체가 없으며 실패하면 올해·내년과 오류 배너다 | DSH-R16, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.years.test.tsx` |
| DSH-034 | Quarter 토글은 여러 개를 오름차순으로 URL에 쓰고 활성 탭 조회에 보낸다 | DSH-R16, DSH-R17, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/dashboardParams.test.ts` |
| DSH-035 | 넷 다 누르면 눌린 상태·URL은 남지만 조회·링크에는 분기가 없고 숫자는 전체와 같다 | DSH-R16, DSH-R25, DSH-UC3 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx`, `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/dashboardParams.test.ts`, `features/dashboard/drillDown.test.ts` |
| DSH-036 | 목록에 없는 Vendor는 전체로 보이고 빠지며 목록을 읽는 동안·실패하면 선택한 Vendor로 조회한다 | DSH-R16, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx`, `features/dashboard/DashboardPage.vendorLoad.test.tsx` |
| DSH-037 | 활성 탭 조건만 조회하고 같은 조건은 다시 요청하지 않는다 | DSH-R17, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx` |
| DSH-038 | 새 조건을 기다리는 동안 이전 숫자를 보이며 불러오는 중이고 링크를 막는다 | DSH-R17, DSH-R26, DSH-UC3 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.reviewFollowUp.test.tsx` |
| DSH-039 | 요약 조회가 실패하면 오류 배너를 보이고 필터는 계속 쓸 수 있다 | DSH-R17, DSH-UC1 | frontend | `features/dashboard/DashboardPage.test.tsx` |
| DSH-040 | 안내 줄은 응답 기준일을 보이고 Deal이 없으면 두 탭 모두 빈 상태 문구다 | DSH-R18, DSH-UC1 | frontend | `features/dashboard/DashboardPage.test.tsx`, `features/dashboard/DashboardPage.forecast.test.tsx`, `features/dashboard/DashboardPage.reviewFollowUp.test.tsx` |
| DSH-041 | Forecast 타일은 Open 코드 순서·Open 합계·기간이 붙은 Won이고 Lost 타일이 없다 | DSH-R19, DSH-UC1 | frontend | `features/dashboard/DashboardPage.forecast.test.tsx`, `features/dashboard/DashboardPage.status.test.tsx` |
| DSH-042 | Status 표는 코드 순서 행·건수·원 금액·합계 행이고 0 행도 남는다 | DSH-R20, DSH-UC1 | frontend | `features/dashboard/DashboardPage.status.test.tsx` |
| DSH-043 | Status 막대 차트는 코드 순서 막대·"이름 (N건)" 라벨·원 금액 높이이고 Forecast 탭에는 없다 | DSH-R20, DSH-R24, DSH-UC1 | frontend | `features/dashboard/StatusChart.test.tsx`, `features/dashboard/chartAmountUnit.test.tsx` |
| DSH-044 | 주의 필요 Deal 타일은 기한초과·N일 미업데이트·이번 분기이고 응답 값을 보인다 | DSH-R21, DSH-UC1 | frontend | `features/dashboard/DashboardPage.quarters.test.tsx`, `features/dashboard/DashboardPage.status.test.tsx` |
| DSH-045 | 분기 표는 Lost 없는 열·Open 합계·합계이고 고른 분기 행만, 없으면 4행이다 | DSH-R22, DSH-UC2 | frontend | `features/dashboard/DashboardPage.forecast.test.tsx` |
| DSH-046 | 분기 누적 막대는 보이는 분기 축과 Forecast 열 데이터셋이고 강조가 없다 | DSH-R22, DSH-R24, DSH-UC2 | frontend | `features/dashboard/QuarterChart.test.tsx`, `features/dashboard/chartAmountUnit.test.tsx` |
| DSH-047 | Closing Attention은 이번 달·이번 분기·미업데이트이고 기한초과가 없다 | DSH-R23, DSH-UC2 | frontend | `features/dashboard/DashboardPage.forecast.test.tsx` |
| DSH-048 | Drill-down 주소는 표의 조건과 고정 키 순서이고 정렬·페이지·outcome이 없다 | DSH-R25, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx`, `features/dashboard/DashboardPage.forecast.test.tsx`, `features/dashboard/DashboardPage.status.test.tsx`, `features/dashboard/DashboardPage.tabFilters.test.tsx`, `features/dashboard/drillDown.test.ts` |
| DSH-049 | 보낼 Forecast 집합이 비면 그 숫자는 링크가 아니다 | DSH-R25, DSH-R26, DSH-UC4 | frontend | `features/dashboard/DashboardPage.status.test.tsx`, `features/dashboard/drillDown.test.ts` |
| DSH-050 | 숫자를 누르면 그 조건만의 Deals 목록이 열리고 필터 바와 목록 기억이 그 조건이다 | DSH-R27, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx` |
| DSH-051 | 목록 총 건수가 누른 숫자와 같다 | DSH-R27, DSH-R11, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx` |
| DSH-052 | 여러 분기를 고른 Drill-down은 같은 분기 목록이고 분기 칸·주의 타일 주소는 고른 분기와 무관하다 | DSH-R25, DSH-R27, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx`, `features/dashboard/DashboardPage.forecast.test.tsx`, `features/dashboard/drillDown.test.ts` |
| DSH-053 | 뒤로 가기는 같은 탭·조건의 Dashboard이고 Dashboard를 보기만 하면 목록 기억이 바뀌지 않는다 | DSH-R27, DSH-R15, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx` |
| DSH-054 | 막대를 누르면 표 링크와 같은 곳으로 가고 빈 곳은 무시하며 표 링크는 키보드로 쓴다 | DSH-R26, DSH-UC4 | frontend | `features/dashboard/DashboardPage.drillDown.test.tsx`, `features/dashboard/QuarterChart.test.tsx`, `features/dashboard/StatusChart.test.tsx` |
| DSH-055 | Deal 변경·경고 기준 저장 뒤 요약을 다시 읽는다 | DSH-R17, DSH-UC1 | frontend | `data/dashboard.test.tsx` |
| DSH-056 | 게이트웨이는 조건을 서버 쿼리로, 응답을 화면 모양으로 바꾼다 | DSH-R28 | frontend | `gateway/http/dashboard.test.ts` |

### DSH-001 모든 역할이 요약을 읽고 미인증은 401이다
- Given KIM이 담당자인 Deal 1건(금액 7, Expected Close 2026-06-30)
- When ROOT·KIM·VIEWER가 각각, 그리고 로그인하지 않은 채 `year=2026`으로 요약을 조회한다
- Then 세 역할은 200이고 `statuses.total`이 `{count: 1, amount: 7}`로 같으며 미인증은 401 `unauthenticated`다

### DSH-002 year 누락·문자·1899·10000은 422이고 1900·9999는 된다
- Given 로그인한 KIM
- When `year` 없이, `year=abc`, `year=1899`, `year=10000`, `year=1900`, `year=9999`로 조회한다
- Then 앞의 넷은 422 `request-validation`, 뒤의 둘은 200이다

### DSH-003 분기 0·5·문자·5개, 모르는 키(month·vendor), 문자 id는 422 request-validation이다
- Given 로그인한 KIM
- When `year=2026`에 `quarter=0`, `quarter=5`, `quarter=x`, `quarter=1&quarter=0`, `quarter`를 1·2·3·4·2로 5개, `month=3`, `vendor=SAP`, `owner_user_id=abc`, `vendor_id=abc`를 각각 붙여 조회한다
- Then 모두 422 `request-validation`이고 분기 오류의 위치는 `quarter`다

### DSH-004 응답은 일곱 키이고 as_of·today는 서버 시계의 시각·업무 날짜다
- Given 서버 시계 2026-10-23 12:00(+09:00)
- When `year=2026&quarter=4`로 조회한다
- Then 최상위 키가 정확히 `as_of`·`today`·`period`·`forecasts`·`statuses`·`quarters`·`attention`이고 `as_of`는 시계 시각(오프셋 표기), `today`는 `2026-10-23`이다

### DSH-005 연만 주면 period는 quarter null·quarters []·연 전체이고 분기 하나면 그 분기다
- When `year=2026`, `year=2026&quarter=2`로 조회한다
- Then 첫째 `period`는 `{year: 2026, quarter: null, quarters: [], from: "2026-01-01", to: "2026-12-31"}`, 둘째는 `{year: 2026, quarter: 2, quarters: [2], from: "2026-04-01", to: "2026-06-30"}`이다

### DSH-006 여러 분기는 오름차순 quarters와 첫 분기~마지막 분기 범위이고 넷 다·빈 목록·중복은 정규화된다
- When `quarter=3&quarter=1`, `quarter`를 1·2·3·4 모두, `quarter` 없이, `quarter=2&quarter=2`로 `year=2026` 조회한다
- Then 첫째 `period`는 `quarter: null, quarters: [1, 3], from 2026-01-01, to 2026-09-30`, 넷 다는 분기 없는 조회와 `period`·숫자가 같고(`quarters: []`), 중복은 `quarters: [2]`다

### DSH-007 Forecast 열은 Lost를 뺀 코드 순서이고 추가한 Open 코드가 열과 Open 합계에 든다
- Given admin이 Forecast 코드 "Verbal"(key `verbal`, 마지막 순서)을 추가했고 2026년 Deal은 Verbal 70원·Pipeline 5원
- When `year=2026`으로 조회한다
- Then `forecasts.columns` key는 `pipeline, best, most_likely, commit, won, verbal` 순서이고 `lost`는 없으며 `cells`도 같은 순서, `verbal` 셀은 1건·70, `open_total`은 2건·75다

### DSH-008 Forecast 타일은 같은 조건 Forecast 실시간 합계 행과 같다
- Given KIM·LEE의 Deal이 2026년 Q1·Q4와 2027년에 Forecast·Vendor(SAP·없음)를 섞어 있다(Lost 포함)
- When 조건 `year=2026`, `+quarter=4`, `+owner=KIM`, `+vendor=SAP`로 Dashboard 요약과 같은 조건의 Forecast 실시간 요약을 각각 조회한다
- Then 각 조건에서 Dashboard `forecasts`의 열·셀·`open_total`이 Forecast 요약 합계 행과 같다

### DSH-009 Q1·Q3를 고르면 타일과 Status는 두 분기 Deal만 센다
- Given 2026-02-01 Pipeline 1원, 2026-05-01 Commit 2원, 2026-08-01 Best 4원, 2025-08-01 Pipeline 8원
- When `year=2026&quarter=1&quarter=3`으로 조회한다
- Then `statuses.total`과 `open_total`은 2건·5이고 Commit 셀은 0, Pipeline 셀은 1건·1이다

### DSH-010 Status 항목은 모든 Status 코드를 순서대로 담고 Deal이 없으면 0이다
- Given 기본 Status 코드 7개와 Deal 없음
- When `year=2026`으로 조회한다
- Then `statuses.items` key가 `prospecting, introduction, poc_preparation, poc_completed, technical_evaluation, price_negotiation, contract_completed` 순서이고 첫 이름은 "기회발굴", 모든 항목과 `total`이 0·0이다

### DSH-011 Status는 Lost를 빼고 Won을 넣으며 합계는 항목의 합이다
- Given 2026년 Deal: 기회발굴·Pipeline 100, POC완료·Commit 200, 계약완료·Won 300, 가격협상·Lost 400
- When `year=2026`으로 조회한다
- Then 기회발굴 1건·100, POC완료 1건·200, 계약완료 1건·300, 가격협상 0이고 `total`은 3건·600(항목 합)이다

### DSH-012 Status는 연도·분기·담당자·Vendor를 따르고 기간 밖 Deal은 빠진다
- Given KIM의 2026-02-01·2026-11-01·2025-12-31·2027-01-01 Deal, LEE의 2026-02-02 Deal, Vendor SAP인 2026-02-03 Deal
- When `year=2026`, `year=2026&quarter=1`, `+owner=LEE`, `+vendor=SAP`로 조회한다
- Then 각 `statuses.total`은 연도 안 4건, Q1 3건, LEE 1건, SAP 1건이고 2025·2027 Deal은 어디에도 없다

### DSH-013 기간 경계는 Expected Close 양끝 포함이다(12-31·01-01·03-31·04-01)
- Given Expected Close가 2026-12-31, 2027-01-01, 2026-03-31, 2026-04-01인 Deal을 하나씩(각 경우 따로)
- When 각각 `year=2026`, `year=2026&quarter=4`, `year=2026`(01-01 Deal), `year=2027&quarter=1`, `year=2026&quarter=1`(03-31·04-01 Deal)로 조회한다
- Then 12-31은 2026과 Q4에 들고, 01-01은 2026에 없고 2027 Q1에 들며, 03-31은 Q1에 들고 04-01은 Q1에 없다(`statuses.total` 건수 1/0)

### DSH-014 분기 행은 고른 분기와 무관하게 Q1~Q4이고 합계는 Open + Won, Lost는 없다
- Given 2026-02-01 Pipeline 1, 2026-05-01 Commit 2, 2026-08-01 Best 4, 2026-12-31 Won 8, 2026-12-30 Lost 99
- When `year=2026&quarter=2`로 조회한다
- Then `quarters`는 Q1~Q4 네 행(각 분기 첫날·마지막 날)이고 `total`이 1·2·4·8, Q4 `open_total`은 0(Won 제외), Lost 99는 어느 칸에도 없으며 `statuses.total`은 Q2만 1건·2다

### DSH-015 분기 행은 담당자·Vendor를 따르고 각 분기가 그 분기 Forecast 합계 행과 같다
- Given KIM·LEE의 2026년 분기별 Deal(Vendor SAP·없음 섞임)
- When `year=2026&owner_user_id=KIM&vendor_id=SAP`로 조회하고 분기마다 같은 담당자·Vendor·분기의 Forecast 실시간 요약을 조회한다
- Then 각 분기 행의 셀·`open_total`이 그 분기 Forecast 합계 행과 같고 `total`은 `open_total` + Won 셀이며 LEE·다른 Vendor Deal은 들지 않는다

### DSH-016 기한초과·미업데이트 수는 기간을 무시하고 담당자·Vendor만 따르며 종결 Deal은 빠진다
- Given Expected Close 2024-05-01인 Pipeline Deal(Due 어제)과 Lost Deal(Due 어제), 2026-10-05인 Deal(Due 오늘), 경고 기준 7일에 7일 동안 Action이 없는 KIM·LEE의 2024년 Deal
- When `year=2026&quarter=1`, 같은 조건에 `owner_user_id=LEE`로 조회한다
- Then `overdue`는 1(기간 밖이어도 세고 Lost·Due 오늘은 제외), 전체 `stale`은 2, LEE만은 1이고 같은 담당자의 Deal 목록 `overdue=true`·`stale=true` total과 같다

### DSH-017 stale_days는 저장한 경고 기준이고 없으면 14이며 14일째부터 미업데이트다
- Given 경고 기준을 저장한 적이 없고 오늘 등록한 Deal 1건
- When 13일 뒤, 14일 뒤, 그리고 경고 기준을 30으로 저장한 뒤 조회한다
- Then `stale_days`는 14, 13일 뒤 `stale` 0, 14일 뒤 1이고 저장 뒤 `stale_days`는 30이다

### DSH-018 이번 달·이번 분기 Expected Close는 업무 날짜의 Open Deal만 세고 고른 기간을 무시한다
- Given 오늘 2026-10-23, Deal: 10-05 Pipeline, 11-15 Commit, 10-30 Won, 10-10 Lost, 09-30 Pipeline, 2027-01-01 Pipeline
- When `year=2020&quarter=1`로 조회한다
- Then `closing_this_month`는 `{year: 2026, month: 10, count: 1}`, `closing_this_quarter`는 `{year: 2026, quarter: 4, count: 2}`다

### DSH-019 업무 날짜가 12-31이면 12월·Q4, 01-01이면 새해 1월·Q1이다
- Given Expected Close 2026-12-31·2027-01-01인 Pipeline Deal
- When 오늘이 2026-12-31일 때와 2027-01-01일 때 `year=2026`으로 조회한다
- Then 12-31에는 `{2026, 12, 1}`·`{2026, Q4, 1}`, 01-01에는 `{2027, 1, 1}`·`{2027, Q1, 1}`이다

### DSH-020 이번 달·이번 분기 Expected Close는 담당자·Vendor를 따른다
- Given 오늘 2026-10-23, KIM의 10-05 Deal, LEE의 10-06·11-06 Deal, Vendor SAP인 10-07 Deal
- When `owner_user_id=LEE`, `vendor_id=SAP`로 조회한다
- Then LEE는 이번 달 1·이번 분기 2, SAP는 이번 분기 1이다

### DSH-021 Deal이 없으면 모든 숫자가 0이다
- Given Deal 없음
- When `year=2026`으로 조회한다
- Then Forecast 셀·`open_total`·Status 항목·분기 행·`overdue`·`stale`·이번 달·이번 분기 건수가 모두 0이다

### DSH-022 조건 조합마다 모든 숫자가 같은 조건 Deal 목록 원장과 같다
- Given KIM·LEE, Vendor SAP·Oracle, 2025-12-31~2027-01-01에 걸친 여러 Status·Forecast(Lost 포함)의 Deal 10건
- When 조건 `year=2026`, `+quarter=4`, `+owner=KIM`, `+vendor=SAP`, `year=2026&vendor=SAP`로 요약을 조회하고 DSH-R11 표의 조건으로 Deal 목록을 조회한다
- Then 각 숫자(Forecast 셀·Open 합계·Status 항목·Status 합계·기한초과·미업데이트·이번 달·이번 분기·분기 셀·분기 합계)의 건수·금액이 목록 원장과 같다

### DSH-023 Open 합계·Lost 제외 합계는 응답 Forecast 열로 만든 key 집합 목록 total과 같다
- Given 추가 Open 코드 Verbal과 2026년 Deal: Pipeline 10, Commit 20, Verbal 30, Won 40, Lost 50
- When `year=2026` 요약의 `forecasts.columns`에서 Open 집합·Lost 제외 집합을 만들어 같은 연도로 `forecast_key`를 반복한 Deal 목록을 조회한다(분기 Q1·Q3를 고른 경우도 같은 분기로 조회)
- Then Open 집합에 `verbal`이 있고 목록 total이 `open_total` 건수(3)와, Lost 제외 집합 목록 total이 `statuses.total` 건수(4)와 같다

### DSH-024 금액은 원 합계 그대로이고 32비트를 넘어도 정확하다
- Given 같은 Status의 2026년 Deal 두 건, 금액 3,000,000,000원과 2,500,000,000원
- When 그 조건을 집계한다
- Then 금액 합이 5,500,000,000원으로 정확하다

### DSH-025 /dashboard는 모든 역할에게 제목과 Status·Forecast 탭을 보이고 미인증은 로그인으로 간다
- Given admin·sales·user 각각 로그인(그리고 로그인하지 않은 방문자)
- When `/dashboard`를 열거나 상단 메뉴 "Dashboard"를 누른다
- Then 제목 "Dashboard" 바로 아래 강조 탭 "Status"(선택)·"Forecast"가 있고 "준비 중" 문구가 없으며, 미인증은 `/login`으로 간다

### DSH-026 tab=forecast면 Forecast 탭이고 모르는 tab 값은 Status 탭이다
- When `/dashboard?tab=forecast`, `?tab=reports`, `?tab=FORECAST`, `?tab=`을 연다
- Then 첫째만 Forecast 탭(제목 "Quarter Closing Forecast")이고 나머지는 Status 탭이다

### DSH-027 조건 없이 열면 두 탭이 앱 시계 올해·분기 없음·전체이고 연도만 조회한다
- Given 앱 시계가 2026-12-31 23:30(+09:00)이고 요약 응답의 today는 2027-01-01
- When `/dashboard`와 `/dashboard?tab=forecast`를 연다
- Then 연도는 2026, Quarter 버튼은 모두 눌리지 않음, 담당자·Vendor는 "전체"이고 조회 조건은 `{year: 2026}`뿐이다

### DSH-028 조건은 탭마다 따로이고 탭을 오가도 각 탭 조건이 남는다
- Given `/dashboard?tab=status&status.year=2026&status.quarter=2`
- When Forecast 탭으로 가서 담당자를 고르고 다시 Status 탭으로 온다
- Then Forecast 탭에서는 Q2가 눌리지 않았고, Status 탭으로 돌아오면 Q2가 눌려 있고 담당자는 전체다

### DSH-029 조건을 바꾸면 tab·두 연도·값 있는 접두사 키만 URL에 쓰고 새로고침하면 복원된다
- Given `/dashboard`
- When Status 탭에서 Q2를 누르고, 그 주소(또는 `tab=forecast&forecast.year=2027&forecast.quarter=3&forecast.owner=<PARK>&forecast.vendor=<Okta>`)를 새로 연다
- Then 주소는 `tab=status`, `status.year=2026`, `status.quarter=2`, `forecast.year=2026`만 있고(빈 값·예전 키·`sq` 없음) 새로 연 화면은 같은 탭·연도·눌린 분기·담당자·Vendor를 보인다

### DSH-030 예전 주소는 year·owner·vendor를 두 탭에, quarter를 Status 탭에만 쓰고 sq는 무시한다
- Given `/dashboard?year=2026&quarter=3&owner=<KIM>&sq=2`
- When 열고 Forecast 탭으로 간다
- Then Status 조회는 `{year: 2026, quarters: [3], ownerId: KIM}`, Forecast 조회는 `{year: 2026, ownerId: KIM}`이고 Selected Quarter는 없으며, 열기만으로는 주소가 바뀌지 않고 접두사 키가 있으면 그 값이 예전 키보다 우선한다

### DSH-031 틀린 URL 연도·담당자·Vendor·분기 값은 무시된다
- When `owner=abc`, `owner=0`, `owner=-3`, 4자리가 아니거나 1900 미만인 연도, `quarter=1,x,5` 주소를 연다
- Then 담당자는 "전체"이고 조회에 담당자가 없으며, 연도는 올해, 분기는 1만 눌린다

### DSH-032 필터 바는 두 탭 모두 연도·Quarter·담당자(퇴사자 포함)·Vendor이고 월이 없다
- When Status 탭과 Forecast 탭을 연다
- Then 폼 "Dashboard 필터"에 "연도", "Quarter" 버튼 묶음(Q1~Q4), "담당자"(퇴사자 "강퇴사(퇴사)" 포함), "Vendor"가 있고 "월" 칸은 없다

### DSH-033 연도 선택지는 가장 이른 연도~내년이고 전체가 없으며 실패하면 올해·내년과 오류 배너다
- Given 가장 이른 Expected Close 연도가 2023(또는 없음, 또는 조회 실패)
- When Status 탭·Forecast 탭을 열고, URL 연도 2020인 주소를 연다
- Then 선택지는 2023~2027이고 "전체"·2028은 없으며, 없음·읽는 중은 2026·2027, 실패는 2026·2027과 필터 안 오류 배너, URL 2020은 선택지에 더해져 선택된다

### DSH-034 Quarter 토글은 여러 개를 오름차순으로 URL에 쓰고 활성 탭 조회에 보낸다
- Given Status 탭
- When Q3, Q1 순서로 누르고 Q3를 다시 누른다(Forecast 탭에서도 같은 조작)
- Then 누른 버튼은 `aria-pressed=true`, URL `status.quarter`는 `1,3` 다음 `1`이고 조회는 `quarters: [1, 3]` 다음 `[1]`이며 Forecast 탭은 `forecast.quarter`만 바뀐다

### DSH-035 넷 다 누르면 눌린 상태·URL은 남지만 조회·링크에는 분기가 없고 숫자는 전체와 같다
- When Q1~Q4를 모두 누른 뒤 하나를 끈다
- Then 넷 다 누른 동안 네 버튼이 눌려 있고 URL은 `1,2,3,4`, 조회와 Drill-down 링크에는 분기가 없고 숫자는 분기 없는 조회와 같으며, 하나를 끄면 나머지 셋으로 조회한다

### DSH-036 목록에 없는 Vendor는 전체로 보이고 빠지며 목록을 읽는 동안·실패하면 선택한 Vendor로 조회한다
- Given URL `status.vendor`가 없는 id, 그리고 Vendor 목록을 읽는 중·실패한 경우의 등록된 id
- When 화면을 연다
- Then 없는 id는 목록을 읽은 뒤 "전체"로 보이고 조회·링크에 Vendor가 없으며(다른 탭 조건에는 영향 없음), 읽는 중·실패에는 "선택한 Vendor"가 선택된 채 그 id로 조회하고 실패면 오류 배너를 보인다

### DSH-037 활성 탭 조건만 조회하고 같은 조건은 다시 요청하지 않는다
- Given 두 탭 조건이 같은 주소, 그리고 두 탭 조건이 다른 주소
- When 탭을 오간다
- Then 같은 조건이면 처음 한 번만 요청하고, 다르면 바꾼 탭 조건으로만 요청하며 이미 읽은 조건으로 돌아가면 다시 요청하지 않는다

### DSH-038 새 조건을 기다리는 동안 이전 숫자를 보이며 불러오는 중이고 링크를 막는다
- Given 요약이 보이는 Status 탭과 늦게 오는 다음 응답
- When Q3를 누르거나 연도를 바꾸거나 탭을 바꾼다
- Then 응답 전에는 이전 표가 그대로 보이고 "불러오는 중…"이 있으며 타일·표 링크가 없고 막대 클릭도 이동하지 않으며 빈 상태 문구가 깜빡이지 않고, 응답이 오면 링크가 돌아온다

### DSH-039 요약 조회가 실패하면 오류 배너를 보이고 필터는 계속 쓸 수 있다
- Given 요약 조회가 500 "서버 오류가 발생했습니다."(또는 501)로 실패한다
- When `/dashboard`를 열고 Q1을 누른다
- Then 오류 배너에 서버 문구가 보이고 "준비 중" 문구는 없으며, Q1을 누르면 URL과 조회 조건이 바뀐다

### DSH-040 안내 줄은 응답 기준일을 보이고 Deal이 없으면 두 탭 모두 빈 상태 문구다
- Given 응답 today 2027-01-01(앱 시계는 2026-12-31), 그리고 모든 값이 0인 응답
- When Status 탭과 Forecast 탭을 연다
- Then 안내 "기간은 Expected Close 기준이며 금액 단위는 원입니다. 기준일 2027-01-01"이 보이고, 0 응답이면 두 탭 모두 "조건에 맞는 Deal이 없습니다."와 0인 표가 보이며, Deal이 있으면 문구가 없다(Forecast 탭은 보이는 분기 행 기준)

### DSH-041 Forecast 타일은 Open 코드 순서·Open 합계·기간이 붙은 Won이고 Lost 타일이 없다
- Given 응답 Forecast 열에 추가 코드 Verbal과 이름을 바꾼 코드가 있고 `period.quarters`가 [1, 3]
- When Status 탭과 Forecast 탭을 연다
- Then 타일은 Open 코드 순서 → "Open 합계" → "Won (2026 Q1, Q3)"이고(분기가 없으면 "Won (2026)") Lost 타일은 없으며 Verbal 타일과 새 이름이 보이고 각 타일은 "N건"과 원 금액이다

### DSH-042 Status 표는 코드 순서 행·건수·원 금액·합계 행이고 0 행도 남는다
- Given Status 항목 값이 고정된 응답(일부 0, 이름을 바꾼 코드 포함)
- When Status 탭을 연다
- Then 표 "Status별 건수와 금액"의 열이 Status·건수·금액(단위:원), 행이 코드 순서이고 "N건"·원 콤마, 0인 Status도 행이 있으며 맨 아래 "합계"가 응답 합계와 행 합과 같다

### DSH-043 Status 막대 차트는 코드 순서 막대·"이름 (N건)" 라벨·원 금액 높이이고 Forecast 탭에는 없다
- Given Status 항목 값이 고정된 응답
- When Status 탭과 Forecast 탭을 연다
- Then Status 탭 차트는 막대가 코드 순서, 라벨 "기회발굴 (N건)", 값은 원 금액, 세로축 제목 "금액(단위:원)"·눈금 단축, 툴팁 원 콤마이고 접근성 이름이 있으며 Forecast 탭에는 이 차트가 없다

### DSH-044 주의 필요 Deal 타일은 기한초과·N일 미업데이트·이번 분기이고 응답 값을 보인다
- Given 응답 `attention`이 stale_days 7, overdue 2, stale 0, 이번 분기 2027 Q1·3건
- When Status 탭을 연다(분기 버튼을 눌러도 본다)
- Then 타일 "기한초과 2건", "7일 이상 미업데이트 0건", "이번 분기(2027 Q1) Expected Close 3건"이 보이고 분기를 눌러도 숫자·링크가 같으며 "이번 달" 타일은 없다

### DSH-045 분기 표는 Lost 없는 열·Open 합계·합계이고 고른 분기 행만, 없으면 4행이다
- Given 분기 행 값이 고정된 응답
- When Forecast 탭을 분기 없이, Q1·Q3, Q2, 넷 다로 연다
- Then 표 열은 분기·Forecast 열 이름(코드 순서, Lost 없음)·"Open 합계"·"합계", 칸은 "N건 · 원 금액", 행은 분기 없음·넷 다면 Q1~Q4, Q1·Q3면 그 두 행 오름차순, Q2면 한 행이고 Selected Quarter 영역과 행 강조가 없다

### DSH-046 분기 누적 막대는 보이는 분기 축과 Forecast 열 데이터셋이고 강조가 없다
- Given 분기 행 값과 추가 코드가 있는 응답
- When Forecast 탭을 분기 없이, Q1·Q3로 연다
- Then 가로축은 Q1~Q4(또는 Q1·Q3), 데이터셋은 Forecast 열마다 하나(코드 순서·코드 이름·각자 색), 값은 그 분기 원 금액, 두 축 누적이며 흐린 막대가 없다

### DSH-047 Closing Attention은 이번 달·이번 분기·미업데이트이고 기한초과가 없다
- Given 응답 `attention`이 이번 달 2026-10·2건, 이번 분기 2026 Q4·5건, stale_days 7·stale 1
- When Forecast 탭을 연다
- Then "이번 달(10월) Expected Close 2건", "이번 분기(2026 Q4) Expected Close 5건", "7일 이상 미업데이트 1건"이 보이고 "기한초과" 타일은 없다

### DSH-048 Drill-down 주소는 표의 조건과 고정 키 순서이고 정렬·페이지·outcome이 없다
- Given 범위 `{year: 2026, quarters: [1, 3], owner: 7, vendor: 3}`와 Forecast 열(Open 4개 + Won)
- When DSH-R25 표의 모든 주소를 만든다
- Then 각 주소는 표의 조건만 `year, quarter, month, owner, vendor, status, forecast, overdue, stale` 순서로 담고(예: Status POC완료 = `/deals?year=2026&quarter=1%2C3&owner=7&vendor=3&status=poc_completed&forecast=best%2Ccommit%2Cmost_likely%2Cpipeline%2Cwon`) `sort`·`order`·`page`·`outcome`이 없으며 Deal 목록이 같은 조건으로 다시 읽는다

### DSH-049 보낼 Forecast 집합이 비면 그 숫자는 링크가 아니다
- Given Forecast 열에 Open 코드가 없는 응답(그리고 Won만 있는 경우)
- When 화면을 연다
- Then "Open 합계"·이번 달·이번 분기 숫자는 링크 없이 글자로 보이고 Won만 있어도 Status 행·합계는 링크다

### DSH-050 숫자를 누르면 그 조건만의 Deals 목록이 열리고 필터 바와 목록 기억이 그 조건이다
- Given 목록 기억이 `status=prospecting&sort=owner&order=asc&page=3&q=old`이고 `/dashboard?year=2026&quarter=4&owner=<KIM>`
- When Pipeline 타일(또는 Status 표 "기회발굴" 링크, Open 합계)을 누르고 다른 화면을 거쳐 상단 메뉴 Deals를 누른다
- Then 주소는 `/deals?year=2026&forecast=pipeline` 같은 누른 조건뿐이고 필터 바에 같은 값(Status 기회발굴·Close 연도 2026·Quarter Q4·담당자 김영업)이 보이며 기억도 그 조건이라 메뉴 Deals가 같은 주소를 연다

### DSH-051 목록 총 건수가 누른 숫자와 같다
- Given Fake 시드 Deal과 admin이 추가한 Open 코드
- When Forecast 타일, Open 합계, Status 행·합계, 기한초과·미업데이트, 이번 분기·이번 달, 분기 합계·분기 Open 합계를 각각 누른다
- Then 각 Deals 목록의 "총 N건"이 누른 숫자와 같다

### DSH-052 여러 분기를 고른 Drill-down은 같은 분기 목록이고 분기 칸·주의 타일 주소는 고른 분기와 무관하다
- Given Status·Forecast 탭에서 Q1·Q3를 고른 상태
- When Forecast 타일·Open 합계·Status 행·합계, 분기 Q4 칸, 이번 분기·이번 달·기한초과 타일을 누른다
- Then 앞의 넷은 `quarter=1%2C3` 목록이고 건수가 같으며, 분기 칸은 그 분기 하나, 주의 타일 주소는 분기를 고르지 않았을 때와 같다

### DSH-053 뒤로 가기는 같은 탭·조건의 Dashboard이고 Dashboard를 보기만 하면 목록 기억이 바뀌지 않는다
- Given `/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C4`, 그리고 목록 기억이 없는 상태에서 `/dashboard?year=2026&quarter=2&owner=<PARK>`
- When 첫 화면에서 분기 칸을 눌러 목록으로 간 뒤 뒤로 가고, 둘째 화면에서는 아무것도 누르지 않고 상단 메뉴 Deals를 누른다
- Then 첫째는 같은 주소·Forecast 탭·Q3 눌림으로 돌아오고, 둘째는 목록 기억이 비어 있어 기본 Deals 목록 주소로 간다

### DSH-054 막대를 누르면 표 링크와 같은 곳으로 가고 빈 곳은 무시하며 표 링크는 키보드로 쓴다
- Given Status 탭과 Forecast 탭 차트
- When Status 막대(POC완료), 분기 막대 조각(추가 코드가 중간에 있는 경우 포함), 막대가 아닌 곳을 누르고, 표 링크에 Tab으로 가서 Enter를 누른다
- Then 막대는 같은 행·칸의 표 링크와 같은 주소로 가고(분기 조각은 고른 분기가 아니라 그 분기 하나·담당자·Vendor 유지), 빈 곳은 이동하지 않으며, 막대 위에서만 손가락 커서이고, Tab으로 모든 행 링크·합계 링크에 닿아 Enter로 이동한다

### DSH-055 Deal 변경·경고 기준 저장 뒤 요약을 다시 읽는다
- Given 요약을 읽은 상태
- When Deal의 Forecast를 바꾸고(또는 경고 기준을 저장하고) 다시 본다
- Then 셀 숫자(또는 `stale_days`)가 새 값이고, 조회가 실패하면 재시도 없이 `ApiError`이며 조건이 바뀌는 동안 이전 요약을 유지한다

### DSH-056 게이트웨이는 조건을 서버 쿼리로, 응답을 화면 모양으로 바꾼다
- Given HTTP 게이트웨이와 가짜 서버 응답
- When 연도만, 분기 2개·담당자·Vendor를 넣어, 빈 분기 목록으로 조회하고 응답(cells 목록 일부 누락, `period.quarters` [0]·[5]·[1, 7], 422·401 오류 포함)을 받는다
- Then 쿼리는 `year`만 / `quarter` 반복·`owner_user_id`·`vendor_id` 정수 / 분기 키 없음이고 월은 없으며, 응답은 camelCase·key별 Record(빠진 셀 0)·Q1~Q4 행·attention으로 바뀌고 분기 값이 1~4 밖이면 형식 오류, 422·401은 `ApiError`다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 최초 작성(구현된 동작을 정본으로 옮김, 초안) | DSH-001~DSH-056 |
| 2026-11-11 | 사용자 결정 반영(추천대로): F1 Fake를 서버 동작에 맞춤(DSH-R29 신설: 범위 밖 연도·분기 422 `request-validation`), F2 Dashboard 연도에 '전체' 없음(DSH-R16, DL-R24 문구 정리), F4 FC 이름 참조를 FC 규칙 번호로(FC 범위 FC-R1~R35, 합계 행 FC-R4~R6, 조건 FC-R3, 집계 FC-R5)와 다른 문서 참조를 번호로(CL-R3·R7~R10, DE-R4, CD-R1·R5, AC-R2, RK-R1·R2), F5 운영 코드 주석 "슬라이드 7·9"는 그대로 | 없음(케이스 기대 결과 변경 없음) |
| 2026-11-16 | 확정(2026-11-16 사용자 확인): DL 변경(Deal 목록 연도 선택 상자 이름 "Close 연도", DL-R24)에 따라 DSH-050 Then의 Deals 필터 바 표기를 고침. Dashboard 화면의 "연도" 라벨·동작은 그대로 | 변경: DSH-050 |
