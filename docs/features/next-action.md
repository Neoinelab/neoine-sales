# Next Action 상태·Action 검색   (feature 코드: NA, 상태: 확정(2026-11-17 사용자 확인))

> 이 문서는 **이미 구현된 동작**을 정본 명세로 옮긴 것입니다(2026-11-10). 근거는 작업 트리의 코드입니다.
> - backend: `domain/deal_action/{next_action_status.py,entities.py(change_next_action_status·ensure_status_changeable_by),errors.py,policy.py,history.py(next_action_status_draft)}`, `application/deal_action/{change_next_action_status.py,list_deal_actions.py,inputs.py}`, `application/ports/deal_action_repository.py`(`DealActionQuery`·`DealActionSort`·`NextActionStatusFilter`), `domain/common/validation.py`, `infra/db/{deal_action_repository.py(_filtered),deal_action_order.py,like.py}`, `web/routers/deal_actions.py`, `web/schemas/deal_action.py`(`NextActionStatusRequest`·`DealActionSearchParams`), `web/permissions.py`
> - frontend: `features/deals/detail/{ActionsTab.tsx,ActionSearchBar.tsx,NextActionStatusCell.tsx,NextActionCloseDialog.tsx,actionSort.ts,ActionTable.tsx(머리글 정렬·상태 칸),useLatest.ts}`, `shared/model/{nextActionStatus.ts,periodChoice.ts}`, `shared/ui/PeriodField.tsx`, `data/actions.ts`, `gateway/http/{actions.ts,mappers/nextActionStatus.ts}`, `test/fake/gateway/{actions.ts,nextActionStatus.ts}`
>
> Next Action 상태 분리(2026-10-20)와 Action 머리글 정렬·기간 프리셋 계획의 결정을 따른다. 계획과 코드가 다른 곳은 코드를 따랐다. 코드와 Fake·테스트가 어긋나던 점은 2026-11-10 사용자 결정으로 정리했다: Fake 게이트웨이는 서버 동작에 맞추고(NA-R30), Due Date 범위의 1900~2999 미검사는 현행대로 둔다(NA-R16). 결정 목록은 `artifacts/10-analysis/na-plan.md`에 있다.

## 1. 개요

- 목적: 영업이 Deal의 Next Action을 끝냈는지(수행·미수행) 기록하고, Deal 상세 Actions 탭에서 그 Deal의 Action을 조건으로 찾아 원하는 순서로 본다.
- 사용자(역할)
  - 상태 변경: Action 작성자 본인(`sales`)과 `admin`. `user`는 할 수 없다.
  - Action 검색·정렬: 로그인한 모든 역할(`admin`·`sales`·`user`).
- 범위
  - `PUT /api/v1/deal-actions/{action_id}/next-action-status`(상태 변경·종료 Comment·이력)
  - `GET /api/v1/deals/{code}/actions`의 조회 계약: 쿼리 조건(유형·담당자·검색어·수행일·Due Date·Next Action 상태), 정렬 10종, 응답 모양(`{items}`, 페이지 없음), 없는 Deal 404
  - Actions 탭의 상태 칸·상태 버튼·종료 팝업, 검색 바(기간 프리셋 포함), 머리글 정렬, 빈 결과 문구
- 범위 밖
  - Action 등록·수정·삭제와 그 검증(AC-R1~R17), 등록 때 상태가 Open으로 시작하는 것(AC-R4), 수정으로 Next Action을 비우거나 채울 때의 상태 변화(AC-R14), 등록하며 이전 Next Action 종료(`close_previous_next_action_id`, AC-R7 — 그 이력의 대상·문구 형식은 이 문서 NA-R8), `GET /deal-actions/{id}`(AC-R19), 조건 없는 목록의 기본 순서(AC-R18), Actions 표의 열 구성·행 표시(AC-R21)·Action 추가/수정/삭제 버튼(AC-R22) → AC(`deal-actions.md`, 2026-11-10 경계 결정)
  - Deal 목록의 Next Action 상태 필터(기준 행의 상태로 Deal 거르기)·URL `next_status` → DL(DL-R21)
  - Next Action 기준 행·Deal 응답 `next_action.status`·최종 업데이트·기한초과 판정, 요약 바의 상태 라벨, Action 표 기한초과 배지 → RK(RK-R1, RK-R2, RK-R4, RK-R17, RK-R18)
  - 기간 프리셋을 주는 `GET /deals/updated-periods` → DL(DL-R17)
  - Actions 탭 틀(`?tab=actions`) → DD(DD-R27), Deal History 탭 표시·이력 문구 길이 제한 → DD(DD-R38, DD-R20)
  - 미인증 401·CSRF 403·업무 쓰기 가드(`user` 403)·id 경로/쿼리 형식·NUL 공통 원칙·없는 경로 404 → PL(PL-R4~R6, PL-R9, PL-R12, PL-R13, PL-R15, PL-R16)
  - 업무 날짜·업무일 시작 → TM(TM-R4, TM-R5), 날짜 입력 칸(`DateInput`)·정렬 머리글·확인 대화상자 공통 컴포넌트 자체 → UI(`DateInput` UI-R1~R11, 정렬 머리글 UI-R32, 확인 대화상자 UI-R29)
- 관련 화면·메뉴: Deal 상세(`/deals/:code?tab=actions`) Actions 탭.

## 2. 명세 (SDD)

### 2.1 용어

| 용어 | 뜻 |
| --- | --- |
| Next Action 상태 | Next Action이 있는 Action에만 있는 값. `open`(Open)·`done`(종료(수행))·`not_done`(종료(미수행)). 화면 값은 `open`·`done`·`notDone` |
| 종료 상태 | `done`·`not_done` |
| 종료일(`next_action_closed_on`) | 종료 상태로 바꾼 요청의 업무 날짜(TM-R4). Open이거나 Next Action이 없으면 null. 이 문서의 "종료 시각"은 모두 이 종료일이다 |
| 종료 Comment | 상태를 종료로 바꿀 때 함께 보내는 글. 그 Action의 Action Comment가 된다(CM-R15) |
| 진행사항만 Action | Next Action이 없는 Action. 상태가 없다(null) |
| 상태 필터 | Action 검색의 `next_action_status`: `open`·`done`·`not_done`·`closed`(= `done` 또는 `not_done`) |
| 작성자 | Action의 수행자(`actor`). 등록한 사용자이며 바뀌지 않는다(AC-R4, AC-R14) |
| 업무 날짜 | 서버 OS 시간대의 달력 날짜(TM-R4) |

### 2.2 데이터 모델

- `deal_actions`의 이 feature 컬럼(테이블 전체는 AC 2.2 소유, 기준선 `00c3126aa926`, SC)
  - `next_action_status VARCHAR NULL`: `open`·`done`·`not_done`. Next Action이 없으면 NULL. 서버 기본값 없음.
  - `next_action_closed_on DATE NULL`: 종료 상태일 때만 값이 있다(CHECK `ck_deal_actions_next_action_closed_on`).
  - 상태 변경은 `updated_at`도 바꾼다(종료 Comment는 `deal_comments`에 새 행으로 남는다, CM-R15).
- 도메인 객체
  - `NextActionStatus` StrEnum: `label`(Open·종료(수행)·종료(미수행)), `is_closed`, `sort_rank`(open 0·done 1·not_done 2).
  - `NextActionState(status, closed_on)`: Open이면 `closed_on`이 없어야 하고, 종료면 `closed_on`(date)이 있어야 한다(어기면 `InvalidValueError`, 프로그래밍 오류).
  - `NextActionStatusChange(before, after, note)`: 이력용 결과(note는 trim한 종료 Comment).
  - `DealAction.next_action_state`: Next Action이 있으면 반드시 있고 없으면 반드시 없다.
  - `DealActionQuery`(Port 쪽 값 객체): 검색 조건과 `acted_window()`(반개구간). `keyword`는 진행사항·Next Action 또는 Action Comment 본문에 일치한다(CM-R19).
  - `NextActionStatusFilter` StrEnum: `open`·`done`·`not_done`·`closed`, `statuses()`로 상태 묶음을 준다.
  - `DealActionSort` StrEnum 10값(NA-R18).
- 마이그레이션: 날짜 전환 리비전 `b4d7e2a9c613`(SC-R20)이 `next_action_closed_at`을 `next_action_closed_on`으로 바꾼다(NA-R32).

### 2.3 비즈니스 규칙

Next Action 상태 변경(backend)
- **NA-R1** 상태는 Next Action이 있는 Action에만 있다. Action 응답의 `next_action_status`·`next_action_closed_on`은 진행사항만 Action이면 둘 다 null, Open이면 `"open"`·null, 종료면 상태 값과 종료일이다.
- **NA-R2** `PUT /deal-actions/{action_id}/next-action-status` 본문 `{"status": "open"|"done"|"not_done", "comment": "<문자열>"}`(comment는 선택, 기본 `""`). 예전 `memo` 키는 422 `request-validation`이다. 지금 상태와 **다른** 상태로는 어느 쪽이든 바꿀 수 있다: Open→종료(수행)·종료(미수행), 종료(수행)⇄종료(미수행), 종료→Open. 성공하면 200과 바뀐 Action(응답 모양은 AC-R20)이다.
- **NA-R3** 종료 Comment는 CM-R15·CM-R1을 따른다. 비었거나 공백뿐이면 Comment를 만들지 않는다. 종료 상태로 바꿀 때 비어 있지 않으면 그 Action의 Action Comment 1건(작성자 = 요청자)을 만든다. Open으로 되돌리며 비어 있지 않은 Comment를 보내면 422 `invalid-value` "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."이다(공백뿐이면 허용). NUL이 있으면 422 `invalid-value` "Comment에는 NUL 문자를 쓸 수 없습니다"이다. 길이 제한은 없다. Action 내용은 바뀌지 않는다.
- **NA-R4** 종료일: 종료 상태로 바꾸면 그 요청의 업무 날짜(오늘)다. 종료(수행)⇄종료(미수행) 전환도 그 요청의 오늘로 다시 정한다(같은 날이면 값이 같다). Open으로 되돌리면 null이 되고, 그때 만든 Comment는 그대로 남는다. Action 등록 때 이전 Next Action 종료의 종료일도 수행일과 무관하게 오늘이다(AC-R36).
- **NA-R32** 기존 데이터 변환(리비전 `b4d7e2a9c613`, SC-R20): `next_action_closed_on`은 저장된 `next_action_closed_at`을 업무 시간대(서버 OS 로컬)로 바꾼 날짜다. 값이 없던 행은 계속 null이다. 상태·종료일 CHECK(종료 상태일 때만 값)는 새 컬럼 기준으로 다시 만든다. 행 수는 그대로이고 시각만 버린다. downgrade는 종료일의 업무 시간대 00:00으로 되살린다.
- **NA-R5** 상태 변경은 상태·종료 시각과 Action `updated_at`만 바꾼다(Comment는 CM-R15).
  - 그대로인 것: 진행사항·Next Action·Due Date·유형·수행일·작성자·등록 시점 Status·Forecast, Deal `updated_at`.
  - Deal의 최종 업데이트는 바뀌지 않는다(RK-R2). 기한초과는 바뀔 수 있다: 종료하면 그 Next Action은 기한초과 판정에서 빠지고 Open으로 되돌리면 다시 판정 대상이 된다(RK-R4, 2026-11-18).
