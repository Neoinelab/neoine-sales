# 서버 시간·업무 날짜   (feature 코드: TM, 상태: 확정(2026-11-13 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09). 근거는 작업 트리의 코드(`backend/src/app/domain/common/business_date.py`, `domain/deal/updated_period.py`의 `months_before`·`months_after`, `application/time/get_server_time.py`, `web/routers/time.py`, `web/schemas/{time,server_datetime}.py`, `infra/system_clock.py`, `frontend/src/gateway/{clock.ts,http/time.ts}`, `data/{time.ts,today.ts}`, `features/auth/RequireAuth.tsx`, `shared/format.ts`, `shared/model/dates.ts`)와 이전 계획 `artifacts/10-analysis/server-time-plan.md`(2026-10-23 사용자 결정 Q1 A)입니다. 계획과 코드가 다른 곳은 코드를 따랐습니다(예: 포커스 재동기는 마지막 동기 후 30분이 지났을 때만).

## 1. 개요

- 목적: 앱의 "지금"과 "오늘"을 서버 한 곳에서 정하고, 화면에 보이는 모든 시각을 서버 시간대로 보여 준다. 브라우저 시계·시간대가 서버와 달라도 결과가 같다.
- 사용자(역할): 로그인한 모든 역할(`admin`·`sales`·`user`). 업무 날짜 규칙은 다른 feature의 서버 계산이 쓴다.
- 범위
  - 서버 시계(`Clock` Port)와 업무 시간대·업무 시각·업무 날짜·업무일 시작, 개월 이동(`months_before`·`months_after`) 달력 규칙
  - `GET /api/v1/time`
  - 응답 시각 직렬화(`ServerDateTime`)와 재발 방지 검사
  - 프런트 서버 동기 시계(`createServerClock`), 동기 훅(`useServerTimeSync`)과 로그인 후 화면 보류(`RequireAuth`), `useToday`, 시각 표기 함수(`shared/format.ts`), 브라우저 시계·시간대 사용 금지(T-ARCH-03)
- 범위 밖
  - 각 화면·기능이 업무 날짜를 어디에 쓰는지(기본 연도·분기, 경고 판정, Deal code 날짜, 기간 프리셋, 스냅숏 월 등)는 각 feature: DE(Deal code 날짜), RK(경고·체류 일수), DL(최종 업데이트 기간 프리셋 `/deals/updated-periods`, 날짜 범위 조건), NA(Action 수행일 검색), FC(스냅숏 기준 월), DSH(이번 달·분기), RQ(상대 기간·결과 셀), LC(만료 임박 색)
  - 서버 시간대 설정값(`APP_TZ` 같은 설정 없음), 사용자별 표시 시간대, DB 저장 형식(`timestamptz`)
  - 날짜 입력 칸(`DateInput`, UI-R1~R11), 로그인 전 화면의 시각(로그인·최초 설정 화면은 시각을 쓰지 않음)
  - 인증 가드 자체(401 판정·문구는 AU·PL), 경쟁·동시성 테스트
- 운영 전제: 서버(product는 api 컨테이너, `/etc/localtime` mount) OS 시간대가 업무 시간대다. Asia/Seoul이어야 화면 시각이 한국 시각이 된다(배포 담당자 확인 사항).
- 관련 화면·메뉴: 메뉴 없음. 로그인 후 모든 화면의 "불러오는 중…"(첫 동기 전)과 시각 표시.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 서버 시계 | `application/ports/clock.py`의 `Clock.now()`. 실제 구현 `SystemClock`은 시간대가 있는 UTC 현재 시각을 돌려준다. 테스트는 `FixedClock`·`SteppingClock`(부를 때마다 1초) |
| 업무 시간대 | 서버 프로세스(OS)의 로컬 시간대(환경 변수 `TZ` 또는 `/etc/localtime`). 별도 설정값이 없다 |
| 업무 시각 | 같은 순간을 업무 시간대 오프셋으로 바꾼 시각(`business_time`) |
| 업무 날짜(오늘) | 업무 시각의 달력 날짜(`business_date`) |
| 업무일 시작 | 업무 날짜의 업무 시간대 00:00 순간(`start_of_business_day`) |
| 개월 이동 | 날짜를 n개월 앞·뒤의 같은 날로 옮기되 그날이 없으면 그 달 말일로 맞추는 계산(`months_before`·`months_after`) |
| 오프셋 ISO | `YYYY-MM-DDTHH:MM:SS[.ffffff](Z|±HH:MM)` 형식의 시각 문자열 |
| 앱 시계 | 프런트 `gateway/index.ts`의 `clock`(`createServerClock()`). 화면의 지금·오늘의 유일한 출처 |
| 동기 | 앱 시계가 `GET /api/v1/time` 응답으로 보정값(skew)과 오프셋을 정하는 일(`clock.syncWith`) |
| 벽시계 | 오프셋 ISO 문자열에 적힌 그 오프셋의 날짜·시각 그대로의 값 |

### 2.2 데이터 모델

테이블 없음. 마이그레이션 없음.

- `ServerTimeView`(application, frozen): `now: datetime`(업무 시각), `today: date`(업무 날짜).
- `ServerTimeResponse`(web): `now: ServerDateTime`, `today: date`.
- `ServerDateTime`(web): `Annotated[datetime, PlainSerializer(business_time, return_type=datetime, when_used="always")]`.
- 프런트 `ServerTime`(`gateway/types.ts`): `{ now: string /* 오프셋 ISO */, today: string /* YYYY-MM-DD */ }`, `Clock`: `now(): string`, `syncWith(fetch: () => Promise<ServerTime>): Promise<ServerTime>`, `Today`(`data/today.ts`): `{ now: string, today: string, year: number }`.

### 2.3 비즈니스 규칙

