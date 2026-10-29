from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactKind
from app.domain.deal.code import DealCode
from app.domain.partner_meeting.errors import COMPANY_NOT_FOUND, MeetingInputError, MeetingIssue
from app.domain.partner_meeting.links import LinkedDeals, deal_link_problem, resolve_company
from app.domain.partner_meeting.values import MeetingContent, MeetingSubject, check_meeting_date

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import date

    from app.application.partner_meeting.inputs import MeetingInput
    from app.application.ports.partner_meeting_repository import (
        PartnerDealChoice,
        PartnerMeetingRecord,
    )
    from app.application.ports.unit_of_work import UnitOfWork

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class CheckedMeeting:
    subject: MeetingSubject
    meeting_date: date
    content: MeetingContent
    deal_name: str


class MeetingChecker:
    """미팅 입력을 검증한다. 위반은 모두 모아 위치와 함께 MeetingInputError로 알린다.

    한 행의 검사 순서는 회사 -> Deal -> 날짜 -> 내용이고, 회사가 틀리면 그 행의 Deal 검사만
    건너뛴다. 회사 목록은 한 번, 회사별 Deal 선택지는 대표 표기마다 한 번만 읽는다.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._companies: Sequence[str] | None = None
        self._choices: dict[str, Sequence[PartnerDealChoice]] = {}

    async def check_all(self, items: Sequence[MeetingInput]) -> list[CheckedMeeting]:
        issues: list[MeetingIssue] = []
        checked: list[CheckedMeeting] = []
        for index, data in enumerate(items):
            row = await self._check(data, ("items", index), issues, link=None)
            if row is not None:
                checked.append(row)
        if issues:
            raise MeetingInputError(tuple(issues))
        return checked

    async def check_update(
        self, data: MeetingInput, current: PartnerMeetingRecord, *, link: bool
    ) -> CheckedMeeting:
        """수정 입력 검증. link=False면 회사·Deal은 현재 값을 유지하고 날짜·내용만 본다."""
        issues: list[MeetingIssue] = []
        row = await self._check(data, (), issues, link=None if link else current)
        if row is None:
            raise MeetingInputError(tuple(issues))
        return row

    async def _check(
        self,
        data: MeetingInput,
        prefix: Location,
        issues: list[MeetingIssue],
        *,
        link: PartnerMeetingRecord | None,
    ) -> CheckedMeeting | None:
        """link가 있으면 그 기록의 회사·Deal을 유지하고, 없으면 연결을 검사한다."""
        before = len(issues)
        found = (
            (link.meeting.subject, link.deal_name)
            if link is not None
            else await self._check_link(data, prefix, issues)
        )
        day = _guard(
            lambda: check_meeting_date(data.meeting_date), (*prefix, "meeting_date"), issues
        )
        content = _guard(lambda: MeetingContent(data.content), (*prefix, "content"), issues)
        if len(issues) > before or found is None or day is None or content is None:
            return None
        return CheckedMeeting(found[0], day, content, found[1])

    async def _check_link(
        self, data: MeetingInput, prefix: Location, issues: list[MeetingIssue]
    ) -> tuple[MeetingSubject, str] | None:
        company = resolve_company(data.partner_company, await self._company_names())
        if company is None:
            issues.append(MeetingIssue((*prefix, "partner_company"), COMPANY_NOT_FOUND))
            return None
        code = DealCode.parse_or_none(data.deal_code)
        choices = await self._choices_of(company)
        chosen = next((c for c in choices if c.code == code), None)
        if code is not None and chosen is not None:
            return MeetingSubject(company, code), chosen.name
        linked = LinkedDeals(company, frozenset(c.code for c in choices))
        problem = deal_link_problem(
            code, deal_exists=code is not None and await self._deal_exists(code), linked=linked
        )
        if problem is not None:
            issues.append(MeetingIssue((*prefix, "deal_code"), problem))
        return None

    async def _company_names(self) -> Sequence[str]:
        if self._companies is None:
            self._companies = await self._uow.contacts.companies(ContactKind.PARTNER)
        return self._companies

    async def _choices_of(self, company: str) -> Sequence[PartnerDealChoice]:
        if company not in self._choices:
            self._choices[company] = await self._uow.partner_meetings.deal_choices(company)
        return self._choices[company]

    async def _deal_exists(self, code: DealCode) -> bool:
        return await self._uow.deals.exists(code)


def _guard[T](check: Callable[[], T], location: Location, issues: list[MeetingIssue]) -> T | None:
    try:
        return check()
    except InvalidValueError as error:
        issues.append(MeetingIssue(location, str(error)))
        return None
