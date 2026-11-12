# Status·Forecast 코드   (feature 코드: CD, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/domain/code/{values,entities,rules,errors}.py`, `app/application/code/*.py`, `app/web/routers/codes.py`, `app/web/schemas/code.py`, `app/infra/db/{code_repository,models_catalog}.py`, `app/infra/db/deal_action_repository.py::count_by_code`, `frontend/src/features/admin/deal-management/{DealManagementPage,CodeManager,CodeRow,InlineNameEdit}.tsx`, `data/codes.ts`, `gateway/http/codes.ts`, `gateway/http/mappers/code.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 화면·테스트·Fake가 어긋나는 점은 계획(`artifacts/10-analysis/cd-plan.md`)의 확인 필요 질문으로 분리했습니다.

## 1. 개요

- 목적: Deal의 진행 단계(Status)와 수주 전망(Forecast)에 쓰는 코드 목록을 admin이 관리한다(추가·이름 변경·순서 변경·삭제·사용 현황). 모든 화면은 이 목록(`GET /codes`)을 읽어 선택지·배지·필터를 그린다.
- 사용자(역할): admin(관리 전부), sales·user(조회만).
- 범위
  - Admin > Deal 관리(`/admin/deal`) 화면의 틀(탭 6개)과 "Status 코드"·"Forecast 코드" 탭
  - API `GET /codes`, `GET /codes/usage`, `POST /codes`, `PATCH /codes/{code_id}`, `PUT /codes/order`, `DELETE /codes/{code_id}`
  - 코드 이름·key·순서·잠금·결과(outcome)·확률 힌트 규칙, 삭제 판정(잠금·Deal 사용·Action 스냅숏 사용)
  - 기본 코드(시드)의 의미: 잠금 5개와 Forecast 결과(outcome)
- 범위 밖(다른 feature)
  - Status↔Forecast 동기화(계약완료 ↔ Won 등 잠금 key가 연결된 시스템 규칙) → DD. Won 진입·이탈 계약 처리 → LC
  - Deal·Action에 코드를 저장할 때의 검증(없는 key 거부 등) → DE·AC
  - 기본 시드를 마이그레이션이 넣는 일과 그 값 표 → SC(SC-R3, SC 2.2 "기본 시드")
  - 다른 탭(BANT Label·Action 유형·Vendor → CL, 경고 기준 → RK)의 내용
  - 공통 권한 판정·CSRF·Problem 형식·id 형식·NUL 공통 원칙·Admin 화면 가드·화면 오류 문구 → PL(PL-R2, PL-R4~R7, PL-R9~R12, PL-R15, PL-R16, PL-R31, PL-R35, PL-R37, PL-R39)
- 관련 화면·메뉴: Admin > Deal 관리(`/admin/deal`, Admin 서브 메뉴 "Deal 관리", PL-R35).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 종류(kind) | `status`(Deal 진행 단계) 또는 `forecast`(수주 전망). 표시 순서는 Status → Forecast |
| key | 코드의 내부 고유 값. 같은 종류 안에서 유일, 한 번 만들면 바뀌지 않는다. Deal·Action은 이 key로 코드를 가리킨다 |
| 이름 | 화면에 보이는 값. 바꿀 수 있다. 바꾸면 그 key를 쓰는 모든 화면에 새 이름이 보인다 |
| 순서(order) | 같은 종류 안의 표시 순서(1부터) |
| 잠금(locked) | 시스템 규칙이 key로 연결한 코드. 삭제할 수 없고 이름·순서는 바꿀 수 있다 |
| 결과(outcome) | Forecast 코드가 시스템에 알리는 결과 `open`·`won`·`lost`. Status와 사용자가 만든 코드는 항상 `open` |
| 확률 힌트 | Forecast 코드의 참고 문자열(예: `51–75`). 계산에 쓰지 않는다 |
| 사용 수(usage_count) | 그 코드를 **지금** 쓰는 Deal 수(Status는 Deal의 Status, Forecast는 Deal의 Forecast). Action 스냅숏은 세지 않는다 |
| Action 스냅숏 | Action 등록 때 Deal의 Status·Forecast key를 Action 행에 남긴 값(AC 소유). 삭제 판정에서만 사용으로 본다 |

### 2.2 데이터 모델

`codes`(PK `id` BIGINT identity — SC 공통 규칙, id는 앱이 할당)

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `kind` | varchar(20), CHECK `status`·`forecast` | 종류 |
| `key` | varchar(50), CHECK `^[a-z][a-z0-9_]{0,49}$`, UNIQUE (`kind`, `key`) `uq_codes_kind_key` | key(불변) |
| `name` | varchar(50), 유니크 인덱스 (`kind`, `lower(name)`) `uq_codes_kind_name_lower` | 이름 |
| `sort_order` | integer, CHECK `>= 1`, 인덱스 (`kind`, `sort_order`) | 순서(API `order`) |
| `outcome` | varchar(10), CHECK `open`·`won`·`lost`, CHECK Status면 `open` | 결과 |
| `probability_hint` | varchar(20) null, CHECK Status면 NULL | 확률 힌트 |
| `created_at`, `updated_at` | timestamptz | 등록·마지막 변경 시각(응답에 없음) |

- 참조: `deals`(`status_kind`,`status_key`)·(`forecast_kind`,`forecast_key`)와 `deal_actions`의 같은 두 쌍이 (`kind`,`key`)를 복합 FK(RESTRICT, 이름 `fk_deals_status_code`·`fk_deals_forecast_code`·`fk_deal_actions_status_code`·`fk_deal_actions_forecast_code`)로 가리킨다.
- 기본 시드 13행(Status 7·Forecast 6)의 값은 SC 2.2 "기본 시드" 표가 정본이다(마이그레이션 적용은 SC-R3). 이 문서는 그 값의 의미(CD-R3 잠금, CD-R4 결과)만 정한다.
- 값 객체: `CodeKind`(`status`·`forecast`), `ForecastOutcome`(`open`·`won`·`lost`), `CodeKey`(형식 위 CHECK와 같음, 아니면 "코드 key는 소문자로 시작하고 소문자, 숫자, '_'만 쓸 수 있습니다(50자 이내)"), 상수 `CODE_NAME_MAX` 50, `PROBABILITY_HINT_MAX` 20, `KEY_MAX` 50.
- 쓰기 유스케이스(등록·이름 변경·순서 변경·삭제)는 같은 종류를 트랜잭션 advisory lock(Status 7302001, Forecast 7302002)으로 잠근 뒤 그 종류의 행을 읽어 판정한다.

### 2.3 비즈니스 규칙

코드와 기본값
- **CD-R1** 코드 종류는 `status`·`forecast` 두 가지다. 코드 응답(`CodeResponse`) 필드는 정확히 `id`, `kind`, `key`, `name`, `order`, `locked`, `outcome`, `probability_hint`이고, 관리용 응답(`CodeUsageResponse`)은 여기에 `usage_count`를 더한다.
- **CD-R2** 새 시스템에는 기본 코드(SC 2.2 "기본 시드")가 있다: Status 7개(기회발굴 … 계약완료, order 1~7, 모두 `open`, 힌트 없음, `lost` key 없음), Forecast 6개(Pipeline·Best·Most Likely·Commit = `open`과 힌트 `0–50`·`51–75`·`75–85`·`85–100`(EN DASH), Won = `won`, Lost = `lost`, 힌트 없음, order 1~6).
- **CD-R3** 잠금 코드는 정확히 다섯 개다: Status `prospecting`·`contract_completed`, Forecast `pipeline`·`won`·`lost`. 잠금 여부는 key로 정해지며(`locked`), 잠금 코드는 이름·순서를 바꿀 수 있지만 삭제할 수 없다(CD-R15). 잠금 key가 어떤 시스템 규칙에 쓰이는지는 DD·LC가 정한다.
- **CD-R4** Status 코드는 결과가 항상 `open`이고 확률 힌트를 가질 수 없다. Forecast의 `won`·`lost` 결과는 기본 코드(Won·Lost)만 가진다. 새로 만든 코드는 종류와 무관하게 결과 `open`이다. 등록 뒤에는 결과·확률 힌트를 바꾸는 API가 없다(이름 변경·순서 변경은 이 둘을 건드리지 않는다).

