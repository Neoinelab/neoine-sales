# Forecast: 실시간·월말 스냅숏   (feature 코드: FC, 상태: 확정(2026-11-11 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`backend/src/app/web/routers/forecast.py`, `app/web/schemas/forecast.py`, `app/application/forecast/{get_summary,get_snapshot_summary,list_snapshots,take_snapshot,ensure_monthly_snapshot,views}.py`, `app/application/ports/{forecast_repository,job_lock}.py`, `app/domain/forecast/{period,summary,snapshot,errors}.py`, `app/infra/db/{forecast_repository,forecast_snapshot_repository,advisory_job_lock,models_forecast}.py`, `app/infra/scheduling/periodic.py`, `app/container_forecast.py`, `app/main.py`의 lifespan, `app/config/{base,profiles}.py`의 스케줄러 설정, `frontend/src/features/forecast/*`, `data/forecast.ts`, `gateway/http/forecast.ts`, `test/fake/gateway/{forecast,forecastSnapshots}.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트·안내서가 어긋나던 점은 2026-11-11 사용자 결정으로 정리했습니다: Fake 게이트웨이는 서버 동작에 맞추고(FC-R36), 스냅숏 기준 월 직접 지정은 현행대로 문서화하며(FC-R12), Forecast 연도 선택지에는 '전체'가 없습니다(FC-R26, DL-R24). 안내서(`docs/user-guide.html`) 수정은 별도 문서 작업입니다. 결정 목록은 계획(`artifacts/10-analysis/fc-plan.md`)에 있습니다.

## 1. 개요

- 목적: 로그인한 모든 사용자가 Expected Close 기간(연·분기·월)별로 담당자 × Forecast 코드의 건수·금액을 보고(Open 합계와 Won 별도), 담당자 한 명의 Deal을 같은 조건으로 검토한다. 서버는 매월 전월 기준 스냅숏을 자동으로 저장하고, 화면은 "기준 시점"으로 그 저장값을 다시 볼 수 있다.
- 사용자(역할): admin·sales·user 모두 같은 화면·같은 데이터(조회 전용, 쓰기 동작 없음). 스냅숏 저장의 행위자는 서버 안의 주기 작업이다.
- 범위
  - 화면 `/forecast`: 필터(기준 시점·연도·Quarter·월·담당자·Vendor), 기준 문구, 요약 카드, 담당자별 요약 표, 선택한 담당자의 Deal 목록
  - API `GET /forecast/summary`, `GET /forecast/snapshots`, `GET /forecast/snapshots/{period}/summary`
  - 월말 스냅숏 저장(`TakeForecastSnapshot`)·자동 확인(`EnsureMonthlyForecastSnapshot`)·주기 실행기(`PeriodicTask`)·작업 잠금(`JobLock`, `PgAdvisoryJobLock`)·앱 lifespan의 스케줄러 시작·스케줄러 설정(`scheduler_enabled`·확인 간격, PL-R28이 FC로 넘김)
  - 스냅숏 테이블 3개(`forecast_snapshots`·`forecast_snapshot_columns`·`forecast_snapshot_cells`)의 컬럼·제약(SC가 넘긴 테이블별 스키마)
- 범위 밖(다른 feature)
  - Deal 조건(연·분기·월·담당자·Vendor)의 해석 자체 → DL(DL-R5·R6·R9, 한 곳에 있는 해석 DL-R15). FC는 같은 해석을 쓴다
  - Dashboard의 Forecast 탭(DSH-R19, DSH-R22, DSH-R23)·`/dashboard/summary`(DSH-R1~R12) → DSH. Dashboard 타일·분기 행이 FC 실시간 합계와 같아야 한다는 규칙은 DSH-R6·DSH-R8이 가진다
  - 담당자 Deal 목록과 "Deals 목록에서 모두 보기" 링크가 도착한 Deal 목록의 해석 → DL(DL-R20)
  - Forecast 코드 추가·이름·순서·결과(outcome) → CD(CD-R4, CD-R9, CD-R10, CD-R13, CD-R14)
  - 사용자 표시 참조 `UserRef`(US-R12), 사용자 삭제·퇴사 판정(US-R17) → US
  - 업무 날짜·응답 시각 오프셋·시각 표기·앱 시계 → TM(TM-R1, TM-R4, TM-R8, TM-R12, TM-R14)
  - 공통 권한 판정·Problem 형식·쿼리 id·화면 가드·상단 메뉴·오류 배너·게이트웨이 오류 → PL(PL-R2, PL-R5, PL-R12, PL-R15, PL-R16, PL-R29, PL-R34, PL-R37, PL-R39)
  - 연도 선택지 범위 규칙(`selectableYears`) → DL-R24(FC는 "전체" 없이 사용, FC-R26)
  - 기준선 마이그레이션·대리 키·FK 공통 규칙 → SC(SC-R11, SC-R15, SC-R17)
- 관련 화면·메뉴: 상단 메뉴 "Forecast"(PL-R34), 가드 RequireAuth(PL-R29).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 실시간 요약 | 요청 시점의 Deal 원장에서 바로 집계한 요약(`basis: "live"`) |
| 스냅숏 | 기준 월 하나에 대해 저장해 둔 집계(열 = 그때의 Forecast 코드 목록, 셀 = 그때의 모든 Deal 묶음). `basis: "snapshot"` |
| 기준 월(period) | 스냅숏의 이름인 연·월. 텍스트 형식은 `YYYY-MM` 하나뿐 |
| 기간 | 요약 조건의 Expected Close 범위: 연 / 연+분기 / 연+월(양끝 포함, 분기와 월은 함께 쓸 수 없음) |
| 열(column) | Lost가 아닌 Forecast 코드 하나(`{key, name, outcome, order}`) |
| 셀(cell) | (담당자, Forecast key)의 건수·금액. 금액은 `revenue_amount`(원) 합 |
| Total(Open) / `open_total` | outcome이 `open`인 열의 셀 합(Won·Lost 제외) |
| 원장 | 같은 조건의 Deal 목록(`GET /deals`, DL-R1) |
| 확인(check) | 스케줄러가 전월 스냅숏이 있는지 보고 없으면 만드는 한 번의 실행 |
| 작업 잠금 | 여러 서버 프로세스 중 한 곳만 확인을 하게 하는 잠금(`JobLock`, 작업 이름 `forecast-snapshot`) |

### 2.2 데이터 모델

읽는 값: `deals`(DE-R4 — `owner_user_id`·`forecast_key`·`revenue_amount`·`revenue_date`·`vendor_id`), `codes`(CD-R1·CD-R5 — Forecast 코드의 key·이름·outcome·order), `users`(US-R12 — UserRef).

소유 테이블(스냅숏, 대리 키는 SC-R11, FK 공통은 SC-R15·SC-R17)

| 테이블 | 컬럼 | 제약 |
| --- | --- | --- |
| `forecast_snapshots`(헤더) | `id` BIGINT identity PK, `snapshot_year` int, `snapshot_month` int, `taken_at` timestamptz (모두 NOT NULL) | UNIQUE(`snapshot_year`,`snapshot_month`) — 기준 월당 1행, CHECK `snapshot_month BETWEEN 1 AND 12` |
| `forecast_snapshot_columns`(그때의 코드 목록) | `id`, `snapshot_id` → `forecast_snapshots.id` ON DELETE CASCADE, `forecast_key` varchar(50), `forecast_name` varchar(50), `forecast_outcome` varchar(10), `forecast_order` int | UNIQUE(`snapshot_id`,`forecast_key`), CHECK `forecast_outcome IN ('open','won','lost')`. `codes`를 FK로 가리키지 않는다(과거 기록 보존) |
| `forecast_snapshot_cells`(Deal이 있는 칸) | `id`, `snapshot_id`, `revenue_year` int, `revenue_month` int, `owner_user_id` → `users.id` RESTRICT, `forecast_key` varchar(50), `deal_count` int, `amount` bigint | 복합 FK (`snapshot_id`,`forecast_key`) → columns ON DELETE CASCADE(이름 `fk_forecast_snapshot_cells_snapshot_id_snapshot_columns`, 헤더로 가는 직접 FK 없음), UNIQUE(`snapshot_id`,`revenue_year`,`revenue_month`,`owner_user_id`,`forecast_key`), CHECK `revenue_month BETWEEN 1 AND 12`, `deal_count >= 1`, `amount >= 0`, 인덱스 `ix_forecast_snapshot_cells_owner_user_id` |

조건 모델(`ForecastCriteria`): `period`(`ForecastPeriod{year 1900~9999, quarters 정규화된 집합 또는 없음, month 1~12 또는 없음}`), `owner_user_id?`, `vendor_id?`. `to_deal_query()`로 같은 값의 `DealQuery`(DL 2.2)가 된다.

### 2.3 비즈니스 규칙

실시간 요약 (`GET /forecast/summary`)
- **FC-R1** 로그인한 모든 역할이 읽는다(업무 조회, PL-R2). 읽기만 하고 아무것도 저장하지 않는다. 미인증은 401 `unauthenticated`(PL-R5). 다른 담당자의 숫자도 모든 역할에게 같다.
- **FC-R2** 쿼리 키는 `year`(필수), `quarter`, `month`, `owner_user_id`, `vendor_id` 다섯 개뿐이다. `year`는 정수 1900~9999, `quarter`는 정수 1~4 **한 값**(Deal 목록과 달리 여러 분기를 받지 않음), `month`는 정수 1~12, `owner_user_id`·`vendor_id`는 쿼리 id(PL-R15)다. 판정 순서: 401 → 422 `request-validation`(`year` 누락·정수 아님·범위 밖, `quarter`·`month` 범위 밖, id 형식, 모르는 키 — 예: `vendor=SAP`) → 422 `invalid-value` "Quarter와 월은 함께 선택할 수 없습니다."(quarter와 month를 함께 줌) → 결과.
- **FC-R3** 조건은 Deal 목록과 같은 해석(DL-R15)이다: 기간은 Expected Close가 그 해 1월 1일~12월 31일 / 그 분기 첫날~마지막 날 / 그 달 1일~말일(윤년 2월 29일 포함)에 들면 맞는다(DL-R9, 양끝 포함, 12-31은 그 해 Q4·12월, 01-01은 다음 해 Q1·1월). 연도를 채우는 규칙은 없다(`year` 필수). `owner_user_id`는 Owner가 같은 Deal(퇴사자 포함, DL-R5), `vendor_id`는 그 Vendor의 Deal이고 없는 id는 오류 없이 0건이다(DL-R6). Vendor 조건이 없으면 Vendor가 없는 Deal도 센다.
- **FC-R4** 열(`columns`)은 Forecast 코드 중 outcome이 `lost`가 아닌 것을 코드 order 오름차순으로 나열한 것이다. 항목은 정확히 `{key, name, outcome, order}`이고 이름·순서는 **지금** 코드 값이다(CD-R13 이름 변경, CD-R14 순서 변경이 바로 반영). admin이 추가한 코드(CD-R10, outcome `open`)도 열이 된다. 이름을 바꿔도 key와 그 key의 셀은 그대로다(CD-R9). 조건에 Deal이 없어도 열은 모두 나온다.
- **FC-R5** 셀은 (담당자, Forecast key)별 Deal 건수와 `revenue_amount` 합(원, 정수)이다. 2^31을 넘는 금액도 정확히 더한다. 각 행의 `cells`는 `columns`와 같은 순서·같은 key의 목록이고 Deal이 없는 칸은 `{count: 0, amount: 0}`이다. Lost Deal은 어떤 셀·합계에도 들어가지 않는다.
- **FC-R6** `open_total`은 그 행에서 outcome이 `open`인 열의 셀 합이다(Won·Lost 제외). 합계 행(`total`)은 담당자 행들의 셀 합이고 `owner`는 null이다.
- **FC-R7** 행(`rows`)은 기간·조건 안에 Open 또는 Won Deal이 한 건이라도 있는 담당자만이다(Lost만 있으면 행이 없다). 행의 `owner`는 UserRef(US-R12)이며 퇴사자도 남는다(`resigned: true`, `label` `<이름>(퇴사)`). 순서: 재직자 먼저 → UserRef `name`의 문자 코드 순 → 사용자 id 순.
- **FC-R8** 응답은 정확히 `{basis, as_of, snapshot_period, period, columns, rows, total}`이다. 실시간은 `basis` `"live"`, `as_of` = 서버 현재 시각(TM-R1, 오프셋 포함 TM-R8), `snapshot_period` null. `period`는 `{year, quarter, month, from, to}`: `quarter`는 분기가 하나일 때 그 값·아니면 null, `month`는 월 또는 null, `from`·`to`는 기간 양끝 날짜(예: 2026 Q4 → 2026-10-01~2026-12-31, 2028년 2월 → 2028-02-01~2028-02-29). 조건에 Deal이 없으면 `rows` `[]`, 합계 셀·`open_total` 모두 0이다.
- **FC-R9** 원장 일치: 같은 연·분기·월·담당자·Vendor 조건의 Deal 목록에서 Lost가 아닌 Deal의 건수·금액 = 요약 `total`의 Open 셀 합(`open_total`) + Won 열 셀. Deal의 경고 상태(기한초과·미업데이트, RK-R3~R5)는 집계에 영향이 없다.

