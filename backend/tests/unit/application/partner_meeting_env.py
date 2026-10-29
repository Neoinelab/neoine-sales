"""파트너 Activity 유스케이스 단위 테스트의 공용 환경: Fake UoW 위의 유스케이스 묶음과 준비 도우미.

이 모듈은 구현을 모듈 수준에서 가져온다. 그래서 `conftest.py`의 `meeting_env` fixture가 사용
시점에 가져온다(구현이 없어도 다른 테스트의 수집이 막히지 않는다). Deal·연락처는 Fake 저장소에
직접 둔다(RegisterDeal의 다른 규칙과 섞이지 않게). 준비용 commit은 커밋 횟수 단언에 섞이지
않도록 0으로 되돌린다.
"""

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from app.application.deal.inputs import Actor
from app.application.partner_meeting.delete_partner_meeting import DeletePartnerMeeting
from app.application.partner_meeting.inputs import MeetingInput
from app.application.partner_meeting.list_partner_deal_choices import ListPartnerDealChoices
from app.application.partner_meeting.list_partner_meetings import ListPartnerMeetings
from app.application.partner_meeting.register_partner_meetings import RegisterPartnerMeetings
from app.application.partner_meeting.update_partner_meeting import UpdatePartnerMeeting
from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
from app.domain.auth.principal import Role
from tests.factories import make_deal, make_deal_code
from tests.factories_contact import make_customer, make_partner
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    import builtins

    from app.application.ports.partner_meeting_repository import PartnerMeetingRecord
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.contact.entities import Contact
    from app.domain.deal.code import DealCode
    from app.domain.partner_meeting.values import PartnerMeetingId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

KIM = Actor(user_id=uid("mt-kim"), role=Role.SALES)
PARK = Actor(user_id=uid("mt-park"), role=Role.SALES)
BOSS = Actor(user_id=uid("mt-boss"), role=Role.ADMIN)
VIEWER = Actor(user_id=uid("mt-viewer"), role=Role.USER)
HANBIT = "한빛파트너스"
EDIT_FORBIDDEN = "본인 미팅 기록 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN = "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."
NOT_FOUND = "미팅 기록을 찾을 수 없습니다."
DAY = date(2026, 10, 1)


def item(
    deal_code: DealCode | str,
    *,
    company: str = HANBIT,
    meeting_date: date = DAY,
    content: str = "킥오프 미팅",
) -> MeetingInput:
    code = deal_code if isinstance(deal_code, str) else deal_code.value
    return MeetingInput(
        partner_company=company, deal_code=code, meeting_date=meeting_date, content=content
    )


@dataclass
class MeetingEnv:
    uow: FakeUnitOfWork
    uow_factory: UnitOfWorkFactory
    clock: FixedClock
    register: RegisterPartnerMeetings
    update: UpdatePartnerMeeting
    delete: DeletePartnerMeeting
    list: ListPartnerMeetings
    choices: ListPartnerDealChoices
    _deals: int = 0
    _contacts: int = 0

    async def partner(self, company: str = HANBIT, name: str | None = None) -> Contact:
        """파트너 연락처 한 명(같은 회사의 담당자는 이름으로 구분한다)."""
        self._contacts += 1
        person = name or f"담당자{self._contacts}"
        contact = make_partner(
            company=company, name=person, email=f"p{self._contacts}@partner.test"
        )
        await self.uow.contacts.add(contact)
        return contact

    async def deal(  # noqa: PLR0913 - Deal 준비에 필요한 독립적인 선택지
        self,
        *,
        name: str = "ERP 구축",
        partner: Contact | None = None,
        company: str | None = HANBIT,
        forecast_key: str = "pipeline",
        status_key: str = "prospecting",
        customer_company: str = "네오인",
    ) -> DealCode:
        """Deal 한 건. partner를 주면 그 연락처가 활성 파트너이고, 생략하면 company의 새 담당자가
        파트너다(company=None이면 파트너 없는 Deal)."""
        self._deals += 1
        code = make_deal_code(f"D{self._deals:03d}")
        customer = make_customer(
            company=customer_company, name=f"고객{self._deals}", email=f"c{self._deals}@c.test"
        )
        await self.uow.contacts.add(customer)
        linked = partner
        if linked is None and company is not None:
            linked = await self.partner(company)
        await self.uow.deals.add(
            make_deal(
                code=code,
                name=name,
                customer_id=customer.id,
                partner_id=None if linked is None else linked.id,
                forecast_key=forecast_key,
                status_key=status_key,
            )
        )
        return code

    async def unlink_partner(self, code: DealCode) -> None:
        """Deal의 활성 파트너를 해제한다(링크는 해제 시각과 함께 남는다)."""
        deal = await self.uow.deals.get(code)
        deal.replace_partner(None, self.clock.now())
        await self.uow.deals.update(deal)

    async def relink_partner(self, code: DealCode, contact: Contact) -> None:
        deal = await self.uow.deals.get(code)
        deal.replace_partner(contact.id, self.clock.now())
        await self.uow.deals.update(deal)

    async def register_one(
        self,
        actor: Actor,
        code: DealCode,
        **fields: Any,  # noqa: ANN401 - 입력 필드(회사·날짜·내용)를 그대로 넘긴다
    ) -> PartnerMeetingRecord:
        """미팅 한 건을 등록한다(시계가 60초 흐른 뒤라 등록 시각이 서로 다르다)."""
        self.clock.advance(60)
        (record,) = await self.register.execute([item(code, **fields)], actor)
        return record

    async def stored(self, meeting_id: PartnerMeetingId) -> PartnerMeetingRecord:
        async with self.uow_factory() as active:
            return await active.partner_meetings.get(meeting_id)

    async def everything(self, **criteria: Any) -> builtins.list[PartnerMeetingRecord]:  # noqa: ANN401
        """저장된 미팅 전부(기본 정렬, 한 페이지에 200건까지)."""
        async with self.uow_factory() as active:
            return list(
                await active.partner_meetings.search(PartnerMeetingQuery(limit=200, **criteria))
            )


async def build_meeting_env(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> MeetingEnv:
    async with uow_factory() as active:
        await ensure_users(active.users, KIM.user_id, PARK.user_id, BOSS.user_id, VIEWER.user_id)
        await active.commit()
    uow.commits = 0
    return MeetingEnv(
        uow=uow,
        uow_factory=uow_factory,
        clock=clock,
        register=RegisterPartnerMeetings(uow_factory, clock),
        update=UpdatePartnerMeeting(uow_factory, clock),
        delete=DeletePartnerMeeting(uow_factory),
        list=ListPartnerMeetings(uow_factory),
        choices=ListPartnerDealChoices(uow_factory),
    )
