# 고객·파트너 연락처   (feature 코드: CT, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/web/routers/contacts.py`, `app/web/schemas/contact.py`, `app/application/contact/*.py`, `app/application/deal/contact_change_log.py`, `app/application/ports/contact_repository.py`, `app/domain/contact/*.py`, `app/domain/common/{contact,validation}.py`, `app/domain/deal/history.py`의 `contact_info_text`·`contact_change_target`, `app/infra/db/{contact_repository,contact_usage,models_contact}.py`, `frontend/src/features/admin/contacts/*.tsx`, `shared/contact/*.tsx`, `shared/model/contactRules.ts`, `data/contacts.ts`, `gateway/http/contacts.ts`, `gateway/http/mappers/contact.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 Fake·테스트가 어긋나는 점은 계획(`artifacts/10-analysis/ct-plan.md`)의 확인 필요 질문으로 분리했습니다.

## 1. 개요

- 목적: Deal의 고객·파트너 담당자(명함) 정보를 한 곳(`contacts`)에 두고, admin이 등록·수정·삭제하며, Deal 화면이 회사 → 담당자 순으로 고를 수 있게 한다. 같은 사람이 두 번 등록되지 않게 막고, 연락처를 고치면 그 연락처를 쓰는 모든 Deal의 History에 남긴다.
- 사용자(역할): admin(관리 목록·등록·수정·삭제), sales·user(회사 목록·회사별 담당자 조회만).
- 범위
  - Admin > contacts 관리 화면(`/admin/contacts`): 구분 필터·키워드 검색·페이지·등록·수정·삭제
  - API `GET·POST /contacts`, `PUT·DELETE /contacts/{contact_id}`, `GET /contacts/companies`, `GET /contacts/by-company`
  - 입력 값 규칙(공백 거부·형식), 같은 사람 판정(3단계), 참조 Deal 수, 참조 중 삭제 거부, 연락처 변경 시 Deal History 기록(CT-R10)
  - 연락처 선택기 `ContactPicker`(회사명 → 담당자 → 직급·이메일·전화)와 화면 입력 규칙(`contactRules.ts`, `useWhitespaceGuard`)
  - 폐지된 `/customers*`·`/partners*` API 경로가 없음
- 범위 밖(다른 feature)
  - Deal 저장 때 고객·파트너 연결, 선택기 값(`ContactDraft`)으로 새 연락처 생성·같은 사람 병합(`merge_same_person`)·파트너 링크 활성/비활성 → DE (DE는 같은 사람 판정 CT-R7과 변경 이력 CT-R10을 번호로 가리킨다)
  - Deal 상세의 연락처 카드·인라인 수정·History 탭 표시 → DD
  - 파트너 Activity의 파트너 회사 목록 사용 → PA
  - 공통 권한 판정·CSRF·Problem 형식·id 경로 형식·NUL 공통 원칙·Admin 화면 가드·Admin 메뉴 이름 → PL(PL-R2, PL-R4, PL-R5, PL-R7, PL-R9~R13, PL-R15, PL-R16, PL-R31, PL-R35, PL-R37~R39)
  - 시각 표기 → TM, 페이저(UI-R30)·콤보박스(UI-R18~R21) 등 공통 컴포넌트 자체 → UI
- 관련 화면·메뉴: Admin > contacts 관리(`/admin/contacts`, Admin 서브 메뉴 "contacts 관리" — PL-R35). Deal 등록·수정 폼과 Deal 상세 인라인 수정이 `ContactPicker`를 쓴다(DE·DD).

## 2. 명세 (SDD)

### 2026-11-26 회사명 공백 허용 (사용자 요청 확정)

회사명은 내부 공백을 포함한 원문 표기를 보존하며 UI 입력 차단·API 공백 검사·DB `no_space` 검사에서 제외한다. 아래 기존 규칙의 회사명 공백 거부 설명을 대체한다. 담당자명·이메일·전화의 공백 금지는 유지한다. Excel 가져오기 파트너 연락처는 담당자명이 빈 문자열일 수 있으며 조회 시 보존한다. 일반 연락처/Deal 입력에서는 담당자명 필수 규칙을 유지한다.

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 연락처 | 고객 또는 파트너 회사의 담당자 한 명(명함). `contacts` 한 행 |
| 종류(kind) | `customer`(고객) 또는 `partner`(파트너). 만든 뒤 바꾸지 않는다 |
| 같은 사람 | 같은 종류 안에서 회사명·담당자명이 대소문자 무시로 같고 이메일 규칙(CT-R7)을 만족하는 연락처 |
| 동명이인 | 회사명·담당자명이 같지만 둘 다 이메일이 있고 서로 다른 연락처. 따로 저장된다 |
| 참조 Deal | 그 연락처를 고객(`deals.customer_id`)으로 쓰거나 파트너 링크(`deal_partners.contact_id`, 해제된 비활성 링크 포함)로 가진 Deal |
| 참조 Deal 수(`deal_count`) | 참조 Deal의 개수. 한 Deal이 같은 연락처를 고객과 파트너로 둘 다 참조해도 1 |
| 연락 정보 | 직급·이메일·전화(History 문구에 쓰는 세 값) |
| 선택기 | `ContactPicker`. Deal 화면에서 회사명 → 담당자를 고르거나 새로 입력하는 입력 묶음. 결과는 `ContactDraft {contactId, company, name, title, email, phone}` |

### 2.2 데이터 모델

`contacts`(PK `id` BIGINT identity — SC 공통 규칙, 감사 컬럼 `created_at`·`updated_at` timestamptz)

| 컬럼 | 타입·제약 | 뜻 |
| --- | --- | --- |
| `kind` | varchar(10), CHECK `kind in ('customer','partner')` | 종류 |
| `company` | varchar(200) NOT NULL | 회사명(입력 표기 그대로) |
| `name` | varchar(100) NOT NULL | 담당자명(입력 표기 그대로) |
| `title` | varchar(100) null | 직급(앞뒤 공백 제거, 내부 공백 허용) |
| `email` | varchar(254) null | 이메일(소문자) |
| `phone` | varchar(40) null | 전화(입력 표기 그대로) |

- CHECK `no_space`: `company`·`name`·`email`·`phone`에 공백 문자(`\s`)가 없다(NULL은 통과).
- 인덱스: `(kind, lower(company))`, `(kind, lower(company), lower(name))`, `(created_at, id)`. 같은 사람 중복을 막는 DB 유니크 제약은 없다 — 유스케이스가 `(kind, lower(company), lower(name))` 단위 트랜잭션 잠금을 잡은 뒤 다시 확인한다.
- 참조 FK(RESTRICT): `deals.customer_id → contacts.id`(`fk_deals_customer_id_contacts`), `deal_partners.contact_id → contacts.id`(`fk_deal_partners_contact_id_contacts`). 소유는 DE.
- 예전 `customers`·`partners` 테이블은 없다.
- 값 객체: `ContactKind`(선언 순서 고객 → 파트너가 목록 정렬 순서), `ContactDetails{company, name, title, email: Email|null, phone: PhoneNumber|null}`(모든 값이 같아야 "같은 값"), `Email`, `PhoneNumber`.

### 2.3 비즈니스 규칙

입력 값(등록·수정 공통)
- **CT-R1** 종류는 `customer`·`partner` 둘뿐이다. 등록 때 필수이고(누락·다른 값은 422 `request-validation`), 만든 뒤 바꿀 수 없다: 수정 본문에 `kind`가 있으면 422 `request-validation`이고 종류는 그대로다.
- **CT-R2** 회사명·담당자명은 필수이고 **잘라 내지 않는다**. 빈 문자열이면 422 `invalid-value` "회사명을 입력하세요."·"담당자명을 입력하세요.", 공백 문자(스페이스·탭·줄바꿈·전각 공백 등 `\s`)가 앞·뒤·가운데 어디든 하나라도 있으면 "공백은 입력할 수 없습니다.", 회사명 201자 이상은 "회사명은(는) 200자를 넘을 수 없습니다", 담당자명 101자 이상은 "담당자명은(는) 100자를 넘을 수 없습니다", NUL 문자는 "회사명에는 NUL 문자를 쓸 수 없습니다"·"담당자명에는 NUL 문자를 쓸 수 없습니다". 회사명 200자·담당자명 100자는 저장된다. 표기(대소문자)는 입력 그대로 저장한다.
- **CT-R3** 직급은 선택이다. 앞뒤 공백을 지우고 내부 공백은 그대로 둔다("  팀장  " → "팀장", "수석 과장" 그대로). 빈 문자열·공백뿐·null·생략은 직급 없음(null)이다. 지운 뒤 101자 이상이면 422 `invalid-value` "직급은(는) 100자를 넘을 수 없습니다", NUL은 "직급에는 NUL 문자를 쓸 수 없습니다".
- **CT-R4** 이메일은 선택이다. 빈 문자열·null·생략은 이메일 없음(null)이다. 공백 문자가 하나라도 있으면(공백뿐인 값 포함) "공백은 입력할 수 없습니다."이고, 그 밖에는 소문자로 바꾼 값이 254자 이하이고 `^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$`에 맞아야 한다(아니면 "이메일 형식이 올바르지 않습니다."). NUL은 "이메일에는 NUL 문자를 쓸 수 없습니다". 저장 값은 소문자다(`Kim@Neoine.Example` → `kim@neoine.example`).
- **CT-R5** 전화는 선택이다. 빈 문자열·null·생략은 전화 없음(null)이다. 공백 문자가 하나라도 있으면(공백뿐인 값 포함) "공백은 입력할 수 없습니다."이고, 그 밖에는 40자 이하, 문자는 숫자·`+`·`-`·`(`·`)`만, 숫자가 7~15개여야 한다(아니면 "전화번호 형식이 올바르지 않습니다."). NUL은 "전화번호에는 NUL 문자를 쓸 수 없습니다". 입력 표기 그대로 저장한다.
- **CT-R6** 입력 판정 순서(앞에서 걸리면 뒤는 보지 않는다): ① 요청 형식 422 `request-validation`(필수 키 누락, 문자열이 아닌 값, 모르는 필드 — 예전 고객 API의 `company_name`·`contact_name`·`employee_count`·`notes` 포함, 수정 본문의 `kind`) → ② 회사명·담당자명·이메일·전화 중 하나라도 공백 문자 → ③ 이메일(NUL·형식) → ④ 전화(NUL·형식) → ⑤ 회사명(NUL·빈 값·길이) → ⑥ 담당자명(NUL·빈 값·길이) → ⑦ 직급(NUL·길이) → (수정만) ⑧ 없는 연락처 404 → ⑨ 같은 사람 409(CT-R7). ②~⑦은 모두 422 `invalid-value`이고 칸 위치(`errors`)는 싣지 않으며, 어떤 경우에도 `detail`에 DB 드라이버 문구가 없다(PL-R16). 거절되면 아무것도 저장되지 않는다.

같은 사람
- **CT-R7** 같은 종류 안에서 회사명과 담당자명이 **대소문자 무시로** 같은 기존 연락처(후보) 중에서 다음 순서로 같은 사람을 찾는다: ① 입력에 이메일이 있으면 이메일이 같은(대소문자 무시) 후보 ② 없으면 이메일이 없는 후보(기존 연락처에 이메일을 채워 넣는 경우) ③ 입력에 이메일이 없으면 후보 중 첫째. 동률은 id가 작은 것. 같은 사람이 있으면 409 `already-exists` "이미 등록된 연락처입니다."이고 저장되지 않는다. 즉 둘 다 이메일이 있고 서로 다르면 동명이인이라 저장된다. 종류가 다르면 같은 회사명·담당자명이어도 별개다. 수정은 자기 자신을 후보에서 뺀다(자기 표기의 대소문자만 바꾸거나 다른 값만 바꾸는 것은 충돌이 아니다). 대소문자 비교는 DB의 `lower()` 기준이다(특수 대문자도 같게 본다). 같은 사람의 등록·수정은 `(종류, lower(회사명), lower(담당자명))` 단위 잠금 안에서 판정한다.

등록·수정
- **CT-R8** 등록 `POST /contacts`(admin 전용): 성공하면 201, `Location: /api/v1/contacts/<id>`, 본문 `ContactResponse`(2.6). `created_at`과 `updated_at`은 같은 서버 시각이다. 등록한 연락처는 관리 목록(CT-R13)과 조회(CT-R14·R15)에 바로 나온다.
- **CT-R9** 수정 `PUT /contacts/{contact_id}`(admin 전용)은 **전체 교체**다: 본문의 회사명·담당자명은 필수이고, 직급·이메일·전화는 보내지 않거나 null이면 지운다. id·종류·`created_at`은 그대로이고 `updated_at`은 서버 시각이 된다(값이 하나도 바뀌지 않아도 갱신된다). 없는 연락처는 404 `not-found` "연락처를 찾을 수 없습니다.". 응답은 200 `ContactResponse`.
- **CT-R10** 연락처 변경 이력: 수정으로 값(`ContactDetails` 다섯 값 중 하나라도)이 실제로 바뀌면 그 연락처의 참조 Deal마다, 참조 역할(고객·파트너)마다 한 건씩 Deal History를 남긴다(같은 Deal을 같은 역할로 여러 번 참조해도 한 건). 항목: 분류 `contact`, 대상 "고객 연락처 정보 (<새 회사명> <새 담당자명>)" 또는 "파트너 연락처 정보 (…)", 이전·이후 값 "직급 <직급> · 이메일 <이메일> · 전화 <전화>"(없는 값은 `-`), 변경자 = 요청한 사용자, 시각 = 서버 시각. 이력을 남긴 Deal의 `updated_at`도 같은 서버 시각이 된다. 파트너 링크는 해제된(비활성) 링크도 포함한다. 값이 그대로면 이력도 Deal 시각 변경도 없다. 수정이 거절되면 이력도 없다. 같은 트랜잭션에서 저장된다. (Deal 화면에서 선택기로 연락처 값을 바꿔 저장하는 경로도 이 규칙을 쓴다 — DE.)

