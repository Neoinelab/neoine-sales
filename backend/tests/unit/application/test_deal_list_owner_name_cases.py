"""Deal 목록(DL) BDD 케이스 — 담당자 이름 검색(`owner_name`, DL-R39).

유스케이스 `ListDeals`를 When으로 부르고 Deal·사용자·연락처 저장소는 모두 Fake UoW다.
HTTP 수준 검증(422 kind·mine·내보내기)은 `unit/web/test_deal_list_http_cases.py`가 본다.
케이스 정의: docs/features/deal-list.md 4절(DL-129~DL-134).
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW
from tests.factories_auth import make_resigned_user, make_user
from tests.factories_deal import seed_deal

if TYPE_CHECKING:
    from app.application.deal.dto import DealPage
    from app.domain.user.entities import User
    from tests.unit.application.deal_env import DealEnv
FULL_L, FULL_R = chr(0xFF08), chr(0xFF09)  # 전각 괄호


def _codes(page: DealPage) -> set[str]:
    return {view.item.deal.id.value for view in page.items}


async def _owner(  # noqa: PLR0913 - 담당자 준비에 필요한 독립 값
    env: DealEnv,
    code: str,
    login: str,
    display_name: str | None = None,
    *,
    role: Role = Role.SALES,
    resigned: bool = False,
) -> User:
    """담당자를 저장소에 두고 그 사람의 Deal 한 건(code)을 직접 넣는다."""
    user = (
        make_resigned_user(login, role, display_name=display_name)
        if resigned
        else make_user(login, role, display_name=display_name)
    )
    await env.uow.users.add(user)
    await seed_deal(env.uow, code=code, owner_user_id=user.id, now=NOW)
    return user


async def _owner_name(env: DealEnv, text: str) -> set[str]:
    return _codes(await env.list.execute(DealQuery(owner_name=text)))


async def test_owner_name_matches_active_owners_by_partial_name_and_not_resigned_by_part(
    env: DealEnv,
) -> None:
    """owner_name은 재직 담당자 이름의 부분 일치(대소문자 무시)이고 퇴사자는 부분 일치로 안 걸린다.

    테스트 코드: DL-129
    """
    # given: 재직 sales 김영업·박영업·Alice의 Deal 각 1건, 퇴사한 강영업의 Deal 1건
    await _owner(env, "20261120-K001", "kim", "김영업")
    await _owner(env, "20261120-P001", "park", "박영업")
    await _owner(env, "20261120-A001", "alice", "Alice")
    await _owner(env, "20261120-R001", "kang", "강영업", resigned=True)
    # when: 영업·ALI·강영·강영업으로 각각 조회한다
    by_part = await _owner_name(env, "영업")
    by_upper = await _owner_name(env, "ALI")
    by_resigned_part = await _owner_name(env, "강영")
    by_resigned_full = await _owner_name(env, "강영업")
    # then: 영업은 김영업·박영업(강영업 제외), ALI는 Alice, 퇴사자는 (퇴사) 없이 0건이다
    assert by_part == {"20261120-K001", "20261120-P001"}
    assert by_upper == {"20261120-A001"}
    assert by_resigned_part == set()
    assert by_resigned_full == set()


async def test_resigned_owner_matches_only_the_exact_name_with_the_suffix_for_every_namesake(
    env: DealEnv,
) -> None:
    """ "이름(퇴사)"는 그 이름의 퇴사자 Deal(동명 모두)이고 덜 친·띄어 쓴 값은 맞지 않는다.

    테스트 코드: DL-130
    """
    # given: 퇴사한 강영업 두 명(서로 다른 사용자)과 Bob의 Deal, 재직 김영업의 Deal
    await _owner(env, "20261120-R001", "kang1", "강영업", resigned=True)
    await _owner(env, "20261120-R002", "kang2", "강영업", resigned=True)
    await _owner(env, "20261120-B001", "bob", "Bob", resigned=True)
    await _owner(env, "20261120-K001", "kim", "김영업")
    # when: 정확한 값·앞뒤 공백·대소문자만 다른 값과, 덜 친·띄어 쓴·전각·일부 값으로 각각 조회한다
    exact = await _owner_name(env, "강영업(퇴사)")
    bob = await _owner_name(env, " bob(퇴사) ")
    misses = [
        await _owner_name(env, text)
        for text in ("강영업(퇴", "강영업 (퇴사)", f"강영업{FULL_L}퇴사{FULL_R}", "영업(퇴사)")
    ]
    # then: 정확한 값은 동명 두 퇴사자 Deal, bob은 Bob Deal이고 나머지는 모두 0건이다(김영업도 제외)
    assert exact == {"20261120-R001", "20261120-R002"}
    assert bob == {"20261120-B001"}
    assert misses == [set(), set(), set(), set()]


async def test_several_matching_owners_are_ored_and_no_match_is_an_empty_page(
    env: DealEnv,
) -> None:
    """맞는 재직 담당자가 여럿이면 모두의 Deal이고 맞는 사람이 없으면 오류 없이 0건이다.

    테스트 코드: DL-131
    """
    # given: 재직 sales 이영업 두 명과 이영업2의 Deal 각 1건
    await _owner(env, "20261120-L001", "lee1", "이영업")
    await _owner(env, "20261120-L002", "lee2", "이영업")
    await _owner(env, "20261120-L003", "lee3", "이영업2")
    # when: 이영업과 최로 조회한다
    several = await env.list.execute(DealQuery(owner_name="이영업"))
    none = await env.list.execute(DealQuery(owner_name="최"))
    # then: 이영업은 세 사람의 Deal 3건·total 3, 최는 items [] total 0이다
    assert _codes(several) == {"20261120-L001", "20261120-L002", "20261120-L003"}
    assert several.total == 3
    assert (none.items, none.total) == ([], 0)


async def test_owner_name_compares_the_screen_name_only_and_ignores_the_role(
    env: DealEnv,
) -> None:
    """owner_name은 화면 이름으로만 비교하고(아이디로 찾지 않음) 역할이 바뀐 재직 Owner도 걸린다.

    테스트 코드: DL-132
    """
    # given: 표시 이름 없는 carol, 표시 이름 홍길동·아이디 hong, 역할이 admin으로 바뀐 재직 정관리
    await _owner(env, "20261120-C001", "carol")
    await _owner(env, "20261120-H001", "hong", "홍길동")
    await _owner(env, "20261120-J001", "jung", "정관리", role=Role.ADMIN)
    # when: car·hong·정관으로 각각 조회한다
    by_login_fallback = await _owner_name(env, "car")
    by_login_with_name = await _owner_name(env, "hong")
    by_admin_name = await _owner_name(env, "정관")
    # then: car는 carol(아이디가 화면 이름), hong은 0건(표시 이름이 있으면 아이디로 못 찾음)
    # then: 정관은 역할이 바뀐 정관리다
    assert by_login_fallback == {"20261120-C001"}
    assert by_login_with_name == set()
    assert by_admin_name == {"20261120-J001"}


async def test_owner_name_text_is_trimmed_blank_is_no_condition_and_wildcards_are_literal(
    env: DealEnv,
) -> None:
    """owner_name은 트림·공백뿐 없음·%·_는 글자 그대로이고 100자는 되며 101자·NUL은 오류다.

    테스트 코드: DL-133
    """
    # given: 재직 김_영%와 김영업의 Deal
    await _owner(env, "20261120-W001", "wild", "김_영%")
    await _owner(env, "20261120-K001", "kim", "김영업")
    # when: 앞뒤 공백·공백뿐·와일드카드 글자·100자로 각각 조회한다
    trimmed = await _owner_name(env, "  김_  ")
    blank = await _owner_name(env, "   ")
    literal = await _owner_name(env, "_영%")
    hundred = await _owner_name(env, "가" * 100)
    # then: 공백은 지우고 `_`는 글자이며 공백뿐은 조건 없음(2건), 100자는 0건이다
    assert trimmed == {"20261120-W001"}
    assert blank == {"20261120-W001", "20261120-K001"}
    assert literal == {"20261120-W001"}
    assert hundred == set()
    # when·then: 101자·NUL은 DealQuery를 만들 때 거절된다
    for bad in ("가" * 101, "a\x00b"):
        with pytest.raises(InvalidValueError):
            DealQuery(owner_name=bad)


async def test_owner_name_is_anded_with_other_conditions(env: DealEnv) -> None:
    """owner_name은 다른 조건과 AND이다.

    테스트 코드: DL-134
    """
    # given: 김영업의 Deal은 prospecting, 박영업의 Deal은 introduction
    await _owner(env, "20261120-K001", "kim", "김영업")
    park = make_user("park", Role.SALES, display_name="박영업")
    await env.uow.users.add(park)
    await seed_deal(
        env.uow, code="20261120-P001", owner_user_id=park.id, status_key="introduction", now=NOW
    )
    # when: 영업과 김영업 Deal의 Status로 조회한다
    page = await env.list.execute(DealQuery(owner_name="영업", status_key="prospecting"))
    # then: 두 조건을 모두 만족하는 김영업 Deal만이다
    assert _codes(page) == {"20261120-K001"}
    assert page.total == 1
