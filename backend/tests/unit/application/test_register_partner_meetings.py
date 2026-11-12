"""RegisterPartnerMeetings: 파트너 회사 검증, 원자성, 위치별 위반(Deal은 무관)."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.partner_meeting.errors import COMPANY_NOT_FOUND, NO_ITEMS, MeetingInputError
from tests.support.expect import raises_with
from tests.unit.application.partner_meeting_env import BOSS, HANBIT, KIM, item

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
        """여러 건을 한 번에 등록하면 입력 순서대로 한 번의 커밋으로 저장된다.

        테스트 코드: PA-001
        """
        # given: 파트너 연락처가 있고 시계가 흐른 상태
        await meeting_env.partner(HANBIT)
        meeting_env.clock.advance(60)
        # when: KIM이 세 건을 등록한다
        saved = await meeting_env.register.execute(
            [
                item(content="첫 번째", meeting_date=date(2026, 10, 3)),
                item(content="두 번째", meeting_date=date(2026, 10, 2)),
                item(content="세 번째", meeting_date=date(2026, 10, 1)),
            ],
            KIM,
        )
        # then: 입력 순서대로 돌려주고 한 번 커밋했으며 저장소에도 세 건이 있다
        assert [m.content.value for m in saved] == ["첫 번째", "두 번째", "세 번째"]
        assert meeting_env.uow.commits == 1
        stored = await meeting_env.everything()
        assert {m.id for m in stored} == {m.id for m in saved}

    async def test_the_saved_meeting_carries_author_company_date_content_and_times(
        self, meeting_env: MeetingEnv
    ) -> None:
        """저장된 기록은 작성자·회사·날짜·정리된 내용과 같은 두 시각을 갖는다.

        테스트 코드: PA-002
        """
        # given: 파트너 연락처가 있고 시계가 흐른 상태
        await meeting_env.partner(HANBIT)
        meeting_env.clock.advance(60)
        # when: KIM이 내용 앞뒤에 공백이 있는 한 건을 등록한다
        (saved,) = await meeting_env.register.execute(
            [item(meeting_date=date(2026, 11, 5), content=" 계약 논의\n내용 ")], KIM
        )
        # then: 저장된 기록의 작성자는 KIM이고 두 시각은 지금이다
        meeting = await meeting_env.stored(saved.id)
        assert meeting.author_user_id == KIM.user_id
        assert meeting.partner_company == HANBIT
        assert meeting.meeting_date == date(2026, 11, 5)
        assert meeting.content.value == "계약 논의\n내용"
        assert meeting.created_at == meeting.updated_at == meeting_env.clock.now()

    async def test_ids_come_from_the_allocator_one_per_item(self, meeting_env: MeetingEnv) -> None:
        """id는 할당기에서 항목마다 하나씩 받는다.

        테스트 코드: PA-002
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when: 두 건을 등록한다
        saved = await meeting_env.register.execute([item(), item()], KIM)
        # then: id는 1, 2다
        assert [m.id for m in saved] == [1, 2]

    async def test_admin_registers_and_the_content_edges_are_trimmed(
        self, meeting_env: MeetingEnv
    ) -> None:
        """admin도 등록하고 내용의 앞뒤 공백은 지워지며 가운데 줄바꿈은 남는다.

        테스트 코드: PA-003
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when: admin이 앞뒤에 줄바꿈·공백이 붙은 내용으로 등록한다
        (saved,) = await meeting_env.register.execute(
            [item(content="\n 계약 논의\n다음 주 방문 \n")], BOSS
        )
        # then: 저장된 내용은 앞뒤만 정리되고 작성자는 admin이다
        meeting = await meeting_env.stored(saved.id)
        assert meeting.content.value == "계약 논의\n다음 주 방문"
        assert meeting.author_user_id == BOSS.user_id

    async def test_company_case_is_stored_in_the_registered_spelling(
        self, meeting_env: MeetingEnv
    ) -> None:
        """대소문자가 다른 회사명은 등록된 대표 표기로 저장된다.

        테스트 코드: PA-004
        """
        # given: 연락처 회사 "HanbitPartners"
        await meeting_env.partner("HanbitPartners")
        # when: 회사를 "hanbitPARTNERS"로 등록한다
        (meeting,) = await meeting_env.register.execute([item(company="hanbitPARTNERS")], KIM)
        # then: 응답과 저장된 회사명은 "HanbitPartners"다
        assert meeting.partner_company == "HanbitPartners"
        assert (await meeting_env.stored(meeting.id)).partner_company == "HanbitPartners"

    async def test_a_partner_company_without_any_linked_deal_is_registered(
        self, meeting_env: MeetingEnv
    ) -> None:
        """어느 Deal에도 연결되지 않은 파트너 회사도 연락처가 있으면 등록된다.

        테스트 코드: PA-005
        """
        # given: Deal은 하나도 없고 파트너 연락처만 있다
        await meeting_env.partner(HANBIT)
        # when: 그 회사로 등록한다
        (meeting,) = await meeting_env.register.execute([item()], KIM)
        # then: 회사명이 저장된다
        assert meeting.partner_company == HANBIT
        assert (await meeting_env.stored(meeting.id)).partner_company == HANBIT

    async def test_any_contact_of_the_company_makes_it_a_registered_partner_company(
        self, meeting_env: MeetingEnv
    ) -> None:
        """같은 회사의 연락처가 둘 이상이어도 그 회사로 등록된다.

        테스트 코드: PA-005
        """
        # given: 같은 회사의 파트너 연락처 두 명
        await meeting_env.partner(HANBIT, "이영희")
        await meeting_env.partner(HANBIT, "박민수")
        # when: 그 회사로 등록한다
        (meeting,) = await meeting_env.register.execute([item(company=HANBIT)], KIM)
        # then: 회사명이 저장된다
        assert meeting.partner_company == HANBIT

    async def test_boundary_dates_are_allowed_and_duplicates_are_stored(
        self, meeting_env: MeetingEnv
    ) -> None:
        """미래·양끝 미팅 날짜를 받고 같은 회사·날짜·내용의 중복도 저장된다.

        테스트 코드: PA-006
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when: 2999-12-31, 1900-01-01과 같은 회사·날짜·내용 두 건을 등록한다
        saved = await meeting_env.register.execute(
            [
                item(meeting_date=date(2999, 12, 31)),
                item(meeting_date=date(1900, 1, 1)),
                item(),
                item(),
            ],
            KIM,
        )
        # then: 날짜가 그대로이고 같은 내용의 기록이 두 건 있다
        assert [m.meeting_date for m in saved][:2] == [date(2999, 12, 31), date(1900, 1, 1)]
        stored = await meeting_env.everything()
        assert len(stored) == 4
        assert sum(1 for m in stored if m.meeting_date == date(2026, 10, 1)) == 2


