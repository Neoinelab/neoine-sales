# Action 등록·수정·삭제   (feature 코드: AC, 상태: 확정(2026-11-17 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드(`backend/src/app/domain/deal_action/{entities,value_objects,history,policy,errors}.py`, `app/domain/deal/sync_sequence.py`, `app/application/deal_action/{register_deal_action,update_deal_action,delete_deal_action,list_deal_actions,get_deal_action,type_choice,inputs}.py`, `app/application/deal/sync_change.py`, `app/web/routers/deal_actions.py`, `app/web/schemas/deal_action.py`, `app/infra/db/{models,deal_action_repository,deal_action_order}.py`, `frontend/src/features/deals/detail/{ActionsTab,ActionForm,ActionTable,ActionTypeInput,ActionSyncFields,PreviousUpdate,useActionSync,syncDraft}.tsx|ts`, `shared/model/{nextActionBasis,permissions}.ts`, `gateway/http/{actions,mappers/action}.ts`, `test/fake/gateway/actions.ts`)이며 문구·type·상태 코드는 코드에서 그대로 옮겼습니다. 코드와 화면·테스트·Fake가 어긋나던 점은 2026-11-10 사용자 결정으로 정리했습니다: 화면이 쓰지 않는 서버 동작과 화면 표시는 현행대로 문서화하고(AC-R6 단건 `status_change`, AC-R31 삭제 실패 표시), Fake 게이트웨이는 서버 동작에 맞춥니다(AC-R33). 결정 목록은 계획(`artifacts/10-analysis/ac-plan.md`)에 있습니다.
>
> 2026-11-13 변경(확정·구현 완료): Action **수정 때 수행일도 고칠 수 있게** 했습니다(사용자 요청 "Deal action 수정시 수행일자도 수정 가능하도록 해줘"). 신설 AC-R45~R47·AC-UC6, 변경 AC-R11·R13~R15·R24·R30·R32·R33·R38~R40과 2.6. 결정 7건(Q1~Q7)은 2026-11-13 사용자가 권고안대로 확인했습니다. 화면 입력 타입 `ActionUpdateInput.actedOn`은 `string | null`(null·빈 값은 보내지 않음)입니다.
>
> 2026-11-16 변경(확정, 2026-11-16 사용자 확인): Actions 탭 개편(사용자 요청 "Actions 탭에서 보여주는 항목중에 등록시점의 담당자/Status/Forecast/Memo/삭제 항목은 제거해주고, 진행사항과 Next Action의 폭을 더 넓혀주도록 한다. 특정 action을 클릭하였을때 팝업으로 전체내용(앞에서 제거된 항목 포함)을 보여주고, Deal 상세처럼 inline으로 수정되도록 한다. 삭제 버튼은 해당 팝업으로 이동하며, 삭제시 삭제 컨펌을 받도록 한다."). 표에서 담당자·등록 시점 Status·Forecast·Memo·관리(수정·삭제) 열을 빼고 진행사항·Next Action 칸을 넓힌다(AC-R21·R22·R53). 행을 누르면 Action 상세 팝업이 모든 항목을 보이고(AC-R48·R49) 칸별 인라인 수정(AC-R50·R51)과 확인 뒤 삭제(AC-R52, AC-R31)를 한다. "Action 수정" 팝업은 폐지한다(AC-R30). 백엔드·API·마이그레이션 변경은 없다. 확인 질문 Q1~Q8은 2026-11-16 사용자가 확정했습니다(Q1~Q3·Q5·Q6·Q8 권고안대로, Q4·Q7은 사용자 변경: 상세 팝업에서도 Next Action 상태를 바꾼다 AC-R54, 진행사항·Next Action 칸은 한글 약 40자 폭 `min-width: 40em` AC-R53). 기록은 `artifacts/10-analysis/01-plan.md`.

## 1. 개요

- 목적: 영업이 Deal에서 한 일(진행사항)과 다음 계획(Next Action·Due Date)을 Action으로 남기고, 필요하면 같은 저장에서 Status·Forecast를 바꾸고 이전 Next Action을 끝냈다고 표시한다. 남긴 Action은 담당자 본인과 admin이 고치거나 지운다.
- 사용자(역할): 조회는 로그인한 모든 역할(admin·sales·user), 등록은 sales·admin(Deal Owner 여부와 무관), 수정·삭제는 Action 담당자 본인 sales와 admin.
- 범위
  - 화면: Deal 상세 Actions 탭(`/deals/:code?tab=actions`)의 "Action 추가" 버튼, Action 목록 표(열·행 열기), Action 상세 팝업(전체 항목, 칸별 인라인 수정, 삭제 — 2026-11-16), Action 추가 팝업(이전 Update 카드, 수행일 칸, Status·Forecast·유형 한 줄, 내용 칸), 삭제 확인
  - API `POST /deals/{code}/actions`(등록), `GET /deals/{code}/actions`(조건 없는 기본 목록), `GET /deal-actions/{action_id}`, `PUT /deal-actions/{action_id}`, `DELETE /deal-actions/{action_id}`
  - Action 등록에 딸린 Status·Forecast 변경(최대 2건 순차 적용, `finalize_sequence`)과 이전 Next Action 종료(`close_previous_next_action_id`)
  - Action 등록·수정의 수행일(`acted_on`) 지정(수정은 2026-11-13 추가)
  - Action 유형 선택을 저장한 결과(새 유형 생성의 원자성, 판정 순서, 이력의 유형 이름)
  - Action 등록·수정·삭제·등록 때 이전 Next Action 종료가 Deal History에 남기는 문구
- 범위 밖(다른 feature)
  - Actions 탭 틀(탭 이름·주소 `?tab=actions`·알림 위치) → DD(DD-R27). Deal 저장의 동기화 규칙(불변식·계획·답) → DD(DD-R5~R10), Deal 필드 이력 diff와 자르기 → DD(DD-R20·R21)
  - `{id}`/`{name}` 선택 요청 형식과 Action 유형 해석·이름 규칙·새 유형의 속성 → CL(CL-R1, CL-R12, CL-R13, CL-R15, CL-R16), 유형 이름 변경의 효과 → CL(CL-R9)
  - Next Action 상태 변경 API(`PUT /deal-actions/{id}/next-action-status`), 표의 상태 칸·종료 팝업, Action 목록 검색 조건(유형·담당자·키워드·수행일·Due·상태 필터)·검색 바·정렬 선택(`sort` 파라미터·머리글 정렬) → NA(상태 변경 NA-R1~R9, 조회 조건·필터 NA-R11~R17·R19·R20, 정렬 NA-R18, 상태 칸·종료 팝업 NA-R21~R24, 검색 바·머리글 정렬·빈 결과 문구 NA-R25~R29). "이전 Next Action 종료" 이력의 대상·문구 형식 → NA(NA-R8)
  - Next Action 기준 행·최종 업데이트·기한초과 판정과 Action 표의 기한초과 배지 → RK(RK-R1, RK-R2, RK-R4, RK-R18), Status 진입일 → RK(RK-R9)
  - Won 진입·이탈 계약 처리와 `delete_license_contracts`, Action 등록 때의 계약 처리 확인 화면 → LC(LC-R6~R9, LC-R36)
  - Deal 삭제 때 Action이 함께 지워지는 것 → DD(DD-R25), 삭제 영향의 Action 건수 → DD(DD-R22)
  - 공통 권한 판정·CSRF·Problem 형식·id 경로 파라미터·NUL 거부·화면 오류 문구 → PL(PL-R6, PL-R9~R12, PL-R15, PL-R16, PL-R37)
  - 날짜 입력 `DateInput`·콤보박스·모달 공통 동작 → UI(`DateInput` UI-R1~R11, 콤보박스 UI-R18~R21, 모달 UI-R25~R28), 서버 시각 표기 → TM(TM-R8)
- 관련 화면·메뉴: Deals → Deal 상세 → Actions 탭.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| Action | Deal에서 일어난 활동 한 건. 유형, 진행사항, Next Action, Due Date, 수행일, 담당자(수행자), 등록 시점 Status·Forecast를 가진다 |
| Comment | Action에 대한 글은 별도 엔티티 Action Comment다(CM-R2). Action 등록 요청의 `comment`로 함께 남길 수 있다 |
| 진행사항 | 한 일. API 필드 `action`, 화면 `progress` |
| Next Action / Due Date | 다음에 할 일과 그 기한. 둘은 함께 있거나 함께 없다 |
| 진행사항만 Action / Next Action만 Action | Next Action이 없는 Action / 진행사항이 없는 Action |
| 수행일(`acted_on`) | Action을 한 업무 날짜(TM-R4). 날짜만 저장하고 시각은 없다. 등록 때 정하고(AC-R34) 수정에서 고칠 수 있으며(AC-R45) Next Action 상태 변경으로는 바뀌지 않는다. 등록에서 지정하지 않으면 오늘 |
| 수행일 지정 | 등록·수정 요청의 `acted_on`. 오늘 또는 지난 날짜이고 Deal 등록일 이상(AC-R35, AC-R45). 수정에서 생략·null이면 기존 값 유지 |
| 요청 시각 | 등록 요청을 처리한 서버 시각. 수행일과 무관하게 `created_at`·`updated_at`·이력·동반 변경·이전 Next Action 종료의 시각이다(AC-R37) |
| 담당자(`actor`) | 등록한 사용자. 바뀌지 않는다. 수정·삭제 권한의 기준이다 |
| 스냅숏 | Action에 남는 등록 시점(동반 변경이 있으면 변경 뒤)의 Status·Forecast key. 바뀌지 않는다 |
| 동반 변경 | Action 등록 요청에 실린 Status·Forecast 변경(`status_change` 또는 `status_changes`) |
| 기준 행 | 그 Deal에서 Next Action이 있는 가장 최근 Action(정의는 RK-R1) |
| 이전 Next Action 종료 | 등록 요청의 `close_previous_next_action_id`로 기준 행의 Next Action을 같은 저장에서 종료(수행)로 바꾸는 것 |
| 요약 | Deal History에 쓰는 Action 한 줄 표기(AC-R10) |

### 2.2 데이터 모델

- `deal_actions`(PK `id` BIGINT identity): `deal_id`(deals FK **CASCADE**), `action_type_id`(action_types FK RESTRICT), `action` TEXT NULL, `next_action` TEXT NULL, `due_date` DATE NULL, `next_action_status` VARCHAR(20) NULL(`open`·`done`·`not_done`), `next_action_closed_on` DATE NULL(Next Action 종료일), `acted_on` DATE NOT NULL(수행일, 인덱스 `ix_deal_actions_acted_on`·`ix_deal_actions_deal_id_acted_on`), `actor_user_id`(users FK RESTRICT), `status_key`·`forecast_key`(codes 복합 FK RESTRICT), `created_at`, `updated_at`. 2026-11-17 리비전(SC-R24)이 값을 Action Comment로 옮긴 뒤 `memo` 컬럼을 drop했다(CM-R21~R23). 유니크 `uq_deal_actions_id (id, deal_id)`를 추가한다(Comment 복합 FK의 대상).
- CHECK: `action_or_next`(진행사항·Next Action 중 하나 이상), `next_action_fields`(Next Action·Due Date·상태가 함께 있거나 함께 없음), `next_action_status`(세 값), `next_action_closed_on`(이름 `ck_deal_actions_next_action_closed_on`, 종료 상태일 때만 종료일). 텍스트 길이 상한은 없다. 이 문서에서 Next Action의 "종료 시각"은 종료일(업무 날짜, NA-R4)을 뜻한다. 수행일과 종료일 사이의 선후 CHECK는 없다(AC-R46).
- 담당자 FK가 RESTRICT라 Action을 남긴 사용자는 물리 삭제 대신 퇴사 처리된다(US-R17). 유형 FK가 RESTRICT라 쓰이는 유형은 지울 수 없다(CL-R10).
- 값 객체: `ActionContent(action_type, action, next_action, due_date)`, `NextActionState(status, closed_on)`, `DealActionId`(int). `StatusChangeInput(field, value, resolution)`, `DealActionInput(content, status_changes, close_previous_next_action_id, delete_license_contracts, acted_on)`에 `comment: str = ""`가 추가된다, `DealActionUpdateInput(content, acted_on)`(수정, 2026-11-13 추가). 수행일 결정 함수 `resolve_acted_on(acted_on, *, now, deal_registered_at) -> date`(domain, AC-R34·R35)와 범위 판정 `ensure_acted_on_in_range(acted_on, *, now, deal_registered_at) -> None`(등록·수정 공통, AC-R35·R45, 2026-11-13 추가). 마이그레이션은 날짜 전환 리비전 `b4d7e2a9c613`(SC-R20)이고, `acted_at`을 `acted_on`으로, `next_action_closed_at`을 `next_action_closed_on`으로 바꾼다(AC-R44, NA-R32). 수정 때 수행일 변경은 스키마 변경이 없다.

### 2.3 비즈니스 규칙

등록 API
- **AC-R1** `POST /deals/{code}/actions`는 업무 쓰기다(sales·admin, user는 PL-R6 403). 성공은 201, 헤더 `Location: /api/v1/deal-actions/<id>`, 본문 `DealActionResponse`(AC-R20). Deal Owner가 아닌 sales도 어떤 Deal에든 등록할 수 있다(Owner 검사 없음).
- **AC-R2** 요청 본문(모르는 키는 422 `request-validation`): `action_type`(필수, CL-R12 선택 객체), `action`·`next_action`(문자열, 생략하면 ""), `comment`(문자열, 생략하면 "", CM-R14), `due_date`(`YYYY-MM-DD` 또는 null, 생략하면 null — 달력 날짜가 아니면 422 `request-validation`), `status_change`(선택, 단건)·`status_changes`(선택, 최대 2건), `close_previous_next_action_id`(선택, JSON 정수 1~2^53−1 또는 null), `delete_license_contracts`(LC-R9), `acted_on`(선택, `YYYY-MM-DD` 또는 null, 생략·null이면 오늘 — 달력 날짜가 아니거나 시각이 붙은 값·숫자는 422 `request-validation`, AC-R34). 서버가 정하는 `acted_at`·`actor_user_id`·`actor`·`deal_code`와 폐지된 `title`을 보내면 422 `request-validation`이다(수행 시점은 `acted_on`으로만 고른다). 스키마에 텍스트 길이 상한(`maxLength`)이 없다. 예전 `memo` 키는 422 `request-validation`이다(2026-11-17).
- **AC-R3** 내용 규칙(`ActionContent.parse`, 등록·수정 공통), 위에서부터 첫 위반만 알린다:
  1. 진행사항·Next Action에 NUL 문자가 있으면 422 `invalid-value` "<진행사항|Next Action>에는 NUL 문자를 쓸 수 없습니다"
  2. 앞뒤 공백을 지운 진행사항·Next Action이 모두 비면(`comment`만 있어도) 422 `invalid-value` "진행사항 또는 Next Action을 입력하세요."
  3. Next Action이 있는데 Due Date가 없으면 422 `invalid-value` "Due Date를 입력하세요."
  4. Next Action이 없는데 Due Date가 있으면 422 `invalid-value` "Next Action 없이 Due Date를 입력할 수 없습니다."
  
  통과하면 두 텍스트의 앞뒤 공백을 지워 저장하고, 빈 진행사항·Next Action은 null로 저장한다. 길이 상한이 없다(예: 5,000·5,000자). 길이 상한이 없어 자르지 않는다. 지난 Due Date도 받는다.
- **AC-R4** 서버가 정하는 값: `acted_on` = AC-R34로 정한 수행일(지정이 없으면 오늘), `created_at` = `updated_at` = 요청 시각, 담당자 = 요청자, 스냅숏 = 동반 변경을 모두 적용한 뒤의 Deal Status·Forecast key(동반 변경이 없으면 현재 값). Next Action이 있으면 상태 `open`·종료 시각 null, 없으면 상태·종료 시각 모두 null.
- **AC-R5** 유형: `action_type`은 CL-R13으로 해석한다(없는 id 422 "선택한 유형이 없습니다. 목록에서 다시 선택하세요.", 이름 규칙 CL-R1, 없는 이름은 새 유형 CL-R15). 새 유형은 Action 저장과 같은 작업 단위에서 만들어지므로 등록이 어떤 이유로든 거절되면(입력·이전 Next Action·동반 변경·계약 판정) 새 유형도 남지 않는다. 같은 이름으로 다시 등록하면 만든 유형을 재사용한다.
- **AC-R6** 동반 변경
  - 형식(위반은 422 `request-validation`): 항목은 `{change: {field, value}, resolution?}`, `field`는 `status_key`·`forecast_key`만(`revenue_amount`·`revenue_date`·`name` 등 거부), `value`는 문자열, `resolution`은 DD-R11과 같다. `status_changes`는 최대 2건이고 같은 `field`가 두 번 오면 거부한다. `status_change`와 `status_changes`를 함께 보내면(빈 배열이어도) 거부하고, 둘 다 null이면 변경 없음이다. 빈 배열도 변경 없음이다. 단건 `status_change`는 1건짜리 `status_changes`와 같다. 화면은 `status_changes`만 보내지만 단건 `status_change`는 하위 호환으로 유지한다(현행 유지, 2026-11-10 결정).
  - 판정: 먼저 모든 항목의 `value`가 코드 목록에 있는지 확인한다(없으면 422 `invalid-value` "존재하지 않는 코드입니다." — 두 번째 항목의 코드도 첫 항목의 매출 판정보다 먼저). 그다음 배열 순서대로 각 항목을 **직전 항목을 적용한 상태** 기준으로 DD-R6~R10(계획·답)에 따라 확정한다. 두 항목이 있을 때 두 번째 결과가 첫 항목이 바꾼 필드의 값을 다시 바꾸면 422 `invalid-value` "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."이다(예: Status를 제품소개로 바꾼 뒤 Forecast를 Won으로 = 종결이라 Status가 계약완료가 됨). 두 번째 항목이 첫 항목이 **함께 바꾼** 필드를 바꾸는 것은 된다(예: Won Deal의 Forecast를 Commit으로 되돌리며 Status를 PoC완료로 고른 뒤 Status를 제품소개로).
  - 결과: 단계마다 Deal의 Status·Forecast(종결이면 금액·Expected Close)를 바꾸고 단계마다 DD-R20·R21 이력을 남긴다(함께 바뀐 쪽에 "함께 변경" 표기). 값이 실제로 바뀌면 Deal `updated_at` = 요청 시각, Status 진입일은 RK-R9. 같은 값으로 바꾸는 항목은 아무것도 바꾸지 않는다(Deal 이력·`updated_at` 그대로, Action만 남음). Won 진입·이탈은 처음과 끝만 견줘 LC-R6~R9로 처리한다.
- **AC-R7** 이전 Next Action 종료: `close_previous_next_action_id`가 null이거나 없으면 이전 Action을 건드리지 않는다. 값이 있으면
  1. 그 Deal의 기준 행(RK-R1, 진행사항만 Action은 건너뜀, 상태 무관)의 id와 같지 않으면(그 사이 더 최근 Next Action이 생김, 다른 Deal의 Action, 없는 id, 그 Deal에 Next Action이 하나도 없음) 409 `invalid-state` "이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요."
  2. 요청자가 기준 행을 바꿀 권한(AC-R18, 기준 행의 담당자 본인 sales 또는 admin)이 없으면 403 `forbidden` "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다." — 기준 행이 이미 종료여도 이 판정을 한다
  3. 기준 행이 이미 종료(`done`·`not_done`)면 상태·종료 시각을 바꾸지 않고 이력도 남기지 않는다
  4. Open이면 상태 `done`, 종료일 = 오늘(요청의 업무 날짜), `updated_at` = 요청 시각으로 바꾼다. Comment를 만들지 않는다(CM-R15)
  
  새 Action에 Next Action이 없어도(진행사항만) 이전 행을 닫을 수 있다. 수정 요청에는 이 필드가 없다(보내면 422 `request-validation`).
- **AC-R8** 등록 판정 순서: 401 → CSRF 403(PL-R9) → user 403(PL-R6) → 요청 형식 422 `request-validation`(AC-R2, AC-R6 형식, CL-R12) → 없는 Deal·형식이 틀린 code 404 `not-found` "Deal을 찾을 수 없습니다."(DD-R1) → 유형 422(AC-R5) → 내용 422(AC-R3) → Comment 422(CM-R14) → 수행일 422(AC-R35: 오늘 이후 → Deal 등록일 이전) → 이전 Next Action 409 → 그 권한 403(AC-R7) → 수행일·기준 행 422(AC-R36) → 코드 존재 422 → 단계별 동기화 422(DD-R7·R8) → 충돌 422(AC-R6) → 계약 409(LC-R8).
- **AC-R9** 원자성: 등록 요청이 거절되면 Action·Deal 값·Deal History·새 유형·이전 Action 상태·계약·Comment 모두 그대로다. 성공하면 이 모두가 한 트랜잭션으로 저장된다.

Deal History
- **AC-R10** 요약(`action_summary`): `<유형 이름>` + (진행사항이 있으면 ` · <진행사항>`) + (Next Action이 있으면 ` / Next Action: <Next Action> (Due <YYYY-MM-DD>)`). 유형 이름은 그 시점의 이름이고, 나중에 유형 이름을 바꿔도 이미 남은 문구는 그대로다(CL-R9). 예: "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)". 2026-11-17 전에 남은 이력의 ' / Memo: …' 부분은 그대로다(SC-R8). 요약에는 수행일이 없다(수행일이 바뀐 수정만 AC-R11 표처럼 끝에 덧붙인다).
- **AC-R11** Action이 남기는 이력(구분 `action`, 변경자 = 요청자, 시각 = 요청 처리 시각, 자르기 DD-R20):

  | 행동 | 대상 | 변경 전 | 변경 후 |
  | --- | --- | --- | --- |
  | 등록 | Action | "" | "등록: <요약>" |
  | 등록 때 이전 Next Action 종료(AC-R7 ④) | Next Action | NA-R8 형식: "<Next Action> (Due <날짜>) · Open" | NA-R8 형식: "종료(수행)"(Comment 없음) |
  | 수정(내용이나 수행일이 바뀐 경우만) | Action | <수정 전 요약>[" / 수행일: <이전 수행일>"] | "수정: <수정 후 요약>"[" / 수행일: <새 수행일>"] |
  | 삭제 | Action | <삭제 전 요약> | "삭제" 또는 "삭제 (Comment <N>건 함께 삭제)"(CM-R16) |

  수정 줄의 `[ / 수행일: <YYYY-MM-DD>]` 부분은 그 수정으로 수행일이 바뀐 경우에만 변경 전·후 양쪽 끝에 붙고(AC-R45, 2026-11-13 추가), 수행일이 그대로인 수정의 문구는 예전과 같다. 이전 Next Action 종료 줄의 대상·문구 형식은 NA-R8이 정하고(2026-11-10 결정), 이 규칙은 등록 경로에서 그 줄이 남는 조건(AC-R7 ④)과 저장 순서만 정한다. 한 등록에서 나온 항목은 같은 시각이고 저장 순서는 동반 변경의 Deal 필드 이력(단계 순서) → 이전 Next Action 종료 → Action 등록 → (comment가 있으면) Comment 등록(CM-R14)이다. 그래서 이력 목록(DD-R17, 같은 시각이면 나중에 저장한 것이 위)의 맨 위는 Comment 등록 줄(있으면) 또는 Action 등록 줄이다. 요약이 1,000자를 넘으면 이력만 999자 + "…"로 자르고 Action 원문은 자르지 않는다(덧붙인 수행일 부분도 자르기 대상이라 아주 긴 요약에서는 보이지 않을 수 있다). 1,000자 뒤에서만 달라진 수정도 이력 1건을 남긴다.
- **AC-R12** Deal에 미치는 효과: Action 등록·수정·삭제는 동반 변경이 없으면 Deal 값과 Deal `updated_at`을 바꾸지 않는다. Deal의 `next_action`·`last_updated_on`은 Action에서 다시 계산된다(RK-R1·R2) — 등록한 Action이 Next Action을 가지면 그 Action이 기준 행이 되고, 가장 최근 Action을 지우면 그 이전 Action이 기준 행이 되며, 하나뿐인 Action을 지우면 `next_action`은 null이다. 수정으로 수행일을 바꾸면 기준 행·최종 업데이트일도 다시 계산된다(AC-R46).

