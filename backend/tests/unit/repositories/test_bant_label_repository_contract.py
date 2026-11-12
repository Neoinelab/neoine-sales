"""BantLabelRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

SQL 쪽에는 마이그레이션 시드(기본 Label 23개)가 있을 수 있어 비어 있는 저장소를 가정하지 않는다.
이름은 시드와 겹치지 않는 값을 쓰고, 목록은 `mine_labels`로 자기가 만든 행만 비교한다.
정렬 계약: 구분 선언 순, 기본 Label 먼저(default_order), 직접 만든 것은 lower(name), id.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.errors import BantLabelNotFoundError, DuplicateLabelNameError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_catalog import make_label
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.catalog_case import CatalogCase


async def test_add_then_get_round_trips_a_custom_label_with_its_creator(
    catalog: CatalogCase,
) -> None:
    """직접 만든 Label을 저장하고 읽으면 만든 사람까지 그대로다."""
    # given: 만든 사용자와 그가 만든 Need Label이 저장돼 있다
    creator = UserId(new_id())
    await catalog.ensure_user(creator)
    label = make_label(BantCategory.NEED, name="ZZ 규제 대응", created_by=creator, now=NOW)
    await catalog.labels.add(label)

    # when: Label을 id로 읽는다
    stored = await catalog.labels.get(label.id)

    # then: 구분·이름·기본 여부·만든 사람·시각이 저장한 값과 같다
    assert stored == label
    assert (stored.category, stored.name) == (BantCategory.NEED, "ZZ 규제 대응")
    assert (stored.is_default, stored.default_order) == (False, None)
    assert stored.created_by_user_id == creator
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_default_label_round_trips_without_a_creator(catalog: CatalogCase) -> None:
    """기본 Label은 만든 사람 없이 저장·조회된다."""
    # given: 기본 순서 99인 기본 Label이 저장돼 있다
    label = make_label(BantCategory.BUDGET, name="ZZ 기본", is_default=True, default_order=99)
    await catalog.labels.add(label)

    # when: Label을 id로 읽는다
    stored = await catalog.labels.get(label.id)

    # then: 기본 Label이고 순서 99이며 만든 사람이 없다
    assert (stored.is_default, stored.default_order, stored.created_by_user_id) == (True, 99, None)


async def test_get_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    """없는 Label을 읽으면 BantLabelNotFoundError다."""
    # when·then: 없는 id로 읽으면 BantLabelNotFoundError다
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.get(BantLabelId(new_id()))


async def test_list_puts_defaults_first_by_default_order_then_custom_by_name(
    catalog: CatalogCase,
) -> None:
    """목록은 기본 Label을 기본 순서대로, 그다음 직접 만든 Label을 이름순으로 돌려준다."""
    # given: Authority 구분의 직접 만든 Label 둘과 기본 Label 둘이 섞여 저장돼 있다
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

    # when: 그 Label들의 목록을 읽는다
    listed = await catalog.mine_labels(BantCategory.AUTHORITY, ids)

    # then: 기본 순서의 기본 Label, 이름순의 직접 만든 Label 순서다
    assert [x.id for x in listed] == [default_1.id, default_2.id, custom_a.id, custom_b.id]


async def test_list_sorts_custom_labels_ignoring_case(catalog: CatalogCase) -> None:
    """직접 만든 Label은 대소문자를 무시한 이름순으로 정렬된다."""
    # given: 대문자·소문자로 시작하는 Need Label 둘이 저장돼 있다
    upper = make_label(BantCategory.NEED, name="ZZ Charlie")
    lower = make_label(BantCategory.NEED, name="zz bravo")
    await catalog.labels.add(upper)
    await catalog.labels.add(lower)

    # when: 그 Label들의 목록을 읽는다
    listed = await catalog.mine_labels(BantCategory.NEED, {upper.id, lower.id})

    # then: 대소문자와 무관하게 이름순이다
    assert [x.id for x in listed] == [lower.id, upper.id]


async def test_list_orders_categories_in_declared_order(catalog: CatalogCase) -> None:
    """구분 전체 목록은 구분 선언 순서로 돌려준다."""
    # given: 네 구분의 Label이 선언과 다른 순서로 저장돼 있다
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

    # when: 구분 없이 목록을 읽는다
    listed = await catalog.mine_labels(None, {x.id for x in labels.values()})

    # then: Budget, Authority, Need, Timeline 순이다
    assert [x.category for x in listed] == [
        BantCategory.BUDGET,
        BantCategory.AUTHORITY,
        BantCategory.NEED,
        BantCategory.TIMELINE,
    ]


async def test_list_with_category_returns_only_that_category(catalog: CatalogCase) -> None:
    """구분을 지정한 목록은 그 구분의 Label만 돌려준다."""
    # given: Budget Label과 Need Label이 저장돼 있다
    budget = make_label(BantCategory.BUDGET, name="ZZ B")
    need = make_label(BantCategory.NEED, name="ZZ N")
    await catalog.labels.add(budget)
    await catalog.labels.add(need)

    # when: Need 구분 목록을 읽는다
    listed = await catalog.labels.list(BantCategory.NEED)

    # then: Need Label만 들어 있고 Budget Label은 없다
    assert need.id in {x.id for x in listed}
    assert budget.id not in {x.id for x in listed}
    assert {x.category for x in listed} == {BantCategory.NEED}


async def test_list_for_update_returns_the_same_rows(catalog: CatalogCase) -> None:
    """잠금 목록은 일반 목록과 같은 행을 돌려준다."""
    # given: Need Label이 저장돼 있다
    label = make_label(BantCategory.NEED, name="ZZ N")
    await catalog.labels.add(label)

    # when: 일반 목록과 for_update 목록을 읽는다
    plain = await catalog.labels.list(BantCategory.NEED)
    locked = await catalog.labels.list(BantCategory.NEED, for_update=True)

    # then: 두 목록의 id가 같다
    assert [x.id for x in locked] == [x.id for x in plain]


@pytest.mark.parametrize("duplicate", ["zz label", "ZZ LABEL", "Zz Label"])
async def test_add_with_same_name_in_the_category_ignoring_case_conflicts(
    catalog: CatalogCase, duplicate: str
) -> None:
    """같은 구분에서 대소문자만 다른 이름을 추가하면 충돌한다."""
    # given: Need 구분에 ZZ Label이 저장돼 있다
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ Label"))

    # when·then: 대소문자만 다른 이름을 추가하면 DuplicateLabelNameError다
    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.add(make_label(BantCategory.NEED, name=duplicate))


async def test_add_with_same_name_in_another_category_is_allowed(catalog: CatalogCase) -> None:
    """다른 구분에서는 같은 이름을 추가할 수 있다."""
    # given: Need 구분에 ZZ Label이 저장돼 있다
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ Label"))
    other = make_label(BantCategory.BUDGET, name="ZZ Label")

    # when: Budget 구분에 같은 이름을 추가한다
    await catalog.labels.add(other)

    # then: Budget 구분 Label로 읽힌다
    assert (await catalog.labels.get(other.id)).category is BantCategory.BUDGET


async def test_repository_stays_usable_after_a_conflict(catalog: CatalogCase) -> None:
    """충돌 뒤에도 저장소를 계속 쓸 수 있다."""
    # given: Need 구분에 ZZ One이 저장돼 있다
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ One"))
    # when·then: 대소문자만 다른 이름을 추가하면 DuplicateLabelNameError다
    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.add(make_label(BantCategory.NEED, name="zz one"))
    after = make_label(BantCategory.NEED, name="ZZ Two")

    # when: 충돌 뒤 다른 이름을 추가한다
    await catalog.labels.add(after)

    # then: 새 Label이 읽힌다
    assert (await catalog.labels.get(after.id)).name == "ZZ Two"


async def test_update_persists_the_new_name(catalog: CatalogCase) -> None:
    """이름을 바꿔 갱신하면 새 이름과 수정 시각이 저장된다."""
    # given: ZZ Old 이름의 저장된 Label을 ZZ New로 바꾼 상태
    label = make_label(BantCategory.NEED, name="ZZ Old")
    await catalog.labels.add(label)
    label.rename("ZZ New", later(60))

    # when: 갱신한다
    await catalog.labels.update(label)

    # then: 새 이름과 수정 시각이 저장되고 생성 시각은 그대로다
    stored = await catalog.labels.get(label.id)
    assert (stored.name, stored.updated_at, stored.created_at) == ("ZZ New", later(60), NOW)


async def test_update_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    """없는 Label을 갱신하면 BantLabelNotFoundError다."""
    # when·then: 저장되지 않은 Label을 갱신하면 BantLabelNotFoundError다
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.update(make_label(BantCategory.NEED, name="ZZ Ghost"))


async def test_update_to_another_labels_name_ignoring_case_conflicts(catalog: CatalogCase) -> None:
    """다른 Label의 이름과 대소문자만 달라도 갱신은 충돌한다."""
    # given: 같은 구분의 Label 둘이 있고 둘째 이름을 첫째와 대소문자만 다르게 바꾼 상태
    await catalog.labels.add(make_label(BantCategory.NEED, name="ZZ One"))
    other = make_label(BantCategory.NEED, name="ZZ Two")
    await catalog.labels.add(other)
    other.rename("zz one", later(60))

    # when·then: 갱신하면 DuplicateLabelNameError다
    with pytest.raises(DuplicateLabelNameError):
        await catalog.labels.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(catalog: CatalogCase) -> None:
    """자기 이름을 대소문자만 바꾸는 갱신은 허용된다."""
    # given: 저장된 Label의 이름을 대소문자만 바꾼 상태
    label = make_label(BantCategory.NEED, name="ZZ Name")
    await catalog.labels.add(label)
    label.rename("zz name", later(60))

    # when: 갱신한다
    await catalog.labels.update(label)

    # then: 바뀐 이름이 저장된다
    assert (await catalog.labels.get(label.id)).name == "zz name"


async def test_delete_removes_only_that_label(catalog: CatalogCase) -> None:
    """삭제는 지정한 Label만 지운다."""
    # given: 같은 구분의 Label 둘이 저장돼 있다
    gone = make_label(BantCategory.NEED, name="ZZ Gone")
    kept = make_label(BantCategory.NEED, name="ZZ Kept")
    await catalog.labels.add(gone)
    await catalog.labels.add(kept)

    # when: 하나를 삭제한다
    await catalog.labels.delete(gone.id)

    # then: 나머지만 목록에 남고 삭제한 Label은 읽을 수 없다
    assert [x.id for x in await catalog.mine_labels(BantCategory.NEED, {gone.id, kept.id})] == [
        kept.id
    ]
    # then: 삭제한 Label을 읽으면 BantLabelNotFoundError다
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.get(gone.id)


async def test_deleted_name_can_be_added_again(catalog: CatalogCase) -> None:
    """삭제한 이름은 다시 추가할 수 있다."""
    # given: 저장했다가 삭제한 Label과 같은 이름의 새 Label
    first = make_label(BantCategory.NEED, name="ZZ Again")
    await catalog.labels.add(first)
    await catalog.labels.delete(first.id)
    again = make_label(BantCategory.NEED, name="ZZ Again")

    # when: 새 Label을 추가한다
    await catalog.labels.add(again)

    # then: 새 Label이 읽힌다
    assert (await catalog.labels.get(again.id)).id == again.id


async def test_delete_missing_label_raises_not_found(catalog: CatalogCase) -> None:
    """없는 Label을 삭제하면 BantLabelNotFoundError다."""
    # when·then: 없는 id를 삭제하면 BantLabelNotFoundError다
    with pytest.raises(BantLabelNotFoundError):
        await catalog.labels.delete(BantLabelId(new_id()))