월말 스냅숏 저장 (`TakeForecastSnapshot`)
- **FC-R10** 스냅숏 하나는 기준 월, 생성 시각 `taken_at`(= 실행 시각), 열(실행 시점의 **모든** Forecast 코드 — Lost 포함 — 의 key·이름·outcome·order), 셀(실행 시점의 **모든** Deal을 기간 제한 없이 (Expected Close 연, Expected Close 월, Owner, Forecast key)로 묶은 건수·금액, Lost 포함)이다. 셀은 Deal이 있는 칸만 저장하고 코드 속성(이름 등)은 열에만 있다. 같은 달이라도 연도가 다르면 다른 셀이다. Deal이 하나도 없으면 열만 저장한다. 값은 실행 순간의 Deal이다(월말 순간이 아니라 확인이 실행된 시각, FC-R19).
- **FC-R11** 기준 월당 스냅숏은 하나다. 처음 저장하면 새로 만들고(결과 `replaced: false`), 같은 기준 월로 다시 저장하면 생성 시각·열·셀을 통째로 바꾼다(`replaced: true`, 그 사이 지운 Deal의 셀은 사라짐, 열은 지금 코드 목록). 다른 기준 월의 스냅숏은 바뀌지 않는다. 결과는 `{period, taken_at, cell_count, replaced}`다.
- **FC-R12** 대상 기준 월: 지정하지 않으면 실행 시각의 업무 날짜(TM-R4)의 전월이다(1월 1일 실행 → 전년 12월, 어느 달 말일 23시 실행 → 그 달의 전월). 지정하면 그 업무 날짜의 전월·당월만 허용하고, 그 밖(전전월 이전·다음 달 이후)은 `InvalidValueError` "<YYYY-MM> 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다."로 거절하며 아무것도 쓰지 않는다(기존 스냅숏 그대로). (지정 경로를 부르는 운영 호출자는 현재 없지만 현행 규칙으로 문서화하고 FC-021로 검증한다, 2026-11-11 결정.)
- **FC-R13** 저장은 한 트랜잭션이다: 중간에 실패하면 롤백되어 이전 스냅숏(있었다면)이 그대로 남는다. 열 목록을 읽은 뒤 Deal이 열에 없는 Forecast key로 옮겨져 셀이 복합 FK에 막히면 `RuntimeError` "스냅숏을 만드는 사이 Forecast 코드가 바뀌어 저장하지 못했습니다. 다시 실행하세요."이다. 같은 기준 월의 저장은 기준 월별 트랜잭션 잠금으로 순서대로 처리한다(동시성 동작은 검증 대상 아님).
- **FC-R14** 스냅숏 테이블 3개의 컬럼·제약은 2.2 표와 같다(head 스키마).
- **FC-R15** 스냅숏 셀의 Owner는 사용자 연결이다(SC-R17의 `forecast_snapshot_cells.owner_user_id`). 그래서 스냅숏에만 남은 사용자를 삭제하면 퇴사 처리되고(US-R17, 결과 `resigned`) 스냅숏 요약에 `<이름>(퇴사)`로 남는다. 퇴사·삭제 판정 규칙은 US-R17이 가지고, 스냅숏 셀 때문에 퇴사되는 결과 케이스(FC-024)는 FC가 가진다(2026-11-11 결정). 어떤 셀도 가리키지 않는 사용자는 스냅숏이 있어도 물리 삭제된다(`deleted`).

스냅숏 읽기
- **FC-R16** `GET /forecast/snapshots`(로그인한 모든 역할, 쿼리 없음)는 200 `{items: [{period: "YYYY-MM", taken_at}]}`(항목 키는 이 둘)이다. 기준 월 최근 순(연도 먼저, 같은 해는 월)이며 저장된 것이 없으면 `items` `[]`다. `taken_at`은 서버 오프셋 시각(TM-R8).
- **FC-R17** `GET /forecast/snapshots/{period}/summary`(로그인한 모든 역할)의 쿼리는 `year`(필수)·`quarter`·`month`·`owner_user_id` 네 개뿐이고 값 규칙은 FC-R2와 같다. `vendor_id`를 포함한 모르는 키는 422 `request-validation`이다(스냅숏에는 Vendor가 없다). 판정 순서: 401 → 쿼리 422(`request-validation` → `invalid-value` "Quarter와 월은 함께 선택할 수 없습니다.") → 기준 월 404. `period`가 정확히 `YYYY-MM`(7자, 숫자 4 + `-` + 숫자 2, 월 01~12)이 아니거나(예: `2026-9`, `abc`, `2026-13`) 그 기준 월 스냅숏이 없으면 404 `not-found` "해당 기준 월의 스냅숏이 없습니다: <period>"다.
- **FC-R18** 스냅숏 요약은 실시간 요약과 같은 모양(FC-R8)이고 `basis` `"snapshot"`, `as_of` = 그 스냅숏의 `taken_at`, `snapshot_period` = 기준 월이다. 값은 저장된 셀이라 이후 Deal 추가·수정·삭제와 무관하다. 열은 **저장된 코드 목록**에서 Lost를 뺀 것(저장된 order 순, 저장 당시 이름)이다: 저장 뒤 이름을 바꾼 코드는 옛 이름, 저장 뒤 추가한 코드는 열이 아니고, 저장 당시 Deal이 없던 코드도 0건 열이다. 기간은 저장된 월별 셀 중 (연, 월)이 기간에 드는 것만 모은다(분기는 그 분기의 세 달). `owner_user_id`는 그 담당자의 셀만이다. 행·합계·`open_total`·Lost 제외 규칙은 FC-R5~R7과 같고, 행의 `owner`는 **지금의** 사용자 정보(현재 이름·퇴사 여부)다. 기간에 셀이 하나도 없어도 열은 모두 나오고 `rows`는 `[]`다.

스케줄러
- **FC-R19** 확인(`EnsureMonthlyForecastSnapshot`): 기준 월 = 확인 시각의 업무 날짜 전월(잠금을 잡기 전에 한 번 계산). 작업 잠금 `forecast-snapshot`을 기다리지 않고 잡아 본다. 다른 곳이 쥐고 있으면 아무것도 읽거나 쓰지 않고 결과 `locked-elsewhere`. 잡았으면 전월 스냅숏이 있으면 아무것도 바꾸지 않고 `already-exists`(생성 시각·셀 유지, 그 사이 Deal이 바뀌었어도), 없으면 FC-R10으로 전월분을 저장하고 `taken`. 그래서 월초에 앱이 꺼져 있었어도 그달 안의 첫 확인이 전월분을 만들고, 전전월 이전은 만들지 않는다. 저장 실패는 호출자에게 전파되며 잠금은 어떤 경우든 블록을 나갈 때 풀린다.
- **FC-R20** 작업 잠금(`JobLock.try_hold(job)`): 기다리지 않는다. 잡으면 True이고 블록을 나갈 때(오류 포함) 푼다. 다른 보유자가 있으면 False이며 보유자의 잠금을 풀지 않는다. 다른 작업 이름끼리는 막지 않는다. 구현(`PgAdvisoryJobLock`)은 PostgreSQL 세션 advisory lock이고 키는 `('FJOB' << 32) | crc32(작업 이름)`(프로세스 간 같은 값, signed bigint 범위)이다. 해제에 실패하면 연결을 버려 잠금이 풀에 남지 않게 한다.
- **FC-R21** 주기 실행기(`PeriodicTask`): 시작하자마자 한 번 실행하고(첫 실행 전에 기다리지 않음) 이후 간격마다 반복한다. 실행 중 예외는 로그 "주기 작업 실패(다음 주기에 다시 시도): <이름>"을 남기고 계속한다. 취소는 전파되어 루프가 끝난다. 간격이 0 이하면 `ValueError`.
- **FC-R22** 앱 lifespan: `scheduler_enabled`가 참이고 앱이 실제 Container를 만든 경우(유스케이스를 주입한 테스트 앱이 아닐 때)만 기동 때 확인 주기 실행기(이름 `forecast-snapshot-check`)를 시작한다. 종료 때 그 작업을 취소한 뒤 Container를 정리한다. 확인 결과가 `taken`이면 INFO 로그 "Forecast 스냅숏 저장 완료: period=… cell_count=… replaced=… taken_at=…", 그 밖은 DEBUG 로그다.
- **FC-R23** 설정: `APP_SCHEDULER_ENABLED`(local 기본 false, dev·product 기본 true, env로 끄거나 켬), `APP_FORECAST_SNAPSHOT_CHECK_INTERVAL_SECONDS`(기본 600, 30~3600 밖이면 설정 오류로 기동 실패). 수동 실행 명령(CLI)은 없다.

화면 (frontend, `/forecast`)
- **FC-R24** 화면 틀: 제목(h1) "Forecast", 필터 폼(이름 "Forecast 필터", FC-R26), 요약 오류 배너(PL-R37), 처음 읽는 동안 "불러오는 중…"(`role=status`), 응답이 오면 기준 문구(FC-R28), 행이 있으면 요약 카드(FC-R29)와 요약 표(FC-R30), 행이 없으면 "조건에 맞는 Deal이 없습니다.", 담당자를 골랐으면 그 아래 Deal 목록(FC-R32). 모든 역할이 같은 화면을 보며 등록·수정·삭제 버튼이 없다.
- **FC-R25** URL이 조건의 정본이다(키 `year`, `quarter`, `month`, `owner`, `vendor`, `sel`, `snap`, 잘못된 값은 오류 없이 무시).
  - `year`: 4자리 숫자면 그 연도, 없거나 아니면 앱 시계(TM-R12)의 올해(주소는 바꾸지 않음).
  - `quarter`: `1`~`4`만. `month`: `1`~`12`(앞자리 0·소수·문자 무시). 둘 다 있으면 `quarter`만 쓴다.
  - `owner`·`vendor`·`sel`: 1~2^53−1 정수 id만(`0`, `-1`, `1.5`, `1e3`, `01`, `+3`, UUID·이름 무시).
  - `snap`: 정확히 `YYYY-MM`(월 01~12)만(`2026-9`, `2026-00`, `202609`, `2026/09`, 앞 공백, `2026-09-01` 무시 → 실시간).
  - 필터를 바꾸면 주소를 다시 쓴다: `year`는 항상, `quarter` 또는 `month`(함께 쓰지 않음), `owner`, `vendor`, `sel`, `snap`(값이 있을 때만). 새로 고침 없이 표가 바뀐다.
- **FC-R26** 필터 칸(이 순서): 기준 시점, 연도, Quarter, 월, 담당자, Vendor.
  - 기준 시점: "지금"(값 없음, 기본) + 저장된 스냅숏마다 "<YYYY-MM> 월말"(서버 목록 순서). URL `snap`이 목록에 없으면 그 값을 선택지로 하나 더 보인다. 고르면 `snap`을 바꾸고 담당자 선택(`sel`)을 지운다. "지금"을 고르면 `snap`을 지운다.
  - 연도: DL-R24의 범위(가장 이른 Expected Close 연도와 올해 중 이른 해 ~ 내년, 읽는 동안·실패·Deal 없음이면 올해·내년, URL 연도가 범위 밖이면 더해서 선택)이되 **"전체"가 없다**(연도 필수, '전체'는 Deal 목록에만 있다 — DL-R24, 2026-11-11 결정). 스냅숏 모드에서도 같다. 바꾸면 `year`.
  - Quarter: "전체" + Q1~Q4 단일 선택. 고르면 `month`를 지운다. 월: "전체" + 1월~12월. 고르면 `quarter`를 지운다.
  - 담당자: 사용자 선택(퇴사자 포함), 바꾸면 `owner`.
  - Vendor: 값은 id, 표시는 이름이다. 목록을 읽은 뒤 URL `vendor`가 목록에 없으면 "전체"로 보이고 요약·담당자 Deal 목록 조회에서 뺀다. 읽는 동안·실패하면 "선택한 Vendor"를 선택된 상태로 보이고 URL id로 조회한다(DL-R26과 같은 방식). 스냅숏 모드(FC-R33)에서는 비활성이다.
  - 연도 기준·Vendor 목록·스냅숏 목록을 읽지 못하면 필터 안에 오류 배너를 보이고, 요약은 그대로 조회된다.
