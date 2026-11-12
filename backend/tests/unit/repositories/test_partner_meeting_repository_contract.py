"""PartnerMeetingRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트.

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
    """저장한 기록을 읽으면 모든 필드가 그대로다."""
    # given: 모든 필드를 지정한 기록
    meeting = make_meeting(
        company="한빛파트너스",
        meeting_date=date(2026, 11, 5),
        content="계약 논의\n다음 주 재방문",
        author=KIM,
        now=NOW,
    )
    await meeting_case.add(meeting)
    # when: 저장한 기록을 읽는다
    stored = await meeting_case.repository.get(meeting.id)
    # then: 필드가 모두 그대로다
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
    """길이 제한 없이 긴 여러 줄 유니코드 내용이 그대로 저장된다.

    테스트 코드: PA-007
    """
    # given: 2만 줄의 유니코드 내용으로 저장한 기록
    text = ("한글 😀 line\n" * 20_000).strip()
    meeting = await meeting_case.add(make_meeting(content=text))
    # when: 읽는다
    stored = await meeting_case.repository.get(meeting.id)
    # then: 보낸 글자와 똑같다
    assert stored.content.value == text


async def test_get_with_for_update_returns_the_same_record(meeting_case: MeetingCase) -> None:
    """잠금 읽기(for_update)도 같은 기록을 돌려준다."""
    # given: 저장한 기록
    meeting = await meeting_case.add(make_meeting())
    # when: 일반 읽기와 잠금 읽기로 각각 읽는다
    plain = await meeting_case.repository.get(meeting.id)
    locked = await meeting_case.repository.get(meeting.id, for_update=True)
    # then: 같은 기록이다
    assert locked.id == plain.id
    assert locked.content == plain.content
    assert locked.partner_company == plain.partner_company


async def test_update_saves_company_date_content_and_updated_at_only(
    meeting_case: MeetingCase,
) -> None:
    """수정은 회사·날짜·내용·변경 시각만 저장한다."""
    # given: 저장한 기록과 고친 값
    meeting = await meeting_case.add(make_meeting(author=KIM, content="이전", now=NOW))
    meeting.revise(
        partner_company="다른파트너",
        meeting_date=date(2026, 12, 24),
        content=MeetingContent("이후"),
        now=later(3600),
    )

    # when: 수정을 저장한다
    await meeting_case.repository.update(meeting)
    # then: 네 값이 바뀌고 작성자·등록 시각은 그대로다
    stored = await meeting_case.repository.get(meeting.id)
    assert stored.partner_company == "다른파트너"
    assert stored.meeting_date == date(2026, 12, 24)
    assert stored.content.value == "이후"
    assert stored.updated_at == later(3600)
    assert stored.author_user_id == KIM
    assert stored.created_at == NOW


async def test_update_never_changes_the_author_or_created_at(meeting_case: MeetingCase) -> None:
    """수정은 작성자와 등록 시각을 바꾸지 않는다."""
    # given: 작성자·등록 시각까지 바뀐 상태의 기록
    meeting = await meeting_case.add(make_meeting(author=KIM, now=NOW))
    await meeting_case.author(PARK)
    meeting.author_user_id = PARK
    meeting.created_at = later(999)
    meeting.content = MeetingContent("바뀐 내용")
    # when: 수정을 저장한다
    await meeting_case.repository.update(meeting)
    # then: 작성자와 등록 시각은 저장된 값 그대로다
    stored = await meeting_case.repository.get(meeting.id)
    assert stored.author_user_id == KIM
    assert stored.created_at == NOW


async def test_update_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    """없는 기록의 수정은 NotFound다."""
    # when·then: 저장하지 않은 기록을 수정하면 NotFound다
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.update(make_meeting())


async def test_delete_removes_only_that_meeting(meeting_case: MeetingCase) -> None:
    """삭제는 그 기록만 지운다."""
    # given: 기록 두 건
    keep, drop = await meeting_case.add_many("남김", "지움")
    # when: 한 건을 삭제한다
    await meeting_case.repository.delete(drop.id)
    # then: 다른 기록만 남는다
    assert await meeting_case.contents() == ["남김"]
    assert (await meeting_case.repository.get(keep.id)).content.value == "남김"
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.get(drop.id)


async def test_delete_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    """없는 기록의 삭제는 NotFound다."""
    # when·then: 없는 id를 삭제하면 NotFound다
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.delete(PartnerMeetingId(new_id()))


async def test_get_of_a_missing_meeting_raises_not_found(meeting_case: MeetingCase) -> None:
    """없는 기록의 읽기는 NotFound다."""
    # when·then: 없는 id를 읽으면 NotFound다
    with pytest.raises(PartnerMeetingNotFoundError):
        await meeting_case.repository.get(PartnerMeetingId(new_id()))


async def test_the_same_company_date_and_content_may_be_stored_twice(
    meeting_case: MeetingCase,
) -> None:
    """같은 회사·날짜·내용의 기록을 두 번 저장할 수 있다.

    테스트 코드: PA-006
    """
    # when: 같은 회사·날짜·내용으로 두 번 저장한다
    for _ in range(2):
        await meeting_case.add(make_meeting(meeting_date=date(2026, 10, 1), content="같은 내용"))
    # then: 두 건이 있다
    assert await meeting_case.total() == 2


async def test_add_with_a_missing_author_raises_invalid_reference(
    meeting_case: MeetingCase,
) -> None:
    """없는 작성자로 저장하면 InvalidReference다."""
    # given: 존재하지 않는 작성자의 기록
    meeting = make_meeting(author=uid("repo-ghost"))
    # when·then: 저장하면 InvalidReference다
    with pytest.raises(InvalidReferenceError):
        await meeting_case.repository.add(meeting)


async def test_add_with_an_existing_id_raises_already_exists(meeting_case: MeetingCase) -> None:
    """같은 id로 저장하면 AlreadyExists다."""
    # given: 저장한 기록과 같은 id의 다른 기록
    first = await meeting_case.add(make_meeting())
    duplicate = make_meeting(entity_id=first.id, content="다른 내용")
    # when·then: 저장하면 AlreadyExists다
    with pytest.raises(AlreadyExistsError):
        await meeting_case.repository.add(duplicate)


async def test_a_far_future_date_is_stored_as_is(meeting_case: MeetingCase) -> None:
    """아주 먼 미래 날짜도 그대로 저장된다.

    테스트 코드: PA-006
    """
    # given: 약 100년 뒤 날짜의 기록
    meeting = await meeting_case.add(make_meeting(meeting_date=NOW.date() + timedelta(days=36_000)))
    # when: 읽는다
    stored = await meeting_case.repository.get(meeting.id)
    # then: 날짜가 그대로다
    assert stored.meeting_date == NOW.date() + timedelta(days=36_000)
