# 저장 리포트·결과 배치   (feature 코드: RS, 상태: 확정(2026-11-18 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`backend/src/app/domain/saved_report/{entities,values,policy,layout,errors}.py`, `app/application/report/{create_report,update_report,copy_report,get_report,list_reports,delete_report,run_saved_report,change_report_layout,execution,saved_inputs,saved_views}.py`, `app/application/ports/report_repository.py`, `app/infra/db/{report_repository,models_report}.py`, `app/web/routers/saved_reports.py`, `app/web/schemas/saved_report.py`, `app/web/error_handlers.py`, `frontend/src/features/reports/{ReportsPage,SaveReportDialog,ReportNotFound}.tsx`, `list/*`, `view/*`, `result/{ResultPanel,ResultTiles,TileFrame,ViewModePicker,layout}.ts(x)`, `designer/{Designer,DesignerHeading,DesignerTabs,ReportEditPage,useSaveFlow,useLeaveGuard}.ts(x)`, `data/reports.ts`, `gateway/http/reports.ts`, `shared/model/permissions.ts`, `test/fake/gateway/savedReports.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·안내서가 어긋나던 점은 2026-11-11 사용자 결정으로 정리했습니다: 저장 리포트 Fake 게이트웨이는 서버 동작에 맞추고(RS-R47), 깨진 저장 정의는 보기·편집 화면이 배너만 보이는 현행대로 두며(RS-R17), 배치 자동 저장의 "한 번에 하나·마지막 값"은 순차 규칙으로 둡니다(RS-R41). 저장 정의 JSON 읽기 변환은 RQ-R57, 차트 필드의 저장·복제·`chart_kind`·`chart_problem`은 RC(RC-R18~RC-R22)가 가집니다. 안내서(`docs/user-guide.html` 15.8) 문구는 코드에 맞춥니다. 결정 목록은 계획(`artifacts/10-analysis/rs-plan.md`)에 있습니다.

## 1. 개요

- 목적: 로그인한 모든 사용자가 Reports 디자이너에서 조회한 설계를 이름 붙여 저장하고, 목록에서 찾아 열 때마다 최신 데이터로 다시 조회하며, 공개 범위에 따라 다른 사람과 함께 쓰고 고친다. 결과의 보기 방식과 표·차트 타일 배치도 리포트와 함께 저장한다.
- 사용자(역할): admin·sales·user 모두 만들기·열기·복제를 할 수 있다(역할 가드 없음, PL-R6). 대상별 권한(보기·수정·공개 범위·삭제)은 만든 사람·공개 범위·admin으로 정한다(RS-R5~R8).
- 범위
  - 화면 `/reports`(목록), `/reports/:id`(보기), `/reports/:id/edit`(편집), 저장 대화상자, 디자이너의 저장·다른 이름으로 저장·덮어쓰기·되돌리기/초기화·"● 저장 안 됨"·떠날 때 확인, 디자이너의 작성/결과 탭 전환, 결과 탭과 보기 화면의 보기 방식·타일 배치(끌어서 놓기·Alt+화살표), 보기 화면 배치 자동 저장
  - API `GET·POST /reports`, `GET·PUT·DELETE /reports/{id}`, `POST /reports/{id}/copy`, `POST /reports/{id}/run`, `PUT /reports/{id}/layout`
  - 권한 판정 순서, revision 낙관적 잠금, 이름 전체 고유, 깨진 저장 정의(`stored-invalid`), 작성자 퇴사 결과, `reports` 테이블
- 범위 밖(다른 feature)
  - 리포트 정의(컬럼·조건·범위·행 수)의 값 검증(RQ-R7~RQ-R19), SQL 생성(RQ-R20~RQ-R35), `/reports/fields`·`/reports/query`(RQ-R1), 실행 결과 모양(`ReportQueryResponse`, RQ-R36)·합계(RQ-R32)·시간 제한(503 `report-timeout`, RQ-R35), 저장 정의 JSON의 모양·읽을 수 있는지 판정·예전 형식 읽기 변환(포맷·최상위 정렬, RQ-R57 — 2026-11-11 결정), 작성 탭 내용(RQ-R40~RQ-R48)·위반 표시(RQ-R49)·결과 표(RQ-R50, RQ-R51)·생성 SQL 보기(RQ-R53) → RQ
  - 요청 `chart`의 값 검증·정규화(RC-R3~RC-R17), 저장·덮어쓰기·복제 때 차트가 어떻게 되는지(PUT에서 `chart` 생략·null이면 삭제, 복제 때 원본 차트 다시 검증·승계 — RC-R18, RC-R20), 목록·상세의 `chart_kind`(RC-R19), 저장 차트 읽기 변환·읽을 수 없는 차트 안내(`chart_problem`, RC-R21, RC-R22), 목록 "차트" 열의 종류 라벨(RC-R37), 차트 타일·설정 패널(RC-R24~RC-R36), 편집 화면 저장 안 됨·되돌리기 중 차트 부분(RC-R38) → RC(2026-11-11 결정). 차트 없는 리포트의 결과 배치·보기 방식은 RS(RS-R37)
  - 사용자 표시 참조(US-R12), 사용자 삭제·퇴사 판정(US-R17) → US
  - 응답 시각 오프셋(TM-R8), 시각 표기 `formatStamp`(TM-R14), 업무 날짜(TM-R4) → TM
  - 권한 분류·판정 순서 기본값·CSRF·Problem 형식·id 경로·NUL·화면 가드·상단 메뉴·오류 문구·게이트웨이 공통 변환 → PL(PL-R2, PL-R4, PL-R5, PL-R6, PL-R9, PL-R10, PL-R12, PL-R15, PL-R16, PL-R29, PL-R33, PL-R34, PL-R36, PL-R37, PL-R39)
  - 대리 키·사용자 FK 공통 규칙 → SC(SC-R11, SC-R17)
- 관련 화면·메뉴: 상단 메뉴 "Reports"(PL-R34), 가드 RequireAuth(PL-R29, PL-R33). 화면 라우트는 React.lazy 청크다.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 저장 리포트 | 이름·설명·공개 범위·정의·서버 생성 SQL·차트(선택)·결과 배치·만든 사람·최종 수정자·revision·생성/수정 시각의 묶음. 결과 데이터는 저장하지 않는다 |
| 정의(definition) | `/reports/query` 요청과 같은 모양의 조회 설계(RQ-R7). 저장 형식과 읽기 변환은 RQ-R57 |
| 공개 범위 | `public`(화면 "모든 사용자에게 보임") / `private`(화면 "나만 보기") |
| 만든 사람(owner) / 최종 수정자(updated_by) | 만든 요청자 / 마지막으로 덮어쓰기·배치 저장한 요청자 |
| revision | 낙관적 잠금 번호. 만들기 1, 덮어쓰기·배치 저장마다 +1 |
| 깨진 저장 정의 | 저장된 정의 JSON을 읽을 수 없는 리포트(엔티티의 `definition`이 None) |
| 결과 배치(layout) | `{view, order, arrange}` — 보기 방식, 타일 순서, 한 줄/두 줄 |
| 보기 방식(view) | `both`(표+차트) · `chart`(차트만) · `table`(표만) |
| 타일 | 결과 영역의 표 타일·차트 타일 |
| 기준선(편집 화면) | 편집 화면이 "저장된 설계"로 보는 값: 처음 불러온 리포트, 내 덮어쓰기 뒤에는 그 응답 |
| 확인된 배치(보기 화면) | 서버가 마지막으로 확인한 `{layout, revision}`(처음엔 연 리포트, 이후 배치 저장 응답) |
| 대기 값 | 배치 저장 요청 중에 바뀐 마지막 배치 하나 |

### 2.2 데이터 모델

소유 테이블 `reports`(대리 키 SC-R11, 사용자 FK SC-R17)

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `id` | BIGINT identity PK | 리포트 id |
| `name` | varchar(100) NOT NULL | 정규화된 이름. 유니크 인덱스 `uq_reports_name_lower` = `lower(name)`(모든 리포트 사이) |
| `description` | varchar(1000) NOT NULL, DB 기본값 없음 | 정규화된 설명(빈 문자열 가능) |
| `visibility` | varchar(10) NOT NULL, CHECK `visibility in ('public','private')` | 공개 범위 |
| `owner_user_id` | BIGINT FK `users.id` RESTRICT, 인덱스 `ix_reports_owner_user_id` | 만든 사람 |
| `updated_by_user_id` | BIGINT FK `users.id` RESTRICT, 인덱스 `ix_reports_updated_by_user_id` | 최종 수정자 |
| `definition` | JSONB NOT NULL, CHECK `jsonb_typeof(definition) = 'object'` | 검증을 통과한 원시 정의 |
| `generated_sql` | TEXT NOT NULL | 저장 때 서버가 만든 SQL(표시용) |
| `chart` | JSONB NULL | 차트 설정(없으면 NULL, 내용 규칙은 RC-R18~RC-R22) |
| `layout` | JSONB NULL, CHECK `layout is null or jsonb_typeof(layout) = 'object'` | 결과 배치(NULL이면 기본 배치로 읽음) |
| `revision` | int NOT NULL, CHECK `revision >= 1` | 낙관적 잠금 |
| `created_at`, `updated_at` | timestamptz NOT NULL | 생성·마지막 저장 시각(서버 시각) |

도메인: `Report`(Aggregate, `create`·`overwrite`·`change_layout`·`copy_as`·`ensure_visible_to`·`ensure_deletable_by`·`readable_definition`), 값 객체 `ReportVisibility`, `ReportContent`, `ReportListScope{viewer_id, see_all}`, `ReportLayout{view, order, arrange}`·`DEFAULT_LAYOUT`. Port `ReportRepository`(`list(scope)`·`get(id, for_update)`·`add`·`update`·`update_layout`·`delete`).

### 2.3 비즈니스 규칙

저장 내용
- **RS-R1** 저장 리포트에는 결과 데이터가 없다. SQL은 서버가 정의로 만든 것만 저장하고 응답에 싣는다(`generated_sql`). 요청 본문은 정해진 키만 받는다: 모르는 키(예: `generated_sql`, `id`, `owner`)·필수 키 누락·문자열이 아닌 이름/설명/공개 범위·정수가 아닌 revision은 422 `request-validation`(PL-R12)이고 아무것도 저장되지 않는다.
- **RS-R2** 메타 규칙(모두 422 `invalid-value`, 첫 위반 하나): 이름은 NUL이 있으면 "리포트 이름에는 NUL 문자를 쓸 수 없습니다"(PL-R16), 앞뒤 공백을 지운 뒤 비면 "리포트 이름을 입력하세요.", 101자 이상이면 "리포트 이름은 100자 이내로 입력하세요."(100자는 됨, 길이는 공백을 지운 뒤 센다). 설명은 선택(생략하면 `""`)이고 NUL이면 "설명에는 NUL 문자를 쓸 수 없습니다", 앞뒤 공백을 지운 뒤 1,001자 이상이면 "설명은 1,000자 이내로 입력하세요."(1,000자는 됨). 공개 범위는 정확히 `public` 또는 `private`(대소문자·공백 구분)이고 그 밖은 "공개 범위는 public 또는 private입니다.". 이름·설명은 정규화된 값으로 저장된다.
- **RS-R3** 이름 고유: 정규화한 이름이 **모든 리포트**(만든 사람·공개 범위·요청자가 볼 수 있는지와 무관) 사이에서 대소문자 무시로 하나뿐이어야 한다. 겹치면 409 `already-exists` "같은 이름의 리포트가 이미 있습니다."이고 아무것도 바뀌지 않는다(만들기·덮어쓰기·복제). 자기 리포트의 이름을 대소문자만 바꿔 저장하는 것은 된다. 삭제된 리포트의 이름은 다시 쓸 수 있다. 남의 비공개 리포트 이름의 존재가 드러나는 것은 받아들인 위험이다.
- **RS-R4** 저장 내용 검증 순서(만들기·덮어쓰기): 이름 → 설명 → 공개 범위(RS-R2) → 정의(RQ-R7~RQ-R19, 위반을 모두 모아 422 `invalid-report`, RQ-R8) → 차트(RC-R3~RC-R17, 정의 위반이 있으면 검사하지 않음, RC-R5) → 배치(RS-R20, 차트 위반이 있으면 검사하지 않음). 통과하면 서버가 정의를 요청 시점의 업무 날짜(TM-R4)로 풀어 SQL을 만들어 함께 저장한다. 어느 단계에서 거절되어도 아무것도 저장·변경되지 않는다.

권한
- **RS-R5** 보기: admin은 모든 리포트, 그 밖의 역할은 자기가 만든 리포트와 공개 리포트를 본다. 볼 수 없는 리포트(남의 비공개)는 **없는 id와 같은** 404 `not-found` "리포트를 찾을 수 없습니다."이며 상세·덮어쓰기·배치 저장·삭제·복제·실행 모두 다른 판정(본문 값·revision·깨진 정의)보다 먼저다.
- **RS-R6** 수정(덮어쓰기·배치 저장): 볼 수 있는 리포트는 수정할 수 있다(공개 리포트는 user를 포함한 모든 역할, 비공개는 만든 사람과 admin). 수정 권한 403 `forbidden` "이 리포트를 수정할 권한이 없습니다."는 지금 규칙으로는 닿지 않는 방어 동작이다(판정 위치는 RS-R12·RS-R22).
- **RS-R7** 공개 범위 변경은 만든 사람과 admin만 한다. 다른 편집자가 저장된 값과 **다른** 공개 범위를 보내면 403 `forbidden` "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."이고 아무것도 바뀌지 않는다. 같은 값을 보내는 것은 된다. 비공개가 되면 만든 사람·admin이 아닌 사람에게는 RS-R5의 404가 된다.
- **RS-R8** 삭제는 만든 사람(공개·비공개 무관)과 admin만 한다. 볼 수 있지만 권한이 없으면(남의 공개 리포트) 403 `forbidden` "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."다.
- **RS-R9** 만들기·복제는 모든 역할이 하며 만든 사람과 최종 수정자는 요청자다. 역할 가드가 없어 user도 막히지 않는다(PL-R6). 판정 순서는 PL-R4의 예외로 각 경로 규칙(RS-R12~R18, RS-R22)을 따른다: 대상 404가 도메인 값 422보다 먼저다.

목록·상세
- **RS-R10** `GET /reports`: 요청자가 볼 수 있는 리포트(RS-R5)를 `updated_at` 내림차순, 같으면 id 내림차순으로 준다(배치 저장도 `updated_at`을 바꾼다). 항목은 정확히 `{id, name, description, visibility, owner, updated_by, entities, created_at, updated_at, chart_kind}`이고 정의·SQL·revision·차트 본문·배치는 없다. `entities`는 정의의 컬럼·조건이 쓰는 데이터 묶음(`deal` 항상, Deal Actions 필드를 쓰면 `["deal", "action"]`)이다. `chart_kind`는 저장 차트의 종류 또는 null(RC-R19). 볼 수 있는 것이 없으면 `[]`.
- **RS-R11** revision: 만들기 1, 덮어쓰기·배치 저장 성공마다 +1. 요청의 `revision`(필수, 정수 ≥ 1)이 저장된 값과 다르면(낮든 높든) 409 `invalid-state` "다른 사용자가 먼저 이 리포트를 저장했습니다. 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."이고 아무것도 바뀌지 않는다. 같은 revision으로 두 번 차례로 보내면 첫 번째만 된다. 응답의 revision으로 이어 저장하면 된다.
- **RS-R15** `GET /reports/{id}`: 404(RS-R5) → 깨진 저장 정의 422(RS-R17) → 200 상세 = 목록 항목 + `{revision, definition, generated_sql, chart, chart_problem, layout}`. `owner`·`updated_by`는 UserRef(US-R12, 퇴사자 `resigned: true`·`label` "<이름>(퇴사)")이고 시각은 서버 오프셋 시각(TM-R8)이다. `chart`·`chart_problem`·`chart_kind`의 내용은 RC-R19·RC-R21.

쓰기 경로
- **RS-R12** `PUT /reports/{id}` 본문 `{name, description?, visibility, definition, chart?, layout?, revision}`. 판정 순서: 404(RS-R5, revision이 틀려도) → 422 내용(RS-R4) → 403 수정 권한(RS-R6, 방어) → 403 공개 범위(RS-R7, revision이 틀려도) → 409 revision(RS-R11) → 409 이름(RS-R3). 성공 200 상세: 이름·설명·공개 범위·정의·SQL(새로 생성)·차트를 바꾼다. 차트의 교체·삭제(`chart`를 생략하거나 null로 보내면 저장된 차트를 지우고 읽을 수 없던 차트도 정리됨)는 RC-R18이 정한다. `layout`을 생략하거나 null로 보내면 저장된 배치를 그대로 두고, 보내면 바꾼다. 만든 사람·생성 시각은 그대로, 최종 수정자 = 요청자, 수정 시각 = 서버 시각, revision + 1. 깨진 저장 정의(RS-R17)도 새 정의로 덮어쓰면 복구된다(revision 검사는 그대로 한다).
- **RS-R13** `POST /reports/{id}/copy` 본문 `{name, description?, visibility}`(정의·차트·배치 키는 422 `request-validation`, 설명 생략은 `""`). 판정 순서: 404(RS-R5) → 깨진 원본 정의 422(RS-R17) → 메타 422(RS-R2) → 원본 정의·차트를 **지금** 규칙으로 다시 검증(위반 422 `invalid-report`, RQ-R7~RQ-R19·RC-R20) → 409 이름(RS-R3). 성공 201, `Location: /api/v1/reports/<새 id>`, 상세: 정의 = 원본, 차트는 RC-R20(원본 차트 승계, 읽을 수 없으면 차트 없이), 배치 = 원본, 만든 사람·최종 수정자 = 요청자, revision 1, SQL은 새로 만든다. 원본은 바뀌지 않는다.
- **RS-R14** `POST /reports` 본문 `{name, description?, visibility, definition, chart?, layout?}`. 판정 순서: 422 내용(RS-R4) → 409 이름(RS-R3). 성공 201, `Location: /api/v1/reports/<id>`, 상세: revision 1, 만든 사람 = 최종 수정자 = 요청자, 생성 시각 = 수정 시각 = 서버 시각, `layout`을 생략하거나 null이면 기본 배치(RS-R19). 두 번 만들면 서로 다른 id다.
- **RS-R16** `POST /reports/{id}/run`(본문 없음): 404(RS-R5) → 깨진 저장 정의 422(RS-R17) → 저장된 정의를 **지금** 카탈로그 규칙으로 다시 검증(위반 422 `invalid-report`, RQ-R7~RQ-R19) → 실행 시각의 업무 날짜로 풀어 읽기 전용으로 실행한다. 응답은 `/reports/query`와 같은 모양(RQ-R36)이고 같은 정의를 같은 순간 `/query`로 조회한 결과와 같다. 저장된 `generated_sql`은 쓰지 않고 매번 새로 만든다. 아무것도 저장하지 않는다(revision·수정 시각 그대로). 시간 초과는 503 `report-timeout`(RQ-R35).
- **RS-R17** 깨진 저장 정의: 저장소는 읽을 수 없는 정의를 실패 없이 `definition = None`인 리포트로 읽는다. 목록(RS-R10)에는 남고 `entities`는 `[]`다. 상세·실행·복제·배치 저장은 보기 판정(404) **뒤** 422 `invalid-report`, `detail` "저장된 리포트 정의를 읽을 수 없습니다.", `errors` = `[{location: ["definition"], code: "stored-invalid", message: "저장된 리포트 정의를 읽을 수 없습니다."}]`이고 아무것도 실행·생성·변경되지 않는다. API로는 덮어쓰기(새 정의)로 복구하고, 삭제할 수 있다. 화면에서는 보기·편집 화면 모두 이 422에 오류 배너만 보이고 설계를 싣지 않으므로 화면에서 고칠 수 없으며, 목록 ⋯ 메뉴의 삭제만 된다(RS-R34·RS-R35, 현행대로 문서화 2026-11-11 결정 — 화면 복구는 별도 요청). 어떤 저장 정의가 읽을 수 없는지와 예전 형식 정의를 새 형식으로 읽는 변환은 RQ-R57이 정한다.
- **RS-R18** `DELETE /reports/{id}`: 404(RS-R5) → 403(RS-R8) → 204(본문 없음), 그 리포트만 물리 삭제한다. 깨진 정의·차트여도 지울 수 있다. 없는 id는 404다.