- **FC-R27** 조회: `snap`이 없으면 실시간 요약(연도, Quarter 또는 월, 담당자, 조회에 쓰는 Vendor), 있으면 그 기준 월의 스냅숏 요약(Vendor 없이)을 읽는다. 조건이 바뀌어 다시 읽는 동안 이전 요약을 그대로 보인다. 조회가 실패하면(501 포함, 특별한 "준비 중" 처리 없음) 오류 배너에 서버 문구를 보이고 필터는 계속 보여 조건을 바꿀 수 있다. 없는 기준 월이면 서버 404 문구("해당 기준 월의 스냅숏이 없습니다: <period>", FC-R17)를 배너로 보인다.
- **FC-R28** 기준 문구(응답이 있으면 행이 없어도 보임): 실시간 "기준: 지금(YYYY-MM-DD HH:mm)", 스냅숏 "기준: <YYYY-MM> 월말(생성 YYYY-MM-DD HH:mm)". 시각은 서버 문자열의 오프셋 벽시계 그대로다(TM-R14).
- **FC-R29** 요약 카드(섹션 이름 "<기간> 요약", 기간 = "<연도> Q<n>" / "<연도> <m>월" / "<연도> 전체"): "Open 합계(단위:원)" = 합계 행 `open_total` 금액과 "<기간> · N건", "Won (별도, 단위:원)" = Won 열 합계 셀들의 금액 합과 "<기간> · N건".
- **FC-R30** 요약 표: 가로 스크롤 영역(`region` "담당자별 Forecast 표 (가로 스크롤)", 키보드 포커스 가능) 안의 표 "담당자별 Forecast 요약", 캡션 "셀 값: 건수 · 금액(단위:원)". 머리글: "담당자", Open 열을 서버 순서의 **역순**(기본 코드면 Commit, Most Likely, Best, Pipeline), "Total(Open)", Won 열. 셀은 "N건 · <원 단위 콤마>", 0건은 "—". 행은 서버 순서, 담당자 칸은 UserRef `label`(퇴사자 "<이름>(퇴사)"). 맨 아래 "합계" 행. Lost 열은 없다.
- **FC-R31** 담당자 선택(실시간만): 담당자 칸은 버튼(`aria-pressed`)이고 누르면 URL `sel`=그 id, 같은 버튼을 다시 누르면 `sel`을 지운다. 고른 행은 강조된다. 담당자 상세로 가는 메뉴·링크는 없다.
- **FC-R32** 선택한 담당자의 Deal 목록(실시간에서 `sel`이 있을 때): 영역 제목 "선택한 담당자: <이름>"(요약 행 이름, 없으면 사용자 목록의 label, 그것도 없으면 "선택한 담당자")과 "선택 해제" 버튼(`sel` 삭제).
  - 요청: `GET /deals`에 담당자, 연도, Quarter(분기 하나) 또는 월, 조회에 쓰는 Vendor, `forecast_key` = 요약 열 중 Lost가 아닌 key 전부(정렬), 정렬 Expected Close 오름차순, `limit` 200. Lost가 아닌 key가 하나도 없으면 요청하지 않고 "조건에 맞는 Deal이 없습니다."만 보인다.
  - 위에 "Open N건 · 금액(단위:원) <금액>" = 요약 표 그 담당자 행의 `open_total`(목록에서 다시 계산하지 않음, 행이 없으면 생략). Lost Deal과 Lost 관련 안내는 없다.
  - `total`이 받은 `limit`보다 크면 "총 N건 중 200건만 표시합니다." + 링크 "Deals 목록에서 모두 보기" = `/deals?owner=<id>&year=<연도>[&quarter=<n> | &month=<m>][&vendor=<id>]&forecast=<Lost 아닌 key 콤마 목록>`(DL-R20이 해석, Lost 제외 목록). 넘지 않으면 안내·링크가 없다.
  - 표 "<이름>의 Deal 목록"(가로 스크롤 영역): 열 Deal(이름 링크 `/deals/<code>` + 고객 회사명), Status 배지, Forecast 배지, 금액(단위:원), Expected Close, Next Action(내용 + "기한 · 상태 라벨", 없으면 "—"). 빈 목록이면 "조건에 맞는 Deal이 없습니다.". 읽는 동안 "불러오는 중…", 실패하면 오류 배너.
- **FC-R33** 스냅숏 모드(`snap` 있음): Vendor 칸 비활성 + 안내 "스냅숏에서는 Vendor 필터를 사용할 수 없습니다."(실시간에서는 활성·안내 없음), URL `vendor`는 스냅숏 요청에 보내지 않는다. 요약 표의 담당자 이름은 버튼이 아닌 글자이고 URL에 `sel`이 있어도 선택 표시·담당자 Deal 목록·링크가 없다. 실시간에서 스냅숏으로 바꾸면 `sel`을 지우므로 다시 "지금"으로 돌아와도 목록이 열리지 않는다.
- **FC-R34** 게이트웨이(`gateway/http/forecast.ts`): `summary(query)` = `GET /forecast/summary`에 `year`와 있는 값만 `quarter`·`month`·`owner_user_id`·`vendor_id`. `snapshots()` = `GET /forecast/snapshots`(쿼리 없음) → `[{period, takenAt}]`(서버 순서). `snapshotSummary(period, query)` = 경로에 `period`, 쿼리는 `year`·`quarter`·`month`·`owner_user_id`만(호출자가 Vendor를 넘겨도 보내지 않음). 응답 변환: 열 `{key, name, outcome(won이면 won, 그 밖 open), order}`, 행 `{ownerId: owner.id, ownerName: owner.label(합계 행은 null·"합계"), cells: key별 레코드(없는 key는 0), total: open_total}`, `basis`·`asOf`·`snapshotPeriod`(없으면 null)·보낸 조건(`query`). 오류는 PL-R39(`ApiError`).
- **FC-R35** 갱신: Forecast 요약 캐시는 Deal·코드·사용자·Action 변경 훅이 함께 무효화하는 묶음(`['forecast']`) 아래에 있어, 같은 화면 세션에서 Deal 값을 바꾸면 요약을 다시 읽는다.
- **FC-R36** Fake 게이트웨이(`test/fake/gateway/{forecast,forecastSnapshots}.ts`, 스냅숏 fixture `test/fixtures/forecastSnapshot.ts`)는 실시간·스냅숏 요약에서 서버와 같은 규칙을 따른다. 서버와 달랐던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**: ① 스냅숏 열은 저장된 코드 목록(Lost 제외, 저장 order 순·저장 당시 이름)이고 저장 당시 Deal이 없던 코드도 0건 열이다(FC-R18 — 저장 셀에서 열을 만들지 않으며 fixture는 저장 열 목록을 가진다) ② 행 순서는 재직자 먼저 → UserRef `name`의 문자 코드 순 → 사용자 id 순이다(FC-R7 — `localeCompare` 아님) ③ 없는 기준 월은 404 `not-found` "해당 기준 월의 스냅숏이 없습니다: <period>"다(FC-R17) ④ 스냅숏 요약에 Vendor 조건이 오면 서버와 같은 422 `request-validation`(게이트웨이 kind `validation`, Fake 고유 문구 아님)이다(FC-R17. 게이트웨이·화면은 Vendor를 보내지 않는다 — FC-R33·R34). 그래서 케이스 기대 결과는 서버 동작 기준이다(FC-075, FC-081).

### 2.4 상태와 전이

스냅숏(기준 월 하나): 없음 → (확인 또는 저장) → 있음(생성 시각 T1) → (같은 기준 월 저장 — FC-R11, 지정 저장만) → 있음(T2). 확인(FC-R19)은 "있음"을 바꾸지 않는다. 삭제 경로는 없다.

확인 한 번의 결과: `locked-elsewhere` | `already-exists` | `taken` | (예외 전파).

화면 기준 시점: 지금(`snap` 없음) ⇄ 스냅숏(`snap=YYYY-MM`). 지금 → 스냅숏 전환은 `sel`을 지운다.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /forecast/summary`, `GET /forecast/snapshots`, `GET /forecast/snapshots/{period}/summary` | 401 | 가능 | 가능 | 가능 |
| 화면 `/forecast`(요약·담당자 Deal 목록·기준 시점) | `/login`으로 | 가능 | 가능 | 가능 |
| 스냅숏 저장 | HTTP 경로 없음(서버 주기 작업만) | — | — | — |

세 경로는 업무 조회(PL-R2)라 역할 가드·CSRF가 없다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/forecast/summary` | query `year`(필수, 1900~9999), `quarter?`(1~4), `month?`(1~12), `owner_user_id?`(id), `vendor_id?`(id) | 200 `ForecastSummaryResponse` | 401, 422 `request-validation`·`invalid-value` |
| GET `/forecast/snapshots` | — | 200 `{items: [{period: str, taken_at: datetime}]}` | 401 |
| GET `/forecast/snapshots/{period}/summary` | path `period`(`YYYY-MM`), query `year`(필수), `quarter?`, `month?`, `owner_user_id?` | 200 `ForecastSummaryResponse` | 401, 404 `not-found`, 422 `request-validation`·`invalid-value` |

- `ForecastSummaryResponse` = `{basis: "live"|"snapshot", as_of: datetime, snapshot_period: str|null, period: {year, quarter: int|null, month: int|null, from: date, to: date}, columns: [{key, name, outcome: "open"|"won"|"lost", order}], rows: [Row], total: Row}`, `Row` = `{owner: UserRef|null, cells: [{key, count, amount}], open_total: {count, amount}}`.
- openapi: 세 경로는 GET만 있고, 요약 경로의 파라미터 이름은 정확히 `year`·`quarter`·`month`·`owner_user_id`·`vendor_id`, 스냅숏 요약은 `period`(path)와 `year`·`quarter`·`month`·`owner_user_id`다.

### 2.7 화면 동작

FC-R24~FC-R36.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| `year` 누락·형식·범위, `quarter`·`month` 범위, id 형식, 모르는 키(스냅숏 요약의 `vendor_id` 포함) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12) |
| Quarter와 월 동시 | 422 `invalid-value` | Quarter와 월은 함께 선택할 수 없습니다. |
| 형식이 틀리거나 없는 기준 월 | 404 `not-found` | 해당 기준 월의 스냅숏이 없습니다: <period> |
| 미인증 | 401 `unauthenticated` | 로그인이 필요합니다(PL-R5) |
| (내부) 허용되지 않은 지정 기준 월 | `InvalidValueError` | <YYYY-MM> 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다. |
| (내부) 저장 중 코드 변경 | `RuntimeError` | 스냅숏을 만드는 사이 Forecast 코드가 바뀌어 저장하지 못했습니다. 다시 실행하세요. |

화면 문구: "Forecast", "기준 시점", "지금", "<YYYY-MM> 월말", "기준: 지금(…)", "기준: <YYYY-MM> 월말(생성 …)", "불러오는 중…", "조건에 맞는 Deal이 없습니다.", "Open 합계(단위:원)", "Won (별도, 단위:원)", "셀 값: 건수 · 금액(단위:원)", "Total(Open)", "합계", "선택한 담당자: <이름>", "선택 해제", "총 N건 중 200건만 표시합니다.", "Deals 목록에서 모두 보기", "선택한 Vendor", "스냅숏에서는 Vendor 필터를 사용할 수 없습니다.". 서버 문구 표시는 PL-R37.

## 3. Business use case

### FC-UC1 실시간 Forecast 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, 메뉴 Forecast(`/forecast`)
- 기본 흐름: 올해 전체 기간의 담당자별 요약이 열린다(FC-R25) → 연도·Quarter·월·담당자·Vendor를 바꾸면 주소가 바뀌고 요약을 다시 읽는다(FC-R1~R9, R26, R27) → 카드와 표에서 Open 합계·Won을 본다(FC-R29, R30)
- 대안: 주소를 공유해 같은 조건으로 연다, 기간에 Deal이 없으면 빈 문구
- 예외: 잘못된 URL 값은 무시, 서버 오류는 배너, 연도·Vendor 목록 실패는 필터 배너
- 결과: 같은 조건의 Deal 목록과 일치하는 요약(FC-R9)