참조와 삭제
- **CT-R11** 참조 Deal 수(`deal_count`)는 (연락처, Deal) 쌍의 개수다: 고객 참조와 파트너 링크(비활성 포함)를 합치고 한 Deal은 연락처마다 한 번만 센다. 지워진 Deal은 세지 않는다. 참조가 없으면 0이다.
- **CT-R12** 삭제 `DELETE /contacts/{contact_id}`(admin 전용)는 물리 삭제이며 복구할 수 없다. 판정 순서: 없는 id(이미 지운 id 포함) 404 `not-found` "연락처를 찾을 수 없습니다." → 참조 Deal이 N(≥1)건이면 409 `invalid-state` "연결된 Deal이 N건 있어 삭제할 수 없습니다."(N은 CT-R11 기준)이고 연락처는 그대로다. 참조가 없으면 204(본문 없음)이고 그 연락처만 지워진다. 참조하던 Deal이 모두 지워지면 삭제할 수 있다. 판정 뒤 DB FK가 막은 경우도 같은 409이고 건수를 다시 센다.

조회
- **CT-R13** 관리 목록 `GET /contacts`(admin 전용). 쿼리: `kind`(없으면 둘 다), `keyword`(최대 100자), `offset`(0 이상, 기본 0), `limit`(1~200, 기본 50). 모르는 파라미터(예: `company_name`)·범위 밖 값·모르는 `kind`·101자 이상 키워드는 422 `request-validation`. 키워드는 앞뒤 공백을 지우고 공백뿐이면 조건 없음이며, NUL이 있으면 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다". 키워드는 회사명·담당자명·이메일 중 하나에 대소문자 무시 부분 일치하고(이메일 없는 연락처는 이메일로 맞지 않음) `%`·`_`는 글자 그대로다. 직급·전화는 검색 대상이 아니다. 정렬: 고객 먼저 → `lower(회사명)` → `lower(담당자명)`(둘 다 코드 포인트 순) → id. 필터 뒤에 `offset`·`limit`을 적용한다. 응답 `{items, total, offset, limit}`: `total`은 페이지와 무관한 조건 일치 전체 건수, `offset`·`limit`은 요청 값, 끝을 넘은 페이지는 `items`가 비고 `total`은 그대로다. 항목은 `ContactRowResponse`(= `ContactResponse` + `deal_count`).
- **CT-R14** 회사 목록 `GET /contacts/companies?kind=`(로그인한 모든 역할). `kind` 필수(누락·다른 값 422 `request-validation`). 그 종류의 회사명을 `lower(회사명)`이 같으면 하나로 묶어 돌려주며, 묶음의 표기는 가장 먼저 등록된 연락처(`created_at`, 같으면 작은 id)의 표기다. 정렬은 `lower(회사명)` 코드 포인트 순. 응답은 문자열 배열이고 없으면 `[]`.
- **CT-R15** 회사별 담당자 `GET /contacts/by-company?kind=&company=`(로그인한 모든 역할). `kind`·`company` 필수, `company` 200자 이하(누락·초과·다른 `kind`는 422 `request-validation`). 그 종류에서 회사명이 대소문자 무시로 같은 연락처를 `lower(담당자명)`·id 순으로 돌려준다. 항목은 관리 목록 항목과 같은 필드(`deal_count` 포함, CT-R11)다. 없는 회사는 `[]`.
- **CT-R16** 예전 고객·파트너 API(`/api/v1/customers`, `/api/v1/customers/{id}`, `/api/v1/partners`, `/api/v1/partners/{id}`의 GET·POST·PUT·DELETE)는 없다: admin이 불러도 404(PL-R13)이고 다른 곳으로 보내지 않는다(`Location` 없음).

화면(frontend, `/admin/contacts`, 가드 PL-R31)
- **CT-R17** 관리 화면 틀: 제목(h2) "contacts 관리", 버튼 "연락처 등록", 안내 "Deal에서 쓰는 고객·파트너 연락처(명함) 데이터입니다. 연결된 Deal이 있으면 삭제할 수 없습니다.". 조건 줄: "구분" 선택(전체·고객·파트너, 기본 전체)과 검색 폼(`search` 역할, 칸 "검색어", 버튼 "검색", Enter도 검색). 구분을 바꾸거나 검색하면 첫 페이지부터 다시 조회한다. 검색어는 앞뒤 공백을 지우고 비면 키워드 없이 조회한다. 한 페이지 20건(`limit=20`)이며 전체가 20건을 넘을 때만 페이저를 보인다. 표 머리글 8칸: 구분, 회사명, 담당자명, 직급, 이메일, 전화, 연결 Deal, 작업. 칸 값: 구분은 배지 "고객"·"파트너", 직급·이메일·전화가 없으면 `-`, 연결 Deal은 `deal_count`, 작업은 행마다 "수정"·"삭제"(참조 Deal이 있어도 삭제 버튼은 있음). 읽는 동안 "불러오는 중…". 빈 목록: 구분이나 검색어 조건이 있으면 "조건에 맞는 연락처가 없습니다.", 없으면 "등록된 연락처가 없습니다.". 목록·삭제 오류는 페이지 오류 배너 하나에 서버 문구(PL-R37)로 보인다.
- **CT-R18** 등록·수정 폼(화면 안 카드, form 이름·제목 "연락처 등록"/"연락처 수정", 버튼 "저장"·"취소"): 칸 회사명·담당자명·직급·이메일·전화. 등록은 "연락처 구분" 선택(고객·파트너, 기본 고객), 수정은 구분을 글자로만 보인다(바꿀 수 없음). 수정 폼은 현재 값을 채우고(없는 값은 빈 칸), 참조 Deal이 1건 이상이면 "이 연락처를 쓰는 N개 Deal에 모두 반영됩니다."를 보인다. 회사명·담당자명·이메일·전화는 입력·붙여넣기 중 공백 문자를 바로 지우고 그 칸 아래에 "공백은 입력할 수 없습니다."를 3초 보인다(직급은 공백 허용). 안내 "회사명·담당자명·이메일·전화에는 공백을 입력할 수 없습니다. 이메일은 없어도 됩니다.". "저장"을 누르면 요청 전에 CT-R21 규칙으로 검사해 칸 아래에 문구를 보이고 오류가 있으면 요청하지 않는다. 보내는 값: 직급은 앞뒤 공백을 지우고 빈 직급은 null, 빈 이메일·전화는 null. 성공하면 폼을 닫고 페이지 알림 "연락처를 등록했습니다."/"연락처를 수정했습니다."를 보인다. 서버가 거절하면 폼 위 오류 배너에 서버 문구를 보이고 폼과 입력을 유지한다. "취소"는 요청 없이 닫는다. 폼을 열거나 수정을 시작하면 이전 알림을 지운다.
- **CT-R19** 삭제: "삭제"를 누르면 확인 대화상자(제목 "연락처 삭제", 위험 버튼 "삭제", 문구 "<회사명> <담당자명> 연락처를 삭제할까요? 연결된 Deal이 있으면 삭제할 수 없습니다."). 확인하면 대화상자를 닫고, 성공하면 알림 "<회사명> <담당자명> 연락처를 삭제했습니다."와 함께 목록에서 행이 사라진다. 실패(예: 참조 중 409)하면 페이지 오류 배너에 서버 문구를 보이고 행은 남는다. "취소"는 요청 없이 닫는다.
- **CT-R20** 캐시 갱신: 등록·삭제 성공 뒤 연락처 조회(목록·회사 목록·회사별 담당자)를, 수정 성공 뒤 연락처 조회·Deal 조회·History·파트너 미팅 조회를 다시 읽게 한다. 그래서 연락처를 고치면 Deal 목록 Quick View·Deal 상세에 새 값이 보인다.
- **CT-R21** 화면 입력 규칙(`shared/model/contactRules.ts`, 서버와 같은 경계값): 회사명·담당자명이 빈 값이면 "회사명을 입력하세요."·"담당자명을 입력하세요.", 공백 문자가 있으면 "공백은 입력할 수 없습니다."; 이메일(null이 아닐 때)은 공백 → 공백 문구, 254자 초과·형식 → "이메일 형식이 올바르지 않습니다."; 전화(null이 아닐 때)는 공백 → 공백 문구, `[0-9+\-()]` 밖 문자·숫자 7~15개 밖 → "전화번호 형식이 올바르지 않습니다."; 직급은 검사하지 않는다. 같은 사람 판정 `findSamePerson`은 CT-R7과 같은 3단계 규칙이다.
- **CT-R22** 연락처 선택기 `ContactPicker`(props: 종류, 라벨 접두어 "고객"/"파트너", 값 `ContactDraft`, 폼 오류, `linkedHere`, 콜백, 배치 `stack`|`rows`):
  - 칸: "<라벨> 회사명"(콤보박스) → "<라벨> 담당자명"(콤보박스) → "<라벨> 직급"·"<라벨> 이메일"·"<라벨> 전화".
  - 회사명 후보는 그 종류의 회사 목록(CT-R14)이고 직접 입력도 된다. 담당자 후보는 입력한 회사의 담당자(CT-R15, 회사명이 비면 조회하지 않음)이며 후보 설명은 "직급 · 이메일"(있는 값만)이다.
  - 담당자 후보를 고르면 회사명·담당자명·직급·이메일·전화를 그 연락처 값으로 채우고 `contactId`를 그 id로 둔다. 채운 직급·이메일·전화를 고쳐도 `contactId`는 유지된다(저장 때 그 연락처가 갱신됨 — DE). 담당자명을 대소문자 무시로 다른 이름으로 바꾸면 `contactId`가 풀린다(null). 회사명을 대소문자 무시로 다른 회사로 바꾸면 고른 사람이 있을 때 담당자명·직급·이메일·전화를 비우고 `contactId`를 null로 한다(대소문자만 다르면 유지). 직접 입력한 새 회사·사람은 `contactId` null이다.
  - 회사명·담당자명·이메일·전화는 입력·붙여넣기 중 공백 문자를 지우고 3초 동안 "공백은 입력할 수 없습니다."를 안내로 보인다. 직급은 공백을 허용한다. 이메일·전화를 비우면 값은 null이다.
  - 이메일 칸을 한 번 떠난 뒤 이메일 값이 형식에 맞지 않으면 "이메일 형식이 올바르지 않습니다."를 보인다. 폼이 넘긴 칸별 오류는 그 칸 아래에 `alert`로 보인다(폼 오류가 이메일 형식 안내보다 우선).
  - 새로 입력 중(`contactId` null)이고 이메일이 없으며 회사명·담당자명이 그 회사 담당자 중 같은 사람(CT-R21)이면 "기존 연락처와 같은 사람으로 처리됩니다(회사명·담당자명 일치, 이메일 없음)."를 보인다. 이메일이 있으면 보이지 않는다.
  - 고른 연락처의 참조 Deal 수가 기준(현재 Deal에 이미 연결돼 있으면 2, 아니면 1) 이상이면 "이 연락처는 N개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다."를 보인다.
  - 배치 `stack`(기본): 테두리 묶음과 범례 "<라벨>", 칸 라벨은 전체 글자. `rows`: 범례는 숨기고 보이는 라벨은 "회사"·"담당자"·"직급"·"이메일"·"전화"로 짧게, 접근성 이름은 전체 글자 그대로.
- **CT-R23** 게이트웨이(`gateway/http/contacts.ts`): 회사 목록은 `kind`를, 회사별 담당자는 `kind`·`company`를 보낸다. 관리 목록은 정한 조건(`kind`·`keyword`·`offset`·`limit`)만 보낸다. 등록 본문은 `kind` + 회사명·담당자명·직급·이메일·전화, 수정 본문은 `kind` 없이 같은 다섯 값이며 빈 직급(`''`)은 null로 보낸다. 응답 변환: 직급 null → `''`, `deal_count` → `dealCount`, 시각은 그대로. 삭제는 204를 성공으로 받는다. 오류는 PL-R39대로 `ApiError`(409 문구는 서버 `detail`).

### 2.4 상태와 전이

