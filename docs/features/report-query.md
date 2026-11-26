# Reports 조회 엔진·디자이너 작성   (feature 코드: RQ, 상태: 확정(2026-11-18 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`backend/src/app/domain/report/{vocabulary,fields,catalog,catalog_deal,catalog_action,labels,raw,parse,parse_columns,parse_conditions,condition_values,definition,errors,resolve,stored}.py`, `app/application/report/{list_fields,run_report,execution,views}.py`, `app/application/ports/report_query_runner.py`, `app/infra/db/{report_runner,report_select,report_grouped,report_parts,report_conditions,report_buckets,report_fields,report_fields_deal,report_fields_action,report_risk,report_render,read_only}.py`, `app/web/routers/reports.py`, `app/web/schemas/{report_fields,report_query}.py`, `app/web/error_handlers.py`의 Reports 처리, `frontend/src/features/reports/designer/**`(편집 화면 전용 부분 제외), `features/reports/result/{ResultPanel,TableTile}.tsx`의 표·SQL 부분, `data/reports.ts`의 카탈로그·조회 훅, `gateway/http/reports.ts`·`mappers/report.ts`의 카탈로그·조회, `test/fake/gateway/reports.ts`, `test/fake/seed/reportCatalog.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·안내서가 어긋나던 점은 2026-11-11 사용자 결정으로 정리했습니다: 조회 Fake 게이트웨이는 서버 동작에 맞추되 흉내 내는 위반의 범위는 넓히지 않고(RQ-R56), 금액 건수 집계 열의 `unit` `krw`는 현행대로 두며(RQ-R36), 저장 정의 JSON의 예전 형식 읽기 변환은 이 문서가 가집니다(RQ-R57). 안내서(`docs/user-guide.html` 15.7) 문구는 코드에 맞춥니다. 결정 목록은 계획(`artifacts/10-analysis/rq-plan.md`)에 있습니다. 저장 리포트(RS)·차트(RC)·공통 입력(UI)은 규칙 번호로 가리킵니다.
>
> 2026-11-16 변경(초안, 사용자 확인 대기): Deal의 Solution을 Product로 이름 변경(화면 문구, API 필드·쿼리 `product`, Reports key `deal.product`, DB 컬럼 `deals.product`). 영향 규칙·케이스는 5장.
>
> 2026-11-18 변경(확정, 2026-11-18 사용자 확인): 바뀐 설계에서 브라우저 뒤로·앞으로 가기도 떠날 때 확인을 묻는다(RQ-R54, RQ-UC5, RQ-125~RQ-127). 프런트 전용, API·마이그레이션 변경 없음.

## 1. 개요

- 목적: 로그인한 모든 사용자가 서버가 정한 필드 목록(화이트리스트)에서 컬럼·조건을 골라 Deal·Deal Action 데이터를 표로 조회한다. SQL은 서버만 만들고(사용자 SQL 입력 없음) 읽기 전용·시간 제한 안에서 실행하며, 결과 숫자는 Deals 목록과 같다.
- 사용자(역할): admin·sales·user 모두 같은 화면·같은 데이터(모든 Deal 대상). 조회는 아무것도 저장하지 않는다.
- 범위
  - API `GET /reports/fields`(필드 카탈로그·한도·어휘), `POST /reports/query`(정의 검증 → SQL 생성 → 읽기 전용 실행 → 결과·합계·표시 SQL)
  - 정의 검증 규칙(컬럼·포맷·앞 N자·그룹핑·집계·컬럼 정렬·조건·연산자·값·결합·행 수), 상대 기간 해석, 행 범위(Deal/Action), Deal당 한 번 집계, 합계 행, 정렬, 행 수 제한, 시간 제한, 표시 SQL
  - 화면 `/reports/new`의 디자이너: 제목 줄(초기화), 작성/결과 탭, 작성 탭(필드 목록·데이터 범위 표시·컬럼 칩·컬럼 설정·조건·최대 행·조회·조회 실패 알림), 결과 탭의 표 타일(총 행·조회 시간·합계 행·결과 표·페이지)과 다시 조회 안내·생성 SQL 보기, 떠날 때 확인
  - 프런트 게이트웨이의 카탈로그·조회 변환, 데이터 훅(`useReportFields`·`useRunReport`·`reportRunFailure`), 조회 Fake 게이트웨이
  - 저장 리포트 정의 JSON의 모양·읽을 수 있는지 판정·예전 형식 읽기 변환(`domain/report/stored.py`의 `definition_to_json`·`definition_from_json`, RQ-R57, 2026-11-11 결정). 읽을 수 없는 정의일 때 API 응답(`stored-invalid` 422)은 RS-R17
- 범위 밖(다른 feature)
  - 저장·목록·보기·편집 화면(RS-R27~RS-R35), `/reports`·`/reports/{id}`·`/copy`·`/run`·`/layout`(RS-R10~RS-R18, RS-R22), 저장 버튼 활성 조건·저장 대화상자(RS-R30, RS-R31), 결과 보기 방식·타일 배치(RS-R19~RS-R23, RS-R37~RS-R43), 깨진 저장 정의의 API 응답(`stored-invalid`, RS-R17), 편집 화면의 불러오기·되돌리기·저장 안 됨 판정(RS-R32~RS-R34) → RS. 저장 리포트 실행도 이 문서의 실행 규칙(RQ-R20~RQ-R36)을 쓴다
  - 차트 타일·차트 설정(RC-R24~RC-R36)·`chart` 검증(RC-R3~RC-R17), 차트 위반의 결과 탭 표시(RC-R33) → RC
  - 날짜 입력(`DateInput`)·금액 입력(`AmountInput`)·다중 선택(`MultiCheckSelect`)·확인 대화상자·페이저 자체의 입력·표시 규칙 → UI(날짜 입력 UI-R1~R11, 금액 입력 UI-R12~R16, 다중 선택 UI-R22~R24, 확인 대화상자 UI-R29, 페이저 UI-R30)
  - 경고·체류 일수·최종 업데이트 판정식 → RK(RK-R3~RK-R7, RK-R10). Reports는 같은 판정을 쓴다
  - Deal 목록 조건 해석(원장 비교 대상) → DL(DL-R1, DL-R6, DL-R9, DL-R12, DL-R15)
  - 업무 날짜·업무일 시작·개월 이동·응답 시각 오프셋·앱 시계·시각 표기 → TM(TM-R4, TM-R5, TM-R6, TM-R8, TM-R12, TM-R14)
  - 공통 권한 분류·판정 순서·CSRF·Problem 형식·화면 가드·오류 문구·게이트웨이 오류 → PL(PL-R2, PL-R4, PL-R5, PL-R9, PL-R12, PL-R33, PL-R37, PL-R39)
  - 사용자 표시 이름·퇴사 표기 → US(US-R12), Status·Forecast 코드 순서·이름 → CD(CD-R5), BANT Label·Action 유형·Vendor 목록 → CL(CL-R3), Next Action 상태 라벨 → NA(NA-R1)
- 관련 화면·메뉴: 상단 메뉴 "Reports"(PL-R34), `/reports/new`는 RequireAuth(PL-R33, 모든 역할). `/reports` 목록의 "+ 새 리포트"는 RS-R27.
- 참고 문서: `docs/user-guide.html` 15.3~15.7·15.10, `docs/dev-guide.html` 10.6(SQL 생성 원칙과 허용 필드 추가).

## 2. 명세 (SDD)

### Comments 엔티티

- 디자이너의 필드 선택 목록은 Deal, Deal Actions, Comments로 구성한다. Comments의 본문, 작성일자, 수정일자, 작성자를 컬럼과 조건에 사용할 수 있다. 날짜 필드는 저장된 시각을 사용하며 기본 포맷은 `ymd_hm`이다. 작성자는 사용자 표시 이름으로 표시하고 조건에서는 사용자 ID를 사용한다.
- Comments 필드를 컬럼이나 조건에 사용하면 댓글 하나가 결과 한 행이다. Action 필드를 쓰지 않으면 Deal에 직접 작성한 댓글과 그 Deal의 모든 Action 댓글을 포함한다. Action 필드를 컬럼이나 조건에 쓰면 해당 Action에 연결된 댓글만 포함한다. 댓글 없는 Deal이나 Action은 댓글 행을 만들지 않는다.
- 그룹과 전체 합계에서 Deal 및 Action 집계는 댓글 수에 따라 중복되지 않는다. 댓글 본문의 건수는 댓글 행을 센다.
- 예전 저장 리포트의 `deal.comment`와 `action.comment`는 기존 문자열 결합 방식으로 계속 동작한다. 새 필드를 추가하는 선택 목록에서는 숨긴다.

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 카탈로그 | 리포트에 쓸 수 있는 필드 45개(Deal 29 + Deal Actions 12 + Comments 4)와 한도·어휘. 여기 없는 key는 어떤 경로로도 SQL에 닿지 않는다 |
| 정의 | 조회 요청 하나: `columns`(컬럼 목록), `conditions`(조건 목록), `combine`(and/or), `row_limit` |
| 컬럼 | 필드 + 표시 이름·포맷·앞 N자·그룹핑·집계·정렬 |
| 그룹핑 리포트 | 그룹 컬럼(`group: true`)이 하나라도 있는 정의. 나머지 컬럼은 모두 집계가 된다 |
| 행 범위(row_scope) | 결과 한 행의 단위: `deal`(Deal 1건) 또는 `action`(Action 1건) |
| Action 조건 방식(action_filter) | `none`(Action 필드 없음) / `exists`(조건에만, Deal마다 EXISTS) / `join`(컬럼에 있음, Action과 JOIN) |
| Deal 숫자 | Deal 단위 숫자 필드(`deal.amount`·`deal.users`·`deal.status_days`, 카탈로그 `deal_number: true`) |
| Deal당 한 번 | Action 행 범위의 그룹핑에서 Deal 필드의 합계·평균·건수를 그룹마다 Deal 하나당 한 번만 세는 규칙 |
| 합계 행(totals) | 같은 조건의 전체 범위를 그룹 없이 한 번 더 집계한 한 행 |
| 묶음 포맷 | SQL의 묶음 단위를 바꾸는 날짜 포맷(`ymd`·`year`·`quarter`·`month`, `affects_query: true`). 나머지 포맷은 표시 전용 |
| 위반(issue) | 정의 규칙 위반 하나: `{location, code, message}` |
| 표시 SQL | 사람이 읽도록 입력 값을 리터럴로 넣은 SQL 문자열(실행에는 쓰지 않음) |
| 설계 | 디자이너 화면의 현재 상태(컬럼·조건·결합·최대 행, 저장 전에는 이 화면에만 있음) |

### 2.2 데이터 모델

새 테이블 없음(마이그레이션 없음). 읽는 테이블: `deals`·`deal_actions`·`deal_comments`·`users`·`contacts`·`deal_partners`·`vendors`·`codes`·`bant_labels`·`deal_bant`·`action_types`·`alert_settings`(경고 기준).

카탈로그 필드(이 순서, 응답 `fields` 순서와 같다)

| # | key | 이름 | 형식 | 비고 |
| --- | --- | --- | --- | --- |
| 1 | `deal.code` | Deal code | text | |
| 2 | `deal.name` | Deal 이름 | text | |
| 3 | `deal.product` | Product | text | |
| 4 | `deal.procurement` | 구매절차 | text | |
| 5 | `deal.owner` | 담당자 | user | 값 id, 출처 `users` |
| 6 | `deal.customer_company` | 고객사 | text | 연결된 고객 연락처의 회사 |
| 7 | `deal.customer_contact` | 고객 담당자 | text | 연결된 고객 연락처의 이름 |
| 8 | `deal.partner_company` | 파트너사(현재) | text | 활성 파트너 연결의 회사 |
| 9 | `deal.vendor` | Vendor | code | 값 id, 출처 `vendors` |
| 10 | `deal.status` | Status | code | 값 key, 출처 `status_codes` |
| 11 | `deal.forecast` | Forecast | code | 값 key, 출처 `forecast_codes` |
| 12 | `deal.forecast_outcome` | Forecast 구분 | code | 정적: open/Open, won/Won, lost/Lost |
| 13 | `deal.quote_submitted` | 견적 제출 | code | 정적: YES/YES, NO/NO |
| 14 | `deal.poc_state` | POC 상태 | code | 정적: YES, ING, NO |
| 15~18 | `deal.bant_budget`·`deal.bant_authority`·`deal.bant_need`·`deal.bant_timeline` | BANT Budget·BANT Authority·BANT Need·BANT Timeline | code | 값 id, 출처 `bant_labels`, `options_category` = budget·authority·need·timeline |
| 19 | `deal.risk` | 경고 | code | 정적: overdue/기한초과, stale/미업데이트 |
| 20 | `deal.amount` | 금액 | number | `unit: krw`, 기본 집계 합계, Deal 숫자 |
| 21 | `deal.users` | Users count | number | 기본 집계 합계, Deal 숫자 |
| 22 | `deal.status_days` | Status 체류 일수 | number | 기본 집계 평균, Deal 숫자 |
| 23 | `deal.expected_close` | Expected Close | date | |
| 24 | `deal.quote_submitted_date` | 견적 제출일 | date | |
| 25 | `deal.poc_completed_date` | POC 완료일 | date | |
| 26 | `deal.created_at` | 등록일 | datetime | |
| 27 | `deal.last_updated_at` | 최종 업데이트 | date | RK-R2의 `last_updated_on`(key 유지, RQ-R58) |
| 28 | `deal.status_changed_at` | Status 진입일 | date | `status_changed_on`(key 유지, RQ-R58) |
| 29 | `deal.comment` | Comment(Deal 전체) | text | 그 Deal 소속 Comment 전부(Deal Comment와 Action Comment 모두)를 작성 순(created_at·id 오름차순)으로 줄바꿈("\n")으로 이은 값. 없으면 null. Deal 필드(RQ-R61) |
| 30 | `action.action` | 진행사항 | text | |
| 31 | `action.next_action` | Next Action | text | |
| 32 | `action.comment` | Comment(Action) | text | 그 Action에 연결된 Action Comment만 작성 순으로 줄바꿈으로 이은 값. 없으면 null(RQ-R60) |
| 33 | `action.actor` | 수행자 | user | 값 id, 출처 `users` |
| 34 | `action.type` | Action 유형 | code | 값 id, 출처 `action_types` |
| 35 | `action.next_action_status` | Next Action 상태 | code | 정적: Next Action 상태 3개와 그 라벨(NA-R1) |
| 36 | `action.status` | 당시 Status | code | 값 key, 출처 `status_codes`. Action 등록 요청 시점 값(수행일 당시 아님, AC-R37) |
| 37 | `action.forecast` | 당시 Forecast | code | 값 key, 출처 `forecast_codes`. 등록 요청 시점 값(AC-R37) |
| 38 | `action.due_date` | Due Date | date | |
| 39 | `action.acted_at` | 수행일 | date | Action `acted_on`(key 유지, RQ-R58) |
| 40 | `action.closed_at` | 종료일 | date | Next Action 종료일 `next_action_closed_on`(key 유지, RQ-R58) |
| 41 | `action.count` | Action 건수 | number | 가상 필드: 그룹핑 전용, 조건 불가, 집계 건수 고정 |
| 42 | `comment.body` | Comment 본문 | text | 개별 Comment 본문 |
| 43 | `comment.created_at` | 작성일자 | datetime | Comment 작성 시각 |
| 44 | `comment.updated_at` | 수정일자 | datetime | Comment 수정 시각 |
| 45 | `comment.author` | 작성자 | user | Comment 작성자이며 조건 값은 사용자 ID |

형식별 허용표(카탈로그 각 필드의 `formats`·`operators`·`aggregates`·기본값)

| 형식 | 포맷(첫째가 기본) | 연산자 | 집계(그룹핑할 때) |
| --- | --- | --- | --- |
| text | 없음(기본 null) | contains, equals, starts_with, is_empty, is_not_empty | count, count_distinct |
| code, user | 없음 | in, not_in, is_empty | count, count_distinct |
| number | 없음 | eq, ne, gt, gte, lt, lte, between | sum, avg, min, max |
| date | ymd, year, quarter, month, weekday, relative | between, before, after, relative | count, count_distinct |
| datetime | ymd_hm, ymd, year, quarter, month, weekday, relative | between, before, after, relative | count, count_distinct |

원시 정의(웹 → 도메인): `RawReportDefinition{columns: RawColumn[], conditions: RawCondition[] = [], combine = "and", row_limit = 1000}`, `RawColumn{field, label?, format?, prefix_length?, group = false, aggregate?, sort?}`, `RawCondition{field, operator, value?}`. 검증을 통과하면 `ReportDefinition`(컬럼은 `FieldSpec`·적용된 포맷·집계를 가진다)이 되고, 실행 직전 날짜 조건이 절대 범위로 풀린 `ResolvedReport`(+ `ReportContext{today, utc_offset, risk}`)가 Port `ReportQueryRunner.run`에 넘어간다.

### 2.3 비즈니스 규칙

카탈로그 (`GET /reports/fields`)
- **RQ-R1** `GET /reports/fields`와 `POST /reports/query`는 로그인한 모든 역할이 부른다(업무 조회, PL-R2). `POST /reports/query`는 POST지만 저장·변경이 없어 역할 가드가 없고 `user`도 실행한다. 미인증은 401 `unauthenticated`(PL-R5), `POST`는 CSRF 헤더가 없으면 403 `csrf`(PL-R9, 판정 순서 PL-R4). 두 경로 모두 아무것도 저장하지 않는다. 모든 역할이 모든 Deal을 대상으로 같은 결과를 받는다.
- **RQ-R2** 카탈로그 응답은 정확히 `{limits, entities, formats, operators, aggregates, relative_periods, fields}`다. `fields`는 2.2 표의 45개를 `deal.*` 29개, `action.*` 12개, `comment.*` 4개 순으로 담는다. 각 항목은 `{key, label, entity, type, formats, default_format, unit, operators, aggregates, default_aggregate, groupable, filterable, requires_grouping, deal_number, value_kind, options, options_source, options_category}`다. 필드 키의 접두어는 `entity`와 같다. `entities`는 Deal, Deal Actions, Comments 순이다.
- **RQ-R3** 각 필드의 `formats`·`default_format`·`operators`·`aggregates`는 2.2 형식별 허용표대로다. text·code·user·number는 `formats: []`, `default_format: null`이다. 숫자 필드는 `default_aggregate`가 있고(금액·Users count 합계, Status 체류 일수 평균) `deal_number: true`이며, 그 밖의 필드는 `default_aggregate: null`·`deal_number: false`다.
- **RQ-R4** `unit`이 있는 필드는 `deal.amount`(`"krw"`, 원 단위) 하나뿐이다. `action.count`는 `operators: []`·`aggregates: []`·`default_aggregate: "count"`·`groupable: false`·`filterable: false`·`requires_grouping: true`·`deal_number: false`이며, `requires_grouping: true`인 필드는 이것 하나다. 그 밖의 필드는 모두 `groupable: true`·`filterable: true`다.
- **RQ-R5** code·user 필드의 조건 값: 정적 선택지 필드(Forecast 구분·견적 제출·POC 상태·경고·Next Action 상태)는 `value_kind: "key"`와 `options: [{value, label}]`(2.2 표 순서)를 갖고 `options_source: null`이다. 경고의 선택지는 overdue·stale 둘뿐이다(결과 값의 "기한초과·미업데이트"는 선택지가 아니다). 출처 필드는 `options: null`과 `options_source`(`users`·`vendors`·`status_codes`·`forecast_codes`·`bant_labels`·`action_types`)를 갖고, `value_kind`는 담당자·수행자·Vendor·BANT·Action 유형이 `"id"`, Status·Forecast(당시 포함)가 `"key"`다. BANT 필드는 `options_category`(budget·authority·need·timeline)를 갖고 그 밖은 null이다.
- **RQ-R6** `limits` = `{columns_min: 1, columns_max: 30, conditions_max: 20, row_limits: [100, 1000, 10000], default_row_limit: 1000, statement_timeout_seconds: 10, text_value_max: 200, list_value_max: 100, last_n_days_max: 3650, label_max: 100, prefix_max: 200}`. 어휘(모두 이 순서):
  - `formats`: `[{key, label, affects_query}]` = ymd "연-월-일"(true), ymd_hm "연-월-일 시:분"(false), year "연도"(true), quarter "분기"(true), month "월"(true), weekday "요일"(false), relative "상대 시각"(false). 예전 포맷(as_is·prefix·name·key·thousands·krw_thousand·krw_million·decimal1·percent_share)은 없다.
  - `operators`: `[{key, label, value}]` = contains "포함"(text), equals "같음"(text), starts_with "시작"(text), is_empty "비어 있음"(none), is_not_empty "비어 있지 않음"(none), in "다음 중 하나"(list), not_in "다음이 아님"(list), eq "="·ne "≠"·gt ">"·gte "≥"·lt "<"·lte "≤"(number), between "범위"(range — 날짜·시각 필드는 날짜 범위로 해석), before "이전"(date), after "이후"(date), relative "상대 기간"(relative).
  - `aggregates`: sum "합계", avg "평균", min "최소", max "최대", count "건수", count_distinct "고유 건수".
  - `relative_periods`: `[{key, label, needs_days}]` = last_1_month "최근 1개월", last_3_months "최근 3개월", last_6_months "최근 6개월", this_year "올해", this_quarter "이번 분기", this_month "이번 달", last_n_days "최근 N일"(needs_days true), before_today "오늘 이전". `needs_days`는 last_n_days만 true다.