### FC-UC2 담당자 Deal 검토
- 행위자: 로그인한 모든 역할
- 사전 조건: 실시간 요약(FC-UC1)
- 기본 흐름: 표에서 담당자를 누른다 → 아래에 같은 조건·Lost 제외의 그 담당자 Deal이 Expected Close 순으로 나온다 → Deal 이름으로 상세로 간다(FC-R31, R32)
- 대안: 200건을 넘으면 Deals 목록 링크로 전부 본다, "선택 해제"나 같은 버튼으로 닫는다
- 예외: 목록 조회 실패는 배너
- 결과: 요약 행의 Open 합계와 같은 조건의 Deal 목록

### FC-UC3 월말 스냅숏 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: 저장된 스냅숏이 하나 이상
- 기본 흐름: "기준 시점"에서 "<YYYY-MM> 월말"을 고른다 → 같은 모양의 요약이 저장값으로 나오고 기준 문구가 바뀐다(FC-R16~R18, R26, R28, R33)
- 대안: 연도·Quarter·월·담당자로 저장값을 다시 거른다, "지금"으로 돌아간다
- 예외: 스냅숏이 없으면 "지금"만, 없는 기준 월 주소는 서버 문구 배너, 형식이 틀린 `snap`은 실시간
- 결과: 저장 당시의 값·코드 이름으로 된 요약(Vendor 조건·담당자 Deal 목록 없음)

### FC-UC4 전월 스냅숏 자동 저장
- 행위자: 서버(앱 lifespan의 주기 작업)
- 사전 조건: `scheduler_enabled`가 참인 프로세스가 떠 있음
- 기본 흐름: 기동 직후와 설정 간격마다 확인한다 → 작업 잠금을 잡은 한 곳만 → 전월 스냅숏이 없으면 그 순간의 모든 Deal로 저장한다(FC-R10, R19~R23)
- 대안: 이미 있으면 아무것도 하지 않음, 다른 프로세스가 잠금을 쥐면 건너뜀, 월초에 꺼져 있었으면 그달 첫 확인이 만든다
- 예외: 저장 실패는 로그를 남기고 다음 주기에 다시 시도(FC-R21), 이전 스냅숏은 그대로(FC-R13)
- 결과: 기준 월당 하나의 스냅숏, 전전월 이전은 만들지 않음

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM·LEE·PARK(sales), VIEWER(user). 서버 업무 시간대 Asia/Seoul, 실시간 기준 시각 2026-10-15. 스냅숏 실행 시각 예: RUN 2026-10-01 00:05, LATER 2026-10-01 09:00, MID 2026-10-15 14:30, AUG 2026-09-01 00:05. 기본 Forecast 코드는 pipeline·best·most_likely·commit(open), won, lost(CD-R2). backend 케이스는 Fake UoW(Deal·코드·사용자·Vendor·Forecast 집계·스냅숏 Fake, `FakeJobLock`, 고정 Clock)를 쓰는 유스케이스 단위 테스트, FakeUseCases + TestClient를 쓰는 web 단위 테스트, 그리고 Fake와 SQL에 함께 도는 Repository 계약·잠금·스키마 테스트(integration 표시)다. frontend 케이스는 Fake 게이트웨이(기준 시각 2026-10-15T09:00+09:00, 스냅숏 fixture 2026-09·생성 2026-10-01 00:05)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| FC-001 | 모든 역할이 실시간 요약을 읽고 미인증은 401이다 | FC-R1, FC-UC1 | backend | `web/test_forecast_routes.py` |
| FC-002 | 실시간 요약은 담당자·Forecast 코드별 건수·금액이고 Lost와 기간 밖 Deal은 빠진다 | FC-R3, FC-R5, FC-UC1 | backend | `application/test_get_forecast_summary.py` |
| FC-003 | Total(Open)은 Open 열 합이고 Won·Lost를 빼며 합계 행은 담당자 행의 합이다 | FC-R6, FC-UC1 | backend | `application/test_get_forecast_summary.py` |
| FC-004 | Lost만 있는 담당자는 행이 없다 | FC-R7, FC-UC1 | backend | `application/test_get_forecast_summary.py` |
| FC-005 | 퇴사한 담당자도 행에 남고 재직자 다음에 이름 순으로 온다 | FC-R7, FC-UC1 | backend | `application/test_get_forecast_summary.py` |
| FC-006 | 열은 Lost를 뺀 코드 order 순이고 바꾼 이름·추가한 Open 코드를 따르며 셀은 열 순서의 목록이다 | FC-R4, FC-R5, FC-UC1 | backend | `application/test_get_forecast_summary.py` |
| FC-007 | 기간은 Expected Close의 연·분기·월 양끝을 포함하고 이웃 기간은 뺀다 | FC-R3, FC-UC1 | backend | `repositories/test_forecast_tally_contract.py` |
| FC-008 | owner_user_id·vendor_id는 그 담당자·Vendor의 Deal만 센다 | FC-R3, FC-UC1 | backend | `application/test_get_forecast_summary.py`, `repositories/test_forecast_tally_contract.py` |
| FC-009 | Deal이 없는 기간도 모든 열과 0인 합계를 돌려준다 | FC-R8, FC-UC1 | backend | `application/test_get_forecast_summary.py`, `web/test_forecast_routes.py` |
| FC-010 | 응답은 basis live·서버 현재 시각·기간 양끝 날짜를 담는다 | FC-R8, FC-UC1 | backend | `application/test_get_forecast_summary.py`, `web/test_forecast_routes.py` |
| FC-011 | 요약 합계는 같은 조건의 Deal 목록(Lost 제외) 건수·금액과 같다 | FC-R9, FC-UC1 | backend | `repositories/test_forecast_tally_contract.py` |
| FC-012 | 경고 상태는 Forecast 집계를 바꾸지 않는다 | FC-R9, FC-UC1 | backend | `repositories/test_forecast_tally_contract.py` |
| FC-013 | 2^31을 넘는 금액도 정확히 더한다 | FC-R5, FC-UC1 | backend | `repositories/test_forecast_tally_by_month_contract.py`, `repositories/test_forecast_tally_contract.py` |
| FC-014 | 연도 누락·범위 밖·형식 오류·모르는 키는 422 request-validation이다 | FC-R2, FC-UC1 | backend | `web/test_forecast_routes.py` |
| FC-015 | Quarter와 월을 함께 주면 422 invalid-value와 안내 문구다 | FC-R2, FC-UC1 | backend | `web/test_forecast_routes.py` |
| FC-016 | openapi에 요약 경로는 GET뿐이고 파라미터는 다섯 개다 | FC-R2 | backend | `web/test_forecast_routes.py` |
| FC-017 | 스냅숏 셀은 모든 Deal을 연·월·담당자·Forecast key로 묶고 Lost도 담는다 | FC-R10, FC-UC4 | backend | `application/test_take_forecast_snapshot.py` |
| FC-018 | 스냅숏 열은 실행 시점의 Forecast 코드 전부(Lost·Deal 없는 코드 포함)다 | FC-R10, FC-UC4 | backend | `application/test_take_forecast_snapshot.py` |
| FC-019 | 대상 기준 월을 정하지 않으면 업무 날짜의 전월이다 | FC-R12, FC-UC4 | backend | `application/test_take_forecast_snapshot.py` |
| FC-020 | 같은 기준 월을 다시 저장하면 통째로 바꾸고 다른 기준 월은 그대로다 | FC-R11, FC-UC4 | backend | `application/test_take_forecast_snapshot.py`, `repositories/test_forecast_snapshot_repository_contract.py` |
| FC-021 | 지정 기준 월은 전월·당월만 되고 그 밖은 거절하며 아무것도 쓰지 않는다 | FC-R12 | backend | `application/test_take_forecast_snapshot.py` |
| FC-022 | 저장이 실패하면 이전 스냅숏이 남고 코드가 바뀐 충돌은 다시 실행 안내다 | FC-R13, FC-UC4 | backend | `application/test_take_forecast_snapshot.py`, `repositories/test_forecast_snapshot_stale_columns.py` |
| FC-023 | 스냅숏 테이블 3개의 컬럼·제약이 명세와 같다 | FC-R14 | backend | `infra/schema/test_forecast_snapshot_schema.py` |
| FC-024 | 스냅숏에만 남은 담당자를 삭제하면 퇴사 처리되고 셀이 없으면 물리 삭제된다 | FC-R15 | backend | `application/test_forecast_snapshot_user_delete.py` |
| FC-025 | 스냅숏 목록은 기준 월 최근 순의 period·taken_at이고 없으면 빈 목록이다 | FC-R16, FC-UC3 | backend | `application/test_list_forecast_snapshots.py`, `repositories/test_forecast_snapshot_repository_contract.py`, `web/test_forecast_snapshot_routes.py` |
| FC-026 | 스냅숏 요약은 실시간과 같은 모양이고 basis snapshot·생성 시각·기준 월을 담는다 | FC-R18, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py`, `web/test_forecast_snapshot_routes.py` |
| FC-027 | 스냅숏 값은 저장 뒤 Deal을 추가·삭제해도 바뀌지 않는다 | FC-R18, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py` |
| FC-028 | 스냅숏 열은 저장된 코드 목록이다(옛 이름, 뒤에 추가한 코드 없음, 0건 열 포함) | FC-R18, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py` |
| FC-029 | 스냅숏 요약은 저장된 월별 셀을 기간으로 모은다 | FC-R18, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py`, `web/test_forecast_snapshot_routes.py` |
| FC-030 | 스냅숏 요약의 owner_user_id는 그 담당자 행만 남긴다 | FC-R18, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py`, `web/test_forecast_snapshot_routes.py` |
| FC-031 | 스냅숏의 Lost 셀은 열·합계·행에 나오지 않는다 | FC-R18, FC-R7, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py` |
| FC-032 | 스냅숏 행의 담당자는 지금 사용자 정보이고 재직자 먼저 이름 순이다 | FC-R18, FC-R7, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py` |
| FC-033 | 없거나 형식이 틀린 기준 월은 404 not-found다 | FC-R17, FC-UC3 | backend | `application/test_get_forecast_snapshot_summary.py`, `web/test_forecast_snapshot_routes.py` |
| FC-034 | 스냅숏 요약에 vendor_id·잘못된 쿼리는 422이고 쿼리 오류가 404보다 먼저다 | FC-R17, FC-UC3 | backend | `web/test_forecast_snapshot_routes.py` |
| FC-035 | 모든 역할이 스냅숏 목록·요약을 읽고 미인증은 401이다 | FC-R16, FC-R17, FC-UC3 | backend | `web/test_forecast_snapshot_routes.py` |
| FC-036 | openapi에 스냅숏 두 경로는 GET뿐이다 | FC-R17 | backend | `web/test_forecast_snapshot_routes.py` |
| FC-037 | 전월 스냅숏이 없으면 확인이 만들고 taken이다 | FC-R19, FC-UC4 | backend | `application/test_forecast_snapshot_schedule.py` |
| FC-038 | 전월 스냅숏이 있으면 확인은 아무것도 바꾸지 않고 already-exists다 | FC-R19, FC-UC4 | backend | `application/test_forecast_snapshot_schedule.py` |
| FC-039 | 그달 중순 첫 확인이 전월분을 만들고 전전월 이전은 만들지 않는다 | FC-R19, FC-UC4 | backend | `application/test_forecast_snapshot_schedule.py` |
| FC-040 | 다른 곳이 잠금을 쥐면 확인은 읽지도 쓰지도 않고 locked-elsewhere다 | FC-R19, FC-R20, FC-UC4 | backend | `application/test_ensure_monthly_forecast_snapshot.py` |
| FC-041 | 확인이 실패해도 정상이어도 잠금은 풀리고 실패는 전파된다 | FC-R19, FC-R20, FC-UC4 | backend | `application/test_ensure_monthly_forecast_snapshot.py` |
| FC-042 | 두 달의 확인이 쌓이면 목록은 최근 기준 월부터다 | FC-R19, FC-R16, FC-UC4 | backend | `application/test_forecast_snapshot_schedule.py` |
| FC-043 | 작업 잠금은 기다리지 않고 한 보유자만 허용하며 블록이 끝나면 풀린다 | FC-R20, FC-UC4 | backend | `repositories/test_advisory_job_lock.py` |
| FC-044 | 주기 실행기는 즉시 한 번, 이후 간격마다 실행하고 오류에도 계속한다 | FC-R21, FC-UC4 | backend | `infra/test_periodic_task.py` |
| FC-045 | 스케줄러는 켜져 있고 실제 Container일 때만 기동되고 종료 때 취소된다 | FC-R22, FC-UC4 | backend | `web/test_app_factory.py` |
| FC-046 | 스케줄러 설정은 프로파일 기본값과 간격 범위를 지킨다 | FC-R23 | backend | `test_settings_scheduler.py` |
| FC-047 | 모든 역할이 Forecast 화면을 보고 쓰기 동작은 없다 | FC-R24, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx`, `gateway/contract/forecast.contract.ts` |
| FC-048 | 연도 없이 열면 앱 시계의 올해로 조회하고 URL 연도는 그대로 쓴다 | FC-R25, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx`, `features/forecast/ForecastPage.today.test.tsx` |
| FC-049 | 요약 표 머리글은 Open 역순·Total(Open)·Won이고 담당자 버튼과 합계 행이 있다 | FC-R30, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-050 | 표의 모든 셀이 Deal 목록 원장 합과 같고 Total은 Open 합이며 Lost 열이 없다 | FC-R30, FC-R9, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx`, `gateway/contract/forecast.contract.ts` |
| FC-051 | Expected Close 12/31은 그 해 Q4, 1/1은 다음 해 Q1로 들어간다 | FC-R30, FC-R3, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-052 | 연도·Quarter·Vendor를 걸어도 합계가 원장 합과 같다 | FC-R30, FC-R9, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-053 | 요약 카드는 기간의 Open 합계와 Won(별도)을 건수와 함께 보인다 | FC-R29, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-054 | 퇴사 담당자는 "(퇴사)" 이름으로 행에 나온다 | FC-R30, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-055 | 조건에 Deal이 없으면 빈 문구, 읽는 동안 로딩 문구를 보인다 | FC-R24, FC-R27, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-056 | 요약 조회가 실패하면(501 포함) 오류 배너를 보이고 필터는 남는다 | FC-R27, FC-UC1 | frontend | `features/forecast/ForecastPage.notReady.test.tsx`, `features/forecast/ForecastPage.test.tsx` |
| FC-057 | 조건을 바꿔 다시 읽는 동안 이전 요약을 그대로 보인다 | FC-R27, FC-UC1 | frontend | `features/forecast/ForecastPage.keepPrevious.test.tsx` |
| FC-058 | 실시간 기준 문구는 서버 시각을 그 오프셋 그대로 보이고 빈 기간에도 보인다 | FC-R28, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-059 | 요약 표는 이름 있는 가로 스크롤 영역 안에 있다 | FC-R30, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-060 | URL 조건이 필터 칸에 복원되고 필터를 바꾸면 URL과 표가 바뀐다 | FC-R25, FC-R26, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-061 | Quarter와 월은 서로를 지우고 월을 고르면 그 달만 집계한다 | FC-R25, FC-R26, FC-R29, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx` |
| FC-062 | URL의 id·월·snap 값은 형식이 맞을 때만 쓰고 다시 URL로 쓸 수 있다 | FC-R25 | frontend | `features/forecast/forecastParams.test.ts` |
| FC-063 | 연도 선택지는 가장 이른 연도~내년이고 "전체"가 없으며 URL 연도를 더한다 | FC-R26, FC-UC1 | frontend | `features/forecast/ForecastPage.years.test.tsx` |
| FC-064 | 연도 기준을 읽는 동안·실패하면 올해·내년만 보이고 실패는 필터 배너다 | FC-R26, FC-UC1 | frontend | `features/forecast/ForecastPage.years.test.tsx` |
| FC-065 | Vendor 선택지는 등록 Vendor id이고 목록에 없는 URL id는 전체로 보이며 조회에서 빠진다 | FC-R26, FC-UC1 | frontend | `features/forecast/ForecastPage.test.tsx`, `features/forecast/ForecastPage.vendorMismatch.test.tsx` |
| FC-066 | Vendor 목록을 읽지 못하면 배너와 "선택한 Vendor"를 보이고 URL id로 조회한다 | FC-R26, FC-UC1 | frontend | `features/forecast/ForecastPage.vendorLoadError.test.tsx` |
| FC-067 | 담당자를 누르면 아래에 그 담당자 Deal 목록이 열리고 다시 누르거나 선택 해제로 닫힌다 | FC-R31, FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx`, `features/forecast/ForecastPage.test.tsx` |
| FC-068 | 담당자 목록 위 Open 요약은 요약 행 값이고 Lost Deal·안내는 없다 | FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx`, `features/forecast/ForecastPage.test.tsx` |
| FC-069 | 담당자 목록은 같은 기간·Vendor·Lost 아닌 코드로 200건까지 Expected Close 순으로 요청한다 | FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx`, `features/forecast/ForecastPage.test.tsx` |
| FC-070 | 200건을 넘으면 안내와 같은 조건의 Deals 목록 링크를 보이고 넘지 않으면 없다 | FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx` |
| FC-071 | 링크로 연 Deals 목록에는 Lost Deal이 없다 | FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx` |
| FC-072 | Lost 아닌 열이 없으면 담당자 목록을 요청하지 않고 링크도 없다 | FC-R32, FC-UC2 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx` |
| FC-073 | 기준 시점 선택지는 "지금"과 저장된 스냅숏이고 기본은 "지금"이다 | FC-R26, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx`, `gateway/contract/forecast.contract.ts` |
| FC-074 | 스냅숏을 고르면 URL snap이 생기고 "지금"이면 지워지며 URL snap으로 바로 열린다 | FC-R25, FC-R26, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-075 | 스냅숏 표의 열은 저장된 코드 목록과 저장 당시 이름이다 | FC-R33, FC-R18, FC-R36, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-076 | 스냅숏 표는 저장값(Lost 제외)이고 Deal을 추가해도 그대로이며 실시간은 바뀐다 | FC-R33, FC-R18, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-077 | 스냅숏에서도 기간·담당자 조건이 저장값을 거른다 | FC-R33, FC-R18, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-078 | 스냅숏 기준 문구는 기준 월과 생성 시각을 보인다 | FC-R28, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-079 | 스냅숏에서는 Vendor 칸이 비활성·안내이고 Vendor를 보내지 않는다 | FC-R33, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-080 | 스냅숏에서는 담당자를 고를 수 없고 담당자 Deal 목록이 없다 | FC-R33, FC-R31, FC-UC3 | frontend | `features/forecast/ForecastPage.ownerDeals.test.tsx`, `features/forecast/ForecastPage.snapshot.test.tsx` |
| FC-081 | 스냅숏 목록 실패·없는 기준 월·잘못된 snap을 처리한다 | FC-R27, FC-R26, FC-R36, FC-UC3 | frontend | `features/forecast/ForecastPage.snapshot.test.tsx`, `gateway/contract/forecast.contract.ts` |
| FC-082 | 게이트웨이는 실시간 요약 조건을 쿼리로 보내고 응답을 화면 모양으로 바꾼다 | FC-R34 | frontend | `gateway/http/forecast.snapshot.test.ts`, `gateway/http/forecast.test.ts` |
| FC-083 | 게이트웨이는 스냅숏 목록·요약을 읽고 Vendor를 보내지 않는다 | FC-R34 | frontend | `gateway/http/forecast.snapshot.test.ts` |
| FC-084 | Deal Forecast를 바꾸면 열려 있는 Forecast 요약이 다시 읽힌다 | FC-R35 | frontend | `data/hooks.test.tsx` |