수행일 지정(2026-11-13 추가)
- **AC-R34** 수행일 결정: 오늘 = 요청 시각의 업무 날짜(TM-R4). `acted_on`이 없거나 null이면 수행일은 오늘이고, 값이 있으면 그 날짜(AC-R35 범위 안)다. 시각은 저장하지 않는다. '지난 날짜는 23:59:59, 오늘은 요청 시각'이던 규칙은 2026-11-13에 폐지했다. 예(Asia/Seoul): 2026-11-13 14:30 요청에서 `acted_on`이 2026-11-10이면 수행일은 2026-11-10이고, 생략하면 2026-11-13이다.
- **AC-R35** 수행일 범위(Deal을 찾은 뒤, 내용 검증 다음에 판정): `acted_on` > 오늘이면 422 `invalid-value` "수행일은 오늘 이후로 지정할 수 없습니다."(내일부터 거절). `acted_on` < Deal 등록일(Deal `created_at`의 업무 날짜)이면 422 `invalid-value` "수행일은 Deal 등록일(<YYYY-MM-DD>) 이전으로 지정할 수 없습니다."(등록일 당일은 허용). 둘 다 위반이 될 수 없으므로 위에서부터 하나만 알린다. 수정의 수행일도 같은 범위·문구다(AC-R45).
- **AC-R36** 이전 Next Action 종료와 수행일: `close_previous_next_action_id`가 있고 AC-R7 ①(409)·②(403)를 통과한 뒤, 새 수행일(지정이 없으면 오늘)이 기준 행 수행일(`acted_on`)보다 앞이면 422 `invalid-value` "이전 Next Action의 수행일(<YYYY-MM-DD>)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다."다. 같은 날은 허용한다. 기준 행이 이미 종료여도 이 판정을 한다(AC-R7 ②와 같음). 종료할 때 종료일은 오늘이고 기준 행 `updated_at`·이력 시각은 요청 시각이다(수행일이 아님). 이 규칙은 등록에만 있고 수정에는 적용하지 않는다(AC-R46).
- **AC-R37** 수행일과 무관하게 요청 시각으로 남는 것: 새 Action의 `created_at`·`updated_at`, 스냅숏(요청 처리 시점의 Deal Status·Forecast, 동반 변경이 있으면 변경 뒤 — 수행일 당시 값이 아님), 동반 변경의 Deal `updated_at`·Deal History 시각, Status 진입일(오늘, RK-R9), 이전 Next Action 종료일(오늘), 이 등록이 남기는 모든 이력 시각, 새 유형 생성 시각.
- **AC-R38** 파생 값에 미치는 효과: 기준 행(RK-R1)·최종 업데이트일(RK-R2)·기본 목록 순서(AC-R18)·수행일 정렬(NA-R18)·수행일 검색(NA-R15)·Reports `action.acted_at`(date, RQ-R58)은 모두 `acted_on`을 쓴다. 지난 날짜 Action은 더 늦은 수행일의 Action이 있으면 최종 업데이트일을 바꾸지 않고, Next Action이 있는 더 늦은(같은 날이면 나중에 등록한) Action이 있으면 기준 행도 바꾸지 않으며, 목록에서는 그 날짜 자리에 놓인다. 같은 수행일 안에서는 id가 큰 Action, 곧 나중에 등록한 Action이 더 최근이다(AC-R43). 수정으로 수행일을 바꾼 Action도 같은 규칙으로 바뀐 수행일 자리에 놓인다(AC-R46). 이 규칙은 RK-R1·R2의 정의를 바꾸지 않는다.
- **AC-R39** 수행일을 정하는 곳: 등록(AC-R34)과 `acted_on`을 보낸 수정(AC-R45)만 `acted_on`을 정한다. Next Action 상태 변경(NA-R5)과 `acted_on`을 보내지 않은(생략·null) 수정은 `acted_on`을 바꾸지 않는다. (2026-11-13 변경: 이전에는 '수행일은 등록 때만 정한다')

수정 API
- **AC-R13** `PUT /deal-actions/{action_id}`는 업무 쓰기다. 본문은 AC-R2의 내용 칸(`action_type`·`action`·`next_action`·`due_date`)과 `acted_on`(선택, 형식은 AC-R2의 등록과 같음 — `YYYY-MM-DD` 또는 null, 달력 날짜가 아니거나 시각이 붙은 값·숫자는 422 `request-validation`, 2026-11-13 추가)이다. `status_change`·`status_changes`·`close_previous_next_action_id`·`memo`·`comment`(CM-R17)·서버 필드(`acted_at`·`actor_user_id`·`actor`·`deal_code`)를 보내면 422 `request-validation`이다. `action_id`는 PL-R15. 성공은 200 `DealActionResponse`.
- **AC-R14** 수정 결과: 내용과 (보냈으면) 수행일을 바꾼다(AC-R45). 담당자·스냅숏·`created_at`·소속 Deal은 그대로이고 내용이나 수행일이 바뀌면 `updated_at` = 서버 시각이다. 유형·두 텍스트·Due Date(정규화 뒤)가 모두 같고(앞뒤 공백만 다름, 같은 유형 id, 대소문자만 다른 같은 유형 이름) 수행일도 그대로면(`acted_on` 생략·null·지금과 같은 날짜) 200이지만 저장·이력·`updated_at` 변경이 없고 새 유형도 생기지 않는다. Next Action 상태: Next Action을 비우면 상태·종료 시각이 null(종료였어도), 없던 Next Action을 채우면 `open`, 있던 Next Action의 텍스트·Due Date나 다른 칸·수행일만 고치면 상태·종료 시각 그대로(종료여도). 유형만 바꿔도 이력 1건이며 새 이름이면 새 유형이 생긴다(실패하면 남지 않음).
- **AC-R15** 수정 판정 순서: 401 → CSRF 403 → user 403(PL-R6, 없는 id여도 먼저) → 요청 형식 422(`acted_on` 형식 포함) → 없는 Action 404 `not-found` "Action을 찾을 수 없습니다." → 담당자가 아님 403 `forbidden` "본인 Action 또는 admin만 수정할 수 있습니다."(본문이 잘못돼도 403) → 유형 422(AC-R5) → 내용 422(AC-R3) → 수행일 422(AC-R45: 오늘 이후 → Deal 등록일 이전). 거절되면 Action·이력·유형 목록이 그대로다.

수정 때 수행일 변경(2026-11-13 추가)
- **AC-R45** 수정의 수행일: `acted_on`이 없거나 null이거나 지금 수행일과 같은 날짜면 수행일을 바꾸지 않고 범위 판정도 하지 않는다. 다른 날짜면 AC-R35와 같은 범위·문구로 판정한다(오늘 = 요청 시각의 업무 날짜, Deal 등록일 = 그 Action이 속한 Deal `created_at`의 업무 날짜): 오늘보다 뒤면 422 `invalid-value` "수행일은 오늘 이후로 지정할 수 없습니다.", Deal 등록일보다 앞이면 422 `invalid-value` "수행일은 Deal 등록일(<YYYY-MM-DD>) 이전으로 지정할 수 없습니다."(오늘·등록일 당일은 허용). 통과하면 수행일을 그 날짜로 바꾼다. 수행일 변경은 내용 변경과 같이 다룬다: 수행일만 바뀌어도 저장하고 `updated_at` = 요청 시각, 이력 1건(AC-R11, 수행일 부분을 덧붙임). 바뀌지 않는 것: 담당자·스냅숏·`created_at`·Next Action 상태와 종료일·Deal 값과 Deal `updated_at`.
- **AC-R46** 수정 수행일에 없는 제약과 파생 값: 등록의 AC-R36(이전 Next Action 기준 행보다 앞 금지)은 수정에 적용하지 않는다(수정에는 이전 Next Action 종료가 없다). 이 Action의 Next Action 종료일, 이 Action이 등록 때 닫은 이전 Action의 수행일, 같은 Deal의 다른 Action 수행일과의 선후도 판정하지 않는다. 그래서 수정 뒤에는 '종료일이 수행일보다 앞인 Action'이나 '자기가 닫은 Action보다 앞선 수행일의 Action'이 있을 수 있다. 기준 행(RK-R1)·최종 업데이트일(RK-R2)·기본 목록 순서(AC-R18)·수행일 정렬(NA-R18)·수행일 검색(NA-R15)은 바뀐 수행일로 다시 계산된다. 같은 수행일 안의 순서는 계속 id(등록 순서, AC-R43)이고 수정해도 id는 바뀌지 않는다.

삭제 API
- **AC-R16** `DELETE /deal-actions/{action_id}`는 업무 쓰기다. 성공은 204(본문 없음)이고 행을 물리 삭제하며 그 Action의 Action Comment도 함께 지우고(CM-R16) 이력(AC-R11)을 남긴다. 판정 순서: 401 → CSRF 403 → user 403(없는 id여도 먼저) → id 형식 422(PL-R15) → 없는 Action·이미 지운 Action 404 "Action을 찾을 수 없습니다." → 담당자가 아님 403 `forbidden` "본인 Action 또는 admin만 삭제할 수 있습니다.". 거절되면 Action·이력이 그대로다.

권한
- **AC-R17** 등록은 sales·admin 누구나 모든 Deal에 한다. 수정(수행일 변경 포함)·삭제·등록 때 이전 Next Action 종료는 `can_edit_action`: admin은 모든 Action, sales는 자기가 담당자인 Action만(Deal Owner와 무관), user는 자기 id여도 불가. admin이 남의 Action을 고치거나 지워도 담당자는 바뀌지 않고 이력 변경자는 admin이다.

조회 API
- **AC-R18** `GET /deals/{code}/actions`(검색 조건 없이 부를 때)는 로그인한 모든 역할이 부른다. 없는 Deal·형식이 틀린 code는 404 "Deal을 찾을 수 없습니다.". 응답은 `{items: DealActionResponse[]}`(키 `items`뿐)이고 페이지가 없어 그 Deal의 Action 전부를 돌려주며 다른 Deal의 Action은 섞이지 않는다. 기본 순서는 수행일 내림차순이고, 수행일이 같으면 id 내림차순(나중에 등록한 것이 앞, AC-R43)이다. 조건 없는 기본 순서와 표 열 구성(AC-R21)은 AC, 조회 조건·필터는 NA(NA-R11~R17, NA-R19, NA-R20), 정렬 선택은 NA-R18이 정한다(NA-R18의 기본값 `acted_at_desc`가 이 순서, 2026-11-10 결정). 전역 Action 검색 경로(`GET /deal-actions`)는 없다.
- **AC-R19** `GET /deal-actions/{action_id}`는 로그인한 모든 역할이 부른다. 없는 id는 상한값(2^53−1)이어도 404 "Action을 찾을 수 없습니다."(형식은 PL-R15).
- **AC-R20** `DealActionResponse` 키는 정확히 `id`, `deal_code`, `action_type`(`{id, name}`, 이름은 읽는 시점의 현재 이름), `action`, `next_action`, `due_date`, `next_action_status`, `next_action_closed_on`(날짜 또는 null), `acted_on`(날짜 `YYYY-MM-DD`, null 아님), `actor`(UserRef, 퇴사자도 `resigned` true), `status_key`, `forecast_key`, `created_at`, `updated_at`이다. `action`·`next_action`·`due_date`·`next_action_status`·`next_action_closed_on`은 null일 수 있으나 키는 항상 있다. id는 JSON 정수, 시각 표기는 TM-R8.

화면(frontend, Actions 탭)
- **AC-R21** 목록 표(이름 "Action 목록")의 열 순서: 수행일(`YYYY-MM-DD`), 유형(현재 이름), 진행사항, Next Action, Due Date(기한초과 배지 RK-R18), 상태(NA), Comment(아이콘·읽지 않은 수, CM-R40) — 7열이다. 담당자·등록 시점 Status·Forecast·관리 열은 없다(이 값들은 상세 팝업 AC-R49에서 본다). Memo 열은 없다(CM). 칸 폭은 AC-R53. 빈 값은 "—". 서버 순서를 그대로 보인다. 처음 읽는 동안 "불러오는 중…", 조건 없이 Action이 없으면 "등록된 Action이 없습니다."(조건 있을 때 문구는 NA), 목록 오류는 오류 배너(PL-R37). 행을 누르면 그 Action의 상세 팝업이 열린다(AC-R48).
- **AC-R22** 버튼과 권한: `canWrite`(admin·sales, PL-R36)면 표 위에 "Action 추가" 버튼이 있고 user에게는 없다. 다른 sales에게도 추가 버튼은 보인다. 표에는 "수정"·"삭제" 버튼과 관리 열이 없다(2026-11-16 폐지). Action 한 건의 수정·삭제는 상세 팝업에서 `canEditAction`(AC-R17)일 때만 한다(AC-R50, AC-R52).
- **AC-R23** 추가 팝업(모달, 제목 "Action 추가", 넓은 폭): 맨 위 이전 Update 카드(AC-R26, 기준 행이 있을 때), 그 아래 폼. 안내 "담당자: <내 이름>". 그 아래 수행일 칸(AC-R40). 한 줄 그룹(이름 "Status · Forecast · 유형")에 Status 선택(현재 값), Forecast 선택(현재 값), 유형 입력(빈 값). 그 아래 진행사항(여러 줄), Next Action(한 줄), Due Date(`DateInput`, UI-R1~R11), Comment(여러 줄, 선택 — CM-R42), 버튼 "등록"·"취소". 열리면 진행사항 칸에 포커스가 간다. 예전 "Next Action 업데이트" 문구는 없다. (2026-11-17 Memo 칸 → Comment 칸)
- **AC-R24** 추가 팝업의 화면 검증(요청 전, 위에서부터): 수행일(AC-R41) → 유형 — 공백뿐이면 "유형을 입력하세요.", 51자 이상(코드 포인트)이면 "유형은 50자 이내로 입력하세요."(50자 허용) → 진행사항·Next Action이 모두 비면 "진행사항 또는 Next Action을 입력하세요." → Next Action이 있는데 Due Date가 비면 "Due Date를 입력하세요.", Due Date가 틀리거나 덜 쳤으면 `DateInput` 문구(UI-R7), Next Action 없이 Due Date가 있으면 "Next Action 없이 Due Date를 입력할 수 없습니다.". 문구는 그 칸 아래에 보이고 첫 오류 칸(수행일 → 유형 → 진행사항 → Due Date)으로 포커스를 옮기며 요청을 보내지 않는다. Next Action을 모두 지우면 Due Date도 비운다. yyyymmdd로 친 Due Date는 ISO 날짜로 보낸다. 상세 팝업 인라인 편집은 같은 문구를 칸별로 쓴다(AC-R47, AC-R51). (2026-11-16 변경: 수정 팝업 폐지로 추가 팝업만)
- **AC-R25** 유형 입력(콤보박스, UI-R18~R21): 누르면 서버 순서(CL-R3)의 유형 후보, 치면 부분 일치(대소문자 무시) 후보, 고르면 이름을 채운다. 목록을 읽었고 입력이 어떤 유형과도(대소문자 무시) 같지 않으면 안내 "목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다."를 보인다(목록을 읽는 중·실패면 안내 없음, 실패는 오류 배너). 저장 때 CL-R16으로 `{id}` 또는 `{name}`을 보낸다. 새 이름으로 등록한 유형은 다음 팝업 후보에 나온다. 서버가 유형을 거절하면 그 문구를 팝업 안에 보이고 입력을 유지한다.
- **AC-R26** 이전 Update 카드(이름 "이전 Update", 등록 팝업에만): 기준 행(화면 계산 `latestWithNextAction` — 수행일로 비교, 같으면 id가 큰 행, 상태 무관, 서버 RK-R1과 같다)의 진행사항·Next Action·Due("—" 대체)를 읽기 전용으로 보인다. "이전 Next Action을 진행사항에 채우기"를 누르면 진행사항을 그 Next Action으로 채운다. 채운 뒤 기준 행이 Open이고 내가 바꿀 수 있으면(AC-R17) 체크박스 "저장 시 이전 Next Action을 종료(수행)로 바꿈"이 켜진 채 나타나고(다시 눌러도 사용자가 끈 체크는 유지), 바꿀 수 없으면 안내 "다른 담당자의 Next Action이라 상태는 바꾸지 않습니다.", 이미 종료면 둘 다 없다. 체크가 켜져 있을 때만 등록 요청에 `close_previous_next_action_id`(채운 행의 id)를 싣는다. 채운 뒤 카드가 다른 행으로 바뀌면 "이전 Update가 바뀌었습니다. 확인 후 다시 채우세요."를 보이고 체크를 끄며 id를 보내지 않는다(입력한 진행사항은 그대로).
- **AC-R27** Status·Forecast 칸(등록 팝업에만): 다른 값을 고르면 DD-R36과 같은 대화상자(매출 확정·함께 바꿀 값 선택, 겹친 팝업)로 답을 받고, 바꾼 순서대로 최대 2건을 쌓는다(각 변경은 직전 상태 기준). 바뀐 칸 아래 "현재: <원래 이름>". 두 번째 변경이 첫 변경 값을 뒤집으면(대화상자 전이든 답 뒤든) 저장 전에 막고 "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."를 보인다(다음 성공 변경에서 지움). 대화상자를 취소하면 앞선 변경은 유지된다. 이미 바꾼 칸을 다시 바꾸거나 원래 값으로 되돌리면 그 칸과 그 뒤 변경을 버리고, 다른 칸 변경도 함께 버려졌으면 "<Status|Forecast> 변경도 취소되었습니다. 필요하면 다시 선택하세요."를 보인다. 변경이 있으면 "Status·Forecast 변경 취소" 버튼으로 모두 버린다(동기화 알림도 지움). 저장 때 쌓인 변경을 순서대로 `status_changes`로 보내고, 없으면 보내지 않는다. Won 이탈이면 요청 전에 LC-R36 확인을 거친다.
- **AC-R28** 저장과 알림: 등록 성공이면 팝업을 닫고 알림 "Action이 등록되었습니다."에 (이전 Next Action을 닫았으면) " 이전 Next Action을 종료(수행)로 바꿨습니다." , (최종 Status·Forecast가 처음과 다르면) " Status가 '<이름>'(으)로, Forecast가 '<이름>'(으)로 변경되었습니다."(바뀐 쪽만, Status 먼저)를 이어 붙인다. 새 Action이 목록 맨 위에 보이고 요약 바의 Next Action(RK-R1, RK-R17)이 새로 읽힌다. 상세 팝업의 인라인 저장 성공은 "Action이 수정되었습니다."(AC-R50). 서버 거절(422·403·409 등)은 팝업 안 오류 배너(서버 문구)이고 팝업과 입력을 유지한다. 409(이전 Next Action 바뀜) 뒤 팝업을 닫고 다시 열면 카드가 새 기준 행을 보이고 그 행을 닫는 등록이 된다.
- **AC-R29** 닫기·포커스(추가 팝업): "취소"·Esc는 저장 없이 닫고 입력을 버린다. 닫으면 포커스는 "Action 추가" 버튼으로 돌아간다. 저장 중에는 "취소"가 꺼지고 Esc를 무시하며, 끝나면(실패면 다시 켜짐) 정상 동작한다. 겹친 팝업(동기화·계약 확인)이 열려 있으면 Esc는 맨 위 팝업만 닫고 Tab 포커스는 맨 위 팝업 안에서만 돈다. 유형 후보 목록이 열려 있을 때 Esc는 후보만 닫는다. 상세 팝업의 닫기·포커스는 AC-R48~R50. (2026-11-16 변경: 수정 팝업 부분 삭제)
- **AC-R30** 폐지(2026-11-16): "Action 수정" 팝업(값을 채운 수정 폼, "저장"·"취소")은 없다. Action 수정은 상세 팝업의 칸별 인라인 편집(AC-R50·R51)으로 한다. 예전 이 규칙의 "건드리지 않은 유형은 이름이 바뀌어도 원래 id로 보낸다"는 AC-R50으로 옮겼다.
- **AC-R31** 삭제 확인(제목 "Action 삭제", 상세 팝업의 "삭제" 버튼으로 연다 — AC-R52): 문구 "\"<진행사항, 없으면 Next Action>\" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다."(그 Action에 Comment가 N(≥1)건 있으면 끝에 " 연결된 Comment <N>건도 함께 삭제됩니다." — 건수는 화면의 Comment 목록 기준, CM-R16·CM-080), 버튼 "취소"·위험 버튼 "삭제". 상세 팝업 위에 겹친 대화상자다(UI-R27·R28). 확인해야 삭제 요청을 보낸다. 성공하면 확인 대화상자와 상세 팝업을 모두 닫고 알림 "Action이 삭제되었습니다.", 목록과 요약 바 Next Action이 새로 읽힌다. "취소"·Esc는 확인 대화상자만 닫고 상세 팝업은 그대로다. 실패하면 확인 대화상자를 닫고 상세 팝업 안 오류 배너(서버 문구)를 보이며 상세 팝업은 열린 채다. (2026-11-16 변경: 표의 "삭제" 버튼 → 상세 팝업, 실패 표시는 탭 위 배너 → 상세 팝업 안 배너 — 확정 Q8)
- **AC-R32** 게이트웨이(`gateway/http`): `actions.create` = `POST /deals/{code}/actions` 본문 snake_case(`action` ← 진행사항, `next_action`, `due_date`(빈 값은 null), `comment`(입력 그대로, 빈 값 "" — CM-R14), `action_type` 선택 객체 하나 — id와 name을 함께 보내지 않음), 텍스트를 다듬거나 자르지 않음, `acted_at`·담당자 없음, `status_changes`는 있을 때만(각 항목에 자기 resolution만), `close_previous_next_action_id`·`delete_license_contracts`·`acted_on`(ISO 날짜)은 값이 있을 때만. `actions.update` = `PUT /deal-actions/{id}` 내용 칸과 `acted_on`(값이 있을 때만, ISO 날짜, 2026-11-13 추가)(memo·comment 없음, CM-R17). `actions.remove` = `DELETE /deal-actions/{id}`(204면 값 없이 끝). `actions.list`(조건 없음) = `GET /deals/{code}/actions` 쿼리 없이, `offset`·`limit` 없음, 응답 `items`를 매핑. 응답 매핑: `action` → 진행사항, `action_type` → 유형 이름·`typeId`, null 값은 null 그대로, 담당자는 역할·퇴사 표기 포함, 텍스트 가공 없음. `memo`는 없다. 오류는 서버 문구 그대로(PL-R39).
- **AC-R33** Fake 게이트웨이(`test/fake/gateway/actions.ts`)는 등록·수정·삭제에서 서버와 같은 규칙·판정 순서·이력을 따른다. 서버와 달랐던 두 곳은 **Fake를 서버 동작에 맞춘다(2026-11-10 결정)**: 진행사항·Next Action에 NUL 문자가 있으면 AC-R3 ①의 422 `invalid-value` "<진행사항|Next Action>에는 NUL 문자를 쓸 수 없습니다", 달력 날짜가 아닌 Due Date는 AC-R2의 422 `request-validation`이다("Due Date를 입력하세요."가 아님). 화면은 이런 값을 보내지 않는다. 수행일(등록 AC-R34~R36, 수정 AC-R45·R46)도 서버와 같은 결정·판정 순서·문구·이력을 따른다(Fake 시계의 업무 날짜 기준).
- **AC-R40** 수행일 칸(추가 팝업): 라벨 "수행일", 공통 `DateInput`(UI-R1~R11). 처음 값은 팝업을 연 때의 오늘(`useToday`, TM-R12)이다. 안내 문단 바로 아래, "Status · Forecast · 유형" 줄 위에 둔다. 시각 입력 칸은 없다. 상세 팝업의 수행일 인라인 편집은 AC-R47·R51. (2026-11-13 변경: 수정 팝업에도 있었다. 2026-11-16 변경: 수정 팝업 폐지)
- **AC-R41** 수행일 화면 검증(추가 팝업, AC-R24의 첫 단계, 위에서부터 첫 위반만): 비면 "수행일을 입력하세요.", 덜 쳤거나 틀린 날짜는 `DateInput` 문구(UI-R7), 제출 때 오늘(`useToday`)보다 뒤면 "수행일은 오늘 이후로 지정할 수 없습니다.", Deal 등록일(Deal `createdAt` 앞 10자, 서버 오프셋 벽시계 날짜 TM-R14)보다 앞이면 "수행일은 Deal 등록일(<YYYY-MM-DD>) 이전으로 지정할 수 없습니다.", 이전 Next Action 종료를 실제로 보낼 상태(AC-R26 체크가 켜져 있고 유효)에서 기준 행 수행일보다 앞이면 "이전 Next Action의 수행일(<YYYY-MM-DD>)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다.". 문구는 칸 아래, 포커스는 수행일 칸, 요청하지 않는다. 체크를 끄면 마지막 문구 없이 저장할 수 있다. 서버 422(AC-R35·R36)는 AC-R28처럼 팝업 안 오류 배너다. 상세 팝업 인라인 편집은 AC-R47.
- **AC-R42** 수행일 보내기(추가 팝업): 제출 때 수행일이 오늘(`useToday`)과 같으면 `acted_on`을 보내지 않고(서버가 오늘로 정함), 다르면 ISO 날짜로 보낸다. 등록 성공 뒤 목록은 서버가 준 `acted_on`을 보이고 서버 순서를 그대로 따른다(AC-R21).
- **AC-R43** 같은 수행일의 순서: 수행일이 같으면 id가 큰 Action(나중에 등록한 것)이 더 최근이다. 기준 행(RK-R1), 기본 목록(AC-R18), 수행일 내림차순 정렬(NA-R18)이 이 순서를 따른다. 오름차순 정렬은 id 오름차순이다. 화면 계산(`latestWithNextAction`)과 Fake도 같다.
- **AC-R44** 기존 데이터 변환(리비전 `b4d7e2a9c613`, SC-R20): 기존 Action의 수행일은 저장된 수행 일시를 업무 시간대(서버 OS 로컬, TM-R4)로 바꾼 날짜다. 예(Asia/Seoul): `2026-11-10T23:59:59+09:00` → 2026-11-10, `2026-11-10T15:30:00Z` → 2026-11-11. 행 수는 그대로이고 시각만 버린다(2026-11-13 사용자 승인). downgrade는 `acted_at`을 수행일의 업무 시간대 00:00으로 되살리며, 원래 시각은 복원되지 않는다.
- **AC-R47** 상세 팝업 수행일 인라인 편집의 검증·보내기(2026-11-13 추가, 2026-11-16 수정 팝업 → 상세 팝업 인라인으로 변경): 검증은 AC-R41에서 이전 Next Action 비교를 뺀 단계만 위에서부터 한다 — 빈 값 "수행일을 입력하세요." → 덜 쳤거나 틀린 날짜는 `DateInput` 문구(UI-R7)이고 저장하지 않음(DD-R31) → 저장 때 오늘(`useToday`)보다 뒤 "수행일은 오늘 이후로 지정할 수 없습니다." → Deal 등록일(Deal `createdAt` 앞 10자, TM-R14)보다 앞 "수행일은 Deal 등록일(<YYYY-MM-DD>) 이전으로 지정할 수 없습니다.". 기준 행·다른 Action·종료일과의 비교는 하지 않는다(AC-R46). 문구는 그 칸 아래에 보이고 편집이 열린 채이며 요청을 보내지 않는다. 그 Action의 원래 수행일과 같으면 요청 없이 편집을 닫고(DD-R31), 다르면 `acted_on`(ISO 날짜)을 실어 보낸다(AC-R50). 성공하면 알림 "Action이 수정되었습니다."(AC-R28), 팝업 수행일이 새 날짜이고, 목록·요약 바 Next Action을 다시 읽어 그 행이 바뀐 수행일 자리(서버 순서)에 보인다. 서버 422(AC-R45)는 그 칸 아래 오류 배너다.
- **AC-R48** 행 열기(2026-11-16): 표의 각 행은 누를 수 있다(포인터 모양). 행을 누르거나, Tab으로 행에 포커스를 둔 채(행마다 한 번 멈춤) Enter·Space를 누르면 그 Action의 상세 팝업(AC-R49)이 열린다(Space로 화면이 스크롤되지 않는다). 행 안의 상태 칸 버튼("종료(수행)"·"종료(미수행)"·"Open으로", NA-R21)을 누르거나 그 버튼에서 Enter·Space를 누르면 상태 변경만 하고 상세 팝업은 열리지 않는다. 모든 역할(user 포함)이 연다. 상세 팝업이 닫히면 포커스는 그 행으로 돌아간다(UI-R26, 삭제로 행이 사라진 경우는 제외). 행 마지막 칸의 Comment 아이콘 버튼(CM-R40)은 상태 버튼처럼 행 열기와 따로 처리된다. 같은 상세 팝업을 열되 포커스를 Comment 입력 칸(user는 Comment 영역)으로 보낸다. 주소 `?tab=actions&action=<id>`로 들어오면 그 Action 팝업을 연다(CM-R37).
- **AC-R49** 상세 팝업(2026-11-16, 모달 `wide`, 제목 "Action 상세"): 키·값 줄로 위에서부터 수행일(`YYYY-MM-DD`), 담당자(사용자 표기, 퇴사자 "<이름>(퇴사)"), 등록 시점 Status·Forecast(스냅숏 배지 둘, 현재 Deal 값과 다를 수 있음), 유형(현재 이름), 진행사항(줄바꿈 그대로), Next Action, Due Date(표와 같은 판정으로 기한초과면 RK-R18 배지), Next Action 상태(라벨 Open·종료(수행)·종료(미수행), 종료면 뒤에 " · 종료일 <YYYY-MM-DD>", Next Action이 없으면 "—")를 보이고, 맨 아래에 Comment 영역(CM-R41)이 있다. 빈 값은 "—". 담당자·등록 시점 Status·Forecast는 누구에게나 읽기 전용이다. Next Action 상태는 라벨 옆에 표의 상태 칸과 같은 상태 버튼이 있어 팝업에서도 바꿀 수 있다(AC-R54, 확정 Q4). 아래 버튼: 수정 권한(AC-R50)이 있으면 위험 스타일 "삭제"(AC-R52)와 "닫기". `canWrite`이지만 그 Action을 바꿀 수 없는 사람(다른 sales)에게는 "삭제"가 꺼진 채 title "본인 Action 또는 admin만 삭제할 수 있습니다."이고 팝업 위쪽에 안내 "본인 Action 또는 admin만 수정·삭제할 수 있습니다."가 보인다(확정 Q6). user에게는 "삭제"와 안내가 없고 "닫기"만 있다. 열면 포커스는 UI-R26대로 간다. "닫기"·Esc는 팝업을 닫는다(편집 중인 칸이 있으면 Esc는 그 칸만 닫음, AC-R50). 팝업이 보이는 값은 연 Action의 최신 서버 값(인라인 저장 응답 또는 목록 재조회)이고, 저장 뒤 그 Action이 검색 조건에서 빠져도 팝업은 닫히지 않는다. (2026-11-17 Memo 줄 → Comment 영역)
- **AC-R50** 상세 팝업 인라인 수정 공통(2026-11-16): 수정 권한 = `canWrite`이고 `canEditAction`(AC-R17: admin은 모든 Action, sales는 본인 Action)이다. 권한이 있으면 수행일·유형·진행사항·Next Action·Due Date 값이 Deal 상세 인라인 편집(DD-R31)처럼 누를 수 있는 값 버튼(접근 이름 "<칸 이름> 수정", Next Action과 Due Date는 한 버튼 "Next Action · Due Date 수정")이고, 권한이 없으면 값만 보인다. 편집 열기(누름·Enter·Space)·입력기 포커스·Enter와 포커스 이동 저장·값이 그대로면 요청 없음·실패 시 칸 아래 오류 배너와 편집 유지는 DD-R31을 따른다. 칸 하나를 저장하면 `PUT /deal-actions/{id}`(AC-R13)를 한 번 보낸다: 바꾼 칸만 새 값이고 나머지 내용 칸(`action`·`next_action`·`due_date`)은 팝업이 보이는 현재 값 그대로, `action_type`은 유형 칸을 저장할 때가 아니면 그 Action의 원래 유형 `{id}`다(팝업을 연 뒤 admin이 유형 이름을 바꿔도 원래 id라 새 유형이 생기지 않음 — 예전 AC-R30에서 옮김). `acted_on`은 수행일 칸을 다른 날짜로 저장할 때만 싣는다(AC-R47). 내용이 바뀐 저장마다 Deal History "수정" 이력이 1건씩 남는다(AC-R11). 성공하면 그 칸 편집을 닫고 팝업에 서버 응답 값을 보이며, 탭 알림 "Action이 수정되었습니다."(AC-R28)와 함께 목록·요약 바 Next Action·Deal History를 다시 읽는다. 팝업은 열린 채다. 저장 중(요청 진행 중)에는 "닫기"·"삭제"가 꺼지고 Esc를 무시한다. 편집 중인 칸이 있을 때 Esc는 그 칸 입력을 버리고 편집만 닫으며 팝업은 열려 있다(다음 Esc가 팝업을 닫음). 서버 거절(403 남의 Action, 404 "Action을 찾을 수 없습니다.", 422)은 그 칸 아래 오류 배너(서버 문구)이고 입력을 유지한다. (2026-11-17 Memo 칸 삭제)
- **AC-R51** 칸별 편집기와 화면 검증(2026-11-16, 걸리면 그 칸 아래 문구, 편집 유지, 요청 없음): (2026-11-17 Memo 칸 삭제)
  - 수행일: `DateInput`(UI-R1~R11, 처음 값 그 Action의 수행일). 검증·보내기는 AC-R47.
  - 유형: 콤보박스(UI-R18~R21, 서버 순서 CL-R3의 유형 후보, 부분 일치·대소문자 무시, 처음 값 현재 이름). 후보를 고르면 즉시, 직접 입력은 Enter·포커스 이동으로 저장한다. 공백뿐이면 "유형을 입력하세요.", 51자 이상(코드 포인트)이면 "유형은 50자 이내로 입력하세요.". 목록을 읽었고 입력이 어떤 유형과도(대소문자 무시) 같지 않으면 편집 중 안내 "목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다."(AC-R25). 보낼 때 CL-R16(같은 이름이 있으면 `{id}`, 없으면 `{name}`). 현재 이름과 같으면 요청 없음.
  - 진행사항: 여러 줄 칸(처음 값 현재 값). Enter(Shift 없이, 한글 조합 중이 아님)는 저장, Shift+Enter는 줄바꿈, 포커스 이동은 저장(확정 Q3). 진행사항을 비웠고 Next Action도 비어 있으면 "진행사항 또는 Next Action을 입력하세요.".
  - Next Action·Due Date(한 묶음, 확정 Q2): 편집을 열면 Next Action 한 줄 입력(접근 이름 "Next Action")과 Due Date `DateInput`(접근 이름 "Due Date")이 함께 열리고 Next Action 칸에 포커스가 간다. 묶음 밖으로 포커스가 나가거나 어느 칸에서든 Enter를 누르면 두 값을 한 요청으로 저장한다(묶음 안 두 칸 사이 이동·달력 버튼 이동은 저장이 아님). Next Action을 모두 지우면 Due Date도 비운다. 검증(위에서부터): Next Action과 진행사항이 모두 비면 "진행사항 또는 Next Action을 입력하세요." → Next Action이 있는데 Due Date가 비면 "Due Date를 입력하세요.", 덜 쳤거나 틀린 Due Date는 `DateInput` 문구(UI-R7) → Next Action 없이 Due Date가 있으면 "Next Action 없이 Due Date를 입력할 수 없습니다.". 두 값이 그대로면 요청 없음. yyyymmdd로 친 Due Date는 ISO 날짜로 보낸다. 저장 결과의 Next Action 상태는 AC-R14(비우면 상태 없음, 없던 Next Action을 채우면 Open, 고치면 그대로)다.