정의 검증 (`POST /reports/query`)
- **RQ-R7** 요청 모양: 본문은 `columns`(필수, 객체 목록), `conditions`(선택, 기본 `[]`), `combine`(선택, 기본 `"and"`), `row_limit`(선택, 기본 1000) 네 키뿐이다. 컬럼 키는 `field`(필수 문자열)·`label`·`format`·`aggregate`·`sort`(문자열 또는 null)·`group`(boolean, 기본 false)·`prefix_length`(아무 JSON 값), 조건 키는 `field`·`operator`(필수 문자열)·`value`(아무 JSON 값)뿐이다. 모르는 키(예전 최상위 `sort` — 값이 null이어도, 최상위 `group` 포함), 필수 키 누락, 문자열·boolean 자리에 다른 형식(예: 컬럼 `sort: 1`·`true`·`{}`)은 422 `request-validation`(PL-R12)이다. `combine`·`row_limit`·`prefix_length`·조건 `value`의 값과 문자열 값의 허용 여부는 아래 규칙으로 판정해 422 `invalid-report`로 알린다.
- **RQ-R8** 정의 위반은 처음에 멈추지 않고 모두 모아 422 `invalid-report`로 알린다: `errors` = `[{location, code, message}]`(location은 `["columns", i, 항목]`처럼 문자열·정수 목록), `detail` = 첫 위반의 `message`. 순서는 컬럼(index 순, 한 컬럼 안에서는 field → label → format → prefix_length → group·aggregate → sort) → 조건(index 순) → combine → row_limit. 위반이 있으면 DB를 열지 않고 조회하지 않는다. 모든 `message`는 한국어 문장이다.
- **RQ-R9** 필드 key는 카탈로그 key와 정확히 같을 때만 허용한다(대소문자·앞뒤 공백 구분). 아니면 `["columns", i, "field"]`(조건은 `["conditions", i, "field"]`) `unknown-field` "허용되지 않은 필드입니다: <key 앞 50자>"이고 그 컬럼·조건의 나머지 항목은 검사하지 않는다.
- **RQ-R10** 컬럼 수는 1~30개다. 벗어나면 `["columns"]` `columns-count` "컬럼은 1개 이상 30개 이하로 지정하세요"이고 개별 컬럼은 검사하지 않는다.
- **RQ-R11** 표시 이름(`label`): 생략·null이면 필드 이름이다. 값이 있으면 앞뒤 공백을 지운 1~100자여야 한다. 빈 값·공백뿐·NUL 포함·100자 초과는 `["columns", i, "label"]` `label-invalid` "표시 이름은 공백이 아닌 100자 이하여야 합니다". 정확히 100자는 허용한다.
- **RQ-R12** 포맷(`format`): 생략·null이면 필드 기본 포맷(date `ymd`, datetime `ymd_hm`, 그 밖 없음)이다. 값이 있으면 그 필드 `formats` 안의 값이어야 한다. 포맷이 없는 필드에 값을 주면 `["columns", i, "format"]` `format-not-allowed` "이 필드는 포맷을 고를 수 없습니다", 포맷이 있는 필드에 목록 밖 값을 주면 같은 위치·code의 "이 필드에 쓸 수 없는 포맷입니다. 가능: <포맷 key를 ", "로 이음>"이다. 예전 포맷(RQ-R6 목록)도 이 위반이다(요청에서는 변환하지 않는다 — 저장 정의 읽기 변환은 RQ-R57).
- **RQ-R13** 앞 N자(`prefix_length`): 모든 컬럼(형식·그룹·집계 무관)에서 null(생략) 또는 1~200의 정수(boolean·소수·문자열 제외)다. 아니면 `["columns", i, "prefix_length"]` `value-invalid` "앞 N자의 N은 1~200의 정수여야 합니다". 앞 N자는 표시 전용이라 SQL·그룹핑·정렬·조건에 영향이 없다(그룹은 전체 값 기준).
- **RQ-R14** 그룹핑·집계(그룹핑 리포트 여부는 `group: true` 컬럼이 하나라도 있는지로 정한다)
  - 그룹 컬럼: `groupable: false` 필드면 `["columns", i, "group"]` `group-not-allowed` "이 필드는 그룹핑할 수 없습니다", 집계를 주면 `["columns", i, "aggregate"]` `aggregate-not-allowed` "그룹 컬럼에는 집계를 지정할 수 없습니다". 그룹 컬럼의 집계는 null이다.
  - 그룹핑이 없는 리포트: `requires_grouping` 필드(Action 건수)는 `["columns", i]` `grouping-required` "이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요", 집계를 주면 `["columns", i, "aggregate"]` `aggregate-not-allowed` "그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요". 집계는 null이다.
  - 그룹핑 리포트의 비그룹 컬럼: 집계를 생략하면 기본 집계(금액·Users count 합계, Status 체류 일수 평균, Action 건수 건수)이고, 기본 집계가 없는 필드(text·code·user·date·datetime)는 `["columns", i, "aggregate"]` `aggregate-required` "그룹핑할 때 이 컬럼은 집계(<허용 집계 이름을 " 또는 "로 이음>)를 골라야 합니다. 그룹핑하거나 빼세요"다. 집계를 주면 허용 집계(2.2 표, Action 건수는 건수 하나) 안의 값이어야 하고 아니면(모르는 이름 포함) 같은 위치 `aggregate-not-allowed` "그룹핑할 때 이 컬럼은 <허용 집계 이름을 " 또는 "로 이음>만 고를 수 있습니다. 그룹핑하거나 빼세요"다. 예: 텍스트 → "건수 또는 고유 건수", 숫자 → "합계 또는 평균 또는 최소 또는 최대".
- **RQ-R15** 컬럼 정렬(`sort`): null(생략) = 정렬 안 함, `"asc"`·`"desc"`만 허용한다(대소문자 구분). 아니면 `["columns", i, "sort"]` `sort-invalid` "정렬은 asc 또는 desc만 쓸 수 있습니다"이고 틀린 컬럼마다 하나씩 알린다. 그룹 컬럼·집계 컬럼도 정렬할 수 있다. 정렬한 컬럼들은 컬럼 순서(왼쪽 먼저)가 우선순위다.
- **RQ-R16** 조건: 개수는 20개까지이고 넘으면 `["conditions"]` `conditions-count` "조건은 20개까지 지정할 수 있습니다"(개별 조건은 검사하지 않음). 필드는 RQ-R9, `filterable: false`(Action 건수)는 `["conditions", i, "field"]` `not-filterable` "이 필드는 조건에 쓸 수 없습니다". 연산자는 그 필드 `operators` 안의 값이어야 하고 아니면 `["conditions", i, "operator"]` `operator-not-allowed` "이 필드에 쓸 수 없는 연산자입니다. 가능: <연산자 key를 ", "로 이음>"이다. 앞 단계에서 걸리면 뒤 단계(연산자·값)는 검사하지 않는다.
- **RQ-R17** 조건 값의 모양(연산자별, 위반은 `["conditions", i, "value"]` `value-invalid`와 아래 문구)
  - is_empty·is_not_empty: 값이 null(생략)이어야 한다 — "이 연산자에는 값이 필요하지 않습니다".
  - contains·equals·starts_with: 문자열(NUL 없음) — 아니면 "검색어를 문자열로 입력하세요". 앞뒤 공백을 지운 1~200자 — 아니면 "검색어는 공백이 아닌 200자 이하여야 합니다". 다듬은 값으로 비교한다.
  - in·not_in: 1~100개 목록 — 아니면 "선택 값은 1개 이상 100개 이하의 목록이어야 합니다". 값 종류 id면 항목이 1~2^53−1 정수(boolean 제외) — 아니면 "선택 값은 양의 정수 id여야 합니다", key면 1~200자의 NUL 없는 문자열 — 아니면 "선택 값은 비어 있지 않은 문자열이어야 합니다".
  - eq·ne·gt·gte·lt·lte(숫자): 절댓값 2^53−1 이하 정수(boolean·소수·문자열 제외) — 아니면 "정수(절댓값 9007199254740991 이하)를 입력하세요".
  - between: 두 값 목록 — 아니면 "범위는 시작과 끝 두 값이 필요합니다". 숫자 필드는 각 값이 위 정수이고 시작 ≤ 끝 — 아니면 "범위의 시작이 끝보다 클 수 없습니다". 날짜·시각 필드는 각 값이 아래 날짜이고 시작 ≤ 끝 — 아니면 "범위의 시작이 끝보다 늦을 수 없습니다".
  - before·after와 날짜 범위의 값: `YYYY-MM-DD` 문자열 — 아니면 "날짜는 YYYY-MM-DD 형식으로 입력하세요", 실제 날짜 — 아니면 "존재하지 않는 날짜입니다", 1900-01-01~2999-12-31 — 아니면 "날짜는 1900-01-01부터 2999-12-31 사이여야 합니다".
  - relative: 키가 `period`(와 `days`)뿐인 객체 — 아니면 "상대 기간은 period(와 days)를 가진 객체여야 합니다", `period`가 RQ-R6의 8개 중 하나 — 아니면 "알 수 없는 상대 기간입니다", last_n_days가 아닌데 `days`가 있으면 "days는 최근 N일에서만 쓸 수 있습니다", last_n_days의 `days`는 1~3650 정수 — 아니면 "최근 N일의 N은 1~3650의 정수여야 합니다".
- **RQ-R18** 정적 선택지가 있는 필드(RQ-R5)의 in·not_in 값은 그 선택지 key 안이어야 한다. 아니면 `value-invalid` "선택지에 없는 값입니다. 가능: <선택지 key를 ", "로 이음>"이다(경고에 `overdue_stale`을 주면 거절). 출처 필드(Status·Forecast key, id 목록)는 값의 존재를 검사하지 않고 없는 값은 맞는 행이 없을 뿐이다.
- **RQ-R19** 결합(`combine`)은 정확히 `"and"`·`"or"` — 아니면 `["combine"]` `combine-invalid` "조건 결합은 and 또는 or만 쓸 수 있습니다". 행 수 제한(`row_limit`)은 정수 100·1000·10000 중 하나(문자열 "1000"·boolean 제외) — 아니면 `["row_limit"]` `row-limit-invalid` "행 수 제한은 100, 1000, 10000 중 하나여야 합니다". 생략하면 `"and"`·1000이다. 한 정의 안에서 AND와 OR를 섞거나 괄호로 묶을 수 없다.