### FC-001 모든 역할이 실시간 요약을 읽고 미인증은 401이다
- Given KIM의 Pipeline Deal 1건(금액 7, Expected Close 2026-11-15)
- When ROOT·KIM·VIEWER가 각각, 그리고 로그인하지 않은 채 `GET /forecast/summary?year=2026`을 부른다
- Then 세 역할은 200이고 합계 `open_total`이 `{count: 1, amount: 7}`로 같으며, 미인증은 401 `unauthenticated`다

### FC-002 실시간 요약은 담당자·Forecast 코드별 건수·금액이고 Lost와 기간 밖 Deal은 빠진다
- Given KIM: pipeline 100(2026-11-15)·pipeline 40(2026-10-01)·commit 7(2026-12-31)·won 500(2026-11-20)·lost 999(2026-11-01)·pipeline 5000(2026-09-30), LEE: most_likely 30(2026-11-02), PARK: lost 77(2026-11-03)
- When `year=2026&quarter=4`로 요약을 읽는다
- Then KIM 행 셀은 pipeline (2, 140)·commit (1, 7)·won (1, 500)·나머지 0, LEE 행은 most_likely (1, 30)이고, 5000원 Deal과 Lost 금액은 어떤 셀에도 없다

### FC-003 Total(Open)은 Open 열 합이고 Won·Lost를 빼며 합계 행은 담당자 행의 합이다
- Given FC-002와 같은 Deal
- When 같은 조건으로 요약을 읽는다
- Then KIM `open_total`은 (3, 147), LEE는 (1, 30), 합계 행 셀은 pipeline (2, 140)·commit (1, 7)·most_likely (1, 30)·won (1, 500)이고 `open_total`은 (4, 177), 합계 행 `owner`는 null이다

### FC-004 Lost만 있는 담당자는 행이 없다
- Given FC-002와 같은 Deal(PARK은 Lost 1건뿐)
- When 같은 조건으로 요약을 읽는다
- Then 행의 담당자는 KIM·LEE 둘뿐이고 PARK 행이 없다

### FC-005 퇴사한 담당자도 행에 남고 재직자 다음에 이름 순으로 온다
- Given 이름 "aaa-gone"인 sales의 Deal 1건과 KIM의 Deal 1건(둘 다 2026년), 그 뒤 "aaa-gone"이 퇴사 처리됨
- When `year=2026`으로 요약을 읽는다
- Then 행 순서는 KIM, aaa-gone이고 두 번째 행 `owner`는 `resigned: true`, `label` "aaa-gone(퇴사)", 첫 행은 `resigned: false`다

### FC-006 열은 Lost를 뺀 코드 order 순이고 바꾼 이름·추가한 Open 코드를 따르며 셀은 열 순서의 목록이다
- Given admin이 Forecast 코드 "Verbal"을 추가하고 `commit` 이름을 "확정"으로 바꿈, KIM의 commit 7·Verbal 3 Deal(2026 Q4)
- When `year=2026&quarter=4`로 요약을 읽는다
- Then 열은 코드 order 순이고 Lost가 없으며 `commit` 열 이름은 "확정", Verbal 열의 outcome은 `open`이고, KIM 행은 commit (1, 7)·Verbal (1, 3)·`open_total` (2, 10)이며 모든 행의 `cells` key 순서는 `columns` 순서와 같다

### FC-007 기간은 Expected Close의 연·분기·월 양끝을 포함하고 이웃 기간은 뺀다
- Given KIM의 Pipeline Deal 금액 1(2026-09-30)·2(2026-12-31)·4(2027-01-01)·8(2027-03-31)·16(2027-04-01), 별도로 2028-02-29 Deal
- When 2026 Q3, 2026 Q4, 2026년 12월, 2026년 9월, 2027 Q1, 2027년 1월, 2027 Q2, 2026년 전체, 2028년 2월로 각각 읽는다
- Then 합계 `open_total` 금액은 차례로 1, 2, 2, 1, 12, 4, 16, 3이고 2028년 2월에는 2-29 Deal이 들어간다

### FC-008 owner_user_id·vendor_id는 그 담당자·Vendor의 Deal만 센다
- Given Vendor SAP, KIM: SAP Deal 1원·Vendor 없는 Deal 2원, LEE: SAP Deal 4원(모두 2026년)
- When `year=2026&owner_user_id=<KIM>&vendor_id=<SAP>`, `year=2026&vendor_id=<없는 id>`, `year=2026`으로 읽는다
- Then 첫 요청은 행이 KIM 하나이고 합계 pipeline (1, 1), 둘째는 행 없음·합계 0, 셋째(Vendor 조건 없음)는 Vendor 없는 Deal도 세어 합계 금액 7이다

### FC-009 Deal이 없는 기간도 모든 열과 0인 합계를 돌려준다
- Given 2031년 Expected Close인 Deal이 없다
- When `year=2031`로 읽는다
- Then 200이고 `columns` key는 pipeline·best·most_likely·commit·won, `rows`는 `[]`, 합계 행 셀은 모두 `{count: 0, amount: 0}`이고 `open_total`도 0이다

