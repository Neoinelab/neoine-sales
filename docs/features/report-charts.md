# Reports 차트   (feature 코드: RC, 상태: 확정(2026-11-11 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11 초안). 근거는 작업 트리의 코드(`backend/src/app/domain/report/{chart_kinds,chart,parse_chart,parse_chart_fields,parse_chart_options,stored_chart,raw}.py`, `app/application/report/{execution,copy_report}.py`의 차트 부분, `app/domain/saved_report/entities.py`의 `chart`·`chart_unreadable`·`chart_kind()`, `app/infra/db/report_repository.py`의 `_stored_chart`, `app/web/schemas/saved_report.py`의 차트 스키마·`CHART_PROBLEM`, `app/web/error_handlers.py`의 `_invalid_report`, `frontend/src/features/reports/chart/**`, `features/reports/result/ChartTile.tsx`, `features/reports/designer/{Designer.tsx,state/issues.ts,state/issueView.ts}`의 차트 부분, `gateway/http/mappers/reportChart.ts`, `test/fake/gateway/savedReports.ts`의 `normalizeChart`)이며 문구·코드·위치는 코드에서 그대로 옮겼습니다. 코드와 Fake·안내서가 어긋나던 점은 2026-11-11 사용자 결정으로 정리했습니다: Fake 게이트웨이의 차트 처리는 서버 동작에 맞추고(RC-R57), bool이 아닌 `swap` 문구(RC-R10)와 화면 안내 "범주 열을 고르세요"·part `category`(RC-R32)는 현행대로 두며, 저장·덮어쓰기·복제 때의 차트 값·`chart_kind`·`chart_problem`은 이 문서가 가집니다(RC-R18~RC-R22). 안내서(`docs/user-guide.html` 15.9) 문구는 코드에 맞춥니다. 결정 목록은 계획(`artifacts/10-analysis/rc-plan.md`)에 있습니다.

## 1. 개요

- 목적: 리포트 결과(그룹핑한 결과, 예외로 그룹핑 없는 히스토그램)를 Excel(Microsoft 365) "차트 삽입"과 같은 13분류 33종 차트로 그리고, 차트 설정을 리포트와 함께 저장해 다시 연다.
- 사용자(역할): 리포트를 만들거나 고칠 수 있는 사람(디자이너·편집 화면)과 리포트를 볼 수 있는 사람(보기 화면·목록). 역할별 허용은 RS 2.5가 정한다(RC는 권한을 따로 두지 않는다).
- 범위
  - 결과 탭의 차트 타일 본문: 빈 상태(차트 만들기), 미리보기, 설정 패널(종류 · 데이터 · 종류별 옵션 · 제목과 범례 · 축), 차트 삭제
  - 종류 33종·13분류와 종류별 규칙표(`KIND_RULES`, 화면 복제본 `chartKinds.ts`)
  - 요청 `chart`의 검증·정규화(`parse_chart`)와 422 `invalid-report`의 차트 위치·코드·문구
  - 저장 리포트 안의 차트 값: 저장·덮어쓰기·삭제·복제 때 차트가 어떻게 되는지(PUT에서 생략·null이면 삭제, 복제 승계), 목록·상세 `chart_kind`, 저장 차트 JSON 읽기(`chart_from_json`, 옛 13키·옛 콤보·구간 없는 히스토그램 변환, 깨진 JSON → `chart_problem`). 2026-11-11 결정으로 RC가 가지며 RS는 RC-R18~RC-R22를 가리킨다
  - 프런트 계산(`chart/compute/`)과 빌더(`chart/build/`, `buildChart`, `pivot`)가 만드는 Chart.js 설정 값(type·data·options·notes). 실제 픽셀 그리기는 대상이 아니다
  - 보기 화면의 읽기 전용 차트, 편집 화면의 저장 차트 열기·저장 안 됨·되돌리기 중 차트 부분, 목록 "차트" 열, 게이트웨이 차트 변환, 테스트 Fake 게이트웨이의 차트 처리
- 범위 밖(다른 feature)
  - 저장 리포트 API 자체(경로 RS-R26·권한 RS-R5~RS-R9·404/403/409 판정 순서 RS-R12~RS-R14·revision 잠금 RS-R11·이름 규칙 RS-R2·RS-R3·목록 RS-R10·삭제 RS-R18·실행 RS-R16·배치 `layout` RS-R19~RS-R23·결과 타일 배치와 보기 방식 RS-R37~RS-R39, 차트 없는 리포트 포함) → RS
  - 리포트 정의(컬럼·그룹핑·집계·조건·앞 N자 `prefix_length`·행 한도) 검증(RQ-R7~RQ-R19), 결과 표 서식(`formatCell`, RQ-R51)·금액 `unit`(RQ-R4, RQ-R36), 디자이너 작성/결과 탭과 조회(RQ-R39, RQ-R48, RQ-R49) → RQ. 저장 안 됨·떠날 때 확인의 일반 규칙은 새 리포트 화면 RQ-R54, 편집 화면 RS-R32·RS-R33(차트 부분만 RC-R38)
  - Problem 형식·`request-validation`(PL-R12), 화면 오류 문구(PL-R37), 게이트웨이 오류 변환(PL-R39)
  - Dashboard 차트(DSH-R20, DSH-R22, DSH-R24) — Reports 차트와 플러그인·코드를 공유하지 않는다(데이터 레이블 플러그인은 인스턴스에만 붙음)
- 관련 화면: `/reports/new`·`/reports/:id/edit`의 결과 탭 차트 타일, `/reports/:id` 보기 화면의 차트 타일, `/reports` 목록의 "차트" 열.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 종류(kind) | 차트 하나의 모양. 33개 키(RC-R1) |
| 분류(family) | 종류 묶음 13개(Excel 대화상자 왼쪽 목록) |
| 그룹 컬럼 | 정의에서 `group: true`인 컬럼(RQ-R14). 차트의 범주·계열 후보 |
| 값 컬럼 | 그룹이 아니고 집계(`aggregate`)가 있는 컬럼. 그룹핑 없는 히스토그램만 "집계 없는 숫자(정수·소수) 컬럼" |
| 범주(category) | 가로축(가로 막대는 세로축) 항목이 되는 그룹 컬럼의 index |
| 계열(series) | 그룹 컬럼이 2개일 때 색으로 나뉘는 나머지 그룹 컬럼의 index |
| 값(values) | 값 컬럼 index 목록(순서 유지, 최대 10) |
| 정의 index | 차트가 컬럼을 가리키는 방법: 정의 `columns`의 0부터 센 위치. 화면 초안은 컬럼 uid로 가리키고 요청 때 index로 바꾼다 |
| 정규화 | 서버가 검증을 통과한 차트를 16개 키를 모두 채운 값으로 바꾸는 것(RC-R17) |
| 깨진 저장 차트 | DB `reports.chart` JSON이 읽기 규칙(RC-R21)에 맞지 않는 것. 리포트는 차트 없이 열린다 |
| 점 수 | 범주 수 × 데이터셋 수(종류별 세는 법은 RC-R42) |

### 2.2 데이터 모델

- 저장: `reports.chart` JSONB NULL(테이블·열은 RS-R25, SC-R11). 마이그레이션 없음.
- 원시 차트(`RawChart`, 요청·저장 공통 16키): `kind`, `category`, `values`(필수 키) / `series`(기본 null), `swap`(false), `title`(""), `legend`("top"), `data_labels`(false), `category_axis_title`(""), `value_axis_title`(""), `value_min`(null), `value_max`(null), `secondary_axis`(false), `histogram`(null), `show_total`(false), `combo_series`(null).
- `histogram` = `{bin_mode: auto|count|width, bin_count: int|null, bin_width: number|null, overflow: number|null, underflow: number|null}`(정확히 5키).
- `combo_series` = 값 순서와 같은 `[{type: column|stacked_column|line|line_markers|area|stacked_area, secondary: bool}]`(항목은 정확히 2키).
- 한도: 값 최대 10(`CHART_VALUES_MAX`, 색 10개와 같음), 글자 100자, 구간 수 1~100, 숫자 절댓값 2^53−1, 화면 점 1,000개.
- 엔티티: `Report.chart`(정규화된 원시 차트 또는 None), `Report.chart_unreadable`(저장 차트를 읽지 못함, 이때 chart는 None), `Report.chart_kind()`(chart의 종류 또는 None).
- 화면 초안(`ChartDraft`): 종류, `categoryUid`·`seriesUid`·`valueUids`(컬럼 uid), 글자·켜기끄기 칸, 숫자 칸은 입력 문자열('' = 자동), `histogram`(입력 문자열 5칸), `showTotal`, `comboTypes`(값 컬럼 uid → 계열 설정).

### 2.3 비즈니스 규칙

종류와 규칙표
- **RC-R1** 종류는 33개다. 키와 화면 이름(분류 순):
  - 세로 막대형: `bar` 묶은 세로 막대, `stacked_bar` 누적 세로 막대, `stacked_100_bar` 100% 누적 세로 막대
  - 가로 막대형: `horizontal_bar` 묶은 가로 막대, `stacked_horizontal_bar` 누적 가로 막대, `stacked_100_horizontal_bar` 100% 누적 가로 막대
  - 꺾은선형: `line` 꺾은선, `line_markers` 표식이 있는 꺾은선, `stacked_line` 누적 꺾은선, `stacked_line_markers` 표식이 있는 누적 꺾은선, `stacked_100_line` 100% 누적 꺾은선, `stacked_100_line_markers` 표식이 있는 100% 누적 꺾은선
  - 원형: `pie` 원형, `doughnut` 도넛형
  - 영역형: `area` 영역, `stacked_area` 누적 영역, `stacked_100_area` 100% 누적 영역
  - 분산형(X, Y) 또는 거품형: `scatter` 분산형(표식만), `scatter_smooth_markers` 곡선 및 표식이 있는 분산형, `scatter_smooth` 곡선이 있는 분산형, `scatter_line_markers` 직선 및 표식이 있는 분산형, `scatter_line` 직선이 있는 분산형, `bubble` 거품형
  - 방사형: `radar` 방사형, `radar_markers` 표식이 있는 방사형, `radar_filled` 채워진 방사형
  - 트리맵: `treemap` / 선버스트: `sunburst` / 히스토그램: `histogram` 히스토그램, `pareto` 파레토 / 폭포: `waterfall` / 깔때기: `funnel` / 콤보: `combo`
  - 4단계 때의 10개 키(`bar`·`stacked_bar`·`stacked_100_bar`·`horizontal_bar`·`line`·`area`·`pie`·`doughnut`·`scatter`·`combo`)는 이름이 그대로다. 전용 옵션 키는 `histogram`·`show_total`·`combo_series` 셋이다.
- **RC-R2** 종류별 규칙표(서버 `KIND_RULES`가 정본, 화면 `chartKinds.ts`는 같은 값의 복제본):

  | 종류 | 그룹 수 | 계열 | 값 개수 | 행/열 전환 | 축 범위 | 보조 축 | 범주 열 | 옵션 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | 세로·가로 막대, 꺾은선, 영역(100% 누적 포함 18종), 방사형 3종 | 1~2 | 가능 | 1~10 | 가능 | 가능(100% 누적 5종은 0~100) | 불가 | 씀 | — |
  | `pie`·`doughnut` | 1 | 불가 | 1 | 불가 | 불가 | 불가 | 씀 | — |
  | 분산형 5종 | 1 | 불가 | 2~10 | 불가 | 가능 | 불가 | 씀 | — |
  | `bubble` | 1 | 불가 | 3 | 불가 | 가능 | 불가 | 씀 | — |
  | `treemap`·`sunburst` | 1~2 | 가능 | 1 | 불가 | 불가 | 불가 | 씀 | — |
  | `histogram` | 0~2 | 불가 | 1 | 불가 | 가능 | 불가 | **안 씀(null)** | `histogram` |
  | `pareto` | 1 | 불가 | 1 | 불가 | 가능 | 불가 | 씀 | — |
  | `waterfall` | 1 | 불가 | 1 | 불가 | 가능 | 불가 | 씀 | `show_total` |
  | `funnel` | 1 | 불가 | 1 | 불가 | 불가 | 불가 | 씀 | — |
  | `combo` | 1 | 불가 | 2~10 | 불가 | 가능 | **가능** | 씀 | `combo_series` |

  계열을 쓰면 값은 정확히 1개다. 100% 누적 5종은 `stacked_100_bar`·`stacked_100_horizontal_bar`·`stacked_100_line`·`stacked_100_line_markers`·`stacked_100_area`다. 화면의 분류 13개 순서는 RC-R1의 순서이고 분류별 하위 종류 수는 3·3·6·2·3·6·3·1·1·2·1·1·1이다.

요청 `chart` 검증 (서버, `parse_chart`)
- **RC-R3** 차트는 그룹핑한 정의로만 만든다. 그룹 컬럼이 3개 이상이면 다른 검사 없이 위반 하나 `["chart"]` `chart-too-many-groups` "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다"(히스토그램 포함). 그룹 컬럼이 없고 종류가 히스토그램이 아니면 위반 하나 `["chart"]` `chart-needs-grouping` "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)". 그룹 컬럼이 없고 종류를 모르면 종류 위반(RC-R6) 하나뿐이다.
- **RC-R4** 요청 모양: `chart`는 POST·PUT 본문의 선택 필드(생략·null = 차트 없음)이고 16키 외의 키, 필수 키(`kind`·`category`·`values`) 누락은 422 `request-validation`(PL-R12)이다. 값의 타입은 모양 검사에서 보지 않아(모두 `Any`) 예를 들어 `category: "0"`이나 범위를 넘는 큰 정수는 `invalid-report`로 판정된다(500이 아님). 복제 요청 본문에는 `chart` 키가 없어 보내면 `request-validation`이다.
- **RC-R5** 판정 순서와 응답: 메타(이름·설명·공개 범위) 오류가 먼저이고(RS-R2, RS-R4), 정의 위반이 있으면 정의 위반만 알리고 차트는 검사하지 않으며(RQ-R8, RS-R4), 차트 위반이 있으면 배치(`layout`)는 검사하지 않는다(RS-R4, RS-R20). 차트 위반은 **모두 모아** 422 `invalid-report`(type 접미사), `detail` = 첫 위반 문구, `errors` = `[{location: ["chart", …], code, message}]`로 알리고 아무것도 저장하지 않는다(커밋 없음). 모든 문구는 한국어다.
- **RC-R6** 종류: 33개 키가 아니면 `["chart","kind"]` `chart-kind-invalid` "차트 종류를 알 수 없습니다". 그룹 컬럼 수가 종류의 최대를 넘으면 `["chart","kind"]` `chart-kind-groups` "이 차트는 그룹핑 컬럼이 {N}개 이하일 때 만들 수 있습니다"(N = 그 종류의 최대). 종류를 모르면 종류에 따른 판정(범주 사용 여부·계열 허용·값 개수·전환·보조 축·축 범위 허용·옵션 허용)은 건너뛰고 종류와 무관한 판정(index 형식·글자·범례·켜기끄기 타입·숫자 형식)은 한다.
- **RC-R7** 범주: 범주를 쓰는 종류는 그룹 컬럼의 정수 index여야 한다(그룹 2개면 둘 중 어느 쪽이든). 아니면(값 컬럼 index, 범위 밖, null, 문자열, bool) `["chart","category"]` `chart-category-invalid` "범주 열은 그룹핑한 컬럼이어야 합니다". 히스토그램은 범주가 null이어야 하고 값이 있으면 같은 코드 "이 차트는 범주 열을 쓰지 않습니다".
- **RC-R8** 계열: 계열을 허용하는 종류이고 그룹 컬럼이 2개인데 계열이 null이면 `["chart","series"]` `chart-series-required` "그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요". 계열을 허용하지 않는 종류에 계열 값이 있으면 `chart-series-invalid` "이 종류는 계열 열을 쓰지 않습니다". 계열이 범주와 다른 그룹 컬럼 index가 아니면(그룹 1개인 정의 포함) `chart-series-invalid` "계열 열은 범주와 다른 그룹핑 컬럼이어야 합니다".
- **RC-R9** 값: 목록이 아니면 `["chart","values"]` `chart-values-invalid` "값 열을 고르세요". 10개를 넘으면 위반 하나 `["chart","values"]` `chart-values-count` "값 열은 최대 10개까지 고를 수 있습니다"(항목별 검사 없음). 항목 i가 값 컬럼 index가 아니면 `["chart","values",i]` `chart-value-invalid` "값 열은 숫자(집계) 컬럼이어야 합니다"(그룹핑 없는 히스토그램은 "값 열은 숫자 컬럼이어야 합니다"), 앞 항목과 같으면 `chart-value-duplicate` "같은 값 열을 두 번 고를 수 없습니다". 종류를 알면 받은 개수(잘못된 항목 포함)가 RC-R2 범위 밖일 때 `["chart","values"]` `chart-values-count` "이 차트는 값 열을 {N}개 골라야 합니다" 또는 "…{a}~{b}개 골라야 합니다". 빈 목록도 개수 위반이다. 순서는 받은 그대로 저장한다. 그룹핑 없는 히스토그램의 값 후보는 그룹·집계가 없는 정수·소수 컬럼, 그룹 있는 히스토그램은 집계 컬럼이다.
- **RC-R10** 켜기·끄기: `swap`·`data_labels`·`secondary_axis`·`show_total`은 bool이어야 한다. bool이 아니면 `swap`은 `["chart","swap"]` `chart-swap-invalid` "이 차트는 행/열 전환을 쓸 수 없습니다"(다른 켜기·끄기 칸과 문구가 다르지만 현행대로 둔다, 2026-11-11 결정), 나머지는 `chart-flag-invalid` "켜기·끄기 값이어야 합니다". `swap: true`는 전환 가능한 종류만(아니면 `chart-swap-invalid` 같은 문구), `secondary_axis: true`는 콤보만(아니면 `["chart","secondary_axis"]` `chart-secondary-invalid` "보조 축은 콤보 차트에서만 쓸 수 있습니다").
- **RC-R11** 글자: `title`·`category_axis_title`·`value_axis_title`은 문자열이고 NUL 문자가 없으며 앞뒤 공백을 지운 길이가 100 이하여야 한다. 아니면 `["chart",<키>]` `chart-text-invalid` "100자 이내 글자로 입력하세요". 앞뒤 공백을 지워 저장하고 공백만이면 빈 글자다.
- **RC-R12** 범례: `top`·`right`·`bottom`·`none` 중 하나, 아니면 `["chart","legend"]` `chart-legend-invalid` "범례 위치는 top·right·bottom·none 중 하나입니다".
- **RC-R13** 축 범위 `value_min`·`value_max`: null이거나 bool이 아닌 유한 정수·소수이고 절댓값 2^53−1 이하(아니면 `["chart",<키>]` `chart-range-invalid` "숫자를 입력하세요"). 축 범위를 쓰지 않는 종류(원형·도넛형·트리맵·선버스트·깔때기)에 값이 있으면 같은 코드 "이 차트는 축 범위를 쓸 수 없습니다". 100% 누적 5종은 0~100 밖이면 "0~100 사이로 입력하세요". 한쪽만 줘도 된다. 둘 다 있고 최소 ≥ 최대이면(어떤 `chart-range-invalid`도 없을 때만) `["chart","value_max"]` `chart-range-order` "최대는 최소보다 커야 합니다".
- **RC-R14** 히스토그램 구간 `histogram`(히스토그램만): 생략·null이면 `auto`(나머지 4칸 null)로 정규화한다. 정확히 5키 객체가 아니면 `["chart","histogram"]` `chart-histogram-invalid` "구간 설정 형식이 올바르지 않습니다". `bin_mode`가 셋 중 하나가 아니면 `["chart","histogram","bin_mode"]` "구간 방식은 auto·count·width 중 하나입니다". `count`: `bin_count`는 1~100 정수("구간 수는 1~100의 정수입니다"), `width`: `bin_width`는 0보다 큰 유한 숫자(절댓값 2^53−1 이하, "구간 너비는 0보다 큰 숫자입니다"), 방식이 쓰지 않는 칸(`auto`의 두 칸, `count`의 너비, `width`의 수)은 null이어야 한다("이 구간 방식에서는 비워 두세요"). `overflow`·`underflow`는 null 또는 숫자("숫자를 입력하세요")이고 둘 다 있으면 언더플로 < 오버플로(아니면 `["chart","histogram","overflow"]` `chart-range-order` "오버플로 구간은 언더플로 구간보다 커야 합니다"). 위 구간 위반의 코드는 모두 `chart-histogram-invalid`(순서만 `chart-range-order`)다.
- **RC-R15** 폭포 합계 `show_total`: `true`는 폭포만 쓸 수 있다(다른 종류는 `["chart","show_total"]` `chart-option-invalid` "이 차트는 이 옵션을 쓰지 않습니다"). `false`는 모든 종류에 허용된다.
- **RC-R16** 콤보 계열 `combo_series`(콤보만): 생략·null이면 옛 규칙으로 채운다 — 첫 값은 `{column, secondary: false}`, 나머지는 `{line, secondary: <secondary_axis>}`. 목록이 아니면 `["chart","combo_series"]` `chart-combo-invalid` "계열 설정은 목록이어야 합니다", 길이가 값 개수와 다르거나 10을 넘으면 위반 하나 "계열 설정 수가 값 열 수와 같아야 합니다", 항목 i가 `{type: 6종 중 하나, secondary: bool}` 정확히 2키가 아니면 `["chart","combo_series",i]` "계열 종류와 보조 축을 확인하세요". 모든 계열이 보조 축이면 `["chart","combo_series"]` `chart-combo-secondary-all` "모든 계열을 보조 축에 둘 수 없습니다". `secondary_axis`가 bool이고 "보조 축 계열이 하나라도 있음"과 다르면 `["chart","secondary_axis"]` `chart-secondary-mismatch` "보조 축 설정이 계열 설정과 맞지 않습니다". 저장되는 `secondary_axis`는 계열에서 계산한 값이다.
- **RC-R17** 종류가 쓰지 않는 옵션(`histogram`·`combo_series`에 값, `show_total: true`)은 `["chart",<옵션>]` `chart-option-invalid` "이 차트는 이 옵션을 쓰지 않습니다"다. 검증을 통과한 차트의 정규화 값은 16키를 모두 가진다: 글자는 앞뒤 공백 제거, `histogram`은 히스토그램만 값(그 밖 null), `show_total`은 폭포가 아니면 false, `combo_series`는 콤보만 값(그 밖 null), `secondary_axis`는 콤보면 계열에서 계산. 정규화 값을 다시 검증하면 같은 값이 나온다.

