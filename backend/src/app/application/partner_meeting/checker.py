from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactKind
from app.domain.partner_meeting.company import resolve_company
from app.domain.partner_meeting.errors import COMPANY_NOT_FOUND, MeetingInputError, MeetingIssue
from app.domain.partner_meeting.values import MeetingContent, check_meeting_date

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from datetime import date

    from app.application.partner_meeting.inputs import MeetingInput
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.partner_meeting.entities import PartnerMeeting

type Location = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class CheckedMeeting:
    partner_company: str
    meeting_date: date
    content: MeetingContent


class MeetingChecker:
    """미팅 입력을 검증한다. 위반은 모두 모아 위치와 함께 MeetingInputError로 알린다.

    한 행의 검사 순서는 회사 -> 날짜 -> 내용이고, 회사 목록은 요청당 한 번만 읽는다.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._companies: Sequence[str] | None = None

    async def check_all(self, items: Sequence[MeetingInput]) -> list[CheckedMeeting]:
        issues: list[MeetingIssue] = []
        checked: list[CheckedMeeting] = []
        for index, data in enumerate(items):
            row = await self._check(data, ("items", index), issues, company=None)
            if row is not None:
                checked.append(row)
        if issues:
            raise MeetingInputError(tuple(issues))
        return checked

    async def check_update(
        self, data: MeetingInput, current: PartnerMeeting, *, recheck_company: bool
    ) -> CheckedMeeting:
        """수정 입력 검증. recheck_company=False면 회사는 저장값을 유지하고 날짜·내용만 본다."""
        issues: list[MeetingIssue] = []
        kept = None if recheck_company else current.partner_company
        row = await self._check(data, (), issues, company=kept)
        if row is None:
            raise MeetingInputError(tuple(issues))
        return row

    async def _check(
        self,
        data: MeetingInput,
        prefix: Location,
        issues: list[MeetingIssue],
        *,
        company: str | None,
    ) -> CheckedMeeting | None:
        """company가 있으면 그 표기를 유지하고, 없으면 회사 목록으로 확인한다."""
        before = len(issues)
        found = company if company is not None else await self._check_company(data, prefix, issues)
        day = _guard(
            lambda: check_meeting_date(data.meeting_date), (*prefix, "meeting_date"), issues
        )
        content = _guard(lambda: MeetingContent(data.content), (*prefix, "content"), issues)
        if len(issues) > before or found is None or day is None or content is None:
            return None
        return CheckedMeeting(found, day, content)

    async def _check_company(
        self, data: MeetingInput, prefix: Location, issues: list[MeetingIssue]
    ) -> str | None:
        company = resolve_company(data.partner_company, await self._company_names())
        if company is None:
            issues.append(MeetingIssue((*prefix, "partner_company"), COMPANY_NOT_FOUND))
        return company

    async def _company_names(self) -> Sequence[str]:
        if self._companies is None:
            self._companies = await self._uow.contacts.companies(ContactKind.PARTNER)
        return self._companies


def _guard[T](check: Callable[[], T], location: Location, issues: list[MeetingIssue]) -> T | None:
    try:
        return check()
    except InvalidValueError as error:
        issues.append(MeetingIssue(location, str(error)))
        return None
