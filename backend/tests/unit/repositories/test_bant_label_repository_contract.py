"""BantLabelRepository 계약(AC-10·11·12): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

SQL 쪽에는 마이그레이션 시드(기본 Label 23개)가 있을 수 있어 비어 있는 저장소를 가정하지 않는다.
이름은 시드와 겹치지 않는 값을 쓰고, 목록은 `mine_labels`로 자기가 만든 행만 비교한다.
정렬 계약: 구분 선언 순, 기본 Label 먼저(default_order), 직접 만든 것은 lower(name), id.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.bant.errors import BantLabelNotFoundError, DuplicateLabelNameError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_catalog import make_label

if TYPE_CHECKING:
    from tests.unit.repositories.catalog_case import CatalogCase


async def test_add_then_get_round_trips_a_custom_label_with_its_creator(
    catalog: CatalogCase,
) -> None:
    creator = UserId(uuid4())
    await catalog.ensure_user(creator)
    label = make_label(BantCategory.NEED, name="ZZ 규제 대응", created_by=creator, now=NOW)
    await catalog.labels.add(label)

    stored = await catalog.labels.get(label.id)

    assert stored == label
    assert (stored.category, stored.name) == (BantCategory.NEED, "ZZ 규제 대응")
    assert (stored.is_default, stored.default_order) == (False, None)
    assert stored.created_by_user_id == creator
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_default_label_round_trips_without_a_creator(catalog: CatalogCase) -> None:
    label = make_label(BantCategory.BUDGET, name="ZZ 기본", is_default=True, default_order=99)
    await catalog.labels.add(label)

    stored = await catalog.labels.get(label.id)

    assert (stored.is_default, stored.default_order, stored.created_by_user_id) == (True, 99, None)


async def test_get_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.get(BantLabelId(uuid4()))


async def test_list_puts_defaults_first_by_default_order_then_custom_by_name(
    catalog: CatalogCase,
) -> None:
    custom_b = make_label(BantCategory.AUTHORITY, name="ZZ beta")
    custom_a = make_label(BantCategory.AUTHORITY, name="ZZ Alpha")
    default_2 = make_label(
        BantCategory.AUTHORITY, name="ZZ 기본2", is_default=True, default_order=902
    )
    default_1 = make_label(
        BantCategory.AUTHORITY, name="ZZ 기본1", is_default=True, default_order=901
    )
    for label in (custom_b, default_2, custom_a, default_1):
        await catalog.labels.add(label)
    ids = {custom_b.id, custom_a.id, default_2.id, default_1.id}

    listed = await catalog.mine_labels(BantCategory.AUTHORITY, ids)

    assert [x.id for x in listed] == [default_1.id, default_2.id, custom_a.id, custom_b.id]


async def test_list_sorts_custom_labels_ignoring_case(catalog: CatalogCase) -> None:
    upper = make_label(BantCategory.NEED, name="ZZ Charlie")
    lower = make_label(BantCategory.NEED, name="zz bravo")
    await catalog.labels.add(upper)
    await catalog.labels.add(lower)

    listed = await catalog.mine_labels(BantCategory.NEED, {upper.id, lower.id})

    assert [x.id for x in listed] == [lower.id, upper.id]


async def test_list_orders_categories_in_declared_order(catalog: CatalogCase) -> None:
    labels = {
        category: make_label(category, name=f"ZZ {category.value}")
        for category in (
            BantCategory.TIMELINE,
            BantCategory.NEED,
            BantCategory.BUDGET,
            BantCategory.AUTHORITY,
        )
    }
    for label in labels.values():
        await catalog.labels.add(label)

    listed = await catalog.mine_labels(None, {x.id for x in labels.values()})

    assert [x.category for x in listed] == [
        BantCategory.BUDGET,
        BantCategory.AUTHORITY,
        BantCategory.NEED,
        BantCategory.TIMELINE,
    ]


async def test_list_with_category_returns_only_that_category(catalog: CatalogCase) -> None:
    budget = make_label(BantCategory.BUDGET, name="ZZ B")
    need = make_label(BantCategory.NEED, name="ZZ N")
    await catalog.labels.add(budget)
    await catalog.labels.add(need)

    listed = await catalog.labels.list(BantCategory.NEED)

    assert need.id in {x.id for x in listed}
    assert budget.id not in {x.id for x in listed}
    assert {x.category for x in listed} == {BantCategory.NEED}


async def test_list_for_update_returns_the_same_rows(catalog: CatalogCase) -> None:
    label = make_label(BantCategory.NEED, name="ZZ N")
    await catalog.labels.add(label)

    plain = await catalog.labels.list(BantCategory.NEED)
    locked = await catalog.labels.list(BantCategory.NEED, for_update=True)

    assert [x.id for x in locked] == [x.id for x in plain]


@pytest.mark.parametrize("duplicate", ["zz label", "ZZ LABEL", "Zz Label"])
async def test_add_with_same_name_in_the_category_ignoring_case_conflicts(
    catalog: CatalogCase, duplicate: str
) -> None:
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ Label"))

    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.add(make_label(BantCategory.NEED, name=duplicate))


async def test_add_with_same_name_in_another_category_is_allowed(catalog: CatalogCase) -> None:
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ Label"))
    other = make_label(BantCategory.BUDGET, name="ZZ Label")

    await catalog.labels.add(other)

    assert (await catalog.labels.get(other.id)).category is BantCategory.BUDGET


async def test_repository_stays_usable_after_a_conflict(catalog: CatalogCase) -> None:
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ One"))
    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.add(make_label(BantCategory.NEED, name="zz one"))
    after = make_label(BantCategory.NEED, name="ZZ Two")

    await catalog.labels.add(after)

    assert (await catalog.labels.get(after.id)).name == "ZZ Two"


async def test_update_persists_the_new_name(catalog: CatalogCase) -> None:
    label = make_label(BantCategory.NEED, name="ZZ Old")
    await catalog.labels.add(label)
    label.rename("ZZ New", later(60))

    await catalog.labels.update(label)

    stored = await catalog.labels.get(label.id)
    assert (stored.name, stored.updated_at, stored.created_at) == ("ZZ New", later(60), NOW)


async def test_update_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.update(make_label(BantCategory.NEED, name="ZZ Ghost"))


async def test_update_to_another_labels_name_ignoring_case_conflicts(catalog: CatalogCase) -> None:
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ One"))
    other = make_label(BantCategory.NEED, name="ZZ Two")
    await catalog.labels.add(other)
    other.rename("zz one", later(60))

    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(catalog: CatalogCase) -> None:
    label = make_label(BantCategory.NEED, name="ZZ Name")
    await catalog.labels.add(label)
    label.rename("zz name", later(60))

    await catalog.labels.update(label)

    assert (await catalog.labels.get(label.id)).name == "zz name"


async def test_delete_removes_only_that_label(catalog: CatalogCase) -> None:
    gone = make_label(BantCategory.NEED, name="ZZ Gone")
    kept = make_label(BantCategory.NEED, name="ZZ Kept")
    await catalog.labels.add(gone)
    await catalog.labels.add(kept)

    await catalog.labels.delete(gone.id)

    assert [x.id for x in await catalog.mine_labels(BantCategory.NEED, {gone.id, kept.id})] == [
        kept.id
    ]
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.get(gone.id)


async def test_deleted_name_can_be_added_again(catalog: CatalogCase) -> None:
    first = make_label(BantCategory.NEED, name="ZZ Again")
    await catalog.labels.add(first)
    await catalog.labels.delete(first.id)
    again = make_label(BantCategory.NEED, name="ZZ Again")

    await catalog.labels.add(again)

    assert (await catalog.labels.get(again.id)).id == again.id


async def test_delete_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.delete(BantLabelId(uuid4()))
