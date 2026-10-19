"""Action 이력 문구(AC-03·11·12, R-12): 요약·등록·수정·삭제 초안과 1,000자 자르기."""

from datetime import date

from app.domain.deal.history import HistoryCategory
from app.domain.deal_action.history import (
    ACTION_TARGET,
    action_created_draft,
    action_deleted_draft,
    action_summary,
    action_updated_draft,
)
from tests.factories import make_action_content
from tests.factories_action_type import make_type_ref

SUMMARY = "미팅 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"


def test_summary_without_memo_ends_at_the_due_date() -> None:
    assert action_summary(make_action_content(memo="")) == SUMMARY


def test_summary_with_memo_appends_the_memo_at_the_end() -> None:
    summary = action_summary(make_action_content(memo="요구사항 정리"))

    assert summary == f"{SUMMARY} / Memo: 요구사항 정리"


def test_summary_uses_the_type_name() -> None:
    summary = action_summary(make_action_content(action_type="협상", memo=""))

    assert summary.startswith("협상 · 킥오프 미팅")


def test_summary_uses_the_name_of_a_custom_type_as_it_is() -> None:
    summary = action_summary(make_action_content(action_type=make_type_ref("Webinar"), memo=""))

    assert summary.startswith("Webinar · 킥오프 미팅")


def test_summary_writes_the_due_date_as_iso() -> None:
    summary = action_summary(make_action_content(due_date=date(2027, 3, 4), memo=""))

    assert summary.endswith("(Due 2027-03-04)")


def test_created_draft_has_an_empty_before_and_a_registration_prefix() -> None:
    draft = action_created_draft(make_action_content(memo=""))

    assert (draft.category, draft.target, draft.before, draft.after) == (
        HistoryCategory.ACTION,
        ACTION_TARGET,
        "",
        f"등록: {SUMMARY}",
    )
    assert ACTION_TARGET == "Action"


def test_updated_draft_shows_the_old_summary_before_and_the_new_one_after() -> None:
    before = make_action_content(memo="")
    after = make_action_content(action="제안 발표", memo="변경")

    draft = action_updated_draft(before, after)

    assert draft.category is HistoryCategory.ACTION
    assert draft.target == "Action"
    assert draft.before == SUMMARY
    assert draft.after == (
        "수정: 미팅 · 제안 발표 / Next Action: 요구사항 문서 전달 (Due 2026-01-15) / Memo: 변경"
    )


def test_deleted_draft_shows_the_summary_before_and_the_word_deleted_after() -> None:
    draft = action_deleted_draft(make_action_content(memo=""))

    assert (draft.category, draft.target, draft.before, draft.after) == (
        HistoryCategory.ACTION,
        "Action",
        SUMMARY,
        "삭제",
    )


def test_action_draft_clips_long_summary_to_history_limit() -> None:
    draft = action_created_draft(make_action_content(action="가" * 2_000))

    assert len(draft.after) == 1_000
    assert draft.after.endswith("…")
    assert (
        draft.after[:-1]
        == ("등록: " + action_summary(make_action_content(action="가" * 2_000)))[:999]
    )


def test_updated_and_deleted_drafts_clip_the_old_summary_too() -> None:
    long_content = make_action_content(next_action="나" * 3_000)

    updated = action_updated_draft(long_content, make_action_content())
    deleted = action_deleted_draft(long_content)

    assert len(updated.before) == len(deleted.before) == 1_000
    assert updated.before.endswith("…")
    assert deleted.before.endswith("…")


def test_a_summary_exactly_at_the_limit_is_not_clipped() -> None:
    probe = make_action_content(action="가", memo="")
    overhead = len(action_created_draft(probe).after) - 1  # 진행사항 밖의 고정 문구 길이
    fitting = make_action_content(action="가" * (1_000 - overhead), memo="")

    draft = action_created_draft(fitting)

    assert len(draft.after) == 1_000
    assert not draft.after.endswith("…")


def test_updated_draft_with_only_a_new_type_shows_both_type_names() -> None:
    before = make_action_content(action_type="미팅", memo="")
    after = make_action_content(action_type="데모", memo="")

    draft = action_updated_draft(before, after)

    assert draft.before == SUMMARY
    assert draft.after == (
        "수정: 데모 · 킥오프 미팅 / Next Action: 요구사항 문서 전달 (Due 2026-01-15)"
    )


def test_deleted_draft_uses_the_type_name_in_the_summary() -> None:
    draft = action_deleted_draft(make_action_content(action_type="계약", memo=""))

    assert draft.before.startswith("계약 · 킥오프 미팅")
    assert draft.after == "삭제"
