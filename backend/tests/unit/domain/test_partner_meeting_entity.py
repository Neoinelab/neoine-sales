"""PartnerMeeting 엔티티: 기록, 변경 감지, 회사 확인 필요 여부, 수정·삭제 권한."""

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
        """기록을 만들면 받은 회사·날짜·내용·작성자를 그대로 갖고 두 시각이 같다."""
        # given: 새 기록의 id
        entity_id = PartnerMeetingId(new_id())
        # when: 기록을 만든다
        meeting = PartnerMeeting.record(
            entity_id=entity_id,
            partner_company="한빛파트너스",
            meeting_date=date(2026, 10, 1),
            content=MeetingContent("킥오프"),
            author_user_id=ACTOR_ID,
            now=later(5),
        )
        # then: 받은 값이 그대로이고 두 시각이 같다
        assert meeting.id == entity_id
        assert meeting.partner_company == "한빛파트너스"
        assert meeting.meeting_date == date(2026, 10, 1)
        assert meeting.content.value == "킥오프"
        assert meeting.author_user_id == ACTOR_ID
        assert meeting.created_at == meeting.updated_at == later(5)

    def test_record_requires_an_aware_time(self) -> None:
        """시간대 없는 시각으로는 기록을 만들 수 없다."""
        # when·then: naive 시각이면 ValueError다
        with pytest.raises(ValueError, match="timezone"):
            make_meeting(now=NOW.replace(tzinfo=None))


class TestRevise:
    def test_revise_with_same_values_returns_false_and_keeps_updated_at(self) -> None:
        """같은 값으로 고치면 False이고 변경 시각이 그대로다."""
        # given: 기록
        meeting = make_meeting(now=NOW)
        # when: 같은 값으로 고친다
        changed = _revise(meeting, now=later(60))
        # then: 바뀌지 않았다
        assert changed is False
        assert meeting.updated_at == NOW

    def test_revise_with_a_new_content_returns_true_and_touches_updated_at(self) -> None:
        """내용을 바꾸면 True이고 변경 시각이 갱신된다."""
        # given: 내용 "이전"인 기록
        meeting = make_meeting(content="이전", now=NOW)
        # when: 내용을 "이후"로 고친다
        changed = _revise(meeting, content="이후", now=later(60))
        # then: 바뀌었고 변경 시각이 갱신된다
        assert changed is True
        assert meeting.content.value == "이후"
        assert meeting.updated_at == later(60)

    def test_revise_with_a_new_date_returns_true(self) -> None:
        """날짜를 바꾸면 True다."""
        # given: 10/1 기록
        meeting = make_meeting(meeting_date=date(2026, 10, 1))
        # when: 10/2로 고친다
        changed = _revise(meeting, meeting_date=date(2026, 10, 2))
        # then: 바뀌었고 날짜가 10/2다
        assert changed is True
        assert meeting.meeting_date == date(2026, 10, 2)

    def test_revise_with_a_new_company_updates_it(self) -> None:
        """회사를 바꾸면 True이고 회사가 갱신된다."""
        # given: 한빛파트너스 기록
        meeting = make_meeting(company="한빛파트너스")
        # when: 회사를 바꿔 고친다
        changed = _revise(meeting, company="다른파트너")
        # then: 바뀌었고 회사가 갱신된다
        assert changed is True
        assert meeting.partner_company == "다른파트너"

    def test_revise_never_changes_author_or_created_at(self) -> None:
        """고쳐도 작성자와 등록 시각은 바뀌지 않는다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM, now=NOW)
        # when: 내용을 고친다
        _revise(meeting, content="변경", now=later(60))
        # then: 작성자와 등록 시각은 그대로다
        assert meeting.author_user_id == KIM
        assert meeting.created_at == NOW


class TestNeedsCompanyCheck:
    def test_needs_company_check_ignores_case(self) -> None:
        """대소문자만 다른 회사는 확인이 필요 없다."""
        # given: "Hanbit Partners" 기록
        meeting = make_meeting(company="Hanbit Partners")
        # when·then: "HANBIT partners"는 확인이 필요 없다
        assert not meeting.needs_company_check("HANBIT partners")

    def test_the_same_spelling_does_not_need_a_company_check(self) -> None:
        """같은 표기의 회사는 확인이 필요 없다."""
        # given: 한빛파트너스 기록
        meeting = make_meeting(company="한빛파트너스")
        # when·then: 같은 이름은 확인이 필요 없다
        assert not meeting.needs_company_check("한빛파트너스")

    def test_needs_company_check_is_true_for_another_company(self) -> None:
        """다른 회사로 바꾸려면 확인이 필요하다."""
        # given: 한빛파트너스 기록
        meeting = make_meeting(company="한빛파트너스")
        # when·then: 다른 이름은 확인이 필요하다
        assert meeting.needs_company_check("다른파트너")


class TestPermissions:
    def test_the_author_sales_may_edit_and_delete(self) -> None:
        """작성자인 sales는 수정·삭제할 수 있다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM)
        # when·then: KIM(sales)의 수정·삭제는 오류 없이 통과한다
        meeting.ensure_editable_by(KIM, Role.SALES)
        meeting.ensure_deletable_by(KIM, Role.SALES)

    def test_admin_may_edit_and_delete_anyones_record(self) -> None:
        """admin은 남의 기록도 수정·삭제할 수 있다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM)
        # when·then: admin의 수정·삭제는 오류 없이 통과한다
        meeting.ensure_editable_by(BOSS, Role.ADMIN)
        meeting.ensure_deletable_by(BOSS, Role.ADMIN)

    def test_ensure_editable_by_another_sales_raises_forbidden(self) -> None:
        """다른 sales의 수정은 금지 오류다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM)
        # when·then: PARK(sales)의 수정은 수정 금지 오류다
        with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
            meeting.ensure_editable_by(PARK, Role.SALES)

    def test_ensure_deletable_by_another_sales_raises_forbidden(self) -> None:
        """다른 sales의 삭제는 금지 오류다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM)
        # when·then: PARK(sales)의 삭제는 삭제 금지 오류다
        with raises_with(PartnerMeetingDeleteForbiddenError, DELETE_FORBIDDEN):
            meeting.ensure_deletable_by(PARK, Role.SALES)

    def test_a_read_only_user_cannot_edit_even_their_own_record(self) -> None:
        """user 역할은 자기 기록이라도 수정·삭제할 수 없다."""
        # given: KIM의 기록
        meeting = make_meeting(author=KIM)
        # when·then: user 역할의 수정은 수정 금지 오류다
        with pytest.raises(PartnerMeetingEditForbiddenError):
            meeting.ensure_editable_by(KIM, Role.USER)
        # when·then: user 역할의 삭제는 삭제 금지 오류다
        with pytest.raises(PartnerMeetingDeleteForbiddenError):
            meeting.ensure_deletable_by(KIM, Role.USER)

    def test_the_forbidden_errors_are_access_denied_errors(self) -> None:
        """금지 오류는 AccessDeniedError의 하위 타입이다."""
        # when·then: 상속 관계를 살피면 수정·삭제 금지 오류 모두 AccessDeniedError다
        assert issubclass(PartnerMeetingEditForbiddenError, AccessDeniedError)
        assert issubclass(PartnerMeetingDeleteForbiddenError, AccessDeniedError)