서버 시각과 업무 날짜(다른 feature가 가리키는 공유 규칙)
- **TM-R1** 서버 쪽의 모든 "지금"은 `Clock` Port 하나에서 나온다. 유스케이스·도메인은 시스템 시계를 직접 읽지 않고 받은 `now`(시간대가 있는 시각)로 계산한다. 업무 시각·업무 날짜 계산에 시간대 정보가 없는 시각을 넣으면 `InvalidValueError` "moment은(는) 시간대(timezone) 정보가 있어야 합니다"로 거절한다(프로그래밍 오류이며 API 입력으로는 생기지 않는다).
- **TM-R2** 업무 시간대는 서버 프로세스의 OS 로컬 시간대다. 설정값으로 바꿀 수 없다. 서머타임이 있는 시간대면 시각마다 그 순간의 오프셋을 쓴다(예: America/New_York에서 7월은 −04:00, 12월은 −05:00).
- **TM-R3** 업무 시각(`business_time`)은 같은 순간을 업무 시간대 오프셋으로 바꾼 값이다. 순간·마이크로초는 바뀌지 않는다. 다른 오프셋으로 들어온 시각도 업무 시간대로 바꾼다. 예(Asia/Seoul): `2026-10-22T15:30:00Z` → `2026-10-23T00:30:00+09:00`, `2026-10-22T20:00:00-04:00` → `2026-10-23T09:00:00+09:00`.
- **TM-R4** 업무 날짜(오늘, `business_date`)는 업무 시각의 달력 날짜다. UTC 날짜가 아니다. 날짜가 바뀌는 순간은 업무 시간대 00:00이다: Asia/Seoul이면 UTC 14:59는 같은 날, UTC 15:00은 다음 날(예: `2026-12-31T15:00Z` → 2027-01-01). 업무 시간대가 UTC면 UTC 날짜와 같다. 다른 feature의 "오늘"(Deal code 날짜·경고·체류 일수·기간 프리셋·Dashboard 이번 달/분기·Forecast 스냅숏 월·Reports 상대 기간)은 모두 이 값이다.
- **TM-R5** 업무일 시작(`start_of_business_day(day)`)은 그 날짜의 업무 시간대 00:00 순간(시간대 있음)이다. 예(Asia/Seoul): 2026-10-16 → `2026-10-15T15:00:00Z`. 그 순간의 업무 날짜는 그 날이고 1마이크로초 전은 전날이다. 양끝을 포함하는 날짜 범위(`from`~`to`)를 시각 조건으로 바꿀 때는 `start_of_business_day(from)` 이상, `start_of_business_day(to + 1일)` 미만이다(DL·NA·RQ가 이 규칙을 쓴다).
- **TM-R6** 개월 이동: `months_before(day, n)`·`months_after(day, n)`은 n개월 전·뒤의 같은 날이고, 그 달에 그날이 없으면 그 달 말일이다. n = 0이면 같은 날, n = 12면 1년 전·뒤 같은 날(2024-02-29 → 2023-02-28 / 2025-02-28). 연 경계를 넘을 수 있다. 예: 2026-03-31의 1개월 전 = 2026-02-28, 2024-03-31의 1개월 전 = 2024-02-29, 2026-01-31의 1개월 뒤 = 2026-02-28, 2026-12-31의 2개월 뒤 = 2027-02-28. n이 음수면 `ValueError`(프로그래밍 오류). 기간 프리셋(DL)·Reports 상대 기간(RQ)은 이 규칙으로 시작일·끝일을 정한다.

서버 시각 API
- **TM-R7** `GET /api/v1/time`은 로그인한 모든 역할에게 200 `{"now", "today"}`(키는 정확히 이 둘)를 준다. 서버 시계를 **한 번만** 읽어 `now` = 업무 시각, `today` = `now`의 날짜 부분이다(따라서 `today == now[:10]`이 항상 성립하고, 자정 직전에 읽어도 둘이 어긋나지 않는다). `now`는 오프셋 ISO이며 마이크로초가 0이면 소수 초가 없고 아니면 6자리다. 로그인하지 않으면 401 `unauthenticated`(problem+json, 판정·문구는 인증 가드 소유). DB를 읽지 않는다. openapi에는 `now`가 `string/date-time`, `today`가 `string/date`, 둘 다 required, 401 응답이 문서화된다.

응답 시각 표기
- **TM-R8** 모든 API 응답의 시각(`datetime`) 필드는 `ServerDateTime`이며 같은 순간을 업무 시간대 오프셋으로 직렬화한다(Asia/Seoul이면 `+09:00`, `Z`가 아님). `model_dump(mode="json")`·`model_dump_json()`·FastAPI 응답 모두 같다. 순간은 바뀌지 않고(문자열을 다시 읽으면 원래 순간), 마이크로초는 유지되며, `null`은 `null`이다. openapi 필드 스키마는 일반 `datetime`과 같다(`{"type":"string","format":"date-time"}`, nullable은 `anyOf [date-time, null]`, required 여부 유지). 날짜(`date`) 필드는 `YYYY-MM-DD` 그대로다. `app.web.schemas`의 어떤 응답·요청 모델에도 `ServerDateTime`이 아닌 맨 `datetime` 필드를 두지 않는다(재발 방지 검사). Reports 결과 셀의 시각 값도 같은 표기다(RQ가 검증).

프런트 앱 시계
- **TM-R9** 앱 시계(`createServerClock(browserMs = Date.now)`): 동기할 때 요청 직전·응답 직후 브라우저 시각의 중간을 서버 `now`의 순간으로 보아(왕복 지연 절반 보정) 보정값 = `Date.parse(서버 now) − (직전 + 직후) / 2`, 오프셋 = 서버 `now` 문자열의 오프셋(`Z`는 0분)으로 정한다. 이후 `now()` = `브라우저 ms + 보정값`을 서버 오프셋으로 쓴 `YYYY-MM-DDTHH:MM:SS±HH:MM`(소수 초 없음, 오프셋 0은 `+00:00`)이다. 즉 브라우저 시계는 경과 시간 측정에만 쓰고, 브라우저 날짜·시간대는 결과에 영향이 없다. 동기 사이에 자정을 지나면 날짜가 서버 오프셋 기준으로 바뀐다. 다시 동기하면 보정값·오프셋을 새 값으로 바꾼다. 서버 `now`에 오프셋이 없거나 시각으로 읽을 수 없으면 `RangeError`("서버 시각 형식이 올바르지 않습니다: <값>")로 reject하고, `fetch`가 실패하면 그 오류로 reject한다. 두 경우 모두 직전 동기 상태가 그대로다. 성공하면 받은 `ServerTime`을 그대로 돌려준다. 첫 동기 전 `now()`는 브라우저 시각·브라우저 오프셋이며 앱은 이 값을 화면에 쓰지 않는다(TM-R11 보류). 시계 인스턴스끼리 상태를 나누지 않는다.
- **TM-R10** HTTP 게이트웨이 `time.get()`은 `GET /api/v1/time`을 부르고 `{now, today}`만 돌려준다(`Z` 표기도 그대로). `now`가 오프셋 ISO가 아니거나 읽을 수 없는 시각, `today`가 `YYYY-MM-DD`가 아니거나(시각 포함 등) 없으면 `ApiError` 502 `malformed-response` "서버 응답을 해석할 수 없습니다."로 reject한다. 401 등 서버 오류는 그 상태의 `ApiError`로 그대로 넘긴다. Fake 게이트웨이도 같은 모양을 낸다(계약 스위트 `time.contract.ts`).
- **TM-R11** 동기 시점(`useServerTimeSync(enabled)` + `RequireAuth`): 로그인 확인(`useMe` 성공) 뒤에만 첫 동기를 요청한다(로그인하지 않았으면 요청 없이 `/login`으로 보낸다). 첫 동기 응답 전에는 로그인 후 레이아웃 대신 "불러오는 중…"을 보이고, 첫 동기가 실패하면 레이아웃 없이 오류 배너(`role="alert"`, 서버 `detail`)를 보인다. 실패는 재시도하지 않는다. 동기 성공 뒤 30분마다 다시 동기하고, 마지막 동기 후 30분이 지난 뒤 창에 포커스가 돌아오면 다시 동기한다(30분 안의 포커스 복귀는 요청하지 않음). 재동기가 실패하면 직전 결과와 앱 시계를 유지하고 화면은 그대로다(오류 배너 없음). 로그인 세션 하나에서 첫 화면 진입 시 요청은 1회다.
- **TM-R12** `useToday()`는 렌더할 때마다 앱 시계를 읽어 `{ now: clock.now(), today: now의 앞 10자, year: today의 연도 숫자 }`를 돌려준다(구독하지 않는다). 화면은 지금·오늘·올해를 이 훅(또는 앱 시계)으로만 얻는다.
- **TM-R13** 브라우저 시계·시간대 금지(T-ARCH-03): 앱 소스(테스트·`test/`·`testHelpers`/`testUtils`·`gateway/contract/**` 제외, 주석 제외)에서 `gateway/clock.ts` 밖에는 `Date.now(`, 인자 없는 `new Date()`, `getTimezoneOffset`, `toLocaleDateString`·`toLocaleTimeString`, 날짜의 `toLocaleString`, 로컬 getter·setter(`getFullYear`·`getMonth`·`getDate`·`getDay`·`getHours`·`getMinutes`·`getSeconds`·`getMilliseconds`·`getYear`, `setFullYear`·`setMonth`·`setDate`·`setHours`·`setMinutes`·`setSeconds`·`setMilliseconds`), `timeZone` 없는 `Intl.DateTimeFormat`, 오프셋 없는 날짜·시각 문자열의 `new Date`/`Date.parse`, `String(new Date(…))`, 날짜의 `toString()`, `resolvedOptions().timeZone`이 없다. `gateway/clock.ts`는 `Date.now`를 읽는 유일한 파일이다.

