"""UpdatePartnerMeeting(AC14·15·17): 판정 순서 404 -> 403 -> 422, 회사·Deal을 바꿀 때만 연결."""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
    DEAL_NOT_LINKED,
    MeetingInputError,
    PartnerMeetingEditForbiddenError,
    PartnerMeetingNotFoundError,
)
from app.domain.partner_meeting.values import PartnerMeetingId

from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.partner_meeting_env import (
    BOSS,
    EDIT_FORBIDDEN,
    HANBIT,
    KIM,
    NOT_FOUND,
    PARK,
    VIEWER,
    item,
)

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv

CONTENT_REQUIRED = "미팅 내용을 입력하세요."


def _found(error: MeetingInputError) -> list[tuple[tuple[str | int, ...], str]]:
    return [(issue.location, issue.message) for issue in error.issues]


async def test_the_author_changes_date_and_content_and_updated_at_moves(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)
    meeting_env.clock.advance(3600)

    record = await meeting_env.update.execute(
        created.meeting.id, item(code, meeting_date=date(2026, 12, 1), content="수정한 내용"), KIM
    )

    stored = (await meeting_env.stored(created.meeting.id)).meeting
    assert (stored.meeting_date, stored.content.value) == (date(2026, 12, 1), "수정한 내용")
    assert stored.updated_at == meeting_env.clock.now() > created.meeting.updated_at
    assert stored.created_at == created.meeting.created_at
    assert stored.author_user_id == KIM.user_id
    assert record.meeting.content.value == "수정한 내용"
    assert record.deal_name == "ERP 구축"


async def test_admin_edits_another_users_record(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    await meeting_env.update.execute(created.meeting.id, item(code, content="admin 수정"), BOSS)

    stored = (await meeting_env.stored(created.meeting.id)).meeting
    assert stored.content.value == "admin 수정"
    assert stored.author_user_id == KIM.user_id


async def test_a_content_only_change_skips_the_link_check(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)
    await meeting_env.unlink_partner(code)  # 그 사이 링크가 바뀌었다

    await meeting_env.update.execute(
        created.meeting.id, item(code, content="링크 해제 뒤 수정"), KIM
    )

    assert (
        await meeting_env.stored(created.meeting.id)
    ).meeting.content.value == "링크 해제 뒤 수정"


async def test_a_date_only_change_skips_the_link_check(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)
    await meeting_env.unlink_partner(code)

    await meeting_env.update.execute(
        created.meeting.id,
        item(code, meeting_date=date(2026, 9, 9), content=created.meeting.content.value),
        KIM,
    )

    assert (await meeting_env.stored(created.meeting.id)).meeting.meeting_date == date(2026, 9, 9)


async def test_a_company_spelling_that_differs_only_in_case_skips_the_link_check(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal(company="HanbitPartners")
    created = await meeting_env.register_one(KIM, code, company="HanbitPartners")
    await meeting_env.unlink_partner(code)

    await meeting_env.update.execute(
        created.meeting.id, item(code, company="HANBITpartners", content="대소문자만 다름"), KIM
    )

    assert (await meeting_env.stored(created.meeting.id)).meeting.content.value == "대소문자만 다름"


async def test_changing_the_deal_to_a_linked_one_moves_the_record_and_returns_its_name(
    meeting_env: MeetingEnv,
) -> None:
    first = await meeting_env.deal(name="ERP")
    second = await meeting_env.deal(name="MES")
    created = await meeting_env.register_one(KIM, first)

    record = await meeting_env.update.execute(created.meeting.id, item(second), KIM)

    assert record.meeting.subject.deal_code == second
    assert record.deal_name == "MES"
    assert (await meeting_env.stored(created.meeting.id)).meeting.subject.deal_code == second


async def test_changing_the_deal_to_an_unlinked_one_is_rejected_and_nothing_changes(
    meeting_env: MeetingEnv,
) -> None:
    first = await meeting_env.deal(name="ERP")
    await meeting_env.partner(HANBIT)
    foreign = await meeting_env.deal(name="타사", company="다른파트너")
    created = await meeting_env.register_one(KIM, first)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.meeting.id, item(foreign), KIM)

    assert _found(raised.value) == [(("deal_code",), DEAL_NOT_LINKED)]
    assert (await meeting_env.stored(created.meeting.id)).meeting.subject.deal_code == first


async def test_changing_the_company_rechecks_that_the_deal_belongs_to_it(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal(company=HANBIT)
    await meeting_env.partner("다른파트너")
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.meeting.id, item(code, company="다른파트너"), KIM)

    assert _found(raised.value) == [(("deal_code",), DEAL_NOT_LINKED)]


async def test_changing_to_an_unregistered_company_is_rejected_at_the_company_location(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.meeting.id, item(code, company="없는회사"), KIM)

    assert _found(raised.value) == [(("partner_company",), COMPANY_NOT_FOUND)]


async def test_a_blank_content_is_rejected_at_the_content_location(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.meeting.id, item(code, content="  \n"), KIM)

    assert _found(raised.value) == [(("content",), CONTENT_REQUIRED)]
    assert (await meeting_env.stored(created.meeting.id)).meeting.content.value == "킥오프 미팅"


async def test_a_date_outside_the_bounds_is_rejected_at_the_date_location(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(
            created.meeting.id, item(code, meeting_date=date(3000, 1, 1)), KIM
        )

    assert [location for location, _ in _found(raised.value)] == [("meeting_date",)]


async def test_an_update_without_changes_neither_saves_nor_commits(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)
    commits = meeting_env.uow.commits
    meeting_env.clock.advance(3600)

    record = await meeting_env.update.execute(
        created.meeting.id,
        item(
            code, meeting_date=created.meeting.meeting_date, content=created.meeting.content.value
        ),
        KIM,
    )

    assert meeting_env.uow.commits == commits
    assert record.meeting.updated_at == created.meeting.updated_at
    assert (await meeting_env.stored(created.meeting.id)).meeting.updated_at == (
        created.meeting.updated_at
    )


async def test_a_missing_record_is_not_found_before_validation(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()

    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.update.execute(
            PartnerMeetingId(new_id()), item(code, content="  ", company="없는회사"), PARK
        )


async def test_another_sales_is_forbidden_before_validation(meeting_env: MeetingEnv) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
        await meeting_env.update.execute(
            created.meeting.id, item(code, content="  ", company="없는회사"), PARK
        )

    assert (await meeting_env.stored(created.meeting.id)).meeting.content.value == "킥오프 미팅"


async def test_a_read_only_user_is_forbidden_even_for_their_own_record_id(
    meeting_env: MeetingEnv,
) -> None:
    code = await meeting_env.deal()
    created = await meeting_env.register_one(KIM, code)

    with pytest.raises(PartnerMeetingEditForbiddenError):
        await meeting_env.update.execute(created.meeting.id, item(code, content="변경"), VIEWER)