결과 배치
- **RS-R19** 배치 = `{view: "both"|"chart"|"table", order: ["table","chart"] 또는 ["chart","table"], arrange: "side_by_side"|"stacked"}`. `order`의 앞이 한 줄이면 왼쪽, 두 줄이면 위다. 기본 배치는 `{both, [table, chart], stacked}`(표+차트, 표 → 차트, 두 줄)다. 타일이 하나만 보여도 `order`·`arrange`는 그대로 저장·보존한다.
- **RS-R20** 배치 검증: 요청의 배치 객체는 세 키가 모두 있어야 하고 모르는 키는 안 된다(422 `request-validation`). 값 위반은 모두 모아 422 `invalid-report`이고 각 항목은 code `invalid-value`, 위치·문구는 `["layout","view"]` "보기 방식은 both, chart, table 중 하나입니다", `["layout","order"]` "타일 순서는 table과 chart를 한 번씩 담아야 합니다"(길이 2인 목록이고 두 값이 서로 다른 table·chart), `["layout","arrange"]` "배치는 side_by_side 또는 stacked입니다"다. 값은 문자열이 정확히 일치할 때만 받는다.
- **RS-R21** 저장된 배치 읽기: `layout`이 NULL이거나 객체가 아니거나 값이 틀리면 오류 없이 기본 배치로 읽는다. 그런 리포트를 덮어쓰면 그때의 배치(기본 포함)가 객체로 저장된다.
- **RS-R22** `PUT /reports/{id}/layout` 본문 `{layout, revision}`(둘 다 필수, 모르는 키 422 `request-validation`). 판정 순서: 404(RS-R5) → 깨진 저장 정의 422(RS-R17) → 배치 값 422(RS-R20) → 403 수정 권한(RS-R6, 방어) → 409 revision(RS-R11). 성공 200 상세: 배치·최종 수정자(= 요청자)·수정 시각·revision(+1)만 바뀌고 이름·설명·공개 범위·정의·SQL·차트는 그대로다(읽을 수 없는 저장 차트도 그대로 남아 `chart_problem`이 계속 나온다). 남의 공개 리포트의 배치도 저장할 수 있고, admin은 남의 비공개 리포트의 배치도 저장한다.
- **RS-R23** 배치는 만들기(RS-R14)·덮어쓰기(RS-R12)·복제(RS-R13)에 포함되고 상세에 항상 있으며(`layout` 필수), 목록 항목에는 없다.

사용자 연결
- **RS-R24** 만든 사람·최종 수정자는 사용자 연결이다(SC-R17의 `reports.owner_user_id`·`reports.updated_by_user_id`, RESTRICT). 그래서 리포트를 만들었거나 마지막으로 수정한 사용자를 삭제하면 퇴사 처리되고(US-R17, 결과 `resigned`) 리포트는 남는다. 목록·상세의 `owner`·`updated_by`는 "<이름>(퇴사)"로 보이고, 퇴사자가 만든 공개 리포트도 다른 사용자가 열고 실행한다. 퇴사·삭제 판정 규칙은 US-R17이 가지고, 리포트 때문에 퇴사되는 결과 케이스(RS-047)는 RS가 가진다.
- **RS-R25** `reports` 테이블의 컬럼·제약은 2.2 표와 같다(head 스키마).

경로 공통
- **RS-R26** 7개 경로(11개 메서드)는 로그인한 모든 역할이 쓰고(미인증 401, PL-R5) 역할 가드가 없다(PL-R6). 상태 변경 메서드는 CSRF 헤더가 필요하다(PL-R9). `{report_id}`는 id 경로 규칙(PL-R15, 잘못되면 422 `request-validation`)이다. `/reports/fields`·`/reports/query`(RQ-R1)가 `/reports/{report_id}`보다 먼저 맞는다. openapi: 성공 코드 `GET`·`PUT` 200, `POST /reports`·`/copy` 201, `DELETE` 204, `/run` 200(응답 스키마 = 조회 응답). 문서화한 오류: 상세 404·422, 덮어쓰기·배치 403·404·409·422, 삭제 403·404·422, 복제 404·409·422, 실행 404·422·503, 만들기 409·422. 요청 스키마에 SQL 필드가 없고, `revision`은 정수 최소 1, 상세 응답의 `layout`은 필수, 목록 항목에는 `layout`이 없다.

화면 (frontend)
- **RS-R27** 목록 `/reports`: 읽는 동안 "불러오는 중…". 제목(h1) "Reports"와 링크 "+ 새 리포트"(`/reports/new`, 모든 역할). 목록 오류는 오류 배너(PL-R37). 볼 수 있는 리포트가 없으면 "아직 저장한 리포트가 없습니다. 새 리포트를 만들어 조건에 맞는 Deal을 조회해 보세요."(필터를 보이지 않음). 있으면 필터 "이름·설명 검색"(이름 또는 설명에 부분 일치, 대소문자 무시, 앞뒤 공백 무시)과 "리포트 범위"("전체 리포트" / "내가 만든 리포트" = 만든 사람이 나)이고 둘은 주소 `?q=<검색어>&mine=1`(값이 있을 때만, 이력 교체)에 남고 주소에서 복원된다. 거른 순서는 서버 순서 그대로다. 남는 것이 없으면 "조건에 맞는 리포트가 없습니다.". 표(캡션 "리포트 목록") 열: 이름(링크 `/reports/<id>`, 비공개면 태그 "비공개"), 설명, 데이터(태그 "Deal" 항상 + `action`이 있으면 "Actions"), 차트(종류 라벨 RC-R37, 없으면 "—"), 만든 사람(UserRef `label`), 최종 수정(`formatStamp`(TM-R14) + 최종 수정자 ≠ 만든 사람이면 " 수정: <label>"), ⋯ 메뉴.
- **RS-R28** ⋯ 메뉴: 버튼 "<이름> 메뉴"(`aria-haspopup="menu"`, `aria-expanded`), 항목 "열기"(`/reports/<id>`), "편집"(`/reports/<id>/edit`, `canEditReport`일 때만), "복제", "삭제"(`canDeleteReport`일 때만). 단추로 여닫고, Escape는 닫고 포커스를 단추로 돌리며, 바깥 클릭과 항목 선택도 닫는다. 화면 판단 함수(`shared/model/permissions.ts`)는 RS-R5~R8과 같다: `canViewReport` = admin·만든 사람·공개, `canEditReport` = `canViewReport`, `canDeleteReport` = `canChangeReportVisibility` = admin·만든 사람.
- **RS-R29** 삭제(목록 메뉴·보기 화면 "삭제"): 확인 창 제목 "리포트 삭제", 문구 "‘<이름>’ 리포트를 삭제할까요? 되돌릴 수 없습니다.", 버튼 "삭제"(위험)·"취소". 삭제하면 목록에서는 행이 사라지고(마지막이면 빈 안내), 보기 화면에서는 `/reports`로 간다. 실패는 창 안 오류 배너. 취소는 요청을 보내지 않는다.
- **RS-R30** 저장 대화상자(제목 "리포트 저장", 모드 `create`·`overwrite`·`saveAs`·`copy`): 기본값은 create = 빈 이름·빈 설명·공개, overwrite = 지금 리포트의 이름·설명·공개 범위, saveAs·copy = "<이름> 복사본"(100자로 자름)·원래 설명·공개. 칸: "이름"(필수, 최대 100자), "설명"(최대 1,000자), "공개 범위"("모든 사용자에게 보임"/"나만 보기"). overwrite에서 요청자가 공개 범위를 바꿀 수 없으면(RS-R7) 선택이 잠기고 "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다"가 보인다(다른 모드는 항상 바꿀 수 있음). 안내 "저장 내용: 컬럼·조건·정렬·행 수·차트 설정과 생성 SQL. 결과 데이터는 저장하지 않고 열 때마다 다시 조회합니다.". 이름이 공백뿐이면 요청 없이 이름 칸 아래 "이름을 입력하세요". 실패 표시: 이름 중복(409 `already-exists`) = 이름 칸 아래 서버 문구, 저장 충돌(409 `invalid-state`) = 알림에 서버 문구 + "다른 이름으로 저장" 버튼(편집 화면) + 아래 버튼은 "닫기"뿐, 정의 위반(422 `invalid-report`) = create·overwrite·saveAs는 대화상자를 닫고 디자이너에 위반을 보이며(표시는 RQ-R49) 첫 위반 위치가 `chart`면 결과 탭으로 가서 차트 설정을 연다(RC-R33), copy는 창 안에 "원본 설계가 지금 규칙과 맞지 않아 복제할 수 없습니다. 편집에서 고치세요. <서버 문구>", 그 밖 = 창 안에 서버 문구. 요청 중에는 "저장"·"취소"가 비활성이고 Esc·닫기로 닫히지 않는다.
- **RS-R31** 디자이너의 저장: 머리 버튼은 새 리포트 화면 "초기화"·"저장", 편집 화면 "되돌리기"·"다른 이름으로 저장"·"저장". "저장"은 조회가 성공했고 그 뒤 설계를 바꾸지 않았으며 조회 중이 아닐 때만 켜지고, 꺼져 있으면 `title` "먼저 조회하세요"(결과 없음) 또는 "바뀐 설계를 다시 조회한 뒤 저장하세요". 새 리포트의 "저장"과 "다른 이름으로 저장"은 만들기 요청(정의·차트·배치를 항상 보냄)을 보내고, 성공하면 `/reports/<새 id>/edit`로 이력을 교체해 간다: 방금 결과가 지금 설계로 조회한 것이면 새 편집 화면이 그 결과를 넘겨받아 다시 조회하지 않고 저장 전에 보던 탭으로 열리며, 아니면 작성 탭으로 열려 자동 조회한다. 편집 화면의 "저장"은 덮어쓰기(`revision` = 화면의 기준 리포트 revision)이고 화면에 머문다: 제목이 새 이름을 따르고, 기준선이 서버 응답이 되며, 다시 조회하지 않는다. 화면의 기준 리포트(revision·대화상자 기본값)는 처음 불러온 값이고 **내 덮어쓰기 응답으로만** 바뀐다(다른 사람의 저장으로 상세를 다시 받아도 따라가지 않아, 그 뒤 덮어쓰기는 409가 된다).
- **RS-R32** "● 저장 안 됨"(`role=status`, 제목 옆): 새 리포트 화면은 설계가 빈 설계와 다를 때(보기·배치만 바꾼 것으로는 붙지 않음), 편집 화면은 설계(정의·차트·보기·배치)가 기준선과 다를 때 붙고(차트 부분은 RC-R38), 되돌리면 사라진다. 떠날 때 확인(저장 안 됨일 때만): 앱 안의 링크를 누르면 확인 창 "저장하지 않은 변경이 있습니다" / "저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?", "떠나기"(이동)·"머물기"(남음). 새로고침·탭 닫기는 브라우저 확인(`beforeunload`)이며 저장 안 됨일 때만 막는다. 브라우저 뒤로·앞으로 가기로 다른 경로로 가려 할 때도 같은 확인 창을 보이고("떠나기"는 멈춘 이동을 마저 함, "머물기"는 주소·설계 그대로, 규칙은 RQ-R54와 같음, 2026-11-18). 로그아웃과 코드의 직접 이동은 묻지 않는다. 덮어쓰기·첫 저장·되돌리기 직후에는 묻지 않는다.
- **RS-R33** 되돌리기/초기화: 편집 화면 "되돌리기"는 저장 안 됨이 아니면 아무것도 하지 않는다(결과·저장 버튼 그대로). 저장 안 됨이면 확인 창 "저장된 설계로 되돌릴까요?" / "저장하지 않은 변경이 사라집니다." "되돌리기"·"취소". 되돌리면 기준선(마지막 덮어쓰기 기준)의 정의·차트(차트 부분은 RC-R38)·배치로 돌아가며, 조회가 달라지는 설계가 같으면 결과를 유지하고(차트·배치만 되돌림) 다르면 결과를 지운다. 새 리포트 화면 "초기화"는 저장 안 됨이 아니면(보기·배치만 바꾼 경우 포함) 확인 없이 설계·배치를 기본으로, 저장 안 됨이면 확인 창 "설계를 모두 지울까요?" / "컬럼과 조건이 모두 사라집니다." "초기화"·"취소" 뒤 설계·배치를 기본으로 되돌린다.
- **RS-R34** 편집 화면 `/reports/:id/edit`: 주소 id가 정수 1~2^53−1이 아니거나(`abc`, `0`, `1.5` 등) 상세가 404면 안내 화면(h1 "Reports", "리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.", 링크 "리포트 목록"). 그 밖의 상세·카탈로그 오류(깨진 정의 422 포함)는 오류 배너만. 수정 권한이 없으면 "<이름>", "수정 권한이 없습니다.", 링크 "리포트 보기"(지금 규칙으로는 닿지 않는 방어). 열리면 저장된 정의·차트·배치를 디자이너에 싣고 **작성 탭**으로 열어(RS-R31의 넘겨받기 예외) 한 번 자동 조회하며 결과 탭으로 옮기지 않는다. 그 뒤 스스로 다시 조회하지 않는다. 남의 공개 리포트도 열린다.
- **RS-R35** 보기 화면 `/reports/:id`: 주소 id가 잘못이거나 404면 RS-R34의 안내 화면이고 실행 요청을 보내지 않는다. 그 밖의 상세 오류(깨진 정의 422 포함)는 오류 배너만 보인다. 열리면: 경로 "Reports ›", h1 이름, 비공개 태그, 설명(있을 때), 메타 "<만든 사람 label> · <수정 시각 formatStamp>" + 최종 수정자 ≠ 만든 사람이면 " (수정: <label>)". 버튼 "다시 조회"(실행 중 비활성), "편집"(`canEditReport`), "복제", "삭제"(`canDeleteReport`). 열 때마다(화면에 들어올 때마다) 저장 리포트를 실행하고 창 포커스로는 다시 실행하지 않는다. 실행 실패: 정의 위반(422 `invalid-report`)이면 알림 "저장된 설계가 지금 규칙과 맞지 않습니다. 편집에서 고치세요"와 위반 문구 목록(없으면 서버 문구)이고 결과 표가 없으며 "편집"은 그대로 있다. 그 밖(시간 초과 포함)은 서버 문구 알림이고 "다시 조회"로 다시 한다. 결과는 저장된 배치로 그린 결과 영역(RS-R37)이고 차트 타일은 저장 차트를 읽기 전용으로 그린다(RC-R36). 탭·차트 설정·저장 버튼은 없다.
- **RS-R36** 디자이너 탭: `tablist` "리포트 디자이너"의 탭 "작성"·"결과"(그 탭에 보일 위반이 있으면 "<이름> (고칠 곳 N)", 수는 RQ-R39·RQ-R49가 정하며 차트 위치 위반은 결과 탭 수 — RC-R33). 새 리포트·편집 화면은 작성 탭으로 연다(RS-R31 예외). ←/→ 키로 다른 탭으로 가고 포커스도 옮긴다. 비활성 패널은 `hidden`으로 DOM에 남아 표 페이지·합계 행 선택·설계·보기·배치가 탭을 오가도 유지된다. "조회"가 성공하면 결과 탭으로 간다(두 번째 조회도). 실패·입력 문제면 작성 탭에 머물고 결과 탭에는 이전 결과가 남는다. 결과 탭 = 보기 선택·타일·생성 SQL(RQ-R53). 조회 전 결과 탭의 표 타일은 "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요."이고 보기·배치는 바꿀 수 있다. 보기·배치 변경은 "설계가 바뀌었습니다…" 안내를 띄우지 않고 저장 버튼을 끄지 않는다(행 수 등 조회 설계 변경은 띄움, RQ-R52).
- **RS-R37** 보기 선택과 보이는 타일: `radiogroup` "보기"의 "표+차트"·"차트만"·"표만". 보기 화면에서 저장 차트가 없거나 읽을 수 없으면 차트를 쓸 수 없어 표 타일만 보이고 "표+차트"·"차트만"은 비활성(`title` "저장된 차트가 없습니다"), 화면의 보기는 "표만"이지만 저장된 배치는 바꾸지 않는다. 그 밖에는 `order` 순서 중 보기에 맞는 타일이 보인다(디자이너는 차트가 없어도 차트 타일에 만들기 안내를 보임, RC-R24). 타일 두 개이고 `side_by_side`면 한 줄, 아니면 두 줄이며, 화면 폭 900px 이하에서는 한 줄도 세로로 쌓는다(저장된 순서는 그대로). 타일은 `section` "표 타일"/"차트 타일"이고 머리에 제목 "표"/"차트"가 있다. 다시 조회해도 보기 선택은 유지된다.
- **RS-R38** 끌어서 놓기(타일 두 개일 때만): 타일 머리가 끄는 손잡이다. 놓는 가장자리는 대상 타일 안 상대 위치로 정한다(밖의 좌표는 가장자리로 자름): 가로 0.2 미만 = 왼쪽, 0.8 초과 = 오른쪽, 그 사이는 세로 0.5 미만 = 위, 아니면 아래(경계 0.2·0.8은 상하로, 세로 정확히 절반은 아래). 놓으면 왼쪽·위 = `[끈 타일, 대상]`, 오른쪽·아래 = `[대상, 끈 타일]`, 왼쪽·오른쪽 = 한 줄(`side_by_side`), 위·아래 = 두 줄(`stacked`)이며 보기 방식은 그대로다. 끄는 동안 대상 타일에 놓일 가장자리 표시가 붙고 포인터를 따라 옮겨지며 놓으면 지워진다. 자기 위에 놓거나 타일 밖에서 끝내면 아무것도 바뀌지 않는다. 배치 변경은 놓을 때 한 번만 일어난다(끄는 중에는 없음). 조회 결과가 없어도 놓을 수 있다.
- **RS-R39** 키보드 옮기기(타일 두 개일 때만): 각 타일 머리에 버튼 "<표|차트> 타일 옮기기"(`title` "끌어서 옮기거나 Alt+화살표 키로 옮깁니다"). Alt+→/←/↓/↑는 그 타일을 다른 타일의 오른쪽/왼쪽/아래/위에 놓는 것(RS-R38과 같은 결과)이고, 옮긴 뒤 포커스는 같은 버튼에 남으며 화면 읽기 영역에 "<표|차트>를 <차트|표> <오른쪽에|왼쪽에|위에|아래에> 놓았습니다(<한 줄|두 줄>)"를 알린다. Alt 없는 화살표는 아무것도 하지 않는다. 타일이 하나면 버튼이 없다.
- **RS-R40** 디자이너의 배치: 화면 상태에만 두고 바꿔도 요청을 보내지 않는다(저장 버튼으로만 저장). 새 리포트 저장·다른 이름으로 저장·덮어쓰기 요청에 항상 `layout`을 보낸다(손대지 않았으면 기본 배치). 편집 화면은 저장된 배치로 열리고(배치가 없던 리포트는 기본), 저장해 넘어간 새 편집 화면도 저장한 배치로 열린다. 배치만 바꾼 덮어쓰기는 다시 조회하지 않는다. 결과 탭의 배치 변경은 작성 탭의 컬럼·조건을 바꾸지 않고, 작성 탭 변경도 배치를 바꾸지 않는다.
- **RS-R41** 보기 화면 배치 자동 저장(`canEditReport`): 보기 선택·놓기·키보드 옮기기마다 화면 배치를 바꾸고, 그 값이 확인된 배치와 다르면 `PUT /reports/{id}/layout`(확인된 revision)을 보낸다. 같으면 보내지 않는다. 요청은 한 번에 하나이며, 요청 중에 바뀐 값은 마지막 하나(대기 값)만 기억했다가 응답의 revision으로 이어 보낸다(대기 값이 응답 배치와 같으면 보내지 않음). 화면 배치는 응답으로 덮어쓰지 않는다. 상태 줄(`role=status`)은 요청 중 "배치 저장 중…", 끝나면 "배치를 저장했습니다"이고 다음 변경에서 지워진다. 성공 응답으로 머리의 최종 수정자·시각과 목록이 갱신되고 결과는 다시 조회하지 않는다. 저장 중(요청 중이거나 대기 값이 있음)에는 "편집"이 `aria-disabled`이고 눌러도 이동하지 않으며 "복제"가 비활성이고 둘 다 `title` "배치를 저장하는 중입니다"다. "다시 조회"는 영향이 없다. 저장 요청 중에 화면을 떠나면 마지막 변경은 저장되지 않을 수 있다. "한 번에 하나·마지막 값"은 한 화면 안의 순차 규칙이고 경쟁(동시성) 규칙이 아니다 — RS-096은 Fake gate로 응답 순서를 고정한 순차 시나리오로 검증한다(2026-11-11 결정).
- **RS-R42** 자동 저장 실패: 409 → 멈추고 재시도하지 않으며 대기 값을 버리고, 최신 리포트를 다시 읽어 화면 배치를 그 값으로 바꾸고 결과를 다시 조회하며, 알림 "다른 사람이 이 리포트를 먼저 수정해 최신 내용을 다시 불러왔습니다. 내가 바꾼 배치는 저장되지 않았습니다. 필요하면 배치를 다시 바꾸세요."를 보인다. 다시 읽는 동안 바꾼 값은 보내지 않고, 그 뒤의 변경은 새 revision으로 저장한다. 403 → 화면 배치를 유지하고 알림 "이 리포트를 수정할 권한이 없어 배치를 저장하지 못했습니다. 바꾼 배치는 이 화면에서만 유지됩니다.", 이후 요청 없음. 404 → 알림 "리포트를 찾을 수 없어 배치를 저장하지 못했습니다. 목록에서 다시 확인하세요." + 링크 "리포트 목록", 이후 요청 없음. 그 밖 → 알림 "배치를 저장하지 못했습니다. 잠시 뒤 다시 시도하세요." + 버튼 "다시 시도"(지금 화면 배치를 마지막 확인 revision으로 보내고 알림을 지움). 자동 재시도는 없고 다음 변경도 마지막 확인 revision으로 보낸다. 대기 값 저장이 실패하면 실패 상태로 끝나고 버튼은 다시 켜진다.
- **RS-R43** 수정 권한이 없는 보기 화면(지금 규칙으로는 닿지 않는 방어): 보기 선택 줄에 "보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다", 보기·배치는 화면에서만 바뀌고 요청이 없으며 "편집"이 없다.
- **RS-R44** 복제(목록 메뉴·보기 화면): copy 모드 대화상자(RS-R30). 성공하면 `/reports/<새 id>/edit`로 간다. 요청 본문은 메타뿐이다(정의·차트·배치 없음, 서버가 원본 것을 쓴다). 취소하면 요청이 없다.
- **RS-R45** 게이트웨이(`gateway/http/reports.ts`의 저장 리포트 부분): `list()` = `GET /reports` → 요약(camelCase: `updatedBy`, `createdAt`, `updatedAt`, `chartKind`, 배치 없음), `get(id)` = `GET /reports/{id}` → 상세(정의·`generatedSql`·`chart`·`chartProblem`·`layout` 그대로), `create(input)` = `POST /reports`, `update(id, input)` = `PUT /reports/{id}`(본문에 `revision`, 차트가 없으면 `chart: null` — RC-R38·RC-R39), `copy(id, meta)` = `POST /reports/{id}/copy`(메타만), `remove(id)` = `DELETE` → 본문 없이 성공, `run(id)` = `POST /reports/{id}/run` → 조회 결과와 같은 변환(RQ-R55), `saveReportLayout(id, {layout, revision})` = `PUT /reports/{id}/layout`(그 두 키만). 요청 본문은 snake_case이고 SQL·id·만든 사람을 보내지 않는다. 오류: 409는 서버 kind(`already-exists`·`invalid-state`)를 **그대로** 두고(PL-R39의 예외 — 화면이 이름 중복과 저장 충돌을 구분), `invalid-report`의 `errors`는 `reportErrors`(위치·code·문구)로 옮기며, `report-timeout`, 연결 실패는 PL-R39의 네트워크 오류다.
- **RS-R46** 화면 데이터 캐시(`data/reports.ts`): 목록·상세·실행은 실패해도 재시도하지 않는다. 실행은 데이터를 항상 낡은 것으로 보아 화면에 들어올 때마다 다시 실행하고 창 포커스로는 다시 실행하지 않는다. 만들기·덮어쓰기·복제 성공 → 응답을 상세 캐시에 넣고 그 리포트의 실행 캐시를 지우며 목록을 다시 받는다(필드 카탈로그는 다시 받지 않음). 배치 저장 성공 → 상세 캐시를 응답으로 바꾸고 목록을 다시 받는다(실행 캐시는 그대로). 삭제 성공 → 상세·실행 캐시를 지우고 목록을 다시 받는다. 저장 실패 분류(`saveFailure`): `already-exists` = 이름, `invalid-state` = 충돌, `invalid-report` = 위반(항목, 없으면 빈 목록), `forbidden` = 권한, `not-found` = 없음, 그 밖 = 기타(문구는 PL-R37).
- **RS-R47** 화면 테스트용 Fake 게이트웨이(`test/fake/gateway/savedReports.ts`)는 서버 규칙(RS-R1~R24)과 같은 결과를 낸다. 서버와 다르던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**: ① 덮어쓰기 판정 순서는 서버(RS-R12)와 같이 404 → 422 → 403(수정) → 403(공개 범위) → 409(revision) → 409(이름)이다(예전 Fake는 revision 409가 공개 범위 403보다 먼저였음). ② 깨진 저장 정의를 시드로 만들 수 있고, 그 리포트는 목록에 `entities` `[]`로 남으며 상세·실행·복제·배치 저장은 보기 판정(404) 뒤 RS-R17의 422 `invalid-report`(`detail` "저장된 리포트 정의를 읽을 수 없습니다.", `errors` `[{location: ["definition"], code: "stored-invalid", message: "저장된 리포트 정의를 읽을 수 없습니다."}]`)이고, 새 정의로 덮어쓰면(revision 검사 유지) 복구되며 삭제할 수 있다. ③ 이름·설명의 NUL 거절은 RS-R2와 같은 문구("리포트 이름에는 NUL 문자를 쓸 수 없습니다"·"설명에는 NUL 문자를 쓸 수 없습니다")이고 NUL 검사가 빈 이름·길이 검사보다 먼저다(예전 Fake는 이름 NUL을 "리포트 이름을 입력하세요.", 설명 NUL을 길이 문구로 거절). 차트 부분의 Fake 규칙은 RC-R57이다.

