"""Deal 목록 열 정렬 feature의 step: 담당자·고객·파트너·Vendor·Forecast가 서로 다른 Deal을 만든다.

Given은 공개 API로 Deal을 만들고(이름이 대소문자 섞여 소문자 기준과 원문 기준이 달라진다),
When은 `steps/deals.py`의 목록 조회 하나, Then은 응답의 code 순서만 본다.
"""

from typing import TYPE_CHECKING

from tests.functional.steps.auth import given_user_registered
from tests.functional.steps.deals import customer_draft, given_deal, partner_draft
from tests.functional.steps.vendors import given_vendor

if TYPE_CHECKING:
    from tests.functional.conftest import Api

# 번호 1~3의 오름차순 결과가 열마다 다르다. 소문자 기준: 고객 alpha < Bravo < charlie.
OWNERS = {1: "so-bob", 2: "so-carol", 3: "so-alice"}  # 표시 이름은 "사용자 <아이디>"
CUSTOMERS = {1: "Bravo", 2: "alpha", 3: "charlie"}
PARTNERS = {1: "delta", 2: "Echo", 3: "Charlie"}
VENDORS = {1: "ZZ beta", 2: "ZZ Gamma", 3: "ZZ alpha"}
FORECASTS = {1: "commit", 2: "pipeline", 3: "best"}
ASCENDING_NUMBERS = {
    "owner": [3, 1, 2],
    "customer": [2, 1, 3],
    "partner": [3, 1, 2],
    "vendor": [3, 1, 2],
    "forecast": [2, 3, 1],
}


async def given_three_deals_with_different_columns(api: Api) -> list[str]:
    """담당자·고객·파트너·Vendor·Forecast가 모두 다른 Deal 3건(번호 순서로 등록). code 목록."""
    owner_ids = {
        number: await given_user_registered(api, login_id=login, role="sales")
        for number, login in OWNERS.items()
    }
    vendor_ids = {}
    for number, name in VENDORS.items():
        vendor_ids[number] = (await given_vendor(api, name)).id
    codes = []
    for number in (1, 2, 3):
        deal = await given_deal(
            api,
            name=f"딜 {number}",
            owner_user_id=owner_ids[number],
            customer=customer_draft(company=CUSTOMERS[number]),
            partner=partner_draft(company=PARTNERS[number]),
            vendor_id=vendor_ids[number],
            forecast_key=FORECASTS[number],
        )
        codes.append(str(deal["code"]))
    return codes


async def given_two_deals_without_partner_or_vendor(api: Api) -> list[str]:
    """번호 1·3은 파트너·Vendor가 있고 2·4는 없는 Deal 4건. code 목록(번호 순서)."""
    owner = await given_user_registered(api, login_id="so-owner", role="sales")
    vendor_ids = {
        1: (await given_vendor(api, "ZZ bravo")).id,
        3: (await given_vendor(api, "ZZ alpha")).id,
    }
    partners = {1: "bravo", 3: "alpha"}
    codes = []
    for number in (1, 2, 3, 4):
        deal = await given_deal(
            api,
            name=f"딜 {number}",
            owner_user_id=owner,
            partner=partner_draft(company=partners[number]) if number in partners else None,
            vendor_id=vendor_ids.get(number),
        )
        codes.append(str(deal["code"]))
    return codes
