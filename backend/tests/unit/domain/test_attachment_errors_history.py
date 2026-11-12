"""첨부 오류의 종류·문구와 Deal 이력 문구."""

import unicodedata

import pytest

from app.domain.attachment.errors import (
    AttachmentContentMissingError,
    AttachmentDeleteForbiddenError,
    AttachmentNameTakenError,
    AttachmentNotFoundError,
    AttachmentReplaceForbiddenError,
)
from app.domain.attachment.history import (
    ATTACHMENT_TARGET,
    deleted_draft,
    replaced_draft,
    uploaded_draft,
)
from app.domain.attachment.values import FileName
from app.domain.auth.errors import AccessDeniedError
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.deal.history import HistoryCategory
from tests.support.expect import raises_with
from tests.support.ids import new_id


def test_not_found_and_content_missing_are_not_found_errors_with_their_sentences() -> None:
    """첨부 없음·내용 없음 오류는 NotFound 계열이고 각자의 문구를 가진다."""
    # when·then: 첨부 없음 오류는 "첨부 파일을 찾을 수 없습니다."다
    with raises_with(AttachmentNotFoundError, "첨부 파일을 찾을 수 없습니다."):
        raise AttachmentNotFoundError(new_id())
    # when·then: 내용 없음 오류는 관리자 문의 문구다
    with raises_with(
        AttachmentContentMissingError, "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
    ):
        raise AttachmentContentMissingError

    # then: 둘 다 NotFound 계열이다
    assert issubclass(AttachmentNotFoundError, NotFoundError)
    assert issubclass(AttachmentContentMissingError, NotFoundError)


def test_the_two_not_found_errors_are_distinguishable() -> None:
    """두 NotFound 오류는 서로 구분된다."""
    # when: 두 오류의 상속 관계를 확인한다
    is_subclass = issubclass(AttachmentContentMissingError, AttachmentNotFoundError)

    # then: 내용 없음 오류는 첨부 없음 오류의 하위 클래스가 아니다
    assert not is_subclass
    assert not issubclass(AttachmentNotFoundError, AttachmentContentMissingError)


def test_forbidden_errors_are_access_denied_errors() -> None:
    """삭제·교체 권한 오류는 AccessDenied 계열이다."""
    # when: 삭제 권한 오류의 상속 관계를 확인한다
    is_denied = issubclass(AttachmentDeleteForbiddenError, AccessDeniedError)

    # then: 삭제 권한 오류는 AccessDenied 계열이다
    assert is_denied
    assert issubclass(AttachmentReplaceForbiddenError, AccessDeniedError)


def test_name_taken_names_the_file_and_is_an_already_exists_error() -> None:
    """같은 이름 오류는 파일 이름을 문구에 담고 AlreadyExists 계열이다.

    테스트 코드: AT-017
    """
    # when·then: 오류 문구가 "같은 이름의 파일이 이미 있습니다: a.pdf"다
    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        raise AttachmentNameTakenError("a.pdf")

    # then: AlreadyExists 계열이다
    assert issubclass(AttachmentNameTakenError, AlreadyExistsError)


@pytest.mark.parametrize(
    ("make", "after"),
    [
        (uploaded_draft, "업로드 a.pdf"),
        (replaced_draft, "교체 a.pdf"),
        (deleted_draft, "삭제 a.pdf"),
    ],
)
def test_history_drafts_are_attachment_entries_with_an_empty_before(
    make: object, after: str
) -> None:
    """이력 초안은 변경 전이 빈 문자열인 첨부 구분 항목이다.

    테스트 코드: AT-003
    """
    # when: 파일 이름으로 업로드·교체·삭제 이력 초안을 만든다
    draft = make(FileName.parse("a.pdf"))  # type: ignore[operator]

    # then: 구분은 첨부, 대상은 "첨부 파일", 변경 전은 "", 변경 후는 "업로드/교체/삭제 a.pdf"다
    assert draft.category is HistoryCategory.ATTACHMENT
    assert (draft.target, draft.before, draft.after) == (ATTACHMENT_TARGET, "", after)


def test_the_history_target_is_the_attachment_label() -> None:
    """이력 대상 문구는 "첨부 파일"이다.

    테스트 코드: AT-003
    """
    # when·then: 대상 상수가 "첨부 파일"이다
    assert ATTACHMENT_TARGET == "첨부 파일"


def test_history_text_uses_the_normalized_file_name() -> None:
    """이력 문구는 NFC로 정규화한 파일 이름을 쓴다.

    테스트 코드: AT-010
    """
    # given: NFD로 분해된 "한글.pdf"
    decomposed = unicodedata.normalize("NFD", "한글.pdf")

    # when: 업로드 이력 초안을 만든다
    draft = uploaded_draft(FileName.parse(decomposed))

    # then: 변경 후 문구가 NFC "업로드 한글.pdf"다
    assert draft.after == "업로드 한글.pdf"