class TestRejections:
    async def test_empty_items_are_rejected(self, meeting_env: MeetingEnv) -> None:
        """유스케이스는 빈 목록을 거절한다(HTTP에서는 닿지 않는 내부 방어)."""
        # when·then: 빈 목록을 등록하면 "입력한 미팅이 없습니다." 오류다
        with raises_with(InvalidValueError, NO_ITEMS):
            await meeting_env.register.execute([], KIM)
        # then: 커밋하지 않는다
        assert meeting_env.uow.commits == 0

    async def test_unknown_company_rejects_the_whole_batch_with_its_location(
        self, meeting_env: MeetingEnv
    ) -> None:
        """등록되지 않은 회사가 한 행이면 전체를 저장하지 않고 그 행의 위치를 알려 준다.

        테스트 코드: PA-008
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when·then: 가운데 행이 없는 회사이면 그 행의 partner_company 위치로 거절된다
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(), item(company="없는회사"), item()], KIM)
        assert _found(raised.value) == [(("items", 1, "partner_company"), COMPANY_NOT_FOUND)]
        # then: 정상 행도 저장되지 않았다
        assert meeting_env.uow.commits == 0
        assert await meeting_env.everything() == []

    async def test_violations_of_several_rows_are_all_reported(
        self, meeting_env: MeetingEnv
    ) -> None:
        """여러 행이 틀리면 아무것도 저장하지 않고 모든 위반을 행·칸 위치와 함께 모은다.

        테스트 코드: PA-008
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when·then: 정상 행, 없는 회사, 빈 내용, 범위 밖 날짜를 등록하면 위반 셋이 순서대로 모인다
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
        # then: 정상 행을 포함해 저장된 기록이 없다
        assert await meeting_env.everything() == []

    async def test_no_violation_is_ever_located_at_a_deal_code(
        self, meeting_env: MeetingEnv
    ) -> None:
        """한 행의 위반 셋도 회사·날짜·내용 위치뿐이고 deal_code 위치는 없다.

        테스트 코드: PA-008
        """
        # when·then: 회사·날짜·내용이 모두 틀린 한 행을 등록한다
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute(
                [item(company="없는회사", meeting_date=date(1899, 12, 31), content="")], KIM
            )
        # then: 위치는 세 칸뿐이다
        assert [location for location, _ in _found(raised.value)] == [
            ("items", 0, "partner_company"),
            ("items", 0, "meeting_date"),
            ("items", 0, "content"),
        ]

    async def test_a_company_that_lost_all_its_partner_contacts_is_rejected(
        self, meeting_env: MeetingEnv
    ) -> None:
        """파트너 연락처가 모두 지워진 회사는 등록되지 않는다.

        테스트 코드: PA-009
        """
        # given: 연락처 하나를 등록했다가 지운 회사
        contact = await meeting_env.partner(HANBIT)
        await meeting_env.drop_partner(contact)
        # when·then: 그 회사로 등록하면 partner_company 위치로 거절된다
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item()], KIM)
        assert _found(raised.value) == [(("items", 0, "partner_company"), COMPANY_NOT_FOUND)]
        # then: 저장되지 않았다
        assert await meeting_env.everything() == []

    @pytest.mark.parametrize("bad", [date(1899, 12, 31), date(3000, 1, 1)])
    async def test_a_date_outside_the_bounds_is_reported_at_the_date_location(
        self, meeting_env: MeetingEnv, bad: date
    ) -> None:
        """범위 밖 미팅 날짜는 날짜 위치로 거절된다.

        테스트 코드: PA-010
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when·then: 두 번째 행의 날짜가 범위 밖이면 그 행의 meeting_date 위치다
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(), item(meeting_date=bad)], KIM)
        assert _found(raised.value) == [(("items", 1, "meeting_date"), OUT_OF_BOUNDS)]
        # then: 저장되지 않았다
        assert await meeting_env.everything() == []

    async def test_nul_in_the_content_is_reported_at_the_content_location(
        self, meeting_env: MeetingEnv
    ) -> None:
        """NUL이 든 내용은 내용 위치로 거절된다.

        테스트 코드: PA-010
        """
        # given: 파트너 연락처가 있다
        await meeting_env.partner(HANBIT)
        # when·then: 내용에 NUL이 있으면 content 위치로 거절된다
        with pytest.raises(MeetingInputError) as raised:
            await meeting_env.register.execute([item(content="a\x00b")], KIM)
        assert [location for location, _ in _found(raised.value)] == [("items", 0, "content")]
        assert "NUL" in _found(raised.value)[0][1]
        # then: 저장되지 않았다
        assert await meeting_env.everything() == []
