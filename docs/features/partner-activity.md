# 파트너 Activity   (feature 코드: PA, 상태: 확정(2026-11-11 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-11). 근거는 작업 트리의 코드(`backend/src/app/web/routers/partner_meetings.py`, `app/web/schemas/partner_meeting.py`, `app/web/error_handlers.py`의 `_invalid_meeting`, `app/application/partner_meeting/{register_partner_meetings,update_partner_meeting,delete_partner_meeting,list_partner_meetings,checker,inputs,dto}.py`, `app/application/ports/partner_meeting_repository.py`, `app/domain/partner_meeting/{entities,values,company,policy,errors}.py`, `app/infra/db/{partner_meeting_repository,models_meeting}.py`, 기준선 마이그레이션의 `partner_meetings`, `frontend/src/features/partner-activity/*`, `data/partnerMeetings.ts`, `gateway/http/{partnerMeetings,mappers/partnerMeeting}.ts`, `shared/model/permissions.ts`의 `canEditMeeting`, `test/fake/gateway/partnerMeetings.ts`)와 `docs/user-guide.html` 16장이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 배경은 하네스 이력 2026-10-28(파트너 Activity 도입)·2026-11-03(Deal 연결 제거, 미팅 날짜 기간 선택)입니다. Deal 연결은 폐지되었습니다. 테스트 Fake가 서버와 다르던 곳은 2026-11-11 사용자 결정으로 Fake를 서버 동작에 맞추기로 했고(PA-R42), 이 문서의 기대 결과는 **서버 동작 기준**입니다. 유스케이스의 빈 목록 거절은 HTTP로 닿지 않는 내부 방어로 남깁니다(PA-R4). 공통 부품은 UI 규칙 번호로, 기간 선택 부품은 NA-R26으로 가리킵니다. 결정 목록은 계획(`artifacts/10-analysis/pa-plan.md`)에 있습니다.

## 1. 개요

- 목적: 영업 담당자가 파트너 회사와 가진 미팅을 회사·날짜·내용으로 여러 건 한 번에 기록하고, 모든 사용자가 모든 파트너의 미팅 기록을 항목별로 검색·정렬해 본다. 미팅은 Deal 없이 여러 주제로 진행되므로 Deal과 연결하지 않는다.
- 사용자(역할): 조회는 admin·sales·user 모두, 입력은 sales·admin, 수정·삭제는 작성자 본인(sales)과 admin.
- 범위
  - 화면 `/partner-activities`: 목록(항목별 검색·열 정렬·기본 미팅 날짜 최신순·10건씩 무한 스크롤), 미팅 날짜 기간 선택, 일괄 입력 팝업, 수정 팝업, 삭제 확인
  - API `GET·POST /partner-meetings`, `PUT·DELETE /partner-meetings/{meeting_id}`(일괄 등록 1~50건 원자적, 위반은 422 `errors[].location`)
  - 테이블 `partner_meetings`의 컬럼·제약(SC가 넘긴 테이블별 스키마), 작성자 사용자 연결의 결과(퇴사 처리 뒤에도 기록에 남음)
- 범위 밖(다른 feature)
  - 파트너 연락처 등록·수정·삭제와 회사 목록 `GET /contacts/companies`의 규칙(대표 표기·정렬) → CT(CT-R2, CT-R14). PA는 그 목록을 쓴다
  - 연락처 수정 뒤 미팅 조회 캐시 무효화 → CT(CT-R20)
  - Deal 삭제와 삭제 영향 응답의 키 목록, Deal 삭제 뒤 미팅이 남는다는 Deal 쪽 규칙 → DD(DD-R22, DD-R25, DD-057, DD-113)
  - 기간 프리셋 API `GET /deals/updated-periods`의 날짜 계산 → DL(DL-R17). Deal 목록 '최종 업데이트' 선택 동작 → DL(DL-R25)
  - 사용자 퇴사·삭제 판정, `UserRef`, 사용자 선택지 `GET /user-options` → US(US-R12, US-R17, US-R20)
  - 업무 날짜·앱 시계·응답 시각 오프셋 → TM(TM-R4, TM-R8, TM-R12)
  - 공통 권한 판정 순서·업무 쓰기 가드·CSRF·Problem 형식·id 형식·NUL·화면 가드·상단 메뉴·오류 문구·게이트웨이 오류 변환 → PL(PL-R2, PL-R4~R6, PL-R9~R13, PL-R15, PL-R16, PL-R33, PL-R34, PL-R36, PL-R37, PL-R39)
  - 대리 키·FK 공통 규칙·id 할당 → SC(SC-R11, SC-R15, SC-R17, SC-R19)
  - 공통 입력·표시 컴포넌트의 자체 동작 → UI: `DateInput`(UI-R1~R11), `ComboBox`(UI-R18~R21), `Modal`(UI-R25~R28), `ConfirmDialog`(UI-R29), `useInfiniteScroll`(UI-R31), `SortableHeader`(UI-R32)
  - 기간 선택 부품 `PeriodField`·`periodChoice`의 자체 동작 → NA(NA-R26)
- 관련 화면·메뉴: 상단 메뉴 "파트너 Activity"(PL-R34), 가드 RequireAuth(PL-R33). 화면은 `React.lazy` 청크다.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 미팅 기록 | 파트너 회사와 가진 미팅 한 건(회사명·미팅 날짜·내용·작성자) |
| 파트너 회사 목록 | 지금 등록된 파트너 연락처의 회사명 목록(CT-R14, 대소문자 무시로 묶은 대표 표기) |
| 대표 표기 | 회사 목록에 보이는 그 회사의 글자(가장 먼저 등록된 연락처의 표기, CT-R14) |
| 일괄 등록 | 한 요청의 1~50건을 한 트랜잭션으로 저장하는 것. 하나라도 틀리면 아무것도 저장하지 않는다 |
| 위치(location) | 위반이 난 요청 안의 자리. 등록은 `["items", <i>, <필드>]`, 수정은 `[<필드>]` |
| 작성자 | 기록을 등록한 사용자. 바뀌지 않는다 |
| 기간 프리셋 | 최근 2주·1·2·3·6개월(서버 업무 날짜 기준, DL-R17) |

### 2.2 데이터 모델

테이블 `partner_meetings`(대리 키는 SC-R11, FK 공통은 SC-R15·SC-R17, id 할당은 SC-R19의 `partner_meeting`)

| 컬럼 | 형식 | 제약·뜻 |
| --- | --- | --- |
| `id` | BIGINT identity PK | 앱이 미리 받은 id(`uow.ids`)로 넣는다 |
| `partner_company` | varchar(200) NOT NULL | 저장 시점의 대표 표기 텍스트. CHECK `ck_partner_meetings_company_valid`: 빈 문자열이 아니고 공백 문자(`\s`)가 하나도 없다(CT-R2 회사명 규칙과 같음). 연락처를 가리키지 않는다 |
| `meeting_date` | date NOT NULL | 미팅 날짜(1900-01-01~2999-12-31은 앱 검증, DB는 모든 날짜를 받음) |
| `content` | text NOT NULL | 미팅 내용(길이 제한 없음). CHECK `ck_partner_meetings_content_not_blank`: 공백이 아닌 글자가 하나 이상(`content ~ '\S'`) |
| `created_by_user_id` | BIGINT NOT NULL FK `users.id` ON DELETE RESTRICT(`fk_partner_meetings_created_by_user_id_users`) | 작성자 |
| `created_at`, `updated_at` | timestamptz NOT NULL | 등록 시각, 마지막 변경 시각 |

- 인덱스: `pk_partner_meetings`(유일한 UNIQUE), `ix_partner_meetings_meeting_date_id`(`meeting_date, id`), `ix_partner_meetings_created_by_user_id`. 회사명 인덱스는 없다. 같은 회사·날짜·내용의 행이 여러 개여도 된다.
- Deal과의 연결 컬럼·FK·인덱스(`deal_id`, `fk_partner_meetings_deal_id_deals`, `ix_partner_meetings_deal_id`)는 없다.
- 도메인: `PartnerMeeting`(엔티티, `record`로 만들고 `revise`로 바꿈 — 값이 모두 같으면 바꾸지 않고 False), `MeetingContent`(값 객체), `check_meeting_date`, `resolve_company`, `can_edit_meeting`, 오류 `MeetingInputError`(위반 `MeetingIssue{location, message}` 모음), `PartnerMeetingNotFoundError`, `PartnerMeetingEditForbiddenError`, `PartnerMeetingDeleteForbiddenError`.
- 조회 조건 `PartnerMeetingQuery{partner?, content?, date_from?, date_to?, author_user_id?, sort, order, offset, limit}`, 정렬 키 `PartnerMeetingSort`(`meeting_date`·`partner`·`content`·`author`).

### 2.3 비즈니스 규칙

모델·스키마
- **PA-R1** 미팅 기록은 파트너 회사명(텍스트)·미팅 날짜·내용·작성자·등록 시각·변경 시각으로 이루어지고 Deal·연락처 행을 가리키지 않는다. 작성자와 등록 시각은 바뀌지 않는다. 삭제는 물리 삭제다.
- **PA-R2** 테이블 `partner_meetings`의 컬럼·형식·NULL 여부·CHECK·FK·인덱스는 2.2 표와 같다(head 스키마). 원시 INSERT로 빈 회사명·공백이 든 회사명(`"한빛 파트너스"`, `" 한빛"`, `"한빛\t"`)·201자 회사명·빈 내용(`""`, `"   "`, `"\n\t \n"`)·없는 작성자는 그 제약 이름으로 거절되고, 1900-01-01·2999-12-31·아주 긴 여러 줄 내용은 저장된다. 미팅을 쓴 사용자 행은 DB에서 직접 지울 수 없다(FK RESTRICT). Deal 행을 지워도 미팅 행은 그대로다.

일괄 등록 (`POST /partner-meetings`)
- **PA-R3** 업무 쓰기 경로다(PL-R2): sales·admin만 등록한다. user는 본문·회사 검사보다 먼저 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(PL-R6)이고 아무것도 저장되지 않는다. 미인증은 401(PL-R5), CSRF 헤더가 없으면 403 `csrf`(PL-R9).
- **PA-R4** 요청 형식: 본문은 정확히 `{items: [...]}`이고 `items`는 1~50개, 각 항목은 정확히 `partner_company`(문자열, 200자 이하), `meeting_date`(`YYYY-MM-DD` 날짜), `content`(문자열) 세 키다. 다음은 모두 422 `request-validation`(PL-R12)이고 아무것도 저장되지 않는다: `items` 누락·배열 아님·0개·51개 이상, 항목의 키 누락(오류 `loc`에 항목 번호가 들어간다, 예: `["body", "items", 0, "content"]`), 형식이 틀린 값(날짜가 아닌 글자, 문자열이 아닌 값, 201자 이상 회사명), 모르는 키(예전 `deal_code` 포함). (유스케이스도 빈 목록을 "입력한 미팅이 없습니다."로 거절한다. HTTP에서는 형식 검사가 먼저라 닿지 않는 내부 방어이고 그대로 둔다 — 2026-11-11 결정, 케이스 없이 BDD 밖 단위 테스트로 확인.)
- **PA-R5** 파트너 회사: 입력 글자가 **지금** 파트너 회사 목록(CT-R14)의 한 회사와 대소문자 무시로 같아야 한다(앞뒤 공백 정리·부분 일치 없음). 저장값은 목록의 대표 표기다(`hanbitco` → `HanbitCo`). 그 회사의 연락처가 하나라도 있으면 되고 Deal 연결 여부는 보지 않는다. 그 회사의 파트너 연락처가 모두 지워졌으면 목록에 없다. 없으면 위반 "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."(위치 `partner_company`). 회사 목록은 요청당 한 번 읽는다.
- **PA-R6** 미팅 날짜: 시각 없는 날짜이고 1900-01-01~2999-12-31(양끝 포함)이다. 미래 날짜도 받는다. 밖이면 위반 "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(위치 `meeting_date`).
- **PA-R7** 미팅 내용: 앞뒤 공백(줄바꿈·탭 포함)을 지워 저장하고 가운데 줄바꿈은 그대로 둔다. 지운 뒤 비면 위반 "미팅 내용을 입력하세요.", NUL 문자가 있으면 "미팅 내용에는 NUL 문자를 쓸 수 없습니다"(위치 `content`, PL-R16). 길이 제한은 없다(이모지·여러 줄 포함 그대로 저장).
- **PA-R8** 일괄 판정: 모든 항목을 행 순서대로, 한 행 안에서는 회사 → 날짜 → 내용 순으로 **모두** 검사해 위반을 모은다. 하나라도 있으면 422 `invalid-value`, `detail` = 첫 위반 문구, `errors` = `[{location: ["items", <i>, <필드>], message}]`(검사 순서대로)이고 아무것도 저장하지 않는다(원자적). 위치에 `deal_code`는 나오지 않는다.
- **PA-R9** 성공하면 201(본문 있음, `Location` 헤더 없음) `{items: [...]}`이고 항목은 입력 순서다. 각 기록의 작성자는 요청자, `created_at` = `updated_at` = 요청 처리 때의 서버 시각(오프셋 표기, TM-R8), id는 항목마다 새로 받는다(SC-R19). 같은 회사·날짜·내용을 여러 번 저장해도 된다.
- **PA-R10** 응답 항목(`PartnerMeetingResponse`)은 정확히 `{id, partner_company, meeting_date, content, author, created_at, updated_at}`이고 `author`는 `UserRef`(US-R12)다. Deal 관련 필드(`deal` 등)는 없다. 목록·등록·수정 응답이 같은 항목 모양이다.

