"""RegisterPartnerMeetings(AC1·AC2): 파트너 회사 검증, 원자성, 위치별 위반(Deal은 무관)."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.partner_meeting.errors import COMPANY_NOT_FOUND, NO_ITEMS, MeetingInputError
from tests.support.expect import raises_with
from tests.unit.application.partner_meeting_env import HANBIT, KIM, item

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv

CONTENT_REQUIRED = "미팅 내용을 입력하세요."
OUT_OF_BOUNDS = "미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다"


def _found(error: MeetingInputError) -> list[tuple[tuple[str | int, ...], str]]:
    return [(issue.location, issue.message) for issue in error.issues]


class TestSaving:
    async def test_valid_items_are_saved_in_input_order_in_one_commit(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)
        meeting_env.clock.advance(60)

        saved = await meeting_env.register.execute(
            [
                item(content="첫 번째", meeting_date=date(2026, 10, 3)),
                item(content="두 번째", meeting_date=date(2026, 10, 2)),
                item(content="세 번째", meeting_date=date(2026, 10, 1)),
            ],
            KIM,
        )

        assert [m.content.value for m in saved] == ["첫 번째", "두 번째", "세 번째"]
        assert meeting_env.uow.commits == 1
        stored = await meeting_env.everything()
        assert {m.id for m in stored} == {m.id for m in saved}

    async def test_a_partner_company_without_any_linked_deal_is_registered(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)  # Deal은 하나도 없다

        (meeting,) = await meeting_env.register.execute([item()], KIM)

        assert meeting.partner_company == HANBIT
        assert (await meeting_env.stored(meeting.id)).partner_company == HANBIT

    async def test_the_saved_meeting_carries_author_company_date_content_and_times(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)
        meeting_env.clock.advance(60)

        (saved,) = await meeting_env.register.execute(
            [item(meeting_date=date(2026, 11, 5), content=" 계약 논의\n내용 ")], KIM
        )

        meeting = await meeting_env.stored(saved.id)
        assert meeting.author_user_id == KIM.user_id
        assert meeting.partner_company == HANBIT
        assert meeting.meeting_date == date(2026, 11, 5)
        assert meeting.content.value == "계약 논의\n내용"
        assert meeting.created_at == meeting.updated_at == meeting_env.clock.now()

    async def test_ids_come_from_the_allocator_one_per_item(self, meeting_env: MeetingEnv) -> None:
        await meeting_env.partner(HANBIT)

        saved = await meeting_env.register.execute([item(), item()], KIM)

        assert [m.id for m in saved] == [1, 2]

    async def test_a_future_date_is_allowed(self, meeting_env: MeetingEnv) -> None:
        await meeting_env.partner(HANBIT)

        (meeting,) = await meeting_env.register.execute(
            [item(meeting_date=date(2999, 12, 31))], KIM
        )

        assert meeting.meeting_date == date(2999, 12, 31)

    async def test_the_same_company_and_date_may_be_recorded_twice(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)

        await meeting_env.register.execute([item(), item()], KIM)

        assert len(await meeting_env.everything()) == 2

    async def test_company_case_is_stored_in_the_registered_spelling(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner("HanbitPartners")

        (meeting,) = await meeting_env.register.execute([item(company="hanbitPARTNERS")], KIM)

        assert meeting.partner_company == "HanbitPartners"
        assert (await meeting_env.stored(meeting.id)).partner_company == "HanbitPartners"

    async def test_any_contact_of_the_company_makes_it_a_registered_partner_company(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT, "이영희")
        await meeting_env.partner(HANBIT, "박민수")

        (meeting,) = await meeting_env.register.execute([item(company=HANBIT)], KIM)

        assert meeting.partner_company == HANBIT


class TestRejections:
    async def test_empty_items_are_rejected(self, meeting_env: MeetingEnv) -> None:
        with raises_with(InvalidValueError, NO_ITEMS):
            await meeting_env.register.execute([], KIM)

        assert meeting_env.uow.commits == 0

    async def test_unknown_company_rejects_the_whole_batch_with_its_location(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(), item(company="없는회사"), item()], KIM)

        assert _found(raised.value) == [(("items", 1, "partner_company"), COMPANY_NOT_FOUND)]
        assert meeting_env.uow.commits == 0
        assert await meeting_env.everything() == []

    async def test_violations_of_several_rows_are_all_reported(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute(
                [
                    item(),
                    item(company="없는회사"),
                    item(content="  "),
                    item(meeting_date=date(3000, 1, 1)),
                ],
                KIM,
            )

        assert _found(raised.value) == [
            (("items", 1, "partner_company"), COMPANY_NOT_FOUND),
            (("items", 2, "content"), CONTENT_REQUIRED),
            (("items", 3, "meeting_date"), OUT_OF_BOUNDS),
        ]
        assert await meeting_env.everything() == []

    async def test_no_violation_is_ever_located_at_a_deal_code(
        self, meeting_env: MeetingEnv
    ) -> None:
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute(
                [item(company="없는회사", meeting_date=date(1899, 12, 31), content="")], KIM
            )

        assert [location for location, _ in _found(raised.value)] == [
            ("items", 0, "partner_company"),
            ("items", 0, "meeting_date"),
            ("items", 0, "content"),
        ]

    async def test_a_company_that_lost_all_its_partner_contacts_is_rejected(
        self, meeting_env: MeetingEnv
    ) -> None:
        contact = await meeting_env.partner(HANBIT)
        await meeting_env.drop_partner(contact)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item()], KIM)

        assert _found(raised.value) == [(("items", 0, "partner_company"), COMPANY_NOT_FOUND)]

    @pytest.mark.parametrize("bad", [date(1899, 12, 31), date(3000, 1, 1)])
    async def test_a_date_outside_the_bounds_is_reported_at_the_date_location(
        self, meeting_env: MeetingEnv, bad: date
    ) -> None:
        await meeting_env.partner(HANBIT)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(), item(meeting_date=bad)], KIM)

        assert _found(raised.value) == [(("items", 1, "meeting_date"), OUT_OF_BOUNDS)]

    async def test_nul_in_the_content_is_reported_at_the_content_location(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(content="a\x00b")], KIM)

        assert [location for location, _ in _found(raised.value)] == [("items", 0, "content")]
        assert "NUL" in _found(raised.value)[0][1]
