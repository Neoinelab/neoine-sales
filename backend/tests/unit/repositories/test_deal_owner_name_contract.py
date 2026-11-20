"""DealRepository.search/count의 owner_name(DL-R39) 계약: Fake와 SQL(PostgreSQL)에 같은 기대값.

비교 대상은 담당자의 화면 이름(표시 이름, 없으면 login_id)이다. 재직자는 대소문자 무시 부분 일치
(`%`·`_`는 글자 그대로, 역할 무관), 퇴사자는 `이름(퇴사)` 전체가 같을 때만 맞는다(동명 모두).
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.auth.principal import Role
from tests.factories import later, make_deal
from tests.factories_auth import make_user
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId
    from tests.unit.repositories.deal_case import DealCase

FULL_L, FULL_R = chr(0xFF08), chr(0xFF09)  # 전각 괄호


async def _owner(
    case: DealCase, login: str, display: str | None, code: str, role: Role = Role.SALES
) -> UserId:
    """담당자를 저장하고 그 사람의 Deal 한 건을 넣는다."""
    user_id = uid(login)
    await case.users.add(make_user(login, role, entity_id=user_id, display_name=display))
    await case.add(make_deal(later(1), code=code, owner_user_id=user_id))
    return user_id


async def _by_name(case: DealCase, text: str) -> list[str]:
    found = await case.deals.search(DealQuery(owner_name=text))
    return sorted(item.deal.id.value for item in found)


async def test_active_owner_matches_by_case_insensitive_partial_screen_name(
    deal_case: DealCase,
) -> None:
    """재직 담당자는 화면 이름의 대소문자 무시 부분 일치로 걸리고 total도 같다."""
    # given: 김영업·박영업·Alice(재직)와 퇴사한 강영업의 Deal
    await _owner(deal_case, "on_kim", "김영업", "20261016-K001")
    await _owner(deal_case, "on_park", "박영업", "20261016-P001")
    await _owner(deal_case, "on_alice", "Alice", "20261016-A001")
    kang = await _owner(deal_case, "on_kang", "강영업", "20261016-R001")
    await deal_case.resign(kang, later(30))

    # when: 영업·ALI·강영으로 검색한다
    by_part = await _by_name(deal_case, "영업")
    by_upper = await _by_name(deal_case, "ALI")
    by_resigned_part = await _by_name(deal_case, "강영")
    total = await deal_case.deals.count(DealQuery(owner_name="영업"))

    # then: 재직자만 걸리고 퇴사자는 부분 일치로 안 걸린다
    assert by_part == ["20261016-K001", "20261016-P001"]
    assert by_upper == ["20261016-A001"]
    assert by_resigned_part == []
    assert total == 2


async def test_resigned_owner_matches_only_the_exact_name_with_the_suffix(
    deal_case: DealCase,
) -> None:
    """퇴사자는 "이름(퇴사)" 정확 일치(동명 모두, 대소문자 무시)일 때만 걸린다."""
    # given: 퇴사한 강영업 둘·Bob과 재직 김영업의 Deal
    for login, display, code in (
        ("on_k1", "강영업", "20261016-R001"),
        ("on_k2", "강영업", "20261016-R002"),
        ("on_bob", "Bob", "20261016-B001"),
    ):
        owner = await _owner(deal_case, login, display, code)
        await deal_case.resign(owner, later(30))
    await _owner(deal_case, "on_kim", "김영업", "20261016-K001")

    # when: 정확한 값·대소문자 다른 값과 덜 친·띄어 쓴·전각·일부 값으로 검색한다
    exact = await _by_name(deal_case, "강영업(퇴사)")
    bob = await _by_name(deal_case, "bob(퇴사)")
    misses = [
        await _by_name(deal_case, text)
        for text in ("강영업(퇴", "강영업 (퇴사)", f"강영업{FULL_L}퇴사{FULL_R}", "영업(퇴사)")
    ]

    # then: 동명 모두 걸리고 나머지는 0건이다
    assert exact == ["20261016-R001", "20261016-R002"]
    assert bob == ["20261016-B001"]
    assert misses == [[], [], [], []]


async def test_screen_name_falls_back_to_the_login_id_only_without_a_display_name(
    deal_case: DealCase,
) -> None:
    """표시 이름이 있으면 아이디로 찾지 않고, 없으면 아이디가 화면 이름이다. 역할은 보지 않는다."""
    # given: 표시 이름 없는 carol, 표시 이름 홍길동(아이디 hong), 역할이 admin인 정관리
    await _owner(deal_case, "on_carol", None, "20261016-C001")
    await _owner(deal_case, "on_hong", "홍길동", "20261016-H001")
    await _owner(deal_case, "on_jung", "정관리", "20261016-J001", Role.ADMIN)

    # when: 아이디 일부·표시 이름이 있는 사용자의 아이디·admin 이름으로 검색한다
    by_login = await _by_name(deal_case, "on_car")
    by_hidden_login = await _by_name(deal_case, "on_hong")
    by_admin = await _by_name(deal_case, "정관")

    # then: 표시 이름 없는 사용자만 아이디로 걸리고 역할과 무관하게 이름으로 걸린다
    assert by_login == ["20261016-C001"]
    assert by_hidden_login == []
    assert by_admin == ["20261016-J001"]


async def test_wildcard_characters_are_literal_and_no_match_is_empty(deal_case: DealCase) -> None:
    """%·_는 글자 그대로이고 맞는 담당자가 없으면 0건이다."""
    # given: 김_영%와 김영업의 Deal
    await _owner(deal_case, "on_wild", "김_영%", "20261016-W001")
    await _owner(deal_case, "on_plain", "김영업", "20261016-K001")

    # when: 와일드카드 글자·없는 이름으로 검색한다
    underscore = await _by_name(deal_case, "김_")
    percent = await _by_name(deal_case, "영%")
    nobody = await _by_name(deal_case, "최")

    # then: 글자가 든 담당자만 걸리고 없는 이름은 0건이다
    assert underscore == ["20261016-W001"]
    assert percent == ["20261016-W001"]
    assert nobody == []