시각 표기(frontend)
- **TM-R14** 시각 표시 함수는 문자열에 적힌 오프셋의 벽시계를 그대로 보이고 브라우저 시간대로 바꾸지 않는다. 시각으로 읽는 문자열은 끝에 오프셋(`Z`·`±HH:MM`)이 있는 ISO뿐이며 그 밖의 값(빈 문자열, 날짜만, 오프셋 없는 시각, 공백 구분, 달력에 없는 값)은 예외 없이 **원문 그대로** 돌려준다.
  - `formatDateTime(iso)` = `ko-KR` `dateStyle: medium`·`timeStyle: short` 형식. 예: `2026-10-23T15:04:59+09:00` → `2026. 10. 23. 오후 3:04`, `2026-10-23T00:30:00-05:00` → `2026. 10. 23. 오전 12:30`, `2030-06-14T16:00:00Z` → `2030. 6. 14. 오후 4:00`. 소수 초·30분 단위 오프셋도 읽는다.
  - `formatStamp(iso)` = `YYYY-MM-DD HH:mm`. 예: `2026-10-23T15:04:59.123456+09:00` → `2026-10-23 15:04`, `2026-10-23T23:30:00-05:00` → `2026-10-23 23:30`.
  - `formatDate(value)` = 앞 10자(날짜는 그대로, 시각은 문자열에 적힌 날짜).
- **TM-R15** 상대 시각 `formatRelativeTime(iso, now)`(`now`는 `useToday().now`): 차이가 1분 미만이거나 미래면 `방금 전`, 60분 미만 `N분 전`, 24시간 미만 `N시간 전`, 30일 미만 `N일 전`(모두 내림), 30일 이상이면 `formatDate(iso)`(문자열에 적힌 날짜).
- **TM-R16** 달력 날짜 계산은 시간대 없이 달력만 쓴다: `nextDay('YYYY-MM-DD')`는 다음 날(월말·연말·윤일 포함, 예: 2026-12-31 → 2027-01-01, 2028-02-28 → 2028-02-29, 2026-02-28 → 2026-03-01). `shared/model/dates.ts`의 `addDays`·`daysBetween`·`datePart`·`formatWithOffset`·`offsetMinutes`도 같은 원칙이다.

### 2.4 상태와 전이

앱 시계 동기 상태(frontend)

| 상태 | 화면 | `useToday` | 다음 |
| --- | --- | --- | --- |
| 로그인 확인 전·미로그인 | "불러오는 중…" 또는 `/login` | 쓰지 않음 | 로그인 확인 → 첫 동기 요청 |
| 첫 동기 대기 | "불러오는 중…"(레이아웃 없음) | 쓰지 않음 | 성공 → 동기됨 / 실패 → 첫 동기 실패 |
| 첫 동기 실패 | 오류 배너(레이아웃 없음) | 쓰지 않음 | (재시도 없음) |
| 동기됨 | 레이아웃 | 서버 기준 | 30분 경과·30분 뒤 포커스 복귀 → 재동기(성공: 값 교체, 실패: 직전 값 유지) |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /time` | 401 | 가능 | 가능 | 가능 |

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/time` | — | 200 `ServerTimeResponse` `{"now":"2026-10-23T09:30:00.123456+09:00","today":"2026-10-23"}` | 401 `unauthenticated` |

- 라우터: `BusinessRouter(prefix="/api/v1/time", tags=["time"])`(로그인 가드), 유스케이스 `GetServerTime(clock)`, 조립 `provider.get_server_time()`.
- 모든 응답의 시각 필드는 TM-R8 표기다. 새 오류 type 없음.

### 2.7 화면 동작

TM-R9~TM-R16. 화면 기능(기본 연도·분기, 상대 시각 표시, Forecast 기준 시각 문구, Deal 목록 최종 업데이트 title 등)은 각 feature가 TM-R12·TM-R14·TM-R15를 가리킨다.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구 |
| --- | --- | --- |
| 미로그인 `GET /time` | 401 `unauthenticated` | 인증 가드 문구(AU) |
| 프런트: `/time` 응답 형식 오류 | `ApiError` 502 `malformed-response` | 서버 응답을 해석할 수 없습니다. |
| 프런트: 동기 시 서버 `now` 오프셋 없음·읽기 불가 | `RangeError` | 서버 시각 형식이 올바르지 않습니다: <값> |
| 프런트: 첫 동기 실패 | 오류 배너 | 서버 `detail` 그대로 |
| 서버: 시간대 없는 시각 계산(프로그래밍 오류) | `InvalidValueError` | moment은(는) 시간대(timezone) 정보가 있어야 합니다 |
| 서버: 음수 개월 이동(프로그래밍 오류) | `ValueError` | months는 0 이상이어야 합니다: <n> |

## 3. Business use case

### TM-UC1 서버 시각 조회
- 행위자: 로그인한 사용자(앱)
- 사전 조건: 로그인 세션
- 기본 흐름: `GET /api/v1/time` → 서버 시계를 한 번 읽어 업무 시각과 업무 날짜를 돌려준다(TM-R7)
- 예외: 로그인하지 않으면 401
- 결과: `{now, today}`, `today == now[:10]`