| 현재 | 행동 | 다음 | 조건 |
| --- | --- | --- | --- |
| (없음) | 등록 | 있음 | CT-R1~R8 |
| 있음 | 수정 | 있음(종류 그대로) | CT-R9, 값이 바뀌면 CT-R10 |
| 있음, 참조 Deal 0 | 삭제 | (없음, 물리 삭제) | CT-R12 |
| 있음, 참조 Deal ≥1 | 삭제 | 있음 | 409(CT-R12) |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /contacts`(관리 목록) | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| `POST /contacts`, `PUT /contacts/{id}`, `DELETE /contacts/{id}` | 401 | 403 관리자 문구 | 403 관리자 문구 | 가능 |
| `GET /contacts/companies`, `GET /contacts/by-company` | 401 | 가능 | 가능 | 가능 |
| 화면 `/admin/contacts` | `/login`으로 | `/deals`로 | `/deals`로 | 열림 |

관리 목록·쓰기는 관리자 가드(PL-R7, "관리자 권한이 필요합니다")이고 쓰기는 CSRF(PL-R9)가 걸린다. 회사 목록·회사별 담당자는 업무 조회(PL-R2)다. 판정 순서는 PL-R4.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/contacts` | query `kind?`, `keyword?`(≤100), `offset`(≥0, 기본 0), `limit`(1~200, 기본 50) | 200 `CountedPage[ContactRowResponse]` `{items, total, offset, limit}` | 422 `request-validation`·`invalid-value` |
| POST `/contacts` | `ContactCreateRequest` `{kind: "customer"\|"partner", company: str, name: str, title?: str\|null, email?: str\|null, phone?: str\|null}` | 201 `ContactResponse` + `Location` | 409 `already-exists`, 422 `invalid-value`·`request-validation` |
| PUT `/contacts/{contact_id}` | `ContactUpdateRequest` `{company: str, name: str, title?: str\|null, email?: str\|null, phone?: str\|null}`(생략 = null) | 200 `ContactResponse` | 404 `not-found`, 409 `already-exists`, 422 |
| DELETE `/contacts/{contact_id}` | — | 204 | 404 `not-found`, 409 `invalid-state`, 422(id 형식) |
| GET `/contacts/companies` | query `kind` | 200 `string[]` | 422 |
| GET `/contacts/by-company` | query `kind`, `company`(≤200) | 200 `ContactRowResponse[]` | 422 |

- `ContactResponse` 필드는 정확히 `id`, `created_at`, `updated_at`, `kind`, `company`, `name`, `title`(null 가능), `email`(null 가능), `phone`(null 가능). `ContactRowResponse` = `ContactResponse` + `deal_count`(정수). 시각 표기는 TM.
- 모든 본문·쿼리는 모르는 키를 거부한다(422 `request-validation`). 공통 오류(401·403·CSRF·id 형식 422)는 PL.

### 2.7 화면 동작

CT-R17~CT-R23.

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 회사명·담당자명·이메일·전화에 공백 문자 | 422 `invalid-value` | 공백은 입력할 수 없습니다. |
| 회사명 / 담당자명 빈 값 | 422 `invalid-value` | 회사명을 입력하세요. / 담당자명을 입력하세요. |
| 회사명 201자 이상 / 담당자명 101자 이상 / 직급 101자 이상 | 422 `invalid-value` | 회사명은(는) 200자를 넘을 수 없습니다 / 담당자명은(는) 100자를 넘을 수 없습니다 / 직급은(는) 100자를 넘을 수 없습니다 |
| NUL 문자 | 422 `invalid-value` | <회사명·담당자명·직급·이메일·전화번호>에는 NUL 문자를 쓸 수 없습니다 |
| 이메일 형식 | 422 `invalid-value` | 이메일 형식이 올바르지 않습니다. |
| 전화 형식 | 422 `invalid-value` | 전화번호 형식이 올바르지 않습니다. |
| 같은 사람 | 409 `already-exists` | 이미 등록된 연락처입니다. |
| 없는 연락처 | 404 `not-found` | 연락처를 찾을 수 없습니다. |
| 참조 중 삭제 | 409 `invalid-state` | 연결된 Deal이 N건 있어 삭제할 수 없습니다. |
| 검색어 NUL | 422 `invalid-value` | 검색어에는 NUL 문자를 쓸 수 없습니다 |
| 요청 형식(누락·모르는 키·범위 밖) | 422 `request-validation` | 요청 형식이 올바르지 않습니다(PL-R12) |

화면 문구: CT-R17~CT-R22(요청 전 검사 문구, 알림, 대화상자, 선택기 안내). 서버 문구 표시는 PL-R37.

## 3. Business use case

### CT-UC1 연락처 목록 보기·찾기
- 행위자: admin
- 사전 조건: admin으로 로그인, `/admin/contacts`
- 기본 흐름: 화면이 첫 페이지(20건)를 읽어 표로 보인다(CT-R13, R17)
- 대안: 구분을 고르거나 검색어로 찾는다, 페이저로 다음 페이지를 본다
- 예외: 목록을 읽지 못하면 오류 배너, 결과가 없으면 빈 메시지
- 결과: 조건에 맞는 연락처와 각 연락처의 참조 Deal 수

### CT-UC2 연락처 등록
- 행위자: admin
- 기본 흐름: 연락처 등록 → 구분·회사명·담당자명·(직급·이메일·전화) → 저장 → 201(CT-R1~R8, R18)
- 예외: 빈 필수 값·형식 오류(화면이 요청 전 거름, 서버 422), 같은 사람 409, 공백 입력(화면이 지움, 서버 422)
- 결과: 관리 목록·선택기 후보에 나오는 새 연락처

### CT-UC3 연락처 수정
- 행위자: admin
- 사전 조건: 연락처가 있음
- 기본 흐름: 수정 → 값 변경 → 저장 → 200(CT-R9, R18)
- 대안: 값이 그대로면 이력 없이 저장
- 예외: 형식 오류 422, 다른 사람과 같아짐 409, 없는 연락처 404
- 결과: 바뀐 값이 그 연락처를 쓰는 모든 Deal에 보이고 각 Deal History에 남는다(CT-R10, R20)

### CT-UC4 연락처 삭제
- 행위자: admin
- 기본 흐름: 삭제 → 확인 → 204(CT-R12, R19)
- 예외: 참조 Deal이 있으면 409(N건 안내), 없는 연락처 404, 취소
- 결과: 참조 없는 연락처가 사라진다