- **AC-R52** 상세 팝업 삭제(2026-11-16): "삭제" 버튼은 상세 팝업 아래쪽에만 있다(표에는 없음). 수정 권한(AC-R50)이 있을 때만 켜지고 다른 sales에게는 꺼진 채 보이며 user에게는 없다(AC-R49). 누르면 삭제 확인(AC-R31)이 상세 팝업 위에 열리고, 확인해야 `DELETE /deal-actions/{id}`(AC-R16)를 보낸다.
- **AC-R53** 표 칸 폭(2026-11-16): Action 목록 표의 진행사항·Next Action 칸은 최소 폭 `40em`(한글 약 40자가 한 줄에 들어가는 폭)이고 최대 폭 제한이 없으며(공통 `.dd-table td.wrap`의 280px 제한을 받지 않음) 긴 글은 칸 안에서 줄을 바꾼다. 수행일·유형·Due Date·상태 칸은 줄바꿈하지 않는다(`white-space: nowrap`). 화면이 좁으면 표 전체가 가로로 스크롤된다(`dd-scroll`). 다른 표(Deal History 등)의 칸 폭은 바뀌지 않는다. (확정 Q7: 40em, 사용자 변경)
- **AC-R54** 상세 팝업의 Next Action 상태 변경(2026-11-16, 확정 Q4): 상세 팝업의 Next Action 상태 줄은 라벨(AC-R49)과 함께 표의 상태 칸과 같은 상태 버튼(NA-R21: 지금 상태를 뺀 나머지 — "종료(수행)"·"종료(미수행)"·"Open으로")을 보인다. 버튼은 표의 상태 칸과 같은 사람(쓰기 권한이 있고 admin이거나 본인 Action의 sales)에게만 보이고 다른 sales와 `user`는 라벨만 본다. 동작·요청·오류·캐시 무효화는 표와 같다(NA-R22~R24): "종료(수행)"·"종료(미수행)"은 `NextActionCloseDialog` 종료 대화상자(팝업 위에 겹침, UI-R27·R28)를 거쳐 입력한 Comment(빈 값 가능, NA-R22·CM-R43)로 `PUT /deal-actions/{id}/next-action-status`를 보내고, "Open으로"는 대화상자 없이 Comment `""`로 바로 보낸다. 성공하면 대화상자만 닫고 상세 팝업은 열린 채 새 상태·종료일과 Comment 영역의 새 Comment를 보이며 표의 상태 칸도 같은 값이다. 실패하면 종료 대화상자는 서버 문구를 안에 보이며 입력한 Comment를 유지하고, "Open으로" 실패는 상세 팝업 안 오류 배너에 서버 문구를 보인다. 요청이 진행 중이면 표·팝업의 모든 상태 버튼과 "닫기"·"삭제"가 꺼진다. Next Action이 없는 Action은 상태 줄이 "—"이고 버튼이 없다. 종료 대화상자의 "취소"·Esc는 그 대화상자만 닫는다.

### 2.4 상태와 전이

Action의 Next Action 상태(이 문서가 정하는 전이만, 상태 변경 API의 전이는 NA-R2·NA 2.4):