### TM-UC2 업무 날짜·시각 계산
- 행위자: 시스템(다른 feature의 서버 계산)
- 사전 조건: 시간대가 있는 `now`
- 기본 흐름: `business_time`·`business_date`·`start_of_business_day`·`months_before`/`months_after`로 업무 시각·오늘·날짜 경계·기간 시작/끝을 정한다(TM-R2~R6)
- 예외: 시간대 없는 시각·음수 개월은 프로그래밍 오류로 거절
- 결과: 서버 OS 시간대 기준의 날짜·순간

### TM-UC3 응답 시각 표기
- 행위자: 시스템(모든 API 응답)
- 기본 흐름: 응답 모델의 시각 필드를 업무 시간대 오프셋 문자열로 직렬화한다(TM-R8)
- 결과: 같은 순간, 서버 오프셋 문자열, openapi 스키마 변화 없음

### TM-UC4 앱 시계 동기
- 행위자: 로그인한 사용자(앱)
- 사전 조건: 로그인 확인
- 기본 흐름: 첫 동기 요청 → 응답 전 보류 → 응답으로 보정값·오프셋 설정 → 레이아웃 표시 → 30분마다·30분 뒤 포커스 복귀 시 재동기(TM-R9~R11)
- 대안: 재동기 실패는 직전 값 유지
- 예외: 첫 동기 실패는 오류 배너, 형식 오류는 502 `malformed-response`·`RangeError`
- 결과: 화면의 지금·오늘이 서버 기준