실행 (`POST /reports/query`)
- **RQ-R20** 행 범위: Action 필드(`action.count` 포함)가 컬럼에 하나라도 있으면 `row_scope: "action"`·`action_filter: "join"` — 결과 한 행은 Action 1건이고 Deal 값은 그 Deal의 Action마다 반복되며 Action이 없는 Deal은 빠진다. Action 필드가 조건에만 있으면 `row_scope: "deal"`·`action_filter: "exists"`. Action 필드가 없으면 `"deal"`·`"none"`. 조건이 없으면 모든 Deal(Action 행이면 모든 Action)이 대상이다.
- **RQ-R21** `exists`일 때 Action 조건은 모두 EXISTS 하나에 묶는다: AND면 **같은 Action 하나**가 모든 Action 조건을 만족해야 하고, OR이면 Action 조건끼리 OR이다. 그 EXISTS를 Deal 조건과 `combine`으로 묶는다(AND면 Deal 조건 AND EXISTS, OR이면 Deal 조건 OR EXISTS). 행은 Deal마다 한 번이다. `join`일 때 Action 조건은 각 Action 행에 바로 적용한다.
- **RQ-R22** 연산자의 뜻
  - contains·starts_with: 대소문자 무시 부분·앞부분 일치이고 `%`·`_`·`\`는 글자 그대로 찾는다. equals: 대소문자 무시 전체 일치.
  - is_empty: 텍스트는 NULL 또는 빈 문자열, code·user는 NULL. is_not_empty: 텍스트가 NULL도 빈 문자열도 아님.
  - in: 값 중 하나. not_in: 값 중 어느 것도 아니거나 **값이 없는(NULL) 행**.
  - 숫자 비교·between(양끝 포함)은 2^31을 넘는 값도 비교한다.
  - 날짜 필드: between은 양끝 포함, before d는 d 전날까지, after d는 d 다음 날부터.
  - 시각 필드: 같은 날짜 범위를 업무일 경계의 반열린 구간 `[start_of_business_day(첫날), start_of_business_day(끝날+1일))`로 비교한다(TM-R5).
  - SQL처럼 보이는 값은 글자 그대로 비교하며 데이터는 바뀌지 않는다(RQ-R34).
- **RQ-R23** 상대 기간은 **조회할 때마다** 서버 업무 날짜(오늘, TM-R4)로 다시 풀린다: last_1_month·last_3_months·last_6_months = `months_before(오늘, 1·3·6)`(TM-R6) ~ 오늘, this_year = 올해 1-1~12-31, this_quarter = 이번 분기 첫날~마지막 날, this_month = 이번 달 1일~말일, last_n_days(N) = 오늘−(N−1)일 ~ 오늘, before_today = ~어제(시작 없음). 양끝 포함이고, 시각 필드는 RQ-R22의 반열린 구간이 된다. 저장한 리포트도 실행할 때 다시 푼다.
- **RQ-R24** 경고(`deal.risk`) 조건은 Deals 목록 경고 필터(DL-R12)와 같은 판정(RK-R3~RK-R7, 경고 기준 `stale_days`는 조회 시점 설정, 없으면 기본값)이다. `in [overdue]`는 기한초과, `in [stale]`은 미업데이트, `in [overdue, stale]`은 둘 중 하나, `not_in`은 `in`의 여집합, `is_empty`는 경고가 없는 Deal을 고른다. Forecast가 `won` 또는 `lost`이면 모든 경고에서 제외하고, Status가 `contract_completed`이면 미업데이트에서 제외한다.
- **RQ-R25** 결과 값(표시 값): code 필드는 이름(Status·Forecast는 코드 이름 CD-R1, Vendor 이름, BANT는 Label 이름, Action 유형 이름), 정적 선택지 필드는 그 라벨(경고 값은 "기한초과"·"미업데이트"·"기한초과·미업데이트" 또는 null), user 필드는 표시 이름(없거나 빈 값이면 아이디)이고 퇴사자는 뒤에 "(퇴사)"(US-R12). 고객사·고객 담당자는 연결된 고객 연락처, 파트너사(현재)는 활성 파트너 연결의 회사다. `deal.status_days`·`deal.last_updated_at`·`deal.risk`는 Deals 목록 행의 값과 같다(RK-R6·RK-R10, 최종 업데이트는 RK-R2).
- **RQ-R26** 날짜 묶음 포맷: year = 정수 연도, quarter = 텍스트 `"YYYY Qn"`, month = 텍스트 `"YYYY-MM"`, ymd = 날짜(시각 필드는 업무 날짜). 시각 필드는 업무 시간대 오프셋의 달력 날짜로 묶는다(예: `2026-12-31T15:30Z`는 +09:00에서 2027년·`"2027-01"`·2027-01-01). 표시 전용 포맷(ymd_hm·weekday·relative)과 포맷 없음은 SQL 식을 바꾸지 않아 원래 값으로 묶는다.
- **RQ-R27** 결과 열의 `value_type`: 집계가 count·count_distinct면 `integer`, avg면 `decimal`, sum·min·max이거나 숫자 필드면 `integer`, 날짜·시각 필드는 포맷 year → `integer`, quarter·month → `text`, 날짜 필드이거나 포맷 ymd → `date`, 그 밖 → `datetime`, 나머지는 `text`. 값: integer는 정수, decimal은 소수 둘째 자리 반올림 실수, date는 `YYYY-MM-DD`, datetime은 서버 오프셋 ISO 시각(TM-R8), 빈 값은 null.
- **RQ-R28** 그룹핑: 그룹 컬럼들의 조합으로 묶는다. 묶는 기준은 code·user 필드면 id·key(이름이 같아도 다른 값이면 다른 그룹), 날짜는 묶음 포맷 값, 그 밖은 원래 값이다. 행이 있는 그룹만 나온다. `total_count`는 그룹 수다.
- **RQ-R29** 집계: sum·avg·min·max는 값, count는 값이 있는 행 수, count_distinct는 key 기준 고유 수다(이름이 아님). **Deal당 한 번**: 행 범위가 Action이고 그룹핑이면, Deal 필드의 sum·avg·count는 그룹마다 Deal 하나당 한 번만 센다(한 Deal이 두 그룹에 있으면 그룹마다 한 번). min·max·count_distinct는 원래 중복 영향이 없다. Action 필드의 count는 Action마다 센다. 응답 `deal_numbers_once`는 행 범위 action + 그룹핑 + Deal 숫자의 sum·avg 비그룹 컬럼이 있을 때만 true다. Deal 행 범위의 그룹핑은 Deal이 한 행이라 이 규칙이 필요 없다.
- **RQ-R30** 정렬: 정렬을 고른 컬럼들을 컬럼 순서대로 적용하고(같은 식은 한 번), NULL은 방향과 무관하게 맨 뒤다. 정렬 값은 code(Status·Forecast)는 코드 순서, 정적 선택지는 선언 순서, 그 밖은 표시 값(그룹핑하지 않은 날짜 컬럼은 원래 날짜)이다. 그룹핑 리포트는 집계 컬럼으로도 정렬하고, 지정 정렬 뒤에 남은 그룹 컬럼의 정렬 값 → 그룹 key 오름차순(NULL 뒤)으로 가른다. 그룹핑하지 않은 행의 동률은 Deal code 오름차순, Action 행이면 이어서 수행일·Action id 오름차순이다. 정렬을 하나도 고르지 않은 그룹핑 없는 결과는 Deal code 순이다. 정렬은 행 수 제한 전에 적용한다.
- **RQ-R31** 행 수 제한: 결과 `rows`는 최대 `row_limit`행(그룹)이다. `total_count` = 제한 전 전체 행(그룹) 수, `truncated` = `total_count > rows 수`. 맞는 행이 없으면 `rows: []`·`total_count: 0`·`truncated: false`.
- **RQ-R32** 합계 행(`totals`): 그룹핑하고 비그룹(집계) 컬럼이 하나 이상일 때만, 같은 조건의 **전체 범위**를 그룹 없이 한 번 더 집계한 한 행이다(컬럼 순서, 그룹 컬럼 자리는 null). 행 수 제한과 무관하고, 고유 건수·평균은 전체 기준이며, Action 행 범위면 Deal 필드를 전체에서 Deal당 한 번 센다. 그룹핑이 없거나 모든 컬럼이 그룹 컬럼이면 `totals: null`이다.
- **RQ-R33** 원장 일치: Vendor(그룹) × Expected Close 분기(그룹) × 금액 합계 × Deal code 건수, 조건 Forecast 구분 not_in [lost]·Expected Close 올해인 리포트의 각 칸은 같은 연도·분기·Vendor의 Deals 목록(DL-R1·DL-R6·DL-R9, Lost 제외) 건수·금액과 같다. 합계 행은 같은 조건 Deals 목록 전체 건수·금액과 같다.
- **RQ-R34** SQL 안전: 식별자(테이블·열)는 카탈로그 필드의 SQL 레지스트리에서만 오고, 사용자 값(검색어·목록·숫자·날짜)과 행 수 제한은 모두 바인딩 파라미터다. LIKE 특수 문자는 이스케이프한다. 필요한 JOIN만 붙인다(이름이 필요한 컬럼의 JOIN, Action 행일 때만 `deal_actions` JOIN, 조건에만 있으면 EXISTS 하위 쿼리). 카탈로그의 모든 필드는 그룹핑 없는 컬럼으로, 그룹핑할 수 있는 필드는 그룹 컬럼으로, 모든 (필드, 연산자)는 조건으로 SQL이 된다. 응답 `sql`은 표시 SQL(PostgreSQL 문법, 입력 값이 리터럴로 보임)이고 실행에 쓰지 않는다. 같은 정의에서 Port `render_sql`(DB 미사용)과 `run`의 `sql`은 같은 문자열이다. 그룹핑 리포트의 `sql`은 데이터 문장이다(합계 문장 제외).
- **RQ-R35** 읽기 전용·시간 제한: 조회 문장은 SAVEPOINT 안에서 `SET TRANSACTION READ ONLY`와 `SET LOCAL statement_timeout = 10000`(ms, `STATEMENT_TIMEOUT_SECONDS` 10 × 1000 — 숫자를 다른 곳에 하드코딩하지 않음)로 실행하고 끝나면 항상 되돌린다(블록 안 쓰기는 거절, 블록 밖 설정·쓰기는 영향 없음, 오류 뒤에도 되돌림). 제한을 넘으면(SQLSTATE 57014) 503 `report-timeout` "조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요"(DB 문구는 싣지 않음)이고 그 뒤에도 세션은 쓸 수 있다. 다른 DB 오류는 시간 초과로 바꾸지 않는다. 그룹핑 리포트는 데이터·합계 두 문장이라 최대 약 20초가 걸릴 수 있다(사용자 수용 2026-10-27).
- **RQ-R36** 조회 응답은 정확히 `{row_scope, action_filter, deal_numbers_once, columns, rows, totals, total_count, truncated, row_limit, sql, elapsed_ms, today}`다. `columns[i]` = `{index, field, label, entity, type, value_type, format, unit, prefix_length, group, aggregate}`: `label`은 적용된 표시 이름, `format`은 적용된 포맷(날짜 기본 포함, 포맷 없는 필드는 null), `unit`은 필드 단위(금액이면 집계가 건수여도 `"krw"` — 화면은 건수·고유 건수면 머리글에 "(원)"을 붙이지 않는다(RQ-R51), 현행 유지 2026-11-11 결정), `prefix_length`는 요청 값, `aggregate`는 적용된 집계(기본 포함) 또는 null. `rows[r]`의 값 순서는 컬럼 순서다. 금액은 원 단위 그대로다. `row_limit`은 적용 값, `elapsed_ms`는 실행 시간(ms), `today`는 조회 시점 업무 날짜(TM-R4)다. 조회 유스케이스는 서버 시계 하나(TM-R1)로 업무 날짜·업무 오프셋·경고 기준(`RiskBasis(오늘, stale_days)`)을 정해 정의와 함께 Port에 넘긴다.
- **RQ-R37** openapi: `GET /reports/fields`는 422를 문서화하지 않고(입력 없음), `POST /reports/query`는 422·503을 Problem으로 문서화한다. `format`·`default_format` 스키마는 nullable이고 enum 7값(RQ-R6), `unit`은 nullable이고 enum `krw` 하나(필드·결과 열 모두), 요청 컬럼에 `sort`가 있고 요청 최상위에 `sort`가 없다. 503 문구의 초는 도메인 상수에서 온다.

화면 (frontend, `/reports/new`)
- **RQ-R38** 화면 틀: 카탈로그를 읽는 동안 제목(h1) "새 리포트"와 "불러오는 중…", 실패하면 오류 배너(PL-R37)와 "다시 시도" 버튼(누르면 다시 읽음). 읽으면 디자이너: 경로 링크 "Reports"(`/reports`) + "›", 제목 "새 리포트", 설계가 바뀌었으면(RQ-R54) "● 저장 안 됨"(`role=status`), 버튼 "초기화"와 "저장"(활성 조건·저장 흐름은 RS-R31). 카탈로그는 세션 동안 한 번만 읽는다(RQ-R55).
- **RQ-R39** 탭: `tablist` "리포트 디자이너" 안의 "작성"·"결과" 두 탭이고 처음에는 작성 탭이다. 탭 버튼 클릭이나 ←/→ 키로 바꾸며(포커스도 이동), 비활성 패널은 DOM에 남기고 `hidden`으로 숨긴다. 그래서 탭을 옮겨도 설계·표 페이지·합계 행 선택이 남는다. 작성 탭에 고칠 곳(서버 위반 요약, RQ-R49)이 있으면 탭 이름이 "작성 (고칠 곳 N)"이고 위반이 없으면 이름만이다(결과 탭의 수는 차트 위반 — RC-R33). 작성 탭: 왼쪽 필드 목록, 오른쪽 위에서부터 데이터 범위 표시 → 컬럼 → 조건 → 최대 행·조회 → 조회 실패 알림. 결과 탭: 다시 조회 안내(RQ-R52), 보기 방식·타일(RS-R37~RS-R39, RC-R24~RC-R36), 표 타일(RQ-R50), 생성 SQL 보기(RQ-R53).
- **RQ-R40** 필드 목록(`aside` "필드 목록"): 검색 칸 "필드 검색"은 표시 이름의 부분 일치(대소문자 무시, 앞뒤 공백 무시)로 거른다. 묶음은 카탈로그 entity 순서(그룹 이름 "Deal"·"Deal Actions", 필드가 남은 묶음만)이고 필드마다 이름 버튼(접근성 이름 "<이름> 컬럼에 추가")·형식 라벨(텍스트·코드·사용자·숫자·날짜·시각)·`filterable` 필드만 "+조건" 버튼("<이름> 조건 추가")이다. 일치하는 필드가 없으면 "일치하는 필드가 없습니다.". 컬럼이 30개면 컬럼 추가 버튼, 조건이 20개면 "+조건"이 비활성이다. 이미 컬럼에 있는 필드는 흐리게 보이고, 다시 누르면 확인 대화상자 "같은 필드 추가" / "'<이름>'은(는) 이미 컬럼에 있습니다. 한 번 더 추가할까요?"(확인 "추가", 취소·Escape는 추가하지 않음)를 거친다. "+조건"은 묻지 않는다.
- **RQ-R41** 데이터 범위 표시(`role=status`, 설계가 바뀔 때마다 바뀜, 판정은 서버 RQ-R20·RQ-R29와 같은 규칙): Action 필드가 컬럼에 있으면 "행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)", 조건에만 있으면 "행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만" + 결합이 AND면 "(같은 Action 하나가 모든 Action 조건을 만족)"·OR면 "(Action 조건 중 하나를 만족하는 Action이 있는 Deal)", 없으면 "행 단위: Deal 1건". Deal당 한 번이 적용될 설계면 "Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다"를 덧붙인다. Deal 필드 조건만 있으면 Action 문구가 없다.
- **RQ-R42** 컬럼 칩(카드 "컬럼"): 컬럼이 없으면 "왼쪽 필드 목록에서 컬럼을 추가하세요.". 추가한 칩이 선택된다(누르면 선택, `aria-pressed`). 칩 이름은 표시 이름(비면 필드 이름), "<이름> 빼기"(×)로 뺀다. 칩은 끌어서 놓기로 옮기고, 키보드는 칩에서 Alt+←/→로 한 칸 옮기며 옮긴 칩에 포커스가 남고 "‘<이름>’를 N번째로 옮겼습니다"를 알린다(끝을 넘거나 Alt 없는 화살표는 아무것도 하지 않음, 옮기기 버튼 없음). 배지: 그룹 컬럼 "그룹" 또는 집계 이름, 기본과 다른 포맷 이름, 앞 N자를 켜면 "앞 N자", 정렬 "▲ 오름"·"▼ 내림"(정렬한 컬럼이 둘 이상이면 뒤에 우선순위 번호), 그룹핑이 없을 때 Action 건수에 "그룹핑할 때만". 컬럼이 30개면 "컬럼은 최대 30개입니다".
- **RQ-R43** 컬럼 설정(선택한 칩 아래 한 줄, `section` "컬럼 설정: <이름>"): 첫 칸에 컬럼 이름, 이어서 "표시 이름"(최대 100자, 자리 표시 = 필드 이름), "포맷"(포맷이 있는 필드만, 카탈로그 라벨 + 묶음 포맷이면 " (묶음)"), "앞 N자만 보기" 체크박스와 "앞 N자의 N"(1~200, 켜기 전에는 비활성, 켜면 비어 있을 때 20), "그룹핑" 체크박스(`groupable: false`면 비활성), "집계"(그룹핑 리포트의 비그룹·잠기지 않은 컬럼에서만 활성, 비활성이고 값이 없으면 "—", 그룹핑이 없으면 옆에 "(그룹핑이 있을 때)"), "정렬"("정렬 없음"·"오름차순"·"내림차순", 기본 정렬 없음). 칸 이름은 `aria-label`·`title`이고 위반 문구는 줄 아래(표시 이름·포맷·앞 N자·그룹핑·집계·정렬 순)다. 포맷을 바꿔도 앞 N자는 유지된다.
- **RQ-R44** 집계 자동 맞춤: 그룹 컬럼이 생기면 집계가 비어 있는 비그룹 컬럼에 기본 집계(숫자 기본, 없으면 "건수", 건수도 없으면 첫 선택지)를 채우고, 그 뒤에 추가한 컬럼도 같다(그룹핑 중 빈 집계 선택지는 없다). 그룹 컬럼이 모두 없어지면(체크 해제·컬럼 빼기) 모든 집계를 비운다. 컬럼을 그룹으로 바꾸면 그 컬럼 집계를 비운다. Action 건수는 그룹핑을 켤 수 없고 집계가 "건수"로 잠긴다. 화면은 서버가 거절할 조합을 미리 막지 않는다(최종 판정은 서버).
- **RQ-R45** 조건 행(카드 "조건"): 결합 라디오(`legend` "조건 결합") "모든 조건을 만족(AND)"·"하나라도 만족(OR)", 기본 AND. 조건이 없으면 "조건이 없으면 모든 Deal이 대상입니다"(Action 행이면 "…모든 Action이…"). 행은 접속어(둘째 행부터 결합의 대문자 AND/OR) · "조건 N 필드"(조건에 쓸 수 있는 필드만) · "조건 N 연산자"(그 필드의 연산자, 카탈로그 라벨) · 값 · "조건 N 삭제"이고 삭제하면 번호가 다시 매겨진다. 새 조건(필드 목록 "+조건" 또는 "+ 조건 추가" = 첫 조건 가능 필드)과 필드 변경은 연산자를 그 필드의 첫 연산자로, 값을 빈 값으로 둔다. 연산자를 바꾸면 값 모양이 같을 때만 값을 유지한다. 20개면 "+ 조건 추가" 비활성과 "조건은 최대 20개입니다".
- **RQ-R46** 조건 값 입력(연산자 모양별): none은 입력 칸 없음, text는 "조건 N 값"(최대 200자), number는 정수 칸(금액 필드는 원 단위 금액 입력 — 숫자·콤마만, 입력 중 콤마 자동, 옆에 "(원)", UI-R12), range는 "조건 N 시작"·"~"·"조건 N 끝"(금액이면 둘 다 금액 입력과 "(원)", Users count·일수에는 "(원)" 없음), date는 날짜 입력(`DateInput`, UI-R1~R11), 날짜 범위는 시작·끝 날짜 입력, relative는 "조건 N 기간"(카탈로그 순서 8개, 새 값 기본 "올해")과 최근 N일일 때만 "조건 N 일수"다. list는 다중 선택(UI-R22~R24)이며 접근성 이름은 "조건 N 값"과 선택 요약을 포함한다. 선택한 값이 없으면 "선택"을 표시하고, 값이 있으면 "N개 선택"과 모든 선택값의 이름을 표시한다. "선택 해제"로 모두 해제할 수 있다. 목록 선택지는 정적 선택지는 카탈로그 순서, 담당자·수행자는 퇴사자 포함 사용자 목록, Vendor는 Vendor 목록, Status·Forecast는 코드 순서(CD-R5), BANT는 그 구분의 Label만, Action 유형은 유형 목록이며 목록을 읽지 못하면 오류 배너를 함께 보인다.
- **RQ-R47** 조회 요청 만들기: 컬럼은 `field`, `group`, 표시 이름(앞뒤 공백을 지운 값이 비었거나 필드 이름과 같으면 생략), `format`(있을 때만), `prefix_length`(앞 N자를 켰을 때만), `aggregate`·`sort`(있을 때만)를, 조건은 `field`·`operator`·`value`(값 없는 연산자는 생략)를, 그리고 `combine`·`row_limit`을 보낸다(게이트웨이가 snake_case로 바꿈). 숫자는 콤마를 빼고 정수로 읽고(안전 정수 범위), id 목록은 숫자로, 금액은 입력한 원 그대로, 날짜는 ISO `YYYY-MM-DD`, 상대 기간은 `{period}`(최근 N일만 `days` 포함 — 최근 n개월은 일수 칸이 남아도 보내지 않음). 읽을 수 없는 입력이 하나라도 있으면 **요청을 보내지 않고** 그 칸 아래에 문구를 보인다(`aria-invalid`): 빈 텍스트 "값을 입력하세요", 빈 목록 "하나 이상 선택하세요", 정수가 아님 "정수로 입력하세요", 범위 시작 > 끝 "시작이 끝보다 클 수 없습니다", 빈 날짜 "날짜를 고르세요", 덜 쳤거나 틀린 날짜는 날짜 입력 규칙의 문구(UI-R7), 최근 N일의 N "1~3650 사이 정수를 입력하세요", 앞 N자의 N "1~200 사이 정수를 입력하세요". 작성 탭에 머문다.
- **RQ-R48** 최대 행·조회(카드 "최대 행과 조회"): "최대 행" 선택지는 카탈로그 `row_limits`(표시 100·1,000·10,000), 기본 1,000. "조회" 버튼은 컬럼이 없거나 조회 중이면 비활성이고 조회 중에는 "조회 중…"이다(두 번째 조회를 막음).
- **RQ-R49** 조회 결과 처리: 성공하면 결과 탭으로 옮긴다(매 성공마다). 실패하면 작성 탭에 머물고 조회 버튼 아래에 알림(`role=alert`)을 보이며 결과 탭에는 마지막 성공 결과가 그대로 남는다. 정의 위반(`invalid-report`)이면 "고칠 곳 N개"와 항목별 "<위치>: <서버 문구>" 목록이고, 위치 이름은 "컬럼 i(<칩 이름>)"·"조건 i(<필드 이름>)"·"컬럼"·"조건"·"조건 결합"·"최대 행"이며 위치를 모르는 위반(예전 최상위 `sort` 등)은 위치 없이 요약에만 보인다. 같은 위반을 해당 칩(칩 아래)·컬럼 설정 칸·조건 행·결합·최대 행 아래에도 보인다(위반 위치는 마지막 조회 때의 index → 화면 항목으로 옮김). 그 항목을 고치면(컬럼 설정 변경, 조건 필드·연산자·값 변경, 컬럼·조건 추가·삭제는 목록 위반, 결합·최대 행 변경) 그 표시가 사라지고, 지운 컬럼·조건의 위반은 사라지며, 남은 위반이 없으면 요약도 없다. 시간 초과·연결 끊김·그 밖의 오류는 서버 문구(게이트웨이 문구, PL-R37·PL-R39) 한 줄이다. 다음 조회가 성공하면 실패 알림이 사라진다.
- **RQ-R50** 표 타일(결과 탭): 조회 전에는 "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요."(보기 방식·배치는 결과가 없어도 바꿀 수 있음 — RS-R36). 결과가 있으면 머리에 "총 N행 · 조회 S초"(S = 소수 둘째 자리, 잘렸으면 "총 N행 중 M행 표시(최대 행 수 제한)" · …, 숫자는 천 단위 콤마), `totals`가 있으면 "합계 행" 체크박스(기본 꺼짐, 새 결과가 오면 다시 꺼짐). 표(캡션 "조회 결과", 가로 스크롤 컨테이너 안)의 머리글은 결과 열 `label`(RQ-R51), 행은 100행씩이고 100행을 넘을 때만 페이저가 있으며 새 결과가 오면 첫 페이지다. 합계 행을 켜면 `tfoot`에 한 행: 첫 그룹 열 칸은 "합계", 나머지는 합계 값(앞 N자로 자르지 않음). 합계 행을 켰고 `deal_numbers_once`면 표 아래에 "한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다".
- **RQ-R51** 셀 표시: null은 "—". 숫자는 천 단위 콤마·소수 없는 반올림(평균 포함), 포맷 year는 콤마 없이 그대로. 금액 열(단위 krw이고 집계가 건수·고유 건수가 아님)은 머리글 뒤에 " (원)"이 붙고 값은 원 그대로. 숫자 열(value_type integer·decimal)은 오른쪽 정렬. 날짜: weekday "YYYY-MM-DD (요일 한 글자)", relative는 앱 시계(TM-R12)의 오늘 기준 "오늘"·"N일 전"·"N일 후", 그 밖은 값 그대로. 시각: ymd_hm은 시각 표기(TM-R14), ymd는 날짜 부분, weekday "날짜 (요일)", relative는 상대 시각 표기(Deals 목록 최종 업데이트와 같음). 묶음 값(연도·분기·월 텍스트)은 그대로. 앞 N자: 포맷한 글자를 코드 포인트 기준 앞 N자만 보이고 넘치면 "…"를 붙이며(정확히 N자·"—"는 그대로) 셀 `title`에 전체 값을 둔다. 잘리지 않은 text·code·user 문자열 셀도 `title`이 값이다.
- **RQ-R52** 다시 조회 안내: 마지막 성공 조회 뒤 컬럼(정렬·앞 N자 포함)·조건·결합·최대 행이 바뀌면 결과 탭 위에 "설계가 바뀌었습니다. 작성 탭에서 '조회'를 눌러 다시 조회하세요"(`aria-live`)를 보이고 결과는 이전 그대로다. 칩 선택·차트·보기 방식·배치만 바뀐 것은 해당하지 않는다. 조회 전과 다시 조회한 뒤에는 없다. 작성 탭에는 보이지 않는다.
- **RQ-R53** 생성 SQL 보기(결과 탭 아래): 조회 전에는 "조회하면 서버가 만든 SQL이 여기에 보입니다", 조회 뒤에는 접힌 영역 "생성 SQL 보기(읽기 전용)" 안에 마지막 성공 조회의 `sql`을 키보드로 스크롤할 수 있는 읽기 전용 영역으로 보인다. SQL 입력 칸은 어디에도 없다.
- **RQ-R54** 떠날 때 확인·초기화(새 리포트): 설계가 바뀐 상태(컬럼·조건이 있거나, 결합이 OR이거나, 최대 행이 기본값이 아니거나, 차트 초안이 있음 — 결과 배치만 바뀐 것은 제외, 넣었다 다시 빼면 바뀌지 않은 상태)에서 (1) 앱 안 다른 주소의 링크를 누르거나 (2) 브라우저 뒤로 가기·앞으로 가기(history 이동)로 다른 경로(pathname)로 가려 하면 확인 대화상자 "저장하지 않은 변경이 있습니다" / "저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?"("떠나기"·"머물기")를 보인다. 링크의 "떠나기"는 원래 링크 동작(이동·열린 메뉴 닫기 포함)을 이어 하고, 뒤로·앞으로 가기의 "떠나기"는 멈춘 history 이동을 마저 해 이전(다음) 화면으로 간다. "머물기"는 그대로 둔다 — 뒤로·앞으로 가기에서 머물면 주소도 이 화면 그대로이고 설계·결과·탭·위반 표시가 남으며, 다시 뒤로 가기를 하면 다시 묻는다. 경로가 같은 history 이동(검색어·해시만 다름)은 묻지 않는다. 확인 창은 한 번에 하나이고, 링크 "떠나기"로 시작한 이동에는 다시 묻지 않는다. 바뀐 상태인 동안만 새로고침·탭 닫기(그리고 앱 밖 문서로 가는 뒤로 가기)에 브라우저 확인(`beforeunload`)을 건다(떠나면 해제). 코드의 직접 이동(저장 뒤 편집 화면으로 이동, 로그아웃 등)은 막지 않는다(2026-10-27 사용자 결정 유지). 바뀌지 않았으면 묻지 않는다. 뒤로·앞으로 가기 확인은 2026-11-18 사용자 요청으로 추가했고 2026-10-27 결정(Q2=A)의 '뒤로 가기 제외'를 대체한다. 구현은 앱 라우터를 데이터 라우터(`createBrowserRouter` + `RouterProvider`)로 바꾸고 `useBlocker`를 history 이동(POP)에만 쓴다. "초기화": 바뀐 상태면 "설계를 모두 지울까요?" / "컬럼과 조건이 모두 사라집니다."("초기화"·"취소") 확인 뒤, 아니면 바로 설계·결과·위반 표시를 모두 지운다(취소하면 그대로). 편집 화면의 같은 동작은 RS-R32·RS-R33이고, 편집 화면에서 차트를 바꾼 경우의 저장 안 됨·되돌리기는 RC-R38이다.
- **RQ-R55** 게이트웨이·데이터 훅: `reports.fields()` = `GET /reports/fields` → camelCase(`limits.columnsMax` 등, 연산자 `value` → `shape`, 필드의 모든 속성과 선택지, 포맷 없는 필드는 `formats: []`·`defaultFormat: null`). `reports.query(input)` = `POST /reports/query`에 snake_case 본문(설계가 비운 키는 보내지 않음) → camelCase 결과(`rowScope`·`actionFilter`·`dealNumbersOnce`·`totalCount`·`rowLimit`·`elapsedMs`, 열의 `valueType`·`unit`·`prefixLength`, `totals` null 유지). 오류: 401은 `unauthorized`, `invalid-report`는 본문 `errors`를 `problem.reportErrors`(`{location, code, message}`, 모양이 맞는 항목만)로 옮기고 일반 오류 변환에서 빼서 TypeError 없이 `ApiError`(문구 = detail), `request-validation`은 `validation`(칸 문구 포함, PL-R37), `report-timeout`은 서버 detail 유지, 연결 실패는 network(PL-R39). `useReportFields`는 키 `reportFields`·다시 받지 않음(staleTime 무한)·재시도 없음, `useRunReport`는 버튼으로만 실행하고 어떤 쿼리도 무효화하지 않는다. `reportRunFailure`: invalid-report → `{kind: invalid, message, issues(없으면 [])}`, report-timeout → timeout, network → network, 그 밖의 ApiError → other(문구), ApiError가 아닌 오류 → other(일반 문구).
- **RQ-R56** 조회 Fake 게이트웨이(`test/fake/gateway/reports.ts`, 카탈로그 `test/fake/seed/reportCatalog.ts`): 카탈로그는 서버 카탈로그와 같은 내용의 사본(호출자가 바꿔도 원본 불변)을 주고, 미인증은 401이다. 서버와 다르던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**. 조회는 테스트가 응답 처리기(`setReportQueryHandler`)를 정하면 그 결과·오류를 쓰고, 아니면 다음 위반만 서버와 같은 code·location·문구로 흉내 낸다: 컬럼 수, 컬럼·조건의 unknown-field, group-not-allowed, 그룹 컬럼 집계, grouping-required, 그룹핑 없는 집계, aggregate-required, 그룹핑 집계 허용 목록, conditions-count, row-limit-invalid("행 수 제한은 100, 1000, 10000 중 하나여야 합니다" — 서버 RQ-R19와 같은 문구). 위반이 있으면 `invalid-report`(detail = 첫 문구)이고, 없으면 합성 결과(3행, 값 형식별 결정적 값, 범위 판정은 서버 RQ-R20·RQ-R29와 같음, `today` = Fake 시계, `totalCount` 3, `truncated` false)를 준다. 조회 요청은 모두 기록하고 데이터 초기화 때 처리기·기록을 지운다. 포맷·표시 이름·앞 N자·정렬·연산자·값·결합 위반은 흉내 내지 않는다 — 이 범위는 넓히지 않고, 그런 위반이 필요한 화면 테스트는 처리기로 위반을 주입한다(2026-11-11 결정). 합계 행(`totals`)은 서버(RQ-R32)와 같이 그룹핑하고 비그룹(집계) 컬럼이 하나 이상일 때만 주고 그룹핑이 없거나 모든 컬럼이 그룹 컬럼이면 null이다. 합계 행의 그룹 칸은 null이고 집계 칸은 비우지 않는다: 합성 행에서 그 집계로 계산한 값(sum·count·count_distinct는 행 값의 합, avg는 행 값의 평균을 소수 둘째 자리에서 반올림, min·max는 행 값의 최소·최대)이다.

저장 정의 JSON (2026-11-11 결정으로 RQ 소유)
- **RQ-R58** 날짜로 바뀐 필드(2026-11-13): `deal.last_updated_at`·`deal.status_changed_at`·`action.acted_at`·`action.closed_at`은 형식이 date다. 포맷은 date 허용표(기본 ymd)를 따르고 `ymd_hm`은 쓸 수 없다(요청하면 RQ-R12의 422 `format-not-allowed`). 저장 리포트 정의에 이 네 필드의 `ymd_hm`이 있으면 읽을 때 `ymd`로 바꾼다(RQ-R57과 같은 자동 변환이고, 다시 저장하면 새 값이 들어간다). 조건 값과 상대 기간은 date 형식 규칙을 따른다. 이제 datetime 형식 필드는 `deal.created_at` 하나뿐이다.
- **RQ-R57** 저장 리포트의 정의 JSON(`reports.definition`, RS-R1)은 `/reports/query` 요청과 같은 모양으로 쓴다: 컬럼마다 `field`·`label`·`format`·`prefix_length`·`group`·`aggregate`·`sort` 7키, 그리고 `conditions`(`field`·`operator`·`value`)·`combine`·`row_limit`이며 최상위 `sort`는 없다. 읽을 때(`definition_from_json` — 목록·상세·실행·복제·배치 저장이 모두 이것으로 읽는다) 예전 형식을 새 형식으로 바꾼다:
  - ① 예전 텍스트·코드 포맷 `as_is`·`prefix`·`name`·`key`와 예전 숫자 포맷 `thousands`·`krw_thousand`·`krw_million`·`decimal1`·`percent_share`는 포맷 없음(null)으로 읽고 `prefix_length`는 그대로 둔다(예전 `prefix` 포맷의 N은 앞 N자 옵션으로 남는다). 그래서 코드·사용자 열은 이름으로, 예전 구성비 열은 원래 집계 값(금액은 원)으로 실행된다. 지금 포맷(RQ-R6)은 그대로다.
  - ② 예전 최상위 `sort` `{column, direction}`(direction 생략은 `asc`)은 그 위치 컬럼의 `sort`로 옮긴다. 그 컬럼에 자기 `sort` 값이 있으면(빈 문자열 포함) 그것이 우선한다. 최상위 `sort: null`은 정렬 없음이다.
  - ③ `combine`·`row_limit` 키가 없으면 `"and"`·1000으로 읽는다. 그 밖의 값(상대 기간 키 포함)은 바꾸지 않는다.
  - ④ 컬럼·조건의 `field`가 예전 key `deal.solution`이면 `deal.product`로 읽는다(2026-11-16 이름 변경, RQ-R59). 컬럼 `label`은 사용자가 쓴 값이라 바꾸지 않는다.
  - ⑤ 컬럼·조건의 `field`가 예전 key `action.memo`면 `action.comment`로 읽는다(2026-11-17, RQ-R60). `label`은 바꾸지 않는다.
  - 값(포맷·정렬 방향·집계·연산자·조건 값·행 수)은 읽을 때 검사하지 않고 실행·복제 때 RQ-R7~RQ-R19로 다시 검증한다(예: 예전 정렬 방향 `up`은 읽기는 되고 실행 때 `["columns", i, "sort"]` `sort-invalid`).
  - 다음 모양이면 읽을 수 없는 정의다(위반 하나 `["definition"]` `stored-invalid` "저장된 리포트 정의를 읽을 수 없습니다."): 객체가 아님, `columns`가 없거나 객체 목록이 아님, 컬럼 `field`가 문자열이 아님, 컬럼 `label`·`format`·`aggregate`·`sort`가 null도 문자열도 아님, `group`이 bool이 아님(없으면 false), `conditions`가 있는데 객체 목록이 아님, 조건 `field`·`operator`가 문자열이 아님, 최상위 `sort`가 null도 객체도 아님, 그 `column`이 컬럼 위치(0 ~ 컬럼 수 − 1) 정수가 아님(bool·문자열 제외), `direction`이 문자열이 아님. 읽을 수 없는 정의의 목록·상세·실행·복제·배치 저장 결과는 RS-R17이 정한다.
  - 읽은(변환한) 정의를 다시 쓰면 새 형식(포맷 null, 컬럼 `sort`, 최상위 `sort` 없음)으로 쓰인다. 상세 응답의 `definition`도 읽은 정의를 새 형식으로 쓴 값이다.
- **RQ-R59** Product 필드 key(2026-11-16): Deal의 Solution 이름을 Product로 바꿔 카탈로그 3번 필드는 key `deal.product`, 이름 "Product"다(형식·연산자·집계·그룹핑·SQL 식은 그대로, 컬럼 `deals.product`). `/reports/query`·저장·수정 요청의 `deal.solution`은 변환하지 않고 RQ-R9의 `unknown-field` "허용되지 않은 필드입니다: deal.solution"이다. 저장 정의 JSON의 `deal.solution`은 읽을 때 바꾼다(RQ-R57 ④).
- **RQ-R60** `action.comment`(2026-11-17)
  - Action 필드이고 text 형식이다. 포맷·연산자·집계·그룹핑은 text 허용표를 따른다.
  - SQL 식은 `deal_comments`에서 `action_id` = 그 Action id인 행의 `string_agg(body, E'\n' ORDER BY created_at, id)` 스칼라 서브쿼리다. Comment가 없으면 null이고, 따라서 `is_empty`에 맞는다.
  - Action 필드이므로 다른 Action 필드와 똑같이 action_filter를 정한다: 컬럼에 있으면 `join`, 조건에만 있으면 `exists`.
  - 요청의 `action.memo`는 RQ-R9의 `unknown-field` "허용되지 않은 필드입니다: action.memo"다. 저장 정의 JSON의 `action.memo`는 읽을 때 바꾼다(RQ-R57 ⑤).
  - **API 응답 호환 깨짐**(사용자 승인 2026-11-17).
- **RQ-R61** `deal.comment`(2026-11-17)
  - Deal 필드이고 text 형식이다. 범위는 그 Deal 소속 Comment 전부다(CM-R2: Action 연결 여부와 무관하며, Action Comment 본문은 `action.comment`와 겹쳐 나온다).
  - SQL 식은 `deal_comments`에서 `deal_id` = 그 Deal id인 행의 `string_agg(body, E'\n' ORDER BY created_at, id)` 스칼라 서브쿼리다. 없으면 null이다.
  - action_filter와의 관계: Deal 필드이므로 이 필드만으로는 Action 범위가 되지 않는다(`none` 유지). 다른 Action 필드와 함께 쓰면 그 규칙대로 Action 행 범위가 된다. 이때 같은 Deal의 Action 행마다 같은 값이 반복된다(다른 Deal 필드와 같다).
  - Deal당 한 번 규칙과의 관계: Action 행 범위에서 그룹핑하면 `deal.comment`의 집계 `count`·`count_distinct`는 다른 Deal 필드처럼 그룹마다 Deal 하나당 한 번만 센다. 그래서 Action 행 수와 무관하게, Comment가 있는(null이 아닌) Deal 수가 된다.
  - 그룹핑 열로 쓰면 이어 붙인 전체 값이 같은 Deal끼리 묶인다(text 규칙 그대로).
  - 조건 `contains`는 Deal 소속 Comment 중 어느 하나의 본문에 포함되면 맞는다. 이어 붙인 값에 대해 검사하므로, 줄바꿈을 넘는 부분 일치도 맞을 수 있다(수용).
  - 하위 호환 추가다.

### 2.4 상태와 전이

디자이너(새 리포트): 카탈로그 읽는 중 → (실패 ⇄ 다시 시도) → 설계 중(바뀌지 않음 ⇄ 바뀜) → 조회 중 → [성공: 결과 탭, 결과 있음(최신)] 또는 [실패: 작성 탭, 실패 알림, 이전 결과 유지] → 설계 변경 → 결과 있음(낡음, RQ-R52) → 다시 조회 …. 초기화는 설계 중(바뀌지 않음)·결과 없음으로 돌아간다.

조회 한 번의 서버 결과: 422 `request-validation`(모양) | 422 `invalid-report`(정의) | 503 `report-timeout` | 200.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /reports/fields` | 401 | 가능 | 가능 | 가능 |
| `POST /reports/query` | 401 | 가능(CSRF 헤더 필요) | 가능 | 가능 |
| 화면 `/reports/new`(설계·조회) | `/login`으로(PL-R29) | 가능 | 가능 | 가능 |