| 현재 | 행동 | 다음 |
| --- | --- | --- |
| (없음) | 등록: Next Action 있음 / 없음 | `open` / null |
| null(진행사항만) | 수정: Next Action 채움 | `open` |
| `open`·`done`·`not_done` | 수정: Next Action 비움 | null(종료 시각도 null) |
| `open`·`done`·`not_done` | 수정: 그 밖의 내용 변경·수행일 변경 | 그대로(종료 시각 그대로) |
| `open`(기준 행) | 다음 Action 등록 + `close_previous_next_action_id` | `done`(종료일 = 오늘) |
| `done`·`not_done`(기준 행) | 다음 Action 등록 + `close_previous_next_action_id` | 그대로 |
| (모든 상태) | 삭제 | (없음) |

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /deals/{code}/actions`, `GET /deal-actions/{action_id}` | 401 | 가능 | 가능 | 가능 |
| `POST /deals/{code}/actions` | 401 | 403 읽기 전용 문구 | 모든 Deal 가능 | 모든 Deal 가능 |
| 등록 때 이전 Next Action 종료 | — | — | 기준 행 담당자 본인만(아니면 403) | 모두 |
| `PUT /deal-actions/{action_id}`(수행일 변경 포함) | 401 | 403 읽기 전용 문구 | 본인 Action만(아니면 403) | 모두 |
| `DELETE /deal-actions/{action_id}` | 401 | 403 읽기 전용 문구 | 본인 Action만(아니면 403) | 모두 |
| 화면 Actions 탭 | `/login`으로 | 표·상세 팝업 보기만(추가 버튼·인라인 편집·삭제 버튼 없음) | 추가, 상세 팝업에서 본인 Action 인라인 수정·삭제(남의 Action은 보기만, 삭제 꺼짐) | 추가, 상세 팝업에서 모든 Action 인라인 수정·삭제 |

조회는 업무 조회, 등록·수정·삭제는 업무 쓰기(PL-R2, PL-R6, CSRF PL-R9)다.

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| POST `/deals/{code}/actions` | `DealActionCreateRequest` `{action_type: CatalogChoiceRequest, action?: str, next_action?: str, due_date?: date\|null, comment?: str, status_change?: ActionStatusChangeRequest\|null, status_changes?: ActionStatusChangeRequest[]\|null (≤2), close_previous_next_action_id?: int\|null, delete_license_contracts?: bool, acted_on?: date\|null}` | 201 `DealActionResponse`, `Location` | 401, 403 `forbidden`·`csrf`, 404 `not-found`, 409 `invalid-state`, 422 `invalid-value`·`request-validation` |
| GET `/deals/{code}/actions` | (검색 쿼리는 NA-R11~R19) | 200 `DealActionList` `{items: DealActionResponse[]}` | 401, 404, 422(NA-R19, NA-R20) |
| GET `/deal-actions/{action_id}` | — | 200 `DealActionResponse` | 401, 404, 422 |
| PUT `/deal-actions/{action_id}` | `DealActionUpdateRequest` `{action_type, action?, next_action?, due_date?, acted_on?: date\|null}` | 200 `DealActionResponse` | 401, 403, 404, 422 `invalid-value`·`request-validation` |
| DELETE `/deal-actions/{action_id}` | — | 204 | 401, 403, 404, 422 |

- `ActionStatusChangeRequest` = `{change: CodeChange, resolution?: ResolutionRequest|null}`(DD 2.6). 모든 본문은 모르는 필드를 거부한다.
- OpenAPI: 등록·수정 요청의 `action`·`next_action`·`comment`에 `maxLength`가 없고 `action`·`next_action`·`due_date`는 required가 아니며 `action_type`은 required(`CatalogChoiceRequest` 참조)다. 서버 필드(`acted_at`·`actor_user_id`·`actor`)가 없다. `status_change(s)`·`close_previous_next_action_id`는 등록 요청에만 있다. `acted_on`(format date, nullable, required 아님)은 등록·수정 요청 모두에 있다(수정은 2026-11-13 추가, 하위 호환 추가 — 보내지 않는 기존 클라이언트의 동작은 같다). `ActionType` enum 스키마는 없다. 응답 `action_type`은 `{id, name}`, nullable 다섯 필드는 required + null 허용이다.

### 2.7 화면 동작

AC-R21~AC-R29, AC-R31~AC-R33, AC-R40~AC-R43, AC-R47~AC-R54(AC-R30 폐지).

### 2.8 오류와 메시지

| 상황 | 상태·kind | detail(문구) |
| --- | --- | --- |
| 진행사항·Next Action 모두 비어 있음 | 422 `invalid-value` | 진행사항 또는 Next Action을 입력하세요. |
| Next Action은 있는데 Due Date 없음 | 422 `invalid-value` | Due Date를 입력하세요. |
| Next Action 없이 Due Date | 422 `invalid-value` | Next Action 없이 Due Date를 입력할 수 없습니다. |
| 텍스트에 NUL | 422 `invalid-value` | <진행사항\|Next Action>에는 NUL 문자를 쓸 수 없습니다 |
| Comment NUL | 422 `invalid-value` | CM 2.8 |
| 없는 유형 id / 유형 이름 규칙 | 422 `invalid-value` | 선택한 유형이 없습니다. 목록에서 다시 선택하세요. / CL 2.8 |
| 동반 변경: 없는 코드·매출 없음·선택 없음 | 422 `invalid-value` | 존재하지 않는 코드입니다. / DD 2.8 |
| 동반 변경: 두 번째가 첫 변경을 뒤집음 | 422 `invalid-value` | 먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요. |
| 요청 형식 오류(서버 필드·모르는 키·유형 형식·동반 변경 형식·close id 형식·날짜 형식·수행일 형식) | 422 `request-validation` | 요청 형식이 올바르지 않습니다 |
| 없는 Deal·형식이 틀린 code | 404 `not-found` | Deal을 찾을 수 없습니다. |
| 없는 Action | 404 `not-found` | Action을 찾을 수 없습니다. |
| 수행일이 오늘 이후(등록·수정) | 422 `invalid-value` | 수행일은 오늘 이후로 지정할 수 없습니다. |
| 수행일이 Deal 등록일 이전(등록·수정) | 422 `invalid-value` | 수행일은 Deal 등록일(<YYYY-MM-DD>) 이전으로 지정할 수 없습니다. |
| 이전 Next Action보다 앞선 수행일로 종료(등록만) | 422 `invalid-value` | 이전 Next Action의 수행일(<YYYY-MM-DD>)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다. |
| 수행일 빈 값(화면, 추가·수정) | — | 수행일을 입력하세요. |
| 이전 Next Action이 기준 행이 아님 | 409 `invalid-state` | 이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요. |
| 남의 기준 행 종료 | 403 `forbidden` | 본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다. |
| 남의 Action 수정 / 삭제 | 403 `forbidden` | 본인 Action 또는 admin만 수정할 수 있습니다. / 본인 Action 또는 admin만 삭제할 수 있습니다. |
| user의 등록·수정·삭제 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) |
| 발급 계약 있는 Deal의 Won 이탈 | 409 `invalid-state` | LC-R8 문구 |
| 상세 팝업: 바꿀 수 없는 Action(화면, 다른 sales) | — | 본인 Action 또는 admin만 수정·삭제할 수 있습니다. |

화면 문구: AC-R21~AC-R29, AC-R31, AC-R41, AC-R47, AC-R49~AC-R52. 서버 문구 표시는 PL-R37.

## 3. Business use case

### AC-UC1 Action 등록
- 행위자: sales·admin
- 사전 조건: Deal 상세 Actions 탭
- 기본 흐름: "Action 추가" → (이전 Update 확인·채우기) → 유형·진행사항·Next Action·Due Date·Comment 입력 → "등록" → `POST /deals/{code}/actions` → 201, 팝업 닫힘, 알림, 목록 맨 위·요약 바 갱신(AC-R1~R5, R10~R12, R23~R28)
- 대안: Status·Forecast를 함께 바꿈(AC-R6, AC-R27), 이전 Next Action을 종료(수행)로 닫음(AC-R7, AC-R26), 새 유형 이름 입력(AC-R5, AC-R25)
- 예외: 화면 검증(AC-R24), 입력 422, 동반 변경 422, 409(기준 행 바뀜·계약), 403(남의 기준 행·user), 404(Deal) — 아무것도 저장 안 됨(AC-R9)
- 결과: Action 1건, 이력, (동반 변경이면) Deal 변경과 그 이력, (종료면) 이전 행 종료(수행)

### AC-UC2 Action 수정
- 행위자: Action 담당자 sales, admin
- 사전 조건: 그 Action의 상세 팝업이 열려 있고 수정 권한이 있음(AC-R48~R50)
- 기본 흐름: 고칠 값(수행일·유형·진행사항·Next Action · Due Date)을 누름 → 그 자리 입력기에서 고침 → Enter 또는 포커스 이동 → `PUT /deal-actions/{id}`(그 칸만 바뀐 내용) → 200, 팝업에 새 값, 알림 "Action이 수정되었습니다."(AC-R13~R15, AC-R50·R51)
- 대안: 값이 그대로면 요청 없음(DD-R31), 공백만 다른 값은 서버가 변경 없음으로 처리(AC-R14). Esc로 그 칸 편집만 취소. 수행일을 고침(AC-UC6)
- 예외: 화면 검증(AC-R51), 남의 Action 403, 없는 Action 404, 입력 422, 수행일 범위 422(AC-R45), user 403 — 칸 아래 오류, 편집 유지
- 결과: 그 칸(묶음이면 Next Action·Due Date)만 바뀌고 담당자·스냅숏 그대로, 이력 1건, 팝업은 열린 채

### AC-UC2b 상세 팝업에서 Next Action 상태 변경
- 행위자: Action 담당자 sales, admin
- 사전 조건: 그 Action의 상세 팝업이 열려 있고 Next Action이 있으며 상태를 바꿀 수 있음(AC-R54)
- 기본 흐름: 상태 줄의 "종료(수행)"·"종료(미수행)" → 종료 대화상자 → "종료"(또는 "Open으로"는 바로) → `PUT /deal-actions/{id}/next-action-status`(NA-R2~R8) → 팝업에 새 상태·종료일·새 Comment
- 예외: 같은 상태 409, 남의 Action 403, 없는 Action 404 — 대화상자 또는 팝업 안 오류
- 결과: 표의 상태 칸과 같은 상태, 팝업은 열린 채

### AC-UC3 Action 삭제
- 행위자: Action 담당자 sales, admin
- 사전 조건: 그 Action의 상세 팝업이 열려 있음(AC-R48·R49)
- 기본 흐름: 팝업의 "삭제" → 확인 대화상자 → "삭제" → `DELETE /deal-actions/{id}` → 204, 두 팝업 닫힘, "Action이 삭제되었습니다."(AC-R16, AC-R31, AC-R52)
- 대안: 확인 대화상자에서 "취소"·Esc — 상세 팝업으로 돌아감
- 예외: 남의 Action 403, 없는 Action 404, user 403 — 상세 팝업 안 오류 배너
- 결과: Action이 사라지고 이력 "삭제", Deal의 Next Action 기준 행이 다시 계산됨(AC-R12)

### AC-UC4 Action 목록·한 건 보기
- 행위자: 로그인한 모든 역할
- 기본 흐름: Actions 탭 → `GET /deals/{code}/actions` → 최신순 6열 표(AC-R18, AC-R21) → 행을 누르면 상세 팝업(AC-R48·R49), 또는 `GET /deal-actions/{id}`(AC-R19)
- 예외: 없는 Deal 404, 없는 Action 404
- 결과: 그 Deal의 Action 전부, 행을 열면 그 Action의 모든 항목(담당자·등록 시점 Status·Forecast·Next Action 상태와 그 Action의 Comment 포함)

### AC-UC5 지난 날짜로 Action 등록
- 행위자: sales·admin
- 사전 조건: Deal 상세 Actions 탭, 며칠 전에 한 일을 이제 기록한다
- 기본 흐름: "Action 추가" → 수행일 칸(오늘)을 지난 날짜로 바꿈 → 내용 입력 → "등록" → `POST /deals/{code}/actions`(`acted_on`) → 201, 목록에서 그 날짜 자리에 보임(AC-R34, AC-R38, AC-R40~R43)
- 대안: 오늘 그대로 두면 지금 시각으로 기록(AC-R34). 이전 Next Action을 함께 닫음(같은 날 이후만, AC-R36). Status·Forecast를 함께 바꿈(요청 시점 기준, AC-R37)
- 예외: 빈·틀린·미래·등록일 이전 수행일(화면 AC-R41, 서버 422 AC-R35), 기준 행보다 앞선 수행일로 종료(422 AC-R36) — 아무것도 저장 안 됨(AC-R9)
- 결과: Action 1건(`acted_on` = 그 날짜), 더 늦은 수행일의 Action이 없으면 Deal의 Next Action·최종 업데이트가 이 Action을 가리킴

### AC-UC6 Action 수행일 고치기(2026-11-13 추가)
- 행위자: Action 담당자 sales, admin
- 사전 조건: 그 Action의 상세 팝업이 열려 있고 수정 권한이 있음(AC-R50). 수행일을 잘못 넣었거나 오늘로 등록했지만 실제로는 며칠 전에 한 일이다
- 기본 흐름: 상세 팝업의 수행일 값을 누름 → 편집 칸(그 Action의 수행일)을 다른 날짜로 바꿈 → Enter 또는 포커스 이동 → `PUT /deal-actions/{id}`(`acted_on`) → 200, "Action이 수정되었습니다.", 목록에서 바뀐 날짜 자리에 보이고 요약 바 Next Action·최종 업데이트가 다시 계산됨(AC-R45~R47)
- 대안: 수행일을 원래 날짜로 두면 요청 없이 편집만 닫힘(AC-R47). 다른 칸 저장에는 `acted_on`이 없음(AC-R50). 기준 행보다 앞선 날짜도 허용(AC-R46)
- 예외: 빈·틀린·미래·등록일 이전 수행일(화면 AC-R47, 서버 422 AC-R45), 남의 Action 403, 없는 Action 404 — 아무것도 저장 안 됨
- 결과: 그 Action의 `acted_on`과 `updated_at`만 (내용을 고쳤으면 내용도) 바뀌고, 이력 1건(수행일 부분 포함), 담당자·스냅숏·Next Action 상태·종료일·Deal `updated_at`은 그대로

## 4. BDD 테스트 케이스

요청자 예시: ROOT(admin), KIM(sales), LEE(sales), VIEWER(user). 기본 Deal 예: Owner KIM, Status 기회발굴(prospecting)·Forecast Pipeline, 금액 150,000,000, Expected Close 2026-06-30. 종결 Deal 예: 계약완료·Won, 금액 777, Expected Close 2026-09-01. 매출 답 예: 900,000,000·2026-10-20. 기본 Action 입력: 유형 `{name: "미팅"}`(기본 유형), 진행사항 "킥오프 미팅", Next Action "요구사항 문서 전달", Due 2027-01-15(Comment는 Action 입력에 없고 별도로 등록, CM) — 요약 "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)". backend 케이스는 기본 코드·기본 유형을 넣은 Fake UoW로 유스케이스를 부르는 단위 테스트(application·domain)와 Fake 유스케이스로 라우터·스키마를 부르는 web 단위 테스트다. frontend 케이스는 Fake 게이트웨이(시드 Deal·Action·유형·사용자)를 쓰는 Vitest다.

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| AC-001 | sales가 Action을 등록하면 201과 Location이고 수행일·담당자·스냅숏을 서버가 정한다 | AC-R1, AC-R4, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `domain/test_deal_action_entity.py`, `web/test_deal_action_routes.py` |
| AC-002 | 등록 응답은 문서화된 14개 키를 가지고(`memo` 없음) 유형은 {id, name}이다 | AC-R20, AC-UC1 | backend | `web/test_deal_action_response_nullable.py`, `web/test_deal_action_routes.py` |
| AC-003 | 텍스트 앞뒤 공백을 지워 저장하고 지난 Due Date도 받는다 | AC-R3, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py` |
| AC-004 | 진행사항·Next Action은 길이 상한 없이 그대로 저장된다 | AC-R2, AC-R3, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `web/test_deal_action_requests.py` |
| AC-005 | (폐기 2026-11-17) Memo 기본값 "" — CM-027이 대신함 | AC-R2 | backend | — |
| AC-006 | 진행사항만 Action은 Next Action·Due·상태·종료 시각이 모두 null이다 | AC-R3, AC-R4, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `domain/test_action_history.py`, `domain/test_deal_action_entity.py`, `web/test_deal_action_requests.py`, `web/test_deal_action_response_nullable.py`, `features/deals/detail/ActionsTab.nextActionStatus.test.tsx`, `gateway/contract/actionsStatus.contract.ts` |
| AC-007 | Next Action만 Action은 진행사항이 null이고 상태가 Open이다 | AC-R3, AC-R4, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `domain/test_action_history.py`, `domain/test_deal_action_entity.py`, `web/test_deal_action_requests.py`, `web/test_deal_action_response_nullable.py`, `features/deals/detail/ActionsTab.nextActionStatus.test.tsx`, `gateway/contract/actionsStatus.contract.ts` |
| AC-008 | 진행사항·Next Action이 모두 비면 422이고 아무것도 저장되지 않는다 | AC-R3, AC-R9, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `web/test_deal_action_requests.py`, `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| AC-009 | Next Action이 있는데 Due Date가 없으면 422 "Due Date를 입력하세요."다 | AC-R3, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py`, `web/test_deal_action_requests.py`, `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| AC-010 | Next Action 없이 Due Date만 있으면 422다 | AC-R3, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_content.py` |
| AC-011 | 내용 검증은 NUL → 둘 다 빔 → Due 필수 → Due 금지 순서로 첫 위반만 알린다 | AC-R3, AC-UC1 | backend | `domain/test_action_content.py` |
| AC-012 | 서버가 정하는 필드·`memo` 키·모르는 필드·날짜가 아닌 Due를 보내면 422 request-validation이다 | AC-R2, AC-UC1 | backend | `web/test_deal_action_requests.py` |
| AC-013 | 없는 Deal·형식이 틀린 code는 입력이 잘못돼도 404가 먼저다 | AC-R8, AC-UC1 | backend | `application/test_register_deal_action.py` |
| AC-014 | user의 등록은 읽기 전용 403, 미인증은 401이다 | AC-R1, AC-R8, AC-UC1 | backend | `web/test_deal_action_routes.py` |
| AC-015 | Deal Owner가 아닌 sales도 Action을 등록할 수 있다 | AC-R1, AC-R17, AC-UC1 | backend | `application/test_register_deal_action.py` |
| AC-016 | 등록하면 Deal History에 "등록: <요약>" 1건이 요청 시각·요청자로 남고 요약에 Memo가 없다 | AC-R10, AC-R11, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_history.py` |
| AC-017 | 긴 요약은 이력에서만 1,000자로 잘리고 Action 원문은 그대로다 | AC-R11, AC-UC1 | backend | `application/test_register_deal_action.py`, `domain/test_action_history.py` |
| AC-018 | 등록해도 Deal 수정 시각은 그대로이고 Deal의 Next Action·최종 업데이트가 새 Action을 가리킨다 | AC-R12, AC-UC1 | backend | `application/test_register_deal_action.py` |
| AC-019 | 이름으로 새 유형을 고른 등록이 다른 이유로 거절되면 새 유형이 남지 않는다 | AC-R5, AC-R9, AC-UC1 | backend | `application/test_deal_action_type_choice.py` |
| AC-020 | 없는 Deal은 유형 오류보다 먼저 404이고 새 유형도 생기지 않는다 | AC-R5, AC-R8, AC-UC1 | backend | `application/test_deal_action_type_choice.py` |
| AC-021 | 유형 오류는 진행사항 오류보다 먼저 판정된다 | AC-R5, AC-R8, AC-UC1 | backend | `application/test_deal_action_type_choice.py` |
| AC-022 | 이력 요약의 유형 자리에는 고른(새로 만든) 유형 이름이 들어간다 | AC-R5, AC-R10, AC-UC1 | backend | `application/test_deal_action_type_choice.py`, `domain/test_action_history.py` |
| AC-023 | 계약완료로 바꾸며 등록하면 Deal이 종결되고 스냅숏은 변경 뒤 값이며 이력은 Deal 변경 다음 Action 등록 순서다 | AC-R4, AC-R6, AC-R11, AC-UC1 | backend | `application/test_register_deal_action_status_change.py` |
| AC-024 | 종결로 바꾸며 매출을 주지 않으면 422이고 Action·Deal·이력이 그대로다 | AC-R6, AC-R9, AC-UC1 | backend | `application/test_register_deal_action_status_change.py`, `domain/test_sync_sequence.py` |
| AC-025 | Forecast만 바꾸면 Status는 그대로이고 Deal 수정 시각이 요청 시각이 된다 | AC-R6, AC-UC1 | backend | `application/test_register_deal_action_status_change.py` |
| AC-026 | Won Deal을 되돌리며 함께 바꿀 값을 고르지 않으면 422, 고르면 그 값이 스냅숏이 된다 | AC-R6, AC-UC1 | backend | `application/test_register_deal_action_status_change.py` |
| AC-027 | 없는 코드로 바꾸려 하면 422 "존재하지 않는 코드입니다."이고 두 번째 항목 코드도 매출 판정보다 먼저 본다 | AC-R6, AC-R8, AC-UC1 | backend | `application/test_register_deal_action_status_change.py`, `application/test_register_deal_action_two_changes.py` |
| AC-028 | 현재와 같은 값으로 바꾸면 Deal은 그대로이고 Action만 남는다 | AC-R6, AC-UC1 | backend | `application/test_register_deal_action_status_change.py`, `application/test_register_deal_action_two_changes.py`, `domain/test_sync_sequence.py` |
| AC-029 | 내용 오류는 동반 변경보다 먼저 판정되어 Deal이 바뀌지 않는다 | AC-R8, AC-R9, AC-UC1 | backend | `application/test_register_deal_action_status_change.py`, `application/test_register_deal_action_two_changes.py` |
| AC-030 | Status와 Forecast 두 변경을 순서대로 적용하고 이력도 그 순서다 | AC-R6, AC-UC1 | backend | `application/test_register_deal_action_two_changes.py`, `domain/test_sync_sequence.py`, `web/test_deal_action_status_changes.py` |
| AC-031 | 두 번째 변경은 첫 변경을 적용한 상태로 판정한다(Won 되돌림 뒤 Status 이동) | AC-R6, AC-UC1 | backend | `application/test_register_deal_action_two_changes.py`, `domain/test_sync_sequence.py` |
| AC-032 | 두 번째 변경이 첫 변경 값을 뒤집으면 422 충돌 문구이고 아무것도 저장되지 않는다 | AC-R6, AC-R9, AC-UC1 | backend | `application/test_register_deal_action_two_changes.py`, `domain/test_sync_sequence.py` |
| AC-033 | 두 번째 변경이 실패하면 첫 변경도 저장되지 않는다 | AC-R6, AC-R9, AC-UC1 | backend | `application/test_register_deal_action_two_changes.py`, `domain/test_sync_sequence.py` |
| AC-034 | 동반 변경 형식이 틀리면 422 request-validation이고 null·빈 배열은 변경 없음이다 | AC-R6, AC-UC1 | backend | `domain/test_sync_sequence.py`, `web/test_deal_action_requests.py`, `web/test_deal_action_status_changes.py` |
| AC-035 | Action 스냅숏은 나중의 Deal 변경과 Action 수정에도 그대로다 | AC-R4, AC-R14, AC-UC1, AC-UC2 | backend | `application/test_register_deal_action_status_change.py`, `application/test_update_deal_action.py`, `domain/test_deal_action_entity.py` |
| AC-036 | 이전 Next Action id와 함께 저장하면 기준 행이 종료(수행)가 되고 한 번에 저장된다 | AC-R7, AC-UC1 | backend | `application/test_register_action_closes_previous.py`, `domain/test_deal_action_close_for_next_update.py`, `web/test_deal_action_close_previous_request.py` |
| AC-037 | 이전 Next Action 종료 줄 다음에 등록 줄이 같은 시각으로 남는다 | AC-R11, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-038 | 필드를 빼거나 null이면 이전 Next Action은 Open 그대로다 | AC-R7, AC-UC1 | backend | `application/test_register_action_closes_previous.py`, `web/test_deal_action_close_previous_request.py` |
| AC-039 | 기준 행이 아닌 id(더 최근 행 생김·다른 Deal·없는 id·Next Action 없음)는 409이고 아무것도 저장되지 않는다 | AC-R7, AC-R9, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-040 | 이미 종료된 기준 행은 건너뛰고 새 Action만 저장한다 | AC-R7, AC-UC1 | backend | `application/test_register_action_closes_previous.py`, `domain/test_deal_action_close_for_next_update.py` |
| AC-041 | 남의 기준 행이면 sales는 403, admin은 닫을 수 있다 | AC-R7, AC-R17, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-042 | 이전 Next Action 409 판정이 권한 403보다 먼저다 | AC-R7, AC-R8, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-043 | 내용 오류나 동반 변경 실패면 이전 Next Action은 Open 그대로다 | AC-R7, AC-R9, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-044 | 새 Action이 진행사항만이어도 이전 행을 닫을 수 있고 기준 행만 닫힌다 | AC-R7, AC-UC1 | backend | `application/test_register_action_closes_previous.py` |
| AC-045 | 이전 Next Action id 형식이 틀리면 422 request-validation이다 | AC-R2, AC-R7, AC-UC1 | backend | `web/test_deal_action_close_previous_request.py` |
| AC-046 | 담당자가 고치면 내용만 바뀌고 수행일·담당자·스냅숏은 그대로이며 이력 1건이 남는다 | AC-R13, AC-R14, AC-R11, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_action_history.py`, `domain/test_deal_action_entity.py` |
| AC-047 | 내용이 같은 수정은 200이지만 이력·수정 시각이 그대로이고 새 유형도 없다 | AC-R14, AC-UC2 | backend | `application/test_update_action_type_choice.py`, `application/test_update_deal_action.py`, `domain/test_deal_action_entity.py` |
| AC-048 | 수정 내용 규칙을 어기면 422이고 Action은 그대로다 | AC-R3, AC-R15, AC-UC2 | backend | `application/test_update_deal_action.py` |
| AC-049 | 수정도 길이 상한이 없고 1,000자 뒤에서만 달라진 수정도 이력 1건이다 | AC-R11, AC-R14, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_action_history.py` |
| AC-050 | 수정으로 Next Action을 비우면 Due·상태·종료 시각이 null이 된다 | AC-R14, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_deal_action_entity.py`, `gateway/contract/actionsStatus.contract.ts` |
| AC-051 | 진행사항만 Action에 Next Action을 채우면 Open이 된다 | AC-R14, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_deal_action_entity.py`, `gateway/contract/actionsStatus.contract.ts` |
| AC-052 | 종료된 Next Action의 내용을 고쳐도 종료 상태와 종료 시각은 그대로다 | AC-R14, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_deal_action_entity.py`, `gateway/contract/actionsStatus.contract.ts` |
| AC-053 | 유형만 바꿔도 이력 1건이 남고 새 이름이면 새 유형이 생기며 실패하면 남지 않는다 | AC-R5, AC-R14, AC-UC2 | backend | `application/test_update_action_type_choice.py`, `domain/test_action_history.py`, `domain/test_deal_action_entity.py` |
| AC-054 | 수정 본문에 동반 변경·이전 Next Action id·서버 필드가 있으면 422 request-validation이다 | AC-R13, AC-UC2 | backend | `web/test_deal_action_close_previous_request.py`, `web/test_deal_action_requests.py`, `web/test_deal_action_status_changes.py`, `web/test_deal_action_acted_on_request.py` |
| AC-055 | admin은 남의 Action을 고치고 담당자는 그대로이며 이력 변경자는 admin이다 | AC-R17, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_action_policy.py`, `domain/test_deal_action_entity.py` |
| AC-056 | 다른 sales의 수정은 본문이 잘못돼도 403이고 Action·이력이 그대로다 | AC-R15, AC-R17, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_action_policy.py`, `domain/test_deal_action_entity.py` |
| AC-057 | 없는 Action의 수정은 담당자·유형 확인보다 먼저 404다 | AC-R15, AC-UC2 | backend | `application/test_update_action_type_choice.py`, `application/test_update_deal_action.py` |
| AC-058 | user의 수정은 읽기 전용 403, 미인증은 401이다 | AC-R15, AC-UC2 | backend | `application/test_update_deal_action.py`, `domain/test_action_policy.py`, `domain/test_deal_action_entity.py`, `web/test_deal_action_routes.py` |
| AC-059 | 담당자가 지우면 204이고 행이 사라지며 이력에 요약과 "삭제"가 남는다(Comment 없는 Action이면 "삭제" 그대로) | AC-R11, AC-R16, AC-UC3 | backend | `application/test_delete_deal_action.py`, `domain/test_action_history.py` |
| AC-060 | 가장 최근 Action을 지우면 Deal Next Action이 이전 Action으로, 하나뿐이면 null이 된다 | AC-R12, AC-UC3 | backend | `application/test_delete_deal_action.py` |
| AC-061 | admin은 남의 Action을 지우고 이력 변경자는 admin이다 | AC-R16, AC-R17, AC-UC3 | backend | `application/test_delete_deal_action.py`, `domain/test_action_policy.py`, `domain/test_deal_action_entity.py` |
| AC-062 | 다른 sales의 삭제는 403이고 Action·이력이 그대로다 | AC-R16, AC-R17, AC-UC3 | backend | `application/test_delete_deal_action.py`, `domain/test_action_policy.py`, `domain/test_deal_action_entity.py` |
| AC-063 | 없는 Action·이미 지운 Action의 삭제는 404다 | AC-R16, AC-UC3 | backend | `application/test_delete_deal_action.py`, `domain/test_deal_action_entity.py` |
| AC-064 | user의 삭제는 없는 id여도 읽기 전용 403, 미인증은 401이다 | AC-R16, AC-UC3 | backend | `application/test_delete_deal_action.py`, `domain/test_deal_action_entity.py`, `web/test_deal_action_routes.py` |
| AC-065 | Deal의 Action 목록은 페이지 없이 그 Deal 것만 {items}로 돌려준다 | AC-R18, AC-UC4 | backend | `application/test_list_deal_actions_default.py` |
| AC-066 | 기본 목록은 수행일 최신순이고 같은 수행일이면 나중에 등록한 것이 앞이다 | AC-R18, AC-UC4 | backend | `application/test_list_deal_actions_default.py` |
| AC-067 | 없는 Deal의 목록은 404다 | AC-R18, AC-UC4 | backend | `application/test_list_deal_actions_default.py` |
| AC-068 | 어떤 역할이든 목록과 한 건을 읽고 유형은 현재 이름으로 나온다 | AC-R18, AC-R19, AC-R20, AC-UC4 | backend | `application/test_list_deal_actions_default.py`, `web/test_deal_action_routes.py` |
| AC-069 | 없는 Action 한 건 조회는 상한 id여도 404다 | AC-R19, AC-UC4 | backend | `application/test_list_deal_actions_default.py`, `web/test_deal_action_routes.py` |
| AC-070 | OpenAPI 계약: `memo` 없음·등록 `comment`·길이 상한·서버 필드 없음, 선택 입력·nullable 응답, 등록에만 동반 변경·이전 id, 전역 검색 없음 | AC-R2, AC-R13, AC-R18, AC-R20 | backend | `web/test_deal_action_close_previous_request.py`, `web/test_deal_action_openapi.py`, `web/test_deal_action_acted_on_request.py` |
| AC-071 | 화면: 목록은 최신순으로 수행일·유형·진행사항·Next Action·Due Date·상태 6열과 Comment 열만 보이고 수정·삭제 버튼이 없다 | AC-R21, AC-R22, AC-UC4 | frontend | `features/deals/detail/ActionsTab.cases.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| AC-072 | 화면: user는 추가 버튼이 없고 상세 팝업은 보기만 한다 | AC-R22, AC-R49, AC-R50, AC-UC4 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx`, `features/deals/detail/ActionsTab.dialog.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| AC-073 | (폐기 2026-11-16) 표 관리 열의 본인 행 수정·삭제 — 관리 열 폐지, AC-135로 대체 | AC-R22 | frontend | — |
| AC-074 | 화면: 추가 팝업은 이전 Update 카드·한 줄 Status·Forecast·유형·내용 칸을 보이고 진행사항에 포커스가 간다 | AC-R23, AC-UC1 | frontend | `features/deals/detail/ActionForm.syncFields.test.tsx`, `features/deals/detail/ActionForm.type.test.tsx`, `features/deals/detail/ActionsTab.dialog.test.tsx`, `features/deals/detail/ActionsTab.test.tsx`, `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-075 | 화면: 검증 문구는 유형 → 진행사항 → Due Date 순이고 첫 오류 칸에 포커스하며 요청하지 않는다 | AC-R24, AC-UC1 | frontend | `features/deals/detail/ActionForm.dateInput.test.tsx`, `features/deals/detail/ActionForm.type.test.tsx`, `features/deals/detail/ActionsTab.nextActionStatus.test.tsx`, `features/deals/detail/ActionsTab.dialog.test.tsx`, `features/deals/detail/ActionsTab.test.tsx`, `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-076 | 화면: Due Date는 yyyymmdd 입력을 ISO로 보내고 틀리거나 덜 친 날짜는 막는다 | AC-R24, AC-UC1 | frontend | `features/deals/detail/ActionForm.dateInput.test.tsx` |
| AC-077 | 화면: 등록하면 팝업이 닫히고 알림·목록 맨 위·요약 바가 갱신된다 | AC-R28, AC-UC1 | frontend | `features/deals/detail/ActionsTab.dialog.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| AC-078 | 화면: 목록에 없는 유형은 안내 후 이름으로, 목록에 있는 유형은 id로 보낸다 | AC-R25, AC-UC1 | frontend | `features/deals/detail/ActionForm.type.test.tsx`, `features/deals/detail/ActionForm.typeStable.test.tsx` |
| AC-079 | 화면: Status·Forecast를 바꾸면 바꾼 순서대로 보내고 알림에 변경 요약이 붙는다 | AC-R27, AC-R28, AC-UC1 | frontend | `features/deals/detail/ActionForm.syncFields.test.tsx`, `features/deals/detail/ActionsTab.dialog.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| AC-080 | 화면: 첫 변경을 뒤집는 두 번째 변경은 저장 전에 막고, 되돌림·취소 버튼은 변경을 버린다 | AC-R27, AC-UC1 | frontend | `features/deals/detail/ActionForm.syncConflict.test.tsx`, `features/deals/detail/ActionForm.syncFields.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| AC-081 | 화면: 이전 Next Action을 채우면 종료 체크가 켜지고 켠 채 저장하면 같은 요청으로 닫는다 | AC-R26, AC-R28, AC-UC1 | frontend | `features/deals/detail/ActionForm.closePrevious.test.tsx`, `features/deals/detail/ActionsTab.test.tsx`, `shared/model/nextActionBasis.test.ts` |
| AC-082 | 화면: 종료됐거나 남의 이전 Next Action에는 체크를 주지 않는다 | AC-R26, AC-UC1 | frontend | `features/deals/detail/ActionForm.closePrevious.test.tsx` |
| AC-083 | 화면: 409·403이면 팝업과 입력을 유지하고, 카드가 바뀌면 다시 채우라고 알린다 | AC-R26, AC-R28, AC-UC1 | frontend | `features/deals/detail/ActionForm.closePrevious.test.tsx` |
| AC-084 | 화면: 등록 저장 실패는 팝업 안 배너이고 저장 중에는 닫히지 않는다 | AC-R28, AC-R29, AC-UC1 | frontend | `features/deals/detail/ActionsTab.dialog.test.tsx` |
| AC-085 | 화면: 추가 팝업의 취소·Esc는 저장 없이 닫고 포커스를 돌려주며 겹친 팝업은 위부터 닫힌다 | AC-R29, AC-UC1 | frontend | `features/deals/detail/ActionForm.closePrevious.test.tsx`, `features/deals/detail/ActionForm.type.test.tsx`, `features/deals/detail/ActionsTab.dialog.test.tsx` |
| AC-086 | (폐기 2026-11-16) 수정 팝업 — 수정 팝업 폐지, AC-136으로 대체 | AC-R30 | frontend | — |
| AC-087 | 화면: 상세 팝업에서 유형이 아닌 칸을 저장하면 유형 이름이 바뀌었어도 원래 id로 보낸다 | AC-R50, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-088 | 화면: 상세 팝업의 삭제는 확인 뒤 지우고 두 팝업을 닫으며, 취소·실패면 상세 팝업이 남는다 | AC-R31, AC-R52, AC-UC3 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx` |
| AC-089 | 게이트웨이: 등록·수정·삭제·기본 목록 요청과 응답을 서버 계약대로 바꾼다 | AC-R32 | frontend | `gateway/http/actions.test.ts`, `gateway/http/mappers/action.test.ts` |
| AC-090 | Fake 게이트웨이는 등록·수정·삭제의 서버 규칙(판정 순서·이력·순차 변경·이전 종료)을 따른다 | AC-R3, AC-R6~R8, AC-R11, AC-R14~R17, AC-R33 | frontend | `test/fake/gateway/actions.closePrevious.test.ts`, `test/fake/gateway/actions.entryRules.test.ts`, `test/fake/gateway/actions.rules.test.ts`, `test/fake/gateway/actions.sequence.test.ts`, `test/fake/gateway/actions.test.ts`, `gateway/contract/actionsSequence.contract.ts`, `gateway/contract/actions.contract.ts`, `test/fake/gateway/actions.actedOn.test.ts` |
| AC-091 | 수행일을 생략·null·오늘로 보내면 수행일은 오늘이다 | AC-R34, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py`, `domain/test_resolve_acted_on.py`, `web/test_deal_action_acted_on_request.py` |
| AC-092 | 지난 수행일로 등록하면 수행일은 그 날짜이고 등록·수정 시각은 요청 시각이다 | AC-R34, AC-R37, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py`, `domain/test_resolve_acted_on.py`, `web/test_deal_action_acted_on_request.py` |
| AC-093 | 내일 수행일은 422이고 아무것도 저장되지 않는다 | AC-R35, AC-R9, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py`, `domain/test_resolve_acted_on.py` |
| AC-094 | Deal 등록일 전날 수행일은 422, 등록일 당일은 등록된다 | AC-R35, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py`, `domain/test_resolve_acted_on.py` |
| AC-095 | 수행일 형식이 틀리거나 시각이 붙으면 422 request-validation이고 acted_at은 계속 거부된다 | AC-R2, AC-UC5 | backend | `web/test_deal_action_acted_on_request.py` |
| AC-096 | 수행일 판정은 내용 오류 다음, 이전 Next Action 409 앞이다 | AC-R8, AC-R35, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-097 | 더 늦은 Action이 있으면 지난 날짜 Action은 Deal의 Next Action·최종 업데이트를 바꾸지 않는다 | AC-R38, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-098 | 지난 날짜 Action이 가장 늦은 수행일이면 Next Action·최종 업데이트일이 그 Action을 따른다 | AC-R38, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-099 | 기본 목록에서 지난 날짜 Action은 수행일 순서 자리에 놓인다 | AC-R38, AC-R18, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-100 | 기준 행보다 앞선 수행일로 이전 Next Action을 닫으면 422이고 기준 행은 Open, 같은 날이면 닫힌다 | AC-R36, AC-R9, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py`, `domain/test_resolve_acted_on.py` |
| AC-101 | 지난 수행일로 이전 Next Action을 닫으면 종료일은 오늘이고 이력 시각은 요청 시각이다 | AC-R36, AC-R37, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-102 | 지난 수행일로 Status를 바꾸며 등록하면 스냅숏·Status 진입일·Deal 수정 시각·이력 시각은 요청 시점 기준이다 | AC-R37, AC-UC5 | backend | `application/test_register_deal_action_acted_on.py` |
| AC-103 | Next Action 상태 변경과 수행일을 보내지 않는 수정은 수행일을 바꾸지 않는다 | AC-R39, AC-R45, AC-UC2 | backend | `application/test_register_deal_action_acted_on.py`, `web/test_deal_action_acted_on_request.py`, `application/test_update_deal_action_acted_on.py`, `domain/test_deal_action_revise_acted_on.py` |
| AC-104 | OpenAPI: 등록·수정 요청에 선택 nullable 날짜 acted_on이 있다 | AC-R2, AC-R13 | backend | `web/test_deal_action_acted_on_request.py` |
| AC-105 | 화면: 추가 팝업에 오늘로 채운 수행일 칸이 있다 | AC-R40, AC-R23, AC-UC5 | frontend | `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-106 | 화면: 수행일을 그대로 두면 acted_on을 보내지 않고 지난 날짜로 바꾸면 그 날짜를 보내며 목록에 그 날짜로 보인다 | AC-R42, AC-UC5 | frontend | `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-107 | 화면: 빈·틀린·미래·등록일 이전 수행일은 문구와 함께 막고 요청하지 않는다 | AC-R41, AC-R24, AC-UC5 | frontend | `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-108 | 화면: 이전 Next Action 종료를 켠 채 기준 행보다 앞선 수행일이면 막고, 체크를 끄면 등록된다 | AC-R41, AC-R26, AC-UC5 | frontend | `features/deals/detail/ActionForm.actedOn.test.tsx` |
| AC-109 | 게이트웨이: acted_on은 등록·수정 모두 값이 있을 때만 ISO 날짜로 보낸다 | AC-R32, AC-R42, AC-R47 | frontend | `gateway/http/actions.test.ts`, `gateway/http/mappers/action.test.ts` |
| AC-110 | Fake 게이트웨이는 수행일 결정·범위·종료 비교·판정 순서를 서버와 같게 따른다 | AC-R33, AC-R34~R36 | frontend | `test/fake/gateway/actions.actedOn.test.ts`, `gateway/contract/actions.contract.ts` |
| AC-111 | 같은 수행일의 Next Action Action은 나중에 등록한 것이 기준 행이고 오름차순 정렬에서는 뒤에 온다 | AC-R43, RK-R1, AC-UC4 | backend | `application/test_action_same_day_order.py` |
| AC-112 | 응답과 OpenAPI에 날짜 acted_on·next_action_closed_on이 있고 acted_at·next_action_closed_at 키가 없다 | AC-R20 | backend | `web/test_deal_action_openapi.py`, `web/test_deal_action_response_nullable.py` |
| AC-113 | 마이그레이션은 기존 수행 일시를 업무 시간대 날짜로 채우고 행 수를 유지한 뒤 acted_at을 없앤다(스키마 확인 대상에서 `memo` 제외) | AC-R44 | backend | `infra/schema/test_business_dates_migration.py` |
| AC-114 | 마이그레이션 downgrade는 acted_at을 수행일 00:00으로 되살린다 | AC-R44 | backend | `infra/schema/test_business_dates_migration.py` |
| AC-115 | Repository는 수행일·id로 기준 행·최종 업데이트일·목록 순서를 정한다 | AC-R43, AC-R38 | backend | `repositories/test_deal_action_latest_next_action_contract.py`, `repositories/test_deal_action_search_contract.py`, `repositories/test_deal_derived_values_contract.py` |
| AC-116 | 화면: 목록 수행일 칸은 YYYY-MM-DD이고 시각이 없으며 상세 팝업 수행일 편집 칸은 그 날짜다 | AC-R21, AC-R49, AC-R51 | frontend | `features/deals/detail/ActionDetailDialog.actedOn.test.tsx` |
| AC-117 | 게이트웨이·Fake: 응답 acted_on을 actedOn으로 매핑하고 같은 수행일은 id 큰 것이 앞이다 | AC-R32, AC-R33, AC-R43 | frontend | `gateway/http/mappers/action.test.ts`, `test/fake/gateway/actions.dates.test.ts` |
| AC-118 | 수행일만 고치면 수행일·수정 시각만 바뀌고 수행일이 붙은 이력 1건이 남는다 | AC-R45, AC-R11, AC-R14, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_action_history.py`, `domain/test_deal_action_revise_acted_on.py`, `web/test_deal_action_acted_on_request.py` |
| AC-119 | 수행일과 내용을 함께 고치면 이력 1건에 둘 다 반영된다 | AC-R45, AC-R11, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_action_history.py`, `domain/test_deal_action_revise_acted_on.py` |
| AC-120 | 수정 수행일을 생략·null·같은 날짜로 보내면 수행일은 그대로이고 내용도 같으면 아무것도 바뀌지 않는다 | AC-R45, AC-R14, AC-UC2 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_action_history.py`, `domain/test_deal_action_revise_acted_on.py`, `web/test_deal_action_acted_on_request.py` |
| AC-121 | 수정 수행일이 내일이면 422이고 Action·이력이 그대로이며 오늘은 된다 | AC-R45, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_ensure_acted_on_in_range.py`, `web/test_deal_action_update_acted_on_routes.py` |
| AC-122 | 수정 수행일이 Deal 등록일 전날이면 422이고 등록일 당일은 된다 | AC-R45, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_ensure_acted_on_in_range.py` |
| AC-123 | 수정 판정은 404 → 403 → 유형 → 내용 → 수행일 순이고 수행일로 거절돼도 새 유형이 남지 않는다 | AC-R15, AC-R45, AC-R5, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py` |
| AC-124 | 수정 수행일 형식이 틀리거나 시각이 붙으면 422 request-validation이다 | AC-R13, AC-UC6 | backend | `web/test_deal_action_acted_on_request.py`, `web/test_deal_action_update_acted_on_routes.py` |
| AC-125 | 수행일을 고치면 Deal의 Next Action·최종 업데이트일·목록 순서가 바뀐 수행일로 다시 계산된다 | AC-R46, AC-R38, AC-R12, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py` |
| AC-126 | 수정 수행일은 기준 행·종료일·닫은 이전 Action과의 선후를 따지지 않는다 | AC-R46, AC-UC6 | backend | `application/test_update_deal_action_acted_on.py`, `domain/test_deal_action_revise_acted_on.py` |
| AC-127 | Repository의 Action 수정은 수행일도 저장한다 | AC-R45 | backend | `repositories/test_deal_action_repository_contract.py` |
| AC-128 | (폐기 2026-11-16) 수정 팝업의 수행일 칸 — 수정 팝업 폐지, AC-132·AC-116으로 대체 | AC-R30, AC-R40 | frontend | — |
| AC-129 | 화면: 상세 팝업에서 수행일을 바꾸면 acted_on을 보내고 행이 바뀐 날짜 자리에 보이며, 다른 칸 저장에는 acted_on이 없다 | AC-R47, AC-R50, AC-UC6 | frontend | `features/deals/detail/ActionDetailDialog.actedOn.test.tsx` |
| AC-130 | 화면: 상세 팝업 수행일의 빈·틀린·미래·등록일 이전 값은 막고 기준 행보다 앞선 날짜는 막지 않는다 | AC-R47, AC-R51, AC-UC6 | frontend | `features/deals/detail/ActionDetailDialog.actedOn.test.tsx` |
| AC-131 | Fake 게이트웨이는 수정 수행일의 유지·범위·판정 순서·이력을 서버와 같게 따른다 | AC-R33, AC-R45, AC-R46 | frontend | `test/fake/gateway/actions.updateActedOn.test.ts` |
| AC-132 | 화면: 행을 누르면 상세 팝업이 모든 항목(담당자·등록 시점 Status·Forecast·상태 포함, Memo 없음)을 보인다 | AC-R48, AC-R49, AC-UC4 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx` |
| AC-133 | 화면: 키보드로 행에서 Enter·Space를 누르면 팝업이 열리고 닫으면 포커스가 행으로 돌아온다 | AC-R48 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx` |
| AC-134 | 화면: 행 안의 상태 칸 버튼은 상태만 바꾸고 상세 팝업을 열지 않는다 | AC-R48, NA-R21 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx` |
| AC-135 | 화면: 상세 팝업의 편집·삭제는 본인 Action과 admin에게만 켜지고 다른 sales는 보기만 한다 | AC-R49, AC-R50, AC-R52, AC-R17 | frontend | `features/deals/detail/ActionDetailDialog.test.tsx` |
| AC-136 | 화면: 진행사항을 인라인으로 고치면 그 칸만 바꾼 수정 요청을 보내고 팝업은 열린 채 새 값을 보인다 | AC-R50, AC-R51, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-137 | 화면: 유형 인라인 편집은 후보면 id로, 없는 이름이면 안내 후 이름으로 보내고 빈 값·51자는 막는다 | AC-R51, AC-R25, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-138 | 화면: 진행사항은 Shift+Enter로 줄을 바꾸고 Enter로 저장하며, 진행사항과 Next Action이 모두 비면 막는다 | AC-R51, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-139 | 화면: Next Action과 Due Date는 한 묶음으로 고치고 함께 검증한다 | AC-R51, AC-R14, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-140 | 화면: 편집 중 Esc는 그 칸만 닫고, 값이 그대로면 요청하지 않는다 | AC-R50, AC-R49 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-141 | 화면: 인라인 저장 실패는 그 칸 아래 서버 문구이고 저장 중에는 닫기·삭제가 꺼진다 | AC-R50, AC-UC2 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx`, `features/deals/detail/ActionDetailDialog.actedOn.test.tsx` |
| AC-142 | 화면: 진행사항·Next Action 칸은 넓고 짧은 칸은 줄바꿈하지 않는다(정적 점검) | AC-R53 | frontend | `features/deals/detail/ActionTable.style.test.tsx` |
| AC-143 | 화면: 저장 뒤 검색 조건에서 빠져도 상세 팝업은 열린 채 새 값을 보인다 | AC-R49, AC-R50 | frontend | `features/deals/detail/ActionDetailDialog.inline.test.tsx` |
| AC-144 | 화면: 상세 팝업의 상태 버튼으로 Next Action 상태를 바꾸면 종료 대화상자를 거쳐 팝업이 열린 채 새 상태·새 Comment를 보이고 표 상태 칸도 같다 | AC-R54, NA-R21, NA-R22, AC-UC2b | frontend | `features/deals/detail/ActionDetailDialog.status.test.tsx` |
| AC-145 | 화면: 팝업의 상태 버튼은 본인 Action·admin에게만 보이고 다른 sales·user는 라벨만 보며, 팝업의 "Open으로"는 대화상자 없이 바로 되돌린다 | AC-R54, NA-R21, NA-R23 | frontend | `features/deals/detail/ActionDetailDialog.status.test.tsx` |

