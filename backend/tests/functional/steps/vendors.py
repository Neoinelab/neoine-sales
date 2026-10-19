"""Vendor·Solution feature의 step: 목록·추가·이름 변경·삭제와 Deal 연동 확인.

Given은 공개 API로 사전 상태를 만든다. 쓰기는 admin만 할 수 있으므로 `given_vendor`는
admin(`root`)으로 로그인한 상태에서 만들고, 호출한 뒤에도 admin 로그인이 유지된다(Deal을 등록할
역할로는 호출 뒤에 다시 로그인한다). When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tests.functional.steps.auth import given_logged_in_as

if TYPE_CHECKING:
    from collections.abc import Sequence

    from httpx import Response

    from tests.functional.conftest import Api

VENDORS: Final = "/api/v1/vendors"
PLACEHOLDER_ID: Final = "6f1c1b3a-0000-4000-8000-0000000000aa"

DUPLICATE_VENDOR: Final = "이미 있는 Vendor 이름입니다."
DUPLICATE_SOLUTION: Final = "이 Vendor에 이미 있는 Solution 이름입니다."
VENDOR_BLANK: Final = "Vendor 이름을 입력하세요."
VENDOR_LONG: Final = "Vendor 이름은 100자 이내로 입력하세요."
SOLUTION_BLANK: Final = "Solution 이름을 입력하세요."
SOLUTION_LONG: Final = "Solution 이름은 200자 이내로 입력하세요."
SOLUTION_NEEDS_VENDOR: Final = "Solution을 선택하려면 Vendor를 먼저 선택하세요."
UNKNOWN_VENDOR: Final = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."
SOLUTION_MISMATCH: Final = "선택한 Solution은 이 Vendor에 속하지 않습니다."
ADMIN_DENIED: Final = "관리자 권한이 필요합니다"


@dataclass(frozen=True)
class VendorRef:
    """Given으로 만든 Vendor와 소속 Solution(이름 -> id)."""

    id: str
    name: str
    solutions: dict[str, str]


def in_use_vendor(count: int) -> str:
    return f"사용 중인 Vendor는 삭제할 수 없습니다. (Deal {count}건)"


def in_use_solution(count: int) -> str:
    return f"사용 중인 Solution은 삭제할 수 없습니다. (Deal {count}건)"


# --- Given ---


async def given_vendor(api: Api, name: str = "SAP", solutions: Sequence[str] = ()) -> VendorRef:
    """admin이 Vendor와 소속 Solution을 만들어 두었다(admin 로그인 상태가 된다)."""
    await given_logged_in_as(api, role="admin")
    created = await when_create_vendor(api, name=name)
    assert created.status_code == 201, f"Given 실패 {created.status_code}: {created.text}"
    vendor_id = str(created.json()["id"])
    ids: dict[str, str] = {}
    for solution in solutions:
        response = await when_create_solution(api, vendor_id=vendor_id, name=solution)
        assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
        ids[solution] = str(response.json()["id"])
    return VendorRef(vendor_id, name, ids)


async def given_vendor_list(api: Api) -> list[dict[str, object]]:
    response = await api.get(VENDORS)
    assert response.status_code == 200, response.text
    return list(response.json())


# --- When (HTTP API 하나) ---


async def when_list_vendors(api: Api) -> Response:
    return await api.get(VENDORS)


async def when_create_vendor(api: Api, *, name: str) -> Response:
    return await api.post(VENDORS, json={"name": name})


async def when_rename_vendor(api: Api, *, vendor_id: str, name: str) -> Response:
    return await api.patch(f"{VENDORS}/{vendor_id}", json={"name": name})


async def when_delete_vendor(api: Api, *, vendor_id: str) -> Response:
    return await api.delete(f"{VENDORS}/{vendor_id}")


async def when_create_solution(api: Api, *, vendor_id: str, name: str) -> Response:
    return await api.post(f"{VENDORS}/{vendor_id}/solutions", json={"name": name})


async def when_rename_solution(
    api: Api, *, vendor_id: str, solution_id: str, name: str
) -> Response:
    return await api.patch(f"{VENDORS}/{vendor_id}/solutions/{solution_id}", json={"name": name})


async def when_delete_solution(api: Api, *, vendor_id: str, solution_id: str) -> Response:
    return await api.delete(f"{VENDORS}/{vendor_id}/solutions/{solution_id}")


WRITE_OPERATIONS: Final = (
    "create_vendor",
    "rename_vendor",
    "delete_vendor",
    "create_solution",
    "rename_solution",
    "delete_solution",
)


async def when_write(api: Api, operation: str, *, vendor_id: str, solution_id: str) -> Response:
    """쓰기 API 하나를 이름으로 고른다(권한 시나리오를 operation별로 나누려는 용도)."""
    calls = {
        "create_vendor": lambda: when_create_vendor(api, name="X"),
        "rename_vendor": lambda: when_rename_vendor(api, vendor_id=vendor_id, name="X"),
        "delete_vendor": lambda: when_delete_vendor(api, vendor_id=vendor_id),
        "create_solution": lambda: when_create_solution(api, vendor_id=vendor_id, name="X"),
        "rename_solution": lambda: when_rename_solution(
            api, vendor_id=vendor_id, solution_id=solution_id, name="X"
        ),
        "delete_solution": lambda: when_delete_solution(
            api, vendor_id=vendor_id, solution_id=solution_id
        ),
    }
    return await calls[operation]()


# --- Then ---


def then_location_points_to(response: Response, location: str) -> None:
    assert response.headers["location"] == location


async def then_vendors_are(api: Api, expected: list[tuple[str, list[str]]]) -> None:
    """다시 조회한 목록이 (Vendor 이름, [Solution 이름...])과 순서까지 같다."""
    listed = [
        (str(v["name"]), [str(s["name"]) for s in v["solutions"]])  # type: ignore[attr-defined]
        for v in await given_vendor_list(api)
    ]
    assert listed == expected


async def then_usage_is(api: Api, *, vendor: str, count: int, solution: str | None = None) -> None:
    """다시 조회한 목록에서 Vendor(또는 그 Solution)의 사용 Deal 수."""
    (found,) = [v for v in await given_vendor_list(api) if v["name"] == vendor]
    if solution is None:
        assert found["usage_count"] == count
        return
    (item,) = [s for s in found["solutions"] if s["name"] == solution]  # type: ignore[attr-defined]
    assert item["usage_count"] == count
