"""Action 이력 문구: 요약·등록·수정·삭제 초안과 1,000자 자르기."""

from datetime import date

from app.domain.deal.history import HistoryCategory
from app.domain.deal_action.history import (
    ACTION_TARGET,
    action_created_draft,
    action_deleted_draft,
    action_summary,
    action_updated_draft,
    next_action_status_draft,
)
from app.domain.deal_action.next_action_status import NextActionStatus, NextActionStatusChange
from tests.factories import make_action_content
from tests.factories_action_type import make_type_ref

SUMMARY = "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"


def test_summary_without_memo_ends_at_the_due_date() -> None:
    """Memo가 없으면 요약은 Due Date에서 끝난다.

    테스트 코드: AC-016
    """
    # when: Memo 없는 내용의 요약을 만든다
    summary = action_summary(make_action_content(memo=""))
    # then: Due Date 괄호에서 끝난다
    assert summary == SUMMARY


def test_summary_with_memo_appends_the_memo_at_the_end() -> None:
    """Memo가 있으면 요약 맨 끝에 Memo가 붙는다.

    테스트 코드: AC-016
    """
    # when: Memo가 있는 내용의 요약을 만든다
    summary = action_summary(make_action_content(memo="요구사항 정리"))

    # then: 요약 끝에 " / Memo: …"가 붙는다
    assert summary == f"{SUMMARY} / Memo: 요구사항 정리"


def test_summary_uses_the_type_name() -> None:
    """요약의 유형 자리에는 유형 이름이 들어간다.

    테스트 코드: AC-022
    """
    # when: 유형 "협상"인 내용의 요약을 만든다
    summary = action_summary(make_action_content(action_type="협상", memo=""))

    # then: 요약이 "협상 · …"로 시작한다
    assert summary.startswith("협상 · 킥오프 미팅")


def test_summary_uses_the_name_of_a_custom_type_as_it_is() -> None:
    """새로 만든 유형도 그 이름 그대로 요약에 쓴다.

    테스트 코드: AC-022
    """
    # when: 유형 "Webinar"인 내용의 요약을 만든다
    summary = action_summary(make_action_content(action_type=make_type_ref("Webinar"), memo=""))

    # then: 요약이 "Webinar · …"로 시작한다
    assert summary.startswith("Webinar · 킥오프 미팅")


def test_summary_writes_the_due_date_as_iso() -> None:
    """요약의 Due Date는 ISO 날짜로 쓴다.

    테스트 코드: AC-016
    """
    # when: Due 2027-03-04인 내용의 요약을 만든다
    summary = action_summary(make_action_content(due_date=date(2027, 3, 4), memo=""))

    # then: 요약이 "(Due 2027-03-04)"로 끝난다
    assert summary.endswith("(Due 2027-03-04)")


def test_created_draft_has_an_empty_before_and_a_registration_prefix() -> None:
    """등록 이력은 변경 전이 비고 변경 후는 "등록: 요약"이다.

    테스트 코드: AC-016
    """
    # when: Memo 없는 내용의 등록 이력 초안을 만든다
    draft = action_created_draft(make_action_content(memo=""))

    # then: 구분 Action·대상 Action·변경 전 ""·변경 후 "등록: <요약>"이다
    assert (draft.category, draft.target, draft.before, draft.after) == (
        HistoryCategory.ACTION,
        ACTION_TARGET,
        "",
        f"등록: {SUMMARY}",
    )
    assert ACTION_TARGET == "Action"


def test_updated_draft_shows_the_old_summary_before_and_the_new_one_after() -> None:
    """수정 이력은 변경 전에 옛 요약, 변경 후에 "수정: 새 요약"을 쓴다.

    테스트 코드: AC-046
    """
    # given: 수정 전 내용과 수정 후 내용
    before = make_action_content(memo="")
    after = make_action_content(action="제안 발표", memo="변경")

    # when: 수정 이력 초안을 만든다
    draft = action_updated_draft(before, after)

    # then: 변경 전은 옛 요약이고 변경 후는 "수정: <새 요약>"이다
    assert draft.category is HistoryCategory.ACTION
    assert draft.target == "Action"
    assert draft.before == SUMMARY
    assert draft.after == (
        "수정: 미팅 · 제안 발표 / Next Action: 요구사항 문서 전달 (Due 2026-01-15) / Memo: 변경"
    )


def test_deleted_draft_shows_the_summary_before_and_the_word_deleted_after() -> None:
    """삭제 이력은 변경 전에 요약, 변경 후에 "삭제"를 쓴다.

    테스트 코드: AC-059
    """
    # when: 삭제 이력 초안을 만든다
    draft = action_deleted_draft(make_action_content(memo=""))

    # then: 변경 전은 요약이고 변경 후는 "삭제"다
    assert (draft.category, draft.target, draft.before, draft.after) == (
        HistoryCategory.ACTION,
        "Action",
        SUMMARY,
        "삭제",
    )


