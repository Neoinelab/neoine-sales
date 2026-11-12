"""사용자 선택 목록 API(`GET /api/v1/user-options`)의 HTTP 계약: 역할 권한·응답 키·쿼리 검증.

FakeUseCases 위에서 라우터와 스키마를 확인한다(DB 없음). 조건별 선택 규칙은
`unit/application/test_user_options.py`가 맡는다.
"""

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.vendor_http import client_for, problem

OPTIONS = "/api/v1/user-options"
OPTION_KEYS = {"id", "name", "resigned", "label", "role"}


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_signed_in_role_reads_the_user_options(role: Role) -> None:
    """모든 역할이 사용자 선택 목록을 읽는다.

    테스트 코드: US-068
    """
    # given: 재직 사용자 kim과 해당 역할로 로그인한 요청자
    use_cases = FakeUseCases()
    await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases, role=role) as http:
        # when: 선택 목록을 읽는다
        response = await http.get(OPTIONS)

    # then: 200이고 kim이 들어 있다
    assert response.status_code == 200, response.text
    assert "kim" in [item["name"] for item in response.json()["items"]]


async def test_option_items_carry_only_id_name_resigned_label_and_role() -> None:
    """선택 목록 항목은 id·name·resigned·label·role만 담고 이메일·아이디가 없다.

    테스트 코드: US-069
    """
    # given: 표시 이름이 있는 사용자(아이디 kim, 이름 김영업)
    use_cases = FakeUseCases()
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    async with client_for(use_cases) as http:
        # when: 선택 목록을 읽는다
        response = await http.get(OPTIONS)

    # then: 모든 항목의 키가 다섯 개뿐이고 표시 이름이 있는 사용자의 아이디 값은 어디에도 없다
    items = response.json()["items"]
    assert all(set(item) == OPTION_KEYS for item in items)
    kim = next(item for item in items if item["name"] == "김영업")
    assert kim["role"] == "sales"
    assert '"kim"' not in response.text
    assert "email" not in response.text


async def test_options_hide_resigned_users_unless_include_resigned_is_true() -> None:
    """선택 목록은 기본이 재직자이고 include_resigned=true면 퇴사자를 (퇴사) 라벨로 더한다.

    테스트 코드: US-070
    """
    # given: 재직 kim과 퇴사한 gone
    use_cases = FakeUseCases()
    await use_cases.seed_user("kim", Role.SALES, display_name="김영업")
    gone = await use_cases.seed_user("gone", Role.SALES, display_name="이탈자")
    await use_cases.resign_user(gone.id)
    async with client_for(use_cases) as http:
        # when: 조건 없이, 그리고 include_resigned=true로 읽는다
        default = await http.get(OPTIONS)
        with_resigned = await http.get(f"{OPTIONS}?include_resigned=true")

    # then: 기본에는 퇴사자가 없고, 더하면 이름(퇴사) 라벨로 나온다
    assert "이탈자" not in [item["name"] for item in default.json()["items"]]
    labels = {item["name"]: item["label"] for item in with_resigned.json()["items"]}
    assert labels["이탈자"] == "이탈자(퇴사)"
    assert labels["김영업"] == "김영업"


async def test_options_filter_by_keyword_and_role_over_http() -> None:
    """keyword는 화면 이름을 대소문자 무시로 찾고 role 필터와 함께 쓸 수 있다.

    테스트 코드: US-071, US-072
    """
    # given: 이름이 비슷한 sales 둘과 user 하나
    use_cases = FakeUseCases()
    await use_cases.seed_user("a", Role.SALES, display_name="Kim 영업")
    await use_cases.seed_user("b", Role.USER, display_name="Kim 조회")
    await use_cases.seed_user("c", Role.SALES, display_name="이영업")
    async with client_for(use_cases) as http:
        # when: 소문자 keyword만, 그리고 role=sales와 함께 읽는다
        by_keyword = await http.get(f"{OPTIONS}?keyword=kim")
        by_both = await http.get(f"{OPTIONS}?keyword=kim&role=sales")

    # then: keyword는 이름이 맞는 둘을, 함께 쓰면 sales 한 명만 돌려준다
    assert [i["name"] for i in by_keyword.json()["items"]] == ["Kim 영업", "Kim 조회"]
    assert [i["name"] for i in by_both.json()["items"]] == ["Kim 영업"]


@pytest.mark.parametrize(
    "query",
    [
        "limit=3",
        "offset=0",
        "bogus=1",
        "role=boss",
        "include_resigned=maybe",
        f"keyword={'a' * 101}",
    ],
)
async def test_options_with_an_invalid_or_unknown_parameter_are_422(query: str) -> None:
    """선택 목록의 잘못된 파라미터·모르는 파라미터(limit·offset 포함)는 422 request-validation이다.

    테스트 코드: US-074
    """
    # given: 로그인한 요청자
    async with client_for(FakeUseCases(), role=Role.USER) as http:
        # when: 틀린 쿼리로 읽는다
        response = await http.get(f"{OPTIONS}?{query}")

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")
