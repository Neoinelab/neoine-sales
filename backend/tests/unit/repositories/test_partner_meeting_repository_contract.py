"""PartnerMeetingRepository 계약(AC2·AC6·AC12): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트.

저장·읽기·수정·삭제와 참조 오류. 미팅은 Deal과 연결되지 않는다. 실패하는 호출은 테스트마다
마지막 하나뿐이다(SQL 트랜잭션).
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import PartnerMeetingNotFoundError
from app.domain.partner_meeting.values import MeetingContent, PartnerMeetingId
from tests.factories import NOW, later
from tests.factories_partner_meeting import make_meeting
from tests.support.ids import new_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase

KIM = uid("repo-kim")
PARK = uid("repo-park")


async def test_add_and_get_round_trip_keeps_every_field(meeting_case: MeetingCase) -> None:
    meeting = make_meeting(
        company="한빛파트너스",
        meeting_date=date(2026, 11, 5),
        content="계약 논의\n다음 주 재방문",
        author=KIM,
        now=NOW,
    )
    await meeting_case.add(meeting)

    stored = await meeting_case.repository.get(meeting.id)

    assert isinstance(stored, PartnerMeeting)
    assert stored.id == meeting.id
    assert stored.partner_company == "한빛파트너스"
    assert stored.meeting_date == date(2026, 11, 5)
    assert stored.content.value == "계약 논의\n다음 주 재방문"
    assert stored.author_user_id == KIM
    assert stored.created_at == stored.updated_at == NOW


async def test_a_very_long_multiline_unicode_content_round_trips(
    meeting_case: MeetingCase,
) -> None:
    text = ("한글 😀 line\n" * 20_000).strip()
    meeting = await meeting_case.add(make_meeting(content=text))

    stored = await meeting_case.repository.get(meeting.id)

    assert stored.content.value == text


async def test_get_with_for_update_returns_the_same_record(meeting_case: MeetingCase) -> None:
    meeting = await meeting_case.add(make_meeting())

    plain = await meeting_case.repository.get(meeting.id)
    locked = await meeting_case.repository.get(meeting.id, for_update=True)

    assert locked.id == plain.id
    assert locked.content == plain.content
    assert locked.partner_company == plain.partner_company


async def test_update_saves_company_date_content_and_updated_at_only(
    meeting_case: MeetingCase,
) -> None:
    meeting = await meeting_case.add(make_meeting(author=KIM, content="이전", now=NOW))
    meeting.revise(
        partner_company="다른파트너",
        meeting_date=date(2026, 12, 24),
        content=MeetingContent("이후"),
        now=later(3600),
    )

    await meeting_case.repository.update(meeting)

    stored = await meeting_case.repository.get(meeting.id)
    assert stored.partner_company == "다른파트너"
    assert stored.meeting_date == date(2026, 12, 24)
    assert stored.content.value == "이후"
    assert stored.updated_at == later(3600)
    assert stored.author_user_id == KIM
    assert stored.created_at == NOW


async def test_update_never_changes_the_author_or_created_at(meeting_case: MeetingCase) -> None:
    meeting = await meeting_case.add(make_meeting(author=KIM, now=NOW))
    await meeting_case.author(PARK)
    meeting.author_user_id = PARK
    meeting.created_at = later(999)
    meeting.content = MeetingContent("바뀐 내용")

    await meeting_case.repository.update(meeting)

    stored = await meeting_case.repository.get(meeting.id)
    assert stored.author_user_id == KIM
    assert stored.created_at == NOW


async def test_update_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.update(make_meeting())


async def test_delete_removes_only_that_meeting(meeting_case: MeetingCase) -> None:
    keep, drop = await meeting_case.add_many("남김", "지움")

    await meeting_case.repository.delete(drop.id)

    assert await meeting_case.contents() == ["남김"]
    assert (await meeting_case.repository.get(keep.id)).content.value == "남김"
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.get(drop.id)


async def test_delete_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.delete(PartnerMeetingId(new_id()))


async def test_get_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.get(PartnerMeetingId(new_id()))


async def test_the_same_company_date_and_content_may_be_stored_twice(
    meeting_case: MeetingCase,
) -> None:
    for _ in range(2):
        await meeting_case.add(make_meeting(meeting_date=date(2026, 10, 1), content="같은 내용"))

    assert await meeting_case.total() == 2


async def test_add_with_a_missing_author_raises_invalid_reference(
    meeting_case: MeetingCase,
) -> None:
    meeting = make_meeting(author=uid("repo-ghost"))

    with pytest.raises(InvalidReferenceError):
        await meeting_case.repository.add(meeting)


async def test_add_with_an_existing_id_raises_already_exists(meeting_case: MeetingCase) -> None:
    first = await meeting_case.add(make_meeting())
    duplicate = make_meeting(entity_id=first.id, content="다른 내용")

    with pytest.raises(AlreadyExistsError):
        await meeting_case.repository.add(duplicate)


async def test_a_far_future_date_is_stored_as_is(meeting_case: MeetingCase) -> None:
    meeting = await meeting_case.add(make_meeting(meeting_date=NOW.date() + timedelta(days=36_000)))

    stored = await meeting_case.repository.get(meeting.id)

    assert stored.meeting_date == NOW.date() + timedelta(days=36_000)
