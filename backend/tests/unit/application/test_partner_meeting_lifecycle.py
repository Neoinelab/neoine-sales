"""파트너 미팅 기록과 다른 데이터의 수명: 작성자 퇴사, 연락처 회사명 변경."""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.partner_meeting_repository import PartnerMeetingQuery
from app.application.user.delete_user import DeleteOutcome, DeleteUser
from app.application.user.list_user_options import ListUserOptions
from app.application.user.resolve_user_refs import ResolveUserRefs
from app.domain.auth.principal import Role
from app.domain.partner_meeting.errors import COMPANY_NOT_FOUND, MeetingInputError
from tests.factories_auth import make_user
from tests.unit.application.partner_meeting_env import HANBIT, KIM, item

if TYPE_CHECKING:
    from tests.unit.application.partner_meeting_env import MeetingEnv


async def test_deleting_the_author_resigns_them_and_the_record_stays_searchable(
    meeting_env: MeetingEnv,
) -> None:
    """미팅을 쓴 사용자를 삭제하면 퇴사 처리되고 기록은 작성자 조건·선택지로 찾는다.

    테스트 코드: PA-045
    """
    # given: KIM이 쓴 기록과 KIM이 아닌 재직 admin
    await meeting_env.partner(HANBIT)
    written = await meeting_env.register_one(KIM, content="퇴사자 기록")
    root = make_user("mt-root", Role.ADMIN)
    async with meeting_env.uow_factory() as active:
        await active.users.add(root)
        await active.commit()
    # when: admin이 KIM을 삭제한다
    delete = DeleteUser(meeting_env.uow_factory, meeting_env.clock)
    outcome = await delete.execute(user_id=KIM.user_id, actor=root.to_principal())
    # then: 결과가 resigned이고 기록은 남는다
    assert outcome is DeleteOutcome.RESIGNED
    assert (await meeting_env.stored(written.id)).author_user_id == KIM.user_id
    # when: 작성자 표기, 작성자 조건 목록, 퇴사자 포함 사용자 선택지를 읽는다
    authors = await ResolveUserRefs(meeting_env.uow_factory).execute([KIM.user_id])
    page = await meeting_env.list.execute(PartnerMeetingQuery(author_user_id=KIM.user_id))
    options = await ListUserOptions(meeting_env.uow_factory).execute(include_resigned=True)
    # then: 작성자는 퇴사 표기이고 그 기록이 나오며 선택지에 "(퇴사)" 표기의 KIM이 있다
    assert authors[KIM.user_id].resigned is True
    assert authors[KIM.user_id].label.endswith("(퇴사)")
    assert [m.id for m in page.items] == [written.id]
    resigned = [o for o in options if o.id == KIM.user_id]
    assert [(o.resigned, o.label.endswith("(퇴사)")) for o in resigned] == [(True, True)]


async def test_renaming_the_contact_company_keeps_old_records_and_changes_what_registers(
    meeting_env: MeetingEnv,
) -> None:
    """연락처 회사명을 바꿔도 기존 기록은 옛 이름이고 새 등록은 새 이름만 받는다.

    테스트 코드: PA-046
    """
    # given: "한빛파트너스" 기록과, 그 뒤 회사명이 "새회사명"으로 바뀐 연락처
    contact = await meeting_env.partner(HANBIT)
    await meeting_env.register_one(KIM)
    await meeting_env.rename_partner_company(contact, "새회사명")
    # when: 옛 이름으로 검색한다
    found = await meeting_env.list.execute(PartnerMeetingQuery(partner=HANBIT))
    # then: 기록의 회사명은 옛 이름 그대로다
    assert [m.partner_company for m in found.items] == [HANBIT]
    # when·then: 옛 이름으로 등록하면 partner_company 위치로 거절된다
    with pytest.raises(MeetingInputError) as raised:
        await meeting_env.register.execute([item(company=HANBIT)], KIM)
    assert [(i.location, i.message) for i in raised.value.issues] == [
        (("items", 0, "partner_company"), COMPANY_NOT_FOUND)
    ]
    # when: 새 이름으로 등록한다
    (created,) = await meeting_env.register.execute([item(company="새회사명")], KIM)
    # then: 새 이름으로 저장된다
    assert created.partner_company == "새회사명"
