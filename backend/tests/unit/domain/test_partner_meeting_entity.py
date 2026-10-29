"""PartnerMeeting 엔티티(AC14·15): 기록, 변경 감지, 연결 검사 필요 여부, 수정·삭제 권한."""

from datetime import date, datetime

import pytest
from app.domain.partner_meeting.entities import PartnerMeeting
from app.domain.partner_meeting.errors import (
    PartnerMeetingDeleteForbiddenError,
    PartnerMeetingEditForbiddenError,
)
from app.domain.partner_meeting.values import MeetingContent, PartnerMeetingId

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Role
from tests.factories import NOW, later, make_deal_code
from tests.factories_partner_meeting import make_meeting, make_subject
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
    deal_suffix: str | None = None,
    meeting_date: date | None = None,
    content: str | None = None,
    now: datetime | None = None,
) -> bool:
    subject = make_subject(
        meeting.subject.partner_company,
        make_deal_code(deal_suffix) if deal_suffix else meeting.subject.deal_code,
    )
    return meeting.revise(
        subject=subject,
        meeting_date=meeting_date or meeting.meeting_date,
        content=MeetingContent(content or meeting.content.value),
        now=now or later(60),
    )


class TestRecord:
    def test_record_keeps_the_values_and_stamps_both_times(self) -> None:
        entity_id = PartnerMeetingId(new_id())

        meeting = PartnerMeeting.record(
            entity_id=entity_id,
            subject=make_subject("한빛파트너스", make_deal_code("A7K2")),
            meeting_date=date(2026, 10, 1),
            content=MeetingContent("킥오프"),
            author_user_id=ACTOR_ID,
            now=later(5),
        )

        assert meeting.id == entity_id
        assert meeting.subject.partner_company == "한빛파트너스"
        assert meeting.subject.deal_code == make_deal_code("A7K2")
        assert meeting.meeting_date == date(2026, 10, 1)
        assert meeting.content.value == "킥오프"
        assert meeting.author_user_id == ACTOR_ID
        assert meeting.created_at == meeting.updated_at == later(5)

    def test_record_requires_an_aware_time(self) -> None:
        with pytest.raises(ValueError, match="timezone"):
            make_meeting(now=NOW.replace(tzinfo=None))


class TestRevise:
    def test_revise_with_the_same_values_returns_false_and_keeps_updated_at(self) -> None:
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

    def test_revise_with_a_new_deal_returns_true_and_moves_the_subject(self) -> None:
        meeting = make_meeting(deal_code=make_deal_code("A001"))

        assert _revise(meeting, deal_suffix="B002") is True
        assert meeting.subject.deal_code == make_deal_code("B002")

    def test_revise_never_changes_author_or_created_at(self) -> None:
        meeting = make_meeting(author=KIM, now=NOW)

        _revise(meeting, content="변경", now=later(60))

        assert meeting.author_user_id == KIM
        assert meeting.created_at == NOW


class TestNeedsLinkCheck:
    def test_same_company_and_deal_do_not_need_a_link_check(self) -> None:
        meeting = make_meeting(company="한빛파트너스", deal_code=make_deal_code("A001"))

        assert not meeting.needs_link_check(make_subject("한빛파트너스", make_deal_code("A001")))

    def test_a_company_that_differs_only_in_case_does_not_need_a_link_check(self) -> None:
        meeting = make_meeting(company="Hanbit Partners", deal_code=make_deal_code("A001"))

        assert not meeting.needs_link_check(make_subject("HANBIT partners", make_deal_code("A001")))

    def test_a_different_company_needs_a_link_check(self) -> None:
        meeting = make_meeting(company="한빛파트너스", deal_code=make_deal_code("A001"))

        assert meeting.needs_link_check(make_subject("다른파트너", make_deal_code("A001")))

    def test_a_different_deal_needs_a_link_check(self) -> None:
        meeting = make_meeting(company="한빛파트너스", deal_code=make_deal_code("A001"))

        assert meeting.needs_link_check(make_subject("한빛파트너스", make_deal_code("A002")))


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
