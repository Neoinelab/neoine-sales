"""파트너 미팅 id는 UoW의 IdAllocator가 주는 번호다(종류 PARTNER_MEETING, 번호를 나누지 않는다)."""

from typing import TYPE_CHECKING

from app.application.ids import new_partner_meeting_id
from app.application.ports.id_allocator import IdKind

if TYPE_CHECKING:
    from tests.fakes.unit_of_work import FakeUnitOfWork


def test_the_partner_meeting_kind_has_the_planned_value() -> None:
    assert IdKind.PARTNER_MEETING.value == "partner_meeting"


async def test_new_partner_meeting_id_counts_up_from_one(uow: FakeUnitOfWork) -> None:
    first = await new_partner_meeting_id(uow.ids)
    second = await new_partner_meeting_id(uow.ids)

    assert (first, second) == (1, 2)


async def test_partner_meeting_ids_do_not_share_numbers_with_other_kinds(
    uow: FakeUnitOfWork,
) -> None:
    await uow.ids.next_id(IdKind.REPORT)
    await uow.ids.next_id(IdKind.REPORT)

    assert await new_partner_meeting_id(uow.ids) == 1