### FC-010 응답은 basis live·서버 현재 시각·기간 양끝 날짜를 담는다
- Given 서버 시각 2026-10-15T09:00+09:00
- When `year=2026&quarter=4`, `year=2028&month=2`로 읽는다
- Then 키는 정확히 `basis, as_of, snapshot_period, period, columns, rows, total`이고 `basis` "live", `snapshot_period` null, `as_of`는 오프셋이 있는 서버 시각과 같으며, `period`는 각각 `{2026, 4, null, 2026-10-01, 2026-12-31}`, `{2028, null, 2, 2028-02-01, 2028-02-29}`다

### FC-011 요약 합계는 같은 조건의 Deal 목록(Lost 제외) 건수·금액과 같다
- Given Vendor SAP, KIM·LEE의 Deal 7건(pipeline·commit·lost·best·won·most_likely, 2026-03-15~2027-01-01, 일부 SAP)
- When 연, 연+분기, 연+월, 다음 해 1월, Vendor, 담당자, 월+담당자+Vendor 조건으로 각각 요약과 Deal 목록을 읽는다
- Then 모든 조건에서 요약 `total.open_total` + Won 셀의 건수·금액 = 같은 조건 Deal 목록 중 Lost가 아닌 Deal의 건수·금액 합이다

### FC-012 경고 상태는 Forecast 집계를 바꾸지 않는다
- Given 같은 기간에 기한초과·미업데이트 Deal과 정상 Deal이 섞여 있다
- When 요약을 읽는다
- Then 셀 값은 경고 상태와 무관하게 Deal 건수·금액 그대로다

### FC-013 2^31을 넘는 금액도 정확히 더한다
- Given 같은 담당자·같은 코드의 Deal 두 건, 각 3,000,000,000원
- When 요약(또는 월별 묶음)을 읽는다
- Then 그 셀 금액은 6,000,000,000이다

### FC-014 연도 누락·범위 밖·형식 오류·모르는 키는 422 request-validation이다
- Given 로그인한 KIM
- When 쿼리 없음, `year=abc`, `year=1899`, `year=10000`, `quarter=0`·`5`, `month=0`·`13`, `vendor=SAP`, `owner_user_id=abc`(나머지는 `year=2026`)로 각각 읽는다
- Then 모두 422 `request-validation`이다

### FC-015 Quarter와 월을 함께 주면 422 invalid-value와 안내 문구다
- Given 로그인한 KIM
- When `year=2026&quarter=1&month=1`로 읽는다
- Then 422 `invalid-value`, `detail` "Quarter와 월은 함께 선택할 수 없습니다."다

### FC-016 openapi에 요약 경로는 GET뿐이고 파라미터는 다섯 개다
- When openapi 문서를 만든다
- Then `/api/v1/forecast/summary`의 메서드는 GET뿐이고 파라미터 이름은 `year`·`quarter`·`month`·`owner_user_id`·`vendor_id`다

### FC-017 스냅숏 셀은 모든 Deal을 연·월·담당자·Forecast key로 묶고 Lost도 담는다
- Given KIM: pipeline 100(2026-08-15)·pipeline 40(2026-08-31)·commit 7(2026-09-30)·won 500(2026-08-20)·lost 999(2026-08-01)·pipeline 5000(2026-11-01), LEE: best 30(2026-09-02), 그리고 2025-08 Deal 1건
- When RUN 시각에 기준 월을 정하지 않고 스냅숏을 저장한다
- Then 셀은 (2026, 8, KIM, pipeline, 2건 140)·(2026, 8, KIM, won)·(2026, 8, KIM, lost, 999)·(2026, 9, KIM, commit)·(2026, 11, KIM, pipeline, 5000)·(2026, 9, LEE, best)와 2025년 8월 셀이 따로 있고, 셀에는 코드 이름이 없다

### FC-018 스냅숏 열은 실행 시점의 Forecast 코드 전부(Lost·Deal 없는 코드 포함)다
- Given 실행 전에 admin이 코드 "Verbal"을 추가하고 `commit` 이름·순서를 바꿈, Deal은 pipeline 1건뿐(별도로 Deal이 하나도 없는 상태)
- When 스냅숏을 저장한다
- Then 열은 lost·Verbal을 포함한 모든 Forecast 코드의 key·실행 시점 이름·outcome·order이고 Deal 없는 코드도 있으며, Deal이 없는 상태에서는 열만 있고 셀은 없다

### FC-019 대상 기준 월을 정하지 않으면 업무 날짜의 전월이다
- Given 실행 시각 2026-10-01 00:05, 2026-10-31 23:30, 2027-01-01 00:05(모두 +09:00)
- When 기준 월 없이 각각 저장한다
- Then 기준 월은 2026-09, 2026-09, 2026-12다

### FC-020 같은 기준 월을 다시 저장하면 통째로 바꾸고 다른 기준 월은 그대로다
- Given RUN 시각의 2026-09 스냅숏과 2026-08 스냅숏, 그 뒤 Deal 1건 삭제·1건 추가·코드 이름 변경
- When LATER 시각에 기준 월 2026-09를 다시 저장한다
- Then 첫 저장 결과는 `replaced: false`·`taken_at` = RUN이었고, 이번 결과는 `replaced: true`, 2026-09는 한 개만 있으며 생성 시각·셀(지운 Deal 셀 없음)·열(새 이름)이 새 값이고 2026-08 스냅숏은 그대로다

### FC-021 지정 기준 월은 전월·당월만 되고 그 밖은 거절하며 아무것도 쓰지 않는다
- Given 실행 업무 날짜 2026-10-15, 2026-08 스냅숏이 이미 있음
- When 기준 월 2026-09, 2026-10, 2026-08, 2026-11로 각각 저장한다
- Then 2026-09·2026-10은 저장되고, 2026-08은 "2026-08 기준 월은 다시 계산할 수 없습니다. 전월과 당월만 가능합니다." 오류이며 기존 2026-08 스냅숏이 그대로, 2026-11도 같은 오류이며 저장된 것이 없다

### FC-022 저장이 실패하면 이전 스냅숏이 남고 코드가 바뀐 충돌은 다시 실행 안내다
- Given 2026-09 스냅숏(생성 RUN)이 있고, 다시 저장하는 중 오류가 나거나 열에 없는 key의 셀이 들어가게 됨
- When 2026-09를 다시 저장한다
- Then 오류가 전파되고(코드 충돌이면 "스냅숏을 만드는 사이 Forecast 코드가 바뀌어 저장하지 못했습니다. 다시 실행하세요."), 롤백 뒤 2026-09 스냅숏은 생성 시각·열·셀이 이전 값 그대로다

### FC-023 스냅숏 테이블 3개의 컬럼·제약이 명세와 같다
- Given head까지 올린 빈 스키마
- When 세 테이블의 컬럼·제약·인덱스를 읽는다
- Then 2.2 표의 컬럼 형식·NOT NULL·UNIQUE·CHECK·FK(ON DELETE 포함)·인덱스와 같고 `codes`로 가는 FK는 없다

### FC-024 스냅숏에만 남은 담당자를 삭제하면 퇴사 처리되고 셀이 없으면 물리 삭제된다
- Given KIM의 Deal 1건으로 2026-09 스냅숏을 만든 뒤 그 Deal을 삭제함(KIM을 가리키는 것은 스냅숏 셀뿐), LEE는 어떤 데이터에도 연결되지 않음
- When ROOT가 KIM과 LEE를 각각 삭제한다
- Then KIM은 `{"outcome": "resigned"}`이고 2026-09 스냅숏 요약에서 KIM 행 `owner`가 `resigned: true`·`label` "<이름>(퇴사)"이며, LEE는 `{"outcome": "deleted"}`다

### FC-025 스냅숏 목록은 기준 월 최근 순의 period·taken_at이고 없으면 빈 목록이다
- Given 2025-12·2026-08·2026-09 스냅숏(그리고 별도로 스냅숏이 하나도 없는 상태)
- When `GET /forecast/snapshots`를 부른다
- Then 항목 순서는 2026-09·2026-08·2025-12이고 각 항목 키는 정확히 `period`·`taken_at`(오프셋 포함)이며, 빈 상태는 `items` `[]`다

### FC-026 스냅숏 요약은 실시간과 같은 모양이고 basis snapshot·생성 시각·기준 월을 담는다
- Given KIM: pipeline 100(2026-08-15)·commit 7(2026-09-30), LEE: best 30(2026-09-02)로 RUN 시각에 만든 2026-09 스냅숏
- When `GET /forecast/snapshots/2026-09/summary?year=2026&quarter=3`
- Then 200, `basis` "snapshot", `snapshot_period` "2026-09", `as_of` = RUN, 열 key는 기본 5개, 행은 KIM·LEE, KIM 셀 pipeline (1, 100)·commit (1, 7)·`open_total` (2, 107), 합계 `owner` null이다

### FC-027 스냅숏 값은 저장 뒤 Deal을 추가·삭제해도 바뀌지 않는다
- Given FC-026의 스냅숏, 그 뒤 KIM pipeline 900(2026-08-20) 추가와 기존 Deal 1건 삭제
- When 스냅숏 요약과 실시간 요약을 `year=2026&quarter=3`으로 읽는다
- Then 스냅숏 KIM 행은 여전히 pipeline (1, 100)·commit (1, 7)이고, 실시간 KIM 행은 추가·삭제가 반영된 값이다

### FC-028 스냅숏 열은 저장된 코드 목록이다(옛 이름, 뒤에 추가한 코드 없음, 0건 열 포함)
- Given KIM pipeline 5(2026-08-15)만 있는 상태로 2026-09 스냅숏 저장, 그 뒤 `commit` 이름을 "확정"으로 바꾸고 코드 "Verbal"을 추가
- When 스냅숏 요약과 실시간 요약을 읽는다
- Then 스냅숏 열은 저장 순서의 pipeline·best·most_likely·commit·won이고 commit 이름은 옛 이름 "Commit", Verbal 열은 없으며 Deal 없던 best·most_likely·commit도 0건 열이다. 실시간 commit 이름은 "확정"이다

### FC-029 스냅숏 요약은 저장된 월별 셀을 기간으로 모은다
- Given FC-026의 스냅숏
- When `year=2026&quarter=3`, `month=8`, `month=9`, `quarter=4`, `year=2025`, `quarter=1`로 각각 읽는다
- Then 합계 `open_total`은 (3, 137), (1, 100), (2, 37), (0, 0), (0, 0), (0, 0)이고 0인 경우에도 열은 모두 나오며 `rows`는 `[]`다

### FC-030 스냅숏 요약의 owner_user_id는 그 담당자 행만 남긴다
- Given FC-026의 스냅숏
- When `year=2026&owner_user_id=<LEE>`로 읽는다
- Then 행은 LEE 하나이고 합계 `open_total`은 (1, 30)이다

### FC-031 스냅숏의 Lost 셀은 열·합계·행에 나오지 않는다
- Given KIM pipeline 5·lost 999, PARK lost 77(모두 2026-08)로 만든 2026-09 스냅숏
- When `year=2026`으로 스냅숏 요약을 읽는다
- Then 행은 KIM 하나, 열에 `lost`가 없고 합계 `open_total`은 (1, 5)다

### FC-032 스냅숏 행의 담당자는 지금 사용자 정보이고 재직자 먼저 이름 순이다
- Given KIM·LEE 셀이 있는 스냅숏, 그 뒤 LEE가 퇴사 처리됨
- When 스냅숏 요약을 읽는다
- Then 행 순서는 KIM, LEE이고 LEE `owner`는 `resigned: true`·`label` "<이름>(퇴사)"다

### FC-033 없거나 형식이 틀린 기준 월은 404 not-found다
- Given 2026-09 스냅숏만 있다
- When 기준 월 `2026-08`, `2027-01`, `2026-9`, `abc`, `2026-13`으로 `?year=2026` 요약을 읽는다
- Then 모두 404 `not-found`이고 `detail`은 "해당 기준 월의 스냅숏이 없습니다: <보낸 기준 월>"이다

### FC-034 스냅숏 요약에 vendor_id·잘못된 쿼리는 422이고 쿼리 오류가 404보다 먼저다
- Given 2026-09 스냅숏
- When 2026-09에 `vendor_id=1`, 쿼리 없음, `year=1899`, `quarter=5`, `month=13`을, 그리고 없는 기준 월 `1999-01`에 `quarter=1&month=1`을 보낸다
- Then 앞의 다섯은 422 `request-validation`, 마지막은 404가 아니라 422 `invalid-value` "Quarter와 월은 함께 선택할 수 없습니다."다

