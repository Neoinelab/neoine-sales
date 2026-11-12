"""UpdatePartnerMeeting: 판정 순서 404 -> 403 -> 422, 회사를 바꿀 때만 회사 목록을 확인."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.partner_meeting.errors import (
    COMPANY_NOT_FOUND,
    MeetingInputError,
    PartnerMeetingEditForbiddenError,
    PartnerMeetingNotFoundError,
)
from app.domain.partner_meeting.values import PartnerMeetingId
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.unit.application.partner_meeting_env import (
    BOSS,
    DAY,
    EDIT_FORBIDDEN,
    HANBIT,
    KIM,
    NOT_FOUND,
    PARK,
    VIEWER,
    item,
)

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv

CONTENT_REQUIRED = "미팅 내용을 입력하세요."


def _found(error: MeetingInputError) -> list[tuple[tuple[str | int, ...], str]]:
    return [(issue.location, issue.message) for issue in error.issues]


async def test_the_author_changes_date_and_content_and_updated_at_moves(
    meeting_env: MeetingEnv,
) -> None:
    """작성자가 날짜·내용을 고치면 변경 시각만 바뀌고 작성자·등록 시각은 그대로다.

    테스트 코드: PA-030
    """
    # given: KIM이 등록한 기록과 한 시간이 지난 시계
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    meeting_env.clock.advance(3600)
    # when: KIM이 날짜와 내용을 고친다
    updated = await meeting_env.update.execute(
        created.id, item(meeting_date=date(2026, 12, 1), content="수정한 내용"), KIM
    )
    # then: 날짜·내용과 변경 시각이 바뀌고 작성자·등록 시각은 그대로다
    stored = await meeting_env.stored(created.id)
    assert (stored.meeting_date, stored.content.value) == (date(2026, 12, 1), "수정한 내용")
    assert stored.updated_at == meeting_env.clock.now() > created.updated_at
    assert stored.created_at == created.created_at
    assert stored.author_user_id == KIM.user_id
    assert updated.content.value == "수정한 내용"


async def test_admin_edits_another_users_record(meeting_env: MeetingEnv) -> None:
    """admin은 남의 기록을 고친다.

    테스트 코드: PA-031
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when: admin이 내용을 고친다
    await meeting_env.update.execute(created.id, item(content="admin 수정"), BOSS)
    # then: 내용이 바뀌고 작성자는 KIM 그대로다
    stored = await meeting_env.stored(created.id)
    assert stored.content.value == "admin 수정"
    assert stored.author_user_id == KIM.user_id


async def test_no_change_does_not_save(meeting_env: MeetingEnv) -> None:
    """값이 그대로인 수정은 저장하지 않고 변경 시각도 그대로다.

    테스트 코드: PA-032
    """
    # given: KIM의 기록과 한 시간이 지난 시계
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    commits = meeting_env.uow.commits
    meeting_env.clock.advance(3600)
    # when: KIM이 같은 값으로 고친다
    returned = await meeting_env.update.execute(
        created.id, item(meeting_date=created.meeting_date, content=created.content.value), KIM
    )
    # then: 커밋이 없고 변경 시각은 이전 값이다
    assert meeting_env.uow.commits == commits
    assert returned.updated_at == created.updated_at
    assert (await meeting_env.stored(created.id)).updated_at == created.updated_at


async def test_no_change_with_a_company_in_other_case_keeps_the_stored_spelling(
    meeting_env: MeetingEnv,
) -> None:
    """회사만 대소문자가 다르고 공백이 더해진 내용이면 저장하지 않고 저장 표기를 유지한다.

    테스트 코드: PA-032
    """
    # given: "HanbitPartners" 회사의 KIM 기록
    await meeting_env.partner("HanbitPartners")
    created = await meeting_env.register_one(KIM, company="HanbitPartners", content="같음")
    commits = meeting_env.uow.commits
    meeting_env.clock.advance(86_400)
    # when: KIM이 회사 "hanbitpartners"와 공백이 붙은 같은 내용으로 고친다
    returned = await meeting_env.update.execute(
        created.id, item(company="hanbitpartners", content="  같음  ", meeting_date=DAY), KIM
    )
    # then: 회사는 저장 표기 그대로이고 커밋과 변경 시각 변화가 없다
    assert returned.partner_company == "HanbitPartners"
    assert meeting_env.uow.commits == commits
    assert (await meeting_env.stored(created.id)).updated_at == created.updated_at


async def test_another_sales_is_forbidden_and_the_record_stays(meeting_env: MeetingEnv) -> None:
    """다른 sales의 수정은 403 문구이고 기록은 그대로다.

    테스트 코드: PA-033
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: PARK이 고치면 "본인 미팅 기록 또는 admin만 수정할 수 있습니다." 오류다
    with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
        await meeting_env.update.execute(created.id, item(content="가로채기"), PARK)
    # then: 기록은 그대로다
    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_read_only_user_is_forbidden_even_for_their_own_record_id(
    meeting_env: MeetingEnv,
) -> None:
    """user 역할은 자기 기록 id라도 수정할 수 없다.

    테스트 코드: PA-033
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: user 역할로 그 기록을 고치면 수정 금지 오류다
    with pytest.raises(PartnerMeetingEditForbiddenError):
        await meeting_env.update.execute(created.id, item(content="변경"), VIEWER)
    # then: 기록은 그대로다
    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_missing_record_is_not_found_before_validation(meeting_env: MeetingEnv) -> None:
    """없는 기록은 입력이 틀려도 404가 먼저다.

    테스트 코드: PA-034
    """
    # when·then: 없는 id를 빈 내용·없는 회사로 고치면 "미팅 기록을 찾을 수 없습니다." 오류다
    with raises_with(PartnerMeetingNotFoundError, NOT_FOUND):
        await meeting_env.update.execute(
            PartnerMeetingId(new_id()), item(content="  ", company="없는회사"), PARK
        )


