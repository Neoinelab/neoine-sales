"""코드·BANT Label 사용 수 집계와 삭제 시 FK 위반 매핑(AC-14·15, R3).

사용 수는 저장된 Deal의 status_key·forecast_key·BANT 선택 기준이다. 사용 수 집계가 놓친 연결을
DB의 FK가 막아도 같은 409(CodeInUseError·LabelInUseError, 실제 연결 수 포함)가 되어야 한다.
`forecast_counts`·`bant_label_counts` 주입은 "집계가 0이라고 한 낡은 값"을 흉내 낸다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.bant.delete_label import DeleteBantLabel
from app.application.bant.list_labels import ListBantLabels
from app.application.code.delete_code import DeleteCode
from app.application.code.list_codes_with_usage import ListCodesWithUsage
from app.domain.bant.errors import LabelInUseError
from app.domain.bant.values import BantCategory
from app.domain.code.errors import CodeInUseError
from app.domain.code.values import CodeKind
from tests.support.catalog import code_by_key, label_by_name

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_forecast_usage_counts_the_deals_that_use_each_forecast_key(env: DealEnv) -> None:
    await env.new_deal(forecast_key="best")
    await env.new_deal(forecast_key="best")
    await env.new_deal(forecast_key="commit")

    usage = await ListCodesWithUsage(env.uow_factory).execute(CodeKind.FORECAST)

    counts = {u.code.key.value: u.usage_count for u in usage if u.usage_count}
    assert counts == {"best": 2, "commit": 1}


async def test_status_usage_counts_the_deals_that_use_each_status_key(env: DealEnv) -> None:
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="prospecting")

    usage = await ListCodesWithUsage(env.uow_factory).execute(CodeKind.STATUS)

    counts = {u.code.key.value: u.usage_count for u in usage if u.usage_count}
    assert counts == {"introduction": 2, "prospecting": 1}


async def test_label_usage_counts_the_deals_that_selected_it(env: DealEnv) -> None:
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    need = await label_by_name(env.uow, BantCategory.NEED, "CISO 지시")
    await env.new_deal(bant={BantCategory.BUDGET: budget.id, BantCategory.NEED: need.id})
    await env.new_deal(bant={BantCategory.BUDGET: budget.id})
    await env.new_deal()

    usage = await ListBantLabels(env.uow_factory).execute()

    counts = {u.label.name: u.usage_count for u in usage if u.usage_count}
    assert counts == {"풀 예산 확보": 2, "CISO 지시": 1}


async def test_a_label_in_use_cannot_be_deleted_and_the_message_has_the_real_count(
    env: DealEnv,
) -> None:
    label = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    await env.new_deal(bant={BantCategory.BUDGET: label.id})
    await env.new_deal(bant={BantCategory.BUDGET: label.id})

    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(env.uow_factory).execute(label.id)

    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"
    assert await env.uow.bant_labels.get(label.id) == label


async def test_a_label_connection_missed_by_the_count_is_caught_as_in_use_with_the_real_count(
    env: DealEnv,
) -> None:
    label = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    await env.new_deal(bant={BantCategory.BUDGET: label.id})
    env.uow.deals.bant_label_counts = {}  # 집계가 0이라고 낡은 값을 돌려준다

    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(env.uow_factory).execute(label.id)

    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 1건)"
    assert await env.uow.bant_labels.get(label.id) == label


async def test_an_unused_label_is_deleted_even_when_other_labels_are_used(env: DealEnv) -> None:
    used = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    idle = await label_by_name(env.uow, BantCategory.BUDGET, "예산 없음")
    await env.new_deal(bant={BantCategory.BUDGET: used.id})

    await DeleteBantLabel(env.uow_factory).execute(idle.id)

    names = [x.name for x in await env.uow.bant_labels.list(BantCategory.BUDGET)]
    assert "예산 없음" not in names
    assert "풀 예산 확보" in names


async def test_a_forecast_in_use_cannot_be_deleted_and_the_message_has_the_real_count(
    env: DealEnv,
) -> None:
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="best")

    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(best.id)

    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"
    assert (await env.uow.codes.get(best.id)).key.value == "best"


async def test_a_status_in_use_cannot_be_deleted(env: DealEnv) -> None:
    status = await code_by_key(env.uow, CodeKind.STATUS, "introduction")
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="introduction")

    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(status.id)

    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"


async def test_a_code_connection_missed_by_the_count_is_caught_as_in_use_with_the_real_count(
    env: DealEnv,
) -> None:
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="best")
    env.uow.deals.forecast_counts = {}  # 집계가 0이라고 낡은 값을 돌려준다

    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(best.id)

    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"
    assert (await env.uow.codes.get(best.id)).key.value == "best"


async def test_an_unused_forecast_is_deleted(env: DealEnv) -> None:
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="commit")

    await DeleteCode(env.uow_factory).execute(best.id)

    keys = [c.key.value for c in await env.uow.codes.list(CodeKind.FORECAST)]
    assert "best" not in keys
