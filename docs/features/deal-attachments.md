# Deal 첨부 파일   (feature 코드: AT, 상태: 확정(2026-11-10 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/domain/attachment/{values,entities,policy,errors,history}.py`, `app/application/attachment/{upload_attachment,delete_attachment,download_attachment,list_attachments,get_attachment,storage_cleanup,inputs}.py`, `app/application/ports/{attachment_repository,file_storage}.py`, `app/application/storage/{errors,folders}.py`, `app/infra/db/{models_attachment,attachment_repository,deal_aggregates}.py`, `app/infra/storage/local_file_storage.py`, `app/web/routers/{attachments,attachment_items}.py`, `app/web/schemas/attachment.py`, `app/web/content_disposition.py`, `frontend/src/features/deals/detail/{AttachmentsPanel,UploadForm,detailHelpers}.tsx|ts`, `shared/model/{fileRules,permissions}.ts`, `data/attachments.ts`, `gateway/http/{attachments,contentDisposition}.ts`, `test/fake/gateway/attachments.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 화면·Fake·다른 문서가 어긋나던 점은 2026-11-10 사용자 결정으로 현행 동작대로 문서화했습니다(AT-R7 업로드 `Location`, AT-R16 화면이 쓰지 않는 단건 조회, AT-R26·R27 알림·대화상자 이름 표기, AT-R27 "건너뛰기"). 설명 NUL 규칙은 LC-R21에 보충했습니다(LC-085). 결정 목록은 계획(`artifacts/10-analysis/at-plan.md`)에 있습니다.

## 1. 개요

- 목적: Deal에 견적서·제안서 같은 파일을 올려 두고, 로그인한 누구나 목록을 보고 내려받게 한다. 같은 이름을 다시 올리면 묻고(교체·건너뛰기), 올리기·교체·삭제는 Deal History에 남는다.
- 사용자(역할): 조회·다운로드는 로그인한 모든 역할(admin·sales·user), 업로드는 sales·admin, 삭제·교체는 admin(모든 파일)과 sales(본인 파일, 퇴사한 sales의 파일).
- 범위
  - API `GET·POST /deals/{code}/attachments`, `GET /attachments/{attachment_id}`, `GET /attachments/{attachment_id}/download`, `DELETE /attachments/{attachment_id}`
  - 업로드 검증(파일 없음·설명·크기·차단 확장자·파일 이름), 같은 이름 처리(`ask`·`skip`·`replace`), 교체·삭제 권한, 디스크 저장 위치(`<저장 위치>/<deal_code>/<key>`)와 저장·커밋 실패 시 파일 정리, 다운로드 헤더(`Content-Disposition`)
  - 첨부가 남기는 Deal History 항목 문구와 Deal 수정 시각, 삭제 영향의 첨부 건수 계산
  - 화면: Deal 상세 탭의 첨부 패널(목록·업로드 폼·같은 이름 확인·삭제 확인·내려받기), 게이트웨이, Fake 게이트웨이
- 범위 밖(다른 feature)
  - 계약 첨부(`/license-contracts/{id}/attachments`, `/license-contract-attachments/*`), 계약 폴더 → LC. 업로드 검증 규칙의 목록·문구(LC-R21), 삭제·교체 권한 행렬과 문구(LC-R23), 다운로드 헤더·실패 문구(LC-R24)는 **LC가 먼저 정의했으므로 이 문서는 번호로 가리키고 Deal 첨부에만 있는 동작을 더한다**(2026-11-10 결정: 파일 이름·확장자·권한·다운로드 규칙은 LC 소유)
  - 저장 위치 설정·쓰기 테스트·경로 규칙 → IN(IN-R22~R27, IN-R36)
  - Deal 삭제 시 첨부 행 CASCADE와 `<저장 위치>/<deal_code>` 폴더 정리 → DD(DD-R25·R26), 삭제 확인 대화상자의 첨부 건수 표시 → DD(DD-R39). 삭제 영향 API 자체 → DD(DD-R22), 첨부 건수의 계산 → AT-R21
  - Deal History 목록·필터·자르기 → DD(DD-R17·R20·R38). 첨부 탭 위치·탭 틀 → DD(DD-R27)
  - 최종 업데이트(`last_updated_at`)는 첨부와 무관 → RK(RK-R2)
  - 업로더 사용자 삭제 시 퇴사 처리 → US(US-R17)
  - 공통 판정 순서·CSRF·401·Problem 형식·id 경로 파라미터·화면 오류 문구 → PL(PL-R4~R6, PL-R9~R13, PL-R22, PL-R36~R39), 시각 표기 → TM(TM-R8)
  - 경쟁·동시성(같은 이름 동시 업로드, 업로드 도중 Deal 삭제 등)은 코드가 Deal 행 잠금으로 직렬화하지만 테스트 케이스로 두지 않는다
- 관련 화면·메뉴: Deals → Deal 상세(`/deals/:dealCode`)의 "Deal 상세" 탭 안 "첨부 파일" 영역(DD-R27).

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| 첨부 | `deal_attachments` 한 행(메타데이터)과 디스크 파일 하나. Deal 하나에 속한다 |
| 저장 위치 | 첨부 파일을 두는 서버 디렉터리(`storage_settings`, IN-R22). 없으면 업로드·다운로드를 할 수 없다 |
| Deal 폴더 | `<저장 위치>/<deal_code>/` |
| 저장 키(`storage_key`) | 디스크 파일 이름. 업로드·교체마다 새로 만드는 32자 소문자 16진수(원래 파일 이름을 쓰지 않는다) |
| 같은 이름 | 같은 Deal 안에서 NFC 정규화한 파일 이름이 글자 그대로(대소문자 구분) 같은 것 |
| `on_exists` | 같은 이름이 있을 때의 선택: `ask`(묻기, 기본) · `skip`(건너뛰기) · `replace`(교체) |
| 교체 | 같은 첨부 id·이름을 유지한 채 내용·설명·업로더·업로드 시각을 새 파일로 바꾸는 것 |

### 2.2 데이터 모델

`deal_attachments`

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | BIGINT identity (MAXVALUE 2^53−1) | PK | API에서 JSON 정수 |
| deal_id | BIGINT | NOT NULL, FK `deals.id` ON DELETE CASCADE | |
| file_name | VARCHAR(255) | NOT NULL, UNIQUE(deal_id, file_name) `uq_deal_attachments_deal_id_file_name` | NFC 정규화 값 |
| description | VARCHAR(100) | NOT NULL DEFAULT '' | 앞뒤 공백 제거 값 |
| mime | VARCHAR(255) | NOT NULL | 업로드 때의 Content-Type(AT-R6) |
| size_bytes | BIGINT | NOT NULL, CHECK 0~104,857,600 | 실제 저장한 바이트 수 |
| storage_key | VARCHAR(32) | NOT NULL, UNIQUE | |
| uploaded_by_user_id | BIGINT | NOT NULL, FK `users.id` RESTRICT | |
| uploaded_at, created_at, updated_at | TIMESTAMPTZ | NOT NULL | |

- 인덱스: `ix_deal_attachments_uploaded_by_user_id`, `ix_deal_attachments_deal_id_uploaded_at`.
- 디스크: `<저장 위치>/<deal_code>/<storage_key>`(LC-R25와 같은 배치). 폴더 조각은 application이 정하고(`deal_folder`), 저장소 구현은 경로 조각의 심볼릭 링크를 따라가지 않는다.
- 도메인: `Attachment`(`upload`·`replace`·`ensure_deletable_by`·`ensure_replaceable_by`), `FileName`(NFC, `parse`·`extension`), `UploadCandidate.check`(검증 순서), `OnExists`, `can_delete_attachment`(권한), 이력 초안 `uploaded_draft`·`replaced_draft`·`deleted_draft`. Port: `AttachmentRepository`, `FileStorage`, `StorageSettingsRepository`(IN).

### 2.3 비즈니스 규칙

첨부와 이름
- **AT-R1** 첨부는 Deal 하나에 속하고 이름과 소속 Deal은 바뀌지 않는다. 메타데이터는 DB가 정본이고 내용은 디스크에 있다. 저장 위치를 바꿔도 기존 파일은 옮기지 않는다(IN-R25).
- **AT-R2** 파일 이름은 NFC로 정규화해 저장·비교·표시한다. 앞뒤 공백은 자르지 않는다. 같은 Deal 안에서 같은 이름(AT-R12)은 하나뿐이고(DB UNIQUE), 대소문자만 다른 이름(`Report.PDF`·`report.pdf`)은 다른 파일이며, 다른 Deal의 같은 이름은 별개 파일이다.

