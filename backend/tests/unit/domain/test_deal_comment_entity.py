"""DealComment 엔티티: 작성·읽음 처리·삭제 권한 확인(수정 기능은 없다)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.deal_action.value_objects import DealActionId
from app.domain.deal_comment.errors import (
    DealCommentDeleteForbiddenError,
    DealCommentNotFoundError,
    DealCommentReadForbiddenError,
)
from tests.factories import NOW, later, make_deal_code
from tests.factories_comment import make_comment
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

KIM = uid("cm-kim")
PARK = uid("cm-park")
READ_FORBIDDEN = "Deal Owner만 Comment를 읽음 처리할 수 있습니다."
DELETE_FORBIDDEN = "본인 Comment 또는 admin만 삭제할 수 있습니다."


def test_a_written_comment_has_the_given_links_and_equal_timestamps() -> None:
    """작성한 Comment는 준 값을 그대로 가지고 작성·수정 시각이 같다.

    테스트 코드: CM-001, CM-008
    """
    # given: Deal·Action id
    code = make_deal_code()
    action_id = DealActionId(new_id())

    # when: Action에 연결한 Comment를 쓴다
    comment = make_comment(deal_code=code, action_id=action_id, author=KIM, body="자료 전달")

    # then: 소속 Deal·연결 Action·작성자·본문이 그대로이고 시각이 같다
    assert (comment.deal_code, comment.action_id, comment.author_user_id) == (code, action_id, KIM)
    assert comment.body == "자료 전달"
    assert comment.created_at == comment.updated_at == NOW


def test_a_comment_without_an_action_is_a_deal_comment() -> None:
    """action_id가 없으면 Deal Comment다.

    테스트 코드: CM-001
    """
    # when: Action 없이 쓴다
    comment = make_comment()

    # then: 연결 Action이 없다
    assert comment.action_id is None


def test_the_owners_own_comment_is_born_read_and_anyone_elses_is_unread() -> None:
    """작성자가 Deal Owner이면 작성 시각이 읽음 시각이고, 그 밖의 사람이 쓰면 읽지 않음이다.

    테스트 코드: CM-048
    """
    # given: Deal Owner가 KIM이다
    # when: KIM(Owner)이 쓰고, PARK(Owner 아님)이 쓴다
    by_owner = make_comment(author=KIM, deal_owner=KIM)
    by_other = make_comment(author=PARK, deal_owner=KIM)

    # then: Owner의 것은 작성 시각이 읽음 시각이고 다른 사람의 것은 읽지 않음이다
    assert by_owner.read_at == NOW
    assert by_other.read_at is None


def test_mark_read_fills_read_at_once_and_a_second_call_changes_nothing() -> None:
    """읽지 않은 Comment를 읽음 처리하면 True이고 read_at만 채워지며, 다시 처리하면 False·그대로다.

    테스트 코드: CM-049, CM-051, CM-054
    """
    # given: 읽지 않은 Comment
    comment = make_comment(author=PARK, deal_owner=KIM, body="자료 전달")
    before = (comment.body, comment.updated_at, comment.created_at, comment.author_user_id)

    # when: 처음 읽음 처리한다
    first = comment.mark_read(later(60))

    # then: True이고 read_at만 바뀐다(본문·수정 시각은 그대로)
    assert first is True
    assert comment.read_at == later(60)
    assert (comment.body, comment.updated_at, comment.created_at, comment.author_user_id) == before

    # when: 나중에 다시 처리한다
    second = comment.mark_read(later(120))

    # then: False이고 read_at은 처음 값 그대로다
    assert second is False
    assert comment.read_at == later(60)


def test_mark_read_on_a_comment_born_read_keeps_the_creation_time() -> None:
    """Owner가 쓴(이미 읽음인) Comment의 읽음 처리는 False이고 read_at이 작성 시각 그대로다.

    테스트 코드: CM-051
    """
    # given: Owner가 쓴 Comment
    comment = make_comment(author=KIM, deal_owner=KIM)

    # when: 읽음 처리한다
    changed = comment.mark_read(later(60))

    # then: False이고 read_at은 작성 시각이다
    assert changed is False
    assert comment.read_at == NOW


def test_a_comment_has_no_edit_operations() -> None:
    """수정 기능이 폐지되어 revise·ensure_editable_by가 없다(본문은 작성 뒤 바뀌지 않는다).

    테스트 코드: CM-057
    """
    # given: Comment
    comment = make_comment()

    # when·then: 수정 관련 메서드가 없다
    assert not hasattr(comment, "revise")
    assert not hasattr(comment, "ensure_editable_by")


@pytest.mark.parametrize(
    ("user", "role"),
    [(KIM, Role.SALES), (PARK, Role.ADMIN)],
    ids=["author", "admin"],
)
def test_the_author_and_admin_may_delete(user: UserId, role: Role) -> None:
    """작성자 sales와 admin은 삭제 확인을 통과한다.

    테스트 코드: CM-025
    """
    # given: KIM이 쓴 Comment
    comment = make_comment(author=KIM)

    # when·then: 예외 없이 통과한다
    comment.ensure_deletable_by(user, role)


def test_another_sales_and_a_user_are_rejected_with_the_fixed_message() -> None:
    """다른 sales와 user는 정해진 문구의 오류로 삭제를 거절당한다.

    테스트 코드: CM-025
    """
    # given: KIM이 쓴 Comment
    comment = make_comment(author=KIM)

    # when·then: 정해진 문구로 거절된다
    for user, role in ((PARK, Role.SALES), (KIM, Role.USER)):
        with raises_with(DealCommentDeleteForbiddenError, DELETE_FORBIDDEN):
            comment.ensure_deletable_by(user, role)


def test_read_forbidden_error_has_the_fixed_message() -> None:
    """Owner가 아닌 사람의 읽음 처리 오류 문구는 정해져 있다.

    테스트 코드: CM-050
    """
    # when·then: 문구가 정해져 있다
    with raises_with(DealCommentReadForbiddenError, READ_FORBIDDEN):
        raise DealCommentReadForbiddenError


def test_not_found_error_has_the_fixed_message() -> None:
    """없는 Comment 오류의 문구는 정해져 있다.

    테스트 코드: CM-016
    """
    # when·then: 어떤 id든 같은 문구다
    with raises_with(DealCommentNotFoundError, "Comment를 찾을 수 없습니다."):
        raise DealCommentNotFoundError(999_999)