async def test_another_sales_is_forbidden_before_validation(meeting_env: MeetingEnv) -> None:
    """작성자가 아니면 입력이 틀려도 403이 422보다 먼저다.

    테스트 코드: PA-034
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: PARK이 빈 내용·없는 회사로 고치면 입력 오류가 아니라 수정 금지 오류다
    with raises_with(PartnerMeetingEditForbiddenError, EDIT_FORBIDDEN):
        await meeting_env.update.execute(created.id, item(content="  ", company="없는회사"), PARK)
    # then: 기록은 그대로다
    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_blank_content_is_rejected_at_the_content_location(
    meeting_env: MeetingEnv,
) -> None:
    """빈 내용은 필드만의 위치로 거절된다.

    테스트 코드: PA-035
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: 공백뿐인 내용으로 고치면 content 위치 위반이다
    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(content="  \n"), KIM)
    assert _found(raised.value) == [(("content",), CONTENT_REQUIRED)]
    # then: 기록은 그대로다
    assert (await meeting_env.stored(created.id)).content.value == "킥오프 미팅"


async def test_a_date_outside_the_bounds_is_rejected_at_the_date_location(
    meeting_env: MeetingEnv,
) -> None:
    """범위 밖 날짜는 필드만의 위치로 거절된다.

    테스트 코드: PA-035
    """
    # given: KIM의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: 3000-01-01로 고치면 meeting_date 위치 위반이다
    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(meeting_date=date(3000, 1, 1)), KIM)
    assert [location for location, _ in _found(raised.value)] == [("meeting_date",)]
    # then: 날짜는 그대로다
    assert (await meeting_env.stored(created.id)).meeting_date == DAY


async def test_same_company_in_other_case_keeps_the_stored_company_without_lookup(
    meeting_env: MeetingEnv,
) -> None:
    """같은 회사(대소문자만 다름)는 회사 목록을 확인하지 않고 저장 표기를 유지한다.

    테스트 코드: PA-036
    """
    # given: 기록을 남긴 뒤 연락처를 지워 회사 목록에서 사라진 "HanbitPartners"
    contact = await meeting_env.partner("HanbitPartners")
    created = await meeting_env.register_one(KIM, company="HanbitPartners")
    await meeting_env.drop_partner(contact)
    # when: 작성자가 회사를 "HANBITpartners"로 쓰고 내용을 고친다
    await meeting_env.update.execute(
        created.id, item(company="HANBITpartners", content="대소문자만 다름"), KIM
    )
    # then: 내용은 바뀌고 회사는 저장된 표기 그대로다
    stored = await meeting_env.stored(created.id)
    assert stored.content.value == "대소문자만 다름"
    assert stored.partner_company == "HanbitPartners"


async def test_editing_date_and_content_succeeds_after_the_contact_company_was_renamed(
    meeting_env: MeetingEnv,
) -> None:
    """연락처 회사명이 바뀐 뒤에도 같은 회사 이름으로 날짜·내용을 고친다.

    테스트 코드: PA-036
    """
    # given: 기록을 남긴 뒤 연락처 회사명을 "새회사명"으로 바꿔 옛 이름이 목록에 없다
    contact = await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    await meeting_env.rename_partner_company(contact, "새회사명")
    # when: 작성자가 같은 회사 이름으로 날짜와 내용을 고친다
    await meeting_env.update.execute(
        created.id, item(company=HANBIT, meeting_date=date(2026, 9, 9), content="이름 변경 뒤"), KIM
    )
    # then: 회사는 그대로이고 날짜·내용이 바뀐다
    stored = await meeting_env.stored(created.id)
    assert (stored.partner_company, stored.meeting_date) == (HANBIT, date(2026, 9, 9))
    assert stored.content.value == "이름 변경 뒤"


async def test_changing_to_another_registered_company_stores_the_new_spelling(
    meeting_env: MeetingEnv,
) -> None:
    """다른 등록 회사로 바꾸면 그 회사의 대표 표기로 저장된다.

    테스트 코드: PA-037
    """
    # given: 회사 두 곳과 첫 회사의 기록
    await meeting_env.partner(HANBIT)
    await meeting_env.partner("OtherPartners")
    created = await meeting_env.register_one(KIM)
    # when: 회사를 "otherPARTNERS"로 바꾼다
    updated = await meeting_env.update.execute(created.id, item(company="otherPARTNERS"), KIM)
    # then: 응답과 저장된 회사는 "OtherPartners"다
    assert updated.partner_company == "OtherPartners"
    assert (await meeting_env.stored(created.id)).partner_company == "OtherPartners"


async def test_changing_to_an_unknown_company_is_rejected_at_partner_company(
    meeting_env: MeetingEnv,
) -> None:
    """등록되지 않은 회사로 바꾸면 partner_company 위치로 거절된다.

    테스트 코드: PA-037
    """
    # given: 파트너 연락처와 그 회사의 기록
    await meeting_env.partner(HANBIT)
    created = await meeting_env.register_one(KIM)
    # when·then: 없는 회사로 고치면 partner_company 위치 위반이다
    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.update.execute(created.id, item(company="없는회사"), KIM)
    assert _found(raised.value) == [(("partner_company",), COMPANY_NOT_FOUND)]
    # then: 회사는 그대로다
    assert (await meeting_env.stored(created.id)).partner_company == HANBIT