### CT-UC5 Deal 화면에서 연락처 고르기
- 행위자: Deal을 등록·수정하는 sales·admin(조회는 모든 역할 가능)
- 사전 조건: Deal 폼 또는 상세 인라인 수정의 선택기
- 기본 흐름: 회사명 고름 → 그 회사 담당자 고름 → 연락 정보 자동 채움(CT-R14, R15, R22)
- 대안: 새 회사·사람 직접 입력, 채운 값 고침, 같은 사람 안내
- 예외: 공백 입력은 지워지고 안내, 이메일 형식 안내
- 결과: 폼이 저장에 쓸 `ContactDraft`(저장 처리는 DE)

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), VIEWER(user). 기본 입력 예: 고객 "네오인 김철수, 팀장, kim@neoine.example, 010-1234-5678", 파트너 "한빛파트너스 이영희, 이사, lee@hanbit.example, 02-123-4567". backend 케이스는 Fake UoW(연락처·Deal·History Fake)를 쓰는 유스케이스 단위 테스트와 FakeUseCases + TestClient를 쓰는 web 단위 테스트, frontend 케이스는 Fake 게이트웨이를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| CT-001 | admin이 고객·파트너 연락처를 등록하면 201과 Location·문서화된 필드가 오고 목록에 나온다 | CT-R8, CT-R1, CT-UC2 | backend | `application/test_contact_register.py::test_persists_the_contact_and_commits_once`<br>`application/test_contact_register.py::test_partner_kind_is_kept`<br>`web/test_contact_routes.py::test_admin_registers_a_contact_with_201_location_and_documented_fields` |
| CT-002 | 종류·회사명·담당자명만 보내면 직급·이메일·전화는 null로 저장된다 | CT-R3, CT-R4, CT-R5, CT-UC2 | backend | `application/test_contact_input.py::test_missing_email_phone_or_title_stays_none`<br>`web/test_contact_routes.py::test_registration_with_only_required_fields_leaves_optional_ones_null` |
| CT-003 | 이메일은 소문자로 저장된다 | CT-R4, CT-UC2 | backend | `application/test_contact_input.py::test_valid_input_becomes_details_with_value_objects`<br>`application/test_contact_register.py::test_builds_normalized_value_objects`<br>`web/test_contact_routes.py::test_registration_lowercases_the_email` |
| CT-004 | 직급은 앞뒤 공백만 지워지고 빈 값·공백뿐·null은 null이 된다 | CT-R3, CT-UC2 | backend | `application/test_contact_input.py::test_empty_string_email_phone_or_title_becomes_none`<br>`application/test_contact_input.py::test_title_is_trimmed_but_keeps_inner_spaces`<br>`application/test_contact_register.py::test_builds_normalized_value_objects`<br>`web/test_contact_routes.py::test_registration_trims_title_and_turns_blank_title_into_null` |
| CT-005 | 이메일·전화의 빈 문자열은 없는 값으로 저장된다 | CT-R4, CT-R5, CT-UC2 | backend | `application/test_contact_input.py::test_empty_string_email_phone_or_title_becomes_none`<br>`web/test_contact_routes.py::test_registration_treats_empty_email_and_phone_as_missing` |
| CT-006 | 회사명·담당자명·이메일·전화에 공백 문자가 있으면 잘라 내지 않고 422로 거절한다 | CT-R2, CT-R4, CT-R5, CT-R6, CT-UC2 | backend | `application/test_contact_input.py::test_any_whitespace_in_company_name_email_or_phone_is_rejected`<br>`application/test_contact_register.py::test_invalid_input_stores_nothing_and_does_not_commit` |
| CT-007 | 공백뿐인 이메일·전화는 없는 값이 아니라 공백 오류다 | CT-R4, CT-R5, CT-UC2 | backend | `application/test_contact_input.py::test_whitespace_only_email_or_phone_is_rejected_not_treated_as_empty` |
| CT-008 | 회사명·담당자명이 비어 있으면 각자의 문구로 422다 | CT-R2, CT-UC2 | backend | `application/test_contact_input.py::test_empty_company_or_name_is_rejected_with_its_message`<br>`application/test_contact_register.py::test_invalid_input_stores_nothing_and_does_not_commit` |
| CT-009 | 형식이 틀리거나 254자를 넘는 이메일은 422다 | CT-R4, CT-UC2 | backend | `application/test_contact_input.py::test_malformed_email_is_rejected_with_the_format_message`<br>`application/test_contact_input.py::test_email_over_254_characters_is_rejected_and_254_is_accepted`<br>`application/test_contact_register.py::test_invalid_input_stores_nothing_and_does_not_commit` |
| CT-010 | 형식이 틀리거나 숫자 7~15개를 벗어난 전화는 422이고 흔한 형식은 저장된다 | CT-R5, CT-UC2 | backend | `application/test_contact_input.py::test_malformed_phone_is_rejected_with_the_format_message`<br>`application/test_contact_input.py::test_common_phone_formats_are_accepted`<br>`application/test_contact_register.py::test_invalid_input_stores_nothing_and_does_not_commit` |
| CT-011 | NUL 문자가 든 입력은 500이 아니라 422이고 DB 문구가 없다 | CT-R6, CT-UC2 | backend | `application/test_contact_input.py::test_nul_character_is_rejected`<br>`application/test_contact_input.py::test_the_nul_message_names_the_problem_for_text_fields`<br>`web/test_contact_routes.py::test_nul_character_is_422_invalid_value_without_database_wording` |
| CT-012 | 회사명 200자·담당자명 100자·직급 100자는 등록된다 | CT-R2, CT-R3, CT-UC2 | backend | `application/test_contact_input.py::test_values_at_the_length_limits_are_accepted` |
| CT-013 | 회사명 201자·담당자명 101자·직급 101자는 422이고 저장되지 않는다 | CT-R2, CT-R3, CT-UC2 | backend | `application/test_contact_input.py::test_values_over_the_length_limits_are_rejected` |
| CT-014 | 종류·회사명·담당자명 중 하나가 빠지면 422 request-validation이다 | CT-R1, CT-R6, CT-UC2 | backend | `web/test_contact_routes.py::test_registration_without_a_required_field_is_request_validation` |
| CT-015 | 알 수 없는 종류는 422 request-validation이다 | CT-R1, CT-UC2 | backend | `web/test_contact_routes.py::test_registration_with_an_unknown_kind_is_request_validation` |
| CT-016 | 모르는 필드와 예전 고객 API 필드는 422이고 저장되지 않는다 | CT-R6, CT-UC2 | backend | `web/test_contact_routes.py::test_registration_rejects_unknown_and_retired_fields` |
| CT-017 | 이메일 없이 같은 회사명·담당자명을 다시 등록하면 409이고 한 건만 남는다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_the_same_company_and_name_without_email_conflicts`<br>`web/test_contact_routes.py::test_duplicate_registration_and_update_are_409_already_exists` |
| CT-018 | 이메일까지 같으면(대소문자 무시) 409다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_the_same_email_conflicts_even_when_the_case_differs` |
| CT-019 | 회사명·담당자명은 대소문자만 달라도 같은 사람이다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_company_and_name_are_compared_ignoring_case`<br>`application/test_contact_register.py::test_a_company_with_a_special_capital_letter_conflicts_on_the_second_registration`<br>`application/test_contact_register.py::test_a_candidate_returned_by_same_identity_is_not_filtered_again_by_case` |
| CT-020 | 둘 다 이메일이 있고 서로 다르면 동명이인으로 등록된다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_a_different_email_is_a_namesake_and_is_registered` |
| CT-021 | 이메일 없는 기존 연락처에 이메일을 채워 등록하면 같은 사람이라 409다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_filling_in_the_email_of_an_existing_contact_without_one_conflicts` |
| CT-022 | 이메일 없이 입력하면 이메일이 있는 기존 연락처와 같은 사람이라 409다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_no_email_input_conflicts_with_a_namesake_that_has_an_email` |
| CT-023 | 종류가 다르면 같은 회사명·담당자명도 따로 등록된다 | CT-R7, CT-UC2 | backend | `application/test_contact_register.py::test_the_same_person_in_the_other_kind_is_not_a_conflict` |
| CT-024 | 관리 목록은 items·total·offset·limit이고 항목에 deal_count가 있다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_query_keeps_given_values`<br>`application/test_contact_search.py::test_returns_items_total_offset_and_limit`<br>`web/test_contact_routes.py::test_list_has_items_total_offset_limit_and_deal_count_in_each_item` |
| CT-025 | 연락처가 없으면 items가 비고 total 0, 기본 offset 0·limit 50이다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_query_defaults_to_all_kinds_first_page_without_keyword`<br>`application/test_contact_search.py::test_an_empty_result_has_total_zero`<br>`web/test_contact_routes.py::test_empty_list_uses_default_offset_0_and_limit_50` |
| CT-026 | 목록은 고객 먼저, 회사명·담당자명(대소문자 무시), id 순이다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_sorts_customers_first_then_company_name_ignoring_case_then_id` |
| CT-027 | 종류 조건을 주면 그 종류만 나온다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_filters_by_kind` |
| CT-028 | 키워드는 회사명·담당자명·이메일에 대소문자 무시로 부분 일치한다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_keyword_matches_company_name_and_email_ignoring_case` |
| CT-029 | 키워드는 직급과 전화를 찾지 않는다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_keyword_does_not_search_title_or_phone` |
| CT-030 | 공백뿐인 키워드는 조건이 없는 것과 같다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_query_strips_keyword_and_blank_is_none`<br>`application/test_contact_search.py::test_a_blank_keyword_is_the_same_as_no_condition` |
| CT-031 | 키워드의 %와 _는 글자 그대로 찾는다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_percent_and_underscore_in_keyword_are_plain_characters` |
| CT-032 | 필터 뒤에 페이지가 적용되고 total은 전체 일치 건수다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_returns_items_total_offset_and_limit`<br>`application/test_contact_search.py::test_total_counts_every_match_not_just_the_page` |
| CT-033 | 끝을 넘은 페이지는 비지만 total은 그대로다 | CT-R13, CT-UC1 | backend | `application/test_contact_search.py::test_a_page_past_the_end_is_empty_but_total_stays` |
| CT-034 | deal_count는 고객·파트너(비활성 링크 포함)로 참조하는 Deal 수이고 한 Deal은 한 번만 센다 | CT-R11, CT-UC1 | backend | `application/test_contact_search.py::test_deal_count_counts_deals_referencing_the_contact_as_customer_or_partner`<br>`application/test_contact_search.py::test_deal_count_includes_replaced_partner_links_and_counts_a_deal_once` |
| CT-035 | 키워드 100자는 되고 101자는 422 request-validation이다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_keyword_max_is_100`<br>`application/test_contact_query.py::test_query_rejects_keyword_over_100_chars`<br>`web/test_contact_routes.py::test_keyword_of_100_characters_is_accepted_and_101_is_request_validation` |
| CT-036 | 키워드에 NUL이 있으면 422 invalid-value다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_query_rejects_nul_in_keyword`<br>`web/test_contact_routes.py::test_keyword_with_nul_is_422_invalid_value` |
| CT-037 | 모르는 쿼리 파라미터·모르는 종류는 422 request-validation이다 | CT-R13, CT-UC1 | backend | `web/test_contact_routes.py::test_list_rejects_unknown_parameters_and_unknown_kinds` |
| CT-038 | 범위 밖 offset·limit은 키워드가 있어도 422 request-validation이다 | CT-R13, CT-UC1 | backend | `application/test_contact_query.py::test_query_rejects_negative_offset`<br>`application/test_contact_query.py::test_query_rejects_limit_out_of_range`<br>`application/test_contact_query.py::test_query_accepts_limit_boundaries`<br>`application/test_contact_search.py::test_rejects_invalid_paging_in_the_query`<br>`web/test_contact_routes.py::test_list_rejects_out_of_range_paging_even_with_a_keyword` |
| CT-039 | 모든 역할이 종류별 회사 목록을 대소문자 무시 순서로 받는다 | CT-R14, CT-UC5 | backend | `application/test_contact_search.py::test_lists_distinct_companies_with_the_first_registered_spelling`<br>`application/test_contact_search.py::test_orders_companies_by_lowercase_code_point`<br>`web/test_contact_routes.py::test_every_role_gets_companies_and_people_of_a_company` |
| CT-040 | 대소문자만 다른 회사명은 먼저 등록된 표기 하나로 나온다 | CT-R14, CT-UC5 | backend | `application/test_contact_search.py::test_lists_distinct_companies_with_the_first_registered_spelling` |
| CT-041 | 회사 목록은 요청 종류로 한정되고 없으면 빈 배열이다 | CT-R14, CT-UC5 | backend | `application/test_contact_search.py::test_lists_only_the_requested_kind`<br>`application/test_contact_search.py::test_an_empty_kind_lists_nothing`<br>`web/test_contact_routes.py::test_companies_and_people_are_scoped_to_the_requested_kind` |
| CT-042 | 회사 목록에 종류가 없거나 모르는 값이면 422다 | CT-R14, CT-UC5 | backend | `web/test_contact_routes.py::test_companies_requires_a_known_kind` |
| CT-043 | 모든 역할이 회사(대소문자 무시)의 담당자를 이름순으로 deal_count와 함께 받는다 | CT-R15, CT-R11, CT-UC5 | backend | `application/test_contact_search.py::test_lists_the_company_ignoring_case_sorted_by_name_with_deal_counts`<br>`application/test_contact_search.py::test_people_of_a_company_carry_their_deal_counts`<br>`web/test_contact_routes.py::test_every_role_gets_companies_and_people_of_a_company` |
| CT-044 | 회사별 담당자는 요청 종류로 한정되고 없는 회사는 빈 배열이다 | CT-R15, CT-UC5 | backend | `application/test_contact_search.py::test_other_kinds_and_companies_are_excluded`<br>`web/test_contact_routes.py::test_companies_and_people_are_scoped_to_the_requested_kind` |
| CT-045 | 회사별 담당자에 종류·회사가 빠지거나 회사명이 200자를 넘으면 422다 | CT-R15, CT-UC5 | backend | `web/test_contact_routes.py::test_by_company_requires_kind_and_a_company_of_200_characters_or_less`<br>`web/test_contact_routes.py::test_by_company_accepts_a_company_of_exactly_200_characters` |
| CT-046 | 수정하면 모든 값이 바뀌고 id·종류·등록 시각은 그대로, 수정 시각은 서버 시각이다 | CT-R9, CT-UC3 | backend | `application/test_contact_update.py::test_replaces_details_and_uses_the_clock`<br>`application/test_contact_update.py::test_unchanged_values_still_refresh_the_update_time`<br>`application/test_contact_update.py::test_keeps_the_kind`<br>`web/test_contact_routes.py::test_update_returns_200_and_unknown_id_is_404` |
| CT-047 | 수정에서 직급·이메일·전화를 null로 보내거나 빼면 지워진다 | CT-R9, CT-UC3 | backend | `application/test_contact_update.py::test_replaces_details_and_uses_the_clock`<br>`application/test_contact_update.py::test_omitted_optional_values_are_cleared_on_update`<br>`web/test_contact_routes.py::test_update_omitting_optional_keys_clears_them` |
| CT-048 | 수정 본문에 종류가 있으면 422이고 종류는 그대로다 | CT-R1, CT-UC3 | backend | `web/test_contact_routes.py::test_update_with_kind_in_the_body_is_request_validation_and_kind_stays` |
| CT-049 | 수정 본문에 모르는 필드가 있으면 422이고 값은 그대로다 | CT-R6, CT-UC3 | backend | `web/test_contact_routes.py::test_update_with_an_unknown_field_is_request_validation_and_values_stay` |
| CT-050 | 공백·형식이 틀린 값으로 수정하면 422이고 기존 값이 남는다 | CT-R6, CT-UC3 | backend | `application/test_contact_update.py::test_invalid_input_leaves_the_contact_unchanged` |
| CT-051 | 없는 연락처를 수정하면 404 "연락처를 찾을 수 없습니다."다 | CT-R9, CT-UC3 | backend | `application/test_contact_update.py::test_missing_contact_raises_not_found`<br>`web/test_contact_routes.py::test_update_returns_200_and_unknown_id_is_404` |
| CT-052 | 이미 있는 다른 사람과 같아지게 수정하면 409이고 그대로 남는다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_becoming_another_existing_person_conflicts_and_changes_nothing`<br>`web/test_contact_routes.py::test_duplicate_registration_and_update_are_409_already_exists` |
| CT-053 | 자기 회사명·담당자명을 유지하고 다른 값만 바꾸면 충돌이 아니다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_keeping_its_own_identity_is_not_a_conflict` |
| CT-054 | 자기 회사명의 대소문자만 바꾸는 수정은 충돌이 아니다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_changing_only_the_case_of_its_own_name_is_not_a_conflict` |
| CT-055 | 다른 이메일을 가진 동명이인이 되는 수정은 된다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_becoming_a_namesake_with_another_email_is_allowed` |
| CT-056 | 이메일을 채워 이메일 없는 다른 연락처와 같은 사람이 되면 409다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_adding_an_email_to_become_the_same_person_as_one_without_email_conflicts` |
| CT-057 | 다른 종류의 같은 사람과 같아지는 수정은 충돌이 아니다 | CT-R7, CT-UC3 | backend | `application/test_contact_update.py::test_the_same_person_of_the_other_kind_is_not_a_conflict` |
| CT-058 | 고객 연락처를 고치면 그 고객을 쓰는 모든 Deal에 이력이 한 건씩 남고 Deal 수정 시각이 바뀐다 | CT-R10, CT-UC3 | backend | `application/test_update_contact_history.py::test_changing_a_customer_logs_on_every_deal_that_uses_it` |
| CT-059 | 이력의 변경자는 연락처를 고친 admin이고 시각은 서버 시각이다 | CT-R10, CT-UC3 | backend | `application/test_update_contact_history.py::test_the_history_author_is_the_admin_who_changed_the_contact` |
| CT-060 | 파트너 연락처를 고치면 교체돼 비활성인 링크의 Deal에도 '파트너 연락처 정보' 이력이 남는다 | CT-R10, CT-UC3 | backend | `application/test_update_contact_history.py::test_changing_a_partner_logs_with_the_partner_target_even_after_it_was_replaced` |
| CT-061 | 값이 그대로인 수정은 Deal 이력도 Deal 수정 시각도 바꾸지 않는다 | CT-R10, CT-R9, CT-UC3 | backend | `application/test_update_contact_history.py::test_an_unchanged_contact_logs_nothing_and_touches_no_deal` |
| CT-062 | 참조 Deal이 없는 연락처는 이력 없이 수정된다 | CT-R10, CT-UC3 | backend | `application/test_update_contact_history.py::test_a_contact_without_deals_changes_without_any_history` |
| CT-063 | 거절된 수정은 이력을 남기지 않는다 | CT-R10, CT-UC3 | backend | `application/test_update_contact_history.py::test_a_rejected_update_leaves_no_history` |
| CT-064 | 참조 Deal이 없는 고객·파트너 연락처는 204로 삭제되고 다른 연락처는 남는다 | CT-R12, CT-UC4 | backend | `application/test_contact_delete.py::test_deletes_the_contact_physically_and_commits`<br>`application/test_contact_delete.py::test_a_partner_contact_is_deleted_the_same_way`<br>`application/test_contact_delete.py::test_other_contacts_are_untouched`<br>`web/test_contact_routes.py::test_delete_unreferenced_contact_is_204_with_empty_body` |
| CT-065 | 없는 id나 이미 지운 연락처를 지우면 404다 | CT-R12, CT-UC4 | backend | `application/test_contact_delete.py::test_missing_contact_raises_not_found`<br>`application/test_contact_delete.py::test_deleting_twice_raises_not_found`<br>`web/test_contact_routes.py::test_delete_unknown_or_already_deleted_contact_is_404` |
| CT-066 | 고객으로 참조되는 연락처는 409 "연결된 Deal이 1건 있어 삭제할 수 없습니다."이고 남는다 | CT-R12, CT-UC4 | backend | `application/test_contact_delete.py::test_customer_with_a_deal_cannot_be_deleted`<br>`application/test_contact_delete.py::test_the_error_is_an_invalid_state` |
| CT-067 | 파트너로(비활성 링크 포함) 참조되는 연락처는 지울 수 없다 | CT-R12, CT-R11, CT-UC4 | backend | `application/test_contact_delete.py::test_partner_with_a_deal_cannot_be_deleted`<br>`application/test_contact_delete.py::test_a_partner_link_that_is_no_longer_active_still_blocks_deletion` |
| CT-068 | 거절 문구의 건수는 참조 Deal 수이고 한 Deal이 고객·파트너로 함께 참조해도 1건이다 | CT-R12, CT-R11, CT-UC4 | backend | `application/test_contact_delete.py::test_the_message_counts_every_referencing_deal`<br>`application/test_contact_delete.py::test_one_deal_using_the_contact_as_customer_and_partner_counts_once` |
| CT-069 | 참조하던 Deal을 지우면 연락처를 지울 수 있다 | CT-R12, CT-UC4 | backend | `application/test_contact_delete.py::test_contact_can_be_deleted_after_its_deal_is_deleted` |
| CT-070 | 다른 연락처를 참조하는 Deal은 삭제를 막지 않는다 | CT-R12, CT-UC4 | backend | `application/test_contact_delete.py::test_deals_of_other_contacts_do_not_block_deletion` |
| CT-071 | 예전 고객·파트너 경로는 admin이 불러도 404이고 Location이 없다 | CT-R16 | backend | `web/test_contact_routes.py::test_retired_customer_and_partner_routes_are_404_without_location` |
| CT-072 | 관리 화면은 8칸 표로 첫 20건을 보이고 없는 값은 '-', 연결 Deal 수를 보인다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > lists the first page with company, name, title, email, phone and linked deal count` |
| CT-073 | 20건을 넘으면 페이저로 다음 페이지를 본다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > pages through all 24 contacts` |
| CT-074 | 구분을 고르면 그 종류만 보인다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > filters by kind` |
| CT-075 | 검색어(버튼·Enter)는 첫 페이지부터 찾고 이메일로도 찾는다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > searches by keyword from the first page, also with Enter`<br>`features/admin/contacts/ContactsPage.test.tsx > searches by email too` |
| CT-076 | 검색어를 비우고 검색하면 전체 목록으로 돌아온다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows the full list again when the keyword is emptied` |
| CT-077 | 결과가 없으면 조건 유무에 따라 다른 빈 문구를 보인다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows an empty search message when nothing matches`<br>`features/admin/contacts/ContactsPage.test.tsx > shows the empty message without conditions when there are no contacts` |
| CT-078 | 목록을 읽지 못하면 오류 배너에 서버 문구를 보인다 | CT-R17, CT-UC1 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows the message when the list cannot be loaded` |
| CT-079 | 고객·파트너 연락처를 등록하면 폼이 닫히고 알림과 함께 목록에 Deal 0으로 나온다 | CT-R18, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > creates a customer contact without an email`<br>`features/admin/contacts/ContactsPage.test.tsx > creates a partner contact` |
| CT-080 | 등록·수정 폼은 회사명·담당자명·이메일·전화의 공백을 입력 즉시 지우고 안내하며 직급은 공백을 허용한다 | CT-R18, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > removes whitespace while typing and tells the user`<br>`features/admin/contacts/ContactsPage.test.tsx > allows spaces inside the title in the form`<br>`features/admin/contacts/ContactsPage.test.tsx > blocks whitespace on edit too` |
| CT-081 | 필수 칸이 비면 요청 없이 칸 아래에 문구를 보인다 | CT-R18, CT-R21, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows required messages and does not send a request when empty` |
| CT-082 | 이메일·전화 형식이 틀리면 요청 없이 칸 아래에 문구를 보인다 | CT-R18, CT-R21, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows the email format message`<br>`features/admin/contacts/ContactsPage.test.tsx > shows the phone format message` |
| CT-083 | 서버가 같은 사람으로 거절하면 폼 안에 서버 문구를 보이고 폼을 유지한다 | CT-R18, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > shows the server message for a contact that already exists` |
| CT-084 | 취소하면 요청 없이 폼이 닫힌다 | CT-R18, CT-UC2 | frontend | `features/admin/contacts/ContactsPage.test.tsx > closes the form with cancel` |
| CT-085 | 수정 폼은 현재 값과 공유 Deal 수 안내를 보이고 저장하면 알림과 함께 표에 반영된다 | CT-R18, CT-UC3 | frontend | `features/admin/contacts/ContactsPage.test.tsx > tells how many deals will reflect the change and saves it` |
| CT-086 | 참조 Deal이 없는 연락처의 수정 폼에는 공유 안내가 없다 | CT-R18, CT-UC3 | frontend | `features/admin/contacts/ContactsPage.test.tsx > does not show the sharing notice when no deal uses the contact` |
| CT-087 | 연락처를 고치면 그 연락처를 쓰는 Deal의 Quick View와 상세에 새 값이 보인다 | CT-R20, CT-R10, CT-UC3 | frontend | `test/crossScreen.test.tsx > shows the edited title in the list quick view and in the deal detail` |
| CT-088 | 참조 중인 연락처 삭제는 대화상자를 닫고 배너에 건수 문구를 보이며 행이 남는다 | CT-R19, CT-UC4 | frontend | `features/admin/contacts/ContactsPage.test.tsx > refuses to delete a contact that deals use and says how many` |
| CT-089 | 참조 없는 연락처는 확인 뒤 삭제되고 알림을 보인다 | CT-R19, CT-UC4 | frontend | `features/admin/contacts/ContactsPage.test.tsx > deletes a contact nobody uses after confirmation` |
| CT-090 | 삭제 확인을 취소하면 요청하지 않는다 | CT-R19, CT-UC4 | frontend | `features/admin/contacts/ContactsPage.test.tsx > does nothing when the confirmation is declined` |
| CT-091 | 화면 입력 규칙은 서버와 같은 공백·필수·이메일·전화 경계값으로 판정한다 | CT-R21 | frontend | `shared/model/contactRules.server.test.ts > 문구`<br>`shared/model/contactRules.server.test.ts > %s 는 허용`<br>`shared/model/contactRules.server.test.ts > %s 는 형식 오류(%s)`<br>`shared/model/contactRules.server.test.ts > 공백이 있으면 형식보다 공백 오류가 먼저다`<br>`shared/model/contactRules.server.test.ts > 없으면(null) 검사하지 않는다`<br>`shared/model/contactRules.server.test.ts > %s 는 형식 오류`<br>`shared/model/contactRules.server.test.ts > 254자를 넘으면 형식 오류`<br>`shared/model/contactRules.test.ts > T-CONTACT-01 모든 공백 문자를 제거한다`<br>`shared/model/contactRules.test.ts > T-CONTACT-02 회사/담당자/이메일/전화에 공백이 있으면 오류, 직급 내부 공백은 허용`<br>`shared/model/contactRules.test.ts > 필수 누락과 이메일 형식` |
| CT-092 | 화면 같은 사람 판정은 서버와 같은 3단계 규칙이다 | CT-R21, CT-R7 | frontend | `shared/model/contactRules.test.ts > T-CONTACT-04 이메일이 없으면 회사+이름이 같은 연락처와 같은 사람이다`<br>`shared/model/contactRules.test.ts > T-CONTACT-05 이메일이 다르면 동명이인이다`<br>`shared/model/contactRules.test.ts > 기존 연락처에 이메일이 없으면 이메일을 채워 같은 사람으로 본다`<br>`shared/model/contactRules.test.ts > 구분이 다르면 비교하지 않고 excludeId는 자기 자신을 뺀다`<br>`shared/model/contactRules.test.ts > 대소문자 무시` |
| CT-093 | 선택기의 회사 후보는 그 종류의 회사 목록이다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > lists distinct companies of the given kind` |
| CT-094 | 회사를 정하면 그 회사(대소문자 무시)의 담당자가 직급·이메일 설명과 함께 후보로 나온다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > lists the people of the chosen company with title and email`<br>`shared/contact/ContactPicker.test.tsx > shows the same-company people regardless of letter case` |
| CT-095 | 기존 담당자를 고르면 직급·이메일·전화가 채워지고 그 연락처 id가 잡힌다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > fills title, email and phone when an existing person is chosen` |
| CT-096 | 채운 연락 정보를 고쳐도 연락처 id는 유지된다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > keeps the contact id when the user edits the filled fields, so the card is updated` |
| CT-097 | 새 회사·사람을 직접 입력하면 새 연락처(id 없음)다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > treats typing a new company and person as a new contact` |
| CT-098 | 고른 담당자의 이름을 다른 이름으로 바꾸면 연락처 id가 풀린다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > releases the contact id when the chosen name is changed to another name` |
| CT-099 | 회사를 다른 회사로 바꾸면 고른 사람과 연락 정보가 비워진다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > clears the old person when the company is changed to another one`<br>`shared/contact/ContactPicker.test.tsx > keeps the chosen person when only the letter case of the company changes` |
| CT-100 | 선택기에서 이메일·전화를 비우면 null이 된다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > maps an emptied email to null`<br>`shared/contact/ContactPicker.test.tsx > maps an emptied phone to null` |
| CT-101 | 선택기는 회사명·담당자명·이메일·전화의 공백(붙여넣기 포함)을 지우고 안내하며 직급은 허용한다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > blocks whitespace while typing and says so`<br>`shared/contact/ContactPicker.test.tsx > blocks whitespace in name, email and phone too, including pasted text`<br>`shared/contact/ContactPicker.test.tsx > allows spaces inside the title` |
| CT-102 | 이메일 칸을 떠난 뒤 형식이 틀리면 안내하고 폼이 준 칸 오류를 보인다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > shows an email format message after leaving the field`<br>`shared/contact/ContactPicker.test.tsx > shows errors handed in by the form`<br>`shared/contact/ContactPicker.test.tsx > prefers the email error from the form over the format message` |
| CT-103 | 이메일 없이 기존 사람과 같은 회사명·담당자명이면 같은 사람 안내를 보이고 이메일이 있으면 보이지 않는다 | CT-R22, CT-R21, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > explains that a person without email is merged into the existing one`<br>`shared/contact/ContactPicker.test.tsx > does not show the merge note when an email is given` |
| CT-104 | 고른 연락처를 다른 Deal도 쓰면 공유 안내를 보인다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > warns when the chosen contact is shared by other deals` |
| CT-105 | rows 배치는 짧은 보이는 라벨, 기본 배치는 전체 라벨이다 | CT-R22, CT-UC5 | frontend | `shared/contact/ContactPicker.test.tsx > renders short visible labels in the rows layout`<br>`shared/contact/ContactPicker.test.tsx > keeps the stacked layout and full labels by default` |
| CT-106 | 게이트웨이는 조회에 정한 조건만 보내고 응답의 null 직급을 빈 값으로 바꾼다 | CT-R23 | frontend | `gateway/http/contacts.test.ts > companies reads GET /contacts/companies for the kind`<br>`gateway/http/contacts.test.ts > byCompany reads the people of one company with their Deal counts`<br>`gateway/http/contacts.test.ts > maps a missing title to an empty string`<br>`gateway/http/contacts.test.ts > list sends the filters and reads total from the page`<br>`gateway/http/contacts.test.ts > list omits the filters that are not set` |
| CT-107 | 게이트웨이는 쓰기에 빈 직급을 null로, 수정은 종류 없이 보내고 삭제 204·409 문구를 다룬다 | CT-R23 | frontend | `gateway/http/contacts.test.ts > create posts the kind with company, name, title, email and phone`<br>`gateway/http/contacts.test.ts > create sends an empty title as null`<br>`gateway/http/contacts.test.ts > create failure %i "%s" keeps the server message`<br>`gateway/http/contacts.test.ts > update puts the fields without the kind`<br>`gateway/http/contacts.test.ts > remove deletes and accepts 204`<br>`gateway/http/contacts.test.ts > remove shows the server message when Deals still use the contact`<br>`gateway/http/mappers/contact.test.ts > sends an empty title as null and keeps the other fields`<br>`gateway/http/mappers/contact.test.ts > keeps a title as typed` |