목록 (`GET /partner-meetings`)
- **PA-R11** 로그인한 모든 역할이 읽는다(업무 조회). 미인증 401. 쿼리 키는 `partner`(200자 이하), `content`(100자 이하), `date_from`, `date_to`(날짜), `author_user_id`(쿼리 id, PL-R15), `sort`(`meeting_date`|`partner`|`content`|`author`, 기본 `meeting_date`), `order`(`asc`|`desc`, 기본 `desc`), `offset`(0 이상, 기본 0), `limit`(1~200, 기본 10)뿐이다. 모르는 키(예전 `deal`·`deal_code` 포함), `sort=deal` 같은 모르는 값, 형식·범위 위반(`limit=0`·`201`, `offset=-1`, 날짜 아님, 길이 초과, id 형식)은 422 `request-validation`이다.
- **PA-R12** 조건은 모두 AND다. `partner`는 **저장된 회사명**, `content`는 내용의 대소문자 무시 부분 일치이고 `%`·`_`·`\`는 글자 그대로다. 텍스트 조건은 앞뒤 공백을 지우고 비면(공백뿐 포함) 조건이 없다. 날짜 범위는 양끝을 포함하고 한쪽만 줘도 된다. `date_from`이 `date_to`보다 늦으면 422 `invalid-value` "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.", 범위 날짜가 1900-01-01~2999-12-31 밖이면 422 `invalid-value` "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다". 텍스트 조건의 NUL은 422 `invalid-value`(PL-R16). `author_user_id`는 그 사용자가 작성한 기록만(퇴사자 포함)이고 없는 id는 0건이다.
- **PA-R13** 정렬: `meeting_date`는 (미팅 날짜, id)를 방향대로 정렬한다(기본 내림차순 = 최신 날짜 먼저, 같은 날은 나중에 등록한 것 먼저). `partner`·`content`·`author`는 주 키 `lower(값)`를 코드 포인트 순(`COLLATE "C"`)으로 방향대로 정렬하고, 같으면 **방향과 무관하게** 미팅 날짜 내림차순 → id 내림차순이다. `author`의 값은 작성자 표시 이름(비었으면 아이디)이고 퇴사자도 포함한다.
- **PA-R14** 응답은 `{items, total, offset, limit}`이다. `items`는 정렬 뒤 `offset`부터 `limit`개, `total`은 페이지와 무관하게 조건에 맞는 전체 건수, `offset`·`limit`은 받은 값이다. 맞는 기록이 없으면 `items` `[]`, `total` 0이다.

수정 (`PUT /partner-meetings/{meeting_id}`)
- **PA-R15** 업무 쓰기 경로다. 본문은 등록 항목과 같은 세 키(PA-R4 항목 규칙, 모르는 키 `deal_code`·누락·형식 오류는 422 `request-validation`)이고 **전체 교체**다. 판정 순서(PL-R4): 401 → CSRF 403 → 역할 403(user, PL-R6) → 422 `request-validation`(경로 id 형식 PL-R15 포함) → 404 `not-found` "미팅 기록을 찾을 수 없습니다." → 403 `forbidden` "본인 미팅 기록 또는 admin만 수정할 수 있습니다."(PA-R16) → 422 `invalid-value`(PA-R18).
- **PA-R16** 수정·삭제 권한(도메인): admin은 모든 기록, sales는 자기가 작성한 기록만, user는 자기 기록이라도 불가(경로에서는 PL-R6이 먼저 막는다).
- **PA-R17** 회사 판정: 입력 회사가 저장된 회사명과 대소문자 무시로 같으면 회사 목록을 다시 확인하지 않고 **저장된 표기를 그대로 유지**한다(그래서 연락처 회사명이 바뀌거나 그 회사 연락처가 없어진 뒤에도 날짜·내용을 고칠 수 있다). 다르면 PA-R5로 확인하고 새 회사의 대표 표기를 저장한다.
- **PA-R18** 수정 위반은 PA-R5~R7과 같은 문구로 모두 모아 422 `invalid-value`, `errors[].location`은 `["partner_company"]`·`["meeting_date"]`·`["content"]`처럼 필드만이다(`items` 접두 없음). 아무것도 저장하지 않는다.
- **PA-R19** 성공하면 200 `PartnerMeetingResponse`. 정리한 값(대표 표기·내용 앞뒤 공백 제거)이 저장값과 모두 같으면 저장하지 않고 `updated_at`도 그대로다. 하나라도 바뀌면 바뀐 값과 `updated_at` = 서버 시각을 저장한다. 작성자·`created_at`은 바뀌지 않는다.

삭제 (`DELETE /partner-meetings/{meeting_id}`)
- **PA-R20** 업무 쓰기 경로다. 판정 순서: 401 → CSRF 403 → 역할 403(user) → 422 `request-validation`(id 형식) → 404 `not-found` "미팅 기록을 찾을 수 없습니다." → 403 `forbidden` "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."(PA-R16). 성공하면 204(본문 없음)이고 그 기록만 물리 삭제된다(다시 지우면 404).

다른 데이터와의 관계
- **PA-R21** 미팅은 Deal과 무관하다: Deal 입력·연결·선택지 경로가 없고(`GET /partner-meetings/deal-options`는 없는 경로 — PL-R13), Deal을 지워도 미팅 기록은 남으며, Deal 삭제 영향 응답(DD-R22)에 미팅 건수가 없다. openapi에도 미팅 API의 Deal 관련 스키마·파라미터·정렬 값이 없다.
- **PA-R22** 작성자 연결: `partner_meetings.created_by_user_id`는 사용자 연결(US 2.2, SC-R17)이다. 그래서 미팅을 쓴 사용자를 삭제하면 퇴사 처리되고(US-R17, 결과 `resigned`) 기록은 남는다: 목록의 `author`는 `resigned: true`, `label` "<이름>(퇴사)"이고 `author_user_id` 조건으로 계속 찾으며, 퇴사자 포함 사용자 선택지(US-R20 `include_resigned=true`)에 그 사용자가 있다. 퇴사·삭제 판정 규칙은 US-R17이 가지고, 미팅 때문에 퇴사되는 결과 케이스(PA-045)는 PA가 가진다.
- **PA-R23** 기록의 회사명은 저장 시점 텍스트다: 연락처 회사명을 바꿔도(CT-R9) 기존 기록은 옛 이름으로 남고 옛 이름으로 검색된다. 바꾼 뒤 새 기록은 새 이름만 받고 옛 이름은 PA-R5 위반이다.

API 문서
- **PA-R24** openapi: 경로는 `/api/v1/partner-meetings`(GET·POST)와 `/api/v1/partner-meetings/{meeting_id}`(PUT·DELETE) 두 개이고 모두 태그 `partner-meetings`다. 성공 코드 GET 200·POST 201·PUT 200·DELETE 204, 모든 작업에 401, 오류 문서는 POST 422·PUT 404·422·DELETE 404, GET은 422만이고 읽기에는 403을 문서화하지 않는다. `meeting_id`는 1~2^53−1 정수, 목록 파라미터는 PA-R11의 9개(`sort` enum 4값, `order` enum, 텍스트 최대 길이 200·100), 등록 본문은 `MeetingItemRequest` 1~50개 배열, 수정 본문은 `MeetingItemRequest` 하나(속성 정확히 3개, 회사 최대 200자), 목록 응답은 `PartnerMeetingResponse`의 counted page, 등록 응답은 `{items}`, 작성자는 공용 `UserRef` 스키마다. Deal 선택지 경로·스키마는 없다.

화면 (frontend, `/partner-activities`)
- **PA-R25** 화면 틀: 제목(h1) "파트너 Activity", `canWrite`(admin·sales, PL-R36)면 오른쪽 위 버튼 "미팅 내용 입력"(PA-R33). 그 아래 검색 폼(PA-R30), 성공 알림(닫기 가능), 목록 오류 배너(PL-R37), 표(PA-R26). 처음 읽는 동안 "불러오는 중…". 응답이 오고 `total`이 0이면 "기록된 미팅이 없습니다."(조건이 있어도 같은 문구). 다음 쪽이 있으면 "더 보기" 버튼, 다 읽었고 1건 이상이면 "모두 불러왔습니다 (전체 N건)"(PA-R28).
- **PA-R26** 표(이름 "파트너 미팅 기록"): 열은 파트너, 미팅 날짜, 미팅 내용, 작성자 순서이고(모두 정렬 머리글, PA-R32), `canWrite`면 맨 끝에 정렬 없는 "관리" 열이 있다. 칸: 파트너 = 저장된 회사명, 미팅 날짜 = `YYYY-MM-DD` 그대로, 미팅 내용 = 줄바꿈 그대로, 작성자 = 이름(퇴사자는 "<이름>(퇴사)"). 관리 칸에는 PA-R29가 참인 행에만 "수정"·"삭제" 버튼이 있고 아니면 비어 있다. user에게는 관리 열·입력 버튼이 없다. Deal 열·Deal 링크는 없다. 행 순서는 서버 순서다.
- **PA-R27** URL이 조건의 정본이다. 키: `partner`, `from`, `to`, `content`, `author`, `sort`, `order`. 읽을 때: `partner`·`content`는 값 그대로(요청에는 앞뒤 공백을 지운 값, 비면 보내지 않음), `from`·`to`는 실제 달력 날짜(`YYYY-MM-DD`)만, `author`는 1~2^53−1 정수 id만, `sort`는 `meetingDate`·`partner`·`content`·`author`만(그 밖, 예전 `sort=deal`이면 기본 정렬이고 `order`도 버려 미팅 날짜 내림차순), `order`는 `asc`일 때만 오름차순. 예전 `deal` 키는 읽지 않는다. 쓸 때(검색·정렬): 값이 있는 조건만, 정렬은 기본(`meetingDate`)이 아닐 때만 `sort`, 오름차순일 때만 `order=asc`를 쓴다. 기본 화면의 주소에는 쿼리가 없다. 서버 요청은 언제나 정렬·방향을 보낸다(PA-R41).
- **PA-R28** 목록 데이터: 한 쪽 10건씩 `offset`을 늘려 읽고(서버 `total` 기준으로 다음 쪽 판단) 쪽을 이어 붙인다. 목록 끝의 감시 요소가 화면 아래 200px 안에 들어오면 다음 쪽을 읽고, "더 보기" 버튼으로도 읽는다(읽는 동안 비활성). 다 읽으면 더 읽지 않는다. 쪽 사이에 다른 사용자의 등록으로 경계가 밀려 같은 기록이 다시 와도 id로 한 번만 보인다. 조건·정렬이 바뀌면 첫 쪽부터 다시 읽는다.
- **PA-R29** 화면의 대상별 판단 `canEditMeeting(viewer, authorId)`: admin이면 참, sales이고 viewer id가 작성자 id면 참, 그 밖(user 포함) 거짓. 정본 판정은 서버다(PA-R16).
- **PA-R30** 검색 폼(`search` 역할, 이름 "미팅 기록 검색"): 칸 순서 파트너(텍스트, 최대 200자), 미팅 날짜(PA-R31), 미팅 내용(텍스트, 최대 100자), 작성자(퇴사자 포함 사용자 선택, US-R20)와 버튼 "검색"·"초기화". Deal 칸은 없다. 칸 값은 "검색" 버튼 또는 텍스트 칸의 Enter로 한꺼번에 URL에 반영한다(정렬은 유지, 첫 쪽부터). "초기화"는 모든 칸을 비우고 주소의 쿼리를 모두 지운다(정렬 포함). 주소가 바깥에서 실제로 바뀌면(뒤로 가기·초기화) 칸이 따라가고, 정렬만 바뀐 경우에는 아직 검색하지 않은 입력을 지우지 않는다. 날짜 글자가 틀리면(덜 쳤거나 없는 날짜) 검색하지 않고 그 날짜 칸에 문구를 보인다. 시작이 끝보다 늦은 범위는 그대로 검색해 서버 문구(PA-R12)를 목록 오류 배너로 보인다.
- **PA-R31** 미팅 날짜 기간 선택(Deals '최종 업데이트'와 같은 선택지, DL-R25 참고): 선택 상자 "미팅 날짜"는 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정(7개)이고 서버 프리셋(DL-R17)에 없는 키는 비활성이다. 프리셋을 읽지 못하면 폼 안에 오류 배너를 보이고 프리셋이 모두 비활성이다. **적용은 "검색"을 누를 때다**(Deals처럼 즉시 바꾸지 않는다):
  - 프리셋을 고르고 검색하면 그 순간 프리셋을 서버에 다시 물어(캐시 안 씀) 받은 `from`·`to` **날짜**를 URL·요청에 쓴다(프리셋 이름은 쓰지 않는다). 다시 묻기가 실패하면 폼에 오류 배너를 보이고 URL·조건을 바꾸지 않는다. 다시 받은 프리셋에 그 키가 없으면 날짜 조건 없이 나머지 조건으로 검색한다. 늦게 온 이전 응답은 버린다.
  - "직접 지정"을 고르면 시작·끝 날짜 칸(`DateInput`, UI-R1~R11)이 보인다. 한쪽만 넣어도 검색되고 양끝을 포함한다. 직접 지정으로 검색한 날짜가 마침 프리셋 범위와 같아도 직접 지정과 날짜 칸이 그대로 유지되고, 다른 조건만 바꿔 다시 검색해도 친 날짜를 그대로 보낸다(프리셋으로 다시 풀지 않는다). 프리셋으로 바꾸면 날짜 칸이 사라진다.
  - "전체"는 날짜 조건을 지운다(검색하면 URL에서 `from`·`to`가 빠진다). "초기화"하면 전체로 돌아간다.
  - 표시: 사용자가 이번에 고른 값, 아니면 직접 지정으로 검색한 상태면 직접 지정, 아니면 URL 날짜가 **오늘의** 프리셋과 정확히 같으면 그 프리셋, 날짜가 없으면 전체, 그 밖(한쪽만 있음, 전날 저장한 프리셋 날짜 포함)은 직접 지정과 그 날짜. 프리셋을 읽지 못해도 URL 날짜로 검색한다. 예전 주소(날짜 칸 두 개 시절 `from`·`to`)도 같은 결과로 열린다.
- **PA-R32** 정렬 머리글: 파트너·미팅 날짜·미팅 내용·작성자 네 열이 정렬 버튼이고 정렬 중인 열에만 방향 표시가 있다. 정렬이 없는 주소는 미팅 날짜 내림차순으로 표시한다. 지금 정렬하지 않는 열을 누르면 오름차순으로 시작하고 같은 열을 다시 누르면 방향을 바꾼다(미팅 날짜 열: 내림차순 → 오름차순 → 내림차순). 정렬을 바꾸면 조건은 유지하고 첫 10건부터 다시 읽는다. URL의 정렬로 머리글 표시를 복원한다.
- **PA-R33** 입력 팝업(제목 "미팅 내용 입력", 넓은 모달): 열면 빈 행 하나이고 첫 칸(파트너)에 포커스, 미팅 날짜 기본값은 앱 시계의 오늘(TM-R12)이다. 각 행은 `group` "미팅 <번호>"이고 칸 순서는 파트너 → 미팅 날짜 → 미팅 내용 → "행 삭제" 버튼이다(Deal 칸 없음). "행 추가"는 오늘 날짜의 빈 행을 아래에 더하고, "행 삭제"는 그 행을 지우고 번호를 다시 매긴다(행이 하나면 비활성). 행은 50개까지이고 51번째를 더하려 하면 행을 더하지 않고 "한 번에 50건까지 입력할 수 있습니다."(`alert`)를 보인다. 아래에 "취소"·"저장" 버튼(저장 중 비활성).
- **PA-R34** 파트너 칸(콤보박스 "파트너"): 선택지는 파트너 회사 목록(CT-R14)이고 친 글자로 좁혀진다(포커스만으로는 열리지 않음). 목록에서 고르면 그 회사가 행의 회사가 되고 포커스가 미팅 날짜 칸으로 간다. 목록 글자와 같은 글자(대소문자·앞뒤 공백 무시)를 다 치고 Enter를 누르면 고른 것으로 보고 날짜 칸으로 넘어가며, 같은 항목이 없으면 칸 아래 "목록에서 선택하세요."를 보인다(글자를 고치거나 목록에서 고르면 사라짐). Enter 없이 친 글자만으로는 고른 것이 아니다. 고른 뒤 글자를 고치면 고른 회사가 풀린다. 행마다 따로다.
- **PA-R35** 칸 이동 키: 목록이 닫힌(또는 활성 항목 없는) 파트너 칸의 Enter는 PA-R34대로, 칸이 비어 있고 이미 고른 회사가 있으면 날짜 칸으로 간다. 목록이 열려 있으면 Enter는 활성 항목을 고른다(콤보박스 동작). 날짜 칸에 `yyyymmdd`를 치고 Enter, 또는 달력에서 고르면 내용 칸으로 간다. 덜 쳤거나 없는 날짜에서 Enter는 날짜 칸에 머물고 날짜 칸 문구를 보인다. 내용 칸: Shift+Enter는 줄바꿈, 한글 조합을 확정하는 Enter는 무시, 그 밖의 Enter는 ① 그 행에 빠진 칸(파트너 미선택 → 틀리거나 빈 날짜 → 빈 내용 순)이 있으면 첫 빠진 칸으로 ② 다음 행이 있으면 다음 행 파트너로 ③ 마지막 행이면 오늘 날짜의 새 행을 더하고 그 파트너로 간다(50행이면 PA-R33 안내만).
- **PA-R36** 저장: 완전히 빈 행(파트너 글자·고른 회사·내용이 모두 빈 행, 날짜는 보지 않음)은 건너뛴다. 모두 빈 행이면 요청하지 않고 "입력한 미팅이 없습니다."(`alert`). 빈 행이 아닌 행은 칸별로 검사해 빠진 칸에 "파트너를 선택하세요."(목록에서 고르지 않음)·"미팅 날짜를 입력하세요."(빈 날짜)·날짜 칸 문구(틀린 날짜, UI-R7)·"미팅 내용을 입력하세요."(공백뿐)를 보이고 요청하지 않으며 첫 오류(행 순서 → 칸 순서)로 포커스한다. 칸을 고치면 그 칸 문구가 사라진다. 내용 칸 문구는 textarea의 접근성 설명(`aria-describedby`)이고 `aria-invalid`가 켜진다. 통과하면 빈 행을 뺀 행들을 화면 순서대로 한 요청(행마다 `partnerCompany`·`meetingDate`·`content` 세 값만)으로 보낸다. 성공하면 팝업을 닫고 알림 "미팅 N건을 저장했습니다."(N = 보낸 행 수)를 보이며 목록을 처음부터 다시 읽는다(PA-R40, 새 기록은 기본 정렬에서 맨 위, 작성자는 로그인 사용자, 줄바꿈 유지). 다시 열면 빈 행 하나다. 실패하면 아무것도 저장되지 않았으므로 입력을 유지하고, 서버가 위치를 준 위반(PA-R8)은 그 요청 항목이 화면의 몇 번째 행이었는지로 옮겨 그 행·칸 아래에 서버 문구를 보이고(칸마다 첫 문구, 놓을 수 없는 위치·`deal_code`는 무시) 첫 오류로 포커스한다. 위치가 없는 실패(403 등)는 팝업 안 오류 배너다.
- **PA-R37** 입력 팝업 닫기: "취소"·Esc·닫기 버튼은 모든 행이 빈 행이면(기본 날짜는 입력으로 보지 않음) 바로 닫는다. 입력이 있으면 확인 대화상자(제목 "입력 취소", 문구 "입력한 내용을 버릴까요?", 위험 버튼 "버리기", 취소 버튼 "계속 입력")를 띄운다. "계속 입력"은 입력을 그대로 두고, "버리기"는 두 대화상자를 닫고 입력을 버린다.
- **PA-R38** 수정 팝업(제목 "미팅 수정"): 관리 열의 "수정"으로 열고, 저장값으로 채운 행 하나(PA-R34·R35의 칸 동작, "행 추가"·"행 삭제" 없음)이며 내용 칸에 포커스가 간다. 내용 칸의 Enter(Shift·한글 조합 제외)는 "저장" 버튼으로 포커스를 옮긴다. 저장은 PA-R36과 같은 칸 검사(빈 행도 검사)를 하고 통과하면 세 값만 `PUT`한다. 다른 파트너를 골라도 날짜·내용은 유지된다. 성공하면 팝업을 닫고 목록을 처음부터 다시 읽어 새 위치에 보인다(알림 없음). 실패하면 위치가 있는 위반(PA-R18)은 그 칸 아래, 그 밖(404 "미팅 기록을 찾을 수 없습니다." 등)은 팝업 안 오류 배너다. "취소"·Esc는 저장 없이 닫는다(확인 없음). 저장된 회사 그대로면 연락처 회사명이 그 사이 바뀌었어도 저장된다(PA-R17).
- **PA-R39** 삭제: 관리 열의 "삭제"는 확인 대화상자(제목 "미팅 기록 삭제", 문구 "이 미팅 기록을 삭제할까요?", 위험 버튼 "삭제")를 띄운다. 취소하면 요청 없이 닫고 기록은 남는다. 확인하면 삭제 중 버튼이 바쁨 상태이고 다른 행은 계속 보이며, 성공하면 닫고 목록을 처음부터 다시 읽는다(그 기록이 사라지고 다음 기록이 보임). 실패하면(이미 지워져 404 등) 대화상자 안에 서버 문구를 보인다.
- **PA-R40** 갱신: 등록·수정·삭제가 성공하면 미팅 목록 쿼리를 초기화해 지금 조건의 첫 쪽을 **한 번만** 다시 요청한다(불러 둔 다른 쪽을 다시 받지 않음). 연락처 수정 뒤 미팅 조회 무효화는 CT-R20이다.
- **PA-R41** 게이트웨이(`gateway/http/partnerMeetings.ts`): `list(query, offset, limit)`는 값이 있는 조건만 snake_case 쿼리(`partner`, `content`, `date_from`, `date_to`, `author_user_id`)로 보내고 `sort`(`meetingDate` → `meeting_date`, 나머지 같음)·`order`·`offset`·`limit`은 늘 보낸다. Deal 조건은 보내지 않는다. 응답 항목은 `{id, partnerCompany, meetingDate, content, author(UserRef 변환 — 퇴사자는 status `resigned`), createdAt, updatedAt}`이고 쪽은 `{items, total, offset, limit}`. `create(items)`는 `POST {items: [{partner_company, meeting_date, content}]}`(정확히 세 키)이고 생성 항목을 순서대로 돌려준다. `update(id, input)`은 `PUT /partner-meetings/{id}`에 같은 세 키, `remove(id)`는 `DELETE`이며 204를 성공으로 받는다. Deal 선택지 호출은 없다. 실패는 `ApiError`(PL-R39)이고, 422 `invalid-value`의 `errors[{location, message}]`는 `problem.itemErrors`로 옮기고 `errors`를 뺀 본문으로 문구를 만든다(그래서 문구에 필드 접미사가 붙지 않음). 422 `request-validation`은 PL-R37 문구(필드 설명 포함)를 그대로 쓴다.
- **PA-R42** Fake 게이트웨이(`test/fake/gateway/partnerMeetings.ts`)와 backend Fake 저장소(`tests/fakes/partner_meetings.py`)는 서버와 같은 규칙을 따른다: 읽기는 모든 역할, 쓰기는 sales·admin(user 403), 수정·삭제는 작성자·admin, 회사는 대표 표기 텍스트, 일괄 위반은 위치와 함께 모두 모으고 아무것도 저장하지 않음, Deal과 무관, 정렬·동률 규칙 PA-R13. 서버와 다르던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-11 결정)**:
  - 요청 형식 오류: 등록 목록 0개·51개 이상, 형식이 틀린 미팅 날짜(실제 `YYYY-MM-DD` 날짜가 아님 — 예 `2027-02-30`, `20270310`, `abc`. 형식 판정이 범위 판정보다 먼저), 201자 이상 회사명은 행 위반이 아니라 요청 전체의 422 "요청 형식이 올바르지 않습니다"(서버 `request-validation`, Fake `requestValidation()`, `itemErrors` 없음)이고 아무것도 저장하지 않는다(PA-R4). 그래서 판정 순서는 401 → 403(역할) → 422 요청 형식 → 404 → 403(작성자) → 422 입력 위반이다(PA-R15). 예전 Fake 자체 문구("입력한 미팅이 없습니다."·"한 번에 50건까지 입력할 수 있습니다."·"날짜 형식이 올바르지 않습니다.")는 Fake 응답에 쓰지 않는다(화면 안내 PA-R33·PA-R36은 그대로).
  - 내용 NUL: 등록·수정 모두 위치 `content`의 "미팅 내용에는 NUL 문자를 쓸 수 없습니다"를 다른 위반과 함께 모은다(PA-R7, PA-R8, PA-R18).
  - 목록 조건: 서버와 같은 순서로 텍스트 조건 NUL → 날짜 범위 → 날짜 역전을 본다. 날짜가 1900-01-01~2999-12-31 밖이면 422 "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(역전 판정보다 먼저), `partner` 200자·`content` 100자 초과는 422 요청 형식 문구, 텍스트 조건 NUL은 422 입력 위반(PA-R11, PA-R12).
  - 케이스 기대 결과는 서버 기준이다(PA-091, PA-093).
  - 받아들인 차이(2026-11-12 리뷰 반영, 화면 경로에서는 나오지 않는 입력): 서버 스키마는 `"86400"`(유닉스 초)·`"2027-03-10T00:00:00"`(자정 일시)도 날짜로 받지만 Fake는 `YYYY-MM-DD`만 받는다. 길이 판정은 서버가 코드 포인트, Fake가 JS `.length`라 이모지 같은 서로게이트 문자에서 경계 결과가 다를 수 있다. 케이스는 이 경계를 다루지 않는다.

### 2.4 상태와 전이

미팅 기록: 없음 → (등록, PA-R9) → 있음 → (수정, 값이 바뀔 때만 `updated_at` 변경, PA-R19) → 있음 → (삭제, PA-R20) → 없음. 작성자가 퇴사해도 기록은 "있음"이다(PA-R22).

입력 팝업 행: 빈 행 ⇄ 입력 중(빈 행이 아님) → 저장 대상. 저장은 전부 성공 또는 전부 실패다.

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /partner-meetings`, 화면 `/partner-activities` 조회 | 401 / `/login`으로 | 가능 | 가능 | 가능 |
| `POST /partner-meetings`(일괄 등록), "미팅 내용 입력" 버튼 | 401 | 403 읽기 전용(버튼 없음) | 가능 | 가능 |
| `PUT /partner-meetings/{meeting_id}`, "수정" 버튼 | 401 | 403 읽기 전용(관리 열 없음) | 본인이 작성한 기록만(남의 기록 403) | 모든 기록 |
| `DELETE /partner-meetings/{meeting_id}`, "삭제" 버튼 | 401 | 403 읽기 전용(관리 열 없음) | 본인이 작성한 기록만(남의 기록 403) | 모든 기록 |

