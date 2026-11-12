"""Attachment 엔티티: 업로드로 만들기, 교체, 삭제·교체 권한."""

from datetime import timedelta

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
from tests.support.ids import new_id
from tests.support.user_ids import uid

KIM = uid("kim")
PARK = uid("park")


def _ref(user_id: object, role: Role, *, resigned: bool = False) -> UserRef:
    return UserRef(id=user_id, name="업로더", resigned=resigned, role=role)  # type: ignore[arg-type]


def test_upload_keeps_every_field_and_stamps_all_times_with_now() -> None:
    """업로드로 만든 첨부는 모든 필드를 그대로 두고 세 시각을 현재 시각으로 찍는다."""
    # given: Deal code와 검증을 통과한 업로드 후보
    code = make_deal_code()
    candidate = UploadCandidate.check(file_name="견적서.pdf", description=" 최종 ", size=1_234)

    # when: 요청 시각으로 첨부를 만든다
    attachment = Attachment.upload(
        deal_code=code,
        candidate=candidate,
        size=1_234,
        mime="application/pdf",
        storage_key="a" * 32,
        uploaded_by=KIM,
        now=later(5),
        entity_id=AttachmentId(new_id()),
    )

    # then: 모든 필드가 입력대로이고 설명은 공백이 제거되며 세 시각이 같다
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


def test_upload_uses_the_given_id() -> None:
    """첨부는 주어진 id를 쓴다."""
    # given: 고정 id
    fixed = AttachmentId(new_id())

    # when: 고정 id로 첨부를 만든다
    used_id = make_attachment(entity_id=fixed).id

    # then: 첨부의 id가 고정 id다
    assert used_id == fixed


def test_attachments_are_equal_when_their_ids_are_equal() -> None:
    """id가 같은 첨부는 다른 필드가 달라도 같다."""
    # given: 첨부 하나
    attachment = make_attachment()

    # when: 같은 id에 다른 이름을 준 첨부를 만든다
    same_id = make_attachment(entity_id=attachment.id, name="other.txt")

    # then: 두 첨부가 같다
    assert attachment == same_id


def test_upload_requires_a_timezone_aware_time() -> None:
    """시간대 없는 시각으로는 첨부를 만들 수 없다."""
    # when·then: 시간대 없는 시각으로 만들면 값 오류다
    with pytest.raises(InvalidValueError):
        make_attachment(NOW.replace(tzinfo=None))


def test_replace_returns_the_previous_storage_key_and_swaps_the_content_fields() -> None:
    """교체하면 이전 저장 키를 돌려주고 내용 필드를 바꾸되 id·생성 시각은 유지한다.

    테스트 코드: AT-019
    """
    # given: 설명 "이전", 키 "1" 32개인 첨부
    original = make_attachment(NOW, name="a.pdf", description="이전", storage_key="1" * 32)
    original_id, created = original.id, original.created_at

    # when: 새 설명·크기·mime·키·업로더·시각으로 교체한다
    old_key = original.replace(
        description="새 설명",
        size=99,
        mime="text/plain",
        storage_key="2" * 32,
        uploaded_by=PARK,
        now=later(60),
    )

    # then: 이전 키를 돌려주고 내용 필드·업로더·시각이 새 값이며 id·생성 시각은 그대로다
    assert old_key == "1" * 32
    assert (original.description, original.size, original.mime) == ("새 설명", 99, "text/plain")
    assert (original.storage_key, original.uploaded_by) == ("2" * 32, PARK)
    assert original.uploaded_at == original.updated_at == later(60)
    assert (original.id, original.created_at) == (original_id, created)


def test_replace_never_changes_the_name_or_the_deal() -> None:
    """교체해도 이름과 소속 Deal은 바뀌지 않는다.

    테스트 코드: AT-019
    """
    # given: "a.pdf" 첨부
    attachment = make_attachment(name="a.pdf")
    deal_code = attachment.deal_code

    # when: 새 내용으로 교체한다
    attachment.replace(
        description="", size=1, mime="x/y", storage_key="3" * 32, uploaded_by=KIM, now=later(1)
    )

    # then: 이름과 Deal code가 그대로다
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
    """삭제와 교체는 같은 권한 규칙(admin 모두, sales는 본인·퇴사 sales 파일, user 불가)을 쓴다.

    테스트 코드: AT-037
    """
    # given: 업로더 정보가 있는 첨부
    attachment = make_attachment(uploaded_by=uploader.id)

    # when·then: 허용이면 삭제·교체 확인이 통과하고, 아니면 둘 다 권한 오류다
    if allowed:
        attachment.ensure_deletable_by(KIM, role, uploader)
        attachment.ensure_replaceable_by(KIM, role, uploader)
        return
    with pytest.raises(AttachmentDeleteForbiddenError):
        attachment.ensure_deletable_by(KIM, role, uploader)
    with pytest.raises(AttachmentReplaceForbiddenError):
        attachment.ensure_replaceable_by(KIM, role, uploader)


def test_the_forbidden_errors_carry_their_own_sentences() -> None:
    """삭제·교체 권한 오류는 각자의 문구를 가진다.

    테스트 코드: AT-037
    """
    # given: 다른 사람이 올린 첨부
    attachment = make_attachment(uploaded_by=PARK)
    uploader = _ref(PARK, Role.SALES)

    # when·then: 삭제 확인은 "본인이 올린 파일만 삭제할 수 있습니다."로 거절한다
    with raises_with(AttachmentDeleteForbiddenError, "본인이 올린 파일만 삭제할 수 있습니다."):
        attachment.ensure_deletable_by(KIM, Role.SALES, uploader)
    # when·then: 교체 확인은 "본인이 올린 파일만 교체할 수 있습니다."로 거절한다
    with raises_with(AttachmentReplaceForbiddenError, "본인이 올린 파일만 교체할 수 있습니다."):
        attachment.ensure_replaceable_by(KIM, Role.SALES, uploader)


def test_a_replaced_attachment_is_newer_than_before() -> None:
    """교체한 첨부의 업로드 시각은 이전보다 늦다."""
    # given: 첨부와 교체 전 업로드 시각
    attachment = make_attachment(NOW)
    before = attachment.uploaded_at

    # when: 한 시간 뒤로 교체한다
    attachment.replace(
        description="",
        size=1,
        mime="x/y",
        storage_key="4" * 32,
        uploaded_by=KIM,
        now=NOW + timedelta(hours=1),
    )

    # then: 업로드 시각이 이전보다 늦다
    assert attachment.uploaded_at > before
