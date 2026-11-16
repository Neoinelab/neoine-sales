# 계약관리(라이선스 계약)   (feature 코드: LC, 상태: 확정(2026-11-16 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-09 시범 적용). 근거는 작업 트리의 코드(`backend/src/app/**/license_contract*`, Deal 유스케이스 4경로·Deal 삭제, `frontend/src/features/contracts/**`, `frontend/src/features/deals/useWonExitConfirm.tsx` 등)이며, 이전 계획 `artifacts/10-analysis/license-contracts-plan.md`와 코드가 다른 곳은 코드를 따랐습니다. 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 화면 문구의 "라이선스"/"라이선스" 혼용은 코드 그대로입니다(통일은 후속 과제).
>
> **2026-11-09 사용자 결정으로 코드와 달라지는 규칙 2개**(구현 전까지 현재 코드와 다름): 정렬 키 `deal_code` 제거(LC-R18, LC-021·LC-084), 계약 삭제는 admin이 아니면 존재 여부와 무관하게 403 먼저(LC-R15·LC-R28, LC-029·LC-083).
>
> 2026-11-16 변경(초안, 사용자 확인 대기): Deal의 Solution을 Product로 이름 변경(화면 문구, API 필드·쿼리 `product`, Reports key `deal.product`, DB 컬럼 `deals.product`). 영향 규칙·케이스는 5장.

## 1. 개요

- 목적: Won(계약 완료)이 된 Deal의 라이선스 계약을 관리한다. 계약은 Deal이 Won이 될 때 자동으로 생기고, 영업·관리자가 발급·갱신·종료·첨부를 관리한다. 발급된 계약이 있는 Deal은 Won에서 벗어날 수 없다.
- 사용자(역할): `admin`(모든 조작 + 계약 삭제), `sales`(조회·계약 칸 수정·발급·갱신·종료·첨부), `user`(조회·다운로드만).
- 범위
  - 계약 목록(검색·정렬·50건씩 무한 스크롤)·단건 조회·계약 칸 수정·발급·갱신·종료·admin 삭제
  - 계약 첨부 목록·업로드(ask/skip/replace)·다운로드·삭제
  - Deal 연동: Won 진입 시 자동 생성, Won 이탈 시 삭제/유지 선택과 발급 계약 차단, Deal 삭제 시 함께 삭제, Deal 응답의 계약 건수·발급 여부
- 범위 밖: 수동 '계약 추가', 기존 Won Deal 계약 일괄 생성(2026-11-09 제외 확정), 종료일 경과 자동 종료, 만료 알림, Deal 상세 안 계약 목록, Reports·Dashboard 연계, 계약 변경의 Deal History 기록, 동시 수정 잠금(마지막 저장이 이김), 경쟁·동시성 테스트
- 관련 화면·메뉴: 메뉴 "계약관리"(Deals 오른쪽, `/contracts`, 모든 역할), 계약 수정 대화상자, Deal 화면 4곳의 '라이선스 계약 처리' 대화상자(Deal 폼 수정, 목록 인라인 편집, 상세 요약 바, Action 등록), Deal 삭제 확인 대화상자

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 계약 | `license_contracts` 한 행. Deal 하나에 속한다(Deal 1:N) |
| 계약 칸 | 계약 자체 값: 기술담당(`tech_owner`, 자유 텍스트), 점검주기(`inspection_cycle`), Note(`note`) |
| Deal 값 | 계약 행에 함께 보이지만 Deal에서 읽는 값: Deal 코드·Deal명·고객사명·Vendor·제품명·파트너사·담당영업 |
| 기간 | 라이선스 시작일·종료일·기간(수량 1~99 + 단위 `month`/`year`) |
| 발급 상태 | `issued_new`(발급(신규)) 또는 `issued_renewal`(발급(갱신)) |
| Won | Deal Forecast가 `won`인 상태. 동기화 규칙상 Status `contract_completed`와 항상 함께 움직인다 |
| Won 진입 / Won 이탈 | 변경 전에 Won이 아니고 변경 후 Won이면 진입, 변경 전에 Won이고 변경 후 Won이 아니면 이탈 |
| Deal 변경 4경로 | ① Deal 등록 `POST /deals` ② Deal 폼 수정 `PATCH /deals/{code}` ③ 단일 변경 적용 `POST /deals/{code}/changes`(목록 인라인·상세 요약 바) ④ Action 등록 `POST /deals/{code}/actions`의 `status_changes` |
| 저장 위치 | 첨부 파일을 두는 서버 디렉터리(`storage_settings`). 없으면 첨부 업로드·다운로드를 할 수 없다 |
| 계약 폴더 | `<저장 위치>/license-contracts/<계약 id>/` |

### 2.2 데이터 모델

`license_contracts`

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | BIGINT identity (MAXVALUE 2^53−1) | PK | API에서 JSON 정수 |
| deal_id | BIGINT | NOT NULL, FK `deals.id` ON DELETE CASCADE | |
| status | VARCHAR(20) | NOT NULL, CHECK 4값 | `not_issued`·`issued_new`·`issued_renewal`·`ended` |
| license_start, license_end | DATE | NULL | 종료일은 서버 계산(LC-R4) |
| term_amount | SMALLINT | NULL, CHECK 1~99 | |
| term_unit | VARCHAR(10) | NULL, CHECK `month`/`year` | |
| tech_owner | VARCHAR(100) | NOT NULL DEFAULT '' | |
| inspection_cycle | VARCHAR(20) | NOT NULL DEFAULT 'none', CHECK 5값 | `monthly`·`quarterly`·`semiannual`·`yearly`·`none` |
| note | TEXT | NOT NULL DEFAULT '' | 앱 검증 2000자 |
| renewed_from_id | BIGINT | NULL, FK `license_contracts.id` ON DELETE SET NULL | 갱신 원본 |
| ended_on | DATE | NULL | 종료일(종료한 요청의 업무 날짜) |
| created_by_user_id, updated_by_user_id | BIGINT | NOT NULL, FK `users.id` RESTRICT | |
| created_at, updated_at | TIMESTAMPTZ | NOT NULL | |

- CHECK: 기간 네 칸은 모두 NULL이거나 모두 NOT NULL / `not_issued`면 기간 없음 / 발급 상태면 기간 있음 / 종료일 ≥ 시작일 / `ended_on`은 `status = 'ended'`일 때만(`ck_license_contracts_ended_has_date`).
- 부분 유니크 인덱스 `uq_license_contracts_deal_id_issued` ON (deal_id) WHERE status IN ('issued_new','issued_renewal').
- Deal 값 컬럼(고객사·Vendor·제품·파트너·담당영업)은 없다.

`license_contract_attachments`: id BIGINT identity PK, contract_id FK `license_contracts.id` ON DELETE CASCADE, file_name VARCHAR(255), description VARCHAR(100) DEFAULT '', mime VARCHAR(255), size_bytes BIGINT CHECK 0~104,857,600, storage_key VARCHAR(32) UNIQUE, uploaded_by_user_id FK users RESTRICT, uploaded_at, created_at, updated_at. UNIQUE(contract_id, file_name).

도메인: `domain/license_contract/`의 `LicenseContract`(`create_for_won`·`revise`·`issue`·`renew`·`end`·`ensure_deletable_by`), `ContractStatus`·`InspectionCycle`·`LicenseTerm`·`ContractFields`(값 객체), `license_end`(종료일 계산), `won_transition`·`ensure_can_leave_won`·`ensure_issuable_on`(Won 규칙), `ContractAttachment`.

### 2.3 비즈니스 규칙

계약과 Deal
- **LC-R1** 계약은 Deal 하나에 속하고 한 Deal에 계약이 여러 개 있을 수 있다. 계약 행이 보여 주는 Deal 값은 조회 시점의 Deal 값이다: 고객사명 = Deal 고객 연락처의 회사명, Vendor = Deal Vendor(`{id, name}`, 없으면 null), 제품명 = Deal Product(2026-11-16 전 이름 Solution, 컬럼 `deals.product`), 파트너사 = Deal의 연결 해제되지 않은 파트너 연락처 회사명(없으면 null), 담당영업 = Deal Owner(퇴사자 포함). Deal 값을 바꾸면 계약 행에도 바로 반영된다.
- **LC-R2** 상태는 4개이고 전이는 2.4의 표만 허용한다. 허용되지 않은 전이는 409 `invalid-state`이고 계약은 바뀌지 않는다.
- **LC-R3** 한 Deal에 발급 상태 계약은 최대 1건이다. 같은 Deal에 다른 발급 상태 계약이 있을 때의 발급은 409 `invalid-state` "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다."이다(DB 부분 유니크 인덱스가 같은 상황을 거부). 종료·미발급 계약, 다른 Deal의 계약은 이 제한에 들지 않는다.
- **LC-R4** 종료일은 요청으로 받지 않고 서버가 `시작일 + 기간 − 1일`로 계산한다. 시작일이 d일(d>1)이면 (시작 월 + 기간)달의 d−1일, 그 달에 그날이 없으면 그 달 말일이다. 시작일이 1일이면 (시작 월 + 기간)달 1일의 전날(전달 말일)이다. 예: 2026-01-01+1년=2026-12-31, 2026-01-01+6개월=2026-06-30, 2026-03-15+1개월=2026-04-14, 2026-11-15+3개월=2027-02-14, 2026-01-31+1개월=2026-02-28. 기간 수량은 1~99, 단위는 `month`·`year`. 시작일은 1900-01-01~2999-12-31이어야 하고("라이선스 시작일은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"), 종료 연도가 2999를 넘으면 422 `invalid-value` "라이선스 종료일이 허용 범위를 벗어납니다."이다. 화면의 종료일 미리보기(`licenseEnd`)는 같은 계산이다.
- **LC-R5** 미발급 계약은 시작일·종료일·기간이 모두 없다. 발급 상태 계약은 모두 있다. 종료된 계약은 종료 직전의 기간을 그대로 가진다(미발급에서 종료했으면 없음). `ended_on`은 종료 상태에만 있다.
- **LC-R38** 기존 데이터 변환(리비전 `b4d7e2a9c613`, SC-R20): `ended_on`은 저장된 `ended_at`을 업무 시간대(서버 OS 로컬)로 바꾼 날짜다. 값이 없던 행은 계속 null이다. CHECK `ck_license_contracts_ended_has_time`은 `ck_license_contracts_ended_has_date`로 다시 만든다. 행 수는 그대로이고 시각만 버린다. downgrade는 종료일의 업무 시간대 00:00으로 되살린다.

Won 연동
- **LC-R6** Won 판정은 Forecast `won`이다. 등록(경로 ①)은 변경 전 상태가 없으므로 진입만 생길 수 있다. Action 등록(경로 ④)의 여러 단계 변경은 처음과 끝만 비교한다. 시작과 끝이 모두 Won인 변경(예: 금액만 변경)은 진입도 이탈도 아니다.
- **LC-R7** Won 진입이고 그 Deal에 계약이 하나도 없으면(종료 포함 0건) Deal 변경과 같은 트랜잭션에서 미발급 계약 1건이 생긴다: 기술담당 '', 점검주기 `none`, Note '', 기간 없음, 등록자·수정자 = 요청자. 계약이 1건이라도 있으면 만들지 않는다. Deal 변경이 거절되면 계약도 생기지 않는다. 계약을 직접 만드는 API는 없고, 이미 Won인 Deal에 계약을 일괄로 만드는 동작도 없다.
- **LC-R8** Won 이탈인데 그 Deal에 발급 상태 계약이 있으면 경로 ②③④ 모두 409 `invalid-state`, `detail` = "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."이다. `delete_license_contracts` 값(true·false·생략)과 무관하다. 이 요청은 아무것도 저장하지 않는다(Deal Status·Forecast·History·계약·첨부 그대로, Action 경로는 Action 행과 이전 Next Action 종료도 저장 안 함). 잘못 발급한 경우의 정정 경로는 admin의 계약 삭제(LC-R15)다.
- **LC-R9** Won 이탈이고 발급 상태 계약이 없을 때 요청의 `delete_license_contracts: true`면 그 Deal의 계약과 계약 첨부 행이 모두 지워지고(같은 트랜잭션), 커밋 뒤 지운 계약들의 계약 폴더가 지워진다(LC-R26). false이거나 생략하면 계약은 그대로 남는다. Won 이탈이 아닌 변경에서는 이 값을 무시한다(오류 없음, 아무것도 지우지 않음). Deal을 바꿀 수 있는 역할(sales·admin) 누구나 삭제를 고를 수 있다. 이 필드는 경로 ②③④의 요청에만 있고(`StrictBool`, 기본 false, 불리언이 아니면 422 `request-validation`) 경로 ① 요청에는 없다.
- **LC-R10** 발급·갱신은 Deal이 Won일 때만 된다. Won이 아니면 409 `invalid-state` "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."이고 계약은 바뀌지 않는다. 계약 칸 수정·종료·첨부·admin 삭제는 Deal 상태와 무관하게 된다.

계약 조작
- **LC-R11** 발급: 미발급 계약만 발급(신규)가 된다. 요청의 계약 칸·시작일·기간을 저장하고 종료일을 계산한다. 응답 200. 검사 순서: 없는 계약 404 → Deal이 Won 아님 409(LC-R10) → 미발급 아님 409 "미발급 계약만 발급할 수 있습니다." → 같은 Deal에 다른 발급 계약 409(LC-R3).
- **LC-R12** 갱신: 발급 상태 계약만 갱신된다(아니면 409 "발급 상태 계약만 갱신할 수 있습니다."). 한 트랜잭션에서 이전 계약은 종료(`ended_on` = 오늘)되고 같은 Deal에 새 계약(`issued_renewal`, `renewed_from_id` = 이전 id, 계약 칸·시작일·기간 = 요청 값)이 생긴다. 응답 201, `Location: /api/v1/license-contracts/<새 id>`, 본문은 새 계약. 갱신 시작일은 제약이 없다(이전 종료일 다음 날은 화면 기본값일 뿐). 첨부는 이전 계약에 남는다. 검사 순서: 404 → Won 아님 409 → 발급 상태 아님 409.
- **LC-R13** 종료: 종료가 아닌 계약(미발급·발급(신규)·발급(갱신))은 종료로 바뀌고 `ended_on`(오늘)이 기록되며 기간은 유지된다. 이미 종료면 409 "이미 종료된 계약입니다."이고 첫 종료일이 유지된다. 종료된 계약은 다시 발급·갱신할 수 없다(LC-R11·R12의 409). 종료일이 지나도 자동으로 종료되지 않는다.
- **LC-R14** 계약 칸 수정(`PUT`)은 모든 상태에서 되며 세 칸을 통째로 바꾼다(부분 수정이 아님, 2026-11-09 확정): 요청에서 생략한 칸은 기본값(기술담당 '', 점검주기 `none`, Note '')으로 저장된다. 기간·Deal·등록자·갱신 원본은 바뀌지 않고 수정자·수정 시각은 요청자·요청 시각이 된다. 텍스트는 앞뒤 공백을 지우고 저장하며 비어도 된다. 한도(오류 형식 차이는 2026-11-09 정본 확정): 기술담당 100자(요청 원문, 즉 공백 제거 전 기준 초과 시 422 `request-validation`), Note 2000자(공백 제거 후 초과 시 422 `invalid-value` "Note은(는) 2000자를 넘을 수 없습니다"), NUL 문자는 422 `invalid-value`("기술담당에는 NUL 문자를 쓸 수 없습니다" / "Note에는 NUL 문자를 쓸 수 없습니다"). Deal 값 칸(`customer`·`vendor`·`product`·`partner`·`sales_owner` 등)이나 알 수 없는 필드는 422 `request-validation`이다.
- **LC-R15** 삭제는 admin만, 상태와 무관하게 된다(204). **admin이 아니면 계약이 있든 없든 403이 먼저다**(2026-11-09 결정): user는 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)", sales는 403 `forbidden` "계약 삭제는 관리자만 할 수 있습니다.". 없는 계약의 404는 admin에게만 나온다. 계약 첨부 행이 함께 지워지고 커밋 뒤 그 계약 폴더가 지워진다. 같은 Deal의 다른 계약·Deal 첨부는 그대로다. 갱신 원본을 지우면 그 후속 계약의 `renewed_from_id`는 null이 된다.
- **LC-R16** 계약 변경(수정·발급·갱신·종료·삭제·첨부 업로드·첨부 삭제)은 Deal History를 남기지 않고 Deal 수정 시각도 바꾸지 않는다.