GET은 업무 조회, POST·PUT·DELETE는 업무 쓰기(PL-R2)다. 쓰기는 CSRF 헤더가 필요하다(PL-R9).

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/partner-meetings` | query `partner?`(≤200), `content?`(≤100), `date_from?`, `date_to?`, `author_user_id?`, `sort?`(`meeting_date`·`partner`·`content`·`author`), `order?`(`asc`·`desc`), `offset?`(≥0), `limit?`(1~200, 기본 10) | 200 `{items: PartnerMeetingResponse[], total, offset, limit}` | 401, 422 `request-validation`·`invalid-value` |
| POST `/partner-meetings` | `{items: MeetingItemRequest[1..50]}` | 201 `{items: PartnerMeetingResponse[]}`(입력 순서, `Location` 없음) | 401, 403 `csrf`·`forbidden`, 422 `request-validation`·`invalid-value`(+`errors[{location, message}]`) |
| PUT `/partner-meetings/{meeting_id}` | `MeetingItemRequest` | 200 `PartnerMeetingResponse` | 401, 403 `csrf`·`forbidden`, 404 `not-found`, 422 `request-validation`·`invalid-value`(+`errors`) |
| DELETE `/partner-meetings/{meeting_id}` | — | 204 | 401, 403 `csrf`·`forbidden`, 404 `not-found`, 422 `request-validation` |

- `MeetingItemRequest` = `{partner_company: string(≤200), meeting_date: date, content: string}`(추가 키 금지).
- `PartnerMeetingResponse` = `{id: int, partner_company: string, meeting_date: date, content: string, author: UserRef, created_at: datetime, updated_at: datetime}`.
- 422 `invalid-value`(입력 위반) 본문: Problem(PL-R10) + `errors: [{location: (string|int)[], message: string}]`, `detail` = 첫 위반 문구.

### 2.7 화면 동작

PA-R25~PA-R42.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 등록 목록 0개·51개 이상, 키 누락·모르는 키(`deal_code`)·형식 오류, 목록 쿼리 형식·모르는 키·`sort=deal`, 경로 id 형식 | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12) |
| 등록되지 않은 파트너 회사 | 422 `invalid-value`(위치 `partner_company`) | 등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요. |
| 미팅 날짜 범위 밖(입력·검색) | 422 `invalid-value`(입력은 위치 `meeting_date`) | 미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다 |
| 빈 미팅 내용 | 422 `invalid-value`(위치 `content`) | 미팅 내용을 입력하세요. |
| 미팅 내용 NUL | 422 `invalid-value`(위치 `content`) | 미팅 내용에는 NUL 문자를 쓸 수 없습니다 |
| 검색 날짜 범위 역전 | 422 `invalid-value` | 미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다. |
| 없는 기록(수정·삭제) | 404 `not-found` | 미팅 기록을 찾을 수 없습니다. |
| 남의 기록 수정(sales) | 403 `forbidden` | 본인 미팅 기록 또는 admin만 수정할 수 있습니다. |
| 남의 기록 삭제(sales) | 403 `forbidden` | 본인 미팅 기록 또는 admin만 삭제할 수 있습니다. |
| user의 쓰기 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정)(PL-R6) |
| 미인증 | 401 `unauthenticated` | 로그인이 필요합니다(PL-R5) |
| (내부) 유스케이스에 빈 목록 | `InvalidValueError` | 입력한 미팅이 없습니다. |

화면 문구: "파트너 Activity", "미팅 내용 입력", "미팅 기록 검색", "파트너", "미팅 날짜", "미팅 내용", "작성자", "관리", "검색", "초기화", "수정", "삭제", "불러오는 중…", "기록된 미팅이 없습니다.", "더 보기", "모두 불러왔습니다 (전체 N건)", "행 추가", "행 삭제", "미팅 <n>", "한 번에 50건까지 입력할 수 있습니다.", "입력한 미팅이 없습니다.", "파트너를 선택하세요.", "미팅 날짜를 입력하세요.", "미팅 내용을 입력하세요.", "목록에서 선택하세요.", "미팅 N건을 저장했습니다.", "입력 취소", "입력한 내용을 버릴까요?", "버리기", "계속 입력", "미팅 수정", "미팅 기록 삭제", "이 미팅 기록을 삭제할까요?". 기간 선택지 문구는 DL-R25와 같다. 서버 문구 표시는 PL-R37.

## 3. Business use case

### PA-UC1 미팅 일괄 입력
- 행위자: sales, admin
- 사전 조건: 로그인, 파트너 연락처(CT)가 하나 이상 등록되어 있음
- 기본 흐름: "미팅 내용 입력"을 누른다 → 행마다 파트너를 목록에서 고르고(PA-R34) 날짜(기본 오늘)와 내용을 쓴다 → 내용 칸 Enter로 다음 행을 만든다(PA-R35) → "저장" → 서버가 모든 행을 검사해 한 번에 저장한다(PA-R3~R9) → 알림과 함께 목록 맨 위에 보인다(PA-R36)
- 대안: 행 추가·삭제, 빈 행은 건너뜀, 미래 날짜, 대소문자가 다른 회사명은 대표 표기로 저장
- 예외: 빠진 칸은 요청 없이 칸 문구, 서버 위반은 해당 행·칸 문구와 함께 아무것도 저장 안 됨, 50행 초과 안내, 입력이 있을 때 닫으면 버릴지 확인(PA-R37), user는 버튼이 없고 API는 403
- 결과: 입력 순서대로 작성자 = 나인 기록 N건

### PA-UC2 미팅 기록 찾기
- 행위자: 로그인한 모든 역할
- 사전 조건: 로그인, 메뉴 "파트너 Activity"
- 기본 흐름: 미팅 날짜 최신순 10건이 보인다 → 아래로 내리면 10건씩 더 붙는다(PA-R28) → 파트너·미팅 날짜(기간 선택)·내용·작성자로 검색하고(PA-R30, R31) 열 머리글로 정렬한다(PA-R32)
- 대안: 주소를 공유해 같은 조건·정렬로 연다, 초기화
- 예외: 틀린 날짜는 칸 문구, 역전 범위는 서버 문구 배너, 프리셋을 못 읽으면 배너(URL 날짜 검색은 계속), 맞는 기록 없음 문구
- 결과: 조건(AND)에 맞는 기록과 전체 건수(PA-R11~R14)

### PA-UC3 미팅 기록 수정
- 행위자: 작성자 본인(sales), admin
- 사전 조건: 목록에 그 기록이 보이고 관리 열에 "수정"이 있음(PA-R29)
- 기본 흐름: "수정" → 저장값이 채워진 한 행을 고친다 → "저장" → 서버가 판정 순서대로 확인하고 저장한다(PA-R15~R19) → 목록을 다시 읽는다
- 대안: 회사를 그대로 두고 날짜·내용만 고침(연락처 회사명이 바뀌었어도 됨), 다른 등록 회사로 바꿈, 값이 그대로면 시각도 그대로
- 예외: 빈 내용·틀린 날짜 칸 문구, 미등록 회사 422, 남의 기록 403, 그 사이 지워진 기록 404 배너
- 결과: 바뀐 값과 새 변경 시각(작성자·등록 시각 불변)

### PA-UC4 미팅 기록 삭제
- 행위자: 작성자 본인(sales), admin
- 사전 조건: 관리 열에 "삭제"가 있음
- 기본 흐름: "삭제" → 확인 → 물리 삭제(PA-R20, R39) → 목록을 다시 읽는다
- 대안: 확인 창에서 취소
- 예외: 이미 지워진 기록 404 문구(대화상자 안), 남의 기록 403
- 결과: 그 기록만 사라짐

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM·LEE(sales), VIEWER(user). 파트너 연락처: "HanbitCo"(담당자 가나다), "비컴퍼니"(담당자 라마바). backend 서버 시각 예: 2026-10-15 10:00+09:00. backend 케이스는 Fake UoW(연락처·사용자·미팅 Fake, 고정 Clock)를 쓰는 유스케이스 단위 테스트, FakeUseCases + TestClient를 쓰는 web 단위 테스트, Fake와 SQL에 함께 도는 Repository 계약·스키마 테스트(integration 표시)다. frontend 케이스는 Fake 게이트웨이(서버 시각 2027-03-15, 시드 미팅 12건)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| PA-001 | sales가 여러 건을 한 번에 등록하면 201로 입력 순서대로 저장되고 Location이 없다 | PA-R9, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_valid_items_are_saved_in_input_order_in_one_commit`<br>`web/test_partner_meeting_routes.py::test_create_returns_201_with_items_in_input_order_and_no_location` |
| PA-002 | 등록한 기록은 문서의 필드만 갖고 작성자는 요청자, 두 시각은 같은 서버 오프셋 시각이며 Deal 필드가 없다 | PA-R9, PA-R10, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_the_saved_meeting_carries_author_company_date_content_and_times`<br>`web/test_partner_meeting_routes.py::test_created_item_has_the_documented_fields`<br>외 3건 |
| PA-003 | admin도 등록하고 내용의 앞뒤 공백은 지워지며 가운데 줄바꿈은 남는다 | PA-R3, PA-R7, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_admin_registers_and_the_content_edges_are_trimmed` |
| PA-004 | 대소문자가 다른 회사명은 등록된 대표 표기로 저장된다 | PA-R5, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_company_case_is_stored_in_the_registered_spelling` |
| PA-005 | 어느 Deal에도 연결되지 않은 파트너 회사도 그 회사 연락처가 있으면 등록된다 | PA-R5, PA-R21, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_a_partner_company_without_any_linked_deal_is_registered`<br>`web/test_partner_meeting_routes.py::test_a_partner_company_without_any_deal_can_be_recorded`<br>외 1건 |
| PA-006 | 미래·양끝 미팅 날짜를 받고 같은 회사·날짜·내용의 중복도 저장된다 | PA-R6, PA-R9, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestSaving::test_boundary_dates_are_allowed_and_duplicates_are_stored`<br>`repositories/test_partner_meeting_repository_contract.py::test_the_same_company_date_and_content_may_be_stored_twice`<br>`web/test_partner_meeting_routes.py::test_a_future_meeting_date_is_accepted`<br>외 1건 |
| PA-007 | 길이 제한 없이 긴 여러 줄 유니코드 내용이 그대로 저장된다 | PA-R7, PA-UC1 | backend | `repositories/test_partner_meeting_repository_contract.py::test_a_very_long_multiline_unicode_content_round_trips` |
| PA-008 | 일부 행이 틀리면 아무것도 저장하지 않고 모든 위반을 행·칸 위치와 함께 돌려준다 | PA-R8, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestRejections::test_unknown_company_rejects_the_whole_batch_with_its_location`<br>`web/test_partner_meeting_routes.py::test_domain_violations_map_to_invalid_value_with_error_locations`<br>외 2건 |
| PA-009 | 파트너 연락처가 모두 지워진 회사는 등록되지 않는다 | PA-R5, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestRejections::test_a_company_that_lost_all_its_partner_contacts_is_rejected` |
| PA-010 | 범위 밖 미팅 날짜는 날짜 위치로, NUL이 든 내용은 내용 위치로 거절된다 | PA-R6, PA-R7, PA-R8, PA-UC1 | backend | `application/test_register_partner_meetings.py::TestRejections::test_a_date_outside_the_bounds_is_reported_at_the_date_location`<br>외 1건 |
| PA-011 | 50건은 받고 51건·빈 목록·누락·형식 오류·deal_code 키는 422 request-validation이며 저장되지 않는다 | PA-R4, PA-UC1 | backend | `web/test_partner_meeting_routes.py::test_fifty_items_are_accepted_and_fifty_one_are_not`<br>외 5건 |
| PA-012 | user의 등록은 본문 검사보다 먼저 403 읽기 전용이고 미인증은 401이다 | PA-R3, PA-UC1 | backend | `web/test_partner_meeting_route_permissions.py::test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked`<br>외 2건 |
| PA-013 | 기본 목록은 미팅 날짜 최신순 10건과 전체 건수다 | PA-R11, PA-R13, PA-R14, PA-UC2 | backend | `application/test_list_partner_meetings.py::test_the_first_page_has_ten_items_and_the_total_counts_all`<br>`application/test_partner_meeting_query.py::test_defaults_are_the_first_page_of_ten_by_meeting_date_descending`<br>`repositories/test_partner_meeting_sort_contract.py::test_the_default_is_meeting_date_descending_then_id_descending`<br>`web/test_partner_meeting_routes.py::test_list_defaults_to_ten_items_newest_meeting_date_first` |
| PA-014 | offset으로 다음 쪽이 겹침 없이 이어진다 | PA-R14, PA-UC2 | backend | `application/test_list_partner_meetings.py::test_the_next_page_continues_where_the_first_stopped`<br>`repositories/test_partner_meeting_search_contract.py::test_offset_and_limit_cut_the_page_but_count_ignores_them`<br>`web/test_partner_meeting_routes.py::test_list_offset_continues_the_previous_page` |
| PA-015 | 같은 날의 미팅은 나중에 등록한 것이 먼저다 | PA-R13, PA-UC2 | backend | `repositories/test_partner_meeting_sort_contract.py::test_the_default_is_meeting_date_descending_then_id_descending`<br>외 1건 |
| PA-016 | 네 정렬 키가 양방향으로 정렬되고 텍스트 열의 동률은 방향과 무관하게 날짜·id 내림차순이다 | PA-R13, PA-UC2 | backend | `repositories/test_partner_meeting_sort_contract.py::test_text_sorts_tie_by_date_descending_then_id_descending_regardless_of_order`<br>`web/test_partner_meeting_routes.py::test_list_params_map_to_the_query`<br>외 3건 |
| PA-017 | 작성자 정렬은 표시 이름(없으면 아이디) 기준이고 퇴사자도 포함한다 | PA-R13, PA-UC2 | backend | `repositories/test_partner_meeting_sort_contract.py::test_the_author_sort_uses_the_display_name_or_the_login_id_including_resigned` |
| PA-018 | 정렬을 바꾸면 그 순서의 첫 쪽부터 나뉜다 | PA-R13, PA-R14, PA-UC2 | backend | `repositories/test_partner_meeting_sort_contract.py::test_paging_follows_the_sort_order` |
| PA-019 | limit은 200까지 받고 201은 422다 | PA-R11, PA-UC2 | backend | `application/test_partner_meeting_query.py::test_page_bounds_are_checked`<br>`web/test_partner_meeting_routes.py::test_list_limit_allows_up_to_200`<br>외 1건 |
| PA-020 | 기록이 없으면 빈 쪽과 0건이다 | PA-R14, PA-UC2 | backend | `application/test_list_partner_meetings.py::test_no_records_gives_an_empty_page_with_zero_total`<br>`repositories/test_partner_meeting_search_contract.py::test_an_empty_store_has_no_results_and_a_zero_count` |
| PA-021 | 모든 역할이 목록을 읽고 미인증은 401이다 | PA-R11, PA-UC2 | backend | `web/test_partner_meeting_route_permissions.py::test_every_role_may_read_the_list`<br>외 1건 |
| PA-022 | 내용·파트너 조건은 대소문자 무시 부분 일치이고 파트너는 저장된 회사명을 본다 | PA-R12, PA-UC2 | backend | `repositories/test_partner_meeting_search_contract.py::test_the_content_filter_is_a_case_insensitive_substring`<br>`web/test_partner_meeting_routes.py::test_list_params_map_to_the_query`<br>외 1건 |
| PA-023 | 텍스트 조건의 %·_·\ 는 글자 그대로 찾는다 | PA-R12, PA-UC2 | backend | `repositories/test_partner_meeting_search_contract.py::test_like_special_characters_in_the_content_filter_are_literal`<br>외 1건 |
| PA-024 | 날짜 범위는 양끝을 포함하고 한쪽만 줘도 된다 | PA-R12, PA-UC2 | backend | `application/test_partner_meeting_query.py::test_a_single_day_range_and_open_ended_ranges_are_allowed`<br>`repositories/test_partner_meeting_search_contract.py::test_the_date_range_is_inclusive_on_both_ends`<br>`web/test_partner_meeting_routes.py::test_list_params_map_to_the_query` |
| PA-025 | 작성자 조건은 그 사용자의 기록만이고 퇴사자도 찾는다 | PA-R12, PA-UC2 | backend | `repositories/test_partner_meeting_search_contract.py::test_the_author_filter_matches_exactly_one_user`<br>`web/test_partner_meeting_routes.py::test_list_params_map_to_the_query`<br>외 1건 |
| PA-026 | 조건은 AND이고 전체 건수는 페이지가 아니라 조건을 따른다 | PA-R12, PA-R14, PA-UC2 | backend | `application/test_list_partner_meetings.py::test_the_total_follows_the_filters_not_the_page`<br>`repositories/test_partner_meeting_search_contract.py::test_filters_are_anded`<br>외 1건 |
| PA-027 | 공백뿐인 텍스트 조건은 무시하고 앞뒤 공백은 지운다 | PA-R12, PA-UC2 | backend | `application/test_partner_meeting_query.py::test_blank_text_filters_become_none`<br>`web/test_partner_meeting_routes.py::test_blank_text_filters_are_ignored`<br>외 1건 |
| PA-028 | 역전된 날짜 범위와 범위 밖 검색 날짜는 422 invalid-value와 안내 문구다 | PA-R12, PA-UC2 | backend | `application/test_partner_meeting_query.py::test_a_reversed_date_range_is_rejected`<br>`web/test_partner_meeting_routes.py::test_a_reversed_date_range_is_an_invalid_value_error`<br>외 3건 |
| PA-029 | 모르는 쿼리(deal 포함)·sort=deal·형식·길이·id 오류는 422 request-validation이다 | PA-R11, PA-UC2 | backend | `application/test_partner_meeting_query.py::test_the_content_filter_is_limited_to_100_characters`<br>`web/test_partner_meeting_routes.py::test_list_with_deal_parameter_is_422`<br>외 4건 |
| PA-030 | 작성자가 날짜·내용을 고치면 200이고 변경 시각만 바뀌며 작성자·등록 시각은 그대로다 | PA-R15, PA-R19, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_the_author_changes_date_and_content_and_updated_at_moves`<br>`web/test_partner_meeting_routes.py::test_update_returns_the_changed_record` |
| PA-031 | admin은 남의 기록을 고친다 | PA-R16, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_admin_edits_another_users_record`<br>`web/test_partner_meeting_routes.py::test_admin_may_update_anyones_record` |
| PA-032 | 값이 그대로인 수정은 저장하지 않고 변경 시각도 그대로다 | PA-R19, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_no_change_does_not_save`<br>외 1건 |
| PA-033 | 다른 sales의 수정은 403 문구이고 기록은 그대로이며 user는 자기 기록이라도 403이다 | PA-R15, PA-R16, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_another_sales_is_forbidden_and_the_record_stays`<br>`web/test_partner_meeting_routes.py::test_update_by_another_sales_is_403_with_the_message_and_changes_nothing`<br>외 1건 |
| PA-034 | 수정 판정 순서는 없는 기록 404 → 작성자 403 → 입력 422다 | PA-R15, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_a_missing_record_is_not_found_before_validation`<br>`web/test_partner_meeting_routes.py::test_update_of_a_missing_record_is_404_with_the_message`<br>외 1건 |
| PA-035 | 수정의 빈 내용·범위 밖 날짜는 필드만의 위치로 422 invalid-value다 | PA-R18, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_a_blank_content_is_rejected_at_the_content_location`<br>`web/test_partner_meeting_routes.py::test_update_domain_violation_has_a_field_only_location`<br>외 1건 |
| PA-036 | 같은 회사(대소문자만 다름)는 목록 재확인 없이 저장 표기를 유지하고 연락처 회사명이 바뀐 뒤에도 날짜·내용을 고친다 | PA-R17, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_same_company_in_other_case_keeps_the_stored_company_without_lookup`<br>외 1건 |
| PA-037 | 다른 등록 회사로 바꾸면 새 대표 표기이고 미등록 회사는 partner_company 위치로 거절된다 | PA-R17, PA-R18, PA-UC3 | backend | `application/test_update_partner_meeting.py::test_changing_to_another_registered_company_stores_the_new_spelling`<br>`web/test_partner_meeting_routes.py::test_update_changing_to_an_unknown_company_has_the_company_location`<br>외 1건 |
| PA-038 | 수정 본문의 deal_code 키·누락·형식 오류는 422 request-validation이다 | PA-R15, PA-UC3 | backend | `web/test_partner_meeting_routes.py::test_update_with_a_malformed_body_is_a_request_validation_error`<br>외 1건 |
| PA-039 | 작성자가 삭제하면 204이고 그 기록만 사라진다 | PA-R20, PA-UC4 | backend | `application/test_delete_partner_meeting.py::test_deleting_one_record_keeps_the_others`<br>`web/test_partner_meeting_routes.py::test_delete_returns_204_and_the_record_disappears` |
| PA-040 | admin은 남의 기록을 삭제한다 | PA-R20, PA-R16, PA-UC4 | backend | `application/test_delete_partner_meeting.py::test_admin_deletes_another_users_record` |
| PA-041 | 다른 sales의 삭제는 403 문구이고 기록은 남으며 user는 403 읽기 전용이다 | PA-R20, PA-R16, PA-UC4 | backend | `application/test_delete_partner_meeting.py::test_another_sales_is_forbidden_and_the_record_stays`<br>`web/test_partner_meeting_route_permissions.py::test_a_read_only_user_cannot_write_and_nothing_is_saved`<br>`web/test_partner_meeting_routes.py::test_delete_by_another_sales_is_403_with_the_message`<br>외 1건 |
| PA-042 | 없는 기록의 삭제와 두 번째 삭제는 404다 | PA-R20, PA-UC4 | backend | `application/test_delete_partner_meeting.py::test_a_missing_record_is_not_found`<br>`web/test_partner_meeting_routes.py::test_delete_of_a_missing_record_is_404`<br>외 1건 |
| PA-043 | 잘못된 meeting_id 경로 값은 수정·삭제 모두 422 request-validation이다 | PA-R15, PA-R20 | backend | `web/test_partner_meeting_routes.py::test_a_bad_path_id_is_a_request_validation_error` |
| PA-044 | 미팅은 Deal과 무관하다: Deal 선택지 경로가 없고 Deal 삭제 영향에 미팅 건수가 없으며 Deal을 지워도 남는다 | PA-R21 | backend | `infra/schema/test_partner_meeting_schema.py::test_deleting_a_deal_does_not_touch_meetings`<br>`web/test_partner_meeting_deletion_impact_route.py::test_deletion_impact_response_has_four_counts`<br>`web/test_partner_meeting_openapi.py::test_the_deletion_impact_response_has_four_counts`<br>`web/test_partner_meeting_routes.py::test_deal_options_path_no_longer_serves_get`<br>외 1건 |
| PA-045 | 미팅을 쓴 사용자를 삭제하면 퇴사 처리되고 기록에 "(퇴사)" 작성자로 남아 작성자 조건·선택지로 찾는다 | PA-R22, PA-UC2 | backend | `application/test_partner_meeting_lifecycle.py::test_deleting_the_author_resigns_them_and_the_record_stays_searchable` |
| PA-046 | 연락처 회사명을 바꿔도 기존 기록은 옛 이름이고 새 등록은 새 이름만 받는다 | PA-R23, PA-R5 | backend | `application/test_partner_meeting_lifecycle.py::test_renaming_the_contact_company_keeps_old_records_and_changes_what_registers` |
| PA-047 | partner_meetings 테이블의 컬럼·제약·인덱스가 명세와 같다 | PA-R2 | backend | `infra/schema/test_partner_meeting_schema.py::test_partner_meetings_columns_types_and_nullability`<br>외 12건 |
| PA-048 | openapi에 미팅 경로·파라미터·본문·응답·오류 코드가 명세대로 있고 Deal 관련 항목이 없다 | PA-R24, PA-R21 | backend | `web/test_partner_meeting_openapi.py::test_paths_and_methods`<br>외 20건 |
| PA-049 | 화면은 제목과 네 열을 보이고 쓰기 역할에만 관리 열이 있으며 Deal 열이 없다 | PA-R25, PA-R26, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows the heading and the four columns in order, ending with a management column for people who can write`<br>외 2건 |
| PA-050 | 기본 화면은 미팅 날짜 최신 10건이고 주소에 쿼리가 없다 | PA-R27, PA-R28, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > lists the ten newest meetings first by meeting date (newest on top)`<br>외 1건 |
| PA-051 | 칸은 회사명·YYYY-MM-DD 날짜·줄바꿈 내용·작성자이고 퇴사한 작성자는 "(퇴사)"다 | PA-R26, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows partner company, date as yyyy-mm-dd and the author name, with no deal link`<br>외 2건 |
| PA-052 | 기록이 없으면 빈 문구이고 더 보기가 없다 | PA-R25, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows the empty message and no more-button when there are no meetings` |
| PA-053 | 목록 끝이 보이면 10건씩 붙이고 다 읽으면 끝 문구를 보이며 더 읽지 않는다 | PA-R28, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > appends the next ten when the end of the list scrolls into view, then says everything is loaded`<br>외 2건 |
| PA-054 | 다음 쪽이 있는 동안 더 보기 버튼이 있고 누르면 다음 쪽을 읽는다 | PA-R28, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows a more-button while there is a next page and loads it on click` |
| PA-055 | 쪽 사이에 다른 사용자가 기록을 더해도 같은 기록은 한 번만 보인다 | PA-R28, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows each meeting once even when another user adds one between the pages` |
| PA-056 | 수정·삭제 버튼은 sales 본인 행·admin 모든 행에만 있고 user에게는 아무 버튼도 없다 | PA-R26, PA-R29, PA-R25 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > shows edit and delete only on the rows the viewer may change`<br>외 2건 |
| PA-057 | 미로그인은 로그인 화면으로 가고 상단 메뉴로 화면에 온다 | PA-R25, PL-R33, PL-R34 | frontend | `features/partner-activity/PartnerActivityPage.test.tsx > sends a visitor who is not logged in to the login page`<br>외 1건 |
| PA-058 | 검색 폼은 Deal 없이 네 조건과 검색·초기화이고 텍스트 칸은 서버 길이로 제한된다 | PA-R30, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > has the four conditions without a deal and the search and reset buttons`<br>외 1건 |
| PA-059 | 파트너 일부 글자로 검색하면 URL에 쓰이고 텍스트 칸 Enter로도 검색된다 | PA-R30, PA-R27, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > searches the partner by part of the company name and writes it to the URL`<br>외 1건 |
| PA-060 | 작성자로 검색하고 선택지에 퇴사자가 있다 | PA-R30, PA-R22, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > searches by author, with resigned users among the choices` |
| PA-061 | 조건은 AND이고 %·_ 는 글자이며 맞는 기록이 없으면 빈 문구다 | PA-R30, PA-R12, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > ands the conditions`<br>외 2건 |
| PA-062 | 틀린 날짜면 검색하지 않고 칸 문구를, 역전 범위면 서버 문구 배너를 보인다 | PA-R30, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > shows the error when the start date is later than the end date`<br>`features/partner-activity/PartnerActivityPage.search.test.tsx > does not search and marks the field when a date is wrong`<br>외 1건 |
| PA-063 | 검색하면 첫 쪽부터이고 주소로 조건·결과를 복원하며 초기화는 모든 조건과 주소를 지운다 | PA-R27, PA-R30, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > starts from the first page again after a search`<br>외 2건 |
| PA-064 | 정렬만 바뀌면 검색 전 입력이 남고 주소가 바깥에서 바뀌면 칸이 따라간다 | PA-R30, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > keeps what was typed but not searched yet when only the sort changes`<br>외 1건 |
| PA-065 | 네 열 머리글로 정렬하고 기본 미팅 날짜 내림차순, 새 열은 오름차순부터 다시 누르면 반대다 | PA-R32, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > makes the four columns sortable and starts on the meeting date, descending`<br>외 3건 |
| PA-066 | 정렬을 바꾸면 첫 10건부터이고 주소의 정렬을 복원하며 검색해도 정렬이 유지된다 | PA-R32, PA-R27, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > restarts from the first ten when the sort changes after loading more`<br>외 2건 |
| PA-067 | 예전 주소의 deal은 무시하고 sort=deal은 기본 정렬로 열며 Deal을 주소·서버에 쓰지 않는다 | PA-R27, PA-R21, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.search.test.tsx > ignores ?deal= and opens ?sort=deal with the default sort, sending no deal to the server`<br>외 1건 |
| PA-068 | 미팅 날짜는 일곱 선택지의 선택 상자이고 서버 프리셋에 없는 키는 비활성이다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > replaces the two date inputs with one select offering the same seven options as Deals`<br>외 1건 |
| PA-069 | 프리셋을 골라 검색하면 서버에 다시 물은 날짜를 URL·요청에 쓰고 그 날짜가 오늘의 프리셋이면 프리셋으로 보인다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > sends the server preset range to the URL from/to and to the request after searching`<br>외 2건 |
| PA-070 | 프리셋 다시 묻기가 실패하면 배너와 함께 조건을 바꾸지 않고 프리셋을 못 읽으면 모두 비활성이다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > shows the error and keeps the URL dates when asking for the presets again fails`<br>외 1건 |
| PA-071 | 직접 지정을 골라야 날짜 칸이 보이고 한쪽만으로 검색되며 프리셋으로 바꾸면 칸이 사라진다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > shows the start and end inputs only after choosing 직접 지정`<br>`features/partner-activity/PartnerActivityPage.search.test.tsx > searches a date range through the date inputs, both ends included`<br>외 3건 |
| PA-072 | 전체는 날짜 조건을 지우고 초기화하면 전체로 돌아간다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > removes from and to from the URL and the request when 전체 is chosen after a dated search`<br>외 2건 |
| PA-073 | 주소로 열면 오늘의 프리셋과 같을 때만 프리셋이고 그 밖은 직접 지정이며 프리셋을 못 읽어도 날짜로 검색한다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > shows the preset when the URL dates equal the server preset`<br>외 6건 |
| PA-074 | 직접 지정으로 검색한 날짜는 프리셋 범위와 같아도 직접 지정으로 남고 다시 받은 프리셋에 키가 없으면 날짜 없이 검색한다 | PA-R31, PA-UC2 | frontend | `features/partner-activity/PartnerActivityPage.period.test.tsx > keeps 직접 지정 and the date inputs after searching dates equal to a preset range`<br>외 2건 |
| PA-075 | 입력 팝업은 빈 행 하나·파트너 포커스·오늘 날짜로 열리고 admin도 열며 user에게는 버튼이 없다 | PA-R33, PA-UC1 | frontend | `features/partner-activity/PartnerActivityPage.entry.test.tsx > opens a dialog with one empty row, focus on the partner, and today as the default date`<br>`features/partner-activity/PartnerActivityPage.test.tsx > shows no buttons at all to a read-only user, not even the entry button`<br>외 3건 |
| PA-076 | 행 추가는 오늘 날짜 행을 더하고 행 삭제는 번호를 다시 매기며 50행을 넘기지 않는다 | PA-R33, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.keys.test.tsx > does not add a 51st row with Enter and explains the limit`<br>`features/partner-activity/PartnerActivityPage.entry.test.tsx > adds a row with today as its date and renumbers the rows when one is removed`<br>외 1건 |
| PA-077 | 파트너 칸은 등록된 회사 목록을 친 글자로 좁히고 고르면 날짜 칸으로 가며 행마다 따로다 | PA-R34, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.keys.test.tsx > moves the focus to the date field when a partner is chosen from the list`<br>`features/partner-activity/PartnerActivityPage.entry.test.tsx > lists the registered partner companies`<br>외 5건 |
| PA-078 | 목록 글자를 그대로 치고 Enter면 고른 것으로 보고 없으면 "목록에서 선택하세요."다 | PA-R34, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.exactMatch.test.tsx > takes a partner typed exactly as in the list as chosen and moves to the date field`<br>외 5건 |
| PA-079 | 날짜 Enter·달력 선택은 내용 칸으로 가고 덜 친 날짜는 머물며 콤보박스 Enter는 상태대로 움직인다 | PA-R35, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.keys.test.tsx > moves the focus to the content when 20270310 and Enter are typed in the date field`<br>외 4건 |
| PA-080 | 내용 칸 Enter는 빠진 칸·다음 행·새 행 순으로 가고 Shift+Enter는 줄바꿈, 한글 조합 Enter는 무시한다 | PA-R35, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.keys.test.tsx > adds a new row with today as its date and puts the focus on its partner when Enter is pressed in the last full row`<br>외 5건 |
| PA-081 | 저장하면 빈 행을 건너뛴 N건이 저장되고 팝업이 닫히며 알림과 함께 목록 맨 위에 보인다 | PA-R36, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.save.test.tsx > saves several rows, closes the dialog, shows them at the top of the list and says how many were saved`<br>외 5건 |
| PA-082 | 저장 전 검사는 모든 행이 비면 안내하고 빠진 칸 문구와 첫 칸 포커스를 보이며 요청하지 않는다 | PA-R36, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.save.test.tsx > sends nothing and says so when every row is empty`<br>외 7건 |
| PA-083 | 서버가 거절하면 입력을 유지하고 거절된 행·칸에 서버 문구를, 위치 없는 실패는 팝업 배너를 보인다 | PA-R36, PA-R8, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.save.test.tsx > saves nothing, keeps the dialog open and shows the server message at the row and field that were rejected`<br>외 1건 |
| PA-084 | 빈 팝업은 바로 닫히고 입력이 있으면 버릴지 묻는다 | PA-R37, PA-UC1 | frontend | `features/partner-activity/MeetingEntryDialog.close.test.tsx > closes an empty dialog at once with 취소`<br>외 6건 |
| PA-085 | 수정 팝업은 저장값 한 행이고 내용 Enter는 저장 버튼으로 가며 저장하면 닫히고 새 위치에 보인다 | PA-R38, PA-UC3 | frontend | `features/partner-activity/MeetingEditDialog.test.tsx > opens one row filled with the stored values and no way to add rows`<br>외 5건 |
| PA-086 | 수정 팝업은 빈 내용·틀린 날짜를 막고 다른 파트너를 골라도 날짜·내용을 유지하며 서버 오류를 보인다 | PA-R38, PA-R17, PA-UC3 | frontend | `features/partner-activity/MeetingEditDialog.test.tsx > saves a content-only change even after the contact company was renamed meanwhile`<br>외 5건 |
| PA-087 | 삭제는 확인 뒤 지우고 취소하면 남기며 이미 지워졌으면 대화상자에 서버 문구를 보인다 | PA-R39, PA-UC4 | frontend | `features/partner-activity/MeetingTable.test.tsx > asks for confirmation naming the action`<br>외 5건 |
| PA-088 | 등록·수정·삭제 뒤 목록 첫 쪽을 한 번만 다시 요청한다 | PA-R40 | frontend | `features/partner-activity/PartnerActivityPage.requests.test.tsx > asks for the first page once after a registration`<br>외 2건 |
| PA-089 | 게이트웨이 목록은 값 있는 조건만 snake_case로 보내고 응답을 화면 모양으로 바꾼다 | PA-R41 | frontend | `gateway/http/partnerMeetings.test.ts > 목록은 GET /partner-meetings에 쪽과 정렬을 snake_case로 보내고 응답을 화면 모양으로 바꾼다`<br>외 7건 |
| PA-090 | 게이트웨이 등록·수정·삭제는 세 키 본문을 보내고 422 위치 위반을 itemErrors로 옮긴다 | PA-R41 | frontend | `gateway/http/partnerMeetings.test.ts > 등록은 {items}를 snake_case로 보내고 만든 기록을 순서대로 바꾼다`<br>외 9건 |
| PA-091 | Fake 게이트웨이는 권한·판정 순서·일괄 위반·요청 형식 오류에서 서버와 같은 결과를 낸다 | PA-R42 | frontend | `gateway/contract/partnerMeetings.contract.ts > creates several meetings in input order and lists them newest meeting date first`<br>`test/fake/gateway/partnerMeetings.test.ts > has twelve sample meetings in the planned default order`<br>외 38건 |
| PA-092 | canEditMeeting은 admin 모두·sales 본인만 참이고 user는 거짓이다 | PA-R29 | frontend | `shared/model/permissions.test.ts > 수정·삭제: %s` |
| PA-093 | Fake 목록 조회는 서버처럼 범위 밖 날짜·긴 텍스트·NUL 조건을 거절한다 | PA-R42, PA-R11, PA-R12 | frontend | `gateway/contract/partnerMeetings.contract.ts > rejects an out-of-bounds search date with the range message and a too long text condition with the request-format error`<br>`test/fake/gateway/partnerMeetings.test.ts > rejects the out-of-bounds search date (%s) with the range message, not the reversed-range message`<br>외 4건 |

