"""RegisterPartnerMeetings(AC11·12·17·18, P2·P8): 일괄 입력의 연결 검사, 원자성, 위치별 위반."""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
    DEAL_NOT_FOUND,
    DEAL_NOT_LINKED,
    NO_ITEMS,
    MeetingInputError,
)

from app.domain.common.errors import InvalidValueError
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
        first = await meeting_env.deal(name="ERP")
        second = await meeting_env.deal(name="MES", company=HANBIT)
        meeting_env.clock.advance(60)

        records = await meeting_env.register.execute(
            [
                item(first, content="첫 번째", meeting_date=date(2026, 10, 3)),
                item(second, content="두 번째", meeting_date=date(2026, 10, 2)),
                item(first, content="세 번째", meeting_date=date(2026, 10, 1)),
            ],
            KIM,
        )

        assert [r.meeting.content.value for r in records] == ["첫 번째", "두 번째", "세 번째"]
        assert [r.deal_name for r in records] == ["ERP", "MES", "ERP"]
        assert meeting_env.uow.commits == 1
        stored = await meeting_env.everything()
        assert {r.meeting.id for r in stored} == {r.meeting.id for r in records}

    async def test_the_saved_meeting_carries_author_company_deal_date_and_times(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal()
        meeting_env.clock.advance(60)

        (record,) = await meeting_env.register.execute(
            [item(code, meeting_date=date(2026, 11, 5), content=" 계약 논의\n내용 ")], KIM
        )

        meeting = (await meeting_env.stored(record.meeting.id)).meeting
        assert meeting.author_user_id == KIM.user_id
        assert meeting.subject.partner_company == HANBIT
        assert meeting.subject.deal_code == code
        assert meeting.meeting_date == date(2026, 11, 5)
        assert meeting.content.value == "계약 논의\n내용"
        assert meeting.created_at == meeting.updated_at == meeting_env.clock.now()

    async def test_ids_come_from_the_allocator_one_per_item(self, meeting_env: MeetingEnv) -> None:
        code = await meeting_env.deal()

        records = await meeting_env.register.execute([item(code), item(code)], KIM)

        assert [r.meeting.id for r in records] == [1, 2]

    async def test_a_future_date_is_allowed(self, meeting_env: MeetingEnv) -> None:
        code = await meeting_env.deal()

        (record,) = await meeting_env.register.execute(
            [item(code, meeting_date=date(2999, 12, 31))], KIM
        )

        assert record.meeting.meeting_date == date(2999, 12, 31)

    async def test_the_same_deal_and_date_may_be_recorded_twice(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal()

        await meeting_env.register.execute([item(code), item(code)], KIM)

        assert len(await meeting_env.everything()) == 2

    async def test_company_case_is_normalized_to_the_representative_spelling(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal(company="HanbitPartners")

        (record,) = await meeting_env.register.execute([item(code, company="hanbitPARTNERS")], KIM)

        assert record.meeting.subject.partner_company == "HanbitPartners"
        stored = await meeting_env.stored(record.meeting.id)
        assert stored.meeting.subject.partner_company == "HanbitPartners"

    async def test_a_deal_linked_through_another_contact_of_the_same_company_is_accepted(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT, "이영희")
        other = await meeting_env.partner(HANBIT, "박민수")
        code = await meeting_env.deal(partner=other)

        (record,) = await meeting_env.register.execute([item(code, company=HANBIT)], KIM)

        assert record.meeting.subject.deal_code == code

    @pytest.mark.parametrize(
        ("forecast_key", "status_key"),
        [("won", "contract_completed"), ("lost", "prospecting"), ("commit", "price_negotiation")],
    )
    async def test_won_and_lost_deals_are_accepted_like_open_ones(
        self, meeting_env: MeetingEnv, forecast_key: str, status_key: str
    ) -> None:
        code = await meeting_env.deal(forecast_key=forecast_key, status_key=status_key)

        (record,) = await meeting_env.register.execute([item(code)], KIM)

        assert record.meeting.subject.deal_code == code


class TestRejections:
    async def test_empty_items_are_rejected(self, meeting_env: MeetingEnv) -> None:
        with raises_with(InvalidValueError, NO_ITEMS):
            await meeting_env.register.execute([], KIM)

        assert meeting_env.uow.commits == 0

    async def test_any_invalid_item_saves_nothing_and_reports_all_locations(
        self, meeting_env: MeetingEnv
    ) -> None:
        good = await meeting_env.deal()
        other_company_deal = await meeting_env.deal(company="다른파트너")

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute(
                [
                    item(good),
                    item(good, company="없는회사"),
                    item(other_company_deal, company=HANBIT, content="  "),
                    item(good),
                ],
                KIM,
            )

        assert _found(raised.value) == [
            (("items", 1, "partner_company"), COMPANY_NOT_FOUND),
            (("items", 2, "deal_code"), DEAL_NOT_LINKED),
            (("items", 2, "content"), CONTENT_REQUIRED),
        ]
        assert meeting_env.uow.commits == 0
        assert await meeting_env.everything() == []

    async def test_a_row_reports_company_deal_date_and_content_in_that_order(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.partner(HANBIT)
        other = await meeting_env.deal(company="다른파트너")

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute(
                [item(other, company=HANBIT, meeting_date=date(1899, 12, 31), content="")], KIM
            )

        assert [location for location, _ in _found(raised.value)] == [
            ("items", 0, "deal_code"),
            ("items", 0, "meeting_date"),
            ("items", 0, "content"),
        ]
        assert _found(raised.value)[1][1] == OUT_OF_BOUNDS

    async def test_an_unknown_company_skips_the_deal_check_for_that_row(
        self, meeting_env: MeetingEnv
    ) -> None:
        await meeting_env.deal()

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item("20261016-ZZZZ", company="없는회사")], KIM)

        assert _found(raised.value) == [(("items", 0, "partner_company"), COMPANY_NOT_FOUND)]

    async def test_an_unknown_company_row_still_checks_date_and_content(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal()

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code, company="없는회사", content="  ")], KIM)

        assert [location for location, _ in _found(raised.value)] == [
            ("items", 0, "partner_company"),
            ("items", 0, "content"),
        ]

    @pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code", "", "20261016-zzzz"])
    async def test_a_missing_deal_and_a_malformed_code_report_the_same_not_found_message(
        self, meeting_env: MeetingEnv, code: str
    ) -> None:
        await meeting_env.deal()

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code)], KIM)

        assert _found(raised.value) == [(("items", 0, "deal_code"), DEAL_NOT_FOUND)]

    async def test_a_deal_of_another_company_is_not_linked(self, meeting_env: MeetingEnv) -> None:
        await meeting_env.partner(HANBIT)
        other = await meeting_env.deal(company="다른파트너")

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(other, company=HANBIT)], KIM)

        assert _found(raised.value) == [(("items", 0, "deal_code"), DEAL_NOT_LINKED)]

    async def test_a_deal_without_any_partner_is_not_linked(self, meeting_env: MeetingEnv) -> None:
        await meeting_env.partner(HANBIT)
        code = await meeting_env.deal(company=None)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code)], KIM)

        assert _found(raised.value) == [(("items", 0, "deal_code"), DEAL_NOT_LINKED)]

    async def test_a_partner_that_was_unlinked_from_the_deal_is_rejected(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal()
        await meeting_env.unlink_partner(code)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code)], KIM)

        assert _found(raised.value) == [(("items", 0, "deal_code"), DEAL_NOT_LINKED)]

    async def test_a_past_partner_is_rejected_after_the_deal_switched_to_another_company(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal(company=HANBIT)
        replacement = await meeting_env.partner("새파트너")
        await meeting_env.relink_partner(code, replacement)

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code, company=HANBIT)], KIM)
        (record,) = await meeting_env.register.execute([item(code, company="새파트너")], KIM)

        assert _found(raised.value) == [(("items", 0, "deal_code"), DEAL_NOT_LINKED)]
        assert record.meeting.subject.partner_company == "새파트너"

    @pytest.mark.parametrize("bad", [date(1899, 12, 31), date(3000, 1, 1)])
    async def test_a_date_outside_the_bounds_is_reported_at_the_date_location(
        self, meeting_env: MeetingEnv, bad: date
    ) -> None:
        code = await meeting_env.deal()

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code), item(code, meeting_date=bad)], KIM)

        assert _found(raised.value) == [(("items", 1, "meeting_date"), OUT_OF_BOUNDS)]

    async def test_nul_in_the_content_is_reported_at_the_content_location(
        self, meeting_env: MeetingEnv
    ) -> None:
        code = await meeting_env.deal()

        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(code, content="a\x00b")], KIM)

        assert [location for location, _ in _found(raised.value)] == [("items", 0, "content")]
        assert "NUL" in _found(raised.value)[0][1]