조회
- **CD-R5** `GET /codes`는 로그인한 모든 역할이 부른다. 응답은 `{statuses: CodeResponse[], forecasts: CodeResponse[]}`이고 각 목록은 `order` 오름차순(같으면 id 오름차순)이다. 이름·순서를 바꾸면 다음 조회부터 그 값이 보인다.
- **CD-R6** `GET /codes/usage?kind=<status|forecast>`(admin 전용)는 그 종류의 코드만 CD-R5 순서로, 각 코드를 지금 쓰는 Deal 수(`usage_count`)와 함께 돌려준다. Status는 Deal의 Status key, Forecast는 Deal의 Forecast key 기준이고 쓰는 Deal이 없으면 0이다. Action 스냅숏(과거 Action 행의 Status·Forecast)은 세지 않는다. `kind`가 없거나 두 값이 아니면 422 `request-validation`.

이름·key
- **CD-R7** 이름 검증(등록·이름 변경 공통, 모두 422 `invalid-value`, 저장하지 않음): ① NUL 문자가 있으면 "이름에는 NUL 문자를 쓸 수 없습니다" ② 앞뒤 공백을 지운 값이 비면 "이름을 입력하세요." ③ 지운 값이 50자를 넘으면 "이름은 50자 이내로 입력하세요."(50자는 허용). 저장되는 이름은 앞뒤 공백을 지운 값이다. 자르지 않고 거절한다.
- **CD-R8** 이름은 같은 종류 안에서 대소문자를 무시하고 유일하다. 다른 코드와 겹치면 409 `already-exists` "같은 이름의 코드가 이미 있습니다."이고 저장하지 않는다(기본 코드 이름도 포함). 다른 종류의 코드와는 같은 이름을 쓸 수 있다. 이름 변경에서 자기 자신과만 겹치는 경우(대소문자만 바꿈)는 허용한다. DB 유니크 인덱스가 놓친 경우도 같은 409다.
- **CD-R9** key는 등록할 때 이름에서 만들어지고 바뀌지 않는다: 이름을 소문자로 바꾸고 `[a-z0-9]`가 아닌 글자 묶음을 `_` 하나로 바꾼 뒤 앞뒤 `_`를 지운다. 결과가 비면(영문·숫자 없음) 같은 종류에서 쓰지 않은 가장 작은 `code_<N>`(N=1부터). 숫자로 시작하면 앞에 `c_`를 붙인다. 50자로 자른다. 같은 종류에 같은 key가 있으면 `_2`, `_3` …을 붙이며(붙인 뒤에도 50자 이하가 되게 앞부분을 자름) 다른 종류의 key와는 겹쳐도 된다. 예: "Final Review" → `final_review`, "보류" → `code_1`, "Best!"(Forecast) → `best_2`, "Won"(Status) → `won`, "2026 Plan" → `c_2026_plan`.

등록
- **CD-R10** `POST /codes` 본문 `{kind, name, probability_hint?}`(admin 전용). 성공하면 201, `Location: /api/v1/codes/<id>`, 본문 `CodeUsageResponse`: 새 코드는 그 종류의 **맨 끝**(그 종류의 가장 큰 order + 1, 중간 빈 번호를 채우지 않음)에 놓이고 `locked` false, `outcome` `open`, `usage_count` 0, 등록·변경 시각 = 서버 시각이다.
- **CD-R11** 확률 힌트(등록 때만, 선택): 키 없음·null이면 없음. 문자열이면 ① NUL이 있으면 422 `invalid-value` "확률 힌트에는 NUL 문자를 쓸 수 없습니다" ② 앞뒤 공백을 지우고 비면 없음(null로 저장, Status도 허용) ③ Status인데 힌트가 남으면 422 `invalid-value` "Status에는 확률 힌트를 둘 수 없습니다." ④ 지운 값이 20자를 넘으면 422 `invalid-value` "확률 힌트는 20자 이내로 입력하세요."(20자는 허용). 거절되면 저장하지 않는다.
- **CD-R12** 등록 판정 순서: ① 요청 형식 422 `request-validation`(`kind`·`name` 누락, `kind`가 두 값이 아님, 문자열이 아님, 모르는 필드) ② 이름(CD-R7) ③ 이름 중복 409(CD-R8) ④ 확률 힌트(CD-R11).

이름 변경
- **CD-R13** `PATCH /codes/{code_id}` 본문 `{name}`(admin 전용). 판정 순서: 이름(CD-R7) 422 → 없는 id 404 `not-found` "코드을(를) 찾을 수 없습니다: <id>" → 중복(CD-R8) 409. 성공하면 200 `CodeUsageResponse`: 이름만 바뀌고 key·order·locked·outcome·확률 힌트는 그대로이며 변경 시각 = 서버 시각, `usage_count`는 CD-R6 값이다. 잠금 코드도 바꿀 수 있다.

순서 변경
- **CD-R14** `PUT /codes/order` 본문 `{kind, ordered_ids: int[]}`(admin 전용). `ordered_ids`는 그 종류의 **모든** 코드 id를 정확히 한 번씩 담아야 한다(빠짐·중복·없는 id·다른 종류 id·빈 목록이면 422 `invalid-value` "순서 목록이 올바르지 않습니다."이고 아무것도 바뀌지 않음). id는 JSON 정수만 받는다(문자열·실수·불리언은 422 `request-validation`, PL-R15). 성공하면 목록 순서대로 order를 1부터 다시 매기고(빈 번호가 메워짐) order가 바뀐 코드만 변경 시각을 갱신한다. 다른 종류는 그대로다. 응답은 200, 그 종류의 `CodeUsageResponse[]`(새 순서).

삭제
- **CD-R15** `DELETE /codes/{code_id}`(admin 전용). 판정 순서: 없는 id 404 `not-found` "코드을(를) 찾을 수 없습니다: <id>" → 잠금 코드 409 `invalid-state` "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."(쓰는 Deal 유무와 무관) → 그 코드를 쓰는 Deal이 있으면 409 `invalid-state` "사용 중인 코드는 삭제할 수 없습니다. (Deal <N>건)" → Deal은 없고 그 코드를 스냅숏으로 가진 Action이 있으면 409 `invalid-state` "사용 중인 코드는 삭제할 수 없습니다. (Action <N>건)". 통과하면 행을 지우고 204(본문 없음). 다른 Status·Forecast를 쓰는 Deal은 막지 않는다. 남은 코드의 order는 그대로이고(빈 번호가 생김) 다음 순서 변경 때 메워진다. 쓰던 Deal·Action이 모두 없어지면 지울 수 있다.
- **CD-R16** 사용 수 집계가 0이라고 했어도 DB FK가 연결을 막으면 같은 409이며, 문구의 N은 실제로 연결된 Deal 수(Deal이 없으면 Action 수)다.