### PA-001 sales가 여러 건을 한 번에 등록하면 201로 입력 순서대로 저장되고 Location이 없다
- Given 파트너 연락처 "HanbitCo"·"비컴퍼니", KIM(sales) 로그인
- When KIM이 `[HanbitCo 2027-03-03 "첫째", 비컴퍼니 2027-03-02 "둘째", HanbitCo 2027-03-01 "셋째"]`를 `POST /partner-meetings`로 보낸다
- Then 201이고 `Location` 헤더가 없으며 응답 `items`의 내용은 "첫째"·"둘째"·"셋째", 회사는 HanbitCo·비컴퍼니·HanbitCo 순서이고, 저장소에도 세 건이 있으며 한 번의 커밋으로 저장된다

### PA-002 등록한 기록은 문서의 필드만 갖고 작성자는 요청자, 두 시각은 같은 서버 오프셋 시각이며 Deal 필드가 없다
- Given 파트너 "HanbitCo", Deal이 하나도 없음, 서버 시각 2026-10-15 10:00+09:00, KIM 로그인
- When KIM이 HanbitCo 미팅 한 건을 등록한다
- Then 항목 키는 정확히 `id`·`partner_company`·`meeting_date`·`content`·`author`·`created_at`·`updated_at`이고 `deal` 키가 없으며, `author.id`는 KIM, `created_at` = `updated_at` = `2026-10-15T10:00:00+09:00`(끝이 `Z`가 아님)이고 id는 할당기에서 항목마다 하나씩 받는다