### TM-UC5 화면의 지금·오늘·시각 표시
- 행위자: 화면(모든 feature)
- 기본 흐름: `useToday()`로 지금·오늘·올해를 얻고(TM-R12), 서버가 준 시각 문자열은 `formatDateTime`·`formatStamp`·`formatDate`·`formatRelativeTime`으로 보인다(TM-R14·R15)
- 예외: 읽을 수 없는 문자열은 원문 그대로
- 결과: 브라우저 시간대와 무관한 표시

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| TM-001 | 로그인한 사용자는 서버 업무 시각과 업무 날짜를 받는다 | TM-R7, TM-R4, TM-UC1 | backend | `web/test_server_time_routes.py::test_logged_in_user_gets_server_time`<br>`application/test_get_server_time.py::test_returns_local_now_and_business_date` |
| TM-002 | 세 역할 모두 서버 시각을 읽을 수 있다 | TM-R7, TM-UC1 | backend | `web/test_server_time_routes.py::test_every_role_can_read_server_time` |
| TM-003 | 로그인하지 않으면 서버 시각은 401이다 | TM-R7, TM-UC1 | backend | `web/test_server_time_routes.py::test_anonymous_request_is_unauthorized` |
| TM-004 | UTC로는 전날이어도 업무 날짜는 서버 시간대의 다음 날이다 | TM-R4, TM-R7, TM-UC1 | backend | `web/test_server_time_routes.py::test_today_is_next_day_when_utc_is_still_previous_day` |
| TM-005 | 서버 시간대가 UTC면 오늘은 UTC 날짜이고 오프셋은 0이다 | TM-R2, TM-R7, TM-UC1 | backend | `application/test_get_server_time.py::test_today_follows_utc_process_timezone` |
| TM-006 | 서버 시계를 한 번만 읽어 자정 직전에도 now와 today가 같은 날이다 | TM-R7, TM-UC1 | backend | `application/test_get_server_time.py::test_reads_the_clock_once_so_now_and_today_agree`<br>`application/test_get_server_time.py::test_today_is_the_date_part_of_now` |
| TM-007 | openapi에 서버 시각 응답 모양과 401이 문서화된다 | TM-R7 | backend | `web/test_server_time_routes.py::test_openapi_documents_the_time_route_with_a_date_time_now` |
| TM-008 | 업무 시각은 같은 순간을 서버 시간대 오프셋으로 바꾸고 마이크로초를 지킨다 | TM-R3, TM-UC2 | backend | `domain/test_business_time.py::test_utc_moment_becomes_local_offset_same_instant`<br>`domain/test_business_time.py::test_microseconds_are_kept`<br>`domain/test_business_time.py::test_other_offset_input_is_converted_to_local` |
| TM-009 | 서머타임 시간대에서는 시각마다 그 순간의 오프셋을 쓴다 | TM-R2, TM-R3, TM-UC2 | backend | `domain/test_business_time.py::test_offset_follows_process_timezone`<br>`domain/test_business_time.py::test_offset_is_chosen_per_moment_across_daylight_saving` |
| TM-010 | 시간대 없는 시각은 업무 시각 계산에서 거절된다 | TM-R1, TM-UC2 | backend | `domain/test_business_time.py::test_naive_moment_is_rejected` |
| TM-011 | 업무 날짜는 서버 시간대 00:00에 바뀐다(서울 UTC 14:59/15:00 경계) | TM-R4, TM-UC2 | backend | `domain/test_business_date.py::TestLocalTimeZoneIsSeoul::test_utc_1459_is_still_the_same_day`<br>`domain/test_business_date.py::TestLocalTimeZoneIsSeoul::test_utc_1500_exactly_is_midnight_of_the_next_day`<br>`domain/test_business_date.py::TestLocalTimeZoneIsUtc::test_utc_midnight_starts_the_next_day`<br>`domain/test_business_date.py::test_a_zone_behind_utc_uses_its_own_calendar` |
| TM-012 | 다른 오프셋 시각도 서버 시간대로 먼저 바꾼 뒤 날짜를 정하고 연말을 넘긴다 | TM-R4, TM-UC2 | backend | `domain/test_business_date.py::TestLocalTimeZoneIsSeoul::test_another_offset_is_converted_to_local_time_first`<br>`domain/test_business_date.py::TestLocalTimeZoneIsSeoul::test_year_end_rolls_over`<br>`domain/test_business_date.py::TestLocalTimeZoneIsUtc::test_a_seoul_offset_time_is_converted_to_utc_first`<br>`domain/test_business_time.py::test_business_date_equals_the_date_of_business_time` |
| TM-013 | 업무일 시작은 서버 시간대 00:00이고 그 앞 순간은 전날이다 | TM-R5, TM-UC2 | backend | `domain/test_start_of_business_day.py::test_start_of_business_day_is_local_midnight_in_seoul`<br>`domain/test_start_of_business_day.py::test_start_of_business_day_is_local_midnight_in_utc`<br>`domain/test_start_of_business_day.py::test_the_start_moment_belongs_to_its_own_business_date_and_the_one_before_to_the_previous` |
| TM-014 | n개월 전은 같은 날이고 없는 날은 그 달 말일이다 | TM-R6, TM-UC2 | backend | `domain/test_updated_period.py::test_months_before_keeps_the_day_or_falls_back_to_month_end` |
| TM-015 | n개월 뒤는 같은 날이고 없는 날은 그 달 말일이다 | TM-R6, TM-UC2 | backend | `domain/test_updated_period.py::test_months_after_keeps_the_day_or_falls_back_to_month_end` |
| TM-016 | 개월 이동의 경계: 0개월·12개월·윤일·음수 | TM-R6, TM-UC2 | backend | `domain/test_updated_period.py::test_months_before_zero_is_the_same_day`<br>`domain/test_updated_period.py::test_months_after_twelve_lands_on_the_same_day_a_year_later`<br>`domain/test_updated_period.py::test_negative_months_are_a_programming_error` |
| TM-017 | 응답 시각은 서버 오프셋 문자열로 나가고 다시 읽으면 같은 순간이다 | TM-R8, TM-UC3 | backend | `web/test_server_datetime.py::test_serializes_with_server_offset`<br>`web/test_server_datetime.py::test_json_string_output_also_carries_the_server_offset`<br>`web/test_server_datetime.py::test_fastapi_response_carries_the_server_offset` |
| TM-018 | 응답 시각 오프셋은 서버 프로세스 시간대를 따른다 | TM-R8, TM-R2, TM-UC3 | backend | `web/test_server_datetime.py::test_offset_follows_the_process_timezone` |
| TM-019 | 비어 있는 시각은 null이고 openapi 스키마는 일반 date-time과 같다 | TM-R8, TM-UC3 | backend | `web/test_server_datetime.py::test_none_stays_null`<br>`web/test_server_datetime.py::test_openapi_schema_is_unchanged` |
| TM-020 | 응답 스키마에 맨 datetime 필드가 남지 않는다 | TM-R8, TM-UC3 | backend | `web/test_schema_datetime_guard.py::test_no_bare_datetime_field_in_web_schemas`<br>`web/test_schema_datetime_guard.py::test_the_guard_detects_a_bare_datetime` |
| TM-021 | Deal 상세·목록·Dashboard 응답의 시각은 서버 오프셋이고 순간은 서버 시계와 같다 | TM-R8, TM-UC3 | backend | `web/test_response_time_offsets.py::test_deal_detail_timestamps_carry_server_offset`, `web/test_response_time_offsets.py::test_deal_list_timestamps_carry_server_offset`, `web/test_response_time_offsets.py::test_dashboard_as_of_carries_server_offset`, `web/test_deal_response_risk.py` <br><br><br> |
| TM-022 | 앱 시계는 왕복 지연의 절반을 보정해 서버 시각에 맞춘다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > syncs to the server time at the round-trip midpoint` |
| TM-023 | 브라우저 날짜·시간대가 달라도 앱 시계는 서버 오프셋과 경과 시간만 따른다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > follows the browser elapsed time, not the browser date`<br>`gateway/clock.test.ts > keeps the server offset even when the browser zone differs` |
| TM-024 | 서버 now의 Z와 마이크로초를 읽는다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > treats Z as a zero offset`<br>`gateway/clock.test.ts > accepts the microsecond fraction the server sends` |
| TM-025 | 동기 사이 자정을 지나면 앱 시계 날짜가 바뀐다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > rolls over the date as browser time passes without resync` |
| TM-026 | 다시 동기하면 보정값과 오프셋이 새 값으로 바뀐다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > replaces the skew on resync`<br>`gateway/clock.test.ts > takes the offset of the latest sync` |
| TM-027 | 동기가 실패하거나 서버 now에 오프셋이 없으면 직전 동기가 유지된다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > keeps the previous sync when fetch fails`<br>`gateway/clock.test.ts > keeps the previous sync when the server time has no offset` |
| TM-028 | 첫 동기 전 앱 시계는 브라우저 시각이다 | TM-R9, TM-UC4 | frontend | `gateway/clock.test.ts > uses the browser clock only before the first sync`<br>`gateway/index.test.ts > app clock is the server clock that falls back to the browser clock before the first sync` |
| TM-029 | HTTP 게이트웨이는 GET /api/v1/time의 now·today를 그대로 돌려준다 | TM-R10, TM-UC4 | frontend | `gateway/http/time.test.ts > maps now and today from GET /api/v1/time`<br>`gateway/index.test.ts > app clock follows the server time after a sync through the app gateway`<br>`gateway/contract/time.contract.ts > returns the server now with an offset and its date to %s`<br>`test/fake/gateway/time.test.ts > answers the clock now and its calendar date to %s`<br>`gateway/http/wiring.test.ts` |
| TM-030 | 형식이 틀린 서버 시각 응답은 502 malformed-response다 | TM-R10, TM-UC4 | frontend | `gateway/http/time.test.ts > rejects a malformed body with %s` |
| TM-031 | 로그인하지 않았으면 서버 시각을 요청하지 않고 로그인 화면으로 간다 | TM-R11, TM-R10, TM-UC4 | frontend | `features/auth/RequireAuth.test.tsx > does not request the server time before login is confirmed`<br>`data/time.test.tsx > does not request before it is enabled`<br>`data/time.test.tsx > starts requesting when enabled turns true`<br>`gateway/http/time.test.ts > passes a 401 through as an ApiError` |
| TM-032 | 첫 동기 응답 전에는 레이아웃 대신 불러오는 중을 보인다 | TM-R11, TM-UC4 | frontend | `features/auth/RequireAuth.test.tsx > holds the layout until the server time arrives`<br>`features/auth/RequireAuth.test.tsx > requests the server time once for a logged-in session` |
| TM-033 | 첫 동기가 실패하면 레이아웃 없이 오류 배너를 보이고 재시도하지 않는다 | TM-R11, TM-UC4 | frontend | `features/auth/RequireAuth.test.tsx > shows an error and no layout when the first sync fails`<br>`data/time.test.tsx > reports a rejected sync as an ApiError without retrying` |
| TM-034 | 30분마다 다시 동기한다 | TM-R11, TM-UC4 | frontend | `data/time.test.tsx > syncs again every 30 minutes` |
| TM-035 | 30분이 지난 뒤 창에 포커스가 돌아오면 다시 동기한다 | TM-R11, TM-UC4 | frontend | `data/time.test.tsx > syncs again when the window regains focus after the data went stale` |
| TM-036 | 재동기가 실패해도 직전 값과 화면이 유지된다 | TM-R11, TM-UC4 | frontend | `data/time.test.tsx > keeps the previous data when a later sync fails`<br>`features/auth/RequireAuth.test.tsx > keeps the layout when a later resync fails` |
| TM-037 | useToday는 앱 시계의 지금·오늘·연도를 렌더마다 읽는다 | TM-R12, TM-UC5 | frontend | `data/today.test.tsx > returns the mock clock now, its calendar date and year`<br>`data/today.test.tsx > follows the clock when it is changed between renders` |
| TM-038 | 앱 소스는 gateway/clock.ts 밖에서 브라우저 시계·시간대를 읽지 않는다 | TM-R13, TM-UC5 | frontend | `test/architecture.test.ts > app sources do not read the browser clock or time zone outside gateway/clock.ts`<br>`test/architecture.test.ts > keeps the only browser clock read inside gateway/clock.ts` |
| TM-039 | 날짜·시각 표시는 문자열 오프셋의 벽시계 그대로다 | TM-R14, TM-UC5 | frontend | `shared/format.test.ts > shows the wall time of the given offset`<br>`shared/format.test.ts > keeps the offset wall time as YYYY-MM-DD HH:mm` |
| TM-040 | 읽을 수 없는 시각 문자열은 원문 그대로 보인다 | TM-R14, TM-UC5 | frontend | `shared/format.test.ts > formatDateTime returns %j without throwing`<br>`shared/format.test.ts > formatStamp returns %j without throwing` |
| TM-041 | 상대 시각은 분·시간·일 전으로, 30일 이상은 날짜로 보인다 | TM-R15, TM-UC5 | frontend | `shared/format.test.ts > shows minutes, hours and days ago`<br>`shared/format.test.ts > falls back to a date after 30 days` |
| TM-042 | 다음 날 계산은 달력만 쓴다 | TM-R16, TM-UC5 | frontend | `shared/format.test.ts > returns the following date across month and year ends`<br>`shared/format.test.ts > handles leap days` |

