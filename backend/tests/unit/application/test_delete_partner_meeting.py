"""DeletePartnerMeeting: 작성자 본인과 admin만 물리 삭제, 판정 순서 404 -> 403."""

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
    HANBIT,
    KIM,
    NOT_FOUND,
    PARK,
    VIEWER,
)

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def test_deleting_one_record_keeps_the_others(meeting_env: MeetingEnv) -> None:
    """작성자가 삭제하면 그 기록만 사라지고 나머지는 남는다.

    테스트 코드: PA-039
    """
    # given: KIM의 기록 두 건
    await meeting_env.partner(HANBIT)
    keep = await meeting_env.register_one(KIM, content="남는 기록")
    drop = await meeting_env.register_one(KIM, content="지울 기록")
    # when: KIM이 한 건을 삭제한다
    await meeting_env.delete.execute(drop.id, KIM)
    # then: 지운 기록은 없고 다른 기록만 남는다
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_env.stored(drop.id)
    assert [m.id for m in await meeting_env.everything()] == [keep.id]


async def test_admin_deletes_another_users_record(meeting_env: MeetingEnv) -> None:
    """admin은 남의 기록을 삭제한다.

    테스트 코드: PA-040
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when: admin이 삭제한다
    await meeting_env.delete.execute(created.id, BOSS)
    # then: 기록이 없다
    assert await meeting_env.everything() == []


async def test_another_sales_is_forbidden_and_the_record_stays(meeting_env: MeetingEnv) -> None:
    """다른 sales의 삭제는 403 문구이고 기록은 남는다.

    테스트 코드: PA-041
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: PARK이 삭제하면 "본인 미팅 기록 또는 admin만 삭제할 수 있습니다." 오류다
    with raises_with(PartnerMeetingDeleteForbiddenError, DELETE_FORBIDDEN):
        await meeting_env.delete.execute(created.id, PARK)
    # then: 기록은 남아 있다
    assert len(await meeting_env.everything()) == 1


async def test_a_read_only_user_is_forbidden(meeting_env: MeetingEnv) -> None:
    """user 역할의 삭제는 거절되고 기록은 남는다.

    테스트 코드: PA-041
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: user 역할로 삭제하면 삭제 금지 오류다
    with pytest.raises(PartnerMeetingDeleteForbiddenError):
        await meeting_env.delete.execute(created.id, VIEWER)
    # then: 기록은 남아 있다
    assert len(await meeting_env.everything()) == 1


async def test_a_missing_record_is_not_found(meeting_env: MeetingEnv) -> None:
    """없는 기록의 삭제는 404다.

    테스트 코드: PA-042
    """
    # when·then: 없는 id를 삭제하면 "미팅 기록을 찾을 수 없습니다." 오류다
    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.delete.execute(PartnerMeetingId(new_id()), KIM)


async def test_deleting_the_same_record_twice_is_not_found_the_second_time(
    meeting_env: MeetingEnv,
) -> None:
    """같은 기록의 두 번째 삭제는 404다.

    테스트 코드: PA-042
    """
    # given: 한 번 삭제한 KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    await meeting_env.delete.execute(created.id, KIM)
    # when·then: 같은 기록을 다시 삭제하면 "미팅 기록을 찾을 수 없습니다." 오류다
    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.delete.execute(created.id, KIM)


async def test_not_found_wins_over_forbidden_for_a_read_only_user(meeting_env: MeetingEnv) -> None:
    """유스케이스는 없는 기록이면 user 역할이라도 404를 먼저 판정한다."""
    # when·then: user 역할이 없는 id를 삭제하면 404 오류다
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_env.delete.execute(PartnerMeetingId(new_id()), VIEWER)
