"""첨부 오류의 종류·문구(P2b 4.6)와 Deal 이력 문구(P2b AC-07·10·14)."""

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
    with raises_with(AttachmentNotFoundError, "첨부 파일을 찾을 수 없습니다."):
        raise AttachmentNotFoundError(new_id())
    with raises_with(
        AttachmentContentMissingError, "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
    ):
        raise AttachmentContentMissingError

    assert issubclass(AttachmentNotFoundError, NotFoundError)
    assert issubclass(AttachmentContentMissingError, NotFoundError)


def test_the_two_not_found_errors_are_distinguishable() -> None:
    assert not issubclass(AttachmentContentMissingError, AttachmentNotFoundError)
    assert not issubclass(AttachmentNotFoundError, AttachmentContentMissingError)


def test_forbidden_errors_are_access_denied_errors() -> None:
    assert issubclass(AttachmentDeleteForbiddenError, AccessDeniedError)
    assert issubclass(AttachmentReplaceForbiddenError, AccessDeniedError)


def test_name_taken_names_the_file_and_is_an_already_exists_error() -> None:
    with raises_with(AttachmentNameTakenError, "같은 이름의 파일이 이미 있습니다: a.pdf"):
        raise AttachmentNameTakenError("a.pdf")

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
    draft = make(FileName.parse("a.pdf"))  # type: ignore[operator]

    assert draft.category is HistoryCategory.ATTACHMENT
    assert (draft.target, draft.before, draft.after) == (ATTACHMENT_TARGET, "", after)


def test_the_history_target_is_the_attachment_label() -> None:
    assert ATTACHMENT_TARGET == "첨부 파일"


def test_history_text_uses_the_normalized_file_name() -> None:
    decomposed = unicodedata.normalize("NFD", "한글.pdf")

    assert uploaded_draft(FileName.parse(decomposed)).after == "업로드 한글.pdf"