### PA-003 admin도 등록하고 내용의 앞뒤 공백은 지워지며 가운데 줄바꿈은 남는다
- Given 파트너 "HanbitCo", ROOT(admin) 로그인
- When ROOT가 내용 `"\n 계약 논의\n다음 주 방문 \n"`인 미팅을 등록한다
- Then 201이고 저장된 내용은 `"계약 논의\n다음 주 방문"`이다

### PA-004 대소문자가 다른 회사명은 등록된 대표 표기로 저장된다
- Given 파트너 연락처 회사 "HanbitCo"
- When 회사를 `"hanbitco"`로 등록한다
- Then 201이고 저장된 `partner_company`는 "HanbitCo"다

### PA-005 어느 Deal에도 연결되지 않은 파트너 회사도 그 회사 연락처가 있으면 등록된다
- Given 파트너 연락처 회사 "NoDealPartner"(어느 Deal의 파트너도 아님), 같은 회사의 연락처가 둘 이상 있는 "HanbitCo"
- When 각 회사로 미팅을 등록한다
- Then 둘 다 201이고 회사명은 각각 "NoDealPartner"·"HanbitCo"다

### PA-006 미래·양끝 미팅 날짜를 받고 같은 회사·날짜·내용의 중복도 저장된다
- Given 파트너 "HanbitCo"
- When 미팅 날짜 2999-12-31, 1900-01-01로 각각 등록하고, 같은 회사·날짜·내용의 미팅을 두 번 등록한다
- Then 모두 201이고 날짜가 그대로 저장되며 같은 내용의 기록이 두 건 있다