목록
- **LC-R17** 목록 조건은 AND다. `customer`(고객사명)·`product`(제품명)는 Deal 값의 대소문자 무시 부분 일치이며 `%`·`_`·`\`는 글자 그대로다. 앞뒤 공백을 지우고 비면 조건이 아니다. 최대 200자. `vendor_id`는 Deal Vendor id, `owner_user_id`는 Deal Owner id(퇴사자 포함) 일치, `status`는 4값 중 하나. 날짜 범위 `start_from`·`start_to`(시작일), `end_from`·`end_to`(종료일)는 양끝 포함, 한쪽만 줄 수 있고, 날짜 조건이 있으면 그 날짜가 없는 계약은 빠진다. 범위가 거꾸로면 422 `invalid-value` "라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다." / "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."(같은 날은 허용). 날짜는 1900-01-01~2999-12-31.
- **LC-R18** 정렬 `sort`는 12개(`deal_name`·`customer`·`vendor`·`product`·`partner`·`license_start`·`license_end`·`status`·`sales_owner`·`tech_owner`·`inspection`·`note`)로 화면 표의 12열과 같다. `deal_code`는 정렬 키가 아니다(2026-11-09 제거, 보내면 다른 잘못된 정렬 키와 같은 422 `request-validation`). `order`는 `asc`·`desc`, 기본은 `license_end` `asc`. 텍스트는 소문자 C 정렬, 상태 순서는 not_issued < issued_new < issued_renewal < ended, 점검주기 순서는 monthly < quarterly < semiannual < yearly < none, 담당영업은 Owner 표시 이름(없으면 login_id). 값 없는 칸(날짜 null, Vendor·파트너 없음, 빈 Deal명·제품명·기술담당·Note)은 방향과 무관하게 맨 뒤, 동률은 id 오름차순.
- **LC-R19** 페이지: `offset` 0 이상(기본 0), `limit` 1~200(기본 50). 응답은 `{items, total, offset, limit}`이며 `total`은 페이지와 무관한 조건 전체 건수다. 알 수 없는 쿼리 파라미터는 422 `request-validation`.
- **LC-R20** Deal 쪽 표시값: Deal 목록 행·상세 응답의 `license_contract_count`(종료 포함 그 Deal의 계약 수)와 `has_issued_license_contract`(발급 상태 계약이 있을 때만 true), 계약 응답의 `deal_is_won`(Deal Forecast가 won일 때 true), `GET /deals/{code}/deletion-impact`의 `license_contract_count`. 계약 첨부는 Deal의 `attachment_count`에 세지 않는다.

계약 첨부(Deal 첨부와 같은 규칙)
- **LC-R21** 업로드 검증 순서: 파일 없음 "업로드할 파일을 선택하세요." → 설명(NUL 문자가 있으면 길이 판정보다 먼저 "설명에는 NUL 문자를 쓸 수 없습니다" — 2026-11-10 보충, Deal 첨부 AT-R4와 같은 검사 / 앞뒤 공백 제거 후 100자 초과 "설명은 100자 이내로 입력하세요.") → 크기(104,857,600바이트 초과 "파일 크기가 100MB를 초과합니다. (최대 100MB)") → 차단 확장자(이름 끝 공백·점을 걷은 마지막 확장자, 대소문자 무시, 24개: exe msi bat cmd sh ps1 jar com scr dmg pkg deb rpm vbs vbe wsf wsh hta cpl msp mst apk appimage run, "실행·설치 파일(.<ext>)은 업로드할 수 없습니다.") → 파일 이름(NFC 정규화, 비었거나 255자 초과, `.`·`..`, `/`·`\`, 제어·서식 문자 "사용할 수 없는 파일 이름입니다."). 모두 422 `invalid-value`. 계약 상태·Deal의 Won 여부와 무관하게 업로드할 수 있다. 성공(새 파일)은 201 `{outcome: "uploaded", attachment}` + `Location: /api/v1/license-contract-attachments/<id>/download`.
- **LC-R22** 같은 계약에 같은 이름(NFC 비교, 대소문자 구분)이 있으면 `on_exists`에 따라: `ask`(기본) 409 `file-exists` "같은 이름의 파일이 이미 있습니다: <이름>", `skip` 200 `{outcome: "skipped", attachment: null}`(아무것도 바뀌지 않고 새 파일도 남지 않음), `replace` 200 `{outcome: "replaced"}`(같은 첨부 id, 내용·설명·업로더·업로드 시각 교체, 이전 파일은 커밋 뒤 삭제). 다른 계약의 같은 이름은 새 파일이다.
- **LC-R23** 첨부 삭제·교체 권한: admin은 모든 파일, sales는 본인이 올린 파일 또는 퇴사한 sales가 올린 파일, user는 불가. 위반은 403 `forbidden` "본인이 올린 파일만 삭제할 수 있습니다." / "본인이 올린 파일만 교체할 수 있습니다.". 없는 첨부는 권한 판정보다 먼저 404 "첨부 파일을 찾을 수 없습니다.".
- **LC-R24** 첨부 목록(최신 업로드 순, 같으면 id 내림차순)과 다운로드는 모든 로그인 역할이 할 수 있다. 다운로드는 `application/octet-stream`, `Content-Disposition: attachment`, 정확한 바이트. 저장 위치 설정이 없거나 읽을 수 없으면 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.", 행은 있는데 파일이 없으면 404 "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."(Deal 폴더 등 다른 위치에서 대신 읽지 않음). 저장 위치 없음의 업로드는 503 "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.".
- **LC-R25** 계약 첨부 파일은 `<저장 위치>/license-contracts/<계약 id>/<key>`에 저장된다. Deal 첨부는 `<저장 위치>/<deal_code>/<key>` 그대로다. 갱신으로 생긴 새 계약은 자기 id 폴더를 쓰고 이전 계약 파일은 이전 폴더에 남는다.
- **LC-R26** 파일 정리는 항상 커밋 뒤에 한다. 계약을 지우는 세 경로는 계약 폴더를 통째로 지운다: admin 계약 삭제(그 계약 폴더), Won 이탈 삭제(그 Deal의 모든 계약 폴더), Deal 삭제(Deal 폴더 + 그 Deal의 모든 계약 폴더). 첨부 하나를 지우면 그 파일만 지우고 계약 폴더는 남는다. 저장 위치 설정이 없으면 파일을 건드리지 않고, 디스크 삭제가 실패하면 경고 로그만 남기고 요청은 성공한다. 커밋이 실패하거나 권한 거절이면 폴더를 지우지 않는다. 업로드 도중(파일 저장 뒤 행 기록 전) 계약이 지워지면 업로드는 404로 끝나고 그 계약 폴더는 남지 않는다.

Deal 삭제·권한·사용자
- **LC-R27** Deal을 삭제하면 그 Deal의 계약·계약 첨부 행이 함께 지워진다(발급 계약이 있어도 계약 때문에 막지는 않는다. 다만 Won Deal의 삭제는 admin만 할 수 있다 — DD-R41, 2026-11-12). 파일은 LC-R26대로 정리한다.
- **LC-R28** 권한은 2.5의 표다. 판정 순서: 미인증 401 → `user`의 쓰기 요청 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(요청 본문 검증·존재 확인보다 먼저) → 요청 형식 422 `request-validation` → 없음 404 → 도메인 권한 403 → 상태 409. **예외: 계약 삭제는 admin 판정(403)이 존재 확인(404)보다 먼저다**(LC-R15). 첨부 삭제·교체는 기본 순서대로 404가 403보다 먼저다(LC-R23).
- **LC-R29** 계약 등록·수정자, 계약 첨부 업로더는 users FK RESTRICT라 그 사용자는 물리 삭제 대신 퇴사 처리된다(사용자 관리 feature의 연결 탐지가 적용).

화면(frontend)
- **LC-R30** 계약 목록 화면: 열 12개(Deal명, 고객사명, Vendor, 제품명, 파트너사, 라이선스 시작일, 라이선스 종료일, 상태, 담당영업, 기술담당, 점검주기, Note), Deal명 칸의 title은 Deal 코드, 빈 값은 `-`, 상태 표시 `미발급`·`발급(신규)`·`발급(갱신)`·`종료`, 점검주기 표시 `월 1회`·`분기 1회`·`반기 1회`·`연 1회`·`없음`. 50건씩 읽고 끝이 화면에 들어오면(또는 `더 보기`) 다음 50건을 잇는다. 같은 id는 한 번만 보인다. `전체 N건`은 서버 `total`, 다 읽으면 `모두 불러왔습니다 (전체 N건)`, 결과가 없으면 `조건에 맞는 계약이 없습니다.`. 머리글을 누르면 그 열로 서버 정렬(같은 열은 방향 전환, 다른 열은 오름차순), 기본은 종료일 오름차순. 행 클릭 또는 행에 포커스 후 Enter·Space로 계약 수정 대화상자를 연다.
- **LC-R31** 검색 바: 고객사명·제품명(텍스트, 200자, 앞뒤 공백 제거 뒤 비면 조건 아님), Vendor(Vendor 관리 목록, `전체`), 담당영업(사용자 선택, 퇴사자 포함), 상태(`전체` + 4개), 라이선스 시작일·종료일 기간 선택(Deals '최종 업데이트'와 같은 프리셋 + 직접 지정, 종료일에만 다가오는 기간 프리셋 2개). 텍스트 칸 Enter 또는 `검색`으로 적용, `초기화`로 모두 비움. 범위가 거꾸로면 검색하지 않고 그 칸에 서버와 같은 문구를 보인다.
- **LC-R32** 만료 임박 색: 발급 상태 계약만, 종료일 < 오늘+1개월이면 위험(`만료 1개월 미만`, 지난 날 포함), 종료일 < 오늘+2개월이면 주의(`만료 2개월 미만`). 오늘+N개월은 같은 날이 없으면 그 달 말일. 오늘은 서버 시계 기준. 상태 칸은 발급 상태면 `status-issued`, 종료면 `status-ended`.
- **LC-R33** 계약 수정 대화상자(제목 `계약 수정 - <Deal명>`): Deal 정보(고객사명·Vendor·제품명·파트너사·담당영업)는 읽기 전용, 기술담당·점검주기·Note는 sales·admin만 편집. 라이선스 칸(시작일·기간·종료일 미리보기)은 평소 비활성이고 `라이선스 발급`(미발급)·`라이선스 갱신`(발급 상태) 버튼을 눌러야 활성화된다(시작일로 포커스, 안내 `저장하면 발급(신규)됩니다`/`저장하면 발급(갱신)됩니다`). 발급 기본값은 오늘부터 1년, 갱신 기본값은 현재 종료일 다음 날부터 현재 기간. `저장`은 버튼을 누르지 않았으면 계약 칸 수정, 눌렀으면 발급 또는 갱신 요청을 보낸다. 시작일이 비었으면 `라이선스 시작일을 입력하세요.`, 기간이 1~99 정수가 아니면 `기간을 1~99 사이의 숫자로 입력하세요.`를 보이고 요청하지 않는다. Deal이 Won이 아니면(`dealIsWon` false) 발급·갱신 버튼은 비활성이고 힌트 `Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.`를 보인다. 종료 계약에는 발급·갱신·계약 종료 버튼이 없다. 성공하면 대화상자를 닫고 목록 위 알림(`계약을 수정했습니다.`·`라이선스를 발급했습니다.`·`라이선스를 갱신했습니다.`·`계약을 종료했습니다.`·`계약을 삭제했습니다.`), 서버 거절(409·422 등)은 대화상자 안 `role="alert"`로 보이고 닫히지 않는다. `취소`는 입력을 버린다. user에게는 `저장` 버튼이 없고 칸이 비활성이다.
- **LC-R34** `계약 종료`(종료가 아닌 계약, sales·admin)는 확인 대화상자(제목 `계약 종료 확인`, `Deal <Deal명>의 계약을 종료합니다. 종료한 계약은 다시 발급·갱신할 수 없습니다.`, 버튼 `종료`) 뒤에 요청한다. `삭제`(admin에게만, 모든 상태)는 확인 대화상자(제목 `계약 삭제`, `Deal <Deal명>의 계약과 첨부 파일을 삭제합니다. 삭제한 계약은 복구할 수 없습니다.`, 버튼 `삭제`) 뒤에 요청한다. 확인 대화상자에서 취소하면 아무것도 바뀌지 않는다.
- **LC-R35** 계약 첨부 영역(대화상자 안 `첨부 파일`): 목록(파일명·설명·크기·업로드한 사용자·업로드 시각), 파일명을 누르면 내려받기, 업로드 폼과 `관리` 열은 sales·admin에게만. 화면 규칙(파일 없음·차단 확장자·설명 100자)을 어기면 요청 없이 문구를 보인다. 409 `file-exists`면 `같은 이름의 파일` 확인(`교체`/`건너뛰기`, 교체 권한이 없으면 `교체` 비활성 + `본인이 올린 파일만 교체할 수 있습니다.`). 성공 알림 `업로드되었습니다: <이름>`·`교체되었습니다: <이름>`·`삭제되었습니다: <이름>`. 삭제는 확인(`첨부 파일 삭제`, `"<이름>" 파일을 삭제합니다.`) 뒤, 권한이 없는 행의 `삭제`는 비활성(title `본인이 올린 파일만 삭제할 수 있습니다.`). 서버 오류(503 등)는 서버 문구를 `role="alert"`로 보인다. 비었으면 `첨부된 파일이 없습니다.`.
- **LC-R36** Won 이탈 확인(화면 4곳: Deal 폼 수정, 목록 인라인 편집, 상세 요약 바, Action 등록): 동기화 확인(Forecast/Status 선택) 뒤, 요청 전에 판정한다. Won 이탈이 아니면 묻지 않는다. Won 이탈이고 `hasIssuedLicenseContract`면 '확인' 버튼 하나뿐인 안내 대화상자(제목 `라이선스 계약 처리`, 본문 LC-R8 문구)를 띄우고 요청하지 않으며 값은 원래대로다. 발급 계약이 없고 `licenseContractCount` ≥ 1이면 `라이선스 계약 처리` 대화상자(`이 Deal의 라이선스 계약 N건도 삭제할까요?`, 버튼 `취소`·`유지`·`삭제`)를 띄운다: 삭제 → `deleteLicenseContracts: true`, 유지 → false로 요청, 취소 → 요청하지 않음. 계약이 0건이면 묻지 않고 요청한다. 화면 값이 오래되어 서버가 409를 주면 각 화면의 기존 오류 자리에 서버 문구를 보이고 편집 상태를 유지하며 Deal을 다시 읽어, 같은 변경을 다시 시도하면 안내 대화상자가 뜬다.
- **LC-R37** Deal 삭제 확인 대화상자는 `라이선스 계약 N건`(0 포함)을 함께 지운다고 보여 준다.

### 2.4 상태와 전이

| 현재 \ 행동 | 발급(`/issue`) | 갱신(`/renewal`) | 종료(`/end`) | 계약 칸 수정 | admin 삭제 |
| --- | --- | --- | --- | --- | --- |
| `not_issued` 미발급 | → `issued_new` (Won Deal, 다른 발급 없음) | 409 ISSUED_ONLY | → `ended` | 가능 | 가능 |
| `issued_new` 발급(신규) | 409 NOT_ISSUED_ONLY | 이 행 → `ended` + 새 행 `issued_renewal` (Won Deal) | → `ended` | 가능 | 가능 |
| `issued_renewal` 발급(갱신) | 409 NOT_ISSUED_ONLY | 이 행 → `ended` + 새 행 `issued_renewal` (Won Deal) | → `ended` | 가능 | 가능 |
| `ended` 종료 | 409 NOT_ISSUED_ONLY | 409 ISSUED_ONLY | 409 ALREADY_ENDED | 가능 | 가능 |

- 생성은 Won 진입 자동 생성(`not_issued`)과 갱신(`issued_renewal`)뿐이다.
- Won이 아닌 Deal에서는 발급·갱신이 409 DEAL_NOT_WON(전이 판정보다 먼저).
- 발급 상태 계약이 있는 Deal은 Won을 벗어날 수 없다(LC-R8).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| 계약 목록·상세·첨부 목록·다운로드 | 401 | 가능 | 가능 | 가능 |
| 계약 칸 수정·발급·갱신·종료 | 401 | 403 | 가능 | 가능 |
| 계약 삭제 | 401 | 403(읽기 전용 문구, 존재 무관) | 403(관리자만 문구, 존재 무관) | 가능(없으면 404) |
| 첨부 업로드 | 401 | 403 | 가능(교체는 LC-R23) | 가능 |
| 첨부 삭제 | 401 | 403 | 본인·퇴사 sales 파일 | 모든 파일 |
| Won 이탈 시 계약 삭제 선택 | — | Deal 변경 불가 | 가능 | 가능 |

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/license-contracts` | query: `customer`, `product`, `vendor_id`, `owner_user_id`, `status`, `start_from`, `start_to`, `end_from`, `end_to`, `sort`(12값), `order`, `offset`, `limit` | 200 `CountedPage[LicenseContractResponse]` | 422 |
| GET `/license-contracts/{contract_id}` | — | 200 `LicenseContractResponse` | 404, 422(id 형식) |
| PUT `/license-contracts/{contract_id}` | `LicenseContractFieldsRequest` | 200 | 403, 404, 422 |
| POST `/license-contracts/{contract_id}/issue` | `LicenseIssueRequest` | 200(`issued_new`) | 403, 404, 409, 422 |
| POST `/license-contracts/{contract_id}/renewal` | `LicenseIssueRequest` | 201 + `Location`, 새 계약 | 403, 404, 409, 422 |
| POST `/license-contracts/{contract_id}/end` | — | 200(`ended`) | 403, 404, 409 |
| DELETE `/license-contracts/{contract_id}` | — | 204 | 403(admin이 아니면 먼저), 404(admin만) |
| GET `/license-contracts/{contract_id}/attachments` | — | 200 `{items: ContractAttachmentResponse[]}` | 404 |
| POST `/license-contracts/{contract_id}/attachments` | multipart `file`, `description`(기본 ''), `on_exists`(`ask`·`skip`·`replace`, 기본 `ask`) | 201 uploaded / 200 replaced·skipped | 403, 404, 409 `file-exists`, 422, 503 |
| GET `/license-contract-attachments/{attachment_id}/download` | — | 200 octet-stream | 404, 503 |
| DELETE `/license-contract-attachments/{attachment_id}` | — | 204 | 403, 404 |

