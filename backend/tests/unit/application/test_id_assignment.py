"""새 항목의 id는 UoW의 `IdAllocator`가 주는 번호다.

Fake 할당기는 종류별로 1부터 센다. 같은 종류에서 나중에 만든 항목의 id가 더 크고(2번째가 2),
종류가 달라도 서로 번호를 나누지 않는다. 시드(기본 코드·Label·유형)는 높은 번호를 가지므로
첫 새 항목은 항상 1이다. 도메인은 id를 만들지 않으므로(`test_entity_ids.py`) 이 번호의 출처는
application이 부르는 `uow.ids.next_id(kind)`뿐이다.
"""

from typing import TYPE_CHECKING

from app.application.action_type.register_action_type import RegisterActionType
from app.application.bant.register_label import RegisterBantLabel
from app.application.code.register_code import RegisterCode
from app.application.contact.register_contact import RegisterContact
from app.application.vendor.register_vendor import RegisterVendor
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.bant.values import BantCategory
from app.domain.code.values import CodeKind
from tests.factories_auth import make_user
from tests.factories_contact import make_contact_input
from tests.fakes.admin_stack import ADMIN_ACTOR
from tests.support.auth_seed import seed_setup_prerequisites, seed_user

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
    from tests.unit.application.action_env import ActionEnv
    from tests.unit.application.attachment_env import AttachmentEnv


async def test_register_vendor_assigns_the_next_vendor_id(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Vendor를 연속 등록하면 vendor id가 1, 2로 매겨지는지 확인한다."""
    register = RegisterVendor(uow_factory, clock)

    # when: Vendor 두 개를 차례로 등록한다
    first = await register.execute("SAP")
    second = await register.execute("Oracle")

    # then: Vendor id가 (1, 2)다
    assert (first.vendor.id, second.vendor.id) == (1, 2)


def test_there_is_no_solution_id_kind() -> None:
    """Solution id 종류와 발급 함수가 더는 없는지 확인한다."""
    # when·then: IdKind와 ids 모듈에 Solution 항목이 없다
    from app.application import ids  # noqa: PLC0415
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    assert not hasattr(IdKind, "SOLUTION")
    assert not hasattr(ids, "new_solution_id")


async def test_register_code_assigns_the_next_code_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """코드를 연속 등록하면 code id가 1, 2로 매겨지는지 확인한다."""
    register = RegisterCode(uow_factory, clock)

    # when: 같은 종류 코드 두 개를 차례로 등록한다 (전제: 시드된 UoW)
    first = await register.execute(kind=CodeKind.STATUS, name="보류", probability_hint=None)
    second = await register.execute(kind=CodeKind.STATUS, name="재검토", probability_hint=None)

    # then: 코드 id가 (1, 2)다
    assert (first.code.id, second.code.id) == (1, 2)


async def test_register_label_assigns_the_next_bant_label_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """BANT Label을 연속 등록하면 label id가 1, 2로 매겨지는지 확인한다."""
    # given: 등록자 사용자가 있다
    creator = make_user("kim")
    await seeded.users.add(creator)
    register = RegisterBantLabel(uow_factory, clock)

    # when: Label 두 개를 차례로 등록한다
    first = await register.execute(BantCategory.NEED, "규제 대응", creator.id)
    second = await register.execute(BantCategory.NEED, "감사 대응", creator.id)

    # then: BANT Label id가 (1, 2)다
    assert (first.label.id, second.label.id) == (1, 2)


async def test_register_action_type_assigns_the_next_action_type_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Action 유형을 연속 등록하면 유형 id가 1, 2로 매겨지는지 확인한다."""
    from tests.fakes.catalog_seed import seed_action_types  # noqa: PLC0415 - 도메인 지연 import

    # given: 기본 Action 유형이 시드되어 있고 등록자 사용자가 있다
    seed_action_types(seeded)
    creator = make_user("kim")
    await seeded.users.add(creator)
    register = RegisterActionType(uow_factory, clock)

    # when: 유형 두 개를 차례로 등록한다
    first = await register.execute("웨비나", creator.id)
    second = await register.execute("세미나", creator.id)

    # then: Action 유형 id가 (1, 2)다
    assert (first.action_type.id, second.action_type.id) == (1, 2)


async def test_register_contact_assigns_the_next_contact_id(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """연락처를 연속 등록하면 contact id가 1, 2로 매겨지는지 확인한다."""
    register = RegisterContact(uow_factory, clock)

    # when: 연락처 두 개를 차례로 등록한다
    first = await register.execute(make_contact_input(company="가나다"))
    second = await register.execute(make_contact_input(company="라마바"))

    # then: 연락처 id가 (1, 2)다
    assert (first.id, second.id) == (1, 2)


async def test_register_user_assigns_the_next_user_id(admin: AdminStack) -> None:
    """사용자를 연속 등록하면 user id가 1, 2로 매겨지는지 확인한다."""
    # when: 사용자 두 명을 차례로 등록한다
    first = await admin.register_user.execute(
        login_id="first.hire", role=Role.SALES, actor=ADMIN_ACTOR
    )
    second = await admin.register_user.execute(
        login_id="second.hire", role=Role.SALES, actor=ADMIN_ACTOR
    )

    # then: 사용자 id가 (1, 2)다
    assert (first.id, second.id) == (1, 2)


async def test_issue_session_assigns_the_next_session_id(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """세션을 연속 발급하면 session id가 1, 2로 매겨지는지 확인한다."""
    # given: 사용자가 있다
    user = await seed_user(uow_factory, "kim", Role.SALES)

    # when: 세션을 두 번 발급한다
    await auth.issue.execute(user.to_principal())
    await auth.issue.execute(user.to_principal())

    # then: 세션 id가 [1, 2]다
    assert sorted(s.id for s in uow.sessions._items.values()) == [1, 2]


async def test_setup_first_admin_assigns_the_next_user_and_session_ids(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """최초 admin 설정이 user id와 session id를 1로 매기는지 확인한다."""
    from app.domain.auth.credentials import Password  # noqa: PLC0415

    # given: 최초 설정 선행 조건이 갖춰져 있다
    await seed_setup_prerequisites(uow_factory)

    # when: 최초 admin을 설정한다
    await auth.setup_admin.execute(
        login_id="kim", password=Password("pw-kim"), client_ip="10.0.0.1"
    )

    # then: 사용자 id와 세션 id가 모두 1이다
    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert admin.id == 1
    assert [s.id for s in uow.sessions._items.values()] == [1]


async def test_recording_an_action_assigns_the_next_deal_action_id(action_env: ActionEnv) -> None:
    """Action을 연속 기록하면 action id가 1, 2로 매겨지는지 확인한다."""
    # when: Action을 두 번 기록한다
    first = await action_env.act()
    second = await action_env.act()

    # then: Action id가 (1, 2)다
    assert (first.id, second.id) == (1, 2)


async def test_uploading_a_new_file_assigns_the_next_attachment_id(
    attachment_env: AttachmentEnv,
) -> None:
    """새 파일을 연속 올리면 첨부 id가 1, 2로 매겨지는지 확인한다."""
    # when: 서로 다른 파일 두 개를 올린다
    first = await attachment_env.uploaded(name="a.pdf", data=b"1")
    second = await attachment_env.uploaded(name="b.pdf", data=b"2")

    # then: 첨부 id가 (1, 2)다
    assert (first.id, second.id) == (1, 2)
