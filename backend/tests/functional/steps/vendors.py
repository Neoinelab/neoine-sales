"""Vendor feature의 step: 목록·추가·이름 변경·삭제와 Deal 연동 확인.

Solution은 Vendor 관리 대상이 아니라 Deal의 자유 텍스트이므로 여기에 없다(폐지된 Solution 관리
API가 404인지만 `when_call_removed_solution_api`로 확인한다).
Given은 공개 API로 사전 상태를 만든다. 쓰기는 admin만 할 수 있으므로 `given_vendor`는
admin(`root`)으로 로그인한 상태에서 만들고, 호출한 뒤에도 admin 로그인이 유지된다(Deal을 등록할
역할로는 호출 뒤에 다시 로그인한다). When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tests.functional.steps.auth import given_logged_in_as
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

VENDORS: Final = "/api/v1/vendors"
PLACEHOLDER_ID: Final = MISSING_ID

DUPLICATE_VENDOR: Final = "이미 있는 Vendor 이름입니다."
VENDOR_BLANK: Final = "Vendor 이름을 입력하세요."
VENDOR_LONG: Final = "Vendor 이름은 100자 이내로 입력하세요."
UNKNOWN_VENDOR: Final = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."
SOLUTION_REQUIRED: Final = "Solution을 입력하세요."
SOLUTION_LONG: Final = "Solution은 200자 이내로 입력하세요."
ADMIN_DENIED: Final = "관리자 권한이 필요합니다"

VENDOR_FIELDS: Final = {"id", "name", "usage_count", "created_at", "updated_at"}


@dataclass(frozen=True)
class VendorRef:
    """Given으로 만든 Vendor."""

    id: int
    name: str


def in_use_vendor(count: int) -> str:
    return f"사용 중인 Vendor는 삭제할 수 없습니다. (Deal {count}건)"


# --- Given ---


async def given_vendor(api: Api, name: str = "SAP") -> VendorRef:
    """admin이 Vendor를 만들어 두었다(admin 로그인 상태가 된다)."""
    await given_logged_in_as(api, role="admin")
    created = await when_create_vendor(api, name=name)
    assert created.status_code == 201, f"Given 실패 {created.status_code}: {created.text}"
    return VendorRef(int(created.json()["id"]), name)


async def given_vendor_list(api: Api) -> list[dict[str, object]]:
    response = await api.get(VENDORS)
    assert response.status_code == 200, response.text
    return list(response.json())


# --- When (HTTP API 하나) ---


async def when_list_vendors(api: Api) -> Response:
    return await api.get(VENDORS)


async def when_create_vendor(api: Api, *, name: str) -> Response:
    return await api.post(VENDORS, json={"name": name})


async def when_rename_vendor(api: Api, *, vendor_id: object, name: str) -> Response:
    return await api.patch(f"{VENDORS}/{vendor_id}", json={"name": name})


async def when_delete_vendor(api: Api, *, vendor_id: object) -> Response:
    return await api.delete(f"{VENDORS}/{vendor_id}")


REMOVED_SOLUTION_CALLS: Final = ("create", "rename", "delete")


async def when_call_removed_solution_api(api: Api, call: str, *, vendor_id: object) -> Response:
    """폐지된 Solution 관리 API(경로 3개) 중 하나를 호출한다."""
    calls = {
        "create": lambda: api.post(f"{VENDORS}/{vendor_id}/solutions", json={"name": "Cloud"}),
        "rename": lambda: api.patch(
            f"{VENDORS}/{vendor_id}/solutions/{PLACEHOLDER_ID}", json={"name": "Cloud"}
        ),
        "delete": lambda: api.delete(f"{VENDORS}/{vendor_id}/solutions/{PLACEHOLDER_ID}"),
    }
    return await calls[call]()


WRITE_OPERATIONS: Final = ("create_vendor", "rename_vendor", "delete_vendor")


async def when_write(api: Api, operation: str, *, vendor_id: object) -> Response:
    """쓰기 API 하나를 이름으로 고른다(권한 시나리오를 operation별로 나누려는 용도)."""
    calls = {
        "create_vendor": lambda: when_create_vendor(api, name="X"),
        "rename_vendor": lambda: when_rename_vendor(api, vendor_id=vendor_id, name="X"),
        "delete_vendor": lambda: when_delete_vendor(api, vendor_id=vendor_id),
    }
    return await calls[operation]()


# --- Then ---


def then_location_points_to(response: Response, location: str) -> None:
    assert response.headers["location"] == location


async def then_vendors_are(api: Api, expected: list[str]) -> None:
    """다시 조회한 목록의 Vendor 이름이 순서까지 같다."""
    assert [str(v["name"]) for v in await given_vendor_list(api)] == expected


async def then_usage_is(api: Api, *, vendor: str, count: int) -> None:
    """다시 조회한 목록에서 Vendor의 사용 Deal 수."""
    (found,) = [v for v in await given_vendor_list(api) if v["name"] == vendor]
    assert found["usage_count"] == count