업로드
- **AT-R3** 업로드 검증은 LC-R21과 같은 순서·문구·차단 확장자 24개·이름 규칙이다(`UploadCandidate.check`). Deal 첨부에서 분명히 할 세부: ① 크기는 요청이 선언한 파일 크기가 있을 때 이 단계에서 보고, 저장하면서 실제 바이트로 다시 본다(AT-R6). ② 차단 확장자는 **정규화 전 원본 이름**에서 끝의 공백(유니코드 공백 포함)과 점을 걷은 뒤 마지막 `.` 뒤를 소문자로 본다. 마지막 `.`가 맨 앞이거나 없으면 확장자가 없다(`.exe`, `.bashrc`, `README`). 그래서 `setup.exe `·`setup.exe.`·`RUN.Sh`·`a.b.ps1`은 막히고 `a.tar.gz`·`exe.txt`·`a.exe.txt`는 된다. 문구의 확장자는 소문자다. ③ 이름 규칙(NFC 뒤 판정): 빈 이름, 255 코드 포인트 초과, `.`·`..`, `/`·`\`, 제어 문자(U+0000~U+001F, U+007F), 유니코드 서식 문자(범주 Cf 전부: 방향 제어 U+202A~202E·U+2066~2069·U+200E/F·U+061C, 제로폭 U+200B·ZWJ U+200D, BOM U+FEFF 등)를 거부한다. 서식 문자가 없는 한글·이모지·오른쪽→왼쪽 글자는 된다. 위반은 모두 422 `invalid-value`이고 첫 위반 하나만 보인다. 실패하면 행·이력·디스크 파일이 남지 않는다.
- **AT-R4** 설명은 앞뒤 공백을 지우고 저장하며 비어도 된다(생략 = ''). 길이는 공백 제거 뒤 코드 포인트 100 이하(LC-R21). 설명에 NUL 문자가 있으면 길이 판정보다 먼저 422 `invalid-value` "설명에는 NUL 문자를 쓸 수 없습니다"다(LC-R21, 2026-11-10 보충 — 계약 첨부도 같다, LC-085).
- **AT-R5** 요청은 `multipart/form-data`이고 파트는 `file`(파일, 없으면 AT-R3의 "업로드할 파일을 선택하세요."), `description`(문자열, 기본 ''), `on_exists`(`ask`·`replace`·`skip`, 기본 `ask`)다. `on_exists`가 이 셋이 아니거나 본문이 multipart가 아니면(예: JSON) 422 `request-validation`이다(500이 아님).
- **AT-R6** 저장: 새 저장 키로 `<저장 위치>/<deal_code>/<key>`에 새 파일을 만든다(없는 Deal 폴더는 만든다). `size`는 실제로 쓴 바이트 수다(선언 크기와 무관, 선언이 없어도 된다, 0바이트 허용). 쓰는 도중 104,857,600바이트를 넘으면 422 `invalid-value` "파일 크기가 100MB를 초과합니다. (최대 100MB)"이고 쓰던 파일은 남지 않는다(정확히 104,857,600바이트는 된다). `mime`은 요청 파일 파트의 Content-Type이고, 없거나 255자를 넘으면 `application/octet-stream`이다. `uploaded_at`·`created_at`·`updated_at`은 요청 시각(서버 시계), 업로더는 요청자다.
- **AT-R7** 새 파일 성공은 201 `{outcome: "uploaded", attachment: AttachmentResponse}`이고 `Location: /api/v1/attachments/<id>`(단건 조회 주소. 계약 첨부는 다운로드 주소(LC-R21)로 다르며 현행 유지, 2026-11-10 결정)다.
- **AT-R8** 저장 위치: 설정이 없으면 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."(검증 위반이 먼저, 같은 이름 판정보다 먼저). 설정은 있으나 폴더를 만들거나 쓸 수 없으면 같은 503이다(같은 이름 판정 뒤). 두 경우 모두 행·이력·파일이 남지 않는다. 원인(OS 오류)은 응답에 싣지 않고 로그로만 남긴다.
- **AT-R9** 업로드(새 파일)·교체·삭제는 각각 Deal History 1건을 남긴다: 구분 `attachment`, 대상 "첨부 파일", 변경 전 "", 변경 후 "업로드 <이름>" / "교체 <이름>" / "삭제 <이름>"(NFC 이름), 변경자 = 요청자, 시각 = 요청 시각. 같은 트랜잭션에서 Deal `updated_at`이 요청 시각이 된다. 거절된 요청, `ask`의 409, `skip`은 이력도 Deal 시각 변경도 없다. 최종 업데이트(`last_updated_at`)는 바뀌지 않는다(RK-R2).
- **AT-R10** 업로드 판정 순서: 401(PL-R5) → CSRF 403(PL-R9) → `user` 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(PL-R6, 없는 Deal이어도) → 요청 형식 422 `request-validation`(AT-R5) → 없는 Deal·형식이 틀린 code 404 "Deal을 찾을 수 없습니다."(DD-R1, 파일 검증·저장 위치보다 먼저) → 검증 422(AT-R3·R4) → 저장 위치 없음 503(AT-R8) → 같은 이름(AT-R12, `replace`면 교체 권한 403 AT-R13) → 저장 실패 503·실제 크기 초과 422(AT-R6·R8).
- **AT-R11** `user`는 업로드·삭제를 할 수 없고(403, PL-R6) 목록·단건·다운로드는 할 수 있다. 미인증은 모든 첨부 경로에서 401이다.

같은 이름
- **AT-R12** 같은 Deal에 같은 이름(AT-R2)이 있으면 `on_exists`에 따라: `ask` 409 `file-exists` "같은 이름의 파일이 이미 있습니다: <NFC 이름>"이고 아무것도 바뀌지 않는다. `skip` 200 `{outcome: "skipped", attachment: null}`, `Location` 없음, 행·내용·이력·Deal 수정 시각이 그대로이고 새로 쓴 파일도 남지 않는다. `replace` 200 `{outcome: "replaced", attachment}` — 같은 id·이름, 설명(요청 값, 생략이면 '')·크기·mime·저장 키·업로더(= 요청자)·`uploaded_at`·`updated_at`(= 요청 시각)이 바뀌고 `created_at`은 그대로이며, 이전 디스크 파일은 커밋 뒤 지운다. 같은 이름이 없으면 `replace`·`skip`도 새 업로드(201 `uploaded`)다.
- **AT-R13** 교체·삭제 권한은 하나의 규칙(LC-R23의 행렬과 문구)이다: admin은 모든 파일, sales는 본인이 올린 파일 또는 **업로더가 퇴사한 sales**인 파일(퇴사한 admin의 파일은 안 됨), user는 불가. 교체 위반은 403 `forbidden` "본인이 올린 파일만 교체할 수 있습니다.", 삭제 위반은 403 `forbidden` "본인이 올린 파일만 삭제할 수 있습니다."이고 아무것도 바뀌지 않는다. `ask`·`skip`은 권한을 보지 않는다(남의 파일 이름이어도 `ask`는 409, `skip`은 200).

저장 실패 정리
- **AT-R14** DB가 정본이다. 커밋 전에 실패하면(권한 거절, DB 오류, 커밋 실패 등) 새로 쓴 파일을 지우고 오류를 그대로 낸다. 교체였으면 이전 파일은 그대로 남는다. 커밋이 끝난 뒤의 오류에서는 커밋된 행이 새 파일을 가리키므로 새 파일을 지우지 않는다. 교체 뒤 이전 파일을 지우지 못해도 교체는 성공이고 경고 로그 `attachment file cleanup failed folder=<deal_code> key=<key>`만 남는다. 업로드 스트림이 도중에 끊기거나 읽기 오류가 나면 쓰던 파일은 남지 않는다.

목록·단건·다운로드
- **AT-R15** `GET /deals/{code}/attachments`는 로그인한 모든 역할이 부른다. 200 `{items: AttachmentResponse[]}` — 그 Deal의 첨부만, `uploaded_at` 내림차순·같으면 id 내림차순(교체한 파일은 업로드 시각이 바뀌어 위로 온다). 첨부가 없으면 `{items: []}`. 없는 Deal·형식이 틀린 code는 404 "Deal을 찾을 수 없습니다."(DD-R1). 목록은 저장 위치·디스크 상태와 무관하게 행 기준으로 나온다.
- **AT-R16** `GET /attachments/{attachment_id}`는 로그인한 모든 역할이 부른다. 200 `AttachmentResponse`(목록 항목·업로드 응답과 같은 값), 없으면 404 `not-found` "첨부 파일을 찾을 수 없습니다.". id 형식은 PL-R22. 화면은 이 경로를 쓰지 않으며 공개 API로 유지한다(현행 유지, 2026-11-10 결정).
- **AT-R17** `GET /attachments/{attachment_id}/download`는 로그인한 모든 역할이 부른다(다운로드 공통 규칙은 LC-R24, 여기서는 Deal 첨부 경로와 헤더 세부를 정한다). 200 본문은 저장한 바이트 그대로(여러 청크로 흘려보내도 같음, 0바이트 가능), `Content-Type: application/octet-stream`(올린 mime과 무관 — HTML도 브라우저 안에서 열리지 않음), `Content-Length` = 디스크 파일 크기, `Content-Disposition: attachment; filename="<대체 이름>"; filename*=UTF-8''<퍼센트 인코딩 이름>`. 대체 이름은 출력 가능한 ASCII(U+0020~U+007E) 중 `"`·`\`·`%`가 아닌 글자는 그대로, 나머지는 코드 포인트마다 `_`다. `filename*`는 UTF-8 퍼센트 인코딩이고 안전 문자 예외가 없다(공백 `%20`, `/`·`;`·`%`도 인코딩). 헤더에 줄바꿈이 들어가지 않는다. 예: `report.pdf` → `attachment; filename="report.pdf"; filename*=UTF-8''report.pdf`, `견적서 최종.pdf` → `filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C%20%EC%B5%9C%EC%A2%85.pdf`.
- **AT-R18** 다운로드 실패(문구는 LC-R24와 같다): 없는 첨부 404 "첨부 파일을 찾을 수 없습니다."; 저장 위치 설정 없음 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."; **현재** 저장 위치의 `<deal_code>/<key>`에 파일이 없으면(파일·폴더 없음, 폴더 자리가 일반 파일, 경로 조각이 심볼릭 링크) 404 `not-found` "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."; 파일은 있으나 읽을 수 없으면 '없음'이 아니라 503(같은 다운로드 문구)이다. 저장 위치를 바꾸고 파일을 옮기지 않았으면 다운로드는 404 내용 없음이지만 목록·단건은 그대로 보인다.

삭제
- **AT-R19** `DELETE /attachments/{attachment_id}` 성공은 204(본문 없음). 판정 순서: 401 → CSRF 403 → `user` 403(PL-R6, 없는 id여도 404보다 먼저) → id 형식 422(PL-R22) → 없는 첨부 404 "첨부 파일을 찾을 수 없습니다."(sales·admin, 권한 판정보다 먼저) → 삭제 권한 403(AT-R13). 성공하면 한 트랜잭션에서 행을 지우고 이력(AT-R9)을 남기고 Deal 수정 시각을 바꾼 뒤, 커밋 뒤 그 디스크 파일 하나만 지운다(Deal 폴더와 같은 Deal의 다른 파일은 남는다). 이미 지운 첨부를 다시 지우면 404다.
- **AT-R20** 삭제 파일 정리: 저장 위치 설정이 없으면 디스크를 건드리지 않고 행만 지운다(204). 디스크 파일을 지우지 못하면 204이고 행·이력은 지워진 그대로이며 경고 로그만 남는다. 권한 거절이나 커밋 실패로 끝나면 행과 파일이 모두 남는다.
- **AT-R21** 삭제 영향(`GET /deals/{code}/deletion-impact`, DD-R22)의 `attachment_count`는 그 Deal의 현재 첨부 행 수다: 교체는 같은 행이라 1건, 지운 첨부는 빠지고, 다른 Deal의 첨부와 계약 첨부(LC-R20)는 세지 않는다.
- **AT-R22** 업로더는 users FK RESTRICT라, 첨부를 올린 사용자를 삭제하면 물리 삭제 대신 퇴사 처리되고(US-R17) 첨부와 파일은 남는다. 응답의 `uploaded_by`는 퇴사자도 그 사용자(`resigned` true, `label` "<이름>(퇴사)")다.

