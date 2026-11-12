"""리포트를 만들었거나 마지막으로 수정한 사용자의 삭제 결과: 퇴사 처리되고 리포트는 남는다."""

from typing import TYPE_CHECKING

from app.application.report.create_report import CreateReport
from app.application.report.get_report import GetReport
from app.application.report.list_reports import ListReports
from app.application.report.run_saved_report import RunSavedReport
from app.application.report.update_report import UpdateReport
from app.application.user.delete_user import DeleteOutcome
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserStatusFilter
from tests.support.auth_seed import seed_user
from tests.unit.application.saved_report_env import content_input, viewer

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.unit_of_work import FixedClock


async def test_deleting_a_creator_or_last_editor_resigns_the_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """만들었거나 마지막으로 수정한 사용자는 삭제하면 퇴사 처리되고 연결 없는 사용자는 삭제된다.

    테스트 코드: RS-047
    """
    # given: ALICE가 공개 리포트를 만들고 BOB이 덮어씀, 연결이 없는 사용자 PARK
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    alice = await seed_user(uow_factory, "alice", Role.SALES)
    bob = await seed_user(uow_factory, "bob", Role.SALES)
    park = await seed_user(uow_factory, "park", Role.SALES)
    report = await CreateReport(uow_factory, clock).execute(content_input("공개"), viewer(alice.id))
    await UpdateReport(uow_factory, clock).execute(
        report.id, content_input("공개"), report.revision, viewer(bob.id)
    )
    # when: ROOT가 ALICE를 삭제한다
    alice_outcome = await admin.delete_user.execute(user_id=alice.id, actor=root.to_principal())
    # then: ALICE는 퇴사 처리된다
    assert alice_outcome is DeleteOutcome.RESIGNED
    # when: ROOT가 BOB을 삭제한다
    bob_outcome = await admin.delete_user.execute(user_id=bob.id, actor=root.to_principal())
    # then: BOB도 퇴사 처리된다
    assert bob_outcome is DeleteOutcome.RESIGNED
    # when: ROOT가 연결 없는 PARK을 삭제한다
    park_outcome = await admin.delete_user.execute(user_id=park.id, actor=root.to_principal())
    # then: PARK은 물리 삭제된다
    assert park_outcome is DeleteOutcome.DELETED
    # when: 퇴사자를 포함해 사용자 목록을 읽는다
    resigned = await admin.list_users.execute(status=UserStatusFilter.RESIGNED)
    everyone = await admin.list_users.execute(status=UserStatusFilter.ALL)
    # then: ALICE·BOB은 퇴사자 목록에 남고 PARK은 어느 목록에도 없다
    assert {u.id for u in resigned} == {alice.id, bob.id}
    assert park.id not in {u.id for u in everyone}


async def test_report_of_a_resigned_creator_stays_and_is_shown_as_resigned(
    admin: AdminStack, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """만든 사람이 퇴사해도 리포트는 남아 "(퇴사)"로 보이고 다른 사용자가 열고 실행한다.

    테스트 코드: RS-048
    """
    # given: ALICE의 공개 리포트 R, 그 뒤 ALICE가 퇴사 처리됨
    root = await seed_user(uow_factory, "root", Role.ADMIN)
    alice = await seed_user(uow_factory, "alice", Role.SALES)
    viewer_user = await seed_user(uow_factory, "viewer", Role.USER)
    report = await CreateReport(uow_factory, clock).execute(content_input("공개"), viewer(alice.id))
    await admin.delete_user.execute(user_id=alice.id, actor=root.to_principal())
    # when: VIEWER가 목록을 읽고 R을 열고 실행한다
    items = await ListReports(uow_factory).execute(viewer(viewer_user.id, Role.USER))
    opened = await GetReport(uow_factory).execute(report.id, viewer(viewer_user.id, Role.USER))
    ran = await RunSavedReport(uow_factory, clock).execute(
        report.id, viewer(viewer_user.id, Role.USER)
    )
    # then: 목록에 R이 있고 실행이 된다
    assert [i.report.id for i in items] == [report.id]
    assert ran is not None
    # then: 만든 사람·최종 수정자 표시는 "(퇴사)" 라벨의 퇴사자다
    refs = await admin.resolve_user_refs.execute({opened.owner_user_id, opened.updated_by_user_id})
    owner, editor = refs[opened.owner_user_id], refs[opened.updated_by_user_id]
    assert owner.resigned is True
    assert owner.label.endswith("(퇴사)")
    assert (editor.resigned, editor.label) == (True, owner.label)