### TM-001 로그인한 사용자는 서버 업무 시각과 업무 날짜를 받는다
- Given 서버 시간대가 Asia/Seoul이고 서버 시계가 `2026-12-31T15:30:00Z`이며 user로 로그인했다
- When `GET /api/v1/time`을 부른다
- Then 200이고 본문 키는 `now`·`today` 둘뿐이며 `now`는 `"2027-01-01T00:30:00+09:00"`(순간은 서버 시계와 같음), `today`는 `"2027-01-01"`이다

### TM-002 세 역할 모두 서버 시각을 읽을 수 있다
- Given admin, sales, user 중 하나로 로그인했다
- When `GET /api/v1/time`을 부른다
- Then 세 역할 모두 200이다

### TM-003 로그인하지 않으면 서버 시각은 401이다
- Given 로그인하지 않았다(또는 로그아웃했다)
- When `GET /api/v1/time`을 부른다
- Then 401이고 `Content-Type`이 `application/problem+json`이며 `type`이 `unauthenticated`로 끝난다

### TM-004 UTC로는 전날이어도 업무 날짜는 서버 시간대의 다음 날이다
- Given 서버 시간대가 Asia/Seoul이고 서버 시계가 `2026-10-22T15:00:00Z`이며 sales로 로그인했다
- When `GET /api/v1/time`을 부른다
- Then `today`는 `"2026-10-23"`이고 `now`의 날짜 부분과 같다

### TM-005 서버 시간대가 UTC면 오늘은 UTC 날짜이고 오프셋은 0이다
- Given 서버 시간대가 UTC이고 서버 시계가 `2026-12-31T15:30:00Z`다
- When 서버 시각을 조회한다(`GetServerTime`)
- Then `now`의 오프셋은 0이고 `today`는 2026-12-31이다

### TM-006 서버 시계를 한 번만 읽어 자정 직전에도 now와 today가 같은 날이다
- Given 서버 시간대가 Asia/Seoul이고 읽을 때마다 1초씩 흐르는 서버 시계가 `2026-10-22T14:59:59Z`(로컬 23:59:59)다
- When 서버 시각을 조회한다
- Then `now`는 `2026-10-22T23:59:59+09:00`이고 `today`는 2026-10-22다(다음 날로 섞이지 않는다)

### TM-007 openapi에 서버 시각 응답 모양과 401이 문서화된다
- When 앱의 openapi 문서를 만든다
- Then `GET /api/v1/time`의 200 응답 스키마는 속성·required가 `now`·`today`이고 `now`는 `format: date-time`, `today`는 `format: date`이며 401 응답이 있다

### TM-008 업무 시각은 같은 순간을 서버 시간대 오프셋으로 바꾸고 마이크로초를 지킨다
- Given 서버 시간대가 Asia/Seoul이다
- When `2026-10-22T15:30:00Z`와 `2026-10-22T15:30:01.123456Z`의 업무 시각을 구한다
- Then 각각 `2026-10-23T00:30:00+09:00`, `2026-10-23T00:30:01.123456+09:00`이고 순간은 입력과 같으며 오프셋은 +9시간이다

### TM-009 서머타임 시간대에서는 시각마다 그 순간의 오프셋을 쓴다
- Given 서버 시간대가 America/New_York이다
- When `2026-07-01T12:00Z`와 `2026-12-01T12:00Z`, `2026-10-22T12:00Z`의 업무 시각을 구한다
- Then 오프셋은 각각 −04:00, −05:00이고 `2026-10-22T12:00Z`는 `2026-10-22T08:00:00-04:00`이다

### TM-010 시간대 없는 시각은 업무 시각 계산에서 거절된다
- When 시간대 정보가 없는 `2026-10-22 15:30`의 업무 시각을 구한다
- Then `InvalidValueError`가 난다

### TM-011 업무 날짜는 서버 시간대 00:00에 바뀐다
- Given 서버 시간대가 Asia/Seoul이다
- When `2026-10-15T14:59Z`, `2026-10-15T15:00Z`, `2026-10-15T15:30Z`의 업무 날짜를 구한다
- Then 각각 2026-10-15, 2026-10-16, 2026-10-16이다. 서버 시간대가 UTC면 `2026-10-15T15:30Z`·`23:59Z`는 2026-10-15, `2026-10-16T00:00Z`는 2026-10-16이고, America/New_York이면 `2026-10-16T02:00Z`는 2026-10-15다

### TM-012 다른 오프셋 시각도 서버 시간대로 먼저 바꾼 뒤 날짜를 정하고 연말을 넘긴다
- Given 서버 시간대가 Asia/Seoul이다
- When `2026-10-15T20:00-04:00`과 `2026-12-31T15:00Z`의 업무 날짜를 구한다
- Then 각각 2026-10-16, 2027-01-01이고, 업무 날짜는 항상 업무 시각의 날짜 부분과 같다. 서버 시간대가 UTC면 `2026-10-16T08:00+09:00`은 2026-10-15다

### TM-013 업무일 시작은 서버 시간대 00:00이고 그 앞 순간은 전날이다
- Given 서버 시간대가 Asia/Seoul이다
- When 2026-10-16의 업무일 시작을 구한다
- Then `2026-10-15T15:00Z`(시간대 있음)이고, 그 순간의 업무 날짜는 2026-10-16, 1마이크로초 전은 2026-10-15이며, 2026-10-17의 시작과는 24시간 차이다. 서버 시간대가 UTC면 `2026-10-16T00:00Z`다

### TM-014 n개월 전은 같은 날이고 없는 날은 그 달 말일이다
- When 2026-10-21의 1·2·3·6개월 전, 2026-03-31·2024-03-31의 1개월 전, 2026-08-31의 6개월 전, 2026-05-31의 3개월 전, 2026-12-31의 6개월 전, 2026-10-31의 1개월 전, 2026-01-15의 3개월 전을 구한다
- Then 2026-09-21·2026-08-21·2026-07-21·2026-04-21, 2026-02-28·2024-02-29, 2026-02-28, 2026-02-28, 2026-06-30, 2026-09-30, 2025-10-15다