### 2.4 상태와 전이

리포트: 없음 → (만들기·복제) → 있음(revision 1) → (덮어쓰기·배치 저장) → 있음(revision n+1) → (삭제) → 없음. 깨진 저장 정의는 "있음"의 하위 상태이며 덮어쓰기로만 정상이 된다(목록·삭제는 가능, 상세·실행·복제·배치 저장은 422).

보기 화면 자동 저장(한 화면 세션): `idle` → (다른 값으로 변경) → `saving`(요청 1개, 대기 값 0~1개) → `saved` | `conflict`(다시 읽는 중 → 다시 바꿀 수 있음) | `forbidden`·`notFound`(멈춤, 이후 요청 없음) | `failed`("다시 시도"·다음 변경으로 `saving`). `saved`에서 다음 변경은 `saving` 또는 `idle`(확인된 배치와 같으면).

편집 화면: 기준선과 같음 ⇄ 저장 안 됨(변경·되돌리기), 저장 안 됨 → (덮어쓰기) → 같음(새 기준선).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /reports`(목록) | 401 | 공개 + 자기 것 | 공개 + 자기 것 | 전부 |
| `GET /reports/{id}`, `POST /reports/{id}/run`, `POST /reports/{id}/copy` | 401 | 공개·자기 것, 남의 비공개 404 | 같음 | 전부 |
| `POST /reports`(만들기) | 401 | 가능 | 가능 | 가능 |
| `PUT /reports/{id}`, `PUT /reports/{id}/layout` | 401 | 공개·자기 것, 남의 비공개 404 | 같음 | 전부 |
| 덮어쓰기에서 공개 범위 변경 | 401 | 자기 것만(남의 공개 403) | 같음 | 전부 |
| `DELETE /reports/{id}` | 401 | 자기 것(남의 공개 403, 남의 비공개 404) | 같음 | 전부 |
| 화면 `/reports`, `/reports/:id`, `/reports/:id/edit` | `/login`으로 | 가능 | 가능 | 가능 |

모든 경로는 역할 가드가 없는 저장 리포트 분류(PL-R2)이고 상태 변경 메서드는 CSRF 헤더가 필요하다(PL-R9).

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/reports` | — | 200 `ReportSummary[]` | 401 |
| POST `/reports` | `{name, description?: "", visibility, definition, chart?: Chart\|null, layout?: Layout\|null}` | 201 `ReportDetail`, `Location` | 401, 403 `csrf`, 409 `already-exists`, 422 `request-validation`·`invalid-value`·`invalid-report` |
| GET `/reports/{report_id}` | path id | 200 `ReportDetail` | 401, 404 `not-found`, 422 `request-validation`·`invalid-report`(stored-invalid) |
| PUT `/reports/{report_id}` | `{name, description?, visibility, definition, chart?, layout?, revision ≥ 1}` | 200 `ReportDetail` | 401, 403 `csrf`·`forbidden`, 404, 409 `invalid-state`·`already-exists`, 422 |
| PUT `/reports/{report_id}/layout` | `{layout: Layout, revision ≥ 1}` | 200 `ReportDetail` | 401, 403, 404, 409 `invalid-state`, 422 `request-validation`·`invalid-report` |
| DELETE `/reports/{report_id}` | — | 204 | 401, 403 `csrf`·`forbidden`, 404, 422 `request-validation` |
| POST `/reports/{report_id}/copy` | `{name, description?: "", visibility}` | 201 `ReportDetail`, `Location` | 401, 403 `csrf`, 404, 409 `already-exists`, 422 |
| POST `/reports/{report_id}/run` | — | 200 조회 응답(RQ-R36) | 401, 403 `csrf`, 404, 422 `invalid-report`, 503 `report-timeout` |

- `ReportSummary` = `{id, name, description, visibility: "public"|"private", owner: UserRef, updated_by: UserRef, entities: ("deal"|"action")[], created_at, updated_at, chart_kind: ChartKind|null}`.
- `ReportDetail` = `ReportSummary` + `{revision: int, definition, generated_sql: str, chart: Chart|null, chart_problem: str|null, layout: Layout}`.
- `Layout` = `{view: "both"|"chart"|"table", order: [tile, tile](길이 2), arrange: "side_by_side"|"stacked"}`. 요청의 `Layout`은 세 키 필수·모르는 키 금지. `Chart`의 모양·값은 RC-R23, `definition`은 RQ-R7(저장 형식은 RQ-R57).
- `invalid-report` 오류 본문 = Problem(PL-R10) + `errors: [{location: (str|int)[], code: str, message: str}]`, `detail` = 첫 위반 문구.

### 2.7 화면 동작

RS-R27~RS-R47.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 없거나 볼 수 없는 리포트 | 404 `not-found` | 리포트를 찾을 수 없습니다. |
| 이름 비어 있음 / 101자 이상 | 422 `invalid-value` | 리포트 이름을 입력하세요. / 리포트 이름은 100자 이내로 입력하세요. |
| 설명 1,001자 이상 | 422 `invalid-value` | 설명은 1,000자 이내로 입력하세요. |
| 이름·설명 NUL | 422 `invalid-value` | 리포트 이름에는 NUL 문자를 쓸 수 없습니다 / 설명에는 NUL 문자를 쓸 수 없습니다 |
| 공개 범위 값 | 422 `invalid-value` | 공개 범위는 public 또는 private입니다. |
| 정의·차트·배치 값 위반 | 422 `invalid-report` | 첫 위반 문구(배치는 RS-R20, 정의는 RQ-R8, 차트는 RC-R5) |
| 깨진 저장 정의 | 422 `invalid-report`(code `stored-invalid`) | 저장된 리포트 정의를 읽을 수 없습니다. |
| 모양 오류(키·타입·revision) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12) |
| 이름 중복 | 409 `already-exists` | 같은 이름의 리포트가 이미 있습니다. |
| revision 불일치 | 409 `invalid-state` | 다른 사용자가 먼저 이 리포트를 저장했습니다. 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요. |
| 공개 범위 변경 권한 | 403 `forbidden` | 공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다. |
| 삭제 권한 | 403 `forbidden` | 리포트를 만든 사람 또는 admin만 삭제할 수 있습니다. |
| 수정 권한(방어) | 403 `forbidden` | 이 리포트를 수정할 권한이 없습니다. |
| 미인증 / CSRF | 401 `unauthenticated` / 403 `csrf` | PL-R5 / PL-R9 |

화면 문구: "Reports", "+ 새 리포트", "불러오는 중…", "아직 저장한 리포트가 없습니다. 새 리포트를 만들어 조건에 맞는 Deal을 조회해 보세요.", "이름·설명 검색", "리포트 범위", "전체 리포트", "내가 만든 리포트", "조건에 맞는 리포트가 없습니다.", "비공개", "Deal", "Actions", " 수정: <이름>", "<이름> 메뉴", "열기", "편집", "복제", "삭제", "리포트 삭제", "‘<이름>’ 리포트를 삭제할까요? 되돌릴 수 없습니다.", "리포트 저장", "이름", "설명", "공개 범위", "모든 사용자에게 보임", "나만 보기", "이름을 입력하세요", "다른 이름으로 저장", "닫기", "원본 설계가 지금 규칙과 맞지 않아 복제할 수 없습니다. 편집에서 고치세요. <문구>", "<이름> 복사본", "초기화", "되돌리기", "저장", "먼저 조회하세요", "바뀐 설계를 다시 조회한 뒤 저장하세요", "● 저장 안 됨", "저장하지 않은 변경이 있습니다", "저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?", "떠나기", "머물기", "저장된 설계로 되돌릴까요?", "저장하지 않은 변경이 사라집니다.", "설계를 모두 지울까요?", "컬럼과 조건이 모두 사라집니다.", "리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.", "리포트 목록", "수정 권한이 없습니다.", "리포트 보기", "다시 조회", "저장된 설계가 지금 규칙과 맞지 않습니다. 편집에서 고치세요", "작성", "결과", "(고칠 곳 N)", "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요.", "보기", "표+차트", "차트만", "표만", "저장된 차트가 없습니다", "표 타일", "차트 타일", "<표|차트> 타일 옮기기", "끌어서 옮기거나 Alt+화살표 키로 옮깁니다", "<표|차트>를 <차트|표> <방향> 놓았습니다(<한 줄|두 줄>)", "배치 저장 중…", "배치를 저장했습니다", "배치를 저장하는 중입니다", RS-R42의 알림 네 가지, "다시 시도", "보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다". 서버 문구 표시는 PL-R37.

## 3. Business use case

### RS-UC1 리포트 저장(새로·다른 이름으로·덮어쓰기)
- 행위자: 로그인한 모든 역할
- 사전 조건: 디자이너에서 조회가 성공했고 그 뒤 설계를 바꾸지 않음
- 기본 흐름: "저장"을 누른다 → 대화상자에 이름·설명·공개 범위를 넣는다 → 서버가 메타·정의·차트·배치를 검증하고 SQL을 만들어 저장한다 → 새 리포트면 그 편집 화면으로, 덮어쓰기면 같은 화면에 머물고 "저장 안 됨"이 사라진다(RS-R1~R4, R11~R14, R30~R33, R40)
- 대안: 편집 화면에서 "다른 이름으로 저장"으로 원본을 두고 새 리포트를 만든다, 저장 충돌 경고에서 바로 다른 이름으로 저장한다
- 예외: 이름 중복 409, 다른 사람이 먼저 저장 409, 공개 범위 403, 정의·차트·배치 위반 422(대화상자를 닫고 위반 표시), 메타 422
- 결과: revision이 정해진 저장 리포트(만든 사람·최종 수정자 기록)