### AC-001 sales가 Action을 등록하면 201과 Location이고 수행일·담당자·스냅숏을 서버가 정한다
- Given KIM이 Status 제품소개(introduction)·Forecast Best인 Deal을 연 상태이고 서버 시계가 T다
- When KIM이 기본 Action 입력으로 등록한다
- Then 201이고 `Location`은 `/api/v1/deal-actions/<id>`다. `acted_on` = T의 업무 날짜, `created_at` = `updated_at` = T, 담당자는 KIM(역할 sales), `status_key` introduction·`forecast_key` best, `next_action_status` open·`next_action_closed_on` null, 유형 `{id: <미팅 id>, name: "미팅"}`이다. 같은 id로 다시 읽어도 같은 값이다

### AC-002 등록 응답은 문서화된 14개 키를 가지고(`memo` 없음) 유형은 {id, name}이다
- When KIM이 기본 Action을 등록한다
- Then 응답 키는 정확히 `id`, `deal_code`, `action_type`, `action`, `next_action`, `due_date`, `next_action_status`, `next_action_closed_on`, `acted_on`, `actor`, `status_key`, `forecast_key`, `created_at`, `updated_at`이고 `action_type`의 키는 `id`·`name`이며 id는 JSON 정수다

### AC-003 텍스트 앞뒤 공백을 지워 저장하고 지난 Due Date도 받는다
- When 진행사항 "  킥오프  ", Next Action " 견적 ", Due 2000-01-01로 등록한다
- Then 201이고 "킥오프"·"견적"·2000-01-01로 저장된다

### AC-004 진행사항·Next Action은 길이 상한 없이 그대로 저장된다
- When 진행사항 "가"×5,000, Next Action "😀"×5,000으로 등록한다(Memo 20,000자는 CM-002가 검증)
- Then 201이고 두 값이 잘리지 않고 그대로 저장된다

### AC-005 (폐기 2026-11-17)
- 폐기: `memo` 컬럼이 없어졌다(Comment 분리). 기본값 케이스는 CM-027이 대신한다.

### AC-006 진행사항만 Action은 Next Action·Due·상태·종료 시각이 모두 null이다
- When Next Action ""·Due null로 등록한다
- Then 201이고 `action` "킥오프 미팅", `next_action`·`due_date`·`next_action_status`·`next_action_closed_on`은 null이며 이력은 "등록: 미팅 · 킥오프 미팅"이다

### AC-007 Next Action만 Action은 진행사항이 null이고 상태가 Open이다
- When 진행사항 ""로 등록한다
- Then 201이고 `action` null, `next_action` "요구사항 문서 전달", `due_date` 2027-01-15, 상태 open이며 이력은 "등록: 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)"이다

### AC-008 진행사항·Next Action이 모두 비면 422이고 아무것도 저장되지 않는다
- When 진행사항 "   "·Next Action ""(`comment`는 있음)로 등록한다
- Then 422 `invalid-value` "진행사항 또는 Next Action을 입력하세요."이고 그 Deal의 Action·이력이 없다

### AC-009 Next Action이 있는데 Due Date가 없으면 422 "Due Date를 입력하세요."다
- When Due Date를 null로 보내거나 `due_date` 키 없이 등록한다(진행사항 유무와 무관)
- Then 둘 다 422 `invalid-value` "Due Date를 입력하세요."이고 저장된 것이 없다

### AC-010 Next Action 없이 Due Date만 있으면 422다
- When Next Action "  "·Due 2027-01-15로 등록한다
- Then 422 `invalid-value` "Next Action 없이 Due Date를 입력할 수 없습니다."이고 저장된 것이 없다

### AC-011 내용 검증은 NUL → 둘 다 빔 → Due 필수 → Due 금지 순서로 첫 위반만 알린다
- When 진행사항·Next Action이 모두 비고 Due 2027-01-15인 등록과, 진행사항·Next Action 중 하나에 NUL(`가\x00나`)이 든 등록을 각각 보낸다
- Then 앞은 "진행사항 또는 Next Action을 입력하세요."(Due 금지보다 먼저), 뒤는 NUL 문구의 422 `invalid-value`이며 500이 아니다

### AC-012 서버가 정하는 필드·`memo` 키·모르는 필드·날짜가 아닌 Due를 보내면 422 request-validation이다
- When 본문에 `acted_at`, `actor_user_id`, `actor`, `deal_code`, `title`, `memo` 중 하나를 넣거나 `due_date`를 "2027-13-01"처럼 달력에 없는 값으로 보낸다
- Then 422 `request-validation`이고 Action이 저장되지 않는다

### AC-013 없는 Deal·형식이 틀린 code는 입력이 잘못돼도 404가 먼저다
- When 없는 code "20260101-ZZZZ"와 "not-a-code"에 진행사항 "  "·Next Action ""로 등록한다
- Then 둘 다 404 `not-found` "Deal을 찾을 수 없습니다."다

### AC-014 user의 등록은 읽기 전용 403, 미인증은 401이다
- When VIEWER가 등록하고, 로그인하지 않은 방문자가 잘못된 본문으로 등록한다
- Then VIEWER는 403 "이 작업을 할 권한이 없습니다(읽기 전용 계정)"이고 Action이 없으며, 방문자는 401 `unauthenticated`다(본문 검증보다 먼저)

### AC-015 Deal Owner가 아닌 sales도 Action을 등록할 수 있다
- Given Owner가 KIM인 Deal이다
- When LEE가 기본 Action을 등록한다
- Then 201이고 담당자는 LEE다

### AC-016 등록하면 Deal History에 "등록: <요약>" 1건이 요청 시각·요청자로 남고 요약에 Comment가 없다
- When KIM이 기본 Action을 등록하고, 다른 Deal에도 등록한다
- Then 첫 Deal 이력은 (`action`, "Action", "", "등록: 미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)") 1건이고 변경자 KIM, 시각 = 요청 시각 T이다. 둘째 Deal도 " / Comment:" 같은 부분이 없다

### AC-017 긴 요약은 이력에서만 1,000자로 잘리고 Action 원문은 그대로다
- When 진행사항 "가"×2,000으로 등록한다
- Then 등록 이력의 변경 후는 1,000자이고 "…"로 끝나며, Action의 진행사항은 2,000자 그대로다

### AC-018 등록해도 Deal 수정 시각은 그대로이고 Deal의 Next Action·최종 업데이트가 새 Action을 가리킨다
- Given Deal의 `updated_at`이 U다
- When Next Action "계약서 검토"·Due 2027-02-05로 등록한다
- Then Deal `updated_at`은 U 그대로이고 Deal `next_action`은 {"계약서 검토", 2027-02-05, open}, `last_updated_on`은 새 Action의 `acted_on`이다

### AC-019 이름으로 새 유형을 고른 등록이 다른 이유로 거절되면 새 유형이 남지 않는다
- Given 유형은 기본 8개다
- When 유형 `{name: "웨비나"}`로 ① 진행사항·Next Action이 빈 등록, ② Due 없는 등록, ③ 매출 없이 계약완료로 바꾸는 등록을 각각 보낸다
- Then 모두 422이고 유형은 8개 그대로이며 Action이 없다

### AC-020 없는 Deal은 유형 오류보다 먼저 404이고 새 유형도 생기지 않는다
- When 없는 code에 유형 `{name: "웨비나"}`·진행사항 "  "로 등록한다
- Then 404 "Deal을 찾을 수 없습니다."이고 유형은 8개 그대로다