화면(frontend, `/admin/deal`, 가드 PL-R31)
- **CD-R17** Deal 관리 화면 틀: 제목(h2) "Deal 관리", 탭 목록(이름 "Deal 관리 항목") 6개 — "Status 코드", "Forecast 코드", "BANT Label", "Action 유형", "Vendor", "경고 기준" 순서. 주소 `?tab=`의 값(`status`·`forecast`·`label`·`action-type`·`vendor`·`alert`)으로 탭을 열고, 없거나 모르는 값이면 "Status 코드"다. 탭을 고르면 주소를 이력 교체로 바꾸며 Status 코드 탭은 `tab` 파라미터를 지운다. Status·Forecast 탭은 같은 코드 관리 화면(CD-R18~R23)을 종류만 바꿔 쓰고, 다른 탭 내용은 CL·RK다.
- **CD-R18** 코드 표(표 이름 "Status 코드"·"Forecast 코드"): 위에 안내 "Won과 계약완료는 이름을 바꿔도 같은 의미로 동기화됩니다(CM-07). 이름과 순서를 바꾸면 목록·상세·필터에 바로 반영됩니다.". 머리글은 순서, 이름, 내부 코드, (Forecast만) 확률 참고, (Forecast만) 구분, 사용 중 Deal, 시스템, 작업. 칸 값: order, 이름, key, 확률 힌트(없으면 `-`), 구분 배지(`open`→"Open", `won`→"Won", `lost`→"Lost"), `usage_count`, 잠금이면 배지 "시스템 연결" 아니면 `-`. 행은 CD-R6 순서다. 읽는 동안 "불러오는 중…", 행이 없으면 "등록된 코드가 없습니다.", 읽기 실패는 오류 배너(PL-R37).
- **CD-R19** 이름 수정: 행의 "이름 수정"을 누르면 이름 칸이 입력(접근 이름 "코드 이름", 현재 이름, 자동 포커스)과 "저장"·"취소"로 바뀐다(그 행의 "이름 수정"은 비활성). "저장" 또는 Enter는 입력값을 그대로 보내고(화면 검증 없음), 성공하면 입력을 닫고 새 이름을 보인다. 실패하면 서버 문구를 오류 배너에 보이고 입력과 값을 그대로 둔다. "취소"·Esc는 요청 없이 닫는다.
- **CD-R20** 순서 변경: 행마다 "↑"(접근 이름 "<이름> 위로 이동")·"↓"("<이름> 아래로 이동"). 첫 행의 ↑, 마지막 행의 ↓는 비활성이다. 누르면 이웃과 자리를 바꾼 **그 종류 전체 id 목록**을 보내고 성공하면 새 순서로 다시 그린다. 실패하면 오류 배너다.
- **CD-R21** 추가: 표 아래 폼(이름 "<Status 코드|Forecast 코드> 추가")의 "새 코드 이름" 칸과 "추가" 버튼(요청 중 비활성), 안내 "내부 코드는 이름에서 자동으로 만들어지며 한 번 만들면 바뀌지 않습니다.". 화면 검증 없이 입력값을 보내며 확률 힌트 칸은 없다(항상 null 전송). 성공하면 입력을 비우고 목록을 다시 읽어 새 코드가 맨 끝에 사용 0으로 보인다. 실패하면 서버 문구를 오류 배너에 보이고 입력은 남긴다.
- **CD-R22** 삭제: 잠금 행의 "삭제"는 비활성이고 접근 설명이 "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."다. 다른 행의 "삭제"는 확인 대화상자(제목 "코드 삭제", 문구 "'<이름>' 코드를 삭제할까요? 사용 중인 코드는 삭제할 수 없습니다.", 위험 버튼 "삭제", "취소")를 연다. "삭제"를 누르면 요청하고 결과와 무관하게 대화상자를 닫으며, 거절되면 서버 문구를 오류 배너에 보이고 행은 남는다. "취소"는 요청 없이 닫는다.
- **CD-R23** 공통: 요청 중에는 이동·저장·삭제 버튼이 비활성이다. 새 작업(추가·이름 수정 시작·저장·이동·삭제 확인)을 시작하면 이전 오류 배너를 지운다. 캐시 갱신: 추가·삭제 성공 뒤 코드 조회 전체(코드 목록·사용 현황)를, 이름 변경·순서 변경 성공 뒤 코드 조회 전체와 Deal·Forecast 조회를 다시 읽게 한다.
- **CD-R24** 게이트웨이(`gateway/http/codes.ts`): `all` = `GET /codes`, `list(kind)` = `GET /codes/usage?kind=`, `create` = `POST /codes` 본문 `{kind, name, probability_hint}`(힌트가 없으면 null), `rename` = `PATCH /codes/{id}` `{name}`, `reorder` = `PUT /codes/order` `{kind, ordered_ids}`, `remove` = `DELETE /codes/{id}`(204 성공). 응답의 `probability_hint`·`usage_count`는 `probabilityHint`·`usageCount`로 바꾼다. `outcome`이 `open`·`won`·`lost`가 아니면 502 "서버 응답을 해석할 수 없습니다."로 거절한다. 오류는 PL-R39로 바꾼다(409 → `conflict`, 422 → `validation`).

### 2.4 상태와 전이

코드 한 줄의 상태는 "있음"과 "없음"뿐이다.

| 현재 | 행동 | 다음 | 조건 |
| --- | --- | --- | --- |
| (없음) | 등록 | 있음(맨 끝, `open`) | CD-R7~R12 |
| 있음 | 이름 변경·순서 변경 | 있음(key·결과 그대로) | CD-R13·R14, 잠금 코드도 가능 |
| 있음 | 삭제 | (없음) | 잠금 아님, Deal·Action 사용 없음(CD-R15) |
| 있음(잠금) | 삭제 | — | 409(CD-R15) |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /codes` | 401 | 가능 | 가능 | 가능 |
| `GET /codes/usage`, `POST /codes`, `PATCH /codes/{code_id}`, `PUT /codes/order`, `DELETE /codes/{code_id}` | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| 화면 `/admin/deal` | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

`GET /codes`는 업무 조회(PL-R2), 나머지는 관리자 전용(관리자 가드 PL-R7 "관리자 권한이 필요합니다", 상태 변경은 CSRF PL-R9)이다. 거절된 요청은 아무것도 바꾸지 않는다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/codes` | — | 200 `CodeSetResponse` `{statuses, forecasts}` | 401 |
| GET `/codes/usage` | query `kind`(`status`·`forecast`, 필수) | 200 `CodeUsageResponse[]` | 401, 403, 422 |
| POST `/codes` | `CodeCreateRequest` `{kind: CodeKind, name: str, probability_hint?: str\|null}` | 201 `CodeUsageResponse` + `Location: /api/v1/codes/<id>` | 401, 403, 409 `already-exists`, 422 `invalid-value`·`request-validation` |
| PUT `/codes/order` | `CodeOrderRequest` `{kind: CodeKind, ordered_ids: int[]}` | 200 `CodeUsageResponse[]` | 401, 403, 422 |
| PATCH `/codes/{code_id}` | `CodeRenameRequest` `{name: str}` | 200 `CodeUsageResponse` | 401, 403, 404, 409 `already-exists`, 422 |
| DELETE `/codes/{code_id}` | — | 204 | 401, 403, 404, 409 `invalid-state` |

- `CodeResponse`·`CodeUsageResponse` 필드는 CD-R1. 모든 본문은 모르는 필드를 거부한다(422 `request-validation`). `code_id` 형식은 PL-R15. `GET /codes/{code_id}`는 없다(405, 확인 필요 Q1).

### 2.7 화면 동작

CD-R17~CD-R24.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 이름에 NUL | 422 `invalid-value` | 이름에는 NUL 문자를 쓸 수 없습니다 |
| 이름 빈 값·공백뿐 | 422 `invalid-value` | 이름을 입력하세요. |
| 이름 50자 초과 | 422 `invalid-value` | 이름은 50자 이내로 입력하세요. |
| 같은 종류 이름 중복 | 409 `already-exists` | 같은 이름의 코드가 이미 있습니다. |
| 확률 힌트에 NUL | 422 `invalid-value` | 확률 힌트에는 NUL 문자를 쓸 수 없습니다 |
| Status에 확률 힌트 | 422 `invalid-value` | Status에는 확률 힌트를 둘 수 없습니다. |
| 확률 힌트 20자 초과 | 422 `invalid-value` | 확률 힌트는 20자 이내로 입력하세요. |
| 순서 목록 오류 | 422 `invalid-value` | 순서 목록이 올바르지 않습니다. |
| 없는 코드 | 404 `not-found` | 코드을(를) 찾을 수 없습니다: <id> |
| 잠금 코드 삭제 | 409 `invalid-state` | 시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다. |
| Deal이 쓰는 코드 삭제 | 409 `invalid-state` | 사용 중인 코드는 삭제할 수 없습니다. (Deal <N>건) |
| Action 스냅숏만 쓰는 코드 삭제 | 409 `invalid-state` | 사용 중인 코드는 삭제할 수 없습니다. (Action <N>건) |

화면 문구: CD-R18~CD-R22. 서버 문구 표시는 PL-R37.

## 3. Business use case

### CD-UC1 코드 목록 조회
- 행위자: 로그인한 모든 역할(Deal 폼·목록·상세·Dashboard·Forecast 화면이 선택지·배지로 사용)
- 사전 조건: 로그인
- 기본 흐름: `GET /codes` → Status·Forecast를 순서대로 받는다(CD-R1~R5)
- 예외: 미인증 401(PL)
- 결과: 현재 이름·순서·잠금·결과·힌트를 가진 코드 목록