### RS-UC2 저장 리포트 찾기
- 행위자: 로그인한 모든 역할
- 사전 조건: 메뉴 Reports(`/reports`)
- 기본 흐름: 볼 수 있는 리포트가 최근 수정 순으로 나온다 → 이름·설명 검색이나 "내가 만든 리포트"로 거른다 → 이름 또는 ⋯ 메뉴로 열기·편집·복제·삭제한다(RS-R5, R10, R27, R28)
- 대안: 주소(`?q=&mine=1`)로 같은 조건을 다시 연다
- 예외: 리포트가 없으면 빈 안내, 맞는 것이 없으면 안내, 목록 오류는 배너
- 결과: 요청자가 볼 수 있는 리포트만 보인다(admin은 전부)

### RS-UC3 저장 리포트 보기(다시 조회)
- 행위자: 로그인한 모든 역할
- 사전 조건: 볼 수 있는 리포트
- 기본 흐름: `/reports/:id`를 연다 → 저장된 정의를 오늘 기준으로 다시 검증·실행해 저장된 배치로 결과를 보인다 → "다시 조회"로 다시 실행한다(RS-R15, R16, R35, R37)
- 대안: 편집 화면으로 간다, 복제·삭제한다
- 예외: 없거나 볼 수 없으면 찾을 수 없음 안내, 정의가 지금 규칙과 맞지 않으면 위반 안내, 깨진 정의는 오류 배너, 시간 초과 안내
- 결과: 그 순간의 데이터로 만든 결과(아무것도 저장되지 않음)

### RS-UC4 결과 배치 바꾸기
- 행위자: 로그인한 모든 역할
- 사전 조건: 디자이너 결과 탭, 편집 화면 결과 탭, 또는 보기 화면
- 기본 흐름: 보기 방식을 고르거나 타일을 끌어 놓거나 Alt+화살표로 옮긴다(RS-R37~R39) → 디자이너·편집 화면은 화면에만 두었다가 저장 때 함께 저장한다(RS-R40) → 보기 화면은 수정할 수 있으면 바로 자동 저장한다(RS-R22, R41)
- 대안: 수정할 수 없으면 화면에서만 바뀐다(RS-R43)
- 예외: 자동 저장 409는 최신 배치로 돌아감, 403·404는 멈춤, 그 밖의 실패는 "다시 시도"(RS-R42)
- 결과: 다음에 열면 저장된 배치로 보인다

### RS-UC5 리포트 복제
- 행위자: 로그인한 모든 역할
- 사전 조건: 볼 수 있는 리포트(목록 메뉴 또는 보기 화면)
- 기본 흐름: "복제" → 이름("<이름> 복사본")·설명·공개 범위를 정한다 → 원본 정의·차트·배치로 내 리포트가 생기고 그 편집 화면으로 간다(RS-R13, R44)
- 예외: 이름 중복 409, 원본 정의가 지금 규칙과 맞지 않으면 422 안내, 깨진 원본 422
- 결과: 원본은 그대로, 새 리포트의 만든 사람은 나

### RS-UC6 리포트 삭제
- 행위자: 만든 사람 또는 admin
- 사전 조건: 볼 수 있는 리포트
- 기본 흐름: "삭제" → 확인 → 물리 삭제되고 목록에서 사라진다(RS-R8, R18, R29)
- 예외: 남의 공개 리포트는 403(화면은 메뉴를 보이지 않음), 취소하면 그대로
- 결과: 모든 사람에게서 사라진다

### RS-UC7 리포트 작성자 삭제(퇴사)
- 행위자: admin(사용자 관리)
- 사전 조건: 사용자가 리포트를 만들었거나 마지막으로 수정함
- 기본 흐름: 그 사용자를 삭제한다 → 퇴사 처리되고 리포트는 남아 "<이름>(퇴사)"로 보인다(RS-R24, US-R17)
- 결과: 다른 사용자가 그 리포트를 계속 열고 실행한다

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), ALICE·BOB(sales), VIEWER(user). 정의 예: SIMPLE = 컬럼 `deal.code`·`deal.amount`(행 100), OTHER = `deal.vendor`(그룹핑)·`deal.amount`(행 100). 배치 예: DEFAULT `{both, [table, chart], stacked}`, CHART_SIDE `{chart, [chart, table], side_by_side}`, TABLE_ONLY `{table, [table, chart], stacked}`, BOTH_SIDE `{both, [table, chart], side_by_side}`. backend 케이스는 Fake UoW(`FakeReportRepository`, 사용자 Fake·사용자 연결, Fake 조회 실행기, 고정 Clock)를 쓰는 유스케이스 단위 테스트, FakeUseCases + TestClient를 쓰는 web 단위 테스트, 그리고 Fake와 SQL에 함께 도는 Repository 계약·스키마 테스트(integration 표시)다. frontend 케이스는 Fake 게이트웨이(`test/fake/gateway/savedReports.ts`, 배치 저장 응답을 잡아 두는 gate)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| RS-001 | 모든 역할이 리포트를 만들고 만든 사람·최종 수정자는 요청자, revision 1, 201과 Location이다 | RS-R9, RS-R14, RS-UC1 | backend | `application/test_saved_report_create.py`, `web/test_saved_report_routes.py` |
| RS-002 | 저장하면 서버가 정의로 만든 SQL과 조건을 함께 저장하고 다시 열어도 같다 | RS-R1, RS-R4, RS-UC1 | backend | `application/test_saved_report_create.py`, `web/test_saved_report_routes.py` |
| RS-003 | 본문에 SQL 같은 모르는 키나 모양 오류가 있으면 422 request-validation이고 저장되지 않는다 | RS-R1, RS-UC1 | backend | `web/test_saved_report_routes.py`, `web/test_saved_report_validation.py` |
| RS-004 | 이름·설명은 앞뒤 공백을 지워 저장하고 100자·1,000자는 받는다 | RS-R2, RS-UC1 | backend | `application/test_saved_report_create.py`, `web/test_saved_report_validation.py` |
| RS-005 | 빈 이름·101자 이름·1,001자 설명·NUL·알 수 없는 공개 범위는 422 invalid-value 문구이고 저장되지 않는다 | RS-R2, RS-R47, RS-UC1 | both | `application/test_saved_report_create.py`, `gateway/contract/savedReports.contract.ts`, `test/fake/gateway/savedReports.test.ts`, `web/test_saved_report_validation.py` |
| RS-006 | 규칙을 어긴 정의는 422 invalid-report(위치·code)이고 저장되지 않는다 | RS-R4, RS-UC1 | backend | `application/test_saved_report_create.py`, `web/test_saved_report_validation.py` |
| RS-007 | 메타 오류가 먼저이고 정의 위반이면 차트·배치를, 차트 위반이면 배치를 검사하지 않는다 | RS-R4, RS-UC1 | backend | `application/test_saved_report_create.py`, `application/test_saved_report_layout.py` |
| RS-008 | 대소문자만 다른 이름은 자기 것·남의 것·남의 비공개 리포트와도 409 already-exists다 | RS-R3, RS-UC1 | backend | `application/test_saved_report_create.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-009 | 이름은 공백을 지운 뒤 비교하고 자기 이름의 대소문자 변경과 지운 리포트 이름 재사용은 된다 | RS-R3, RS-UC1 | backend | `application/test_saved_report_create.py`, `application/test_saved_report_update.py`, `repositories/test_saved_report_repository_contract.py` |
| RS-010 | 목록은 공개·자기 리포트만 최근 수정 순(동률 id 내림차순)이고 정의·배치가 없다 | RS-R5, RS-R10, RS-UC2 | backend | `application/test_saved_report_list_get.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_layout_routes.py`, `web/test_saved_report_routes.py` |
| RS-011 | admin의 목록에는 남의 비공개 리포트도 있다 | RS-R5, RS-R10, RS-UC2 | backend | `application/test_saved_report_list_get.py`, `web/test_saved_report_routes.py` |
| RS-012 | 목록 항목의 데이터는 정의가 쓰는 deal·action이다 | RS-R10, RS-UC2 | backend | `application/test_saved_report_list_get.py`, `domain/test_saved_report_entity.py` |
| RS-013 | 볼 수 있는 리포트의 상세는 정의·SQL·revision·차트·배치를 담는다 | RS-R15, RS-UC3 | backend | `application/test_saved_report_list_get.py`, `web/test_saved_report_routes.py` |
| RS-014 | 남의 비공개 리포트는 여섯 동작 모두 없는 id와 같은 404이고 그대로다 | RS-R5, RS-UC3 | backend | `application/test_saved_report_copy.py`, `application/test_saved_report_delete.py`, `application/test_saved_report_layout.py`, `application/test_saved_report_list_get.py`, `application/test_saved_report_run.py`, `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `domain/test_saved_report_layout_entity.py`, `web/test_saved_report_layout_routes.py`, `web/test_saved_report_routes.py` |
| RS-015 | admin은 남의 비공개 리포트를 열고 실행·덮어쓰기·배치 저장·복제·삭제한다 | RS-R5, RS-R6, RS-R8 | backend | `application/test_saved_report_copy.py`, `application/test_saved_report_delete.py`, `application/test_saved_report_layout.py`, `application/test_saved_report_list_get.py`, `application/test_saved_report_run.py`, `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py` |
| RS-016 | 덮어쓰면 내용·SQL이 바뀌고 revision이 오르며 만든 사람·생성 시각은 그대로다 | RS-R12, RS-UC1 | backend | `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-017 | sales·user도 남의 공개 리포트를 덮어쓰고 최종 수정자가 된다 | RS-R6, RS-R12, RS-UC1 | backend | `application/test_saved_report_update.py`, `web/test_saved_report_routes.py` |
| RS-018 | 저장된 것과 다른 revision으로 덮어쓰면 409 invalid-state이고 그대로다 | RS-R11, RS-UC1 | backend | `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `web/test_saved_report_routes.py` |
| RS-019 | 만든 사람이 아닌 편집자가 공개 범위를 바꾸면 403이고 같은 값은 된다 | RS-R7, RS-UC1 | backend | `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `web/test_saved_report_routes.py` |
| RS-020 | 만든 사람과 admin은 공개 범위를 바꾸고 비공개가 되면 남에게 404다 | RS-R7, RS-R5, RS-UC1 | backend | `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `repositories/test_saved_report_repository_contract.py` |
| RS-021 | 덮어쓰기는 404 → 422 → 403 → 409 순서로 판정한다 | RS-R12, RS-R47, RS-UC1 | both | `application/test_saved_report_update.py`, `domain/test_saved_report_entity.py`, `gateway/contract/savedReports.contract.ts`, `test/fake/gateway/savedReports.test.ts` |
| RS-022 | 다른 리포트의 이름으로 바꾸면 409 already-exists이고 그대로다 | RS-R3, RS-R12, RS-UC1 | backend | `application/test_saved_report_update.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-023 | 규칙을 어긴 정의로 덮어쓰면 422이고 저장된 리포트는 그대로다 | RS-R4, RS-R12, RS-UC1 | backend | `application/test_saved_report_update.py`, `web/test_saved_report_validation.py` |
| RS-024 | 만든 사람은 공개·비공개 자기 리포트를 지우고 그 리포트만 사라진다 | RS-R8, RS-R18, RS-UC6 | backend | `application/test_saved_report_delete.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-025 | sales·user가 남의 공개 리포트를 지우면 403이고 그대로다 | RS-R8, RS-UC6 | backend | `application/test_saved_report_delete.py`, `domain/test_saved_report_entity.py`, `web/test_saved_report_routes.py` |
| RS-026 | admin은 남의 공개·비공개 리포트를 지운다 | RS-R8, RS-UC6 | backend | `application/test_saved_report_delete.py`, `web/test_saved_report_routes.py` |
| RS-027 | 없는 리포트를 지우면 404다 | RS-R18, RS-UC6 | backend | `application/test_saved_report_delete.py`, `repositories/test_saved_report_repository_contract.py` |
| RS-028 | 복제하면 정의·배치는 원본이고 만든 사람은 요청자, revision 1이며 원본은 그대로다 | RS-R13, RS-UC5 | backend | `application/test_saved_report_copy.py`, `application/test_saved_report_layout.py`, `domain/test_saved_report_entity.py`, `domain/test_saved_report_layout_entity.py`, `web/test_saved_report_layout_routes.py`, `web/test_saved_report_routes.py` |
| RS-029 | 모든 역할이 공개 리포트를, admin은 남의 비공개 리포트도 복제하고 설명 생략은 빈 문자열이다 | RS-R9, RS-R13, RS-UC5 | backend | `application/test_saved_report_copy.py`, `web/test_saved_report_routes.py` |
| RS-030 | 복제 이름이 어떤 리포트와 겹치면 409다 | RS-R3, RS-R13, RS-UC5 | backend | `application/test_saved_report_copy.py`, `web/test_saved_report_routes.py` |
| RS-031 | 원본 정의가 지금 규칙과 맞지 않거나 메타가 틀리면 복제는 422이고 아무것도 생기지 않는다 | RS-R13, RS-UC5 | backend | `application/test_saved_report_copy.py` |
| RS-032 | 실행은 저장된 정의를 오늘 기준으로 풀어 /query와 같은 결과를 주고 아무것도 저장하지 않는다 | RS-R16, RS-UC3 | backend | `application/test_saved_report_run.py`, `web/test_saved_report_routes.py` |
| RS-033 | 다시 실행하면 저장된 결과가 아니라 그때의 데이터로 조회한다 | RS-R16, RS-UC3 | backend | `application/test_saved_report_run.py` |
| RS-034 | 지금 규칙과 맞지 않는 저장 정의의 실행은 422이고 시간 초과는 503이다 | RS-R16, RS-UC3 | backend | `application/test_saved_report_run.py`, `web/test_saved_report_routes.py` |
| RS-035 | 깨진 저장 정의 리포트는 목록에 데이터 없이 남고 남의 비공개면 숨는다 | RS-R17, RS-UC2 | backend | `application/test_saved_report_broken_definition.py`, `domain/test_saved_report_entity.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-036 | 깨진 저장 정의의 상세·실행·복제는 404 판정 뒤 422 stored-invalid이고 아무것도 실행·생성되지 않는다 | RS-R17, RS-UC3 | backend | `application/test_saved_report_broken_definition.py`, `domain/test_saved_report_entity.py`, `web/test_saved_report_routes.py` |
| RS-037 | 깨진 저장 정의 리포트는 새 정의로 덮어써 복구되고(revision 검사 유지) 지울 수 있다 | RS-R17, RS-R12, RS-R18 | backend | `application/test_saved_report_broken_definition.py`, `domain/test_saved_report_entity.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-038 | 배치를 정해 저장하면 같은 배치로 열리고 배치 없이 저장하면 기본 배치다 | RS-R14, RS-R19, RS-R23, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout_entity.py`, `repositories/test_saved_report_layout_contract.py`, `web/test_saved_report_layout_routes.py` |
| RS-039 | 저장된 배치가 NULL이거나 깨졌으면 기본 배치로 열린다 | RS-R21, RS-UC4 | backend | `domain/test_saved_report_layout.py`, `repositories/test_saved_report_layout_contract.py` |
| RS-040 | 배치 없이 덮어쓰면 저장된 배치가 남고 배치를 보내면 바뀐다 | RS-R12, RS-R23, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout_entity.py`, `repositories/test_saved_report_layout_contract.py`, `web/test_saved_report_layout_routes.py` |
| RS-041 | 배치만 저장하면 배치·수정자·시각·revision만 바뀌고 정의·차트·이름·차트 안내는 그대로다 | RS-R22, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout_entity.py`, `repositories/test_saved_report_layout_contract.py`, `web/test_saved_report_layout_routes.py` |
| RS-042 | 응답 revision으로 배치를 이어 저장하면 모두 되고 낡은 revision은 409다 | RS-R22, RS-R11, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout_entity.py`, `web/test_saved_report_layout_routes.py` |
| RS-043 | 남의 공개 리포트도 배치를 저장하고 최종 수정자가 기록된다 | RS-R22, RS-R6, RS-UC4 | backend | `application/test_saved_report_layout.py`, `web/test_saved_report_layout_routes.py` |
| RS-044 | 배치 값이 틀리면 만들기·덮어쓰기·배치 저장 모두 422 invalid-report(layout 위치 전부)이고 저장되지 않는다 | RS-R20, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout.py`, `web/test_saved_report_layout_routes.py` |
| RS-045 | 배치 요청의 모양 오류는 422 request-validation이다 | RS-R20, RS-R22, RS-UC4 | backend | `web/test_saved_report_layout_routes.py` |
| RS-046 | 배치 저장은 404 → 깨진 정의 422 → 배치 값 422 → 403 → 409 순서로 판정한다 | RS-R22, RS-UC4 | backend | `application/test_saved_report_layout.py`, `domain/test_saved_report_layout_entity.py`, `web/test_saved_report_layout_routes.py` |
| RS-047 | 리포트를 만들었거나 마지막으로 수정한 사용자를 삭제하면 퇴사 처리된다 | RS-R24, RS-UC7 | backend | `application/test_saved_report_resigned_owner.py` |
| RS-048 | 만든 사람이 퇴사해도 리포트는 남아 "(퇴사)"로 보이고 다른 사용자가 열고 실행한다 | RS-R24, RS-UC7 | backend | `application/test_saved_report_resigned_owner.py`, `repositories/test_saved_report_repository_contract.py`, `web/test_saved_report_routes.py` |
| RS-049 | reports 테이블의 컬럼·제약이 명세와 같다 | RS-R25 | backend | `infra/schema/test_reports_layout_schema.py`, `infra/schema/test_reports_schema.py` |
| RS-050 | 모든 경로는 로그인이 필요하고 쓰기는 CSRF 헤더가 필요하며 잘못된 id는 422다 | RS-R26 | backend | `web/test_saved_report_layout_routes.py`, `web/test_saved_report_routes.py` |
| RS-051 | /reports/fields·/reports/query는 리포트 id 경로에 걸리지 않는다 | RS-R26 | backend | `web/test_saved_report_routes.py` |
| RS-052 | openapi에 저장 리포트 경로·성공·오류 코드·요청·응답 필드가 명세와 같다 | RS-R26 | backend | `web/test_saved_report_layout_openapi.py`, `web/test_saved_report_openapi.py` |
| RS-053 | 모든 역할이 목록 화면을 열고 리포트가 없으면 빈 안내와 새 리포트 링크를 본다 | RS-R27, RS-UC2 | frontend | `features/reports/ReportsPage.test.tsx` |
| RS-054 | 목록 행은 이름 링크·비공개·데이터 태그·만든 사람·최종 수정과 "수정: 이름"을 보인다 | RS-R27, RS-UC2 | frontend | `features/reports/ReportsPage.test.tsx` |
| RS-055 | admin에게는 남의 비공개 리포트도 목록에 보인다 | RS-R27, RS-R5, RS-UC2 | frontend | `features/reports/ReportsPage.test.tsx` |
| RS-056 | 검색어와 "내가 만든 리포트"로 거르고 주소에 남으며 주소에서 복원된다 | RS-R27, RS-UC2 | frontend | `features/reports/ReportsPage.test.tsx`, `features/reports/list/filterReports.test.ts` |
| RS-057 | ⋯ 메뉴는 aria 상태로 여닫고 Escape·바깥 클릭으로 닫히며 편집·삭제는 권한 있을 때만 있다 | RS-R28, RS-UC2 | frontend | `features/reports/ReportsPage.test.tsx` |
| RS-058 | 목록에서 확인 뒤 삭제하면 행이 사라지고 취소하면 요청이 없다 | RS-R29, RS-UC6 | frontend | `features/reports/ReportsPage.test.tsx` |
| RS-059 | 목록·보기에서 복제하면 "복사본" 이름으로 시작해 새 리포트 편집 화면으로 간다 | RS-R30, RS-R44, RS-UC5 | frontend | `features/reports/ReportsPage.test.tsx`, `features/reports/view/ReportViewPage.test.tsx` |
| RS-060 | 복제 이름 중복·원본 규칙 위반은 대화상자 안에 보이고 취소하면 요청이 없다 | RS-R30, RS-R44, RS-UC5 | frontend | `features/reports/ReportsPage.test.tsx`, `features/reports/view/ReportViewPage.test.tsx` |
| RS-061 | 보기 화면은 열 때마다 저장된 리포트를 실행해 메타·결과·SQL을 보이고 "다시 조회"로 다시 실행한다 | RS-R35, RS-R46, RS-UC3 | frontend | `features/reports/view/ReportViewPage.test.tsx` |
| RS-062 | 보기 화면 머리에 비공개 태그·"수정: 이름"·퇴사자 표시가 있고 admin은 남의 비공개를 연다 | RS-R35, RS-UC3 | frontend | `features/reports/view/ReportViewPage.test.tsx` |
| RS-063 | 보기 화면 버튼은 권한에 따르고 삭제하면 목록으로, 편집 링크는 편집 화면으로 간다 | RS-R35, RS-R29, RS-UC3 | frontend | `features/reports/view/ReportViewPage.test.tsx` |
| RS-064 | 없는·숨긴·잘못된 id는 보기·편집 화면 모두 찾을 수 없음 안내이고 실행하지 않는다 | RS-R34, RS-R35, RS-UC3 | frontend | `features/reports/designer/ReportEditPage.test.tsx`, `features/reports/view/ReportViewPage.test.tsx` |
| RS-065 | 지금 규칙과 맞지 않는 저장 정의는 위반 안내, 시간 초과는 문구와 다시 조회다 | RS-R35, RS-UC3 | frontend | `features/reports/view/ReportViewPage.test.tsx` |
| RS-066 | 깨진 저장 정의 리포트는 보기·편집 화면에 서버 문구 배너를 보이고 목록에는 남는다 | RS-R17, RS-R34, RS-R35, RS-R47 | frontend | `features/reports/view/ReportViewPage.stored.test.tsx`, `test/fake/gateway/savedReports.test.ts` |
| RS-067 | 저장 버튼은 성공한 결과가 지금 설계와 같을 때만 켜지고 새 리포트에는 다른 이름 버튼이 없다 | RS-R31, RS-UC1 | frontend | `features/reports/ReportsPage.test.tsx`, `features/reports/designer/ReportDesignerPage.save.test.tsx` |
| RS-068 | 저장 대화상자의 기본값·안내·빈 이름 검사·취소·요청 중 잠금 | RS-R30, RS-UC1 | frontend | `features/reports/SaveReportDialog.busy.test.tsx`, `features/reports/designer/ReportDesignerPage.save.test.tsx` |
| RS-069 | 새 리포트를 저장하면 편집 화면으로 바뀌고 저장 안 됨이 없으며 user도 저장한다 | RS-R31, RS-R32, RS-UC1 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx` |
| RS-070 | 이름이 다른 리포트와 겹치면 이름 칸 아래 문구이고 디자이너에 머문다 | RS-R30, RS-R3, RS-UC1 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx`, `features/reports/designer/ReportEditPage.test.tsx` |
| RS-071 | 서버가 정의를 거절하면 대화상자를 닫고 디자이너에 위반을 보인다 | RS-R30, RS-UC1 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx` |
| RS-072 | 새 편집 화면은 지금 설계의 결과를 넘겨받아 저장 전 탭으로 열리고 설계가 바뀌었으면 다시 조회한다 | RS-R31, RS-UC1 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx`, `features/reports/designer/ReportEditPage.review.test.tsx` |
| RS-073 | 편집 화면은 저장된 설계를 작성 탭에 싣고 한 번 조회하며 스스로 다시 조회하지 않는다 | RS-R34, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.layout.test.tsx`, `features/reports/designer/ReportEditPage.test.tsx` |
| RS-074 | 덮어쓰면 저장 안 됨이 사라지고 제목이 새 이름을 따르며 다음 덮어쓰기는 응답 revision을 쓴다 | RS-R31, RS-R32, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.test.tsx` |
| RS-075 | 다른 사람이 먼저 저장했으면 충돌 경고와 "다른 이름으로 저장"이 나오고 닫아도 설계가 남는다 | RS-R30, RS-R31, RS-R11, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.test.tsx` |
| RS-076 | 상세를 다시 받아도 편집 화면의 기준 revision·대화상자 기본값은 처음 값이나 내 덮어쓰기 값이다 | RS-R31, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.review.test.tsx` |
| RS-077 | 다른 이름으로 저장은 "복사본" 이름(100자로 자름)·자유로운 공개 범위로 새 리포트를 만든다 | RS-R30, RS-R31, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.test.tsx` |
| RS-078 | 만든 사람이 아닌 편집자는 공개 범위가 잠기고 지금 값으로 덮어쓴다 | RS-R30, RS-R7, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.test.tsx` |
| RS-079 | 되돌리기는 확인 뒤 마지막으로 저장된 설계로 돌아가고 변경이 없으면 아무것도 하지 않는다 | RS-R33, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.review.test.tsx`, `features/reports/designer/ReportEditPage.test.tsx` |
| RS-080 | 설계를 바꾸면 저장 안 됨이 붙고 되돌리면 사라진다 | RS-R32, RS-UC1 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx`, `features/reports/designer/ReportEditPage.test.tsx`, `features/reports/designer/state/designKey.test.ts` |
| RS-081 | 저장 안 됨일 때만 떠날 때 확인하고 저장·되돌린 직후에는 묻지 않는다 | RS-R32, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.leave.test.tsx` |
| RS-082 | 디자이너 탭은 작성으로 열리고 화살표로 바뀌며 숨긴 패널의 화면 상태가 남는다 | RS-R36, RS-UC4 | frontend | `features/reports/designer/DesignerTabs.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx` |
| RS-083 | 조회가 성공하면 결과 탭으로 가고 실패하면 작성 탭에 머물며 이전 결과가 남는다 | RS-R36, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.tabs.test.tsx` |
| RS-084 | 조회 전 결과 탭은 안내를 보이되 보기·배치를 바꿀 수 있고 보기·배치 변경은 다시 조회를 요구하지 않는다 | RS-R36, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RS-085 | 보기 선택에 맞는 타일이 보이고 다시 조회해도 선택이 남는다 | RS-R37, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/designer/ReportDesignerPage.tabs.test.tsx`, `features/reports/result/layout.test.ts` |
| RS-086 | 타일을 다른 타일의 네 가장자리에 놓으면 순서와 한 줄/두 줄이 정해진다 | RS-R38, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/designer/state/designerState.test.ts`, `features/reports/result/layout.test.ts` |
| RS-087 | 자기 위에 놓거나 타일 밖에서 끝내면 바뀌지 않고 끄는 동안의 표시는 놓으면 지워진다 | RS-R38, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/designer/state/designerState.test.ts`, `features/reports/result/layout.test.ts` |
| RS-088 | Alt+화살표로 타일을 옮기고 포커스·안내가 남으며 타일이 하나면 옮기기 버튼이 없다 | RS-R39, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/result/layout.test.ts` |
| RS-089 | 새 리포트 화면의 배치 변경은 요청·저장 안 됨·떠날 때 확인이 없고 초기화는 배치도 기본으로 되돌린다 | RS-R40, RS-R32, RS-R33, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.layout.test.tsx`, `features/reports/designer/state/designerState.test.ts` |
| RS-090 | 새 리포트 저장 요청에 배치를 보내고 새 편집 화면은 그 배치로 열린다 | RS-R40, RS-R31, RS-UC4 | frontend | `features/reports/designer/ReportDesignerPage.save.test.tsx` |
| RS-091 | 편집 화면은 저장된 배치로 열리고 보기·배치 변경만으로 저장 안 됨·떠날 때 확인이 생긴다 | RS-R40, RS-R32, RS-UC4 | frontend | `features/reports/designer/ReportEditPage.layout.test.tsx`, `features/reports/designer/state/designKey.test.ts`, `features/reports/designer/state/designerState.test.ts`, `features/reports/designer/state/fromRequest.test.ts` |
| RS-092 | 편집 화면 배치는 스스로 저장되지 않고 덮어쓰기로 저장되며 되돌리기는 저장된 배치로 돌아간다 | RS-R40, RS-R33, RS-UC4 | frontend | `features/reports/designer/ReportEditPage.layout.test.tsx` |
| RS-093 | 보기 화면은 저장된 배치로 열리고 저장 차트가 없으면 표만 보이며 차트 보기가 비활성이다 | RS-R35, RS-R37, RS-UC4 | frontend | `features/reports/result/layout.test.ts`, `features/reports/view/ReportViewPage.layout.test.tsx` |
| RS-094 | 보기 화면에서 보기·놓기·키보드 이동은 바로 한 번 저장되고 상태 줄과 머리 메타가 바뀐다 | RS-R41, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-095 | 배치가 바뀌지 않는 선택은 요청이 없고 다음 변경은 저장됨 표시를 지운다 | RS-R41, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-096 | 요청 중의 여러 변경은 마지막 값 하나만 응답 revision으로 이어 보낸다 | RS-R41, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-097 | 배치 저장 중에는 편집·복제를 쓸 수 없고 끝나면 다시 쓸 수 있다 | RS-R41, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx` |
| RS-098 | 보기 화면에서 복제하면 저장된 배치가 복사되고 요청에는 배치가 없다 | RS-R44, RS-R13, RS-UC5 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx` |
| RS-099 | 배치 자동 저장이 409면 재시도 없이 최신 배치로 돌아가 다시 조회하고 안내한다 | RS-R42, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-100 | 배치 자동 저장이 403·404면 멈추고 안내하며 더 보내지 않는다 | RS-R42, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-101 | 그 밖의 실패는 "다시 시도"로만 다시 보내고 다음 변경은 마지막 확인 revision을 쓴다 | RS-R42, RS-UC4 | frontend | `features/reports/view/ReportViewPage.layout.test.tsx`, `features/reports/view/layoutAutosaveQueue.test.ts` |
| RS-102 | 수정 권한이 없으면 보기·배치는 화면에서만 바뀌고 요청·편집 링크가 없다 | RS-R43, RS-UC4 | frontend | `features/reports/view/ReportViewPage.readonly.test.tsx` |
| RS-103 | 게이트웨이는 저장 리포트 요청을 경로·snake_case 본문으로 보내고 응답을 camelCase로 바꾼다 | RS-R45 | frontend | `gateway/http/reports.saved.test.ts` |
| RS-104 | 게이트웨이는 409 두 kind를 구분해 두고 위반·시간 초과·연결 실패를 ApiError로 준다 | RS-R45 | frontend | `gateway/http/reports.saved.test.ts` |
| RS-105 | 게이트웨이는 배치를 그대로 옮기고 배치 저장에 layout·revision만 보낸다 | RS-R45, RS-UC4 | frontend | `gateway/http/reports.saved.test.ts` |
| RS-106 | 화면 데이터 캐시는 저장·배치 저장·삭제 뒤 정해진 캐시만 바꾸고 실패를 종류별로 나눈다 | RS-R46 | frontend | `data/savedReports.test.tsx` |
| RS-107 | 편집 화면에서 저장 안 됨일 때 뒤로 가기는 묻고 저장·되돌린 직후에는 묻지 않는다 | RS-R32, RS-UC1 | frontend | `features/reports/designer/ReportEditPage.leave.test.tsx` |