### CT-001 admin이 고객·파트너 연락처를 등록하면 201과 Location·문서화된 필드가 오고 목록에 나온다
- Given ROOT로 로그인했고 연락처가 없다
- When 고객(또는 파트너) "네오인 김철수, 팀장, Kim@Neoine.Example, 010-1234-5678"을 등록한다
- Then 201이고 `Location`이 `/api/v1/contacts/<새 id>`이며, 본문 키는 정확히 `id`·`created_at`·`updated_at`·`kind`·`company`·`name`·`title`·`email`·`phone`이고 `kind`는 요청 종류, `created_at`과 `updated_at`이 같으며, 관리 목록에 그 id가 회사명 "네오인"으로 나온다

### CT-002 종류·회사명·담당자명만 보내면 직급·이메일·전화는 null로 저장된다
- Given ROOT로 로그인했다
- When `{kind: customer, company: "회사", name: "담당"}`을 등록한다
- Then 201이고 `title`·`email`·`phone`이 모두 null이다

### CT-003 이메일은 소문자로 저장된다
- Given ROOT로 로그인했다
- When 이메일 "Kim@Neoine.Example"로 등록한다
- Then 저장된 이메일은 "kim@neoine.example"이다

### CT-004 직급은 앞뒤 공백만 지워지고 빈 값·공백뿐·null은 null이 된다
- Given ROOT로 로그인했다
- When 직급을 "  팀장  ", "수석 과장", "   ", "", null로 각각 등록한다
- Then 저장된 직급은 차례로 "팀장", "수석 과장", null, null, null이다