### CD-UC2 코드 사용 현황 보기
- 행위자: admin
- 사전 조건: `/admin/deal`(Status 코드 또는 Forecast 코드 탭)
- 기본 흐름: 화면이 `GET /codes/usage?kind=`로 그 종류를 읽어 표로 보인다(CD-R6, CD-R17·R18)
- 대안: 주소 `?tab=forecast`로 Forecast 탭을 바로 연다
- 예외: 읽기 실패 오류 배너
- 결과: 코드별 사용 중 Deal 수와 잠금 표시

### CD-UC3 코드 추가
- 행위자: admin
- 기본 흐름: 새 코드 이름 입력 → 추가 → 201, 맨 끝에 사용 0으로 보인다(CD-R7~R12, CD-R21)
- 대안: API로 Forecast에 확률 힌트를 함께 준다(화면에는 힌트 칸 없음)
- 예외: 이름 빈 값·50자 초과·NUL 422, 같은 종류 중복 409, Status 힌트·힌트 20자 초과 422
- 결과: 이름에서 만든 key를 가진 `open` 코드

### CD-UC4 코드 이름 변경
- 행위자: admin
- 기본 흐름: 이름 수정 → 새 이름 → 저장(또는 Enter) → 200, 모든 화면에 새 이름(CD-R13, CD-R19)
- 대안: 잠금 코드도 바꾼다, Esc·취소로 그만둔다
- 예외: 이름 오류 422, 중복 409, 없는 코드 404
- 결과: key·순서·잠금·결과는 그대로이고 이름만 바뀐다

### CD-UC5 코드 순서 변경
- 행위자: admin
- 기본 흐름: ↑/↓ → 종류 전체 id 목록 전송 → 200, 1부터 다시 매긴 순서(CD-R14, CD-R20)
- 예외: 목록 오류 422(화면은 항상 전체 목록을 보냄)
- 결과: 모든 화면의 선택지·목록이 새 순서를 따른다