### AC-021 유형 오류는 진행사항 오류보다 먼저 판정된다
- When 진행사항 "  "에 유형 `{name: "   "}`, `{name: "가"×51}`, 없는 유형 id를 각각 보낸다
- Then 각각 "유형을 입력하세요.", "유형은 50자 이내로 입력하세요.", "선택한 유형이 없습니다. 목록에서 다시 선택하세요."의 422 `invalid-value`다(진행사항 문구 아님). 유형이 맞으면 진행사항 오류가 Next Action·Due 오류보다 먼저다

### AC-022 이력 요약의 유형 자리에는 고른(새로 만든) 유형 이름이 들어간다
- When 유형 "웨비나"(새 이름)로 등록한다
- Then 등록 이력은 "등록: 웨비나 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15)"이다

### AC-023 계약완료로 바꾸며 등록하면 Deal이 종결되고 스냅숏은 변경 뒤 값이며 이력은 Deal 변경 다음 Action 등록 순서다
- Given 기본 Deal이다
- When `status_change` = Status 계약완료 + 매출 답(900,000,000·2026-10-20)으로 등록한다
- Then 201이고 Action 스냅숏은 contract_completed·won, Deal은 계약완료·Won·900,000,000·2026-10-20이다. 이력은 저장 순서대로 (status, Status, 기회발굴→계약완료), (forecast, Forecast, Pipeline→"Won (Status 계약완료와 함께 변경)"), (amount, 금액(단위:원), 150,000,000→900,000,000), (expectedClose, Expected Close, 2026-06-30→2026-10-20), (action, Action, "", "등록: …")이고 이력 목록 맨 위는 Action 등록 줄이다

### AC-024 종결로 바꾸며 매출을 주지 않으면 422이고 Action·Deal·이력이 그대로다
- When 매출 답 없이 Status 계약완료로 등록한다
- Then 422 "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."이고 Action이 없고 Deal은 기회발굴·Pipeline, 이력은 비어 있다

### AC-025 Forecast만 바꾸면 Status는 그대로이고 Deal 수정 시각이 요청 시각이 된다
- When Forecast Lost로 바꾸며 등록하고, 다른 Deal은 Forecast Best로 바꾸며 등록한다
- Then 스냅숏은 prospecting·lost이고 이력은 (forecast, Pipeline→Lost) 다음 Action 등록이다. Best로 바꾼 Deal의 `updated_at`은 그 등록의 요청 시각이다

### AC-026 Won Deal을 되돌리며 함께 바꿀 값을 고르지 않으면 422, 고르면 그 값이 스냅숏이 된다
- Given 종결 Deal이다
- When Forecast Commit으로 바꾸며 답 없이 등록하고, 이어서 답 Status PoC완료(poc_completed)로 등록한다
- Then 앞은 422 "함께 바꿀 값을 선택하세요."이고 Action 없음·Deal 그대로, 뒤는 201이고 스냅숏 poc_completed·commit이다

### AC-027 없는 코드로 바꾸려 하면 422 "존재하지 않는 코드입니다."이고 두 번째 항목 코드도 매출 판정보다 먼저 본다
- When Status `no_such_status`로 등록하고, `status_changes` = [Status 계약완료(답 없음), Forecast `nope`]로 등록한다
- Then 둘 다 422 "존재하지 않는 코드입니다."이고 Action·이력이 없다

### AC-028 현재와 같은 값으로 바꾸면 Deal은 그대로이고 Action만 남는다
- When Status prospecting(현재 값)으로 바꾸며 등록하고, 다른 요청은 두 항목 모두 현재 값으로 보낸다
- Then 201이고 스냅숏은 prospecting·pipeline, Deal `updated_at`은 그대로이며 이력은 Action 등록 1건뿐이다

### AC-029 내용 오류는 동반 변경보다 먼저 판정되어 Deal이 바뀌지 않는다
- When 진행사항·Next Action이 비고 Forecast Best로 바꾸는(또는 두 항목) 등록을 보낸다
- Then 422 "진행사항 또는 Next Action을 입력하세요."이고 Deal은 Pipeline 그대로다

### AC-030 Status와 Forecast 두 변경을 순서대로 적용하고 이력도 그 순서다
- When `status_changes` = [Status 제품소개, Forecast Best]로 등록한다
- Then 201이고 스냅숏·Deal 모두 introduction·best, 이력은 (status, 기회발굴→제품소개), (forecast, Pipeline→Best), Action 등록 순서다

### AC-031 두 번째 변경은 첫 변경을 적용한 상태로 판정한다(Won 되돌림 뒤 Status 이동)
- Given 종결 Deal이다
- When `status_changes` = [Forecast Commit(답 Status poc_completed), Status 제품소개]로 등록한다
- Then 201이고 Deal과 스냅숏은 introduction·commit이며 이력은 단계마다 남는다

### AC-032 두 번째 변경이 첫 변경 값을 뒤집으면 422 충돌 문구이고 아무것도 저장되지 않는다
- When `status_changes` = [Status 제품소개, Forecast Won(매출 답 있음)]으로 등록한다
- Then 422 "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."이고 Action 없음, Deal 기회발굴·Pipeline, 이력 없음이다

### AC-033 두 번째 변경이 실패하면 첫 변경도 저장되지 않는다
- Given Status 기회발굴·Forecast Lost인 Deal이다
- When `status_changes` = [Status 제품소개, Forecast Commit(답 없음)]으로 등록한다
- Then 422 "함께 바꿀 값을 선택하세요."이고 Deal은 기회발굴·Lost 그대로, Action·이력 없음이다

### AC-034 동반 변경 형식이 틀리면 422 request-validation이고 null·빈 배열은 변경 없음이다
- When `status_changes`에 같은 field 두 번, 항목 3개, `status_change`와 `status_changes`(빈 배열 포함)를 함께, field `revenue_amount`·`revenue_date`·`name`을 각각 보낸다. 또 `status_change`·`status_changes`를 둘 다 null로, `status_changes`를 빈 배열로 보낸다
- Then 앞의 것들은 422 `request-validation`이고 Action이 없다. 뒤의 것들은 201이고 Deal이 바뀌지 않는다. 단건 `status_change`는 1건짜리 목록과 같은 결과다

### AC-035 Action 스냅숏은 나중의 Deal 변경과 Action 수정에도 그대로다
- Given Forecast Best로 바꾸며 등록한 Action이 있다
- When Deal Forecast를 Commit으로 단일 변경한 뒤 그 Action의 진행사항을 고친다
- Then Action의 `status_key`·`forecast_key`는 prospecting·best, `acted_on`·담당자도 그대로다

### AC-036 이전 Next Action id와 함께 저장하면 기준 행이 종료(수행)가 되고 한 번에 저장된다
- Given KIM이 남긴 Open Action P가 기준 행이다
- When KIM이 `close_previous_next_action_id` = P.id, Next Action "다음 일정 확인"·Due 2027-02-01로 등록한다
- Then 201이고 P는 `done`, `next_action_closed_on` = 오늘(요청의 업무 날짜)이며 Action은 2건, Deal `next_action`은 "다음 일정 확인"이다. 커밋은 1번이다

### AC-037 이전 Next Action 종료 줄 다음에 등록 줄이 같은 시각으로 남는다
- When AC-036처럼 등록한다
- Then 이력 끝 두 줄은 저장 순서대로 (action, "Next Action", "요구사항 문서 전달 (Due 2027-01-15) · Open", "종료(수행)"), (action, "Action", "", "등록: …")이고 같은 시각이며 목록에서는 등록 줄이 위다

### AC-038 필드를 빼거나 null이면 이전 Next Action은 Open 그대로다
- Given Open 기준 행 P가 있다
- When 필드 없이, 또 null로 등록한다
- Then 둘 다 201이고 P는 Open 그대로다

### AC-039 기준 행이 아닌 id(더 최근 행 생김·다른 Deal·없는 id·Next Action 없음)는 409이고 아무것도 저장되지 않는다
- Given 기준 행 P 뒤에 Next Action이 있는 Action Q가 더 생겼다(또 다른 Deal의 Action, 없는 id, Next Action이 하나도 없는 Deal)
- When P.id(각각 그 id)로 닫으며 등록한다
- Then 409 `invalid-state` "이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요."이고 Action 수·이전 행 상태·이력이 그대로다

### AC-040 이미 종료된 기준 행은 건너뛰고 새 Action만 저장한다
- Given 기준 행 P를 종료(미수행) "못 함"으로 닫아 두었다
- When P.id로 닫으며 등록한다
- Then 201이고 P는 `not_done`·종료 시각 그대로이며 이력은 Action 등록 줄만 늘었다

### AC-041 남의 기준 행이면 sales는 403, admin은 닫을 수 있다
- Given KIM이 남긴 Open 기준 행 P다
- When LEE가 P.id로 닫으며 등록하고, ROOT가 같은 요청을 보낸다
- Then LEE는 403 "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."이고 Action 1건·P Open 그대로다. ROOT는 201이고 P는 종료(수행), 종료 줄의 변경자는 ROOT다. 다른 사람의 진행사항만 Action이 뒤에 있어도 KIM은 자기 P를 닫을 수 있다

### AC-042 이전 Next Action 409 판정이 권한 403보다 먼저다
- Given KIM의 P 뒤에 KIM의 Q가 더 생겼다
- When LEE가 P.id로 닫으며 등록한다
- Then 409다(403이 아님)

### AC-043 내용 오류나 동반 변경 실패면 이전 Next Action은 Open 그대로다
- When P.id로 닫으며 진행사항·Next Action이 빈 등록, 매출 없이 계약완료로 바꾸는 등록을 각각 보낸다
- Then 422이고 Action은 1건, P는 Open 그대로다

### AC-044 새 Action이 진행사항만이어도 이전 행을 닫을 수 있고 기준 행만 닫힌다
- Given Open Next Action 행 A(오래됨)·B(기준 행) 뒤에 진행사항만 Action C가 있다
- When B.id로 닫으며 진행사항만 Action을 등록한다
- Then 201이고 B만 종료(수행), A는 Open이다

### AC-045 이전 Next Action id 형식이 틀리면 422 request-validation이다
- When `close_previous_next_action_id`를 "7", 0, -1, 1.5, true, [1], 2^53으로 보낸다
- Then 모두 422 `request-validation`이고 이전 행은 Open이다

### AC-046 담당자가 고치면 내용만 바뀌고 수행일·담당자·스냅숏은 그대로이며 이력 1건이 남는다
- Given KIM이 기본 Action을 남겼다
- When KIM이 유형 "제안", 진행사항 "제안 발표", Next Action "견적 회신", Due 2027-02-01로 고친다
- Then 200이고 값이 바뀌며 `acted_on`·`created_at`·담당자·스냅숏은 그대로, `updated_at`은 서버 시각이다. 이력 최신 줄은 (action, Action, "<기본 요약>", "수정: 제안 · 제안 발표 / Next Action: 견적 회신 (Due 2027-02-01)")·변경자 KIM이고 Deal `updated_at`·`last_updated_on`은 그대로다

### AC-047 내용이 같은 수정은 200이지만 이력·수정 시각이 그대로이고 새 유형도 없다
- When 같은 내용, 앞뒤 공백만 다른 내용, 같은 유형 id, 대소문자만 다른 같은 유형 이름(" DEMO2 ")으로 각각 고친다
- Then 모두 200이고 `updated_at`·이력·유형 수가 그대로다

### AC-048 수정 내용 규칙을 어기면 422이고 Action은 그대로다
- When 진행사항·Next Action을 모두 비우거나, Due를 비우거나, Next Action만 비우고 Due를 남겨 고친다
- Then 각각 AC-R3 문구의 422 `invalid-value`이고 Action은 그대로다

### AC-049 수정도 길이 상한이 없고 1,000자 뒤에서만 달라진 수정도 이력 1건이다
- When 진행사항 "가"×5,000으로 고치고, 1,000자 넘는 요약의 뒷부분만 바꿔 고친다
- Then 원문이 그대로 저장되고 이력은 각각 1건이며 요약만 1,000자로 잘린다

### AC-050 수정으로 Next Action을 비우면 Due·상태·종료 시각이 null이 된다
- Given 종료(수행)로 닫은 Action이다
- When Next Action ""·Due null로 고친다
- Then 200이고 `next_action`·`due_date`·`next_action_status`·`next_action_closed_on`이 모두 null이다

### AC-051 진행사항만 Action에 Next Action을 채우면 Open이 된다
- Given 진행사항만 Action이다
- When Next Action "새 계획"·Due 2027-03-01로 고친다
- Then 상태 open이다. Next Action만 Action에 진행사항을 채워도 상태는 open 그대로다

### AC-052 종료된 Next Action의 내용을 고쳐도 종료 상태와 종료 시각은 그대로다
- Given 종료(미수행)로 닫은 Action이다
- When Next Action "바뀐 계획"·Due 2027-05-01로 고치고, 진행사항만 고친다
- Then 상태 `not_done`과 종료 시각이 그대로다

### AC-053 유형만 바꿔도 이력 1건이 남고 새 이름이면 새 유형이 생기며 실패하면 남지 않는다
- Given 유형 "미팅", Comment가 없는 Action이다
- When 유형만 `{name: "웨비나"}`로 고치고, 다른 Action은 유형 `{name: "웨비나2"}`·진행사항 "   "로 고치고, 또 없는 유형 id로 고친다
- Then 첫 수정은 200, 새 유형 "웨비나"(사용 1, "미팅" 사용 0), 이력 (Action, "<미팅 요약>", "수정: 웨비나 · …") 1건이다. 둘째는 422이고 "웨비나2"가 없다. 셋째는 422 "선택한 유형이 없습니다. 목록에서 다시 선택하세요."이고 유형이 그대로다

### AC-054 수정 본문에 동반 변경·이전 Next Action id·서버 필드가 있으면 422 request-validation이다
- When 수정 본문에 `status_change`, `status_changes`, `close_previous_next_action_id`, `acted_at` 중 하나를 넣는다
- Then 422 `request-validation`이고 Action은 그대로다. `acted_on`은 이 거부 목록에 없다(수정에서 받는다, AC-R13·R45, 2026-11-13 변경)

### AC-055 admin은 남의 Action을 고치고 담당자는 그대로이며 이력 변경자는 admin이다
- Given KIM의 Action이다
- When ROOT가 진행사항 "admin이 고침"으로 고친다
- Then 200이고 담당자는 KIM 그대로, 이력 변경자는 ROOT다. Deal Owner가 다른 사람이어도 KIM은 자기 Action을 고칠 수 있다

### AC-056 다른 sales의 수정은 본문이 잘못돼도 403이고 Action·이력이 그대로다
- Given KIM의 Action이다
- When LEE가 정상 본문으로, 또 진행사항 "   "·Due null인 본문으로 고친다
- Then 둘 다 403 "본인 Action 또는 admin만 수정할 수 있습니다."이고 Action·이력이 그대로다

### AC-057 없는 Action의 수정은 담당자·유형 확인보다 먼저 404다
- When LEE가 없는 id를, 잘못된 유형 이름과 함께 고친다
- Then 404 "Action을 찾을 수 없습니다."다. 남의 Action에 잘못된 유형을 보내면 403이 유형 오류보다 먼저다

### AC-058 user의 수정은 읽기 전용 403, 미인증은 401이다
- When VIEWER가 KIM의 Action을 고치고, 방문자가 없는 id를 고친다
- Then VIEWER는 403 읽기 전용 문구이고 Action이 그대로, 방문자는 401이다

### AC-059 담당자가 지우면 204이고 행이 사라지며 이력에 요약과 "삭제"가 남는다
- Given KIM의 기본 Action이다(Comment 없음)
- When KIM이 지운다
- Then 204이고 그 id 조회는 404, 이력 최신 줄은 (action, Action, "<기본 요약>", "삭제")·변경자 KIM이다(Comment가 없으니 "삭제" 그대로). 요약이 1,000자를 넘으면 변경 전만 잘린다

### AC-060 가장 최근 Action을 지우면 Deal Next Action이 이전 Action으로, 하나뿐이면 null이 된다
- Given Next Action "먼저 할 일"(Due 2027-03-01) Action 뒤에 "나중 할 일"(Due 2027-04-01) Action이 있다
- When 나중 Action을 지운다
- Then Deal `next_action`은 "먼저 할 일"·2027-03-01이고 목록에는 먼저 Action만 남는다. Action이 하나뿐인 Deal에서 그것을 지우면 `next_action`은 null이다

### AC-061 admin은 남의 Action을 지우고 이력 변경자는 admin이다
- When ROOT가 KIM의 Action을 지운다
- Then 204이고 이력 (… , "삭제")의 변경자는 ROOT다

### AC-062 다른 sales의 삭제는 403이고 Action·이력이 그대로다
- When LEE가 KIM의 Action을 지운다
- Then 403 "본인 Action 또는 admin만 삭제할 수 있습니다."이고 Action·이력이 그대로다

### AC-063 없는 Action·이미 지운 Action의 삭제는 404다
- When LEE가 없는 id를 지우고, KIM이 이미 지운 자기 Action을 다시 지운다
- Then 둘 다 404 "Action을 찾을 수 없습니다."다

### AC-064 user의 삭제는 없는 id여도 읽기 전용 403, 미인증은 401이다
- When VIEWER가 KIM의 Action과 없는 id를 지우고, 방문자가 지운다
- Then VIEWER는 둘 다 403 읽기 전용 문구(Action 그대로), 방문자는 401이다

### AC-065 Deal의 Action 목록은 페이지 없이 그 Deal 것만 {items}로 돌려준다
- Given Deal A에 Action 3건, Deal B에 1건이 있다
- When A의 목록을 조건 없이 읽는다
- Then 200이고 본문 키는 `items`뿐이며 A의 3건이 모두 있고 B의 것은 없다

### AC-066 기본 목록은 수행일 최신순이고 같은 수행일이면 나중에 등록한 것이 앞이다
- Given 수행일이 서로 다른 Action 3건과, 같은 수행일에 "먼저 등록"·"나중 등록" 순으로 남긴 2건이 있다
- When 조건 없이 목록을 읽는다
- Then 수행일 내림차순이고 같은 수행일의 두 건은 "나중 등록"(큰 id)이 앞이다

### AC-067 없는 Deal의 목록은 404다
- When 없는 code와 형식이 틀린 code의 목록을 읽는다
- Then 404 "Deal을 찾을 수 없습니다."다

### AC-068 어떤 역할이든 목록과 한 건을 읽고 유형은 현재 이름으로 나온다
- Given KIM의 "미팅" Action이 있고 admin이 "미팅"을 "회의"로 바꿨다
- When VIEWER·KIM·ROOT가 목록과 그 Action 한 건을 읽는다
- Then 모두 200이고 유형은 {같은 id, "회의"}이며 이미 남은 등록 이력 문구는 "미팅"이다

### AC-069 없는 Action 한 건 조회는 상한 id여도 404다
- When 없는 id와 2^53−1로 한 건을 읽는다
- Then 둘 다 404 `not-found`다(500이 아님)

### AC-070 OpenAPI 계약: `memo` 없음·등록 `comment`·길이 상한·서버 필드 없음, 선택 입력·nullable 응답, 등록에만 동반 변경·이전 id, 전역 검색 없음
- When OpenAPI 문서를 읽는다
- Then 요청에 `memo`가 없고 등록 요청에 `comment`가 있으며, 등록·수정 요청의 `action`·`next_action`·`comment`에 `maxLength`가 없고 `acted_at`·`actor_user_id`·`actor`가 없으며 `action_type`은 required `CatalogChoiceRequest`, `action`·`next_action`·`due_date`는 required가 아니다. `status_change(s)`·`close_previous_next_action_id`는 등록 요청에만 있다. 응답의 nullable 다섯 필드는 required + null 허용, `action_type`은 `{id, name}`, `ActionType` enum 스키마는 없다. `/api/v1/deal-actions`(전역 목록) 경로가 없고 Deal 목록 응답은 `{items}`뿐이며 `offset`·`limit`이 없다. 수정·삭제는 403·404를 문서화한다

### AC-071 화면: 목록은 최신순으로 수행일·유형·진행사항·Next Action·Due Date·상태 6열과 Comment 열만 보이고 수정·삭제 버튼이 없다
- Given Deal이 지금 계약완료·Won이고 예전 Action은 기회발굴·Pipeline 때 KIM이 남겼다
- When KIM이 Actions 탭을 연다
- Then 표 "Action 목록" 머리글이 수행일·유형·진행사항·Next Action·Due Date·상태·Comment 순으로 7개이고 최신 Action이 위다. "담당자"·"등록 시점 Status·Forecast"·"Memo"·"관리" 머리글, 행의 기회발굴·Pipeline 배지, "수정"·"삭제" 버튼이 없다. 빈 값은 "—"다. Action이 없는 Deal은 "등록된 Action이 없습니다."다

### AC-072 화면: user는 추가 버튼이 없고 상세 팝업은 보기만 한다
- When VIEWER가 Actions 탭을 열고 KIM의 행을 누른다
- Then 행은 보이지만 "Action 추가" 버튼이 없다. "Action 상세" 팝업은 열려 모든 값을 보이되 "<칸> 수정" 편집 버튼, "삭제" 버튼, 권한 안내 문구가 없고 "닫기"만 있다

### AC-073 (폐기 2026-11-16)
- 폐기: 표의 관리 열(수정·삭제 버튼)이 없어졌다. 상세 팝업 권한은 AC-135.

### AC-074 화면: 추가 팝업은 이전 Update 카드·한 줄 Status·Forecast·유형·내용 칸을 보이고 진행사항에 포커스가 간다
- When KIM이 "Action 추가"를 누른다
- Then 제목 "Action 추가" 모달 하나가 열리고 맨 위에 "이전 Update" 카드(기준 행 값, 읽기 전용)가 폼 앞에 있다. 그룹 "Status · Forecast · 유형"에 현재 Status·Forecast와 빈 유형 칸이 있고 진행사항·Next Action·Due Date·Comment 칸, 안내 "업데이트 일자: 등록 시각으로 자동 기록 · 담당자: <KIM 이름>"이 있다. 포커스는 진행사항 칸이다. "Next Action 업데이트" 문구는 없다

### AC-075 화면: 검증 문구는 유형 → 진행사항 → Due Date 순이고 첫 오류 칸에 포커스하며 요청하지 않는다
- When 모든 칸을 비우고 "등록"을 누르고, 유형 "   "·유형 51자·유형 50자로 각각 누르고, Next Action만 쓰고 누른다
- Then 첫 경우 "유형을 입력하세요."·"진행사항 또는 Next Action을 입력하세요." 문구와 유형 칸 포커스, 공백 유형은 "유형을 입력하세요.", 51자는 "유형은 50자 이내로 입력하세요."(50자는 통과), Next Action만이면 "Due Date를 입력하세요."다. 어느 경우도 요청이 없다. Next Action을 지우면 Due Date도 비워진다

### AC-076 화면: Due Date는 yyyymmdd 입력을 ISO로 보내고 틀리거나 덜 친 날짜는 막는다
- When Due Date에 "20270115"를 치고 등록하고, "20270231"·"202701"을 쳐 등록한다
- Then 앞은 "2027.01.15"로 보이고 `2027-01-15`로 등록된다. 뒤의 둘은 날짜 문구로 막혀 요청이 없다

### AC-077 화면: 등록하면 팝업이 닫히고 알림·목록 맨 위·요약 바가 갱신된다
- When 지난 Due Date를 포함해 올바르게 입력하고 "등록"을 누른다
- Then 팝업이 닫히고 알림 "Action이 등록되었습니다."가 보이며 새 Action이 목록 맨 위에 있고 요약 바 Next Action이 새 값이다. "취소"를 누르면 아무것도 등록되지 않는다

### AC-078 화면: 목록에 없는 유형은 안내 후 이름으로, 목록에 있는 유형은 id로 보낸다
- When 유형 칸에 "웨비나"를 쳐 등록하고, "DEMO"(목록의 "Demo")를 쳐 등록하고, 후보에서 골라 등록한다
- Then "웨비나"는 안내 "목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다."가 보이고 `{name: "웨비나"}`로 등록되며 다음 팝업 후보에 나온다. 나머지는 `{id}`로 보낸다. 목록을 읽는 중이면 안내가 없고, 읽기에 실패하면 안내 대신 오류 배너다. 서버가 유형을 거절하면 그 문구를 팝업에 보이고 입력을 유지한다