- id 경로 파라미터는 1~2^53−1 정수(벗어나면 422 `request-validation`). 계약 생성(POST `/license-contracts`)은 없다.
- `LicenseContractSort` enum은 12값(`deal_name`, `customer`, `vendor`, `product`, `partner`, `license_start`, `license_end`, `status`, `sales_owner`, `tech_owner`, `inspection`, `note`). `deal_code`는 2026-11-09 제거(**공개 API 호환 깨짐, 사용자 승인**, 클라이언트는 이 저장소 프런트뿐이며 프런트는 이미 이 값을 보내지 않음). 응답 필드 `deal_code`는 그대로 있다.
- `LicenseContractFieldsRequest`(알 수 없는 필드 금지): `tech_owner`(str, 최대 100, 기본 ""), `inspection_cycle`(enum 5값, 기본 `none`), `note`(str, 기본 "", 도메인 2000자).
- `LicenseIssueRequest` = 위 필드 + `start_date`(date, 필수), `term_amount`(StrictInt 1~99, 필수), `term_unit`(`month`|`year`, 필수). 종료일 필드는 없다(보내면 422).
- `LicenseContractResponse`: `id`, `deal_code`, `deal_name`, `customer`, `vendor`(`{id,name}`|null), `product`, `partner`(str|null), `sales_owner`(UserRef), `status`, `license_start`·`license_end`(date|null), `term`(`{amount, unit}`|null), `tech_owner`, `inspection_cycle`, `note`, `renewed_from_id`(int|null), `ended_on`(date|null), `attachment_count`, `deal_is_won`, `created_by`·`updated_by`(UserRef), `created_at`·`updated_at`.
- `ContractAttachmentResponse`: `id`, `contract_id`, `deal_code`, `file_name`, `description`, `size`, `mime`, `uploaded_by`(UserRef), `uploaded_at`. 업로드 응답 `{outcome: "uploaded"|"replaced"|"skipped", attachment: ...|null}`.
- Deal API 쪽(하위 호환 추가): `PATCH /deals/{code}`·`POST /deals/{code}/changes`·`POST /deals/{code}/actions` 요청에 `delete_license_contracts`(StrictBool, 기본 false), 이 세 경로는 LC-R8의 409를 낼 수 있다. Deal 목록 행·상세 응답에 `license_contract_count`(int)·`has_issued_license_contract`(bool), `GET /deals/{code}/deletion-impact`에 `license_contract_count`.
- 오류 본문은 Problem JSON(`type` = `https://neoine-sales.example/problems/<kind>`, `title`, `status`, `detail`, `instance`). 예외 매핑: NotFoundError 404 `not-found`, AccessDeniedError 403 `forbidden`, AttachmentNameTakenError 409 `file-exists`, InvalidValueError 422 `invalid-value`, InvalidStateError 409 `invalid-state`, StorageUnavailableError 503 `storage-unavailable`, 요청 형식 422 `request-validation`("요청 형식이 올바르지 않습니다", `errors` 목록).

### 2.7 화면 동작

LC-R30~LC-R37. 화면은 게이트웨이(`gateway.licenseContracts`)로만 서버를 부르고, 계약 변경 성공 뒤 계약 목록을 처음부터 다시 읽고 Deal 쿼리도 무효화한다(Deal의 계약 건수·발급 여부 갱신). 종료일·만료 단계 계산은 미리보기용이며 서버 값이 정본이다. 화면의 정렬 키는 표 12열과 같아 `deal_code` 제거로 바뀌는 화면 동작은 없다.

### 2.8 오류와 메시지

| 상황 | 상태·type | detail(문구) |
| --- | --- | --- |
| 없는 계약 | 404 `not-found` | 라이선스 계약을 찾을 수 없습니다. |
| 없는 계약 첨부 | 404 `not-found` | 첨부 파일을 찾을 수 없습니다. |
| 첨부 파일 내용 없음 | 404 `not-found` | 첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요. |
| 미발급 아닌 계약 발급 | 409 `invalid-state` | 미발급 계약만 발급할 수 있습니다. |
| 발급 상태 아닌 계약 갱신 | 409 `invalid-state` | 발급 상태 계약만 갱신할 수 있습니다. |
| 이미 종료 | 409 `invalid-state` | 이미 종료된 계약입니다. |
| 같은 Deal 두 번째 발급 | 409 `invalid-state` | 이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다. |
| Won 아닌 Deal 발급·갱신 | 409 `invalid-state` | Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다. |
| 발급 계약 있는 Deal의 Won 이탈 | 409 `invalid-state` | 발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요. |
| sales의 계약 삭제(계약 존재 무관) | 403 `forbidden` | 계약 삭제는 관리자만 할 수 있습니다. |
| user의 쓰기 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |
| 남의 첨부 삭제·교체 | 403 `forbidden` | 본인이 올린 파일만 삭제할 수 있습니다. / 본인이 올린 파일만 교체할 수 있습니다. |
| 같은 이름 첨부(ask) | 409 `file-exists` | 같은 이름의 파일이 이미 있습니다: <이름> |
| 범위 역전 | 422 `invalid-value` | 라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다. / 라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다. |
| 종료일 범위 초과 | 422 `invalid-value` | 라이선스 종료일이 허용 범위를 벗어납니다. |
| Note 2000자 초과 | 422 `invalid-value` | Note은(는) 2000자를 넘을 수 없습니다 |
| 첨부 검증(설명 NUL 포함) | 422 `invalid-value` | LC-R21 문구 |
| 저장 위치 없음(업로드) | 503 `storage-unavailable` | 파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요. |
| 저장 위치 없음·읽기 불가(다운로드) | 503 `storage-unavailable` | 파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요. |
| 요청 형식(기간·칸·알 수 없는 필드·파라미터·플래그 타입·정렬 키 `deal_code` 등 없는 정렬 키) | 422 `request-validation` | 요청 형식이 올바르지 않습니다 |

## 3. Business use case

### LC-UC1 Won 진입 시 계약 자동 생성
- 행위자: sales·admin(Deal 등록·변경하는 사람), 시스템
- 사전 조건: Deal이 Won이 아니거나(변경) 새로 등록
- 기본 흐름: 경로 ①~④ 중 하나로 Deal이 Won이 된다 → 그 Deal에 계약이 0건이면 같은 트랜잭션에서 미발급 계약 1건을 만든다(LC-R7)
- 대안: 계약이 이미 있으면(종료 포함) 만들지 않는다. Won 유지 변경은 진입이 아니다
- 예외: Deal 변경이 거절되면 계약도 생기지 않는다
- 결과: Won Deal마다 계약이 최소 1건(admin이 지운 경우, 이 기능 이전부터 Won이던 Deal 제외)

### LC-UC2 Won 이탈 처리
- 행위자: sales·admin
- 사전 조건: Won인 Deal
- 기본 흐름: 화면에서 Won 밖으로 바꾼다 → 발급 계약이 없고 계약이 있으면 삭제/유지/취소를 묻는다 → 서버는 `delete_license_contracts`에 따라 계약을 지우거나 남기고 Deal을 바꾼다(LC-R9)
- 대안: 계약 0건이면 묻지 않는다. 취소하면 요청하지 않는다
- 예외: 발급 계약이 있으면 화면은 안내만 하고 요청하지 않으며, 서버도 409로 거절해 아무것도 저장하지 않는다(LC-R8). 정정은 admin의 계약 삭제
- 결과: Deal이 Won을 벗어나고 계약은 지워지거나 남는다, 또는 아무 변화 없음

### LC-UC3 계약 목록 조회
- 행위자: 모든 로그인 역할
- 기본 흐름: `/contracts`를 연다 → 종료일 오름차순 50건 → 스크롤로 이어 읽기 → 조건 검색·머리글 정렬(LC-R17~R19, R30~R32)
- 예외: 범위 역전·잘못된 파라미터(없는 정렬 키 포함) 422(화면은 범위 역전을 요청 전에 막음)
- 결과: 조건에 맞는 계약과 전체 건수

### LC-UC4 계약 상세와 Deal 쪽 표시값
- 행위자: 모든 로그인 역할(상세), Deal 화면(표시값)
- 기본 흐름: 계약 하나를 조회한다 / Deal을 조회하면 계약 건수·발급 여부가 함께 온다(LC-R1·R20)
- 예외: 없는 계약 404
- 결과: 조회 시점 Deal 값을 포함한 계약

### LC-UC5 계약 칸 수정
- 행위자: sales·admin
- 기본 흐름: 대화상자에서 기술담당·점검주기·Note를 고치고 저장 → PUT → 저장(LC-R14)
- 예외: 한도 초과·Deal 칸·알 수 없는 필드 422, 없는 계약 404, user 403
- 결과: 계약 칸이 바뀐다(상태 무관)

### LC-UC6 라이선스 발급
- 행위자: sales·admin
- 사전 조건: Won Deal의 미발급 계약, 같은 Deal에 다른 발급 계약 없음
- 기본 흐름: `라이선스 발급` → 시작일·기간 입력 → 저장 → 발급(신규), 종료일 계산(LC-R4·R11)
- 예외: Won 아님·미발급 아님·중복 발급 409, 기간 형식 422, 종료일 범위 초과 422
- 결과: 발급(신규) 계약

### LC-UC7 라이선스 갱신
- 행위자: sales·admin
- 사전 조건: Won Deal의 발급 상태 계약
- 기본 흐름: `라이선스 갱신` → 시작일(기본 종료일 다음 날)·기간 → 저장 → 이전 종료 + 새 발급(갱신) 행(LC-R12)
- 예외: Won 아님·발급 상태 아님 409, 기간 형식 422
- 결과: Deal당 발급 계약 1건 유지, 첨부는 이전 계약에 남음

### LC-UC8 계약 종료
- 행위자: sales·admin
- 기본 흐름: `계약 종료` → 확인 → 종료(LC-R13)
- 예외: 이미 종료 409
- 결과: 종료 계약(이후 발급·갱신 불가, 칸 수정·첨부 가능)

### LC-UC9 계약 삭제(admin)
- 행위자: admin
- 기본 흐름: `삭제` → 확인 → 계약·첨부 행 삭제, 커밋 뒤 계약 폴더 삭제(LC-R15·R26)
- 예외: admin이 아니면 계약 존재와 무관하게 403(user는 읽기 전용 문구, sales는 관리자만 문구), admin의 없는 계약 404
- 결과: 계약이 사라지고, 발급 계약이었다면 그 Deal은 Won을 벗어날 수 있다

### LC-UC10 계약 첨부 업로드
- 행위자: sales·admin
- 기본 흐름: 파일·설명 선택 → 업로드 → 계약 폴더에 저장(LC-R21·R25)
- 대안: 같은 이름이면 교체/건너뛰기 선택(LC-R22)
- 예외: 검증 실패 422, 저장 위치 없음 503, 없는 계약 404, 교체 권한 없음 403, 업로드 도중 계약 삭제 404
- 결과: 첨부 행과 파일

### LC-UC11 계약 첨부 목록·다운로드
- 행위자: 모든 로그인 역할
- 기본 흐름: 대화상자에서 목록을 보고 파일명을 눌러 내려받는다(LC-R24)
- 예외: 저장 위치 없음 503, 파일 내용 없음·없는 첨부 404

### LC-UC12 계약 첨부 삭제
- 행위자: sales(본인·퇴사 sales 파일)·admin
- 기본 흐름: `삭제` → 확인 → 행과 파일 삭제, 계약 폴더는 남김(LC-R23·R26)
- 예외: 권한 없음 403, 없는 첨부 404

### LC-UC13 Deal 삭제와 계약
- 행위자: Deal을 삭제할 수 있는 사용자(Deal feature 규칙)
- 기본 흐름: 삭제 영향에 계약 건수 표시 → 삭제 → 계약·첨부 행 삭제, 커밋 뒤 Deal 폴더·계약 폴더 삭제(LC-R20·R26·R27)
- 결과: 그 Deal의 계약 관련 데이터·파일이 남지 않는다

## 4. BDD 테스트 케이스