저장 리포트 안의 차트 (RS 경로의 차트 부분 — 2026-11-11 결정으로 RC 소유. RS-R10·RS-R12·RS-R13·RS-R15는 이 번호를 가리키고, 같은 동작의 케이스는 RC-033~RC-048이 가진다)
- **RC-R18** 저장·덮어쓰기(POST·PUT): 차트는 **함께 보낸 정의**로 검증한다(RC-R3~R17). 통과하면 정규화 값을 저장하고 응답 `chart`는 그 값, `chart_problem`은 null이다. `chart`를 생략하거나 null로 보내면 차트 없음이고, PUT에서는 저장된 차트를 지운다. 차트만 바꿔도 revision이 1 오르고 `updated_by`·`updated_at`이 바뀌며 `generated_sql`은 차트와 무관하다. 위반이면 아무것도 바뀌지 않는다(정의·차트·revision 그대로). 덮어쓰면 "읽을 수 없음" 표시가 지워진다.
- **RC-R19** 목록 항목에는 `chart`가 없고 `chart_kind` = 저장 차트의 종류 키(차트 없음·읽을 수 없음이면 null)다. 상세(GET·POST·PUT·복제 응답)에는 `chart`·`chart_problem`·`chart_kind`가 있다.
- **RC-R20** 복제: 원본 차트를 원본 정의 기준으로 **지금 규칙으로 다시 검증**해 복사한다. 원본 차트가 지금 규칙에 맞지 않으면 422 `invalid-report`(차트 위치)이고 복사본을 만들지 않는다. 원본 차트를 읽을 수 없으면 차트 없이 복사한다(복사본 `chart` null, `chart_problem` null). 원본은 바뀌지 않는다.
- **RC-R21** 저장 차트 읽기(`chart_from_json`)는 모양과 값 형식만 보고 **정의와 맞는지는 보지 않는다**(맞지 않는 차트도 그대로 나오고 화면이 RC-R40으로 알린다). 다음이면 깨진 차트다: 객체가 아님, `kind`·`category`·`values` 키 없음, `kind`가 33개 키가 아님, `legend`가 네 값이 아님, `category`가 null·정수가 아님, `values`가 정수 목록이 아님, `series`가 null·정수가 아님, 글자 키가 문자열이 아님, 켜기끄기 키(`swap`·`data_labels`·`secondary_axis`·`show_total`)가 bool이 아님, 축 범위가 null·숫자가 아님, `histogram`이 null이 아니면서 5키·`bin_mode` 3값·`bin_count` null·정수·나머지 null·숫자가 아님, `combo_series`가 null이 아니면서 `{type: 6종, secondary: bool}` 목록이 아님. 깨진 차트는 리포트를 막지 않는다: 상세 200 `chart` null·`chart_problem` "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."·`chart_kind` null, 목록 `chart_kind` null, 실행·삭제·덮어쓰기(새 차트 또는 차트 없이 — 복구)는 그대로 된다.
- **RC-R22** 읽기 호환 변환: 옛 13키(새 키 `histogram`·`show_total`·`combo_series`가 없음)와 선택 키가 빠진 저장 값은 기본값(RC-2.2)으로 읽는다. 종류가 히스토그램이고 `histogram`이 없거나 null이면 `auto` 구간, 종류가 콤보이고 `combo_series`가 없거나 null이면 RC-R16의 옛 규칙(첫 값 묶은 세로 막대, 나머지 꺾은선, 저장된 `secondary_axis`가 true면 꺾은선이 보조 축)으로 채운다. 저장된 구간·합계·콤보 계열 값은 그대로 둔다. 읽을 때는 종류와 무관하게 `category` null을 받는다. 예전에 `line`으로 저장한 차트는 지금 규칙대로 표식 없이 그린다(RC-R44).
- **RC-R23** API 계약(openapi): 요청 `ReportChartRequest`는 16키·알 수 없는 키 금지(`additionalProperties: false`), `chart`는 POST·PUT의 선택·nullable 필드이고 `category`는 nullable, 복제 요청에는 `chart`가 없다. 상세 응답 `chart`는 `ReportChartResponse | null`(16키 모두 필수, `kind`는 33값 enum, `category`·`series`·`value_min`·`value_max` nullable, `histogram`은 5키 `HistogramResponse | null`, `combo_series`는 `{type, secondary}` 목록 | null, `show_total` 필수 bool), `chart_problem: string | null`, `chart_kind: ChartKind | null`. 목록 항목은 `chart_kind`만 있다. 실행(`/run`)·조회(`/reports/query`) 계약은 차트와 무관하다.

화면: 차트 타일과 설정 패널
- **RC-R24** 차트가 없을 때 타일 본문(`ChartEmpty`): "차트 만들기" 버튼과 안내. 그룹 컬럼 1~2개: "그룹핑 컬럼은 범주(와 계열)로, 나머지 컬럼은 값으로 차트를 그립니다.", 그룹 0개이고 숫자 필드 컬럼이 있으면 "그룹핑이 없으면 히스토그램만 만들 수 있습니다", 숫자 필드도 없으면 "그룹핑한 결과로 차트를 만들 수 있습니다"와 버튼 비활성, 그룹 3개 이상은 "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다"와 버튼 비활성. 편집 화면에서 저장 차트를 읽을 수 없었으면(`chart_problem`) 그 문구를 위에 보인다.
- **RC-R25** "차트 만들기"의 기본 차트(`defaultChart`): 그룹 1개 → `bar`, 범주 = 그 그룹, 값 = 첫 번째 그룹 아닌 컬럼(없으면 빈 값), 그룹 2개 → `stacked_bar`, 범주 = 첫 그룹, 계열 = 둘째 그룹. 가로축 제목 = 범주 머리글, 세로축 제목 = 값 머리글(없으면 ""), 제목 "", 범례 위, 데이터 레이블·전환·보조 축 끔, 범위 비움, 구간 자동, 합계 끔. 그룹 0개 → 첫 숫자 필드 컬럼 하나의 `histogram`(범주·계열 없음, 가로축 제목 = 그 머리글, 세로축 제목 "빈도"), 숫자 필드가 없거나 판정 함수가 없으면 만들지 않음. 그룹 3개 이상이면 만들지 않음. 머리글은 마지막 조회 결과의 열 머리글, 아직 조회하지 않은 컬럼은 설계의 컬럼 이름이다.
- **RC-R26** 패널 열림: 차트를 만들면 설정 패널이 열린다. 타일 머리의 "차트 설정" 버튼(차트가 있을 때만)이 패널을 열고 닫는다. 패널 아래 "차트 삭제"는 차트를 없애 빈 상태(RC-R24)로 돌린다. 패널 열림은 저장하지 않으며 다시 조회해도 차트·패널 열림·결과 탭이 유지된다. 차트를 바꿔도 결과 표는 다시 조회할 필요가 없다(조회 설계에 들어가지 않음).
- **RC-R27** 종류 고르기(`KindPicker`): 왼쪽 라디오 그룹 "차트 분류"(13개, RC-R1 순서)와 오른쪽 버튼 묶음 "하위 종류"(고른 분류의 하위 종류만, 고른 종류는 `aria-pressed=true`). 하위 종류 버튼을 누르면 그 종류, 분류를 고르면 그 분류에서 지금 그룹 수로 쓸 수 있는 첫 하위 종류가 된다. 그룹 수가 최소보다 적은 종류는 잠기고 이유(title) "그룹핑한 결과로 만들 수 있습니다", 최대보다 많은 종류는 "그룹핑 컬럼이 {N}개 이하일 때 쓸 수 있습니다". 쓸 수 있는 하위 종류가 없는 분류는 잠기고 첫 하위 종류의 이유를 보이며 눌러도 바뀌지 않는다(그룹 0개면 히스토그램 분류만, 그 안의 파레토는 잠김). 키보드: 화살표로 분류 이동(이동한 분류의 첫 하위 종류로 바뀜), Tab으로 하위 종류 버튼, Enter·Space로 선택.
- **RC-R28** 종류를 바꿀 때 정리(`normalizeForKind`): 범주를 쓰지 않는 종류(히스토그램)는 범주·계열을 비우고, 범주를 쓰는 종류로 오면 비어 있던 범주를 첫 그룹으로 채운다(있던 범주는 유지). 계열을 쓰지 않는 종류는 계열을 비우고, 계열을 쓰는 종류이고 그룹 2개·계열 없음이면 범주가 아닌 그룹을 계열로 채운다. 값은 종류 최대(계열이 있으면 1)까지 자른다(모자란 값은 안내로 알림, RC-R32). 전환·보조 축·축 범위는 종류가 허용하지 않으면 끄거나 비우고, 합계는 폭포가 아니면 끄고, 콤보로 오면 값마다 계열 설정을 채운다(있던 설정은 값 컬럼 uid로 유지, 없으면 첫 값 묶은 세로 막대·나머지 꺾은선).
- **RC-R29** 데이터 칸: "범주" 선택은 그룹 컬럼만(히스토그램은 비활성·"(없음)"·title과 안내 "이 차트는 범주 열을 쓰지 않습니다"), "계열" 선택은 그룹이 2개일 때만 그 둘(계열을 쓰지 않는 종류는 비활성 title "이 종류는 계열 열을 쓰지 않습니다", 그룹이 2개 미만이면 "(없음)"·title "그룹핑 컬럼이 2개일 때 계열을 고를 수 있습니다"). 계열에 지금 범주 컬럼을 고르거나 범주에 지금 계열 컬럼을 고르면 둘이 서로 바뀌고, 계열을 새로 고르면 값은 첫 하나만 남는다. "값"은 그룹이 아닌 컬럼마다 체크박스(그룹핑 없는 히스토그램은 숫자 필드 컬럼만, 후보가 없으면 "값으로 쓸 숫자 컬럼이 없습니다")이고, 값 최대가 1이면 체크한 것으로 바꾼다. 값 순서는 컬럼 순서다. "행/열 전환"은 허용 종류만(그 밖 비활성 title "이 종류는 행/열 전환을 쓸 수 없습니다").
- **RC-R30** 종류별 옵션 칸:
  - "구간"(히스토그램만, `HistogramOptions`): "구간 방식" 자동·구간 수·구간 너비, "구간 수"는 구간 수 방식에서만, "구간 너비"는 너비 방식에서만 활성(아니면 title "구간 방식이 구간 수일 때 쓸 수 있습니다" / "…구간 너비일 때…"), "오버플로 구간"(안내 "이 값보다 큰 값을 한 구간으로 묶습니다")·"언더플로 구간"("이 값 이하의 값을 한 구간으로 묶습니다"). 입력은 글자 그대로 보관하고 방식을 바꿔도 쓰지 않는 칸 글자를 지우지 않는다.
  - "폭포"(폭포만): 체크박스 "마지막에 합계 막대".
  - "계열"(콤보만, `ComboSeriesEditor`): "콤보 프리셋" 선택(묶은 세로 막대 - 꺾은선 / 묶은 세로 막대 - 보조 축의 꺾은선 / 누적 영역 - 묶은 세로 막대 / 사용자 지정 조합)과 값마다 한 줄(머리글, "<머리글> 종류" 6종: 묶은 세로 막대·누적 세로 막대·꺾은선·표식이 있는 꺾은선·영역·누적 영역, "<머리글> 보조 축"). 프리셋을 고르면 모든 줄을 채우고, 지금 설정이 어느 프리셋과 같으면 그 프리셋, 아니면 "사용자 지정 조합"으로 보인다. 프리셋은 저장하지 않는다. 프리셋 내용: ① 첫 값 묶은 세로 막대·나머지 꺾은선 ② ①과 같되 꺾은선이 보조 축 ③ 마지막 값 묶은 세로 막대·나머지 누적 영역. 어느 프리셋도 모든 계열을 보조 축에 두지 않는다. 계열 설정을 바꾸면 `secondaryAxis` = 보조 축 계열이 하나라도 있음.
- **RC-R31** 제목·범례·축 칸: "차트 제목", "범례"(위·오른쪽·아래·숨김), "데이터 레이블"(트리맵은 비활성 title "트리맵은 이름과 값을 항상 보입니다"), 축 제목 두 칸(가로 막대 3종·깔때기는 "세로축 제목(범주)"·"가로축 제목(값)", 그 밖 "가로축 제목"·"세로축 제목"), 범위 두 칸("<축> 최소"·"<축> 최대", 축 = 방사형 "반지름 축", 가로 막대·깔때기 "가로축", 그 밖 "세로축"). 원형·방사형·트리맵·선버스트 분류는 두 축 제목이 비활성(title "이 종류는 축이 없습니다"), 깔때기는 값 축 제목이 비활성("깔때기는 값 축을 보이지 않습니다"), 범위를 쓰지 않는 종류는 범위 칸 비활성("이 종류는 축 범위를 쓸 수 없습니다"), 100% 누적은 안내 "100% 누적은 0~100 사이로 입력하세요", 콤보가 아니면 "보조 축" 체크박스가 비활성(title "보조 축은 콤보 차트에서만 쓸 수 있습니다", 콤보는 계열 칸에서 고름). 설정을 바꾸면 미리보기가 바로 바뀐다.
- **RC-R32** 화면 안내(`chartDraftIssues`, 저장을 막지 않음, 서버가 정본): 그룹 수가 종류 최대 초과(part `category`, "이 차트는 그룹핑 컬럼이 {N}개 이하일 때 만들 수 있습니다"), 범주를 쓰는 종류의 범주 없음·그룹 아님("범주 열을 고르세요"), 계열 필요(RC-R8 문구), 값 없음("값 열을 고르세요")·개수(RC-R9 문구), 범위 글자가 숫자가 아님("숫자를 입력하세요")·순서(RC-R13 문구), 히스토그램 구간(RC-R14의 수·너비·숫자·순서 문구, 방식이 쓰지 않는 칸은 보지 않음)과 그룹핑 없는 히스토그램의 숫자 아닌 값("값 열은 숫자 컬럼이어야 합니다"), 콤보 모든 계열 보조 축(RC-R16 문구). 범주 안내 문구가 서버("범주 열은 그룹핑한 컬럼이어야 합니다")와 다른 "범주 열을 고르세요"인 것과 그룹 수 초과 안내가 part `category`에 붙는 것은 현행대로 둔다(2026-11-11 결정). 안내는 해당 칸 옆에 보이고 칸에 `aria-invalid`·`aria-describedby`가 붙는다. 안내가 하나라도 있으면 미리보기는 그리지 않는다(RC-R35).
- **RC-R33** 서버 위반 표시: 저장이 422 `invalid-report`로 거절되면 `["chart", …]` 위치의 위반은 차트 칸에 붙는다. 칸 이름은 `"chart"` 뒤의 문자열 조각을 "."로 이은 것이고 항목 번호는 버린다(`["chart","histogram","bin_count"]` → `histogram.bin_count`, `["chart","values",0]` → `values`, `["chart"]` → 차트 전체). `category`·`series`·`values`·`value_min`·`value_max`·`combo_series`·`histogram.*`는 그 칸 옆, 나머지(`kind`·전체 등)는 패널 위쪽에 보인다. 화면 안내와 같은 문구는 한 번만 보인다. 첫 위반이 차트 위치면 결과 탭으로 옮기고 설정 패널을 연다(아니면 작성 탭, RQ-R49). 차트를 고치면 그 서버 위반은 사라진다.
- **RC-R34** 컬럼 참조와 요청 변환: 초안은 컬럼 uid로 가리켜 컬럼을 옮기면 요청 index가 따라 바뀐다. 컬럼을 지우거나 그룹핑을 바꾸면(`reconcileChart`) 없어진 범주·계열은 비우고, 지워졌거나 그룹이 된 값은 빼며 나머지 설정은 그대로 둔다(컬럼만 옮기면 차트는 그대로). 요청(`chartInputFor`)은 참조가 없으면 범위 밖 index 대신 null, 숫자 칸은 빈칸 → null·숫자 글자 → 숫자·그 밖 글자는 그대로 보내 서버가 위치와 함께 거절하게 한다. 종류가 쓰지 않는 옵션은 비워 보내고(`histogram` null, `showTotal` false, `comboSeries` null), 구간은 방식이 쓰는 칸만 보내며(나머지 null), 콤보는 값 순서대로 계열 설정(없으면 기본)과 계산한 `secondaryAxis`를 보낸다. 저장된 차트(index)를 초안으로 바꿀 때(`fromChartInput`) 범위 밖 index는 참조 없음으로 두고, 구간 숫자는 글자로, 콤보 계열은 값 컬럼 uid 키로 옮긴다.
- **RC-R35** 미리보기(편집): 안내가 있으면 "설정을 완성하면 차트가 그려집니다", 결과가 없으면 "조회하면 차트가 그려집니다", 차트가 쓰는 컬럼이 마지막 조회 결과에 없으면 "조회하면 차트에 반영됩니다", 그 밖에는 그린다. 그린 차트 아래에 빌더 안내(notes)를 한 줄씩, 결과가 행 한도로 잘렸으면(RQ-R31) "최대 행 수 제한으로 표시된 행만 차트에 그렸습니다"를 보인다. 그림(canvas)은 `role=img`이고 접근성 이름은 "<제목>. <설명>. 같은 값이 결과 표에 있습니다"(제목이 없으면 앞부분 생략, 설명 = "<종류 이름> 차트: <범주 머리글> 기준 <값 머리글, …>", 히스토그램은 "히스토그램 차트: <값 머리글> 분포")다. 데이터 레이블 플러그인은 차트 인스턴스에만 붙인다(전역 등록 없음).
- **RC-R36** 보기 화면 차트 타일: 설정 패널·"차트 설정" 버튼 없이 저장 차트를 그린다. 저장 차트가 없으면 `chart_problem`이 있을 때 그 문구, 없을 때 "이 리포트에는 저장된 차트가 없습니다. 편집 화면에서 만들 수 있습니다.", 결과를 읽는 동안 "불러오는 중…". 편집 화면은 저장 차트를 같은 패널 값으로 열고(RC-R34), 차트가 없거나 읽을 수 없었으면 빈 상태(RC-R24)로 연다.
- **RC-R37** 목록 "차트" 열: "데이터" 열 다음, "만든 사람" 열 앞. 값 = `chart_kind`의 화면 이름(RC-R1), 없으면 "—".
- **RC-R38** 편집 화면의 차트와 저장 상태: 편집 화면 저장 안 됨·되돌리기 중 차트 부분은 이 규칙이 가진다(일반 규칙은 새 리포트 화면 RQ-R54, 편집 화면 RS-R32·RS-R33, 2026-11-11 결정). 차트(만들기·바꾸기·종류·지우기)는 설계 키에 들어가 저장 안 됨 표시와 떠날 때 확인을 일으키고, 원래대로 돌리면(만들었다 지움 포함) 표시가 사라진다. 차트만 바꿔도 결과 표는 그대로다. "되돌리기"는 저장 차트를 되살리고(로드 뒤 만든 차트는 지움) 차트만 바뀐 경우 결과 표를 유지, 조회 설계도 바뀐 경우 결과를 지운다. 덮어쓰기 성공 뒤 초안과 기준선은 서버가 정리한 값(예: 제목 앞뒤 공백 제거)으로 맞춘다. 저장 본문에는 차트가 없으면 `chart: null`을 보내 덮어쓰기가 차트를 지운다.
- **RC-R39** 게이트웨이 변환(`mappers/reportChart.ts`): 응답 차트를 화면 모양(camelCase)으로 바꾸고 null인 범위·계열은 null로 둔다. 모르는 `kind`(상세·목록 `chart_kind` 모두)·`legend`·`bin_mode`·콤보 `type`은 화면이 그릴 수 없으므로 `malformed-response`(502, PL-R39)다. 요청 본문은 16키 snake_case를 모두 보내며 불완전한 값도 그대로 보낸다. 복제 요청에는 차트를 보내지 않는다.

