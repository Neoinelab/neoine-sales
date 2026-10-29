"""PartnerMeetingRepository Port의 InMemory 구현(Fake). 파트너 Activity의 미팅 기록 저장소.

도메인·Port 모듈(app.domain.partner_meeting, app.application.ports.partner_meeting_repository)은
사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기 때문에, 모듈 수준 import는 미팅과
무관한 테스트의 수집까지 막는다(vendors.py와 같은 이유).

계약(SQL 구현과 같다)
- add: 같은 id AlreadyExistsError, Deal이 없으면 DealNotFoundError, 작성자 행이 없으면
  InvalidReferenceError("사용자")
- get: 없으면 PartnerMeetingNotFoundError. record.deal_name은 읽는 시점의 Deal 이름
- update: subject(회사 표기·Deal)·meeting_date·content·updated_at만 저장한다. 없으면 NotFound,
  새 Deal이 없으면 DealNotFoundError
- delete: 물리 삭제. 없으면 PartnerMeetingNotFoundError. Deal 삭제는 미팅을 함께 지운다(CASCADE)
- search/count: 조건은 AND. 텍스트는 대소문자 무시 부분 일치(`%`·`_`·`\\`는 글자 그대로)
  정렬: meeting_date는 (날짜, id)를 방향대로. partner·deal·content·author는 주 키 lower(...)를
  방향대로 -> 미팅 날짜 내림차순 -> id 내림차순(동률 규칙은 방향과 무관)
  author는 표시 이름(비어 있으면 login_id)이고 퇴사자도 포함한다. deal은 Deal의 현재 이름이다
- deal_choices: 활성 파트너 링크(unlinked_at 없음)의 연락처 회사명이 company와 대소문자 무시로
  같은 Deal 전부(Forecast 무관). lower(name) -> code 오름차순
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import ModuleType

    from app.application.ports.partner_meeting_repository import (
        PartnerDealChoice,
        PartnerMeetingQuery,
        PartnerMeetingRecord,
    )
    from app.domain.partner_meeting.entities import PartnerMeeting
    from app.domain.partner_meeting.values import PartnerMeetingId

    from app.domain.deal.code import DealCode


def _errors() -> ModuleType:
    from app.domain.partner_meeting import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _not_found(meeting_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().PartnerMeetingNotFoundError(meeting_id)


class FakePartnerMeetingRepository(InMemoryStore["PartnerMeeting"]):
    def __init__(self) -> None:
        super().__init__("partner_meeting", _not_found)
        self._deals: Any = None
        self._contacts: Any = None
        self._users: Any = None

    def wire(
        self,
        *,
        deals: Any,  # noqa: ANN401
        contacts: Any,  # noqa: ANN401
        users: Any,  # noqa: ANN401
    ) -> None:
        """Deal·사용자 존재 확인(FK 모사)과 Deal 이름·작성자 이름·연락처 회사명 읽기에 쓴다."""
        self._deals, self._contacts, self._users = deals, contacts, users

    # --- 파생 읽기 ---

    def _deal_name(self, code: DealCode) -> str:
        return str(self._deals._items[code].details.name)

    def _author_name(self, meeting: PartnerMeeting) -> str:
        user = self._users._items.get(meeting.author_user_id)
        if user is None:
            return str(meeting.author_user_id)
        return str(user.display_name or user.login_id.value)

    def _record(self, meeting: PartnerMeeting) -> PartnerMeetingRecord:
        from app.application.ports.partner_meeting_repository import (  # noqa: PLC0415
            PartnerMeetingRecord,
        )

        return PartnerMeetingRecord(
            meeting=copy.deepcopy(meeting), deal_name=self._deal_name(meeting.subject.deal_code)
        )

    def _ensure_references(self, meeting: PartnerMeeting) -> None:
        from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415
        from app.domain.deal.errors import DealNotFoundError  # noqa: PLC0415

        code = meeting.subject.deal_code
        if code not in self._deals._items:
            raise DealNotFoundError(code.value)
        if meeting.author_user_id not in self._users._items:
            raise InvalidReferenceError("사용자", meeting.author_user_id)

    # --- Deal 삭제 연동 ---

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE."""
        for meeting_id in [i for i, m in self._items.items() if m.subject.deal_code == code]:
            del self._items[meeting_id]

    def count_of_deal(self, code: DealCode) -> int:
        return sum(1 for m in self._items.values() if m.subject.deal_code == code)

    # --- 쓰기 ---

    async def add(self, meeting: PartnerMeeting) -> None:
        if meeting.id in self._items:
            self._insert(meeting)  # 같은 id는 AlreadyExistsError
        self._ensure_references(meeting)
        self._insert(meeting)

    async def update(self, meeting: PartnerMeeting) -> None:
        stored = self._fetch(meeting.id)  # 없으면 PartnerMeetingNotFoundError
        self._ensure_references_of_subject(meeting)
        stored.subject = meeting.subject
        stored.meeting_date = meeting.meeting_date
        stored.content = meeting.content
        stored.updated_at = meeting.updated_at
        self._replace(stored)

    def _ensure_references_of_subject(self, meeting: PartnerMeeting) -> None:
        from app.domain.deal.errors import DealNotFoundError  # noqa: PLC0415

        code = meeting.subject.deal_code
        if code not in self._deals._items:
            raise DealNotFoundError(code.value)

    async def delete(self, meeting_id: PartnerMeetingId) -> None:
        self._remove(meeting_id)

    # --- 읽기 ---

    async def get(
        self, meeting_id: PartnerMeetingId, *, for_update: bool = False
    ) -> PartnerMeetingRecord:
        return self._record(self._fetch(meeting_id))

    def _matches(self, meeting: PartnerMeeting, query: PartnerMeetingQuery) -> bool:
        subject = meeting.subject
        if query.partner and query.partner.lower() not in subject.partner_company.lower():
            return False
        if query.deal:
            needle = query.deal.lower()
            name = self._deal_name(subject.deal_code).lower()
            if needle not in name and needle not in subject.deal_code.value.lower():
                return False
        if query.content and query.content.lower() not in meeting.content.value.lower():
            return False
        if query.date_from is not None and meeting.meeting_date < query.date_from:
            return False
        if query.date_to is not None and meeting.meeting_date > query.date_to:
            return False
        return query.author_user_id is None or meeting.author_user_id == query.author_user_id

    def _sorted(
        self, found: list[PartnerMeeting], query: PartnerMeetingQuery
    ) -> list[PartnerMeeting]:
        descending = str(query.order) == "desc"
        sort = str(query.sort)
        if sort == "meeting_date":
            return sorted(found, key=lambda m: (m.meeting_date, m.id), reverse=descending)
        keys: dict[str, Callable[[PartnerMeeting], str]] = {
            "partner": lambda m: m.subject.partner_company.lower(),
            "deal": lambda m: self._deal_name(m.subject.deal_code).lower(),
            "content": lambda m: m.content.value.lower(),
            "author": lambda m: self._author_name(m).lower(),
        }
        # 동률은 방향과 무관하게 미팅 날짜 내림차순 -> id 내림차순. 안정 정렬을 두 번 쓴다.
        ties = sorted(found, key=lambda m: (m.meeting_date, m.id), reverse=True)
        return sorted(ties, key=keys[sort], reverse=descending)

    async def search(self, query: PartnerMeetingQuery) -> Sequence[PartnerMeetingRecord]:
        found = [m for m in self._items.values() if self._matches(m, query)]
        ordered = self._sorted(found, query)
        return [self._record(m) for m in ordered[query.offset : query.offset + query.limit]]

    async def count(self, query: PartnerMeetingQuery) -> int:
        return sum(1 for m in self._items.values() if self._matches(m, query))

    async def deal_choices(self, company: str) -> Sequence[PartnerDealChoice]:
        from app.application.ports.partner_meeting_repository import (  # noqa: PLC0415
            PartnerDealChoice,
        )

        wanted = company.lower()
        contacts = self._contacts._items
        found = []
        for deal in self._deals._items.values():
            linked = any(
                link.active and contacts[link.contact_id].details.company.lower() == wanted
                for link in deal.partner_links
                if link.contact_id in contacts
            )
            if linked:
                found.append(deal)
        found.sort(key=lambda d: (d.details.name.lower(), d.id.value))
        return [
            PartnerDealChoice(
                code=d.id,
                name=str(d.details.name),
                customer_company=str(contacts[d.customer_id].details.company),
            )
            for d in found
        ]