### RS-001 모든 역할이 리포트를 만들고 만든 사람·최종 수정자는 요청자, revision 1, 201과 Location이다
- Given ROOT·ALICE·VIEWER가 각각 로그인함
- When 각자 `POST /reports`로 SIMPLE 정의의 리포트("역할별-<역할>", 공개)를 만든다
- Then 모두 201이고 `Location`은 `/api/v1/reports/<응답 id>`, `revision` 1, `owner.id` = `updated_by.id` = 요청자, `created_at` = `updated_at`이며, 두 번 만든 리포트의 id는 서로 다르고, 다른 이름으로 저장한 새 리포트가 생겨도 이미 있던 리포트는 그대로다

### RS-002 저장하면 서버가 정의로 만든 SQL과 조건을 함께 저장하고 다시 열어도 같다
- Given ALICE가 조건이 하나 있는 SIMPLE 정의로 리포트를 저장함
- When 그 리포트를 `GET /reports/{id}`로 연다
- Then 저장 응답의 `generated_sql`은 서버가 정의를 오늘 기준으로 풀어 만든 SQL(`SELECT`로 시작)이고 열어도 같으며, 상세 `definition`의 컬럼·조건이 보낸 것과 같다

### RS-003 본문에 SQL 같은 모르는 키나 모양 오류가 있으면 422 request-validation이고 저장되지 않는다
- Given ALICE가 로그인함
- When `generated_sql: "DROP TABLE"`을 더한 본문, `visibility`가 없는 본문, 이름이 숫자인 본문으로 각각 만든다
- Then 모두 422 `request-validation`이고 ALICE의 목록은 비어 있다

### RS-004 이름·설명은 앞뒤 공백을 지워 저장하고 100자·1,000자는 받는다
- Given ALICE가 로그인함
- When 이름 "  분기 Pipeline  "·설명 "  메모 "로, 그리고 이름 100자·설명 1,000자로 만든다
- Then 저장된 이름은 "분기 Pipeline", 설명은 "메모"이고, 100자 이름·1,000자 설명도 201이다(공백을 지운 뒤 100자인 이름도 된다)

### RS-005 빈 이름·101자 이름·1,001자 설명·NUL·알 수 없는 공개 범위는 422 invalid-value 문구이고 저장되지 않는다
- Given ALICE가 로그인함
- When 이름 "  ", 이름 101자, 설명 1,001자, 이름에 NUL, 설명에 NUL, 공개 범위 "all"·"Public"으로 각각 만든다
- Then 모두 422 `invalid-value`이고 문구는 차례로 "리포트 이름을 입력하세요.", "리포트 이름은 100자 이내로 입력하세요.", "설명은 1,000자 이내로 입력하세요.", "리포트 이름에는 NUL 문자를 쓸 수 없습니다", "설명에는 NUL 문자를 쓸 수 없습니다", "공개 범위는 public 또는 private입니다."이며 아무것도 저장되지 않는다. frontend: Fake 게이트웨이(계약 테스트)로 같은 요청을 보내면 같은 kind·문구이고 NUL은 빈 이름·길이 문구가 아니다(RS-R47 ③)

### RS-006 규칙을 어긴 정의는 422 invalid-report(위치·code)이고 저장되지 않는다
- Given ALICE가 로그인함
- When 컬럼이 `deal.password` 하나뿐인 정의로 만든다
- Then 422 `invalid-report`이고 `errors`의 (위치, code)는 `(["columns", 0, "field"], "unknown-field")` 하나이며 아무것도 저장되지 않는다

### RS-007 메타 오류가 먼저이고 정의 위반이면 차트·배치를, 차트 위반이면 배치를 검사하지 않는다
- Given ALICE가 로그인함
- When ① 빈 이름 + 틀린 차트, ② 틀린 정의 + 틀린 차트 + 틀린 배치, ③ 맞는 정의 + 틀린 차트 + 틀린 배치로 만들고, ④ 틀린 정의 + 틀린 배치로 SIMPLE 리포트를 덮어쓴다
- Then ①은 422 `invalid-value` 이름 문구, ②④는 정의 위치 위반만 있고 `chart`·`layout` 위치가 없으며, ③은 `chart` 위치 위반만 있고 `layout` 위치가 없다. 어느 경우도 저장·변경되지 않는다

### RS-008 대소문자만 다른 이름은 자기 것·남의 것·남의 비공개 리포트와도 409 already-exists다
- Given ALICE의 공개 리포트 "Sales Report"와 비공개 리포트 "공통 이름"
- When ALICE가 "sales report"로, BOB이 "SALES REPORT"와 "공통 이름"으로 만든다
- Then 모두 409 `already-exists` "같은 이름의 리포트가 이미 있습니다."이고 리포트는 두 개 그대로이며 BOB의 목록에는 "공통 이름"이 보이지 않는다

### RS-009 이름은 공백을 지운 뒤 비교하고 자기 이름의 대소문자 변경과 지운 리포트 이름 재사용은 된다
- Given ALICE의 리포트 "Pipeline"
- When ALICE가 " Pipeline "으로 새로 만들고, 그 리포트를 "PIPELINE"으로 덮어쓰고, 그 리포트를 지운 뒤 "Pipeline"으로 다시 만든다
- Then 첫째는 409, 둘째는 200(이름 "PIPELINE"), 셋째는 201이다

### RS-010 목록은 공개·자기 리포트만 최근 수정 순(동률 id 내림차순)이고 정의·배치가 없다
- Given ALICE의 비공개 "alice 비공개"(T1)·공개 "alice 공개"(T2), BOB의 비공개 "bob 비공개"(T3), 같은 수정 시각의 BOB 리포트 두 개
- When BOB이 `GET /reports`를 부른다
- Then 항목은 수정 시각 내림차순(같으면 id 내림차순)이고 "alice 비공개"는 없으며, 각 항목의 키는 정확히 `id, name, description, visibility, owner, updated_by, entities, created_at, updated_at, chart_kind`이다. 볼 수 있는 것이 없는 사용자에게는 `[]`다

### RS-011 admin의 목록에는 남의 비공개 리포트도 있다
- Given ALICE의 비공개 리포트
- When ROOT가 목록을 읽는다
- Then 그 리포트가 목록에 있다

