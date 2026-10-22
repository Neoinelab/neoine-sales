"""새 항목의 id는 UoW의 `IdAllocator`가 주는 번호다(AC-11).

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
    register = RegisterVendor(uow_factory, clock)

    first = await register.execute("SAP")
    second = await register.execute("Oracle")

    assert (first.vendor.id, second.vendor.id) == (1, 2)


def test_there_is_no_solution_id_kind() -> None:
    from app.application import ids  # noqa: PLC0415
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    assert not hasattr(IdKind, "SOLUTION")
    assert not hasattr(ids, "new_solution_id")


async def test_register_code_assigns_the_next_code_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterCode(uow_factory, clock)

    first = await register.execute(kind=CodeKind.STATUS, name="보류", probability_hint=None)
    second = await register.execute(kind=CodeKind.STATUS, name="재검토", probability_hint=None)

    assert (first.code.id, second.code.id) == (1, 2)


async def test_register_label_assigns_the_next_bant_label_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    creator = make_user("kim")
    await seeded.users.add(creator)
    register = RegisterBantLabel(uow_factory, clock)

    first = await register.execute(BantCategory.NEED, "규제 대응", creator.id)
    second = await register.execute(BantCategory.NEED, "감사 대응", creator.id)

    assert (first.label.id, second.label.id) == (1, 2)


async def test_register_action_type_assigns_the_next_action_type_id(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    from tests.fakes.catalog_seed import seed_action_types  # noqa: PLC0415 - 도메인 지연 import

    seed_action_types(seeded)
    creator = make_user("kim")
    await seeded.users.add(creator)
    register = RegisterActionType(uow_factory, clock)

    first = await register.execute("웨비나", creator.id)
    second = await register.execute("세미나", creator.id)

    assert (first.action_type.id, second.action_type.id) == (1, 2)


async def test_register_contact_assigns_the_next_contact_id(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterContact(uow_factory, clock)

    first = await register.execute(make_contact_input(company="가나다"))
    second = await register.execute(make_contact_input(company="라마바"))

    assert (first.id, second.id) == (1, 2)


async def test_register_user_assigns_the_next_user_id(admin: AdminStack) -> None:
    first = await admin.register_user.execute(
        login_id="first.hire", role=Role.SALES, actor=ADMIN_ACTOR
    )
    second = await admin.register_user.execute(
        login_id="second.hire", role=Role.SALES, actor=ADMIN_ACTOR
    )

    assert (first.id, second.id) == (1, 2)


async def test_issue_session_assigns_the_next_session_id(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    user = await seed_user(uow_factory, "kim", Role.SALES)

    await auth.issue.execute(user.to_principal())
    await auth.issue.execute(user.to_principal())

    assert sorted(s.id for s in uow.sessions._items.values()) == [1, 2]


async def test_setup_first_admin_assigns_the_next_user_and_session_ids(
    auth: AuthStack, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    from app.domain.auth.credentials import Password  # noqa: PLC0415

    await seed_setup_prerequisites(uow_factory)

    await auth.setup_admin.execute(
        login_id="kim", password=Password("pw-kim"), client_ip="10.0.0.1"
    )

    admin = await uow.users.get_active_by_login_id(LoginId("kim"))
    assert admin is not None
    assert admin.id == 1
    assert [s.id for s in uow.sessions._items.values()] == [1]


async def test_dev_login_assigns_the_next_user_id_to_each_new_dev_row(
    auth: AuthStack, uow: FakeUnitOfWork
) -> None:
    await auth.dev_login.execute(Role.ADMIN)
    await auth.dev_login.execute(Role.SALES)
    await auth.dev_login.execute(Role.ADMIN)  # 이미 있는 개발 행은 재사용한다(번호를 쓰지 않는다)

    admin = await uow.users.get_active_by_login_id(LoginId("dev-admin"))
    sales = await uow.users.get_active_by_login_id(LoginId("dev-sales"))
    assert admin is not None
    assert sales is not None
    assert (admin.id, sales.id) == (1, 2)


async def test_recording_an_action_assigns_the_next_deal_action_id(action_env: ActionEnv) -> None:
    first = await action_env.act()
    second = await action_env.act()

    assert (first.id, second.id) == (1, 2)


async def test_uploading_a_new_file_assigns_the_next_attachment_id(
    attachment_env: AttachmentEnv,
) -> None:
    first = await attachment_env.uploaded(name="a.pdf", data=b"1")
    second = await attachment_env.uploaded(name="b.pdf", data=b"2")

    assert (first.id, second.id) == (1, 2)