- **NA-R6** 권한: 업무 쓰기 가드(PL-R6) 때문에 `user`는 403 읽기 전용 문구다. 가드를 지난 뒤 `admin`은 모든 Action, `sales`는 자기가 작성자인 Action만 바꿀 수 있다. 그 밖은 403 `forbidden` "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."다. 도메인 판정도 `user`는 작성자여도 거절한다.
- **NA-R7** 판정 순서(앞에서 거절되면 뒤는 하지 않는다)
  1. 미인증 401 → CSRF 403 → `user` 403(PL-R4~R6)
  2. 요청 형식 422 `request-validation`: id 경로 형식(PL-R15), `status` 누락·null·세 값 밖(`closed`·`notDone`·`DONE` 등 대소문자 구분), `comment`가 문자열 아님, 예전 `memo` 키, 모르는 필드(예: `closed_at`)
  3. 없는 Action 404 `not-found` "Action을 찾을 수 없습니다."
  4. 작성자·admin 아님 403(NA-R6)
  5. Comment NUL 422 → Open으로 되돌리며 Comment 422(NA-R3)
  6. Next Action 없음 409 `invalid-state` "Next Action이 없는 Action은 상태를 바꿀 수 없습니다." → 같은 상태 409 `invalid-state` "이미 {라벨} 상태입니다."(예: "이미 Open 상태입니다.", "이미 종료(수행) 상태입니다.")
- **NA-R8** 이력: 성공하면 그 Deal의 History에 Next Action 줄 정확히 1건을 남긴다.
  - 구분 `action`, 대상 `Next Action`, 변경자 요청자, 변경 시각 요청 시각.
  - 변경 전: `"<Next Action> (Due <YYYY-MM-DD>) · <이전 라벨>"`. 예: "요구사항 문서 전달 (Due 2027-01-15) · Open".
  - 변경 후: 항상 `"<새 라벨>"`(종료 Comment는 이어서 CM-R13의 Comment 등록 줄로 남으므로, Comment가 있는 성공은 History 2건이다). 이전에 남은 이력의 " / Memo: …"는 그대로다.
  - 긴 값은 History 길이 규칙(DD-R20)으로 잘린다.
  - Action 등록 때 이전 Next Action 종료(AC-R7 ④)도 이 형식으로 1건을 남긴다: 변경 전 `"<Next Action> (Due <YYYY-MM-DD>) · Open"`, 변경 후 `"종료(수행)"`(Comment 없음). 이 문구 형식은 NA가 소유하고 AC-R11은 이 규칙을 가리킨다(2026-11-10 결정). 등록 경로의 결과·저장 순서는 AC-037이 검증한다.
- **NA-R9** 원자성: 거절되면(4xx) Action의 상태·종료 시각·Comment와 History가 모두 그대로다.

Action 검색(backend)
- **NA-R10** `GET /deals/{code}/actions`는 로그인한 모든 역할이 쓴다. 응답은 200 `{"items": [Action, ...]}`(키는 `items` 하나)이고 페이지가 없어 조건에 맞는 그 Deal의 Action을 전부 준다. 다른 Deal의 Action은 나오지 않는다.
  - 없는 Deal과 형식이 틀린 code는 404 `not-found` "Deal을 찾을 수 없습니다."다.
  - 전역 검색 경로(`GET /deal-actions`)는 없다(PL-R13의 404).
  - 조건이 없을 때의 기본 순서와 Actions 표 열 구성은 AC-R18·AC-R21이 정하고, 이 문서는 조회 조건·필터·정렬을 정한다(2026-11-10 결정).