화면: 그리기(빌더가 만드는 Chart.js 설정)
- **RC-R40** 결과 대응: 차트 index를 마지막 결과 열로 푼다. 범주가 결과의 그룹 열이 아님, index가 결과 열에 없음, 결과의 그룹 열 수 > 종류 최대, 계열을 쓰지 않는 종류에 계열이 있거나 계열이 그룹 열이 아님·범주와 같음, 값이 그룹 열·숫자 열 아님, 값 개수가 규칙 밖이면 그리지 않고 "차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요"를 보인다. 히스토그램은 범주·계열이 null이고 값이 하나이며 그 열이 그룹이 아닌 숫자 열이어야 한다.
- **RC-R41** 행렬(`pivot`): 범주는 결과 행 순서의 첫 등장 순, 계열이 없으면 값 열마다 데이터셋 하나(이름 = 열 머리글), 계열이 있으면 계열 값(첫 등장 순)마다 데이터셋 하나(값은 첫 값 열). 범주·계열 이름은 결과 표와 같은 서식이고 빈 값은 "(없음)". 앞 N자(RQ-R13, RQ-R51)는 축 눈금·범례 이름에만 적용하고 툴팁 제목·툴팁 계열 이름·데이터 레이블·분산형 점 이름은 전체 값이다. 행/열 전환은 허용 종류에서만 범주와 데이터셋을 맞바꾼다(잘린 이름·전체 이름 짝 유지).
- **RC-R42** 점 한도: 점이 1,000개를 넘으면 그리지 않고 "범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요"(정확히 1,000개는 그림). 점 수 = 막대·꺾은선·영역·원형·방사형·트리맵·선버스트·콤보는 범주 × 데이터셋, 분산형은 결과 행 × (값 − 1), 거품형은 결과 행, 파레토·폭포·깔때기는 범주 수. 히스토그램은 표본이 아니라 일반 구간 수에 한도를 두고 1,000개를 넘으면 "구간이 너무 많아 차트를 그리지 않습니다(최대 1,000개). 구간 너비를 늘리세요"(오버·언더플로 구간은 세지 않음).
- **RC-R43** 공통 옵션: 모든 차트 `responsive: true`·`maintainAspectRatio: false`. 제목 플러그인은 제목이 있을 때만 표시. 범례는 `none`이면 숨기고 그 밖은 그 위치(히스토그램·깔때기·트리맵은 범례 없음). 데이터 레이블은 `data_labels`로 켜고 끄며 글자는 결과 표와 같은 서식(100% 누적은 "x.x%"). 축 제목은 글자가 있을 때만 표시. 값 축 `min`·`max`는 설정에 숫자가 있을 때만(100% 누적은 최대 기본 100). 툴팁 값 글자는 결과 표 칸과 같다. 금액(`unit` krw, RQ-R4·RQ-R36)은 원 그대로 그리고(나누지 않음) 툴팁·레이블은 원 단위 콤마, 값 축에 올라간 값 열이 **모두** 금액(건수 집계 제외)이면 축 눈금을 억·만 단축 표기(`formatWonAxis`)로 쓴다(가로 막대는 x축, 콤보는 축별·분산형은 x·y 따로 판정, 100% 누적은 % 눈금 유지, 원형은 축 없음).
- **RC-R44** 막대·꺾은선·영역 21종: 막대 종류는 Chart.js `bar`, 꺾은선·영역은 `line`. 가로(`horizontal`)는 `indexAxis: 'y'`이고 범주 축이 y, 값 축이 x다. 누적 막대는 두 축 모두 `stacked`, 누적 꺾은선·영역은 값 축 `stacked`(데이터셋 `stack` 공통). 100% 누적은 범주마다 계열 합 대비 %(합 0이면 0)로 그리고 값 축 최대 100·눈금 "<v>%", 툴팁 "<계열>: <x.x>% (<원래 값>)". 빈 칸은 막대·누적이면 0, 누적 아닌 꺾은선·영역이면 null(선이 끊김). 꺾은선 표식은 `_markers` 종류만 `pointRadius: 3`(그 밖 0, `line`은 표식 없음), 영역은 누적이면 `fill: 'stack'` 아니면 `'origin'`, 꺾은선은 `fill: false`. 막대가 아닌 종류는 점 가까이에서 툴팁이 뜨도록 `interaction {mode: 'index', intersect: false}`.
- **RC-R45** 원형·도넛형: Chart.js `pie`·`doughnut`, 데이터셋 하나(첫 데이터셋), 범주마다 한 조각과 색, 빈 값은 0, 툴팁 머리는 범주 전체 이름, 축 없음. 값을 빼지 않는다.
- **RC-R46** 분산형 5종: Chart.js `scatter`, 첫 값 열이 x(선형 축, 축 제목 = 가로축 제목), 나머지 값 열마다 y 계열 하나(이름 = 머리글). 점은 결과 행마다 하나이고 이름은 범주 전체 이름, x·y 중 빈 값이 있는 행은 그 계열에서만 빠진다. 선이 있는 종류는 결과 행 순서대로 잇고(`showLine`), 곡선 종류는 `tension: 0.4`, 표식 종류는 `pointRadius: 3`(그 밖 0). 범위는 y축. 툴팁 "<점 이름>: (<x>, <y>)", 상호작용은 가장 가까운 점.
- **RC-R47** 거품형: Chart.js `bubble`, 값 3개가 x·y·크기. 반지름 = 4 + 26 × √(크기 / 최대 크기) px(면적이 크기에 비례, 최대 30px). x·y가 비면 그 행은 빠지고, 크기가 0 이하·빈 점은 그리지 않으며 "크기가 0 이하이거나 빈 값인 점 {N}개는 그리지 않았습니다". 툴팁 "<이름>: (<x>, <y>, <크기>)". 값이 3개가 아니면 "거품형은 값 열 3개(X, Y, 크기)가 필요합니다".
- **RC-R48** 방사형 3종: Chart.js `radar`, 범주가 꼭짓점, 데이터셋(계열 또는 값 열)마다 선 하나, 빈 값 0, 반지름 축 `r`에 범위 적용. 표식은 `radar_markers`만, 채움은 `radar_filled`만. 범주가 3개 미만이면(계열이 있어도) "방사형은 범주가 3개 이상일 때 그립니다".
- **RC-R49** 트리맵: Chart.js `treemap`(플러그인 `chartjs-chart-treemap`). 행(`treemapTree`)은 (범주, 데이터셋) 칸마다 `{upper: 범주 전체 이름, lower: 계열 전체 이름, value}`이고 계열이 없으면 `{upper, value}`·`groups ['upper']`(한 단계), 있으면 `groups ['upper','lower']`(두 단계). 행 키는 플러그인 예약 이름과 겹치지 않는다. 0 이하·빈 칸은 넣지 않고 "값이 0 이하이거나 빈 칸 {N}개는 그리지 않았습니다", 빈 이름은 "(없음)"으로 바꾼다. 사각형 색은 상위 이름 순번(자식은 부모 색), 글자는 플러그인이 그리고(데이터 레이블 플러그인은 끔) 두 단계면 상위 사각형 캡션 없음·잎은 "<하위 이름>, <값>", 한 단계면 잎에 "<상위 이름>, <값>". 툴팁 제목 = 상위 이름, 본문 = "<하위(또는 상위) 이름>: <값>".
- **RC-R50** 선버스트: Chart.js `doughnut` 겹친 고리. 안쪽 고리(`sunburstRings`) = 범주별 계열 값 합(0 이하·빈 칸 제외 후 합이 0이면 그 범주 없음), 바깥 고리 = (범주, 계열) 쌍을 범주 순서대로(두 고리의 합이 같음). 계열이 없으면 고리는 안쪽 하나뿐이다. 바깥 조각 색은 부모의 안쪽 순번 색(표시 이름이 같은 부모끼리 섞이지 않음). 범례 클릭은 아무것도 숨기지 않는다. 빠진 칸은 "값이 0 이하이거나 빈 칸 {N}개는 그리지 않았습니다". 툴팁 "<상위>: <값>" / "<상위> / <하위>: <값>".
- **RC-R51** 히스토그램 그리기: Chart.js `bar`, 표본 = 값 열의 행마다 한 값(그룹핑 없으면 결과 행, 그룹핑했으면 그룹), 빈 값 제외. 가로축 = 구간 이름(RC-R52), 막대 높이 = 개수, 데이터셋 이름 "빈도", 막대 사이 간격 없음, 범례 없음, 세로축 0부터·정수 눈금, 범위는 세로(빈도)축. 툴팁 제목 = 구간 이름, 본문 "빈도: <개수>".
- **RC-R52** 구간 계산(`histogramBins`): 순서는 언더플로("≤ x", `v ≤ underflow`) → 일반 구간 → 오버플로("> x", `v > overflow`). 일반 구간은 그 사이 값만으로 만든다: `auto`는 Scott 규칙(너비 3.49·s·n^(−1/3), 구간 수 = ⌈범위/너비⌉, 1~100), `count`는 범위를 그 수(1~100)로 같게 나눔, `width`는 최솟값에서 그 너비씩(마지막 구간이 최댓값을 넘을 수 있음, 만들어 보는 구간은 최대 1,001). 표본이 하나이거나 모두 같으면 `[min, max]` 구간 하나. 경계 값은 아래 구간에 든다. 이름은 첫 구간 "[a, b]", 나머지 "(a, b]"이고 숫자는 천 단위 구분·소수 최대 둘째 자리. 표본이 없으면 구간 없음. 개수 합 = 표본 수.
- **RC-R53** 파레토: Chart.js `bar` + 꺾은선. 0 이하·빈 항목을 빼고 값 내림차순(같으면 결과 순서, 리포트 정렬과 무관) 막대(y축)와 누적 %(누계/합 × 100, 마지막은 정확히 100) 꺾은선(오른쪽 보조 축 y1, 0~100, 눈금 "<v>%"). 빠진 항목은 "값이 0 이하이거나 빈 항목 {N}개는 그리지 않았습니다".
- **RC-R54** 폭포: Chart.js `bar`, 결과 행 순서대로 앞 누계에서 시작하는 뜬 막대 `[from, to]`(빈 값 0, 0은 증가). 데이터셋은 "증가"·"감소"(·"합계") 범례 항목으로 나뉘고 `show_total`이면 끝에 범주 "합계"와 `[0, 최종 누계]` 막대를 붙인다(아니면 합계 항목·막대 없음). 툴팁·레이블은 증가·감소 막대는 변화량, 합계 막대는 누계다.
- **RC-R55** 깔때기: Chart.js `bar` 가로(`indexAxis: 'y'`), 결과 행 순서대로(정렬하지 않음) 가운데 정렬 막대 `[−v/2, v/2]`, 값 축(x)은 숨기고 범위는 가장 큰 막대 기준 대칭. 0 이하·빈 항목은 빼고 "값이 0 이하이거나 빈 항목 {N}개는 그리지 않았습니다", 범례 없음.
- **RC-R56** 콤보: Chart.js `bar`에 데이터셋마다 `type`. 값마다 계열 설정(서버가 채운 값, 없으면 RC-R16 옛 규칙 — 화면도 같은 규칙)대로: 묶은 세로 막대는 계열마다 고유 `stack`, 누적 세로 막대는 공통 `stack 'bars'`, 꺾은선(표식 종류만 `pointRadius 3`)은 계열마다 고유 `stack`·`fill: false`, 영역은 고유 `stack`·`fill 'origin'`, 누적 영역은 공통 `stack 'areas'`·`fill 'stack'`. 꺾은선이 막대 위에 그려진다(`order` 꺾은선 0 < 영역 2·막대 1 순). 보조 축 계열은 `yAxisID 'y1'`(오른쪽 축, 격자 없음)이고 보조 축 계열이 있을 때만 y1이 있다. 누적 세로 막대가 있으면 x축 `stacked`, 그 축의 누적 종류가 있으면 y·y1 `stacked`. 범위는 주 축(y). 빈 칸은 막대·누적 종류 0, 꺾은선·영역 null.

테스트 Fake
- **RC-R57** 프런트 Fake 게이트웨이(`test/fake/gateway/savedReports.ts`)의 차트 처리는 서버 규칙의 일부만 흉내 낸다(전체 규칙은 backend 케이스가 정본). 흉내 내는 부분은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**: 차트 없음 → null. 그룹 컬럼이 3개 이상이면 종류와 무관하게(히스토그램 포함) 위반 하나 `["chart"]` `chart-too-many-groups` "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다". 히스토그램이 아닌 종류는 그룹 컬럼이 없으면 위반 하나 `["chart"]` `chart-needs-grouping` "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)"(RC-R3). 범주를 쓰는 종류의 범주가 그룹 컬럼 index가 아니면 `["chart","category"]` `chart-category-invalid` "범주 열은 그룹핑한 컬럼이어야 합니다". 통과한 차트는 RC-R17과 같이 정규화한다: 글자 3칸 앞뒤 공백 제거, 히스토그램 구간 생략·null → `{binMode: "auto", 나머지 null}`, 히스토그램이 아니면 `histogram` null, 폭포가 아니면 `showTotal` false, 콤보가 아니면 `comboSeries` null, 콤보 계열 생략·null → RC-R16 옛 규칙(첫 값 묶은 세로 막대, 나머지 꺾은선, `secondaryAxis`가 true면 꺾은선이 보조 축), 콤보 `secondaryAxis` = 보조 축 계열이 하나라도 있음. 덮어쓰기에서 `chart: null`이면 지움, 복제는 원본 차트를 다시 검증해 복사, 목록 `chartKind`, `chartProblem` null. 그 밖의 차트 위반(종류·계열·값 개수·옵션 값·범위·글자 등)은 흉내 내지 않는다.

### 2.4 상태와 전이

차트 초안(디자이너·편집): 없음 → (차트 만들기) → 있음(패널 열림) ⇄ (차트 설정 버튼) 패널 닫힘 → (차트 삭제) → 없음. 있음 상태에서 종류·칸을 바꿔도 있음.

저장 차트(리포트 하나): 없음 ⇄ (POST·PUT에 차트) 있음 → (PUT에 차트 생략·null) 없음. 있음 → (DB 값이 읽기 규칙 위반) 읽을 수 없음 → (PUT 새 차트) 있음 / (PUT 차트 없이) 없음.

### 2.5 권한

차트 고유의 권한은 없다. 차트를 저장·덮어쓰기·복제하는 권한과 상세·목록·실행을 읽는 권한은 저장 리포트 권한(RS 2.5, RS-R5~RS-R9)을 따른다. 권한 판정은 저장 차트를 읽기 전에 끝난다(RS-R12~RS-R16의 판정 순서). 디자이너의 차트 미리보기는 로그인한 모든 역할이 쓴다(RQ 2.5, RQ-R1).

### 2.6 API 계약 (`/api/v1`)

차트는 RS 경로의 본문·응답 필드다(경로·권한·상태 코드 판정 순서는 RS-R12~RS-R14, RS-R26).

| 경로(RS) | 차트 요청 | 차트 응답 | 차트 오류 |
| --- | --- | --- | --- |
| POST `/reports`, PUT `/reports/{id}` | `chart?: ReportChartRequest \| null`(생략·null = 차트 없음, PUT은 저장 차트 삭제) | 상세: `chart`·`chart_problem`·`chart_kind` | 422 `request-validation`(모양), 422 `invalid-report`(`errors[].location[0] == "chart"`) |
| POST `/reports/{id}/copy` | 없음(`chart` 키를 보내면 `request-validation`) | 상세(복사본) | 422 `invalid-report`(원본 차트가 지금 규칙 위반) |
| GET `/reports/{id}` | — | 상세 | — (깨진 차트도 200) |
| GET `/reports` | — | 항목 `chart_kind`만 | — |

스키마는 RC-R23. `errors` 항목은 `{location: (string|int)[], code: string, message: string}`.

### 2.7 화면 동작

RC-R24~RC-R56.

### 2.8 오류와 메시지

서버 차트 위반(422 `invalid-report`, 위치는 `chart` 접두사):