### CD-UC6 코드 삭제
- 행위자: admin
- 기본 흐름: 삭제 → 확인 → 204, 표에서 사라진다(CD-R15·R16, CD-R22)
- 대안: 확인 대화상자에서 취소
- 예외: 잠금 409(화면은 버튼 비활성), Deal 사용 409(Deal N건), Action 스냅숏 사용 409(Action N건), 없는 코드 404
- 결과: 쓰이지 않는 코드만 지워진다

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), VIEWER(user). backend 케이스는 기본 코드(CD-R2)를 넣은 Fake UoW로 유스케이스를 부르는 단위 테스트(application·domain)와, Fake 유스케이스로 라우터를 부르는 web 단위 테스트다. frontend 케이스는 Fake 게이트웨이(기본 코드 + Fake Deal 시드: 가격협상을 쓰는 Deal 4건, Commit을 쓰는 Deal 1건 이상)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| CD-001 | 어떤 역할이든 기본 Status 7개·Forecast 6개를 이름·순서·잠금·결과·힌트와 함께 순서대로 받는다 | CD-R1, CD-R2, CD-R3, CD-R5, CD-UC1 | backend | `application/test_code_queries.py`, `web/test_code_routes.py` |
| CD-002 | 순서를 바꾼 코드는 조회 결과에서도 그 순서를 따른다 | CD-R5, CD-UC1 | backend | `application/test_code_queries.py` |
| CD-003 | 잠금은 정해진 다섯 key에만 있다 | CD-R3 | backend | `application/test_code_queries.py`, `domain/test_code_values.py`, `domain/test_code_entity.py` |
| CD-004 | Status 사용 수는 그 Status를 쓰는 Deal 수이고 Deal이 없으면 모두 0이다 | CD-R6, CD-UC2 | backend | `application/test_code_queries.py`, `application/test_code_label_usage.py` |
| CD-005 | Forecast 사용 수는 그 Forecast를 쓰는 Deal 수다 | CD-R6, CD-UC2 | backend | `application/test_code_queries.py`, `application/test_code_label_usage.py` |
| CD-006 | 사용 현황은 요청한 종류의 코드만 순서대로 돌려준다 | CD-R6, CD-UC2 | backend | `application/test_code_queries.py`, `web/test_code_routes.py` |
| CD-007 | 사용 수는 Action 스냅숏을 세지 않고 Deal의 현재 값만 센다 | CD-R6, CD-UC2 | backend | `application/test_code_delete_action_usage.py` |
| CD-008 | 사용 현황 요청의 kind가 없거나 잘못되면 422 request-validation이다 | CD-R6, CD-UC2 | backend | `web/test_code_routes.py` |
| CD-009 | Status를 추가하면 key가 만들어지고 맨 끝에 open·힌트 없음·사용 0으로 201과 Location이 돌아온다 | CD-R9, CD-R10, CD-UC3 | backend | `application/test_code_register_rename.py`, `web/test_code_routes.py` |
| CD-010 | Forecast를 확률 힌트와 함께 추가하면 open으로 맨 끝에 놓이고 힌트가 저장된다 | CD-R4, CD-R10, CD-R11, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-011 | 이름의 앞뒤 공백은 지워서 저장한다 | CD-R7, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-012 | 이름 50자는 허용되고 51자는 422이며 저장되지 않는다 | CD-R7, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-013 | 빈 이름·공백뿐인 이름은 422 "이름을 입력하세요."이고 저장되지 않는다 | CD-R7, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-014 | 이름에 NUL이 있으면 422이고 코드가 늘지 않는다 | CD-R7, CD-UC3 | backend | `application/test_code_register_rename.py` |
| CD-015 | 같은 종류에 대소문자·앞뒤 공백만 다른 이름(기본 코드 포함)을 추가하면 409이고 저장되지 않는다 | CD-R8, CD-R12, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py`, `domain/test_code_errors.py` |
| CD-016 | 다른 종류의 코드와 같은 이름은 추가할 수 있다 | CD-R8, CD-UC3 | backend | `application/test_code_register_rename.py` |
| CD-017 | 영문이 없는 이름의 key는 쓰지 않은 code_N 순번이다 | CD-R9, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-018 | key가 같은 종류에서 겹치면 번호가 붙고 다른 종류와는 겹쳐도 된다 | CD-R9, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-019 | key는 소문자·밑줄로 정리되고 숫자로 시작하면 c_가 붙으며 50자를 넘지 않는다 | CD-R9 | backend | `domain/test_code_rules.py`, `domain/test_code_values.py` |
| CD-020 | 중간 순서가 비어 있어도 새 코드는 가장 큰 순서 + 1에 놓인다 | CD-R10, CD-UC3 | backend | `application/test_code_register_rename.py` |
| CD-021 | 확률 힌트는 앞뒤 공백이 지워지고 빈 값이면 없음으로 저장된다(Status도) | CD-R11, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-022 | 확률 힌트 20자는 허용되고 21자는 422이며 저장되지 않는다 | CD-R11, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-023 | Status에 확률 힌트를 주면 422이고 저장되지 않는다 | CD-R4, CD-R11, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-024 | 확률 힌트에 NUL이 있으면 422이고 코드가 늘지 않는다 | CD-R11, CD-UC3 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-025 | 이름을 바꾸면 이름만 바뀌고 key·순서는 그대로이며 사용 수가 함께 돌아온다 | CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-026 | 잠금 코드도 이름을 바꿀 수 있고 잠금·결과는 그대로다 | CD-R3, CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py`, `domain/test_code_entity.py` |
| CD-027 | 자기 이름의 대소문자만 바꾸는 것은 허용된다 | CD-R8, CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-028 | 같은 종류의 다른 코드 이름으로 바꾸면 409이고 이름은 그대로다 | CD-R8, CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py`, `domain/test_code_rules.py` |
| CD-029 | 빈 이름·51자·NUL 이름으로 바꾸면 422이고 이름은 그대로다 | CD-R7, CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py` |
| CD-030 | 없는 코드의 이름을 바꾸면 404다 | CD-R13, CD-UC4 | backend | `application/test_code_register_rename.py` |
| CD-031 | 전체 id 목록으로 순서를 바꾸면 1부터 다시 매긴 새 순서가 돌아오고 조회도 그 순서다 | CD-R14, CD-UC5 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_rules.py` |
| CD-032 | 순서 변경은 순서가 바뀐 코드만 변경 시각을 갱신한다 | CD-R14, CD-UC5 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_rules.py` |
| CD-033 | 한 종류의 순서를 바꿔도 다른 종류는 그대로다 | CD-R14, CD-UC5 | backend | `application/test_code_reorder_delete.py` |
| CD-034 | 순서 변경은 삭제로 생긴 빈 번호를 메운다 | CD-R14, CD-R15, CD-UC5 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_rules.py` |
| CD-035 | 빠진·중복·다른 종류·빈 id 목록은 422 "순서 목록이 올바르지 않습니다."이고 순서가 그대로다 | CD-R14, CD-UC5 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_rules.py` |
| CD-036 | 순서 목록의 id가 정수가 아니면 422 request-validation이다 | CD-R14, CD-UC5 | backend | `web/test_code_order_request.py`, `web/test_code_routes.py` |
| CD-037 | 잠금 코드는 쓰는 Deal이 없어도 409이고 남는다 | CD-R3, CD-R15, CD-UC6 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_entity.py` |
| CD-038 | 잠금 코드를 Deal이 쓰고 있으면 잠금 문구가 먼저다 | CD-R15, CD-UC6 | backend | `application/test_code_reorder_delete.py`, `domain/test_code_entity.py`, `domain/test_code_in_use_by_actions.py` |
| CD-039 | 쓰이지 않는 일반 코드는 지워지고 다른 코드와 다른 코드를 쓰는 Deal은 영향이 없다 | CD-R15, CD-UC6 | backend | `application/test_code_reorder_delete.py`, `application/test_code_delete_action_usage.py`, `application/test_code_label_usage.py`, `domain/test_code_entity.py` |
| CD-040 | Deal이 쓰는 Status·Forecast 코드는 409이고 문구에 Deal 수가 들어가며 남는다 | CD-R15, CD-UC6 | backend | `application/test_code_reorder_delete.py`, `application/test_code_label_usage.py`, `domain/test_code_entity.py`, `domain/test_code_in_use_unit.py` |
| CD-041 | 집계가 놓친 Deal 연결도 실제 Deal 수가 든 같은 409로 거절된다 | CD-R16, CD-UC6 | backend | `application/test_code_label_usage.py` |
| CD-042 | Deal은 안 쓰고 Action 스냅숏만 쓰는 코드는 409이고 문구에 Action 수가 들어간다 | CD-R15, CD-UC6 | backend | `application/test_code_delete_action_usage.py`, `domain/test_code_in_use_by_actions.py` |
| CD-043 | Deal과 Action이 함께 쓰는 코드는 Deal 수 문구가 먼저다 | CD-R15, CD-UC6 | backend | `application/test_code_delete_action_usage.py`, `domain/test_code_in_use_by_actions.py` |
| CD-044 | 코드를 쓰던 마지막 Deal·Action이 없어지면 코드를 지울 수 있다 | CD-R15, CD-UC6 | backend | `application/test_code_delete_action_usage.py`, `domain/test_code_in_use_by_actions.py` |
| CD-045 | 없는 코드를 지우면 404다 | CD-R15, CD-UC6 | backend | `application/test_code_reorder_delete.py` |
| CD-046 | sales·user의 관리 요청은 403 관리자 문구이고 아무것도 바뀌지 않는다 | CD-R6, CD-R10, CD-R13, CD-R14, CD-R15, CD-UC2~UC6 | backend | `web/test_code_routes.py` |
| CD-047 | 화면: Deal 관리는 탭 6개를 순서대로 보이고 Status 코드 탭에서 시작한다 | CD-R17, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-048 | 화면: 주소의 tab 값으로 탭을 열고 모르는 값이면 Status 코드 탭이다 | CD-R17, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-049 | 화면: Won·계약완료 동기화 안내를 보인다 | CD-R18, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-050 | 화면: Status 표는 7개를 순서대로 순서·이름·내부 코드·사용 건수와 함께 보인다 | CD-R18, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-051 | 화면: 잠금 행은 "시스템 연결" 배지와 이유가 붙은 비활성 삭제 버튼을 가진다 | CD-R18, CD-R22, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-052 | 화면: Forecast 표는 6개를 확률 참고·구분(Open/Won/Lost)과 함께 보인다 | CD-R18, CD-UC2 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-053 | 화면: 이름을 표 안에서 바꾸면(저장·Enter) 새 이름이 보이고 잠금 코드도 key가 그대로다 | CD-R19, CD-UC4 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-054 | 화면: Esc로 이름 수정을 그만두면 요청 없이 원래 이름이 남는다 | CD-R19, CD-UC4 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-055 | 화면: 중복 이름이면 서버 문구를 보이고 입력을 유지한다 | CD-R19, CD-UC4 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-056 | 화면: 빈 이름으로 저장하면 서버 문구를 보인다 | CD-R19, CD-UC4 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-057 | 화면: ↑/↓로 코드를 이웃과 자리 바꾼다 | CD-R20, CD-UC5 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-058 | 화면: 첫 행의 ↑와 마지막 행의 ↓는 비활성이다 | CD-R20, CD-UC5 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-059 | 화면: 코드를 추가하면 맨 끝에 사용 0으로 보이고 입력이 비워진다 | CD-R21, CD-UC3 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-060 | 화면: 빈 이름으로 추가하면 서버 문구를 보인다 | CD-R21, CD-UC3 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-061 | 화면: 쓰이지 않는 코드를 확인 뒤 삭제하면 표에서 사라진다 | CD-R22, CD-UC6 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-062 | 화면: 삭제 확인을 취소하면 코드가 남는다 | CD-R22, CD-UC6 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-063 | 화면: Deal이 쓰는 Status·Forecast 삭제는 거절 문구를 보이고 대화상자를 닫으며 행이 남는다 | CD-R22, CD-UC6 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-064 | 화면: Forecast 추가·순서 변경은 Status와 따로 동작한다 | CD-R20, CD-R21, CD-UC3, CD-UC5 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-065 | 화면: Won은 삭제할 수 없지만 이름은 바꿀 수 있다 | CD-R19, CD-R22, CD-UC4 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-066 | 화면: 새 작업을 시작하면 이전 오류 배너가 사라진다 | CD-R23 | frontend | `features/admin/deal-management/CodeManager.test.tsx` |
| CD-067 | 화면: 이름·순서를 바꾸면 Deal·Forecast 조회를 다시 읽게 한다 | CD-R23, CD-UC4, CD-UC5 | frontend | `data/codes.test.tsx` |
| CD-068 | 게이트웨이: 코드 목록·사용 현황을 읽어 화면 값으로 바꾼다 | CD-R24, CD-UC1, CD-UC2 | frontend | `gateway/http/codes.test.ts` |
| CD-069 | 게이트웨이: 추가·이름 변경·순서 변경·삭제를 계약대로 보내고 거절을 서버 문구의 오류로 바꾼다 | CD-R24, CD-UC3~UC6 | frontend | `gateway/http/codes.test.ts` |
| CD-070 | 게이트웨이: 모르는 결과(outcome)는 해석 불가 오류로 거절한다 | CD-R24, CD-UC1 | frontend | `gateway/http/codes.test.ts`, `gateway/http/mappers/code.test.ts` |
| CD-071 | Fake 게이트웨이는 서버와 같은 규칙·문구로 코드 요청에 답한다 | CD-R7, CD-R8, CD-R10, CD-R13~R15, CD-R24 | frontend | `test/fake/gateway/codes.test.ts` |

### CD-001 어떤 역할이든 기본 Status 7개·Forecast 6개를 이름·순서·잠금·결과·힌트와 함께 순서대로 받는다
- Given 기본 코드만 있는 시스템
- When `GET /codes`로 코드 목록을 읽는다(유스케이스 `ListCodeSet`, 역할 허용은 PL 권한 표)
- Then `statuses`는 SC 2.2 순서의 7개이고 각 (key, 이름, order, locked, outcome, 힌트)가 (prospecting 기회발굴 1 true open null) … (contract_completed 계약완료 7 true open null)이며 `lost` key가 없다. `forecasts`는 6개이고 pipeline·won·lost만 잠금, Won·Lost의 결과는 `won`·`lost`, 나머지는 `open`과 `0–50`·`51–75`·`75–85`·`85–100` 힌트다

### CD-002 순서를 바꾼 코드는 조회 결과에서도 그 순서를 따른다
- Given 첫 Status의 order를 99로 바꿔 둔다
- When 코드 목록을 읽는다
- Then 그 Status가 `statuses`의 맨 끝이다

### CD-003 잠금은 정해진 다섯 key에만 있다
- When 종류·key별 코드의 `locked`를 본다
- Then Status `prospecting`·`contract_completed`, Forecast `pipeline`·`won`·`lost`만 true이고 그 밖의 key(예: Status `introduction`, Forecast `best`, Status `won`)는 false다

### CD-004 Status 사용 수는 그 Status를 쓰는 Deal 수이고 Deal이 없으면 모두 0이다
- Given (a) Deal 없음 (b) Status 기회발굴 Deal 2건·제품소개 Deal 1건
- When `GET /codes/usage?kind=status`
- Then (a) 7개 모두 0 (b) prospecting 2, introduction 1, 나머지 0이고 순서는 기본 순서다

### CD-005 Forecast 사용 수는 그 Forecast를 쓰는 Deal 수다
- Given Forecast Best Deal 2건, Commit Deal 1건
- When `GET /codes/usage?kind=forecast`
- Then best 2, commit 1, 나머지 0이다

### CD-006 사용 현황은 요청한 종류의 코드만 순서대로 돌려준다
- When `kind=forecast`로 사용 현황을 읽는다
- Then 모든 항목의 `kind`가 `forecast`이고 기본 순서(pipeline … lost)다

### CD-007 사용 수는 Action 스냅숏을 세지 않고 Deal의 현재 값만 센다
- Given Deal이 제품소개일 때 Action을 남기고(스냅숏 introduction) Deal을 POC준비로 옮긴다
- When Status 사용 현황을 읽는다
- Then introduction 0, poc_preparation 1이다

### CD-008 사용 현황 요청의 kind가 없거나 잘못되면 422 request-validation이다
- Given ROOT로 로그인
- When `GET /codes/usage`(kind 없음), `GET /codes/usage?kind=deal`
- Then 둘 다 422 `request-validation`이고 유스케이스를 부르지 않는다

### CD-009 Status를 추가하면 key가 만들어지고 맨 끝에 open·힌트 없음·사용 0으로 201과 Location이 돌아온다
- Given ROOT로 로그인, 기본 코드
- When `POST /codes` `{"kind": "status", "name": "Final Review"}`
- Then 201, `Location: /api/v1/codes/<새 id>`, 본문 `key` "final_review", `name` "Final Review", `order` 8, `locked` false, `outcome` "open", `probability_hint` null, `usage_count` 0이다. Status 목록의 맨 끝이 이 코드이고 등록 시각은 서버 시각이다

### CD-010 Forecast를 확률 힌트와 함께 추가하면 open으로 맨 끝에 놓이고 힌트가 저장된다
- When `{"kind": "forecast", "name": "Upside", "probability_hint": "10-20"}`로 등록한다
- Then 201, `key` "upside", `order` 7, `outcome` "open", `probability_hint` "10-20"이다. 힌트를 주지 않으면 `probability_hint`는 null이다

### CD-011 이름의 앞뒤 공백은 지워서 저장한다
- When 이름 "  Final Review  "로 Status를 등록한다
- Then 이름 "Final Review", key "final_review"다

### CD-012 이름 50자는 허용되고 51자는 422이며 저장되지 않는다
- When 이름 "가"×50, "가"×51, 앞뒤 공백으로 감싼 "가"×50으로 각각 등록한다
- Then "가"×50과 감싼 값은 201(저장 이름 50자), "가"×51은 422 `invalid-value` "이름은 50자 이내로 입력하세요."이고 그 요청 뒤 Status 수는 요청 전과 같다

### CD-013 빈 이름·공백뿐인 이름은 422 "이름을 입력하세요."이고 저장되지 않는다
- When 이름 "", "   "로 각각 Status를 등록한다
- Then 422 `invalid-value` "이름을 입력하세요."이고 Status는 7개 그대로다

### CD-014 이름에 NUL이 있으면 422이고 코드가 늘지 않는다
- When 이름 "a\x00b", "\x00", "name\x00"으로 각각 Status를 등록한다
- Then 422 `invalid-value` "이름에는 NUL 문자를 쓸 수 없습니다"이고 Status는 7개 그대로다

### CD-015 같은 종류에 대소문자·앞뒤 공백만 다른 이름(기본 코드 포함)을 추가하면 409이고 저장되지 않는다
- Given Status "Final Review"가 있다
- When Status "final review", "FINAL REVIEW", " Final Review ", "기회발굴"과 Forecast "commit", "BEST"를 각각 등록한다
- Then 모두 409 `already-exists` "같은 이름의 코드가 이미 있습니다."이고 그 종류의 코드 수는 그대로다. 이름이 중복이면서 Status에 힌트를 준 요청도 409다(중복 판정이 먼저)

### CD-016 다른 종류의 코드와 같은 이름은 추가할 수 있다
- When Status "Best"를 등록한다(Forecast에 "Best"가 있음)
- Then 201, key "best"다

### CD-017 영문이 없는 이름의 key는 쓰지 않은 code_N 순번이다
- When Status "보류", 이어서 "검토 중"을 등록한다
- Then key는 각각 "code_1", "code_2"이고 order는 8, 9다. `code_1`이 이미 있으면 다음 영문 없는 이름은 쓰지 않은 가장 작은 번호를 받는다

### CD-018 key가 같은 종류에서 겹치면 번호가 붙고 다른 종류와는 겹쳐도 된다
- When Forecast "Best!", Status "Won"을 각각 등록한다
- Then Forecast는 key "best_2"(Best와 key만 겹침), Status는 key "won"이다. 같은 key가 계속 겹치면 `_3`, `_4`…다

### CD-019 key는 소문자·밑줄로 정리되고 숫자로 시작하면 c_가 붙으며 50자를 넘지 않는다
- When 이름에서 key를 만든다: "Final  Review!!", "--Deal Close--", "2026 Plan", "123", "POC준비 Stage", 영문 60자, 영문 50자(같은 key가 이미 있음)
- Then "final_review", "deal_close", "c_2026_plan", "c_123", "poc_stage", 앞 50자, 앞 48자 + "_2"(50자)이고 모두 key 형식(소문자 시작, 소문자·숫자·`_`, 50자 이하)에 맞는다

### CD-020 중간 순서가 비어 있어도 새 코드는 가장 큰 순서 + 1에 놓인다
- Given Status 제품소개(order 2)를 지워 두었다
- When Status "Final Review"를 등록한다
- Then order는 8이다

### CD-021 확률 힌트는 앞뒤 공백이 지워지고 빈 값이면 없음으로 저장된다(Status도)
- When Forecast "Upside"를 힌트 "  10-20  ", "", "   "로 각각 등록하고, Status "Final Review"를 힌트 "", "   "로 각각 등록한다
- Then Forecast는 201이고 힌트 "10-20", null, null이다. Status도 201이고 힌트 null이다

### CD-022 확률 힌트 20자는 허용되고 21자는 422이며 저장되지 않는다
- When Forecast "Upside"를 힌트 "9"×20, "9"×21로 각각 등록한다
- Then 20자는 201, 21자는 422 `invalid-value` "확률 힌트는 20자 이내로 입력하세요."이고 21자 요청 뒤 Forecast 수는 요청 전과 같다

### CD-023 Status에 확률 힌트를 주면 422이고 저장되지 않는다
- When `{"kind": "status", "name": "Final Review", "probability_hint": "10-20"}`
- Then 422 `invalid-value` "Status에는 확률 힌트를 둘 수 없습니다."이고 Status는 7개 그대로다

### CD-024 확률 힌트에 NUL이 있으면 422이고 코드가 늘지 않는다
- When Forecast "Upside"를 힌트 "1\x002", "\x00", "10-20\x00"으로 각각 등록한다
- Then 422 `invalid-value` "확률 힌트에는 NUL 문자를 쓸 수 없습니다"이고 Forecast는 6개 그대로다

### CD-025 이름을 바꾸면 이름만 바뀌고 key·순서는 그대로이며 사용 수가 함께 돌아온다
- Given 제품소개를 쓰는 Deal 2건
- When 제품소개를 "  소개  "로 바꾼다(`PATCH /codes/{id}`)
- Then 200, `name` "소개", `key` "introduction", `order` 2, `locked` false, `usage_count` 2이고 저장된 변경 시각은 서버 시각이다. 코드 목록에도 "소개"가 보인다

### CD-026 잠금 코드도 이름을 바꿀 수 있고 잠금·결과는 그대로다
- When Status 계약완료를 "수주 완료"로, Forecast Won을 "수주"로 바꾼다
- Then 둘 다 200이고 key(`contract_completed`·`won`), `locked` true, order, `outcome`(`open`·`won`)이 그대로다

### CD-027 자기 이름의 대소문자만 바꾸는 것은 허용된다
- When POC완료를 "poc완료"로, Best를 "BEST"로 바꾼다
- Then 200이고 새 이름이 저장된다

### CD-028 같은 종류의 다른 코드 이름으로 바꾸면 409이고 이름은 그대로다
- When 제품소개를 "기회발굴"로, Best를 "commit"으로 바꾼다
- Then 409 `already-exists` "같은 이름의 코드가 이미 있습니다."이고 이름은 "제품소개"·"Best" 그대로다

### CD-029 빈 이름·51자·NUL 이름으로 바꾸면 422이고 이름은 그대로다
- When 제품소개를 "", "   ", "가"×51, "a\x00b"로 각각 바꾼다
- Then 422 `invalid-value`(문구는 CD-R7)이고 이름은 "제품소개" 그대로다

### CD-030 없는 코드의 이름을 바꾸면 404다
- When 없는 id로 이름을 "아무거나"로 바꾼다
- Then 404 `not-found` "코드을(를) 찾을 수 없습니다: <id>"다

### CD-031 전체 id 목록으로 순서를 바꾸면 1부터 다시 매긴 새 순서가 돌아오고 조회도 그 순서다
- When Status 전체 id를 거꾸로 해 `PUT /codes/order`(Forecast도 각각)
- Then 200, 응답 id 순서가 보낸 순서이고 order는 1~7(Forecast 1~6)이며 사용 수가 함께 있다. 코드 목록도 거꾸로 된 key 순서다

### CD-032 순서 변경은 순서가 바뀐 코드만 변경 시각을 갱신한다
- Given 시계를 60초 앞으로 돌린다
- When Status의 마지막 두 개만 자리를 바꾼 전체 목록을 보낸다
- Then 그 두 코드만 변경 시각이 바뀌고 나머지는 그대로다

### CD-033 한 종류의 순서를 바꿔도 다른 종류는 그대로다
- When Status 순서를 거꾸로 바꾼다
- Then Forecast의 (key, order)는 바뀌기 전과 같다

### CD-034 순서 변경은 삭제로 생긴 빈 번호를 메운다
- Given 제품소개를 지워 order 2가 비어 있다
- When 남은 Status 6개를 지금 순서대로 보낸다
- Then order가 1~6이다

### CD-035 빠진·중복·다른 종류·빈 id 목록은 422 "순서 목록이 올바르지 않습니다."이고 순서가 그대로다
- When Status 순서를 (a) 마지막 id를 뺀 목록 (b) 마지막 대신 첫 id를 한 번 더 넣은 목록 (c) 마지막 대신 Forecast id를 넣은 목록 (d) 없는 id를 넣은 목록 (e) 빈 목록으로 보낸다(Forecast에 Status id를 섞는 경우도)
- Then 모두 422 `invalid-value` "순서 목록이 올바르지 않습니다."이고 그 종류의 (key, order)가 그대로다

### CD-036 순서 목록의 id가 정수가 아니면 422 request-validation이다
- When `ordered_ids`에 `"7"`, `1.5`, `true`, 숫자 문자열 목록을 담아 보낸다
- Then 422 `request-validation`이다. 정수 목록(최대 2^53−1 포함)은 보낸 순서 그대로 받아들인다

### CD-037 잠금 코드는 쓰는 Deal이 없어도 409이고 남는다
- When 다섯 잠금 코드를 각각 삭제한다
- Then 409 `invalid-state` "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."이고 코드는 그대로다

### CD-038 잠금 코드를 Deal이 쓰고 있으면 잠금 문구가 먼저다
- Given 기회발굴을 쓰는 Deal 1건
- When 기회발굴을 삭제한다
- Then 409 잠금 문구(CD-037과 같음)다

### CD-039 쓰이지 않는 일반 코드는 지워지고 다른 코드와 다른 코드를 쓰는 Deal은 영향이 없다
- Given 제품소개를 쓰는 Deal 3건, Action 1건(다른 코드 스냅숏)
- When POC완료, Forecast Best(쓰는 Deal 없음, Commit을 쓰는 Deal은 있음), Status 기술평가, Forecast Most Likely를 각각 삭제한다
- Then 204이고 그 코드만 사라진다. 남은 코드의 순서·id 목록은 지운 것만 빠진 그대로다

### CD-040 Deal이 쓰는 Status·Forecast 코드는 409이고 문구에 Deal 수가 들어가며 남는다
- Given POC준비를 쓰는 Deal 2건, Best를 쓰는 Deal 1건
- When POC준비와 Best를 각각 삭제한다
- Then 409 `invalid-state` "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"·"(Deal 1건)"이고 두 코드는 남는다

### CD-041 집계가 놓친 Deal 연결도 실제 Deal 수가 든 같은 409로 거절된다
- Given Best를 쓰는 Deal 1건이 있고 사용 수 집계는 0을 돌려준다(Fake로 낡은 집계를 흉내 냄)
- When Best를 삭제한다
- Then 409 "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"이고 Best는 남는다

### CD-042 Deal은 안 쓰고 Action 스냅숏만 쓰는 코드는 409이고 문구에 Action 수가 들어간다
- Given Deal이 제품소개·Best일 때 Action을 남기고 Deal을 POC준비·Commit으로 옮긴다
- When 제품소개와 Best를 각각 삭제한다
- Then 409 `invalid-state` "사용 중인 코드는 삭제할 수 없습니다. (Action 1건)"이고 코드는 남는다

### CD-043 Deal과 Action이 함께 쓰는 코드는 Deal 수 문구가 먼저다
- Given 제품소개 Deal 1건과 그 상태의 Action 1건
- When 제품소개를 삭제한다
- Then 409 "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"이다

### CD-044 코드를 쓰던 마지막 Deal·Action이 없어지면 코드를 지울 수 있다
- Given (a) Best를 쓰는 Deal 1건이 삭제되었다 (b) 제품소개를 스냅숏으로 가진 유일한 Action이 삭제되었다(Deal은 다른 Status)
- When Best, 제품소개를 각각 삭제한다
- Then 204이고 목록에서 사라진다

### CD-045 없는 코드를 지우면 404다
- When 없는 id로 삭제한다
- Then 404 `not-found` "코드을(를) 찾을 수 없습니다: <id>"다

### CD-046 sales·user의 관리 요청은 403 관리자 문구이고 아무것도 바뀌지 않는다
- Given KIM 또는 VIEWER로 로그인
- When `GET /codes/usage?kind=status`, `POST /codes`, `PATCH /codes/{제품소개 id}`, `PUT /codes/order`(거꾸로 된 전체 목록), `DELETE /codes/{POC완료 id}`
- Then 모두 403 `forbidden` "관리자 권한이 필요합니다"이고 유스케이스를 부르지 않는다(코드 수·이름·순서 그대로). 미인증은 401(PL-R5)

### CD-047 화면: Deal 관리는 탭 6개를 순서대로 보이고 Status 코드 탭에서 시작한다
- Given admin으로 `/admin/deal`을 연다
- Then 탭 목록 "Deal 관리 항목"은 Status 코드, Forecast 코드, BANT Label, Action 유형, Vendor, 경고 기준 순서이고 Status 코드가 선택되어 있다

### CD-048 화면: 주소의 tab 값으로 탭을 열고 모르는 값이면 Status 코드 탭이다
- When `/admin/deal?tab=forecast`, `/admin/deal?tab=unknown`을 연다. 이어서 Forecast 탭에서 Status 코드 탭을 고른다
- Then 각각 Forecast 코드 탭(Forecast 표), Status 코드 탭이 선택된다. Status 코드 탭을 고르면 주소에 `tab`이 없다

### CD-049 화면: Won·계약완료 동기화 안내를 보인다
- When Status 코드 탭을 연다
- Then "Won과 계약완료는 이름을 바꿔도 같은 의미로 동기화됩니다"로 시작하는 안내가 보인다

### CD-050 화면: Status 표는 7개를 순서대로 순서·이름·내부 코드·사용 건수와 함께 보인다
- When Status 코드 탭을 연다
- Then 이름 칸이 기회발굴 … 계약완료 순서이고 머리글 순서·이름·내부 코드·사용 중 Deal이 있으며, 가격협상 행에 `price_negotiation`과 사용 4가 보인다

### CD-051 화면: 잠금 행은 "시스템 연결" 배지와 이유가 붙은 비활성 삭제 버튼을 가진다
- When Status 코드 탭을 연다
- Then 계약완료·기회발굴 행에 "시스템 연결"이 있고 계약완료의 "삭제"는 비활성이며 접근 설명이 잠금 문구(CD-R22)다. 제품소개 행에는 배지가 없다

### CD-052 화면: Forecast 표는 6개를 확률 참고·구분(Open/Won/Lost)과 함께 보인다
- When Forecast 코드 탭을 연다
- Then 이름이 Pipeline, Best, Most Likely, Commit, Won, Lost 순서이고 머리글 "확률 참고"·"구분"이 있으며 Pipeline 행에 `0–50`과 "Open", Lost 행에 "Lost" 배지가 보인다

### CD-053 화면: 이름을 표 안에서 바꾸면(저장·Enter) 새 이름이 보이고 잠금 코드도 key가 그대로다
- When 가격협상의 "이름 수정" → "가격 협의" → "저장", 계약완료의 "이름 수정" → "계약성사" → Enter
- Then "가격 협의"·"계약성사" 행이 보이고 "가격협상" 행과 입력 칸은 사라지며 계약성사 행의 내부 코드는 `contract_completed`다

### CD-054 화면: Esc로 이름 수정을 그만두면 요청 없이 원래 이름이 남는다
- When 가격협상의 "이름 수정" → 글자 추가 → Esc
- Then 입력 칸이 사라지고 "가격협상" 행이 그대로다

### CD-055 화면: 중복 이름이면 서버 문구를 보이고 입력을 유지한다
- When 가격협상을 "제품소개"로 바꿔 저장한다
- Then 오류 알림 "같은 이름의 코드가 이미 있습니다."가 보이고 입력 칸 값은 "제품소개"다

### CD-056 화면: 빈 이름으로 저장하면 서버 문구를 보인다
- When 가격협상 입력을 비우고 저장한다
- Then 오류 알림 "이름을 입력하세요."다

### CD-057 화면: ↑/↓로 코드를 이웃과 자리 바꾼다
- When "가격협상 위로 이동", 이어서 "가격협상 아래로 이동"
- Then 순서가 … POC완료, 가격협상, 기술평가, 계약완료가 되었다가 원래대로 돌아온다

### CD-058 화면: 첫 행의 ↑와 마지막 행의 ↓는 비활성이다
- When Status 코드 탭을 연다
- Then "기회발굴 위로 이동"과 "계약완료 아래로 이동"이 비활성이다

### CD-059 화면: 코드를 추가하면 맨 끝에 사용 0으로 보이고 입력이 비워진다
- When "새 코드 이름"에 "내부검토" → "추가"
- Then 마지막 행이 "내부검토"이고 사용 0이며 입력 칸이 비어 있다

### CD-060 화면: 빈 이름으로 추가하면 서버 문구를 보인다
- When 입력 없이 "추가"
- Then 오류 알림 "이름을 입력하세요."다

### CD-061 화면: 쓰이지 않는 코드를 확인 뒤 삭제하면 표에서 사라진다
- Given "내부검토"를 추가했다
- When 그 행의 "삭제" → 대화상자 "코드 삭제"의 "삭제"
- Then "내부검토" 행이 사라진다

### CD-062 화면: 삭제 확인을 취소하면 코드가 남는다
- Given "내부검토"를 추가했다
- When "삭제" → 대화상자의 "취소"
- Then "내부검토" 행이 남는다

### CD-063 화면: Deal이 쓰는 Status·Forecast 삭제는 거절 문구를 보이고 대화상자를 닫으며 행이 남는다
- When 가격협상(Status), Commit(Forecast)을 각각 삭제 확인한다
- Then 오류 알림 "사용 중인 코드는 삭제할 수 없습니다. (Deal 4건)"(Commit은 "(Deal <N>건)")이 보이고 대화상자가 닫히며 행이 남는다

### CD-064 화면: Forecast 추가·순서 변경은 Status와 따로 동작한다
- When Forecast 탭에서 "Upside"를 추가하고 "Upside 위로 이동"
- Then Upside가 Forecast 표 끝에서 두 번째다

### CD-065 화면: Won은 삭제할 수 없지만 이름은 바꿀 수 있다
- When Forecast 탭의 Won 행을 본 뒤 이름을 "수주"로 바꾼다
- Then Won 행의 "삭제"는 비활성이고 "시스템 연결"이 있으며, 바꾼 뒤 "수주" 행이 보인다

### CD-066 화면: 새 작업을 시작하면 이전 오류 배너가 사라진다
- Given 빈 이름으로 추가해 오류 알림 "이름을 입력하세요."가 보인다
- When 다른 행의 "이름 수정"을 누르거나 "↓"로 이동한다
- Then 오류 알림이 사라진다(이동이 성공하면 다시 생기지 않는다)

### CD-067 화면: 이름·순서를 바꾸면 Deal·Forecast 조회를 다시 읽게 한다
- Given 코드 화면과 Deal·Forecast 조회 캐시가 있다
- When 이름 변경 또는 순서 변경이 성공한다(추가·삭제도 따로 해 본다)
- Then 이름·순서 변경 뒤에는 코드 목록·사용 현황·Deal·Forecast 조회가 무효화되고, 추가·삭제 뒤에는 코드 조회만 무효화된다

### CD-068 게이트웨이: 코드 목록·사용 현황을 읽어 화면 값으로 바꾼다
- When `all()`, `list('status')`를 부른다
- Then `GET /api/v1/codes`, `GET /api/v1/codes/usage?kind=status`를 보내고 `probability_hint`·`usage_count`를 `probabilityHint`·`usageCount`로 바꾼 값을 돌려준다. 결과 `open`·`won`·`lost`를 받아들이고, 서버 403은 상태 403 `forbidden` 오류다

### CD-069 게이트웨이: 추가·이름 변경·순서 변경·삭제를 계약대로 보내고 거절을 서버 문구의 오류로 바꾼다
- When `create`(힌트 있음·없음), `rename`, `reorder`, `remove`를 부르고 서버가 409·422로 거절하게 한다
- Then `POST /codes` `{kind, name, probability_hint}`(없으면 null), `PATCH /codes/{id}` `{name}`, `PUT /codes/order` `{kind, ordered_ids}`, `DELETE /codes/{id}`(204면 성공)를 보낸다. 중복·잠금·사용 중 409는 `conflict`, 빈 이름·순서 목록 422는 `validation`이고 문구는 서버 detail 그대로다

### CD-070 게이트웨이: 모르는 결과(outcome)는 해석 불가 오류로 거절한다
- When 서버가 Forecast `outcome` "weird"를 돌려준다
- Then "서버 응답을 해석할 수 없습니다." 오류다

### CD-071 Fake 게이트웨이는 서버와 같은 규칙·문구로 코드 요청에 답한다
- When 계약 스위트로 Fake 게이트웨이에 추가·중복·빈 이름·이름 변경·순서 변경·잠금 삭제·역할별 요청을 보낸다
- Then 맨 끝 추가(key 형식, `open`), "이름을 입력하세요." 422, "같은 이름의 코드가 이미 있습니다." 409(추가·이름 변경), 이름 변경 뒤 key 그대로, 1부터 다시 매김, "순서 목록이 올바르지 않습니다." 422, 잠금 삭제 409, 모든 역할 조회 가능, sales·user 관리 요청 403이다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 최초 작성(초안): 구현된 Status·Forecast 코드 관리 동작을 정본 명세로 옮김. 규칙 CD-R1~R24, use case CD-UC1~UC6, BDD 케이스 CD-001~CD-071 | CD-001~CD-071(신규) |