### RS-012 목록 항목의 데이터는 정의가 쓰는 deal·action이다
- Given ALICE의 리포트 "먼저"(컬럼 `deal.code`)와 "나중"(컬럼 `deal.code`·`action.type`)
- When 목록을 읽는다
- Then 항목 순서는 "나중", "먼저"이고 `entities`는 각각 `["deal", "action"]`, `["deal"]`이다

### RS-013 볼 수 있는 리포트의 상세는 정의·SQL·revision·차트·배치를 담는다
- Given ALICE의 공개 리포트
- When ALICE와 BOB이 `GET /reports/{id}`로 연다
- Then 둘 다 200이고 목록 항목 키에 `revision`, `definition`, `generated_sql`, `chart`, `chart_problem`, `layout`이 더해져 있다

### RS-014 남의 비공개 리포트는 여섯 동작 모두 없는 id와 같은 404이고 그대로다
- Given ALICE의 비공개 리포트 P, 요청자 BOB(sales)과 VIEWER(user)
- When 각자 P에 상세·덮어쓰기(revision 1)·배치 저장·삭제·복제·실행을 하고, 없는 id에도 같은 요청을 한다
- Then 모든 요청이 404 `not-found` "리포트를 찾을 수 없습니다."로 없는 id의 응답과 상태·type·문구가 같고(잘못된 revision·배치 값이어도), ALICE가 다시 연 P는 이전과 같다

### RS-015 admin은 남의 비공개 리포트를 열고 실행·덮어쓰기·배치 저장·복제·삭제한다
- Given ALICE의 비공개 리포트 P
- When ROOT가 P를 열고, 실행하고, 이름 "admin이 고침"으로 덮어쓰고, 배치를 TABLE_ONLY로 저장하고, 복제하고, 지운다
- Then 차례로 200, 200, 200(`owner`는 ALICE 그대로, `updated_by`는 ROOT), 200, 201, 204다

### RS-016 덮어쓰면 내용·SQL이 바뀌고 revision이 오르며 만든 사람·생성 시각은 그대로다
- Given ALICE의 SIMPLE 리포트 "원본"(revision 1)
- When 1초 뒤 ALICE가 `{name: "수정본", description: "새 설명", definition: OTHER, revision: 1}`로 덮어쓴다
- Then 200이고 이름·설명·정의(첫 컬럼 `deal.vendor`)가 바뀌고 `generated_sql`이 새 정의의 SQL이며 `revision` 2, `owner`·`created_at`은 그대로, `updated_at`은 덮어쓴 시각이고, 다시 열면 같은 값이다

### RS-017 sales·user도 남의 공개 리포트를 덮어쓰고 최종 수정자가 된다
- Given ALICE의 공개 리포트 R
- When BOB(sales)과, 다른 시나리오에서 VIEWER(user)가 공개 범위를 그대로 두고 revision 1로 덮어쓴다
- Then 200이고 `owner`는 ALICE, `updated_by`는 요청자, `revision` 2이며 목록의 그 항목도 `updated_by`가 요청자다

### RS-018 저장된 것과 다른 revision으로 덮어쓰면 409 invalid-state이고 그대로다
- Given ALICE의 공개 리포트 R을 BOB이 revision 1로 덮어써 revision 2가 됨
- When ALICE가 revision 1로, 또 revision 5로 덮어쓴다
- Then 둘 다 409 `invalid-state` "다른 사용자가 먼저 이 리포트를 저장했습니다. 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."이고 R은 BOB이 저장한 값 그대로다. 같은 revision으로 차례로 두 번 보내면 첫 번째만 200이다

### RS-019 만든 사람이 아닌 편집자가 공개 범위를 바꾸면 403이고 같은 값은 된다
- Given ALICE의 공개 리포트 R
- When BOB이 `visibility: "private"`로, 그다음 `visibility: "public"`으로 덮어쓴다(revision 1)
- Then 첫 번째는 403 `forbidden` "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."이고 R은 그대로이며, 두 번째는 200이다

### RS-020 만든 사람과 admin은 공개 범위를 바꾸고 비공개가 되면 남에게 404다
- Given ALICE의 공개 리포트 R1·R2
- When ALICE가 R1을, ROOT가 R2를 `private`로 덮어쓴다
- Then 둘 다 200이고 그 뒤 BOB이 R1·R2를 열면 404, 목록에서도 사라진다

### RS-021 덮어쓰기는 404 → 422 → 403 → 409 순서로 판정한다
- Given ALICE의 비공개 리포트 P(revision 4)와 공개 리포트 R(revision 4)
- When BOB이 P를 틀린 정의·revision 1로, R을 틀린 정의·`private`·revision 1로, R을 맞는 정의·`private`·revision 1로 덮어쓴다
- Then 차례로 404, 422 `invalid-report`, 403(공개 범위)이고 셋 다 R·P를 바꾸지 않는다. frontend: Fake 게이트웨이(계약 테스트)도 같은 순서·결과이고, 특히 맞는 정의·`private`·낡은 revision은 409가 아니라 403이다(RS-R47 ①)

### RS-022 다른 리포트의 이름으로 바꾸면 409 already-exists이고 그대로다
- Given ALICE의 리포트 "첫째"·"둘째", BOB의 공개 리포트 "bob"
- When ALICE가 "둘째"를 "첫째"로, BOB이 "bob"을 "첫째"로 덮어쓴다(맞는 revision)
- Then 둘 다 409 `already-exists`이고 "둘째"·"bob"은 그대로다

### RS-023 규칙을 어긴 정의로 덮어쓰면 422이고 저장된 리포트는 그대로다
- Given ALICE의 리포트 "원본"
- When 컬럼 `nope.x`인 정의로 revision 1 덮어쓰기를 한다
- Then 422 `invalid-report`이고 "원본"의 상세는 이전과 같다

### RS-024 만든 사람은 공개·비공개 자기 리포트를 지우고 그 리포트만 사라진다
- Given VIEWER(user)의 공개 리포트와 비공개 리포트, ALICE의 리포트
- When VIEWER가 자기 두 리포트를 지운다
- Then 둘 다 204(본문 없음)이고 VIEWER의 목록에서 사라지며 ALICE의 리포트는 남는다

### RS-025 sales·user가 남의 공개 리포트를 지우면 403이고 그대로다
- Given ALICE의 공개 리포트 R
- When BOB과 VIEWER가 R을 지운다
- Then 403 `forbidden` "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."이고 R은 그대로다

### RS-026 admin은 남의 공개·비공개 리포트를 지운다
- Given ALICE의 공개 리포트와 비공개 리포트
- When ROOT가 둘을 지운다
- Then 둘 다 204이고 그 뒤 상세는 404다

### RS-027 없는 리포트를 지우면 404다
- Given 리포트가 없음
- When ALICE가 없는 id를 지운다
- Then 404 `not-found` "리포트를 찾을 수 없습니다."다

### RS-028 복제하면 정의·배치는 원본이고 만든 사람은 요청자, revision 1이며 원본은 그대로다
- Given ALICE의 공개 리포트 S(정의 OTHER, 차트 있음, 배치 BOTH_SIDE, revision 3)
- When VIEWER가 `{name: "원본 복사본", description: "복제", visibility: "private"}`로 복제한다
- Then 201, `Location` = `/api/v1/reports/<새 id>`, 새 리포트의 `definition`·`layout`은 S와 같고(차트의 승계는 RC-038이 검증) `owner`·`updated_by`는 VIEWER, `revision` 1, 이름·설명·공개 범위는 보낸 값이며 S는 이전과 같다

### RS-029 모든 역할이 공개 리포트를, admin은 남의 비공개 리포트도 복제하고 설명 생략은 빈 문자열이다
- Given ALICE의 공개 리포트와 비공개 리포트
- When ROOT·BOB·VIEWER가 공개 리포트를, ROOT가 비공개 리포트를 설명 없이 복제한다
- Then 모두 201이고 새 리포트의 `description`은 `""`다

### RS-030 복제 이름이 어떤 리포트와 겹치면 409다
- Given ALICE의 공개 리포트 "원본", BOB의 리포트 "내 리포트", ALICE의 비공개 "숨은 이름"
- When BOB이 "원본"을 이름 "내 리포트"로, "숨은 이름"으로 복제한다
- Then 둘 다 409 `already-exists`이고 새 리포트가 없다

### RS-031 원본 정의가 지금 규칙과 맞지 않거나 메타가 틀리면 복제는 422이고 아무것도 생기지 않는다
- Given 지금 카탈로그에 없는 필드를 쓰는 ALICE의 공개 리포트 S1과 정상 리포트 S2
- When BOB이 S1을 복제하고, S2를 빈 이름으로 복제한다
- Then 각각 422 `invalid-report`(정의 위치), 422 `invalid-value` "리포트 이름을 입력하세요."이고 리포트 수가 그대로다

### RS-032 실행은 저장된 정의를 오늘 기준으로 풀어 /query와 같은 결과를 주고 아무것도 저장하지 않는다
- Given 업무 날짜 2026-10-27, Vendor별 분기 금액 정의를 ALICE가 `/query`로 조회한 결과 Q와 같은 정의로 저장한 리포트 R
- When ALICE가 `POST /reports/{R}/run`을 부른다
- Then 200이고 `rows`·`totals`·`total_count`·`columns`가 Q와 같으며, 실행 기준 날짜는 실행 시각의 업무 날짜이고, R의 `revision`·`updated_at`은 그대로이며 저장이 일어나지 않는다

### RS-033 다시 실행하면 저장된 결과가 아니라 그때의 데이터로 조회한다
- Given ALICE의 리포트 R을 한 번 실행한 결과 A
- When 조건에 맞는 Deal이 하나 늘어난 뒤 R을 다시 실행한다
- Then 결과는 A와 다르고 그 순간 같은 정의로 `/query`를 조회한 결과와 같다

### RS-034 지금 규칙과 맞지 않는 저장 정의의 실행은 422이고 시간 초과는 503이다
- Given 지금 카탈로그에 없는 필드를 쓰는 저장 리포트 R1, 실행이 시간 초과되는 리포트 R2
- When R1·R2를 실행한다
- Then R1은 422 `invalid-report`이고 조회를 실행하지 않으며, R2는 503 `report-timeout`이다

### RS-035 깨진 저장 정의 리포트는 목록에 데이터 없이 남고 남의 비공개면 숨는다
- Given ALICE의 공개 리포트 B1과 비공개 리포트 B2의 저장 정의를 읽을 수 없게 되었고 정상 리포트 H도 있음
- When BOB과 ROOT가 목록을 읽는다
- Then 목록은 오류 없이 200이고 BOB에게는 B1(`entities` `[]`)·H가, ROOT에게는 B1·B2·H가 보인다

### RS-036 깨진 저장 정의의 상세·실행·복제는 404 판정 뒤 422 stored-invalid이고 아무것도 실행·생성되지 않는다
- Given RS-035와 같은 리포트
- When ALICE가 B1의 상세·실행·복제를 하고, BOB이 B2의 상세·실행·복제를 한다
- Then ALICE의 요청은 모두 422 `invalid-report`, `detail` "저장된 리포트 정의를 읽을 수 없습니다.", `errors` = `[{location: ["definition"], code: "stored-invalid", …}]`이고 조회 실행·새 리포트가 없으며, BOB의 요청은 모두 404다

### RS-037 깨진 저장 정의 리포트는 새 정의로 덮어써 복구되고(revision 검사 유지) 지울 수 있다
- Given RS-035의 B1(revision 1)
- When ALICE가 SIMPLE 정의로 revision 2를 보내고, revision 1을 보내고, 다른 B1′를 지운다
- Then 첫째는 409, 둘째는 200이고 그 뒤 상세·실행이 200이며, 지우기는 204다

### RS-038 배치를 정해 저장하면 같은 배치로 열리고 배치 없이 저장하면 기본 배치다
- Given ALICE가 로그인함
- When CHART_SIDE 배치로, 그리고 `layout` 없이(생략·null) 리포트를 만든다
- Then 응답과 다시 연 상세의 `layout`이 각각 CHART_SIDE와 DEFAULT이고 `revision` 1, 다른 필드(`chart` null, 이름)는 보낸 대로다

### RS-039 저장된 배치가 NULL이거나 깨졌으면 기본 배치로 열린다
- Given ALICE의 리포트(배치 CHART_SIDE)의 저장 배치가 NULL이 되었고, 다른 리포트의 저장 배치가 `{"view": "grid"}`가 됨
- When 둘을 연다
- Then 둘 다 200이고 `layout`은 DEFAULT이며, NULL이던 리포트를 덮어쓰면 기본 배치 객체가 저장된다

### RS-040 배치 없이 덮어쓰면 저장된 배치가 남고 배치를 보내면 바뀐다
- Given ALICE의 리포트(배치 CHART_SIDE)
- When `layout` 없이(생략·null) 이름만 바꿔 덮어쓰고, 다음에 TABLE_ONLY를 보내 덮어쓴다
- Then 첫 응답은 이름이 바뀌고 `layout` CHART_SIDE, `revision` 2이며, 다음 응답은 `layout` TABLE_ONLY, `revision` 3이다

### RS-041 배치만 저장하면 배치·수정자·시각·revision만 바뀌고 정의·차트·이름·차트 안내는 그대로다
- Given ALICE의 차트 있는 리포트 R(revision 1)과 저장 차트를 읽을 수 없는 리포트 C
- When ALICE가 R에 `PUT /reports/{R}/layout {layout: CHART_SIDE, revision: 1}`, C에 TABLE_ONLY를 보낸다
- Then R 응답은 `layout` CHART_SIDE, `revision` 2, `updated_by` ALICE이고 `name`·`definition`·`generated_sql`·`chart`·`visibility`·`owner`는 이전과 같으며, C 응답은 `chart` null·`chart_problem` 그대로이고 다시 열어도 같다

### RS-042 응답 revision으로 배치를 이어 저장하면 모두 되고 낡은 revision은 409다
- Given ALICE의 리포트(revision 1)
- When CHART_SIDE·BOTH_SIDE·TABLE_ONLY를 직전 응답의 revision으로 차례로 저장한 뒤, revision 1로 CHART_SIDE를 저장한다
- Then 앞의 셋은 200이고 revision 2·3·4이며, 마지막은 409 `invalid-state`이고 배치는 TABLE_ONLY·revision 4 그대로다. BOB이 먼저 덮어쓴 뒤 ALICE가 이전 revision으로 배치를 저장해도 409이고 그대로다

### RS-043 남의 공개 리포트도 배치를 저장하고 최종 수정자가 기록된다
- Given ALICE의 공개 리포트
- When VIEWER가 TABLE_ONLY를 revision 1로 저장한다
- Then 200, `owner` ALICE, `updated_by` VIEWER, `layout` TABLE_ONLY, `revision` 2다

### RS-044 배치 값이 틀리면 만들기·덮어쓰기·배치 저장 모두 422 invalid-report(layout 위치 전부)이고 저장되지 않는다
- Given ALICE의 리포트(배치 CHART_SIDE)
- When 배치 `order: ["table","table"]`, `view: "grid"`, `arrange: "row"`로 각각 배치 저장하고, 세 값이 모두 틀린 배치로 배치 저장하고, `view: "x"`로 만들기·덮어쓰기를 한다
- Then 모두 422 `invalid-report`이고 위치는 각각 `["layout","order"]`, `["layout","view"]`, `["layout","arrange"]`, 세 위치 모두(code `invalid-value`, RS-R20 문구), `["layout","view"]`이며 리포트가 생기거나 배치가 바뀌지 않는다

### RS-045 배치 요청의 모양 오류는 422 request-validation이다
- Given ALICE의 리포트
- When 배치에 `colour` 키를 더하거나 `view`를 빼거나 배치가 목록이고, `revision`이 없거나 0·"1"·1.5이고, `layout`이 없는 배치 저장을 보낸다
- Then 모두 422 `request-validation`이다

### RS-046 배치 저장은 404 → 깨진 정의 422 → 배치 값 422 → 403 → 409 순서로 판정한다
- Given ALICE의 비공개 리포트 P, 깨진 정의의 공개 리포트 B(revision 4), 정상 공개 리포트 R(revision 4), 수정 권한 판정을 거짓으로 바꾼 시나리오
- When BOB이 P에 틀린 배치를, B에 틀린 배치·revision 1을, R에 틀린 배치를(수정 권한 거짓), R에 맞는 배치·revision 1을(수정 권한 거짓), R에 맞는 배치·revision 1을 보낸다
- Then 차례로 404, 422 `stored-invalid`, 422 `invalid-report`(layout), 403 "이 리포트를 수정할 권한이 없습니다.", 409이고 어느 리포트도 바뀌지 않는다

### RS-047 리포트를 만들었거나 마지막으로 수정한 사용자를 삭제하면 퇴사 처리된다
- Given ALICE가 공개 리포트를 만들고 BOB이 그것을 덮어씀, 연결이 없는 사용자 PARK
- When ROOT가 ALICE, BOB, PARK을 차례로 삭제한다
- Then ALICE·BOB의 결과는 `resigned`(퇴사자 목록에 남음)이고 PARK은 `deleted`다

### RS-048 만든 사람이 퇴사해도 리포트는 남아 "(퇴사)"로 보이고 다른 사용자가 열고 실행한다
- Given ALICE의 공개 리포트 R, 그 뒤 ALICE가 퇴사 처리됨
- When VIEWER가 목록을 읽고 R을 열고 실행한다
- Then 목록 항목·상세의 `owner`는 `resigned: true`, `label` "<이름>(퇴사)"이고 `updated_by`도 같으며, 실행은 200이다

### RS-049 reports 테이블의 컬럼·제약이 명세와 같다
- Given head 스키마
- When `reports` 테이블을 살핀다
- Then 컬럼 타입·NULL 여부·DB 기본값이 2.2와 같고, 사용자 FK 두 개는 RESTRICT라 리포트를 만들었거나 마지막으로 수정한 사용자 행을 물리 삭제할 수 없으며, `lower(name)` 유니크 인덱스가 만든 사람과 무관하게 대소문자만 다른 이름을 막고, `visibility`·`revision >= 1`·`definition`·`layout` 객체 CHECK가 다른 값을 거절하며, 101자 이름은 컬럼이 거절한다

### RS-050 모든 경로는 로그인이 필요하고 쓰기는 CSRF 헤더가 필요하며 잘못된 id는 422다
- Given 로그인하지 않은 클라이언트, 로그인했지만 `X-Requested-With`를 빼는 클라이언트
- When 저장 리포트 11개 메서드를 부르고, 로그인한 채 `/reports/abc`, `/reports/0`, `/reports/1.5`를 부른다
- Then 미인증은 모두 401, 헤더가 없는 POST·PUT·DELETE는 403 `csrf`, 잘못된 id는 422 `request-validation`이며, admin·sales·user 모두 만들기·덮어쓰기·삭제가 역할 가드에 막히지 않는다

