"""Attachment 엔티티(P2b AC-07·10·11·14): 업로드로 만들기, 교체, 삭제·교체 권한."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.attachment.entities import Attachment
from app.domain.attachment.errors import (
    AttachmentDeleteForbiddenError,
    AttachmentReplaceForbiddenError,
)
from app.domain.attachment.values import AttachmentId, FileName, UploadCandidate
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.value_objects import UserRef
from tests.factories import NOW, later, make_deal_code
from tests.factories_attachment import make_attachment
from tests.support.expect import raises_with
from tests.support.user_ids import uid

KIM = uid("kim")
PARK = uid("park")


def _ref(user_id: object, role: Role, *, resigned: bool = False) -> UserRef:
    return UserRef(id=user_id, name="업로더", resigned=resigned, role=role)  # type: ignore[arg-type]


def test_upload_keeps_every_field_and_stamps_all_times_with_now() -> None:
    code = make_deal_code()
    candidate = UploadCandidate.check(file_name="견적서.pdf", description=" 최종 ", size=1_234)

    attachment = Attachment.upload(
        deal_code=code,
        candidate=candidate,
        size=1_234,
        mime="application/pdf",
        storage_key="a" * 32,
        uploaded_by=KIM,
        now=later(5),
    )

    assert attachment.deal_code == code
    assert attachment.file_name == FileName.parse("견적서.pdf")
    assert attachment.description == "최종"
    assert (attachment.size, attachment.mime, attachment.storage_key) == (
        1_234,
        "application/pdf",
        "a" * 32,
    )
    assert attachment.uploaded_by == KIM
    assert attachment.uploaded_at == attachment.created_at == attachment.updated_at == later(5)


def test_upload_gives_each_attachment_its_own_id_unless_one_is_given() -> None:
    first, second = make_attachment(), make_attachment()
    fixed = AttachmentId(uuid4())

    assert isinstance(first.id, UUID)
    assert first.id != second.id
    assert make_attachment(entity_id=fixed).id == fixed


def test_attachments_are_equal_when_their_ids_are_equal() -> None:
    attachment = make_attachment()

    assert attachment == make_attachment(entity_id=attachment.id, name="other.txt")


def test_upload_requires_a_timezone_aware_time() -> None:
    with pytest.raises(InvalidValueError):
        make_attachment(NOW.replace(tzinfo=None))


def test_replace_returns_the_previous_storage_key_and_swaps_the_content_fields() -> None:
    original = make_attachment(NOW, name="a.pdf", description="이전", storage_key="1" * 32)
    original_id, created = original.id, original.created_at

    old_key = original.replace(
        description="새 설명",
        size=99,
        mime="text/plain",
        storage_key="2" * 32,
        uploaded_by=PARK,
        now=later(60),
    )

    assert old_key == "1" * 32
    assert (original.description, original.size, original.mime) == ("새 설명", 99, "text/plain")
    assert (original.storage_key, original.uploaded_by) == ("2" * 32, PARK)
    assert original.uploaded_at == original.updated_at == later(60)
    assert (original.id, original.created_at) == (original_id, created)


def test_replace_never_changes_the_name_or_the_deal() -> None:
    attachment = make_attachment(name="a.pdf")
    deal_code = attachment.deal_code

    attachment.replace(
        description="", size=1, mime="x/y", storage_key="3" * 32, uploaded_by=KIM, now=later(1)
    )

    assert attachment.file_name == FileName.parse("a.pdf")
    assert attachment.deal_code == deal_code


@pytest.mark.parametrize(
    ("role", "uploader", "allowed"),
    [
        (Role.ADMIN, _ref(PARK, Role.SALES), True),
        (Role.SALES, _ref(KIM, Role.SALES), True),
        (Role.SALES, _ref(PARK, Role.SALES, resigned=True), True),
        (Role.SALES, _ref(PARK, Role.SALES), False),
        (Role.SALES, _ref(PARK, Role.ADMIN, resigned=True), False),
        (Role.USER, _ref(KIM, Role.USER), False),
    ],
)
def test_delete_and_replace_share_one_permission_rule(
    role: Role, uploader: UserRef, allowed: bool
) -> None:
    attachment = make_attachment(uploaded_by=uploader.id)

    if allowed:
        attachment.ensure_deletable_by(KIM, role, uploader)
        attachment.ensure_replaceable_by(KIM, role, uploader)
        return
    with pytest.raises(AttachmentDeleteForbiddenError):
        attachment.ensure_deletable_by(KIM, role, uploader)
    with pytest.raises(AttachmentReplaceForbiddenError):
        attachment.ensure_replaceable_by(KIM, role, uploader)


def test_the_forbidden_errors_carry_their_own_sentences() -> None:
    attachment = make_attachment(uploaded_by=PARK)
    uploader = _ref(PARK, Role.SALES)

    with raises_with(AttachmentDeleteForbiddenError, "본인이 올린 파일만 삭제할 수 있습니다."):
        attachment.ensure_deletable_by(KIM, Role.SALES, uploader)
    with raises_with(AttachmentReplaceForbiddenError, "본인이 올린 파일만 교체할 수 있습니다."):
        attachment.ensure_replaceable_by(KIM, Role.SALES, uploader)


def test_a_replaced_attachment_is_newer_than_before() -> None:
    attachment = make_attachment(NOW)
    before = attachment.uploaded_at

    attachment.replace(
        description="",
        size=1,
        mime="x/y",
        storage_key="4" * 32,
        uploaded_by=KIM,
        now=NOW + timedelta(hours=1),
    )

    assert attachment.uploaded_at > before
