"""첨부 업로드·교체·삭제가 Deal 이력에 남기는 문구."""

from typing import TYPE_CHECKING

from app.domain.deal.history import HistoryCategory, HistoryDraft

if TYPE_CHECKING:
    from app.domain.attachment.values import FileName

ATTACHMENT_TARGET = "첨부 파일"


def _draft(verb: str, name: FileName) -> HistoryDraft:
    return HistoryDraft(HistoryCategory.ATTACHMENT, ATTACHMENT_TARGET, "", f"{verb} {name.value}")


def uploaded_draft(name: FileName) -> HistoryDraft:
    return _draft("업로드", name)


def replaced_draft(name: FileName) -> HistoryDraft:
    return _draft("교체", name)


def deleted_draft(name: FileName) -> HistoryDraft:
    return _draft("삭제", name)