### AC-079 화면: Status·Forecast를 바꾸면 바꾼 순서대로 보내고 알림에 변경 요약이 붙는다
- When 팝업에서 Status를 제품소개로, 이어 Forecast를 Best로 바꾸고 등록한다
- Then 요청 `status_changes`가 [Status 제품소개, Forecast Best] 순서이고 알림은 "Action이 등록되었습니다. Status가 '제품소개'로, Forecast가 'Best'로 변경되었습니다."다. 바꾼 칸 아래 "현재: <원래 이름>"이 보인다. 계약완료로 바꾸면 매출 확정 대화상자를 거치고, 대화상자를 취소하면 Status가 그대로다. 아무것도 바꾸지 않으면 `status_changes`가 없다

### AC-080 화면: 첫 변경을 뒤집는 두 번째 변경은 저장 전에 막고, 되돌림·취소 버튼은 변경을 버린다
- Given Status를 제품소개로 바꿔 두었다
- When Forecast를 Won으로 고른다(또는 대화상자 답이 첫 값을 바꾼다), 다음으로 Status를 원래 값으로 되돌린다, 다음으로 "Status·Forecast 변경 취소"를 누른다
- Then 첫 경우 "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."가 보이고 변경이 쌓이지 않는다(다음 성공 변경에서 문구가 사라짐). 앞 칸을 되돌리면 그 뒤 변경도 버려지고 "Forecast 변경도 취소되었습니다. 필요하면 다시 선택하세요."가 보인다. 취소 버튼은 모든 변경과 동기화 알림을 지운다

### AC-081 화면: 이전 Next Action을 채우면 종료 체크가 켜지고 켠 채 저장하면 같은 요청으로 닫는다
- Given KIM의 Open Next Action이 기준 행이다(같은 시각이면 id 큰 행)
- When KIM이 "이전 Next Action을 진행사항에 채우기"를 누르고 등록한다
- Then 진행사항이 그 Next Action으로 채워지고 체크박스 "저장 시 이전 Next Action을 종료(수행)로 바꿈"이 켜진 채 나타나며, 등록 요청 하나에 `close_previous_next_action_id`가 실린다. 알림은 "Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다."이고 이전 행 상태가 종료(수행)로 보인다. 이력에 종료 줄 다음 등록 줄이 있다. 체크를 끄거나 채우기를 누르지 않으면 id를 보내지 않고 이전 행은 Open이다. 다시 채우기를 눌러도 끈 체크는 꺼진 채다

### AC-082 화면: 종료됐거나 남의 이전 Next Action에는 체크를 주지 않는다
- When 기준 행이 이미 종료인 Deal에서 채우기를 누르고, LEE가 KIM의 Open 기준 행을 채운다, ROOT가 채운다
- Then 종료면 체크·안내 모두 없다. LEE는 안내 "다른 담당자의 Next Action이라 상태는 바꾸지 않습니다."만 보이고 id를 보내지 않는다. ROOT는 체크가 나온다

### AC-083 화면: 409·403이면 팝업과 입력을 유지하고, 카드가 바뀌면 다시 채우라고 알린다
- When 채우고 체크한 뒤 그 사이 다른 기준 행이 생겨 409가 나고, 또 403이 난다. 그다음 팝업을 닫고 다시 연다. 별도로, 채운 뒤 카드가 다른 행으로 바뀐다
- Then 409·403은 서버 문구를 팝업 안에 보이고 입력을 유지한다. 다시 열면 카드가 새 기준 행이고 그 행을 닫는 등록이 성공한다. 카드가 바뀌면 "이전 Update가 바뀌었습니다. 확인 후 다시 채우세요."가 보이고 체크가 사라지며 새 행 id도 옛 행 id도 보내지 않는다(진행사항은 그대로)

### AC-084 화면: 등록 저장 실패는 팝업 안 배너이고 저장 중에는 닫히지 않는다
- When 등록이 서버에서 거절되고, 요청이 끝나기 전에 Esc·"취소"를 시도한다
- Then 실패 문구가 팝업 안에 보이고 팝업과 입력이 그대로다. 저장 중에는 "취소"가 꺼지고 Esc가 무시되며 성공하면 닫히고, 실패하면 "취소"가 다시 켜진다

### AC-085 화면: 추가 팝업의 취소·Esc는 저장 없이 닫고 포커스를 돌려주며 겹친 팝업은 위부터 닫힌다
- When 추가 팝업을 "취소"·Esc로 닫고, 동기화 대화상자가 겹친 상태에서 Esc를 두 번 누른다
- Then 추가 팝업은 저장 없이 닫히고 포커스가 "Action 추가" 버튼으로 가며 다시 열면 입력이 비어 있다. 첫 Esc는 동기화 대화상자만 닫고 입력이 남으며 두 번째 Esc가 Action 팝업을 닫는다. Tab 포커스는 맨 위 팝업 안에서만 돈다. 유형 후보가 열려 있으면 Esc는 후보만 닫는다

### AC-086 (폐기 2026-11-16)
- 폐기: "Action 수정" 팝업이 없어졌다(AC-R30). 인라인 수정은 AC-136.

### AC-087 화면: 상세 팝업에서 유형이 아닌 칸을 저장하면 유형 이름이 바뀌었어도 원래 id로 보낸다
- Given KIM의 Action A(유형 미팅) 상세 팝업을 연 뒤 admin이 "미팅" 이름을 "고객 미팅"으로 바꿔 유형 목록이 다시 읽혔다
- When KIM이 진행사항을 고쳐 Enter를 누른다
- Then 요청의 유형은 `{id: <미팅 id>}`이고 새 유형이 생기지 않으며, 저장 뒤 팝업 유형 값은 "고객 미팅"이다

### AC-088 화면: 상세 팝업의 삭제는 확인 뒤 지우고 두 팝업을 닫으며, 취소·실패면 상세 팝업이 남는다
- Given KIM의 최신 Action과 그 이전 Next Action이 있는 Action이 있다
- When KIM이 최신 Action 상세 팝업의 "삭제"를 누르고 확인 대화상자에서 "삭제"를 누른다. 또 다른 Action 팝업에서 "삭제" → "취소"를 누르고, 서버가 삭제를 거절하는 Action 팝업에서 "삭제"를 확인한다
- Then 제목 "Action 삭제" 대화상자가 상세 팝업 위에 열리고 "\"<진행사항>\" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다."를 보인다. 확인하면 두 대화상자가 닫히고 그 행이 사라지며 알림 "Action이 삭제되었습니다.", 요약 바 Next Action이 이전 Action 값이 된다. 취소하면 확인 대화상자만 닫히고 상세 팝업과 행이 남는다. 거절되면 확인 대화상자가 닫히고 상세 팝업 안 오류 배너에 서버 문구가 보이며 행이 남는다. 표에는 어느 행에도 "삭제" 버튼이 없다

### AC-089 게이트웨이: 등록·수정·삭제·기본 목록 요청과 응답을 서버 계약대로 바꾼다
- When HTTP 게이트웨이로 등록(진행사항만·Next Action만·긴 텍스트·빈 Due·동반 변경 2건·이전 id·계약 삭제 플래그 포함 여부별), 수정, 삭제, 조건 없는 목록을 부른다
- Then AC-R32의 경로·본문(snake_case, `action` ← 진행사항, 빈 Due → null, 가공 없음, `acted_at`·담당자 없음, 선택 필드는 있을 때만, 유형 id와 name 중 하나만)으로 보내고, 응답(201·200·204·`{items}`)을 매핑하며 null 값과 퇴사 담당자 표기를 유지한다. 오류(403·404·409·422)는 서버 문구 그대로 보인다. 등록 본문에 `comment`가 있고 `memo`는 없으며, 수정 본문에는 둘 다 없다

### AC-090 Fake 게이트웨이는 등록·수정·삭제의 서버 규칙(판정 순서·이력·순차 변경·이전 종료)을 따른다
- Given Fake 게이트웨이
- When 등록·수정·삭제를 서버 단위 케이스와 같은 입력으로 부른다(user 403, 404 → 422 순서, 이력 문구·자르기, 무변경 수정, 담당자 권한, 두 변경 순서·충돌·코드 먼저, 이전 Next Action 409·403·건너뜀, 진행사항·Next Action·Comment의 NUL, 달력 날짜가 아닌 Due Date)
- Then 결과·문구·이력이 서버 규칙과 같다(mock 계약 테스트 포함). NUL은 422 `invalid-value` NUL 문구, 날짜가 아닌 Due Date는 422 `request-validation`이다(Fake를 서버 동작에 맞춤, 2026-11-10 결정)

공통 예(AC-091~AC-110, AC-118~AC-131): 업무 시간대 Asia/Seoul, 서버 시계 T = 2026-11-13T14:30:00+09:00(오늘 2026-11-13), Deal 등록 2026-11-01T09:00+09:00.

### AC-091 수행일을 생략·null·오늘로 보내면 수행일은 오늘이다
- Given 서버 시계가 T다
- When KIM이 `acted_on` 없이, `acted_on: null`로, `acted_on: "2026-11-13"`으로 각각 기본 Action을 등록한다
- Then 셋 다 201이고 `acted_on`은 2026-11-13, `created_at` = `updated_at` = T다

### AC-092 지난 수행일로 등록하면 수행일은 그 날짜이고 등록·수정 시각은 요청 시각이다
- Given 서버 시계가 T다
- When KIM이 `acted_on: "2026-11-10"`으로 기본 Action을 등록한다
- Then 201이고 `acted_on`은 2026-11-10, `created_at`·`updated_at`은 T, 이력 "등록: <요약>"의 시각은 T다

### AC-093 내일 수행일은 422이고 아무것도 저장되지 않는다
- When KIM이 `acted_on: "2026-11-14"`로 등록한다
- Then 422 `invalid-value` "수행일은 오늘 이후로 지정할 수 없습니다."이고 그 Deal의 Action·이력·새 유형이 없다

### AC-094 Deal 등록일 전날 수행일은 422, 등록일 당일은 등록된다
- When KIM이 `acted_on: "2026-10-31"`과 `"2026-11-01"`로 각각 등록한다
- Then 앞은 422 `invalid-value` "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."이고 저장된 것이 없으며, 뒤는 201·`acted_on` 2026-11-01이다

### AC-095 수행일 형식이 틀리거나 시각이 붙으면 422 request-validation이고 acted_at은 계속 거부된다
- When `acted_on`을 "2026-13-01", "2026-11-10T10:00:00+09:00", 20261110(숫자)로, 또는 `acted_at`을 넣어 등록한다
- Then 모두 422 `request-validation`이고 Action이 저장되지 않는다

### AC-096 수행일 판정은 내용 오류 다음, 이전 Next Action 409 앞이다
- When 진행사항·Next Action이 모두 비고 `acted_on` "2026-11-14"인 등록과, 내용은 맞고 `acted_on` "2026-11-14"·기준 행이 아닌 `close_previous_next_action_id`인 등록을 보낸다
- Then 앞은 "진행사항 또는 Next Action을 입력하세요.", 뒤는 "수행일은 오늘 이후로 지정할 수 없습니다."(409 아님)의 422다

### AC-097 더 늦은 Action이 있으면 지난 날짜 Action은 Deal의 Next Action·최종 업데이트를 바꾸지 않는다
- Given Deal에 수행일이 2026-11-12인 Next Action "견적 발송"(Due 2026-11-20) Action이 있다
- When KIM이 `acted_on` "2026-11-11"로 Next Action "자료 전달"(Due 2026-11-15) Action을 등록한다
- Then 201이고 Deal의 `next_action.text`는 "견적 발송", `last_updated_on`은 2026-11-12 그대로다

### AC-098 지난 날짜 Action이 가장 늦은 수행일이면 Next Action·최종 업데이트일이 그 Action을 따른다
- Given Deal에 수행일이 2026-11-05인 Next Action "견적 발송" Action뿐이다
- When KIM이 `acted_on` "2026-11-10"으로 Next Action "자료 전달"(Due 2026-11-15) Action을 등록한다
- Then Deal의 `next_action.text`는 "자료 전달", `last_updated_on`은 2026-11-10이다

### AC-099 기본 목록에서 지난 날짜 Action은 수행일 순서 자리에 놓인다
- Given 수행일이 2026-11-05와 2026-11-12인 Action이 있다
- When `acted_on` "2026-11-10"으로 하나를 더 등록하고 조건 없이 목록을 읽는다
- Then 순서는 11-12 → 11-10 → 11-05다

### AC-100 기준 행보다 앞선 수행일로 이전 Next Action을 닫으면 422이고 기준 행은 Open, 같은 날이면 닫힌다
- Given KIM의 기준 행(Open)의 수행일이 2026-11-12다
- When KIM이 그 id를 `close_previous_next_action_id`로 `acted_on` "2026-11-11"로 등록하고, 다시 `acted_on` "2026-11-12"로 등록한다
- Then 앞은 422 `invalid-value` "이전 Next Action의 수행일(2026-11-12)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다."이고 기준 행은 Open·새 Action 없음이며, 뒤는 201이고 기준 행이 종료(수행)다

### AC-101 지난 수행일로 이전 Next Action을 닫으면 종료일은 오늘이고 이력 시각은 요청 시각이다
- Given KIM의 기준 행(Open)의 수행일이 2026-11-05이고 서버 시계가 T(2026-11-13)다
- When KIM이 그 id와 `acted_on` "2026-11-10"으로 등록한다
- Then 기준 행의 `next_action_closed_on`은 2026-11-13, `updated_at`은 T, NA-R8 형식 종료 이력과 등록 이력의 시각은 T이고 새 Action의 `acted_on`은 2026-11-10이다

### AC-102 지난 수행일로 Status를 바꾸며 등록하면 요청 시점 기준이다
- Given Status 기회발굴·Forecast Pipeline Deal, 서버 시계 T
- When KIM이 `acted_on` "2026-11-10", Status를 제품소개로 바꾸는 `status_changes`로 등록한다
- Then 새 Action 스냅숏은 제품소개, Deal `status_changed_on`은 2026-11-13, `updated_at`과 Status 변경 이력 시각은 T, `acted_on`은 2026-11-10이다

### AC-103 Next Action 상태 변경과 수행일을 보내지 않는 수정은 수행일을 바꾸지 않는다
- Given `acted_on`이 2026-11-10인 KIM의 Action
- When 진행사항만 고쳐(`acted_on` 키 없이) 보내고, 다시 `acted_on: null`로 진행사항을 고쳐 보내고, Next Action 상태를 종료(수행)로 바꾼다
- Then 셋 다 성공하고 `acted_on`은 2026-11-10 그대로다. 수정 이력에는 수행일 부분이 없다 (2026-11-13 변경: 이전에는 '수정 본문의 `acted_on`은 422'였다)

### AC-104 OpenAPI: 등록·수정 요청에 선택 nullable 날짜 acted_on이 있다
- When OpenAPI 문서를 읽는다
- Then `DealActionCreateRequest`와 `DealActionUpdateRequest`에 모두 `acted_on`(format date, null 허용, required 아님)이 있고 두 요청 모두 `acted_at`이 없다 (2026-11-13 변경: 이전에는 수정 요청에 없었다)

### AC-105 화면: 추가 팝업에 오늘로 채운 수행일 칸이 있다
- Given Fake 시계의 오늘이 2026-11-13이다
- When KIM이 "Action 추가"를 누른다
- Then 추가 팝업에 안내 "담당자: <KIM 이름>"과 "Status · Forecast · 유형" 줄 위의 "수행일" 칸(2026.11.13)이 있다. 수정 팝업의 수행일 칸은 AC-128이 확인한다 (2026-11-13 변경: 이전에는 '수정 팝업에는 칸이 없다'를 함께 확인했다)

### AC-106 화면: 수행일을 그대로 두면 acted_on을 보내지 않고 지난 날짜로 바꾸면 그 날짜를 보낸다
- When KIM이 수행일을 그대로 두고 등록하고, 다시 수행일에 `20261110`을 쳐서 등록한다
- Then 첫 요청에는 `acted_on`이 없고 두 번째는 `acted_on: "2026-11-10"`이며, 목록에 수행일이 "2026-11-10"인 행이 그 날짜 순서 자리에 보인다

### AC-107 화면: 빈·틀린·미래·등록일 이전 수행일은 문구와 함께 막고 요청하지 않는다
- Given Deal 등록일 2026-11-01, 오늘 2026-11-13
- When 수행일을 비우고, `2026.11`로 두고, `20261114`로, `20261031`로 각각 바꿔 "등록"을 누른다
- Then 차례로 "수행일을 입력하세요.", "날짜를 yyyymmdd 형식으로 입력하세요.", "수행일은 오늘 이후로 지정할 수 없습니다.", "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."가 수행일 칸 아래에 보이고 포커스가 수행일 칸이며 요청이 없다. 유형도 비어 있으면 수행일 문구가 먼저 포커스를 가진다

### AC-108 화면: 이전 Next Action 종료를 켠 채 기준 행보다 앞선 수행일이면 막고, 체크를 끄면 등록된다
- Given KIM의 Open 기준 행이 2026-11-12에 수행됐다
- When "이전 Next Action을 진행사항에 채우기"로 체크가 켜진 뒤 수행일을 `20261111`로 바꿔 등록하고, 체크를 끄고 다시 등록한다
- Then 첫째는 "이전 Next Action의 수행일(2026-11-12)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다."를 보이고 요청하지 않으며, 둘째는 `close_previous_next_action_id` 없이 `acted_on: "2026-11-11"`로 등록된다

### AC-109 게이트웨이: acted_on은 등록·수정 모두 값이 있을 때만 ISO 날짜로 보낸다
- When HTTP 게이트웨이 `actions.create`와 `actions.update`를 각각 수행일 없이, `actedOn: "2026-11-10"`으로 부른다
- Then 수행일이 없으면 두 본문 모두 `acted_on` 키가 없고, 있으면 두 본문 모두 `acted_on: "2026-11-10"`이다 (2026-11-13 변경: 이전에는 '수정 요청에는 어느 경우도 없다')

### AC-110 Fake 게이트웨이는 수행일 결정·범위·종료 비교·판정 순서를 서버와 같게 따른다
- Given Fake 게이트웨이(Fake 시계 오늘 2026-11-13)
- When AC-091~AC-094, AC-096, AC-100과 같은 입력으로 등록한다
- Then `actedOn`·422 문구·판정 순서·저장 여부가 서버 케이스와 같다(계약 테스트 포함)

### AC-111 같은 수행일의 Next Action Action은 나중에 등록한 것이 기준 행이고 오름차순 정렬에서는 뒤에 온다
- Given 수행일 2026-11-12로 Next Action이 "A"인 Action을 등록한 뒤, 같은 수행일로 Next Action이 "B"인 Action을 등록했다
- When Deal을 읽고, `acted_at_asc`로 Action 목록을 읽는다
- Then Deal `next_action.text`는 "B"이고, 오름차순 목록은 A → B다

### AC-112 응답과 OpenAPI에 날짜 acted_on·next_action_closed_on이 있고 acted_at·next_action_closed_at 키가 없다
- When Action을 등록·조회하고 OpenAPI 문서를 읽는다
- Then 응답 `acted_on`은 "YYYY-MM-DD"이고 required이며 null이 될 수 없다. `next_action_closed_on`은 "YYYY-MM-DD" 또는 null이고 required다. `acted_at`·`next_action_closed_at` 키는 없다. 두 필드의 스키마는 format date다

### AC-113 마이그레이션은 기존 수행 일시를 업무 시간대 날짜로 채우고 행 수를 유지한 뒤 acted_at을 없앤다(스키마 확인 대상에서 `memo` 제외)
- Given 기준선 리비전 DB(업무 시간대 Asia/Seoul)에 `acted_at`이 `2026-11-10T23:59:59+09:00`, `2026-11-10T15:30:00Z`, `2026-11-11T00:00:00+09:00`인 Action 3건이 있다
- When `upgrade head`를 실행한다
- Then Action은 3건 그대로이고 `acted_on`은 차례로 2026-11-10, 2026-11-11, 2026-11-11이다. `acted_on`은 NOT NULL이고, `acted_at` 컬럼은 없으며, 인덱스는 `ix_deal_actions_acted_on`·`ix_deal_actions_deal_id_acted_on`이다

### AC-114 마이그레이션 downgrade는 acted_at을 수행일 00:00으로 되살린다
- Given head DB에 `acted_on`이 2026-11-10인 Action이 있다
- When `downgrade -1`을 실행한다
- Then `acted_at`은 `2026-11-10T00:00:00+09:00`(NOT NULL)이고 `acted_on` 컬럼은 없으며 행 수는 그대로다

### AC-115 Repository는 수행일·id로 기준 행·최종 업데이트일·목록 순서를 정한다
- Given 한 Deal에 수행일이 11-05, 11-12, 11-12(나중 등록)인 Next Action Action이 있고, Action이 없는 Deal도 하나 있다
- When Repository로 목록·기준 행·최종 업데이트일을 읽는다
- Then 목록 순서는 11-12(나중 등록) → 11-12 → 11-05이고, 기준 행은 11-12(나중 등록), 최종 업데이트일은 2026-11-12다. Action이 없는 Deal의 최종 업데이트일은 그 Deal의 등록일이다

### AC-116 화면: 목록 수행일 칸은 YYYY-MM-DD이고 시각이 없으며 상세 팝업 수행일 편집 칸은 그 날짜다
- Given 수행일이 2026-11-10인 KIM의 Action이 있다
- When Actions 탭을 열고 그 행을 눌러 상세 팝업에서 "수행일 수정"을 누른다
- Then 첫 열 머리글은 "수행일", 칸 값은 "2026-11-10"이고, 상세 팝업 수행일 값은 "2026-11-10", 편집 칸은 "2026.11.10"이다. 시:분 표기는 어디에도 없다 (2026-11-16 변경: 수정 팝업 → 상세 팝업 인라인)

### AC-117 게이트웨이·Fake: 응답 acted_on을 actedOn으로 매핑하고 같은 수행일은 id 큰 것이 앞이다
- When HTTP 게이트웨이가 `acted_on: "2026-11-10"` 응답을 받고, Fake에는 같은 수행일 Action 두 건을 등록한 뒤 목록을 읽는다
- Then 화면 모델의 `actedOn`은 "2026-11-10"이고 `actedAt`은 없다. Fake 목록에서는 나중에 등록한 Action이 앞이다

AC-118~AC-127 공통: KIM의 기본 Action X(수행일 2026-11-12, `created_at` = `updated_at` = C, 스냅숏 prospecting·pipeline, Next Action Open)가 있다. "같은 내용"은 X의 유형 id·진행사항·Next Action·Due를 그대로(수정 본문에 Comment는 없다) 보내는 것이다.

### AC-118 수행일만 고치면 수행일·수정 시각만 바뀌고 수행일이 붙은 이력 1건이 남는다
- Given X가 있고 서버 시계가 T다. Deal `updated_at`은 U다
- When KIM이 X를 같은 내용과 `acted_on: "2026-11-10"`으로 고친다
- Then 200이고 `acted_on`은 2026-11-10, `updated_at`은 T이며 내용·`created_at` C·담당자 KIM·스냅숏·`next_action_status` open·`next_action_closed_on` null은 그대로다. 이력 최신 줄은 (action, "Action", "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15) / 수행일: 2026-11-12", "수정: 미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2027-01-15) / 수행일: 2026-11-10") 1건이고 변경자 KIM·시각 T다. Deal `updated_at`은 U 그대로다

### AC-119 수행일과 내용을 함께 고치면 이력 1건에 둘 다 반영된다
- Given X가 있다
- When KIM이 진행사항 "제안 발표"와 `acted_on: "2026-11-05"`로 고친다
- Then 200이고 이력은 1건, 변경 전 "<기본 요약> / 수행일: 2026-11-12", 변경 후 "수정: 미팅 · 제안 발표 / Next Action: 요구사항 문서 전달 (Due 2027-01-15) / 수행일: 2026-11-05"다

### AC-120 수정 수행일을 생략·null·같은 날짜로 보내면 수행일은 그대로이고 내용도 같으면 아무것도 바뀌지 않는다
- Given X가 있다
- When KIM이 같은 내용으로 `acted_on` 키 없이, `acted_on: null`로, `acted_on: "2026-11-12"`로 각각 고친다
- Then 셋 다 200이고 `acted_on`은 2026-11-12, `updated_at`은 C, 이력과 유형 수가 그대로다

