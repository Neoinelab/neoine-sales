"""DELETE /deals/{code}: 완료된 Deal을 admin이 아닌 Owner가 지우면 403 forbidden(DD-R41)."""

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.deal_detail_http import BASE, CODE, clients, problem, seed, stored_deal_codes

COMPLETED = "완료된 Deal은 관리자만 삭제할 수 있습니다."
WON = {"status_key": "contract_completed", "forecast_key": "won"}


async def test_the_owner_sales_user_gets_a_403_forbidden_for_a_completed_deal() -> None:
    """Owner 영업이 완료된 Deal을 지우면 code와 무관하게 403 forbidden 완료 문구다.

    테스트 코드: DD-118
    """
    # given: owner가 Owner인 Won Deal
    use_cases = FakeUseCases()
    await seed(use_cases, **WON)

    # when: owner가 틀린 code와 맞는 code로 각각 지운다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        wrong = await c["owner"].delete(f"{BASE}/{CODE}", params={"confirm_code": "wrong"})
        right = await c["owner"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 둘 다 403 forbidden 완료 문구이고 Deal은 남는다
    for response in (wrong, right):
        assert problem(response, 403, "forbidden")["detail"] == COMPLETED
    assert stored_deal_codes(use_cases) == {CODE}


async def test_an_admin_deletes_a_completed_deal_with_204() -> None:
    """admin은 완료된 Deal도 204로 지운다.

    테스트 코드: DD-119
    """
    # given: owner가 Owner인 Won Deal
    use_cases = FakeUseCases()
    await seed(use_cases, **WON)

    # when: admin이 정확한 code로 지운다
    async with clients(use_cases, {"boss": Role.ADMIN}) as c:
        response = await c["boss"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 204이고 Deal이 없다
    assert response.status_code == 204
    assert stored_deal_codes(use_cases) == set()


async def test_the_owner_sales_user_deletes_a_lost_deal_with_204() -> None:
    """Owner 영업은 Lost Deal을 204로 지운다.

    테스트 코드: DD-120
    """
    # given: owner가 Owner인 Lost Deal
    use_cases = FakeUseCases()
    await seed(use_cases, status_key="price_negotiation", forecast_key="lost")

    # when: owner가 정확한 code로 지운다
    async with clients(use_cases, {"owner": Role.SALES}) as c:
        response = await c["owner"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 204이고 Deal이 없다
    assert response.status_code == 204
    assert stored_deal_codes(use_cases) == set()


async def test_another_sales_user_gets_the_owner_403_for_a_completed_deal() -> None:
    """다른 영업이 완료된 Deal을 지우면 Owner 문구 403이다.

    테스트 코드: DD-121
    """
    # given: owner가 Owner인 Won Deal과 다른 영업
    use_cases = FakeUseCases()
    await seed(use_cases, **WON)

    # when: other가 정확한 code로 지운다
    async with clients(use_cases, {"other": Role.SALES}) as c:
        response = await c["other"].delete(f"{BASE}/{CODE}", params={"confirm_code": CODE})

    # then: 403 forbidden "본인 Deal 또는 admin만" 문구이고 Deal은 남는다
    assert (
        problem(response, 403, "forbidden")["detail"]
        == "본인 Deal 또는 admin만 삭제할 수 있습니다."
    )
    assert stored_deal_codes(use_cases) == {CODE}
