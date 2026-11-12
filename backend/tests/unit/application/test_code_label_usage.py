"""코드·BANT Label 사용 수 집계와 삭제 시 FK 위반 매핑(R3).

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
    """Forecast 사용 수는 저장된 Deal의 Forecast key별 Deal 수다.

    테스트 코드: CD-005
    """
    # given: Forecast Best Deal 2건, Commit Deal 1건
    await env.new_deal(forecast_key="best")
    await env.new_deal(forecast_key="best")
    await env.new_deal(forecast_key="commit")

    # when: Forecast 사용 현황을 읽는다
    usage = await ListCodesWithUsage(env.uow_factory).execute(CodeKind.FORECAST)

    # then: best 2, commit 1, 나머지 0이다
    counts = {u.code.key.value: u.usage_count for u in usage if u.usage_count}
    assert counts == {"best": 2, "commit": 1}


async def test_status_usage_counts_the_deals_that_use_each_status_key(env: DealEnv) -> None:
    """Status 사용 수는 저장된 Deal의 Status key별 Deal 수다.

    테스트 코드: CD-004
    """
    # given: 제품소개 Deal 2건, 기회발굴 Deal 1건
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="prospecting")

    # when: Status 사용 현황을 읽는다
    usage = await ListCodesWithUsage(env.uow_factory).execute(CodeKind.STATUS)

    # then: introduction 2, prospecting 1, 나머지 0이다
    counts = {u.code.key.value: u.usage_count for u in usage if u.usage_count}
    assert counts == {"introduction": 2, "prospecting": 1}


async def test_label_usage_counts_the_deals_that_selected_it(env: DealEnv) -> None:
    """Label의 사용 수는 그 Label을 선택한 Deal 수이고 BANT 없는 Deal은 세지 않는다.

    테스트 코드: CL-003
    """
    # given: '풀 예산 확보'를 Deal 2건이, 'CISO 지시'를 1건이 선택했고 BANT 없는 Deal도 있다
    budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    need = await label_by_name(env.uow, BantCategory.NEED, "CISO 지시")
    await env.new_deal(bant={BantCategory.BUDGET: budget.id, BantCategory.NEED: need.id})
    await env.new_deal(bant={BantCategory.BUDGET: budget.id})
    await env.new_deal()

    # when: Label 목록을 읽는다
    usage = await ListBantLabels(env.uow_factory).execute()

    # then: '풀 예산 확보' 2, 'CISO 지시' 1이고 나머지는 0이다
    counts = {u.label.name: u.usage_count for u in usage if u.usage_count}
    assert counts == {"풀 예산 확보": 2, "CISO 지시": 1}


async def test_a_label_in_use_cannot_be_deleted_and_the_message_has_the_real_count(
    env: DealEnv,
) -> None:
    """Deal이 선택한 Label을 지우면 실제 Deal 수가 든 오류이고 Label은 남는다.

    테스트 코드: CL-020
    """
    # given: budget '풀 예산 확보'를 Deal 2건이 선택했다
    label = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    await env.new_deal(bant={BantCategory.BUDGET: label.id})
    await env.new_deal(bant={BantCategory.BUDGET: label.id})

    # when: Label을 삭제한다
    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(env.uow_factory).execute(label.id)

    # then: '(Deal 2건)' 오류이고 Label은 그대로다
    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 2건)"
    assert await env.uow.bant_labels.get(label.id) == label


async def test_a_label_connection_missed_by_the_count_is_caught_as_in_use_with_the_real_count(
    env: DealEnv,
) -> None:
    """사용 수 집계가 놓친 연결도 삭제를 막고 실제 건수로 거절한다.

    테스트 코드: CL-021
    """
    # given: Deal 1건이 Label을 가리키지만 집계는 0으로 낡은 값을 돌려준다
    label = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    await env.new_deal(bant={BantCategory.BUDGET: label.id})
    env.uow.deals.bant_label_counts = {}  # 집계가 0이라고 낡은 값을 돌려준다

    # when: Label을 삭제한다
    with pytest.raises(LabelInUseError) as raised:
        await DeleteBantLabel(env.uow_factory).execute(label.id)

    # then: '(Deal 1건)' 오류이고 Label은 남는다
    assert str(raised.value) == "사용 중인 Label은 삭제할 수 없습니다. (Deal 1건)"
    assert await env.uow.bant_labels.get(label.id) == label


async def test_an_unused_label_is_deleted_even_when_other_labels_are_used(env: DealEnv) -> None:
    """쓰이지 않는 Label은 다른 Label이 쓰이는 중에도 삭제되고 쓰이는 Label은 남는다.

    테스트 코드: CL-019
    """
    # given: '풀 예산 확보'는 Deal이 쓰고 '예산 없음'은 쓰이지 않는다
    used = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
    idle = await label_by_name(env.uow, BantCategory.BUDGET, "예산 없음")
    await env.new_deal(bant={BantCategory.BUDGET: used.id})

    # when: '예산 없음'을 삭제한다
    await DeleteBantLabel(env.uow_factory).execute(idle.id)

    # then: '예산 없음'만 사라지고 '풀 예산 확보'는 남는다
    names = [x.name for x in await env.uow.bant_labels.list(BantCategory.BUDGET)]
    assert "예산 없음" not in names
    assert "풀 예산 확보" in names


async def test_a_forecast_in_use_cannot_be_deleted_and_the_message_has_the_real_count(
    env: DealEnv,
) -> None:
    """Deal이 쓰는 Forecast 코드는 삭제할 수 없고 문구에 Deal 수가 들어간다.

    테스트 코드: CD-040
    """
    # given: Best를 쓰는 Deal 1건
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="best")

    # when: Best를 삭제한다
    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(best.id)

    # then: Deal 1건 문구의 거절이고 Best는 남는다
    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"
    assert (await env.uow.codes.get(best.id)).key.value == "best"


async def test_a_status_in_use_cannot_be_deleted(env: DealEnv) -> None:
    """Deal이 쓰는 Status 코드는 삭제할 수 없고 문구에 Deal 수가 들어간다.

    테스트 코드: CD-040
    """
    # given: 제품소개를 쓰는 Deal 2건
    status = await code_by_key(env.uow, CodeKind.STATUS, "introduction")
    await env.new_deal(status_key="introduction")
    await env.new_deal(status_key="introduction")

    # when: 제품소개를 삭제한다
    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(status.id)

    # then: Deal 2건 문구의 거절이고 제품소개는 남는다
    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"
    assert (await env.uow.codes.get(status.id)).key.value == "introduction"


async def test_a_code_connection_missed_by_the_count_is_caught_as_in_use_with_the_real_count(
    env: DealEnv,
) -> None:
    """집계가 놓친 Deal 연결도 실제 Deal 수가 든 같은 거절이 된다.

    테스트 코드: CD-041
    """
    # given: Best를 쓰는 Deal 1건이 있고 사용 수 집계는 0을 돌려준다(낡은 집계를 흉내 낸다)
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="best")
    env.uow.deals.forecast_counts = {}

    # when: Best를 삭제한다
    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(env.uow_factory).execute(best.id)

    # then: Deal 1건 문구의 거절이고 Best는 남는다
    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"
    assert (await env.uow.codes.get(best.id)).key.value == "best"


async def test_an_unused_forecast_is_deleted(env: DealEnv) -> None:
    """쓰이지 않는 Forecast 코드는 다른 Forecast를 쓰는 Deal이 있어도 지워진다.

    테스트 코드: CD-039
    """
    # given: Best는 쓰는 Deal이 없고 Commit을 쓰는 Deal은 있다
    best = await code_by_key(env.uow, CodeKind.FORECAST, "best")
    await env.new_deal(forecast_key="commit")

    # when: Best를 삭제한다
    await DeleteCode(env.uow_factory).execute(best.id)

    # then: Best가 사라진다
    keys = [c.key.value for c in await env.uow.codes.list(CodeKind.FORECAST)]
    assert "best" not in keys
