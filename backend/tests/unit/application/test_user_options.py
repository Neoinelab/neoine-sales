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
        stored.record_login(later(n), display_name=name, email=f"{login}@corp.test", phone=None)
        if kw.get("resigned"):
            stored.resign(later(n + 100))
        await uow.users.update(stored)
        await uow.commit()


async def test_options_default_to_active_users_with_labels(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """선택 목록은 기본이 재직자이고 표시 이름을 가진다

    테스트 코드: US-070
    """
    # given: 재직 hong과 퇴사 gone
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)

    # when: 기본 조건으로 읽는다
    options = await admin.list_user_options.execute()

    # then: 재직자 하나만 이름·라벨과 함께 나온다
    assert [(o.name, o.resigned, o.label) for o in options] == [("홍길동", False, "홍길동")]


async def test_options_include_resigned_users_with_the_resigned_label(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """include_resigned면 퇴사자를 (퇴사) 라벨로 더한다

    테스트 코드: US-070
    """
    # given: 재직 hong과 퇴사 gone
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)

    # when: include_resigned로 읽는다
    options = await admin.list_user_options.execute(include_resigned=True)

    # then: 퇴사자가 이름(퇴사) 라벨로 더해진다
    assert [(o.name, o.resigned, o.label) for o in options] == [
        ("홍길동", False, "홍길동"),
        ("이탈자", True, "이탈자(퇴사)"),
    ]