### FC-035 모든 역할이 스냅숏 목록·요약을 읽고 미인증은 401이다
- Given 2026-09 스냅숏
- When ROOT·KIM·VIEWER가, 그리고 미인증으로 목록과 `2026-09` 요약을 읽는다
- Then 세 역할은 둘 다 200(목록 ["2026-09"])이고 미인증은 둘 다 401 `unauthenticated`다

### FC-036 openapi에 스냅숏 두 경로는 GET뿐이다
- When openapi 문서를 만든다
- Then `/api/v1/forecast/snapshots`와 `/api/v1/forecast/snapshots/{period}/summary`의 메서드는 GET뿐이다

### FC-037 전월 스냅숏이 없으면 확인이 만들고 taken이다
- Given FC-017의 Deal, 스냅숏 없음
- When RUN 시각에 확인을 한 번 한다
- Then 결과 `taken`, 목록은 ["2026-09"]·생성 시각 RUN이고, 2026-09 요약 Q3의 KIM 행은 pipeline (2, 140)·commit (1, 7)·won (1, 500)·`open_total` (3, 147), LEE 행은 best (1, 30), Q4의 KIM 행은 pipeline (1, 5000)이다

### FC-038 전월 스냅숏이 있으면 확인은 아무것도 바꾸지 않고 already-exists다
- Given RUN 시각에 만든 2026-09 스냅숏, 그 뒤 KIM pipeline 1000(2026-08-10) 추가
- When LATER 시각에 확인한다
- Then 결과 `already-exists`, 목록은 ["2026-09"]이고 생성 시각은 RUN 그대로, 요약 KIM 행은 FC-037의 값 그대로다

### FC-039 그달 중순 첫 확인이 전월분을 만들고 전전월 이전은 만들지 않는다
- Given FC-017의 Deal, 스냅숏 없음(10월 초에 앱이 꺼져 있었음)
- When MID 시각에 확인한다
- Then 결과 `taken`, 목록은 ["2026-09"]뿐이고 생성 시각은 MID다(2026-08 이전은 없다)

### FC-040 다른 곳이 잠금을 쥐면 확인은 읽지도 쓰지도 않고 locked-elsewhere다
- Given 작업 잠금 `forecast-snapshot`을 다른 프로세스가 쥐고 있음, 스냅숏 없음
- When 확인한다
- Then 결과 `locked-elsewhere`(기준 월 2026-09), 스냅숏 존재 확인과 저장이 일어나지 않아 목록은 비어 있다

### FC-041 확인이 실패해도 정상이어도 잠금은 풀리고 실패는 전파된다
- Given 저장이 오류를 내도록 만든 상태(그리고 정상 상태)
- When 확인한다
- Then 오류 상태에서는 오류가 호출자에게 전파되고 잠금은 풀려 있으며, 정상 실행 뒤에도 잠금이 풀려 있고, 기준 월은 잠금을 잡기 전에 한 번만 계산된다

### FC-042 두 달의 확인이 쌓이면 목록은 최근 기준 월부터다
- Given AUG 시각에 만든 2026-08 스냅숏
- When RUN 시각에 확인한다
- Then 결과 `taken`, 목록 순서는 2026-09, 2026-08이고 생성 시각은 차례로 RUN, AUG다

### FC-043 작업 잠금은 기다리지 않고 한 보유자만 허용하며 블록이 끝나면 풀린다
- Given PostgreSQL 연결 두 개
- When 한 곳이 `forecast-snapshot`을 쥔 동안 다른 곳이 시도하고, 블록이 정상·오류로 끝난 뒤 다시 시도하고, 다른 작업 이름을 시도한다
- Then 쥔 동안의 시도는 기다리지 않고 False이며 보유자의 잠금을 풀지 않고, 블록이 끝나면(오류 포함) 다시 True이며, 다른 작업 이름은 막히지 않는다. 키는 실행마다 같고 signed bigint 범위다

### FC-044 주기 실행기는 즉시 한 번, 이후 간격마다 실행하고 오류에도 계속한다
- Given 간격 600초, 기록용 작업(한 번은 예외를 던짐)
- When 실행기를 돌리고 몇 주기 뒤 취소한다
- Then 첫 실행은 기다리기 전에 일어나고 이후 600초 대기마다 실행되며, 예외는 "주기 작업 실패(다음 주기에 다시 시도)" 로그를 남기고 다음 주기로 이어지고, 취소하면 루프가 끝난다. 간격 0·음수로 만들면 `ValueError`다

### FC-045 스케줄러는 켜져 있고 실제 Container일 때만 기동되고 종료 때 취소된다
- Given `scheduler_enabled` true·false, 유스케이스 주입 여부, local 기본 설정
- When 앱을 기동했다가 종료한다
- Then true이고 실제 Container면 기동 때 주기 작업이 시작되고 종료 때 취소된 뒤 Container가 정리되며, false·주입 앱·local 기본은 시작하지 않는다

### FC-046 스케줄러 설정은 프로파일 기본값과 간격 범위를 지킨다
- Given 프로파일 local·dev·product와 env `APP_SCHEDULER_ENABLED`·`APP_FORECAST_SNAPSHOT_CHECK_INTERVAL_SECONDS`
- When 설정을 읽는다
- Then 기본값은 local false, dev·product true, 간격 600이고, env로 dev를 끌 수 있으며, 간격 30·3600은 되고 29·3601은 설정 오류다

### FC-047 모든 역할이 Forecast 화면을 보고 쓰기 동작은 없다
- Given admin·sales·user 각각 로그인
- When `/forecast?year=2026`을 연다
- Then 제목 "Forecast"와 요약 표가 보이고 등록·수정·삭제 버튼이 없다

### FC-048 연도 없이 열면 앱 시계의 올해로 조회하고 URL 연도는 그대로 쓴다
- Given 앱 시계 2026-10-15
- When `/forecast`와 `/forecast?year=2025`를 연다
- Then 앞은 연도 칸이 2026이고 2026으로 조회하며 선택지가 올해 앞뒤를 포함하고, 뒤는 2025로 조회한다

### FC-049 요약 표 머리글은 Open 역순·Total(Open)·Won이고 담당자 버튼과 합계 행이 있다
- Given 기본 Fake 시드(2026년 Deal)
- When `/forecast?year=2026`을 연다
- Then 머리글은 담당자, Commit, Most Likely, Best, Pipeline, Total(Open), Won이고 김영업·박영업은 버튼, 맨 아래 "합계" 행이 있다

### FC-050 표의 모든 셀이 Deal 목록 원장 합과 같고 Total은 Open 합이며 Lost 열이 없다
- Given 기본 Fake 시드(Lost·Won Deal 포함)
- When `/forecast?year=2026`을 연다
- Then 합계 행과 각 담당자 행의 셀이 같은 조건 Deal 목록의 코드별 "N건 · 금액"과 같고, Total(Open)은 Open 코드 합, Won 칸은 Won 합이며 "Lost" 머리글이 없다

### FC-051 Expected Close 12/31은 그 해 Q4, 1/1은 다음 해 Q1로 들어간다
- Given 이영업 Pipeline Deal 두 건의 Expected Close를 2026-12-31(650,000,000)과 2027-01-01(180,000,000)로 바꿈
- When 2026 Q4를 본 뒤 연도 2027·Quarter Q1로 바꾼다
- Then 2026 Q4의 이영업 Pipeline 칸은 "1건 · 650,000,000", 2027 Q1은 "1건 · 180,000,000"이다

### FC-052 연도·Quarter·Vendor를 걸어도 합계가 원장 합과 같다
- Given 기본 Fake 시드, Vendor Silverfort
- When `/forecast?year=2026&quarter=4&vendor=<Silverfort>`를 연다
- Then 합계 행 셀이 같은 조건 Deal 목록의 코드별 합과 같다

### FC-053 요약 카드는 기간의 Open 합계와 Won(별도)을 건수와 함께 보인다
- Given 기본 Fake 시드
- When `/forecast?year=2026&quarter=4`를 연다
- Then "2026 Q4 요약" 영역에 "Open 합계(단위:원)" = Open 합 금액·"2026 Q4 · N건", "Won (별도, 단위:원)" = Won 합 금액·"2026 Q4 · M건"이 보이고, 표 캡션은 "셀 값: 건수 · 금액(단위:원)"이다

### FC-054 퇴사 담당자는 "(퇴사)" 이름으로 행에 나온다
- Given 퇴사한 담당자의 Deal이 있는 Fake 시드
- When `/forecast?year=2026`을 연다
- Then 그 담당자 행의 이름이 "<이름>(퇴사)"다

### FC-055 조건에 Deal이 없으면 빈 문구, 읽는 동안 로딩 문구를 보인다
- Given Deal이 없는 연도, 그리고 응답이 늦는 요약
- When 각각 화면을 연다
- Then 빈 연도는 "조건에 맞는 Deal이 없습니다."와 기준 문구를 보이고 표가 없으며, 늦는 동안에는 "불러오는 중…"(status)이 보인다

### FC-056 요약 조회가 실패하면(501 포함) 오류 배너를 보이고 필터는 남는다
- Given 요약 조회가 서버 오류(500)·501로 실패
- When 화면을 연다
- Then 서버 문구가 `role=alert` 배너로 보이고 "준비 중" 같은 별도 문구는 없으며 "Forecast 필터" 폼이 그대로 보인다. 기본 Fake로는 정상 표가 보인다

### FC-057 조건을 바꿔 다시 읽는 동안 이전 요약을 그대로 보인다
- Given 2026 요약이 보이고 다음 조회 응답이 늦음
- When Quarter를 바꾼다
- Then 새 응답이 올 때까지 이전 표가 그대로 보인다

### FC-058 실시간 기준 문구는 서버 시각을 그 오프셋 그대로 보이고 빈 기간에도 보인다
- Given 서버 `as_of` "2026-10-15T09:00:00+09:00"(또는 다른 오프셋)
- When 화면을 연다(Deal 없는 연도 포함)
- Then "기준: 지금(2026-10-15 09:00)"처럼 서버 문자열의 벽시계로 보이고 Deal이 없는 기간에도 보인다

### FC-059 요약 표는 이름 있는 가로 스크롤 영역 안에 있다
- When `/forecast?year=2026`을 연다
- Then 표 "담당자별 Forecast 요약"은 이름 "담당자별 Forecast 표 (가로 스크롤)"인 포커스 가능한 region 안에 있다

### FC-060 URL 조건이 필터 칸에 복원되고 필터를 바꾸면 URL과 표가 바뀐다
- Given `/forecast?year=2026&quarter=4&owner=<김영업>&vendor=<Silverfort>`
- When 화면을 열고 이어서 연도·Quarter·담당자를 바꾼다
- Then 처음에는 네 칸이 URL 값으로 보이고, 바꿀 때마다 URL 쿼리(`year`는 항상)가 바뀌고 새로 고침 없이 표가 바뀐다

### FC-061 Quarter와 월은 서로를 지우고 월을 고르면 그 달만 집계한다
- Given `/forecast?year=2026&quarter=4`
- When 월 11월을 고르고, 이어서 Quarter Q1을 고르고, 별도로 `?year=2026&quarter=4&month=11`을 연다
- Then 월 선택지는 "전체"+1월~12월이고, 11월을 고르면 URL에 `month=11`만 남아 그 달만 집계하며 카드 제목이 "2026 11월"이고, Q1을 고르면 `month`가 지워지며, 둘 다 있는 주소는 Quarter만 쓴다

### FC-062 URL의 id·월·snap 값은 형식이 맞을 때만 쓰고 다시 URL로 쓸 수 있다
- Given URL 값 `vendor`·`owner`·`sel` = `7`·`9007199254740991`·`0`·`-1`·`1.5`·`1e3`·`01`·`+3`·`9007199254740992`·UUID, `month` = `1`·`12`·`0`·`13`·`03`·`abc`, `snap` = `2026-09`·`2026-9`·`2026-13`·`2026-00`·`202609`·`2026/09`·` 2026-09`·`2026-09-01`
- When 필터로 읽고 다시 URL로 쓴다
- Then 정수 id(1~2^53−1)·월 1~12·`YYYY-MM`만 쓰고 나머지는 없는 값이며, 쓴 URL을 다시 읽으면 같은 필터이고 `sel`·`snap`은 요약 조회 조건에 들어가지 않는다