### TM-015 n개월 뒤는 같은 날이고 없는 날은 그 달 말일이다
- When 2026-10-22의 1·2개월 뒤, 2026-01-31·2024-01-31의 1개월 뒤, 2026-12-31의 2개월 뒤, 2026-03-31의 1개월 뒤, 2026-07-31의 2개월 뒤, 2026-11-15의 2개월 뒤, 2026-12-01의 1개월 뒤를 구한다
- Then 2026-11-22·2026-12-22, 2026-02-28·2024-02-29, 2027-02-28, 2026-04-30, 2026-09-30, 2027-01-15, 2027-01-01이다

### TM-016 개월 이동의 경계: 0개월·12개월·윤일·음수
- When 0개월·12개월 전/뒤와 2024-02-29의 12개월 전/뒤, −1개월을 구한다
- Then 0개월은 같은 날, 12개월은 1년 전/뒤 같은 날(2024-02-29 → 2023-02-28 / 2025-02-28)이고, −1개월은 전/뒤 모두 `ValueError`("months")다

### TM-017 응답 시각은 서버 오프셋 문자열로 나가고 다시 읽으면 같은 순간이다
- Given 서버 시간대가 Asia/Seoul이고 응답 모델의 시각 필드 값이 `2026-10-22T15:30:00Z`다
- When 모델을 JSON으로 만든다(`model_dump(mode="json")`, `model_dump_json()`, FastAPI 응답)
- Then 세 방식 모두 `"2026-10-23T00:30:00+09:00"`이고, 다시 읽은 순간은 원래 값과 같으며, `2026-10-22T20:00-04:00` 입력은 `"2026-10-23T09:00:00+09:00"`, 마이크로초 입력은 `"…00:30:01.123456+09:00"`이다

### TM-018 응답 시각 오프셋은 서버 프로세스 시간대를 따른다
- Given 서버 시간대가 America/New_York이다
- When 시각 필드 값이 `2026-10-22T15:30:00Z`인 모델을 JSON으로 만든다
- Then `"2026-10-22T11:30:00-04:00"`이다

### TM-019 비어 있는 시각은 null이고 openapi 스키마는 일반 date-time과 같다
- Given 필수 시각 필드와 선택(`| None`) 시각 필드가 있는 응답 모델이다
- When 선택 필드를 비워 직렬화하고 openapi 문서를 만든다
- Then 선택 필드는 `null`이고, 필수 필드 스키마는 `{"type":"string","format":"date-time"}`, 선택 필드는 `anyOf [date-time, null]`이며 필수 필드만 required에 있다

### TM-020 응답 스키마에 맨 datetime 필드가 남지 않는다
- Given `app.web.schemas` 패키지의 모든 pydantic 모델(Deal 행·상세·사용자 응답 포함)이다
- When 각 모델의 필드 타입(Optional·list·Union 안쪽 포함)을 검사한다
- Then `datetime` 필드는 모두 `ServerDateTime`이다(검사기는 맨 `datetime`을 찾아내고 `ServerDateTime`·`ServerDateTime | None`은 통과시킨다)

### TM-021 Deal 상세·목록·Dashboard 응답의 시각은 서버 오프셋이고 순간은 서버 시계와 같다
- Given 서버 시간대가 Asia/Seoul이고 서버 시계가 `2026-12-31T15:00:00Z`로 고정되었으며 그 시각에 Deal 하나가 등록되었다
- When Deal 상세, Deal 목록, Dashboard 요약(`year=2026`)을 조회한다
- Then 상세의 `created_at`·`updated_at`, 목록 행의 `created_at`, Dashboard의 `as_of`가 모두 `+09:00`으로 끝나고 순간은 서버 시계와 같다

### TM-022 앱 시계는 왕복 지연의 절반을 보정해 서버 시각에 맞춘다
- Given 브라우저 시각이 1000ms에서 요청하고 3000ms에 응답을 받으며 서버 `now`가 `2026-12-31T23:59:00+09:00`이다
- When 앱 시계를 동기한다
- Then 동기는 받은 서버 시각을 그대로 돌려주고, 응답 시점(3000ms)의 `now()`는 `2026-12-31T23:59:01+09:00`이다

### TM-023 브라우저 날짜·시간대가 달라도 앱 시계는 서버 오프셋과 경과 시간만 따른다
- Given 브라우저 시각이 2000-01-01이고 서버 `now`가 `2026-10-23T09:00:00+09:00`으로 동기되었다
- When 브라우저 시각이 90초 흐른 뒤 `now()`를 읽는다
- Then `2026-10-23T09:01:30+09:00`이다. 서버 `now`가 `…-05:00`이면 `now()`도 `-05:00`으로 끝나고, 다른 시계 인스턴스의 오프셋은 바뀌지 않는다

### TM-024 서버 now의 Z와 마이크로초를 읽는다
- When 서버 `now`가 `2026-10-23T00:30:00Z` 또는 `2026-10-23T09:30:00.123456+09:00`일 때 동기한다
- Then 앞의 경우 `now()`의 순간은 `2026-10-23T00:30:00Z`이고 오프셋은 0이며, 뒤의 경우 `now()`는 `2026-10-23T09:30:00`으로 시작하고 `+09:00`으로 끝난다

### TM-025 동기 사이 자정을 지나면 앱 시계 날짜가 바뀐다
- Given 서버 `now` `2026-12-31T23:59:00+09:00`으로 동기되었다(응답 시점 `23:59:01`)
- When 다시 동기하지 않고 브라우저 시각이 60초 흐른 뒤 `now()`를 읽는다
- Then `2027-01-01T00:00:01+09:00`이다

### TM-026 다시 동기하면 보정값과 오프셋이 새 값으로 바뀐다
- Given 서버 `now` `2026-10-23T09:00:00+09:00`으로 동기되었고 브라우저 시각이 600초 흘렀다
- When 서버 `now` `2026-10-23T09:12:00+09:00`으로 다시 동기한다
- Then `now()`는 `2026-10-23T09:12:00+09:00`이고, 이어서 `…-04:00`으로 동기하면 `now()`는 `-04:00`으로 끝난다

### TM-027 동기가 실패하거나 서버 now에 오프셋이 없으면 직전 동기가 유지된다
- Given `2026-10-23T09:00:00+09:00`으로 동기되었고 브라우저 시각이 흘렀다
- When 동기 요청이 네트워크 오류로 실패하거나, 서버 `now`가 `2026-10-23T09:00:00`·`not-a-date`·빈 문자열·`2026-10-23`인 응답으로 동기한다
- Then 실패는 그 오류로, 형식 오류는 `RangeError`로 reject되고 `now()`는 직전 동기 기준의 시각(예: 10초 뒤 `2026-10-23T09:00:10+09:00`)이다

### TM-028 첫 동기 전 앱 시계는 브라우저 시각이다
- Given 아직 동기하지 않은 앱 시계다
- When `now()`를 읽는다
- Then 순간이 브라우저 시각과 같은 오프셋 ISO 문자열이다(앱 gateway의 `clock`도 같고 `syncWith`를 가진다)

