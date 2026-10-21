"""AC10: 사용자 선택 옵션(ListUserOptions)과 UserRef 일괄 해석(ResolveUserRefs) (T21·T24)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserId, UserStatusFilter
from tests.factories import later
from tests.support.auth_seed import seed_user
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.admin_stack import AdminStack


async def _named(uow_factory: UnitOfWorkFactory, login: str, name: str, n: int, **kw: bool) -> None:
    user = await seed_user(uow_factory, login, Role.SALES, now=later(n))
    async with uow_factory() as uow:
        stored = await uow.users.get(user.id)
        stored.record_login(later(n), display_name=name, email=f"{login}@corp.test")
        if kw.get("resigned"):
            stored.resign(later(n + 100))
        await uow.users.update(stored)
        await uow.commit()


async def test_options_default_to_active_users_with_labels(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)

    options = await admin.list_user_options.execute()

    assert [(o.name, o.resigned, o.label) for o in options] == [("홍길동", False, "홍길동")]


async def test_options_include_resigned_users_with_the_resigned_label(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)

    options = await admin.list_user_options.execute(include_resigned=True)

    assert [(o.name, o.resigned, o.label) for o in options] == [
        ("홍길동", False, "홍길동"),
        ("이탈자", True, "이탈자(퇴사)"),
    ]


async def test_options_keyword_matches_the_display_name_ignoring_case(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong.gd", "홍길동", 1)
    await _named(uow_factory, "kim", "김영업", 2)
    await _named(uow_factory, "lee", "이HONG", 3)

    by_korean = await admin.list_user_options.execute(keyword="영업")
    by_latin = await admin.list_user_options.execute(keyword="hong")

    assert [o.name for o in by_korean] == ["김영업"]
    assert [o.name for o in by_latin] == ["이HONG"]  # hong.gd는 아이디일 뿐 이름이 아니다


async def test_options_keyword_does_not_match_the_login_id_of_a_user_with_a_display_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong.gd", "홍길동", 1)

    assert list(await admin.list_user_options.execute(keyword="hong.gd")) == []
    assert list(await admin.list_user_options.execute(keyword="HONG")) == []


async def test_options_keyword_matches_the_login_id_only_as_the_fallback_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "newbie", Role.USER)  # 로그인 전: 표시 이름 없음, name == login_id

    options = await admin.list_user_options.execute(keyword="NEWB")

    assert [o.name for o in options] == ["newbie"]


async def test_options_do_not_carry_a_login_id_field(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong", "홍길동", 1)

    (option,) = await admin.list_user_options.execute()

    assert not hasattr(option, "login_id")


async def test_options_name_falls_back_to_login_id_before_first_login(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "newbie", Role.USER)

    (option,) = await admin.list_user_options.execute()

    assert (option.name, option.label) == ("newbie", "newbie")


async def test_options_return_every_matching_user_beyond_the_old_200_cap(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    for n in range(1, 206):
        await _named(uow_factory, f"user{n}", f"사용자{n:03d}", n)

    options = await admin.list_user_options.execute()

    assert len(options) == 205
    assert [o.name for o in options][:2] == ["사용자001", "사용자002"]
    assert options[-1].name == "사용자205"


async def test_options_no_longer_accept_a_limit(admin: AdminStack) -> None:
    with pytest.raises(TypeError):
        await admin.list_user_options.execute(limit=3)  # type: ignore[call-arg]


async def test_options_expose_no_email(admin: AdminStack, uow_factory: UnitOfWorkFactory) -> None:
    await _named(uow_factory, "hong", "홍길동", 1)

    (option,) = await admin.list_user_options.execute()

    assert not hasattr(option, "email")


async def test_options_carry_the_role_of_each_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await seed_user(uow_factory, "sales1", Role.SALES, now=later(2))
    await seed_user(uow_factory, "viewer", Role.USER, now=later(3))

    options = await admin.list_user_options.execute()

    assert [(o.name, o.role) for o in options] == [
        ("boss", Role.ADMIN),
        ("sales1", Role.SALES),
        ("viewer", Role.USER),
    ]


async def test_options_filter_by_role_returns_only_active_users_of_that_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await _named(uow_factory, "kim", "김영업", 2)
    await seed_user(uow_factory, "viewer", Role.USER, now=later(3))
    await _named(uow_factory, "gone", "이탈자", 4, resigned=True)

    options = await admin.list_user_options.execute(role=Role.SALES)

    assert [(o.name, o.role, o.resigned) for o in options] == [("김영업", Role.SALES, False)]


async def test_options_filter_by_role_with_resigned_includes_resigned_users_of_that_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "kim", "김영업", 1)
    await seed_user(uow_factory, "viewer", Role.USER, now=later(2))
    await _named(uow_factory, "gone", "이탈자", 3, resigned=True)

    options = await admin.list_user_options.execute(role=Role.SALES, include_resigned=True)

    assert [(o.name, o.resigned) for o in options] == [("김영업", False), ("이탈자", True)]


async def test_options_without_role_keep_returning_every_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await _named(uow_factory, "kim", "김영업", 2)

    options = await admin.list_user_options.execute()

    assert [o.name for o in options] == ["boss", "김영업"]


async def test_options_filter_by_role_combines_with_keyword(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "a", "김하나", 1)
    await _named(uow_factory, "b", "김둘", 2)
    await _named(uow_factory, "c", "김셋", 3)
    await seed_user(uow_factory, "kimv", Role.USER, now=later(4))

    options = await admin.list_user_options.execute(role=Role.SALES, keyword="김")

    assert [o.name for o in options] == ["김하나", "김둘", "김셋"]


async def test_resolve_user_refs_carries_the_role_including_resigned_users(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "gone", "이탈자", 1, resigned=True)
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(2))
    async with uow_factory() as uow:
        users = await uow.users.list_users(status=UserStatusFilter.ALL, limit=100)

    refs = await admin.resolve_user_refs.execute([u.id for u in users])

    assert {r.name: r.role for r in refs.values()} == {"이탈자": Role.SALES, "boss": Role.ADMIN}


async def test_resolve_user_refs_returns_active_and_resigned_users_in_one_mapping(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)
    async with uow_factory() as uow:
        users = await uow.users.list_users(status=UserStatusFilter.ALL, limit=100)
    ids = [u.id for u in users]

    refs = await admin.resolve_user_refs.execute(ids)

    assert {r.label for r in refs.values()} == {"홍길동", "이탈자(퇴사)"}
    assert set(refs) == set(ids)


async def test_resolve_user_refs_skips_unknown_ids_and_accepts_empty_input(
    admin: AdminStack,
) -> None:
    assert dict(await admin.resolve_user_refs.execute([])) == {}
    assert dict(await admin.resolve_user_refs.execute([UserId(new_id())])) == {}