### CT-005 이메일·전화의 빈 문자열은 없는 값으로 저장된다
- Given ROOT로 로그인했다
- When 이메일 "", 전화 ""로 등록한다
- Then 201이고 이메일·전화가 null이다

### CT-006 회사명·담당자명·이메일·전화에 공백 문자가 있으면 잘라 내지 않고 422로 거절한다
- Given ROOT로 로그인했고 연락처가 없다
- When 회사명·담당자명·이메일·전화 중 한 칸을 "x y", " x", "x ", "x\ty", "x\ny", "x　y"(전각), "　x"로 각각 바꿔 등록한다
- Then 모두 422 `invalid-value` "공백은 입력할 수 없습니다."이고 연락처 수는 0이다

### CT-007 공백뿐인 이메일·전화는 없는 값이 아니라 공백 오류다
- Given ROOT로 로그인했다
- When 이메일(또는 전화)을 "   "로 등록한다
- Then 422 `invalid-value` "공백은 입력할 수 없습니다."이고 저장되지 않는다

### CT-008 회사명·담당자명이 비어 있으면 각자의 문구로 422다
- Given ROOT로 로그인했다
- When 회사명 ""(또는 담당자명 "")으로 등록한다
- Then 422 `invalid-value` "회사명을 입력하세요."(또는 "담당자명을 입력하세요.")이고 저장되지 않는다

### CT-009 형식이 틀리거나 254자를 넘는 이메일은 422다
- Given ROOT로 로그인했다
- When 이메일 "not-an-email", "a@b", "@neoine.example", "kim@", "kim@@neoine.example", 255자 이메일로 각각 등록한다
- Then 모두 422 `invalid-value` "이메일 형식이 올바르지 않습니다."이고 저장되지 않는다

### CT-010 형식이 틀리거나 숫자 7~15개를 벗어난 전화는 422이고 흔한 형식은 저장된다
- Given ROOT로 로그인했다
- When 전화 "abc", "12-34", "1234567890123456"(16자리), "010-1234-567x", 41자 전화와 "010-1234-5678", "+82-10-1234-5678", "(02)123-4567"로 각각 등록한다
- Then 앞의 다섯은 422 `invalid-value` "전화번호 형식이 올바르지 않습니다.", 뒤의 셋은 201이고 입력 그대로 저장된다

### CT-011 NUL 문자가 든 입력은 500이 아니라 422이고 DB 문구가 없다
- Given ROOT로 로그인했다
- When 회사명·담당자명·직급·이메일·전화 중 한 칸을 "a\x00b"로 각각 등록한다
- Then 모두 422 `invalid-value`이고 `detail`에 "asyncpg"·"sqlalchemy"·"postgres"·"dbapierror"·"0x00"이 없으며 연락처 수는 0이다

### CT-012 회사명 200자·담당자명 100자·직급 100자는 등록된다
- Given ROOT로 로그인했다
- When 회사명 200자, 담당자명 100자, 직급 100자(앞뒤 공백을 붙여도)로 등록한다
- Then 201이다

### CT-013 회사명 201자·담당자명 101자·직급 101자는 422이고 저장되지 않는다
- Given ROOT로 로그인했다
- When 회사명 201자(또는 담당자명 101자, 직급 101자)로 등록한다
- Then 422 `invalid-value` "회사명은(는) 200자를 넘을 수 없습니다"(또는 "담당자명은(는) 100자를 넘을 수 없습니다", "직급은(는) 100자를 넘을 수 없습니다")이고 연락처 수는 0이다

### CT-014 종류·회사명·담당자명 중 하나가 빠지면 422 request-validation이다
- Given ROOT로 로그인했다
- When `kind`(또는 `company`, `name`) 키를 빼고 등록한다
- Then 422 `request-validation`이고 `errors`의 한 항목 `loc` 끝이 빠진 키 이름이다

### CT-015 알 수 없는 종류는 422 request-validation이다
- Given ROOT로 로그인했다
- When `kind: "supplier"`로 등록한다
- Then 422 `request-validation`이다

### CT-016 모르는 필드와 예전 고객 API 필드는 422이고 저장되지 않는다
- Given ROOT로 로그인했다
- When 본문에 `company_name`(또는 `contact_name`, `employee_count`, `notes`, `x`)을 더해 등록한다
- Then 422 `request-validation`이고 연락처 수는 0이다

### CT-017 이메일 없이 같은 회사명·담당자명을 다시 등록하면 409이고 한 건만 남는다
- Given 이메일 없는 고객 "네오인 김철수"가 있다
- When 이메일 없이 직급만 다르게 고객 "네오인 김철수"를 등록한다
- Then 409 `already-exists` "이미 등록된 연락처입니다."이고 연락처는 1건이다

### CT-018 이메일까지 같으면(대소문자 무시) 409다
- Given 이메일 "kim@neoine.example"인 고객 "네오인 김철수"가 있다
- When 이메일 "KIM@Neoine.Example"로 같은 회사명·담당자명을 등록한다
- Then 409 `already-exists`이고 연락처는 1건이다

### CT-019 회사명·담당자명은 대소문자만 달라도 같은 사람이다
- Given 이메일 없는 고객 "Acme Kim"이 있다
- When 이메일 없이 고객 "ACME KIM"을 등록한다
- Then 409 `already-exists`다

### CT-020 둘 다 이메일이 있고 서로 다르면 동명이인으로 등록된다
- Given 이메일 "kim1@neoine.example"인 고객 "네오인 김철수"가 있다
- When 이메일 "kim2@neoine.example"로 같은 회사명·담당자명을 등록한다
- Then 201이고 연락처는 2건이다

### CT-021 이메일 없는 기존 연락처에 이메일을 채워 등록하면 같은 사람이라 409다
- Given 이메일 없는 고객 "네오인 김철수"가 있다
- When 이메일 "kim@neoine.example"로 같은 회사명·담당자명을 등록한다
- Then 409 `already-exists`이고 연락처는 1건이다

### CT-022 이메일 없이 입력하면 이메일이 있는 기존 연락처와 같은 사람이라 409다
- Given 이메일 "kim@neoine.example"인 고객 "네오인 김철수"가 있다
- When 이메일 없이 같은 회사명·담당자명을 등록한다
- Then 409 `already-exists`다

### CT-023 종류가 다르면 같은 회사명·담당자명도 따로 등록된다
- Given 이메일 없는 고객 "공용회사 공용이름"이 있다
- When 이메일 없이 파트너 "공용회사 공용이름"을 등록한다
- Then 201이고 연락처는 2건이다

### CT-024 관리 목록은 items·total·offset·limit이고 항목에 deal_count가 있다
- Given 연락처 1건이 있다
- When ROOT가 `limit=10`으로 목록을 조회한다
- Then 200 `{items, total: 1, offset: 0, limit: 10}`이고 항목 키는 `ContactResponse` 키에 `deal_count`를 더한 것이다

### CT-025 연락처가 없으면 items가 비고 total 0, 기본 offset 0·limit 50이다
- Given 연락처가 없다
- When ROOT가 조건 없이 목록을 조회한다
- Then `items`는 `[]`, `total` 0, `offset` 0, `limit` 50이다

### CT-026 목록은 고객 먼저, 회사명·담당자명(대소문자 무시), id 순이다
- Given 파트너 "aaa-partner 이영희", 고객 "Beta park", 고객 "alpha zed", 고객 "alpha Amy", 파트너 "bbb-partner 이영희"를 이 순서로 등록했다
- When 목록을 조회한다
- Then 회사명은 alpha, alpha, Beta, aaa-partner, bbb-partner이고 담당자명은 Amy, zed, park, 이영희, 이영희 순이다

### CT-027 종류 조건을 주면 그 종류만 나온다
- Given 고객 "customer-co"와 파트너 "partner-co"가 있다
- When `kind=partner`와 `kind=customer`로 각각 조회한다
- Then 각각 "partner-co"만(total 1), "customer-co"만 나온다

### CT-028 키워드는 회사명·담당자명·이메일에 대소문자 무시로 부분 일치한다
- Given "Alpha상사/가나다/a@x.example", "무관회사/알파담당/b@x.example", "메일회사/라마바/Search.Me@Sample.Example"(저장은 소문자), "다른회사/사아자/c@x.example"가 있다
- When 키워드 "alpha", "알파", "SEARCH.ME@"로 각각 조회한다
- Then 차례로 Alpha상사, 무관회사, 메일회사만 나온다

### CT-029 키워드는 직급과 전화를 찾지 않는다
- Given 직급 "ZETA 팀장", 전화 "031-777-4321"인 연락처만 있다
- When 키워드 "zeta"와 "777-43"으로 조회한다
- Then 둘 다 total 0이다

### CT-030 공백뿐인 키워드는 조건이 없는 것과 같다
- Given 연락처 "가 일", "나 이"가 있다
- When 키워드 "   "로 조회한다
- Then 두 건 모두 나온다

### CT-031 키워드의 %와 _는 글자 그대로 찾는다
- Given 회사명 "백%프로"와 "백천프로"가 있다
- When 키워드 "백%"로 조회한다
- Then "백%프로"만 나온다

### CT-032 필터 뒤에 페이지가 적용되고 total은 전체 일치 건수다
- Given 회사명 hit0~hit3과 other0~other3 연락처 8건이 있다
- When 키워드 "hit", `offset=1`, `limit=2`로 조회한다
- Then 회사명 hit1, hit2가 나오고 `total` 4, `offset` 1, `limit` 2다

### CT-033 끝을 넘은 페이지는 비지만 total은 그대로다
- Given 연락처 3건이 있다
- When `offset=10`, `limit=5`로 조회한다
- Then `items`는 비고 `total`은 3이다

### CT-034 deal_count는 고객·파트너(비활성 링크 포함)로 참조하는 Deal 수이고 한 Deal은 한 번만 센다
- Given 고객 연락처 C를 쓰는 Deal 2건(그중 하나는 파트너 P를 연결), 파트너를 다른 연락처로 교체해 비활성 링크만 남은 파트너 Q의 Deal 1건, 참조 없는 고객 I가 있다
- When 목록을 조회한다
- Then C는 2, P는 1, Q는 1, I는 0이다

### CT-035 키워드 100자는 되고 101자는 422 request-validation이다
- Given ROOT로 로그인했다
- When 키워드 100자와 101자로 각각 조회한다
- Then 100자는 200, 101자는 422 `request-validation`이다

### CT-036 키워드에 NUL이 있으면 422 invalid-value다
- Given ROOT로 로그인했다
- When 키워드 "a\x00b"로 조회한다
- Then 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다"다

### CT-037 모르는 쿼리 파라미터·모르는 종류는 422 request-validation이다
- Given ROOT로 로그인했다
- When `foo=1`, `company_name=a`(키워드와 함께), `kind=supplier`로 각각 조회한다
- Then 모두 422 `request-validation`이다

### CT-038 범위 밖 offset·limit은 키워드가 있어도 422 request-validation이다
- Given ROOT로 로그인했다
- When 키워드 "a"와 `offset=-1`(또는 `limit=0`, `limit=201`)로 조회한다
- Then 422 `request-validation`이다

### CT-039 모든 역할이 종류별 회사 목록을 대소문자 무시 순서로 받는다
- Given 고객 "Beta", 고객 "alpha", 파트너 "partner-co"가 있다
- When ROOT·KIM·VIEWER가 각각 `kind=customer` 회사 목록을 조회한다
- Then 모두 200 `["alpha", "Beta"]`다

### CT-040 대소문자만 다른 회사명은 먼저 등록된 표기 하나로 나온다
- Given 고객 "Acme", "ACME", "acme"를 이 순서로 등록했다(등록 시각이 같으면 id가 작은 것이 먼저)
- When 고객 회사 목록을 조회한다
- Then `["Acme"]`다

### CT-041 회사 목록은 요청 종류로 한정되고 없으면 빈 배열이다
- Given 고객 "customer-co"와 파트너 "partner-co"가 있다
- When `kind=partner`로 조회하고, 연락처가 없는 시스템에서 `kind=customer`로 조회한다
- Then 앞은 `["partner-co"]`, 뒤는 `[]`다

