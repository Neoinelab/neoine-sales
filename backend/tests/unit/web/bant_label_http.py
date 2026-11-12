"""BANT Label 라우터 단위 테스트 공용 도우미: 시드된 FakeUseCases와 Label을 쓰는 Deal 준비."""

from typing import TYPE_CHECKING

from tests.factories import make_bant
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import DEFAULT_LABELS, seed_catalog
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from httpx import AsyncClient

URL = "/api/v1/bant-labels"
LABEL_KEYS = {
    "id",
    "category",
    "name",
    "is_default",
    "created_by",
    "created_at",
    "updated_at",
    "usage_count",
}
CATEGORIES = ["budget", "authority", "need", "timeline"]
DEFAULT_COUNTS = {name: len(names) for name, names in DEFAULT_LABELS.items()}
BASELINE = 23


def seeded_use_cases() -> FakeUseCases:
    """기본 코드·BANT Label 23개가 시드된 FakeUseCases(마이그레이션이 넣는 상태와 같다)."""
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    return use_cases


async def labels_of(http: AsyncClient) -> list[dict[str, object]]:
    """GET 목록 본문(성공해야 한다)."""
    response = await http.get(URL)
    assert response.status_code == 200, response.text
    return list(response.json())


async def label_id_of(http: AsyncClient, category: str, name: str) -> int:
    """구분과 이름으로 찾은 Label의 id(응답의 JSON 정수 그대로)."""
    body = await labels_of(http)
    found = next(x["id"] for x in body if x["category"] == category and x["name"] == name)
    assert isinstance(found, int)
    return found


async def use_label(
    use_cases: FakeUseCases, label_id: int, category: str, *, count: int = 1, start: int = 1
) -> None:
    """label_id를 해당 구분에서 선택한 Deal을 count건 저장소에 직접 둔다."""
    for number in range(start, start + count):
        await seed_deal(
            use_cases.uow,
            code=f"20261016-{number:04d}",
            bant=make_bant(**{category: label_id}),
        )
