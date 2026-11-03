"""UpdatePartnerMeeting(AC6): 판정 순서 404 -> 403 -> 422, 회사를 바꿀 때만 회사 목록을 확인."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
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
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    meeting_env.clock.advance(3600)

    updated = await meeting_env.update.execute(
        created.id, item(meeting_date=date(2026, 12, 1), content="수정한 내용"), KIM
    )

    stored = await meeting_env.stored(created.id)
    assert (stored.meeting_date, stored.content.value) == (date(2026, 12, 1), "수정한 내용")
    assert stored.updated_at == meeting_env.clock.now() > created.updated_at
    assert stored.created_at == created.created_at
    assert stored.author_user_id == KIM.user_id
    assert updated.content.value == "수정한 내용"


async def test_admin_edits_another_users_record(meeting_env: MeetingEnv) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    await meeting_env.update.execute(created.id, item(content="admin 수정"), BOSS)

    stored = await meeting_env.stored(created.id)
    assert stored.content.value == "admin 수정"
    assert stored.author_user_id == KIM.user_id


async def test_same_company_in_other_case_keeps_the_stored_company_without_lookup(
    meeting_env: MeetingEnv,
) -> None:
    contact = await meeting_env.partner("HanbitPartners")
    created = await meeting_env.register_one(KIM, company="HanbitPartners")
    await meeting_env.drop_partner(contact)  # 회사 목록에서 사라졌지만 확인하지 않는다

    await meeting_env.update.execute(
        created.id, item(company="HANBITpartners", content="대소문자만 다름"), KIM
    )

    stored = await meeting_env.stored(created.id)
    assert stored.content.value == "대소문자만 다름"
    assert stored.partner_company == "HanbitPartners"


async def test_editing_date_and_content_succeeds_after_the_contact_company_was_renamed(
    meeting_env: MeetingEnv,
) -> None:
    contact = await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    await meeting_env.drop_partner(contact)
    await meeting_env.partner("새이름파트너")

    await meeting_env.update.execute(
        created.id, item(company=HANBIT, meeting_date=date(2026, 9, 9), content="이름 변경 뒤"), KIM
    )

    stored = await meeting_env.stored(created.id)
    assert (stored.partner_company, stored.meeting_date) == (HANBIT, date(2026, 9, 9))
    assert stored.content.value == "이름 변경 뒤"


async def test_changing_to_another_registered_company_stores_the_new_spelling(
    meeting_env: MeetingEnv,
) -> None:
    await meeting_env.partner(HANBIT)
    await meeting_env.partner("OtherPartners")
    created = await meeting_env.register_one(KIM)

    updated = await meeting_env.update.execute(created.id, item(company="otherPARTNERS"), KIM)

    assert updated.partner_company == "OtherPartners"
    assert (await meeting_env.stored(created.id)).partner_company == "OtherPartners"


async def test_changing_to_an_unknown_company_is_rejected_at_partner_company(
    meeting_env: MeetingEnv,
) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(company="없는회사"), KIM)

    assert _found(raised.value) == [(("partner_company",), COMPANY_NOT_FOUND)]
    assert (await meeting_env.stored(created.id)).partner_company == HANBIT


async def test_a_blank_content_is_rejected_at_the_content_location(
    meeting_env: MeetingEnv,
) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(content="  \n"), KIM)

    assert _found(raised.value) == [(("content",), CONTENT_REQUIRED)]
    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_date_outside_the_bounds_is_rejected_at_the_date_location(
    meeting_env: MeetingEnv,
) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(meeting_date=date(3000, 1, 1)), KIM)

    assert [location for location, _ in _found(raised.value)] == [("meeting_date",)]


async def test_no_change_does_not_save(meeting_env: MeetingEnv) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    commits = meeting_env.uow.commits
    meeting_env.clock.advance(3600)

    returned = await meeting_env.update.execute(
        created.id, item(meeting_date=created.meeting_date, content=created.content.value), KIM
    )

    assert meeting_env.uow.commits == commits
    assert returned.updated_at == created.updated_at
    assert (await meeting_env.stored(created.id)).updated_at == created.updated_at


async def test_a_missing_record_is_not_found_before_validation(meeting_env: MeetingEnv) -> None:
    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.update.execute(
            PartnerMeetingId(new_id()), item(content="  ", company="없는회사"), PARK
        )


async def test_another_sales_is_forbidden_before_validation(meeting_env: MeetingEnv) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
        await meeting_env.update.execute(created.id, item(content="  ", company="없는회사"), PARK)

    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_read_only_user_is_forbidden_even_for_their_own_record_id(
    meeting_env: MeetingEnv,
) -> None:
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)

    with pytest.raises(PartnerMeetingEditForbiddenError):
        await meeting_env.update.execute(created.id, item(content="변경"), VIEWER)