### CT-042 회사 목록에 종류가 없거나 모르는 값이면 422다
- Given KIM으로 로그인했다
- When `kind` 없이, 또는 `kind=supplier`로 회사 목록을 조회한다
- Then 422 `request-validation`이다

### CT-043 모든 역할이 회사(대소문자 무시)의 담당자를 이름순으로 deal_count와 함께 받는다
- Given 고객 "Acme park"(참조 Deal 2건), "ACME kim"(참조 없음), "Other aaa"가 있다
- When ROOT·KIM·VIEWER가 각각 `kind=customer&company=aCmE`로 조회한다
- Then 모두 200이고 담당자명은 kim, park 순, 항목 키는 관리 목록 항목과 같으며 deal_count는 kim 0, park 2다

### CT-044 회사별 담당자는 요청 종류로 한정되고 없는 회사는 빈 배열이다
- Given 고객 "Acme 고객담당"과 파트너 "Acme 파트너담당"이 있다
- When `kind=partner&company=Acme`와 `kind=customer&company=없는회사`로 조회한다
- Then 앞은 파트너담당만, 뒤는 200 `[]`다

### CT-045 회사별 담당자에 종류·회사가 빠지거나 회사명이 200자를 넘으면 422다
- Given KIM으로 로그인했다
- When `company` 없이, `kind` 없이, 회사명 201자로 각각 조회한다
- Then 모두 422 `request-validation`이다

### CT-046 수정하면 모든 값이 바뀌고 id·종류·등록 시각은 그대로, 수정 시각은 서버 시각이다
- Given 파트너 연락처가 있고 서버 시각이 5분 흘렀다
- When 회사명 "새회사", 담당자명 "박영희", 직급 "대표", 이메일 "NEW@Hanbit.Example", 전화 "031-777-4321"로 수정한다
- Then 200이고 값이 모두 바뀌며(이메일은 "new@hanbit.example"), id·`kind`(partner)·`created_at`은 그대로, `updated_at`은 지금 서버 시각이고, 목록 항목도 같은 값이다

### CT-047 수정에서 직급·이메일·전화를 null로 보내거나 빼면 지워진다
- Given 직급·이메일·전화가 있는 연락처가 있다
- When 회사명·담당자명만 두고 직급·이메일·전화를 null로(또는 키를 빼고) 수정한다
- Then 200이고 직급·이메일·전화가 null이다

### CT-048 수정 본문에 종류가 있으면 422이고 종류는 그대로다
- Given 고객 연락처가 있다
- When 본문에 `kind: "partner"`를 넣어 수정한다
- Then 422 `request-validation`이고 목록에서 그 연락처의 종류는 customer다

### CT-049 수정 본문에 모르는 필드가 있으면 422이고 값은 그대로다
- Given 연락처가 있다
- When 본문에 `company_name`(또는 `employee_count`, `notes`, `x`)을 더해 수정한다
- Then 422 `request-validation`이고 회사명은 그대로다

### CT-050 공백·형식이 틀린 값으로 수정하면 422이고 기존 값이 남는다
- Given 연락처 "네오인 김철수, kim@neoine.example"이 있다
- When 회사명 "네오 인", 담당자명 " 김철수", 이메일 "kim @neoine.example", 전화 "010 1234 5678", 이메일 "not-an-email"로 각각 수정한다
- Then 앞의 넷은 422 "공백은 입력할 수 없습니다.", 마지막은 422 "이메일 형식이 올바르지 않습니다."이고 회사명·담당자명·이메일은 그대로다

### CT-051 없는 연락처를 수정하면 404 "연락처를 찾을 수 없습니다."다
- Given ROOT로 로그인했다
- When 없는 id로 올바른 본문을 보내 수정한다
- Then 404 `not-found` "연락처를 찾을 수 없습니다."다

### CT-052 이미 있는 다른 사람과 같아지게 수정하면 409이고 그대로 남는다
- Given 이메일 없는 "네오인 김철수"와 "네오인 박영희"가 있다
- When 박영희를 이메일 없이 담당자명 "김철수"로 수정한다
- Then 409 `already-exists` "이미 등록된 연락처입니다."이고 그 연락처의 담당자명은 "박영희"다

### CT-053 자기 회사명·담당자명을 유지하고 다른 값만 바꾸면 충돌이 아니다
- Given 이메일 없는 "네오인 김철수"가 있다
- When 같은 회사명·담당자명으로 직급만 "이사"로 수정한다
- Then 200이고 직급이 "이사"다

### CT-054 자기 회사명의 대소문자만 바꾸는 수정은 충돌이 아니다
- Given 이메일 없는 "Acme 김철수"가 있다
- When 회사명을 "ACME"로 수정한다
- Then 200이고 회사명이 "ACME"다

### CT-055 다른 이메일을 가진 동명이인이 되는 수정은 된다
- Given "네오인 김철수 kim1@neoine.example"과 "네오인 박영희 park@neoine.example"이 있다
- When 박영희를 담당자명 "김철수", 이메일 "kim2@neoine.example"로 수정한다
- Then 200이다

### CT-056 이메일을 채워 이메일 없는 다른 연락처와 같은 사람이 되면 409다
- Given 이메일 없는 "네오인 김철수"와 "네오인 박영희 park@neoine.example"이 있다
- When 박영희를 담당자명 "김철수", 이메일 "kim@neoine.example"로 수정한다
- Then 409 `already-exists`다

### CT-057 다른 종류의 같은 사람과 같아지는 수정은 충돌이 아니다
- Given 이메일 없는 고객 "공용회사 공용이름"과 파트너 "공용회사 다른이름"이 있다
- When 파트너의 담당자명을 "공용이름"으로 수정한다
- Then 200이다

### CT-058 고객 연락처를 고치면 그 고객을 쓰는 모든 Deal에 이력이 한 건씩 남고 Deal 수정 시각이 바뀐다
- Given 고객 "네오인 김철수(직급 팀장)"를 쓰는 Deal 두 건이 있고 서버 시각이 1시간 흘렀다
- When 직급을 "이사"로 수정한다
- Then 두 Deal의 History에 각각 한 건씩 `contact`, "고객 연락처 정보 (네오인 김철수)", "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678" → "직급 이사 · 이메일 kim@neoine.example · 전화 010-1234-5678"가 남고 두 Deal의 `updated_at`이 지금 서버 시각이다

### CT-059 이력의 변경자는 연락처를 고친 admin이고 시각은 서버 시각이다
- Given 고객 연락처를 쓰는 Deal이 있다
- When ROOT가 그 연락처의 직급을 바꾼다
- Then 그 Deal의 가장 최근 이력은 분류 `contact`이고 변경자는 ROOT, 시각은 지금 서버 시각이다

### CT-060 파트너 연락처를 고치면 교체돼 비활성인 링크의 Deal에도 '파트너 연락처 정보' 이력이 남는다
- Given 파트너 "한빛파트너스 이영희(이사)"를 연결한 Deal A와, 파트너를 다른 연락처로 교체해 이영희 링크가 비활성인 Deal B가 있다
- When 이영희의 직급을 "부장"으로 수정한다
- Then A와 B의 History에 "파트너 연락처 정보 (한빛파트너스 이영희)", "직급 이사 · …" → "직급 부장 · …" 이력이 한 건씩 남는다

### CT-061 값이 그대로인 수정은 Deal 이력도 Deal 수정 시각도 바꾸지 않는다
- Given 고객 연락처를 쓰는 Deal이 있고 서버 시각이 1시간 흘렀다
- When 그 연락처를 지금과 같은 값으로 수정한다
- Then 200이고 Deal History는 비어 있으며 Deal의 `updated_at`은 그대로다(연락처의 `updated_at`은 지금 서버 시각)

### CT-062 참조 Deal이 없는 연락처는 이력 없이 수정된다
- Given 참조 Deal이 없는 파트너 연락처가 있다
- When 직급을 "상무"로 수정한다
- Then 200이고 직급이 "상무"이며 History는 남지 않는다

### CT-063 거절된 수정은 이력을 남기지 않는다
- Given 고객 연락처를 쓰는 Deal과, 같은 고객 회사에 이메일 없는 다른 담당자가 있다
- When 그 연락처를 다른 담당자와 같은 사람이 되게 수정한다(409)
- Then Deal History와 Deal `updated_at`이 그대로다

### CT-064 참조 Deal이 없는 고객·파트너 연락처는 204로 삭제되고 다른 연락처는 남는다
- Given 같은 종류의 "유지회사"와 "삭제회사" 연락처가 있고 참조 Deal이 없다
- When "삭제회사" 연락처를 삭제한다(고객·파트너 각각)
- Then 204이고 본문이 없으며, 목록에서 "삭제회사"는 사라지고 "유지회사"는 남는다

### CT-065 없는 id나 이미 지운 연락처를 지우면 404다
- Given 연락처를 하나 만들어 지웠다
- When 그 id와 없는 id를 각각 다시 삭제한다
- Then 둘 다 404 `not-found`다

### CT-066 고객으로 참조되는 연락처는 409 "연결된 Deal이 1건 있어 삭제할 수 없습니다."이고 남는다
- Given 고객 연락처를 쓰는 Deal 1건이 있다
- When 그 연락처를 삭제한다
- Then 409 `invalid-state` "연결된 Deal이 1건 있어 삭제할 수 없습니다."이고 목록에 남는다

### CT-067 파트너로(비활성 링크 포함) 참조되는 연락처는 지울 수 없다
- Given 파트너 P를 연결한 Deal 1건과, 파트너 교체로 링크가 비활성인 파트너 Q의 Deal 1건이 있다
- When P와 Q를 각각 삭제한다
- Then 둘 다 409 `invalid-state` "연결된 Deal이 1건 있어 삭제할 수 없습니다."이고 남는다

### CT-068 거절 문구의 건수는 참조 Deal 수이고 한 Deal이 고객·파트너로 함께 참조해도 1건이다
- Given 고객 연락처 C를 쓰는 Deal 3건이 있고, (저장소 Fake로) 연락처 X를 같은 Deal의 고객과 파트너로 함께 참조하게 했다
- When C와 X를 각각 삭제한다
- Then C는 "연결된 Deal이 3건 있어 삭제할 수 없습니다.", X는 "연결된 Deal이 1건 있어 삭제할 수 없습니다."다

### CT-069 참조하던 Deal을 지우면 연락처를 지울 수 있다
- Given 고객 연락처를 쓰던 Deal을 삭제했다
- When 그 연락처를 삭제한다
- Then 204이고 연락처 수는 0이다

### CT-070 다른 연락처를 참조하는 Deal은 삭제를 막지 않는다
- Given 연락처 "한가한회사"와, Deal이 쓰는 연락처 "바쁜회사"가 있다
- When "한가한회사"를 삭제한다
- Then 204이고 "바쁜회사"는 남는다

### CT-071 예전 고객·파트너 경로는 admin이 불러도 404이고 Location이 없다
- Given ROOT로 로그인했다
- When `/api/v1/customers`·`/api/v1/partners`의 GET·POST와 `/{id}`의 GET·PUT·DELETE 10개를 각각 부른다
- Then 모두 404이고 `Location` 헤더가 없다

### CT-072 관리 화면은 8칸 표로 첫 20건을 보이고 없는 값은 '-', 연결 Deal 수를 보인다
- Given 연락처 24건(그중 "한빛은행 정민수, 과장, …@hanbit.test, 참조 Deal 1건", 직급·이메일·전화 없는 연락처 포함)이 있다
- When admin이 `/admin/contacts`를 연다
- Then 머리글 구분·회사명·담당자명·직급·이메일·전화·연결 Deal·작업이 있고 본문 행은 20개, 정민수 행에 "과장"·이메일·"1"이 보이며 없는 값 칸은 "-"이다

### CT-073 20건을 넘으면 페이저로 다음 페이지를 본다
- Given 연락처 24건이 있고 관리 화면이 열려 있다
- When "다음"을 누른다
- Then 본문 행이 4개이고 "다음"이 비활성이다

### CT-074 구분을 고르면 그 종류만 보인다
- Given 파트너 7건을 포함한 관리 화면이 열려 있다
- When "구분"에서 파트너를 고른다
- Then 본문 행 7개가 모두 "파트너" 배지이고 고객 행("한빛은행")은 없다

### CT-075 검색어(버튼·Enter)는 첫 페이지부터 찾고 이메일로도 찾는다
- Given 관리 화면 2페이지를 보고 있다
- When 검색어 "한빛"을 Enter로 검색하고, 이어서 "bae1@nuri"를 "검색" 버튼으로 검색한다
- Then 앞은 "한빛"이 든 3행(임태호 포함), 뒤는 배성훈 1행이다

### CT-076 검색어를 비우고 검색하면 전체 목록으로 돌아온다
- Given "한빛"으로 검색해 3행이 보인다
- When 검색어를 비우고 "검색"을 누른다
- Then 본문 행이 20개다

### CT-077 결과가 없으면 조건 유무에 따라 다른 빈 문구를 보인다
- Given 관리 화면이 열려 있다(또는 연락처가 하나도 없다)
- When "없는회사"로 검색한다(또는 조건 없이 화면을 연다)
- Then "조건에 맞는 연락처가 없습니다."(또는 "등록된 연락처가 없습니다.")를 보인다

