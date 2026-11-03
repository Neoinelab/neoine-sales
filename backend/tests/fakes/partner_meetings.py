"""PartnerMeetingRepository Port의 InMemory 구현(Fake). 파트너 Activity의 미팅 기록 저장소.

도메인·Port 모듈(app.domain.partner_meeting, app.application.ports.partner_meeting_repository)은
사용 시점에 가져온다. 이 Fake는 FakeUnitOfWork가 항상 만들기 때문에, 모듈 수준 import는 미팅과
무관한 테스트의 수집까지 막는다(vendors.py와 같은 이유).

미팅은 Deal과 연결되지 않는다(Deal 삭제는 미팅에 영향이 없다).

계약(SQL 구현과 같다)
- add: 같은 id AlreadyExistsError, 작성자 행이 없으면 InvalidReferenceError("사용자")
- get: 없으면 PartnerMeetingNotFoundError. 엔티티(PartnerMeeting)를 돌려준다
- update: partner_company·meeting_date·content·updated_at만 저장한다. 없으면 NotFound
- delete: 물리 삭제. 없으면 PartnerMeetingNotFoundError
- search/count: 조건은 AND. 텍스트는 대소문자 무시 부분 일치(`%`·`_`·`\\`는 글자 그대로)
  정렬: meeting_date는 (날짜, id)를 방향대로. partner·content·author는 주 키 lower(...)를
  방향대로 -> 미팅 날짜 내림차순 -> id 내림차순(동률 규칙은 방향과 무관)
  author는 표시 이름(비어 있으면 login_id)이고 퇴사자도 포함한다
"""

import copy
from typing import TYPE_CHECKING, Any

from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from types import ModuleType

    from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
    from app.domain.partner_meeting.entities import PartnerMeeting
    from app.domain.partner_meeting.values import PartnerMeetingId


def _errors() -> ModuleType:
    from app.domain.partner_meeting import errors  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    return errors


def _not_found(meeting_id: Any) -> Any:  # noqa: ANN401 - NotFoundError 하위 인스턴스
    return _errors().PartnerMeetingNotFoundError(meeting_id)


class FakePartnerMeetingRepository(InMemoryStore["PartnerMeeting"]):
    def __init__(self) -> None:
        super().__init__("partner_meeting", _not_found)
        self._users: Any = None

    def wire(self, *, users: Any) -> None:  # noqa: ANN401
        """작성자 존재 확인(FK 모사)과 작성자 이름 읽기에 쓴다."""
        self._users = users

    def _author_name(self, meeting: PartnerMeeting) -> str:
        user = self._users._items.get(meeting.author_user_id)
        if user is None:
            return str(meeting.author_user_id)
        return str(user.display_name or user.login_id.value)

    def _ensure_references(self, meeting: PartnerMeeting) -> None:
        from app.domain.common.errors import InvalidReferenceError  # noqa: PLC0415

        if meeting.author_user_id not in self._users._items:
            raise InvalidReferenceError("사용자", meeting.author_user_id)

    # --- 쓰기 ---

    async def add(self, meeting: PartnerMeeting) -> None:
        if meeting.id in self._items:
            self._insert(meeting)  # 같은 id는 AlreadyExistsError
        self._ensure_references(meeting)
        self._insert(meeting)

    async def update(self, meeting: PartnerMeeting) -> None:
        stored = self._fetch(meeting.id)  # 없으면 PartnerMeetingNotFoundError
        stored.partner_company = meeting.partner_company
        stored.meeting_date = meeting.meeting_date
        stored.content = meeting.content
        stored.updated_at = meeting.updated_at
        self._replace(stored)

    async def delete(self, meeting_id: PartnerMeetingId) -> None:
        self._remove(meeting_id)

    # --- 읽기 ---

    async def get(
        self, meeting_id: PartnerMeetingId, *, for_update: bool = False
    ) -> PartnerMeeting:
        return copy.deepcopy(self._fetch(meeting_id))

    def _matches(self, meeting: PartnerMeeting, query: PartnerMeetingQuery) -> bool:
        if query.partner and query.partner.lower() not in meeting.partner_company.lower():
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
            "partner": lambda m: m.partner_company.lower(),
            "content": lambda m: m.content.value.lower(),
            "author": lambda m: self._author_name(m).lower(),
        }
        # 동률은 방향과 무관하게 미팅 날짜 내림차순 -> id 내림차순. 안정 정렬을 두 번 쓴다.
        ties = sorted(found, key=lambda m: (m.meeting_date, m.id), reverse=True)
        return sorted(ties, key=keys[sort], reverse=descending)

    async def search(self, query: PartnerMeetingQuery) -> Sequence[PartnerMeeting]:
        found = [m for m in self._items.values() if self._matches(m, query)]
        ordered = self._sorted(found, query)
        return [copy.deepcopy(m) for m in ordered[query.offset : query.offset + query.limit]]

    async def count(self, query: PartnerMeetingQuery) -> int:
        return sum(1 for m in self._items.values() if self._matches(m, query))