| 위치 | 코드 | 문구 |
| --- | --- | --- |
| `chart` | `chart-too-many-groups` | 차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다 |
| `chart` | `chart-needs-grouping` | 그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외) |
| `chart.kind` | `chart-kind-invalid` / `chart-kind-groups` | 차트 종류를 알 수 없습니다 / 이 차트는 그룹핑 컬럼이 {N}개 이하일 때 만들 수 있습니다 |
| `chart.category` | `chart-category-invalid` | 범주 열은 그룹핑한 컬럼이어야 합니다 / 이 차트는 범주 열을 쓰지 않습니다 |
| `chart.series` | `chart-series-required` / `chart-series-invalid` | 그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요 / 이 종류는 계열 열을 쓰지 않습니다 / 계열 열은 범주와 다른 그룹핑 컬럼이어야 합니다 |
| `chart.values` | `chart-values-invalid` / `chart-values-count` | 값 열을 고르세요 / 값 열은 최대 10개까지 고를 수 있습니다 / 이 차트는 값 열을 {N}개(또는 {a}~{b}개) 골라야 합니다 |
| `chart.values.<i>` | `chart-value-invalid` / `chart-value-duplicate` | 값 열은 숫자(집계) 컬럼이어야 합니다 / 값 열은 숫자 컬럼이어야 합니다 / 같은 값 열을 두 번 고를 수 없습니다 |
| `chart.swap` | `chart-swap-invalid` | 이 차트는 행/열 전환을 쓸 수 없습니다 |
| `chart.secondary_axis` | `chart-secondary-invalid` / `chart-flag-invalid` / `chart-secondary-mismatch` | 보조 축은 콤보 차트에서만 쓸 수 있습니다 / 켜기·끄기 값이어야 합니다 / 보조 축 설정이 계열 설정과 맞지 않습니다 |
| `chart.data_labels`, `chart.show_total` | `chart-flag-invalid` | 켜기·끄기 값이어야 합니다 |
| `chart.title` 등 글자 3칸 | `chart-text-invalid` | 100자 이내 글자로 입력하세요 |
| `chart.legend` | `chart-legend-invalid` | 범례 위치는 top·right·bottom·none 중 하나입니다 |
| `chart.value_min`·`value_max` | `chart-range-invalid` / `chart-range-order`(max) | 숫자를 입력하세요 / 이 차트는 축 범위를 쓸 수 없습니다 / 0~100 사이로 입력하세요 / 최대는 최소보다 커야 합니다 |
| `chart.histogram[.*]` | `chart-histogram-invalid` / `chart-range-order`(overflow) | 구간 설정 형식이 올바르지 않습니다 / 구간 방식은 auto·count·width 중 하나입니다 / 구간 수는 1~100의 정수입니다 / 구간 너비는 0보다 큰 숫자입니다 / 이 구간 방식에서는 비워 두세요 / 숫자를 입력하세요 / 오버플로 구간은 언더플로 구간보다 커야 합니다 |
| `chart.histogram`·`show_total`·`combo_series` | `chart-option-invalid` | 이 차트는 이 옵션을 쓰지 않습니다 |
| `chart.combo_series[.<i>]` | `chart-combo-invalid` / `chart-combo-secondary-all` | 계열 설정은 목록이어야 합니다 / 계열 설정 수가 값 열 수와 같아야 합니다 / 계열 종류와 보조 축을 확인하세요 / 모든 계열을 보조 축에 둘 수 없습니다 |

저장 차트 읽기: 응답 `chart_problem` "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."(내부 위반 `["chart"]` `stored-invalid` "저장된 차트 설정을 읽을 수 없습니다.").

화면 문구: "차트 만들기", "차트 설정", "차트 삭제", "차트 분류", "하위 종류", "데이터", "범주", "계열", "값", "행/열 전환", "구간", "구간 방식", "자동", "구간 수", "구간 너비", "오버플로 구간", "언더플로 구간", "폭포", "마지막에 합계 막대", "콤보 프리셋", "사용자 지정 조합", "보조 축", "제목과 범례", "차트 제목", "범례", "위"·"오른쪽"·"아래"·"숨김", "데이터 레이블", "축", "(없음)", "빈도", "합계", "증가", "감소", "누적 %", RC-R24·R27·R29~R36·R40~R55의 안내 문구.

## 3. Business use case

### RC-UC1 차트 만들기와 설정
- 행위자: 리포트를 작성·편집하는 사용자
- 사전 조건: 디자이너(`/reports/new`) 또는 편집 화면에서 조회한 결과가 결과 탭에 있음
- 기본 흐름: 차트 타일에서 "차트 만들기" → 기본 차트와 설정 패널(RC-R24~R26) → 분류·하위 종류 고르기(RC-R27, R28) → 범주·계열·값·옵션·제목·범례·축 설정(RC-R29~R31) → 미리보기가 바로 바뀜(RC-R35, R40~R56)
- 대안: 그룹핑이 없으면 히스토그램으로 시작, 컬럼을 지우거나 옮기면 차트가 따라감(RC-R34), "차트 삭제"로 없앰
- 예외: 그룹핑 없음(숫자 컬럼 없음)·그룹 3개 이상이면 만들 수 없음, 설정이 덜 되면 안내(RC-R32), 결과와 맞지 않거나 점이 많으면 그리지 않고 이유(RC-R40, R42)
- 결과: 결과 표 옆 차트 타일에 Excel과 같은 종류의 차트

### RC-UC2 차트와 함께 저장·덮어쓰기
- 행위자: 리포트를 저장·덮어쓸 수 있는 사용자(RS-R6, RS-R9)
- 사전 조건: 디자이너 또는 편집 화면
- 기본 흐름: 저장(또는 덮어쓰기) → 서버가 함께 보낸 정의로 차트 검증·정규화(RC-R3~R17) → 저장(RC-R18) → 화면은 정리된 값으로 기준선(RC-R38)
- 대안: 차트 없이 저장, 덮어쓰기로 차트 삭제, 복제 시 차트 함께 복사(RC-R20)
- 예외: 위반이면 422 `invalid-report`이고 저장 안 됨 → 결과 탭에서 설정 패널이 열리고 칸 옆에 서버 문구(RC-R33), 모양 오류는 `request-validation`
- 결과: 리포트에 정규화된 차트(또는 차트 없음)가 저장되고 목록에 종류가 보임(RC-R19, R37)

### RC-UC3 저장된 차트 보기
- 행위자: 리포트를 볼 수 있는 사용자(RS-R5)
- 사전 조건: 저장 리포트
- 기본 흐름: 보기 화면을 연다 → 결과를 다시 조회하고 저장 차트를 읽기 전용으로 그린다(RC-R36, R40~R56)
- 대안: 차트 없는 리포트는 안내 문구, 옛 형식 차트는 변환해 그대로 그림(RC-R22)
- 예외: 저장 차트가 깨졌으면 차트 없이 열고 안내(RC-R21), 결과와 맞지 않으면 "편집에서 고치세요"(RC-R40)
- 결과: 저장 당시 설정의 차트(값은 지금 결과)

## 4. BDD 테스트 케이스

