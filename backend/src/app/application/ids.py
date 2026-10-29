"""종류별 id 할당 헬퍼. 유스케이스는 `IdAllocator.next_id`를 직접 부르지 않고 이 함수를 쓴다."""

from typing import TYPE_CHECKING

from app.application.ports.id_allocator import IdKind
from app.domain.action_type.values import ActionTypeId
from app.domain.attachment.values import AttachmentId
from app.domain.auth.session import SessionId
from app.domain.bant.values import BantLabelId
from app.domain.code.values import CodeId
from app.domain.contact.values import ContactId
from app.domain.deal_action.value_objects import DealActionId
from app.domain.partner_meeting.values import PartnerMeetingId
from app.domain.saved_report.values import ReportId
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId

if TYPE_CHECKING:
    from app.application.ports.id_allocator import IdAllocator


async def new_user_id(ids: IdAllocator) -> UserId:
    return UserId(await ids.next_id(IdKind.USER))


async def new_session_id(ids: IdAllocator) -> SessionId:
    return SessionId(await ids.next_id(IdKind.SESSION))


async def new_contact_id(ids: IdAllocator) -> ContactId:
    return ContactId(await ids.next_id(IdKind.CONTACT))


async def new_code_id(ids: IdAllocator) -> CodeId:
    return CodeId(await ids.next_id(IdKind.CODE))


async def new_bant_label_id(ids: IdAllocator) -> BantLabelId:
    return BantLabelId(await ids.next_id(IdKind.BANT_LABEL))


async def new_action_type_id(ids: IdAllocator) -> ActionTypeId:
    return ActionTypeId(await ids.next_id(IdKind.ACTION_TYPE))


async def new_vendor_id(ids: IdAllocator) -> VendorId:
    return VendorId(await ids.next_id(IdKind.VENDOR))


async def new_deal_action_id(ids: IdAllocator) -> DealActionId:
    return DealActionId(await ids.next_id(IdKind.DEAL_ACTION))


async def new_attachment_id(ids: IdAllocator) -> AttachmentId:
    return AttachmentId(await ids.next_id(IdKind.ATTACHMENT))


async def new_report_id(ids: IdAllocator) -> ReportId:
    return ReportId(await ids.next_id(IdKind.REPORT))


async def new_partner_meeting_id(ids: IdAllocator) -> PartnerMeetingId:
    return PartnerMeetingId(await ids.next_id(IdKind.PARTNER_MEETING))