### PA-007 길이 제한 없이 긴 여러 줄 유니코드 내용이 그대로 저장된다
- Given 파트너 "HanbitCo"
- When 내용이 `"줄 0 😀\n줄 1 😀\n…"`(5,000줄)인 미팅을 등록한다
- Then 201이고 저장된 내용이 보낸 글자와 똑같다

### PA-008 일부 행이 틀리면 아무것도 저장하지 않고 모든 위반을 행·칸 위치와 함께 돌려준다
- Given 파트너 "HanbitCo"
- When `[정상 행, 회사 "없는회사", 내용 "  ", 날짜 3000-01-01]` 네 행을 등록한다
- Then 422 `invalid-value`, `detail`은 "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."이고 `errors`는 차례로 `["items",1,"partner_company"]`·`["items",2,"content"]` "미팅 내용을 입력하세요."·`["items",3,"meeting_date"]` "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"이며, 어느 위치에도 `deal_code`가 없고 저장된 기록은 0건이다(정상 행 포함)

### PA-009 파트너 연락처가 모두 지워진 회사는 등록되지 않는다
- Given 파트너 연락처 "OldPartner" 하나를 등록했다가 지움
- When 회사 "OldPartner"로 등록한다
- Then 422 `invalid-value`, 위치 `["items",0,"partner_company"]`이고 저장되지 않는다

### PA-010 범위 밖 미팅 날짜는 날짜 위치로, NUL이 든 내용은 내용 위치로 거절된다
- Given 파트너 "HanbitCo"
- When 날짜 1899-12-31, 3000-01-01인 행과 내용 `"a\x00b"`인 행을 각각 등록한다
- Then 날짜는 422 `invalid-value` 위치 `["items",0,"meeting_date"]`·범위 문구, 내용은 위치 `["items",0,"content"]`·"미팅 내용에는 NUL 문자를 쓸 수 없습니다"이고 둘 다 저장되지 않는다

### PA-011 50건은 받고 51건·빈 목록·누락·형식 오류·deal_code 키는 422 request-validation이며 저장되지 않는다
- Given 파트너 "HanbitCo"
- When 51건, 50건, `{"items": []}`, `{}`, `{"items": "x"}`, `{"items": [{"partner_company": "HanbitCo"}]}`, 날짜가 `"2026-13-01"`인 항목, 201자 회사명 항목, `deal_code`가 붙은 항목을 등록한다
- Then 50건만 201(50건 저장)이고 나머지는 모두 422 `request-validation`이며, 키가 빠진 항목의 오류 `loc`에는 항목 번호가 들어가고, 거절된 요청으로는 아무것도 저장되지 않는다

### PA-012 user의 등록은 본문 검사보다 먼저 403 읽기 전용이고 미인증은 401이다
- Given 파트너 "HanbitCo", VIEWER(user)
- When VIEWER가 정상 본문과 형식이 틀린 본문으로 각각 등록하고, 로그인하지 않은 채 등록한다
- Then VIEWER는 두 요청 모두 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 저장되지 않으며, 미인증은 401이다

### PA-013 기본 목록은 미팅 날짜 최신순 10건과 전체 건수다
- Given 날짜가 서로 다른 미팅 12건
- When 쿼리 없이 `GET /partner-meetings`를 부른다
- Then 날짜가 가장 늦은 10건이 내림차순으로 오고 `total` 12, `offset` 0, `limit` 10이다

### PA-014 offset으로 다음 쪽이 겹침 없이 이어진다
- Given PA-013과 같은 12건
- When `offset=10`으로 부른다
- Then 나머지 2건이 이어지는 순서로 오고 첫 쪽과 겹치지 않는다

### PA-015 같은 날의 미팅은 나중에 등록한 것이 먼저다
- Given 같은 날짜로 "먼저" → "나중" 순서로 등록한 두 기록
- When 기본 정렬로 읽는다
- Then "나중"이 "먼저"보다 앞이다. `order=asc`이면 "먼저"가 앞이다

### PA-016 네 정렬 키가 양방향으로 정렬되고 텍스트 열의 동률은 방향과 무관하게 날짜·id 내림차순이다
- Given 회사 "alpha"·"Beta"·"gamma", 내용 "가"·"나"·"다", 그리고 회사·내용이 같고 날짜만 다른 두 기록
- When `sort`를 `meeting_date`·`partner`·`content`·`author` 각각에 `order` `asc`·`desc`로 읽는다
- Then 각 열의 소문자 값 코드 포인트 순으로 방향대로 정렬되고("alpha" < "Beta" < "gamma"), 주 키가 같은 기록은 `asc`·`desc` 모두 날짜가 늦은 것 → id가 큰 것 먼저다

### PA-017 작성자 정렬은 표시 이름(없으면 아이디) 기준이고 퇴사자도 포함한다
- Given 표시 이름 "Zed"인 KIM, 표시 이름이 비고 아이디 "amy"인 사용자, 퇴사한 "Bob"이 각각 쓴 기록
- When `sort=author&order=asc`로 읽는다
- Then 순서는 amy, Bob, Zed이고 퇴사자의 기록도 나온다

### PA-018 정렬을 바꾸면 그 순서의 첫 쪽부터 나뉜다
- Given 12건
- When `sort=partner&order=asc&limit=5`로 첫 쪽과 `offset=5` 쪽을 읽는다
- Then 두 쪽을 이으면 회사 오름차순 전체 순서의 앞 10건과 같다

### PA-019 limit은 200까지 받고 201은 422다
- Given 기록 몇 건
- When `limit=200`, `limit=201`로 부른다
- Then 200은 200 OK, 201은 422 `request-validation`이다

### PA-020 기록이 없으면 빈 쪽과 0건이다
- Given 기록이 하나도 없음
- When 목록을 읽는다
- Then `items` `[]`, `total` 0이다

### PA-021 모든 역할이 목록을 읽고 미인증은 401이다
- Given 기록 1건
- When ROOT·KIM·VIEWER가 각각, 그리고 로그인하지 않은 채 목록을 부른다
- Then 세 역할은 200이고 같은 1건이며 미인증은 401이다

### PA-022 내용·파트너 조건은 대소문자 무시 부분 일치이고 파트너는 저장된 회사명을 본다
- Given 회사 "HanbitCo" 내용 "Cloud 이전 논의", 회사 "비컴퍼니" 내용 "보안 점검"
- When `content=cloud`, `partner=bit`로 각각 읽는다
- Then 각각 HanbitCo 기록만 나온다