def test_action_draft_clips_long_summary_to_history_limit() -> None:
    """긴 요약은 이력 길이 제한(999자 + "…")으로 잘린다.

    테스트 코드: AC-017
    """
    # when: 진행사항 2,000자로 등록 이력 초안을 만든다
    draft = action_created_draft(make_action_content(action="가" * 2_000))

    # then: 변경 후가 1,000자에서 "…"로 끝난다
    assert len(draft.after) == 1_000
    assert draft.after.endswith("…")
    assert (
        draft.after[:-1]
        == ("등록: " + action_summary(make_action_content(action="가" * 2_000)))[:999]
    )


def test_updated_and_deleted_drafts_clip_the_old_summary_too() -> None:
    """수정·삭제 이력의 변경 전도 같은 제한으로 잘린다.

    테스트 코드: AC-049, AC-059
    """
    # given: 요약이 1,000자를 넘는 내용
    long_content = make_action_content(next_action="나" * 3_000)

    # when: 수정 이력 초안과 삭제 이력 초안을 만든다
    updated = action_updated_draft(long_content, make_action_content())
    deleted = action_deleted_draft(long_content)

    # then: 두 변경 전이 1,000자에서 "…"로 끝난다
    assert len(updated.before) == len(deleted.before) == 1_000
    assert updated.before.endswith("…")
    assert deleted.before.endswith("…")


def test_a_summary_exactly_at_the_limit_is_not_clipped() -> None:
    """요약이 정확히 제한 길이면 자르지 않는다.

    테스트 코드: AC-017
    """
    # given: 고정 문구 길이를 잰 뒤 정확히 1,000자가 되는 진행사항
    probe = make_action_content(action="가", memo="")
    overhead = len(action_created_draft(probe).after) - 1  # 진행사항 밖의 고정 문구 길이
    fitting = make_action_content(action="가" * (1_000 - overhead), memo="")

    # when: 등록 이력 초안을 만든다
    draft = action_created_draft(fitting)

    # then: 1,000자이고 "…"로 끝나지 않는다
    assert len(draft.after) == 1_000
    assert not draft.after.endswith("…")