예시 정의(backend): DEF2 = 그룹 2개(0 Vendor, 1 분기) + 집계 값 3개(2 금액 합계, 3 사용자 수 합계, 4 건수), DEF1 = 그룹 1개(0 Vendor) + 집계 값 3개(1 금액 합계, 2 사용자 수 합계, 3 건수), DEF3 = 그룹 3개 + 집계 1개, UNG = 그룹 없음(0 `deal.code`, 1 `deal.amount`). 차트 예시의 생략한 키는 기본값(2.2). backend 케이스는 도메인 검증(`parse_chart`·`chart_from_json`) 단위 테스트, FakeUoW·FakeReportRepository를 쓰는 유스케이스 테스트, FakeUseCases + TestClient web 테스트, Fake와 SQL에 함께 도는 Repository 계약 테스트다. frontend 예시 결과: 열 0 Vendor(그룹), 1 분기(그룹), 2 금액 합계(합계, 금액), 3 건수, 행은 케이스마다 적는다. frontend 케이스는 순수 함수(빌더·계산·초안) Vitest, 컴포넌트 Vitest, Fake 게이트웨이를 쓰는 화면 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| RC-001 | 종류는 33개 키이고 옛 10개 키 이름과 옵션 키 3개는 그대로다 | RC-R1 | backend | `domain/test_report_chart_kinds.py`<br>`domain/test_report_chart_parse.py` |
| RC-002 | 종류별 규칙표가 명세 표와 같다 | RC-R2 | backend | `domain/test_report_chart_kinds.py` |
| RC-003 | 그룹핑 없는 정의에 히스토그램이 아닌 차트는 chart-needs-grouping 하나뿐이다 | RC-R3, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-004 | 그룹 컬럼이 3개면 히스토그램도 chart-too-many-groups 하나뿐이다 | RC-R3, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-005 | 모르는 종류는 chart.kind 위반이고 종류에 따른 검사만 건너뛴다 | RC-R6, RC-R3, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-006 | 그룹 수가 종류 최대를 넘으면 chart-kind-groups와 공통 문구다 | RC-R6, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-007 | 범주는 그룹 컬럼 index여야 하고 그룹 2개면 어느 쪽이든 된다 | RC-R7, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-008 | 히스토그램은 범주가 null이어야 하고 다른 종류의 null 범주는 위반이다 | RC-R7, RC-UC2 | backend | `domain/test_report_chart_parse_kinds.py` |
| RC-009 | 그룹 2개에서 계열을 쓰는 종류는 계열이 필수다 | RC-R8, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-010 | 계열을 쓰지 않는 종류의 계열, 범주와 같거나 그룹이 아닌 계열은 위반이다 | RC-R8, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-011 | 값은 집계 컬럼 index이고 위치별 위반·중복 위반이 있으며 순서는 유지된다 | RC-R9, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-012 | 값 개수는 종류 규칙을 따르고 계열이 있으면 1개다 | RC-R9, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-013 | 값이 10개를 넘으면 목록이 커도 위반은 하나다 | RC-R9, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-014 | 그룹핑 없는 히스토그램은 집계 없는 숫자 컬럼, 그룹 있는 히스토그램은 집계 컬럼만 값으로 받는다 | RC-R9, RC-UC2 | backend | `domain/test_report_chart_parse_kinds.py` |
| RC-015 | 행/열 전환은 허용 종류만, 보조 축은 콤보만이고 켜기·끄기 값이 아니면 위반이다 | RC-R10, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-016 | 글자 칸은 앞뒤 공백을 지우고 100자까지 받는다 | RC-R11, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-017 | 범례는 네 위치만 받는다 | RC-R12, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-018 | 축 범위는 안전한 유한 숫자이고 한쪽만 줄 수 있으며 최소가 최대보다 작아야 한다 | RC-R13, RC-UC2 | backend | `domain/test_report_chart_parse.py` |
| RC-019 | 축 범위가 없는 종류는 범위를 거절하고 100% 누적은 0~100만 받는다 | RC-R13, RC-UC2 | backend | `domain/test_report_chart_parse.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-020 | 구간 설정이 없는 히스토그램은 자동 구간으로 저장된다 | RC-R14, RC-UC2 | backend | `domain/test_report_chart_options.py`<br>`domain/test_report_chart_parse_kinds.py` |
| RC-021 | 구간 수·구간 너비의 경계와 방식이 쓰지 않는 칸을 검사한다 | RC-R14, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`domain/test_report_chart_options.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-022 | 구간 설정 모양·구간 방식이 틀리면 위치와 함께 거절한다 | RC-R14, RC-UC2 | backend | `domain/test_report_chart_options.py` |
| RC-023 | 오버플로·언더플로는 숫자이고 둘 다면 오버플로가 커야 한다 | RC-R14, RC-UC2 | backend | `domain/test_report_chart_options.py` |
| RC-024 | 합계 막대는 폭포만 켤 수 있고 켜기·끄기 값이어야 한다 | RC-R15, RC-R10, RC-UC2 | backend | `domain/test_report_chart_options.py` |
| RC-025 | 종류가 쓰지 않는 옵션은 chart-option-invalid이고 통과한 차트의 옵션은 기본값이다 | RC-R17, RC-UC2 | backend | `domain/test_report_chart_options.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-026 | 계열 설정 없는 콤보는 첫 값 막대·나머지 꺾은선으로 채운다 | RC-R16, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`domain/test_report_chart_options.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-027 | 콤보 계열 설정은 값 개수만큼의 목록이고 항목 모양을 검사한다 | RC-R16, RC-UC2 | backend | `domain/test_report_chart_options.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-028 | 콤보는 모든 계열을 보조 축에 둘 수 없고 secondary_axis는 계열과 맞아야 한다 | RC-R16, RC-UC2 | backend | `domain/test_report_chart_options.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-029 | 정규화한 차트는 16키를 모두 가지고 다시 검증해도 같다 | RC-R17, RC-UC2 | backend | `domain/test_report_chart_options.py`<br>`domain/test_report_chart_parse.py` |
| RC-030 | 차트 위반은 모두 모아 422 invalid-report의 위치·코드·한국어 문구로 돌아온다 | RC-R5, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`domain/test_report_chart_parse.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-031 | 이름 위반이 먼저이고 정의 위반이 있으면 차트 위반은 알리지 않는다 | RC-R5, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-032 | 모양 오류는 request-validation, 값 오류는 invalid-report다 | RC-R4, RC-UC2 | backend | `web/test_saved_report_chart_routes.py` |
| RC-033 | 차트와 함께 저장하면 정규화된 차트가 상세에 나오고 차트 없이 저장하면 null이다 | RC-R18, RC-R19, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-034 | 위반 차트가 있는 저장은 아무것도 저장하지 않는다 | RC-R18, RC-R5, RC-UC2 | backend | `application/test_saved_report_chart.py` |
| RC-035 | 덮어쓰기는 차트를 바꾸거나 지우고 revision을 올리며 SQL은 그대로다 | RC-R18, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`repositories/test_saved_report_chart_contract.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-036 | 정의를 바꿔 이전 차트가 맞지 않는 덮어쓰기는 거절되고 저장 내용은 그대로다 | RC-R18, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-037 | 목록 항목은 차트 종류만 보이고 차트 본문은 없다 | RC-R19, RC-UC3 | backend | `application/test_saved_report_chart.py`<br>`domain/test_saved_report_chart_entity.py`<br>`repositories/test_saved_report_chart_contract.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-038 | 복제는 원본 차트를 다시 검증해 가져가고 깨진 차트는 버린다 | RC-R20, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-039 | 저장 차트 JSON이 읽기 규칙에 어긋나면 stored-invalid다 | RC-R21, RC-UC3 | backend | `domain/test_report_chart_stored.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-040 | 깨진 저장 차트의 리포트는 차트 없이 안내와 함께 열리고 목록·실행은 된다 | RC-R21, RC-UC3 | backend | `application/test_saved_report_chart.py`<br>`domain/test_saved_report_chart_entity.py`<br>`repositories/test_saved_report_chart_contract.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-041 | 깨진 저장 차트는 덮어쓰기로 복구되고 리포트를 삭제할 수 있다 | RC-R21, RC-R18, RC-UC3 | backend | `application/test_saved_report_chart.py`<br>`domain/test_saved_report_chart_entity.py`<br>`repositories/test_saved_report_chart_contract.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-042 | 저장 차트를 읽을 때는 정의와 맞는지 보지 않는다 | RC-R21, RC-UC3 | backend | `application/test_saved_report_chart.py`<br>`domain/test_report_chart_stored.py` |
| RC-043 | 옛 13키 저장 차트는 새 키 기본값으로 읽힌다 | RC-R22, RC-UC3 | backend | `domain/test_report_chart_stored.py`<br>`repositories/test_saved_report_chart_contract.py` |
| RC-044 | 옛 콤보 저장 차트는 첫 값 막대·나머지 꺾은선으로, 보조 축이면 꺾은선이 보조 축으로 읽힌다 | RC-R22, RC-UC3 | backend | `domain/test_report_chart_stored.py`<br>`repositories/test_saved_report_chart_contract.py` |
| RC-045 | 구간 없는 저장 히스토그램은 자동 구간으로 읽히고 저장된 옵션 값은 그대로다 | RC-R22, RC-UC3 | backend | `domain/test_report_chart_stored.py` |
| RC-046 | openapi의 차트 요청·응답 스키마가 명세와 같다 | RC-R23 | backend | `web/test_saved_report_chart_openapi.py` |
| RC-047 | 새 종류 차트는 저장한 설정 그대로 다시 읽히고 목록에 그 종류가 나온다 | RC-R18, RC-R19, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-048 | 그룹핑 없는 리포트의 히스토그램은 범주 null·자동 구간으로 저장된다 | RC-R18, RC-R14, RC-UC2 | backend | `application/test_saved_report_chart.py`<br>`web/test_saved_report_chart_routes.py` |
| RC-049 | 화면 규칙표는 33종·13분류 순서·분류별 하위 종류 수이고 서버 표와 같은 값이다 | RC-R1, RC-R2 | frontend | `features/reports/chart/chartKinds.test.ts` |
| RC-050 | 차트가 없을 때 타일은 그룹 수에 맞는 안내와 차트 만들기 버튼을 보인다 | RC-R24, RC-UC1 | frontend | `features/reports/designer/ReportDesignerPage.chart.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-051 | 그룹 1·2개의 기본 차트는 묶은·누적 세로 막대와 머리글 축 제목이다 | RC-R25, RC-UC1 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/chart/chartDraft.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-052 | 그룹핑 없는 기본 차트는 첫 숫자 컬럼의 히스토그램이다 | RC-R25, RC-UC1 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-053 | 차트를 만들면 설정 패널이 열리고 차트 설정·차트 삭제·다시 조회가 상태를 지킨다 | RC-R26, RC-UC1 | frontend | `features/reports/designer/ReportDesignerPage.chart.test.tsx`<br>`features/reports/designer/state/designerState.test.ts` |
| RC-054 | 종류 고르기는 13분류와 고른 분류의 하위 종류만 보이고 분류를 바꾸면 첫 쓸 수 있는 종류가 된다 | RC-R27, RC-UC1 | frontend | `features/reports/chart/KindPicker.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-055 | 그룹 수에 맞지 않는 분류·하위 종류는 이유와 함께 잠긴다 | RC-R27, RC-UC1 | frontend | `features/reports/chart/KindPicker.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-056 | 키보드로 분류와 하위 종류를 고를 수 있다 | RC-R27, RC-UC1 | frontend | `features/reports/chart/KindPicker.test.tsx` |
| RC-057 | 종류를 바꾸면 계열·값·전환·범위·보조 축을 종류에 맞게 정리한다 | RC-R28, RC-UC1 | frontend | `features/reports/chart/chartDraft.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx`<br>`features/reports/designer/state/designerState.test.ts` |
| RC-058 | 히스토그램·콤보·폭포·거품형·파레토로 바꿀 때 범주·옵션·값 개수를 정리한다 | RC-R28, RC-UC1 | frontend | `features/reports/chart/chartDraft.kinds.test.ts` |
| RC-059 | 데이터 칸은 그룹만 범주·계열로, 그룹 아닌 컬럼을 값으로 받고 범주·계열을 서로 바꾼다 | RC-R29, RC-UC1 | frontend | `features/reports/chart/ChartSettingsPanel.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-060 | 그룹핑 없는 히스토그램은 범주 칸이 잠기고 숫자 컬럼만 값 후보다 | RC-R29, RC-UC1 | frontend | `features/reports/chart/ChartSettingsPanel.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-061 | 구간 칸은 방식에 따라 칸을 잠그고 입력 글자를 보관한다 | RC-R30, RC-UC1 | frontend | `features/reports/chart/HistogramOptions.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-062 | 합계 막대 옵션은 폭포에만 있고 켜면 합계 막대가 그려진다 | RC-R30, RC-R54, RC-UC1 | frontend | `features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-063 | 콤보 계열 편집기는 값마다 종류·보조 축을 고르고 프리셋과 사용자 지정 조합을 보인다 | RC-R30, RC-UC1 | frontend | `features/reports/chart/ComboSeriesEditor.test.tsx` |
| RC-064 | 콤보 프리셋 셋은 정해진 조합이고 모든 계열을 보조 축에 두지 않는다 | RC-R30, RC-UC1 | frontend | `features/reports/chart/ComboSeriesEditor.test.tsx`<br>`features/reports/chart/build/combo.test.ts`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-065 | 제목·범례·데이터 레이블·축 제목·범위 설정이 차트 옵션에 바로 반영된다 | RC-R31, RC-R43, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-066 | 종류가 쓰지 않는 칸은 이유와 함께 잠기고 축 이름은 방향에 맞게 바뀐다 | RC-R31, RC-UC1 | frontend | `features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-067 | 화면 안내는 범주·계열·값·개수·범위를 서버와 같은 문구로 알린다 | RC-R32, RC-UC1 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/chart/chartDraft.test.ts` |
| RC-068 | 화면 안내는 그룹 수 초과·구간·숫자 아닌 값·콤보 보조 축을 알린다 | RC-R32, RC-UC1 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chartKinds.test.tsx` |
| RC-069 | 서버 차트 위반은 칸 옆에 한 번만 보이고 저장 거절 시 결과 탭의 설정 패널이 열린다 | RC-R33, RC-UC2 | frontend | `features/reports/chart/ChartSettingsPanelNotes.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx`<br>`features/reports/designer/state/issues.test.ts` |
| RC-070 | 컬럼을 지우거나 그룹핑을 바꾸면 차트 참조만 정리되고 옮긴 컬럼은 따라간다 | RC-R34, RC-UC1 | frontend | `features/reports/chart/chartDraft.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx`<br>`features/reports/designer/state/designerState.test.ts` |
| RC-071 | 요청 차트는 없는 참조를 null로, 숫자 글자를 숫자로 바꾸고 종류가 쓰는 옵션만 보낸다 | RC-R34, RC-UC2 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/chart/chartDraft.test.ts` |
| RC-072 | 저장 차트를 초안으로 옮겼다가 다시 요청으로 바꾸면 같은 값이다 | RC-R34, RC-UC3 | frontend | `features/reports/chart/chartDraft.kinds.test.ts`<br>`features/reports/chart/chartDraft.test.ts` |
| RC-073 | 미리보기는 설정 미완성·미조회·반영 전을 알리고 그린 차트 아래 안내를 보인다 | RC-R35, RC-UC1 | frontend | `features/reports/chart/ChartPreview.test.tsx`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-074 | 보기 화면은 저장 차트를 읽기 전용으로 그리고 없거나 깨진 차트는 문구로 알린다 | RC-R36, RC-R21, RC-UC3 | frontend | `features/reports/view/ReportViewPage.chart.test.tsx` |
| RC-075 | 편집 화면은 저장 차트를 같은 패널 값으로 열고 없거나 깨지면 빈 상태로 연다 | RC-R36, RC-R24, RC-UC3 | frontend | `features/reports/designer/ReportEditPage.chart.test.tsx` |
| RC-076 | 편집 화면에서 차트를 만들고 바꾸고 지운 덮어쓰기가 다시 열 때 그대로다 | RC-R38, RC-UC2 | frontend | `features/reports/designer/ReportEditPage.chart.test.tsx` |
| RC-077 | 차트 변경은 저장 안 됨과 되돌리기에 들어가고 결과 표는 그대로다 | RC-R38, RC-UC2 | frontend | `features/reports/designer/ReportEditPage.chart.test.tsx`<br>`features/reports/designer/state/designerState.test.ts` |
| RC-078 | 목록 차트 열은 종류 이름이고 차트가 없으면 대시다 | RC-R37, RC-UC3 | frontend | `features/reports/ReportsPage.chart.test.tsx` |
| RC-079 | 게이트웨이는 차트를 화면 모양으로 바꾸고 모르는 값은 malformed-response다 | RC-R39 | frontend | `gateway/http/mappers/reportChart.test.ts`<br>`gateway/http/reports.saved.test.ts` |
| RC-080 | 결과와 맞지 않는 차트 설정은 그리지 않고 편집 안내를 보인다 | RC-R40, RC-UC3 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts` |
| RC-081 | 범주는 첫 등장 순이고 값 열 또는 계열 값마다 데이터셋이 된다 | RC-R41, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts` |
| RC-082 | 행/열 전환은 범주와 데이터셋을 맞바꾼다 | RC-R41, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-083 | 앞 N자는 축·범례 이름만 자르고 툴팁·레이블은 전체 값이다 | RC-R41, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts` |
| RC-084 | 점이 1,000개를 넘으면 그리지 않고 정확히 1,000개는 그린다 | RC-R42, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-085 | 모든 차트는 크기에 맞춰 그리고 데이터 레이블은 인스턴스 플러그인과 표 서식이다 | RC-R43, RC-R35, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-086 | 금액은 원으로 그리고 금액만 올라간 값 축은 억·만으로 줄여 쓴다 | RC-R43, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-087 | 막대는 세로·가로·누적에 맞는 축과 빈 칸 0으로 그린다 | RC-R44, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-088 | 100% 누적은 범주별 비율과 0~100 축, 비율·원래 값 툴팁으로 그린다 | RC-R44, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts` |
| RC-089 | 꺾은선·영역은 표식·채움·끊김을 종류대로 그리고 점 가까이서 툴팁이 뜬다 | RC-R44, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-090 | 원형·도넛형은 범주마다 한 조각이고 툴팁 머리가 범주 이름이다 | RC-R45, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts` |
| RC-091 | 분산형은 첫 값을 x로, 나머지를 y 계열로 그리고 빈 점은 그 계열에서만 뺀다 | RC-R46, RC-UC1 | frontend | `features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts` |
| RC-092 | 거품형은 크기에 비례한 면적으로 그리고 0 이하·빈 크기를 빼고 알린다 | RC-R47, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/bubbleRadius.test.ts` |
| RC-093 | 방사형은 범주가 3개 이상일 때만 반지름 축 위에 그린다 | RC-R48, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts` |
| RC-094 | 트리맵은 두 단계(계열 있음)·한 단계로 그리고 색·글자·툴팁이 상위를 따른다 | RC-R49, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/buildTreemap.test.ts`<br>`features/reports/chart/buildTreemapSingleLevel.test.ts` |
| RC-095 | 트리맵 행은 칸마다 하나이고 0 이하·빈 칸을 빼며 빈 이름을 (없음)으로 바꾼다 | RC-R49 | frontend | `features/reports/chart/buildTreemap.test.ts`<br>`features/reports/chart/compute/treemapTree.test.ts` |
| RC-096 | 선버스트는 안쪽 상위·바깥 하위 고리이고 범례 클릭으로 숨기지 않는다 | RC-R50, RC-UC1 | frontend | `features/reports/chart/build/sunburstLegend.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/sunburstRings.test.ts` |
| RC-097 | 선버스트 고리는 상위 합과 하위 항목이 같은 합이고 0 이하·빈 칸을 뺀다 | RC-R50 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/sunburstRings.test.ts` |
| RC-098 | 히스토그램은 구간 이름과 빈도 막대로 그리고 구간 한도에 따로 안내한다 | RC-R51, RC-R42, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts` |
| RC-099 | 구간은 자동·구간 수·구간 너비 방식대로 나뉘고 경계 값은 아래 구간이다 | RC-R52 | frontend | `features/reports/chart/compute/histogramBins.test.ts` |
| RC-100 | 오버플로·언더플로 구간은 양끝에 따로 세고 구간 이름은 숫자 서식을 따른다 | RC-R52 | frontend | `features/reports/chart/compute/histogramBins.test.ts` |
| RC-101 | 파레토는 내림차순 막대와 0~100% 보조 축 누적 꺾은선이다 | RC-R53, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/paretoSeries.test.ts` |
| RC-102 | 폭포는 앞 누계에서 시작하는 증가·감소 막대이고 합계 막대는 옵션이다 | RC-R54, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/waterfallSteps.test.ts` |
| RC-103 | 깔때기는 결과 순서의 가운데 정렬 막대이고 0 이하·빈 항목을 뺀다 | RC-R55, RC-UC1 | frontend | `features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/chart/compute/funnelBars.test.ts` |
| RC-104 | 콤보는 계열마다 종류·누적 묶음·보조 축대로 그리고 꺾은선이 막대 위다 | RC-R56, RC-R22, RC-UC1 | frontend | `features/reports/chart/build/comboStack.test.ts`<br>`features/reports/chart/buildChart.test.ts`<br>`features/reports/chart/buildChartKinds.test.ts`<br>`features/reports/designer/ReportDesignerPage.chart.test.tsx` |
| RC-105 | Fake 게이트웨이는 흉내 내는 차트 규칙에서 서버와 같은 결과를 낸다 | RC-R57 | frontend | `gateway/contract/savedReports.contract.ts` |

### RC-001 종류는 33개 키이고 옛 10개 키 이름과 옵션 키 3개는 그대로다
- When 차트 종류 enum과 옵션 enum의 값을 읽는다
- Then 종류 값은 RC-R1의 33개 키 집합과 같고 `bar`·`stacked_bar`·`stacked_100_bar`·`horizontal_bar`·`line`·`area`·`pie`·`doughnut`·`scatter`·`combo`가 들어 있으며, 옵션 값은 `histogram`·`show_total`·`combo_series`다

### RC-002 종류별 규칙표가 명세 표와 같다
- When 33개 종류 각각의 규칙(그룹 최소·최대, 계열, 값 최소·최대, 전환, 축 범위, 보조 축, 100% 축, 범주 사용, 옵션)을 읽는다
- Then 모든 종류가 규칙 하나씩을 가지고 값이 RC-R2 표와 같다: 그룹 0을 허용하고 범주를 쓰지 않는 종류는 `histogram`뿐, 보조 축은 `combo`뿐, 100% 축은 5종뿐이며, 계열이 있으면 값 개수 범위는 (1, 1)이다

### RC-003 그룹핑 없는 정의에 히스토그램이 아닌 차트는 chart-needs-grouping 하나뿐이다
- Given 정의 UNG와 저장된 리포트 없음
- When `bar`·`pie`·`combo`(각각 범주 0, 값 [1])로 저장을 요청한다
- Then 각각 위반은 `["chart"]` `chart-needs-grouping` "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)" 하나뿐이고 리포트는 저장되지 않는다

### RC-004 그룹 컬럼이 3개면 히스토그램도 chart-too-many-groups 하나뿐이다
- Given 정의 DEF3
- When `bar`(범주 0, 계열 1, 값 [3])와 `histogram`(범주 null, 값 [3])으로 각각 검증한다
- Then 둘 다 위반은 `["chart"]` `chart-too-many-groups` "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다" 하나뿐이다

### RC-005 모르는 종류는 chart.kind 위반이고 종류에 따른 검사만 건너뛴다
- Given 정의 DEF2
- When `kind: "nope"`, 범주 0, 계열 1, 값 [2, 3], `swap: true`, `value_min: 5`, `legend: "left"`, 제목 101자로 검증하고, 정의 UNG에 `kind: "nope"`로도 검증한다
- Then DEF2 쪽 위반은 `["chart","kind"]` `chart-kind-invalid`, `["chart","legend"]` `chart-legend-invalid`, `["chart","title"]` `chart-text-invalid`이고 계열·값 개수·전환·범위 허용 위반은 없으며, UNG 쪽 위반은 `chart-kind-invalid` 하나뿐이다

### RC-006 그룹 수가 종류 최대를 넘으면 chart-kind-groups와 공통 문구다
- Given 정의 DEF2(그룹 2개)
- When `pie`·`scatter`·`combo`·`funnel`(범주 0, 종류에 맞는 값)로 검증한다
- Then 각각 `["chart","kind"]` `chart-kind-groups` "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다"가 있다

### RC-007 범주는 그룹 컬럼 index여야 하고 그룹 2개면 어느 쪽이든 된다
- Given 정의 DEF2
- When `stacked_bar`를 범주 0·계열 1, 범주 1·계열 0으로 검증하고, 범주 2(값 컬럼)·9(범위 밖)·"0"(문자열)·true·null로 검증한다
- Then 앞의 둘은 통과하고, 나머지는 각각 `["chart","category"]` `chart-category-invalid` "범주 열은 그룹핑한 컬럼이어야 합니다"다

### RC-008 히스토그램은 범주가 null이어야 하고 다른 종류의 null 범주는 위반이다
- Given 정의 DEF1
- When `histogram`을 범주 0·값 [1]로, `bar`를 범주 null·값 [1]로 검증한다
- Then 히스토그램은 `["chart","category"]` `chart-category-invalid` "이 차트는 범주 열을 쓰지 않습니다", 막대는 같은 위치 "범주 열은 그룹핑한 컬럼이어야 합니다"다

### RC-009 그룹 2개에서 계열을 쓰는 종류는 계열이 필수다
- Given 정의 DEF2
- When `bar`·`radar`·`treemap`·`sunburst`를 범주 0, 계열 null, 값 [2]로 검증하고, `treemap`을 정의 DEF1·계열 null로 검증한다
- Then DEF2의 넷은 `["chart","series"]` `chart-series-required` "그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요", DEF1 트리맵은 통과한다

### RC-010 계열을 쓰지 않는 종류의 계열, 범주와 같거나 그룹이 아닌 계열은 위반이다
- Given 정의 DEF2와 DEF1
- When DEF1에 `pie`·`scatter`·`waterfall`을 계열 0으로, DEF2에 `bar`를 범주 0·계열 0, 범주 0·계열 2로, DEF1에 `bar`를 범주 0·계열 1로 검증한다
- Then 앞의 셋은 `["chart","series"]` `chart-series-invalid` "이 종류는 계열 열을 쓰지 않습니다", 나머지는 같은 위치 "계열 열은 범주와 다른 그룹핑 컬럼이어야 합니다"다

### RC-011 값은 집계 컬럼 index이고 위치별 위반·중복 위반이 있으며 순서는 유지된다
- Given 정의 DEF1
- When `combo`를 값 [0, 1, 1, 9]로, `combo`를 값 [3, 1]로, `bar`를 값 "garbage"로 검증한다
- Then 첫 요청은 `["chart","values",0]` `chart-value-invalid` "값 열은 숫자(집계) 컬럼이어야 합니다", `["chart","values",2]` `chart-value-duplicate` "같은 값 열을 두 번 고를 수 없습니다", `["chart","values",3]` `chart-value-invalid`이고, 둘째는 통과해 값이 [3, 1] 순서로 남으며, 셋째는 `["chart","values"]` `chart-values-invalid` "값 열을 고르세요"다

### RC-012 값 개수는 종류 규칙을 따르고 계열이 있으면 1개다
- Given 정의 DEF1(값 후보 1·2·3)과 DEF2(값 후보 2·3·4)
- When DEF1에 `pie` 값 [1, 2], `scatter` 값 [1], `bubble` 값 [1, 2], `combo` 값 [1], `bar` 값 [], DEF2에 `bar` 계열 1·값 [2, 3]으로 검증하고, DEF1에 `scatter` 값 [1, 2]와 `bubble` 값 [1, 2, 3]으로 검증한다
- Then 앞의 여섯은 `["chart","values"]` `chart-values-count`이고 문구는 차례로 "이 차트는 값 열을 1개 골라야 합니다", "…2~10개…", "…3개…", "…2~10개…", "…1~10개…", "…1개…"이며, 마지막 둘은 통과한다

### RC-013 값이 10개를 넘으면 목록이 커도 위반은 하나다
- Given 정의 DEF1
- When `bar`를 값 11개, 그리고 값 10,000개(모두 잘못된 index)로 검증한다
- Then 각각 위반은 `["chart","values"]` `chart-values-count` "값 열은 최대 10개까지 고를 수 있습니다" 하나뿐이다(web 요청도 같은 한 건)

### RC-014 그룹핑 없는 히스토그램은 집계 없는 숫자 컬럼, 그룹 있는 히스토그램은 집계 컬럼만 값으로 받는다
- Given 정의 UNG(0 `deal.code` 글자, 1 `deal.amount` 숫자)와 DEF1
- When UNG에 `histogram` 범주 null로 값 [1], [0], [5], [0, 1]을, DEF1에 값 [1]과 [0]을 검증한다
- Then UNG 값 [1]은 통과, [0]·[5]는 `["chart","values",0]` "값 열은 숫자 컬럼이어야 합니다", [0, 1]은 그 위반과 함께 `chart-values-count` "이 차트는 값 열을 1개 골라야 합니다"이고, DEF1 값 [1]은 통과, [0](그룹 컬럼)은 "값 열은 숫자(집계) 컬럼이어야 합니다"다

### RC-015 행/열 전환은 허용 종류만, 보조 축은 콤보만이고 켜기·끄기 값이 아니면 위반이다
- Given 정의 DEF1
- When `swap: true`를 `bar`·`radar`·`stacked_100_line`과 `pie`·`scatter`·`treemap`·`combo`에, `secondary_axis: true`를 `bar`·`waterfall`에, `swap: "yes"`, `data_labels: 1`, `secondary_axis: null`을 `bar`에 각각 준다
- Then 앞 셋은 통과, `pie`·`scatter`·`treemap`·`combo`의 전환은 `["chart","swap"]` `chart-swap-invalid` "이 차트는 행/열 전환을 쓸 수 없습니다", 막대·폭포의 보조 축은 `["chart","secondary_axis"]` `chart-secondary-invalid` "보조 축은 콤보 차트에서만 쓸 수 있습니다", `swap: "yes"`는 `chart-swap-invalid`, `data_labels: 1`·`secondary_axis: null`은 `chart-flag-invalid` "켜기·끄기 값이어야 합니다"다

### RC-016 글자 칸은 앞뒤 공백을 지우고 100자까지 받는다
- Given 정의 DEF1의 `bar`
- When 제목·가로축 제목·세로축 제목 각각을 "  Vendor별  ", 100자, 앞뒤 공백 + 100자, "   ", 101자, NUL 포함 글자, 숫자 3으로 준다
- Then 앞 넷은 통과해 "Vendor별", 100자 그대로, 100자, ""로 정규화되고, 나머지는 `["chart",<키>]` `chart-text-invalid` "100자 이내 글자로 입력하세요"다

### RC-017 범례는 네 위치만 받는다
- Given 정의 DEF1의 `bar`
- When `legend`를 `top`·`right`·`bottom`·`none`, 그리고 `left`·`TOP`·null로 준다
- Then 네 값은 그대로 저장되고 나머지는 `["chart","legend"]` `chart-legend-invalid` "범례 위치는 top·right·bottom·none 중 하나입니다"다

### RC-018 축 범위는 안전한 유한 숫자이고 한쪽만 줄 수 있으며 최소가 최대보다 작아야 한다
- Given 정의 DEF1의 `bar`
- When `value_min`/`value_max`를 (−2^53+1, 2^53−1), (0.5, 1.5), (10, null), (null, 10), ("1", null), (true, null), (NaN, null), (2^53, null), (10^400 크기 정수, null), (5, 5), (6, 5)로 준다
- Then 앞 넷은 통과(정수·소수 그대로)하고, 다음 다섯은 그 키에 `chart-range-invalid` "숫자를 입력하세요"(큰 정수도 오류 없이 위반), (5, 5)·(6, 5)는 `["chart","value_max"]` `chart-range-order` "최대는 최소보다 커야 합니다"다

### RC-019 축 범위가 없는 종류는 범위를 거절하고 100% 누적은 0~100만 받는다
- Given 정의 DEF1·DEF2
- When `pie`·`doughnut`·`treemap`·`sunburst`·`funnel`에 `value_min: 0`을, `scatter`·`combo`·`radar`·`histogram`·`waterfall`에 (−1000, 1000)을, 100% 누적 5종에 (0, 100), (−1, null), (null, 101)을 준다
- Then 첫 무리는 `["chart","value_min"]` `chart-range-invalid` "이 차트는 축 범위를 쓸 수 없습니다", 둘째 무리는 통과, 100% 누적은 (0, 100)만 통과하고 나머지는 "0~100 사이로 입력하세요"다

### RC-020 구간 설정이 없는 히스토그램은 자동 구간으로 저장된다
- Given 정의 UNG
- When `histogram`(범주 null, 값 [1])을 `histogram` 키 생략, null로 각각 검증한다
- Then 정규화된 `histogram`은 둘 다 `{bin_mode: "auto", bin_count: null, bin_width: null, overflow: null, underflow: null}`이다

### RC-021 구간 수·구간 너비의 경계와 방식이 쓰지 않는 칸을 검사한다
- Given 정의 UNG의 히스토그램
- When `count` 방식에 `bin_count` 1·100·0·101·2.5·"3"·true를, `width` 방식에 `bin_width` 0.5·2^53−1·0·−1·NaN을, `auto`에 `bin_count: 3`을, `count`에 `bin_width: 5`를, `width`에 `bin_count: 5`를 준다
- Then `bin_count` 1·100, `bin_width` 0.5·2^53−1은 통과(값 유지, 쓰지 않는 칸 null)하고, 잘못된 수는 `["chart","histogram","bin_count"]` "구간 수는 1~100의 정수입니다", 잘못된 너비는 `["chart","histogram","bin_width"]` "구간 너비는 0보다 큰 숫자입니다", 쓰지 않는 칸에 값이 있으면 그 칸 위치 "이 구간 방식에서는 비워 두세요"이며 코드는 모두 `chart-histogram-invalid`다

### RC-022 구간 설정 모양·구간 방식이 틀리면 위치와 함께 거절한다
- Given 정의 UNG의 히스토그램
- When `histogram`을 [], "auto", 4키 객체, 6키 객체로, 그리고 `bin_mode` "manual"·null로 준다
- Then 모양 오류는 `["chart","histogram"]` `chart-histogram-invalid` "구간 설정 형식이 올바르지 않습니다", 방식 오류는 `["chart","histogram","bin_mode"]` "구간 방식은 auto·count·width 중 하나입니다"다

### RC-023 오버플로·언더플로는 숫자이고 둘 다면 오버플로가 커야 한다
- Given 정의 UNG의 히스토그램(auto)
- When (underflow, overflow)를 (10, 100), (null, 100), (10, null), (100, 100), (200, 100), ("x", null), (null, true)로 준다
- Then 앞 셋은 통과, (100, 100)·(200, 100)은 `["chart","histogram","overflow"]` `chart-range-order` "오버플로 구간은 언더플로 구간보다 커야 합니다", 숫자가 아닌 칸은 그 위치 `chart-histogram-invalid` "숫자를 입력하세요"다

### RC-024 합계 막대는 폭포만 켤 수 있고 켜기·끄기 값이어야 한다
- Given 정의 DEF1
- When `waterfall`에 `show_total` true·생략을, `bar`·`pareto`·`funnel`에 true를, `waterfall`에 "yes"를 준다
- Then 폭포는 true·false로 저장되고, 다른 종류의 true는 `["chart","show_total"]` `chart-option-invalid` "이 차트는 이 옵션을 쓰지 않습니다", "yes"는 `chart-flag-invalid` "켜기·끄기 값이어야 합니다"다

### RC-025 종류가 쓰지 않는 옵션은 chart-option-invalid이고 통과한 차트의 옵션은 기본값이다
- Given 정의 DEF1
- When `bar`에 `histogram` 자동 구간을, `pie`에 `combo_series` 목록을 주고, `bar`·`pie`·`scatter`·`waterfall`을 옵션 없이 검증한다
- Then 앞 둘은 `["chart","histogram"]`·`["chart","combo_series"]` `chart-option-invalid`이고, 뒤 넷의 정규화 값은 `histogram` null, `combo_series` null, `show_total` false다

### RC-026 계열 설정 없는 콤보는 첫 값 막대·나머지 꺾은선으로 채운다
- Given 정의 DEF1
- When `combo`(범주 0, 값 [1, 2, 3])를 `combo_series` 없이 `secondary_axis` true로, false로 저장한다
- Then 저장된 `combo_series`는 각각 `[{column, false}, {line, true}, {line, true}]`, `[{column, false}, {line, false}, {line, false}]`이고 `secondary_axis`는 true, false다

### RC-027 콤보 계열 설정은 값 개수만큼의 목록이고 항목 모양을 검사한다
- Given 정의 DEF1의 `combo`(값 [1, 2])
- When `combo_series`를 6종류 각각을 첫 항목에 쓴 목록, 항목 1개·3개·11개 목록, "column", `[{type: "pie", secondary: false}, …]`, `[{type: "line"}, …]`, `[{type: "line", secondary: "no"}, …]`, `[{…, extra: 1}, …]`로 준다
- Then 6종류 목록은 순서·보조 축 그대로 통과하고, 길이가 다르면(11개 포함) `["chart","combo_series"]` "계열 설정 수가 값 열 수와 같아야 합니다" 하나, 목록이 아니면 "계열 설정은 목록이어야 합니다", 항목이 틀리면 `["chart","combo_series",0]` "계열 종류와 보조 축을 확인하세요"이며 코드는 `chart-combo-invalid`다

### RC-028 콤보는 모든 계열을 보조 축에 둘 수 없고 secondary_axis는 계열과 맞아야 한다
- Given 정의 DEF1의 `combo`(값 [1, 2])
- When 계열 `[{column, true}, {line, true}]`, 계열 `[{column, false}, {line, true}]`에 `secondary_axis` false, 계열 `[{column, false}, {line, false}]`에 `secondary_axis` true, 계열 `[{column, false}, {line, true}]`에 `secondary_axis` true로 준다
- Then 첫째는 `["chart","combo_series"]` `chart-combo-secondary-all` "모든 계열을 보조 축에 둘 수 없습니다", 둘째·셋째는 `["chart","secondary_axis"]` `chart-secondary-mismatch` "보조 축 설정이 계열 설정과 맞지 않습니다", 넷째는 통과해 `secondary_axis` true로 저장된다

### RC-029 정규화한 차트는 16키를 모두 가지고 다시 검증해도 같다
- Given 정의 DEF2와 `kind`·`category`·`values`·`series`만 있는 `stacked_bar` 요청, 그리고 모든 키를 준 `combo`(DEF1)
- When 검증해 정규화 값을 만들고 그 값을 다시 검증한다
- Then 정규화 값은 16키를 모두 가지고(빠진 키는 2.2 기본값) 다시 검증한 결과가 처음과 같다

### RC-030 차트 위반은 모두 모아 422 invalid-report의 위치·코드·한국어 문구로 돌아온다
- Given 로그인한 sales, 정의 DEF2
- When `POST /reports`에 `chart: {kind: "bar", category: 9, values: [0], series: 1, legend: "left"}`를 보낸다
- Then 422, type 접미사 `invalid-report`, `detail`은 첫 위반 문구이고 `errors`는 `["chart","category"]` `chart-category-invalid`, `["chart","values",0]` `chart-value-invalid`, `["chart","legend"]` `chart-legend-invalid`를 모두 담으며 각 `message`는 한국어다. 리포트는 저장되지 않는다

### RC-031 이름 위반이 먼저이고 정의 위반이 있으면 차트 위반은 알리지 않는다
- Given 로그인한 sales
- When 이름 ""과 잘못된 차트로, 그리고 이름은 맞고 정의 컬럼 0의 필드가 없는 정의와 `kind: "nope"`·값 "garbage" 차트로 저장을 요청한다
- Then 첫 요청은 이름 오류(차트 위반 아님), 둘째는 위반 위치가 `["columns",0,"field"]`뿐이고 `chart`로 시작하는 위치가 없다

### RC-032 모양 오류는 request-validation, 값 오류는 invalid-report다
- Given 로그인한 sales, 정의 DEF2
- When `chart`에 알 수 없는 키 `colour`를 넣어, `kind`를 빼고, `chart: "bar"`로, 복제 요청에 `chart`를 넣어 보내고, `category: "0"`, `value_min: 10^400 크기 정수`로 보낸다
- Then 앞의 넷은 422 `request-validation`, 뒤의 둘은 422 `invalid-report`(각각 `["chart","category"]`, `["chart","value_min"]`)이며 500은 없다

### RC-033 차트와 함께 저장하면 정규화된 차트가 상세에 나오고 차트 없이 저장하면 null이다
- Given 로그인한 sales, 정의 DEF2
- When 제목 "  Vendor별 분기 Pipeline  "인 `stacked_bar`(범주 0, 계열 1, 값 [2])로 저장하고 상세를 읽은 뒤, 다른 이름으로 `chart` 생략·null로 각각 저장한다
- Then 첫 저장은 201이고 상세 `chart`는 제목이 공백 없이 "Vendor별 분기 Pipeline"인 16키 값, `chart_problem` null, `chart_kind` "stacked_bar"이며, 나머지는 `chart`·`chart_problem`·`chart_kind`가 모두 null이다

### RC-034 위반 차트가 있는 저장은 아무것도 저장하지 않는다
- Given 정의 DEF2, 저장된 리포트 없음
- When 범주가 값 컬럼(2)인 `bar`로 저장을 요청한다
- Then `["chart","category"]` `chart-category-invalid`와 `["chart","series"]` `chart-series-required` 위반으로 거절되고 저장된 리포트가 없으며 커밋이 없다

### RC-035 덮어쓰기는 차트를 바꾸거나 지우고 revision을 올리며 SQL은 그대로다
- Given ALICE의 리포트(정의 DEF2, `bar` 차트, revision 1)
- When ALICE가 같은 정의에 `stacked_bar` 차트로 revision 1 덮어쓰기를 하고, 이어서 `chart` 생략으로 revision 2 덮어쓰기를 한다
- Then 첫 결과는 `chart` = 새 `stacked_bar`, revision 2, `updated_by` ALICE, `updated_at` 덮어쓴 시각, `generated_sql`은 전과 같고, 둘째 결과는 `chart` null·`chart_kind` null·revision 3이며 목록 `chart_kind`도 null이다

### RC-036 정의를 바꿔 이전 차트가 맞지 않는 덮어쓰기는 거절되고 저장 내용은 그대로다
- Given ALICE의 리포트(정의 DEF2, `stacked_bar` 범주 0·계열 1·값 [2], revision 1)
- When 그룹핑을 끈 정의 UNG에 같은 차트로, 그리고 값 컬럼이 index 2 하나뿐인 정의에 값 [4] 차트로 덮어쓰기를 요청한다
- Then 첫 요청은 `["chart"]` `chart-needs-grouping`, 둘째는 `["chart","values",0]` `chart-value-invalid`로 거절되고 저장된 정의·차트·revision 1은 그대로이며 커밋이 없다

### RC-037 목록 항목은 차트 종류만 보이고 차트 본문은 없다
- Given 리포트 "차트 있음"(`stacked_bar`)과 "차트 없음"
- When 목록을 읽는다
- Then "차트 있음"의 `chart_kind`는 "stacked_bar", "차트 없음"은 null이고 어느 항목에도 `chart` 키가 없다

### RC-038 복제는 원본 차트를 다시 검증해 가져가고 깨진 차트는 버린다
- Given ALICE의 원본 리포트 셋: A(정의 DEF2, 제목 "제목"·범례 bottom인 `stacked_bar`), B(차트 없음), C(저장 차트를 읽을 수 없음), D(DB에 직접 넣은 범주가 값 컬럼 2인 `bar`)
- When BOB(user)이 A·B·C를 복제하고, ALICE가 D를 복제한다
- Then A 복사본은 201이고 `chart`가 원본과 같으며 `chart_kind` "stacked_bar"·`chart_problem` null이고 원본도 그대로다. B 복사본 `chart` null, C 복사본은 `chart` null·`chart_problem` null로 만들어진다. D는 `["chart","category"]` `chart-category-invalid` 422이고 복사본이 생기지 않는다

### RC-039 저장 차트 JSON이 읽기 규칙에 어긋나면 stored-invalid다
- When 저장 차트 JSON으로 `[1]`, `"bar"`, `kind` 없는 객체, `kind` "nope", `legend` "left", `category` "0", `values` [1.5], `series` "1", `title` 3, `swap` "yes", `show_total` 1, `value_min` "1", `histogram` 4키, `histogram.bin_mode` "manual", `histogram.bin_count` 2.5, `combo_series` [{type: "pie", secondary: false}]를 각각 읽는다
- Then 모두 `["chart"]` `stored-invalid` "저장된 차트 설정을 읽을 수 없습니다." 위반이다

### RC-040 깨진 저장 차트의 리포트는 차트 없이 안내와 함께 열리고 목록·실행은 된다
- Given ALICE의 리포트(정의 DEF2)의 DB `chart`가 `[1]`이고, 다른 리포트의 `chart` kind가 33개 키에 없는 값
- When ALICE가 목록·상세·실행을 요청한다
- Then 목록 200이고 두 리포트 `chart_kind` null, 상세 200 `chart` null·`chart_problem` "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."·revision 1, 실행 200이고 결과는 차트 없는 같은 정의 리포트의 실행과 같다

### RC-041 깨진 저장 차트는 덮어쓰기로 복구되고 리포트를 삭제할 수 있다
- Given ALICE의 리포트 둘의 저장 차트를 읽을 수 없음(revision 1)
- When 하나는 `combo` 차트로, 다른 하나는 차트 없이 revision 1 덮어쓰기를 하고, 세 번째 깨진 차트 리포트를 삭제한다
- Then 첫째는 200 `chart` = 새 콤보·`chart_problem` null·revision 2, 둘째는 `chart`·`chart_problem` null·revision 2이고 두 리포트 모두 "읽을 수 없음"이 아니며, 삭제는 성공하고 리포트가 사라진다

### RC-042 저장 차트를 읽을 때는 정의와 맞는지 보지 않는다
- Given 정의 UNG인 리포트의 DB `chart`가 `bar`(범주 0, 계열 1, 값 [7])
- When 상세를 읽는다
- Then 200이고 `chart`는 그 값 그대로, `chart_problem`은 null이다(화면이 RC-080으로 알린다)

### RC-043 옛 13키 저장 차트는 새 키 기본값으로 읽힌다
- Given DB `chart` = `histogram`·`show_total`·`combo_series`가 없는 13키 `bar`, 그리고 `kind`·`category`·`values`만 있는 `bar`
- When 상세를 읽는다
- Then `chart_problem` null이고 첫째는 저장 값 + `histogram` null·`show_total` false·`combo_series` null, 둘째는 `series` null·`swap` false·`title` ""·`legend` "top"·축 제목 ""·범위 null·`secondary_axis` false와 새 키 기본값이다

### RC-044 옛 콤보 저장 차트는 첫 값 막대·나머지 꺾은선으로, 보조 축이면 꺾은선이 보조 축으로 읽힌다
- Given 정의 DEF1인 리포트의 DB `chart` = 13키 `combo`(값 [1, 2, 3]), `secondary_axis` false인 것과 true인 것, 그리고 `combo_series: null`인 콤보
- When 상세를 읽는다
- Then `chart_problem` null이고 `combo_series`는 `[{column, false}, {line, s}, {line, s}]`(s = 저장된 `secondary_axis`)이며 `combo_series: null`도 같은 규칙으로 채워진다

### RC-045 구간 없는 저장 히스토그램은 자동 구간으로 읽히고 저장된 옵션 값은 그대로다
- Given DB `chart` = `histogram` 키 없는 히스토그램, `histogram: null`인 히스토그램, `count`·12구간 히스토그램, `show_total: true`인 폭포, 저장된 `combo_series`가 있는 콤보, `category: null`인 `bar`
- When 각각 읽는다
- Then 앞 둘은 자동 구간, 나머지는 저장 값 그대로이고 `category: null`도 깨진 차트가 아니다(콤보가 아닌 종류의 `combo_series`는 null)

### RC-046 openapi의 차트 요청·응답 스키마가 명세와 같다
- When `backend/openapi.json`의 저장 리포트 경로 스키마를 읽는다
- Then RC-R23과 같다: POST·PUT 요청 `chart`는 선택·nullable `ReportChartRequest`(16키, 추가 키 금지, `category` nullable), 복제 요청에 `chart` 없음, 상세 응답(GET·POST·PUT·복제)은 `chart`·`chart_problem`·`chart_kind`, `ReportChartResponse`는 16키 필수·`kind` 33값·`category` nullable·`histogram` 5키·`combo_series` 항목 `type`·`secondary`·`show_total` 필수 bool, 목록 항목은 `chart_kind`만, 실행·조회 스키마에 차트가 없다

### RC-047 새 종류 차트는 저장한 설정 그대로 다시 읽히고 목록에 그 종류가 나온다
- Given 로그인한 sales
- When 정의 DEF2에 `stacked_horizontal_bar`(계열 1, 값 [2])·`treemap`(계열 1, 값 [2])을, DEF1에 `bubble`(값 [1, 2, 3])·`waterfall`(값 [1], `show_total` true)·`combo`(값 [1, 2], 계열 `[{stacked_area, false}, {line_markers, true}]`, `secondary_axis` true)를 각각 저장하고 상세·목록을 읽는다
- Then 각각 201이고 상세 `chart`는 보낸 16키 값과 같으며 목록 `chart_kind`는 그 종류다

### RC-048 그룹핑 없는 리포트의 히스토그램은 범주 null·자동 구간으로 저장된다
- Given 로그인한 sales, 정의 UNG
- When `histogram`(범주 null, 값 [1], 구간 생략)으로 저장하고, 이어서 `bin_mode` count·`bin_count` 101로 저장을 요청한다
- Then 첫 저장은 201, `chart.category` null, `chart.histogram`은 자동 구간, `chart_kind` "histogram"이고, 둘째는 422 `invalid-report` `["chart","histogram","bin_count"]`이며 저장되지 않는다

### RC-049 화면 규칙표는 33종·13분류 순서·분류별 하위 종류 수이고 서버 표와 같은 값이다
- When 화면 규칙표(`CHART_KINDS`)와 분류 목록(`CHART_FAMILIES`)을 읽는다
- Then 종류 키는 33개이고 각 종류가 아는 분류에 속하며, 분류는 세로 막대형·가로 막대형·꺾은선형·원형·영역형·분산형(X, Y) 또는 거품형·방사형·트리맵·선버스트·히스토그램·폭포·깔때기·콤보 순서, 하위 종류 수는 3·3·6·2·3·6·3·1·1·2·1·1·1이며, 각 종류의 그룹 수·계열·값 개수·전환·축 범위·보조 축·100%·범주·옵션이 RC-R2와 같고 값 최대 10·점 한도 1,000이다. 축 계열 빌더를 쓰는 종류는 세로 막대·가로 막대·꺾은선·영역 분류뿐이다

### RC-050 차트가 없을 때 타일은 그룹 수에 맞는 안내와 차트 만들기 버튼을 보인다
- Given 디자이너에서 조회한 결과 탭
- When 그룹 1개, 그룹 0개 + 금액 컬럼, 그룹 0개 + 글자 컬럼만, 그룹 3개인 설계를 각각 조회한다
- Then 차례로 "그룹핑 컬럼은 범주(와 계열)로, 나머지 컬럼은 값으로 차트를 그립니다."와 활성 버튼, "그룹핑이 없으면 히스토그램만 만들 수 있습니다"와 활성 버튼, "그룹핑한 결과로 차트를 만들 수 있습니다"와 비활성 버튼, "차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다"와 비활성 버튼이 보인다

### RC-051 그룹 1·2개의 기본 차트는 묶은·누적 세로 막대와 머리글 축 제목이다
- Given 컬럼 Vendor(그룹)·금액 합계·건수인 설계, Vendor·분기(그룹)·금액 합계인 설계, Vendor(그룹)만 있는 설계
- When 각각 기본 차트를 만든다
- Then 첫째는 `bar`·범주 Vendor·값 [금액 합계]·가로축 제목 "Vendor"·세로축 제목 = 금액 합계 머리글·제목 ""·범례 위·데이터 레이블 끔, 둘째는 `stacked_bar`·범주 Vendor·계열 분기·값 [금액 합계], 셋째는 값 []·세로축 제목 ""이다(설계에 컬럼이 없으면 기본 차트가 없다)

### RC-052 그룹핑 없는 기본 차트는 첫 숫자 컬럼의 히스토그램이다
- Given 컬럼 Deal 코드(글자)·금액(숫자)·사용자 수(숫자)인 그룹 없는 설계
- When 기본 차트를 만들고, 숫자 필드 판정 없이, 글자 컬럼만 있는 설계로도 만든다
- Then 첫째는 `histogram`·범주·계열 null·값 [금액]·가로축 제목 "금액"·세로축 제목 "빈도"·자동 구간이고, 나머지 둘은 기본 차트가 없다

### RC-053 차트를 만들면 설정 패널이 열리고 차트 설정·차트 삭제·다시 조회가 상태를 지킨다
- Given 디자이너에서 그룹 1개 설계를 조회한 결과 탭(차트 없음)
- When "차트 만들기"를 누르고, "차트 설정"으로 패널을 닫았다 열고, 다시 조회하고, "차트 삭제"를 누른다
- Then 만들면 차트와 설정 패널이 보이고, 버튼으로 패널이 닫히고 열리며, 다시 조회해도 결과 탭·차트·열린 패널이 남고, 삭제하면 빈 상태(RC-R24)로 돌아간다. 보기 방식 "표만"이면 차트 타일과 그림이 없다(배치 규칙은 RS-R37)

### RC-054 종류 고르기는 13분류와 고른 분류의 하위 종류만 보이고 분류를 바꾸면 첫 쓸 수 있는 종류가 된다
- Given 그룹 1개 결과의 `line` 차트 패널
- When 분류·하위 종류 목록을 보고, "표식이 있는 꺾은선"을 누르고, 분류 "세로 막대형"을 고른다
- Then "차트 분류"는 13개(RC-R1 순서)이고 "꺾은선형"이 선택, "하위 종류"는 꺾은선형 6개뿐이며 "꺾은선"이 눌림 상태다. 누르면 `line_markers`, 분류를 바꾸면 `bar`가 된다. 한 종류뿐인 분류(트리맵)는 하위 종류 버튼이 하나다

### RC-055 그룹 수에 맞지 않는 분류·하위 종류는 이유와 함께 잠긴다
- Given 차트 패널
- When 그룹 2개, 그룹 1개, 그룹 0개 결과에서 분류·하위 종류를 본다
- Then 그룹 2개면 원형·분산형·폭포·깔때기·콤보 분류가 잠기고 title "그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다", 히스토그램 분류는 열리되 하위 "파레토"만 잠긴다. 그룹 1개면 모두 열린다. 그룹 0개면 히스토그램 분류만 열리고 나머지 분류·"파레토"는 title "그룹핑한 결과로 만들 수 있습니다"이며, 잠긴 분류를 눌러도 종류가 바뀌지 않는다

### RC-056 키보드로 분류와 하위 종류를 고를 수 있다
- Given 그룹 1개 결과의 `bar` 차트 패널
- When 분류 라디오에서 아래 화살표를 누르고, Tab으로 하위 종류 버튼에 가서 Enter, 다른 버튼에서 Space를 누른다
- Then 화살표로 "가로 막대형"이 선택되어 `horizontal_bar`가 되고, Enter·Space로 그 버튼의 종류가 된다

### RC-057 종류를 바꾸면 계열·값·전환·범위·보조 축을 종류에 맞게 정리한다
- Given 그룹 1개(Vendor) 결과의 `bar`(값 금액 합계·건수·사용자 수, 전환 켬, 범위 0~100)와 그룹 2개 결과의 `bar`(범주 Vendor, 계열 없음, 값 1개)
- When 첫째를 `pie`, `scatter`, `combo`로, 둘째를 `stacked_bar`로, 계열이 있는 `stacked_bar`를 `pie`로 바꾼다
- Then `pie`는 값 1개·전환 끔·범위 비움·계열 칸 비활성, `scatter`는 값 유지(최대 10)·범위 유지·전환·보조 축 끔, `combo`는 값 유지·전환 끔, `stacked_bar`는 남은 그룹 분기가 계열로 채워지고, 계열 있던 차트는 `pie`에서 계열이 비워진다

### RC-058 히스토그램·콤보·폭포·거품형·파레토로 바꿀 때 범주·옵션·값 개수를 정리한다
- Given 그룹 1개 결과의 `bar`(값 3개, 합계 켬 상태로 남은 폭포 이력 없음)
- When `histogram`으로 바꿨다가 다시 `bar`로, `combo`로, `waterfall`(합계 켬) 뒤 `bar`로, `bubble`로, `pareto`로 바꾼다
- Then 히스토그램은 범주·계열 null·값 1개, `bar`로 돌아오면 범주 = 첫 그룹, 콤보는 값마다 계열(첫 묶은 세로 막대·나머지 꺾은선, 이미 고른 설정은 값 컬럼 uid로 유지), 폭포에서 `bar`로 가면 합계가 꺼지고 폭포로 돌아가면 다시 끈 채, 거품형은 값 3개까지, 파레토는 1개까지 남는다

### RC-059 데이터 칸은 그룹만 범주·계열로, 그룹 아닌 컬럼을 값으로 받고 범주·계열을 서로 바꾼다
- Given 그룹 2개(Vendor·분기)·금액 합계·건수 결과의 `stacked_bar`(범주 Vendor, 계열 분기, 값 금액 합계)
- When 범주·계열·값 선택지를 보고, 범주로 분기를 고르고, 그룹 1개 결과의 `bar`에서 건수를 더 체크한다
- Then 범주·계열 선택지는 Vendor·분기, 값은 금액 합계·건수이고, 범주에 분기를 고르면 범주 분기·계열 Vendor로 바뀌며, 건수를 체크하면 데이터셋이 머리글 이름 둘(금액 합계·건수)이 된다. 계열이 있을 때 값 최대는 1이라 다른 값을 체크하면 그 값으로 바뀐다

### RC-060 그룹핑 없는 히스토그램은 범주 칸이 잠기고 숫자 컬럼만 값 후보다
- Given 그룹 없는 결과(Deal 코드·금액)의 히스토그램 패널, 그리고 같은 컬럼의 `bar` 패널(그룹 1개 추가)
- When 범주 칸과 값 후보를 본다
- Then 히스토그램은 범주가 비활성 "(없음)"이고 title·안내 "이 차트는 범주 열을 쓰지 않습니다", 값 후보는 금액뿐이다. `bar`는 그룹 아닌 컬럼 모두가 후보다. 후보가 없으면 "값으로 쓸 숫자 컬럼이 없습니다"

### RC-061 구간 칸은 방식에 따라 칸을 잠그고 입력 글자를 보관한다
- Given 히스토그램 패널의 구간(자동)
- When 칸을 보고, 방식을 "구간 수"로 바꿔 "12"를 쓰고, "구간 너비"로 바꿔 "5"를 쓰고 다시 "구간 수"로 바꾼다
- Then 자동에서는 "구간 수"·"구간 너비"가 비활성이고 각각 title "구간 방식이 구간 수일 때 쓸 수 있습니다"·"…구간 너비일 때…", 방식 선택지는 자동·구간 수·구간 너비다. 구간 수 방식에서는 수 칸만, 너비 방식에서는 너비 칸만 활성이고, 쓴 글자는 그대로 보고되며 방식을 바꿔도 "12"·"5"가 지워지지 않는다. 구간 수 12로 바꾸면 미리보기 구간이 12개로 다시 그려진다

### RC-062 합계 막대 옵션은 폭포에만 있고 켜면 합계 막대가 그려진다
- Given 그룹 1개 결과의 차트 패널
- When `waterfall`에서 "마지막에 합계 막대"를 켜고, `bar`·`funnel` 패널을 본다
- Then 폭포에는 "폭포" 묶음과 체크박스가 있고 켜면 미리보기 마지막 범주가 "합계"인 막대가 생기며, 다른 종류에는 그 옵션이 없다

### RC-063 콤보 계열 편집기는 값마다 종류·보조 축을 고르고 프리셋과 사용자 지정 조합을 보인다
- Given 값 금액 합계·건수·사용자 수인 `combo` 패널(기본 계열)
- When 계열 줄을 보고, 프리셋 "묶은 세로 막대 - 보조 축의 꺾은선"을 고르고, 건수 줄의 종류를 "영역"으로 바꾼다
- Then 줄마다 머리글·"<머리글> 종류"(6종)·"<머리글> 보조 축"이 있고 프리셋은 "묶은 세로 막대 - 꺾은선"으로 보인다. 프리셋을 고르면 건수·사용자 수가 꺾은선·보조 축이 되어 미리보기의 두 데이터셋이 오른쪽 축 y1을 쓰고, 한 줄만 바꾸면 그 줄만 바뀌고 프리셋이 "사용자 지정 조합"이 된다. 위반 문구가 있으면 표 아래에 보인다

### RC-064 콤보 프리셋 셋은 정해진 조합이고 모든 계열을 보조 축에 두지 않는다
- When 프리셋 목록과 값 2·3·10개에 대한 각 프리셋의 계열을 만든다
- Then 프리셋은 "묶은 세로 막대 - 꺾은선"·"묶은 세로 막대 - 보조 축의 꺾은선"·"누적 영역 - 묶은 세로 막대" 셋이고, 각각 RC-R30의 조합이며 어느 것도 모든 계열이 보조 축이 아니고, 만든 계열은 그 프리셋으로 다시 알아보며 그 밖 조합은 `custom`이다

### RC-065 제목·범례·데이터 레이블·축 제목·범위 설정이 차트 옵션에 바로 반영된다
- Given 그룹 1개 결과의 `bar` 미리보기
- When 차트 제목 "분기 실적", 범례 "숨김", 데이터 레이블 켬, 가로축 제목 "업체"·세로축 제목 "금액", 세로축 최소 "0"·최대 "500"을 입력한 뒤 범위 칸을 비운다
- Then 차트 옵션의 제목 표시·글자, 범례 `display: false`, `datalabels.display: true`, x·y 축 제목, y `min` 0·`max` 500이 차례로 반영되고, 칸을 비우면 `min`·`max` 키가 없어진다

### RC-066 종류가 쓰지 않는 칸은 이유와 함께 잠기고 축 이름은 방향에 맞게 바뀐다
- Given 그룹 1개 결과의 차트 패널
- When 종류를 `pie`, `radar`, `treemap`, `funnel`, `horizontal_bar`, `stacked_100_bar`, `bar`로 바꿔 축 칸을 본다
- Then `pie`·`treemap`은 축 제목 둘이 "이 종류는 축이 없습니다"로, 범위가 "이 종류는 축 범위를 쓸 수 없습니다"로 잠기고 트리맵은 데이터 레이블도 "트리맵은 이름과 값을 항상 보입니다"로 잠긴다. `radar`는 축 제목이 잠기고 범위 칸 이름이 "반지름 축 최소"·"…최대", `funnel`은 "가로축 제목(값)"이 "깔때기는 값 축을 보이지 않습니다"로 잠기고 범위가 잠기며, `horizontal_bar`는 "세로축 제목(범주)"·"가로축 제목(값)"·"가로축 최소", `stacked_100_bar`는 안내 "100% 누적은 0~100 사이로 입력하세요"가 있다. 콤보가 아니면 "보조 축"이 "보조 축은 콤보 차트에서만 쓸 수 있습니다"로 잠긴다

### RC-067 화면 안내는 범주·계열·값·개수·범위를 서버와 같은 문구로 알린다
- Given 그룹 2개 설계의 `stacked_bar` 초안
- When 완성된 초안, 범주 없음, 계열 없음, 값 없음, `pie`에 값 2개(그룹 1개), 범위 "abc"·"x", 범위 "10"·"5"로 안내를 만든다
- Then 완성된 초안은 안내 없음, 나머지는 차례로 part `category` "범주 열을 고르세요", `series` "그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요", `values` "값 열을 고르세요", `values` "이 차트는 값 열을 1개 골라야 합니다", `value_min`·`value_max` "숫자를 입력하세요", `value_max` "최대는 최소보다 커야 합니다"다

### RC-068 화면 안내는 그룹 수 초과·구간·숫자 아닌 값·콤보 보조 축을 알린다
- Given 차트 초안
- When 그룹 2개에서 `pie`, 그룹 3개에서 `bar`, 그룹 1개에서 `bar`, 그룹 없는 완성 히스토그램, 구간 수 "1"·"100"·"0", 너비 방식 너비 "0"·"−1"·"", 자동 방식에 수 "abc", 언더플로 "10"·오버플로 "5", 글자 컬럼을 고른 그룹 없는 히스토그램, 모든 계열이 보조 축인 콤보, 값 1개인 `scatter`·2개인 `bubble`로 안내를 만든다
- Then `pie`는 part `category` "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다", 그룹 3개 `bar`는 "…2개 이하…", 그룹 1개 `bar`와 완성 히스토그램(범주 요구 없음)·구간 수 1·100·자동 방식의 수 칸은 안내 없음, 수 0은 `histogram.bin_count` "구간 수는 1~100의 정수입니다", 너비는 `histogram.bin_width` "구간 너비는 0보다 큰 숫자입니다", 순서는 `histogram.overflow` "오버플로 구간은 언더플로 구간보다 커야 합니다", 글자 컬럼은 `values` "값 열은 숫자 컬럼이어야 합니다", 콤보는 `combo_series` "모든 계열을 보조 축에 둘 수 없습니다", 분산형·거품형은 `values` 개수 문구다

### RC-069 서버 차트 위반은 칸 옆에 한 번만 보이고 저장 거절 시 결과 탭의 설정 패널이 열린다
- Given 디자이너 작성 탭, 서버가 `["chart","category"]` "범주 열은 그룹핑한 컬럼이어야 합니다"와 `["chart","kind"]` "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다"로 저장을 거절함
- When 저장한다
- Then 결과 탭으로 옮겨 설정 패널이 열리고, 범주 칸 옆에 서버 문구가 보이며(`aria-invalid`), 화면 안내와 같은 그룹 수 문구는 한 번만, 다른 문구는 패널 위쪽에 보인다. 위치 `["chart","histogram","bin_count"]`는 구간 수 칸, `["chart","values",0]`은 값 칸에 붙는다

### RC-070 컬럼을 지우거나 그룹핑을 바꾸면 차트 참조만 정리되고 옮긴 컬럼은 따라간다
- Given 범주 Vendor·계열 분기·값 금액 합계·제목 "T"인 초안
- When 금액 합계를 지우고, Vendor의 그룹핑을 끄고, 분기의 그룹핑을 끄고, 건수를 그룹으로 바꾸고, Vendor를 맨 뒤로 옮긴 뒤 요청 차트를 만든다
- Then 지운 값은 값에서 빠지고 제목 등은 그대로, 그룹을 끈 범주·계열은 비워지며, 그룹이 된 값은 빠지고, 옮긴 Vendor는 요청 `category`가 새 index가 된다. 범주 컬럼을 지운 화면에는 "설정을 완성하면 차트가 그려집니다"가 보이고 나머지 설정은 남는다

### RC-071 요청 차트는 없는 참조를 null로, 숫자 글자를 숫자로 바꾸고 종류가 쓰는 옵션만 보낸다
- Given 초안들: 범주 컬럼이 결과에 없는 `bar`, 범위 "−5"·"", "1e3"·"abc"인 `bar`, 구간 count "12"·너비 글자 "7"인 히스토그램, 합계 켠 상태의 `bar`, 값 금액 합계·건수와 건수만 보조 축인 콤보, 계열 설정이 빠진 콤보
- When 요청 차트로 바꾼다
- Then 각각 `category` null, `valueMin` −5·`valueMax` null 및 1000·"abc", `histogram` `{binMode: count, binCount: 12, binWidth: null, …}`, `showTotal` false·`histogram` null·`comboSeries` null, `comboSeries` 값 순서 `[{column, false}, {line, true}]`·`secondaryAxis` true, 빠진 설정은 첫 묶은 세로 막대·나머지 꺾은선이다. 글자·켜기끄기 칸은 그대로 보낸다

### RC-072 저장 차트를 초안으로 옮겼다가 다시 요청으로 바꾸면 같은 값이다
- Given 저장 차트들: 범위 null·최소 −5인 `stacked_bar`, 구간 width 2.5·오버플로 100인 히스토그램, 값 [2, 3] 계열 설정이 있는 콤보, 합계 켠 폭포, 값 index에 범위 밖 9가 있는 `bar`, null
- When 초안으로 옮긴 뒤 같은 컬럼으로 요청 차트를 만든다
- Then 앞 넷은 처음 값과 같고(콤보 계열은 값 컬럼 uid 키로 보관), 범위 밖 9는 참조 없음으로 빠지며, null은 초안이 없다

### RC-073 미리보기는 설정 미완성·미조회·반영 전을 알리고 그린 차트 아래 안내를 보인다
- Given 디자이너 결과 탭의 차트
- When 값이 없는 초안, 조회 전, 새로 넣은 컬럼을 값으로 고른 채 조회 전, 완성·조회된 거품형(크기 0인 점 1개), 행 한도로 잘린 결과, 잘리지 않은 결과를 본다
- Then 차례로 "설정을 완성하면 차트가 그려집니다", "조회하면 차트가 그려집니다", "조회하면 차트에 반영됩니다", 그림 아래 "크기가 0 이하이거나 빈 값인 점 1개는 그리지 않았습니다", "최대 행 수 제한으로 표시된 행만 차트에 그렸습니다"가 보이고, 마지막은 안내가 없다. 그림의 접근성 이름은 "… 차트: Vendor 기준 금액 합계. 같은 값이 결과 표에 있습니다"처럼 결과 표를 가리킨다

### RC-074 보기 화면은 저장 차트를 읽기 전용으로 그리고 없거나 깨진 차트는 문구로 알린다
- Given 보기 화면, 차트 있는 리포트·차트 없는 리포트·`chart_problem`이 있는 리포트·정의와 맞지 않는 차트의 리포트
- When 각각 연다
- Then 차트 있는 리포트는 표 타일과 차트 타일이 있고 설정 패널·"차트 설정"이 없이 그림이 보인다. 깨진 리포트의 차트 타일에는 "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.", 맞지 않는 차트는 "차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요"가 보인다(차트 없는 리포트의 보기 방식·타일은 RS-R37, RS-093)

### RC-075 편집 화면은 저장 차트를 같은 패널 값으로 열고 없거나 깨지면 빈 상태로 연다
- Given 편집 화면, 콤보·구간 있는 차트가 저장된 리포트, 차트 없는 리포트, `chart_problem` 리포트
- When 각각 열어 차트 타일을 본다
- Then 첫째는 종류·범주·값·계열 설정·제목이 저장 값과 같은 패널과 같은 차트 옵션, 둘째는 "차트 만들기", 셋째는 "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."와 "차트 만들기"다

### RC-076 편집 화면에서 차트를 만들고 바꾸고 지운 덮어쓰기가 다시 열 때 그대로다
- Given ALICE의 차트 없는 리포트 편집 화면(Fake 게이트웨이)
- When 차트를 만들어 제목 "  분기  "로 덮어쓰고 다시 열고, 제목만 바꿔 덮어쓰고, "차트 삭제" 뒤 덮어쓴다
- Then 다시 열면 같은 설정(제목은 "분기")이고, 제목만 바꾼 덮어쓰기 뒤에도 차트가 남으며, 삭제 뒤 덮어쓰기는 요청 `chart` null이고 다시 열면 "차트 만들기"다

### RC-077 차트 변경은 저장 안 됨과 되돌리기에 들어가고 결과 표는 그대로다
- Given 차트가 저장된 리포트의 편집 화면(저장 안 됨 없음, 결과 표 있음)
- When 차트를 바꾸고, 원래 값으로 되돌려 놓고, 차트를 지우고, 되돌리기를 누르고, 차트 없는 리포트에서 차트를 만들었다 지우고, 조회 설계와 차트를 함께 바꾼 뒤 되돌리기를 누른다
- Then 바꾸면 저장 안 됨 표시와 떠날 때 확인이 생기고 결과 표는 그대로이며, 원래 값이면 표시가 사라지고, 지우면 다시 생기고, 되돌리기는 저장 차트를 되살리며 결과 표를 유지한다. 만들었다 지우면 저장 안 됨이 아니고, 설계도 바꾼 되돌리기는 차트와 설계를 되살리고 결과를 지운다. 덮어쓴 뒤 제목 앞뒤 공백을 지운 서버 값이 기준선이라 나중 변경을 되돌리면 저장 안 됨이 아니다

### RC-078 목록 차트 열은 종류 이름이고 차트가 없으면 대시다
- Given 목록, `bar` 리포트·`stacked_bar` 리포트·차트 없는 리포트, 그리고 33종 각각의 리포트
- When 목록을 본다
- Then "차트" 열은 "데이터" 바로 다음·"만든 사람" 바로 앞이고 값은 "묶은 세로 막대"·"누적 세로 막대"·"—"이며, 33종은 RC-R1의 화면 이름이다

### RC-079 게이트웨이는 차트를 화면 모양으로 바꾸고 모르는 값은 malformed-response다
- Given HTTP 게이트웨이와 서버 응답 스텁
- When 차트 있는 상세·`chart_problem` 있는 상세·범위와 계열이 null인 차트·목록 `chart_kind`를 읽고, 모르는 `kind`(상세·목록)·`legend`·`bin_mode`·콤보 `type`을 읽고, 차트 있는·없는·불완전한 차트로 저장·덮어쓰기·복제를 보낸다
- Then 앞 넷은 camelCase 차트·`chartProblem` 문구·null 유지·`chartKind`로 바뀌고, 모르는 값은 `malformed-response`(502) 오류다. 요청은 16키 snake_case(없으면 `chart: null`, 불완전한 값 그대로)이고 복제 본문에는 차트가 없으며, 422의 차트 위치 오류는 `reportErrors`로 옮겨진다

### RC-080 결과와 맞지 않는 차트 설정은 그리지 않고 편집 안내를 보인다
- Given 결과 열 0·1 그룹, 2 금액 합계
- When 범주 2, 범주 9, 값 [1](그룹 열), 그룹 2개 결과의 `pie`, 계열 1인 `funnel`, 그룹 3개 결과의 `bar`, 범주가 있는 히스토그램을 그리고, 그룹 1개 결과의 `pie`를 그린다
- Then 앞의 일곱은 `{problem: "차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요"}`이고 마지막은 그린다

### RC-081 범주는 첫 등장 순이고 값 열 또는 계열 값마다 데이터셋이 된다
- Given 결과 행 (SAP, Q2, 10), (Okta, Q1, 20), (SAP, Q1, 30), (null, Q1, 5)
- When `bar`(범주 0, 값 [2])와 `stacked_bar`(범주 0, 계열 1, 값 [2]), `line`(범주 0, 계열 1)을 그린다
- Then 범주 이름은 "SAP", "Okta", "(없음)" 순, `bar`는 데이터셋 하나(이름 = 금액 합계 머리글), `stacked_bar`는 Q2·Q1 데이터셋이고 Q2의 Okta·(없음) 칸은 0, `line`은 그 칸이 null이다. 범주 이름은 결과 표 칸과 같은 서식이다

### RC-082 행/열 전환은 범주와 데이터셋을 맞바꾼다
- Given RC-081 결과의 `stacked_bar`(범주 0, 계열 1)
- When `swap: true`로 그린다
- Then 가로 항목은 Q2·Q1, 데이터셋은 SAP·Okta·(없음)이고 각 칸 값은 전환 전 같은 (범주, 계열) 칸 값이다

### RC-083 앞 N자는 축·범례 이름만 자르고 툴팁·레이블은 전체 값이다
- Given 범주 열 앞 3자, 계열 열 앞 2자 설정인 결과(범주 "Microsoft"·"Microchip", 계열 "Quarter1")
- When 막대·원형·분산형을 그리고 툴팁·레이블 글자를 만든다
- Then 축 이름 "Mic"이 원래 값마다 하나씩 두 칸이고 범례는 "Qu", 툴팁 제목은 "Microsoft", 툴팁 계열 이름은 "Quarter1", 원형 툴팁 머리는 전체 범주 이름, 분산형 점 이름은 전체 값이며, 값 열에 앞 N자가 있어도 데이터 레이블·툴팁 값은 전체다. 전환해도 잘린 이름과 전체 이름이 짝을 유지한다

### RC-084 점이 1,000개를 넘으면 그리지 않고 정확히 1,000개는 그린다
- Given 범주 1,000개·값 1개, 범주 1,001개, 범주 500개 × 값 3개, 1,001행 분산형(값 2개), 1,001행 거품형, 범주 1,001개 파레토·폭포·깔때기, 새 종류(`stacked_line`)의 범주 1,001개
- When 각각 그린다
- Then 1,000개는 그리고, 나머지는 "범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요"다(화면에도 같은 문구, 정확히 1,000개는 그림)

### RC-085 모든 차트는 크기에 맞춰 그리고 데이터 레이블은 인스턴스 플러그인과 표 서식이다
- Given 그룹 1개 결과
- When 여러 종류를 그리고 데이터 레이블을 켠다
- Then 모든 옵션이 `responsive: true`·`maintainAspectRatio: false`, 제목이 ""이면 제목 표시가 꺼지고, 데이터 레이블 글자는 결과 표 칸 서식이며, 그림 컴포넌트에는 데이터 레이블 플러그인이 인스턴스 `plugins`로 넘어가고 차트 종류(`type`)는 빌더 값 그대로다

### RC-086 금액은 원으로 그리고 금액만 올라간 값 축은 억·만으로 줄여 쓴다
- Given 값 금액 합계(1,870,000,000)·건수·사용자 수 평균(2.6) 결과
- When `bar`(금액만), `horizontal_bar`(금액만), `stacked_bar`·`line`·`area`(금액만), `bar`(금액+건수), `bar`(건수만), `bar`(금액 건수 집계), `stacked_100_bar`, `combo`(막대 금액·꺾은선 건수, 그리고 막대 건수·보조 축 꺾은선 금액), `scatter`(x 금액, y 건수), `pie`를 그린다
- Then 데이터는 1,870,000,000 그대로이고 툴팁·레이블은 "1,870,000,000", 사용자 수는 "3"이다. 금액만 올라간 축(가로 막대는 x)은 눈금 "18.7억", 금액+건수·건수만·금액 건수 집계 축은 단축 없음, 100% 누적은 "%" 눈금, 콤보는 금액이 있는 축만, 분산형은 x만 단축이고 원형은 축이 없다

### RC-087 막대는 세로·가로·누적에 맞는 축과 빈 칸 0으로 그린다
- Given 그룹 2개 결과(빈 칸 있음)
- When `bar`, `horizontal_bar`, `stacked_bar`, `stacked_horizontal_bar`를 그린다
- Then 모두 `type: 'bar'`이고, 가로 종류는 `indexAxis: 'y'`이며 범주 축이 y·값 축이 x(축 제목도 함께 바뀜), 누적 종류는 두 축 모두 `stacked: true`, 빈 칸은 0이다

### RC-088 100% 누적은 범주별 비율과 0~100 축, 비율·원래 값 툴팁으로 그린다
- Given 범주 A(계열 X 30, Y 10), B(X 0, Y 0)
- When `stacked_100_bar`, `stacked_100_horizontal_bar`, `stacked_100_line`, `stacked_100_area`를 그린다
- Then A는 X 75·Y 25, B는 0·0이고 값 축 최대 100(가로는 x)·눈금 "75%", 툴팁 "X: 75% (30)", 데이터 레이블 "75%"이며 영역은 `fill: 'stack'`이다

### RC-089 꺾은선·영역은 표식·채움·끊김을 종류대로 그리고 점 가까이서 툴팁이 뜬다
- Given 그룹 2개 결과(빈 칸 있음)
- When `line`, `line_markers`, `stacked_line`, `stacked_line_markers`, `area`, `stacked_area`, `radar`를 그린다
- Then 모두 `type: 'line'`(방사형 제외)이고, `line`은 `pointRadius 0`·`fill: false`·빈 칸 null, `line_markers`·`stacked_line_markers`는 `pointRadius 3`, 누적 꺾은선은 값 축 `stacked`·빈 칸 0, `area`는 `fill: 'origin'`, `stacked_area`는 `fill: 'stack'`이며, 표식 없는 종류(꺾은선·영역·방사형)는 `interaction {mode: 'index', intersect: false}`다

### RC-090 원형·도넛형은 범주마다 한 조각이고 툴팁 머리가 범주 이름이다
- Given 범주 SAP 10, Okta 빈 값, MS 30
- When `pie`와 `doughnut`을 그린다
- Then `type`은 `pie`·`doughnut`, 데이터셋 하나에 [10, 0, 30]과 범주마다 다른 색, 툴팁은 "SAP: 10"처럼 범주 이름으로 시작하고 축(scales)이 없다

### RC-091 분산형은 첫 값을 x로, 나머지를 y 계열로 그리고 빈 점은 그 계열에서만 뺀다
- Given 행 (A, x 1, y1 2, y2 3), (B, x 4, y1 null, y2 6), (C, x null, y1 7, y2 8)
- When `scatter`·`scatter_line`·`scatter_smooth`·`scatter_smooth_markers`로 그린다
- Then 데이터셋은 y1·y2 둘(이름 = 머리글), y1 점은 A(1, 2)뿐, y2 점은 A(1, 3)·B(4, 6)이고 x축은 선형·축 제목 = 가로축 제목, 범위는 y축이다. `scatter`는 선 없음·`pointRadius 3`, `scatter_line`은 결과 행 순서로 잇고 표식 없음, `scatter_smooth`는 `tension 0.4`·표식 없음, `scatter_smooth_markers`는 곡선·표식이며 툴팁은 "A: (1, 2)"다

### RC-092 거품형은 크기에 비례한 면적으로 그리고 0 이하·빈 크기를 빼고 알린다
- Given 행 크기 100, 25, 0, 빈 값(x·y는 모두 있음), 그리고 값 2개인 거품형 설정
- When 거품형을 그리고 반지름을 계산한다
- Then 반지름은 30, 17이고 나머지 두 점은 그리지 않으며 안내 "크기가 0 이하이거나 빈 값인 점 2개는 그리지 않았습니다"가 있다(모두 그리면 안내 없음, 양수 하나뿐이면 30). 값 2개 설정은 그리지 않는다(결과 대응, RC-080)

### RC-093 방사형은 범주가 3개 이상일 때만 반지름 축 위에 그린다
- Given 범주 3개·계열 2개 결과와 범주 2개(계열 있음) 결과
- When `radar`, `radar_markers`, `radar_filled`를 범위 0~50으로 그린다
- Then 범주 3개는 `type 'radar'`, 계열마다 선 하나, `r` 축 `min 0`·`max 50`이고 표식은 `radar_markers`만·채움은 `radar_filled`만이며, 범주 2개는 "방사형은 범주가 3개 이상일 때 그립니다"다

### RC-094 트리맵은 두 단계(계열 있음)·한 단계로 그리고 색·글자·툴팁이 상위를 따른다
- Given Vendor(SAP·Okta) × 분기 결과와 Vendor만 있는 결과
- When `treemap`을 계열 있게, 없게 그린다
- Then 계열 있으면 `groups ['upper','lower']`, 없으면 `['upper']`이고 `type 'treemap'`·데이터 레이블 플러그인 끔이다. 큰 사각형은 상위마다 다른 색이고 자식은 부모 색, 두 단계의 상위 사각형 캡션은 비고 잎은 하위 이름과 값, 한 단계의 잎은 상위 이름과 값이며, 툴팁 제목은 상위 이름·본문은 "<하위 이름>: <값>"이다

### RC-095 트리맵 행은 칸마다 하나이고 0 이하·빈 칸을 빼며 빈 이름을 (없음)으로 바꾼다
- Given 행렬: 범주 A·""(빈 이름), 데이터셋 X·""; 값 A/X 3, A/"" 2, ""/X 0, ""/"" 빈 값
- When 트리 행을 만든다
- Then 행은 `{upper: "A", lower: "X", value: 3}`, `{upper: "A", lower: "(없음)", value: 2}` 둘이고 빠진 칸 2개, 행 키는 `upper`·`lower`·`value`뿐이며 빈 글자 그룹 키가 없다. 양수가 없으면 행이 없다

### RC-096 선버스트는 안쪽 상위·바깥 하위 고리이고 범례 클릭으로 숨기지 않는다
- Given Vendor(Silverfort 자식 3, Okta 자식 1) × 분기 결과, 같은 표시 이름(앞 N자)의 상위 둘, 계열 없는 결과
- When `sunburst`를 그리고 범례 클릭 동작을 확인한다
- Then `type 'doughnut'`에 안쪽(상위 합)·바깥(하위) 데이터셋 둘이고, 계열이 없으면 고리 하나다. 바깥 조각 색은 부모의 순번 색이라 표시 이름이 같은 두 부모의 자식 색이 섞이지 않으며, 범례 클릭은 어떤 조각도 숨기지 않는다. 0 이하 칸이 있으면 "값이 0 이하이거나 빈 칸 N개는 그리지 않았습니다"

### RC-097 선버스트 고리는 상위 합과 하위 항목이 같은 합이고 0 이하·빈 칸을 뺀다
- Given 행렬: A(X 3, Y 2), B(X 0, Y 빈 값), C(X 4)
- When 고리를 계산한다
- Then 안쪽 [A 5, C 4], 바깥 [A/X 3, A/Y 2, C/X 4](부모 순번 0·0·1), 두 고리의 합 9가 같고 빠진 칸 2개이며 자식이 모두 빠진 B는 안쪽에 없다

### RC-098 히스토그램은 구간 이름과 빈도 막대로 그리고 구간 한도에 따로 안내한다
- Given 그룹 없는 금액 열 결과 1..10, 그룹 결과의 집계 열, 표본 5,000행, 너비 0.001 설정, 999개 일반 구간 + 오버·언더플로 설정, 1,001개 일반 구간 설정
- When 히스토그램을 그린다
- Then 1..10은 `type 'bar'`, 가로 항목 = 구간 이름, 데이터셋 "빈도"의 개수 합 10, 범례 없음, 세로축 0부터·범위 적용, 설명 "히스토그램 차트: <머리글> 분포"이고, 그룹 결과는 그룹마다 한 표본, 5,000행 표본도 그린다. 999 + 2개 구간은 그리고, 1,001개 구간·너비 0.001은 "구간이 너무 많아 차트를 그리지 않습니다(최대 1,000개). 구간 너비를 늘리세요"다

### RC-099 구간은 자동·구간 수·구간 너비 방식대로 나뉘고 경계 값은 아래 구간이다
- Given 표본
- When 1..10을 자동, 큰 표본을 자동, [0, 10, 20, 30, 40]을 구간 수 2·1·100, [0, 10, 40]을 너비 15로 나누고, 빈 값·빈 표본을 넣는다
- Then 1..10 자동은 구간 2개(Scott 너비 약 4.9), 자동 구간은 최대 100개, 구간 수 2는 "[0, 20]" 3개·"(20, 40]" 2개(20은 아래 구간), 구간 수 1은 하나·100은 정확히 100개, 너비 15는 [0, 15]·(15, 30]·(30, 45]로 마지막이 최댓값을 넘으며, 개수 합은 표본 수, 빈 값은 빼고 빈 표본은 구간이 없다

### RC-100 오버플로·언더플로 구간은 양끝에 따로 세고 구간 이름은 숫자 서식을 따른다
- Given 표본 [5, 10, 15, 25, 30, 35]
- When 언더플로 10·오버플로 30, 오버플로 30만, 언더플로 10만으로 나누고, 서식 함수(천 단위)를 준다
- Then 첫째는 "≤ 10" 2개 → 15·25·30만의 일반 구간 → "> 30" 1개 순, 둘째·셋째는 한쪽 끝 구간만 있고, 구간 이름 숫자는 서식 함수 결과다

### RC-101 파레토는 내림차순 막대와 0~100% 보조 축 누적 꺾은선이다
- Given 범주·값 A 10, B 30, C 빈 값, D 20, E −5, F 30(리포트 정렬은 A부터)
- When 파레토를 그린다
- Then 막대는 B 30, F 30, D 20, A 10 순(같은 값은 결과 순서), 누적 %는 33.3·66.7·88.9·100(마지막 정확히 100) 꺾은선이 `y1`(0~100, 눈금 "%")에 있고 안내 "값이 0 이하이거나 빈 항목 2개는 그리지 않았습니다"다. 모두 양수면 안내 없음, 양수가 없으면 빈 막대다

### RC-102 폭포는 앞 누계에서 시작하는 증가·감소 막대이고 합계 막대는 옵션이다
- Given 범주 값 10, −4, 빈 값, 6
- When 폭포를 합계 없이, 합계 켜고 그린다
- Then 막대는 [0, 10] 증가, [10, 6] 감소, [6, 6] 증가(빈 값 0), [6, 12] 증가이고 데이터셋은 "증가"·"감소" 범례 항목, 툴팁은 변화량("감소: −4")이다. 합계를 켜면 범주 "합계"와 [0, 12] 막대·"합계" 항목이 더해지고 그 툴팁은 누계 12다. 값이 없고 합계를 켜면 [0, 0] 합계 막대 하나다

### RC-103 깔때기는 결과 순서의 가운데 정렬 막대이고 0 이하·빈 항목을 뺀다
- Given 범주 값 100, 0, 빈 값, 40, 70(결과 순서)
- When 깔때기를 그린다
- Then `type 'bar'`·`indexAxis 'y'`, 막대는 결과 순서 그대로 [−50, 50], [−20, 20], [−35, 35](정렬 없음), x축 숨김·범위 −50~50, 범례 없음, 안내 "값이 0 이하이거나 빈 항목 2개는 그리지 않았습니다"다. 양수가 없으면 막대가 없다

### RC-104 콤보는 계열마다 종류·누적 묶음·보조 축대로 그리고 꺾은선이 막대 위다
- Given 값 4개의 콤보, 계열 [{stacked_column}, {stacked_column}, {stacked_area}, {line_markers, secondary}]와 [{column}, {column}, {line}]와 계열 설정 없음(`secondaryAxis` true)
- When 콤보를 그린다
- Then 첫째: 누적 막대 둘은 `stack 'bars'` 공통, 누적 영역은 `stack 'areas'`·`fill 'stack'`, 꺾은선은 `yAxisID 'y1'`·`pointRadius 3`이고 x축 `stacked`·y축 `stacked`, `y1`은 오른쪽 축이다. 둘째: 묶은 막대 둘은 서로 다른 `stack`이라 쌓이지 않고 꺾은선 `order`가 막대보다 앞이다(위에 그려짐). 셋째: 첫 값 막대·나머지 꺾은선(보조 축)으로 그린다(서버가 채운 옛 규칙과 같은 모습)

### RC-105 Fake 게이트웨이는 흉내 내는 차트 규칙에서 서버와 같은 결과를 낸다
- Given Fake 게이트웨이와 계약 테스트(같은 시나리오를 Fake에 실행)
- When 차트와 함께 저장·차트 없이 저장·덮어쓰기로 차트만 바꾸고 null로 지우기·범주가 그룹이 아닌 차트·그룹 없는 정의의 막대 차트·그룹 3개 정의의 히스토그램과 막대 차트·구간을 생략한 히스토그램·계열 설정을 생략한 콤보(`secondaryAxis` true)·종류별 옵션을 생략한 막대 차트·정의를 바꿔 맞지 않는 덮어쓰기·복제를 한다
- Then 서버와 같다: 저장 차트·목록 `chartKind`·`chartProblem` null, 차트 없음 null·종류 null, 덮어쓰기 revision 증가와 null 삭제, `["chart","category"]` `chart-category-invalid` "범주 열은 그룹핑한 컬럼이어야 합니다"·`["chart"]` `chart-needs-grouping` "그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)" 위반과 저장 안 됨, 그룹 3개 정의는 히스토그램도 막대도 `["chart"]` `chart-too-many-groups` 위반 하나이고 저장 안 됨, 구간을 생략한 히스토그램은 `histogram.binMode` "auto"(나머지 null), 계열을 생략한 콤보는 첫 값 묶은 세로 막대·나머지 보조 축 꺾은선, 옵션을 생략한 막대는 `histogram`·`comboSeries` null·`showTotal` false로 읽힌다(다른 종류 전용 옵션 값을 넣으면 서버는 `chart-option-invalid`로 거절하며 Fake는 이 위반을 흉내 내지 않는다, RC-R57), 맞지 않는 덮어쓰기는 저장 내용 유지, 복제는 차트 함께 복사

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 초안: 구현된 Reports 차트 동작 문서화(RC-R1~R57, RC-UC1~UC3, RC-001~RC-105) | RC-001~RC-105 |
| 2026-11-11 | 사용자 결정 반영: Fake 차트 처리를 서버에 맞춤(문구 "(히스토그램 제외)", 히스토그램도 그룹 3개 이상 거절, 정규화, RC-R57), bool 아닌 `swap` 문구·"범주 열을 고르세요"·part `category` 현행 유지(RC-R10, RC-R32), 차트 저장 동작(RC-R18~RC-R22)과 편집 화면 차트 부분(RC-R38) RC 소유 명시, RS·RQ·DSH 상호 참조를 규칙 번호로 | RC-105 변경 |