### RS-051 /reports/fields·/reports/query는 리포트 id 경로에 걸리지 않는다
- Given 로그인한 사용자
- When `GET /reports/fields`와 `POST /reports/query`를 부른다
- Then 각각 카탈로그·조회 응답이고 `/reports/{report_id}`의 422·404가 아니다

### RS-052 openapi에 저장 리포트 경로·성공·오류 코드·요청·응답 필드가 명세와 같다
- Given `create_app().openapi()`
- When 저장 리포트 경로를 살핀다
- Then 경로·메서드·성공 코드·문서화한 오류 코드가 RS-R26과 같고, id 경로 파라미터는 1~2^53−1 정수, 만들기·덮어쓰기 요청에 SQL 필드가 없고 `chart`·`layout`은 선택·nullable, 복제 요청에는 `chart`·`layout`이 없으며, `revision`은 정수 최소 1, 상세 응답에 `layout`(enum·order 길이 2)이 필수이고 목록 항목에는 `layout`·`definition`이 없으며, 사용자 필드는 공통 UserRef 스키마, 실행 응답은 조회 응답 스키마다

### RS-053 모든 역할이 목록 화면을 열고 리포트가 없으면 빈 안내와 새 리포트 링크를 본다
- Given 저장 리포트가 없는 Fake, admin·sales·user 각각 로그인
- When `/reports`를 연다
- Then 제목 "Reports", 링크 "+ 새 리포트"(`/reports/new`), "아직 저장한 리포트가 없습니다. 새 리포트를 만들어 조건에 맞는 Deal을 조회해 보세요."가 보이고 필터가 없다

### RS-054 목록 행은 이름 링크·비공개·데이터 태그·만든 사람·최종 수정과 "수정: 이름"을 보인다
- Given 내 비공개 리포트(Actions 필드 사용), 남이 만들고 내가 고친 공개 리포트, 퇴사자가 만든 공개 리포트
- When 목록을 연다
- Then 이름은 `/reports/<id>` 링크이고 비공개 행에 "비공개", 데이터 열에 "Deal"(+ "Actions"), 만든 사람 열에 label("<이름>(퇴사)" 포함), 최종 수정 열에 `YYYY-MM-DD HH:mm`과 고친 행에만 " 수정: <이름>"이 보이고 행 순서는 서버 순서다

### RS-055 admin에게는 남의 비공개 리포트도 목록에 보인다
- Given 다른 사람의 비공개 리포트
- When admin과 sales가 각각 목록을 연다
- Then admin에게만 그 행이 "비공개" 태그와 함께 보인다

### RS-056 검색어와 "내가 만든 리포트"로 거르고 주소에 남으며 주소에서 복원된다
- Given 이름·설명이 다른 리포트 여러 개(내 것·남의 것)
- When "이름·설명 검색"에 대소문자가 다른 설명 일부를 넣고, "리포트 범위"를 "내가 만든 리포트"로 바꾸고, `/reports?q=<값>&mine=1`로 새로 연다
- Then 이름 또는 설명에 들어 있는 리포트만, 범위를 바꾸면 내가 만든 것만 남고 주소는 `?q=…&mine=1`이며 새로 연 화면도 같은 필터·결과다. 맞는 것이 없으면 "조건에 맞는 리포트가 없습니다."다

### RS-057 ⋯ 메뉴는 aria 상태로 여닫고 Escape·바깥 클릭으로 닫히며 편집·삭제는 권한 있을 때만 있다
- Given 내 리포트와 남의 공개 리포트가 있는 목록(sales)
- When 내 리포트의 "<이름> 메뉴"를 열고 Escape를 누르고, 다시 열고 바깥을 누르고, "편집"을 누르고, 남의 리포트 메뉴를 연다
- Then 열리면 `aria-expanded` true와 "열기"·"편집"·"복제"·"삭제", Escape는 닫고 포커스를 메뉴 단추로 되돌리며, 바깥 클릭도 닫고, "편집"은 `/reports/<id>/edit`로 가며, 남의 공개 리포트 메뉴에는 "삭제"가 없다

### RS-058 목록에서 확인 뒤 삭제하면 행이 사라지고 취소하면 요청이 없다
- Given 내 리포트 두 개
- When 하나를 메뉴 "삭제" → 확인 창 "삭제", 다른 하나는 "취소", 그다음 남은 하나도 삭제한다
- Then 확인 창 문구는 "‘<이름>’ 리포트를 삭제할까요? 되돌릴 수 없습니다."이고 삭제한 행이 사라지며, 취소는 삭제 요청이 없고 행이 남으며, 마지막을 지우면 빈 안내가 보인다

### RS-059 목록·보기에서 복제하면 "복사본" 이름으로 시작해 새 리포트 편집 화면으로 간다
- Given 남의 공개 리포트 "분기 Pipeline"
- When 목록 메뉴와 보기 화면에서 각각 "복제"를 누르고 공개 범위를 "나만 보기"로 바꿔 저장한다
- Then 대화상자 이름은 "분기 Pipeline 복사본", 공개 범위는 "모든 사용자에게 보임"으로 시작하고, 저장하면 `/reports/<새 id>/edit`로 가며 새 리포트의 만든 사람은 나, 공개 범위는 비공개다

### RS-060 복제 이름 중복·원본 규칙 위반은 대화상자 안에 보이고 취소하면 요청이 없다
- Given 이름이 겹치는 리포트가 있고, 다른 원본은 지금 카탈로그에 없는 필드를 씀
- When 겹치는 이름으로 복제하고, 규칙 위반 원본을 복제하고, 복제 대화상자를 취소한다
- Then 이름 칸 아래 "같은 이름의 리포트가 이미 있습니다."와 목록에 머묾, 창 안 "원본 설계가 지금 규칙과 맞지 않아 복제할 수 없습니다. 편집에서 고치세요. <서버 문구>", 취소는 복제 요청이 없다

### RS-061 보기 화면은 열 때마다 저장된 리포트를 실행해 메타·결과·SQL을 보이고 "다시 조회"로 다시 실행한다
- Given 내 공개 리포트(설명 있음)
- When 목록에서 이름을 눌러 열고, "다시 조회"를 누르고, 목록으로 갔다가 다시 연다
- Then 경로 "Reports ›", h1 이름, 설명, 메타 "<만든 사람> · <시각>", 결과 표와 생성 SQL이 보이고, "다시 조회"와 다시 열기마다 실행 요청이 하나씩 더 간다

### RS-062 보기 화면 머리에 비공개 태그·"수정: 이름"·퇴사자 표시가 있고 admin은 남의 비공개를 연다
- Given 남이 고친 내 비공개 리포트, 퇴사자가 만든 공개 리포트, 남의 비공개 리포트
- When 각각 연다(마지막은 admin으로)
- Then "비공개" 태그와 메타 끝 " (수정: <이름>)", 만든 사람 "<이름>(퇴사)"이 보이고 admin은 남의 비공개 리포트의 결과를 본다

### RS-063 보기 화면 버튼은 권한에 따르고 삭제하면 목록으로, 편집 링크는 편집 화면으로 간다
- Given 내 리포트와 남의 공개 리포트
- When 남의 리포트를 열고, 내 리포트를 열어 "삭제" → 취소 → 다시 "삭제" → 확인하고, 다른 내 리포트에서 "편집"을 누른다
- Then 남의 리포트에는 "다시 조회"·"편집"·"복제"만 있고 "삭제"가 없으며, 취소는 화면에 머물고, 삭제하면 `/reports`로 가며, "편집"은 `/reports/<id>/edit`로 간다

### RS-064 없는·숨긴·잘못된 id는 보기·편집 화면 모두 찾을 수 없음 안내이고 실행하지 않는다
- Given 남의 비공개 리포트 P
- When `/reports/<P>`, `/reports/abc`, `/reports/0`, `/reports/9007199254740991`, `/reports/<P>/edit`, `/reports/1.5/edit`를 열고 "리포트 목록"을 누른다
- Then 모두 "리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다."와 링크 "리포트 목록"이 보이고 "삭제" 버튼과 실행 요청이 없으며, 링크는 `/reports`로 간다

### RS-065 지금 규칙과 맞지 않는 저장 정의는 위반 안내, 시간 초과는 문구와 다시 조회다
- Given 지금 카탈로그에 없는 필드(`deal.nope`)를 쓰는 리포트 "깨진 정의", 실행이 시간 초과되는 리포트
- When 각각 보기 화면을 연다
- Then 첫째는 h1 "깨진 정의", 알림 "저장된 설계가 지금 규칙과 맞지 않습니다. 편집에서 고치세요"와 "허용되지 않은 필드입니다: deal.nope"이고 결과 표가 없으며 "편집"은 있다. 둘째는 시간 초과 서버 문구와 켜진 "다시 조회"다

### RS-066 깨진 저장 정의 리포트는 보기·편집 화면에 서버 문구 배너를 보이고 목록에는 남는다
- Given Fake에 저장 정의를 읽을 수 없는 내 리포트 B(RS-R47 ②)
- When 목록을 열고, `/reports/<B>`와 `/reports/<B>/edit`를 연다
- Then 목록에는 B 행이 있고, 보기·편집 화면은 "저장된 리포트 정의를 읽을 수 없습니다." 오류 배너만 보이며 찾을 수 없음 안내가 아니고 실행 요청이 없으며 편집 화면에 설계가 실리지 않는다(화면에서 고칠 수 없음, RS-R17). Fake 게이트웨이의 B 상세·실행·복제·배치 저장은 서버와 같은 422 `stored-invalid`이고, 새 정의로 덮어쓰면 상세가 열린다

### RS-067 저장 버튼은 성공한 결과가 지금 설계와 같을 때만 켜지고 새 리포트에는 다른 이름 버튼이 없다
- Given 새 리포트 화면
- When 조회 전, 조회 성공 뒤, 설계를 바꾼 뒤, 조회가 실패한 뒤의 "저장"을 본다
- Then 차례로 꺼짐(`title` "먼저 조회하세요"), 켜짐, 꺼짐("바뀐 설계를 다시 조회한 뒤 저장하세요"), 꺼짐이고 "다른 이름으로 저장" 버튼은 없다

### RS-068 저장 대화상자의 기본값·안내·빈 이름 검사·취소·요청 중 잠금
- Given 조회가 끝난 새 리포트 화면, 응답을 잡아 둔 Fake
- When "저장"을 눌러 대화상자를 보고, 이름 없이 "저장"을 누르고, "취소"를 누르고, 다시 열어 저장 요청을 보낸 채 "취소"·Esc를 누른다
- Then 제목 "리포트 저장", 이름·설명 빈칸, 공개 범위 "모든 사용자에게 보임", 안내 "저장 내용: …"이 보이고, 빈 이름은 요청 없이 "이름을 입력하세요", 취소는 요청 없이 닫히며, 요청 중에는 "저장"·"취소"가 비활성이고 Esc로 닫히지 않다가 응답 뒤 닫힌다(덮어쓰기·다른 이름·복제도 같다)

### RS-069 새 리포트를 저장하면 편집 화면으로 바뀌고 저장 안 됨이 없으며 user도 저장한다
- Given 조회가 끝난 새 리포트 화면(user 포함)
- When 이름을 넣어 저장한다
- Then 주소가 `/reports/<id>/edit`(이력 교체)가 되고 "● 저장 안 됨"이 없으며 "되돌리기"·"다른 이름으로 저장"·"저장"이 보이고, user도 같다

### RS-070 이름이 다른 리포트와 겹치면 이름 칸 아래 문구이고 디자이너에 머문다
- Given 다른 사람이 쓰는 이름 "공통 이름"(비공개 포함), 내 리포트 이름 "내 것"
- When 새 리포트를 "공통 이름"으로, 편집 화면의 다른 리포트를 "내 것"으로 저장한다
- Then 이름 칸 아래 "같은 이름의 리포트가 이미 있습니다."가 보이고 대화상자와 화면이 그대로다

### RS-071 서버가 정의를 거절하면 대화상자를 닫고 디자이너에 위반을 보인다
- Given 저장할 때 서버(Fake)가 정의 위반 422를 돌려주는 설계
- When 저장한다
- Then 대화상자가 닫히고 작성 탭에 위반이 보이며(표시는 RQ-R49) 저장되지 않는다

### RS-072 새 편집 화면은 지금 설계의 결과를 넘겨받아 저장 전 탭으로 열리고 설계가 바뀌었으면 다시 조회한다
- Given 조회가 끝난 새 리포트 화면
- When 결과 탭을 보던 채로 저장하고, 다른 시나리오에서 작성 탭에서 저장하고, 또 다른 시나리오에서 조회 뒤 설계를 바꿔 조회한 직후가 아닌 채 저장 흐름을 거친다
- Then 앞의 둘은 새 편집 화면이 각각 결과 탭·작성 탭으로 열리고 실행 요청을 더 보내지 않으며, 설계가 결과와 다르면 새 편집 화면이 작성 탭에서 한 번 조회한다

### RS-073 편집 화면은 저장된 설계를 작성 탭에 싣고 한 번 조회하며 스스로 다시 조회하지 않는다
- Given 저장된 리포트(남의 공개 리포트 포함, user로도)
- When `/reports/<id>/edit`를 연다
- Then 저장된 컬럼·조건이 실린 작성 탭이 보이고 조회 요청이 한 번 가며 결과 탭에 결과가 채워지되 탭은 옮기지 않고, 그 뒤 기다려도 조회 요청이 더 가지 않는다

### RS-074 덮어쓰면 저장 안 됨이 사라지고 제목이 새 이름을 따르며 다음 덮어쓰기는 응답 revision을 쓴다
- Given 편집 화면(revision 1)
- When 설계를 바꿔 다시 조회하고 이름을 바꿔 "저장"하고, 다시 바꿔 "저장"한다
- Then 첫 덮어쓰기 뒤 "● 저장 안 됨"이 사라지고 h1이 새 이름이며 화면에 머물고, 두 번째 요청의 revision은 2이고, 덮어쓴 뒤 바꾸면 다시 "● 저장 안 됨"이 붙는다

### RS-075 다른 사람이 먼저 저장했으면 충돌 경고와 "다른 이름으로 저장"이 나오고 닫아도 설계가 남는다
- Given 편집 화면을 연 뒤 다른 사용자가 같은 리포트를 덮어씀(Fake)
- When "저장" → 대화상자 "저장"을 누르고, "닫기"를 누르고, 다시 저장해 경고의 "다른 이름으로 저장"을 누른다
- Then 알림에 "다른 사용자가 먼저 이 리포트를 저장했습니다. …"와 버튼 "다른 이름으로 저장", 아래 버튼은 "닫기"뿐이고, 닫아도 바꾼 설계가 남으며, 다른 이름으로 저장 모드로 바뀌어 "<이름> 복사본"으로 새 리포트를 만든다

### RS-076 상세를 다시 받아도 편집 화면의 기준 revision·대화상자 기본값은 처음 값이나 내 덮어쓰기 값이다
- Given 편집 화면을 연 뒤 다른 사용자가 덮어쓰고 상세가 다시 받아짐
- When 저장 대화상자를 열고 저장하고, 다른 시나리오에서 내가 먼저 덮어쓴 뒤 상세가 다시 받아지고 다시 저장한다
- Then 대화상자 기본값은 처음 불러온 이름이고 저장은 409 충돌 경고이며, 두 번째 시나리오의 저장은 내 덮어쓰기 응답 revision으로 가서 된다(그 사이 다른 사람이 저장했으면 409)

### RS-077 다른 이름으로 저장은 "복사본" 이름(100자로 자름)·자유로운 공개 범위로 새 리포트를 만든다
- Given 이름 98자인 남의 공개 리포트의 편집 화면
- When "다른 이름으로 저장"을 연다
- Then 이름은 "<이름> 복사본"을 100자로 자른 값, 공개 범위는 "모든 사용자에게 보임"이고 바꿀 수 있으며, 저장하면 원본은 그대로이고 새 리포트 편집 화면으로 간다

### RS-078 만든 사람이 아닌 편집자는 공개 범위가 잠기고 지금 값으로 덮어쓴다
- Given 남의 공개 리포트의 편집 화면(sales)
- When "저장"을 눌러 대화상자를 보고 저장한다
- Then 공개 범위 선택이 비활성이고 "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다"가 보이며, 요청은 `visibility: "public"`으로 가서 된다

### RS-079 되돌리기는 확인 뒤 마지막으로 저장된 설계로 돌아가고 변경이 없으면 아무것도 하지 않는다
- Given 편집 화면에서 한 번 덮어쓴 뒤 다시 컬럼을 바꿈
- When "되돌리기" → "취소", 다시 "되돌리기" → "되돌리기"를 누르고, 변경 없는 편집 화면에서 "되돌리기"를 누른다
- Then 확인 창 "저장된 설계로 되돌릴까요?"/"저장하지 않은 변경이 사라집니다.", 취소는 변경 유지, 되돌리면 처음 불러온 설계가 아니라 마지막 덮어쓰기의 설계가 되고 "● 저장 안 됨"이 사라지며, 변경이 없으면 확인 창이 없고 결과와 켜진 "저장"이 그대로다

### RS-080 설계를 바꾸면 저장 안 됨이 붙고 되돌리면 사라진다
- Given 새 리포트 화면과 편집 화면
- When 새 리포트에 컬럼을 하나 넣고, 편집 화면에서 컬럼을 빼고 다시 같은 컬럼을 넣는다
- Then 새 리포트는 바로 "● 저장 안 됨", 편집 화면은 뺀 뒤 붙고 원래대로 돌리면 사라진다

### RS-081 저장 안 됨일 때만 떠날 때 확인하고 저장·되돌린 직후에는 묻지 않는다
- Given 저장 안 됨인 편집 화면과 새 리포트 화면
- When 상단 메뉴 링크를 누르고 "머물기", 다시 눌러 "떠나기"를 누르고, `beforeunload`를 보내고, 변경이 없는 화면·변경을 되돌린 화면·덮어쓴 직후·되돌리기 직후·첫 저장 직후에 링크를 누른다
- Then 저장 안 됨일 때는 확인 창 "저장하지 않은 변경이 있습니다"/"저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?"가 뜨고 머물기는 남고 떠나기는 이동하며 `beforeunload`가 막히고, 나머지 경우는 묻지 않고 이동하며 `beforeunload`도 막지 않는다

### RS-082 디자이너 탭은 작성으로 열리고 화살표로 바뀌며 숨긴 패널의 화면 상태가 남는다
- Given 새 리포트 화면
- When 탭을 살피고, "결과" 탭을 누르고, → 키를 누르고, 결과 표 2쪽·합계 행 켬·"표만"을 고른 뒤 작성 탭에 갔다 돌아온다
- Then `tablist` "리포트 디자이너"에 "작성"(선택)·"결과"가 있고 작성 패널에 필드·범위·컬럼·조건·행 수·조회, 결과 패널에 보기 선택·타일·생성 SQL이 있으며 비활성 패널은 DOM에 `hidden`으로 남고, 탭 전환·화살표 전환이 되며, 돌아와도 표 쪽·합계 행·보기·배치·설계가 그대로다

