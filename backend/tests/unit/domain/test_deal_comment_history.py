"""Comment 작성·삭제가 Deal 이력에 남기는 문구(CM-R13)."""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory
from app.domain.deal_comment.history import (
    comment_created_draft,
    comment_deleted_draft,
    comment_target,
)
from tests.factories import make_deal_action

if TYPE_CHECKING:
    from app.domain.deal_action.entities import DealAction

ACTION_TARGET = "Action Comment (2026-11-10 미팅)"


def _action() -> DealAction:
    return make_deal_action(acted_on=date(2026, 11, 10), action_type="미팅")


def test_the_target_of_a_deal_comment_is_just_comment() -> None:
    """연결 Action이 없는 Comment의 대상은 "Comment"다.

    테스트 코드: CM-010
    """
    # when·then: Action이 없으면 "Comment"다
    assert comment_target(None) == "Comment"


def test_the_target_of_an_action_comment_names_the_action_date_and_type() -> None:
    """Action Comment의 대상에는 그 Action의 수행일과 유형 이름이 붙는다.

    테스트 코드: CM-010
    """
    # when·then: 수행일 YYYY-MM-DD와 유형 이름이 붙는다
    assert comment_target(_action()) == ACTION_TARGET


def test_created_draft_has_the_comment_category_an_empty_before_and_a_prefix() -> None:
    """작성 이력은 구분 comment, 변경 전 빈 값, 변경 후 "등록: <본문>"이다.

    테스트 코드: CM-010
    """
    # when: Deal Comment와 Action Comment의 작성 이력 초안을 만든다
    deal = comment_created_draft("예산 확인", None)
    on_action = comment_created_draft("자료 전달", _action())

    # then: 구분·대상·전·후가 문서대로다
    assert deal.category is HistoryCategory.COMMENT
    assert (deal.target, deal.before, deal.after) == ("Comment", "", "등록: 예산 확인")
    assert (on_action.target, on_action.before, on_action.after) == (
        ACTION_TARGET,
        "",
        "등록: 자료 전달",
    )


def test_deleted_draft_shows_the_body_before_and_the_word_deleted_after() -> None:
    """삭제 이력은 변경 전에 본문, 변경 후에 "삭제"다.

    테스트 코드: CM-024
    """
    # when: Deal Comment의 삭제 이력 초안을 만든다
    draft = comment_deleted_draft("예산 확인", None)

    # then: 문서대로다
    assert draft.category is HistoryCategory.COMMENT
    assert (draft.target, draft.before, draft.after) == ("Comment", "예산 확인", "삭제")


def test_a_long_body_is_clipped_in_the_history_only() -> None:
    """긴 본문은 이력에서 999자 + "…"로 잘린다("등록: " 접두어 포함 1,000자 한도).

    테스트 코드: CM-011
    """
    # given: 1,500자 본문
    body = "가" * 1_500

    # when: 작성 이력 초안을 만든다
    draft = comment_created_draft(body, None)

    # then: 변경 후는 "등록: " + 본문 앞부분으로 999자에 "…"가 붙은 1,000자다
    assert len(draft.after) == 1_000
    assert draft.after == ("등록: " + body)[:999] + "…"
    assert draft.after.startswith("등록: 가가")
