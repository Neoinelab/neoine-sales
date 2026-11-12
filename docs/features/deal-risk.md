# 경고·파생 값·경고 기준   (feature 코드: RK, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드입니다.
> - backend: `domain/deal/{risk.py,status_entry.py,entities.py}`, `domain/alert/{thresholds.py,settings.py}`, `application/alert/*`, `application/deal/{views.py,list_deals.py,update_deal.py,history_writer.py}`, `infra/db/{deal_derived.py,deal_risk.py,deal_search.py,alert_settings_repository.py,models_alert.py}`, `web/routers/alert_settings.py`, `web/schemas/{alert_settings.py,deal_response.py}`
> - frontend: `shared/ui/RiskBadge.tsx`, `shared/model/risk.ts`, `features/deals/list/{DealsPage.tsx,DealRowItem.tsx}`, `features/deals/detail/{SummaryBar.tsx,ActionTable.tsx}`, `features/admin/deal-management/AlertSettingsForm.tsx`, `data/alerts.ts`, `gateway/http/alerts.ts`, `test/fake/gateway/{alerts.ts,views.ts}`
>
> 이전 계획(P3, 2026-10-17)과 Next Action 상태 분리(2026-10-20)의 결정을 따른다. 계획과 코드가 다른 곳은 코드를 따랐다.

## 1. 개요

- 목적: 영업이 손봐야 할 Deal을 눈에 띄게 한다.
  - 기한초과: Next Action의 Due Date가 지났다.
  - 미업데이트: 오래 Action이 없다.
  - Status 체류 일수: 지금 Status에 며칠째 머무는지.
  - 이 값들의 기준인 Next Action 기준 행과 최종 업데이트 시각.
  - admin이 미업데이트 기준 일수를 정한다.
- 사용자(역할): 경고·파생 값과 경고 기준 조회는 로그인한 모든 역할(`admin`·`sales`·`user`). 경고 기준 변경은 `admin`만.
- 범위
  - Deal 응답의 파생 필드 `next_action`·`last_updated_at`·`risk`·`status_changed_at`·`status_days`의 계산 규칙
  - 경고 판정식(기한초과·미업데이트·종결 제외)과 Deal 목록 `overdue`·`stale` 필터가 같은 판정으로 고른다는 규칙
  - `deals.status_changed_at` 기록 규칙(어느 저장이 진입 시각을 옮기는가)
  - `GET·PUT /api/v1/alert-settings`와 Admin > Deal 관리 > "경고 기준" 탭
  - 화면의 경고 배지·행 색·목록 범례, 상세 요약 바의 체류 일수·경고 배지, Action 표의 기한초과 배지
- 범위 밖
  - 목록 필터 UI(체크박스·URL)와 필터의 다른 조건 결합·쿼리 형식 오류 → DL
  - 목록 정렬(기본 정렬이 `last_updated_at`이라는 사실은 DL이 이 문서의 RK-R2를 가리킨다), 최종 업데이트 기간 필터 → DL
  - Next Action 상태 변경 API·Action 검색 → NA. Action 등록·수정·삭제 자체 → AC(`acted_at`은 등록 때 서버가 정한다)
  - Status·Forecast 동기화 규칙과 변경 적용 → DD. Deal 등록·수정 검증 → DE
  - Dashboard 주의 필요 타일 → DSH, Reports의 `deal.risk`·`deal.status_days`·`deal.status_changed_at` 필드 → RQ. 둘 다 이 문서의 판정(RK-R3~R7·R10)을 쓴다
  - 업무 날짜·업무일 시작·응답 시각 표기 → TM(TM-R4·R5·R8), 상대 시각 표시 → TM-R15
  - Deal 관리 화면의 탭 틀·탭 순서 → CD-R17
  - 사용자 삭제 시 퇴사 처리 판정 → US-R17(US-058)
  - 공통 401·CSRF·Problem 형식 → PL
- 관련 화면·메뉴: Deals 목록(`/deals`) 범례·행, Deal 상세(`/deals/:code`) 요약 바·Actions 탭 표, Admin > Deal 관리(`/admin/deal?tab=alert`).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| Next Action 기준 행 | 한 Deal의 Action 가운데 Next Action이 있는 행 중 가장 최근 행. Deal의 `next_action` 표시, 기한초과 판정, Next Action 상태 필터(DL·NA)가 이 행을 쓴다 |
| 진행사항만 Action | Next Action이 없는(`next_action` null) Action. 기준 행이 될 수 없다 |
| 최종 업데이트(`last_updated_at`) | 그 Deal의 모든 Action 수행 시각(`acted_at`) 중 가장 늦은 시각. Action이 없으면 Deal 등록 시각 |
| 경고(Risk) | `overdue`(기한초과)·`stale`(미업데이트)·`overdue_stale`(둘 다)·없음(null) |
| 종결 Forecast | Forecast key가 `won` 또는 `lost`. 이름이 아니라 key로 판정한다 |
| 오늘 | 요청 시각의 업무 날짜(TM-R4) |
| 경고 기준(`stale_days`) | 미업데이트 기준 일수. 1~365 정수, 저장 전 기본 14 |
| Status 진입 시각(`status_changed_at`) | Deal이 현재 Status에 들어온 시각 |
| 체류 일수(`status_days`) | 오늘 − 진입 시각의 업무 날짜(일), 음수면 0 |

### 2.2 데이터 모델

- `alert_settings`(단일 행, 시드 없음): `id SMALLINT PK`(CHECK `id = 1`, 이름 `single_row`), `stale_days SMALLINT`(CHECK `BETWEEN 1 AND 365`, 이름 `stale_days_range`), `updated_at TIMESTAMPTZ`, `updated_by_user_id BIGINT` FK `users.id` ON DELETE RESTRICT, 인덱스 `ix_alert_settings_updated_by_user_id`. 행이 없으면 기본값 14다. 저장은 `id = 1` upsert다.
- `deals.status_changed_at TIMESTAMPTZ NOT NULL`. 도메인은 `StatusEntry(status_key, changed_at)`로 들고 `Deal.status_changed_at`으로 노출한다.
- 저장하지 않는 파생 값: `next_action`, `last_updated_at`, `risk`, `status_days`. 조회할 때마다 계산한다(SQL `infra/db/deal_derived.py`의 `LATEST_ACTED`·`LATEST_NEXT`, 도메인 `compute_risk`·`status_days`).
- 도메인 객체
  - `AlertThresholds(stale_days)`: 1~365 정수만(bool 거절), `default()` = 14.
  - `StoredAlertSettings(thresholds, updated_at, updated_by)`.
  - `Risk` StrEnum `overdue`·`stale`·`overdue_stale`.
  - `RiskBasis(today, stale_days)`: 목록 필터·Dashboard·Reports용. `stale_days < 1`이면 `ValueError`(프로그래밍 오류).
- 마이그레이션: 없음(기준선 `00c3126aa926`에 포함, SC).

### 2.3 비즈니스 규칙

Next Action 기준 행과 최종 업데이트
- **RK-R1** Next Action 기준 행은 그 Deal의 Action 중 `next_action`이 있는 행을 `acted_at` 내림차순, 같으면 `id` 내림차순으로 놓았을 때 첫 행이다.
  - 진행사항만 Action은 더 최근이어도 기준 행을 바꾸지 않는다.
  - 기준 행의 Next Action 상태(`open`·`done`·`not_done`)는 기준 행 선택에 영향이 없다.
  - Deal 응답 `next_action`은 기준 행의 `{text, due_date, status}`이고, 기준 행이 없으면 `null`이다.
- **RK-R2** `last_updated_at`은 그 Deal의 모든 Action(진행사항만 Action 포함) `acted_at`의 최댓값이고, Action이 없으면 Deal `created_at`이다.
  - Deal 수정은 값을 바꾸지 않는다: 폼 저장·변경 적용·인라인 수정·연락처 변경 반영·첨부 업로드/삭제 모두 해당하며, 이것들은 `updated_at`만 바꾼다.
  - `acted_at`은 Action 등록 때만 정해지므로 Action 수정과 Next Action 상태 변경도 값을 바꾸지 않는다.
  - Action을 지우면 남은 Action 기준으로 다시 계산한다. 하나도 없으면 등록 시각이다.
  - 같은 Deal의 목록 행과 상세는 같은 `next_action`·`last_updated_at`을 준다.

경고 판정
- **RK-R3** Forecast key가 `won`·`lost`인 Deal은 `risk`가 항상 `null`이다. 기한·갱신과 무관하고 경고 기준과도 무관하다. 다른 Forecast key(`pipeline`·`upside`·`best`·`commit` 등 직접 만든 key 포함)는 판정한다.
- **RK-R4** 기한초과(`overdue`)는 기준 행의 `due_date`가 오늘보다 앞일 때다.
  - Due Date가 오늘이거나 미래면 아니다.
  - 기준 행이 없으면 아니다.
  - 기준 행의 Next Action을 종료(`done`·`not_done`)해도 Due가 지났으면 기한초과가 유지된다.
- **RK-R5** 미업데이트(`stale`)는 `(오늘 − last_updated_at의 업무 날짜).days ≥ stale_days`일 때다.
  - 날짜 단위로 세고 시각은 보지 않는다.
  - 예(기준 14): 마지막 갱신 후 13일째는 아니고 14일째부터 미업데이트다.
  - 예(기준 1): 어제 갱신이면 미업데이트, 오늘 갱신이면 아니다.
  - Next Action 상태는 미업데이트에 영향이 없다.