두 경로는 업무 조회(PL-R2)라 역할 가드가 없다. 대상 데이터는 역할과 무관하게 모든 Deal이다. 저장은 RS.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/reports/fields` | — | 200 `ReportCatalogResponse`(RQ-R2~RQ-R6) | 401 |
| POST `/reports/query` | 본문 `{columns: [{field, label?, format?, prefix_length?, group?, aggregate?, sort?}], conditions?: [{field, operator, value?}], combine?, row_limit?}` | 200 `ReportQueryResponse`(RQ-R36) | 401, 403 `csrf`, 422 `request-validation`·`invalid-report`(`errors: [{location, code, message}]`), 503 `report-timeout` |

위반 code 목록: `unknown-field`, `columns-count`, `label-invalid`, `format-not-allowed`, `value-invalid`(앞 N자·조건 값), `group-not-allowed`, `aggregate-not-allowed`, `aggregate-required`, `grouping-required`, `sort-invalid`, `conditions-count`, `not-filterable`, `operator-not-allowed`, `combine-invalid`, `row-limit-invalid`. (`chart`·`layout` 위치 위반은 저장 요청에서만 — RC-R5·RS-R20. 저장 정의를 읽을 수 없을 때의 `stored-invalid`는 RQ-R57·RS-R17.)

### 2.7 화면 동작

RQ-R38~RQ-R56.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 요청 모양(필수 키·형식·모르는 키·예전 최상위 sort) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12) |
| 정의 위반 | 422 `invalid-report` | 첫 위반 문구(RQ-R9~RQ-R19), `errors`에 전부 |
| 시간 제한 초과 | 503 `report-timeout` | 조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요 |
| 미인증 | 401 `unauthenticated` | 로그인이 필요합니다(PL-R5) |
| CSRF 헤더 없음 | 403 `csrf` | PL-R9 |

정의 위반 문구(서버): "허용되지 않은 필드입니다: <key>", "컬럼은 1개 이상 30개 이하로 지정하세요", "표시 이름은 공백이 아닌 100자 이하여야 합니다", "이 필드는 포맷을 고를 수 없습니다", "이 필드에 쓸 수 없는 포맷입니다. 가능: …", "앞 N자의 N은 1~200의 정수여야 합니다", "이 필드는 그룹핑할 수 없습니다", "그룹 컬럼에는 집계를 지정할 수 없습니다", "이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요", "그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요", "그룹핑할 때 이 컬럼은 집계(…)를 골라야 합니다. 그룹핑하거나 빼세요", "그룹핑할 때 이 컬럼은 …만 고를 수 있습니다. 그룹핑하거나 빼세요", "정렬은 asc 또는 desc만 쓸 수 있습니다", "조건은 20개까지 지정할 수 있습니다", "이 필드는 조건에 쓸 수 없습니다", "이 필드에 쓸 수 없는 연산자입니다. 가능: …", 조건 값 문구(RQ-R17), "선택지에 없는 값입니다. 가능: …", "조건 결합은 and 또는 or만 쓸 수 있습니다", "행 수 제한은 100, 1000, 10000 중 하나여야 합니다".

화면 문구: "새 리포트", "불러오는 중…", "다시 시도", "Reports", "● 저장 안 됨", "초기화", "작성", "결과", "작성 (고칠 곳 N)", "필드 목록", "필드 검색", "일치하는 필드가 없습니다.", "+조건", "같은 필드 추가", "'<이름>'은(는) 이미 컬럼에 있습니다. 한 번 더 추가할까요?", "추가", "행 단위: …"(RQ-R41), "컬럼", "왼쪽 필드 목록에서 컬럼을 추가하세요.", "컬럼은 최대 30개입니다", "‘<이름>’를 N번째로 옮겼습니다", "그룹", "앞 N자", "▲ 오름", "▼ 내림", "그룹핑할 때만", "컬럼 설정: <이름>", "표시 이름", "포맷", " (묶음)", "앞 N자만 보기", "그룹핑", "집계", "(그룹핑이 있을 때)", "정렬", "정렬 없음", "오름차순", "내림차순", "조건", "조건 결합", "모든 조건을 만족(AND)", "하나라도 만족(OR)", "조건이 없으면 모든 Deal이 대상입니다", "+ 조건 추가", "조건은 최대 20개입니다", "(원)", "선택", "선택 해제", 입력 문구(RQ-R47), "최대 행", "조회", "조회 중…", "고칠 곳 N개", "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요.", "총 N행 · 조회 S초", "총 N행 중 M행 표시(최대 행 수 제한)", "합계 행", "합계", "조회 결과", "—", "오늘", "N일 전", "N일 후", "한 Deal이 여러 그룹에 나오면 …", "설계가 바뀌었습니다. 작성 탭에서 '조회'를 눌러 다시 조회하세요", "조회하면 서버가 만든 SQL이 여기에 보입니다", "생성 SQL 보기(읽기 전용)", "저장하지 않은 변경이 있습니다", "저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?", "떠나기", "머물기", "설계를 모두 지울까요?", "컬럼과 조건이 모두 사라집니다.", "취소".

## 3. Business use case

### RQ-UC1 필드 카탈로그 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, Reports 목록에서 "+ 새 리포트" 또는 `/reports/new`
- 기본 흐름: 카탈로그를 읽는다 → 필드 목록(Deal·Deal Actions)과 형식이 보인다 → 검색으로 필드를 찾는다(RQ-R1~RQ-R6, RQ-R38, RQ-R40)
- 대안: 일치하는 필드가 없으면 안내
- 예외: 카탈로그를 읽지 못하면 오류와 "다시 시도"
- 결과: 쓸 수 있는 필드·연산자·한도가 화면에 있다

### RQ-UC2 리포트 설계
- 행위자: 로그인한 모든 역할
- 사전 조건: RQ-UC1
- 기본 흐름: 필드를 컬럼으로 넣는다 → 칩 순서를 바꾼다 → 컬럼 설정(표시 이름·포맷·앞 N자·그룹핑·집계·정렬)을 고른다 → 조건을 넣고 결합·값을 고른다 → 최대 행을 고른다(RQ-R41~RQ-R48)
- 대안: 같은 필드를 확인 뒤 한 번 더 넣는다, 데이터 범위 표시로 행 단위를 확인한다
- 예외: 한도(컬럼 30·조건 20)에서는 추가 버튼이 꺼진다
- 결과: 화면에 설계가 있다(저장 전에는 이 화면에만)

### RQ-UC3 조회와 결과 확인
- 행위자: 로그인한 모든 역할
- 사전 조건: 컬럼이 하나 이상인 설계
- 기본 흐름: "조회"를 누른다 → 서버가 정의를 검증하고 SQL을 만들어 읽기 전용으로 실행한다 → 결과 탭으로 옮겨 총 행·조회 시간·결과 표를 본다 → 합계 행을 켜고 생성 SQL을 확인한다(RQ-R7~RQ-R37, RQ-R49~RQ-R53)
- 대안: 100행을 넘으면 페이지를 넘긴다, 최대 행을 넘으면 잘림 표시, 설계를 바꾸면 다시 조회 안내
- 예외: 정의 위반·시간 초과·연결 실패는 RQ-UC4
- 결과: Deals 목록과 같은 숫자의 결과(RQ-R33), 아무것도 저장되지 않음

### RQ-UC4 위반·실패 고치기
- 행위자: 로그인한 모든 역할
- 사전 조건: 조회가 실패함
- 기본 흐름: 작성 탭에 남아 "고칠 곳 N개"와 칸별 표시를 본다 → 해당 칸을 고친다(표시가 사라짐) → 다시 조회한다(RQ-R47, RQ-R49)
- 대안: 읽을 수 없는 입력은 요청 없이 칸 아래 안내, 시간 초과면 조건을 좁힌다
- 예외: 위치를 모르는 위반은 요약에만
- 결과: 성공하면 실패 알림이 사라지고 결과 탭으로 옮긴다

### RQ-UC5 설계 버리기
- 행위자: 로그인한 모든 역할
- 사전 조건: 설계가 바뀐 상태
- 기본 흐름: "초기화"를 누르고 확인한다, 또는 다른 메뉴 링크를 누르거나 브라우저 뒤로·앞으로 가기를 하고 "떠나기"를 고른다(RQ-R54)
- 대안: "취소"·"머물기"면 그대로(뒤로·앞으로 가기에서 머물면 주소도 그대로), 바뀌지 않았으면 묻지 않음
- 예외: 코드의 직접 이동(저장 뒤 이동·로그아웃)은 묻지 않고 떠난다
- 결과: 설계·결과가 사라지거나 다른 화면으로 이동

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), VIEWER(user). 서버 업무 시간대 Asia/Seoul(+09:00), 오늘(업무 날짜) 2026-10-27, 경고 기준 14일. 기본 Forecast 코드 pipeline·best·most_likely·commit(open)·won·lost, 기본 Action 유형에 "미팅"·"전화" 포함. backend 케이스는 도메인 검증 함수 단위 테스트, `FakeUnitOfWork`(`FakeReportQueryRunner`는 받은 정의를 기록하고 정한 결과를 돌려줄 뿐 SQL을 흉내 내지 않음)·고정 Clock의 유스케이스 단위 테스트, FakeUseCases + TestClient의 web 단위 테스트, SQL 생성 단위 테스트, 그리고 실제 PostgreSQL 임시 DB에서 `SqlReportQueryRunner`를 도는 조회 계약 테스트(integration 표시, `report_case`)다. 결과 행 의미(RQ-R20~RQ-R33)는 Fake가 흉내 내지 않으므로 조회 계약 테스트에 둔다. frontend 케이스는 Fake 게이트웨이(카탈로그 사본, 조회 처리기 지정 가능)를 쓰는 Vitest다. 저장 정의 읽기 케이스(RQ-108~RQ-112)는 `definition_from_json`·`definition_to_json` 도메인 단위 테스트, Fake UoW에 예전 형식 정의를 직접 넣은 저장 리포트 상세·실행 유스케이스 테스트, 예전 형식 행을 읽고 다시 저장하는 Repository 계약 테스트(integration 표시)다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| RQ-001 | 로그인한 사용자는 필드 카탈로그를 받고 미인증은 401이다 | RQ-R1, RQ-R2, RQ-UC1 | backend | `web/test_report_routes.py` |
| RQ-002 | 카탈로그는 Deal 29개·Deal Actions 12개를 정해진 key·이름·순서로 담는다 | RQ-R2, RQ-UC1 | backend | `application/test_list_report_fields.py`, `domain/test_report_catalog.py`, `web/test_report_routes.py` |
| RQ-003 | 필드마다 형식별 포맷·연산자·집계와 기본값을 갖는다 | RQ-R3, RQ-UC1 | backend | `application/test_list_report_fields.py`, `domain/test_report_catalog.py`, `web/test_report_routes.py` |
| RQ-004 | 숫자 필드는 포맷이 없고 금액만 원 단위이며 이름이 '금액'이다 | RQ-R3, RQ-R4, RQ-UC1 | backend | `application/test_list_report_fields.py`, `domain/test_report_catalog.py`, `web/test_report_routes.py` |
| RQ-005 | Action 건수는 그룹핑 전용·조건 불가·집계 건수 고정이다 | RQ-R4, RQ-UC1 | backend | `domain/test_report_catalog.py` |
| RQ-006 | 코드 필드는 정적 선택지나 선택지 출처를 알리고 경고 선택지는 둘뿐이다 | RQ-R5, RQ-UC1 | backend | `domain/test_report_catalog.py`, `web/test_report_routes.py` |
| RQ-007 | 한도와 포맷·연산자·집계·상대 기간 어휘를 알린다 | RQ-R6, RQ-UC1 | backend | `application/test_list_report_fields.py`, `domain/test_report_catalog.py`, `web/test_report_routes.py` |
| RQ-008 | 모든 역할이 쓰기 권한 없이 조회하고 미인증은 401, CSRF 헤더가 없으면 403이다 | RQ-R1, RQ-UC3 | backend | `web/test_report_routes.py` |
| RQ-009 | 요청 모양이 틀리거나 모르는 키(예전 최상위 sort 포함)는 422 request-validation이다 | RQ-R7, RQ-UC4 | backend | `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-010 | 정의 위반은 모두 모아 위치·code·문구로 422 invalid-report이고 조회하지 않는다 | RQ-R8, RQ-UC4 | backend | `application/test_run_report.py`, `domain/test_report_parse_conditions.py`, `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-011 | 필드 key는 카탈로그와 정확히 같아야 하고 아니면 unknown-field다 | RQ-R9, RQ-UC4 | backend | `domain/test_report_catalog.py`, `domain/test_report_parse_limits.py` |
| RQ-012 | 컬럼은 1~30개다 | RQ-R10, RQ-UC4 | backend | `domain/test_report_parse_limits.py` |
| RQ-013 | 표시 이름은 앞뒤 공백을 지운 1~100자이고 생략하면 필드 이름이다 | RQ-R11, RQ-UC2 | backend | `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-014 | 포맷은 그 필드의 포맷 목록에서만 고르고 생략하면 기본 포맷이다 | RQ-R12, RQ-UC2 | backend | `domain/test_report_parse_columns.py`, `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-015 | 예전 텍스트·숫자 포맷은 422 format-not-allowed다 | RQ-R12, RQ-UC4 | backend | `domain/test_report_parse_columns.py`, `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-016 | 앞 N자는 null 또는 1~200 정수이고 모든 컬럼에 쓸 수 있다 | RQ-R13, RQ-UC2 | backend | `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-017 | 그룹핑 리포트에서 숫자가 아닌 컬럼은 집계를 골라야 하고 숫자는 기본 집계가 붙는다 | RQ-R14, RQ-UC2 | backend | `domain/test_report_definition_scope.py`, `domain/test_report_parse_columns.py` |
| RQ-018 | 그룹핑할 때 집계는 형식의 허용 목록에서만 고른다 | RQ-R14, RQ-UC2 | backend | `domain/test_report_parse_columns.py` |
| RQ-019 | 그룹핑이 없으면 집계를 줄 수 없고 그룹 컬럼에도 집계를 줄 수 없다 | RQ-R14, RQ-UC4 | backend | `domain/test_report_parse_columns.py` |
| RQ-020 | Action 건수는 그룹핑할 때만 쓰고 그룹·조건에는 쓸 수 없다 | RQ-R14, RQ-R16, RQ-UC4 | backend | `domain/test_report_definition_scope.py`, `domain/test_report_parse_columns.py` |
| RQ-021 | 컬럼 정렬은 asc·desc·없음만 받고 틀린 값은 그 컬럼 위치로 알린다 | RQ-R15, RQ-UC4 | backend | `domain/test_report_parse_limits.py`, `web/test_report_routes.py` |
| RQ-022 | 조건은 20개까지다 | RQ-R16, RQ-UC4 | backend | `domain/test_report_parse_limits.py` |
| RQ-023 | 형식에 맞지 않는 연산자는 operator-not-allowed다 | RQ-R16, RQ-UC4 | backend | `domain/test_report_parse_conditions.py` |
| RQ-024 | 연산자마다 값 모양이 맞아야 하고 아니면 value-invalid와 그 문구다 | RQ-R17, RQ-UC4 | backend | `domain/test_report_parse_conditions.py` |
| RQ-025 | 조건 값 경계(200자·100개·3650일·±2^53−1·1900~2999년)는 허용된다 | RQ-R17, RQ-UC2 | backend | `domain/test_report_parse_conditions.py` |
| RQ-026 | 정적 선택지 필드는 선택지 안의 key만 받고 출처 필드는 값 존재를 검사하지 않는다 | RQ-R18, RQ-UC2 | backend | `domain/test_report_parse_conditions.py` |
| RQ-027 | 결합은 and·or, 행 수 제한은 100·1000·10000만 받는다 | RQ-R19, RQ-UC4 | backend | `domain/test_report_parse_limits.py` |
| RQ-028 | Action 필드가 컬럼에 있으면 Action 1건이 한 행이고 Action 없는 Deal은 빠진다 | RQ-R20, RQ-UC3 | backend | `domain/test_report_definition_scope.py`, `infra/test_report_sql_scope.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-029 | Action 필드가 조건에만 있으면 맞는 Action이 있는 Deal만 한 번씩 나온다 | RQ-R20, RQ-R21, RQ-UC3 | backend | `application/test_run_report.py`, `domain/test_report_definition_scope.py`, `infra/test_report_sql_scope.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-030 | AND면 한 Action이 모든 Action 조건을 만족해야 하고 OR이면 하나면 된다 | RQ-R21, RQ-UC3 | backend | `infra/test_report_sql_scope.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-031 | 조건이 없으면 모든 Deal이 나온다 | RQ-R20, RQ-UC3 | backend | `domain/test_report_definition_scope.py`, `infra/test_report_sql_scope.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-032 | 텍스트·코드·숫자·날짜 연산자는 정해진 뜻으로 거른다 | RQ-R22, RQ-UC3 | backend | `domain/test_report_resolve.py`, `repositories/test_report_query_operators_contract.py` |
| RQ-033 | SQL처럼 보이는 값과 %·_·\는 글자 그대로 찾고 데이터는 그대로다 | RQ-R22, RQ-R34, RQ-UC3 | backend | `repositories/test_report_query_operators_contract.py` |
| RQ-034 | 2^31을 넘는 숫자도 비교한다 | RQ-R22, RQ-UC3 | backend | `repositories/test_report_query_operators_contract.py` |
| RQ-035 | 시각 조건은 업무일 경계의 반열린 구간으로 비교한다 | RQ-R22, RQ-R23, RQ-UC3 | backend | `domain/test_report_resolve.py`, `repositories/test_report_query_buckets_contract.py` |
| RQ-036 | 올해·이번 분기·이번 달·최근 N일·오늘 이전은 업무 날짜로 풀린다 | RQ-R23, RQ-UC3 | backend | `domain/test_report_resolve.py` |
| RQ-037 | 최근 1·3·6개월은 n개월 전 같은 날(없으면 말일)부터 오늘까지다 | RQ-R23, RQ-UC3 | backend | `domain/test_report_parse_conditions.py`, `domain/test_report_resolve.py` |
| RQ-038 | '이번 달' 조건은 서버 업무 날짜의 달만 고르고 응답 today는 업무 날짜다 | RQ-R23, RQ-R36, RQ-UC3 | backend | `application/test_run_report.py` |
| RQ-039 | 경고 조건은 Deals 목록의 경고 필터와 같은 Deal을 고른다 | RQ-R24, RQ-UC3 | backend | `repositories/test_report_query_derived_contract.py` |
| RQ-040 | 경고·체류 일수·최종 업데이트 값은 Deals 목록 값과 같다 | RQ-R25, RQ-UC3 | backend | `repositories/test_report_query_derived_contract.py` |
| RQ-041 | 코드·사용자·연락처 필드는 이름으로 보이고 퇴사자는 (퇴사)가 붙는다 | RQ-R25, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-042 | 날짜 묶음 포맷은 분기·월·연도 경계를 지키고 표시 전용 포맷은 원래 값으로 묶는다 | RQ-R26, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_buckets_contract.py` |
| RQ-043 | 시각 묶음은 업무 시간대 날짜를 따른다 | RQ-R26, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_buckets_contract.py` |
| RQ-044 | 결과 열의 value_type은 형식·포맷·집계로 정해진다 | RQ-R27, RQ-UC3 | backend | `application/test_run_report.py` |
| RQ-045 | 결과 값은 정수·소수 둘째 자리·ISO 날짜·서버 오프셋 시각이다 | RQ-R27, RQ-UC3 | backend | `repositories/test_report_query_rows_contract.py`, `web/test_report_routes.py` |
| RQ-046 | Vendor×분기 금액 합계·건수는 Deals 목록 원장과 같다 | RQ-R33, RQ-R28, RQ-UC3 | backend | `repositories/test_report_query_ledger_contract.py` |
| RQ-047 | Action 행 그룹핑에서 Deal 금액 합계는 Deal당 한 번이고 Action 건수는 Action 수다 | RQ-R29, RQ-UC3 | backend | `application/test_run_report.py`, `domain/test_report_definition_scope.py`, `infra/test_report_sql_grouping.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-048 | Users count·체류 일수·Deal 필드 건수도 Deal당 한 번이고 Action 필드 건수는 Action마다다 | RQ-R29, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_scope_contract.py` |
| RQ-049 | 한 Deal이 두 그룹에 있으면 그룹마다 한 번씩 센다 | RQ-R29, RQ-UC3 | backend | `repositories/test_report_query_scope_contract.py` |
| RQ-050 | 고유 건수는 이름이 아니라 key로 센다 | RQ-R29, RQ-R28, RQ-UC3 | backend | `repositories/test_report_query_rows_contract.py` |
| RQ-051 | 컬럼 정렬은 컬럼 순서가 우선순위이고 NULL은 맨 뒤, 같으면 Deal code 순이다 | RQ-R30, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `infra/test_report_sql_sort.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-052 | Status 그룹은 코드 순서이고 그룹핑 리포트는 집계 컬럼으로도 정렬한다 | RQ-R30, RQ-R28, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `infra/test_report_sql_sort.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-053 | Action 행의 동률은 수행일·id 순이다 | RQ-R30, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `infra/test_report_sql_sort.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-054 | 행 수 제한은 정렬 뒤 적용되고 total_count는 제한 전 행·그룹 수다 | RQ-R31, RQ-UC3 | backend | `application/test_run_report.py`, `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-055 | 그룹핑 리포트의 합계 행은 같은 조건 전체를 그룹 없이 한 번 더 집계한다 | RQ-R32, RQ-UC3 | backend | `application/test_run_report.py`, `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py`, `web/test_report_routes.py` |
| RQ-056 | 합계 행의 고유 건수는 전체 고유 수이고 Action 행에서도 Deal당 한 번이다 | RQ-R32, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-057 | 그룹핑이 없거나 그룹 컬럼뿐이면 합계 행은 null이다 | RQ-R32, RQ-UC3 | backend | `application/test_run_report.py`, `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-058 | 사용자 값과 행 수 제한은 바인딩 파라미터이고 LIKE 문자는 이스케이프된다 | RQ-R34 | backend | `infra/test_report_sql_binding.py` |
| RQ-059 | 표시 SQL은 입력 값이 보이고 render_sql과 run의 SQL이 같으며 render는 DB를 쓰지 않는다 | RQ-R34, RQ-UC3 | backend | `infra/test_report_render_sql.py`, `infra/test_report_sql_catalog.py`, `repositories/test_report_query_rows_contract.py`, `repositories/test_report_render_sql_contract.py` |
| RQ-060 | 카탈로그의 모든 필드·연산자가 SQL이 되고 필요한 JOIN만 붙는다 | RQ-R34 | backend | `infra/test_report_sql_catalog.py`, `infra/test_report_sql_scope.py` |
| RQ-061 | 조회는 읽기 전용·10초 제한이고 넘으면 503 report-timeout 고정 문구다 | RQ-R35, RQ-UC4 | backend | `application/test_run_report.py`, `infra/test_read_only_guard.py`, `infra/test_report_timeout_source.py`, `web/test_report_openapi.py`, `web/test_report_routes.py` |
| RQ-062 | 응답 열은 적용된 포맷·단위·앞 N자·집계를 설명하고 금액은 원 그대로다 | RQ-R36, RQ-UC3 | backend | `application/test_run_report.py`, `web/test_report_routes.py` |
| RQ-063 | 조회는 업무 날짜·오프셋·경고 기준을 정하고 상대 조건을 푼 정의를 Port에 넘긴다 | RQ-R36, RQ-R23, RQ-UC3 | backend | `application/test_run_report.py`, `domain/test_report_resolve.py` |
| RQ-064 | openapi에 두 경로의 오류·포맷·단위·컬럼 정렬 계약이 있다 | RQ-R37 | backend | `web/test_report_openapi.py` |
| RQ-065 | 앞 N자는 SQL에 영향이 없고 그룹핑은 전체 값 기준이다 | RQ-R13, RQ-R28, RQ-UC3 | backend | `infra/test_report_sql_grouping.py`, `repositories/test_report_query_rows_contract.py` |
| RQ-066 | 카탈로그를 읽는 동안 로딩 문구, 실패하면 오류와 다시 시도다 | RQ-R38, RQ-UC1 | frontend | `features/reports/designer/ReportDesignerPage.fields.test.tsx` |
| RQ-067 | 첫 화면은 제목·초기화·빈 안내·두 탭이고 저장 표시·조회 버튼은 꺼져 있다 | RQ-R38, RQ-R39, RQ-R48, RQ-UC1 | frontend | `features/reports/designer/ReportDesignerPage.fields.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-068 | 탭은 버튼·화살표로 바뀌고 숨은 패널을 유지해 설계·페이지·합계 행 선택이 남는다 | RQ-R39, RQ-UC3 | frontend | `features/reports/designer/DesignerTabs.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx` |
| RQ-069 | 필드 목록은 두 묶음이고 이름 부분 일치로 거른다 | RQ-R40, RQ-UC1 | frontend | `features/reports/designer/ReportDesignerPage.fields.test.tsx` |
| RQ-070 | "+조건"은 조건에 쓸 수 있는 필드에만 있다 | RQ-R40, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.fields.test.tsx` |
| RQ-071 | 필드를 누르면 칩이 생기고 같은 필드는 확인 뒤에만 한 번 더 들어간다 | RQ-R40, RQ-R42, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.columns.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-072 | 칩 순서는 끌어서 놓기와 Alt+←/→로 바꾼다 | RQ-R42, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.columns.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-073 | 데이터 범위 표시는 설계에 따라 행 단위·EXISTS·Deal당 한 번을 알린다 | RQ-R41, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.scope.test.tsx`, `features/reports/designer/state/scope.test.ts` |
| RQ-074 | 컬럼 설정은 한 줄에 이름·표시 이름·포맷·앞 N자·그룹핑·집계·정렬을 보인다 | RQ-R43, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.columns.test.tsx`, `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.settings.test.tsx`, `features/reports/designer/state/columnRules.test.ts`, `features/reports/designer/state/designerState.test.ts` |
| RQ-075 | 그룹핑을 켜고 끄면 집계가 자동으로 채워지고 비워진다 | RQ-R44, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.settings.test.tsx`, `features/reports/designer/state/columnRules.test.ts` |
| RQ-076 | 칩 배지는 그룹·집계·포맷·앞 N자·정렬 우선순위·그룹핑할 때만을 보인다 | RQ-R42, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.settings.test.tsx` |
| RQ-077 | 앞 N자를 켜면 N이 20이고 잘못된 N은 요청 없이 안내한다 | RQ-R43, RQ-R47, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.settings.test.tsx`, `features/reports/designer/state/columnRules.test.ts`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-078 | 조건 행 추가·필드 변경·삭제·한도와 빈 조건 안내 | RQ-R45, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/columnRules.test.ts`, `features/reports/designer/state/designerState.test.ts` |
| RQ-079 | 조건 결합 라디오가 접속어와 요청의 combine을 바꾼다 | RQ-R45, RQ-R47, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-080 | 목록 값 선택지는 출처의 순서·구분을 따르고 선택을 요약한다 | RQ-R46, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx` |
| RQ-081 | 연산자 모양마다 맞는 값 입력 칸을 보인다 | RQ-R46, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/columnRules.test.ts`, `features/reports/designer/state/designerState.test.ts` |
| RQ-082 | 금액 조건은 원 단위로 입력하고 입력한 원 그대로 보낸다 | RQ-R46, RQ-R47, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/columnRules.test.ts`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-083 | 최근 n개월은 일수 없이 보내고 일수 칸을 숨긴다 | RQ-R46, RQ-R47, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-084 | 날짜는 yyyymmdd로 입력해 ISO로 보내고 틀린 날짜는 요청 없이 그 칸에 안내한다 | RQ-R46, RQ-R47, RQ-UC4 | frontend | `features/reports/designer/ReportDesignerPage.conditions.test.tsx`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-085 | 읽을 수 없는 입력이 있으면 요청을 보내지 않고 칸 아래에 문구를 보인다 | RQ-R47, RQ-UC4 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-086 | 조회 요청은 설계대로이고 설계가 비운 키는 보내지 않는다 | RQ-R47, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.errors.test.tsx`, `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/state/designerState.test.ts`, `features/reports/designer/state/toRequest.test.ts` |
| RQ-087 | 최대 행은 100·1,000·10,000 중 고르고 기본은 1,000이다 | RQ-R48, RQ-UC2 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-088 | 조회 중에는 "조회 중…"이고 두 번째 조회를 막는다 | RQ-R48, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx` |
| RQ-089 | 조회가 성공하면 결과 탭으로 옮겨 결과 표를 보인다 | RQ-R49, RQ-R50, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx` |
| RQ-090 | 정의 위반이면 작성 탭에 머물며 고칠 곳 목록과 칸별 표시, 탭 이름 수를 보인다 | RQ-R49, RQ-R39, RQ-UC4 | frontend | `features/reports/designer/DesignerTabs.test.tsx`, `features/reports/designer/ReportDesignerPage.errors.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx`, `features/reports/designer/state/issues.test.ts` |
| RQ-091 | 위치를 모르는 위반은 요약에만 보인다 | RQ-R49, RQ-UC4 | frontend | `features/reports/designer/ReportDesignerPage.errors.test.tsx`, `features/reports/designer/state/issues.test.ts` |
| RQ-092 | 고친 항목·지운 컬럼의 위반 표시는 사라지고 성공하면 실패 알림이 사라진다 | RQ-R49, RQ-UC4 | frontend | `features/reports/designer/ReportDesignerPage.errors.test.tsx`, `features/reports/designer/state/issues.test.ts` |
| RQ-093 | 시간 초과·연결 끊김·그 밖의 오류는 서버 문구를 보이고 이전 결과를 남긴다 | RQ-R49, RQ-UC4 | frontend | `features/reports/designer/ReportDesignerPage.errors.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx` |
| RQ-094 | 표 타일은 결과 전 안내, 총 행·조회 시간, 잘림 표시와 100행 페이지를 보인다 | RQ-R50, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx` |
| RQ-095 | 합계 행은 합계가 있는 결과에서만 켜고 새 결과에서 꺼지며 Deal당 한 번 안내가 붙는다 | RQ-R50, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx` |
| RQ-096 | 숫자는 천 단위·소수 없이 오른쪽 정렬, 금액은 원과 머리글 (원), 빈 값은 —이다 | RQ-R51, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/format/formatCell.test.ts` |
| RQ-097 | 날짜·시각은 서버 오프셋 벽시계와 앱 시계 기준 상대 표기·요일로 보인다 | RQ-R51, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/format/formatCell.test.ts` |
| RQ-098 | 앞 N자는 칸만 자르고 title에 전체 값을 두며 합계 행은 자르지 않는다 | RQ-R51, RQ-R50, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/format/formatCell.test.ts` |
| RQ-099 | 조회 뒤 설계를 바꾸면 결과 탭에 다시 조회 안내가 보이고 다음 조회에서 사라진다 | RQ-R52, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.run.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-100 | 생성 SQL은 조회 전 안내, 조회 뒤 최신 SQL을 결과 탭에 읽기 전용으로 보인다 | RQ-R53, RQ-UC3 | frontend | `features/reports/designer/ReportDesignerPage.sql.test.tsx` |
| RQ-101 | 바뀐 설계에서 다른 화면 링크를 누르면 떠날지 묻는다 | RQ-R54, RQ-UC5 | frontend | `features/reports/designer/ReportDesignerPage.leave.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-102 | 초기화는 바뀐 설계면 확인 뒤 모두 지우고 아니면 바로 지운다 | RQ-R54, RQ-UC5 | frontend | `features/reports/designer/ReportDesignerPage.leave.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RQ-103 | 게이트웨이는 카탈로그·조회를 snake_case↔camelCase로 바꾼다 | RQ-R55 | frontend | `gateway/http/reports.test.ts` |
| RQ-104 | 게이트웨이는 invalid-report 위반을 reportErrors로 옮기고 다른 오류는 PL 규칙대로 바꾼다 | RQ-R55 | frontend | `gateway/http/reports.test.ts` |
| RQ-105 | 데이터 훅은 카탈로그를 한 번만 읽고 조회는 무효화하지 않으며 실패를 분류한다 | RQ-R55 | frontend | `data/reports.test.tsx` |
| RQ-106 | Fake 게이트웨이는 흉내 내는 위반을 서버와 같은 code·위치·문구로 내고 합성 결과를 준다 | RQ-R56 | frontend | `gateway/contract/reports.contract.ts`, `test/fake/gateway/reports.test.ts` |
| RQ-107 | Fake와 계약: 모든 역할이 카탈로그·조회를 쓰고 미인증은 401이다 | RQ-R56, RQ-R1 | frontend | `gateway/contract/reports.contract.ts`, `test/fake/gateway/reports.test.ts` |
| RQ-108 | 저장 정의 JSON은 조회 요청과 같은 모양이고 다시 읽으면 같은 정의다 | RQ-R57, RQ-UC3 | backend | `domain/test_report_stored.py` |
| RQ-109 | 예전 텍스트·코드 포맷은 포맷 없음으로, 예전 앞 N자 포맷의 N은 앞 N자 옵션으로 읽힌다 | RQ-R57, RQ-UC3 | backend | `application/test_report_legacy_definition.py`, `domain/test_report_stored.py`, `repositories/test_saved_report_legacy_definition.py`, `repositories/test_report_legacy_definition_run_contract.py` |
| RQ-110 | 예전 숫자 포맷은 포맷 없음으로 읽히고 값은 집계 그대로다 | RQ-R57, RQ-UC3 | backend | `application/test_report_legacy_definition.py`, `domain/test_report_stored.py`, `repositories/test_saved_report_legacy_definition.py`, `repositories/test_report_legacy_definition_run_contract.py` |
| RQ-111 | 예전 최상위 정렬은 그 컬럼의 정렬로 읽혀 같은 순서로 실행된다 | RQ-R57, RQ-R30, RQ-UC3 | backend | `application/test_report_legacy_definition.py`, `domain/test_report_stored.py`, `repositories/test_saved_report_legacy_definition.py`, `repositories/test_report_legacy_definition_run_contract.py` |
| RQ-112 | 읽을 수 없는 모양은 stored-invalid이고 값 위반은 읽을 때가 아니라 실행 때 알린다 | RQ-R57, RQ-UC4 | backend | `domain/test_report_stored.py` |
| RQ-113 | 카탈로그에서 최종 업데이트·Status 진입일·수행일·종료일은 date 형식이고 기본 포맷 ymd이며 ymd_hm이 없다 | RQ-R58, RQ-R2 | backend | `application/test_list_report_fields.py`, `domain/test_report_catalog.py`, `domain/test_report_resolve.py`, `repositories/test_report_query_rows_contract.py`, `web/test_report_routes.py` |
| RQ-114 | 네 날짜 필드에 ymd_hm을 요청하면 422 format-not-allowed다 | RQ-R58, RQ-R12 | backend | `domain/test_report_parse_columns.py`, `web/test_report_routes.py` |
| RQ-115 | 저장 정의의 네 날짜 필드 ymd_hm은 읽을 때 ymd로 바뀐다 | RQ-R58, RQ-R57 | backend | `domain/test_report_stored.py` |
| RQ-116 | 저장 정의의 예전 key deal.solution은 읽을 때 deal.product로 바뀌어 실행된다 | RQ-R57, RQ-R59, RQ-UC3 | backend | `domain/test_report_stored.py::test_the_old_solution_key_is_read_as_the_product_key_in_columns_and_conditions`, `domain/test_report_stored.py::test_the_product_key_and_other_fields_are_kept_when_read`, `application/test_report_legacy_definition.py::test_legacy_solution_key_opens_and_runs_as_the_product_field`, `repositories/test_report_legacy_definition_run_contract.py::test_legacy_solution_key_runs_as_the_product_field` |
| RQ-117 | 조회·저장 요청의 deal.solution은 unknown-field 422다 | RQ-R59, RQ-R9, RQ-UC4 | backend | `web/test_report_routes.py::test_the_old_solution_key_is_an_unknown_field_and_nothing_is_run`, `web/test_saved_report_validation.py::test_the_old_solution_key_is_422_unknown_field_and_nothing_is_saved` |
| RQ-118 | action.comment는 그 Action의 Comment를 작성 순 줄바꿈으로 이어 붙이고, 없으면 비어 있음 조건에 걸린다 | RQ-R60, RQ-UC1 | backend | `domain/test_report_definition_scope.py`, `repositories/test_report_query_comment_contract.py` |
| RQ-119 | 조회·저장 요청의 action.memo는 unknown-field 422다 | RQ-R60, RQ-R9, RQ-UC1 | backend | `web/test_report_routes.py`, `web/test_saved_report_validation.py` |
| RQ-120 | 저장 정의의 action.memo는 읽을 때 action.comment로 바뀐다 | RQ-R57, RQ-R60, RQ-UC1 | backend | `application/test_report_legacy_definition.py`, `domain/test_report_stored.py` |
| RQ-121 | deal.comment는 Action 연결 여부와 무관하게 그 Deal의 모든 Comment를 작성 순으로 이어 붙이고 다른 Deal 것은 섞이지 않는다 | RQ-R61, RQ-UC1 | backend | `repositories/test_report_query_comment_contract.py` |
| RQ-122 | deal.comment만 쓴 리포트는 Deal 범위(action_filter none)로 Deal당 1행이다 | RQ-R61, RQ-UC1 | backend | `domain/test_report_definition_scope.py`, `repositories/test_report_query_comment_contract.py` |
| RQ-123 | Action 행 범위 그룹핑에서 deal.comment 건수는 Deal당 한 번 센다 | RQ-R61, RQ-UC1 | backend | `repositories/test_report_query_comment_contract.py` |
| RQ-124 | deal.comment contains 조건은 Deal Comment·Action Comment 어느 쪽 본문에 있어도 그 Deal을 고른다 | RQ-R61, RQ-UC1 | backend | `repositories/test_report_query_comment_contract.py` |
| RQ-125 | 바뀐 설계에서 브라우저 뒤로 가기를 하면 떠날지 묻고 머물기면 주소·설계가 그대로다 | RQ-R54, RQ-UC5 | frontend | `features/reports/designer/ReportDesignerPage.leave.test.tsx` |
| RQ-126 | 뒤로·앞으로 가기에서 떠나기를 고르면 멈춘 이동을 마저 해 이전·다음 화면으로 간다 | RQ-R54, RQ-UC5 | frontend | `features/reports/designer/ReportDesignerPage.leave.test.tsx` |
| RQ-127 | 바뀌지 않았거나 되돌린 설계의 뒤로 가기와 링크로 떠난 이동은 묻지 않는다 | RQ-R54, RQ-UC5 | frontend | `features/reports/designer/ReportDesignerPage.leave.test.tsx` |

### RQ-001 로그인한 사용자는 필드 카탈로그를 받고 미인증은 401이다
- Given VIEWER가 로그인함
- When `GET /reports/fields`를 부르고, 로그인하지 않은 채 같은 경로를 부른다
- Then 첫 요청은 200이고 본문 키는 정확히 `limits`·`entities`·`formats`·`operators`·`aggregates`·`relative_periods`·`fields`, `fields` key 순서는 카탈로그 순서, `entities` key는 `deal`·`action`·`comment`이며, 둘째 요청은 401 `unauthenticated`다

### RQ-002 카탈로그는 Deal 29개·Deal Actions 12개·Comments 4개를 담는다
- When 카탈로그를 읽는다
- Then 필드 45개의 키·이름·순서는 2.2 표와 같고, 각 필드의 키 접두어가 `entity`와 같다.

### RQ-003 필드마다 형식별 포맷·연산자·집계와 기본값을 갖는다
- When 카탈로그를 읽는다
- Then `deal.name`은 포맷 없음·연산자 text 5개·집계 count·count_distinct, `deal.expected_close`는 포맷 6개(기본 ymd), `deal.created_at`은 포맷 7개(기본 ymd_hm), `deal.status_days`는 기본 집계 avg·`deal_number: true`, `deal.users`는 `deal_number: true`, `deal.expected_close`는 `deal_number: false`다

### RQ-004 숫자 필드는 포맷이 없고 금액만 원 단위이며 이름이 '금액'이다
- When VIEWER가 카탈로그를 읽는다
- Then `deal.amount`·`deal.users`·`deal.status_days`·`action.count`의 (`formats`, `default_format`)는 모두 (`[]`, null)이고, `unit`이 있는 필드는 `deal.amount: "krw"` 하나이며 그 이름은 "금액", 기본 집계는 sum이다

### RQ-005 Action 건수는 그룹핑 전용·조건 불가·집계 건수 고정이다
- When 카탈로그를 읽는다
- Then `action.count`는 `operators: []`·`aggregates: []`·`default_aggregate: "count"`·`groupable: false`·`filterable: false`·`requires_grouping: true`·`deal_number: false`이고, `requires_grouping: true`인 필드는 이것뿐이다

### RQ-006 코드 필드는 정적 선택지나 선택지 출처를 알리고 경고 선택지는 둘뿐이다
- When 카탈로그를 읽는다
- Then `deal.forecast_outcome` 선택지는 open/Open·won/Won·lost/Lost, `deal.risk`는 overdue/기한초과·stale/미업데이트 둘뿐이고 둘 다 `options_source` null이며, `deal.vendor`는 (`id`, `vendors`), `deal.status`는 (`key`, `status_codes`), `deal.bant_budget`은 (`id`, `bant_labels`, category `budget`), `action.type`은 (`id`, `action_types`), `deal.owner`는 (`id`, `users`)이고 이들의 `options`는 null이다

### RQ-007 한도와 포맷·연산자·집계·상대 기간 어휘를 알린다
- When VIEWER가 카탈로그를 읽는다
- Then `limits`는 RQ-R6 값과 같고, `formats` key는 ymd·ymd_hm·year·quarter·month·weekday·relative 순서이며 `affects_query`가 true인 것은 ymd·year·quarter·month뿐이고 예전 포맷 key가 없으며, `between`의 값 모양은 range, `relative_periods`는 최근 1개월부터 오늘 이전까지 8개 순서이고 `needs_days`는 last_n_days만 true다

### RQ-008 모든 역할이 쓰기 권한 없이 조회하고 미인증은 401, CSRF 헤더가 없으면 403이다
- Given KIM이 담당자인 Deal "Visible" 1건
- When VIEWER·KIM·ROOT가 각각 `POST /reports/query` `{columns: [{field: "deal.name"}]}`를 부르고, 로그인하지 않은 채 부르고, VIEWER가 `X-Requested-With` 없이 부른다
- Then 세 역할은 200이고 `rows`가 `[["Visible"]]`이며, 미인증은 401 `unauthenticated`, 헤더 없는 요청은 403 `csrf`다

### RQ-009 요청 모양이 틀리거나 모르는 키(예전 최상위 sort 포함)는 422 request-validation이다
- When 본문 `{}`, `columns`가 null·문자열·문자열 목록, `field` 없는 컬럼, 숫자 `field`, 컬럼의 모르는 키, 최상위 모르는 키, 문자열 `conditions`, `operator` 없는 조건, 최상위 `sort`(`{column: 0, direction: "asc"}`·`{direction: "asc"}`·null), 컬럼 `sort`가 1·true·`{}`, 최상위 `group`으로 각각 조회한다
- Then 모두 422 `request-validation`이다

### RQ-010 정의 위반은 모두 모아 위치·code·문구로 422 invalid-report이고 조회하지 않는다
- Given 컬럼 `[deal.code, deal.password]`, 조건 `[{field: "deal.name", operator: "gt", value: "x"}]`
- When KIM이 조회한다
- Then 422 `invalid-report`이고 `errors`의 (location, code)는 차례로 (`["columns", 1, "field"]`, `unknown-field`), (`["conditions", 0, "operator"]`, `operator-not-allowed`)이며 모든 항목에 한국어 `message`가 있고 `detail`은 첫 `message`와 같으며, 조회 Port는 한 번도 불리지 않는다

### RQ-011 필드 key는 카탈로그와 정확히 같아야 하고 아니면 unknown-field다
- When 컬럼 field를 `DEAL.CODE`, ` deal.code`, `deal.code `, `deal.nope`, 60자 key로, 조건 field를 `deal.nope`(연산자 `zzz`)로 각각 조회한다
- Then 각 위반은 `["columns", 0, "field"]`(조건은 `["conditions", 0, "field"]`) `unknown-field` "허용되지 않은 필드입니다: <key 앞 50자>"이고, 그 컬럼·조건에는 다른 위반(연산자 등)이 없다

### RQ-012 컬럼은 1~30개다
- When 컬럼 0개, 31개, 1개, 30개로 각각 검증한다
- Then 0개·31개는 `["columns"]` `columns-count` "컬럼은 1개 이상 30개 이하로 지정하세요" 하나뿐이고, 1개·30개는 통과한다

### RQ-013 표시 이름은 앞뒤 공백을 지운 1~100자이고 생략하면 필드 이름이다
- When `deal.amount` 컬럼의 label을 생략, "  금액 합계  ", 정확히 100자, "", "   ", 101자, NUL 포함으로 각각 검증한다
- Then 생략은 "금액", "  금액 합계  "는 "금액 합계", 100자는 그대로 통과하고, 나머지는 `["columns", 0, "label"]` `label-invalid` "표시 이름은 공백이 아닌 100자 이하여야 합니다"다

### RQ-014 포맷은 그 필드의 포맷 목록에서만 고르고 생략하면 기본 포맷이다
- When `deal.name` 포맷 ymd, `deal.amount` 포맷 quarter, `deal.expected_close` 포맷 ymd_hm, `deal.created_at` 포맷 ymd_hm, 포맷을 생략한 `deal.expected_close`·`deal.created_at`·`deal.name`으로 각각 검증한다
- Then `deal.name`·`deal.amount`는 `["columns", 0, "format"]` `format-not-allowed` "이 필드는 포맷을 고를 수 없습니다", `deal.expected_close` ymd_hm은 같은 위치·code의 "이 필드에 쓸 수 없는 포맷입니다. 가능: ymd, year, quarter, month, weekday, relative"이고, `deal.created_at` ymd_hm은 통과하며, 생략은 차례로 ymd·ymd_hm·null이다

### RQ-015 예전 텍스트·숫자 포맷은 422 format-not-allowed다
- When KIM이 `deal.amount` 포맷 krw_thousand(그리고 thousands·krw_million·decimal1·percent_share)로, `deal.name` 포맷 as_is(그리고 prefix·name·key)로 조회한다
- Then 각각 422 `invalid-report`이고 `errors`는 (`["columns", 0, "format"]`, `format-not-allowed`) 하나다

### RQ-016 앞 N자는 null 또는 1~200 정수이고 모든 컬럼에 쓸 수 있다
- When 텍스트·숫자·날짜·시각 컬럼과 그룹 컬럼·집계 컬럼에 `prefix_length` 1과 200을, 그리고 0·201·1.5·"10"·true를 각각 준다
- Then 1·200은 통과하고 생략은 null이며, 0·201·1.5·"10"·true는 `["columns", 0, "prefix_length"]` `value-invalid` "앞 N자의 N은 1~200의 정수여야 합니다"다

### RQ-017 그룹핑 리포트에서 숫자가 아닌 컬럼은 집계를 골라야 하고 숫자는 기본 집계가 붙는다
- Given 첫 컬럼 `deal.vendor`(group)
- When 둘째 컬럼을 집계 없는 `deal.code`, `deal.amount`, `deal.users`, `deal.status_days`로 각각 조회·검증한다
- Then `deal.code`는 `["columns", 1, "aggregate"]` `aggregate-required` "그룹핑할 때 이 컬럼은 집계(건수 또는 고유 건수)를 골라야 합니다. 그룹핑하거나 빼세요"이고, 금액·Users count는 sum, 체류 일수는 avg가 적용된다

### RQ-018 그룹핑할 때 집계는 형식의 허용 목록에서만 고른다
- Given 첫 컬럼 `deal.vendor`(group)
- When 둘째 컬럼을 `deal.amount`의 sum·avg·min·max·count·"median", `deal.name`의 count·count_distinct·sum으로 각각 검증한다
- Then 금액 sum·avg·min·max와 이름 count·count_distinct는 통과하고, 금액 count·"median"은 `aggregate-not-allowed` "그룹핑할 때 이 컬럼은 합계 또는 평균 또는 최소 또는 최대만 고를 수 있습니다. 그룹핑하거나 빼세요", 이름 sum은 같은 code의 "그룹핑할 때 이 컬럼은 건수 또는 고유 건수만 고를 수 있습니다. 그룹핑하거나 빼세요"다

### RQ-019 그룹핑이 없으면 집계를 줄 수 없고 그룹 컬럼에도 집계를 줄 수 없다
- When `[deal.amount(aggregate sum)]`, `[deal.vendor(group, aggregate count), deal.amount]`, `[deal.name, deal.amount]`를 각각 검증한다
- Then 첫째는 `["columns", 0, "aggregate"]` `aggregate-not-allowed` "그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요", 둘째는 같은 위치·code의 "그룹 컬럼에는 집계를 지정할 수 없습니다", 셋째는 통과하고 모든 컬럼 집계가 null이다

### RQ-020 Action 건수는 그룹핑할 때만 쓰고 그룹·조건에는 쓸 수 없다
- When `[action.count]`, `[deal.vendor(group), action.count]`(집계 생략·count·sum), `[action.count(group)]`, 조건 `action.count`로 각각 검증한다
- Then 첫째는 `["columns", 0]` `grouping-required` "이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요", 생략·count는 통과(집계 count), sum은 `aggregate-not-allowed`, 그룹은 `["columns", 0, "group"]` `group-not-allowed` "이 필드는 그룹핑할 수 없습니다", 조건은 `["conditions", 0, "field"]` `not-filterable` "이 필드는 조건에 쓸 수 없습니다"다

### RQ-021 컬럼 정렬은 asc·desc·없음만 받고 틀린 값은 그 컬럼 위치로 알린다
- When 정렬 asc·desc·null·생략, `[deal.name, deal.vendor(sort "up")]`, `[deal.name(sort "ASC"), deal.vendor(sort "")]`, 그룹 컬럼·집계 컬럼의 desc로 각각 검증한다
- Then asc·desc·null·생략과 그룹·집계 컬럼 정렬은 통과하고, "up"은 `["columns", 1, "sort"]` `sort-invalid` "정렬은 asc 또는 desc만 쓸 수 있습니다", "ASC"·""는 위반 둘(각 컬럼 위치)이다

### RQ-022 조건은 20개까지다
- When 조건 0개, 20개, 21개로 검증한다
- Then 0·20개는 통과하고 21개는 `["conditions"]` `conditions-count` "조건은 20개까지 지정할 수 있습니다" 하나다

### RQ-023 형식에 맞지 않는 연산자는 operator-not-allowed다
- When `deal.name` gt, `deal.amount` contains, `deal.expected_close` eq, `deal.status` between, `deal.owner` contains로 각각 검증한다
- Then 모두 `["conditions", 0, "operator"]` `operator-not-allowed` "이 필드에 쓸 수 없는 연산자입니다. 가능: <그 필드 연산자 key 목록>"이고 값은 검사하지 않는다

### RQ-024 연산자마다 값 모양이 맞아야 하고 아니면 value-invalid와 그 문구다
- When `deal.name` is_empty 값 "x", contains 5, contains "   ", contains "  미팅 "; `deal.vendor` in [] · in ["1"]; `deal.status` in [""]; `deal.amount` gt "10" · gt 1.5 · gt true · between [1] · between [5, 1]; `deal.expected_close` between ["2026-10-31", "2026-10-01"] · before "2026/10/01" · before "2026-02-30" · before "1899-12-31" · relative "this_year" · relative {period: "next_year"} · relative {period: "this_year", days: 3} · relative {period: "last_n_days", days: 0}로 각각 검증한다
- Then contains "  미팅 "만 통과해 값이 "미팅"이 되고, 나머지는 `["conditions", 0, "value"]` `value-invalid`이며 문구는 차례로 RQ-R17의 "이 연산자에는 값이 필요하지 않습니다", "검색어를 문자열로 입력하세요", "검색어는 공백이 아닌 200자 이하여야 합니다", "선택 값은 1개 이상 100개 이하의 목록이어야 합니다", "선택 값은 양의 정수 id여야 합니다", "선택 값은 비어 있지 않은 문자열이어야 합니다", 정수 문구 셋, "범위는 시작과 끝 두 값이 필요합니다", "범위의 시작이 끝보다 클 수 없습니다", "범위의 시작이 끝보다 늦을 수 없습니다", "날짜는 YYYY-MM-DD 형식으로 입력하세요", "존재하지 않는 날짜입니다", "날짜는 1900-01-01부터 2999-12-31 사이여야 합니다", "상대 기간은 period(와 days)를 가진 객체여야 합니다", "알 수 없는 상대 기간입니다", "days는 최근 N일에서만 쓸 수 있습니다", "최근 N일의 N은 1~3650의 정수여야 합니다"다

### RQ-025 조건 값 경계(200자·100개·3650일·±2^53−1·1900~2999년)는 허용된다
- When 텍스트 200자, 목록 100개, last_n_days 3650, 숫자 9007199254740991과 −9007199254740991, 날짜 1900-01-01과 2999-12-31, `{period: "last_1_month"}`·`last_3_months`·`last_6_months`(days 없이)로 각각 검증한다
- Then 모두 통과한다

### RQ-026 정적 선택지 필드는 선택지 안의 key만 받고 출처 필드는 값 존재를 검사하지 않는다
- When `deal.forecast_outcome` in ["open", "won", "lost"], in ["closed"], `deal.risk` in ["overdue_stale"], `deal.status` in ["no_such_key"]로 각각 검증한다
- Then 첫째와 `deal.status`는 통과하고, "closed"는 `value-invalid` "선택지에 없는 값입니다. 가능: open, won, lost", "overdue_stale"은 "선택지에 없는 값입니다. 가능: overdue, stale"이다

### RQ-027 결합은 and·or, 행 수 제한은 100·1000·10000만 받는다
- When combine "and"·"or"·"AND"·"xor"·1과 row_limit 100·1000·10000·7·"1000"·true, 그리고 둘 다 생략으로 각각 검증한다
- Then and·or와 100·1000·10000은 통과하고 생략은 and·1000이며, 그 밖의 combine은 `["combine"]` `combine-invalid` "조건 결합은 and 또는 or만 쓸 수 있습니다", 그 밖의 row_limit은 `["row_limit"]` `row-limit-invalid` "행 수 제한은 100, 1000, 10000 중 하나여야 합니다"다

### RQ-028 Action 필드가 컬럼에 있으면 Action 1건이 한 행이고 Action 없는 Deal은 빠진다
- Given Deal A(Action 2건), Deal B(Action 없음)
- When 컬럼 `[deal.code, action.action]`으로 조회한다
- Then 행은 A의 Action 2건뿐이고 B가 없으며 `row_scope` "action", `action_filter` "join"이다(`action.count` 컬럼도 Action 행 범위다)

### RQ-029 Action 필드가 조건에만 있으면 맞는 Action이 있는 Deal만 한 번씩 나온다
- Given "Met"(유형 미팅 Action 2건), "Never"(Action 없음)
- When 컬럼 `[deal.name]`, 조건 `action.type in [미팅 id]`로 조회한다
- Then `rows`는 `[["Met"]]`이고 `row_scope` "deal", `action_filter` "exists"다

### RQ-030 AND면 한 Action이 모든 Action 조건을 만족해야 하고 OR이면 하나면 된다
- Given Deal X: Action(미팅, 진행사항 "견적")·Action(전화, 진행사항 "데모"), Deal Y: Action(미팅, "데모"), Deal Z: Action 없음, 이름 "Zed"
- When 컬럼 `[deal.name]`에 조건 `action.type in [미팅]`·`action.action contains "데모"`를 AND로, OR로 조회하고, 조건 `deal.name equals "Zed"`·`action.type in [미팅]`을 OR로 조회한다
- Then AND는 Y만(X는 두 조건을 한 Action이 함께 만족하지 않음), OR은 X·Y, 마지막은 X·Y·Z이고 각 Deal은 한 번씩이다

### RQ-031 조건이 없으면 모든 Deal이 나온다
- Given Deal 3건(Action 유무 섞임)
- When 컬럼 `[deal.code]`, 조건 없이 조회한다
- Then 3건이 모두 Deal code 순으로 나온다

### RQ-032 텍스트·코드·숫자·날짜 연산자는 정해진 뜻으로 거른다
- Given 이름 "Alpha Deal"·"alphabet"·"Beta", 그중 Vendor IBM이고 Product가 빈 Deal 하나(나머지는 Vendor SAP), 금액 100·200·300, Expected Close 2026-10-01·2026-10-15·2026-10-31인 Deal들
- When `deal.name contains "ALPHA"`, `starts_with "alpha"`, `equals "beta"`, `deal.product is_empty`, `deal.vendor not_in [SAP]`, `deal.amount between [100, 200]`, `gt 200`, `deal.expected_close before "2026-10-15"`, `after "2026-10-15"`, `between ["2026-10-01", "2026-10-15"]`, 그리고 두 조건 AND·OR로 각각 조회한다
- Then contains는 앞의 둘, starts_with도 앞의 둘, equals는 "Beta", is_empty와 not_in은 그 IBM·빈 Product Deal만이고, between은 100·200, gt는 300, before는 10-01만, after는 10-31만, 날짜 between은 10-01·10-15이며, OR은 어느 하나, AND는 모두 맞는 Deal이다

### RQ-033 SQL처럼 보이는 값과 %·_·\는 글자 그대로 찾고 데이터는 그대로다
- Given Deal "Safe", "50%_off\x"
- When `deal.name contains "'; drop table deals; --"`로 조회한 뒤 조건 없이 다시 조회하고, `contains "%_"`, `contains "\"`로 조회한다
- Then 첫 조회는 0행, 다시 조회하면 두 Deal이 그대로 있고, `%_`·`\`는 "50%_off\x"만 찾는다

### RQ-034 2^31을 넘는 숫자도 비교한다
- Given 금액 3,000,000,000인 Deal과 100인 Deal
- When `deal.amount gt 2147483647`로 조회한다
- Then 3,000,000,000인 Deal만 나오고 오류가 없다

### RQ-035 시각 조건은 업무일 경계의 반열린 구간으로 비교한다
- Given 등록 시각 2026-10-26 23:59+09:00, 2026-10-27 00:00+09:00, 2026-10-27 23:59+09:00, 2026-10-28 00:00+09:00인 Deal
- When `deal.created_at between ["2026-10-27", "2026-10-27"]`로 조회한다
- Then 2026-10-27 00:00과 23:59 두 Deal만 나온다

### RQ-036 올해·이번 분기·이번 달·최근 N일·오늘 이전은 업무 날짜로 풀린다
- Given 오늘 2026-10-27
- When 날짜 필드에 this_year, this_quarter, this_month, last_n_days 7, before_today를 풀고, 오늘 2026-01-03에 last_n_days 7, 오늘 2024-02-29에 this_quarter를 푼다
- Then 차례로 2026-01-01~12-31, 2026-10-01~12-31, 2026-10-01~10-31, 2026-10-21~10-27, ~2026-10-26(시작 없음), 2025-12-28~2026-01-03, 2024-01-01~03-31이다

### RQ-037 최근 1·3·6개월은 n개월 전 같은 날(없으면 말일)부터 오늘까지다
- Given 오늘 2026-10-27
- When 날짜 필드에 last_1_month·last_3_months·last_6_months를, 오늘 2026-03-31에 last_1_month를, 시각 필드에 last_1_month를 푼다
- Then 2026-09-27~10-27, 2026-07-27~10-27, 2026-04-27~10-27, 2026-02-28~03-31이고, 시각 필드는 [2026-09-27 00:00+09:00, 2026-10-28 00:00+09:00)이다

### RQ-038 '이번 달' 조건은 서버 업무 날짜의 달만 고르고 응답 today는 업무 날짜다
- Given 오늘 2026-10-27, Expected Close 2026-10-31인 "October"와 2026-11-01인 "November"
- When 컬럼 `[deal.name]`, 조건 `deal.expected_close relative {period: "this_month"}`로 조회한다
- Then `rows`는 `[["October"]]`이고 `today`는 "2026-10-27"이다

### RQ-039 경고 조건은 Deals 목록의 경고 필터와 같은 Deal을 고른다
- Given 기한초과만·미업데이트만·둘 다·경고 없음 Deal과 기한·갱신이 지난 Won·Lost Deal(경고 기준 14일)
- When `deal.risk in [overdue]`, `in [stale]`, `in [overdue, stale]`, `not_in [overdue]`, `is_empty`로 조회하고 같은 날 Deals 목록을 `overdue=true`, `stale=true`, 둘 다로 읽는다
- Then in 결과는 각각 목록 필터 결과와 같고, not_in·is_empty는 그 여집합(경고 없는 Deal과 Won·Lost 포함)이며 Won·Lost는 어떤 in 결과에도 없다

### RQ-040 경고·체류 일수·최종 업데이트 값은 Deals 목록 값과 같다
- Given 경고 상태·Status 진입일·최근 Action이 다른 Deal들
- When 컬럼 `[deal.code, deal.risk, deal.status_days, deal.last_updated_at]`으로 조회한다
- Then 각 행의 경고 라벨("기한초과"·"미업데이트"·"기한초과·미업데이트"·null), 체류 일수, 최종 업데이트일이 같은 Deal의 Deals 목록 `risk`·`status_days`·`last_updated_on`과 같다

### RQ-041 코드·사용자·연락처 필드는 이름으로 보이고 퇴사자는 (퇴사)가 붙는다
- Given 퇴사한 "kim2"가 담당자이고 Status 진행 중·Vendor SAP·고객 연락처(회사 "ACME", 이름 "홍길동")·지난 파트너 연결 "OldP"와 활성 파트너 연결 "NewP"인 Deal, 수행자 KIM의 Action
- When 컬럼 `[deal.owner, deal.status, deal.vendor, deal.customer_company, deal.customer_contact, deal.partner_company, action.actor]`로 조회한다
- Then 값은 "kim2(퇴사)", Status 코드 이름, "SAP", "ACME", "홍길동", "NewP", KIM 표시 이름이다

### RQ-042 날짜 묶음 포맷은 분기·월·연도 경계를 지키고 표시 전용 포맷은 원래 값으로 묶는다
- Given Expected Close 2026-03-31·2026-04-01·2026-12-31·2027-01-01인 Deal
- When `deal.expected_close`를 quarter·month·year·weekday 포맷 그룹 컬럼과 건수로 각각 조회한다
- Then quarter는 "2026 Q1"·"2026 Q2"·"2026 Q4"·"2027 Q1", month는 "2026-03"·"2026-04"·"2026-12"·"2027-01", year는 정수 2026(3건)·2027(1건), weekday는 날짜 4개 그룹(원래 값)이다

### RQ-043 시각 묶음은 업무 시간대 날짜를 따른다
- Given 등록 시각 2026-12-31T15:30Z(= 2027-01-01 00:30+09:00)인 Deal
- When `deal.created_at`을 year·month·ymd 포맷 그룹 컬럼으로 각각 조회한다
- Then 2027, "2027-01", "2027-01-01"이다

### RQ-044 결과 열의 value_type은 형식·포맷·집계로 정해진다
- When count·count_distinct·avg·sum 집계 열, 그룹핑 없는 금액, 날짜 year·quarter·month·ymd 포맷, 시각 ymd·ymd_hm·weekday 포맷, 텍스트 열로 조회한다
- Then value_type은 차례로 integer·integer·decimal·integer, integer, integer·text·text·date, date·datetime·datetime, text다

### RQ-045 결과 값은 정수·소수 둘째 자리·ISO 날짜·서버 오프셋 시각이다
- Given 금액 1·1·2인 Deal 셋(한 그룹)
- When 금액 sum·avg, Expected Close, 등록일(ymd_hm)로 조회한다
- Then sum은 정수 4, avg는 1.33, 날짜는 "YYYY-MM-DD" 문자열, 시각은 "+09:00" 오프셋 ISO 문자열이다

### RQ-046 Vendor×분기 금액 합계·건수는 Deals 목록 원장과 같다
- Given 오늘 2026-10-27, KIM의 Deal(Vendor, Expected Close, Forecast, 금액): (SAP, 2026-02-10, pipeline, 100), (SAP, 2026-03-31, commit, 110), (SAP, 2026-02-11, lost, 5000), (SAP, 2026-05-10, commit, 200), (SAP, 2025-12-31, pipeline, 777), (IBM, 2026-02-12, pipeline, 300), (IBM, 2026-08-10, best, 400), (IBM, 2027-01-01, pipeline, 888), (Oracle, 2026-02-13, pipeline, 50), (Oracle, 2026-11-10, most_likely, 60), (Oracle, 2026-08-11, lost, 9000)
- When KIM이 컬럼 `[deal.vendor(group), deal.expected_close(quarter, group, asc), deal.amount(sum), deal.code(count)]`, 조건 `deal.forecast_outcome not_in [lost]` AND `deal.expected_close relative this_year`로 조회한다
- Then 각 (Vendor, "2026 Qn") 칸의 (건수, 금액)은 같은 분기·Vendor의 Deals 목록(Lost 제외) 값과 같고, Oracle 칸도 같으며, 빈 칸은 행이 없고 Lost·다른 해 Deal은 어떤 칸에도 없으며, 합계 행은 같은 조건 목록 전체와 같다

### RQ-047 Action 행 그룹핑에서 Deal 금액 합계는 Deal당 한 번이고 Action 건수는 Action 수다
- Given Vendor SAP, 금액 100,000,000인 Deal 하나에 Action 3건
- When 컬럼 `[deal.vendor(group), deal.amount(sum), action.count]`로 조회한다
- Then `rows`는 `[["SAP", 100000000, 3]]`, `row_scope` "action", `deal_numbers_once` true다

### RQ-048 Users count·체류 일수·Deal 필드 건수도 Deal당 한 번이고 Action 필드 건수는 Action마다다
- Given Users count 10인 Deal A(Action 3건)와 20인 Deal B(Action 1건), 같은 담당자
- When 담당자 그룹으로 `deal.users` sum·avg, `deal.status_days` avg, `deal.code` count, `action.action` count를 조회하고, Action 필드 없이 담당자 그룹으로 `deal.users` sum을 조회한다
- Then Users 합계 30·평균 15, 체류 일수 평균은 두 Deal 기준, Deal code 건수 2, 진행사항 건수 4이고, Deal 행 범위 결과도 30이며 `deal_numbers_once`는 false다

### RQ-049 한 Deal이 두 그룹에 있으면 그룹마다 한 번씩 센다
- Given 금액 100인 Deal 하나에 미팅 Action 2건·전화 Action 1건
- When `action.type`(group) × `deal.amount`(sum)로 조회한다
- Then 미팅 100, 전화 100이고 합계 행은 100이다

### RQ-050 고유 건수는 이름이 아니라 key로 센다
- Given 표시 이름이 같은 두 사용자가 각각 담당자인 Deal 2건, 같은 Vendor
- When `deal.vendor`(group) × `deal.owner`(count_distinct)로 조회한다
- Then 고유 건수는 2다

### RQ-051 컬럼 정렬은 컬럼 순서가 우선순위이고 NULL은 맨 뒤, 같으면 Deal code 순이다
- Given (이름, 파트너사): (Alpha, "Acme"), (Alpha, "Zeta"), (Beta, "Acme"), (Alpha, 없음) 순서로 등록(모두 Vendor SAP)
- When 컬럼 `[deal.name(asc), deal.partner_company(desc)]`로, 그리고 순서를 바꾼 `[deal.partner_company(desc), deal.name(asc)]`로 조회한다
- Then 첫째는 [Alpha, Zeta], [Alpha, Acme], [Alpha, null], [Beta, Acme]이고, 둘째는 파트너사 내림차순이 먼저(Zeta → Acme → null)다. 정렬 없는 컬럼은 순서에 영향이 없고 정렬 값이 같은 행은 Deal code 순이다

### RQ-052 Status 그룹은 코드 순서이고 그룹핑 리포트는 집계 컬럼으로도 정렬한다
- Given 여러 Status의 Deal(이름의 가나다 순과 코드 순서가 다름), Vendor별 금액이 다른 Deal
- When `deal.status`(group, asc) × 건수, `deal.vendor`(group) × `deal.amount`(sum, desc), `[deal.amount(sum, desc), deal.vendor(group)]`로 조회한다
- Then Status 행은 코드 순서, Vendor 행은 금액 합계 내림차순이고, 집계 정렬이 앞 컬럼이면 그 집계가 먼저다

### RQ-053 Action 행의 동률은 수행일·id 순이다
- Given 한 Deal에 수행일이 다른 Action 셋과 같은 수행일 Action 둘
- When 컬럼 `[deal.code, action.action]`(정렬 없음)으로 조회한다
- Then Deal code → 수행일 오름차순 → Action id 오름차순이다

### RQ-054 행 수 제한은 정렬 뒤 적용되고 total_count는 제한 전 행·그룹 수다
- Given Deal 101건(금액 1~101), 맞는 Deal이 없는 조건
- When `[deal.amount(desc)]` row_limit 100, Vendor 그룹 리포트, 맞는 행이 없는 조건으로 조회한다
- Then 첫째는 100행(101부터 2까지)·`total_count` 101·`truncated` true, 그룹 리포트의 `total_count`는 그룹 수, 마지막은 `rows: []`·0·false다

### RQ-055 그룹핑 리포트의 합계 행은 같은 조건 전체를 그룹 없이 한 번 더 집계한다
- Given Vendor SAP 금액 10, IBM 금액 30인 Deal
- When `[deal.vendor(group, asc), deal.amount(sum)]`로 조회하고, 그룹이 100개를 넘는 리포트를 row_limit 100으로, 조건이 있는 리포트로 조회한다
- Then 첫째 `rows`는 [["IBM", 30], ["SAP", 10]], `totals`는 [null, 40]이고, 잘린 리포트의 합계는 잘린 그룹을 포함하며, 조건이 있으면 같은 조건의 전체 합계다

### RQ-056 합계 행의 고유 건수는 전체 고유 수이고 Action 행에서도 Deal당 한 번이다
- Given 담당자 KIM이 두 Vendor에 Deal을 가짐, 금액 100인 Deal에 Action 3건
- When Vendor 그룹 × `deal.owner`(count_distinct), Action 행 Vendor 그룹 × `deal.amount`(sum)·`deal.code`(count)·`action.action`(count)로 조회한다
- Then 합계 행의 고유 건수는 1(그룹 합 2가 아님), 금액 100·Deal code 건수 1·진행사항 건수 3이다

### RQ-057 그룹핑이 없거나 그룹 컬럼뿐이면 합계 행은 null이다
- When 그룹핑 없는 리포트, 모든 컬럼이 그룹인 리포트로 조회한다
- Then 둘 다 `totals`는 null이고 그룹 리포트의 `rows`는 그대로 있다

### RQ-058 사용자 값과 행 수 제한은 바인딩 파라미터이고 LIKE 문자는 이스케이프된다
- When contains·equals·in(key·id)·숫자 비교 조건과 row_limit을 가진 정의로 SQL 문장을 만든다
- Then 값과 행 수는 컴파일된 문장에 바인딩 파라미터로 있고 문장 글자에 들어 있지 않으며, `%`·`_`·`\`는 이스케이프되고 starts_with는 끝에만 `%`가 붙는다

### RQ-059 표시 SQL은 입력 값이 보이고 render_sql과 run의 SQL이 같으며 render는 DB를 쓰지 않는다
- When 같은 정의로 `render_sql`과 `run`을 부르고, 정의를 바꿔 다시 `render_sql`을 부른다
- Then 두 SQL은 같고 입력한 값이 리터럴로 보이며, `render_sql`은 세션을 쓰지 않고, 정의가 다르면 SQL이 다르다

### RQ-060 카탈로그의 모든 필드·연산자가 SQL이 되고 필요한 JOIN만 붙는다
- When 모든 필드를 그룹핑 없는 컬럼으로, 그룹핑할 수 있는 필드를 그룹 컬럼으로, 모든 (필드, 연산자)를 조건으로 SQL을 만들고, Vendor·담당자 컬럼과 Action 조건만 있는 정의의 SQL을 본다
- Then 모두 오류 없이 표시 SQL이 되고, Vendor·사용자 JOIN은 한 번씩, Action 필드가 없으면 `deal_actions`가 없으며, 조건에만 있으면 JOIN 없이 EXISTS다

### RQ-061 조회는 읽기 전용·10초 제한이고 넘으면 503 report-timeout 고정 문구다
- Given 실행 시간이 제한을 넘는 문장
- When 읽기 전용 가드 안에서 쓰기·긴 문장·다른 DB 오류를 실행하고, 시간 초과를 일으키는 조회를 `POST /reports/query`로 부른다
- Then 쓰기는 거절, 가드 안 제한은 10000ms이고 숫자는 도메인 상수에서 오며, 긴 문장은 시간 초과 오류, 다른 DB 오류는 시간 초과가 아니며, 가드 뒤 설정은 되돌려지고 세션은 쓸 수 있고, API는 503 `report-timeout` "조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요"(DB 문구 없음)다

### RQ-062 응답 열은 적용된 포맷·단위·앞 N자·집계를 설명하고 금액은 원 그대로다
- Given Vendor SAP, 금액 123,456,789인 Deal
- When `[deal.vendor(group), deal.amount(sum), deal.users(sum)]`과 `[deal.name(prefix_length 4)]`로 조회한다
- Then 첫째 열의 (format, unit)은 (null, null)·(null, "krw")·(null, null), `rows[0][1]`은 123456789이고, 둘째 열은 format null·`prefix_length` 4이며, 응답 키는 RQ-R36과 같다

### RQ-063 조회는 업무 날짜·오프셋·경고 기준을 정하고 상대 조건을 푼 정의를 Port에 넘긴다
- Given 고정 시계 2026-10-27T03:00Z, 경고 기준 설정 21일(그리고 설정 없음)
- When 상대 기간 조건이 있는 정의로 조회한다
- Then Port에 넘어간 문맥은 오늘 2026-10-27·오프셋 +09:00·`stale_days` 21(설정 없으면 기본값)이고, 조건은 절대 범위로 풀려 있으며, Port 결과 행·합계·`total_count`가 그대로 뷰가 되고 `truncated`는 `total_count > 행 수`다. Port의 시간 초과 오류는 그대로 전파된다

### RQ-064 openapi에 두 경로의 오류·포맷·단위·컬럼 정렬 계약이 있다
- When openapi를 읽는다
- Then `/reports/fields` GET은 422가 없고, `/reports/query` POST는 422·503이 있으며, format 스키마는 nullable 7값, unit은 nullable `krw`(필드·결과 열), 요청 컬럼에 `sort`가 있고 최상위 `sort`가 없다

### RQ-065 앞 N자는 SQL에 영향이 없고 그룹핑은 전체 값 기준이다
- Given 이름 "Alpha One"·"Alpha Two"인 Deal
- When `deal.name`(group, prefix_length 5) × 건수로 조회하고, 앞 N자만 다른 두 정의(집계·날짜 컬럼 포함)로 SQL을 만든다
- Then 그룹은 2개이고, 두 SQL은 같다

### RQ-066 카탈로그를 읽는 동안 로딩 문구, 실패하면 오류와 다시 시도다
- Given 카탈로그 응답이 늦거나 실패하는 Fake
- When `/reports/new`를 연다
- Then 읽는 동안 "새 리포트"와 "불러오는 중…"이고, 실패하면 오류 배너와 "다시 시도"가 보이며 누르면 다시 읽어 디자이너가 열린다

### RQ-067 첫 화면은 제목·초기화·빈 안내·두 탭이고 저장 표시·조회 버튼은 꺼져 있다
- When VIEWER가 `/reports/new`를 연다
- Then 제목 "새 리포트", "초기화" 버튼, "왼쪽 필드 목록에서 컬럼을 추가하세요.", "조건이 없으면 모든 Deal이 대상입니다", 탭은 "작성"·"결과" 둘(작성 선택), "● 저장 안 됨"이 없고 "조회" 버튼은 비활성이다

### RQ-068 탭은 버튼·화살표로 바뀌고 숨은 패널을 유지해 설계·페이지·합계 행 선택이 남는다
- Given 컬럼을 넣고 100행이 넘는 그룹 결과를 조회해 2쪽과 합계 행을 켬
- When 작성 탭으로 갔다가 결과 탭으로 돌아오고, 탭에서 →·← 키를 누른다
- Then 비활성 패널은 DOM에 `hidden`으로 남고, 돌아오면 설계·2쪽·합계 행 선택이 그대로이며, 화살표로 탭과 포커스가 옮겨진다

### RQ-069 필드 목록은 두 묶음이고 이름 부분 일치로 거른다
- When 디자이너를 열고 "필드 검색"에 "bant", "진행", "없는필드"를 차례로 친다
- Then 처음에는 "Deal"·"Deal Actions" 두 묶음과 형식 라벨이 보이고, "bant"는 BANT 필드 4개, "진행"은 Deal Actions의 "진행사항"만, "없는필드"는 "일치하는 필드가 없습니다."다

### RQ-070 "+조건"은 조건에 쓸 수 있는 필드에만 있다
- When 필드 목록을 본다
- Then "Action 건수"에는 "+조건"이 없고 다른 필드에는 있다

### RQ-071 필드를 누르면 칩이 생기고 같은 필드는 확인 뒤에만 한 번 더 들어간다
- Given 컬럼 "금액"이 있음
- When "Deal 이름 컬럼에 추가"를 누르고, "금액 컬럼에 추가"를 눌러 확인 창에서 "추가"/"취소"/Escape를 각각 고르고, "금액 조건 추가"를 누르고, 컬럼을 30개까지 넣는다
- Then 새 필드는 묻지 않고 칩이 생겨 선택되며, 같은 필드는 "'금액'은(는) 이미 컬럼에 있습니다. 한 번 더 추가할까요?" 창이 뜨고 "추가"일 때만 칩이 하나 늘며, 조건 추가는 묻지 않고, 30개면 추가 버튼이 꺼지고 "컬럼은 최대 30개입니다"다

### RQ-072 칩 순서는 끌어서 놓기와 Alt+←/→로 바꾼다
- Given 칩 A·B·C
- When C를 A 위로 끌어 놓고, B에서 Alt+←, 첫 칩에서 Alt+←, 일반 ←를 누른다
- Then 순서가 C·A·B가 되고, Alt+←는 B를 한 칸 앞으로 옮기며 포커스가 B에 남고 "‘B’를 N번째로 옮겼습니다"가 알려지며, 끝을 넘거나 일반 화살표는 순서를 바꾸지 않는다. 설정 패널에 옮기기 버튼은 없다

### RQ-073 데이터 범위 표시는 설계에 따라 행 단위·EXISTS·Deal당 한 번을 알린다
- When 컬럼 Deal 이름만, Action 컬럼 추가, Action 컬럼 대신 Action 조건(AND와 OR), Deal 조건만, Action 행 그룹핑 + 금액 합계로 설계한다
- Then 차례로 "행 단위: Deal 1건", "행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)", "행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만"과 AND·OR 문구, Action 문구 없음, "Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다"가 보인다

### RQ-074 컬럼 설정은 한 줄에 이름·표시 이름·포맷·앞 N자·그룹핑·집계·정렬을 보인다
- When 칩 "Expected Close"를 고르고 표시 이름을 "마감"으로 바꾸고, 칩 "Deal 이름"·"금액"을 고른다
- Then 설정 영역 "컬럼 설정: …" 첫 칸이 컬럼 이름("마감"으로 바뀜)이고 칸들은 `aria-label`로 이름이 있으며, 날짜 포맷 선택지는 그 형식 6개이고 묶음 포맷 뒤에 " (묶음)"이 붙고, 텍스트·숫자 필드에는 포맷 선택이 없으며, 표시 이름을 지우면 칩은 필드 이름으로 돌아간다

### RQ-075 그룹핑을 켜고 끄면 집계가 자동으로 채워지고 비워진다
- Given 컬럼 Vendor·Deal 이름·금액
- When Vendor 그룹핑을 켜고, 이어서 "Deal code"를 추가하고, 이름 집계를 고유 건수로 바꾸고, Vendor 그룹핑을 끈다
- Then 켜면 이름은 "건수", 금액은 "합계"가 되고 그룹 컬럼 집계는 "—"(비활성)이며 빈 집계 선택지는 없고, 추가한 Deal code도 "건수", 텍스트 집계 선택지는 건수·고유 건수뿐이며, 끄면 모든 집계가 비고 "(그룹핑이 있을 때)"가 보인다. Action 건수는 그룹핑 칸이 꺼져 있고 집계가 "건수"로 잠겨 있다

### RQ-076 칩 배지는 그룹·집계·포맷·앞 N자·정렬 우선순위·그룹핑할 때만을 보인다
- When Vendor를 그룹, 금액을 평균, Expected Close를 분기 포맷, 이름에 앞 N자 10, 이름 오름차순·금액 내림차순 정렬, 그룹 없이 Action 건수를 넣는다
- Then 배지는 "그룹", "평균", "분기"(기본 포맷·숫자 필드는 포맷 배지 없음), "앞 10자", "▲ 오름 1"·"▼ 내림 2"(정렬이 하나면 번호 없음), "그룹핑할 때만"이고, 정렬한 컬럼을 빼면 그 배지도 사라진다

### RQ-077 앞 N자를 켜면 N이 20이고 잘못된 N은 요청 없이 안내한다
- When "앞 N자만 보기"를 켜고, N을 비운 채 조회하고, N을 4로 고쳐 조회하고, 포맷을 바꾸고, 끈다
- Then 켜면 N 칸이 활성되고 20이며 배지 "앞 20자"가 생기고, 빈 N은 요청 없이 "1~200 사이 정수를 입력하세요", 4면 `prefix_length: 4`를 보내며 `format` 키는 없고, 포맷을 바꿔도 앞 N자는 남으며, 끄면 N 칸이 꺼지고 배지가 사라진다

### RQ-078 조건 행 추가·필드 변경·삭제·한도와 빈 조건 안내
- When "Status 조건 추가"를 누르고 필드를 "Deal 이름"으로 바꾸고, "+ 조건 추가"를 누르고, 조건 1을 삭제하고, 조건을 20개까지 넣고, 컬럼에 Action 필드를 넣고 조건을 모두 지운다
- Then 연산자는 그 필드의 첫 연산자로 바뀌고 값은 비며, "+ 조건 추가"는 첫 조건 가능 필드로 행을 만들고, 필드 선택지는 조건 가능 필드뿐이며, 삭제 뒤 번호가 다시 매겨지고, 20개면 버튼이 꺼지고 "조건은 최대 20개입니다", 조건이 없으면 "조건이 없으면 모든 Action이 대상입니다"다

### RQ-079 조건 결합 라디오가 접속어와 요청의 combine을 바꾼다
- Given 조건 2개
- When "하나라도 만족(OR)"을 고르고 조회한다
- Then 라디오 묶음 이름은 "조건 결합", 둘째 행의 접속어가 AND에서 OR로 바뀌고 요청 `combine`은 "or"다

### RQ-080 목록 값 선택지는 출처의 순서·구분을 따르고 선택을 요약한다
- When Forecast 구분·Status·BANT Budget 조건의 값 목록을 열고 값을 0·2·3개 고르고 "선택 해제"를 누른다
- Then 정적 선택지는 카탈로그 순서, Status는 코드 순서를 따르고 BANT Budget은 budget 구분 Label만 표시한다. 요약은 "선택" → "2개 선택 · 이름1, 이름2" → "3개 선택 · 이름1, 이름2, 이름3"으로 바뀐다. 모두 해제하면 "선택"으로 돌아간다.

### RQ-081 연산자 모양마다 맞는 값 입력 칸을 보인다
- When 연산자를 is_empty, 날짜 between, relative(최근 N일), 숫자 eq로 바꾼다
- Then is_empty는 값 칸이 없고, 날짜 between은 "조건 N 시작"·"조건 N 끝" 날짜 칸, relative는 "조건 N 기간"(8개 순서)과 최근 N일일 때만 "조건 N 일수", eq는 정수 칸이며, 필드를 다른 형식으로 바꾸면 이전 값이 남지 않는다

### RQ-082 금액 조건은 원 단위로 입력하고 입력한 원 그대로 보낸다
- When 금액 eq 칸에 "12a34567"을 치고 조회하고, 금액 between에 "1000000"·"5000000"을 친다; Users count·Status 체류 일수 조건을 본다
- Then 금액 칸은 숫자·콤마만 받아 "1,234,567"로 보이고 옆에 "(원)"이 있으며 요청 값은 1234567, 범위는 [1000000, 5000000]이고, Users count·체류 일수에는 "(원)"이 없다

### RQ-083 최근 n개월은 일수 없이 보내고 일수 칸을 숨긴다
- When 기간을 "최근 N일"로 골라 일수를 친 뒤 "최근 3개월"로 바꾸고 조회한다
- Then 일수 칸이 사라지고 요청 값은 `{period: "last_3_months"}`(days 없음)다

### RQ-084 날짜는 yyyymmdd로 입력해 ISO로 보내고 틀린 날짜는 요청 없이 그 칸에 안내한다
- When 날짜 범위 시작·끝에 "20261001"·"20261031"을 쳐 조회하고, 끝을 "20261332"로, 단일 날짜를 "202610"으로, 날짜를 비운 채 조회한다
- Then 첫 요청 값은 ["2026-10-01", "2026-10-31"]이고, 틀린·덜 친 날짜는 요청 없이 그 칸에 날짜 입력 규칙 문구(UI-R7), 빈 날짜는 "날짜를 고르세요"다

### RQ-085 읽을 수 없는 입력이 있으면 요청을 보내지 않고 칸 아래에 문구를 보인다
- When 텍스트 값 빈 칸, 목록 값 0개, 숫자 "1.5", 범위 시작 10·끝 5, 최근 N일 0으로 각각 조회한다
- Then 요청은 하나도 가지 않고 작성 탭에 머물며 각 행 아래에 "값을 입력하세요", "하나 이상 선택하세요", "정수로 입력하세요", "시작이 끝보다 클 수 없습니다", "1~3650 사이 정수를 입력하세요"가 보이고 해당 칸이 `aria-invalid`다

### RQ-086 조회 요청은 설계대로이고 설계가 비운 키는 보내지 않는다
- Given 컬럼 Vendor(그룹)·금액(합계, 표시 이름 "금액 합계", 내림차순)·Deal 이름(표시 이름 "Deal 이름"·정렬 오름차순 → 순서 금액보다 앞), 조건 Forecast 구분 다음이 아님 [lost]
- When 조회한다
- Then 요청은 컬럼 순서대로 `{field, group, label?, format?, prefix_length?, aggregate?, sort?}`이며 필드 이름과 같은 표시 이름·빈 값은 보내지 않고, 정렬은 컬럼 순서대로이며, 조건 값·`combine`·`row_limit`이 함께 간다(HTTP 본문은 snake_case, 빈 키 없음)

### RQ-087 최대 행은 100·1,000·10,000 중 고르고 기본은 1,000이다
- When "최대 행"을 보고 10,000을 골라 조회한다
- Then 선택지는 100·1,000·10,000이고 기본은 1,000이며 요청 `row_limit`은 10000이다

### RQ-088 조회 중에는 "조회 중…"이고 두 번째 조회를 막는다
- Given 응답을 붙잡은 Fake 처리기
- When "조회"를 누르고 다시 누른다
- Then 버튼은 "조회 중…"이고 비활성이며 요청은 한 번뿐이다

### RQ-089 조회가 성공하면 결과 탭으로 옮겨 결과 표를 보인다
- When 컬럼을 넣고 조회한 뒤 작성 탭으로 돌아가 다시 조회한다
- Then 매번 결과 탭이 선택되고 결과 표와 표 타일이 보인다

### RQ-090 정의 위반이면 작성 탭에 머물며 고칠 곳 목록과 칸별 표시, 탭 이름 수를 보인다
- Given 서버가 컬럼 1 집계·조건 1 값·combine·row_limit 위반 4개를 돌려주는 Fake 처리기
- When 조회한다
- Then 작성 탭에 머물고 조회 버튼 아래 "고칠 곳 4개"와 "컬럼 1(<이름>): …", "조건 1(<필드 이름>): …", "조건 결합: …", "최대 행: …"이 보이며, 같은 문구가 칩·집계 칸·조건 행·결합·최대 행 아래에도 있고, 탭 이름은 "작성 (고칠 곳 4)"이다. 위반이 없으면 두 탭 모두 이름만이다

### RQ-091 위치를 모르는 위반은 요약에만 보인다
- Given 위치 `["sort"]`(예전 최상위 정렬)과 `["unknown"]`인 위반을 돌려주는 Fake 처리기
- When 조회한다
- Then 두 문구는 "고칠 곳" 요약에 위치 없이만 보이고 어느 칸에도 없다

### RQ-092 고친 항목·지운 컬럼의 위반 표시는 사라지고 성공하면 실패 알림이 사라진다
- Given RQ-090의 위반이 보임
- When 컬럼 1의 집계를 바꾸고, 조건 1의 값을 바꾸고, 위반이 있는 다른 컬럼을 빼고, 다시 조회해 성공한다
- Then 바꾼 항목의 표시가 차례로 사라지고(탭 이름 수도 줄어듦), 남은 위반이 없으면 요약도 없으며, 성공하면 실패 알림이 없다

### RQ-093 시간 초과·연결 끊김·그 밖의 오류는 서버 문구를 보이고 이전 결과를 남긴다
- Given 한 번 성공한 결과
- When 시간 초과(503 report-timeout), 연결 끊김, 500 오류로 각각 조회한다
- Then 작성 탭에 머물고 조회 버튼 아래 `role=alert`로 "조회가 10초 안에 끝나지 않았습니다. …", 게이트웨이 연결 문구, 서버 문구가 각각 보이며, 결과 탭에는 이전 결과가 그대로다

### RQ-094 표 타일은 결과 전 안내, 총 행·조회 시간, 잘림 표시와 100행 페이지를 보인다
- When 조회 전 결과 탭을 열고, `totalCount` 3·`elapsedMs` 210 결과, `totalCount` 1500·250행·`truncated` 결과, 100행 결과, 250행에서 3쪽을 본 뒤 50행 결과·250행 결과를 받는다
- Then "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요.", "총 3행 · 조회 0.21초", "총 1,500행 중 250행 표시(최대 행 수 제한) · 조회 …"와 페이저, 100행은 페이저 없음, 새 결과는 항상 첫 쪽이고, 표는 가로 스크롤 컨테이너 안에 있다

### RQ-095 합계 행은 합계가 있는 결과에서만 켜고 새 결과에서 꺼지며 Deal당 한 번 안내가 붙는다
- When `totals`가 있는 그룹 결과에서 "합계 행"을 켜고, `dealNumbersOnce` 결과에서 켜고, 새 결과를 받고, `totals`가 null인 결과를 받는다
- Then 켜면 `tfoot`에 첫 그룹 열 "합계"와 합계 값(금액은 원)이 보이고, Deal당 한 번 결과에는 "한 Deal이 여러 그룹에 나오면 …" 안내가 붙으며, 새 결과에서는 꺼져 있고, 합계가 없으면 체크박스가 없다

### RQ-096 숫자는 천 단위·소수 없이 오른쪽 정렬, 금액은 원과 머리글 (원), 빈 값은 —이다
- When 금액 123456789, 금액 건수 집계 7, 평균 1234.6, 연도 2026, null 값이 있는 결과를 본다
- Then 금액 머리글은 "금액 (원)"이고 값 "123,456,789", 건수 열 머리글에는 "(원)"이 없고 "7", 평균 "1,235", 연도 "2026", null "—"이며 숫자 칸은 오른쪽 정렬이다

### RQ-097 날짜·시각은 서버 오프셋 벽시계와 앱 시계 기준 상대 표기·요일로 보인다
- Given 앱 시계 2026-10-27T10:00+09:00
- When 날짜 weekday "2026-10-27", 날짜 relative "2026-10-24"·"2026-10-27"·"2026-10-29", 시각 ymd_hm "2026-10-27T09:05:00+09:00", 시각 ymd·weekday·relative 값을 본다
- Then "2026-10-27 (화)", "3일 전"·"오늘"·"2일 후", "2026-10-27 09:05"(브라우저 시간대와 무관), 날짜 부분, "날짜 (요일)", Deals 목록과 같은 상대 시각 표기다

### RQ-098 앞 N자는 칸만 자르고 title에 전체 값을 두며 합계 행은 자르지 않는다
- When `prefixLength` 4인 열에 "Alpha Deal"·"Beta"·null, 합계 행이 있는 결과를 본다
- Then "Alph…"(title "Alpha Deal"), "Beta"(그대로), "—"(자르지 않음)이고 합계 행 값은 전체다

### RQ-099 조회 뒤 설계를 바꾸면 결과 탭에 다시 조회 안내가 보이고 다음 조회에서 사라진다
- When 조회 전 결과 탭을 보고, 조회한 뒤 컬럼 정렬·최대 행을 바꾸고, 보기 방식·칩 선택만 바꾸고, 다시 조회한다
- Then 조회 전에는 안내가 없고, 정렬·최대 행을 바꾸면 결과 탭에만 "설계가 바뀌었습니다. 작성 탭에서 '조회'를 눌러 다시 조회하세요"가 보이고 결과는 이전 그대로이며, 보기 방식·선택만 바꾸면 없고, 다시 조회하면 사라진다

### RQ-100 생성 SQL은 조회 전 안내, 조회 뒤 최신 SQL을 결과 탭에 읽기 전용으로 보인다
- When 조회 전 결과 탭을 보고, 조회하고, 설계를 바꿔 다시 조회한다
- Then 조회 전 "조회하면 서버가 만든 SQL이 여기에 보입니다"이고 SQL 입력 칸이 없으며, 조회 뒤 "생성 SQL 보기(읽기 전용)"를 펼치면 마지막 조회의 SQL이 보이고, 작성 탭이 보이는 동안 이 영역은 숨어 있다

### RQ-101 바뀐 설계에서 다른 화면 링크를 누르면 떠날지 묻는다
- When 컬럼을 넣고 상단 메뉴 "Deals"를 눌러 "머물기"·"떠나기"를 고르고, 조건만 넣고 누르고, 아무것도 바꾸지 않고 누르고, 넣었던 컬럼을 다시 빼고 누른다
- Then 바뀐 상태면 "저장하지 않은 변경이 있습니다" 창이 뜨고 "머물기"는 그대로, "떠나기"는 이동하며 열린 메뉴도 닫히고, 바뀌지 않았거나 되돌렸으면 묻지 않고 이동한다. `beforeunload`는 바뀐 동안만 걸리고 떠나면 풀린다

### RQ-102 초기화는 바뀐 설계면 확인 뒤 모두 지우고 아니면 바로 지운다
- Given 컬럼·조건과 조회 결과가 있음
- When "초기화"를 눌러 "취소"를 고르고, 다시 눌러 "초기화"를 고르고, 빈 설계에서 "초기화"를 누른다
- Then "설계를 모두 지울까요?" / "컬럼과 조건이 모두 사라집니다." 창이 뜨고, 취소는 그대로, 초기화는 컬럼·조건·결과가 모두 사라지며, 빈 설계에서는 묻지 않는다

### RQ-103 게이트웨이는 카탈로그·조회를 snake_case↔camelCase로 바꾼다
- When `reports.fields()`와 `reports.query(input)`을 부른다
- Then `GET /api/v1/reports/fields`의 응답이 camelCase(연산자 `shape`, 필드 선택지, 포맷 없는 필드 `formats: []`·`defaultFormat: null`)로 바뀌고, `POST /api/v1/reports/query` 본문은 snake_case이며 설계가 비운 키(format·label·prefix_length 등)가 없고, 결과는 camelCase(열 `unit`·`prefixLength`·`format` null 유지, `totals` null 유지)다

### RQ-104 게이트웨이는 invalid-report 위반을 reportErrors로 옮기고 다른 오류는 PL 규칙대로 바꾼다
- When 서버가 401, `invalid-report`(`errors` 2개와 모양이 틀린 항목 1개), `request-validation`, `report-timeout`을 돌려주고, 연결이 끊긴다
- Then 401은 `unauthorized`, invalid-report는 TypeError 없이 `problem.reportErrors`에 맞는 항목 2개·문구 = detail, request-validation은 칸 문구가 붙은 `validation`, report-timeout은 서버 detail, 끊김은 network 오류다

### RQ-105 데이터 훅은 카탈로그를 한 번만 읽고 조회는 무효화하지 않으며 실패를 분류한다
- When `useReportFields`를 두 번 마운트하고, 실패하는 카탈로그를 읽고, `useRunReport`로 조회하고, `reportRunFailure`에 여러 오류를 넣는다
- Then 카탈로그는 `reportFields` 키로 한 번만 읽고 실패는 재시도 없이 ApiError이며, 조회는 결과를 돌려주고 다른 쿼리를 다시 읽지 않고, 분류는 invalid(위반 목록, 없으면 [])·timeout·network·other(문구)·other(일반 문구)다

### RQ-106 Fake 게이트웨이는 흉내 내는 위반을 서버와 같은 code·위치·문구로 내고 합성 결과를 준다
- When Fake에 위반 정의(모르는 필드·집계 없는 그룹 텍스트·그룹핑 없는 집계·그룹핑 없는 Action 건수·컬럼 0개·행 수 7)와 정상 정의(그룹 유무, Action 컬럼, 모든 컬럼이 그룹, 평균·최소·최대 집계 컬럼)를 보내고, 처리기를 정해 보내고, 데이터를 초기화한다
- Then 위반은 RQ-R9·RQ-R10·RQ-R14·RQ-R19의 code·location·문구(행 수는 "행 수 제한은 100, 1000, 10000 중 하나여야 합니다")로 모두 모은 invalid-report이고 detail은 첫 문구이며, 정상 정의는 열 수만큼 넓은 3행·Fake 시계 날짜·서버와 같은 범위 판정이고 합계 행은 그룹핑하고 집계 컬럼이 있을 때만 있고(모든 컬럼이 그룹이면 null, 그룹핑이 없으면 null) 평균·최소·최대 칸도 비지 않으며, 처리기 결과·오류가 그대로 쓰이고 요청이 기록되며, 초기화하면 처리기·기록이 지워진다

### RQ-107 Fake와 계약: 모든 역할이 카탈로그·조회를 쓰고 미인증은 401이다
- When admin·sales·user Fake 게이트웨이로 카탈로그와 조회를 부르고, 로그아웃한 뒤 부른다
- Then 세 역할 모두 40필드 카탈로그와 결과를 받고(카탈로그 불변식·결과 모양은 RQ-R2~RQ-R6·RQ-R36과 같음), 로그아웃 뒤에는 둘 다 401이다

### RQ-108 저장 정의 JSON은 조회 요청과 같은 모양이고 다시 읽으면 같은 정의다
- Given 표시 이름을 생략한 컬럼, 정렬(asc·desc)·앞 N자·그룹·집계가 있는 컬럼, 조건(최근 1개월·최근 3개월·최근 6개월 상대 기간 포함)이 있는 정의, 그리고 `combine`·`row_limit` 키가 없는 저장 JSON
- When 정의를 JSON으로 쓰고 다시 읽은 뒤 검증하고, 키가 없는 JSON을 읽는다
- Then JSON은 컬럼마다 `field`·`label`·`format`·`prefix_length`·`group`·`aggregate`·`sort` 7키와 `conditions`·`combine`·`row_limit`이고 최상위 `sort`가 없으며, 다시 읽은 정의와 그 검증 결과가 처음과 같고(생략한 표시 이름은 생략 그대로, 상대 기간 값은 그대로), 키가 없던 JSON은 `combine` "and"·`row_limit` 1000으로 읽힌다

### RQ-109 예전 텍스트·코드 포맷은 포맷 없음으로, 예전 앞 N자 포맷의 N은 앞 N자 옵션으로 읽힌다
- Given 업무 날짜 2026-10-27, Forecast pipeline인 Deal 1건, ALICE의 저장 리포트 정의 JSON이 컬럼 `deal.name` 포맷 `as_is`, `deal.status` `name`, `deal.forecast` `key`, `deal.code` `prefix`·`prefix_length` 5와 최상위 `sort: null`인 예전 형식으로 바뀌어 있음
- When ALICE가 그 리포트의 상세를 열고 실행한다
- Then 상세는 200이고 `definition` 컬럼의 `format`은 모두 null, `prefix_length`는 [null, null, null, 5]이며 최상위 `sort`가 없다. 실행은 200이고 결과 열 `format`이 모두 null이며 Status·Forecast 칸은 key("pipeline" 등)가 아니라 이름이다. 지금 포맷(ymd·quarter)은 그대로 읽히고, 읽은 정의를 다시 쓰면 예전 포맷 값이 남지 않는다

### RQ-110 예전 숫자 포맷은 포맷 없음으로 읽히고 값은 집계 그대로다
- Given Vendor SAP의 Deal 금액 100·200, ALICE의 저장 리포트 정의 JSON이 컬럼 Vendor(그룹)·금액 합계 `percent_share`·Users count 합계 `krw_million`·Deal code 건수 `decimal1`인 예전 형식으로 바뀌어 있음, 그리고 `thousands`·`krw_thousand`·`krw_million`·`decimal1`·`percent_share` 각각에 `prefix_length` 3을 준 금액 컬럼 JSON
- When 상세를 열고 실행하고, 컬럼 JSON들을 읽는다
- Then 상세 컬럼 `format`은 모두 null이고, 실행 결과 열 `format`은 모두 null·`unit`은 [null, "krw", null, null]이며 첫 행은 ["SAP", 300, …](구성비가 아니라 금액 합계, 원)이다. 다섯 숫자 포맷 컬럼은 모두 포맷 null·`prefix_length` 3으로 읽힌다

### RQ-111 예전 최상위 정렬은 그 컬럼의 정렬로 읽혀 같은 순서로 실행된다
- Given Deal Alpha(Vendor IBM)·Beta(Vendor SAP), ALICE의 저장 리포트 정의 JSON이 컬럼 `deal.name`·`deal.vendor`와 최상위 `sort: {column: 1, direction: "desc"}`인 예전 형식으로 바뀌어 있음
- When 상세를 열고 실행하고, 최상위 `sort`가 `{column: 0}`(방향 없음)·null인 JSON, 컬럼 1에 자기 `sort` "asc" 또는 ""가 있으면서 최상위 `sort: {column: 1, direction: "desc"}`인 JSON을 읽고, 변환한 정의를 다시 쓴다
- Then 상세 `definition` 컬럼 `sort`는 [null, "desc"]이고 최상위 `sort`가 없으며 실행 행은 [["Beta", "SAP"], ["Alpha", "IBM"]]이다. 방향 없음은 컬럼 0이 "asc", null은 정렬 없음, 컬럼 자기 값("asc"·"")이 최상위 정렬보다 우선하며, 다시 쓰면 최상위 `sort` 없이 컬럼 `sort`로만 쓰인다

### RQ-112 읽을 수 없는 모양은 stored-invalid이고 값 위반은 읽을 때가 아니라 실행 때 알린다
- When 저장 JSON으로 `[]`, "text", null, `{}`, `columns` 문자열, 문자열 컬럼, `field` 없는 컬럼, `conditions` 문자열, 숫자 조건, 컬럼 `sort: 1`, 그리고 최상위 `sort`가 "x"·`{column: 5}`·`{column: 3}`(컬럼 3개)·`{column: -1}`·`{column: "0"}`·`{column: true}`·`{column: 0, direction: 1}`인 JSON을 각각 읽고, 최상위 `sort: {column: 1, direction: "up"}`인 JSON을 읽은 뒤 검증한다
- Then 앞의 것은 모두 위반 하나 `["definition"]` `stored-invalid` "저장된 리포트 정의를 읽을 수 없습니다."(API 응답은 RS-R17)이고, "up"은 읽기는 되며 검증에서 `["columns", 1, "sort"]` `sort-invalid` 하나다

### RQ-113 카탈로그에서 최종 업데이트·Status 진입일·수행일·종료일은 date 형식이고 기본 포맷 ymd이며 ymd_hm이 없다
- When `GET /reports/fields`를 부른다
- Then 27 `deal.last_updated_at`(최종 업데이트), 28 `deal.status_changed_at`(Status 진입일), 38 `action.acted_at`(수행일), 39 `action.closed_at`(종료일)은 type date이고, formats는 ymd·year·quarter·month·weekday·relative이며, 기본값은 ymd다. 26 `deal.created_at`은 datetime 그대로다. 필드 개수와 순서는 바뀌지 않는다

### RQ-114 네 날짜 필드에 ymd_hm을 요청하면 422 format-not-allowed다
- When 컬럼 `[{field: "action.acted_at", format: "ymd_hm"}]`로 조회하고, `deal.status_changed_at`·`action.closed_at`·`deal.last_updated_at`도 같은 포맷으로 조회한다
- Then 모두 422 `invalid-report`이고, 위치는 `["columns", 0, "format"]`, code는 `format-not-allowed`다

### RQ-115 저장 정의의 네 날짜 필드 ymd_hm은 읽을 때 ymd로 바뀐다
- Given 저장 정의에 네 날짜 필드가 `format: "ymd_hm"`인 컬럼으로 들어 있다
- When 그 리포트를 열고 실행한다
- Then 정의의 네 포맷은 ymd이고, 결과 칸은 `YYYY-MM-DD`이며, 오류가 없다

### RQ-116 저장 정의의 예전 key deal.solution은 읽을 때 deal.product로 바뀌어 실행된다
- Given Product "ITDR"·"MFA"인 Deal 2건, ALICE의 저장 리포트 정의 JSON이 컬럼 `{field: "deal.solution", label: "솔루션"}`·`{field: "deal.name"}`과 조건 `deal.solution contains "itd"`인 예전 형식
- When 상세를 열고 실행하고, 읽은 정의를 다시 쓴다
- Then 상세 `definition`의 컬럼·조건 field는 `deal.product`이고 컬럼 label "솔루션"은 그대로이며, 실행 결과는 "ITDR" Deal 1행이고 첫 결과 열 이름은 "솔루션"이다. 다시 쓴 JSON에는 `deal.solution`이 없다

### RQ-117 조회·저장 요청의 deal.solution은 unknown-field 422다
- When `/reports/query`에 컬럼 `deal.solution`으로, 또 컬럼 `deal.name`·조건 `deal.solution contains "a"`로 조회하고, `POST /reports`에 컬럼 `deal.solution`인 정의로 저장한다
- Then 각각 422 `invalid-report`이고 위치는 `["columns", 0, "field"]`·`["conditions", 0, "field"]`·`["columns", 0, "field"]`, code `unknown-field` "허용되지 않은 필드입니다: deal.solution"이며 조회 Port는 불리지 않고 리포트는 저장되지 않는다

### RQ-118 action.comment는 그 Action의 Comment를 작성 순 줄바꿈으로 이어 붙이고, 없으면 비어 있음 조건에 걸린다
- Given Action A에 Comment "첫째"·"둘째"가 순서대로 있고 Action B에는 Comment가 없다
- When 컬럼 `action.comment`와 조건 `action.comment is_empty`로 각각 조회한다
- Then A의 값은 "첫째\n둘째"(작성 순)이고, B는 null이며 `is_empty` 조건은 B만 고른다. Repository 계약 테스트다

### RQ-119 조회·저장 요청의 action.memo는 unknown-field 422다
- When `/reports/query`에 컬럼 `action.memo`로, 또 조건 `action.memo contains "a"`로 조회하고, `POST /reports`에 컬럼 `action.memo`인 정의로 저장한다
- Then 각각 422 `invalid-report` code `unknown-field` "허용되지 않은 필드입니다: action.memo"이며 조회 Port는 불리지 않고 리포트는 저장되지 않는다

### RQ-120 저장 정의의 action.memo는 읽을 때 action.comment로 바뀐다
- Given 저장 정의 JSON이 컬럼 `{field: "action.memo", label: "메모"}`와 조건 `action.memo contains "a"`인 예전 형식
- When 상세를 열고 읽은 정의를 다시 쓴다
- Then 컬럼·조건 field는 `action.comment`이고 컬럼 label "메모"는 그대로이며, 다시 쓴 JSON에는 `action.memo`가 없다

### RQ-121 deal.comment는 Action 연결 여부와 무관하게 그 Deal의 모든 Comment를 작성 순으로 이어 붙이고 다른 Deal 것은 섞이지 않는다
- Given Deal D에 Deal Comment "예산"과 Action Comment "견적"이 있고 다른 Deal에 Comment "남"이 있다
- When 컬럼 `deal.comment`로 조회한다
- Then D의 값은 "예산\n견적"(작성 순)이고 "남"은 섞이지 않는다. Repository 계약 테스트다

### RQ-122 deal.comment만 쓴 리포트는 Deal 범위(action_filter none)로 Deal당 1행이다
- Given Action이 여러 건인 Deal 하나와 Comment가 있다
- When 컬럼 `deal.comment`만으로 조회한다
- Then action_filter는 `none`이고 그 Deal은 1행이다

### RQ-123 Action 행 범위 그룹핑에서 deal.comment 건수는 Deal당 한 번 센다
- Given Action이 3건이고 Comment가 있는 Deal 1개를 `action.type`으로 그룹핑한다
- When `deal.comment`의 건수 집계를 조회한다
- Then 그룹마다 Action 행 수가 아니라 Comment가 있는 Deal 수(1)로 센다

### RQ-124 deal.comment contains 조건은 Deal Comment·Action Comment 어느 쪽 본문에 있어도 그 Deal을 고른다
- Given Deal X에는 Deal Comment에만 "예산", Deal Y에는 Action Comment에만 "예산", Deal Z에는 "예산"이 없다
- When 조건 `deal.comment contains "예산"`으로 조회한다
- Then X와 Y가 나오고 Z는 나오지 않는다

### RQ-125 바뀐 설계에서 브라우저 뒤로 가기를 하면 떠날지 묻고 머물기면 주소·설계가 그대로다
- Given KIM이 `/reports`에서 "+ 새 리포트"를 눌러 `/reports/new`에 왔고, 필드 하나를 컬럼으로 넣고 조건 하나를 넣어 "● 저장 안 됨"이 보인다
- When 브라우저 뒤로 가기를 하고 "머물기"를 누른 뒤, 한 번 더 뒤로 가기를 한다
- Then 첫 뒤로 가기에서 "저장하지 않은 변경이 있습니다" / "저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?" 창이 뜨고, "머물기" 뒤 창이 닫히며 주소는 `/reports/new`이고 컬럼 칩·조건·"● 저장 안 됨"이 그대로다. 두 번째 뒤로 가기에서 같은 창이 다시 뜬다

### RQ-126 뒤로·앞으로 가기에서 떠나기를 고르면 멈춘 이동을 마저 해 이전·다음 화면으로 간다
- Given ① RQ-125의 Given과 같다. ② KIM이 `/reports/new`(빈 설계)에서 상단 메뉴 "Deals"를 눌러 `/deals`로 갔다가 브라우저 뒤로 가기로 `/reports/new`에 돌아와 컬럼 하나를 넣었다
- When ① 뒤로 가기를 하고 "떠나기"를 누른다. ② 브라우저 앞으로 가기를 하고 "떠나기"를 누른다
- Then ① 창이 한 번만 뜨고 "떠나기" 뒤 주소가 `/reports`이고 Reports 목록이 보이며, 이후 새로고침(`beforeunload`)을 막지 않는다. ② 창이 뜨고 "떠나기" 뒤 주소가 `/deals`다

### RQ-127 바뀌지 않았거나 되돌린 설계의 뒤로 가기와 링크로 떠난 이동은 묻지 않는다
- Given KIM이 `/reports`에서 "+ 새 리포트"를 눌러 `/reports/new`에 왔다
- When ① 아무것도 바꾸지 않고 뒤로 가기를 한다. ② 다시 들어와 컬럼을 넣었다 그 칩을 지우고 뒤로 가기를 한다. ③ 다시 들어와 컬럼을 넣고 상단 메뉴 "Deals"를 눌러 "떠나기"를 고른다
- Then ①② 확인 창 없이 주소가 `/reports`가 된다. ③ 확인 창은 링크에서 한 번만 뜨고 "떠나기" 뒤 두 번째 창 없이 주소가 `/deals`다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 초안 작성: 구현된 Reports 조회 엔진·디자이너 작성 동작 문서화(RQ-R1~RQ-R56, RQ-UC1~RQ-UC5) | RQ-001~RQ-107 신규 |
| 2026-11-11 | 사용자 결정 반영: 조회 Fake를 서버에 맞춤(행 수 문구·합계 행, 흉내 범위는 그대로, RQ-R56), 금액 건수 집계 `unit` 현행 유지(RQ-R36), 저장 정의 JSON 읽기·예전 형식 변환을 RQ 소유로(RQ-R57 신설, functional `test_saved_report_open.py`의 예전 형식 3개 시나리오 → RQ-109·RQ-110·RQ-111), RS·RC·CL·CD·RK 상호 참조를 규칙 번호로 | RQ-106 변경, RQ-108~RQ-112 신규 |
| 2026-11-11 | UI 문서 작성에 따라 공통 입력 참조를 UI 규칙 번호로 교체(머리말, 1장, RQ-R46, RQ-R47, 케이스 본문). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-13 | AC 수행일 지정(확정)에 맞춰 카탈로그 35·36·38 비고 보강. SQL·동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 최종 업데이트·Status 진입일·수행일·종료일을 date 형식으로 변경(카탈로그 27·28·38·39, RQ-R30, RQ-R58 신설). field key는 유지하고, 저장 리포트의 ymd_hm은 ymd로 자동 변환. 카탈로그·결과 열 형식 변경(호환 깨짐, 사용자 승인) | 신규 RQ-113~RQ-115. 변경 RQ-040, RQ-053 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): Deal Vendor 필수(DE-R7, SC-R22)로 Vendor 없는 Deal 예시를 바꿈(RQ-R33 문장 삭제, is_empty는 빈 Solution, NULL 정렬은 파트너사). `deal.vendor` 필드·연산자·SQL은 그대로 | 변경 RQ-032, RQ-046, RQ-051 |
| 2026-11-16 | 초안(사용자 확인 대기): Deal Solution → Product 이름 변경. 카탈로그 3번 key `deal.product`·이름 "Product"(RQ-R59 신설), 요청의 예전 key는 unknown-field, 저장 정의의 예전 key는 읽을 때 변환(RQ-R57 ④). **API 응답(카탈로그) 호환 깨짐**(사용자 승인) | 신규 RQ-116, RQ-117. 변경(표기·키): RQ-002, RQ-032 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): CM 확정: Memo → Comment 엔티티 분리. 카탈로그 `action.memo`를 `action.comment`(Comment(Action))로 바꾸고 `deal.comment`(Comment(Deal 전체))를 29번으로 추가(Deal 29·Action 12·전체 41, RQ-R60·R61 신설, RQ-R57 ⑤, RQ-R2, 2.2). 읽는 테이블에 `deal_comments` 추가. **API 응답(카탈로그) 호환 깨짐**(사용자 승인) | 신규 RQ-118~RQ-124. 변경 RQ-002 |
| 2026-11-17 | 프런트 Fake 카탈로그를 `deal.comment`·`action.comment`로 맞춤(CM-084) | 없음 |
| 2026-11-18 | 확정(2026-11-18 사용자 확인): 바뀐 설계에서 브라우저 뒤로·앞으로 가기도 떠날 때 확인(RQ-R54, RQ-UC5). 2026-10-27 결정 Q2=A의 '뒤로 가기 제외'를 대체, 코드의 직접 이동은 계속 묻지 않음. 앱 라우터를 데이터 라우터로 전환(프런트 전용, API·마이그레이션 없음) | 신규 RQ-125~RQ-127. 변경 없음(RQ-101·RQ-102 그대로) |