def test_updated_draft_with_only_a_new_type_shows_both_type_names() -> None:
    """유형만 바꾼 수정 이력은 두 유형 이름을 모두 보인다.

    테스트 코드: AC-053
    """
    # given: 유형만 다른 수정 전·후 내용
    before = make_action_content(action_type="미팅", memo="")
    after = make_action_content(action_type="데모", memo="")

    # when: 수정 이력 초안을 만든다
    draft = action_updated_draft(before, after)

    # then: 변경 전은 옛 유형, 변경 후는 "수정: 데모 · …"다
    assert draft.before == SUMMARY
    assert draft.after == (
        "수정: 데모 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    )


def test_deleted_draft_uses_the_type_name_in_the_summary() -> None:
    """삭제 이력의 요약에도 유형 이름이 쓰인다.

    테스트 코드: AC-059
    """
    # when: 유형 "계약"인 내용의 삭제 이력 초안을 만든다
    draft = action_deleted_draft(make_action_content(action_type="계약", memo=""))

    # then: 변경 전은 "계약 · …"로 시작하고 변경 후는 "삭제"다
    assert draft.before.startswith("계약 · 킥오프 미팅")
    assert draft.after == "삭제"


def test_summary_omits_missing_progress_and_next_action() -> None:
    """없는 진행사항·Next Action은 요약에서 빠진다.

    테스트 코드: AC-006, AC-007
    """
    # when: Next Action만, 진행사항만, 진행사항+Memo인 요약을 만든다
    next_only = action_summary(make_action_content(action="", memo=""))
    progress_only = action_summary(make_action_content(next_action="", memo=""))
    with_memo = action_summary(make_action_content(next_action="", memo="메모"))

    # then: 있는 부분만 이어 붙는다
    assert next_only == "미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    assert progress_only == "미팅 · 킥오프 미팅"
    assert with_memo == "미팅 · 킥오프 미팅 / Memo: 메모"


def test_summary_of_a_next_only_action_with_memo_keeps_the_memo_last() -> None:
    """Next Action만 있는 Action의 요약은 Memo가 맨 끝이다.

    테스트 코드: AC-007
    """
    # when: Next Action과 Memo만 있는 내용의 요약을 만든다
    summary = action_summary(make_action_content(action="", memo="메모"))

    # then: Next Action 뒤에 Memo가 붙는다
    assert summary == "미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15) / Memo: 메모"


def test_status_draft_formats_before_and_after() -> None:
    """상태 변경 이력은 변경 전 "<Next Action> (Due …) · <라벨>", 변경 후 "<라벨> / Memo: …"이다.

    테스트 코드: NA-017
    """
    # given: Next Action "견적 전달", Due 2/5이고 Open -> 종료(수행)에 메모 "전달 완료"인 변경
    content = make_action_content(next_action="견적 전달", due_date=date(2026, 2, 5))
    change = NextActionStatusChange(
        before=NextActionStatus.OPEN, after=NextActionStatus.DONE, note="전달 완료"
    )
    # when: 이력 초안을 만든다
    draft = next_action_status_draft(content, change)
    # then: 구분 action, 대상 Next Action, 정해진 변경 전/후 문구다
    assert (draft.category, draft.target, draft.before, draft.after) == (
        HistoryCategory.ACTION,
        "Next Action",
        "견적 전달 (Due 2026-02-05) · Open",
        "종료(수행) / Memo: 전달 완료",
    )


def test_status_draft_without_note_has_label_only() -> None:
    """메모가 없으면 변경 후 값은 새 라벨뿐이다.

    테스트 코드: NA-017
    """
    # given: 종료(미수행) -> Open이고 메모가 없는 변경
    content = make_action_content(next_action="견적 전달", due_date=date(2026, 2, 5))
    change = NextActionStatusChange(
        before=NextActionStatus.NOT_DONE, after=NextActionStatus.OPEN, note=""
    )
    # when: 이력 초안을 만든다
    draft = next_action_status_draft(content, change)
    # then: 변경 전은 "… · 종료(미수행)", 변경 후는 "Open"이다
    assert draft.before == "견적 전달 (Due 2026-02-05) · 종료(미수행)"
    assert draft.after == "Open"


def test_status_draft_clips_a_long_note_to_the_history_limit() -> None:
    """긴 종료 메모는 이력 값 길이 제한(999자 + "…")으로 잘린다.

    테스트 코드: NA-018
    """
    # given: 2,000자 메모로 종료(미수행)하는 변경
    content = make_action_content()
    change = NextActionStatusChange(
        before=NextActionStatus.OPEN, after=NextActionStatus.NOT_DONE, note="가" * 2_000
    )
    # when: 이력 초안을 만든다
    draft = next_action_status_draft(content, change)
    # then: 변경 후 값이 1,000자(999자 + "…")로 잘린다
    assert len(draft.after) == 1_000
    assert draft.after.startswith("종료(미수행) / Memo: ")
    assert draft.after.endswith("…")


def test_updated_draft_appends_the_acted_on_to_both_ends_when_it_changed() -> None:
    """수행일이 바뀐 수정 이력은 변경 전·후 양쪽 끝에 " / 수행일: <날짜>"가 붙는다.

    테스트 코드: AC-118, AC-119
    """
    # given: 내용이 같은 수정 전후와 이전·새 수행일
    content = make_action_content(memo="")

    # when: 수행일 (이전, 새)을 넣어 수정 이력 초안을 만든다
    draft = action_updated_draft(
        content, content, acted_on=(date(2026, 11, 13), date(2026, 11, 10))
    )

    # then: 변경 전은 "<요약> / 수행일: 이전", 변경 후는 "수정: <요약> / 수행일: 새"다
    assert draft.before == f"{SUMMARY} / 수행일: 2026-11-13"
    assert draft.after == f"수정: {SUMMARY} / 수행일: 2026-11-10"


def test_updated_draft_without_an_acted_on_change_keeps_the_old_wording() -> None:
    """수행일 인자를 안 주면 수정 이력 문구는 예전과 같다.

    테스트 코드: AC-120
    """
    # when: 수행일 없이 수정 이력 초안을 만든다
    draft = action_updated_draft(make_action_content(memo=""), make_action_content(memo=""))

    # then: 끝에 수행일 부분이 없다
    assert draft.before == SUMMARY
    assert draft.after == f"수정: {SUMMARY}"
    assert "수행일" not in draft.before + draft.after


def test_updated_draft_clips_the_acted_on_part_with_the_summary() -> None:
    """아주 긴 요약에서는 덧붙인 수행일 부분도 이력 길이 제한으로 잘려 보이지 않을 수 있다.

    테스트 코드: AC-118
    """
    # given: 요약이 1,000자를 넘는 내용
    long_content = make_action_content(action="가" * 2_000)

    # when: 수행일이 바뀐 수정 이력 초안을 만든다
    draft = action_updated_draft(
        long_content, long_content, acted_on=(date(2026, 11, 13), date(2026, 11, 10))
    )

    # then: 변경 전·후가 1,000자에서 "…"로 끝난다
    assert len(draft.before) == len(draft.after) == 1_000
    assert draft.before.endswith("…")
    assert draft.after.endswith("…")