요청자 예시: KIM·PARK(sales), BOSS(admin), VIEWER(user). "Won Deal"은 Status `contract_completed`·Forecast `won`. Won 이탈 예시는 Forecast를 `commit`으로(Status `poc_completed`가 함께) 바꾸는 변경이다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| LC-001 | 처음부터 Won으로 등록한 Deal에 미발급 계약 1건이 생긴다 | LC-R7, LC-UC1 | backend | `application/test_license_contract_won_entry.py::test_register_deal_as_won_creates_not_issued_contract`<br>`application/test_license_contract_scenarios.py::test_registration_response_reports_the_contract_count_and_issued_flag`<br>`test/fake/gateway/licenseContracts.test.ts > creates the contract for a deal registered as Won, through update and through an action too` |
| LC-002 | Won이 아닌 Deal을 등록하면 계약이 생기지 않는다 | LC-R7, LC-UC1 | backend | `application/test_license_contract_won_entry.py::test_register_deal_not_won_creates_no_contract`<br>`application/test_license_contract_scenarios.py::test_registration_response_reports_the_contract_count_and_issued_flag` |
| LC-003 | 변경 경로로 Won이 된 Deal에 미발급 계약 1건이 생긴다 | LC-R6, LC-R7, LC-UC1 | backend | `application/test_license_contract_won_entry.py::test_update_deal_to_won_creates_contract_when_none`<br>`application/test_license_contract_won_entry.py::test_apply_change_forecast_won_creates_contract`<br>`application/test_license_contract_won_entry.py::test_apply_change_status_contract_completed_creates_contract`<br>외 5건 |
| LC-004 | 계약이 이미 있거나 Won을 유지하는 변경이면 새 계약이 생기지 않는다 | LC-R6, LC-R7, LC-R8, LC-UC1 | backend | `application/test_license_contract_won_entry.py::test_update_deal_to_won_skips_when_contract_exists`<br>`application/test_license_contract_won_entry.py::test_update_deal_that_stays_won_creates_no_second_contract`<br>`application/test_license_contract_won_entry.py::test_won_then_left_with_keep_then_won_again_keeps_the_single_contract`<br>외 4건 |
| LC-005 | Won으로 바꾸는 변경이 거절되면 계약도 생기지 않는다 | LC-R7, LC-UC1 | backend | `application/test_license_contract_won_entry.py::test_a_rejected_won_change_creates_no_contract` |
| LC-006 | 발급 계약이 없는 Deal을 삭제 선택과 함께 Won에서 벗어나게 하면 그 Deal의 계약만 지워진다 | LC-R9, LC-R26, LC-UC2 | backend | `application/test_license_contract_folders.py::test_won_exit_delete_removes_every_contract_folder_of_the_deal_only`<br>`application/test_license_contract_won_exit.py::test_apply_change_leave_won_with_delete_removes_contracts_and_files_after_commit`<br>`application/test_license_contract_won_exit.py::test_update_deal_leave_won_with_delete_removes_contracts`<br>외 3건 |
| LC-007 | 삭제를 고르지 않았거나 Won 이탈이 아니면 계약이 지워지지 않는다 | LC-R9, LC-UC2 | backend | `application/test_license_contract_folders.py::test_won_exit_keep_leaves_the_folders`<br>`application/test_license_contract_won_exit.py::test_leave_won_without_the_flag_keeps_contracts_and_files`<br>`application/test_license_contract_won_exit.py::test_update_deal_leave_won_without_flag_keeps_contracts`<br>외 8건 |
| LC-008 | 발급 계약이 있는 Deal은 어느 경로로도 Won에서 벗어날 수 없다 | LC-R8, LC-UC2 | backend | `application/test_license_contract_won_exit_blocked.py::test_leave_won_with_issued_contract_raises_blocked_and_keeps_everything`<br>`application/test_license_contract_won_exit_blocked.py::test_blocked_leave_is_refused_for_every_role_that_may_change_the_deal`<br>`application/test_license_contract_won_exit_blocked.py::test_register_action_blocked_leave_saves_no_action_and_keeps_previous_next_action`<br>외 3건 |
| LC-009 | 발급 계약이 없어진 Deal은 sales도 삭제를 골라 Won에서 벗어날 수 있다 | LC-R8, LC-R9, LC-UC2 | backend | `application/test_license_contract_won_exit_blocked.py::test_leave_won_with_ended_only_contracts_still_asks_and_deletes_by_sales`<br>`application/test_license_contract_won_exit_blocked.py::test_leave_won_with_ended_only_and_keep_leaves_the_contracts`<br>`application/test_license_contract_won_exit_blocked.py::test_leave_won_after_admin_deleted_the_issued_contract_succeeds`<br>외 3건 |
| LC-010 | 화면: Won 이탈 확인에서 삭제를 누르면 삭제 요청이 간다 | LC-R36, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > asks after the sync choice and sends deleteLicenseContracts: true for 삭제`<br>`features/deals/licenseContractsOnWonExit.test.tsx > asks after the sync choice and sends the chosen value`<br>`features/deals/licenseContractsOnWonExit.test.tsx > asks when 저장 is pressed and sends deleteLicenseContracts: true for 삭제`<br>외 1건 |
| LC-011 | 화면: Won 이탈 확인에서 유지를 누르면 계약을 남기는 요청이 간다 | LC-R36, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > sends deleteLicenseContracts: false for 유지 and keeps the contracts`<br>`features/deals/licenseContractsOnWonExit.test.tsx > sends false for 유지 and nothing for 취소`<br>`features/deals/licenseContractsOnWonExit.test.tsx > sends false for 유지 and keeps the form and sends nothing for 취소`<br>외 1건 |
| LC-012 | 화면: Won 이탈 확인에서 취소를 누르면 요청하지 않는다 | LC-R36, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > sends no request and changes nothing for 취소`<br>`features/deals/licenseContractsOnWonExit.test.tsx > sends false for 유지 and nothing for 취소`<br>`features/deals/licenseContractsOnWonExit.test.tsx > sends false for 유지 and keeps the form and sends nothing for 취소`<br>외 1건 |
| LC-013 | 화면: 계약이 없거나 Won 이탈이 아니면 묻지 않는다 | LC-R36, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > does not ask when the deal has no contract`<br>`features/deals/licenseContractsOnWonExit.test.tsx > does not ask when the form does not leave Won`<br>`features/deals/licenseContractsOnWonExit.test.tsx > does not ask when no status change is made` |
| LC-014 | 화면: 발급 계약이 있는 Deal은 안내만 띄우고 요청하지 않는다 | LC-R36, LC-R8, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > 상세 요약 바: 안내만 보이고 요청 없이 값이 Won 그대로다`<br>`features/deals/licenseContractsOnWonExit.test.tsx > 목록 인라인 편집: 안내만 보이고 요청 없이 값이 Won 그대로다`<br>`features/deals/licenseContractsOnWonExit.test.tsx > Deal 폼 수정: 저장을 누르면 안내만 보이고 요청이 없다`<br>외 1건 |
| LC-015 | 화면: 화면 값이 오래돼 서버가 409를 주면 문구를 보이고 다음 시도는 안내로 막는다 | LC-R36, LC-R8, LC-UC2 | frontend | `features/deals/licenseContractsOnWonExit.test.tsx > 상세 요약 바: 유지를 눌러도 서버 문구가 오류로 보이고 Forecast는 Won 그대로다`<br>`features/deals/licenseContractsOnWonExit.test.tsx > 목록 인라인 편집: 유지를 눌러도 서버 문구가 행의 alert에 보이고 편집 칸이 남으며 Forecast는 Won 그대로다`<br>`features/deals/licenseContractsOnWonExit.test.tsx > Deal 폼 수정: 409 뒤 같은 변경을 다시 저장하면 확인 버튼뿐인 안내 대화상자가 뜨고 요청이 없다`<br>외 3건 |
| LC-016 | 조건 없이 목록을 읽으면 종료일 오름차순 50건과 전체 건수가 온다 | LC-R18, LC-R19, LC-UC3 | backend | `application/test_license_contract_query.py::test_list_returns_the_page_with_the_total`<br>`application/test_license_contract_query.py::test_list_second_page_returns_the_rest`<br>`application/test_license_contract_scenarios.py::test_default_list_is_license_end_ascending_with_fifty_per_page`<br>외 7건 |
| LC-017 | 고객사명·제품명은 Deal 값의 대소문자 무시 부분 일치로 거른다 | LC-R17, LC-UC3 | backend | `application/test_license_contract_query.py::test_query_text_filters_are_trimmed_and_blank_means_none`<br>`repositories/test_license_contract_search_contract.py::test_search_customer_is_a_case_insensitive_partial_match_on_the_deal_customer`<br>`repositories/test_license_contract_search_contract.py::test_search_product_is_a_case_insensitive_partial_match_on_the_deal_product`<br>외 1건 |
| LC-018 | Vendor·담당영업·상태 조건은 일치로 거르고 모든 조건은 AND다 | LC-R17, LC-UC3 | backend | `application/test_license_contract_query.py::test_list_filters_by_status_and_counts_the_filtered_total`<br>`repositories/test_license_contract_search_contract.py::test_search_vendor_matches_the_deal_vendor_id`<br>`repositories/test_license_contract_search_contract.py::test_search_owner_matches_the_deal_owner_including_resigned_users`<br>외 2건 |
| LC-019 | 날짜 범위는 양끝을 포함하고 날짜 없는 계약은 뺀다 | LC-R17, LC-UC3 | backend | `application/test_license_contract_query.py::test_query_same_day_range_and_one_sided_ranges_are_accepted`<br>`web/test_license_contract_openapi.py::test_list_query_parameters`<br>`repositories/test_license_contract_search_contract.py::test_search_start_range_is_inclusive_and_excludes_contracts_without_dates`<br>외 1건 |
| LC-020 | 날짜 범위가 거꾸로면 422로 거절한다 | LC-R17, LC-UC3 | backend | `application/test_license_contract_query.py::test_query_reversed_start_range_rejected`<br>`application/test_license_contract_query.py::test_query_reversed_end_range_rejected`<br>`web/test_license_contract_routes.py::test_list_with_a_reversed_range_is_422_invalid_value` |
| LC-021 | 12개 정렬 키는 방향대로 정렬하고 값 없는 칸은 맨 뒤, 동률은 id 순이다 | LC-R18, LC-UC3 | backend | `application/test_license_contract_query.py::test_query_sort_keys_are_the_twelve_table_columns`<br>`web/test_license_contract_openapi.py::test_the_sort_status_and_order_parameters_list_their_values`<br>`repositories/test_license_contract_sort_contract.py::test_search_sort_each_column_asc_empty_last_tie_by_id`<br>외 2건 |
| LC-022 | 화면: 계약관리를 열면 첫 50건과 전체 건수, 12개 머리글이 보인다 | LC-R30, LC-UC3 | frontend | `features/contracts/ContractsPage.test.tsx > shows the first fifty contracts with the server total and the 12 headers in order`<br>`features/contracts/ContractsPage.test.tsx > shows the values of the first server row in its cells and the four status labels`<br>`features/contracts/ContractsPage.test.tsx > has no mock-data notice any more`<br>외 1건 |
| LC-023 | 화면: 목록 끝에 닿으면 다음 50건을 잇고 다 읽으면 끝을 알린다 | LC-R30, LC-UC3 | frontend | `features/contracts/ContractsPage.scroll.test.tsx > reads fifty at a time with the total from the server and appends the next page when the end scrolls into view`<br>`features/contracts/ContractsPage.scroll.test.tsx > observes a sentinel with a 200px root margin and says everything is loaded after the last page`<br>`features/contracts/ContractsPage.scroll.test.tsx > shows each contract once even if the list shifts between pages`<br>외 2건 |
| LC-024 | 화면: 검색 조건이 서버 조건으로 가고 초기화하면 전체로 돌아온다 | LC-R31, LC-R30, LC-UC3 | frontend | `features/contracts/ContractsPage.test.tsx > sends the customer text to the server and restores the list on reset`<br>`features/contracts/ContractsPage.test.tsx > searches on Enter`<br>`features/contracts/ContractsPage.test.tsx > filters by part of the product name ignoring case, using the server`<br>외 6건 |
| LC-025 | 화면: 날짜 범위가 거꾸로면 검색하지 않고 문구를 보인다 | LC-R31, LC-UC3 | frontend | `features/contracts/ContractsPage.test.tsx > does not search and shows the error when the start is later than the end` |
| LC-026 | 화면: 머리글을 누르면 그 열로 서버 정렬하고 다시 누르면 방향이 바뀐다 | LC-R30, LC-UC3 | frontend | `features/contracts/ContractsPage.test.tsx > asks the server for end date ascending by default and flips the direction on click` |
| LC-027 | 화면: 발급 계약의 날짜 칸은 남은 기간에 따라 색이 붙는다 | LC-R32, LC-UC3 | frontend | `features/contracts/ContractsPage.edit.test.tsx > colors the start and end date cells by the remaining period of issued contracts only`<br>`features/contracts/ContractsPage.edit.test.tsx > marks the status cell with status-issued or status-ended and nothing for not-issued`<br>`features/contracts/ContractsPage.edit.test.tsx > removes the expiry color after renewing a near-expiry contract from the dialog`<br>외 6건 |
| LC-028 | 계약 상세는 조회 시점의 Deal 값·첨부 수·Won 여부를 담는다 | LC-R1, LC-R20, LC-UC4 | backend | `application/test_license_contract_query.py::test_get_returns_the_contract_with_the_deal_values`<br>`application/test_license_contract_query.py::test_get_counts_the_attachments`<br>`application/test_license_contract_query.py::test_get_reports_whether_the_deal_is_won`<br>외 15건 |
| LC-029 | 없는 계약·첨부 id로 요청하면 404다(계약 삭제는 admin만) | LC-R28, LC-R15, LC-UC4 | backend | `application/test_license_contract_attachments.py::test_upload_to_a_missing_contract_raises_not_found`<br>`application/test_license_contract_attachments.py::test_list_files_of_a_missing_contract_raises_not_found`<br>`application/test_license_contract_attachments.py::test_download_missing_attachment_raises_not_found`<br>외 18건 |
| LC-030 | Deal 응답의 계약 건수와 발급 여부는 계약 상태를 따른다 | LC-R20, LC-UC4 | backend | `application/test_deal_view_issued_license_flag.py::test_flag_is_false_without_contracts_and_with_only_a_waiting_contract`<br>`application/test_deal_view_issued_license_flag.py::test_flag_is_true_with_an_issued_contract`<br>`application/test_deal_view_issued_license_flag.py::test_flag_is_false_after_the_issued_contract_ends`<br>외 16건 |
| LC-031 | 계약 칸 수정은 모든 상태에서 저장되고 기간·Deal은 그대로다 | LC-R14, LC-UC5 | backend | `application/test_license_contract_end_update_delete.py::test_update_saves_the_contract_fields_in_every_status`<br>`web/test_license_contract_requests.py::test_fields_request_maps_to_the_domain_fields`<br>`web/test_license_contract_routes.py::test_put_saves_the_contract_fields_only`<br>외 3건 |
| LC-032 | 계약 칸 수정에서 생략한 칸은 기본값으로 저장된다 | LC-R14, LC-UC5 | backend | `web/test_license_contract_requests.py::test_fields_request_defaults_are_empty_text_and_no_inspection`<br>`web/test_license_contract_routes.py::test_put_with_an_empty_body_resets_the_fields_to_their_defaults`<br>`domain/test_license_contract_values.py::test_fields_accept_empty_text` |
| LC-033 | 계약 칸 수정에 Deal 값 칸이나 모르는 필드를 보내면 422다 | LC-R14, LC-UC5 | backend | `web/test_license_contract_requests.py::test_fields_request_rejects_the_deal_owned_columns`<br>`web/test_license_contract_routes.py::test_put_rejects_the_deal_owned_columns_and_any_unknown_field`<br>`web/test_license_contract_openapi.py::test_the_fields_body_has_the_three_contract_columns_and_forbids_extras` |
| LC-034 | 계약 칸 길이·문자 한도의 경계 | LC-R14, LC-UC5 | backend | `web/test_license_contract_requests.py::test_fields_request_rejects_a_tech_owner_over_100_chars`<br>`web/test_license_contract_requests.py::test_fields_request_accepts_a_tech_owner_of_100_chars`<br>`web/test_license_contract_routes.py::test_put_rejects_values_over_the_limits`<br>외 7건 |
| LC-035 | 계약 변경은 Deal History와 Deal 수정 시각을 바꾸지 않는다 | LC-R16, LC-UC5 | backend | `application/test_license_contract_attachments.py::test_upload_does_not_write_deal_history_or_touch_the_deal`<br>`application/test_license_contract_issue_renew.py::test_contract_changes_do_not_touch_the_deal`<br>`application/test_license_contract_scenarios.py::test_contract_changes_leave_deal_history_and_modified_time_untouched` |
| LC-036 | 화면: 계약 수정 대화상자에서 계약 칸을 저장하면 표에 반영된다 | LC-R33, LC-R30, LC-UC5 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > saves with the update request and the plain notice when no license button was pressed`<br>`features/contracts/ContractsPage.edit.test.tsx > opens 계약 수정 with the Deal values read-only and the contract fields editable`<br>`features/contracts/ContractsPage.edit.test.tsx > opens the dialog from the keyboard with Enter on the focused row`<br>외 3건 |
| LC-037 | 화면: 서버가 거절하면 대화상자 안에 문구를 보이고 닫지 않는다 | LC-R33, LC-UC5 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > shows the server message in the dialog and keeps it open when another contract of the deal is already issued (AC3, 409)`<br>`features/contracts/ContractsPage.actions.test.tsx > shows the server message when ending fails (409)`<br>`features/contracts/ContractsPage.edit.test.tsx > shows the server message and keeps the dialog open when the server refuses (422)` |
| LC-038 | 화면: user에게는 계약 대화상자가 읽기 전용이다 | LC-R33, LC-R34, LC-R28, LC-UC5 | frontend | `features/contracts/ContractsPage.actions.test.tsx > has no 계약 종료 button for a read-only user`<br>`features/contracts/ContractsPage.edit.test.tsx > shows no save button for a read-only user` |
| LC-039 | Won Deal의 미발급 계약을 발급하면 발급(신규)가 된다 | LC-R11, LC-R4, LC-UC6 | backend | `application/test_license_contract_issue_renew.py::test_issue_not_issued_contract_stores_period_and_computed_end`<br>`application/test_license_contract_issue_renew.py::test_issue_applies_the_contract_fields_sent_with_it`<br>`web/test_license_contract_routes.py::test_issue_returns_200_with_the_computed_end_date`<br>외 2건 |
| LC-040 | 종료일은 시작일+기간−1일이고 없는 날은 그 달 말일이다 | LC-R4, LC-UC6 | both | `application/test_license_contract_scenarios.py::test_issue_computes_the_end_date_from_start_and_term`<br>`features/contracts/ContractEditDialog.status.test.tsx > computes 2026-06-30 for 2026-01-01 + 6 months`<br>`features/contracts/licensePeriod.test.ts > %s + %i %s ends on %s`<br>외 4건 |
| LC-041 | 미발급이 아닌 계약은 발급할 수 없다 | LC-R11, LC-R2, LC-UC6 | backend | `application/test_license_contract_end_update_delete.py::test_ended_contract_cannot_be_issued_or_renewed`<br>`application/test_license_contract_issue_renew.py::test_issue_non_not_issued_raises_transition_error`<br>`web/test_license_contract_routes.py::test_issue_on_an_issued_contract_is_409_invalid_state`<br>외 1건 |
| LC-042 | 같은 Deal에 발급 계약이 있으면 다른 계약을 발급할 수 없다 | LC-R3, LC-UC6 | backend | `application/test_license_contract_end_update_delete.py::test_ending_a_contract_allows_issuing_another_one_of_the_deal`<br>`application/test_license_contract_issue_renew.py::test_issue_when_deal_has_other_issued_raises_already_issued`<br>`application/test_license_contract_issue_renew.py::test_issue_is_allowed_when_the_other_contract_is_ended`<br>외 10건 |
| LC-043 | Won이 아닌 Deal의 계약은 발급할 수 없고 이 검사가 전이 검사보다 먼저다 | LC-R10, LC-R11, LC-UC6 | backend | `application/test_license_contract_issue_renew.py::test_issue_missing_contract_raises_not_found`<br>`application/test_license_contract_won_required.py::test_issue_on_a_non_won_deal_raises_requires_won_and_changes_nothing`<br>`application/test_license_contract_won_required.py::test_issue_on_a_lost_deal_raises_requires_won`<br>외 6건 |
| LC-044 | 발급·갱신 요청의 기간 형식이 틀리면 422이고 1·99는 허용한다 | LC-R4, LC-UC6, LC-UC7 | backend | `web/test_license_contract_requests.py::test_issue_request_rejects_a_term_amount_outside_one_to_ninety_nine`<br>`web/test_license_contract_requests.py::test_issue_request_accepts_the_boundary_amounts`<br>`web/test_license_contract_requests.py::test_issue_request_requires_the_period`<br>외 10건 |
| LC-045 | Won을 벗어날 때 남긴 계약은 다시 Won이 되면 발급할 수 있다 | LC-R10, LC-UC6 | backend | `application/test_license_contract_won_required.py::test_a_contract_kept_after_leaving_won_cannot_be_issued_until_won_again` |
| LC-046 | 화면: 라이선스 발급 버튼으로 기본값을 채워 발급한다 | LC-R33, LC-UC6 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > shows the %s badge and its license button inside the 상태 group`<br>`features/contracts/ContractEditDialog.status.test.tsx > shows empty disabled fields with the 1 year default for a not-issued contract`<br>`features/contracts/ContractEditDialog.status.test.tsx > opens no extra dialog, enables the fields, focuses the start date and shows the guide`<br>외 2건 |
| LC-047 | 화면: 시작일이 비었거나 기간이 틀리면 발급·갱신 요청을 보내지 않는다 | LC-R33, LC-UC6, LC-UC7 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > does not send the request and shows a message when the start date is cleared (C6)`<br>`features/contracts/ContractEditDialog.status.test.tsx > does not send the request when the period is empty (C6)`<br>`features/contracts/ContractEditDialog.status.test.tsx > does not send a renewal whose start date was cleared` |
| LC-048 | 화면: Won이 아닌 Deal의 계약은 발급·갱신 버튼이 비활성이다 | LC-R33, LC-R10, LC-UC6 | frontend | `features/contracts/ContractEditDialog.dealNotWon.test.tsx > keeps the issue button enabled and shows no hint while the deal is Won`<br>`features/contracts/ContractEditDialog.dealNotWon.test.tsx > disables the issue button and shows the hint when the deal left Won`<br>`features/contracts/ContractEditDialog.dealNotWon.test.tsx > does not call the server when the disabled issue button is clicked`<br>외 2건 |
| LC-049 | 발급 계약을 갱신하면 이전 계약은 종료되고 새 발급(갱신) 계약이 생긴다 | LC-R12, LC-R3, LC-UC7 | backend | `application/test_license_contract_issue_renew.py::test_renew_creates_a_new_row_and_ends_the_previous_one`<br>`application/test_license_contract_issue_renew.py::test_renew_keeps_single_issued_per_deal`<br>`web/test_license_contract_routes.py::test_renewal_is_201_with_a_location_and_the_new_contract`<br>외 3건 |
| LC-050 | 발급 상태가 아닌 계약은 갱신할 수 없다 | LC-R12, LC-R2, LC-UC7 | backend | `application/test_license_contract_end_update_delete.py::test_ended_contract_cannot_be_issued_or_renewed`<br>`application/test_license_contract_issue_renew.py::test_renew_not_issued_or_ended_raises`<br>`web/test_license_contract_routes.py::test_renewal_of_a_not_issued_contract_is_409`<br>외 1건 |
| LC-051 | Won이 아닌 Deal의 계약은 갱신할 수 없다 | LC-R10, LC-UC7 | backend | `application/test_license_contract_won_required.py::test_renew_on_a_non_won_deal_raises_requires_won_and_adds_no_row`<br>`web/test_license_contract_routes.py::test_renewal_on_a_non_won_deal_is_409_invalid_state_with_the_won_message`<br>`test/fake/gateway/licenseContracts.test.ts > rejects issue and renew when the deal is not Won, but allows edits and ending` |
| LC-052 | 갱신해도 첨부는 이전 계약 폴더에 남고 새 계약은 새 폴더를 쓴다 | LC-R12, LC-R25, LC-UC7 | backend | `application/test_license_contract_folders.py::test_renewal_uses_a_new_folder_and_the_previous_files_stay`<br>`application/test_license_contract_issue_renew.py::test_renew_leaves_the_attachments_on_the_previous_contract`<br>`application/test_storage_folders.py::test_different_contracts_get_different_folders` |
| LC-053 | 화면: 라이선스 갱신 버튼으로 다음 날부터 갱신한다 | LC-R33, LC-UC7 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > shows the %s badge and its license button inside the 상태 group`<br>`features/contracts/ContractEditDialog.status.test.tsx > defaults the start to the day after the end of an %s contract and focuses it`<br>`features/contracts/ContractEditDialog.status.test.tsx > renews an %s contract through the renew request: a new 발급(갱신) row and the previous one ended` |
| LC-054 | 종료가 아닌 계약을 종료하면 종료일이 기록되고 기간은 남는다 | LC-R13, LC-UC8 | backend | `application/test_license_contract_end_update_delete.py::test_end_moves_the_contract_to_ended`, `domain/test_license_contract_entity.py::test_end_sets_ended_and_records_the_date`, `domain/test_license_contract_entity.py::test_end_keeps_the_license_period` <br><br> |
| LC-055 | 이미 종료된 계약은 다시 종료할 수 없다 | LC-R13, LC-UC8 | backend | `application/test_license_contract_end_update_delete.py::test_end_twice_raises_and_keeps_the_first_end_date`<br>`web/test_license_contract_routes.py::test_end_twice_is_409`<br>`domain/test_license_contract_entity.py::test_end_twice_raises` |
| LC-056 | 종료일이 지나도 계약은 자동으로 종료되지 않는다 | LC-R13, LC-UC8 | backend | `application/test_license_contract_scenarios.py::test_contract_is_not_ended_automatically_after_its_end_date` |
| LC-057 | 화면: 계약 종료는 확인한 뒤에만 요청한다 | LC-R34, LC-UC8 | frontend | `features/contracts/ContractEditDialog.status.test.tsx > shows no license or end button for an ended contract and keeps the license fields disabled`<br>`features/contracts/ContractsPage.actions.test.tsx > has a 계약 종료 button in the status group of an %s contract`<br>`features/contracts/ContractsPage.actions.test.tsx > has no 계약 종료 button for an ended contract`<br>외 2건 |
| LC-058 | admin은 어떤 상태의 계약이든 삭제하고 그 계약 폴더가 지워진다 | LC-R15, LC-R26, LC-UC9 | backend | `application/test_license_contract_end_update_delete.py::test_delete_by_admin_works_in_any_status`<br>`application/test_license_contract_end_update_delete.py::test_delete_contract_by_admin_removes_files_after_commit`<br>`application/test_license_contract_end_update_delete.py::test_delete_contract_keeps_other_contracts_and_the_deal_files`<br>외 6건 |
| LC-059 | sales는 계약을 삭제할 수 없다 | LC-R15, LC-UC9 | backend | `application/test_license_contract_end_update_delete.py::test_delete_by_non_admin_is_forbidden_and_removes_nothing`<br>`application/test_license_contract_folders.py::test_admin_delete_by_a_forbidden_actor_keeps_the_folder`<br>`web/test_license_contract_route_permissions.py::test_delete_by_admin_is_204_and_by_sales_is_403_with_the_admin_only_message`<br>외 2건 |
| LC-060 | 갱신 원본 계약을 지우면 후속 계약의 원본 연결이 비워진다 | LC-R15, LC-UC9 | backend | `application/test_license_contract_end_update_delete.py::test_deleting_the_renewed_row_clears_the_link_of_its_successor`<br>`repositories/test_license_contract_repository_contract.py::test_delete_clears_the_renewal_link_of_the_successor`<br>`infra/schema/test_license_contract_schema.py::test_deleting_the_origin_contract_sets_the_renewal_link_to_null` |
| LC-061 | 화면: 계약 삭제 버튼은 admin에게만 보이고 확인 뒤 삭제한다 | LC-R34, LC-UC9 | frontend | `features/contracts/ContractsPage.actions.test.tsx > shows 삭제 to an admin for an %s contract and deletes it after confirmation`<br>`features/contracts/ContractsPage.actions.test.tsx > keeps the contract when the delete confirmation is cancelled`<br>`features/contracts/ContractsPage.actions.test.tsx > does not show 삭제 to a %s` |
| LC-062 | 저장 위치가 없거나 파일 정리가 실패해도 계약을 지우는 요청은 성공한다 | LC-R26, LC-UC2, LC-UC9, LC-UC13 | backend | `application/test_license_contract_end_update_delete.py::test_delete_contract_survives_a_file_cleanup_failure`<br>`application/test_license_contract_end_update_delete.py::test_delete_contract_without_storage_settings_still_removes_the_rows`<br>`application/test_license_contract_folders.py::test_admin_delete_with_a_failed_commit_keeps_the_folder`<br>외 10건 |
| LC-063 | 계약 첨부를 올리면 계약 폴더에 저장되고 상태와 무관하게 올릴 수 있다 | LC-R21, LC-R25, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_new_file_stores_row_and_disk_file_in_the_contract_folder`<br>`application/test_license_contract_attachments.py::test_upload_is_allowed_on_an_ended_contract`<br>`application/test_license_contract_folders.py::test_upload_saves_the_file_under_the_contract_folder`<br>외 8건 |
| LC-064 | 같은 이름을 기본(ask)으로 올리면 409 file-exists다 | LC-R22, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_same_name_ask_raises_file_exists`<br>`web/test_license_contract_attachment_routes.py::test_upload_of_a_taken_name_is_409_file_exists_by_default`<br>`repositories/test_license_contract_attachment_repository_contract.py::test_the_same_name_in_the_same_contract_is_rejected_and_the_session_stays_usable`<br>외 4건 |
| LC-065 | 같은 이름을 건너뛰기로 올리면 아무것도 바뀌지 않는다 | LC-R22, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_same_name_skip_returns_skipped_and_leaves_no_new_file`<br>`web/test_license_contract_attachment_routes.py::test_upload_with_skip_is_200_skipped_without_an_attachment`<br>`web/test_license_contract_openapi.py::test_the_attachment_upload_also_documents_the_200_for_replaced_and_skipped` |
| LC-066 | 같은 이름을 교체로 올리면 같은 첨부의 내용이 바뀌고 남의 파일은 교체할 수 없다 | LC-R22, LC-R23, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_replace_deletes_old_file_after_commit`<br>`application/test_license_contract_attachments.py::test_upload_replace_by_another_sales_is_forbidden`<br>`application/test_license_contract_attachments.py::test_upload_replace_by_admin_is_allowed`<br>외 5건 |
| LC-067 | 업로드 검증 규칙을 어기면 422이고 경계값은 허용한다 | LC-R21, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_blocked_extension_is_rejected`<br>`application/test_license_contract_attachments.py::test_upload_description_over_100_chars_is_rejected`<br>`application/test_license_contract_attachments.py::test_upload_without_a_file_part_is_rejected`<br>외 5건 |
| LC-068 | 저장 위치가 없으면 업로드는 503이다 | LC-R24, LC-UC10 | backend | `application/test_license_contract_attachments.py::test_upload_without_storage_settings_raises_unavailable`<br>`web/test_license_contract_attachment_routes.py::test_upload_without_a_storage_location_is_503` |
| LC-069 | 업로드 도중 계약이 지워지면 404로 끝나고 계약 폴더가 남지 않는다 | LC-R26, LC-UC10 | backend | `application/test_license_contract_folders.py::test_upload_when_the_contract_is_deleted_before_recording_removes_its_folder` |
| LC-070 | 화면: 파일을 올리면 첨부 목록에 보인다 | LC-R35, LC-UC10 | frontend | `features/contracts/ContractsPage.edit.test.tsx > has a 첨부 파일 area and lists the contract files from the server`<br>`features/contracts/ContractsPage.edit.test.tsx > uploads a file through the gateway, lists it, and still lists it after reopening` |
| LC-071 | 화면: 화면 규칙을 어긴 파일은 요청 없이 문구를 보인다 | LC-R35, LC-UC10 | frontend | `features/contracts/ContractsPage.edit.test.tsx > rejects an executable file with the Deal message`<br>`features/contracts/ContractsPage.edit.test.tsx > rejects a missing file and a description over 100 characters` |
| LC-072 | 화면: 같은 이름이면 교체·건너뛰기를 묻는다 | LC-R35, LC-UC10 | frontend | `features/contracts/ContractsPage.edit.test.tsx > asks to replace or skip on a 409 for the same name and replaces when 교체 is chosen`<br>`features/contracts/ContractsPage.edit.test.tsx > keeps the list as it was when 건너뛰기 is chosen (skip request)` |
| LC-073 | 화면: 저장 위치를 쓸 수 없다는 서버 문구를 보인다 | LC-R35, LC-UC10 | frontend | `features/contracts/ContractsPage.edit.test.tsx > shows the 503 message when the storage location is unavailable` |
| LC-074 | 모든 역할이 첨부 목록을 최신순으로 보고 내려받을 수 있다 | LC-R24, LC-UC11 | both | `application/test_license_contract_attachments.py::test_list_files_returns_newest_first`<br>`application/test_license_contract_attachments.py::test_download_opens_the_stored_content`<br>`application/test_license_contract_folders.py::test_download_reads_from_the_contract_folder`<br>외 4건 |
| LC-075 | 저장 위치가 없거나 파일 내용이 없으면 다운로드가 실패한다 | LC-R24, LC-UC11 | backend | `application/test_license_contract_attachments.py::test_download_without_storage_settings_raises_unavailable`<br>`application/test_license_contract_folders.py::test_download_does_not_fall_back_to_the_deal_folder`<br>`web/test_license_contract_attachment_routes.py::test_download_without_a_storage_location_is_503`<br>외 3건 |
| LC-076 | 업로더가 첨부를 지우면 그 파일만 지워지고 계약 폴더는 남는다 | LC-R23, LC-R26, LC-UC12 | backend | `application/test_license_contract_attachments.py::test_delete_file_by_uploader_removes_row_and_disk_file`<br>`application/test_license_contract_folders.py::test_delete_file_removes_only_the_file_and_keeps_the_contract_folder`<br>`application/test_license_contract_folders.py::test_deleting_the_last_file_keeps_the_empty_contract_folder`<br>외 2건 |
| LC-077 | 첨부 삭제 권한: 남의 파일은 sales가 지울 수 없고 admin·퇴사 sales 파일은 된다 | LC-R23, LC-UC12 | backend | `application/test_license_contract_attachments.py::test_delete_file_by_another_sales_is_forbidden`<br>`application/test_license_contract_attachments.py::test_delete_file_by_admin_and_for_a_resigned_sales_file`<br>`application/test_license_contract_attachments.py::test_delete_file_by_read_only_user_is_forbidden`<br>외 1건 |
| LC-078 | 화면: 첨부 삭제는 확인 뒤에만, 권한 없는 행은 버튼이 비활성이다 | LC-R35, LC-UC12 | frontend | `features/contracts/ContractsPage.edit.test.tsx > deletes a file after confirmation and keeps it when cancelled` |
| LC-079 | Deal 삭제 영향에 계약 건수가 나온다 | LC-R20, LC-UC13 | backend | `application/test_license_contract_scenarios.py::test_deletion_impact_counts_contracts_but_not_contract_attachments`<br>`web/test_license_contract_openapi.py::test_deal_responses_document_the_contract_count`<br>`repositories/test_license_contract_deal_count_contract.py::test_deletion_impact_counts_license_contracts`<br>외 2건 |
| LC-080 | Deal을 지우면 계약·첨부와 Deal 폴더·계약 폴더가 함께 지워진다 | LC-R27, LC-R26, LC-UC13 | backend | `application/test_license_contract_attachments.py::test_deleting_a_deal_removes_its_contracts_attachment_rows_and_files`<br>`application/test_license_contract_folders.py::test_deleting_a_deal_removes_the_deal_folder_and_its_contract_folders`<br>`repositories/test_license_contract_repository_contract.py::test_delete_of_deal_removes_only_that_deals_contracts_and_attachment_rows`<br>외 3건 |
| LC-081 | 화면: Deal 삭제 확인에 라이선스 계약 건수가 보인다 | LC-R37, LC-UC13 | frontend | `features/deals/detail/DeleteDealDialog.contracts.test.tsx > shows the number of license contracts that are deleted together`<br>`features/deals/detail/DeleteDealDialog.contracts.test.tsx > shows 0 for a deal without contracts`<br>`features/deals/detail/DeleteDealDialog.contracts.test.tsx > removes the contracts together with the deal` |
| LC-082 | 조회는 모든 역할, 쓰기는 user에게 먼저 403이다 | LC-R28 | backend | `web/test_license_contract_route_permissions.py::test_a_read_only_user_cannot_write_and_nothing_changes`<br>`web/test_license_contract_route_permissions.py::test_a_read_only_user_is_forbidden_before_the_body_or_the_record_is_checked`<br>`web/test_license_contract_route_permissions.py::test_every_role_may_read_the_list_the_detail_and_the_attachment_list`<br>외 3건 |
| LC-083 | admin이 아니면 없는 계약을 삭제하려 해도 404가 아니라 403이다 | LC-R15, LC-R28, LC-UC9 | backend | `application/test_license_contract_end_update_delete.py::test_delete_missing_contract_by_non_admin_is_forbidden_not_not_found`<br>`application/test_license_contract_end_update_delete.py::test_delete_missing_contract_by_admin_is_not_found`<br>`web/test_license_contract_route_permissions.py::test_delete_of_a_missing_contract_is_403_before_404_unless_admin`<br>외 2건 |
| LC-084 | 정렬 키 deal_code는 422로 거절한다 | LC-R18, LC-UC3 | backend | `application/test_license_contract_query.py::test_query_sort_keys_are_the_twelve_table_columns`<br>`web/test_license_contract_routes.py::test_list_rejects_invalid_or_unknown_query_parameters`<br>`web/test_license_contract_routes.py::test_list_rejects_the_removed_deal_code_sort_like_any_unknown_sort`<br>외 2건 |
| LC-085 | 계약 첨부 설명에 NUL 문자가 있으면 422이고 아무것도 남지 않는다 | LC-R21, LC-UC10 | backend | `application/test_license_contract_attachment_description_nul.py::test_upload_description_with_a_nul_is_rejected_and_nothing_is_left` |
| LC-086 | 종료·갱신하면 ended_on은 요청의 업무 날짜이고 응답에 ended_at 키가 없다 | LC-R12, LC-R13 | backend | `application/test_license_contract_end_update_delete.py`, `domain/test_license_contract_entity.py` |
| LC-087 | 마이그레이션은 계약 종료 시각을 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다 | LC-R38 | backend | `infra/schema/test_business_dates_migration.py`, `infra/schema/test_license_contract_schema.py` |

### LC-001 처음부터 Won으로 등록한 Deal에 미발급 계약 1건이 생긴다
- Given KIM(sales)
- When Status `contract_completed`·Forecast `won`으로 Deal을 등록한다
- Then 그 Deal의 계약이 정확히 1건이고 상태 `not_issued`, 시작일·종료일·기간 없음, 기술담당 '', 점검주기 `none`, Note '', 등록자·수정자 KIM이다. 등록 응답의 `license_contract_count`는 1, `has_issued_license_contract`는 false다

### LC-002 Won이 아닌 Deal을 등록하면 계약이 생기지 않는다
- Given KIM
- When Status `prospecting`·Forecast `pipeline`으로 Deal을 등록한다
- Then 그 Deal의 계약은 0건이고 응답의 `license_contract_count`는 0이다

### LC-003 변경 경로로 Won이 된 Deal에 미발급 계약 1건이 생긴다
- Given 계약이 없는 Won이 아닌 Deal
- When 다음 중 하나로 Won으로 바꾼다(각각): 인라인 변경 Forecast → `won` / 인라인 변경 Status → `contract_completed` / Deal 폼 수정(Status·Forecast) / Action 등록의 `status_changes` 두 단계(끝이 Won)
- Then 그 Deal의 계약이 정확히 1건(`not_issued`, 등록자 = 요청자)이다

### LC-004 계약이 이미 있거나 Won을 유지하는 변경이면 새 계약이 생기지 않는다
- Given (a) Won을 벗어날 때 '유지'로 남긴 미발급 계약 1건이 있는 Won이 아닌 Deal / (b) 종료 계약만 1건 있는 Won이 아닌 Deal / (c) 발급(신규) 계약이 있는 Won Deal
- When (a)(b)는 다시 Won으로 바꾸고, (c)는 금액만 바꾸는 폼 수정을 한다
- Then (a)(b) 계약 수는 그대로 1건이다. (c) 요청은 성공하고 계약 수는 그대로이며 발급 계약도 그대로다

### LC-005 Won으로 바꾸는 변경이 거절되면 계약도 생기지 않는다
- Given 계약이 없는 Won이 아닌 Deal
- When 동기화 규칙에 어긋나는 값(예: Status `contract_completed`와 Forecast `pipeline`)으로 Won 전환을 요청한다
- Then 요청은 오류로 끝나고 Deal은 그대로이며 계약은 0건이다

### LC-006 발급 계약이 없는 Deal을 삭제 선택과 함께 Won에서 벗어나게 하면 그 Deal의 계약만 지워진다
- Given 저장 위치가 설정되어 있고, 미발급 계약 1건(첨부 파일 1개)과 Deal 첨부 파일 1개가 있는 Won Deal A, 계약이 있는 다른 Won Deal B
- When A를 `delete_license_contracts: true`로 Won 밖으로 바꾼다(인라인 변경 / Deal 폼 수정 / Action 등록 각각)
- Then A의 Forecast는 `commit`이고 A의 계약·계약 첨부 행은 0건, 그 계약 폴더는 디스크에 없다. A의 Deal 첨부 파일과 B의 계약·파일은 그대로다

### LC-007 삭제를 고르지 않았거나 Won 이탈이 아니면 계약이 지워지지 않는다
- Given 미발급 계약(첨부 파일 포함)이 있는 Deal
- When (a) Won Deal을 `delete_license_contracts: false`로 / (b) 이 값을 생략하고 Won 밖으로 바꾼다 / (c) Won이 아닌 Deal을 다른 Won 아닌 상태로 / (d) Won Deal의 금액만 / (e) Won이 아닌 Deal을 Won으로 바꾸며 `true`를 보낸다
- Then 모든 요청이 성공하고 계약·첨부 행·파일은 그대로다

### LC-008 발급 계약이 있는 Deal은 어느 경로로도 Won에서 벗어날 수 없다
- Given 발급(신규) 또는 발급(갱신) 계약(첨부 파일 포함)과 이전 Next Action이 있는 Won Deal
- When Won 밖으로 바꾼다(인라인 변경 / Deal 폼 수정 / Action 등록, 각각 `delete_license_contracts` true·false·생략)
- Then 409 `invalid-state`, 문구 "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."이다. Deal Status·Forecast·History, 계약, 첨부 파일은 그대로이고 Action 경로에서는 새 Action 행이 없고 이전 Next Action도 열린 그대로다. sales·admin 모두 같다

### LC-009 발급 계약이 없어진 Deal은 sales도 삭제를 골라 Won에서 벗어날 수 있다
- Given (a) 종료 계약만 있는 Won Deal / (b) 발급 계약을 BOSS(admin)가 삭제해 미발급 계약만 남은 Won Deal
- When KIM(sales)이 `delete_license_contracts: true`로 Won 밖으로 바꾼다
- Then 요청은 성공하고 그 Deal의 계약은 0건이다. 같은 Given에서 `false`로 바꾸면 계약이 그대로 남는다

### LC-010 화면: Won 이탈 확인에서 삭제를 누르면 삭제 요청이 간다
- Given 계약 1건(발급 아님)이 있는 Won Deal을 Deal 폼 수정·목록 인라인 편집·상세 요약 바·Action 등록 화면에서 연다(각각)
- When Won 밖으로 바꾸고(동기화 선택 뒤) `라이선스 계약 처리` 대화상자의 `삭제`를 누른다
- Then 대화상자에 "이 Deal의 라이선스 계약 1건도 삭제할까요?"가 보였고, 요청에 `deleteLicenseContracts: true`가 담겨 가며 계약이 사라진다

### LC-011 화면: Won 이탈 확인에서 유지를 누르면 계약을 남기는 요청이 간다
- Given LC-010과 같다
- When `유지`를 누른다
- Then 요청에 `deleteLicenseContracts: false`가 담겨 가고 계약은 남는다

### LC-012 화면: Won 이탈 확인에서 취소를 누르면 요청하지 않는다
- Given LC-010과 같다
- When `취소`를 누른다
- Then 요청이 가지 않고 Deal 값은 Won 그대로이며 폼·편집 상태는 남는다

### LC-013 화면: 계약이 없거나 Won 이탈이 아니면 묻지 않는다
- Given (a) 계약이 0건인 Won Deal / (b) 계약이 있는 Won Deal에서 Status·Forecast를 바꾸지 않는 폼 저장 / (c) 상태 변경 없는 Action 등록
- When 저장한다
- Then `라이선스 계약 처리` 대화상자 없이 요청이 가고 `deleteLicenseContracts`는 담기지 않는다

### LC-014 화면: 발급 계약이 있는 Deal은 안내만 띄우고 요청하지 않는다
- Given `hasIssuedLicenseContract`가 true인 Won Deal(화면 4곳 각각)
- When Won 밖으로 바꾼다
- Then 제목 `라이선스 계약 처리`, 본문 LC-R8 문구, 버튼 `확인` 하나뿐인 대화상자가 뜨고 삭제/유지 대화상자는 뜨지 않는다. `확인`을 눌러도 요청이 없고 값은 Won 그대로다

### LC-015 화면: 화면 값이 오래돼 서버가 409를 주면 문구를 보이고 다음 시도는 안내로 막는다
- Given 화면에는 발급 계약이 없다고 보이지만 서버에서는 발급 상태인 Won Deal(화면 4곳 각각)
- When Won 밖으로 바꾸고 `유지`를 눌러 요청한다
- Then 서버 409 문구가 그 화면의 오류 자리(인라인 `role="alert"`, 요약 바 편집 오류, 폼·Action 오류 배너)에 보이고 편집 칸·폼 값·Action 팝업이 남으며 Forecast는 Won 그대로다. 같은 변경을 다시 시도하면 LC-014의 안내 대화상자가 뜨고 요청이 없다

### LC-016 조건 없이 목록을 읽으면 종료일 오름차순 50건과 전체 건수가 온다
- Given 계약 60건(종료일 있는 것·없는 것 섞임)
- When 조건 없이 목록을 읽고, 이어 `offset=50`으로 읽는다
- Then 첫 응답은 `limit` 50, `offset` 0, `total` 60, 종료일 오름차순(종료일 없는 계약은 맨 뒤) 50건이고 각 항목은 2.6의 응답 키를 모두 가진다. 두 번째 응답은 나머지 10건이고 `total`은 같다

### LC-017 고객사명·제품명은 Deal 값의 대소문자 무시 부분 일치로 거른다
- Given 고객 회사명 "Neo Acme"·Product "SuperDB"인 Deal의 계약, 고객 회사명 "Beta"·Product "Other"인 Deal의 계약, 고객 회사명에 `%`가 든 Deal의 계약
- When `customer=acme` / `product=superdb` / `customer=%`로 각각 읽는다(앞뒤 공백을 붙인 값, 공백만인 값도)
- Then 각각 해당 Deal의 계약만 온다. `%`는 글자 그대로 일치한다. 공백만인 값은 조건이 없는 것과 같다

### LC-018 Vendor·담당영업·상태 조건은 일치로 거르고 모든 조건은 AND다
- Given Vendor·Owner(퇴사자 포함)·상태가 서로 다른 계약들
- When `vendor_id` / `owner_user_id`(퇴사한 Owner id 포함) / `status`(4값 각각) / 이 셋과 `customer`를 함께 준다
- Then 각 조건에 맞는 계약만 오고, 함께 주면 모두 만족하는 계약만 온다. `total`도 같은 조건의 건수다

### LC-019 날짜 범위는 양끝을 포함하고 날짜 없는 계약은 뺀다
- Given 시작일 2026-01-01·종료일 2026-12-31인 계약, 시작일 2026-06-01·종료일 2027-05-31인 계약, 미발급 계약(날짜 없음)
- When `start_from=2026-01-01&start_to=2026-01-01` / `end_to=2026-12-31`만 / `end_from=2027-01-01`만 준다
- Then 각각 첫째 계약 / 첫째 계약 / 둘째 계약만 온다. 어느 경우에도 미발급 계약은 없다

### LC-020 날짜 범위가 거꾸로면 422로 거절한다
- When `start_from=2026-02-01&start_to=2026-01-31` / `end_from=2026-02-01&end_to=2026-01-31`로 읽는다
- Then 422 `invalid-value`, 문구 "라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다." / "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."이다

### LC-021 12개 정렬 키는 방향대로 정렬하고 값 없는 칸은 맨 뒤, 동률은 id 순이다
- Given 각 정렬 키에 대해 값이 다른 계약, 값이 없는 계약(날짜 null, Vendor·파트너 없음, 빈 Deal명·제품명·기술담당·Note), 같은 값의 계약 둘
- When `sort`=12개 키(`deal_name`~`note`, LC-R18) 각각, `order`=`asc`·`desc`로 읽는다
- Then 값이 있는 계약은 방향대로(상태·점검주기는 LC-R18의 순서, 텍스트는 대소문자 무시) 정렬되고 값 없는 계약은 두 방향 모두 맨 뒤, 같은 값은 id 오름차순이다

### LC-022 화면: 계약관리를 열면 첫 50건과 전체 건수, 12개 머리글이 보인다
- Given 서버에 계약이 50건보다 많다(모든 역할 각각)
- When `/contracts`를 연다
- Then `계약 목록` 표에 50행과 `전체 N건`(서버 `total`), 머리글 12개가 LC-R30의 순서로 보이고, 첫 행 칸에 서버 값(빈 값은 `-`, 상태·점검주기는 표시 이름)이 보인다. 시안 안내 문구는 없다

### LC-023 화면: 목록 끝에 닿으면 다음 50건을 잇고 다 읽으면 끝을 알린다
- Given 서버에 계약 120건
- When 목록 끝(감시 요소)이 화면에 들어오거나 `더 보기`를 누른다(필요한 만큼)
- Then 다음 50건씩 이어 붙고, 쪽 사이에 같은 id가 겹쳐도 한 번만 보인다. 마지막 쪽 뒤에는 `더 보기`가 없고 `모두 불러왔습니다 (전체 120건)`이 보인다

### LC-024 화면: 검색 조건이 서버 조건으로 가고 초기화하면 전체로 돌아온다
- Given 계약 목록 화면
- When 고객사명 칸에 " acme "를 넣고 Enter를 누른다 / 제품명·Vendor·담당영업(퇴사자)·상태·직접 지정 날짜 범위를 고르고 `검색`을 누른다 / `초기화`를 누른다
- Then 게이트웨이 조건에 `customer: 'acme'`(공백 제거), `product`, `vendorId`, `ownerId`, `status`, `startFrom`·`startTo`·`endFrom`·`endTo`가 담겨 가고 표는 서버 결과다. 결과가 없으면 `조건에 맞는 계약이 없습니다.`와 `전체 0건`이 보인다. 초기화하면 모든 칸이 비고 조건 없는 목록이 다시 보인다

### LC-025 화면: 날짜 범위가 거꾸로면 검색하지 않고 문구를 보인다
- Given 라이선스 종료일을 직접 지정으로 시작 2026-02-01, 끝 2026-01-31로 넣었다
- When `검색`을 누른다
- Then 목록 요청이 가지 않고 시작 칸에 "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."가 보인다(시작일 범위도 같은 형식)

### LC-026 화면: 머리글을 누르면 그 열로 서버 정렬하고 다시 누르면 방향이 바뀐다
- Given 계약 목록 화면(처음 요청은 `sort: 'licenseEnd', order: 'asc'`)
- When `라이선스 종료일` 머리글을 누르고, 이어 `고객사명` 머리글을 누른다
- Then 첫 클릭 뒤 요청은 `licenseEnd`·`desc`, 둘째 클릭 뒤 요청은 `customer`·`asc`이고 표는 서버가 준 순서다

### LC-027 화면: 발급 계약의 날짜 칸은 남은 기간에 따라 색이 붙는다
- Given 서버 시계의 오늘이 2027-03-15이고 종료일이 2027-04-14·2027-04-15·2027-05-15인 발급 계약, 종료일 2027-03-31인 종료·미발급 계약
- When 목록을 연다
- Then 시작일·종료일 칸이 각각 위험(title `만료 1개월 미만`)·주의(`만료 2개월 미만`)·색 없음이고 종료·미발급 계약은 색이 없다. 상태 칸은 발급 상태면 `status-issued`, 종료면 `status-ended`, 미발급이면 둘 다 없다. 위험 색 계약을 갱신하면 새 행에는 색이 없다

### LC-028 계약 상세는 조회 시점의 Deal 값·첨부 수·Won 여부를 담는다
- Given 고객·Vendor·Product·파트너·Owner가 있는 Won Deal의 계약과 첨부 2개
- When 계약을 조회하고, Deal의 고객·Vendor·Product·Owner를 바꾸고 파트너 연결을 끊은 뒤 다시 조회하고, Deal을 Won 밖으로 바꾼 뒤 다시 조회한다
- Then 첫 응답은 그 Deal 값과 `attachment_count` 2, `deal_is_won` true다. 둘째 응답은 바뀐 Deal 값(파트너 null, Vendor는 바꾼 Vendor)이고, 셋째 응답의 `deal_is_won`은 false다. 목록 행도 같은 값이다

### LC-029 없는 계약·첨부 id로 요청하면 404다(계약 삭제는 admin만)
- Given sales와 admin
- When 없는 계약 id로 상세·수정·발급·갱신·종료·첨부 목록·첨부 업로드를(sales·admin 각각), 계약 삭제를(admin만), 없는 첨부 id로 다운로드·삭제를(sales·admin 각각) 요청한다
- Then 모두 404 `not-found`이고 문구는 "라이선스 계약을 찾을 수 없습니다." / "첨부 파일을 찾을 수 없습니다."이다. (sales의 없는 계약 삭제는 LC-083)

### LC-030 Deal 응답의 계약 건수와 발급 여부는 계약 상태를 따른다
- Given 미발급 계약 1건이 있는 Won Deal A, 계약이 있는 다른 Won Deal B
- When A에 대해 차례로 (1) 조회 (2) 미발급 계약 발급 (3) 그 계약 갱신 (4) 갱신 계약 종료를 하고 단계마다 A를 조회한다. 따로, 발급 계약이 있는 Won Deal C의 그 계약을 admin이 삭제하고 C를 조회한다
- Then A의 `has_issued_license_contract`는 (1) false (2) true (3) true (4) false이고 `license_contract_count`는 (1) 1 (2) 1 (3) 2 (4) 2다. C는 삭제 뒤 `has_issued_license_contract` false다. B의 값은 A·C의 변경과 무관하다

### LC-031 계약 칸 수정은 모든 상태에서 저장되고 기간·Deal은 그대로다
- Given 미발급·발급(신규)·발급(갱신)·종료 계약(각각), 등록자 KIM
- When PARK(sales)이 기술담당 "  홍길동  ", 점검주기 `quarterly`, Note "메모"로 수정한다
- Then 200이고 저장값은 기술담당 "홍길동"(앞뒤 공백 제거), `quarterly`, "메모"다. 상태·기간·Deal·등록자 KIM·`renewed_from_id`는 그대로이고 수정자는 PARK, 수정 시각은 요청 시각이다

### LC-032 계약 칸 수정에서 생략한 칸은 기본값으로 저장된다
- Given 기술담당 "홍길동", 점검주기 `monthly`, Note "메모"인 계약
- When 빈 본문 `{}`로 수정한다
- Then 200이고 기술담당 '', 점검주기 `none`, Note ''로 저장된다

### LC-033 계약 칸 수정에 Deal 값 칸이나 모르는 필드를 보내면 422다
- Given 계약
- When `customer`·`vendor`·`product`·`partner`·`sales_owner`·`unknown` 중 하나를 넣어 수정한다(각각)
- Then 422 `request-validation`이고 계약은 바뀌지 않는다

### LC-034 계약 칸 길이·문자 한도의 경계
- Given 계약
- When (a) 기술담당 100자·Note 2000자 / (b) 기술담당 101자 / (c) Note 2001자 / (d) 앞뒤 공백 포함 2002자이고 공백 제거 뒤 2000자인 Note / (e) NUL 문자를 넣은 기술담당·Note로 수정한다
- Then (a)(d) 200 저장. (b) 422 `request-validation`. (c) 422 `invalid-value` "Note은(는) 2000자를 넘을 수 없습니다". (e) 422 `invalid-value` "기술담당에는 NUL 문자를 쓸 수 없습니다" / "Note에는 NUL 문자를 쓸 수 없습니다". 실패한 요청 뒤 계약은 그대로다

### LC-035 계약 변경은 Deal History와 Deal 수정 시각을 바꾸지 않는다
- Given Won Deal과 그 계약, Deal의 History 건수와 수정 시각을 기억해 둔다
- When 계약 칸 수정·발급·갱신·종료·첨부 업로드를 차례로 한다
- Then Deal History 건수와 Deal 수정 시각은 처음과 같다

### LC-036 화면: 계약 수정 대화상자에서 계약 칸을 저장하면 표에 반영된다
- Given sales로 연 계약 목록
- When 행을 클릭한다(또는 행에 포커스하고 Enter), 기술담당·점검주기·Note를 고치고 `저장`을 누른다
- Then 제목 `계약 수정 - <Deal명>` 대화상자의 Deal 정보 5칸은 입력 칸이 아닌 글자로 보였고, 요청은 계약 칸 수정(세 칸만, Deal 칸 없음)이며, 대화상자가 닫히고 `계약을 수정했습니다.` 알림과 표의 새 값이 보인다

### LC-037 화면: 서버가 거절하면 대화상자 안에 문구를 보이고 닫지 않는다
- Given 서버가 계약 칸 수정에 422, 발급에 409(다른 발급 계약), 종료에 409를 주도록 준비한 계약(각각)
- When 저장(또는 발급 저장, 계약 종료 확인)을 한다
- Then 대화상자 안 `role="alert"`에 서버 문구(예: "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다.")가 보이고 대화상자는 열려 있으며 표는 바뀌지 않는다

### LC-038 화면: user에게는 계약 대화상자가 읽기 전용이다
- Given user로 연 계약 목록
- When 미발급 계약 행을 연다
- Then `저장`·`라이선스 발급`·`계약 종료`·`삭제` 버튼이 없고 기술담당·점검주기·Note 칸은 비활성이며, 첨부 영역에 업로드 폼과 `관리` 열이 없다

### LC-039 Won Deal의 미발급 계약을 발급하면 발급(신규)가 된다
- Given Won Deal의 미발급 계약
- When 시작일 2026-01-01, 기간 1년, 기술담당 "홍길동"으로 발급한다
- Then 200이고 상태 `issued_new`, 시작일 2026-01-01, 종료일 2026-12-31, 기간 `{amount: 1, unit: "year"}`, 기술담당 "홍길동"이 저장된다

### LC-040 종료일은 시작일+기간−1일이고 없는 날은 그 달 말일이다
- Given 시작일·기간 쌍: 2026-01-01+1년, 2026-01-01+6개월, 2026-01-01+12개월, 2026-01-01+2년, 2026-03-15+1개월, 2026-07-01+1개월, 2026-12-01+1개월, 2026-11-15+3개월, 2026-01-31+1개월, 2027-12-31+2개월, 2028-01-30+1개월
- When (backend) 그 값으로 발급한다 / (frontend) 대화상자에 그 값을 넣는다
- Then 종료일은 차례로 2026-12-31, 2026-06-30, 2026-12-31, 2027-12-31, 2026-04-14, 2026-07-31, 2026-12-31, 2027-02-14, 2026-02-28, 2028-02-29(윤년 2월 말일), 2028-02-29이고 화면 미리보기도 같다

### LC-041 미발급이 아닌 계약은 발급할 수 없다
- Given Won Deal의 발급(신규)·발급(갱신)·종료 계약(각각)
- When 발급한다
- Then 409 `invalid-state` "미발급 계약만 발급할 수 있습니다."이고 계약은 바뀌지 않는다

### LC-042 같은 Deal에 발급 계약이 있으면 다른 계약을 발급할 수 없다
- Given Won Deal X에 발급(신규) 계약과 미발급 계약, Won Deal Y에 미발급 계약, Won Deal Z에 종료 계약과 미발급 계약
- When X의 미발급 계약 / Y의 미발급 계약 / Z의 미발급 계약을 발급한다
- Then X는 409 `invalid-state` "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다."이고 바뀌지 않는다. Y·Z는 200이다. X의 발급 계약을 종료한 뒤 X의 미발급 계약 발급은 200이다

### LC-043 Won이 아닌 Deal의 계약은 발급할 수 없고 이 검사가 전이 검사보다 먼저다
- Given Won을 벗어나며 '유지'로 남은 미발급 계약(Deal Forecast `commit`), Lost Deal의 미발급 계약, Won이 아닌 Deal의 종료 계약
- When 각각 발급한다. 없는 계약 id로도 발급한다
- Then 앞의 셋은 409 `invalid-state` "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."이다(종료 계약도 전이 문구가 아니라 이 문구). 계약은 바뀌지 않는다. 없는 id는 404다

### LC-044 발급·갱신 요청의 기간 형식이 틀리면 422이고 1·99는 허용한다
- Given Won Deal의 미발급 계약과 발급 계약
- When 발급·갱신을 다음 본문으로 요청한다(각각): `term_amount` 0·100·1.5·"1", `term_unit` "week", `start_date`·`term_amount`·`term_unit` 중 하나 누락, `end_date` 필드 추가 / `term_amount` 1·99
- Then 앞의 경우는 422 `request-validation`이고 계약·새 행은 생기지 않는다. 1·99는 성공한다(99년 종료일은 LC-R4 계산)

### LC-045 Won을 벗어날 때 남긴 계약은 다시 Won이 되면 발급할 수 있다
- Given Won을 벗어나며 '유지'로 남긴 미발급 계약(발급이 409인 상태)
- When Deal을 다시 Won으로 바꾸고 그 계약을 발급한다
- Then 새 계약은 생기지 않았고(계약 1건) 발급은 200, 상태 `issued_new`다

### LC-046 화면: 라이선스 발급 버튼으로 기본값을 채워 발급한다
- Given 서버 시계 오늘 2026-11-09, Won Deal의 미발급 계약 대화상자(sales). 라이선스 칸은 비활성이고 시작일 빈 칸·기간 1년이 보인다
- When `라이선스 발급`을 누르고(추가 대화상자 없음) 기간을 6개월로 바꾼 뒤 `저장`을 누른다
- Then 버튼을 누르자 칸이 활성화되고 시작일 칸에 포커스, 시작일 2026-11-09, 안내 `저장하면 발급(신규)됩니다`가 보였다. 발급 요청에 계약 칸·시작일·`{amount: 6, unit: 'month'}`가 담겨 가고, 대화상자가 닫히며 `라이선스를 발급했습니다.`와 서버가 계산한 종료일·`발급(신규)`가 표에 보인다. 버튼을 누른 뒤 `취소`로 닫고 다시 열면 칸은 비활성이고 버튼이 다시 보인다

### LC-047 화면: 시작일이 비었거나 기간이 틀리면 발급·갱신 요청을 보내지 않는다
- Given 발급(또는 갱신) 버튼을 누른 대화상자
- When 시작일을 지우고 저장한다 / 기간을 비우고 저장한다
- Then 요청이 가지 않고 `라이선스 시작일을 입력하세요.` / `기간을 1~99 사이의 숫자로 입력하세요.`가 보인다

### LC-048 화면: Won이 아닌 Deal의 계약은 발급·갱신 버튼이 비활성이다
- Given `dealIsWon`이 false인 미발급 계약 대화상자(sales·admin)
- When `라이선스 발급`을 누른다
- Then 버튼은 비활성이고 힌트 `Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.`가 보이며 요청이 가지 않는다. `계약 종료`·`저장`은 동작하고 admin에게 `삭제`가 보인다. `dealIsWon`이 true면 버튼이 활성이고 힌트가 없다

### LC-049 발급 계약을 갱신하면 이전 계약은 종료되고 새 발급(갱신) 계약이 생긴다
- Given Won Deal의 발급(신규) 계약 P(종료일 2026-12-31) — 발급(갱신) 계약도 같은 케이스
- When 시작일 2027-01-01, 기간 1년, 기술담당 "김기술"로 갱신한다
- Then 201, `Location`이 `/api/v1/license-contracts/<새 id>`이고 본문은 새 계약(상태 `issued_renewal`, `renewed_from_id` = P, 2027-01-01~2027-12-31, 기술담당 "김기술")이다. P는 `ended`이고 `ended_on`이 오늘이며 기간은 그대로다. 그 Deal의 발급 상태 계약은 정확히 1건이다

### LC-050 발급 상태가 아닌 계약은 갱신할 수 없다
- Given Won Deal의 미발급·종료 계약(각각)
- When 갱신한다
- Then 409 `invalid-state` "발급 상태 계약만 갱신할 수 있습니다."이고 새 행이 없으며 계약은 바뀌지 않는다

### LC-051 Won이 아닌 Deal의 계약은 갱신할 수 없다
- Given Won이 아닌 Deal에 남은 발급 계약(이전 규칙 데이터 또는 직접 둔 상태)
- When 갱신한다
- Then 409 `invalid-state` "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."이고 새 행이 없으며 이전 계약은 발급 상태 그대로다

### LC-052 갱신해도 첨부는 이전 계약 폴더에 남고 새 계약은 새 폴더를 쓴다
- Given 첨부 파일 1개가 있는 발급 계약 P
- When P를 갱신하고 새 계약 N에 파일을 올린다
- Then P의 첨부 목록과 파일(`license-contracts/<P>/`)은 그대로이고 N의 첨부는 새 파일 1개뿐이며 `license-contracts/<N>/`에 저장된다

### LC-053 화면: 라이선스 갱신 버튼으로 다음 날부터 갱신한다
- Given 종료일 2026-12-31, 기간 1년인 발급(신규)·발급(갱신) 계약 대화상자(각각)
- When `라이선스 갱신`을 누르고 `저장`을 누른다
- Then 시작일 기본값 2027-01-01(시작일 칸 포커스)·기간 1년이었고, 갱신 요청이 가며 `라이선스를 갱신했습니다.`와 함께 표에 새 `발급(갱신)` 행과 `종료`가 된 이전 행이 보인다

### LC-054 종료가 아닌 계약을 종료하면 종료일이 기록되고 기간은 남는다
- Given 미발급·발급(신규)·발급(갱신) 계약(각각)
- When 계약 종료를 요청한다
- Then 200이고 상태 `ended`, `ended_on` = 오늘, 기간은 종료 전과 같다(미발급이면 없음). 종료한 계약은 칸 수정·첨부 업로드가 성공하고 발급·갱신은 409다

### LC-055 이미 종료된 계약은 다시 종료할 수 없다
- Given 2026-11-10에 종료한 계약
- When 나중 시각에 다시 종료한다
- Then 409 `invalid-state` "이미 종료된 계약입니다."이고 `ended_on`은 2026-11-10 그대로다

### LC-056 종료일이 지나도 계약은 자동으로 종료되지 않는다
- Given 종료일이 2026-12-31인 발급(신규) 계약
- When 시계가 2027-01-10일 때 계약을 조회한다
- Then 상태는 `issued_new` 그대로다

### LC-057 화면: 계약 종료는 확인한 뒤에만 요청한다
- Given sales로 연 미발급·발급(신규)·발급(갱신) 계약 대화상자(각각). 종료 계약 대화상자에는 `계약 종료` 버튼이 없다
- When `계약 종료`를 누르고 확인 대화상자에서 `취소`를, 다시 `계약 종료` → `종료`를 누른다
- Then 확인 대화상자(제목 `계약 종료 확인`, LC-R34 문구)가 떴고 취소에는 요청이 없다. `종료` 뒤 대화상자가 닫히고 `계약을 종료했습니다.`와 표의 `종료`가 보인다

### LC-058 admin은 어떤 상태의 계약이든 삭제하고 그 계약 폴더가 지워진다
- Given 저장 위치가 설정되어 있고, Deal에 계약 C1(미발급·발급(신규)·발급(갱신)·종료 각각, 첨부 파일 포함)과 첨부가 있는 계약 C2, Deal 첨부 파일
- When BOSS(admin)가 C1을 삭제한다
- Then 204이고 C1과 그 첨부 행이 없으며 `license-contracts/<C1>/` 폴더가 디스크에 없다. C2·C2 파일·Deal 첨부 파일은 그대로다

### LC-059 sales는 계약을 삭제할 수 없다
- Given 발급 계약(첨부 파일 포함)이 있는 Won Deal, 등록자 KIM
- When KIM(sales)이 그 계약을 삭제한다
- Then 403 `forbidden` "계약 삭제는 관리자만 할 수 있습니다."이고 계약·첨부·폴더가 그대로이며 Deal은 여전히 Won에서 벗어날 수 없다

### LC-060 갱신 원본 계약을 지우면 후속 계약의 원본 연결이 비워진다
- Given 계약 P를 갱신해 생긴 계약 N(`renewed_from_id` = P)
- When admin이 P를 삭제한다
- Then N은 남아 있고 `renewed_from_id`는 null이다

### LC-061 화면: 계약 삭제 버튼은 admin에게만 보이고 확인 뒤 삭제한다
- Given admin으로 연 미발급·발급(신규)·종료 계약 대화상자(각각), sales·user로 연 대화상자
- When admin이 `삭제` → 확인 대화상자 `취소`, 다시 `삭제` → `삭제`를 누른다
- Then sales·user에게는 `삭제` 버튼이 없다. admin의 취소에는 요청이 없고 계약이 남는다. 확인 뒤 대화상자가 닫히고 `계약을 삭제했습니다.`와 함께 표에서 그 행이 사라진다

### LC-062 저장 위치가 없거나 파일 정리가 실패해도 계약을 지우는 요청은 성공한다
- Given 첨부 파일이 있는 계약과 (a) 저장 위치 설정 없음 / (b) 폴더 삭제가 실패하는 저장소
- When admin 계약 삭제 / Won 이탈 삭제(`delete_license_contracts: true`) / Deal 삭제를 한다(각각)
- Then 요청은 성공하고 계약·첨부 행은 지워진다. (a)는 디스크 파일이 그대로 남는다. (b)는 경고 로그가 남는다. 권한 거절이나 커밋 실패로 끝난 삭제는 폴더를 지우지 않는다

### LC-063 계약 첨부를 올리면 계약 폴더에 저장되고 상태와 무관하게 올릴 수 있다
- Given 저장 위치가 설정되어 있고 미발급 계약, 종료 계약, Won이 아닌 Deal의 계약(각각)
- When KIM이 "계약서.pdf"(7바이트, 설명 "원본")를 올린다
- Then 201 `outcome` `uploaded`, `Location`이 `/api/v1/license-contract-attachments/<id>/download`이고 첨부(`contract_id`, `deal_code`, 이름, 크기 7, 업로더 KIM)가 목록에 있다. 파일은 `license-contracts/<계약 id>/<key>`에 있고 Deal 폴더는 생기지 않는다. 같은 Deal의 Deal 첨부는 Deal 폴더에 그대로 있다

### LC-064 같은 이름을 기본(ask)으로 올리면 409 file-exists다
- Given "a.pdf"가 올라가 있는 계약
- When "a.pdf"를 `on_exists` 없이 올린다
- Then 409 `file-exists` "같은 이름의 파일이 이미 있습니다: a.pdf"이고 첨부는 1개 그대로이며 새 파일이 남지 않는다

### LC-065 같은 이름을 건너뛰기로 올리면 아무것도 바뀌지 않는다
- Given "a.pdf"가 올라가 있는 계약
- When "a.pdf"를 `on_exists=skip`으로 올린다
- Then 200 `{outcome: "skipped", attachment: null}`이고 첨부·내용은 그대로이며 새 파일이 계약 폴더에 남지 않는다

### LC-066 같은 이름을 교체로 올리면 같은 첨부의 내용이 바뀌고 남의 파일은 교체할 수 없다
- Given KIM이 올린 "a.pdf"(내용 "old")가 있는 계약
- When KIM이 / BOSS(admin)가 / PARK(sales)가 "a.pdf"(내용 "new")를 `on_exists=replace`로 올린다(각각)
- Then KIM·BOSS: 200 `replaced`, 같은 첨부 id, 내용 "new", 업로더는 요청자, 이전 파일은 계약 폴더에서 지워졌다. PARK: 403 `forbidden` "본인이 올린 파일만 교체할 수 있습니다."이고 내용 "old" 그대로다

### LC-067 업로드 검증 규칙을 어기면 422이고 경계값은 허용한다
- Given 계약
- When 다음으로 올린다(각각): 파일 없음, 설명 101자, 크기 104,857,601바이트, "setup.exe"·"SETUP.EXE"·"setup.exe. "·"x.appimage", 이름 ".."·"a/b.pdf"·제어 문자 포함 / 설명 100자(앞뒤 공백 제외), "a.pdf"
- Then 앞의 경우는 422 `invalid-value`, 문구 "업로드할 파일을 선택하세요." / "설명은 100자 이내로 입력하세요." / "파일 크기가 100MB를 초과합니다. (최대 100MB)" / "실행·설치 파일(.exe)은 업로드할 수 없습니다."(확장자별) / "사용할 수 없는 파일 이름입니다."이고 첨부·파일이 생기지 않는다. 뒤의 경우는 201이다

### LC-068 저장 위치가 없으면 업로드는 503이다
- Given 저장 위치 설정이 없다
- When 계약에 파일을 올린다
- Then 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."이고 첨부가 생기지 않는다

### LC-069 업로드 도중 계약이 지워지면 404로 끝나고 계약 폴더가 남지 않는다
- Given 업로드의 파일 저장 단계가 끝난 뒤, 행을 기록하기 전에 그 계약이 지워진 상태(순차 재현)
- When 업로드가 행 기록 단계를 진행한다
- Then 404 "라이선스 계약을 찾을 수 없습니다."로 끝나고 `license-contracts/<계약 id>/` 폴더(새 파일 포함)는 디스크에 없다

### LC-070 화면: 파일을 올리면 첨부 목록에 보인다
- Given sales로 연 계약 대화상자의 `첨부 파일` 영역(서버의 기존 첨부 목록이 보인다)
- When 파일을 고르고 `업로드`를 누른다
- Then `업로드되었습니다: <이름>`이 보이고 목록에 그 파일(크기·업로드한 사용자·시각)이 보이며, 대화상자를 닫고 다시 열어도 보인다

### LC-071 화면: 화면 규칙을 어긴 파일은 요청 없이 문구를 보인다
- Given 계약 대화상자의 업로드 폼
- When "setup.exe"를 고르고 업로드한다 / 파일 없이 업로드한다 / 설명 101자로 업로드한다
- Then 요청이 가지 않고 Deal 첨부와 같은 문구가 `role="alert"`로 보인다

### LC-072 화면: 같은 이름이면 교체·건너뛰기를 묻는다
- Given "a.pdf"가 있는 계약 대화상자
- When "a.pdf"를 올려 409를 받은 뒤 `교체`를 누른다 / `건너뛰기`를 누른다
- Then `같은 이름의 파일` 대화상자(`같은 이름의 파일이 이미 있습니다: a.pdf`)가 떴고, 교체는 `replace` 요청 뒤 `교체되었습니다: a.pdf`, 건너뛰기는 `skip` 요청 뒤 목록이 그대로다. 남이 올린 파일이면 `교체`가 비활성이고 `본인이 올린 파일만 교체할 수 있습니다.`가 보인다

### LC-073 화면: 저장 위치를 쓸 수 없다는 서버 문구를 보인다
- Given 서버가 업로드에 503을 주는 상태
- When 파일을 올린다
- Then "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."가 `role="alert"`로 보이고 목록은 그대로다

### LC-074 모든 역할이 첨부 목록을 최신순으로 보고 내려받을 수 있다
- Given 계약에 "a.pdf"(먼저)·"b.pdf"(나중) 첨부
- When (backend) user·sales·admin이 첨부 목록을 읽고 "a.pdf"를 내려받는다 / (frontend) 대화상자에서 파일명 "a.pdf"를 누른다
- Then 목록은 b, a 순이다. 다운로드는 200, `application/octet-stream`, `Content-Disposition: attachment`(파일 이름 포함), 올린 바이트와 같다. 화면은 그 이름·내용으로 파일 저장을 시작한다

### LC-075 저장 위치가 없거나 파일 내용이 없으면 다운로드가 실패한다
- Given 계약 첨부 "a.pdf"
- When (a) 저장 위치 설정을 없앤 뒤 / (b) 계약 폴더의 파일만 없앤 뒤(같은 키 파일이 Deal 폴더에 있어도) 내려받는다
- Then (a) 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요." (b) 404 "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."이고 Deal 폴더의 파일을 대신 주지 않는다

### LC-076 업로더가 첨부를 지우면 그 파일만 지워지고 계약 폴더는 남는다
- Given KIM이 올린 "a.pdf"·"b.pdf"가 있는 계약, 그리고 첨부 1개만 있는 다른 계약
- When KIM이 "a.pdf"를 지우고, 다른 계약의 마지막 첨부도 지운다
- Then 204이고 "a.pdf" 행·파일이 없으며 "b.pdf"는 그대로다. 두 계약의 계약 폴더는 남는다(마지막 첨부를 지워 빈 폴더여도)

### LC-077 첨부 삭제 권한: 남의 파일은 sales가 지울 수 없고 admin·퇴사 sales 파일은 된다
- Given KIM(sales)이 올린 파일, 퇴사한 sales가 올린 파일
- When PARK(sales)가 KIM의 파일을 / BOSS(admin)가 KIM의 파일을 / PARK가 퇴사 sales의 파일을 지운다
- Then PARK→KIM 파일은 403 `forbidden` "본인이 올린 파일만 삭제할 수 있습니다."이고 그대로다. 나머지 둘은 204로 지워진다

### LC-078 화면: 첨부 삭제는 확인 뒤에만, 권한 없는 행은 버튼이 비활성이다
- Given 본인 파일과 남의 파일이 있는 계약 대화상자(sales)
- When 본인 파일의 `삭제` → 확인 대화상자 `취소`, 다시 `삭제` → `삭제`를 누른다
- Then 남의 파일 `삭제`는 비활성(title `본인이 올린 파일만 삭제할 수 있습니다.`)이다. 확인 대화상자(`첨부 파일 삭제`, `"<이름>" 파일을 삭제합니다.`)의 취소에는 요청이 없고, 확인 뒤 `삭제되었습니다: <이름>`과 함께 목록에서 사라진다

### LC-079 Deal 삭제 영향에 계약 건수가 나온다
- Given 계약 2건(계약 첨부 1개)과 Deal 첨부 1개가 있는 Deal, 계약이 없는 Deal
- When 각 Deal의 삭제 영향을 읽는다
- Then 첫 Deal은 `license_contract_count` 2, `attachment_count` 1(계약 첨부는 세지 않음)이고 둘째는 `license_contract_count` 0이다

### LC-080 Deal을 지우면 계약·첨부와 Deal 폴더·계약 폴더가 함께 지워진다
- Given 저장 위치가 설정되어 있고 발급 계약과 종료 계약(각각 첨부 파일)·Deal 첨부 파일이 있는 Deal, 계약이 있는 다른 Deal
- When admin이 Deal을 삭제한다
- Then 삭제는 성공하고(발급 계약이 있어도) 그 Deal의 계약·계약 첨부 행이 없으며 Deal 폴더와 두 계약 폴더가 디스크에 없다. 다른 Deal의 계약·파일은 그대로다

### LC-081 화면: Deal 삭제 확인에 라이선스 계약 건수가 보인다
- Given 계약 2건이 있는 Deal과 계약이 없는 Deal의 상세
- When admin이 Deal 삭제를 누르고, 확인 뒤 삭제한다
- Then 확인 대화상자 문구에 `라이선스 계약 2건` / `라이선스 계약 0건`이 보이고, 삭제 뒤 그 Deal의 계약은 계약 목록에 없다

### LC-082 조회는 모든 역할, 쓰기는 user에게 먼저 403이다
- Given user·sales·admin, 계약과 첨부
- When user가 계약 칸 수정·발급·갱신·종료·삭제·첨부 업로드·첨부 삭제를 요청한다(잘못된 본문이나 없는 id로도) / 세 역할이 목록·상세·첨부 목록·다운로드를 요청한다 / sales·admin이 계약 칸 수정·종료를 요청한다
- Then user의 쓰기는 모두 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고(본문 422·없음 404보다 먼저) 아무것도 바뀌지 않는다. 조회는 세 역할 모두 200이다. sales·admin의 수정·종료는 200이다

### LC-083 admin이 아니면 없는 계약을 삭제하려 해도 404가 아니라 403이다
- Given 계약이 없는 id, KIM(sales), VIEWER(user), BOSS(admin)
- When 각자 그 id의 계약을 삭제한다
- Then KIM은 403 `forbidden` "계약 삭제는 관리자만 할 수 있습니다.", VIEWER는 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이다. BOSS만 404 `not-found` "라이선스 계약을 찾을 수 없습니다."이다

### LC-084 정렬 키 deal_code는 422로 거절한다
- Given 계약이 있는 목록
- When `sort=deal_code`로 목록을 읽는다(`order` 두 방향 각각). 비교로 없는 정렬 키 `sort=unknown`으로도 읽는다
- Then 둘 다 422 `request-validation` "요청 형식이 올바르지 않습니다"이고 같은 형식의 오류다. `sort=deal_name`은 200이다

### LC-085 계약 첨부 설명에 NUL 문자가 있으면 422이고 아무것도 남지 않는다
- Given 저장 위치가 설정되어 있고 계약 C가 있다
- When KIM(sales)이 C에 "a.pdf"를 설명 "a\u0000b"로 올리고, NUL을 포함한 101자 설명으로도 올린다
- Then 둘 다 422 `invalid-value` "설명에는 NUL 문자를 쓸 수 없습니다"이고(101자여도 길이 문구보다 NUL 문구가 먼저) C의 첨부 행과 계약 폴더 파일이 생기지 않는다

### LC-086 종료·갱신하면 ended_on은 요청의 업무 날짜이고 응답에 ended_at 키가 없다
- Given 업무 시간대는 Asia/Seoul, 서버 시계는 `2026-11-13T23:30:00+09:00`이고, 발급(신규) 계약 P와 미발급 계약 Q가 있다
- When P를 갱신하고 Q를 종료한다
- Then P와 Q의 `ended_on`은 "2026-11-13"이고 응답에 `ended_at` 키는 없다. OpenAPI의 `ended_on`은 format date이며 null을 허용한다. 게이트웨이 계약 테스트의 `endedOn`도 날짜 문자열이다

### LC-087 마이그레이션은 계약 종료 시각을 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다
- Given 기준선 리비전 DB(Asia/Seoul)에 `ended_at`이 `2026-11-12T15:30:00Z`인 종료 계약과 `ended_at`이 null인 발급 계약이 있다
- When `upgrade head`를 실행한 뒤 다시 `downgrade -1`을 실행한다
- Then upgrade 뒤에는 계약이 2건 그대로이고, `ended_on`은 2026-11-13, null이며, `ck_license_contracts_ended_has_date`가 있고 `ended_at` 컬럼은 없다. downgrade 뒤에는 `ended_at`이 `2026-11-13T00:00:00+09:00`, null이다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-09 | 최초 작성(시범): 구현된 계약관리 동작을 정본 명세로 옮김. 규칙 LC-R1~R37, use case LC-UC1~UC13, BDD 케이스 LC-001~LC-082 | LC-001~LC-082(신규) |
| 2026-11-09 | 사용자 결정 반영. 확정(코드 그대로): 표기 혼용 유지(통일은 후속), 기술담당/Note 길이 오류 형식 차이(LC-R14), PUT 생략 칸 기본값 덮어쓰기(LC-R14), 기존 Won Deal 계약 일괄 생성 제외(LC-R7·범위 밖). **규칙 변경(운영 코드 변경 필요)**: LC-R18 정렬 키 `deal_code` 제거(12개, 공개 API 호환 깨짐·사용자 승인), LC-R15·LC-R28 계약 삭제는 admin이 아니면 존재 무관 403 먼저(없는 id 404는 admin만), 2.5·2.6·2.8·LC-UC3·LC-UC9 갱신 | 변경: LC-021(13→12 키), LC-029(계약 삭제 404는 admin만). 신규: LC-083, LC-084 |
| 2026-11-10 | 보충(사용자 결정 E4, Deal 첨부 AT 문서 정리): LC-R21에 첨부 설명 NUL 거절(길이 판정보다 먼저, 422 `invalid-value` "설명에는 NUL 문자를 쓸 수 없습니다")을 적고 2.8 첨부 검증 행에 표시. 코드 변경 없음(Deal 첨부와 같은 설명 검사), 상태 줄 그대로 | 신규: LC-085(테스트 위치는 test-engineer가 채움) |
| 2026-11-12 | DD-R41(완료된 Deal은 admin만 삭제)에 맞춰 LC-R27에 주석, 계약이 있는(= Won) Deal을 지우는 LC-080·LC-081의 행위자를 admin으로 명시. 계약 동작 변경 없음 | 변경: LC-080, LC-081(행위자만) |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 계약 종료일을 date `ended_on`으로(2.2, LC-R5·R12·R13, 2.6), LC-R38 신설(데이터 변환). 응답 필드 변경(호환 깨짐, 사용자 승인), 화면 표시는 없음 | 신규 LC-086, LC-087. 변경 LC-054, 갱신 케이스, 이미 종료 케이스 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): Deal Vendor를 비울 수 없게 되어(DE-R7) LC-028 Then 표현만 바꿈. 계약 응답 `vendor` nullable은 그대로 | 변경 LC-028 |
| 2026-11-16 | 초안(사용자 확인 대기): Deal Solution → Product 이름 변경(DE 2026-11-16)에 따라 LC-R1 제품명 출처 표기. 계약 API의 `product` 키·동작은 그대로 | 변경(표기): LC-017, LC-028 |