### PA-023 텍스트 조건의 %·_·\ 는 글자 그대로 찾는다
- Given 내용 "100% 달성", "a_b 확인", "경로 C:\\temp", "평범한 내용"
- When `content=%`, `content=_`, `content=\`로 각각 읽는다
- Then 각각 그 글자가 든 기록 하나만 나온다

### PA-024 날짜 범위는 양끝을 포함하고 한쪽만 줘도 된다
- Given 미팅 날짜 2026-10-01·2026-10-02·2026-10-03·2026-10-04
- When `date_from=2026-10-02&date_to=2026-10-03`, `date_from=2026-10-03`, `date_to=2026-10-01`, `date_from=date_to=2026-10-02`로 읽는다
- Then 각각 10-02·10-03, 10-03·10-04, 10-01, 10-02다

### PA-025 작성자 조건은 그 사용자의 기록만이고 퇴사자도 찾는다
- Given KIM 기록 2건, LEE 기록 1건, 퇴사한 사용자의 기록 1건
- When `author_user_id`를 KIM, 퇴사자, 없는 id로 각각 준다
- Then KIM 2건, 퇴사자 1건, 0건이다

### PA-026 조건은 AND이고 전체 건수는 페이지가 아니라 조건을 따른다
- Given HanbitCo·KIM·10월 기록 3건, HanbitCo·LEE 1건, 비컴퍼니·KIM 1건
- When `partner=Hanbit&author_user_id=<KIM>&date_from=2026-10-01&limit=2`로 읽는다
- Then `items`는 2건, `total`은 3이다. 조건에 맞는 것이 없으면 `items` `[]`·`total` 0이다

### PA-027 공백뿐인 텍스트 조건은 무시하고 앞뒤 공백은 지운다
- Given 기록 3건 중 내용에 "점검"이 든 것 1건
- When `content=%20%20`, `partner=%20`, `content=%20점검%20`으로 읽는다
- Then 앞의 둘은 3건 전부, 마지막은 1건이다

### PA-028 역전된 날짜 범위와 범위 밖 검색 날짜는 422 invalid-value와 안내 문구다
- Given 기록 몇 건
- When `date_from=2026-10-05&date_to=2026-10-01`, `date_from=1899-12-31`, `date_to=3000-01-01`로 읽는다
- Then 첫 요청은 422 `invalid-value` "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.", 나머지는 422 `invalid-value` "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"다

### PA-029 모르는 쿼리(deal 포함)·sort=deal·형식·길이·id 오류는 422 request-validation이다
- Given 기록 몇 건
- When `deal=20261016-A001`, `deal_code=x`, `sort=deal`, `order=up`, `offset=-1`, `limit=0`, `date_from=2026-13-01`, 201자 `partner`, 101자 `content`, `author_user_id=abc`로 각각 읽는다
- Then 모두 422 `request-validation`이다

### PA-030 작성자가 날짜·내용을 고치면 200이고 변경 시각만 바뀌며 작성자·등록 시각은 그대로다
- Given KIM이 2026-10-01 HanbitCo "처음" 기록을 2026-10-15 10:00에 등록, 지금 2026-10-16 09:00
- When KIM이 `{partner_company: "HanbitCo", meeting_date: "2026-10-02", content: "고침"}`으로 `PUT`한다
- Then 200이고 날짜 2026-10-02·내용 "고침"·`updated_at` 2026-10-16 09:00+09:00이며, 작성자 KIM과 `created_at`은 그대로다

### PA-031 admin은 남의 기록을 고친다
- Given KIM의 기록
- When ROOT가 내용을 고친다
- Then 200이고 내용이 바뀌며 작성자는 KIM 그대로다

### PA-032 값이 그대로인 수정은 저장하지 않고 변경 시각도 그대로다
- Given KIM의 기록(회사 HanbitCo, 내용 "같음"), 시계를 하루 뒤로 옮김
- When KIM이 회사 `"hanbitco"`, 같은 날짜, 내용 `"  같음  "`으로 `PUT`한다
- Then 200이고 회사는 "HanbitCo", `updated_at`은 이전 값 그대로이며 저장소에 쓰기가 없다

### PA-033 다른 sales의 수정은 403 문구이고 기록은 그대로이며 user는 자기 기록이라도 403이다
- Given KIM의 기록
- When LEE가 내용을 고치고, (유스케이스에서) user 역할로 자기 기록 id를 고친다
- Then LEE는 403 `forbidden` "본인 미팅 기록 또는 admin만 수정할 수 있습니다."이고 기록은 그대로이며, user는 403이다(경로에서는 PL-R6 읽기 전용 403이 먼저)

### PA-034 수정 판정 순서는 없는 기록 404 → 작성자 403 → 입력 422다
- Given KIM의 기록
- When KIM이 없는 id를 빈 내용으로 고치고, LEE가 KIM 기록을 빈 내용으로 고친다
- Then 첫 요청은 404 `not-found` "미팅 기록을 찾을 수 없습니다."(422 아님), 둘째는 403(422 아님)이다

### PA-035 수정의 빈 내용·범위 밖 날짜는 필드만의 위치로 422 invalid-value다
- Given KIM의 기록
- When KIM이 내용 `"   "`, 날짜 3000-01-01로 각각 고친다
- Then 422 `invalid-value`이고 `errors` 위치는 각각 `["content"]`·`["meeting_date"]`(`items` 접두 없음)이며 기록은 그대로다

### PA-036 같은 회사(대소문자만 다름)는 목록 재확인 없이 저장 표기를 유지하고 연락처 회사명이 바뀐 뒤에도 날짜·내용을 고친다
- Given HanbitCo 기록, 그 뒤 연락처 회사명을 "새회사명"으로 바꿈(파트너 회사 목록에 HanbitCo 없음)
- When 작성자가 회사 `"HANBITCO"`와 새 날짜로 고친다
- Then 200이고 회사는 저장된 "HanbitCo" 그대로, 날짜만 바뀌며 회사 목록은 읽지 않는다

### PA-037 다른 등록 회사로 바꾸면 새 대표 표기이고 미등록 회사는 partner_company 위치로 거절된다
- Given HanbitCo 기록, 파트너 회사 "비컴퍼니"·"DeltaCo"
- When 회사를 `"deltaco"`로, 다음에 `"없는회사"`로 고친다
- Then 첫 요청은 200·회사 "DeltaCo", 둘째는 422 `invalid-value` 위치 `["partner_company"]`·"등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."이고 기록은 DeltaCo 그대로다

### PA-038 수정 본문의 deal_code 키·누락·형식 오류는 422 request-validation이다
- Given KIM의 기록
- When `deal_code`를 더한 본문, `content`가 빠진 본문, 날짜가 글자인 본문으로 고친다
- Then 모두 422 `request-validation`이고 기록은 그대로다

### PA-039 작성자가 삭제하면 204이고 그 기록만 사라진다
- Given KIM의 기록 A·B
- When KIM이 A를 `DELETE`한다
- Then 204(본문 없음)이고 목록에 B만 남는다

### PA-040 admin은 남의 기록을 삭제한다
- Given KIM의 기록
- When ROOT가 삭제한다
- Then 204이고 기록이 없다

### PA-041 다른 sales의 삭제는 403 문구이고 기록은 남으며 user는 403 읽기 전용이다
- Given KIM의 기록
- When LEE가, VIEWER가 각각 삭제한다
- Then LEE는 403 "본인 미팅 기록 또는 admin만 삭제할 수 있습니다.", VIEWER는 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 기록은 남는다

### PA-042 없는 기록의 삭제와 두 번째 삭제는 404다
- Given KIM의 기록 A
- When KIM이 없는 id를 지우고, A를 두 번 지운다
- Then 없는 id와 두 번째 삭제는 404 `not-found` "미팅 기록을 찾을 수 없습니다."이고 첫 삭제는 204다

### PA-043 잘못된 meeting_id 경로 값은 수정·삭제 모두 422 request-validation이다
- Given 로그인한 KIM
- When `PUT`·`DELETE /partner-meetings/{abc|0|-1|1.5|9007199254740992}`를 부른다
- Then 모두 422 `request-validation`이다

### PA-044 미팅은 Deal과 무관하다: Deal 선택지 경로가 없고 Deal 삭제 영향에 미팅 건수가 없으며 Deal을 지워도 남는다
- Given 파트너 HanbitCo가 연결된 Deal과 HanbitCo 미팅 기록
- When `GET /partner-meetings/deal-options`, 그 Deal의 `GET /deals/{code}/deletion-impact`, 그 Deal 삭제를 차례로 부른다
- Then deal-options는 미팅 API로 처리되지 않고(404 또는 405), 삭제 영향 키는 `history_count`·`action_count`·`attachment_count`·`license_contract_count`뿐이며(DD-R22), Deal 삭제 뒤에도 미팅 기록이 그대로 목록에 있다

### PA-045 미팅을 쓴 사용자를 삭제하면 퇴사 처리되고 기록에 "(퇴사)" 작성자로 남아 작성자 조건·선택지로 찾는다
- Given KIM이 쓴 "퇴사자 기록"(KIM의 다른 연결 없음)
- When ROOT가 KIM을 삭제한다
- Then 결과는 `resigned`이고 목록의 그 기록 `author`는 `resigned: true`·label "<이름>(퇴사)"이며, `author_user_id=<KIM>`으로 그 기록이 나오고 `GET /user-options?include_resigned=true`에 KIM이 있다

### PA-046 연락처 회사명을 바꿔도 기존 기록은 옛 이름이고 새 등록은 새 이름만 받는다
- Given 파트너 연락처 "HanbitCo"와 그 회사 기록, 그 뒤 연락처 회사명을 "새회사명"으로 수정
- When `partner=HanbitCo`로 검색하고, "HanbitCo"와 "새회사명"으로 각각 등록한다
- Then 검색 결과의 회사명은 "HanbitCo" 그대로이고, "HanbitCo" 등록은 422(`partner_company`), "새회사명" 등록은 201이다

### PA-047 partner_meetings 테이블의 컬럼·제약·인덱스가 명세와 같다
- Given head 스키마의 임시 DB
- When 컬럼·FK·인덱스를 조회하고 원시 INSERT·DELETE로 제약을 어겨 본다
- Then 2.2 표와 같고(Deal 컬럼·FK·인덱스 없음, UNIQUE는 PK뿐), PA-R2의 거절·허용 결과가 그 제약 이름으로 나온다

### PA-048 openapi에 미팅 경로·파라미터·본문·응답·오류 코드가 명세대로 있고 Deal 관련 항목이 없다
- Given 앱의 openapi
- When 미팅 경로를 읽는다
- Then PA-R24와 같고 `/partner-meetings/deal-options` 경로, 정렬 값 `deal`, Deal 관련 미팅 스키마가 없다

### PA-049 화면은 제목과 네 열을 보이고 쓰기 역할에만 관리 열이 있으며 Deal 열이 없다
- Given 시드 미팅 12건
- When sales와 user가 각각 `/partner-activities`를 연다
- Then 제목 "파트너 Activity", 표 "파트너 미팅 기록"의 머리글은 sales에게 파트너·미팅 날짜·미팅 내용·작성자·관리, user에게 앞의 넷이고, 어느 쪽에도 Deal 열이 없다

### PA-050 기본 화면은 미팅 날짜 최신 10건이고 주소에 쿼리가 없다
- Given 시드 12건
- When 화면을 연다
- Then 미팅 날짜가 가장 늦은 10건이 위에서부터 내림차순이고 주소는 `/partner-activities`(쿼리 없음)다

### PA-051 칸은 회사명·YYYY-MM-DD 날짜·줄바꿈 내용·작성자이고 퇴사한 작성자는 "(퇴사)"다
- Given 줄바꿈이 든 내용의 기록, 작성 뒤 퇴사한 작성자의 기록
- When 화면을 연다
- Then 칸은 회사명, `2027-03-14` 같은 날짜, 줄바꿈이 그대로인 내용, 작성자 이름이고 퇴사자는 "<이름>(퇴사)"이며 Deal 링크가 없다

### PA-052 기록이 없으면 빈 문구이고 더 보기가 없다
- Given 기록 0건
- When 화면을 연다
- Then "기록된 미팅이 없습니다."가 보이고 "더 보기"·끝 문구가 없다

### PA-053 목록 끝이 보이면 10건씩 붙이고 다 읽으면 끝 문구를 보이며 더 읽지 않는다
- Given 시드 12건
- When 목록 끝의 감시 요소가 화면에 들어온다
- Then 감시는 200px 여유로 등록되고, 다음 2건이 아래에 붙어 12건이 되며 "모두 불러왔습니다 (전체 12건)"이 보이고 더 요청하지 않는다. 10건만 보이는 동안에는 끝 문구가 없다

### PA-054 다음 쪽이 있는 동안 더 보기 버튼이 있고 누르면 다음 쪽을 읽는다
- Given 시드 12건, 첫 10건이 보임
- When "더 보기"를 누른다
- Then 12건이 되고 "더 보기"가 사라진다

### PA-055 쪽 사이에 다른 사용자가 기록을 더해도 같은 기록은 한 번만 보인다
- Given 첫 10건을 읽은 뒤 다른 사용자가 가장 최신 날짜의 기록을 더함
- When 다음 쪽을 읽는다
- Then 경계가 밀려 다시 온 기록은 한 번만 보이고 행 수는 중복 없이 늘어난다

### PA-056 수정·삭제 버튼은 sales 본인 행·admin 모든 행에만 있고 user에게는 아무 버튼도 없다
- Given 작성자가 섞인 시드
- When KIM(sales), ROOT(admin), VIEWER(user)가 각각 화면을 연다
- Then KIM은 자기 행에만 "수정"·"삭제"가 있고 남의 행 관리 칸은 비며, ROOT는 모든 행에 있고, VIEWER에게는 관리 열·"미팅 내용 입력" 버튼이 없다. sales·admin에게는 "미팅 내용 입력"이 있다

### PA-057 미로그인은 로그인 화면으로 가고 상단 메뉴로 화면에 온다
- Given 로그인하지 않은 방문자, 로그인한 사용자
- When 방문자가 `/partner-activities`를 열고, 사용자가 상단 메뉴 "파트너 Activity"를 누른다
- Then 방문자는 `/login`으로 가고 사용자는 파트너 Activity 화면에 온다

### PA-058 검색 폼은 Deal 없이 네 조건과 검색·초기화이고 텍스트 칸은 서버 길이로 제한된다
- Given 화면
- When 검색 폼을 본다
- Then 칸은 파트너·미팅 날짜·미팅 내용·작성자(Deal 칸 없음)와 "검색"·"초기화"이고 파트너는 최대 200자, 미팅 내용은 최대 100자다

### PA-059 파트너 일부 글자로 검색하면 URL에 쓰이고 텍스트 칸 Enter로도 검색된다
- Given 시드
- When 파트너에 회사명 일부를 쓰고 "검색"을 누르고, 다른 값을 쓰고 Enter를 누른다
- Then 각각 그 회사의 기록만 보이고 주소에 `partner=<값>`이 있다

### PA-060 작성자로 검색하고 선택지에 퇴사자가 있다
- Given 퇴사한 작성자의 기록이 있는 시드
- When 작성자 선택지에서 퇴사자를 고르고 검색한다
- Then 선택지에 퇴사자가 있고 그 사람의 기록만 보이며 주소에 `author=<id>`가 있다

### PA-061 조건은 AND이고 %·_ 는 글자이며 맞는 기록이 없으면 빈 문구다
- Given 시드와 내용에 "%"·"_"가 든 기록
- When 파트너와 작성자를 함께, 내용 "%"로, 맞는 것이 없는 내용으로 각각 검색한다
- Then 둘 다 맞는 기록만, "%"가 든 기록만, "기록된 미팅이 없습니다."가 보인다

### PA-062 틀린 날짜면 검색하지 않고 칸 문구를, 역전 범위면 서버 문구 배너를 보인다
- Given 직접 지정을 고른 검색 폼
- When 시작에 "2026021"(덜 침)을 쓰고 검색하고, 다음에 시작 2027-03-10·끝 2027-03-01로 검색한다
- Then 첫 검색은 요청·주소 변경 없이 시작 칸에 날짜 문구가 보이고, 둘째는 목록 오류 배너에 "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."가 보인다

### PA-063 검색하면 첫 쪽부터이고 주소로 조건·결과를 복원하며 초기화는 모든 조건과 주소를 지운다
- Given 12건을 모두 읽은 화면
- When 조건을 검색하고, 조건이 든 주소로 새로 열고, "초기화"를 누른다
- Then 검색 뒤 첫 쪽부터 다시 읽고, 주소로 연 화면은 칸 값과 결과가 그 조건이며, 초기화하면 모든 칸이 비고 주소에 쿼리가 없다

### PA-064 정렬만 바뀌면 검색 전 입력이 남고 주소가 바깥에서 바뀌면 칸이 따라간다
- Given 파트너 칸에 검색하지 않은 글자를 쓴 상태
- When 열 머리글로 정렬을 바꾸고, 다음에 뒤로 가기로 다른 조건 주소로 돌아간다
- Then 정렬 뒤에도 쓴 글자가 남고, 주소가 바뀌면 칸이 그 주소의 조건으로 바뀐다

### PA-065 네 열 머리글로 정렬하고 기본 미팅 날짜 내림차순, 새 열은 오름차순부터 다시 누르면 반대다
- Given 시드
- When 머리글을 보고, "파트너"를 두 번, "미팅 날짜"를 두 번 누른다
- Then 네 열이 정렬 버튼이고 처음엔 미팅 날짜 내림차순 표시이며, 파트너는 오름차순 → 내림차순(`sort=partner`, `order=asc` → 없음), 미팅 날짜는 오름차순(`order=asc`) → 내림차순(정렬 키 없음)이다

### PA-066 정렬을 바꾸면 첫 10건부터이고 주소의 정렬을 복원하며 검색해도 정렬이 유지된다
- Given 12건을 모두 읽은 화면
- When 정렬을 바꾸고, `?sort=content&order=asc`로 열고, 그 상태에서 조건을 검색한다
- Then 정렬을 바꾸면 그 순서의 10건부터 보이고, 주소의 정렬이 머리글에 표시되며, 검색 뒤에도 `sort=content&order=asc`가 남는다

### PA-067 예전 주소의 deal은 무시하고 sort=deal은 기본 정렬로 열며 Deal을 주소·서버에 쓰지 않는다
- Given 예전 주소 `?deal=20261016-A001`, `?sort=deal&order=asc`
- When 각각 열고, 검색을 한 번 한다
- Then 두 주소 모두 기본 정렬(미팅 날짜 내림차순) 결과이고 서버 요청에 Deal 조건이 없으며, 검색 뒤 주소에 `deal`이 없다

### PA-068 미팅 날짜는 일곱 선택지의 선택 상자이고 서버 프리셋에 없는 키는 비활성이다
- Given 서버 프리셋이 `2w`·`1m`·`2m`·`3m`만 있음
- When 미팅 날짜 선택 상자를 본다
- Then 선택지는 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정이고(날짜 칸 두 개는 기본으로 없음), 최근 6개월만 비활성이다

### PA-069 프리셋을 골라 검색하면 서버에 다시 물은 날짜를 URL·요청에 쓰고 그 날짜가 오늘의 프리셋이면 프리셋으로 보인다
- Given 서버 날짜 2027-03-15, 처음 받은 `1m` = 2027-02-15~2027-03-15, 검색할 때 다시 받은 `1m` = 2027-02-16~2027-03-16
- When "최근 1개월"을 고르고 검색한다
- Then 프리셋을 한 번 더 요청하고, 주소는 `from=2027-02-16&to=2027-03-16`(프리셋 이름 없음)이며 요청 `date_from`·`date_to`도 같고, 선택 상자는 "최근 1개월"이다

### PA-070 프리셋 다시 묻기가 실패하면 배너와 함께 조건을 바꾸지 않고 프리셋을 못 읽으면 모두 비활성이다
- Given 주소에 날짜가 있는 화면, 다시 묻기 실패, 별도로 처음부터 프리셋 조회 실패
- When 프리셋을 골라 검색하고, 프리셋을 못 읽은 화면을 연다
- Then 첫 경우는 폼에 오류 배너가 보이고 주소·결과가 그대로이며, 둘째는 오류 배너와 함께 프리셋 선택지가 모두 비활성이다

### PA-071 직접 지정을 골라야 날짜 칸이 보이고 한쪽만으로 검색되며 프리셋으로 바꾸면 칸이 사라진다
- Given 화면
- When "직접 지정"을 고르고 시작만 넣어 검색하고, 끝만 넣어 검색하고, 다음에 프리셋을 고른다
- Then 직접 지정을 고른 뒤에만 시작·끝 칸이 보이고, 시작만이면 그날 이후, 끝만이면 그날까지(그날 포함) 기록이며 주소에는 넣은 쪽만 있고, 프리셋을 고르면 날짜 칸이 사라진다

### PA-072 전체는 날짜 조건을 지우고 초기화하면 전체로 돌아간다
- Given 날짜 조건으로 검색한 화면, 프리셋을 고른 화면
- When "전체"를 고르고 검색하고, 초기화한다
- Then 주소와 요청에서 `from`·`to`가 빠지고 선택 상자는 "전체"이며, 초기화 뒤에도 "전체"다

### PA-073 주소로 열면 오늘의 프리셋과 같을 때만 프리셋이고 그 밖은 직접 지정이며 프리셋을 못 읽어도 날짜로 검색한다
- Given 서버 날짜 2027-03-15
- When 오늘의 `1m`과 같은 날짜, 어느 프리셋과도 다른 날짜, `from`만 있는 주소, 전날의 `1m` 날짜, 프리셋 조회 실패 상태의 날짜 주소, 예전 두 날짜 칸 시절 주소로 각각 연다
- Then 첫 주소만 "최근 1개월"이고 나머지는 "직접 지정"과 그 날짜 칸이며, 모든 경우 주소 날짜로 검색해 같은 결과를 보인다

### PA-074 직접 지정으로 검색한 날짜는 프리셋 범위와 같아도 직접 지정으로 남고 다시 받은 프리셋에 키가 없으면 날짜 없이 검색한다
- Given 직접 지정으로 오늘의 `1m`과 같은 날짜를 넣음, 별도로 다시 받은 프리셋에 `6m`이 없음
- When 검색하고 이어서 파트너만 바꿔 다시 검색하고, 별도로 "최근 6개월"을 고른 상태에서 검색한다
- Then 직접 지정과 날짜 칸이 그대로이고 두 번째 검색도 친 날짜를 그대로 보내며, `6m` 경우는 날짜 조건 없이 나머지 조건으로 검색한다. 바깥에서 연 주소가 프리셋 범위와 같으면 프리셋으로 보인다

### PA-075 입력 팝업은 빈 행 하나·파트너 포커스·오늘 날짜로 열리고 admin도 열며 user에게는 버튼이 없다
- Given 서버 날짜 2027-03-15
- When KIM과 ROOT가 "미팅 내용 입력"을 누르고, VIEWER가 화면을 본다
- Then 팝업 "미팅 내용 입력"에 행 "미팅 1" 하나, 파트너 칸에 포커스, 미팅 날짜 칸은 오늘이며, VIEWER에게는 버튼이 없다

### PA-076 행 추가는 오늘 날짜 행을 더하고 행 삭제는 번호를 다시 매기며 50행을 넘기지 않는다
- Given 열린 팝업
- When "행 추가"를 두 번 누르고 2번 행을 지우고, 다음에 50행이 될 때까지 더한 뒤 한 번 더 누른다
- Then 새 행 날짜는 오늘이고 지운 뒤 행 이름은 "미팅 1"·"미팅 2"이며, 행이 하나뿐이면 "행 삭제"가 비활성이고, 51번째는 더해지지 않고 "한 번에 50건까지 입력할 수 있습니다."가 보인다

### PA-077 파트너 칸은 등록된 회사 목록을 친 글자로 좁히고 고르면 날짜 칸으로 가며 행마다 따로다
- Given 파트너 회사 목록
- When 1번 행 파트너 칸에 글자를 치고 항목을 고르고, 2번 행에서 다른 회사를 고른다
- Then 선택지는 등록된 파트너 회사이고 친 글자로 좁혀지며, 고르면 그 행의 날짜 칸으로 포커스가 가고, 2번 행의 선택은 1번 행을 바꾸지 않는다. 행의 칸 순서는 파트너·미팅 날짜·미팅 내용이고 Deal 칸이 없다

### PA-078 목록 글자를 그대로 치고 Enter면 고른 것으로 보고 없으면 "목록에서 선택하세요."다
- Given 파트너 회사 "HanbitCo"
- When `"  hanbitco "`를 치고 Enter, 다음에 없는 글자를 치고 Enter, 다음에 글자를 고친다
- Then 첫 Enter는 "HanbitCo"를 고른 것으로 보고 날짜 칸으로 가며 그 행은 저장 때 다시 고르라고 하지 않고, 없는 글자는 "목록에서 선택하세요."를 보이고 고치거나 목록에서 고르면 문구가 사라진다. Enter 없이 친 글자만으로는 저장 때 "파트너를 선택하세요."다

### PA-079 날짜 Enter·달력 선택은 내용 칸으로 가고 덜 친 날짜는 머물며 콤보박스 Enter는 상태대로 움직인다
- Given 파트너를 고른 행
- When 날짜 칸에 `20270310`+Enter, 달력에서 날짜 선택, `2027031`+Enter를 각각 하고, 파트너 칸에서 목록이 닫힌 채 Enter와 목록이 열린 채 Enter를 누른다
- Then 앞의 둘은 내용 칸으로 가고(날짜 2027-03-10), 덜 친 날짜는 날짜 칸에 머물고 문구가 보이며, 닫힌 콤보박스 Enter는 날짜 칸으로, 열린 목록 Enter는 활성 항목을 고른다

### PA-080 내용 칸 Enter는 빠진 칸·다음 행·새 행 순으로 가고 Shift+Enter는 줄바꿈, 한글 조합 Enter는 무시한다
- Given 행 1(완성), 별도로 행 1·2가 있는 팝업, 파트너를 고르지 않은 행, 날짜가 틀린 행, 50행 팝업
- When 각 행의 내용 칸에서 Enter, Shift+Enter, 한글 조합 중 Enter를 누른다
- Then 마지막 완성 행은 오늘 날짜의 새 행을 더하고 그 파트너로, 다음 행이 있으면 다음 행 파트너로, 빠진 칸이 있으면 그 행의 첫 빠진 칸(파트너 → 틀린 날짜 → 내용)으로 가고, Shift+Enter는 줄바꿈만 넣고, 조합 중 Enter는 아무것도 하지 않으며, 50행에서는 행을 더하지 않고 안내를 보인다

### PA-081 저장하면 빈 행을 건너뛴 N건이 저장되고 팝업이 닫히며 알림과 함께 목록 맨 위에 보인다
- Given 완성 행 2개와 빈 행 1개, 줄바꿈이 든 내용
- When "저장"을 누르고, 다시 "미팅 내용 입력"을 연다
- Then 팝업이 닫히고 "미팅 2건을 저장했습니다."가 보이며, 두 기록이 목록 맨 위에 작성자 = 로그인 사용자·줄바꿈 그대로 보이고, 다시 연 팝업은 빈 행 하나다

### PA-082 저장 전 검사는 모든 행이 비면 안내하고 빠진 칸 문구와 첫 칸 포커스를 보이며 요청하지 않는다
- Given (1) 손대지 않은 행만 있음 (2) 내용만 쓴 행 (3) 파트너 글자만 친 행 (4) 날짜를 지운 행 (5) 틀린 날짜 행
- When 각각 "저장"을 누르고, (2)의 빈 칸을 채운다
- Then (1)은 요청 없이 "입력한 미팅이 없습니다.", (2)는 "파트너를 선택하세요."와 파트너 칸 포커스, (3)은 "파트너를 선택하세요.", (4)는 "미팅 날짜를 입력하세요.", (5)는 날짜 칸 문구와 날짜 칸 포커스이며 어느 경우도 요청하지 않는다. 내용 문구는 textarea의 접근성 설명이고, 칸을 채우면 그 문구가 사라진다

### PA-083 서버가 거절하면 입력을 유지하고 거절된 행·칸에 서버 문구를, 위치 없는 실패는 팝업 배너를 보인다
- Given 1번 빈 행, 2번 정상 행, 3번 행의 회사가 그 사이 목록에서 사라짐, 별도로 서버가 403을 돌려주는 상황
- When "저장"을 누른다
- Then 아무것도 저장되지 않고 팝업과 입력이 그대로이며 3번 행 파트너 칸 아래에 "등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요."가 보이고 그 칸에 포커스가 간다(요청 항목 1번 = 화면 3번 행). 403은 팝업 안 오류 배너다. 보낸 각 항목은 세 값만이다

### PA-084 빈 팝업은 바로 닫히고 입력이 있으면 버릴지 묻는다
- Given 손대지 않은 팝업(기본 날짜만), 내용을 쓴 팝업
- When 빈 팝업을 "취소"·Esc로 닫고, 쓴 팝업을 Esc로 닫으려다 "계속 입력", 다시 닫으려다 "버리기"를 누른다
- Then 빈 팝업은 바로 닫히고, 쓴 팝업은 "입력 취소"/"입력한 내용을 버릴까요?"를 띄우며 "계속 입력"은 입력을 그대로 두고 "버리기"는 두 대화상자를 닫고 다시 열면 빈 행이다

### PA-085 수정 팝업은 저장값 한 행이고 내용 Enter는 저장 버튼으로 가며 저장하면 닫히고 새 위치에 보인다
- Given KIM이 자기 기록과 남의 기록이 있는 목록을 봄, ROOT도 같은 목록
- When KIM이 자기 행 "수정"을 눌러 날짜·내용을 바꾸고(내용 칸 Enter 포함) 저장하고, ROOT가 남의 기록을 고친다
- Then 팝업 "미팅 수정"은 저장값으로 채운 한 행이고 "행 추가"가 없으며 내용 칸 Enter는 "저장"으로 포커스를 옮기고, 저장하면 닫혀 그 기록이 새 날짜 위치에 새 내용으로 보이며, 보낸 본문은 세 값뿐이다. ROOT의 수정도 저장된다

### PA-086 수정 팝업은 빈 내용·틀린 날짜를 막고 다른 파트너를 골라도 날짜·내용을 유지하며 서버 오류를 보인다
- Given 수정 팝업
- When 내용을 비우고 저장하고, 날짜를 틀리게 쓰고 저장하고, 다른 파트너를 고르고, 연락처 회사명이 바뀐 뒤 내용만 고쳐 저장하고, 그 사이 지워진 기록을 저장하고, "취소"를 누른다
- Then 빈 내용은 요청 없이 "미팅 내용을 입력하세요."(textarea 설명), 틀린 날짜는 문구와 날짜 칸 포커스, 다른 파트너를 골라도 날짜·내용은 그대로, 회사명이 바뀐 경우는 저장되고, 지워진 기록은 팝업 안 "미팅 기록을 찾을 수 없습니다.", 취소는 저장 없이 닫힌다

### PA-087 삭제는 확인 뒤 지우고 취소하면 남기며 이미 지워졌으면 대화상자에 서버 문구를 보인다
- Given KIM 자기 기록, ROOT, 이미 지워진 기록
- When "삭제"를 눌러 확인 창을 보고 취소하고, 다시 확인하고, ROOT가 남의 기록을 지우고, 지워진 기록을 확인한다
- Then 확인 창은 "미팅 기록 삭제"/"이 미팅 기록을 삭제할까요?"이고, 취소하면 기록이 남고, 확인하면 지우는 동안 다른 행이 보이다가 그 기록이 사라지고 다음 기록이 보이며, ROOT도 지우고, 지워진 기록은 대화상자 안에 "미팅 기록을 찾을 수 없습니다."가 보인다

### PA-088 등록·수정·삭제 뒤 목록 첫 쪽을 한 번만 다시 요청한다
- Given 목록을 읽은 화면(목록 요청 spy)
- When 등록, 수정, 삭제를 각각 성공시킨다
- Then 각 동작 뒤 목록 요청(offset 0)이 정확히 한 번씩 나가고 화면에 결과가 반영된다

### PA-089 게이트웨이 목록은 값 있는 조건만 snake_case로 보내고 응답을 화면 모양으로 바꾼다
- Given 조건 없는 질의와 `{partner, content, dateFrom, dateTo, authorId, sort: 'author', order: 'asc'}` 질의, 퇴사 작성자가 든 응답
- When `partnerMeetings.list(query, 10, 10)`을 부른다
- Then 첫 요청은 `sort=meeting_date&order=desc&offset=10&limit=10`뿐이고, 둘째는 `partner`·`content`·`date_from`·`date_to`·`author_user_id`·`sort=author`·`order=asc`이며 Deal 조건이 없고, 응답 항목은 camelCase이고 퇴사 작성자는 status `resigned`, 422 역전 범위는 서버 문구의 `ApiError`다

### PA-090 게이트웨이 등록·수정·삭제는 세 키 본문을 보내고 422 위치 위반을 itemErrors로 옮긴다
- Given 입력 두 건, 수정 입력, 서버 응답(201·200·204·422 `invalid-value`+`errors`·422 `request-validation`·403)
- When `create`·`update`·`remove`를 부른다
- Then `POST {items:[{partner_company, meeting_date, content}…]}`·`PUT /partner-meetings/{id}`(세 키)·`DELETE`(204 성공)이고 본문에 Deal이 없으며 생성 항목은 순서대로 바뀐다. `invalid-value`의 위반은 `problem.itemErrors`(위치·문구)로 옮겨지고 문구에 필드 접미사가 없으며, `request-validation`은 필드 설명이 붙은 PL-R37 문구 그대로, 403은 서버 문구다. Deal 선택지 함수는 없다

### PA-091 Fake 게이트웨이는 권한·판정 순서·일괄 위반·요청 형식 오류에서 서버와 같은 결과를 낸다
- Given Fake 게이트웨이(시드 12건, 기본 정렬 순서), 계약 테스트 묶음
- When 남의 기록 수정·삭제, 없는 기록·남의 기록·틀린 입력 조합, 틀린 행이 섞인 일괄 등록, Deal 없는 회사 등록, 회사를 그대로 둔 날짜 수정, Deal 삭제, 빈 목록·51건 등록, 형식이 틀린 날짜(`2027-02-30`·`20270310`·`abc`)가 든 등록과 없는 기록에 대한 같은 날짜의 수정, NUL이 든 내용의 등록을 차례로 한다
- Then 작성자·admin만 수정·삭제되고 404 → 403 → 422 순서이며, 일괄 위반은 모든 위치와 함께 아무것도 저장하지 않고, Deal 없는 회사도 등록되며, 회사를 그대로 두면 회사 목록을 다시 보지 않고, Deal을 지워도 미팅이 남고 삭제 영향에 미팅 건수가 없으며, 빈 목록·51건·형식이 틀린 날짜는 서버와 같은 422 `request-validation`(문구 "요청 형식이 올바르지 않습니다", 행 위치 `itemErrors` 없음, 아무것도 저장하지 않음)이고 형식이 틀린 수정은 없는 기록이어도 404보다 이 422가 먼저이며, NUL 내용은 위치 `["items", 0, "content"]`의 "미팅 내용에는 NUL 문자를 쓸 수 없습니다"다. 예전 Fake 문구 "입력한 미팅이 없습니다."·"한 번에 50건까지 입력할 수 있습니다."·"날짜 형식이 올바르지 않습니다."는 나오지 않는다(Fake를 서버 동작에 맞춤, 2026-11-11 결정). user 쓰기 403은 상태만 확인하고 문구는 단언하지 않는다

### PA-092 canEditMeeting은 admin 모두·sales 본인만 참이고 user는 거짓이다
- Given 작성자 id 7
- When viewer `{admin, 1}`, `{sales, 7}`, `{sales, 8}`, `{user, 7}`로 부른다
- Then 참, 참, 거짓, 거짓이다

### PA-093 Fake 목록 조회는 서버처럼 범위 밖 날짜·긴 텍스트·NUL 조건을 거절한다
- Given Fake 게이트웨이(시드 12건), VIEWER(user) 로그인
- When `list`를 `dateFrom` `1899-12-31`, `dateTo` `3000-01-01`, `dateFrom` `3000-01-01`·`dateTo` `1899-12-31`(범위 밖이며 역전), 201자 `partner`, 101자 `content`, NUL이 든 `content`, 200자 `partner`, 100자 `content`로 각각 부른다
- Then 범위 밖 날짜 세 경우는 422 "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(역전 문구가 아님), 201자 파트너·101자 내용은 422 "요청 형식이 올바르지 않습니다", NUL 내용은 422(입력 위반)이고, 200자 파트너·100자 내용은 오류 없이 빈 쪽(`total` 0)이다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-11 | 최초 작성(구현된 동작을 정본으로 옮김, 초안). functional `tests/functional/partner_meetings/` 5개 파일의 시나리오를 케이스로 흡수 | PA-001~PA-092 |
| 2026-11-11 | 사용자 결정 반영(추천대로): frontend Fake를 서버 동작에 맞춤(PA-R42 — 빈 목록·51건·형식이 틀린 날짜는 요청 형식 422, 내용 NUL, 목록 날짜 범위·텍스트 길이·NUL), 유스케이스 빈 목록 거절은 내부 방어로 유지(PA-R4), Deal 삭제 시 PA 관점은 PA-044·키 목록 정본 DD-R22, 공통 부품 참조를 UI 번호로·`PeriodField`는 NA-R26으로 | 변경: PA-091(형식 오류·NUL·수정 판정 순서 기대 결과), 신규: PA-093 |