### FC-063 연도 선택지는 가장 이른 연도~내년이고 "전체"가 없으며 URL 연도를 더한다
- Given 가장 이른 Expected Close 2024, 앱 시계 2026(그리고 Deal 없음, URL `year=2019`)
- When 화면을 연다(실시간과 `snap` 모드 각각)
- Then 선택지는 2024~2027 연속이고 "전체"·2028이 없으며, Deal이 없으면 2026·2027, URL 2019는 선택지에 더해져 선택된다. 스냅숏 모드도 같다

### FC-064 연도 기준을 읽는 동안·실패하면 올해·내년만 보이고 실패는 필터 배너다
- Given 연도 기준 응답이 늦거나 실패
- When 화면을 연다
- Then 읽는 동안 2026·2027만 보이다가 응답 뒤 넓어지고, 실패하면 2026·2027과 필터 안 오류 배너를 보이며 요약은 조회된다

### FC-065 Vendor 선택지는 등록 Vendor id이고 목록에 없는 URL id는 전체로 보이며 조회에서 빠진다
- Given 등록 Vendor 목록, URL `vendor=<등록 id>`·`vendor=<없는 id>`·옛 이름 값
- When 화면을 열고 담당자를 고른다
- Then 선택지 값은 id·표시는 이름이고, 등록 id는 선택되어 요약·담당자 목록 조회에 쓰이며, 없는 id·옛 이름은 "전체"로 보이고 요약·담당자 목록 조회에 Vendor가 없다

### FC-066 Vendor 목록을 읽지 못하면 배너와 "선택한 Vendor"를 보이고 URL id로 조회한다
- Given Vendor 목록 조회 실패, URL `vendor=7`
- When 화면을 연다
- Then 필터 근처에 오류 배너가 보이고 Vendor 칸은 "선택한 Vendor"가 선택된 상태이며 요약 조회에 `vendorId` 7이 쓰인다

### FC-067 담당자를 누르면 아래에 그 담당자 Deal 목록이 열리고 다시 누르거나 선택 해제로 닫힌다
- Given `/forecast?year=2026`
- When 김영업 버튼을 누르고, 다시 누르고, 또 눌러 연 뒤 "선택 해제"를 누른다
- Then 처음에는 URL에 `sel=<김영업>`이 생기고 "선택한 담당자: 김영업" 영역에 Deal 이름 링크(`/deals/<code>`)가 보이며, 다시 누르면 `sel`이 지워지고, "선택 해제"도 `sel`을 지운다. 담당자 상세 링크는 없다

### FC-068 담당자 목록 위 Open 요약은 요약 행 값이고 Lost Deal·안내는 없다
- Given 김영업에게 Lost Deal이 있는 시드, 목록 응답이 Lost를 포함하지 않음
- When `sel=<김영업>`으로 연다
- Then 영역 위 "Open N건 · 금액(단위:원) X"는 요약 표 김영업 행의 Total(Open) 값과 같고, 목록에 Lost Deal이 없으며 Lost 관련 문구가 없다

### FC-069 담당자 목록은 같은 기간·Vendor·Lost 아닌 코드로 200건까지 Expected Close 순으로 요청한다
- Given `/forecast?year=2026&month=11&sel=<김영업>`, admin이 Open 코드 하나를 추가함
- When 화면을 연다
- Then Deal 목록 요청은 `ownerId` 김영업, `year` 2026, `month` 11, `forecastKeys` = 응답 열 중 Lost가 아닌 key 전부(추가한 코드 포함), `sort` revenueDate·`order` asc, `limit` 200이고 오류 배너 없이 Expected Close 오름차순으로 보인다

### FC-070 200건을 넘으면 안내와 같은 조건의 Deals 목록 링크를 보이고 넘지 않으면 없다
- Given 목록 응답이 `total` 250·`limit` 200(그리고 별도로 다 들어오는 응답)
- When `/forecast?year=2026&quarter=4&vendor=7&sel=<김영업>`과 `?year=2026&month=11&sel=<김영업>`을 연다
- Then "총 250건 중 200건만 표시합니다."와 링크 "Deals 목록에서 모두 보기"가 보이고 링크 쿼리는 각각 `{owner, year: 2026, quarter: 4, vendor: 7, forecast: <Lost 아닌 key 콤마>}`, `{owner, year: 2026, month: 11, forecast: …}`이며, 다 들어오면 안내·링크가 없다

### FC-071 링크로 연 Deals 목록에는 Lost Deal이 없다
- Given FC-070의 링크
- When 링크를 따라간다
- Then Deals 목록의 Forecast 필터가 Lost 제외 묶음이고 Lost Deal 행이 없다

### FC-072 Lost 아닌 열이 없으면 담당자 목록을 요청하지 않고 링크도 없다
- Given 요약 응답의 열이 하나도 없음(Lost 아닌 코드 없음), `sel` 있음
- When 화면을 연다
- Then Deal 목록 요청이 나가지 않고 영역에 "조건에 맞는 Deal이 없습니다."만 있으며 링크가 없다

### FC-073 기준 시점 선택지는 "지금"과 저장된 스냅숏이고 기본은 "지금"이다
- Given 2026-09 스냅숏 fixture(그리고 스냅숏이 없는 시드)
- When `/forecast?year=2026&quarter=3`을 연다
- Then 선택지는 "지금", "2026-09 월말"이고 값은 "지금"이며, 스냅숏이 없으면 "지금"만이다

### FC-074 스냅숏을 고르면 URL snap이 생기고 "지금"이면 지워지며 URL snap으로 바로 열린다
- Given `/forecast?year=2026&quarter=3&owner=<김영업>`
- When "2026-09 월말"을 고르고, 이어서 "지금"을 고르고, 별도로 `…&snap=2026-09`를 연다
- Then 고르면 URL에 `snap=2026-09`가 생기고 `year`·`quarter`·`owner`가 남으며, "지금"이면 `snap`이 지워지고 "기준: 지금(…)"이 보이고, 주소로 열면 처음부터 스냅숏 기준 문구와 선택 값 2026-09다

### FC-075 스냅숏 표의 열은 저장된 코드 목록과 저장 당시 이름이다
- Given 2026-09 스냅숏 fixture(commit 저장 이름 SNAPSHOT_COMMIT_NAME, 저장 열 목록에 저장 당시 Deal이 없던 Open 코드 포함)
- When `…&snap=2026-09`를 연다
- Then 머리글의 Open 열은 저장된 코드 목록(Lost 제외)을 역순으로 모두 보이고 Deal이 없던 저장 코드도 열이며 그 칸은 "—"이고, commit 열 이름은 저장 당시 이름이다(Fake를 서버 동작에 맞춤, 2026-11-11 결정)

### FC-076 스냅숏 표는 저장값(Lost 제외)이고 Deal을 추가해도 그대로이며 실시간은 바뀐다
- Given 2026-09 스냅숏 fixture, 저장된 Lost 셀 포함
- When 스냅숏 화면을 보고, Q3에 Deal을 추가한 뒤 다시 보고, "지금"으로 바꾼다
- Then 담당자 행·합계 행은 저장값이고 Lost가 빠지며, Deal 추가 뒤에도 스냅숏 값은 같고 실시간 값은 늘어난다

### FC-077 스냅숏에서도 기간·담당자 조건이 저장값을 거른다
- Given 2026-09 스냅숏 fixture
- When Quarter·월을 바꾸고, 담당자를 김영업으로 고른다
- Then 표 값이 그 기간의 저장 셀 합으로 바뀌고, 담당자를 고르면 김영업 행만 남는다

### FC-078 스냅숏 기준 문구는 기준 월과 생성 시각을 보인다
- Given 생성 시각 "2026-10-01T00:05:00+09:00"
- When `…&snap=2026-09`를 연다
- Then "기준: 2026-09 월말(생성 2026-10-01 00:05)"이 보이고 "기준: 지금"은 없다

### FC-079 스냅숏에서는 Vendor 칸이 비활성·안내이고 Vendor를 보내지 않는다
- Given `…&vendor=<Silverfort>&snap=2026-09`(그리고 snap 없는 주소)
- When 화면을 연다
- Then 스냅숏에서는 Vendor 칸이 비활성이고 "스냅숏에서는 Vendor 필터를 사용할 수 없습니다."가 보이며 스냅숏 요청에 Vendor가 없다. 실시간에서는 활성이고 안내가 없다

### FC-080 스냅숏에서는 담당자를 고를 수 없고 담당자 Deal 목록이 없다
- Given `…&snap=2026-09&sel=<김영업>`, 그리고 `sel`이 있는 실시간 주소
- When 스냅숏 화면에서 담당자 이름을 누르고, 실시간에서 스냅숏으로 바꾼 뒤 다시 "지금"으로 돌아온다
- Then 스냅숏 담당자 이름은 버튼이 아니고 눌러도 URL에 `sel`이 생기지 않으며 선택 표시·담당자 영역·링크가 없다. 실시간 → 스냅숏 전환은 `sel`을 지우고, "지금"으로 돌아와도 담당자 영역이 열리지 않는다. 실시간 주소에서는 담당자 영역이 보인다(대조)

### FC-081 스냅숏 목록 실패·없는 기준 월·잘못된 snap을 처리한다
- Given 스냅숏 목록 조회 실패, 저장되지 않은 `snap=2026-08`, 형식이 틀린 `snap=2026-9`
- When 각각 화면을 연다
- Then 목록 실패는 필터 오류 배너를 보이되 실시간 표가 보이고, 없는 기준 월은 서버 404 문구 "해당 기준 월의 스냅숏이 없습니다: 2026-08" 배너를 보이며 기준 시점에 "2026-08 월말"이 선택지로 더해지고, 잘못된 `snap`은 무시되어 실시간 화면이다(Fake를 서버 동작에 맞춤, 2026-11-11 결정)

### FC-082 게이트웨이는 실시간 요약 조건을 쿼리로 보내고 응답을 화면 모양으로 바꾼다
- Given `{year: 2026}`, `{year, quarter, ownerId, vendorId}`, `{year, month}` 조건과 서버 응답(행·합계·열)
- When `forecast.summary`를 부른다
- Then 쿼리는 `year`와 있는 값만 snake_case(`quarter`·`month`·`owner_user_id`·`vendor_id`)로 가고 빈 조건은 보내지 않으며, 응답은 열 `{key,name,outcome,order}`, 행 `cells` key 레코드(없는 key 0)·`ownerName` = label·`total` = `open_total`, 합계 행 `ownerId` null·"합계", `basis`·`asOf`·보낸 조건이다. 422·401은 `ApiError`로 전달된다

### FC-083 게이트웨이는 스냅숏 목록·요약을 읽고 Vendor를 보내지 않는다
- Given 스냅숏 목록 응답(최근 순)과 요약 응답
- When `forecast.snapshots()`와 `forecast.snapshotSummary('2026-09', {year, quarter, ownerId, vendorId})`를 부른다
- Then 목록은 쿼리 없이 `GET /forecast/snapshots`이고 `[{period, takenAt}]`를 서버 순서로 주며(빈 목록 포함), 요약은 경로에 기준 월·쿼리에 `year`·`quarter`(또는 `month`)·`owner_user_id`만 있고 `vendor_id`가 없으며, `basis` snapshot·`snapshotPeriod`·`asOf` = 생성 시각으로 바뀐다. 404·422·401은 `ApiError`다

### FC-084 Deal Forecast를 바꾸면 열려 있는 Forecast 요약이 다시 읽힌다
- Given 2026 Forecast 요약을 읽어 둔 화면 세션(commit 합계 N건)
- When 2026년 Deal 하나의 Forecast를 commit으로 바꾸는 변경을 적용한다
- Then 요약이 다시 읽혀 합계 commit 건수가 N+1이 된다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 최초 작성(구현된 동작을 정본으로 옮김, 초안). functional `tests/functional/forecast/` 6개 파일의 시나리오를 케이스로 흡수 | FC-001~FC-084 |
| 2026-11-11 | 사용자 결정 반영(추천대로): F1 Fake를 서버 동작에 맞춤(FC-R36 신설: 스냅숏 0건 열·행 정렬·404 문구·스냅숏 Vendor 422), F2 기준 월 직접 지정 현행 유지(FC-R12)·Forecast 연도에 '전체' 없음(FC-R26, DL-R24 문구 정리), F4 스냅숏 셀 사용자 삭제 결과 케이스는 FC 소유(FC-R15, US-R17)와 다른 문서 참조를 번호로(DSH-R1~R12·R6·R8·R19·R22·R23, DL-R1, DE-R4, CD-R1·R5, US-R12, RK-R3~R5) | 변경: FC-075(0건 열 포함 기대 결과), FC-081(404 문구) |
