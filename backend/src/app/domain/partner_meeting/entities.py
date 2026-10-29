from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.common.entity import AuditedEntity
from app.domain.partner_meeting.errors import (
    PartnerMeetingDeleteForbiddenError,
    PartnerMeetingEditForbiddenError,
)
from app.domain.partner_meeting.policy import can_edit_meeting
from app.domain.partner_meeting.values import PartnerMeetingId

if TYPE_CHECKING:
    from datetime import date, datetime

    from app.domain.auth.principal import Role
    from app.domain.partner_meeting.values import MeetingContent, MeetingSubject
    from app.domain.user.value_objects import UserId


@dataclass(eq=False, kw_only=True)
class PartnerMeeting(AuditedEntity[PartnerMeetingId]):
    """파트너 회사와 가진 미팅 한 건. 작성자와 등록 시각은 바뀌지 않는다."""

    subject: MeetingSubject
    meeting_date: date
    content: MeetingContent
    author_user_id: UserId

    @classmethod
    def record(  # noqa: PLR0913 - 기록 시점에 정해지는 값이 모두 독립적인 필수 입력
        cls,
        *,
        entity_id: PartnerMeetingId,
        subject: MeetingSubject,
        meeting_date: date,
        content: MeetingContent,
        author_user_id: UserId,
        now: datetime,
    ) -> Self:
        return cls(
            id=entity_id,
            subject=subject,
            meeting_date=meeting_date,
            content=content,
            author_user_id=author_user_id,
            created_at=now,
            updated_at=now,
        )

    def revise(
        self,
        *,
        subject: MeetingSubject,
        meeting_date: date,
        content: MeetingContent,
        now: datetime,
    ) -> bool:
        """값을 바꾼다. 모두 같으면 아무것도 바꾸지 않고 False."""
        if (
            subject == self.subject
            and meeting_date == self.meeting_date
            and content == self.content
        ):
            return False
        self.subject = subject
        self.meeting_date = meeting_date
        self.content = content
        self._touch(now)
        return True

    def needs_link_check(self, subject: MeetingSubject) -> bool:
        """회사나 Deal이 바뀌었을 때만 Deal 연결을 다시 확인한다."""
        return not self.subject.same_as(subject)

    def ensure_editable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_meeting(user_id, role, self.author_user_id):
            raise PartnerMeetingEditForbiddenError

    def ensure_deletable_by(self, user_id: UserId, role: Role) -> None:
        if not can_edit_meeting(user_id, role, self.author_user_id):
            raise PartnerMeetingDeleteForbiddenError