async def test_options_keyword_matches_the_display_name_ignoring_case(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """keyword는 화면 이름을 대소문자 무시로 찾는다

    테스트 코드: US-071
    """
    # given: 이름이 다른 사용자 셋
    await _named(uow_factory, "hong.gd", "홍길동", 1)
    await _named(uow_factory, "kim", "김영업", 2)
    await _named(uow_factory, "lee", "이HONG", 3)

    # when: 한글·영문 키워드로 읽는다
    by_korean = await admin.list_user_options.execute(keyword="영업")
    # then: 이름이 맞는 사용자만 나오고 아이디만 맞는 사용자는 빠진다
    by_latin = await admin.list_user_options.execute(keyword="hong")

    assert [o.name for o in by_korean] == ["김영업"]
    assert [o.name for o in by_latin] == ["이HONG"]  # hong.gd는 아이디일 뿐 이름이 아니다


async def test_options_keyword_does_not_match_the_login_id_of_a_user_with_a_display_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """표시 이름이 있는 사용자는 아이디로 찾아지지 않는다

    테스트 코드: US-071
    """
    # given: 표시 이름이 있는 hong.gd
    await _named(uow_factory, "hong.gd", "홍길동", 1)

    # when: 아이디로 검색한다
    actual = list(await admin.list_user_options.execute(keyword="hong.gd"))
    # then: 결과가 없다
    assert actual == []
    assert list(await admin.list_user_options.execute(keyword="HONG")) == []


async def test_options_keyword_matches_the_login_id_only_as_the_fallback_name(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """표시 이름이 없는 사용자는 아이디가 이름이라 아이디로 찾아진다

    테스트 코드: US-071
    """
    # given: 로그인 전 newbie
    await seed_user(uow_factory, "newbie", Role.USER)  # 로그인 전: 표시 이름 없음, name == login_id

    # when: 아이디 일부로 검색한다
    options = await admin.list_user_options.execute(keyword="NEWB")

    # then: newbie가 나온다
    assert [o.name for o in options] == ["newbie"]


async def test_options_carry_the_login_id_of_each_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """선택 목록 항목은 login_id를 가진다(이름과 다를 수 있다)

    테스트 코드: US-069
    """
    # given: 이름이 있는 hong
    await _named(uow_factory, "hong", "홍길동", 1)

    # when: 읽는다
    (option,) = await admin.list_user_options.execute()

    # then: 이름은 표시 이름이고 login_id는 아이디다
    assert (option.name, option.login_id) == ("홍길동", "hong")


async def test_options_name_falls_back_to_login_id_before_first_login(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """로그인 전 사용자의 이름과 라벨은 아이디다

    테스트 코드: US-069
    """
    # given: 로그인 전 newbie
    await seed_user(uow_factory, "newbie", Role.USER)

    # when: 읽는다
    (option,) = await admin.list_user_options.execute()

    # then: 이름·라벨이 아이디다
    assert (option.name, option.label) == ("newbie", "newbie")


async def test_options_always_carry_login_id_for_every_role_and_resigned_users(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """선택 목록은 재직·퇴사·모든 역할 항목에 login_id를 항상 준다

    테스트 코드: US-115
    """
    # given: 같은 이름의 재직 sales kim1·kim2, admin root, 이름 없는 user lee, 퇴사 sales old
    await _named(uow_factory, "kim1", "김영업", 1)
    await _named(uow_factory, "kim2", "김영업", 2)
    root = await seed_user(uow_factory, "root", Role.ADMIN, now=later(3))
    await seed_user(uow_factory, "lee", Role.USER, now=later(4))
    await _named(uow_factory, "old", "박영업", 5, resigned=True)
    async with uow_factory() as uow:
        stored = await uow.users.get(root.id)
        stored.record_login(later(3), display_name="관리자", email=None, phone=None)
        await uow.users.update(stored)
        await uow.commit()

    # when: 조건 없이, include_resigned로 읽는다
    active = await admin.list_user_options.execute()
    with_resigned = await admin.list_user_options.execute(include_resigned=True)

    # then: 재직자 네 명의 login_id가 있고, 퇴사자도 login_id와 (퇴사) 라벨을 가진다
    assert [(o.login_id, o.name) for o in active] == [
        ("kim1", "김영업"),
        ("kim2", "김영업"),
        ("root", "관리자"),
        ("lee", "lee"),
    ]
    old = with_resigned[-1]
    assert (old.login_id, old.label) == ("old", "박영업(퇴사)")


async def test_options_keyword_does_not_find_users_by_login_id_even_though_it_is_returned(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """keyword는 login_id를 내려줘도 표시 이름이 있는 사용자를 아이디로 찾지 않는다

    테스트 코드: US-115
    """
    # given: 표시 이름이 "김영업"인 kim1·kim2
    await _named(uow_factory, "kim1", "김영업", 1)
    await _named(uow_factory, "kim2", "김영업", 2)

    # when: 아이디 일부로 검색한다
    options = await admin.list_user_options.execute(keyword="kim")

    # then: 0건이다
    assert list(options) == []


async def test_options_return_every_matching_user_beyond_the_old_200_cap(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """선택 목록은 페이지 없이 조건에 맞는 사용자를 전부 돌려준다

    테스트 코드: US-073
    """
    # given: 사용자 205명
    for n in range(1, 206):
        await _named(uow_factory, f"user{n}", f"사용자{n:03d}", n)

    # when: 읽는다
    options = await admin.list_user_options.execute()

    # then: 205명 전부가 순서대로 나온다
    assert len(options) == 205
    assert [o.name for o in options][:2] == ["사용자001", "사용자002"]
    assert options[-1].name == "사용자205"


async def test_options_no_longer_accept_a_limit(admin: AdminStack) -> None:
    """선택 목록은 limit 인자를 받지 않는다

    테스트 코드: US-074
    """
    # when: limit을 주고 읽는다
    with pytest.raises(TypeError):
        await admin.list_user_options.execute(limit=3)  # type: ignore[call-arg]
    # then: 인자 오류다


async def test_options_expose_no_email(admin: AdminStack, uow_factory: UnitOfWorkFactory) -> None:
    """선택 목록 항목에는 이메일이 없다

    테스트 코드: US-069
    """
    # given: 이메일이 있는 hong
    await _named(uow_factory, "hong", "홍길동", 1)

    # when: 읽는다
    (option,) = await admin.list_user_options.execute()

    # then: 항목에 email이 없다
    assert not hasattr(option, "email")


async def test_options_carry_the_role_of_each_user(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """선택 목록 항목은 각 사용자의 역할을 가진다

    테스트 코드: US-069
    """
    # given: 역할이 다른 사용자 셋
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await seed_user(uow_factory, "sales1", Role.SALES, now=later(2))
    await seed_user(uow_factory, "viewer", Role.USER, now=later(3))

    # when: 읽는다
    options = await admin.list_user_options.execute()

    # then: 이름과 역할이 등록 순서로 나온다
    assert [(o.name, o.role) for o in options] == [
        ("boss", Role.ADMIN),
        ("sales1", Role.SALES),
        ("viewer", Role.USER),
    ]


async def test_options_filter_by_role_returns_only_active_users_of_that_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """role 필터는 그 역할의 재직자만 돌려준다

    테스트 코드: US-072
    """
    # given: 역할이 섞인 재직자와 퇴사자
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await _named(uow_factory, "kim", "김영업", 2)
    await seed_user(uow_factory, "viewer", Role.USER, now=later(3))
    await _named(uow_factory, "gone", "이탈자", 4, resigned=True)

    # when: sales로 필터해 읽는다
    options = await admin.list_user_options.execute(role=Role.SALES)

    # then: 재직 sales만 나온다
    assert [(o.name, o.role, o.resigned) for o in options] == [("김영업", Role.SALES, False)]


async def test_options_filter_by_role_with_resigned_includes_resigned_users_of_that_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """role 필터는 include_resigned와 함께 쓸 수 있다

    테스트 코드: US-072
    """
    # given: 재직·퇴사 sales와 user
    await _named(uow_factory, "kim", "김영업", 1)
    await seed_user(uow_factory, "viewer", Role.USER, now=later(2))
    await _named(uow_factory, "gone", "이탈자", 3, resigned=True)

    # when: sales와 include_resigned로 읽는다
    options = await admin.list_user_options.execute(role=Role.SALES, include_resigned=True)

    # then: sales의 재직자와 퇴사자가 나온다
    assert [(o.name, o.resigned) for o in options] == [("김영업", False), ("이탈자", True)]


async def test_options_without_role_keep_returning_every_role(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """role을 주지 않으면 모든 역할이 나온다

    테스트 코드: US-072
    """
    # given: admin과 sales
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(1))
    await _named(uow_factory, "kim", "김영업", 2)

    # when: role 없이 읽는다
    options = await admin.list_user_options.execute()

    # then: 두 사람 모두 나온다
    assert [o.name for o in options] == ["boss", "김영업"]


async def test_options_filter_by_role_combines_with_keyword(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """role 필터는 keyword와 함께 쓸 수 있다

    테스트 코드: US-072
    """
    # given: 이름이 같은 접두의 sales 셋과 user
    await _named(uow_factory, "a", "김하나", 1)
    await _named(uow_factory, "b", "김둘", 2)
    await _named(uow_factory, "c", "김셋", 3)
    await seed_user(uow_factory, "kimv", Role.USER, now=later(4))

    # when: sales와 keyword로 읽는다
    options = await admin.list_user_options.execute(role=Role.SALES, keyword="김")

    # then: 키워드에 맞는 sales만 나온다
    assert [o.name for o in options] == ["김하나", "김둘", "김셋"]


async def test_resolve_user_refs_carries_the_role_including_resigned_users(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """사용자 참조 해석은 퇴사자 포함 역할을 가진다"""
    # given: 퇴사한 sales와 admin
    await _named(uow_factory, "gone", "이탈자", 1, resigned=True)
    await seed_user(uow_factory, "boss", Role.ADMIN, now=later(2))
    async with uow_factory() as uow:
        users = await uow.users.list_users(status=UserStatusFilter.ALL, limit=100)

    # when: id들을 해석한다
    refs = await admin.resolve_user_refs.execute([u.id for u in users])

    # then: 이름별 역할이 맞다
    assert {r.name: r.role for r in refs.values()} == {"이탈자": Role.SALES, "boss": Role.ADMIN}


async def test_resolve_user_refs_returns_active_and_resigned_users_in_one_mapping(
    admin: AdminStack, uow_factory: UnitOfWorkFactory
) -> None:
    """사용자 참조 해석은 재직자와 퇴사자를 한 번에 돌려준다"""
    # given: 재직 hong과 퇴사 gone
    await _named(uow_factory, "hong", "홍길동", 1)
    await _named(uow_factory, "gone", "이탈자", 2, resigned=True)
    async with uow_factory() as uow:
        users = await uow.users.list_users(status=UserStatusFilter.ALL, limit=100)
    ids = [u.id for u in users]

    # when: id들을 해석한다
    refs = await admin.resolve_user_refs.execute(ids)

    # then: 라벨에 (퇴사)가 구분되고 모든 id가 있다
    assert {r.label for r in refs.values()} == {"홍길동", "이탈자(퇴사)"}
    assert set(refs) == set(ids)


async def test_resolve_user_refs_skips_unknown_ids_and_accepts_empty_input(
    admin: AdminStack,
) -> None:
    """사용자 참조 해석은 모르는 id를 건너뛰고 빈 입력을 받는다"""
    # when: 빈 목록과 모르는 id를 해석한다
    actual = dict(await admin.resolve_user_refs.execute([]))
    # then: 빈 결과다
    assert actual == {}
    assert dict(await admin.resolve_user_refs.execute([UserId(new_id())])) == {}
