"""ContractAttachment 엔티티: 업로드로 만들기, 교체, 삭제·교체 권한은 Deal 첨부와 같다."""

import pytest

from app.domain.attachment.errors import (
    AttachmentDeleteForbiddenError,
    AttachmentReplaceForbiddenError,
)
from app.domain.attachment.values import FileName, UploadCandidate
from app.domain.auth.principal import Role
from app.domain.license_contract.values import ContractAttachmentId
from app.domain.user.value_objects import UserRef
from tests.factories import later
from tests.factories_license_contract import make_contract, make_contract_attachment
from tests.support.ids import new_id
from tests.support.user_ids import uid

KIM = uid("lca-kim")
PARK = uid("lca-park")


def _ref(user_id: object, role: Role, *, resigned: bool = False) -> UserRef:
    return UserRef(id=user_id, name="업로더", resigned=resigned, role=role)  # type: ignore[arg-type]


def test_upload_keeps_every_field_and_stamps_all_times_with_now() -> None:
    """첨부를 만들면 모든 필드가 담기고 시각이 모두 now다.

    테스트 코드: LC-063
    """
    # given: 계약과 업로드 후보 파일
    contract = make_contract()
    entity_id = ContractAttachmentId(new_id())

    from app.domain.license_contract.attachment import ContractAttachment  # noqa: PLC0415

    # when: ContractAttachment.upload로 만든다
    attachment = ContractAttachment.upload(
        contract_id=contract.id,
        deal_code=contract.deal_code,
        candidate=UploadCandidate.check(file_name="계약서.pdf", description=" 최종 ", size=1_234),
        size=1_234,
        mime="application/pdf",
        storage_key="b" * 32,
        uploaded_by=KIM,
        now=later(5),
        entity_id=entity_id,
    )

    # then: 계약·Deal·이름·설명(공백 제거)·크기·MIME·키·업로더·시각이 담긴다
    assert attachment.id == entity_id
    assert (attachment.contract_id, attachment.deal_code) == (contract.id, contract.deal_code)
    assert attachment.file_name == FileName.parse("계약서.pdf")
    assert attachment.description == "최종"
    assert (attachment.size, attachment.mime, attachment.storage_key) == (
        1_234,
        "application/pdf",
        "b" * 32,
    )
    assert attachment.uploaded_by == KIM
    assert attachment.uploaded_at == attachment.created_at == attachment.updated_at == later(5)


def test_replace_swaps_the_content_fields_and_returns_the_previous_key() -> None:
    """교체하면 내용 필드가 바뀌고 이전 저장 키를 돌려준다.

    테스트 코드: LC-066
    """
    # given: 첨부 하나
    attachment = make_contract_attachment(make_contract(), storage_key="old" + "0" * 29)

    # when: 새 설명·크기·키·업로더로 교체한다
    previous = attachment.replace(
        description="새 설명",
        size=99,
        mime="text/plain",
        storage_key="new" + "0" * 29,
        uploaded_by=PARK,
        now=later(),
    )

    # then: 이전 키 반환, 내용 필드·업로더·시각 갱신
    assert previous == "old" + "0" * 29
    assert (attachment.description, attachment.size, attachment.mime) == (
        "새 설명",
        99,
        "text/plain",
    )
    assert attachment.storage_key == "new" + "0" * 29
    assert (attachment.uploaded_by, attachment.uploaded_at, attachment.updated_at) == (
        PARK,
        later(),
        later(),
    )


@pytest.mark.parametrize(
    ("role", "uploader_is_me", "uploader_role", "uploader_resigned", "expected"),
    [
        (Role.ADMIN, False, Role.SALES, False, True),
        (Role.SALES, True, Role.SALES, False, True),
        (Role.SALES, False, Role.SALES, False, False),
        (Role.SALES, False, Role.SALES, True, True),  # 퇴사한 sales의 파일
        (Role.SALES, False, Role.ADMIN, True, False),
        (Role.USER, True, Role.USER, False, False),
    ],
)
def test_contract_attachment_permission_matches_deal_rule(
    role: Role,
    uploader_is_me: bool,
    uploader_role: Role,
    uploader_resigned: bool,
    expected: bool,
) -> None:
    """계약 첨부의 삭제·교체 권한은 Deal 첨부 규칙과 같다.

    테스트 코드: LC-077
    """
    # given: 요청자 역할과 업로더(본인·퇴사자 여부)
    attachment = make_contract_attachment(make_contract())
    uploader = _ref(KIM if uploader_is_me else PARK, uploader_role, resigned=uploader_resigned)

    if expected:
        attachment.ensure_deletable_by(KIM, role, uploader)
        attachment.ensure_replaceable_by(KIM, role, uploader)
        return
    with pytest.raises(AttachmentDeleteForbiddenError):
        attachment.ensure_deletable_by(KIM, role, uploader)
    # when: 삭제·교체 권한을 확인한다
    with pytest.raises(AttachmentReplaceForbiddenError):
        attachment.ensure_replaceable_by(KIM, role, uploader)
    # then: 허용이면 통과, 아니면 삭제·교체 거절 오류