- **RK-R6** 응답 `risk`: 기한초과이면서 미업데이트면 `"overdue_stale"`, 기한초과만이면 `"overdue"`, 미업데이트만이면 `"stale"`, 둘 다 아니면 `null`이다.
- **RK-R7** 계산 시점과 기준
  - 서버가 요청마다 그 요청의 서버 시각으로 계산한다(저장하지 않음). Deal 응답을 돌려주는 모든 경로가 같은 규칙이다: 목록 행, 상세, 등록·수정 응답, 변경 적용 응답의 `deal`.
  - 경고 기준은 요청당 한 번 읽어 그 요청의 모든 행과 필터에 쓴다. 저장된 값이 없으면 14다.
  - 경고 기준을 바꾸면 다음 요청부터 바로 반영된다(기존 Deal도 다시 판정).
  - 화면은 서버 `risk`를 그대로 쓰고 브라우저에서 다시 계산하지 않는다.
- **RK-R8** 목록 경고 필터: `GET /deals`의 `overdue=true`·`stale=true`는 RK-R3~R5와 같은 판정으로 Deal을 고른다(같은 요청의 오늘과 경고 기준). 응답 `risk`와 어긋나지 않는다.
  - `overdue`만 켜면 `risk ∈ {overdue, overdue_stale}`인 Deal, `stale`만 켜면 `risk ∈ {stale, overdue_stale}`인 Deal이다.
  - 둘 다 켜면 어느 하나라도 해당하는 Deal이다(OR).
  - 종결 Deal은 어느 필터에도 걸리지 않는다. `total`은 필터 결과 건수다.
  - SQL의 미업데이트 조건은 `last_updated_at < start_of_business_day(오늘 − (stale_days − 1))`이며 RK-R5와 같다(TM-R5).
  - 다른 조건과의 AND, 쿼리 값 형식(422)은 DL이 맡는다.

Status 진입 시각과 체류 일수
- **RK-R9** `status_changed_at`의 기록
  - 등록 때는 등록 시각이다.
  - 그 뒤 Deal을 저장할 때 Status key가 저장된 진입 기록의 key와 다르면 진입 시각이 그 요청의 서버 시각으로 바뀌고, 같으면 그대로다. 해당 경로:
    - 폼 수정(`PATCH /deals/{code}`). 종결 값으로 Status가 바뀌는 경우 포함.
    - 변경 적용(`POST /deals/{code}/changes`). Forecast Won 선택으로 Status가 계약완료로 함께 바뀌는 경우와 Won 이탈 때 고른 Status 포함(동기화 규칙 DD).
    - Action 등록의 `status_change`(AC).
  - 진입 시각을 바꾸지 않는 것: Forecast만 변경, 다른 필드만 변경, 같은 Status를 다시 보냄, Status 변경 없는 Action 등록, 연락처 변경 반영에 따른 수정 시각 갱신.
- **RK-R10** `status_days = max(0, (오늘 − status_changed_at의 업무 날짜).days)`다. 진입 당일은 0이다. 종결 Deal도 계산한다(경고와 달리 제외하지 않음).

경고 기준
- **RK-R11** 경고 기준은 시스템 전체 값 하나(`stale_days`)다. 1~365 정수이며 저장한 적이 없으면 14다.
- **RK-R12** `GET /alert-settings`는 로그인한 모든 역할에게 200 `{stale_days, updated_at, updated_by}`(키는 정확히 이 셋)를 준다.
  - 저장 전이면 `{14, null, null}`이다.
  - `updated_by`는 `UserRef`이고, 저장자가 퇴사했으면 퇴사 표시(`resigned: true`)다.
- **RK-R13** `PUT /alert-settings`는 admin만 쓸 수 있다. 본문은 `{"stale_days": <정수>}`이고 그 밖의 필드는 거절한다.
  - 판정 순서(PL-R4): ① 401 → ② CSRF 403 → ③ admin 아님 403 `forbidden`(본문이 틀려도 403) → ④ 형식 422 `request-validation` → ⑤ 범위 422 `invalid-value`.
    - ④ 형식: 누락, 문자열 `"7"`, 소수 `7.5`, bool `true`, `null`, 알 수 없는 필드.
    - ⑤ 범위: 0·366·음수 등 1~365 밖 정수. 문구 "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."
  - 성공하면 200이고 GET과 같은 모양이다. `updated_at`은 서버 시각, `updated_by`는 요청한 admin이다.
  - 마지막 저장이 이긴다(값·저장자·시각을 모두 바꿈). 같은 값을 다시 저장해도 저장자·시각이 바뀐다.
  - 실패하면 저장된 값은 그대로다.
- **RK-R14** `updated_by_user_id`는 users FK RESTRICT다. 그래서 경고 기준을 저장한 사용자는 삭제 대신 퇴사 처리된다(판정은 US-R17).

화면(frontend)
- **RK-R15** 경고 배지(`RiskBadge`)
  - `null`이면 아무것도 그리지 않는다. `overdue`는 "기한초과"(`badge risk-overdue`), `stale`은 "미업데이트"(`badge risk-stale`), `overdue_stale`은 두 배지를 모두 보인다. 색만으로 구분하지 않는다.
  - 목록 행 클래스(`riskRowClass`): `overdue`·`overdue_stale`은 `risk-overdue`(기한초과 우선), `stale`은 `risk-stale`, 그 밖은 없음이다.
- **RK-R16** Deals 목록
  - 필터 바 아래에 범례(`aria-label="Risk 범례"`) 두 줄을 둔다:
    - "기한초과" 배지 + "Next Action의 Due Date가 지났습니다"
    - "미업데이트" 배지 + "{N}일 이상 미업데이트"(N = 저장된 경고 기준). 기준을 읽는 중이거나 읽지 못하면 "기준일 이상 미업데이트".
  - 각 행은 이름 옆에 경고 배지를 두고 행 클래스를 붙인다.
  - 기한초과(`overdue`·`overdue_stale`)면 Due 칸에 `overdue` 클래스를 붙인다. Next Action 칸에는 붙이지 않는다.
  - 최종 업데이트 칸은 상대 시각(TM-R15)이고 `title`은 `formatStamp`다.
  - 목록에는 체류 일수 열·문구가 없다.
- **RK-R17** Deal 상세 요약 바
  - Status 옆에 "{status_days}일째"를 보이고 `title`은 `formatDateTime(status_changed_at)`(오프셋 벽시계, TM-R14)이다.
  - Next Action 줄은 기준 행의 텍스트·"Due {날짜}"·상태 라벨을 보인다. 없으면 "없음"이다. 줄 끝에 경고 배지를 둔다(Action이 없어도 미업데이트면 보임).
  - 최종 업데이트는 상대 시각이고 `title`은 서버 문자열 원문이다.
- **RK-R18** Actions 탭 표의 기한초과 배지
  - 서버 `risk`가 `overdue`·`overdue_stale`이고, 그 행의 Next Action 텍스트와 Due Date가 Deal `next_action`의 `text`·`due_date`와 같을 때만 그 행 Due 칸에 "기한초과" 배지를 단다.
  - 브라우저 시계로 판정하지 않는다. `risk`가 `null`이나 `stale`이면 Due가 지나 보여도 배지가 없다.
- **RK-R19** 경고 기준 탭(Deal 관리 `/admin/deal?tab=alert`, admin 화면, 탭 틀은 CD-R17)
  - 화면 구성: 영역 `aria-label="경고 기준"`, 폼 `aria-label="경고 기준 변경"`, 라벨 "미업데이트 기준(일)"의 숫자 칸(`min=1`·`max=365`·`step=1`, 처음 값은 저장된 값).
  - 안내 문구: "마지막 업데이트 후 이 일수 이상 지나면 Deal에 '미업데이트' 표시가 붙습니다. (1~365일)".
  - 입력이 1~365 정수가 아니면(빈 값·범위 밖·소수) `aria-invalid`를 켜고 "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."를 보이며 "저장"을 비활성으로 한다.
  - 저장된 값과 같거나 저장 중이어도 "저장"은 비활성이다.
  - 저장 기록이 있으면 "마지막 저장 {사용자 표시} · {formatDateTime(updated_at)}"를 보인다.
  - 읽는 중이면 "불러오는 중…"이다. 읽기·저장 오류는 오류 배너에 서버 `detail`을 보인다. 입력을 바꾸면 저장 오류를 지운다.
  - sales·user에게는 탭과 폼이 없다(Admin 화면 접근은 PL).
- **RK-R20** 경고 기준 저장에 성공하면 경고 기준·Deal 목록/상세·Dashboard 캐시를 무효화한다. 그래서 목록 범례 숫자와 행 경고가 새 기준으로 바뀐다. 실패하면 Deal 캐시는 그대로다.
- **RK-R21** 게이트웨이
  - HTTP `alerts.get`/`save`는 `GET`/`PUT /api/v1/alert-settings`를 부르고 `{staleDays, updatedAt, updatedBy}`로 바꾼다.
  - 422 문장은 메시지 그대로 넘기고, 403·401은 그 상태의 `ApiError`다.
  - HTTP Deal 매퍼는 서버 `risk`·`statusChangedAt`·`statusDays`를 그대로 옮기고 다시 계산하지 않는다.
  - Fake 게이트웨이는 `shared/model/risk.ts`의 `computeRisk`·`statusDays`로 서버와 같은 규칙을 흉내 낸다.

