"""PartnerMeeting 엔티티(AC2·AC6·AC12): 기록, 변경 감지, 회사 확인 필요 여부, 수정·삭제 권한."""

from datetime import date, datetime

import pytest

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Role
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import (
    PartnerMeetingDeleteForbiddenError,
    PartnerMeetingEditForbiddenError,
)
from app.domain.partner_meeting.values import MeetingContent, PartnerMeetingId
from tests.factories import NOW, later
from tests.factories_partner_meeting import make_meeting
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID, uid

EDIT_FORBIDDEN = "본인 미팅 기록 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN = "본인 미팅 기록 또는 admin만 삭제할 수 있습니다."
KIM = uid("kim")
PARK = uid("park")
BOSS = uid("boss")


def _revise(
    meeting: PartnerMeeting,
    *,
    company: str | None = None,
    meeting_date: date | None = None,
    content: str | None = None,
    now: datetime | None = None,
) -> bool:
    return meeting.revise(
        partner_company=company or meeting.partner_company,
        meeting_date=meeting_date or meeting.meeting_date,
        content=MeetingContent(content or meeting.content.value),
        now=now or later(60),
    )


class TestRecord:
    def test_record_keeps_the_given_company_date_and_content(self) -> None:
        entity_id = PartnerMeetingId(new_id())

        meeting = PartnerMeeting.record(
            entity_id=entity_id,
            partner_company="한빛파트너스",
            meeting_date=date(2026, 10, 1),
            content=MeetingContent("킥오프"),
            author_user_id=ACTOR_ID,
            now=later(5),
        )

        assert meeting.id == entity_id
        assert meeting.partner_company == "한빛파트너스"
        assert meeting.meeting_date == date(2026, 10, 1)
        assert meeting.content.value == "킥오프"
        assert meeting.author_user_id == ACTOR_ID
        assert meeting.created_at == meeting.updated_at == later(5)

    def test_record_requires_an_aware_time(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            make_meeting(now=NOW.replace(tzinfo=None))


class TestRevise:
    def test_revise_with_same_values_returns_false_and_keeps_updated_at(self) -> None:
        meeting = make_meeting(now=NOW)

        changed = _revise(meeting, now=later(60))

        assert changed is False
        assert meeting.updated_at == NOW

    def test_revise_with_a_new_content_returns_true_and_touches_updated_at(self) -> None:
        meeting = make_meeting(content="이전", now=NOW)

        changed = _revise(meeting, content="이후", now=later(60))

        assert changed is True
        assert meeting.content.value == "이후"
        assert meeting.updated_at == later(60)

    def test_revise_with_a_new_date_returns_true(self) -> None:
        meeting = make_meeting(meeting_date=date(2026, 10, 1))

        assert _revise(meeting, meeting_date=date(2026, 10, 2)) is True
        assert meeting.meeting_date == date(2026, 10, 2)

    def test_revise_with_a_new_company_updates_it(self) -> None:
        meeting = make_meeting(company="한빛파트너스")

        assert _revise(meeting, company="다른파트너") is True
        assert meeting.partner_company == "다른파트너"

    def test_revise_never_changes_author_or_created_at(self) -> None:
        meeting = make_meeting(author=KIM, now=NOW)

        _revise(meeting, content="변경", now=later(60))

        assert meeting.author_user_id == KIM
        assert meeting.created_at == NOW


class TestNeedsCompanyCheck:
    def test_needs_company_check_ignores_case(self) -> None:
        meeting = make_meeting(company="Hanbit Partners")

        assert not meeting.needs_company_check("HANBIT partners")

    def test_the_same_spelling_does_not_need_a_company_check(self) -> None:
        meeting = make_meeting(company="한빛파트너스")

        assert not meeting.needs_company_check("한빛파트너스")

    def test_needs_company_check_is_true_for_another_company(self) -> None:
        meeting = make_meeting(company="한빛파트너스")

        assert meeting.needs_company_check("다른파트너")


class TestPermissions:
    def test_the_author_sales_may_edit_and_delete(self) -> None:
        meeting = make_meeting(author=KIM)

        meeting.ensure_editable_by(KIM, Role.SALES)
        meeting.ensure_deletable_by(KIM, Role.SALES)

    def test_admin_may_edit_and_delete_anyones_record(self) -> None:
        meeting = make_meeting(author=KIM)

        meeting.ensure_editable_by(BOSS, Role.ADMIN)
        meeting.ensure_deletable_by(BOSS, Role.ADMIN)

    def test_ensure_editable_by_another_sales_raises_forbidden(self) -> None:
        meeting = make_meeting(author=KIM)

        with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
            meeting.ensure_editable_by(PARK, Role.SALES)

    def test_ensure_deletable_by_another_sales_raises_forbidden(self) -> None:
        meeting = make_meeting(author=KIM)

        with raises_with(PartnerMeetingDeleteForbiddenError, DELETE_FORBIDDEN):
            meeting.ensure_deletable_by(PARK, Role.SALES)

    def test_a_read_only_user_cannot_edit_even_their_own_record(self) -> None:
        meeting = make_meeting(author=KIM)

        with pytest.raises(PartnerMeetingEditForbiddenError):
            meeting.ensure_editable_by(KIM, Role.USER)
        with pytest.raises(PartnerMeetingDeleteForbiddenError):
            meeting.ensure_deletable_by(KIM, Role.USER)

    def test_the_forbidden_errors_are_access_denied_errors(self) -> None:
        assert issubclass(PartnerMeetingEditForbiddenError, AccessDeniedError)
        assert issubclass(PartnerMeetingDeleteForbiddenError, AccessDeniedError)
