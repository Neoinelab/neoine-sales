"""Customer/Partner/Deal Repository가 공통으로 지켜야 하는 CRUD 계약."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidValueError
from tests.factories import later

if TYPE_CHECKING:
    from tests.contracts.conftest import RepositoryCase


async def test_add_then_get_returns_an_equal_but_separate_entity(case: RepositoryCase) -> None:
    entity = case.make(1)
    await case.add(entity)

    loaded = await case.repository.get(entity.id)

    assert loaded == entity
    assert loaded.details == entity.details
    assert loaded is not entity


async def test_get_missing_entity_raises_not_found(case: RepositoryCase) -> None:
    with pytest.raises(case.not_found):
        await case.repository.get(uuid4())


async def test_add_with_existing_id_raises_already_exists(case: RepositoryCase) -> None:
    entity = case.make(1)
    await case.add(entity)

    with pytest.raises(AlreadyExistsError):
        await case.add(entity)


async def test_list_of_empty_repository_is_empty(case: RepositoryCase) -> None:
    assert list(await case.repository.list()) == []


async def test_list_orders_by_creation_time(case: RepositoryCase) -> None:
    third, first, second = case.make(3), case.make(1), case.make(2)
    for entity in (third, first, second):
        await case.add(entity)

    listed = await case.repository.list()

    assert [e.id for e in listed] == [first.id, second.id, third.id]


async def test_list_paginates_with_offset_and_limit(case: RepositoryCase) -> None:
    entities = [case.make(n) for n in range(1, 6)]
    for entity in entities:
        await case.add(entity)

    page = await case.repository.list(offset=1, limit=2)
    beyond = await case.repository.list(offset=10, limit=2)

    assert [e.id for e in page] == [entities[1].id, entities[2].id]
    assert list(beyond) == []


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_rejects_invalid_paging(case: RepositoryCase, offset: int, limit: int) -> None:
    with pytest.raises(InvalidValueError):
        await case.repository.list(offset=offset, limit=limit)


async def test_update_persists_changes(case: RepositoryCase) -> None:
    original = case.make(1)
    await case.add(original)
    loaded = await case.repository.get(original.id)
    case.change(loaded, later(100))

    await case.repository.update(loaded)
    reloaded = await case.repository.get(original.id)

    assert reloaded.details == loaded.details
    assert reloaded.details != original.details
    assert reloaded.updated_at == later(100)


async def test_update_of_missing_entity_raises_not_found(case: RepositoryCase) -> None:
    with pytest.raises(case.not_found):
        await case.repository.update(case.make(1))


async def test_changes_to_a_loaded_entity_are_not_saved_without_update(
    case: RepositoryCase,
) -> None:
    original = case.make(1)
    await case.add(original)
    loaded = await case.repository.get(original.id)

    case.change(loaded, later(100))
    reloaded = await case.repository.get(original.id)

    assert reloaded.details == original.details


async def test_changes_to_an_added_entity_are_not_saved_without_update(
    case: RepositoryCase,
) -> None:
    entity = case.make(1)
    original_details = entity.details
    await case.add(entity)

    case.change(entity, later(100))
    reloaded = await case.repository.get(entity.id)

    assert reloaded.details == original_details


async def test_delete_removes_the_row_physically(case: RepositoryCase) -> None:
    kept, removed = case.make(1), case.make(2)
    await case.add(kept)
    await case.add(removed)

    await case.repository.delete(removed.id)

    with pytest.raises(case.not_found):
        await case.repository.get(removed.id)
    assert [e.id for e in await case.repository.list()] == [kept.id]
    assert (await case.repository.get(kept.id)).id == kept.id


async def test_delete_of_missing_entity_raises_not_found(case: RepositoryCase) -> None:
    with pytest.raises(case.not_found):
        await case.repository.delete(uuid4())


async def test_deleting_twice_raises_not_found_the_second_time(case: RepositoryCase) -> None:
    entity = case.make(1)
    await case.add(entity)
    await case.repository.delete(entity.id)

    with pytest.raises(case.not_found):
        await case.repository.delete(entity.id)


async def test_update_of_a_deleted_entity_raises_not_found(case: RepositoryCase) -> None:
    entity = case.make(1)
    await case.add(entity)
    await case.repository.delete(entity.id)

    with pytest.raises(case.not_found):
        await case.repository.update(entity)


async def test_deleted_entity_id_can_be_added_again(case: RepositoryCase) -> None:
    entity = case.make(1)
    await case.add(entity)
    await case.repository.delete(entity.id)

    await case.add(entity)

    assert (await case.repository.get(entity.id)).id == entity.id