### AC-121 수정 수행일이 내일이면 422이고 Action·이력이 그대로이며 오늘은 된다
- Given X가 있다
- When KIM이 같은 내용과 `acted_on: "2026-11-14"`로 고치고, 이어서 `acted_on: "2026-11-13"`으로 고친다
- Then 앞은 422 `invalid-value` "수행일은 오늘 이후로 지정할 수 없습니다."이고 X(`acted_on` 2026-11-12, `updated_at` C)와 이력이 그대로다. 뒤는 200이고 `acted_on`은 2026-11-13이다

### AC-122 수정 수행일이 Deal 등록일 전날이면 422이고 등록일 당일은 된다
- Given X가 있다(Deal 등록일 2026-11-01)
- When KIM이 같은 내용과 `acted_on: "2026-10-31"`로 고치고, 이어서 `acted_on: "2026-11-01"`로 고친다
- Then 앞은 422 `invalid-value` "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."이고 X·이력이 그대로다. 뒤는 200이고 `acted_on`은 2026-11-01이다

### AC-123 수정 판정은 404 → 403 → 유형 → 내용 → 수행일 순이고 수행일로 거절돼도 새 유형이 남지 않는다
- Given X가 있고 유형은 기본 8개다. 아래 요청은 모두 `acted_on: "2026-11-14"`(내일)를 싣는다
- When ① LEE가 없는 id를, ② LEE가 X를, ③ KIM이 유형 `{name: "   "}`로 X를, ④ KIM이 진행사항·Next Action을 비워 X를, ⑤ KIM이 유형 `{name: "웨비나"}`와 올바른 내용으로 X를 각각 고친다
- Then ① 404 "Action을 찾을 수 없습니다.", ② 403 "본인 Action 또는 admin만 수정할 수 있습니다.", ③ 422 "유형을 입력하세요.", ④ 422 "진행사항 또는 Next Action을 입력하세요.", ⑤ 422 "수행일은 오늘 이후로 지정할 수 없습니다."다. 모두 X·이력이 그대로이고 유형은 8개 그대로("웨비나" 없음)다

### AC-124 수정 수행일 형식이 틀리거나 시각이 붙으면 422 request-validation이다
- Given X가 있다
- When 수정 본문의 `acted_on`을 "2026-13-01", "2026-11-10T10:00:00+09:00", 20261110(숫자)로 각각 보낸다
- Then 모두 422 `request-validation`이고 X는 그대로다

### AC-125 수행일을 고치면 Deal의 Next Action·최종 업데이트일·목록 순서가 바뀐 수행일로 다시 계산된다
- Given 한 Deal에 KIM의 Action A(수행일 2026-11-05, Next Action "자료 전달", Due 2026-11-20)와 B(수행일 2026-11-12, Next Action "견적 발송", Due 2026-11-25)가 있어 Deal `next_action.text`는 "견적 발송", `last_updated_on`은 2026-11-12다. Deal `updated_at`은 U다
- When KIM이 B를 같은 내용과 `acted_on: "2026-11-03"`으로 고친다
- Then Deal `next_action.text`는 "자료 전달", `last_updated_on`은 2026-11-05이고 조건 없는 목록 순서는 A → B다. Deal `updated_at`은 U 그대로다

### AC-126 수정 수행일은 기준 행·종료일·닫은 이전 Action과의 선후를 따지지 않는다
- Given KIM의 P(수행일 2026-11-05, Next Action 있음)를 KIM이 2026-11-10에 Q(수행일 2026-11-10)를 등록하며 닫아 P는 `done`·종료일 2026-11-10이다
- When KIM이 Q를 같은 내용과 `acted_on: "2026-11-03"`(P 수행일보다 앞)으로 고치고, P를 같은 내용과 `acted_on: "2026-11-12"`(P 종료일보다 뒤)로 고친다
- Then 둘 다 200이다. P는 `done`·종료일 2026-11-10 그대로이고 Q의 `acted_on`은 2026-11-03, P의 `acted_on`은 2026-11-12다

### AC-127 Repository의 Action 수정은 수행일도 저장한다
- Given 저장된 Action(수행일 2026-11-12)이 있다
- When 수행일을 2026-11-10으로 바꾼 엔티티로 `update`를 부르고 다시 읽는다
- Then `acted_on`은 2026-11-10이고 `created_at`·담당자·스냅숏은 그대로이며, 그 Deal의 기준 행·최종 업데이트일·목록 순서가 새 수행일을 따른다

### AC-128 (폐기 2026-11-16)
- 폐기: 수정 팝업이 없어졌다(AC-R30). 상세 팝업 수행일 표시는 AC-132, 편집 칸 값은 AC-116.

### AC-129 화면: 상세 팝업에서 수행일을 바꾸면 acted_on을 보내고 행이 바뀐 날짜 자리에 보이며, 다른 칸 저장에는 acted_on이 없다
- Given 수행일이 2026-11-12와 2026-11-05인 KIM의 Next Action Action 두 건이 있다(11-12 행이 위)
- When KIM이 11-12 행의 상세 팝업에서 진행사항만 고쳐 Enter를 누르고, 이어서 "수행일 수정"에 `20261103`을 쳐 Enter를 누른다
- Then 첫 요청에는 `acted_on`이 없고 두 번째는 `acted_on: "2026-11-03"`이다. 두 번 다 알림 "Action이 수정되었습니다."가 보이고 팝업 수행일은 "2026-11-03"이다. 팝업을 닫으면 그 행은 수행일 "2026-11-03"으로 11-05 행 아래에 있고 요약 바 Next Action은 11-05 행의 값이다

### AC-130 화면: 상세 팝업 수행일의 빈·틀린·미래·등록일 이전 값은 막고 기준 행보다 앞선 날짜는 막지 않는다
- Given Deal 등록일 2026-11-01, 오늘 2026-11-13. KIM의 Action Y(수행일 2026-11-10)보다 수행일이 늦은 Next Action Action(2026-11-12)이 있다
- When Y의 상세 팝업에서 "수행일 수정"을 열어 수행일을 비우고, `2026.11`로 두고, `20261114`로, `20261031`로, `20261102`로 각각 바꿔 Enter를 누른다
- Then 앞의 넷은 차례로 "수행일을 입력하세요.", "날짜를 yyyymmdd 형식으로 입력하세요.", "수행일은 오늘 이후로 지정할 수 없습니다.", "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."가 수행일 칸 아래 보이고 편집이 열린 채 요청이 없다. 마지막은 막지 않고 `acted_on: "2026-11-02"`로 저장된다

### AC-131 Fake 게이트웨이는 수정 수행일의 유지·범위·판정 순서·이력을 서버와 같게 따른다
- Given Fake 게이트웨이(Fake 시계 오늘 2026-11-13)
- When AC-118, AC-120~AC-123, AC-125, AC-126과 같은 입력으로 수정한다
- Then `actedOn`·`updatedAt`·422 문구·판정 순서·이력 문구·저장 여부·목록 순서가 서버 케이스와 같다(계약 테스트 포함)

### AC-132 화면: 행을 누르면 상세 팝업이 모든 항목을 보인다
- Given 지금 계약완료·Won인 Deal에 KIM이 기회발굴·Pipeline 때 남긴 Action A(수행일 2026-11-10, 유형 미팅, 진행사항 "킥오프 미팅", Next Action "요구사항 문서 전달", Due 2027-01-15, Open)가 있다
- When KIM이 Actions 탭에서 A의 행을 누른다
- Then 제목 "Action 상세" 대화상자가 열리고 수행일 "2026-11-10", 담당자 KIM 표기, 등록 시점 기회발굴·Pipeline 배지, 유형 "미팅", 진행사항 "킥오프 미팅", Next Action "요구사항 문서 전달", Due Date "2027-01-15", Next Action 상태 "Open"을 보이고 "Memo" 줄이 없다. 진행사항만 Action을 열면 Next Action·Due Date·Next Action 상태가 "—"이고, 종료(수행)된 Action은 상태가 "종료(수행) · 종료일 <날짜>"다. "닫기"를 누르면 팝업이 닫힌다

### AC-133 화면: 키보드로 행을 열고 닫으면 포커스가 행으로 돌아온다
- Given Actions 탭에 Action 두 건이 있다
- When Tab으로 두 번째 행에 포커스를 두고 Enter를 누른 뒤 Esc로 닫고, 다시 Space를 누른다
- Then Enter와 Space 모두 그 Action의 상세 팝업을 열고, Esc로 닫은 뒤 포커스는 그 행에 있다

### AC-134 화면: 행 안의 상태 칸 버튼은 상태만 바꾸고 상세 팝업을 열지 않는다
- Given KIM의 Open Action 행과 종료(수행)된 Action 행이 있다
- When KIM이 Open 행의 "종료(수행)"을 누르고, 종료 행의 "Open으로"를 누른다
- Then 첫 동작은 종료 팝업 "Next Action 종료(수행)"(NA-R22)만 열고 "Action 상세" 대화상자는 열리지 않는다. "Open으로"는 팝업 없이 행을 "Open"으로 바꾸고 상세 팝업도 열리지 않는다

### AC-135 화면: 상세 팝업의 편집·삭제는 본인 Action과 admin에게만 켜지고 다른 sales는 보기만 한다
- Given KIM의 Action A와 LEE의 Action B가 있다
- When KIM이 A와 B의 상세 팝업을 차례로 열고, ROOT가 B의 상세 팝업을 연다
- Then KIM의 A 팝업은 수행일·유형·진행사항·Next Action · Due Date 값이 편집 버튼("수행일 수정" 등)이고 "삭제"가 켜져 있으며 권한 안내가 없다. KIM의 B 팝업은 값만 보이고(편집 버튼 없음) "삭제"가 꺼진 채 title "본인 Action 또는 admin만 삭제할 수 있습니다."이며 안내 "본인 Action 또는 admin만 수정·삭제할 수 있습니다."가 보인다. 담당자·등록 시점 Status·Forecast는 누구에게도 편집 버튼이 없다(Next Action 상태 버튼은 AC-145). ROOT의 B 팝업은 편집 버튼과 켜진 "삭제"가 있다

### AC-136 화면: 진행사항을 인라인으로 고치면 그 칸만 바꾼 수정 요청을 보내고 팝업은 열린 채 새 값을 보인다
- Given KIM의 Action A 상세 팝업이 열려 있다
- When "진행사항 수정"을 눌러 진행사항을 "킥오프 미팅 완료"로 바꾸고 Enter를 누른다
- Then 수정 요청은 한 번이고 본문은 유형 `{id: <미팅 id>}`, 진행사항 "킥오프 미팅 완료", Next Action "요구사항 문서 전달", Due 2027-01-15이며(`memo` 키 없음) `acted_on`이 없다. 팝업은 열린 채 진행사항 "킥오프 미팅 완료"를 보이고 알림 "Action이 수정되었습니다."가 보이며, 팝업을 닫으면 표의 그 행 진행사항도 새 값이다. 담당자·등록 시점 배지는 그대로다

### AC-137 화면: 유형 인라인 편집은 후보면 id로, 없는 이름이면 안내 후 이름으로 보내고 빈 값·51자는 막는다
- Given KIM의 Action A(유형 미팅) 상세 팝업이 열려 있고 유형 목록에 "이메일"이 있다
- When "유형 수정"을 눌러 후보 "이메일"을 고르고, 다시 열어 "현장 데모"를 쳐 Enter를 누르고, 다시 열어 공백만 두고 Enter를, 51자를 쳐 Enter를 누른다
- Then 첫 저장은 고르는 순간 `{id: <이메일 id>}`로 보낸다. "현장 데모"는 편집 중 "목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다."가 보이고 `{name: "현장 데모"}`로 보내 팝업 유형이 "현장 데모"가 된다. 공백만은 "유형을 입력하세요.", 51자는 "유형은 50자 이내로 입력하세요."가 칸 아래 보이고 요청이 없으며 편집이 열린 채다

### AC-138 화면: 진행사항은 Shift+Enter로 줄을 바꾸고 Enter로 저장하며, 진행사항과 Next Action이 모두 비면 막는다
- Given KIM의 Action A와 진행사항만 Action C(진행사항 "자료 송부", Next Action 없음)가 있다
- When A의 상세 팝업에서 진행사항을 "1줄", Shift+Enter, "2줄"로 고쳐 Enter를 누르고, C의 상세 팝업에서 진행사항을 모두 지우고 Enter를 누른다
- Then 첫 요청의 진행사항은 "1줄\n2줄"이고 팝업 진행사항이 두 줄로 보인다. C는 "진행사항 또는 Next Action을 입력하세요."가 칸 아래 보이고 요청이 없다

### AC-139 화면: Next Action과 Due Date는 한 묶음으로 고치고 함께 검증한다
- Given KIM의 진행사항만 Action C 상세 팝업이 열려 있다
- When "Next Action · Due Date 수정"을 눌러 Next Action에 "견적 발송"만 쓰고 Enter를 누르고, Tab으로 Due Date 칸에 가서 `20270110`을 쓰고 Enter를 누르고, 다시 열어 Next Action을 모두 지우고 Enter를 누른다
- Then 첫 Enter는 "Due Date를 입력하세요."로 막히고 요청이 없다. Due Date 칸으로 Tab 이동한 것으로는 요청이 없다. 두 번째 Enter는 한 요청으로 Next Action "견적 발송"·Due `2027-01-10`을 보내 팝업에 두 값과 상태 "Open"이 보인다. 마지막은 Next Action을 지우자 Due Date 칸도 비고, 요청은 Next Action ""·Due null이며 팝업의 Next Action·Due Date·상태가 "—"가 된다

### AC-140 화면: 편집 중 Esc는 그 칸만 닫고, 값이 그대로면 요청하지 않는다
- Given KIM의 Action A 상세 팝업이 열려 있다
- When "진행사항 수정"을 열어 "버릴 내용"을 쓰고 Esc를 누르고, 다시 Esc를 누르고, 팝업을 다시 열어 "진행사항 수정"을 열고 아무것도 바꾸지 않고 Enter를 누른다
- Then 첫 Esc 뒤 진행사항은 "킥오프 미팅" 그대로이고 팝업은 열려 있으며 두 번째 Esc가 팝업을 닫는다. 바꾸지 않은 Enter는 요청 없이 편집만 닫는다

### AC-141 화면: 인라인 저장 실패는 그 칸 아래 서버 문구이고 저장 중에는 닫기·삭제가 꺼진다
- Given KIM의 Action A 상세 팝업이 열려 있고 그 사이 A가 다른 곳에서 삭제됐다
- When 진행사항을 고쳐 Enter를 누르고, 응답 전에 Esc를 누른다
- Then 응답 전에는 "닫기"·"삭제"가 꺼져 있고 Esc로 팝업이 닫히지 않는다. 응답 뒤 진행사항 칸 아래 "Action을 찾을 수 없습니다."가 보이고 편집과 입력한 글이 그대로다

### AC-142 화면: 진행사항·Next Action 칸은 넓고 짧은 칸은 줄바꿈하지 않는다(정적 점검)
- When Action 목록 표의 CSS 규칙을 읽는다
- Then 진행사항·Next Action 칸 규칙은 `min-width: 40em`이고 `max-width` 제한이 없으며, 수행일·유형·Due Date·상태 칸 규칙은 `white-space: nowrap`이다. 공통 `.dd-table td.wrap` 규칙(280px)은 그대로다

### AC-143 화면: 저장 뒤 검색 조건에서 빠져도 상세 팝업은 열린 채 새 값을 보인다
- Given 키워드 "킥오프"로 검색해 Action A 한 행만 보이고 그 상세 팝업이 열려 있다
- When 진행사항을 "착수 회의"로 고쳐 Enter를 누른다
- Then 팝업은 열린 채 진행사항 "착수 회의"를 보이고, 팝업을 닫으면 표는 "조건에 맞는 Action이 없습니다."다

### AC-144 화면: 상세 팝업에서 Next Action 상태를 바꾼다
- Given KIM의 Open Action A(Next Action "요구사항 문서 전달")의 상세 팝업이 열려 있다
- When KIM이 팝업의 "종료(수행)"을 누르고 열린 종료 대화상자의 Comment 칸에 "전달 완료"를 쓴 뒤 "종료"를 누른다
- Then 종료 대화상자만 닫히고 "Action 상세" 팝업은 열린 채 상태 "종료(수행) · 종료일 <오늘>"을 보이고 Comment 영역 맨 위에 "전달 완료"가 보이며 표의 A 행 상태 칸도 "종료(수행)"이다. 서버가 거절하면 대화상자 안에 서버 문구가 보이고 입력한 Comment가 남는다

### AC-145 화면: 팝업의 상태 버튼 권한과 "Open으로"
- Given KIM의 종료(수행) Action A와 LEE의 Open Action B가 있다
- When KIM이 A의 상세 팝업에서 "Open으로"를 누르고, 이어서 B의 상세 팝업을 열고, user VIEW가 B의 상세 팝업을 연다
- Then A는 대화상자 없이 팝업에서 바로 "Open"이 된다. KIM의 B 팝업과 VIEW의 B 팝업은 상태 라벨만 보이고 상태 버튼이 없으며 admin ROOT의 B 팝업에는 "종료(수행)"·"종료(미수행)" 버튼이 있다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 초안 작성(구현된 동작 문서화) | AC-001~AC-090 |
| 2026-11-10 | 사용자 결정 반영(추천대로): E1 Fake를 서버 동작에 맞춤(AC-R33 신설: NUL·날짜 형식), E2 단건 `status_change` 하위 호환 유지(AC-R6)·삭제 실패 탭 배너 유지(AC-R31), E5 경계(기본 순서·열 구성은 AC-R18·R21, 조건·정렬·필터는 NA, 이전 Next Action 종료 이력 형식은 NA-R8)와 다른 문서 참조를 번호로(NA·TM-R8·US-R17·CL-R10·RK-R17) | 변경: AC-088(삭제 실패 표시 추가), AC-090(AC-R33, NUL·날짜 형식 기대 결과) |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체(1장, AC-R23~R25). 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): Action 등록 수행일 지정(사용자 요청 2026-11-13, 계획 Q1~Q7 권고안대로 확정). 신설 AC-R34~R42, AC-UC5, 용어 수행일·요청 시각. 변경 AC-R2(`acted_on`), AC-R4, AC-R8(판정 순서), AC-R13(`acted_on` 거부), AC-R23(안내 문구), AC-R24(수행일 먼저), AC-R32, AC-R33, 2.6·2.8 | 신규 AC-091~AC-110. 변경: AC-054(수정 본문 거부 목록에 `acted_on` 추가), AC-070(등록 요청 `acted_on`), AC-074(안내 문구·수행일 칸), AC-075(검증 순서 제목에 수행일), AC-089(`acted_on` 있을 때만), AC-090(Fake 수행일 규칙). 그대로: AC-001(`acted_on` 없으면 요청 시각), AC-012 |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 업무 날짜를 date로 저장(사용자 요청 "수행일시는 년월일만", 결정 Q1~Q13). `acted_at`→`acted_on`, `next_action_closed_at`→`next_action_closed_on`(date), 23:59:59 규칙 폐지. 변경: 용어, 2.2, AC-R2·R4·R6·R7·R12~R14·R18·R20·R21·R23·R26·R30·R34·R36~R42, 2.4, UC2·UC5. 신설: AC-R43(같은 날 순서), AC-R44(데이터 변환). API 호환 깨짐(사용자 승인) | 신규 AC-111~AC-117. 변경 AC-001, AC-002, AC-006, AC-016, AC-018, AC-025, AC-035, AC-036, AC-046, AC-050, AC-066, AC-071, AC-086, AC-091, AC-092, AC-094, AC-097~AC-103, AC-105, AC-106, AC-110 |
| 2026-11-13 | 초안(사용자 확인 대기): Action 수정 때 수행일 변경(사용자 요청 "Deal action 수정시 수행일자도 수정 가능하도록 해줘"). 신설 AC-R45(수정 수행일 유지·범위·내용 변경 취급), AC-R46(등록 AC-R36 미적용·선후 제약 없음·파생 값 재계산), AC-R47(수정 팝업 검증·보내기), AC-UC6. 변경: 1장 범위, 용어 수행일·수행일 지정, 2.2(`DealActionUpdateInput`, `ensure_acted_on_in_range`), AC-R10(요약에 수행일 없음 명시), AC-R11(수정 줄 수행일 부분), AC-R12, AC-R13(수정 본문 `acted_on` 허용), AC-R14, AC-R15(판정 순서 끝에 수행일), AC-R17, AC-R24, AC-R30(안내 글 → 칸), AC-R32, AC-R33, AC-R35, AC-R36, AC-R38, AC-R39(등록 때만 → 등록·수정), AC-R40(수정 팝업에도 칸), AC-R41·R42(추가 팝업 한정 명시), 2.4·2.5·2.6(수정 요청 `acted_on`, 하위 호환 추가)·2.8, UC2 | 신규 AC-118~AC-131. 변경 AC-054(`acted_on`은 거부 목록에 없음), AC-086(수정 팝업 수행일 칸), AC-103(제목·내용: 422 → 보내지 않는 수정은 유지), AC-104(수정 요청에도 `acted_on`), AC-105(수정 팝업 부분 삭제), AC-109(수정도 값이 있을 때만 보냄), AC-116(수정 팝업 칸 값·안내). 그대로: AC-046·AC-047(수행일 없는 수정, 이력 문구 같음), AC-110 |
| 2026-11-16 | 확정(2026-11-16 사용자 확인): Q1~Q3·Q5·Q6·Q8 권고안, Q4 변경(상세 팝업에서도 Next Action 상태 변경, 신설 AC-R54·AC-UC2b, AC-R49·AC-135 수정), Q7 변경(진행사항·Next Action 칸 `min-width: 40em`, AC-R53·AC-142 수정). 신설 AC-144·AC-145. 이전 초안 내용: Actions 탭 표 축소와 Action 상세 팝업 인라인 수정·삭제(사용자 요청 2026-11-16). 신설 AC-R48(행 열기), AC-R49(상세 팝업), AC-R50(인라인 수정 공통), AC-R51(칸별 편집기·검증, Next Action·Due Date 묶음), AC-R52(팝업 삭제), AC-R53(표 칸 폭). 폐지 AC-R30(수정 팝업). 변경 1장 범위, AC-R21(6열), AC-R22(관리 열 폐지), AC-R24·R29·R40·R41(추가 팝업 한정), AC-R28(수정 알림 출처), AC-R31(팝업에서 삭제, 실패는 팝업 안 배너), AC-R47(수행일 인라인), 2.5 화면 행, 2.7·2.8, UC2·UC3·UC4·UC6. 백엔드·API·마이그레이션 변경 없음 | 신규 AC-132~AC-145. 변경 AC-071, AC-072, AC-084, AC-085, AC-087, AC-088, AC-116, AC-129, AC-130. 폐기 AC-073(→AC-135), AC-086(→AC-136), AC-128(→AC-132·AC-116). 그대로: backend 케이스 전부, AC-074~AC-083, AC-089~AC-115, AC-117~AC-127, AC-131 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): CM 확정: Memo → Comment 엔티티 분리. `memo` 컬럼·요청·응답 키 제거(2.2, AC-R2·R3·R7·R10·R13·R14·R20·R33, 2.6·2.8), 등록 요청 `comment` 추가(AC-R2, AC-R8 판정 순서, AC-R9 원자성, AC-R11 저장 순서), 삭제 때 Comment 함께 삭제(AC-R11·R16), 프런트 규칙 AC-R23·R49·R50·R51·R54는 프런트 후속에서 개정(CM 2.7) | 변경 AC-002~AC-004, AC-011, AC-012, AC-016, AC-046, AC-049, AC-059, AC-070, AC-113, AC-118, AC-119. 폐기 AC-005. 프런트 후속 AC-074, AC-089, AC-090, AC-132, AC-136, AC-138, AC-140, AC-144 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): Comment 화면 반영 — 표 7열(AC-R21·R48, 주소 action 파라미터), 추가 팝업 Comment 칸(AC-R23), 삭제 확인 Comment 건수(AC-R31), 게이트웨이 comment(AC-R32), Memo 줄 → Comment 영역(AC-R49~R51), 종료 Comment(AC-R54). 이전 행의 "프런트 후속" 해소 | 변경 AC-071, AC-074, AC-089, AC-090, AC-132, AC-135, AC-136, AC-138, AC-140, AC-144 |