### CT-078 목록을 읽지 못하면 오류 배너에 서버 문구를 보인다
- Given 목록 조회가 서버 오류("로그인이 필요합니다.")로 실패한다
- When admin이 관리 화면을 연다
- Then 오류 배너(`alert`)에 "로그인이 필요합니다."가 보인다

### CT-079 고객·파트너 연락처를 등록하면 폼이 닫히고 알림과 함께 목록에 Deal 0으로 나온다
- Given 관리 화면에서 "연락처 등록"으로 폼을 열었다
- When 연락처 구분 고객, 회사명 "새솔물산", 담당자명 "홍길동", 직급 "대리"(이메일 없이)를 넣고 저장한다(파트너는 이메일·전화까지 넣어)
- Then 폼이 닫히고 알림 "연락처를 등록했습니다."가 보이며, 검색하면 "새솔물산 홍길동" 행의 연결 Deal이 "0"이다(파트너는 구분 파트너로 거르면 보인다)

### CT-080 등록·수정 폼은 회사명·담당자명·이메일·전화의 공백을 입력 즉시 지우고 안내하며 직급은 공백을 허용한다
- Given 등록 폼(또는 "정민수" 수정 폼)이 열려 있다
- When 회사명에 "새 솔 물산"(또는 담당자명에 "정 민 수")을 입력하고, 직급에 "수석 과장"을 입력한다
- Then 회사명 칸 값은 "새솔물산"(담당자명은 "정민수")이고 "공백은 입력할 수 없습니다."가 보이며, 직급 칸은 "수석 과장" 그대로다

### CT-081 필수 칸이 비면 요청 없이 칸 아래에 문구를 보인다
- Given 등록 폼이 열려 있다
- When 아무것도 넣지 않고 저장한다
- Then "회사명을 입력하세요."·"담당자명을 입력하세요."가 보이고 등록 요청은 가지 않는다

### CT-082 이메일·전화 형식이 틀리면 요청 없이 칸 아래에 문구를 보인다
- Given 등록 폼에 회사명·담당자명을 넣었다
- When 이메일 "nope"(또는 전화 "12-34")로 저장한다
- Then "이메일 형식이 올바르지 않습니다."(또는 "전화번호 형식이 올바르지 않습니다.")가 보이고 등록 요청은 가지 않는다

### CT-083 서버가 같은 사람으로 거절하면 폼 안에 서버 문구를 보이고 폼을 유지한다
- Given 이메일 없는 고객 "미래전자 권나연"이 있고 등록 폼이 열려 있다
- When 같은 회사명·담당자명으로 저장한다
- Then 폼 안 `alert`에 "이미 등록된 연락처입니다."가 보이고 "연락처 등록" 폼이 그대로 있다

### CT-084 취소하면 요청 없이 폼이 닫힌다
- Given 등록 폼이 열려 있다
- When "취소"를 누른다
- Then 폼이 사라지고 등록 요청은 가지 않는다

### CT-085 수정 폼은 현재 값과 공유 Deal 수 안내를 보이고 저장하면 알림과 함께 표에 반영된다
- Given Deal 1건이 쓰는 "한빛은행 정민수"가 있다
- When 그 행의 "수정"을 눌러 직급을 "부장"으로 바꿔 저장한다
- Then 폼에는 회사명 "한빛은행"·담당자명 "정민수"가 채워져 있고 "이 연락처를 쓰는 1개 Deal에 모두 반영됩니다."가 보였으며, 저장 뒤 폼이 닫히고 알림 "연락처를 수정했습니다."와 함께 그 행 직급이 "부장"이다

### CT-086 참조 Deal이 없는 연락처의 수정 폼에는 공유 안내가 없다
- Given 방금 등록한 "새솔물산 홍길동"(참조 Deal 없음)이 있다
- When 그 행의 "수정"을 누른다
- Then 수정 폼에 "Deal에 모두 반영됩니다" 문구가 없다

### CT-087 연락처를 고치면 그 연락처를 쓰는 Deal의 Quick View와 상세에 새 값이 보인다
- Given Deal이 쓰는 고객 연락처가 있다
- When admin이 관리 화면에서 그 연락처의 직급을 바꿔 저장한 뒤 Deals 목록 Quick View와 Deal 상세를 연다
- Then 두 곳 모두 바뀐 직급이 보인다

### CT-088 참조 중인 연락처 삭제는 대화상자를 닫고 배너에 건수 문구를 보이며 행이 남는다
- Given Deal 1건이 쓰는 "한빛은행 정민수"가 있다
- When 그 행의 "삭제"를 누르고 "연락처 삭제" 대화상자에서 "삭제"를 누른다
- Then 대화상자가 닫히고 오류 배너에 "연결된 Deal이 1건 있어 삭제할 수 없습니다."가 보이며 정민수 행이 남는다

### CT-089 참조 없는 연락처는 확인 뒤 삭제되고 알림을 보인다
- Given 참조 Deal이 없는 "새솔물산 홍길동"이 있다
- When 그 행의 "삭제"를 누르고 대화상자에서 "삭제"를 누른다
- Then 그 행이 사라지고 알림 "새솔물산 홍길동 연락처를 삭제했습니다."가 보인다

### CT-090 삭제 확인을 취소하면 요청하지 않는다
- Given 참조 Deal이 없는 "새솔물산 홍길동"이 있다
- When "삭제"를 누르고 대화상자에서 "취소"를 누른다
- Then 삭제 요청은 가지 않고 행이 남는다

### CT-091 화면 입력 규칙은 서버와 같은 공백·필수·이메일·전화 경계값으로 판정한다
- Given 화면 규칙 `validateContactInput`
- When 공백(스페이스·탭·전각)이 든 회사명·담당자명·이메일·전화, 빈 회사명·담당자명, 이메일 경계값(254자·255자·`a@b`), 전화 경계값(숫자 6·7·15·16개, 문자 포함, 공백 포함), 공백이 든 직급을 각각 검사한다
- Then 서버(CT-R2·R4·R5)와 같은 칸에 같은 문구가 나오고 공백 오류가 형식 오류보다 먼저이며, 직급과 null 이메일·전화는 오류가 없다

### CT-092 화면 같은 사람 판정은 서버와 같은 3단계 규칙이다
- Given 같은 회사명·담당자명(대소문자만 다른 것 포함)의 연락처들(이메일 있음·없음, 다른 종류)이 있다
- When `findSamePerson`으로 이메일 없음·같은 이메일·다른 이메일·자기 제외(excludeId) 입력을 판정한다
- Then 결과가 CT-R7과 같다(이메일 없음 → 가장 작은 id, 같은 이메일 → 그 연락처, 다른 이메일 → 이메일 없는 후보 또는 없음, 다른 종류는 비교하지 않음)

### CT-093 선택기의 회사 후보는 그 종류의 회사 목록이다
- Given 파트너 회사 목록이 있다
- When 파트너 선택기의 "파트너 회사명" 콤보를 연다
- Then 파트너 종류로 회사 목록을 조회하고 그 회사들이 후보로 보인다

### CT-094 회사를 정하면 그 회사(대소문자 무시)의 담당자가 직급·이메일 설명과 함께 후보로 나온다
- Given "한빛상사"에 김철수(부장, kim@hanbit.kr)·이영희(대리)·박무메일(사원, 이메일 없음)이 있다
- When 고객 회사명에 "한빛상사"(또는 대소문자가 다른 표기)를 넣고 담당자 콤보를 연다
- Then 세 사람이 후보이고 김철수의 설명은 "부장 · kim@hanbit.kr", 박무메일은 "사원"이다

### CT-095 기존 담당자를 고르면 직급·이메일·전화가 채워지고 그 연락처 id가 잡힌다
- Given 회사명 "한빛상사"를 넣었다
- When 담당자 후보에서 김철수를 고른다
- Then 직급 "부장", 이메일 "kim@hanbit.kr", 전화 "010-1234-5678"이 채워지고 값의 `contactId`가 김철수의 id다

### CT-096 채운 연락 정보를 고쳐도 연락처 id는 유지된다
- Given 김철수를 골라 연락 정보가 채워졌다
- When 직급을 "상무"로 고친다
- Then `contactId`는 그대로 김철수의 id이고 직급은 "상무"다

### CT-097 새 회사·사람을 직접 입력하면 새 연락처(id 없음)다
- Given 빈 선택기
- When 목록에 없는 회사명과 담당자명을 입력한다
- Then `contactId`는 null이고 입력한 회사명·담당자명이 값이 된다

### CT-098 고른 담당자의 이름을 다른 이름으로 바꾸면 연락처 id가 풀린다
- Given 김철수를 골랐다
- When 담당자명을 "김영수"로 고친다(대소문자만 바꾸면 유지)
- Then `contactId`가 null이다

### CT-099 회사를 다른 회사로 바꾸면 고른 사람과 연락 정보가 비워진다
- Given "한빛상사"의 김철수를 골랐다
- When 회사명을 "대한소프트"로 바꾼다
- Then 담당자명·직급·이메일·전화가 비고 `contactId`가 null이다(회사명 대소문자만 바꾸면 그대로)

### CT-100 선택기에서 이메일·전화를 비우면 null이 된다
- Given 이메일·전화가 채워진 선택기
- When 이메일과 전화 칸을 지운다
- Then 값의 이메일·전화가 null이다

### CT-101 선택기는 회사명·담당자명·이메일·전화의 공백(붙여넣기 포함)을 지우고 안내하며 직급은 허용한다
- Given 빈 선택기
- When 회사명에 "한빛 상사"를 입력하고 담당자명·이메일·전화에 공백이 든 값을 붙여넣고 직급에 "수석 과장"을 입력한다
- Then 네 칸의 값에서 공백이 빠지고 "공백은 입력할 수 없습니다." 안내가 보이며 직급은 "수석 과장" 그대로다

### CT-102 이메일 칸을 떠난 뒤 형식이 틀리면 안내하고 폼이 준 칸 오류를 보인다
- Given 선택기 이메일 칸에 "nope"를 넣었다(폼이 회사명 오류 "고객 회사명을 입력하세요."를 넘긴 경우도 있음)
- When 이메일 칸을 떠난다
- Then 이메일 칸 아래에 "이메일 형식이 올바르지 않습니다."가, 회사명 칸 아래에 폼이 준 문구가 `alert`로 보인다

### CT-103 이메일 없이 기존 사람과 같은 회사명·담당자명이면 같은 사람 안내를 보이고 이메일이 있으면 보이지 않는다
- Given "한빛상사 박무메일"이 있고 선택기에서 고르지 않고 직접 입력 중이다
- When 회사명 "한빛상사", 담당자명 "박무메일"을 이메일 없이 입력한다(또는 이메일을 함께 입력한다)
- Then "기존 연락처와 같은 사람으로 처리됩니다(회사명·담당자명 일치, 이메일 없음)."가 보인다(이메일이 있으면 보이지 않는다)

### CT-104 고른 연락처를 다른 Deal도 쓰면 공유 안내를 보인다
- Given 김철수의 참조 Deal이 3건이다
- When 새 Deal 폼(`linkedHere` false) 선택기에서 김철수를 고른다
- Then "이 연락처는 3개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다."가 보인다(이미 연결된 Deal에서 참조가 1건뿐이면 보이지 않는다)

### CT-105 rows 배치는 짧은 보이는 라벨, 기본 배치는 전체 라벨이다
- Given 고객 선택기
- When `layout="rows"`로(또는 지정하지 않고) 그린다
- Then rows는 보이는 라벨이 "회사"·"담당자"·"직급"·"이메일"·"전화"이고 접근성 이름은 "고객 회사명" 등 전체 글자이며 범례가 숨겨진다(기본은 범례 "고객"과 전체 라벨)

### CT-106 게이트웨이는 조회에 정한 조건만 보내고 응답의 null 직급을 빈 값으로 바꾼다
- Given HTTP 게이트웨이와 가짜 서버 응답
- When 회사 목록·회사별 담당자·관리 목록(조건 일부만)을 조회한다
- Then 요청 쿼리에는 정한 조건만 있고, 응답 항목의 null 직급은 `''`, `deal_count`는 `dealCount`, 목록의 `total`은 그대로다

### CT-107 게이트웨이는 쓰기에 빈 직급을 null로, 수정은 종류 없이 보내고 삭제 204·409 문구를 다룬다
- Given HTTP 게이트웨이와 가짜 서버 응답
- When 직급 `''`으로 등록하고, 수정하고, 삭제(204와 409 두 경우)한다
- Then 등록 본문은 `kind`와 직급 null을, 수정 본문은 `kind` 없이 다섯 값을 보내고, 204는 성공, 409는 서버 `detail`("연결된 Deal이 N건 있어 삭제할 수 없습니다.")을 가진 `ApiError`다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 최초 작성(구현된 동작을 정본으로 옮김, 초안) | CT-001~CT-107 |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체(UI-R18~R21, UI-R30). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
