"""DeletePartnerMeeting(AC14·16): 작성자 본인과 admin만 물리 삭제, 판정 순서 404 -> 403."""

from typing import TYPE_CHECKING

import pytest
from app.domain.partner_meeting.errors import (
    PartnerMeetingDeleteForbiddenError,
    PartnerMeetingNotFoundError,
)
from app.domain.partner_meeting.values import PartnerMeetingId

from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.partner_meeting_env import (
    BOSS,
    DELETE_FORBIDDEN,
    KIM,
    NOT_FOUND,
    PARK,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def test_the_author_sales_deletes_the_record_physically(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    await meeting_env.delete.execute(created.meeting.id, KIM)

    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_env.stored(created.meeting.id)
    assert await meeting_env.everything() == []


async def test_admin_deletes_another_users_record(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    await meeting_env.delete.execute(created.meeting.id, BOSS)

    assert await meeting_env.everything() == []


async def test_deleting_one_record_keeps_the_others(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    keep = await meeting_env.register_one(KIM, code, content="남는 기록")
    drop = await meeting_env.register_one(KIM, code, content="지울 기록")

    await meeting_env.delete.execute(drop.meeting.id, KIM)

    assert [r.meeting.id for r in await meeting_env.everything()] == [keep.meeting.id]


async def test_another_sales_is_forbidden_and_the_record_stays(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with raises_with(PartnerMeetingDeleteForbiddenError, DELETE_FORBIDDEN):
        await meeting_env.delete.execute(created.meeting.id, PARK)

    assert len(await meeting_env.everything()) == 1


async def test_a_read_only_user_is_forbidden(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(PartnerMeetingDeleteForbiddenError):
        await meeting_env.delete.execute(created.meeting.id, VIEWER)

    assert len(await meeting_env.everything()) == 1


async def test_a_missing_record_is_not_found(meeting_env: MeetingEnv) -> None:
    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.delete.execute(PartnerMeetingId(new_id()), KIM)


async def test_not_found_wins_over_forbidden_for_a_read_only_user(meeting_env: MeetingEnv) -> None:
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_env.delete.execute(PartnerMeetingId(new_id()), VIEWER)