### 2.4 상태와 전이

경고는 저장된 상태가 아니라 조회 시점의 계산 결과다(RK-R7).

| 조건(종결 아님) | 기한초과 아님 | 기한초과 |
| --- | --- | --- |
| 미업데이트 아님 | `null` | `overdue` |
| 미업데이트 | `stale` | `overdue_stale` |

종결(`won`·`lost`)은 항상 `null`이다. Status 진입 시각은 Status key가 바뀌는 저장에서만 앞으로 간다(RK-R9).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /alert-settings` | 401 | 가능 | 가능 | 가능 |
| `PUT /alert-settings` | 401 | 403 | 403 | 가능 |
| Deal 파생 값·경고 조회(목록·상세) | 401 | 가능 | 가능 | 가능 |
| 경고 기준 탭 화면 | 로그인 화면 | 없음 | 없음 | 가능 |

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/alert-settings` | — | 200 `AlertSettingsResponse` | 401 `unauthenticated` |
| PUT `/alert-settings` | `AlertSettingsRequest` `{"stale_days": 7}` | 200 `AlertSettingsResponse` | 401, 403 `csrf`, 403 `forbidden`(admin 전용 문구, PL), 422 `request-validation`, 422 `invalid-value` |

- `AlertSettingsResponse`: `{"stale_days": 7, "updated_at": "2026-10-17T10:00:00+09:00" | null, "updated_by": UserRef | null}`.
- `AlertSettingsRequest`: `stale_days: StrictInt`(필수), 알 수 없는 필드 거절(`RequestModel`).
- 라우터: `APIRouter(prefix="/api/v1/alert-settings", tags=["settings"])`, PUT에 `require_admin`. 유스케이스: `GetAlertSettings(uow_factory)`, `UpdateAlertSettings(uow_factory, clock)`. Port: `AlertSettingsRepository.get() -> StoredAlertSettings | None`, `save(thresholds, *, updated_by, now) -> StoredAlertSettings`.
- Deal 응답(`DealRowResponse`·`DealDetailResponse`, 경로는 DE·DD·DL 소유)의 이 feature 필드(모두 required):
  - `next_action: {text: string, due_date: date, status: "open"|"done"|"not_done"} | null`
  - `last_updated_at: date-time`
  - `risk: "overdue"|"stale"|"overdue_stale"|null`
  - `status_changed_at: date-time`
  - `status_days: integer`
  - 시각 표기는 TM-R8을 따른다.
- 새 오류 type 없음.

### 2.7 화면 동작

RK-R15~R21.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구 |
| --- | --- | --- |
| 경고 기준 범위 밖 정수 | 422 `invalid-value` | 미업데이트 기준은 1~365일 사이의 정수로 입력하세요. |
| 경고 기준 형식 오류(누락·문자열·소수·bool·null·알 수 없는 필드) | 422 `request-validation` | 공통 문구(PL-R12) |
| sales·user의 경고 기준 변경 | 403 `forbidden` | admin 전용 공통 문구(PL-R7, `ADMIN_DENIED`) |
| 화면: 입력이 1~365 정수가 아님 | 칸 아래 오류 | 미업데이트 기준은 1~365일 사이의 정수로 입력하세요. |
| 프로그래밍 오류: `RiskBasis(stale_days < 1)` | `ValueError` | stale_days는 1 이상이어야 합니다. |
| 프로그래밍 오류: 시간대 없는 시각 | `InvalidValueError` | TM-R1 |

## 3. Business use case

### RK-UC1 Deal의 파생 값 보기
- 행위자: 로그인한 사용자
- 사전 조건: Deal이 있다
- 기본 흐름: 목록·상세·쓰기 응답을 받으면 서버가 요청 시각의 오늘과 저장된 경고 기준으로 기준 행·최종 업데이트·경고·체류 일수를 계산해 준다(RK-R1~R7, R10)
- 결과: 같은 Deal은 목록·상세에서 같은 값

### RK-UC2 경고 Deal만 골라 보기
- 행위자: 로그인한 사용자
- 기본 흐름: 목록을 `overdue`·`stale`로 조회하면 응답 `risk`와 같은 판정으로 고른다(RK-R8)
- 결과: 필터 결과와 행의 경고가 일치하고 `total`이 맞다

### RK-UC3 Status 진입 시각 기록
- 행위자: sales·admin(저장하는 사람), 시스템
- 기본 흐름: 등록·폼 수정·변경 적용·Action 등록에서 Status key가 바뀌면 그 요청 시각을 진입 시각으로 남긴다(RK-R9)
- 대안: Status가 그대로면 진입 시각 유지
- 결과: 체류 일수가 새 Status 기준으로 0부터 다시 센다

### RK-UC4 경고 기준 조회·변경
- 행위자: 조회는 모든 역할, 변경은 admin
- 기본 흐름: admin이 경고 기준 탭에서 1~365 정수를 저장하면 값·저장자·시각이 남고 Deal 경고가 즉시 새 기준을 따른다(RK-R11~R13, R19, R20)
- 예외: sales·user 403, 범위 밖 422 `invalid-value`, 형식 오류 422 `request-validation`, 미인증 401
- 결과: 마지막 저장이 이긴다