- **NA-R11** 조건은 모두 AND다. 조건이 없으면 그 Deal의 Action 전부다.
- **NA-R12** `action_type_id`: 유형 id가 같은 Action. 유형 이름을 바꿔도 같은 id로 같은 Action이 나오고 응답 유형 이름은 지금 이름이다. 없는 id는 오류 없이 0건이다.
- **NA-R13** `actor_user_id`: 작성자 id가 같은 Action. 퇴사한 작성자도 찾는다. 없는 id는 0건이다.
- **NA-R14** `keyword`
  - 앞뒤 공백을 지운 값으로 진행사항·Next Action 중 하나 또는 그 Action의 Action Comment 본문 중 하나라도(CM-R19) 대소문자 구분 없이 부분 일치하면 맞다. 비어 있는(null) 칸은 맞지 않는다.
  - `%`·`_`·`\`는 와일드카드가 아니라 글자 그대로다.
  - 비었거나 공백뿐이면 조건이 없는 것과 같다.
  - 보낸 원문이 100자(코드 포인트)를 넘으면 422 `request-validation`이다.
  - NUL 문자는 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다"다.
- **NA-R15** 수행일 `acted_from`·`acted_to`(날짜). 대상 값은 Action 수행일 `acted_on`(날짜)이다.
  - 양끝을 포함해 날짜로 비교한다: `from ≤ acted_on ≤ to`. 예: 2027-05-20~2027-05-20은 수행일이 그 날인 Action이다.
  - 한쪽만 주면 그쪽만 제한한다.
  - 각 값은 1900-01-01~2999-12-31이어야 한다. 밖이면 422 `invalid-value` "acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(`acted_to`도 같은 형식)다.
  - 시작이 끝보다 늦으면 422 `invalid-value` "수행일 범위의 시작은 끝보다 늦을 수 없습니다."다. 같은 날은 허용한다.
- **NA-R16** Due Date `due_from`·`due_to`(날짜): 양끝 포함이다. 둘 중 하나라도 주면 Due Date가 없는 Action은 빠진다. 시작이 끝보다 늦으면 422 `invalid-value` "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."다. 같은 날은 허용한다. 1900~2999 범위 검사는 없다(현행 유지, 2026-11-10 결정).
- **NA-R17** `next_action_status`: `open`·`done`·`not_done`은 그 상태, `closed`는 `done`·`not_done` 둘 다다. 상태 필터가 있으면 Next Action이 없는 Action은 빠진다. 상태 필터가 없으면 진행사항만 Action도 나온다. 그 밖의 값(`notDone`·`DONE`·`all`·`close`·빈 문자열)은 422 `request-validation`이다.
- **NA-R18** `sort`(기본 `acted_at_desc`)는 아래 10값이고 대소문자를 구분한다. 그 밖은 422 `request-validation`이다.
  - `acted_at_desc`·`acted_at_asc`: 수행일(값 이름은 호환을 위해 그대로 둔다). 수행일이 같으면 `desc`는 id 내림차순(나중에 등록한 것이 앞), `asc`는 id 오름차순이다(AC-R43). 기본값 `acted_at_desc`의 순서는 조건 없는 목록의 기본 순서(AC-R18)와 같다.
  - 나머지 정렬은 주 키 → 수행일 내림차순 → id 내림차순이다. 이 동률 규칙은 방향을 바꿔도 뒤집히지 않는다.
  - `due_date_asc`·`due_date_desc`: Due Date. Due Date가 없는 Action은 방향과 관계없이 맨 뒤다.
  - `actor_asc`·`actor_desc`: 작성자 표시 이름(비어 있으면 로그인 아이디)을 소문자로 바꿔 코드 포인트 순으로 비교한다. 퇴사자도 포함한다.
  - `action_type_asc`·`action_type_desc`: 지금 유형 이름을 소문자로 바꿔 코드 포인트 순으로 비교한다.
  - `next_action_status_asc`·`next_action_status_desc`: Open → 종료(수행) → 종료(미수행) 순(desc는 반대)이다. 상태가 없는 Action은 방향과 관계없이 맨 뒤다.
- **NA-R19** 그 밖의 쿼리 형식 오류는 422 `request-validation`이다.
  - 모르는·폐지된 파라미터: `offset`, `limit`, `deal_code`, `action_type`(구 enum), `actor`(자유 텍스트), 그 밖의 이름.
  - 형식이 틀린 값: id가 양의 정수 문자열이 아님(PL-R15), 날짜가 아님(`2027-13-40`, `soon`).
- **NA-R20** 검색 판정 순서
  1. 미인증 401
  2. 쿼리 형식 422 `request-validation`(NA-R14 길이, NA-R17~R19)
  3. 형식이 틀린 code 404
  4. 조건 값 422 `invalid-value`(NA-R14 NUL, NA-R15, NA-R16). 이 단계 안에서는 수행일 범위(1900~2999) → 수행일 역전 → Due 역전 → 검색어 NUL 순으로 처음 걸린 것 하나만 알린다(2026-11-11 리뷰 반영, Fake도 같은 순서)
  5. 없는 Deal 404

화면(frontend)
- **NA-R21** 상태 칸(Actions 표 "상태" 열)
  - Next Action이 없는 행은 "—"이고 버튼이 없다. 있으면 라벨(Open·종료(수행)·종료(미수행))을 보인다.
  - 상태 버튼은 쓰기 권한이 있고 그 행을 바꿀 수 있는 사람(admin, 또는 작성자 본인인 sales)에게만 보인다. 다른 sales와 `user`는 라벨만 본다.
  - 버튼은 지금 상태를 뺀 나머지다: Open 행은 "종료(수행)"·"종료(미수행)", 종료(수행) 행은 "종료(미수행)"·"Open으로", 종료(미수행) 행은 "종료(수행)"·"Open으로".
  - 각 버튼은 그 행의 Next Action 칸을 설명으로 연결한다(`aria-describedby`). 상태 변경 요청이 진행 중이면 모든 상태 버튼이 비활성이다.
  - 같은 상태 버튼(권한·버튼 구성·동작 동일)이 Action 상세 팝업(AC-R49)의 Next Action 상태 줄에도 있다(2026-11-16 확정, AC-R54, AC-144·AC-145). 팝업에서 누른 "종료(수행)"·"종료(미수행)"은 아래 종료 팝업(NA-R22)이 상세 팝업 위에 겹쳐 열리고, "Open으로"는 NA-R23대로 바로 요청한다. 성공하면 종료 팝업만 닫히고 상세 팝업은 열린 채다.
- **NA-R22** 종료 팝업
  - "종료(수행)"·"종료(미수행)"을 누르면 확인 대화상자가 열린다(종료 상태 사이 전환 포함).
    - 제목 "Next Action 종료(수행)"(또는 "Next Action 종료(미수행)")
    - 문구 `"<Next Action>"을(를) <라벨>(으)로 종료합니다. 남길 내용이 없으면 비워 두세요.`
    - 글 칸 "Comment에 남길 내용(선택)"(CM-R43), 버튼 "종료"·"취소"
  - "종료"는 입력한 Comment(빈 값 가능)로 상태 변경을 요청한다.
    - 성공해야 팝업이 닫힌다.
    - 실패하면 팝업과 입력한 Comment가 그대로이고 팝업 안 오류 배너에 서버 `detail`을 보인다.
  - "취소"와 Esc는 요청 없이 닫는다(입력한 Comment는 버린다).
- **NA-R23** "Open으로"는 팝업 없이 Comment `""`로 바로 요청한다. 실패하면 탭의 오류 배너에 서버 `detail`을 보인다.
- **NA-R24** 상태 변경에 성공하면 Action 목록, 그 Deal의 History, Deal(목록·상세), Forecast, Action 유형, 라이선스 계약 캐시를 무효화한다. 그래서 행의 라벨, 상세 팝업(AC-R49)의 Comment 영역·Comments 탭과 읽지 않은 수(CM-R44), 요약 바의 Next Action 상태(RK-R17)가 새 값으로 바뀐다(Comment 목록·읽지 않은 수도 무효화, CM-R44).
- **NA-R25** 검색 바(`role="search"`, 이름 "Action 검색")
  - 칸 순서:
    1. 유형: "전체" + Action 유형 이름
    2. 담당자: 퇴사자 포함 사용자 선택, 퇴사자는 "<이름>(퇴사)"
    3. 키워드: `maxLength` 100, placeholder "진행사항·Next Action·Comment"
    4. 수행일(NA-R26)
    5. 기한(NA-R26)
    6. Next Action 상태: "전체"·"Open"·"종료(수행)"·"종료(미수행)"·"종료(전체)"
  - 버튼은 "검색"·"초기화"이고 정렬 입력은 없다. 처음엔 모든 칸이 전체·빈 값이다.
  - 조건은 "검색"(Enter 제출 포함)을 눌러야 적용된다.
  - 질의에는 채운 조건만 넣는다: 키워드는 trim, 빈 값은 보내지 않음, "종료(전체)"는 `closed`, "종료(미수행)"은 `not_done`.
- **NA-R26** 기간 칸(수행일·기한)
  - 수행일 선택지: 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정. 기한 선택지는 같은 목록의 "직접 지정" 앞에 향후 1개월·향후 2개월이 더 있다.
  - 프리셋 날짜는 서버 `GET /deals/updated-periods`(DL-R17)에서 받는다. 수행일은 `periods`, 향후는 `upcoming`을 쓴다. 응답이 오기 전이나 읽지 못했으면 프리셋 선택지가 비활성이고, 읽기 실패면 오류 배너를 보인다.
  - 프리셋을 고른 채 "검색"하면 그때 프리셋을 서버에서 새로 받아 그 `from`·`to`로 검색한다(자정이 지나면 날짜가 바뀐다). 프리셋을 고르지 않았으면 다시 받지 않는다.
    - 새로 받기가 실패하면 질의를 바꾸지 않고 오류 배너를 보인다.
    - 검색·초기화가 그 뒤에 또 있었으면 늦게 온 이전 응답은 버린다.
  - "직접 지정"을 고르면 "<칸> 시작"·"<칸> 끝" 날짜 칸(`DateInput` UI-R1~R11, `yyyymmdd` 입력 가능 — UI-R2)이 나타난다.
    - 채운 날짜만 보낸다.
    - 날짜가 틀렸거나 덜 쳤으면 "검색"을 눌러도 검색하지 않고 칸에 문구를 보인다. 다시 고치기 시작하면 문구를 지운다.
    - 프리셋·전체로 바꾸면 날짜 칸을 숨기고 입력한 날짜는 쓰지 않는다.
  - 범위가 거꾸로면 화면은 막지 않고 서버 문구(NA-R15·R16)를 탭 오류 배너로 보인다.
- **NA-R27** "초기화"는 모든 칸을 처음 값으로 돌리고 조건 없이 다시 조회한다. 기다리던 프리셋 응답은 버린다. 정렬은 그대로다.
- **NA-R28** 머리글 정렬
  - 정렬할 수 있는 머리글은 수행일·유형·Due Date·상태 4개(버튼)다. 나머지 열(진행사항·Next Action)은 정렬하지 않는다. 담당자 열이 없어져(AC-R21, 2026-11-16) 화면은 담당자 정렬(`actor_asc`·`actor_desc`)을 보내지 않지만 서버 정렬 값(NA-R18)과 게이트웨이 변환(NA-R30)은 그대로다.
  - 처음은 수행일 내림차순이다(`aria-sort`로 표시).
  - 같은 머리글을 다시 누르면 방향이 바뀐다. 다른 머리글은 자연 방향(수행일 내림차순, 나머지 오름차순)으로 시작한다.
  - 정렬은 서버 `sort`로 보내고 화면은 서버 순서를 그대로 보인다(다시 정렬하지 않음).
  - 정렬과 검색 조건은 따로 유지된다: 정렬을 바꿔도 적용된 조건이 남고, 다시 검색하거나 초기화해도 정렬이 남는다.
- **NA-R29** 결과 표시
  - 처음 읽는 동안 "불러오는 중…"이다. 새 조건으로 다시 읽는 동안에는 직전 결과를 계속 보인다.
  - 결과가 0건이면 조건이 하나라도 적용돼 있을 때 "조건에 맞는 Action이 없습니다.", 아니면 "등록된 Action이 없습니다."다. 정렬은 조건으로 치지 않는다.
  - 조회 오류는 오류 배너에 서버 `detail`을 보인다.
- **NA-R30** 게이트웨이 요청
  - HTTP `actions.list`는 `GET /api/v1/deals/{code}/actions`에 채운 조건만 쿼리로 보낸다(`offset`·`limit`·구 `action_type` 없음). 정렬은 열·방향을 `sort` 값으로 바꾼다(예: `type`+`asc` → `action_type_asc`, `nextActionStatus`+`desc` → `next_action_status_desc`).
  - HTTP `actions.changeNextActionStatus`는 `PUT /api/v1/deal-actions/{id}/next-action-status`에 `{status, comment}`(화면 `notDone` → `not_done`)를 보내고 응답을 화면 Action으로 바꾼다.
  - Fake 게이트웨이는 같은 상태 변경 규칙(권한·검사 순서·종료 Comment·이력, CM-R15)과 검색·정렬 규칙을 따른다. 서버와 달랐던 곳은 **Fake를 서버 동작에 맞춘다(2026-11-10 결정)**: 수행일 1900~2999 범위 밖 422 `invalid-value`(NA-R15), 검색어 NUL 422 `invalid-value`(NA-R14), 종료 Comment NUL 422 "Comment에는 NUL 문자를 쓸 수 없습니다", Open+Comment 422 "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."(CM-R15).
- **NA-R31** 게이트웨이 오류: HTTP 게이트웨이는 4xx를 서버 상태·`detail` 그대로의 `ApiError`로 넘긴다(범위 역전 422, 없는 Deal 404, 같은 상태 409 등).

### 2.4 상태와 전이

| 지금 \ 요청 | `open` | `done` | `not_done` |
| --- | --- | --- | --- |
| Open | 409 이미 Open | 종료(수행), 종료일=오늘, 종료 Comment 등록(비어 있지 않을 때) | 종료(미수행), 종료일=오늘, 종료 Comment 등록(비어 있지 않을 때) |
| 종료(수행) | Open, 종료일 null(Comment 있으면 422) | 409 이미 종료(수행) | 종료(미수행), 종료일=오늘, 종료 Comment 등록(비어 있지 않을 때) |
| 종료(미수행) | Open, 종료일 null(Comment 있으면 422) | 종료(수행), 종료일=오늘, 종료 Comment 등록(비어 있지 않을 때) | 409 이미 종료(미수행) |
| 상태 없음(진행사항만) | 409 Next Action 없음 | 409 Next Action 없음 | 409 Next Action 없음 |

다른 feature가 일으키는 전이(AC 2.4 소유):
- Action 등록: Next Action이 있으면 Open, 없으면 상태 없음(AC-R4).
- Action 수정: Next Action을 비우면 상태 없음, 새로 채우면 Open, 이미 있던 Next Action만 고치면 상태 유지(AC-R14).
- 이전 Next Action 종료(등록과 함께): 종료(수행), Comment 없음(AC-R7, 이력 문구는 NA-R8).

### 2.5 권한

| 행동 | 미인증 | user | sales | admin |
| --- | --- | --- | --- | --- |
| `GET /deals/{code}/actions`(검색·정렬) | 401 | 가능 | 가능 | 가능 |
| `PUT /deal-actions/{id}/next-action-status` | 401 | 403(읽기 전용) | 자기 Action만(아니면 403) | 모든 Action |
| 화면: 검색 바·머리글 정렬 | 로그인 화면 | 가능 | 가능 | 가능 |
| 화면: 상태 버튼 | — | 없음 | 자기 Action 행만 | 모든 행 |

### 2.6 API 계약 (`/api/v1`)

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| PUT `/deal-actions/{action_id}/next-action-status` | `NextActionStatusRequest` | 200 `DealActionResponse` | 401, 403 `csrf`, 403 `forbidden`(읽기 전용·작성자 아님), 404 `not-found`, 409 `invalid-state`, 422 `request-validation`, 422 `invalid-value` |
| GET `/deals/{code}/actions` | 쿼리 `DealActionSearchParams` | 200 `DealActionList` | 401, 404 `not-found`, 422 `request-validation`, 422 `invalid-value` |

- `NextActionStatusRequest`: `{"status": "done", "comment": "견적 전달 완료"}`. `status: NextActionStatus`(필수), `comment: str = ""`, 모르는 필드 거절(`RequestModel`).
- `DealActionList`: `{"items": [DealActionResponse, ...]}`. 이 feature 필드 `next_action_status: "open"|"done"|"not_done"|null`, `next_action_closed_on: date|null`(`YYYY-MM-DD`). 나머지 필드는 AC-R20.
- `DealActionSearchParams`(모두 선택, 모르는 파라미터 거절)

| 파라미터 | 값 | 규칙 |
| --- | --- | --- |
| `action_type_id` | 양의 정수 문자열 | NA-R12 |
| `actor_user_id` | 양의 정수 문자열 | NA-R13 |
| `keyword` | 문자열 최대 100자 | NA-R14 |
| `acted_from`·`acted_to` | 날짜 | NA-R15 |
| `due_from`·`due_to` | 날짜 | NA-R16 |
| `next_action_status` | `open`·`done`·`not_done`·`closed` | NA-R17 |
| `sort` | 10값, 기본 `acted_at_desc` | NA-R18 |

- 라우터: `BusinessRouter(prefix="/api/v1", tags=["deal-actions"])`(GET은 로그인만, PUT은 업무 쓰기 가드).
- 유스케이스와 Port
  - `ChangeNextActionStatus(uow_factory, clock).execute(action_id, NextActionStatusInput(status, comment), Actor)`
  - `ListDealActions(uow_factory).execute(DealActionQuery)`
  - `DealActionRepository.search(query) -> Sequence[DealAction]`·`get(action_id)`·`update(action)`
- 새 오류 type 없음.

### 2.7 화면 동작

NA-R21~R31.

### 2.8 오류와 메시지

| 상황 | 상태·type | 문구 |
| --- | --- | --- |
| 작성자가 아닌 sales의 상태 변경 | 403 `forbidden` | 본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다. |
| user의 상태 변경 | 403 `forbidden` | 이 작업을 할 권한이 없습니다(읽기 전용 계정) (PL-R6) |
| 없는 Action | 404 `not-found` | Action을 찾을 수 없습니다. |
| 없는·형식이 틀린 Deal의 Action 목록 | 404 `not-found` | Deal을 찾을 수 없습니다. |
| Next Action 없는 Action의 상태 변경 | 409 `invalid-state` | Next Action이 없는 Action은 상태를 바꿀 수 없습니다. |
| 지금과 같은 상태 | 409 `invalid-state` | 이미 Open 상태입니다. / 이미 종료(수행) 상태입니다. / 이미 종료(미수행) 상태입니다. |
| Open으로 되돌리며 Comment | 422 `invalid-value` | Open으로 되돌릴 때는 Comment를 남길 수 없습니다. |
| 종료 Comment NUL | 422 `invalid-value` | Comment에는 NUL 문자를 쓸 수 없습니다 |
| 검색어 NUL | 422 `invalid-value` | 검색어에는 NUL 문자를 쓸 수 없습니다 |
| 수행일 범위 역전 | 422 `invalid-value` | 수행일 범위의 시작은 끝보다 늦을 수 없습니다. |
| Due Date 범위 역전 | 422 `invalid-value` | Due Date 범위의 시작은 끝보다 늦을 수 없습니다. |
| 수행일 1900~2999 밖 | 422 `invalid-value` | acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다 (`acted_to`도 같음) |
| 본문·쿼리 형식 오류 | 422 `request-validation` | 공통 문구(PL-R12) |
| 화면: 결과 0건(조건 있음/없음) | 안내 | 조건에 맞는 Action이 없습니다. / 등록된 Action이 없습니다. |

## 3. Business use case

### NA-UC1 Next Action 종료
- 행위자: 작성자 본인(sales) 또는 admin
- 사전 조건: Next Action이 있는 Action이 있다
- 기본 흐름: Actions 탭에서 그 행의 "종료(수행)"(또는 "종료(미수행)")을 누르고, 팝업에 남길 내용을 쓰거나 비운 채 "종료"를 누른다. 상태·종료 시각이 남고 입력한 내용은 그 Action의 Action Comment로 등록되며 History에 1건이 남는다(NA-R2~R5, R8, R22, R24)
- 대안: 종료(수행)⇄종료(미수행)으로 바로 바꾼다. 팝업을 취소하거나 Esc를 누르면 아무것도 바뀌지 않는다
- 예외: 그사이 같은 상태가 됐으면 409 문구를 팝업 안에 보이고 입력한 Comment를 유지한다. 권한이 없으면 403, Action이 없어졌으면 404
- 결과: 행과 요약 바가 새 상태를 보인다

### NA-UC2 종료한 Next Action 되돌리기
- 행위자: 작성자 본인(sales) 또는 admin
- 사전 조건: 종료 상태인 Action이 있다
- 기본 흐름: "Open으로"를 누르면 팝업 없이 Open이 되고 종료 시각이 지워진다. 만든 Comment는 그대로 남는다(NA-R4, R23)
- 예외: API로 Comment를 함께 보내면 422
- 결과: History에 "… · 종료(수행)" → "Open" 1건

### NA-UC3 상태 변경 거절
- 행위자: 권한 없는 사용자, 또는 규칙에 맞지 않는 요청
- 기본 흐름: 판정 순서(NA-R7)대로 401·403·422·404·409로 거절한다
- 결과: 상태·Comment·History가 그대로다(NA-R9)

### NA-UC4 Action 찾기
- 행위자: 로그인한 사용자
- 사전 조건: Deal이 있다
- 기본 흐름: 검색 바에서 유형·담당자·키워드·수행일·기한·Next Action 상태를 정하고 "검색"을 누른다. 서버는 조건을 AND로 걸러 그 Deal의 Action 전부를 준다(NA-R10~R17, R25~R27, R29)
- 대안: 기간 프리셋을 고르면 검색할 때 서버 날짜로 바뀐다. "초기화"는 조건만 지운다
- 예외: 범위가 거꾸로이거나 형식이 틀리면 422, Deal이 없으면 404
- 결과: 맞는 Action이 표에 나오거나 빈 결과 문구가 나온다

### NA-UC5 Action 정렬
- 행위자: 로그인한 사용자
- 기본 흐름: 머리글(수행일·유형·Due Date·상태)을 누르면 서버가 그 순서로 준다(NA-R18, R28)
- 결과: 조건은 유지되고, 빈 값(Due Date·상태 없음)은 방향과 관계없이 맨 뒤다

## 4. BDD 테스트 케이스

| 코드 | 케이스 | 규칙·UC | 층 | 테스트 위치 |
| --- | --- | --- | --- | --- |
| NA-001 | (폐기 2026-11-17) 종료 메모의 Memo 덧붙임 — CM-031·CM-033이 대신함 | NA-R3 | backend | — |
| NA-002 | (폐기 2026-11-17) 종료 메모의 Memo 덧붙임 — CM-031·CM-033이 대신함 | NA-R3 | backend | — |
| NA-003 | (폐기 2026-11-17) 종료 메모의 Memo 덧붙임 — CM-031·CM-033이 대신함 | NA-R3 | backend | — |
| NA-004 | 종료(수행)에서 종료(미수행)으로 바로 바꾸면 종료일이 그 요청의 오늘로 다시 정해진다 | NA-R2, NA-R4, NA-UC1 | backend | `domain/test_next_action_status.py` |
| NA-005 | Open으로 되돌리면 종료 시각이 없어지고 만든 Comment가 남는다 | NA-R4, NA-UC2 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py` |
| NA-006 | Open으로 되돌리며 Comment를 보내면 422이고 종료 상태가 그대로이며, 공백뿐인 Comment는 허용된다 | NA-R3, NA-R9, NA-UC2 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py` |
| NA-007 | 지금과 같은 상태로 바꾸면 409 "이미 … 상태입니다."이고 Comment 수·History가 그대로다 | NA-R7, NA-R9, NA-UC3 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py` |
| NA-008 | Next Action이 없는 Action의 상태를 바꾸면 409이고 Comment 수·History가 그대로다 | NA-R1, NA-R7, NA-UC3 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py` |
| NA-009 | 종료 Comment에 NUL 문자가 있으면 422 invalid-value이고 Action이 그대로다 | NA-R3, NA-UC3 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py`, `test/fake/gateway/nextActionStatus.rules.test.ts` |
| NA-010 | 도메인 검사는 NUL → Open+Comment → Next Action 없음 → 같은 상태 순서다 | NA-R7, NA-UC3 | backend | `domain/test_next_action_status.py` |
| NA-011 | 상태 변경은 다른 내용·수행 정보·스냅숏과 Deal 수정 시각을 바꾸지 않는다 | NA-R5, NA-UC1 | backend | `application/test_change_next_action_status.py`, `domain/test_next_action_status.py` |
| NA-012 | admin은 다른 사람의 Action 상태를 바꿀 수 있고 History 변경자는 admin이다 | NA-R6, NA-R8, NA-UC1 | backend | `application/test_change_next_action_status.py`, `domain/test_deal_action_entity.py` |
| NA-013 | 작성자가 아닌 sales는 403 고정 문구이고 Action·History가 그대로다 | NA-R6, NA-R9, NA-UC3 | backend | `application/test_change_next_action_status.py`, `domain/test_deal_action_entity.py` |
| NA-014 | user 역할은 자기가 작성자로 기록된 Action이어도 상태를 바꿀 수 없다 | NA-R6, NA-UC3 | backend | `application/test_change_next_action_status.py`, `domain/test_deal_action_entity.py` |
| NA-015 | 없는 Action은 작성자 확인보다 먼저 404다 | NA-R7, NA-UC3 | backend | `application/test_change_next_action_status.py` |
| NA-016 | 본문의 상태 값·형식이 틀리거나 모르는 필드가 있으면 422 request-validation이다 | NA-R7, NA-UC3 | backend | `web/test_next_action_status_request.py` |
| NA-017 | 상태가 바뀔 때마다 History에 "Next Action" 1건이 정해진 문구로 남는다 | NA-R8, NA-UC1, NA-UC2 | backend | `application/test_change_next_action_status.py`, `domain/test_action_history.py` |
| NA-018 | (폐기 2026-11-17) 긴 종료 메모 이력 — CM-011이 대신함 | NA-R8 | backend | — |
| NA-019 | 조건이 없으면 그 Deal의 Action 전부가 페이지 없이 수행일 최신순으로 나온다 | NA-R10, NA-R11, NA-R18, NA-UC4 | backend | `application/test_deal_action_query.py`, `application/test_list_deal_actions.py`, `test/fake/gateway/actions.test.ts`, `web/test_deal_action_openapi.py`, `web/test_deal_action_search_params.py` |
| NA-020 | 다른 Deal의 Action은 목록에 나오지 않는다 | NA-R10, NA-UC4 | backend | `application/test_list_deal_actions.py` |
| NA-021 | 없는 Deal이나 형식이 틀린 code의 Action 목록은 404다 | NA-R10, NA-UC4 | backend | `application/test_list_deal_actions.py`, `test/fake/gateway/actions.listOrder.test.ts`, `web/test_deal_action_search_params.py`, `test/fake/gateway/actions.rules.test.ts` |
| NA-022 | 전역 Action 검색 경로는 없고 개별 Action 경로만 있다 | NA-R10 | backend | `application/test_deal_action_query.py`, `web/test_deal_action_openapi.py` |
| NA-023 | 유형·담당자·검색어 조건은 AND로 결합된다 | NA-R11, NA-UC4 | backend | `application/test_list_deal_actions.py`, `web/test_deal_action_search_params.py`, `gateway/contract/actions.contract.ts` |
| NA-024 | 유형 id로 거르면 이름을 바꿔도 같은 Action이 지금 이름으로 나오고 없는 id는 0건이다 | NA-R12, NA-UC4 | backend | `application/test_list_deal_actions.py` |
| NA-025 | 담당자 조건은 퇴사한 작성자의 Action도 찾고 없는 사용자는 0건이다 | NA-R13, NA-UC4 | backend | `application/test_list_deal_actions_order_and_status.py` |
| NA-026 | 검색어는 진행사항·Next Action·Action Comment 본문에서 대소문자 구분 없이 부분 일치한다 | NA-R14, NA-UC4 | backend | `application/test_list_deal_actions.py`, `gateway/contract/actions.contract.ts`, `repositories/test_deal_action_search_contract.py` |
| NA-027 | 검색어의 %·_는 글자 그대로이고 앞뒤 공백은 무시하며 공백뿐이면 조건이 없다 | NA-R14, NA-UC4 | backend | `application/test_deal_action_query.py`, `application/test_list_deal_actions.py` |
| NA-028 | 검색어 100자는 되고 101자는 422 request-validation, NUL은 422 invalid-value다 | NA-R14, NA-UC4 | backend | `application/test_deal_action_query.py`, `test/fake/gateway/actions.listOrder.test.ts`, `test/fake/gateway/actions.queryRules.test.ts`, `web/test_deal_action_search_params.py` |
| NA-029 | 수행일 조건은 수행일 날짜를 양끝 포함으로 비교한다 | NA-R15, NA-UC4 | backend | `application/test_deal_action_query.py`, `application/test_list_deal_actions.py`, `web/test_deal_action_search_params.py`, `gateway/contract/actions.contract.ts`, `test/fake/gateway/actions.rules.test.ts` |
| NA-030 | Due Date 범위는 양끝을 포함하고 Due Date가 없는 Action은 빠진다 | NA-R16, NA-UC4 | backend | `application/test_list_deal_actions.py`, `web/test_deal_action_search_params.py`, `gateway/contract/actions.contract.ts`, `test/fake/gateway/actions.rules.test.ts` |
| NA-031 | 시작이 끝보다 늦은 범위는 422이고 문구가 범위 종류를 알려 주며 같은 날은 허용된다 | NA-R15, NA-R16, NA-UC4 | backend | `application/test_deal_action_query.py`, `gateway/contract/actions.contract.ts`, `test/fake/gateway/actions.rules.test.ts` |
| NA-032 | 1900~2999년 밖의 수행일은 422 invalid-value이고 양 끝 날짜는 조회된다 | NA-R15, NA-UC4 | backend | `application/test_date_range_bounds.py`, `test/fake/gateway/actions.queryRules.test.ts` |
| NA-033 | 상태 필터는 그 상태만 고르고 closed는 종료 둘 다이며 Next Action 없는 Action은 빠진다 | NA-R17, NA-UC4 | backend | `application/test_list_deal_actions_order_and_status.py`, `application/test_next_action_status_filter.py`, `web/test_deal_action_search_params.py` |
| NA-034 | 상태 필터는 다른 조건과 AND이고 되돌린 Action은 open에 나온다 | NA-R17, NA-R11, NA-UC4 | backend | `application/test_list_deal_actions_order_and_status.py` |
| NA-035 | 허용하지 않는 상태 필터 값은 422 request-validation이다 | NA-R17, NA-UC4 | backend | `application/test_next_action_status_filter.py`, `web/test_deal_action_openapi.py`, `web/test_deal_action_search_params.py` |
| NA-036 | 모르는·폐지된 쿼리와 형식이 틀린 id·날짜는 422 request-validation이다 | NA-R19, NA-UC4 | backend | `application/test_deal_action_query.py`, `application/test_query_nul.py`, `web/test_deal_action_openapi.py`, `web/test_deal_action_search_params.py` |
| NA-037 | 형식이 틀린 code는 범위 오류보다 먼저 404이고 없는 Deal은 범위 오류 다음이다 | NA-R20, NA-UC4 | backend | `web/test_deal_action_search_params.py` |
| NA-038 | 수행일 정렬은 양방향이고 같은 날이면 내림차순은 나중 등록, 오름차순은 먼저 등록이 앞이다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions.py`, `application/test_list_deal_actions_order_and_status.py`, `test/fake/gateway/actions.test.ts` |
| NA-039 | Due Date 정렬은 Due Date가 없는 Action을 방향과 관계없이 맨 뒤에 두고 동률은 최신 수행이 먼저다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions.py`, `application/test_list_deal_actions_order_and_status.py`, `test/fake/gateway/actions.test.ts`, `gateway/contract/actions.contract.ts` |
| NA-040 | 담당자 정렬은 표시 이름(없으면 로그인 아이디)을 대소문자 구분 없이 비교한다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions_order_and_status.py`, `test/fake/gateway/actions.test.ts` |
| NA-041 | 유형 정렬은 지금 유형 이름을 대소문자 구분 없이 비교한다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions_order_and_status.py`, `test/fake/gateway/actions.test.ts`, `gateway/contract/actions.contract.ts` |
| NA-042 | 상태 정렬은 Open·종료(수행)·종료(미수행) 순이고 상태 없음은 방향과 관계없이 맨 뒤다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions_order_and_status.py`, `test/fake/gateway/actions.test.ts` |
| NA-043 | 정렬 값은 정해진 10개만 받고 대소문자를 구분한다 | NA-R18, NA-UC5 | backend | `application/test_deal_action_query.py`, `web/test_deal_action_openapi.py`, `web/test_deal_action_search_params.py` |
| NA-044 | 화면: 상태 칸은 라벨을 보이고 Next Action 없는 행은 "—"이며 작성자에게 Open 행의 종료 버튼 둘이 보인다 | NA-R21, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-045 | 화면: 상태 버튼은 admin에게 보이고 다른 sales·user에게는 라벨만 보인다 | NA-R21, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-046 | 화면: 종료 행의 버튼은 다른 종료 상태와 "Open으로"다 | NA-R21, NA-UC1, NA-UC2 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-047 | 화면: 종료 대화상자를 거쳐 입력한 Comment로 종료하고 행에 새 상태가, 상세 팝업에 새 Comment가 보인다 | NA-R22, NA-R24, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-048 | 화면: 팝업의 취소와 Esc는 상태를 바꾸지 않는다 | NA-R22, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-049 | 화면: "Open으로"는 팝업 없이 바로 되돌린다 | NA-R23, NA-UC2 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-050 | 화면: 서버가 거절하면 팝업이 열린 채 Comment가 남고 서버 문구가 보이며 성공해야 닫힌다 | NA-R22, NA-R23, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-051 | 화면: 상태를 바꾸면 요약 바의 Next Action 상태도 바뀐다 | NA-R24, NA-UC1 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-052 | 화면: 검색 바는 정해진 칸과 버튼을 갖고 정렬 입력이 없다 | NA-R25, NA-UC4 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx`, `features/deals/detail/ActionsTab.sort.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| NA-053 | 화면: 키워드·유형·담당자(퇴사자 포함)로 검색한다 | NA-R25, NA-UC4 | frontend | `features/deals/detail/ActionsTab.test.tsx`, `features/deals/detail/ActionForm.type.test.tsx` |
| NA-054 | 화면: Next Action 상태로 검색한다 | NA-R25, NA-UC4 | frontend | `features/deals/detail/ActionsTab.nextActionStatus.test.tsx` |
| NA-055 | 화면: 수행일·기한 선택지와 기본값 | NA-R26, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.period.test.tsx` |
| NA-056 | 화면: 기간 프리셋은 검색할 때 서버에서 새로 받은 날짜로 보낸다 | NA-R26, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.period.test.tsx` |
| NA-057 | 화면: 직접 지정은 채운 날짜만 보내고 틀리거나 덜 친 날짜면 검색하지 않는다 | NA-R26, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.period.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| NA-058 | 화면: 프리셋을 받지 못하면 프리셋이 비활성이고 늦게 온 이전 응답은 버린다 | NA-R26, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.period.test.tsx` |
| NA-059 | 화면: 초기화는 조건을 비우고 전체 목록을 다시 보이며 정렬은 남긴다 | NA-R27, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.period.test.tsx`, `features/deals/detail/ActionsTab.sort.test.tsx`, `features/deals/detail/ActionsTab.test.tsx` |
| NA-060 | 화면: 키워드는 100자까지 입력되고 100자 검색은 오류가 아니다 | NA-R25, NA-R14, NA-UC4 | frontend | `features/deals/detail/ActionSearchBar.test.tsx` |
| NA-061 | 화면: 빈 결과 문구는 조건 적용 여부로 나뉘고 정렬은 조건이 아니다 | NA-R29, NA-UC4 | frontend | `features/deals/detail/ActionsTab.sort.test.tsx` |
| NA-062 | 화면: 직접 지정 범위가 거꾸로면 서버 문구를 오류 배너로 보인다 | NA-R26, NA-R29, NA-UC4 | frontend | `features/deals/detail/ActionsTab.test.tsx` |
| NA-063 | 화면: 정렬 머리글은 4개이고 같은 열은 방향을 바꾸며 다른 열은 자연 방향으로 시작한다 | NA-R28, NA-UC5 | frontend | `features/deals/detail/ActionTable.sort.test.tsx`, `features/deals/detail/ActionsTab.sort.test.tsx`, `features/deals/detail/ActionsTab.test.tsx`, `features/deals/detail/actionSort.test.ts` |
| NA-064 | 화면: 서버가 준 순서를 그대로 보인다 | NA-R28, NA-UC5 | frontend | `features/deals/detail/ActionsTab.sort.test.tsx` |
| NA-065 | 화면: 정렬을 바꿔도 조건이 남고 다시 검색해도 정렬이 남는다 | NA-R28, NA-UC5 | frontend | `features/deals/detail/ActionsTab.sort.test.tsx` |
| NA-066 | HTTP 게이트웨이는 채운 조건·정렬·상태 변경 본문을 서버 이름으로 보낸다 | NA-R30 | frontend | `gateway/http/actions.test.ts`, `gateway/http/mappers/action.test.ts` |
| NA-067 | HTTP 게이트웨이는 범위 역전 422와 없는 Deal 404를 서버 문구 그대로 넘긴다 | NA-R31 | frontend | `gateway/http/actions.test.ts` |
| NA-068 | Fake 게이트웨이는 서버와 같은 상태 변경·검색·정렬 규칙을 따른다 | NA-R30, NA-R3, NA-R14, NA-R15 | frontend | `test/fake/gateway/actions.listOrder.test.ts`, `test/fake/gateway/actions.queryRules.test.ts`, `test/fake/gateway/actions.test.ts`, `test/fake/gateway/nextActionStatus.rules.test.ts`, `gateway/contract/actionsStatus.contract.ts`, `test/fake/gateway/actions.rules.test.ts` |
| NA-069 | 주 키가 같은 정렬의 동률은 수행일 내림차순 다음 id 내림차순이다 | NA-R18, NA-UC5 | backend | `application/test_list_deal_actions_order_and_status.py`, `repositories/test_deal_action_sort_contract.py` |
| NA-070 | 종료하면 응답 next_action_closed_on은 요청의 업무 날짜이고 Open으로 되돌리면 null이다 | NA-R1, NA-R4 | backend | `application/test_change_next_action_status.py`, `web/test_deal_action_response_nullable.py` |
| NA-071 | 마이그레이션은 종료 시각을 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다 | NA-R32 | backend | `infra/schema/test_business_dates_migration.py` |
| NA-072 | 게이트웨이·Fake: 종료일을 closedOn 날짜로 매핑하고 Fake는 Fake 시계의 오늘로 정한다 | NA-R4, NA-R30 | frontend | `gateway/http/mappers/action.test.ts`, `test/fake/gateway/actions.dates.test.ts` |

### NA-001 (폐기 2026-11-17)
- 폐기: 종료 메모를 Memo에 덧붙이는 동작이 없어졌다(Comment 분리). CM-031·CM-033이 대신한다.

### NA-002 (폐기 2026-11-17)
- 폐기: 종료 메모를 Memo에 덧붙이는 동작이 없어졌다(Comment 분리). CM-031·CM-033이 대신한다.

### NA-003 (폐기 2026-11-17)
- 폐기: 종료 메모를 Memo에 덧붙이는 동작이 없어졌다(Comment 분리). CM-031·CM-033이 대신한다.

### NA-004 종료 상태 사이를 바로 전환한다
- Given 2027-01-10에 종료(수행)된 Action이 있다
- When 작성자가 2027-01-12에 `not_done`, Comment "취소됨"으로 바꾼다
- Then 상태는 `not_done`, 종료일은 2027-01-12, Action Comment "취소됨"이 1건 만들어진다(CM-R15)

### NA-005 Open으로 되돌린다
- Given 종료 Comment "끝"과 함께 종료(수행)한 Action이 있다
- When 작성자가 `open`으로 바꾼다
- Then 상태는 `open`, 종료 시각은 null이고 그때 만든 Comment "끝"은 그대로 남는다

### NA-006 Open으로 되돌리며 Comment를 보낸다
- Given 종료(수행)된 Action이 있다
- When 작성자가 `open`, `comment` "되돌리며 Comment"로 바꾼다
- Then 422 `invalid-value` "Open으로 되돌릴 때는 Comment를 남길 수 없습니다."이고 상태·종료 시각·Comment 수·History가 그대로다. 같은 요청을 `comment` "   "로 보내면 Open이 된다

### NA-007 같은 상태로 바꾼다
- Given Open Action과, 종료 Comment "첫 종료"로 종료(수행)된 Action이 있다
- When 작성자가 Open Action을 `open`으로, 종료(수행) Action을 `done`·`comment` "또 종료"로 바꾼다
- Then 각각 409 `invalid-state` "이미 Open 상태입니다.", "이미 종료(수행) 상태입니다."이고 Comment 수·종료 시각·History 건수가 그대로다

### NA-008 Next Action 없는 Action의 상태를 바꾼다
- Given 진행사항만 Action이 있다
- When 작성자가 `done`, `comment` "Comment"로 바꾼다
- Then 409 `invalid-state` "Next Action이 없는 Action은 상태를 바꿀 수 없습니다."이고 Comment 수·History가 그대로다

### NA-009 종료 Comment에 NUL이 있다
- Given Open Action이 있다
- When 작성자가 `done`, `comment` "가\x00나"로 바꾼다
- Then 422 `invalid-value` "Comment에는 NUL 문자를 쓸 수 없습니다"이고 Action이 그대로다

### NA-010 도메인 검사 순서
- Given 진행사항만 Action과 Open Action이 있다
- When 진행사항만 Action에 `open`+Comment, Open Action에 `open`+NUL Comment를 보낸다
- Then 진행사항만 Action은 409가 아니라 422(Open+Comment)이고, Open Action은 409(같은 상태)가 아니라 422(NUL)다

### NA-011 상태 외 값은 그대로다
- Given 작성자 kim의 Open Action(진행사항·Next Action·Due·유형·수행일·스냅숏 Status/Forecast)과 그 Deal의 수정 시각 D가 있다
- When kim이 `done`으로 바꾼다
- Then 진행사항·Next Action·Due Date·유형·수행일·작성자·스냅숏은 등록 때와 같고 Deal 수정 시각은 D다

### NA-012 admin이 남의 Action을 종료한다
- Given sales kim의 Open Action이 있다
- When admin이 `not_done`으로 바꾼다
- Then 상태가 `not_done`이 되고 새 History 항목의 변경자는 admin이다

### NA-013 작성자가 아닌 sales
- Given sales kim의 Open Action이 있다
- When sales park이 `done`, `comment` "남의 것"으로 바꾼다
- Then 403 `forbidden` "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."이고 상태·Comment 수·History·커밋이 그대로다

### NA-014 user 역할
- Given 작성자 id가 user 역할 사용자 자신인 Action이 있다
- When 그 user가 `done`으로 바꾼다(유스케이스 직접 호출)
- Then 403(작성자 아님 문구)이다. HTTP에서는 업무 쓰기 가드가 먼저 읽기 전용 문구로 거절한다(PL-R6)

### NA-015 없는 Action
- When 어떤 Action에도 없는 id로 user 역할 행위자가 `done`을 요청한다(유스케이스 직접 호출)
- Then 403이 아니라 404 `not-found` "Action을 찾을 수 없습니다."다

### NA-016 본문 형식 오류
- When 본문 `{}`, `{"status": "closed"}`, `{"status": "notDone"}`, `{"status": "DONE"}`, `{"status": null}`, `{"status": "done", "comment": 1}`, `{"status": "done", "memo": "x"}`, `{"status": "done", "closed_at": "2027-01-01T00:00:00Z"}` 각각을 검증한다
- Then 모두 요청 형식 오류(422 `request-validation`)이고(`memo` 키도 422) `{"status": "done"}`은 comment `""`로 받아들인다

### NA-017 상태 변경 이력
- Given Next Action "요구사항 문서 전달", Due 2027-01-15인 Open Action이 있다
- When 작성자가 차례로 `done`+`comment` "전달 완료", `open`, `not_done`(Comment 없음)으로 바꾼다
- Then 첫 변경의 변경 후 값은 "종료(수행)"이고 그 뒤에 Comment 등록 줄 1건이 따라 History는 모두 4건이다. Next Action 줄은 구분 `action`, 대상 `Next Action`, 변경 전/후가 "요구사항 문서 전달 (Due 2027-01-15) · Open"/"종료(수행)", "… · 종료(수행)"/"Open", "… · Open"/"종료(미수행)"이며 변경자·변경 시각은 요청자·요청 시각이다

### NA-018 (폐기 2026-11-17)
- 폐기: 종료 메모를 Memo에 덧붙이는 동작이 없어졌다(Comment 분리). CM-011이 대신한다.

### NA-019 조건 없는 목록
- Given 한 Deal에 Action 25건이 차례로 있다
- When 조건 없이 목록을 조회한다
- Then 25건 전부가 수행일 최신순(같은 날은 나중에 등록한 것이 먼저)으로 오고 응답 키는 `items` 하나다

### NA-020 다른 Deal 제외
- Given Deal A에 "내 활동", Deal B에 "남의 활동"이 있다
- When Deal A의 목록을 조회한다
- Then "내 활동"만 나온다

### NA-021 없는 Deal
- When `20260101-ZZZZ`(없음)과 `not-a-code`(형식 틀림)의 목록을 조회한다
- Then 둘 다 404 `not-found` "Deal을 찾을 수 없습니다."다

### NA-022 전역 검색 경로 없음
- When API 문서의 경로 목록을 본다
- Then `GET /api/v1/deal-actions`는 없고 `/api/v1/deal-actions/{action_id}`(GET·PUT·DELETE)와 `/next-action-status`(PUT)는 있다

### NA-023 조건 AND
- Given kim의 "킥오프"(미팅), park의 "견적 발송"(이메일), park의 "최종 미팅"(미팅)이 있다
- When 유형 미팅 + 담당자 park, 담당자 park + 검색어 "견적", 담당자 admin(Action 없음)으로 각각 조회한다
- Then "최종 미팅", "견적 발송", 0건이다

### NA-024 유형 id 조건
- Given 유형 "이메일"의 "견적 발송"이 있고 유형 이름을 "메일"로 바꿨다
- When 이메일 유형 id로, 그리고 없는 유형 id로 조회한다
- Then 첫 조회는 "견적 발송"이고 응답 유형은 `{id, "메일"}`, 두 번째는 오류 없이 0건이다

### NA-025 퇴사한 작성자
- Given 퇴사 처리된 사용자가 작성한 Action이 있다
- When 그 사용자 id로, 그리고 없는 사용자 id로 조회한다
- Then 첫 조회는 그 Action이고 두 번째는 0건이다

### NA-026 검색어 부분 일치
- Given 진행사항 "Kickoff", Next Action "견적서 준비"인 Action과 Next Action "CONTRACT 초안"인 Action, 진행사항·Next Action에는 없고 Action Comment 본문에만 "회신대기"가 있는 세 번째 Action이 있다
- When 검색어 "kickoff", "contract", "준비", "회신대기"로 조회한다
- Then 각각 첫 Action, 두 번째 Action, 첫 Action, 세 번째 Action이다(CM-R19)

### NA-027 검색어 글자 그대로·공백
- Given Action Comment "예산 100%"인 Action과 다른 Action들이 있다
- When 검색어 "100%", "_", "  견적  ", "   "로 조회한다
- Then 각각 "예산 100%" Action, 0건, "견적"이 들어간 Action, 전체다

### NA-028 검색어 길이와 NUL
- When 검색어 100자, 101자, "a\x00b"로 조회한다
- Then 100자는 정상 조회, 101자는 422 `request-validation`, NUL은 422 `invalid-value` "검색어에는 NUL 문자를 쓸 수 없습니다"다

### NA-029 수행일 하루 범위
- Given 수행일이 2027-05-19, 05-20, 05-20, 05-21인 Action이 있다
- When `acted_from=acted_to=2027-05-20`, `acted_from=2027-05-20`만, `acted_to=2027-05-20`만으로 조회한다
- Then 각각 05-20의 두 건, 05-20 이후 세 건, 05-20까지 세 건이다

### NA-030 Due Date 범위
- Given Due 2027-04-01, 2027-04-10인 Action과 진행사항만 Action이 있다
- When `due_from=2027-04-01&due_to=2027-04-01`, `due_from=2027-04-10`, `due_from=2027-04-02&due_to=2027-04-09`로 조회한다
- Then 각각 04-01 Action, 04-10 Action, 0건이고 진행사항만 Action은 어디에도 없다

### NA-031 거꾸로 된 범위
- When `acted_from=2027-05-21&acted_to=2027-05-20`, `due_from=2027-04-10&due_to=2027-04-01`, 그리고 양쪽 다 같은 날인 범위로 조회한다
- Then 앞의 둘은 422 `invalid-value` "수행일 범위의 시작은 끝보다 늦을 수 없습니다.", "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."이고 같은 날은 정상 조회다

### NA-032 수행일 허용 범위
- When `acted_from` 또는 `acted_to`를 1899-12-31, 3000-01-01, 0001-01-01, 9999-12-31, 1900-01-01, 2999-12-31로 조회한다
- Then 앞의 넷은 422 `invalid-value`(1900-01-01부터 2999-12-31 사이 문구), 뒤의 둘은 정상 조회다

### NA-033 상태 필터
- Given 오래된 순서로 "열림"(Open), "수행"(종료(수행)), "미수행"(종료(미수행)), "진행만"(Next Action 없음)이 있다
- When `next_action_status`를 open, done, not_done, closed, 없음으로 조회한다
- Then 각각 ["열림"], ["수행"], ["미수행"], ["미수행", "수행"], ["진행만", "미수행", "수행", "열림"]이다

### NA-034 상태 필터와 다른 조건
- Given NA-033의 Action들과, 종료했다가 Open으로 되돌린 "되돌림"이 있다
- When `closed`+검색어 "미수행", `open`, `closed`로 조회한다
- Then 각각 ["미수행"], "되돌림"을 포함한 Open 행, "되돌림"이 없는 종료 행이다

### NA-035 허용 밖 상태 필터
- When `next_action_status`를 `notDone`, `DONE`, `all`, `""`, `close`로 조회한다
- Then 모두 422 `request-validation`이다

### NA-036 모르는·틀린 쿼리
- When `offset=0`, `limit=10`, `deal_code=…`, `action_type=meeting`, `actor=박영업`, `unknown=x`, `action_type_id=not-an-id`, `actor_user_id=0`, `due_to=2027-13-40`, `acted_from=soon`으로 조회한다
- Then 모두 422 `request-validation`이다

### NA-037 검색 판정 순서
- When 형식이 틀린 code `not-a-code`에 거꾸로 된 수행일 범위를, 형식은 맞지만 없는 code에 같은 범위를 보낸다
- Then 첫째는 404, 둘째는 422 `invalid-value`(수행일 범위 문구)다

### NA-038 수행일 정렬
- Given 같은 수행일에 "먼저 등록"·"나중 등록"이 있고, 그 다음 날에 "셋째"가 있다
- When `acted_at_desc`, `acted_at_asc`로 조회한다
- Then desc는 "셋째", "나중 등록", "먼저 등록"이고 asc는 "먼저 등록", "나중 등록", "셋째"다

### NA-039 Due Date 정렬
- Given Due 2026-03-01 "늦은 기한", Due 2026-02-01 "빠른 기한 먼저"·"빠른 기한 나중"(나중 수행), 진행사항만 "기한 없음"이 있다
- When `due_date_asc`, `due_date_desc`로 조회한다
- Then asc는 "빠른 기한 나중", "빠른 기한 먼저", "늦은 기한", "기한 없음"이고 desc는 "늦은 기한", "빠른 기한 나중", "빠른 기한 먼저", "기한 없음"이다

### NA-040 담당자 정렬
- Given 표시 이름 "박영업"의 Action, "김영업"의 Action, 표시 이름이 빈 로그인 아이디 "lee"의 Action이 있다
- When `actor_asc`, `actor_desc`로 조회한다
- Then 소문자 코드 포인트 순("lee" < "김영업" < "박영업")과 그 반대 순이다

### NA-041 유형 정렬
- Given 유형 "이메일"·"미팅"·"Demo"의 Action이 있다
- When `action_type_asc`로 조회한다
- Then "demo" < "미팅" < "이메일" 순이다

### NA-042 상태 정렬
- Given NA-033의 네 Action이 있다
- When `next_action_status_asc`, `next_action_status_desc`로 조회한다
- Then asc는 ["열림", "수행", "미수행", "진행만"], desc는 ["미수행", "수행", "열림", "진행만"]이다

### NA-043 정렬 값
- When `sort`를 10개 값 각각과 `actor`, `created_asc`, `DUE_DATE_ASC`, `status_asc`, `""`로 검증한다
- Then 10개 값은 받아들이고 나머지는 422 `request-validation`이다

### NA-044 화면: 상태 칸
- Given sales kim이 작성한 Open Action과 진행사항만 Action이 있는 Deal의 Actions 탭을 kim이 연다
- When 표를 본다
- Then Open 행 상태 칸에 "Open"과 버튼 "종료(수행)"·"종료(미수행)"이 있고 진행사항만 행 상태 칸은 "—"이다

### NA-045 화면: 상태 버튼 권한
- Given kim이 작성한 Open Action이 있다
- When admin, sales park, user가 각각 Actions 탭을 연다
- Then admin에게는 종료 버튼이 보이고 park과 user에게는 "Open" 라벨만 보인다. 그 Action을 종료한 뒤에도 park에게는 전환 버튼이 없다

### NA-046 화면: 종료 행의 버튼
- Given kim의 Action을 종료(수행), 다른 Action을 종료(미수행)으로 바꿨다
- When kim이 표를 본다
- Then 종료(수행) 행은 "종료(미수행)"·"Open으로"만, 종료(미수행) 행은 "종료(수행)"·"Open으로"만 있다

### NA-047 화면: 종료 팝업으로 종료
- Given kim의 Open Action 행이 있다
- When "종료(수행)"을 눌러 열린 "Next Action 종료(수행)" 팝업에 "문서 전달 완료"를 쓰고 "종료"를 누른다
- Then 팝업이 닫히고 행이 "종료(수행)"을 보이며 "Open으로" 버튼이 생기고, 그 행을 눌러 연 상세 팝업 Comment 영역에 "문서 전달 완료"가 있다. Comment를 비운 "종료(미수행)", 종료(수행)→종료(미수행) 전환도 같은 팝업으로 된다

### NA-048 화면: 팝업 취소
- Given 종료 팝업에 "버릴 Comment"를 쓴 상태다
- When "취소"를 누르거나 Esc를 누른다
- Then 팝업이 닫히고 행 상태가 그대로이며 Comment가 새로 생기지 않는다

### NA-049 화면: Open으로
- Given 종료(수행)된 kim의 Action 행이 있다
- When "Open으로"를 누른다
- Then 팝업 없이 행이 "Open"이 된다

### NA-050 화면: 거절된 종료
- Given 종료 팝업에 "잃으면 안 되는 Comment"를 쓴 사이 그 Action이 이미 종료(수행)됐다
- When "종료"를 누른다
- Then 팝업 안에 "이미 종료(수행) 상태입니다."가 보이고 팝업과 Comment가 그대로다. 성공한 종료는 팝업을 닫는다. "Open으로"가 거절되면 탭 오류 배너에 서버 문구가 보인다

### NA-051 화면: 요약 바 상태
- Given 기준 행이 Open인 Deal의 Actions 탭이다
- When 그 행을 종료(수행)한다
- Then 표와 요약 바 모두 "종료(수행)"을 보인다

### NA-052 화면: 검색 바 구성
- When Actions 탭을 연다
- Then "Action 검색" 폼에 유형·담당자·키워드·수행일·기한·Next Action 상태 칸과 "검색"·"초기화" 버튼이 있고 정렬 칸은 없다. 수행일·기한은 "전체"이고 날짜 칸은 없으며, Next Action 상태 선택지는 "전체"·"Open"·"종료(수행)"·"종료(미수행)"·"종료(전체)"다. 키워드 placeholder는 "진행사항·Next Action·Comment"다

### NA-053 화면: 기본 조건 검색
- When 키워드 "ROI", 유형 "이메일", 담당자 "강퇴사(퇴사)"로 각각 검색한다
- Then 각각 "임원 보고용 ROI 자료 전달" 한 행, 이메일 행만, "조건에 맞는 Action이 없습니다."다

### NA-054 화면: 상태 검색
- Given 모든 Action이 Open인 Deal이다
- When Next Action 상태 "Open"으로 검색하고, 다시 "종료(전체)"로 검색한다
- Then 첫 검색은 행이 있고 두 번째는 "조건에 맞는 Action이 없습니다."다

### NA-055 화면: 기간 선택지
- When 수행일·기한 선택 상자를 연다
- Then 수행일은 전체·최근 2주·최근 1개월·최근 2개월·최근 3개월·최근 6개월·직접 지정, 기한은 그 사이 "직접 지정" 앞에 향후 1개월·향후 2개월이 더 있고 둘 다 "전체"가 선택돼 있다

### NA-056 화면: 프리셋 검색
- Given 서버 날짜가 2026-10-22다
- When 수행일 "최근 1개월"과 기한 "향후 2개월"을 골라 검색하고, 서버 날짜가 다음 날로 바뀐 뒤 다시 검색한다
- Then 첫 질의는 수행일 2026-09-22~10-22, 기한 2026-10-22~12-22이고 두 번째는 하루씩 뒤다. 2026-01-31의 "향후 1개월"은 2026-02-28까지이고 프리셋을 고르지 않으면 서버에 다시 묻지 않는다

### NA-057 화면: 직접 지정
- When 수행일 "직접 지정"에 시작만 `20261001`로 쓰고 검색하고, 다시 끝 칸에 `2026-13`을 쓰고 검색한다
- Then 첫 질의는 수행일 시작 2026-10-01만 있고 두 번째는 검색하지 않으며 칸에 날짜 문구가 보인다. 프리셋으로 바꾸면 날짜 칸이 사라지고 입력한 날짜는 질의에 없다

### NA-058 화면: 프리셋을 받지 못함
- Given 기간 프리셋 응답이 실패하거나 아직 오지 않았다
- When 검색 바를 보고, 프리셋 새로 받기가 실패하는 검색을 하고, 프리셋 응답을 기다리는 사이 초기화·새 검색을 한다
- Then 프리셋 선택지는 비활성이고 오류 배너가 보이며, 실패한 검색은 이전 질의를 유지하고, 늦게 온 이전 응답은 질의를 바꾸지 않는다

### NA-059 화면: 초기화
- Given 유형 머리글로 정렬하고 키워드 "ROI"로 검색해 1행이 보인다
- When "초기화"를 누른다
- Then 모든 Action이 다시 보이고 키워드·기간 칸이 비며 유형 정렬은 그대로다

### NA-060 화면: 키워드 길이
- When 키워드 칸에 101자를 쓰고, 100자로 검색한다
- Then 칸에는 100자만 들어가고 100자 검색은 오류 없이 빈 결과 문구다

### NA-061 화면: 빈 결과 문구
- Given 정렬만 유형으로 바꾼 상태에서 그 Deal의 Action이 모두 지워졌다
- When 목록을 다시 읽는다
- Then "등록된 Action이 없습니다."가 보이고 "조건에 맞는 Action이 없습니다."는 없다

### NA-062 화면: 거꾸로 된 직접 지정 범위
- When 수행일 "직접 지정"을 2026-10-21~2026-10-20으로 검색한다
- Then 탭 오류 배너에 "수행일 범위의 시작은 끝보다 늦을 수 없습니다."가 보인다

### NA-063 화면: 정렬 머리글
- When Actions 표를 열고 머리글을 누른다
- Then 버튼 머리글은 수행일·유형·Due Date·상태뿐이고("담당자" 머리글은 없다) 처음은 수행일 내림차순이다. Due Date는 처음 누르면 오름차순, 다시 누르면 내림차순이며 다른 열 뒤 수행일은 다시 내림차순으로 시작한다

### NA-064 화면: 서버 순서 그대로
- When 유형 머리글을 오름차순·내림차순으로 누른다
- Then 행 순서는 서버가 준 순서(같은 유형 안에서는 최신 수행 먼저)와 같다

### NA-065 화면: 정렬과 조건
- Given 키워드 "ROI"로 검색해 1행이다
- When Due Date 머리글을 누르고, 유형 정렬 상태에서 다시 검색한다
- Then 첫 동작 뒤에도 1행이고, 두 번째 뒤에도 유형 오름차순 표시가 남는다

### NA-066 HTTP 게이트웨이 요청
- When 화면 조건 전부(유형 id·담당자 id·키워드·네 날짜·상태 `notDone`·정렬 `type` `asc`)로 목록을 부르고, 빈 조건으로 부르고, 상태를 `notDone`·Comment "접음"으로 바꾼다
- Then 쿼리는 `action_type_id`·`actor_user_id`·`keyword`·`acted_from`·`acted_to`·`due_from`·`due_to`·`next_action_status=not_done`·`sort=action_type_asc`이고, 빈 조건은 쿼리가 없으며(`offset`·`limit` 없음), 상태 변경은 `PUT …/next-action-status` 본문 `{"status":"not_done","comment":"접음"}`이다

### NA-067 HTTP 게이트웨이 오류
- Given 서버가 422 "수행일 범위의 시작은 끝보다 늦을 수 없습니다.", 404 "Deal을 찾을 수 없습니다."를 준다
- When 목록을 부른다
- Then 그 상태와 문구 그대로의 오류가 된다

### NA-068 Fake 게이트웨이 규칙
- When Fake로 종료·되돌림·전환·같은 상태·Next Action 없음·Open+Comment·없는 Action·user·admin을, 그리고 상태 필터·Due/상태 정렬·검색어 길이·검색 오류 순서를, 또 종료 Comment NUL·검색어 NUL·1900~2999 밖 수행일을 실행한다
- Then 결과(상태·종료 시각·생긴 Comment·History 건수, 409·422·404·403, 결과 순서, 422가 404보다 먼저)가 NA-R2~R9, R14~R18, R20과 같다. 종료 Comment NUL은 422 "Comment에는 NUL 문자를 쓸 수 없습니다", 검색어 NUL은 422 "검색어에는 NUL 문자를 쓸 수 없습니다", 범위 밖 수행일은 422 "acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"(`acted_to`도 같음)이고 Action·History가 그대로다(Fake를 서버 동작에 맞춤, 2026-11-10 결정)

### NA-069 주 키가 같은 정렬의 동률은 수행일 내림차순 다음 id 내림차순이다
- Given 유형이 "미팅"이고 수행일이 같은 Action 두 건("먼저 등록"·"나중 등록")과, 유형이 "미팅"이고 수행일이 하루 늦은 "다음 날" Action이 있다
- When `action_type_asc`로 조회한다(Fake에도 같은 입력을 준다)
- Then 순서는 "다음 날" → "나중 등록" → "먼저 등록"이다

### NA-070 종료하면 응답 next_action_closed_on은 요청의 업무 날짜이고 Open으로 되돌리면 null이다
- Given 업무 시간대는 Asia/Seoul, 서버 시계는 `2026-11-13T23:30:00+09:00`이고, kim의 Open Action이 있다
- When kim이 상태를 `done`으로 바꾼 뒤 다시 `open`으로 바꾼다
- Then 첫 응답의 `next_action_closed_on`은 "2026-11-13"이고 `next_action_closed_at` 키는 없다. 두 번째 응답에서는 null이다

### NA-071 마이그레이션은 종료 시각을 업무 날짜로 채우고 비어 있던 행은 null로 두며 CHECK를 새 컬럼으로 만든다
- Given 기준선 리비전 DB(Asia/Seoul)에 Action 세 건이 있다: `next_action_closed_at`이 `2026-11-12T15:30:00Z`인 종료(수행) Action, `next_action_closed_at`이 null인 Open Action, Next Action이 없는 Action
- When `upgrade head`를 실행한 뒤 다시 `downgrade -1`을 실행한다
- Then upgrade 뒤에는 행이 3건 그대로이고, `next_action_closed_on`은 2026-11-13, null, null이며, `ck_deal_actions_next_action_closed_on`이 있고 `next_action_closed_at` 컬럼은 없다. downgrade 뒤에는 첫 행의 `next_action_closed_at`이 `2026-11-13T00:00:00+09:00`이고 나머지 두 행은 null이다

### NA-072 게이트웨이·Fake: 종료일을 closedOn 날짜로 매핑하고 Fake는 Fake 시계의 오늘로 정한다
- Given Fake 시계의 오늘이 2026-11-13이다
- When HTTP 게이트웨이가 `next_action_closed_on: "2026-11-12"` 응답을 받고, Fake로 Open Action을 종료(수행)한다
- Then 화면 모델의 종료일은 "2026-11-12"이고 Fake 결과는 "2026-11-13"이며, 어느 쪽에도 시각 필드는 없다

## 5. 변경 이력

| 날짜 | 변경 | 영향 테스트 코드 |
| --- | --- | --- |
| 2026-11-10 | 초안: 구현된 동작 문서화(NA-R1~R31, NA-UC1~UC5, NA-001~068) | NA-001~068 |
| 2026-11-10 | 사용자 결정 반영(추천대로): E1 Fake를 서버 동작에 맞춤(NA-R30: 수행일 범위·검색어 NUL·종료 메모 NUL), E2 Due Date 범위 1900~2999 미검사 유지(NA-R16), E5 경계(조건·정렬·필터는 NA, 기본 순서·열 구성은 AC-R18·R21, 이전 Next Action 종료 이력 형식은 NA-R8 소유)와 AC 이름 참조를 AC 번호로 | 변경: NA-068(NUL·범위 기대 결과 추가) |
| 2026-11-11 | UI 문서 작성에 따라 공통 컴포넌트 참조를 UI 규칙 번호로 교체(1장, NA-R26). 기간 선택 부품 `PeriodField`·`periodChoice`는 NA-R26 소유로 UI·PA가 가리킴. 동작·케이스 변경 없음, 상태 줄 그대로 | 없음 |
| 2026-11-13 | AC 수행일 지정(확정)에 맞춰 NA-R4·NA-R15에 설명 추가. 동작·케이스 변경 없음, 상태 줄 그대로 | 없음(관련 신규 AC-099·AC-101) |
| 2026-11-13 | 확정(2026-11-13 사용자 확인): 업무 날짜를 date로 저장. 종료일은 `next_action_closed_on`(용어, 2.2, NA-R1·R4, 2.4, 2.6), NA-R32 신설(데이터 변환), NA-R15 날짜 비교, NA-R18 같은 날 동률(desc는 id 내림차순, 나머지 정렬은 수행일 내림차순 → id 내림차순), 머리글 "수행일". 정렬 값 이름 `acted_at_*`은 유지. 응답 필드 변경(호환 깨짐, 사용자 승인) | 신규 NA-069~NA-072. 변경 NA-001, NA-004, NA-019, NA-029, NA-038, 상태 변경 '그대로' 케이스, 머리글 화면 케이스 |
| 2026-11-16 | 확정(2026-11-16 사용자 확인): 상세 팝업에서도 상태 변경 가능(NA-R21 추가 문구, AC-R54·AC-144·AC-145 참조, 서버 동작 변경 없음). 이전 초안 내용: AC Actions 탭 개편(AC-R21 담당자·Memo 열 제거, AC-R49 상세 팝업)에 맞춤. NA-R24(Memo는 상세 팝업에서 보임), NA-R28(정렬 머리글 5→4, 담당자 제외 — 서버 `actor_*` 정렬 값은 유지), NA-UC5. 서버 동작 변경 없음 | 변경 NA-047, NA-059, NA-061, NA-063, NA-064 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): CM 확정: Memo → Comment 엔티티 분리. 종료 메모를 종료 Comment로(NA-R2 `comment`·예전 `memo` 422, NA-R3 전체 교체, NA-R4·R5·R7·R8·R9, NA-R14 키워드가 Action Comment 본문도 검색, 2.1·2.2·2.6·2.8). 프런트 규칙 NA-R22·R23·R25·R30은 프런트 후속에서 개정(CM 2.7) | 변경 NA-005~NA-010, NA-013, NA-016, NA-017, NA-026. 폐기 NA-001~NA-003, NA-018. 프런트 후속 NA-047, NA-050, NA-066, NA-068 |
| 2026-11-17 | 확정(2026-11-17 사용자 확인): 종료 대화상자·되돌리기·검색 placeholder·게이트웨이를 Comment로(NA-R22~R25, R30). "프런트 후속" 해소 | 변경 NA-047, NA-050, NA-052, NA-066, NA-068 |
| 2026-11-18 | RK-R4 변경(기한초과는 Open Next Action만)에 맞춰 NA-R5 하위 항목 문구 갱신. NA 동작·케이스 변경 없음, 상태 줄 그대로 | 없음(관련 RK-013, RK-071) |