### RS-083 조회가 성공하면 결과 탭으로 가고 실패하면 작성 탭에 머물며 이전 결과가 남는다
- Given 한 번 조회해 결과가 있는 새 리포트 화면
- When 다시 조회에 성공하고, 위반·시간 초과·그 밖의 서버 오류·읽을 수 없는 입력으로 각각 조회한다
- Then 성공은 결과 탭으로 가서 결과 표·차트 타일을 보이고, 실패들은 작성 탭에 머물며(입력 문제는 요청 없음) 결과 탭에는 이전 결과가 남는다

### RS-084 조회 전 결과 탭은 안내를 보이되 보기·배치를 바꿀 수 있고 보기·배치 변경은 다시 조회를 요구하지 않는다
- Given 조회 전 새 리포트 화면, 다른 시나리오에서 조회가 끝난 화면
- When 조회 전 결과 탭에서 "표만"을 고르고 타일을 옮기고, 조회 뒤에는 보기·배치를 바꾸고 행 수를 바꾼다
- Then 조회 전 표 타일은 "아직 조회 결과가 없습니다. 작성 탭에서 '조회'를 누르세요."이고 선택·이동이 반영되며, 조회 뒤 보기·배치 변경은 "설계가 바뀌었습니다…" 안내가 없고 "저장"이 켜진 채이며, 행 수 변경은 안내가 뜬다

### RS-085 보기 선택에 맞는 타일이 보이고 다시 조회해도 선택이 남는다
- Given 조회가 끝난 디자이너 결과 탭
- When `radiogroup` "보기"에서 "차트만", "표만", "표+차트"를 차례로 고르고 다시 조회한다
- Then 라디오는 세 개("표+차트" 처음 선택), 차트만은 차트 타일만, 표만은 표 타일만, 표+차트는 두 타일이 저장된 순서대로 보이고 다시 조회해도 선택이 남는다

### RS-086 타일을 다른 타일의 네 가장자리에 놓으면 순서와 한 줄/두 줄이 정해진다
- Given 표 → 차트 두 줄인 결과 탭(조회 전후)
- When 표 타일 머리를 끌어 차트 타일의 오른쪽 20% 띠(위쪽 절반 포함)·가운데 아래쪽·왼쪽 띠·가운데 위쪽에 각각 놓는다
- Then 차례로 차트 → 표 한 줄, 차트 → 표 두 줄, 표 → 차트 한 줄, 표 → 차트 두 줄이고 보기 방식은 그대로이며, 타일 머리가 끄는 손잡이다(가장자리 경계값 0.2·0.8·0.5 판정은 순수 함수 단위 테스트로 함께 확인)

### RS-087 자기 위에 놓거나 타일 밖에서 끝내면 바뀌지 않고 끄는 동안의 표시는 놓으면 지워진다
- Given 두 타일이 보이는 결과 탭
- When 표를 끌어 자기 위에 놓고, 타일 밖에서 끝내고, 차트 위에서 포인터를 왼쪽 띠에서 아래쪽으로 옮긴 뒤 놓는다
- Then 앞의 둘은 배치가 그대로이고, 셋째는 놓일 가장자리 표시가 포인터를 따라 바뀌다가 놓으면 지워진다

### RS-088 Alt+화살표로 타일을 옮기고 포커스·안내가 남으며 타일이 하나면 옮기기 버튼이 없다
- Given 두 타일이 보이는 결과 탭
- When "표 타일 옮기기"에서 Alt+→, Alt+↓, Alt+←를, "차트 타일 옮기기"에서 Alt+↑를, 그리고 Alt 없이 →를 누르고, "표만"·"차트만"을 고른다
- Then 각 이동은 RS-086과 같은 결과이고 포커스가 같은 버튼에 남으며 "표를 차트 오른쪽에 놓았습니다(한 줄)" 같은 안내가 알려지고, Alt 없는 키는 아무것도 바꾸지 않으며, 타일이 하나면 옮기기 버튼이 없다

### RS-089 새 리포트 화면의 배치 변경은 요청·저장 안 됨·떠날 때 확인이 없고 초기화는 배치도 기본으로 되돌린다
- Given 조회가 끝난 새 리포트 화면
- When 배치만 바꾸고 링크를 누르고 "초기화"를 누르고, 다른 시나리오에서 컬럼도 바꾼 뒤 "초기화" → 확인한다
- Then 배치 변경은 저장 요청·"● 저장 안 됨"·떠날 때 확인이 없고, 배치만 바꾼 초기화는 확인 없이 기본 배치로, 컬럼도 바꾼 초기화는 "설계를 모두 지울까요?" 확인 뒤 설계와 배치가 함께 기본이 된다. 작성 탭에서 컬럼을 넣어도 배치는 그대로다

### RS-090 새 리포트 저장 요청에 배치를 보내고 새 편집 화면은 그 배치로 열린다
- Given 조회가 끝난 새 리포트 화면
- When 배치에 손대지 않고 저장하고, 다른 시나리오에서 "차트만"·차트 → 표 한 줄로 바꿔 저장한다
- Then 만들기 요청의 `layout`은 각각 DEFAULT와 `{chart, [chart, table], side_by_side}`이고 새 편집 화면의 결과 탭이 그 배치로 보인다

### RS-091 편집 화면은 저장된 배치로 열리고 보기·배치 변경만으로 저장 안 됨·떠날 때 확인이 생긴다
- Given 배치 CHART_SIDE로 저장된 리포트와 배치가 저장되지 않은 리포트
- When 각각 편집 화면을 열고, 첫째에서 타일을 옮기고·되돌리고, 보기를 바꾸고, 링크를 누른다
- Then 첫째 결과 탭은 차트 → 표 한 줄, 둘째는 표 → 차트 두 줄이고, 배치·보기 변경은 "● 저장 안 됨"과 떠날 때 확인을 만들며 원래 배치로 돌리면 둘 다 사라진다. 배치 변경은 다시 조회를 요구하지 않는다

### RS-092 편집 화면 배치는 스스로 저장되지 않고 덮어쓰기로 저장되며 되돌리기는 저장된 배치로 돌아간다
- Given 배치 CHART_SIDE로 저장된 리포트의 편집 화면
- When 배치를 TABLE_ONLY로 바꾸고 기다리고, "저장"하고, 다시 바꾼 뒤 "되돌리기"(확인)를 누른다
- Then 기다리는 동안 요청이 없고, 덮어쓰기 요청에 TABLE_ONLY가 실리며 실행 요청이 더 가지 않고 그 배치가 새 기준선이 되며, 배치만 바꾼 되돌리기도 확인 창을 거쳐 기본 배치가 아닌 TABLE_ONLY로 돌아가고 결과 표는 남는다

### RS-093 보기 화면은 저장된 배치로 열리고 저장 차트가 없으면 표만 보이며 차트 보기가 비활성이다
- Given 차트와 배치 CHART_SIDE가 저장된 리포트, 배치 `{chart, …}`인 리포트, 차트 없이 배치 BOTH_SIDE가 저장된 리포트
- When 각각 보기 화면을 연다
- Then 첫째는 차트 → 표 한 줄, 둘째는 차트 타일만이고 배치 저장 요청이 없으며, 탭·차트 설정·저장 버튼이 없다. 셋째는 표 타일만, "표+차트"·"차트만" 비활성(`title` "저장된 차트가 없습니다"), "표만" 선택 상태이고 저장된 배치는 바뀌지 않으며 차트 안내 문구(RC-R36)가 결과 위에 보인다. 수정 권한이 있으면 읽기 전용 안내가 없다

### RS-094 보기 화면에서 보기·놓기·키보드 이동은 바로 한 번 저장되고 상태 줄과 머리 메타가 바뀐다
- Given 내가 고칠 수 있는 리포트(revision 3)의 보기 화면, 응답을 잡아 둔 Fake gate
- When "표만"을 고르고, 응답을 풀고, 타일을 끌어 다른 타일 위로 지나가게 한 뒤 놓고, Alt+→로 옮긴다
- Then 첫 요청은 `PUT /reports/{id}/layout {layout: …, revision: 3}`이고 응답 전 "배치 저장 중…", 뒤 "배치를 저장했습니다"이며 머리의 최종 수정 시각·수정자가 응답 값으로 바뀌고 결과는 다시 조회하지 않는다. 끄는 동안에는 요청이 없고 놓을 때 한 번, 키보드 이동도 한 번 저장된다

### RS-095 배치가 바뀌지 않는 선택은 요청이 없고 다음 변경은 저장됨 표시를 지운다
- Given 저장된 보기가 "표+차트"인 보기 화면
- When "표+차트"를 다시 고르고, 표를 자기 자리(같은 결과)에 놓고, "표만"을 저장한 뒤 "차트만"을 고른다
- Then 앞의 둘은 요청이 없고, "배치를 저장했습니다"는 다음 변경과 함께 사라진다

### RS-096 요청 중의 여러 변경은 마지막 값 하나만 응답 revision으로 이어 보낸다
- Given 첫 배치 저장 응답을 gate로 잡아 둔 보기 화면(revision 3)
- When 요청 중에 배치를 세 번 바꾸고 첫 응답(revision 4)을 풀고, 다른 시나리오에서 요청 중 바꾼 값이 첫 응답 배치와 같게 한다
- Then 요청은 모두 두 번이고 동시에 하나만 가며, 두 번째 요청은 세 번째 값·revision 4를 싣고, 첫 응답이 와도 화면 배치는 세 번째 값 그대로다. 대기 값이 응답과 같으면 두 번째 요청이 없다(Fake gate로 순서를 고정한 순차 시나리오)

### RS-097 배치 저장 중에는 편집·복제를 쓸 수 없고 끝나면 다시 쓸 수 있다
- Given 배치 저장 응답을 잡아 둔 보기 화면
- When 배치를 바꿔 요청 중일 때 "편집"을 누르고, 요청 중에 한 번 더 바꾼 뒤 첫 응답만 풀고, 모두 끝낸다
- Then 요청 중·대기 값이 남은 동안 "편집"은 `aria-disabled`이고 눌러도 주소가 바뀌지 않으며 "복제"는 비활성이고 둘 다 `title` "배치를 저장하는 중입니다"이며 "다시 조회"는 켜져 있고, 모두 끝나면 다시 쓸 수 있다

### RS-098 보기 화면에서 복제하면 저장된 배치가 복사되고 요청에는 배치가 없다
- Given 배치 CHART_SIDE로 저장된 리포트의 보기 화면
- When "복제"로 새 리포트를 만든다
- Then 복제 요청 본문은 이름·설명·공개 범위뿐이고 새 리포트 편집 화면의 결과 탭은 CHART_SIDE다

### RS-099 배치 자동 저장이 409면 재시도 없이 최신 배치로 돌아가 다시 조회하고 안내한다
- Given 보기 화면을 연 뒤 다른 사용자가 리포트를 덮어써 배치 TABLE_ONLY·revision 2가 됨
- When 배치를 바꾸고(요청 중 한 번 더 바꿈), 최신 리포트를 다시 읽는 동안 또 바꾸고, 다시 읽은 뒤 배치를 바꾼다
- Then 첫 요청은 409이고 재시도·대기 값 전송 없이 화면 배치가 TABLE_ONLY로 바뀌며 실행 요청이 한 번 더 가고 알림 "다른 사람이 이 리포트를 먼저 수정해 최신 내용을 다시 불러왔습니다. 내가 바꾼 배치는 저장되지 않았습니다. 필요하면 배치를 다시 바꾸세요."가 보이며, 다시 읽는 동안의 변경은 보내지 않고, 그 뒤의 변경은 revision 2로 저장된다

### RS-100 배치 자동 저장이 403·404면 멈추고 안내하며 더 보내지 않는다
- Given 배치 저장에 403을, 다른 시나리오에서 404를 돌려주는 Fake
- When 배치를 바꾸고, 다시 바꾼다
- Then 403은 바꾼 배치가 화면에 남고 알림 "이 리포트를 수정할 권한이 없어 배치를 저장하지 못했습니다. 바꾼 배치는 이 화면에서만 유지됩니다.", 404는 알림 "리포트를 찾을 수 없어 배치를 저장하지 못했습니다. 목록에서 다시 확인하세요."와 링크 "리포트 목록"이며, 두 경우 모두 다음 변경에 요청이 없다

### RS-101 그 밖의 실패는 "다시 시도"로만 다시 보내고 다음 변경은 마지막 확인 revision을 쓴다
- Given 첫 배치 저장을 500으로 실패시키는 Fake(revision 3)
- When 배치를 바꾸고, 기다리고, "다시 시도"를 누르고, 다른 시나리오에서 실패 뒤 배치를 다시 바꾸고, 또 다른 시나리오에서 대기 값의 저장이 실패한다
- Then 알림 "배치를 저장하지 못했습니다. 잠시 뒤 다시 시도하세요."와 "다시 시도"가 보이고 자동 재시도가 없으며, "다시 시도"는 지금 화면 배치를 revision 3으로 보내고 알림을 지우고, 실패 뒤 다음 변경도 revision 3으로 가며, 대기 값 실패는 실패 상태로 끝나 요청이 더 없고 "편집"·"복제"가 다시 켜진다

### RS-102 수정 권한이 없으면 보기·배치는 화면에서만 바뀌고 요청·편집 링크가 없다
- Given 수정 권한 판정을 거짓으로 바꾼 보기 화면(RS-R43, 방어)
- When 보기를 바꾸고 타일을 옮긴다
- Then "보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다"가 보이고 화면은 바뀌지만 배치 저장 요청이 없으며 "편집"이 없다

### RS-103 게이트웨이는 저장 리포트 요청을 경로·snake_case 본문으로 보내고 응답을 camelCase로 바꾼다
- Given 서버 응답을 흉내 내는 fetch
- When `reports.list`·`get`·`create`·`update`·`copy`·`remove`·`run`을 부른다
- Then 각각 `GET /reports`, `GET /reports/{id}`, `POST /reports`, `PUT /reports/{id}`(본문에 `revision`), `POST /reports/{id}/copy`(메타만), `DELETE /reports/{id}`(본문 없는 성공), `POST /reports/{id}/run`이고, 본문은 snake_case이며 SQL·id·만든 사람이 없고, 응답 요약·상세는 camelCase(`updatedBy`, `generatedSql` 등)이며 실행 결과는 조회 결과와 같은 변환이다. HTTP 게이트웨이에 `reports`로 연결되어 있다

### RS-104 게이트웨이는 409 두 kind를 구분해 두고 위반·시간 초과·연결 실패를 ApiError로 준다
- Given 409 `already-exists`·409 `invalid-state`·422 `invalid-report`(errors)·503 `report-timeout`·연결 실패 응답
- When 저장·실행을 부른다
- Then `ApiError` kind가 각각 `already-exists`, `invalid-state`(둘 다 `conflict`로 바뀌지 않음), `invalid-report`(`problem.reportErrors`에 위치·code·문구), `report-timeout`, 네트워크 오류(PL-R39)다

### RS-105 게이트웨이는 배치를 그대로 옮기고 배치 저장에 layout·revision만 보낸다
- Given 상세·만들기·덮어쓰기·복제 응답의 `layout`, 목록 응답
- When 각각 받고, `saveReportLayout(7, {layout, revision: 3})`을 부르고, 그 요청이 409·422(layout 위치)·연결 실패가 되게 한다
- Then 배치는 값 그대로 옮겨지고 목록 항목에는 배치가 없으며, 요청은 `PUT /reports/7/layout` 본문 `{layout, revision: 3}`(다른 키 없음)이고 응답은 상세로 바뀌며, 409는 `invalid-state`, 422는 `reportErrors`의 `["layout", …]` 위치, 연결 실패는 네트워크 오류다

### RS-106 화면 데이터 캐시는 저장·배치 저장·삭제 뒤 정해진 캐시만 바꾸고 실패를 종류별로 나눈다
- Given 목록·상세·실행·필드 카탈로그 캐시가 채워진 화면 데이터 계층
- When 만들기·삭제를 하고, 숨긴 리포트 상세를 읽고, 실행 훅을 두 번 마운트하고, 여러 오류를 `saveFailure`로 나눈다
- Then 만들기는 상세 캐시에 응답을 넣고 목록만 다시 받으며 카탈로그를 다시 받지 않고, 삭제는 그 상세·실행 캐시를 지우고 목록을 다시 받으며, 숨긴 상세는 재시도 없이 not-found, 실행은 마운트마다 다시 가고, 분류는 `already-exists` → 이름, `invalid-state` → 충돌, `invalid-report` → 위반(항목 없으면 빈 목록), `forbidden`·`not-found`·그 밖 → 각 종류다

### RS-107 편집 화면에서 저장 안 됨일 때 뒤로 가기는 묻고 저장·되돌린 직후에는 묻지 않는다
- Given KIM이 자기 리포트 보기 화면 `/reports/<id>`에서 "편집"을 눌러 `/reports/<id>/edit`에 왔다
- When ① 컬럼을 하나 넣어 저장 안 됨인 채 뒤로 가기 → "머물기", 다시 뒤로 가기 → "떠나기". ② 바꾼 뒤 덮어쓰기 저장 직후 뒤로 가기. ③ 바꾼 뒤 "되돌리기" 직후 뒤로 가기
- Then ① 확인 창이 뜨고 머물기면 주소 `/reports/<id>/edit`·넣은 컬럼이 그대로, 떠나기면 `/reports/<id>`. ②③ 묻지 않고 `/reports/<id>`로 간다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 최초 작성(구현된 동작을 정본으로 옮김, 초안). functional `tests/functional/reports/test_saved_report_{editing,layout,open,permissions,resigned_owner}.py`의 시나리오를 케이스로 흡수(예전 형식 정의 읽기 3개 시나리오는 RQ로). Fake 보정 권고 RS-R47 ①~③ | RS-001~RS-106 |
| 2026-11-11 | 사용자 결정 반영: Fake를 서버에 맞춤(RS-R47 ①~③ 확정, RS-005·RS-021 층 both), 깨진 정의는 화면 배너만·화면 복구 불가 현행 문서화(RS-R17), 자동 저장은 순차 규칙(RS-R41), 저장 정의 읽기 변환은 RQ-R57·차트 저장 동작은 RC-R18~RC-R22 소유(RS-028의 차트 부분 → RC-038), RQ·RC 상호 참조를 규칙 번호로. 폐기한 케이스 없음 | RS-005·RS-021·RS-028·RS-066 변경 |
| 2026-11-18 | 확정(2026-11-18 사용자 확인): 편집 화면도 브라우저 뒤로·앞으로 가기 때 떠날 때 확인(RS-R32, 규칙은 RQ-R54) | 신규 RS-107 |