화면(frontend, Deal 상세 탭의 첨부 패널)
- **AT-R23** 패널은 영역(region, 제목 h2 "첨부 파일")이다. 읽는 동안 "불러오는 중…"(role=status), 목록을 읽지 못하면 서버 문구 오류 배너(PL-R37), 첨부가 없으면 "첨부된 파일이 없습니다."다. 표(aria-label "첨부 파일 목록")의 머리글은 파일명·설명·크기·업로드한 사용자·업로드 시각(+ 쓰기 권한이면 관리)이고 서버 순서를 그대로 보인다. 파일명은 버튼(내려받기), 빈 설명은 "—", 크기는 1024바이트 미만 "N B", 1MiB 미만 "N KB"(반올림), 그 이상 "N.N MB"(소수 한 자리), 업로더는 사용자 표기(퇴사자 "<이름>(퇴사)"), 업로드 시각은 TM-R8 표기다.
- **AT-R24** `canWrite`(admin·sales, PL-R36)이면 업로드 폼과 관리 열이 있다. `user`는 파일명을 눌러 내려받기만 하고 업로드 폼·`업로드` 버튼·`삭제` 버튼이 없다.
- **AT-R25** 업로드 폼(aria-label "파일 업로드"): "파일" 칸, "설명" 칸, 글자 수 "<n>/100"(앞뒤 공백을 뺀 코드 포인트, 100 초과면 강조 클래스 `over`), 버튼 "업로드"(요청 중 비활성). 제출하면 먼저 `validateUpload`(서버와 같은 순서·문구: 파일 없음 → 설명 100자 → 100MB → 차단 확장자 → 파일 이름, LC-R21·AT-R3)로 검사하고, 위반이면 요청 없이 폼 아래에 문구를 role=alert로 보인다. 경계값(정확히 100MB, 설명 100자, `a.tar.gz`)은 통과한다. 설명 NUL은 화면에서 검사하지 않는다(서버 AT-R4).
- **AT-R26** 업로드 결과: 성공이면 닫을 수 있는 성공 알림 "업로드되었습니다: <선택한 파일 이름>" 또는 "교체되었습니다: <선택한 파일 이름>"을 보이고 파일·설명 칸을 비우며, 첨부 목록·Deal History·Deal(상세·목록)을 다시 읽는다(새 파일이 맨 위, NFD로 고른 이름은 서버가 준 NFC 이름으로 보임). 알림·같은 이름 대화상자는 선택한 파일 이름 원문(NFD일 수 있음)을, 목록은 서버가 정규화한 NFC 이름을 보인다(현행 유지, 2026-11-10 결정). `file-exists`가 아닌 서버 거절(503 등)은 서버 문구를 폼 아래 role=alert로 보이고 목록은 그대로다.
- **AT-R27** 같은 이름(409 `file-exists`)이면 확인 대화상자(제목 "같은 이름의 파일", 문구 "같은 이름의 파일이 이미 있습니다: <선택한 파일 이름>", 확인 버튼 "교체", 취소 버튼 "건너뛰기")를 띄운다. "교체"는 같은 파일·설명을 `on_exists=replace`로 다시 보낸다. "건너뛰기"(·Esc)는 **요청 없이** 대화상자만 닫고 목록·알림이 바뀌지 않는다(서버 `skip`은 화면이 쓰지 않는다. 현행 유지, 2026-11-10 결정). 목록에서 같은 NFC 이름을 가진 파일의 업로더로 판단해 교체 권한(`canDeleteAttachment`, AT-R28)이 없으면 "교체"는 비활성이고 "본인이 올린 파일만 교체할 수 있습니다."를 보인다(건너뛰기는 활성). 교체 요청이 실패하면 대화상자를 닫고 서버 문구를 폼 아래 role=alert로 보인다.
- **AT-R28** 관리 열의 "삭제" 버튼(접근 이름 "<파일 이름> 삭제")은 `canDeleteAttachment`(admin은 모두, sales는 본인 또는 업로더가 퇴사한 sales, user는 불가 — AT-R13과 같은 규칙)가 거짓이면 비활성이고 title "본인이 올린 파일만 삭제할 수 있습니다."다. 누르면 확인 대화상자(제목 "첨부 파일 삭제", 문구 `"<이름>" 파일을 삭제합니다. 삭제는 Deal History에 기록됩니다.`, 위험 버튼 "삭제", "취소")를 띄우고, 확인하면 삭제 요청 → 성공 알림 "삭제되었습니다: <이름>"과 함께 목록에서 사라지고 Deal History에 남는다. 실패하면 오류 배너다. "취소"는 요청 없이 닫는다.
- **AT-R29** 파일명을 누르면 다운로드 요청을 보내고 받은 내용을 파일로 저장한다. 저장 이름은 `Content-Disposition`에서 읽는다: `filename*`(UTF-8, 문자셋 이름 대소문자 무시)를 우선하고, 없거나 해독할 수 없으면 `filename`(따옴표·`\` 이스케이프 해제, 따옴표 안 `;` 유지, 따옴표 없는 토큰도 읽음), 둘 다 없거나 비면 "download"다. 이름의 `/`는 `_`로 바꾸고 결과가 `.`·`..`이면 "download"다. 다운로드가 실패하면 서버 문구 오류 배너를 보인다.
- **AT-R30** 게이트웨이(`gateway/http/attachments.ts`): `list` = `GET /deals/{code}/attachments`(서버 순서, 항목을 camelCase `Attachment`로 — 업로더의 `role`·퇴사 상태 유지, 빈 설명·0바이트 그대로), `upload` = multipart(`file`은 원래 이름과 함께, `description`은 가공 없이 — 빈 값도 빈 필드로, `on_exists`), 201 → `{outcome: 'uploaded', attachment}`, 200 `replaced` → `{outcome: 'replaced', attachment}`, 200 `skipped` → `{outcome: 'skipped'}`(attachment 없음), `uploaded`·`replaced`인데 attachment가 null이면 502 "서버 응답을 해석할 수 없습니다."(PL-R39), `remove` = `DELETE /attachments/{id}`(204 성공), `download` = blob + AT-R29 이름. 오류는 PL-R39로 바꾸며 `file-exists`·`storage-unavailable` kind와 서버 문구를 유지한다.
- **AT-R31** Fake 게이트웨이(`test/fake/gateway/attachments.ts`)는 서버와 같은 순서·규칙으로 답한다: user 403(없는 id·없는 Deal이어도 먼저) → 없는 Deal 404 → `validateUpload` 위반 422 → 저장소 장애 시뮬레이션 503(업로드 문구) → 같은 이름(NFC 비교·대소문자 구분) `ask` 409 / `skip` 변화 없음 / `replace` 권한 403. 설명은 앞뒤 공백을 지워 저장하고 이름은 NFC로 저장하며, 업로드·교체·삭제는 이력과 Deal `updatedAt`을 남긴다. 삭제는 없는 id 404가 권한 403보다 먼저다. 목록은 최신 업로드 순·같으면 id 내림차순이다.

### 2.4 상태와 전이

첨부에는 상태 값이 없다. 같은 이름이 있을 때의 처리:

| `on_exists` \ 같은 이름 | 없음 | 있음(권한 있음) | 있음(교체 권한 없음) |
| --- | --- | --- | --- |
| `ask`(기본) | 201 uploaded | 409 file-exists | 409 file-exists |
| `skip` | 201 uploaded | 200 skipped(변화 없음) | 200 skipped(변화 없음) |
| `replace` | 201 uploaded | 200 replaced(같은 id) | 403 forbidden |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| 목록·단건·다운로드 | 401 | 가능 | 가능 | 가능 |
| 업로드(새 파일, `ask`, `skip`) | 401 | 403(PL-R6) | 가능 | 가능 |
| 업로드 `replace` | 401 | 403(PL-R6) | 본인 파일·퇴사 sales 파일 | 모든 파일 |
| 삭제 | 401 | 403(PL-R6) | 본인 파일·퇴사 sales 파일 | 모든 파일 |

Owner 여부는 보지 않는다(남의 Deal에도 올릴 수 있다). 업로드·삭제는 CSRF 헤더가 필요하다(PL-R9).

### 2.6 API 계약

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| GET `/deals/{code}/attachments` | — | 200 `{items: AttachmentResponse[]}` | 401, 404 |
| POST `/deals/{code}/attachments` | multipart `file`(binary), `description`(기본 ''), `on_exists`(`ask`·`replace`·`skip`, 기본 `ask`) | 201 `AttachmentUploadResponse`(uploaded) + `Location: /api/v1/attachments/<id>` / 200(replaced·skipped) | 401, 403, 404, 409 `file-exists`, 422 `invalid-value`·`request-validation`, 503 `storage-unavailable` |
| GET `/attachments/{attachment_id}` | — | 200 `AttachmentResponse` | 401, 404, 422(id) |
| GET `/attachments/{attachment_id}/download` | — | 200 `application/octet-stream`(binary, `Content-Length`, `Content-Disposition`) | 401, 404, 422(id), 503 |
| DELETE `/attachments/{attachment_id}` | — | 204(본문 없음) | 401, 403, 404, 422(id) |

- `AttachmentResponse`: `id`(정수), `deal_code`, `file_name`(NFC), `description`, `size`(바이트), `mime`, `uploaded_by`(UserRef `id`·`name`·`resigned`·`label`·`role`), `uploaded_at`(ServerDateTime, TM). 필드는 정확히 이 여덟이다.
- `AttachmentUploadResponse`: `outcome` ∈ {`uploaded`, `replaced`, `skipped`}, `attachment`(`AttachmentResponse` | null — `skipped`만 null). 201·200이 같은 스키마다.
- openapi: 업로드는 multipart 폼(binary `file`), `on_exists`는 닫힌 enum, 다운로드는 binary octet-stream, 삭제는 본문 없음. id 경로 파라미터는 PL-R22.

### 2.7 화면 동작

AT-R23~AT-R30. 탭 위치는 DD-R27, 삭제 대화상자의 첨부 건수는 DD-R39, 서버 문구 표시는 PL-R37.

### 2.8 오류와 메시지

| 상황 | 상태·type | detail |
| --- | --- | --- |
| 없는 Deal·형식이 틀린 code(목록·업로드) | 404 `not-found` | Deal을 찾을 수 없습니다. |
| 없는 첨부(단건·다운로드·삭제) | 404 `not-found` | 첨부 파일을 찾을 수 없습니다. |
| 행은 있는데 디스크 파일 없음 | 404 `not-found` | 첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요. |
| 업로드: 저장 위치 없음·쓸 수 없음 | 503 `storage-unavailable` | 파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요. |
| 다운로드: 저장 위치 없음·읽을 수 없음 | 503 `storage-unavailable` | 파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요. |
| 같은 이름(`ask`) | 409 `file-exists` | 같은 이름의 파일이 이미 있습니다: <이름> |
| 남의 파일 교체 | 403 `forbidden` | 본인이 올린 파일만 교체할 수 있습니다. |
| 남의 파일 삭제 | 403 `forbidden` | 본인이 올린 파일만 삭제할 수 있습니다. |
| user의 업로드·삭제 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |
| 파일 없음 / 설명 100자 초과 / 100MB 초과 / 차단 확장자 / 이름 | 422 `invalid-value` | LC-R21 문구 그대로("업로드할 파일을 선택하세요." / "설명은 100자 이내로 입력하세요." / "파일 크기가 100MB를 초과합니다. (최대 100MB)" / "실행·설치 파일(.<ext>)은 업로드할 수 없습니다." / "사용할 수 없는 파일 이름입니다.") |
| 설명 NUL | 422 `invalid-value` | 설명에는 NUL 문자를 쓸 수 없습니다 |
| `on_exists` 값·multipart 아님·id 형식 | 422 `request-validation` | 요청 형식이 올바르지 않습니다 |

화면 문구: AT-R23~AT-R29.

## 3. Business use case

### AT-UC1 첨부 목록 보기
- 행위자: 로그인한 모든 역할
- 사전 조건: Deal 상세의 "Deal 상세" 탭
- 기본 흐름: 패널이 `GET /deals/{code}/attachments`를 읽어 최신 업로드 순으로 보인다(AT-R15, AT-R23)
- 대안: 첨부가 없으면 "첨부된 파일이 없습니다."
- 예외: 없는 Deal 404, 목록 오류 배너
- 결과: 파일명·설명·크기·업로더·시각이 보이고, 쓰기 권한이면 업로드 폼·관리 열이 함께 보인다(AT-R24)

### AT-UC2 파일 올리기
- 행위자: sales·admin
- 사전 조건: 저장 위치 설정(IN-R22), Deal 존재
- 기본 흐름: 파일·설명 입력 → 화면 검증(AT-R25) → `POST`(ask) → 검증(AT-R3·R4) → 저장(AT-R6) → 행·이력·Deal 시각(AT-R9) → 201 → 알림·목록 갱신(AT-R26)
- 대안: 같은 이름이면 AT-UC3
- 예외: 규칙 위반 422(화면은 요청 없이 문구), 저장 위치 없음·쓸 수 없음 503, 없는 Deal 404, user 403, 커밋 실패 시 새 파일 정리(AT-R14)
- 결과: 첨부 1건과 디스크 파일, 이력 "업로드 <이름>"

### AT-UC3 같은 이름 파일 처리
- 행위자: sales·admin
- 사전 조건: 같은 Deal에 같은 이름의 첨부가 있음
- 기본 흐름: `ask` 409 → 화면이 "같은 이름의 파일" 확인 → "교체" → `replace` → 200 replaced(같은 id, 이력 "교체 <이름>")(AT-R12, AT-R27)
- 대안: "건너뛰기"는 요청 없이 닫힘(화면), API `skip`은 200 skipped(변화 없음)
- 예외: 교체 권한 없음 403(화면은 "교체" 비활성), 교체 커밋 실패 시 이전 파일 유지(AT-R14)
- 결과: 내용·설명·업로더·업로드 시각이 바뀐 같은 첨부, 이전 파일 삭제

### AT-UC4 내려받기와 단건 조회
- 행위자: 로그인한 모든 역할
- 사전 조건: 첨부 행 존재
- 기본 흐름: 파일명 클릭 → `GET /attachments/{id}/download` → 저장한 바이트 그대로 octet-stream·원래 이름으로 저장(AT-R17, AT-R29). API 사용자는 `GET /attachments/{id}`로 메타데이터를 읽는다(AT-R16)
- 예외: 없는 첨부 404, 디스크 파일 없음 404(내용 없음), 저장 위치 없음·읽을 수 없음 503(AT-R18)
- 결과: 원래 이름과 내용의 파일

### AT-UC5 첨부 삭제
- 행위자: admin, sales(본인·퇴사 sales 파일)
- 사전 조건: 첨부 존재
- 기본 흐름: "삭제" → 확인 → `DELETE` → 204, 행·이력·Deal 시각, 커밋 뒤 디스크 파일 삭제(AT-R19, AT-R28)
- 대안: 확인 대화상자 취소
- 예외: user 403, 없는 첨부 404, 남의 파일 403, 디스크 삭제 실패·저장 위치 없음은 행만 지우고 204(AT-R20)
- 결과: 첨부가 목록·삭제 영향 건수에서 빠지고(AT-R21) 이력 "삭제 <이름>"

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| AT-001 | sales가 설명과 함께 새 파일을 올리면 201이고 키 이름으로 그대로 저장된다 | AT-R6, AT-R7, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_a_new_file_is_stored_byte_for_byte_and_recorded`<br>`application/test_upload_attachment_new.py::test_the_disk_file_is_named_by_a_random_key_not_by_the_original_name`<br>`application/test_upload_attachment_new.py::test_every_upload_gets_its_own_key`<br>외 4건 |
| AT-002 | admin도 올릴 수 있고 설명·on_exists를 생략하면 빈 설명·ask다 | AT-R5, AT-R4, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_the_description_defaults_to_empty`<br>`application/test_upload_attachment_same_name.py::test_ask_is_the_default_when_the_choice_is_not_made`<br>`domain/test_attachment_values.py::test_parse_description_of_blank_text_is_empty`<br>외 1건 |
| AT-003 | 업로드는 이력 "업로드 <이름>" 1건을 남기고 Deal 수정 시각을 바꾼다 | AT-R9, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_one_history_entry_records_the_upload`<br>`application/test_upload_attachment_new.py::test_the_deal_modification_time_becomes_the_upload_time`<br>`application/test_upload_attachment_new.py::test_the_upload_is_committed`<br>외 2건 |
| AT-004 | 크기는 실제 저장 바이트, mime은 요청 값(없거나 255자 초과면 octet-stream), 시각은 서버 시각이다 | AT-R6, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_the_upload_time_is_the_server_time_of_the_request`<br>`application/test_upload_attachment_new.py::test_the_size_is_the_number_of_bytes_actually_stored`<br>`application/test_upload_attachment_new.py::test_the_size_is_known_even_when_the_request_did_not_declare_one`<br>외 1건 |
| AT-005 | 경계값 파일(확장자 없음·이중 확장자·0바이트·설명 100자·이름 255자·정확히 100MB)은 올라간다 | AT-R3, AT-R4, AT-R6, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_an_empty_file_is_accepted`<br>`application/test_upload_attachment_new.py::test_ordinary_names_are_accepted`<br>`application/test_upload_attachment_storage.py::test_a_stream_of_exactly_the_limit_is_stored`<br>외 5건 |
| AT-006 | 규칙 위반 업로드는 422 문구이고 행·이력·파일이 남지 않는다 | AT-R3, AT-UC2 | backend | `application/test_upload_attachment_validation.py::test_an_invalid_upload_is_rejected_and_leaves_nothing_behind`<br>`domain/test_attachment_upload_candidate.py::test_one_byte_over_the_limit_is_rejected`<br>`domain/test_attachment_upload_candidate.py::test_the_description_is_trimmed_before_it_is_measured`<br>외 4건 |
| AT-007 | 설명에 NUL이 있으면 422다 | AT-R4, AT-UC2 | backend | `application/test_upload_attachment_validation.py::test_a_nul_in_the_description_is_rejected`<br>`domain/test_attachment_upload_candidate.py::test_a_nul_in_the_description_is_rejected`<br>`domain/test_attachment_values.py::test_parse_description_rejects_nul_even_when_otherwise_valid` |
| AT-008 | 여러 규칙을 어기면 정해진 순서의 첫 위반만 보인다 | AT-R3, AT-UC2 | backend | `application/test_upload_attachment_validation.py::test_the_first_violation_wins_in_the_documented_order`<br>`domain/test_attachment_upload_candidate.py::test_a_missing_file_is_reported_before_everything_else`<br>`domain/test_attachment_upload_candidate.py::test_a_too_long_description_is_reported_before_the_size`<br>외 3건 |
| AT-009 | 차단 확장자는 끝 공백·점을 걷은 마지막 확장자로 대소문자 없이 판정하고 문구는 소문자다 | AT-R3, AT-UC2 | backend | `domain/test_attachment_file_name.py::test_extension_is_the_lowercase_last_one`<br>`domain/test_attachment_file_name.py::test_parse_rejects_an_executable_name_disguised_by_a_trailing_format_character`<br>`domain/test_attachment_upload_candidate.py::test_every_blocked_extension_is_rejected_whatever_its_case`<br>외 9건 |
| AT-010 | 쓸 수 없는 파일 이름은 422이고 이름은 NFC로 저장된다 | AT-R2, AT-R3, AT-UC2 | backend | `domain/test_attachment_errors_history.py::test_history_text_uses_the_normalized_file_name`<br>`domain/test_attachment_file_name.py::test_parse_rejects_names_that_cannot_be_used`<br>`domain/test_attachment_file_name.py::test_parse_accepts_ordinary_names_unchanged`<br>외 9건 |
| AT-011 | 선언 크기와 무관하게 실제 내용이 100MB를 넘으면 422이고 파일이 남지 않는다 | AT-R6, AT-UC2 | backend | `application/test_upload_attachment_storage.py::test_a_stream_longer_than_the_limit_is_rejected_whatever_was_declared`<br>`web/test_attachment_upload_routes.py::test_a_file_over_100mb_is_422_before_anything_is_stored` |
| AT-012 | on_exists 값이 틀리거나 multipart가 아니면 422 request-validation이다 | AT-R5, AT-UC2 | backend | `domain/test_attachment_values.py::test_on_exists_has_the_three_wire_values`<br>`domain/test_attachment_values.py::test_on_exists_rejects_an_unknown_value`<br>`web/test_attachment_upload_routes.py::test_an_unknown_on_exists_value_is_a_request_validation_error`<br>외 1건 |
| AT-013 | 없는 Deal·형식이 틀린 code는 파일 검증·저장 위치보다 먼저 404다 | AT-R10, AT-UC2 | backend | `application/test_upload_attachment_validation.py::test_a_missing_or_malformed_deal_is_not_found_before_the_upload_is_validated`<br>`application/test_upload_attachment_validation.py::test_a_missing_deal_is_not_found_even_without_a_storage_location`<br>`web/test_attachment_upload_routes.py::test_a_missing_or_malformed_deal_is_404_before_the_file_is_checked`<br>`gateway/contract/attachments.contract.ts` |
| AT-014 | 저장 위치 설정이 없으면 503이고 검증 위반이 먼저다 | AT-R8, AT-R10, AT-UC2 | backend | `application/test_upload_attachment_validation.py::test_validation_comes_before_the_storage_location_check`<br>`application/test_upload_attachment_validation.py::test_a_valid_upload_without_a_storage_location_is_unavailable`<br>`web/test_attachment_upload_routes.py::test_without_a_storage_location_the_upload_is_503_storage_unavailable` |
| AT-015 | 저장 위치에 쓸 수 없으면 503이고 아무것도 남지 않는다 | AT-R8, AT-UC2 | backend | `application/test_upload_attachment_storage.py::test_a_storage_location_that_cannot_be_written_is_unavailable`<br>`web/test_attachment_upload_routes.py::test_a_storage_location_that_cannot_be_written_is_503_storage_unavailable` |
| AT-016 | user의 업로드는 없는 Deal이어도 403이고 미인증은 401이다 | AT-R11, AT-R10, AT-UC2 | backend | `web/test_attachment_upload_routes.py::test_a_read_only_user_is_403_even_for_a_missing_deal`<br>`web/test_attachment_upload_routes.py::test_an_anonymous_request_is_401`<br>`gateway/contract/attachments.contract.ts` |
| AT-017 | 같은 이름을 ask로 올리면 409 file-exists이고 아무것도 바뀌지 않는다 | AT-R12, AT-UC3 | backend | `application/test_upload_attachment_same_name.py::test_ask_conflicts_and_changes_nothing`<br>`domain/test_attachment_errors_history.py::test_name_taken_names_the_file_and_is_an_already_exists_error`<br>`web/test_attachment_upload_routes.py::test_the_same_name_with_ask_is_409_file_exists`<br>`gateway/contract/attachments.contract.ts` |
| AT-018 | 같은 이름을 skip으로 올리면 200 skipped이고 아무것도 바뀌지 않는다 | AT-R12, AT-UC3 | backend | `application/test_upload_attachment_same_name.py::test_skip_returns_no_attachment_and_changes_nothing`<br>`web/test_attachment_upload_routes.py::test_the_same_name_with_skip_is_200_skipped_without_an_attachment`<br>`gateway/contract/attachments.contract.ts` |
| AT-019 | 같은 이름을 replace로 올리면 같은 id의 내용이 바뀌고 이전 파일이 지워지며 이력 "교체"가 남는다 | AT-R12, AT-R9, AT-UC3 | backend | `application/test_upload_attachment_same_name.py::test_replace_keeps_the_id_and_swaps_content_description_and_time`<br>`application/test_upload_attachment_same_name.py::test_replace_writes_the_new_content_and_removes_the_old_disk_file`<br>`application/test_upload_attachment_same_name.py::test_replace_records_one_replace_entry_and_touches_the_deal`<br>외 3건 |
| AT-020 | 같은 이름이 없으면 replace·skip도 새 업로드 201이다 | AT-R12, AT-UC2 | backend | `application/test_upload_attachment_new.py::test_replace_and_skip_still_upload_when_no_file_has_that_name`, `gateway/contract/attachments.contract.ts` |
| AT-021 | 이름은 NFC로 비교하고 대소문자가 다르거나 다른 Deal이면 별개 파일이다 | AT-R2, AT-R12, AT-UC3 | backend | `application/test_upload_attachment_new.py::test_the_same_name_in_another_deal_is_a_separate_file`<br>`application/test_upload_attachment_new.py::test_names_that_differ_only_by_case_are_separate_files`<br>`application/test_upload_attachment_same_name.py::test_the_name_is_compared_after_nfc_normalization`<br>외 2건 |
| AT-022 | 업로더 본인·admin·퇴사 sales 파일의 다른 sales는 교체할 수 있고 업로더가 요청자로 바뀐다 | AT-R13, AT-UC3 | backend | `application/test_upload_attachment_same_name.py::test_an_admin_replacing_takes_over_as_the_uploader`<br>`application/test_upload_attachment_same_name.py::test_replace_is_allowed_for_the_uploader_an_admin_and_for_sales_of_a_resigned_sales_file`<br>`web/test_attachment_upload_routes.py::test_an_admin_can_replace_anyones_file`<br>`gateway/contract/attachments.contract.ts` |
| AT-023 | 다른 재직 sales의 교체는 403이고, 같은 사람의 ask는 409·skip은 200이다 | AT-R13, AT-UC3 | backend | `application/test_upload_attachment_same_name.py::test_replace_by_someone_who_may_not_delete_the_file_is_forbidden_and_changes_nothing`<br>`application/test_upload_attachment_same_name.py::test_ask_by_another_sales_is_a_conflict_not_a_permission_error`<br>`application/test_upload_attachment_same_name.py::test_skip_by_another_sales_is_allowed_whoever_owns_the_file`<br>외 1건 |
| AT-024 | 커밋 전 실패는 새 파일을 지우고(교체면 이전 파일 유지), 커밋 뒤 오류·이전 파일 삭제 실패는 성공 상태를 지킨다 | AT-R14, AT-UC2, AT-UC3 | backend | `application/test_upload_attachment_storage.py::test_a_failed_commit_removes_the_new_file_and_raises`<br>`application/test_upload_attachment_storage.py::test_a_failed_commit_of_a_replacement_keeps_the_old_file_and_removes_the_new_one`<br>`application/test_upload_attachment_storage.py::test_a_replacement_succeeds_even_when_the_old_file_cannot_be_removed`<br>외 2건 |
| AT-025 | 업로드 내용을 읽다가 끊기면 쓰던 파일이 남지 않는다 | AT-R14, AT-UC2 | backend | `application/test_upload_attachment_storage.py::test_a_connection_that_breaks_while_reading_leaves_nothing_behind`<br>`repositories/test_file_storage_failure_contract.py::test_a_source_that_fails_midway_surfaces_its_error_and_stores_nothing` |
| AT-026 | 모든 역할이 그 Deal의 첨부만 최신 업로드 순으로 본다 | AT-R15, AT-UC1 | backend | `application/test_list_and_get_attachments.py::test_the_list_is_newest_upload_first`<br>`application/test_list_and_get_attachments.py::test_uploads_at_the_same_time_are_ordered_by_id_descending`<br>`application/test_list_and_get_attachments.py::test_a_replaced_file_moves_to_the_top`<br>외 3건 |
| AT-027 | 첨부가 없는 Deal의 목록은 빈 items다 | AT-R15, AT-UC1 | backend | `application/test_list_and_get_attachments.py::test_a_deal_without_attachments_has_an_empty_list`<br>`web/test_attachment_read_routes.py::test_the_list_of_a_deal_without_files_is_empty` |
| AT-028 | 없는 Deal의 목록은 404, 미인증은 401이다 | AT-R15, AT-R11, AT-UC1 | backend | `application/test_list_and_get_attachments.py::test_listing_a_missing_or_malformed_deal_is_not_found`<br>`web/test_attachment_read_routes.py::test_the_list_of_a_missing_or_malformed_deal_is_404`<br>`web/test_attachment_read_routes.py::test_the_list_needs_a_login`<br>`gateway/contract/attachments.contract.ts` |
| AT-029 | 모든 역할이 id로 첨부 한 건을 읽고 없는 id는 404다 | AT-R16, AT-UC4 | backend | `application/test_list_and_get_attachments.py::test_get_returns_the_attachment`<br>`application/test_list_and_get_attachments.py::test_get_of_an_unknown_id_is_not_found`<br>`web/test_attachment_read_routes.py::test_one_attachment_is_readable_by_a_read_only_user`<br>외 1건 |
| AT-030 | 다운로드는 모든 역할에게 저장 바이트 그대로 octet-stream 첨부로 내려간다 | AT-R17, AT-UC4 | backend | `application/test_download_attachment.py::test_download_returns_the_metadata_and_the_stored_bytes`<br>`web/test_attachment_read_routes.py::test_download_streams_the_bytes_as_an_octet_stream_attachment`<br>`web/test_attachment_read_routes.py::test_download_never_serves_the_clients_content_type`<br>`gateway/contract/attachments.contract.ts` |
| AT-031 | Content-Disposition은 ASCII 대체 이름과 UTF-8 퍼센트 인코딩 이름을 함께 싣는다 | AT-R17, AT-UC4 | backend | `web/test_attachment_read_routes.py::test_download_keeps_a_korean_file_name_in_the_utf8_parameter`<br>`web/test_content_disposition.py::test_an_ascii_name_is_the_same_in_both_parameters`<br>`web/test_content_disposition.py::test_a_korean_name_gets_an_underscore_per_character_and_a_percent_encoded_utf8_name`<br>외 7건 |
| AT-032 | 0바이트 파일과 여러 청크로 흐르는 큰 파일도 그대로 내려간다 | AT-R17, AT-UC4 | backend | `application/test_download_attachment.py::test_download_of_an_empty_file_has_size_zero`<br>`infra/test_local_file_storage.py::test_open_streams_the_file_in_chunks_that_add_up_to_the_content`<br>`web/test_attachment_read_routes.py::test_download_of_an_empty_file_has_zero_length` |
| AT-033 | 없는 첨부의 다운로드는 404다 | AT-R18, AT-UC4 | backend | `application/test_download_attachment.py::test_download_of_an_unknown_id_is_not_found`, `gateway/contract/attachments.contract.ts` |
| AT-034 | 디스크 파일이 없거나 저장 위치가 바뀌었으면 404 내용 없음이고 목록은 그대로다 | AT-R18, AT-R1, AT-UC4 | backend | `application/test_download_attachment.py::test_a_row_without_its_disk_file_reports_the_content_as_missing`<br>`application/test_download_attachment.py::test_the_file_is_looked_up_under_the_current_storage_location`<br>`web/test_attachment_read_routes.py::test_download_of_a_row_whose_file_is_gone_is_404_with_the_content_sentence` |
| AT-035 | 저장 위치가 없거나 파일을 읽을 수 없으면 다운로드는 503이다 | AT-R18, AT-UC4 | backend | `application/test_download_attachment.py::test_without_a_storage_location_the_download_is_unavailable`<br>`application/test_download_attachment.py::test_a_file_that_exists_but_cannot_be_read_is_unavailable_not_missing`<br>`web/test_attachment_read_routes.py::test_download_without_a_storage_location_is_503`<br>외 1건 |
| AT-036 | 업로더가 지우면 204이고 행·그 파일만 사라지며 이력 "삭제"가 남는다 | AT-R19, AT-R9, AT-UC5 | backend | `application/test_delete_attachment.py::test_the_uploader_deletes_the_row_and_the_disk_file`<br>`application/test_delete_attachment.py::test_the_delete_is_recorded_in_the_deal_history_by_the_requester`<br>`application/test_delete_attachment.py::test_the_deal_modification_time_becomes_the_delete_time`<br>외 2건 |
| AT-037 | 삭제 권한: admin은 모두, sales는 본인·퇴사 sales 파일만, 다른 재직 sales·퇴사 admin 파일은 403이다 | AT-R13, AT-R19, AT-UC5 | backend | `application/test_delete_attachment.py::test_delete_is_allowed_for_the_uploader_admins_and_sales_of_a_resigned_sales_file`<br>`application/test_delete_attachment.py::test_delete_by_someone_without_the_right_is_forbidden_and_keeps_everything`<br>`domain/test_attachment_entity.py::test_delete_and_replace_share_one_permission_rule`<br>외 4건 |
| AT-038 | user의 삭제는 없는 id여도 403, sales·admin의 없는 id는 404, 미인증은 401이다 | AT-R19, AT-R11, AT-UC5 | backend | `application/test_delete_attachment.py::test_an_unknown_id_is_not_found_whoever_asks`<br>`application/test_delete_attachment.py::test_deleting_twice_is_not_found_the_second_time`<br>`web/test_attachment_read_routes.py::test_a_read_only_user_is_403_before_the_file_is_looked_up`<br>외 2건 |
| AT-039 | 디스크 삭제 실패·저장 위치 없음이어도 행은 지워지고, 커밋 실패면 행과 파일이 남는다 | AT-R20, AT-UC5 | backend | `application/test_delete_attachment.py::test_the_row_is_deleted_even_when_the_disk_file_cannot_be_removed`<br>`application/test_delete_attachment.py::test_the_row_is_deleted_when_no_storage_location_is_configured`<br>`application/test_delete_attachment.py::test_a_failed_commit_keeps_the_row_and_the_disk_file` |
| AT-040 | 삭제 영향의 첨부 수는 그 Deal의 현재 첨부 행 수다 | AT-R21, AT-UC5 | backend | `application/test_delete_deal_attachments.py::test_the_deletion_impact_counts_the_attachments_of_that_deal`<br>`application/test_delete_deal_attachments.py::test_the_impact_counts_a_replaced_file_once_and_drops_a_deleted_one`<br>`gateway/contract/attachments.contract.ts`<br>`repositories/test_attachment_deletion_impact_contract.py` |
| AT-041 | 화면: 첨부 목록은 파일명·설명·크기·업로더·시각을 보이고 퇴사 업로더는 "(퇴사)"다 | AT-R23, AT-UC1 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 첨부 목록은 파일명·설명·크기·업로더·시각을 보이고 파일명은 내려받기 버튼이다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 퇴사한 업로더는 "이름(퇴사)"로 보인다` |
| AT-042 | 화면: 첨부가 없으면 "첨부된 파일이 없습니다."다 | AT-R23, AT-UC1 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 첨부가 없는 Deal은 "첨부된 파일이 없습니다."를 보인다` |
| AT-043 | 화면: user는 내려받기만 하고 업로드 폼·삭제 버튼이 없다 | AT-R24, AT-UC1 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > user는 내려받기만 하고 업로드 폼과 삭제 버튼이 없다` |
| AT-044 | 화면: 규칙 위반 파일은 요청 없이 문구를 보이고 경계값은 통과한다 | AT-R25, AT-UC2 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 파일 없이 업로드하면 요청 없이 문구를 보인다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 100MB를 넘는 파일은 요청 없이 문구를 보이고 목록에 없다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 정확히 100MB 파일은 올라간다`<br>외 33건 |
| AT-045 | 화면: 설명 글자 수는 앞뒤 공백을 뺀 코드 포인트로 세고 100자를 넘으면 강조한다 | AT-R25, AT-UC2 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 설명이 100자를 넘으면 글자 수를 강조하고 업로드 때 문구를 보인다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 설명 정확히 100자는 강조 없이 올라간다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 설명은 앞뒤 공백을 뺀 글자 수로 세어 공백 사이 100자는 올라간다`<br>외 3건 |
| AT-046 | 화면: 올리면 목록 맨 위에 보이고 알림·History가 남으며 폼이 비워진다 | AT-R26, AT-UC2 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 올리면 목록에 보이고 알림이 뜨며 폼이 비워지고 History에 남는다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > NFD로 고른 파일은 NFC 이름으로 목록에 보인다` |
| AT-047 | 화면: 저장 위치 장애면 서버 문구를 보이고 목록은 그대로다 | AT-R26, AT-UC2 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 저장 위치 장애면 서버 문구를 보이고 목록은 그대로다` |
| AT-048 | 화면: 같은 이름이면 교체/건너뛰기를 묻고, 교체하면 바뀌고 건너뛰면 그대로다 | AT-R27, AT-UC3 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 같은 이름이면 묻고 "교체"를 누르면 설명이 바뀐다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > "건너뛰기"를 누르면 목록이 그대로다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 다른 sales의 파일이어도 "건너뛰기"는 권한 안내 없이 닫힌다` |
| AT-049 | 화면: 교체 권한이 없으면 "교체"가 비활성이고 안내가 보인다 | AT-R27, AT-R28, AT-UC3 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 재직 중인 다른 sales의 파일이면 "교체"는 비활성이고 안내가 보인다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 본인 파일이면 "교체"가 활성이고 안내가 없다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 퇴사한 sales의 파일이면 "교체"가 활성이고 안내가 없다`<br>외 3건 |
| AT-050 | 화면: 삭제 버튼은 권한이 있을 때만 활성이다 | AT-R28, AT-UC5 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > sales는 본인·퇴사 sales 파일은 지울 수 있고 다른 sales 파일은 지울 수 없다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > admin은 모든 파일을 지울 수 있다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 다른 sales는 자기 파일만 지울 수 있다`<br>외 1건 |
| AT-051 | 화면: 확인하면 삭제되고 History에 남으며 취소하면 그대로다 | AT-R28, AT-UC5 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 확인하면 삭제되고 History에 남는다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 삭제를 취소하면 파일이 그대로다` |
| AT-052 | 화면: 파일명을 누르면 내려받고 실패하면 서버 문구를 보인다 | AT-R29, AT-UC4 | frontend | `features/deals/detail/AttachmentsPanel.test.tsx > 파일명을 누르면 첨부 이름으로 파일 저장을 시작한다`<br>`features/deals/detail/AttachmentsPanel.test.tsx > 다운로드가 503으로 실패하면 서버 문구를 보이고 저장하지 않는다` |
| AT-053 | 게이트웨이: 업로드·삭제·다운로드 요청과 응답·오류를 계약대로 바꾼다 | AT-R30, AT-R29 | frontend | `gateway/http/attachments.test.ts > Deal 첨부 목록을 읽어 각 항목을 바꾼다`<br>`gateway/http/attachments.test.ts > 서버가 보낸 순서(최신 순)를 유지한다`<br>`gateway/http/attachments.test.ts > 첨부가 없으면 빈 목록을 돌려준다`<br>외 35건 |
| AT-054 | Fake 게이트웨이는 서버와 같은 순서·규칙으로 답한다 | AT-R31 | frontend | `test/fake/gateway/attachments.test.ts > 모든 역할이 조회하고 최신 업로드순이다`<br>`test/fake/gateway/attachments.test.ts > 다운로드는 파일명과 Blob을 돌려준다`<br>`test/fake/gateway/attachments.test.ts > user는 403`<br>외 32건 |

### AT-001 sales가 설명과 함께 새 파일을 올리면 201이고 키 이름으로 그대로 저장된다
- Given 저장 위치가 설정되어 있고 Deal D가 있다
- When sales KIM이 D에 "견적서.pdf"(바이너리 바이트, Content-Type `application/pdf`)를 설명 "  최종본  "으로 올린다
- Then 201 `outcome` `uploaded`, `Location: /api/v1/attachments/<id>`이고 첨부는 `deal_code` D, `file_name` "견적서.pdf", `description` "최종본", `size` = 바이트 수, `mime` `application/pdf`, 업로더 KIM이다. 디스크에는 `<저장 위치>/<D>/<32자 소문자 16진수 키>` 파일 하나가 올린 바이트 그대로 있고(원래 이름으로 된 파일은 없음), 업로드마다 키가 다르다. 목록에 "견적서.pdf"가 보인다

### AT-002 admin도 올릴 수 있고 설명·on_exists를 생략하면 빈 설명·ask다
- Given 저장 위치가 설정된 Deal D, 같은 이름 "a.pdf"가 이미 있다
- When admin이 설명·`on_exists` 없이 "memo.txt"를 올리고, 이어서 `on_exists` 없이 "a.pdf"를 올린다
- Then 첫 요청은 201이고 `description` ""이다. 둘째는 `ask`와 같은 409 `file-exists`다

### AT-003 업로드는 이력 "업로드 <이름>" 1건을 남기고 Deal 수정 시각을 바꾼다
- Given Deal D(수정 시각 T0), 요청 시각 T1
- When sales가 "a.pdf"를 올린다
- Then D의 History에 구분 `attachment`, 대상 "첨부 파일", 변경 전 "", 변경 후 "업로드 a.pdf", 변경자 요청자, 시각 T1인 항목이 정확히 1건 늘고 D의 `updated_at`은 T1이며 커밋되었다

### AT-004 크기는 실제 저장 바이트, mime은 요청 값(없거나 255자 초과면 octet-stream), 시각은 서버 시각이다
- Given 저장 위치가 설정된 Deal D
- When (a) 선언 크기와 다른 실제 바이트 (b) 선언 크기 없이 (c) Content-Type `text/plain` / 없음 / 256자로 각각 올린다
- Then `size`는 실제로 쓴 바이트 수, `mime`은 `text/plain` / `application/octet-stream` / `application/octet-stream`, `uploaded_at`·`created_at`·`updated_at`은 요청 시각(서버 시계)이다

### AT-005 경계값 파일(확장자 없음·이중 확장자·0바이트·설명 100자·이름 255자·정확히 100MB)은 올라간다
- Given 저장 위치가 설정된 Deal D
- When "README", "a.tar.gz", "exe.txt", "a.exe.txt", 0바이트 "empty.txt", 설명 "😀"×100, 이름 "n"×251+".pdf"(255자), 정확히 104,857,600바이트 파일을 각각 올린다
- Then 모두 201 `uploaded`이고 크기·내용이 그대로 저장된다

### AT-006 규칙 위반 업로드는 422 문구이고 행·이력·파일이 남지 않는다
- Given 저장 위치가 설정된 Deal D
- When 파일 파트 없이, 설명을 공백 포함 "😀"×101로, 104,857,601바이트로, "setup.exe"로, ".."로 각각 올린다
- Then 각각 422 `invalid-value` "업로드할 파일을 선택하세요." / "설명은 100자 이내로 입력하세요." / "파일 크기가 100MB를 초과합니다. (최대 100MB)" / "실행·설치 파일(.exe)은 업로드할 수 없습니다." / "사용할 수 없는 파일 이름입니다."이고 D의 첨부 행·첨부 이력·디스크 파일은 0건이다

### AT-007 설명에 NUL이 있으면 422다
- Given 저장 위치가 설정된 Deal D
- When 설명 "a\u0000b"로 올린다
- Then 422 `invalid-value` "설명에는 NUL 문자를 쓸 수 없습니다"이고 아무것도 남지 않는다

### AT-008 여러 규칙을 어기면 정해진 순서의 첫 위반만 보인다
- Given 저장 위치가 설정된 Deal D
- When (a) 설명 101자 + "a.exe" (b) 100MB 초과 + "a.exe" (c) 차단 확장자 + 쓸 수 없는 이름 ("setup​.exe" 아닌 "../x.exe"처럼 둘 다 어기는 이름)으로 올린다
- Then (a) 설명 문구 (b) 크기 문구 (c) 차단 확장자 문구다(순서: 파일 없음 → 설명 → 크기 → 차단 확장자 → 이름)

### AT-009 차단 확장자는 끝 공백·점을 걷은 마지막 확장자로 대소문자 없이 판정하고 문구는 소문자다
- Given 저장 위치가 설정된 Deal D
- When "SETUP.MSI", "run.Sh", "a.b.ps1", "x.appimage", "x.vbs", "setup.exe ", "setup.exe.", "setup.exe　"(끝 유니코드 공백), 24개 확장자 각각, 그리고 "a.txt ", ".exe"를 올린다
- Then 앞의 것은 422 "실행·설치 파일(.<소문자 확장자>)은 업로드할 수 없습니다."(예: `.msi`, `.sh`, `.exe`)이고, "a.txt "와 ".exe"(확장자 없음)는 차단 확장자로 거절되지 않는다

### AT-010 쓸 수 없는 파일 이름은 422이고 이름은 NFC로 저장된다
- Given 저장 위치가 설정된 Deal D
- When ".", "..", "n"×256, "a/b.pdf", "a\\b.pdf", 제어 문자("a\tb.pdf"), 방향 제어("견적‮gpj.pdf"), 제로폭("setup.exe​"), ZWJ 이모지 시퀀스가 든 이름, 그리고 NFD "한글.pdf", 앞뒤 공백이 있는 " a.pdf ", 오른쪽→왼쪽 글자·한글·이모지 이름을 올린다
- Then 앞의 것은 422 "사용할 수 없는 파일 이름입니다."이고 아무것도 남지 않는다. NFD 이름은 NFC "한글.pdf"로 저장·응답되고(255자 판정도 NFC 뒤), 앞뒤 공백 이름은 공백 그대로, 서식 문자 없는 그 밖의 이름은 201이다

### AT-011 선언 크기와 무관하게 실제 내용이 100MB를 넘으면 422이고 파일이 남지 않는다
- Given 저장 위치가 설정된 Deal D
- When 선언 크기는 작거나 없지만 실제 내용이 104,857,601바이트인 파일을 올린다
- Then 422 "파일 크기가 100MB를 초과합니다. (최대 100MB)"이고 행·이력·디스크 파일이 없다

### AT-012 on_exists 값이 틀리거나 multipart가 아니면 422 request-validation이다
- Given 저장 위치가 설정된 Deal D
- When `on_exists` "overwrite"로 올리고, JSON 본문으로 업로드 경로를 부른다
- Then 둘 다 422 `request-validation`(500 아님)이고 아무것도 남지 않는다

### AT-013 없는 Deal·형식이 틀린 code는 파일 검증·저장 위치보다 먼저 404다
- Given 저장 위치가 있는 경우와 없는 경우
- When sales가 "20991231-ZZZZ"·"not-a-code"에 파일 없이(또는 차단 확장자로) 올린다
- Then 모두 404 `not-found` "Deal을 찾을 수 없습니다."다

### AT-014 저장 위치 설정이 없으면 503이고 검증 위반이 먼저다
- Given 저장 위치 설정이 없는 Deal D
- When 올바른 "a.pdf"를 올리고, "setup.exe"를 올린다
- Then 첫 요청은 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."이고 행·이력·파일이 없다. 둘째는 422 차단 확장자 문구다

### AT-015 저장 위치에 쓸 수 없으면 503이고 아무것도 남지 않는다
- Given 저장 위치가 쓸 수 없는 경로(예: 일반 파일이 가로막음)인 Deal D
- When "a.pdf"를 올린다
- Then 503 `storage-unavailable` 업로드 문구이고 행·이력이 없다

### AT-016 user의 업로드는 없는 Deal이어도 403이고 미인증은 401이다
- Given 저장 위치가 설정된 Deal D
- When user가 D와 없는 Deal에 올리고, 로그인하지 않은 요청이 D에 올린다
- Then user는 둘 다 403 `forbidden` "이 작업을 할 권한이 없습니다(읽기 전용 계정)", 미인증은 401이고 D의 디스크·행은 비어 있다

### AT-017 같은 이름을 ask로 올리면 409 file-exists이고 아무것도 바뀌지 않는다
- Given D에 "a.pdf"(내용 "old")가 있다
- When "a.pdf"(내용 "new")를 `ask`로 올린다
- Then 409 `file-exists` "같은 이름의 파일이 이미 있습니다: a.pdf"이고 첨부·내용 "old"·이력("업로드 a.pdf" 1건)·Deal 수정 시각이 그대로이며 새 파일이 남지 않는다

### AT-018 같은 이름을 skip으로 올리면 200 skipped이고 아무것도 바뀌지 않는다
- Given D에 "a.pdf"(내용 "old")가 있다
- When "a.pdf"(내용 "new")를 `skip`으로 올린다
- Then 200 `{outcome: "skipped", attachment: null}`, `Location` 헤더 없음이고 첨부·내용·이력·Deal 수정 시각이 그대로이며 디스크에는 "old" 파일 하나뿐이다

### AT-019 같은 이름을 replace로 올리면 같은 id의 내용이 바뀌고 이전 파일이 지워지며 이력 "교체"가 남는다
- Given D에 "a.pdf"(내용 "old", 설명 "이전")가 있고 요청 시각은 T1이다
- When "a.pdf"(내용 "newer content", Content-Type `text/plain`, 설명 "새 설명")를 `replace`로 올린다
- Then 200 `replaced`이고 같은 id, `size` 13, `mime` `text/plain`, `description` "새 설명", `uploaded_at`·`updated_at` T1(`created_at`은 그대로)이다. 디스크에는 새 내용 파일 하나뿐(이전 파일 삭제), 행은 1건, 이력에 "교체 a.pdf" 1건이 더해지고 Deal 수정 시각이 T1이다

### AT-020 같은 이름이 없으면 replace·skip도 새 업로드 201이다
- Given 첨부가 없는 Deal D
- When "new.pdf"를 `replace`로, "new2.pdf"를 `skip`으로 올린다
- Then 둘 다 201 `uploaded`이고 파일이 저장된다

### AT-021 이름은 NFC로 비교하고 대소문자가 다르거나 다른 Deal이면 별개 파일이다
- Given D에 "Report.PDF"·"한글.pdf"(NFC), 다른 Deal E에 "a.pdf"가 있다
- When D에 "report.pdf", NFD "한글.pdf", "a.pdf"를 각각 `ask`로 올린다
- Then "report.pdf"는 201(D 목록 "report.pdf"·"한글.pdf"·"Report.PDF" 최신순), NFD "한글.pdf"는 409 `file-exists`, "a.pdf"는 201(E의 파일과 별개)이다

### AT-022 업로더 본인·admin·퇴사 sales 파일의 다른 sales는 교체할 수 있고 업로더가 요청자로 바뀐다
- Given D에 sales KIM이 올린 "a.pdf"
- When (a) KIM이 (b) admin이 (c) KIM을 퇴사 처리한 뒤 sales PARK이 "a.pdf"를 `replace`로 올린다
- Then 모두 200 `replaced`, 같은 id이고 내용이 새 것이며 `uploaded_by`는 요청자(admin이면 role `admin`, PARK이면 "사용자 park")다

### AT-023 다른 재직 sales의 교체는 403이고, 같은 사람의 ask는 409·skip은 200이다
- Given D에 재직 sales KIM이 올린 "a.pdf"(내용 "kim's")
- When sales PARK이 "a.pdf"를 `replace`, `ask`, `skip`으로 차례로 올린다
- Then `replace`는 403 `forbidden` "본인이 올린 파일만 교체할 수 있습니다.", `ask`는 409 `file-exists`, `skip`은 200 `skipped`이고 첨부·내용 "kim's"는 그대로다

### AT-024 커밋 전 실패는 새 파일을 지우고(교체면 이전 파일 유지), 커밋 뒤 오류·이전 파일 삭제 실패는 성공 상태를 지킨다
- Given 저장 위치가 설정된 Deal D(교체 경우는 "a.pdf" 내용 "old")
- When (a) 새 업로드의 커밋이 실패한다 (b) 교체의 커밋이 실패한다 (c) 교체에서 이전 파일 삭제가 실패한다 (d) 새 업로드·교체가 커밋된 뒤 오류가 난다
- Then (a) 오류가 그대로 나고 행·새 파일이 없다 (b) 오류이고 첨부는 "old"를 가리키며 이전 파일이 남고 새 파일은 없다 (c) 200 `replaced`이고 경고 로그가 남는다 (d) 커밋된 행이 가리키는 새 파일이 디스크에 남는다

### AT-025 업로드 내용을 읽다가 끊기면 쓰던 파일이 남지 않는다
- Given 저장 위치가 설정된 Deal D
- When 내용 스트림이 중간에 오류를 내는 업로드를 한다
- Then 오류로 끝나고 D의 행·이력·디스크 파일이 남지 않는다

### AT-026 모든 역할이 그 Deal의 첨부만 최신 업로드 순으로 본다
- Given D에 "first.pdf"(먼저)·"second.pdf"(나중)·같은 시각의 두 파일, 다른 Deal E에 "c.pdf"가 있다
- When admin·sales·user가 D의 목록을 읽고, "first.pdf"를 교체한 뒤 다시 읽는다
- Then 200이고 순서는 업로드 시각 내림차순(같으면 id 내림차순)이며 "c.pdf"는 없다. 항목 키는 정확히 `id`·`deal_code`·`file_name`·`description`·`size`·`mime`·`uploaded_by`·`uploaded_at`이고 id는 JSON 정수다. 교체 뒤에는 "first.pdf"가 맨 위다

### AT-027 첨부가 없는 Deal의 목록은 빈 items다
- Given 첨부가 없는 Deal D
- When 목록을 읽는다
- Then 200 `{"items": []}`다

### AT-028 없는 Deal의 목록은 404, 미인증은 401이다
- When "20991231-ZZZZ"·"not-a-code"의 목록을 읽고, 로그인하지 않고 D의 목록을 읽는다
- Then 404 `not-found` "Deal을 찾을 수 없습니다."와 401이다

### AT-029 모든 역할이 id로 첨부 한 건을 읽고 없는 id는 404다
- Given D에 "a.pdf"(5바이트, 설명 "설명")
- When user가 그 id로 단건을 읽고, 없는 id로 읽는다
- Then 첫 응답은 200이고 업로드 응답의 첨부와 같은 값이다. 둘째는 404 `not-found` "첨부 파일을 찾을 수 없습니다."다

### AT-030 다운로드는 모든 역할에게 저장 바이트 그대로 octet-stream 첨부로 내려간다
- Given D에 바이너리 "report.pdf"와 Content-Type `text/html`로 올린 "page.html"
- When admin·sales·user가 "report.pdf"를, admin이 "page.html"을 내려받는다
- Then 200이고 본문이 올린 바이트와 같으며 `Content-Type` `application/octet-stream`, `Content-Length` = 바이트 수, `Content-Disposition` `attachment; filename="report.pdf"; filename*=UTF-8''report.pdf`다. "page.html"도 octet-stream·attachment이고 단건 조회의 `mime`은 `text/html` 그대로다

### AT-031 Content-Disposition은 ASCII 대체 이름과 UTF-8 퍼센트 인코딩 이름을 함께 싣는다
- Given 이름 "견적서 최종.pdf", `"`·`\`·`%`·`;`·`/`·이모지·줄바꿈 후보가 든 이름
- When 다운로드 헤더를 만든다
- Then "견적서 최종.pdf"는 `filename="___ __.pdf"`(비ASCII 글자마다 `_`)와 `filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C%20%EC%B5%9C%EC%A2%85.pdf`이다. 대체 이름에는 `"`·`\`·`%`가 없고(각각 `_`), `filename*`를 UTF-8로 풀면 원래 이름이며, 헤더에 줄바꿈이 없다

### AT-032 0바이트 파일과 여러 청크로 흐르는 큰 파일도 그대로 내려간다
- Given D에 0바이트 "empty.txt"와 3MiB "big.bin"
- When 둘을 내려받는다
- Then "empty.txt"는 200·빈 본문·`Content-Length` 0, "big.bin"은 바이트·길이가 그대로다

### AT-033 없는 첨부의 다운로드는 404다
- When 없는 id를 내려받는다
- Then 404 `not-found` "첨부 파일을 찾을 수 없습니다."다

### AT-034 디스크 파일이 없거나 저장 위치가 바뀌었으면 404 내용 없음이고 목록은 그대로다
- Given D에 "a.pdf"가 있다
- When (a) 디스크 파일을 지운 뒤 (b) 저장 위치를 파일이 없는 다른 경로로 바꾼 뒤 내려받는다
- Then 둘 다 404 `not-found` "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."이고 목록·단건에는 "a.pdf"가 그대로 보인다

### AT-035 저장 위치가 없거나 파일을 읽을 수 없으면 다운로드는 503이다
- Given D에 "a.pdf"가 있다
- When (a) 저장 위치 설정을 없앤 뒤 (b) 파일은 있으나 읽을 수 없게 한 뒤 내려받는다
- Then 둘 다 503 `storage-unavailable` "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."이고(읽을 수 없음은 404가 아님) (a)에서도 목록은 읽힌다

### AT-036 업로더가 지우면 204이고 행·그 파일만 사라지며 이력 "삭제"가 남는다
- Given D에 KIM이 올린 "gone.pdf"와 "kept.pdf", 요청 시각 T1
- When KIM이 "gone.pdf"를 지운다
- Then 204·빈 본문이고 그 단건 조회는 404, 목록은 "kept.pdf"뿐, 디스크에는 "kept.pdf" 내용만 남는다(Deal 폴더 유지). 이력에 변경자 KIM의 "삭제 gone.pdf"가 더해지고 D의 수정 시각이 T1이다

### AT-037 삭제 권한: admin은 모두, sales는 본인·퇴사 sales 파일만, 다른 재직 sales·퇴사 admin 파일은 403이다
- Given D에 재직 sales KIM의 파일 F1, 퇴사한 sales의 파일 F2, 퇴사한 admin의 파일 F3
- When sales PARK이 F1·F2·F3을, admin이 F1을 지운다
- Then PARK의 F1·F3은 403 `forbidden` "본인이 올린 파일만 삭제할 수 있습니다."이고 행·파일·이력이 그대로다. PARK의 F2와 admin의 F1은 204다

### AT-038 user의 삭제는 없는 id여도 403, sales·admin의 없는 id는 404, 미인증은 401이다
- Given D에 "a.pdf"
- When user가 그 id와 없는 id를, sales·admin이 없는 id와 이미 지운 id를, 로그인하지 않은 요청이 그 id를 지운다
- Then user는 둘 다 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"(파일 그대로), sales·admin은 404 "첨부 파일을 찾을 수 없습니다.", 미인증은 401이다

### AT-039 디스크 삭제 실패·저장 위치 없음이어도 행은 지워지고, 커밋 실패면 행과 파일이 남는다
- Given D에 "a.pdf"
- When (a) 디스크 파일 삭제가 실패하는 저장소에서 (b) 저장 위치 설정이 없을 때 (c) 커밋이 실패할 때 지운다
- Then (a) 204, 행 없음, 이력 "삭제 a.pdf", 경고 로그 (b) 204, 행 없음, 디스크 파일은 그대로 (c) 오류이고 행과 디스크 파일이 그대로다

### AT-040 삭제 영향의 첨부 수는 그 Deal의 현재 첨부 행 수다
- Given D에 "a.pdf"·"b.pdf", 다른 Deal E에 "c.pdf", 첨부 없는 Deal F
- When D의 "a.pdf"를 교체하고 "b.pdf"를 지운 뒤 D·E·F의 삭제 영향을 읽는다(교체·삭제 전에도 한 번)
- Then 전에는 D 2·E 1·F 0이고, 뒤에는 D 1(교체는 1건, 지운 파일 제외)·E 1·F 0이다

### AT-041 화면: 첨부 목록은 파일명·설명·크기·업로더·시각을 보이고 퇴사 업로더는 "(퇴사)"다
- Given sales로 연 Deal(Fake 첨부 3개, 하나는 퇴사자가 올림)의 Deal 상세 탭
- When 첨부 패널을 본다
- Then 머리글은 파일명·설명·크기·업로드한 사용자·업로드 시각·관리이고, 파일명은 버튼, 크기는 "2.3 MB" 같은 표기, 퇴사 업로더는 "강퇴사(퇴사)", 행은 머리글 포함 4개다

### AT-042 화면: 첨부가 없으면 "첨부된 파일이 없습니다."다
- Given 첨부가 없는 Deal
- When 상세를 연다
- Then 첨부 패널에 "첨부된 파일이 없습니다."가 보인다

### AT-043 화면: user는 내려받기만 하고 업로드 폼·삭제 버튼이 없다
- Given user로 연 첨부가 있는 Deal
- When 첨부 패널을 본다
- Then 파일명 버튼은 보이고 "파일" 칸·"업로드" 버튼·"… 삭제" 버튼은 없다

### AT-044 화면: 규칙 위반 파일은 요청 없이 문구를 보이고 경계값은 통과한다
- Given sales로 연 Deal의 업로드 폼
- When 파일 없이, 설명 101자로, 100MB 초과 파일로, "setup.exe "·"tool.vbs"로, "견적‮gpj.pdf"·"a\tb.pdf"·이모지 256개 이름으로 업로드를 누르고, 정확히 100MB 파일·"backup.tar.gz"를 올린다
- Then 위반은 폼 아래 role=alert에 LC-R21 문구("업로드할 파일을 선택하세요." 등, 확장자는 소문자)가 보이고 목록에 새 파일이 없다. 경계값은 목록에 나타난다

### AT-045 화면: 설명 글자 수는 앞뒤 공백을 뺀 코드 포인트로 세고 100자를 넘으면 강조한다
- Given sales로 연 Deal의 업로드 폼
- When 설명에 "가"×100을, 앞뒤 공백 두 칸씩 붙인 "가"×100을, 101자를 넣는다
- Then 앞의 둘은 "100/100"(강조 없음)이고 올리면 설명 "가"×100으로 목록에 보인다. 101자는 "101/100"이 강조되고 업로드를 누르면 "설명은 100자 이내로 입력하세요."다

### AT-046 화면: 올리면 목록 맨 위에 보이고 알림·History가 남으며 폼이 비워진다
- Given sales로 연 Deal(첨부 없음)
- When "제안서.pdf"를 설명 "제안서 초안"으로 올리고, NFD "한글.pdf"를 올린다
- Then "제안서.pdf"가 목록에 보이고 "업로드되었습니다: 제안서.pdf" 알림, 설명 칸이 비워지며 Deal History 탭에 "업로드 제안서.pdf"가 보인다. NFD 파일은 NFC 이름 버튼으로 보인다

### AT-047 화면: 저장 위치 장애면 서버 문구를 보이고 목록은 그대로다
- Given 저장소 장애 시뮬레이션이 켜진 Deal
- When "제안서.pdf"를 올린다
- Then role=alert에 "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."가 보이고 목록에 "제안서.pdf"가 없다

### AT-048 화면: 같은 이름이면 교체/건너뛰기를 묻고, 교체하면 바뀌고 건너뛰면 그대로다
- Given 본인이 올린 "견적서_한빛은행_v2.pdf"와 다른 sales가 올린 "제안서_ITDR.pptx"가 있는 Deal
- When 같은 이름 "견적서_한빛은행_v2.pdf"를 설명 "교체본"으로 올려 대화상자에서 "교체"를 누르고, "제안서_ITDR.pptx"를 올려 "건너뛰기"를 누른다
- Then 대화상자 제목은 "같은 이름의 파일", 문구는 "같은 이름의 파일이 이미 있습니다: <이름>"이다. 교체 뒤 대화상자가 닫히고 그 행 설명이 "교체본", 행 수 그대로, "교체되었습니다: 견적서_한빛은행_v2.pdf"다. 건너뛰기 뒤 대화상자가 닫히고 그 행 설명·행 수가 그대로이며 권한 문구·오류 알림이 없다

### AT-049 화면: 교체 권한이 없으면 "교체"가 비활성이고 안내가 보인다
- Given 본인 파일, 다른 재직 sales 파일, 퇴사 sales 파일이 있는 Deal
- When sales로 각 이름을 다시 올리고, admin으로 다른 sales 파일 이름을 다시 올린다
- Then 다른 재직 sales 파일만 "교체" 비활성 + "본인이 올린 파일만 교체할 수 있습니다."(건너뛰기는 활성)이고, 본인·퇴사 sales 파일(sales)과 다른 sales 파일(admin)은 "교체"가 활성이며 안내가 없다. 퇴사 sales 파일을 교체하면 설명이 바뀌고 업로더가 요청자("김영업")가 된다

### AT-050 화면: 삭제 버튼은 권한이 있을 때만 활성이다
- Given 본인 파일, 퇴사 sales 파일, 다른 재직 sales 파일이 있는 Deal
- When sales KIM, sales PARK, admin으로 각각 연다
- Then KIM은 본인·퇴사 sales 파일 "삭제"가 활성, 다른 sales 파일은 비활성이고 title "본인이 올린 파일만 삭제할 수 있습니다."다. PARK은 자기 파일만 활성이고, admin은 모두 활성이다

### AT-051 화면: 확인하면 삭제되고 History에 남으며 취소하면 그대로다
- Given 삭제할 수 있는 "기술검토.xlsx"
- When "기술검토.xlsx 삭제"를 눌러 확인 대화상자에서 "삭제"를 누르고, 다른 경우에는 "취소"를 누른다
- Then 대화상자 제목은 "첨부 파일 삭제", 문구에 파일 이름이 있다. 삭제하면 목록에서 사라지고 Deal History 탭에 "삭제 기술검토.xlsx"가 보인다. 취소하면 파일이 그대로 보인다

### AT-052 화면: 파일명을 누르면 내려받고 실패하면 서버 문구를 보인다
- Given 첨부 "a.pdf"가 있는 Deal(user 포함 모든 역할)
- When 파일명 "a.pdf"를 누르고, 다운로드가 503으로 실패하는 경우에도 누른다
- Then 성공이면 "a.pdf" 이름·내용으로 파일 저장을 시작한다. 실패면 패널에 서버 문구("파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.") 오류 배너가 보인다

### AT-053 게이트웨이: 업로드·삭제·다운로드 요청과 응답·오류를 계약대로 바꾼다
- Given HTTP 게이트웨이와 가짜 서버 응답
- When list·upload·remove·download를 부른다
- Then list는 서버 순서대로 camelCase로 바꾸고(업로더 role·퇴사 유지, 빈 설명·0바이트 그대로) 404·네트워크 오류는 서버 문구·"서버에 연결할 수 없습니다."다. upload는 multipart에 파일 바이트·원래 이름·가공 없는 설명(빈 값도 필드로)·`on_exists`를 싣고 201→uploaded, 200 replaced→replaced, 200 skipped→attachment 없는 skipped, `file-exists`·`storage-unavailable` kind와 문구를 유지한다. remove는 204에 값 없이 끝난다. download는 blob과 `filename*` 우선(없으면 `filename`, 둘 다 없으면 "download", 경로 탐색 이름은 막음) 이름을 준다

### AT-054 Fake 게이트웨이는 서버와 같은 순서·규칙으로 답한다
- Given Fake 저장소(테스트 seed)
- When user·sales·admin으로 목록·업로드(위반·경계값·같은 이름·NFD·저장소 장애)·삭제(권한·없는 id)·다운로드를 부른다
- Then 목록은 최신순, 위반은 422 문구, user는 무엇보다 먼저 403, 없는 Deal 404 → 규칙 422 → 저장소 장애 503 → 같은 이름 순서이며, NFC 저장·비교, 대소문자 구분, 교체 권한(본인·퇴사 sales·admin), ask 409·skip 변화 없음, 설명 trim, 업로드·교체·삭제의 이력·Deal 갱신 시각, 삭제의 404가 권한 403보다 먼저인 점이 서버와 같다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 초안 작성(구현된 동작 문서화, AT-R1~R31, AT-UC1~UC5) | AT-001~AT-054 신규 |
| 2026-11-10 | 사용자 결정 반영(추천대로): E2 업로드 `Location`·단건 조회·이름 표기 현행 유지(AT-R7·R16·R26), E3 "건너뛰기"는 요청 없이 닫힘(AT-R27), E4 설명 NUL을 LC-R21에 보충(LC-085, AT-R4가 가리킴), E5 파일 이름·확장자·권한·다운로드 규칙은 LC 소유(AT-R17·R18이 LC-R24를 가리킴)와 TM-R8·IN-R22 번호 참조 | 없음(케이스 기대 결과 변경 없음) |