### TM-029 HTTP 게이트웨이는 GET /api/v1/time의 now·today를 그대로 돌려준다
- Given 서버가 `{now: "2026-10-23T09:30:00.123456+09:00", today: "2026-10-23"}`(또는 `now`가 `…Z`)를 준다
- When HTTP 게이트웨이(`createHttpGateway().time` 포함)로 서버 시각을 읽는다
- Then `GET /api/v1/time`을 한 번 부르고 같은 `{now, today}`를 돌려주며 `Z`도 그대로다. 앱 gateway로 동기하면 앱 시계가 그 서버 시각과 오프셋을 따른다. Fake 게이트웨이도 세 역할에 같은 모양(`today == now[:10]`)을 준다

### TM-030 형식이 틀린 서버 시각 응답은 502 malformed-response다
- Given 서버 응답이 오프셋 없는 `now`, 시각이 아닌 `now`, `YYYY/MM/DD`나 시각이 붙은 `today`, `today` 없음, `now` 없음 중 하나다
- When HTTP 게이트웨이로 서버 시각을 읽는다
- Then `ApiError` 502 `malformed-response`로 reject된다

### TM-031 로그인하지 않았으면 서버 시각을 요청하지 않고 로그인 화면으로 간다
- Given 로그인하지 않았다
- When `/deals`를 연다
- Then `/login`으로 이동하고 서버 시각 요청은 0회다. 동기 훅이 꺼져(`enabled=false`) 있으면 요청하지 않고 켜지는 순간 1회 요청한다. 세션 없이 요청하면 게이트웨이는 401 `ApiError`를 넘긴다

### TM-032 첫 동기 응답 전에는 레이아웃 대신 불러오는 중을 보인다
- Given 로그인했고 서버 시각 응답이 아직 오지 않았다
- When `/deals`를 연다
- Then "불러오는 중…"이 보이고 주 메뉴는 없으며, 응답이 오면 주 메뉴가 보인다. 이 진입에서 서버 시각 요청은 1회다

### TM-033 첫 동기가 실패하면 레이아웃 없이 오류 배너를 보이고 재시도하지 않는다
- Given 로그인했고 서버 시각 요청이 500 "서버 시각을 불러오지 못했습니다."로 실패한다
- When `/deals`를 연다
- Then `role="alert"`에 "서버 시각을 불러오지 못했습니다."가 보이고 주 메뉴는 없으며 요청은 1회뿐이다

### TM-034 30분마다 다시 동기한다
- Given 첫 동기가 끝났다
- When 29분이 지나고, 이어서 2분이 더 지난다
- Then 29분 시점까지 동기는 1회, 31분 시점에 2회다

### TM-035 30분이 지난 뒤 창에 포커스가 돌아오면 다시 동기한다
- Given 첫 동기가 끝났다
- When 31분 뒤 창이 포커스를 잃었다가 되찾는다
- Then 동기가 한 번 더 일어난다(합 2회)

### TM-036 재동기가 실패해도 직전 값과 화면이 유지된다
- Given 첫 동기가 끝나 레이아웃이 보인다
- When 재동기 요청이 503 또는 네트워크 오류로 실패한다
- Then 훅의 데이터는 첫 동기 값 그대로이고 주 메뉴가 계속 보이며 오류 배너는 없다

### TM-037 useToday는 앱 시계의 지금·오늘·연도를 렌더마다 읽는다
- Given 앱 시계가 `2030-12-31T23:30:00+09:00`이다
- When `useToday()`를 렌더한다
- Then `{now: "2030-12-31T23:30:00+09:00", today: "2030-12-31", year: 2030}`이고, 시계를 `2028-05-06T10:00:00+09:00`으로 바꾼 뒤 다시 렌더하면 `today` 2028-05-06, `year` 2028이다

### TM-038 앱 소스는 gateway/clock.ts 밖에서 브라우저 시계·시간대를 읽지 않는다
- Given 테스트·테스트 도우미·계약 스위트를 뺀 앱 소스 파일(100개 초과, `gateway/clock.ts` 포함)이다
- When 주석을 지운 코드에서 TM-R13의 금지 패턴을 찾는다
- Then `gateway/clock.ts` 밖에서는 하나도 없고 `gateway/clock.ts`는 `Date.now`를 읽으며, 검사기는 금지 예시 문장마다 위반을 찾아낸다

### TM-039 날짜·시각 표시는 문자열 오프셋의 벽시계 그대로다
- When `formatDateTime`·`formatStamp`·`formatDate`에 오프셋이 다른 시각 문자열을 넣는다
- Then `formatDateTime('2026-10-23T00:30:00-05:00')` = `2026. 10. 23. 오전 12:30`, `('2026-10-23T15:04:59+09:00')` = `2026. 10. 23. 오후 3:04`, `('2030-06-14T16:00:00Z')` = `2030. 6. 14. 오후 4:00`, `('2026-10-23T08:00:00+09:00')` = `2026. 10. 23. 오전 8:00`(UTC 날짜로 옮기지 않음), 소수 초·`+05:30`도 벽시계 그대로이고, `formatStamp('2026-10-23T15:04:59.123456+09:00')` = `2026-10-23 15:04`, `('2026-10-23T23:30:00-05:00')` = `2026-10-23 23:30`, `formatDate`는 `2026-10-15` 그대로·`2026-10-23T23:30:00-05:00` → `2026-10-23`이다

### TM-040 읽을 수 없는 시각 문자열은 원문 그대로 보인다
- When `formatDateTime`·`formatStamp`에 `''`, `'abc'`, `'2026-10-23'`, `'2026-10-23T09:30:00'`, `'2026-10-23 09:30'`, `'2026-13-45T99:99:99+09:00'`을 넣는다
- Then 예외 없이 입력 문자열 그대로다

### TM-041 상대 시각은 분·시간·일 전으로, 30일 이상은 날짜로 보인다
- Given `now`가 `2026-10-15T12:00:00+09:00`이다
- When 20초 전, 30분 전, 3시간 전, 3일 전, 2026-08-01, 1시간 뒤 시각의 상대 시각을 구한다
- Then `방금 전`, `30분 전`, `3시간 전`, `3일 전`, `2026-08-01`, `방금 전`이고, 30일 이상은 문자열에 적힌 날짜(`2026-08-01T23:30:00-05:00` → `2026-08-01`)다

### TM-042 다음 날 계산은 달력만 쓴다
- When `nextDay`에 2026-06-30, 2026-12-31, 2026-06-01, 2028-02-28, 2028-02-29, 2026-02-28을 넣는다
- Then 2026-07-01, 2027-01-01, 2026-06-02, 2028-02-29, 2028-03-01, 2026-03-01이다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성: 구현된 서버 시간·업무 날짜 동작을 정본 명세로 옮김. 규칙 TM-R1~R16, use case TM-UC1~UC5, BDD 케이스 TM-001~TM-042 | TM-001~TM-042(신규) |
| 2026-11-11 | UI 문서 작성에 따라 날짜 입력 칸 참조를 UI 규칙 번호로 교체(UI-R1~R11). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): `status_changed_at`·`last_updated_at`이 날짜(`*_on`)가 되어 TM-021의 응답 시각 목록에서 뺐다 | 변경 TM-021 |