### RK-UC5 화면에서 경고 알아보기
- 행위자: 로그인한 사용자
- 기본 흐름: 목록 범례·배지·행 색·Due 강조, 상세 요약 바의 "N일째"·경고 배지, Actions 표의 기한초과 배지로 서버 값을 보인다(RK-R15~R18)
- 결과: 색과 텍스트로 함께 구분, 브라우저 시계와 무관

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| RK-001 | Next Action 기준 행은 Next Action이 있는 가장 최근 Action이고 더 최근의 진행사항만 Action은 대신하지 않는다 | RK-R1, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_a_later_progress_only_action_does_not_replace_the_next_action`<br>`application/test_list_deals_derived.py::test_the_latest_action_provides_the_next_action_and_the_update_time`<br>`gateway/contract/actionsStatus.contract.ts` |
| RK-002 | 수행 시각이 같으면 id가 큰 Action이 기준 행이다 | RK-R1, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_equal_acted_at_makes_the_larger_id_the_next_action_basis` |
| RK-003 | Next Action이 한 번도 없으면 next_action은 null이다 | RK-R1, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_deal_with_only_progress_only_actions_is_never_overdue`<br>`application/test_list_deals_derived.py::test_a_deal_without_actions_has_no_next_action_and_its_registration_time` |
| RK-004 | 최종 업데이트는 등록 순서와 무관하게 가장 늦은 Action 수행 시각이다(진행사항만 포함) | RK-R2, RK-UC1 | backend | `application/test_list_deals_derived.py::test_the_latest_action_provides_the_next_action_and_the_update_time`<br>`application/test_list_deals_derived.py::test_the_action_with_the_latest_acted_at_wins_regardless_of_registration_order`<br>`application/test_list_deals_derived.py::test_an_action_older_than_the_deal_update_still_sets_the_update_time`<br>`gateway/contract/actionsStatus.contract.ts` |
| RK-005 | Action이 없으면 최종 업데이트는 등록 시각이고 Deal 수정은 반영하지 않는다 | RK-R2, RK-UC1 | backend | `application/test_list_deals_derived.py::test_a_deal_without_actions_has_no_next_action_and_its_registration_time`<br>`application/test_list_deals_derived.py::test_a_deal_edit_does_not_move_the_update_time` |
| RK-006 | 유일한 Action을 지우면 최종 업데이트가 등록 시각으로 돌아간다 | RK-R2, RK-UC1 | backend | `application/test_deal_last_updated_actions.py::test_deleting_the_only_action_returns_last_updated_to_the_registration_time` |
| RK-007 | Action 수정과 Next Action 상태 변경은 최종 업데이트를 바꾸지 않는다 | RK-R2, RK-UC1 | backend | `application/test_deal_last_updated_actions.py::test_editing_an_action_keeps_last_updated`<br>`application/test_deal_last_updated_actions.py::test_changing_the_next_action_status_keeps_last_updated` |
| RK-008 | 같은 Deal의 목록 행과 상세는 같은 파생 값을 준다 | RK-R2, RK-R7, RK-UC1 | backend | `application/test_deal_views_risk.py::test_list_and_detail_agree_on_the_same_deal`<br>`application/test_list_deals_derived.py::test_the_detail_carries_the_same_derived_values` |
| RK-009 | 기준 행의 Due Date가 오늘보다 앞이면 기한초과다 | RK-R4, RK-R6, RK-UC1 | backend | `application/test_deal_views_risk.py::test_action_due_before_today_makes_the_deal_overdue`<br>`domain/test_deal_risk.py::test_due_yesterday_is_overdue` |
| RK-010 | Due Date가 오늘이거나 내일이면 기한초과가 아니다 | RK-R4, RK-UC1 | backend | `application/test_deal_views_risk.py::test_action_due_today_is_not_overdue`<br>`domain/test_deal_risk.py::test_due_today_is_not_overdue`<br>`domain/test_deal_risk.py::test_due_tomorrow_is_not_overdue` |
| RK-011 | 기준 행이 없으면 기한초과가 아니다 | RK-R4, RK-UC1 | backend | `application/test_deal_views_risk.py::test_deal_without_actions_is_never_overdue`<br>`domain/test_deal_risk.py::test_no_action_is_not_overdue` |
| RK-012 | 더 최근에 진행사항만 Action이 있어도 기준 행의 Due로 기한초과를 판정한다 | RK-R4, RK-R1, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_overdue_uses_the_latest_row_that_has_a_next_action` |
| RK-013 | 기한 지난 Next Action을 종료해도 기한초과가 유지된다 | RK-R4, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_closed_next_action_keeps_overdue` |
| RK-014 | 기준 14일에서 13일째는 정상이고 14일째부터 미업데이트다 | RK-R5, RK-UC1 | backend | `domain/test_deal_risk.py::test_stale_from_exactly_stale_days`<br>`domain/test_deal_risk.py::test_not_stale_one_day_before`<br>`domain/test_deal_risk.py::test_stale_far_beyond_the_boundary` |
| RK-015 | 기준 1일이면 어제 갱신은 미업데이트, 오늘 갱신은 정상이다 | RK-R5, RK-UC1 | backend | `domain/test_deal_risk.py::test_stale_days_of_one_makes_yesterday_stale_and_today_fresh` |
| RK-016 | 오늘과 갱신 날짜는 서버 시간대의 업무 날짜로 센다 | RK-R5, RK-R10, RK-UC1 | backend | `application/test_deal_views_risk.py::test_today_and_entry_dates_use_the_local_calendar`<br>`domain/test_deal_risk.py::test_today_uses_local_calendar_date`<br>`domain/test_deal_status_days.py::test_naive_entry_is_rejected`<br>`domain/test_deal_risk.py::test_updated_at_is_converted_to_the_local_zone_before_counting`<br>외 1건 |
| RK-017 | 기한초과이면서 미업데이트면 overdue_stale, 하나만이면 그 값이다 | RK-R6, RK-UC1 | backend | `application/test_deal_views_risk.py::test_list_and_detail_agree_on_the_same_deal`<br>`domain/test_deal_risk.py::test_overdue_and_stale_is_overdue_stale`<br>`domain/test_deal_risk.py::test_overdue_only_is_not_marked_stale` |
| RK-018 | Won·Lost Deal은 기한이 지나고 오래돼도 경고가 없다 | RK-R3, RK-UC1 | backend | `application/test_deal_views_risk.py::test_closed_deal_has_no_risk_in_list_and_detail`<br>`domain/test_deal_risk.py::test_won_and_lost_have_no_risk`<br>`domain/test_deal_risk.py::test_open_forecasts_keep_their_risk`<br>`domain/test_deal_risk.py::test_closed_forecast_is_decided_by_key` |
| RK-019 | Next Action 상태는 미업데이트 판정에 영향이 없다 | RK-R5, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_stale_ignores_the_status_of_the_next_action` |
| RK-020 | 진행사항만 Action을 등록하면 미업데이트가 풀리고 기준일이 다시 지나면 미업데이트다 | RK-R2, RK-R5, RK-UC1 | backend | `application/test_deal_views_next_action_basis.py::test_progress_only_action_refreshes_stale`<br>`application/test_deal_views_next_action_basis.py::test_a_progress_only_action_frees_the_deal_from_stale_until_the_limit_passes_again` |
| RK-021 | Deal을 수정해도 미업데이트가 풀리지 않는다 | RK-R2, RK-R5, RK-UC1 | backend | `application/test_deal_views_risk.py::test_editing_the_deal_does_not_clear_stale` |
| RK-022 | 경고는 저장된 경고 기준으로 계산하고 저장 전이면 14일이다 | RK-R7, RK-R11, RK-UC1 | backend | `application/test_deal_views_risk.py::test_list_rows_carry_risk_from_saved_threshold`<br>`domain/test_alert_thresholds.py::test_default_is_fourteen_days`<br>`domain/test_deal_risk.py::test_custom_stale_days_is_used`<br>`application/test_deal_views_risk.py::test_get_deal_uses_default_threshold_without_settings` |
| RK-023 | 경고 기준을 바꾸면 다음 조회부터 바로 반영된다 | RK-R7, RK-UC4 | backend | `application/test_deal_views_risk.py::test_changing_the_saved_threshold_applies_to_the_same_deals_at_once` |
| RK-024 | 목록은 경고 기준을 요청당 한 번 읽어 모든 행에 쓴다 | RK-R7, RK-UC1 | backend | `application/test_deal_views_risk.py::test_list_reads_the_threshold_once_for_all_rows` |
| RK-025 | 등록·수정·변경 적용 응답도 요청 시각 기준의 경고·체류 일수를 준다 | RK-R7, RK-R10, RK-UC1 | backend | `application/test_deal_views_risk.py::test_register_response_has_zero_days_and_no_risk`<br>`application/test_deal_views_risk.py::test_update_response_is_computed_at_the_request_time`<br>`application/test_deal_views_risk.py::test_apply_change_response_carries_risk_and_days`<br>`application/test_deal_views_risk.py::test_update_response_without_a_status_change_keeps_counting_the_days` |
| RK-026 | Deal 응답은 risk·status_changed_at·status_days를 정해진 모양으로 준다 | RK-R6, RK-R10, RK-UC1 | backend | `web/test_deal_response_risk.py::test_row_and_detail_expose_risk_status_changed_at_and_status_days`<br>`web/test_deal_response_risk.py::test_each_risk_value_is_serialized_as_its_key`<br>`web/test_deal_response_risk.py::test_no_risk_is_serialized_as_null`<br>`web/test_deal_response_risk.py::test_status_changed_at_is_the_deal_entry_time_not_the_update_time`<br>외 1건 |
| RK-027 | overdue 필터는 기한초과 Deal만 고르고 종결 Deal은 빠진다 | RK-R8, RK-UC2 | backend | `application/test_deal_query_risk.py::test_either_flag_makes_the_query_want_risk`<br>`application/test_list_deals_risk_filter.py::test_the_overdue_filter_returns_only_overdue_rows_with_a_matching_total` |
| RK-028 | stale 필터는 미업데이트 Deal만 고른다 | RK-R8, RK-UC2 | backend | `application/test_deal_query_risk.py::test_either_flag_makes_the_query_want_risk`<br>`application/test_list_deals_risk_filter.py::test_the_stale_filter_returns_only_stale_rows_with_a_matching_total` |
| RK-029 | 두 필터를 함께 켜면 어느 하나라도 해당하는 Deal이다 | RK-R8, RK-UC2 | backend | `application/test_deal_query_risk.py::test_risk_filters_default_to_no_condition`<br>`application/test_list_deals_risk_filter.py::test_both_filters_together_return_a_deal_matching_either`<br>`application/test_list_deals_risk_filter.py::test_without_the_filters_every_deal_is_listed` |
| RK-030 | 필터는 같은 요청의 업무 날짜와 저장된 경고 기준(없으면 14)을 쓴다 | RK-R8, RK-R7, RK-UC2 | backend | `application/test_deal_query_risk.py::test_with_risk_basis_fills_the_basis_only_when_a_risk_filter_is_set`<br>`application/test_list_deals_risk_filter.py::test_list_uses_the_business_today_and_the_saved_stale_days`<br>`application/test_list_deals_risk_filter.py::test_list_does_not_flag_a_deal_one_day_short_of_the_saved_stale_days`<br>`application/test_list_deals_risk_filter.py::test_list_uses_the_default_stale_days_when_nothing_is_saved` |
| RK-031 | 미업데이트 필터의 시각 경계는 경고 판정과 일치한다 | RK-R8, RK-R5, RK-UC2 | backend | `domain/test_risk_basis.py::test_stale_before_matches_compute_risk_at_the_day_boundary`<br>`domain/test_risk_basis.py::test_stale_before_with_one_day_means_before_today`<br>`domain/test_risk_basis.py::test_stale_before_agrees_with_compute_risk_for_each_offset`<br>`domain/test_risk_basis.py::test_risk_basis_rejects_stale_days_below_one` |
| RK-032 | 등록하면 진입 시각이 등록 시각이고 체류 0일·경고 없음이다 | RK-R9, RK-R10, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_register_deal_records_the_entry_at_registration_time`<br>`domain/test_deal_status_entry.py::test_create_records_entry_at_registration` |
| RK-033 | 폼 수정으로 Status가 바뀌면 진입 시각이 그 요청 시각이 된다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_update_deal_status_change_moves_status_changed_at`<br>`domain/test_deal_status_entry.py::test_touch_after_status_change_records_now`<br>`domain/test_deal_status_entry.py::test_a_second_status_change_moves_the_entry_again` |
| RK-034 | 폼 수정에서 Forecast만·다른 필드만·같은 Status 재전송은 진입 시각을 바꾸지 않는다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_update_deal_forecast_only_keeps_it`<br>`domain/test_deal_status_entry.py::test_touch_without_status_change_keeps_entry_when_only_forecast_changes`<br>`application/test_status_changed_at_paths.py::test_update_deal_other_fields_keep_it`<br>`application/test_status_changed_at_paths.py::test_update_deal_resending_the_same_status_keeps_it`<br>외 2건 |
| RK-035 | 폼 수정에서 종결 값으로 Status가 바뀌면 진입 시각이 바뀐다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_update_deal_with_closing_values_moves_it` |
| RK-036 | 변경 적용으로 Status를 바꾸면 진입 시각이 바뀌고 Forecast·금액·같은 Status는 그대로다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_apply_change_status_moves_it`<br>`domain/test_deal_status_entry.py::test_apply_sync_forecast_only_change_keeps_status_entry`<br>`application/test_status_changed_at_paths.py::test_apply_change_forecast_only_keeps_it`<br>`application/test_status_changed_at_paths.py::test_apply_change_amount_keeps_it`<br>외 1건 |
| RK-037 | Forecast Won으로 계약완료가 함께 바뀌거나 Won에서 다른 Status로 나가면 진입 시각이 바뀐다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_apply_change_forecast_won_moves_it_with_contract_completed`<br>`domain/test_deal_status_entry.py::test_apply_sync_closing_moves_status_entry`<br>`application/test_status_changed_at_paths.py::test_apply_change_leaving_won_moves_it_to_the_chosen_status`<br>`domain/test_deal_status_entry.py::test_apply_sync_reopening_a_closed_deal_moves_status_entry` |
| RK-038 | Action 등록은 Status를 바꿀 때만 진입 시각을 옮긴다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_register_action_with_status_change_moves_it`<br>`application/test_status_changed_at_paths.py::test_register_action_with_forecast_change_keeps_it`<br>`application/test_status_changed_at_paths.py::test_register_action_with_closing_moves_it`<br>`application/test_status_changed_at_paths.py::test_register_action_without_status_change_keeps_it` |
| RK-039 | 연락처 변경 반영으로 수정 시각이 바뀌어도 진입 시각은 그대로다 | RK-R9, RK-UC3 | backend | `application/test_status_changed_at_paths.py::test_contact_update_touch_keeps_it` |
| RK-040 | 체류 일수는 진입 업무 날짜부터 센 일수이고 당일·미래는 0이다 | RK-R10, RK-UC1 | backend | `application/test_deal_views_risk.py::test_status_days_counts_from_status_changed_at`<br>`domain/test_deal_status_days.py::test_entered_today_is_zero_days`<br>`domain/test_deal_status_days.py::test_entered_three_days_ago_is_three`<br>`domain/test_deal_status_days.py::test_entered_late_yesterday_is_one_day_even_a_few_minutes_ago`<br>외 2건 |
| RK-041 | Status가 바뀌면 체류 일수가 0부터 다시 시작하고 Forecast만 바뀌면 이어진다 | RK-R10, RK-R9, RK-UC3 | backend | `application/test_deal_views_risk.py::test_status_change_resets_the_days_but_forecast_only_change_does_not` |
| RK-042 | 종결 Deal도 체류 일수를 보인다 | RK-R10, RK-UC1 | backend | `application/test_deal_views_risk.py::test_closed_deal_still_shows_status_days` |
| RK-043 | 저장한 적이 없으면 모든 역할이 경고 기준 14일과 빈 저장 기록을 읽는다 | RK-R11, RK-R12, RK-UC4 | backend | `application/test_alert_settings.py::test_get_without_saved_row_returns_default`<br>`web/test_alert_settings_routes.py::test_get_is_open_to_every_role_and_defaults_to_fourteen_days` |
| RK-044 | admin이 저장하면 값·저장자·서버 시각이 응답에 나오고 다시 읽어도 같다 | RK-R12, RK-R13, RK-UC4 | backend | `application/test_alert_settings.py::test_get_returns_the_saved_values_and_the_saver_reference`<br>`web/test_alert_settings_routes.py::test_get_after_an_admin_saved_shows_the_value_the_time_and_the_saver`<br>`application/test_alert_settings.py::test_update_saves_and_returns_actor_and_time`<br>`web/test_alert_settings_routes.py::test_put_by_admin_returns_the_saved_result` |
| RK-045 | 경계값 1일과 365일은 저장된다 | RK-R11, RK-R13, RK-UC4 | backend | `application/test_alert_settings.py::test_update_accepts_the_bounds`<br>`domain/test_alert_thresholds.py::test_bounds_are_one_and_365`<br>`web/test_alert_settings_routes.py::test_put_accepts_the_bounds`<br>`domain/test_alert_thresholds.py::test_values_inside_the_range_are_accepted` |
| RK-046 | 범위 밖 정수는 422 invalid-value 고정 문구이고 저장된 값은 그대로다 | RK-R13, RK-UC4 | backend | `application/test_alert_settings.py::test_update_out_of_range_saves_nothing`<br>`domain/test_alert_thresholds.py::test_values_outside_the_range_are_rejected_with_the_fixed_message`<br>`web/test_alert_settings_routes.py::test_put_out_of_range_is_invalid_value_and_keeps_the_stored_value`<br>`application/test_alert_settings.py::test_update_out_of_range_keeps_the_previous_value` |
| RK-047 | 정수가 아니거나 필드가 없거나 모르는 필드가 있으면 422 request-validation이다 | RK-R13, RK-UC4 | backend | `application/test_alert_settings.py::test_update_rejects_a_bool_as_the_value`<br>`domain/test_alert_thresholds.py::test_bool_is_rejected_even_though_it_is_an_int`<br>`web/test_alert_settings_routes.py::test_put_string_or_float_or_bool_is_request_validation`<br>`domain/test_alert_thresholds.py::test_non_integers_are_rejected`<br>외 2건 |
| RK-048 | sales·user의 변경은 본문과 무관하게 403이고 값은 그대로다 | RK-R13, RK-UC4 | backend | `web/test_alert_settings_routes.py::test_put_by_sales_or_user_is_forbidden_and_saves_nothing`<br>`web/test_alert_settings_routes.py::test_put_by_a_non_admin_with_a_bad_body_is_still_403` |
| RK-049 | 다른 admin이 다시 저장하면 값·저장자·시각이 모두 마지막 저장으로 바뀐다 | RK-R13, RK-UC4 | backend | `application/test_alert_settings.py::test_last_save_wins` |
| RK-050 | 저장자가 퇴사했으면 저장자가 퇴사로 표시된다 | RK-R12, RK-R14, RK-UC4 | backend | `application/test_alert_settings.py::test_get_shows_a_resigned_saver_as_resigned` |
| RK-051 | 화면: 경고 배지는 텍스트로 구분하고 행 색은 기한초과가 우선이다 | RK-R15, RK-UC5 | frontend | `features/deals/list/DealsPage.test.tsx > marks overdue, not-updated and both with badge text and row classes`<br>`shared/ui/Badges.test.tsx > renders nothing for no risk`<br>`features/deals/list/DealsPage.test.tsx > shows no risk on a healthy deal and on closed deals`<br>`shared/ui/Badges.test.tsx > uses text labels, not only color`<br>외 2건 |
| RK-052 | 화면: 목록 범례는 저장된 기준 일수를 보이고 읽는 동안에는 숫자 없이 보인다 | RK-R16, RK-UC5 | frontend | `features/deals/list/DealsPage.alerts.test.tsx > omits the threshold number while the alert settings are loading, then shows the saved one`<br>`features/deals/list/DealsPage.test.tsx > explains the risk colors with a legend, not by color alone` |
| RK-053 | 화면: 경고 기준을 저장하면 목록 범례와 행 경고가 새 기준으로 바뀐다 | RK-R20, RK-R16, RK-UC4 | frontend | `data/alerts.test.tsx > refreshes the cached deal list risk after a successful save`<br>`features/deals/list/DealsPage.alerts.test.tsx > writes the saved threshold into the legend and recolors rows after the save`<br>`data/alerts.test.tsx > leaves the cached deal list untouched when the save is rejected` |
| RK-054 | 화면: 목록에는 체류 일수가 없다 | RK-R16, RK-UC5 | frontend | `features/deals/list/DealsPage.alerts.test.tsx > has no stay-days column or text in the list (the stay is shown on the detail only)` |
| RK-055 | 화면: 기한초과 행은 Due 칸만 강조한다 | RK-R16, RK-UC5 | frontend | `features/deals/list/DealsPage.columns.test.tsx > marks an overdue Next Action date and not a normal one` |
| RK-056 | 화면: 상세 Status 옆에 "N일째"와 진입 시각 툴팁을 보인다 | RK-R17, RK-UC5 | frontend | `features/deals/detail/SummaryBar.stay.test.tsx > shows "N일째" next to Status with the entry time in the tooltip`<br>`features/deals/detail/SummaryBar.stay.test.tsx > shows the tooltip as the wall time of the serialized offset when the change time is UTC`<br>`features/deals/detail/SummaryBar.stay.test.tsx > restarts from 0일째 right after the status changes` |
| RK-057 | 화면: 상세 Next Action 줄에 경고 배지를 보이고 Action이 없어도 미업데이트를 보인다 | RK-R17, RK-UC5 | frontend | `features/deals/detail/SummaryBar.stay.test.tsx > shows the stale badge on a deal that has no action at all` |
| RK-058 | 화면: Actions 표의 기한초과 배지는 서버 경고와 현재 기준 행에만 붙는다 | RK-R18, RK-UC5 | frontend | `features/deals/detail/ActionTable.risk.test.tsx > shows no row badge when the server risk is null even though the due date is past the clock`<br>`features/deals/detail/ActionTable.risk.test.tsx > shows no row badge when the server risk is only stale`<br>`features/deals/detail/ActionTable.risk.test.tsx > shows the badge on the current action row only when the server risk is overdue`<br>`features/deals/detail/ActionTable.risk.test.tsx > shows the badge when the server risk is overdue_stale`<br>외 1건<br>`features/deals/detail/ActionsTab.test.tsx > marks the overdue due date of the current next action` |
| RK-059 | HTTP Deal 매퍼는 서버 경고·체류 일수를 다시 계산하지 않는다 | RK-R21, RK-R7, RK-UC5 | frontend | `gateway/http/mappers/deal.test.ts > uses the server risk %s as it is`<br>`gateway/http/mappers/deal.test.ts > does not recompute risk from the UTC-looking timestamps (an old deal with server risk null stays null)`<br>`gateway/http/mappers/deal.test.ts > maps the status entry time and the stay days from the server` |
| RK-060 | 화면: 경고 기준 탭은 주소로 열리고 현재 값(기본 14)과 저장 기록 없음을 보인다 | RK-R19, RK-UC4 | frontend | `features/admin/deal-management/AlertSettingsForm.test.tsx > is the last (sixth) tab of Deal management, after the Vendor tab`<br>`features/admin/deal-management/AlertSettingsForm.test.tsx > shows the current threshold (default 14) and that nothing was saved yet`<br>`features/admin/deal-management/AlertSettingsForm.test.tsx > opens directly from ?tab=alert for the admin` |
| RK-061 | 화면: 새 값을 저장하면 저장자와 시각을 보이고 다시 열어도 유지된다 | RK-R19, RK-UC4 | frontend | `features/admin/deal-management/AlertSettingsForm.test.tsx > saves a new value, shows who saved it and keeps the value after reload` |
| RK-062 | 화면: 1~365 정수가 아니거나 저장된 값과 같으면 저장할 수 없다 | RK-R19, RK-UC4 | frontend | `features/admin/deal-management/AlertSettingsForm.test.tsx > disables save and explains the range for %s`<br>`features/admin/deal-management/AlertSettingsForm.test.tsx > disables save and explains the range for an empty input`<br>`features/admin/deal-management/AlertSettingsForm.test.tsx > allows the boundary %s`<br>`features/admin/deal-management/AlertSettingsForm.test.tsx > keeps save disabled while the input equals the saved value and enables it for another valid value` |
| RK-063 | 화면: 서버가 거절하면 서버 문구를 보인다 | RK-R19, RK-R21, RK-UC4 | frontend | `features/admin/deal-management/AlertSettingsForm.test.tsx > shows the server sentence when the server refuses the value` |
| RK-064 | 화면: sales에게는 경고 기준 탭이 없다 | RK-R19, RK-UC4 | frontend | `features/admin/deal-management/AlertSettingsForm.test.tsx > is hidden from sales: the tab and the form do not exist` |
| RK-065 | HTTP 경고 기준 게이트웨이는 응답을 바꾸고 오류를 그대로 넘긴다 | RK-R21, RK-UC4 | frontend | `gateway/http/alerts.test.ts > get reads /alert-settings and maps the default (never saved) settings`<br>`gateway/http/alerts.test.ts > get maps the saved time and the saver to a UserRef`<br>`gateway/http/alerts.test.ts > save PUTs {stale_days} and returns the stored settings`<br>`gateway/http/alerts.test.ts > save passes the server 422 sentence through as the message (validation kind)`<br>외 1건 |
| RK-066 | Fake 게이트웨이는 경고 기준·경고·체류 일수를 서버와 같은 규칙으로 낸다 | RK-R21, RK-R3~R5, RK-R9~R13 | frontend | `shared/model/risk.test.ts > T-RISK-01 Due가 오늘이면 기한초과가 아니다`<br>`test/fake/gateway/alerts.test.ts > answers the default 14 days, never saved, to every role`<br>`test/fake/gateway/statusEntry.test.ts > starts at registration with statusDays 0`<br>`shared/model/risk.test.ts > T-RISK-02 Due가 어제면 기한초과다`<br>외 28건 |

### RK-001 Next Action 기준 행은 Next Action이 있는 가장 최근 Action이고 더 최근의 진행사항만 Action은 대신하지 않는다
- Given Deal에 Next Action "계약서 검토"(Due 오늘+30일) Action이 있고, 그 뒤에 진행사항만 Action "전화 통화"가 등록되었다
- When 목록과 상세를 조회한다
- Then 두 응답의 `next_action`은 `{text: "계약서 검토", due_date: 오늘+30일, status: "open"}`이다

### RK-002 수행 시각이 같으면 id가 큰 Action이 기준 행이다
- Given 같은 `acted_at`에 Next Action이 있는 Action 두 건이 있고 나중 행(id가 큼)의 Next Action이 "나중"이다
- When 상세를 조회한다
- Then `next_action.text`는 "나중"이다

### RK-003 Next Action이 한 번도 없으면 next_action은 null이다
- Given Action이 없는 Deal과, 진행사항만 Action만 있는 Deal이 있다
- When 상세를 조회한다
- Then 두 Deal 모두 `next_action`이 `null`이고 `risk`가 기한초과가 아니다

### RK-004 최종 업데이트는 등록 순서와 무관하게 가장 늦은 Action 수행 시각이다
- Given Deal에 수행 시각이 등록+5일인 Action과 그 뒤에 등록한 수행 시각 등록+2일인 Action이 있다
- When 목록을 조회한다
- Then `last_updated_at`은 등록+5일이고 `next_action`은 그 행의 값이다. 진행사항만 Action만 있어도 그 수행 시각이 최종 업데이트다

### RK-005 Action이 없으면 최종 업데이트는 등록 시각이고 Deal 수정은 반영하지 않는다
- Given Action이 없는 Deal을 등록하고 60초 뒤(또는 15일 뒤) 이름·금액을 수정했다
- When 상세를 조회한다
- Then `last_updated_at`은 `created_at`과 같은 순간이다

### RK-006 유일한 Action을 지우면 최종 업데이트가 등록 시각으로 돌아간다
- Given 등록 5일 뒤 Action 하나를 남긴 Deal이다
- When 그 Action을 삭제한 뒤 목록을 조회한다
- Then `last_updated_at`은 Deal 등록 시각이다

### RK-007 Action 수정과 Next Action 상태 변경은 최종 업데이트를 바꾸지 않는다
- Given 등록+1일에 수행한 Action이 있는 Deal이다
- When 등록+3일에 그 Action의 내용을 수정하거나 Next Action 상태를 `done`으로 바꾼다
- Then `last_updated_at`은 여전히 등록+1일이다

### RK-008 같은 Deal의 목록 행과 상세는 같은 파생 값을 준다
- Given Action이 있고 기한초과인 Deal이다
- When 목록과 상세를 같은 시각에 조회한다
- Then `next_action`·`last_updated_at`·`risk`·`status_days`가 같다

### RK-009 기준 행의 Due Date가 오늘보다 앞이면 기한초과다
- Given 서버 시간대가 Asia/Seoul이고 Deal의 기준 행 Due가 어제다
- When 목록과 상세를 조회한다
- Then 두 응답의 `risk`가 `"overdue"`다

### RK-010 Due Date가 오늘이거나 내일이면 기한초과가 아니다
- Given 기준 행 Due가 오늘(또는 내일)이고 최근에 갱신했다
- When 상세를 조회한다
- Then `risk`는 `null`이다

### RK-011 기준 행이 없으면 기한초과가 아니다
- Given Action이 없는 Deal이 등록 직후다
- When 상세를 조회한다
- Then `risk`는 `null`이다

### RK-012 더 최근에 진행사항만 Action이 있어도 기준 행의 Due로 기한초과를 판정한다
- Given 기준 행 Due가 내일인 Action 뒤에 진행사항만 Action이 등록되었다
- When 2일 뒤 상세를 조회한다
- Then `risk`는 `"overdue"`다

### RK-013 기한 지난 Next Action을 종료해도 기한초과가 유지된다
- Given 기준 행 Due가 지났고 그 Next Action 상태를 `done`으로 바꿨다
- When 목록과 상세를 조회한다
- Then `risk`는 `"overdue"`이고 `next_action.status`는 `"done"`이다

### RK-014 기준 14일에서 13일째는 정상이고 14일째부터 미업데이트다
- Given 경고 기준이 기본 14일이고 Action 없는 Deal이 정오에 등록되었다
- When 13일 뒤와 14일 뒤에 목록을 조회한다
- Then 13일 뒤 `risk`는 `null`, 14일 뒤는 `"stale"`이며 훨씬 뒤(예: 60일)도 `"stale"`이다

### RK-015 기준 1일이면 어제 갱신은 미업데이트, 오늘 갱신은 정상이다
- Given 경고 기준이 1일이다
- When 마지막 갱신이 어제인 Deal과 오늘인 Deal을 판정한다
- Then 각각 `"stale"`, `null`이다

### RK-016 오늘과 갱신 날짜는 서버 시간대의 업무 날짜로 센다
- Given 서버 시간대가 Asia/Seoul이다
- When 마지막 갱신이 `2026-10-01T15:30Z`(서울 10-02)이고 요청 시각이 `2026-10-15T15:00Z`(서울 10-16)인 Deal을 기준 14일로 판정한다
- Then 업무 날짜 차이 14일이므로 `"stale"`이고, 시간대 없는 시각은 거절된다(TM-R1)

### RK-017 기한초과이면서 미업데이트면 overdue_stale, 하나만이면 그 값이다
- Given 기준 행 Due가 내일인 Action을 남긴 Deal이다
- When 20일 뒤 상세를 조회한다
- Then `risk`는 `"overdue_stale"`이다. 기한만 지났고 최근 갱신했으면 `"overdue"`다

### RK-018 Won·Lost Deal은 기한이 지나고 오래돼도 경고가 없다
- Given Due가 오늘인 Action을 남긴 뒤 Forecast를 `won`(계약완료) 또는 `lost`로 바꾼 Deal이다
- When 60일 뒤 목록과 상세를 조회한다
- Then `risk`는 `null`이다. `pipeline`·`upside`·`best`·`commit` 같은 다른 key는 판정한다

### RK-019 Next Action 상태는 미업데이트 판정에 영향이 없다
- Given 마지막 Action이 15일 전이고 그 Next Action 상태가 `done`이다
- When 상세를 조회한다
- Then `risk`는 `"stale"`이다

### RK-020 진행사항만 Action을 등록하면 미업데이트가 풀리고 기준일이 다시 지나면 미업데이트다
- Given 등록 13일 뒤 진행사항만 Action을 등록했다
- When 하루 뒤(등록 14일째)에, 그리고 Action 등록 14일 뒤에 상세를 조회한다
- Then 앞의 조회는 `last_updated_at`이 그 Action 수행 시각이고 `risk`가 `null`이며, 뒤의 조회는 `"stale"`이다

### RK-021 Deal을 수정해도 미업데이트가 풀리지 않는다
- Given Action 없이 15일이 지난 Deal이다
- When 금액을 수정한 뒤 상세를 조회한다
- Then `risk`는 `"stale"`이고 `last_updated_at`은 등록 시각이다

### RK-022 경고는 저장된 경고 기준으로 계산하고 저장 전이면 14일이다
- Given 경고 기준이 7일로 저장되어 있다(또는 저장 기록이 없다)
- When 마지막 갱신 후 7일 된 Deal과 13일 된 Deal을 조회한다
- Then 저장 7일이면 둘 다 `"stale"`이고, 저장 기록이 없으면 13일 된 Deal도 `null`이다

### RK-023 경고 기준을 바꾸면 다음 조회부터 바로 반영된다
- Given 8일 지난 Deal(기준 14일에서 `null`)과 15일 지난 Deal(`"stale"`)이 있다
- When admin이 기준을 7일로 저장한 뒤 조회하고, 다시 30일로 저장한 뒤 조회한다
- Then 7일 저장 뒤 8일 된 Deal은 `"stale"`, 30일 저장 뒤 15일 된 Deal은 `null`이다

### RK-024 목록은 경고 기준을 요청당 한 번 읽어 모든 행에 쓴다
- Given Deal 여러 건이 있다
- When 목록을 조회한다
- Then 경고 기준 읽기는 한 번이고 모든 행이 같은 기준으로 판정된다

### RK-025 등록·수정·변경 적용 응답도 요청 시각 기준의 경고·체류 일수를 준다
- Given Due가 내일인 Action을 남기고 3일이 지난 Deal이다
- When 이름을 수정한다(또는 변경 적용을 한다)
- Then 응답의 `risk`는 `"overdue"`, `status_days`는 3이다. 등록 응답은 `status_days` 0, `risk` `null`이다

### RK-026 Deal 응답은 risk·status_changed_at·status_days를 정해진 모양으로 준다
- When Deal 목록 행·상세 응답과 openapi를 만든다
- Then `risk`는 `"overdue"`·`"stale"`·`"overdue_stale"`·`null` 중 하나, `status_changed_at`은 `updated_at`이 아닌 진입 시각(서버 오프셋), `status_days`는 정수이며 셋 다 required이다

### RK-027 overdue 필터는 기한초과 Deal만 고르고 종결 Deal은 빠진다
- Given 기한초과만·미업데이트만·둘 다·정상·기한 지난 Lost Deal이 있다
- When `overdue=true`로 목록을 조회한다
- Then 기한초과만·둘 다 Deal만 나오고 `total`은 2이며 모든 행의 `risk`가 `overdue` 또는 `overdue_stale`이다

### RK-028 stale 필터는 미업데이트 Deal만 고른다
- Given RK-027과 같은 Deal들이다
- When `stale=true`로 조회한다
- Then 미업데이트만·둘 다 Deal만 나오고 `total`은 2이다

### RK-029 두 필터를 함께 켜면 어느 하나라도 해당하는 Deal이다
- Given RK-027과 같은 Deal들이다
- When `overdue=true&stale=true`로 조회한다
- Then 기한초과만·미업데이트만·둘 다 Deal 3건이 나오고 `total`은 3이다. 필터가 없으면 모든 Deal이 나온다

### RK-030 필터는 같은 요청의 업무 날짜와 저장된 경고 기준(없으면 14)을 쓴다
- Given 경고 기준이 7일로 저장되어 있다
- When 마지막 갱신 후 7일 된 Deal과 6일 된 Deal이 있을 때 `stale=true`로 조회한다
- Then 7일 된 Deal만 나온다. 저장 기록이 없으면 14일 기준으로 고른다

### RK-031 미업데이트 필터의 시각 경계는 경고 판정과 일치한다
- Given 서버 시간대가 Asia/Seoul이고 오늘이 2026-10-16, 기준이 14일이다
- When 필터의 기준 시각(`stale_before`)을 구한다
- Then `2026-10-03T00:00+09:00`이며, 이보다 1마이크로초 앞의 갱신은 `compute_risk`도 미업데이트, 이 순간의 갱신은 정상이다. 기준 1일이면 오늘 00:00이고, 기준 0 이하는 `ValueError`다

### RK-032 등록하면 진입 시각이 등록 시각이고 체류 0일·경고 없음이다
- Given sales로 로그인했다
- When Deal을 등록한다
- Then 응답 `status_changed_at`은 서버 시각, `status_days`는 0, `risk`는 `null`이며 저장된 진입 시각도 같다

### RK-033 폼 수정으로 Status가 바뀌면 진입 시각이 그 요청 시각이 된다
- Given Status `prospecting`으로 등록하고 5일이 지났다
- When `PATCH`로 `status_key: "introduction"`을 저장한다
- Then `status_changed_at`은 그 요청의 서버 시각이고 `status_days`는 0이다. 다시 다른 Status로 바꾸면 또 그 시각으로 옮긴다

### RK-034 폼 수정에서 Forecast만·다른 필드만·같은 Status 재전송은 진입 시각을 바꾸지 않는다
- Given Status `prospecting`으로 등록하고 5일이 지났다
- When `{forecast_key: "best"}`, `{name: "다른 이름"}`, `{status_key: "prospecting", name: …}` 중 하나를 저장한다
- Then `status_changed_at`은 등록 시각 그대로다

### RK-035 폼 수정에서 종결 값으로 Status가 바뀌면 진입 시각이 바뀐다
- Given 진행 중인 Deal이다
- When 폼에서 종결 값(Won·계약완료와 매출 정보)으로 저장한다
- Then `status_changed_at`은 그 요청의 서버 시각이다

### RK-036 변경 적용으로 Status를 바꾸면 진입 시각이 바뀌고 Forecast·금액·같은 Status는 그대로다
- Given Status `prospecting`으로 등록하고 5일이 지났다
- When `/changes`로 Status를 `introduction`으로 바꾸거나, Forecast만·금액만·같은 Status를 적용한다
- Then Status를 바꾼 경우만 응답 `deal.status_changed_at`이 그 시각이고 `status_days`가 0이며, 나머지는 등록 시각·5일 그대로다

### RK-037 Forecast Won으로 계약완료가 함께 바뀌거나 Won에서 다른 Status로 나가면 진입 시각이 바뀐다
- Given 진행 중인 Deal(또는 Won Deal)이다
- When `/changes`로 Forecast `won`과 종결 값을 적용한다(또는 Won Deal에서 다른 Status를 골라 나간다)
- Then `status_changed_at`은 그 요청의 서버 시각이다

### RK-038 Action 등록은 Status를 바꿀 때만 진입 시각을 옮긴다
- Given Status `prospecting`으로 등록하고 5일이 지났다
- When `status_change`로 Status를 `introduction`으로 바꾸는 Action, 종결하는 Action, Forecast만 바꾸는 Action, `status_change` 없는 Action 중 하나를 등록한다
- Then 앞의 두 경우는 진입 시각이 Action 등록 시각이고 뒤의 두 경우는 그대로다

### RK-039 연락처 변경 반영으로 수정 시각이 바뀌어도 진입 시각은 그대로다
- Given Deal의 고객 연락처가 연결되어 있다
- When 연락처 수정이 그 Deal의 수정 시각을 갱신한다
- Then `status_changed_at`은 그대로다

### RK-040 체류 일수는 진입 업무 날짜부터 센 일수이고 당일·미래는 0이다
- Given 서버 시간대가 Asia/Seoul이다
- When 진입 시각이 오늘, 3일 전, 어제 23:5x(몇 분 전), 미래인 경우의 체류 일수를 구한다
- Then 각각 0, 3, 1, 0이고, 진입 시각은 서버 시간대 날짜로 바꿔 센다. 5일 전에 등록한 Deal은 목록·상세 모두 5이다

### RK-041 Status가 바뀌면 체류 일수가 0부터 다시 시작하고 Forecast만 바뀌면 이어진다
- Given 5일 전에 등록한 Deal이다
- When Status를 바꾸고 조회하거나, Forecast만 바꾸고 조회한다
- Then 앞의 경우 `status_days` 0, 뒤의 경우 5이다

### RK-042 종결 Deal도 체류 일수를 보인다
- Given 10일 전에 Won(계약완료)이 된 Deal이다
- When 상세를 조회한다
- Then `risk`는 `null`이고 `status_days`는 10이다

### RK-043 저장한 적이 없으면 모든 역할이 경고 기준 14일과 빈 저장 기록을 읽는다
- Given 경고 기준을 저장한 적이 없고 admin, sales, user 중 하나로 로그인했다
- When `GET /api/v1/alert-settings`를 부른다
- Then 200 `{"stale_days": 14, "updated_at": null, "updated_by": null}`이다

### RK-044 admin이 저장하면 값·저장자·서버 시각이 응답에 나오고 다시 읽어도 같다
- Given admin으로 로그인했다
- When `PUT {"stale_days": 7}`을 보낸다
- Then 200이고 키는 `stale_days`·`updated_at`·`updated_by`뿐이며 `stale_days` 7, `updated_by`는 그 admin의 `UserRef`, `updated_at`은 서버 시각(서버 오프셋)이고, 다시 GET한 본문이 같다

### RK-045 경계값 1일과 365일은 저장된다
- Given admin으로 로그인했다
- When `stale_days` 1 또는 365를 저장한다
- Then 200이고 다시 읽은 값이 같다

### RK-046 범위 밖 정수는 422 invalid-value 고정 문구이고 저장된 값은 그대로다
- Given admin이 21일로 저장해 두었다
- When `stale_days` 0, 366, −1 중 하나를 저장한다
- Then 422 `invalid-value`, `detail`은 "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."이고 다시 읽은 값은 21이다

### RK-047 정수가 아니거나 필드가 없거나 모르는 필드가 있으면 422 request-validation이다
- Given admin으로 로그인했다
- When `stale_days`가 `"7"`, `7.5`, `true`, `null`이거나, 본문이 `{}` 또는 `{"stale_days": 7, "long_stay_days": 30}`인 요청을 보낸다
- Then 422 `request-validation`이고 값은 그대로다

### RK-048 sales·user의 변경은 본문과 무관하게 403이고 값은 그대로다
- Given sales 또는 user로 로그인했다
- When `PUT {"stale_days": 7}`(또는 형식이 틀린 본문)을 보낸다
- Then 403 `forbidden`(admin 전용 문구)이고 값은 14 그대로다

### RK-049 다른 admin이 다시 저장하면 값·저장자·시각이 모두 마지막 저장으로 바뀐다
- Given admin A가 7일로 저장했다
- When 5분 뒤 admin B가 30일로 저장한다
- Then 응답과 다시 읽은 값은 `stale_days` 30, `updated_by` B, `updated_at` B의 저장 시각이다

### RK-050 저장자가 퇴사했으면 저장자가 퇴사로 표시된다
- Given admin B가 경고 기준을 저장했고 이후 퇴사 처리되었다(삭제 요청이 퇴사로 바뀐 판정은 US-058)
- When 경고 기준을 조회한다
- Then `updated_by.id`는 B이고 `resigned`는 `true`다

### RK-051 화면: 경고 배지는 텍스트로 구분하고 행 색은 기한초과가 우선이다
- Given Fake 데이터에 기한초과·미업데이트·둘 다·정상·Won Deal이 있다
- When Deals 목록을 연다(또는 `RiskBadge`를 그린다)
- Then 기한초과 행은 "기한초과"만·`risk-overdue`, 미업데이트 행은 "미업데이트"만·`risk-stale`, 둘 다는 두 배지·`risk-overdue`, 정상·Won 행은 배지·클래스가 없다

### RK-052 화면: 목록 범례는 저장된 기준 일수를 보이고 읽는 동안에는 숫자 없이 보인다
- Given 경고 기준 응답이 아직 오지 않았다
- When Deals 목록을 연다
- Then 범례는 "기준일 이상 미업데이트"이고, 응답이 오면 "14일 이상 미업데이트"가 된다

### RK-053 화면: 경고 기준을 저장하면 목록 범례와 행 경고가 새 기준으로 바뀐다
- Given 목록을 한 번 읽어 캐시에 두었다
- When admin이 경고 기준을 21로 저장한다
- Then 범례가 "21일 이상 미업데이트"로 바뀌고 행 경고가 새 기준으로 다시 그려진다. 저장이 거절되면 캐시된 목록은 그대로다

### RK-054 화면: 목록에는 체류 일수가 없다
- When Deals 목록을 연다
- Then "N일째" 같은 체류 일수 열·문구가 없다

### RK-055 화면: 기한초과 행은 Due 칸만 강조한다
- Given 기한초과 Deal과 정상 Deal이 있다
- When Deals 목록을 연다
- Then 기한초과 행의 Due 칸은 그 날짜와 `overdue` 표시가 있고 Next Action 칸은 표시가 없으며, 정상 행 Due 칸은 표시가 없다

### RK-056 화면: 상세 Status 옆에 "N일째"와 진입 시각 툴팁을 보인다
- Given Deal의 `statusDays`가 5이고 `statusChangedAt`이 `2026-10-11T06:00:00Z`다
- When 상세를 연다
- Then Status 옆에 "5일째"가 보이고 툴팁은 문자열 오프셋의 벽시계(`formatDateTime`)다. Status를 바꾸면 "0일째"가 된다

### RK-057 화면: 상세 Next Action 줄에 경고 배지를 보이고 Action이 없어도 미업데이트를 보인다
- Given Action이 없고 `risk`가 `stale`인 Deal이다
- When 상세를 연다
- Then Next Action 줄에 "없음"과 "미업데이트" 배지가 보인다

### RK-058 화면: Actions 표의 기한초과 배지는 서버 경고와 현재 기준 행에만 붙는다
- Given Deal의 기준 행 Due가 지난 것처럼 보이는 Actions 목록이다
- When 서버 `risk`가 `null`·`stale`·`overdue`·`overdue_stale`인 각 경우에 Actions 탭을 연다
- Then `overdue`·`overdue_stale`일 때만 기준 행 Due 칸에 "기한초과" 배지가 하나 보인다. 브라우저 시계가 Due 이전이어도 서버가 `overdue`면 배지가 보인다

### RK-059 HTTP Deal 매퍼는 서버 경고·체류 일수를 다시 계산하지 않는다
- Given 서버 응답의 시각은 오래된 것처럼 보이지만 `risk`가 `null`이고 `status_changed_at`·`status_days`가 있다
- When Deal 응답을 화면 모델로 바꾼다
- Then `risk`는 `null`, `statusChangedAt`·`statusDays`는 서버 값 그대로다

### RK-060 화면: 경고 기준 탭은 주소로 열리고 현재 값(기본 14)과 저장 기록 없음을 보인다
- Given admin으로 로그인했고 저장 기록이 없다
- When `/admin/deal?tab=alert`를 연다
- Then 탭 "경고 기준"이 선택되어 있고(마지막 탭), "미업데이트 기준(일)" 칸이 14이며 "마지막 저장" 문구가 없다

### RK-061 화면: 새 값을 저장하면 저장자와 시각을 보이고 다시 열어도 유지된다
- Given admin이 경고 기준 탭을 열었다
- When 21을 입력하고 "저장"을 누른다
- Then "마지막 저장 {admin 표시} · {시각}"이 보이고, 화면을 다시 열어도 21이다

### RK-062 화면: 1~365 정수가 아니거나 저장된 값과 같으면 저장할 수 없다
- Given admin이 경고 기준 탭을 열었다(저장 값 14)
- When 0, 366, 빈 값을 입력하거나 14를 그대로 둔다
- Then 0·366·빈 값은 칸이 `aria-invalid`이고 "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."가 보이며 "저장"이 비활성이다. 14 그대로면 "저장"이 비활성이고, 1·365는 저장할 수 있다

### RK-063 화면: 서버가 거절하면 서버 문구를 보인다
- Given 서버가 저장을 422로 거절한다
- When "저장"을 누른다
- Then 오류 배너에 서버 `detail`이 보인다

### RK-064 화면: sales에게는 경고 기준 탭이 없다
- Given sales로 로그인했다
- When `/admin/deal?tab=alert`를 연다
- Then "경고 기준" 탭과 "경고 기준 변경" 폼이 없다

### RK-065 HTTP 경고 기준 게이트웨이는 응답을 바꾸고 오류를 그대로 넘긴다
- Given 서버가 기본값, 저장된 값(저장자 포함), 422, 403, 401 응답을 준다
- When HTTP 게이트웨이로 읽고 저장한다
- Then `{staleDays, updatedAt, updatedBy}`로 바뀌고, 저장은 `PUT {stale_days}`이며, 422 문장은 메시지 그대로, 403·401은 그 상태의 `ApiError`다

### RK-066 Fake 게이트웨이는 경고 기준·경고·체류 일수를 서버와 같은 규칙으로 낸다
- Given Fake 게이트웨이와 시계다
- When 경고 기준을 읽고 저장하고(역할별), Deal 경고·체류 일수·진입 시각을 조회·변경한다
- Then 기본 14·admin만 저장·범위 밖 422·경계 1/365가 서버와 같고, `computeRisk`·`statusDays`가 RK-R3~R5·R10과 같으며(Due 오늘 아님, 14일째 stale, 종결 null, 달력 날짜 기준), 진입 시각은 Status가 바뀔 때만 옮긴다(RK-R9)

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 최초 작성: 구현된 경고·파생 값·경고 기준 동작을 정본 명세로 옮김. 규칙 RK-R1~R21, use case RK-UC1~UC5, BDD 케이스 RK-001~RK-066 | RK-001~RK-066(신규) |
