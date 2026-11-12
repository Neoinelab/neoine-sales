"""계약관리 BDD 케이스 중 기존 유스케이스 테스트가 덮지 않던 시나리오.

목록 쪽수, 종료일 계산, 이력 불변, 업로드 검증 경계, Deal 삭제 영향 등. 환경은
`license_contract_env`의 Fake 조립이다.
"""

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pytest

from app.application.attachment.inputs import UploadOutcomeKind
from app.application.ports.license_contract_repository import LicenseContractQuery
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from app.domain.license_contract.values import ContractFields, ContractStatus, InspectionCycle
from tests.factories_deal import make_create_input, make_patch
from tests.support.expect import raises_with
from tests.unit.application.license_contract_env import BOSS, KIM, PARK

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv


async def test_default_list_is_license_end_ascending_with_fifty_per_page(
    contract_env: ContractEnv,
) -> None:
    """조건 없이 읽으면 종료일 오름차순(종료일 없는 계약은 맨 뒤) 50건씩, 전체 건수가 함께 온다.

    테스트 코드: LC-016
    """
    # given: 종료일이 서로 다른 계약 45건(종료)과 종료일 없는 미발급 계약 15건
    code = await contract_env.open_deal()
    ended = [
        await contract_env.seed_contract(code, status="ended", start=date(2026, 1, 1 + n % 28))
        for n in range(45)
    ]
    waiting = [await contract_env.seed_contract(code) for _ in range(15)]
    expected = [c.id for c in sorted(ended, key=lambda c: (c.license_end, c.id))]
    expected += [c.id for c in waiting]
    # when: 조건 없이 읽고, 이어 offset=50으로 읽는다
    first = await contract_env.list.execute(LicenseContractQuery())
    second = await contract_env.list.execute(LicenseContractQuery(offset=50))
    # then: 첫 쪽은 50건·total 60, 종료일 오름차순에 종료일 없는 계약이 뒤. 둘째 쪽은 나머지 10건
    assert (first.limit, first.offset, first.total) == (50, 0, 60)
    assert [r.contract.id for r in first.items] == expected[:50]
    assert [r.contract.id for r in second.items] == expected[50:]
    assert (len(second.items), second.total) == (10, 60)


async def test_get_reflects_deal_values_changed_after_the_first_read(
    contract_env: ContractEnv,
) -> None:
    """계약 조회는 조회 시점의 Deal 값을 보여 주므로 Deal을 고치면 다음 조회에 반영된다.

    테스트 코드: LC-028
    """
    # given: Solution이 "S/4HANA"인 Won Deal의 계약과 첫 조회
    code = await contract_env.won_deal(KIM, solution="S/4HANA")
    (contract,) = await contract_env.contracts_of(code)
    first = await contract_env.get.execute(contract.id)
    # when: Deal의 Solution을 바꾼 뒤 다시 조회한다
    await contract_env.env.update.execute(code, make_patch(solution="Cloud ERP"), KIM)
    second = await contract_env.get.execute(contract.id)
    # then: 첫 조회는 옛 값, 둘째 조회는 바뀐 Deal 값이고 Won 여부는 그대로 true다
    assert first.deal.product == "S/4HANA"
    assert second.deal.product == "Cloud ERP"
    assert first.deal.is_won is True
    assert second.deal.is_won is True


async def test_deal_counts_follow_issue_renewal_and_end(contract_env: ContractEnv) -> None:
    """Deal의 계약 건수와 발급 여부는 발급·갱신·종료를 따르고 다른 Deal에는 영향이 없다.

    테스트 코드: LC-030
    """

    async def snapshot(code: str) -> tuple[bool, int]:
        item = (await contract_env.env.get.execute(code)).item
        return item.has_issued_license_contract, item.license_contract_count

    # given: 미발급 계약 1건이 있는 Won Deal A와 계약이 있는 다른 Won Deal B
    deal_a = await contract_env.won_deal(KIM)
    deal_b = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(deal_a)
    steps = [await snapshot(deal_a)]
    # when: A의 계약을 발급 -> 갱신 -> (갱신 계약)종료하며 단계마다 A를 조회한다
    await contract_env.issue.execute(contract.id, contract_env.issue_input(), KIM)
    steps.append(await snapshot(deal_a))
    await contract_env.renew.execute(contract.id, contract_env.issue_input(date(2027, 1, 1)), KIM)
    steps.append(await snapshot(deal_a))
    renewal = next(c for c in await contract_env.contracts_of(deal_a) if c.id != contract.id)
    await contract_env.end.execute(renewal.id, KIM)
    steps.append(await snapshot(deal_a))
    # then: (발급 여부, 건수)가 (F,1) (T,1) (T,2) (F,2)이고 B는 (F,1) 그대로다
    assert steps == [(False, 1), (True, 1), (True, 2), (False, 2)]
    assert await snapshot(deal_b) == (False, 1)


async def test_deal_flag_is_false_and_count_zero_after_admin_deletes_the_issued_contract(
    contract_env: ContractEnv,
) -> None:
    """발급 계약을 admin이 지우면 Deal의 발급 여부는 false, 건수는 0이다.

    테스트 코드: LC-030
    """
    # given: 발급 계약이 있는 Won Deal C
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    # when: admin이 그 계약을 삭제한다
    await contract_env.delete.execute(issued.id, BOSS)
    # then: C의 발급 여부 false, 계약 건수 0
    item = (await contract_env.env.get.execute(code)).item
    assert (item.has_issued_license_contract, item.license_contract_count) == (False, 0)


async def test_contract_changes_leave_deal_history_and_modified_time_untouched(
    contract_env: ContractEnv,
) -> None:
    """계약 칸 수정·발급·갱신·종료·첨부 업로드는 Deal History와 수정 시각을 바꾸지 않는다.

    테스트 코드: LC-035
    """
    # given: Won Deal과 그 계약, 처음의 Deal History와 수정 시각
    code = await contract_env.won_deal(KIM)
    (contract,) = await contract_env.contracts_of(code)
    history_before = await contract_env.env.history_rows(code)
    updated_before = (await contract_env.uow.deals.get(DealCode(code))).updated_at
    contract_env.clock.advance(3600)
    fields = ContractFields(tech_owner="이기술", inspection=InspectionCycle.YEARLY, note="메모")
    # when: 계약 칸 수정, 발급, 갱신, 종료, 첨부 업로드를 차례로 한다
    await contract_env.update.execute(contract.id, fields, PARK)
    await contract_env.issue.execute(contract.id, contract_env.issue_input(), PARK)
    await contract_env.renew.execute(contract.id, contract_env.issue_input(date(2027, 1, 1)), PARK)
    renewal = next(c for c in await contract_env.contracts_of(code) if c.id != contract.id)
    await contract_env.end.execute(renewal.id, PARK)
    await contract_env.put_file(renewal.id, PARK)
    # then: Deal History 건수와 수정 시각은 처음과 같다
    assert await contract_env.env.history_rows(code) == history_before
    assert (await contract_env.uow.deals.get(DealCode(code))).updated_at == updated_before


@pytest.mark.parametrize(
    ("start", "amount", "unit", "expected_end"),
    [
        (date(2026, 1, 1), 1, "year", date(2026, 12, 31)),
        (date(2026, 1, 1), 6, "month", date(2026, 6, 30)),
        (date(2026, 1, 1), 12, "month", date(2026, 12, 31)),
        (date(2026, 1, 1), 2, "year", date(2027, 12, 31)),
        (date(2026, 3, 15), 1, "month", date(2026, 4, 14)),
        (date(2026, 7, 1), 1, "month", date(2026, 7, 31)),
        (date(2026, 12, 1), 1, "month", date(2026, 12, 31)),
        (date(2026, 11, 15), 3, "month", date(2027, 2, 14)),
        (date(2026, 1, 31), 1, "month", date(2026, 2, 28)),
        (date(2027, 12, 31), 2, "month", date(2028, 2, 29)),
        (date(2028, 1, 30), 1, "month", date(2028, 2, 29)),
    ],
)
async def test_issue_computes_the_end_date_from_start_and_term(
    contract_env: ContractEnv, start: date, amount: int, unit: str, expected_end: date
) -> None:
    """종료일은 시작일+기간-1일이고 그 달에 없는 날은 말일이다(윤년 포함).

    테스트 코드: LC-040
    """
    # given: Won Deal의 미발급 계약
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code)
    # when: 시작일과 기간을 정해 발급한다
    await contract_env.issue.execute(
        contract.id, contract_env.issue_input(start, amount, unit), KIM
    )
    # then: 서버가 계산한 종료일이 기대와 같다
    stored = await contract_env.stored(contract.id)
    assert (stored.license_start, stored.license_end) == (start, expected_end)


async def test_contract_is_not_ended_automatically_after_its_end_date(
    contract_env: ContractEnv,
) -> None:
    """종료일이 지나도 계약은 자동으로 종료되지 않는다.

    테스트 코드: LC-056
    """
    # given: 종료일이 2026-12-31인 발급(신규) 계약
    code = await contract_env.won_deal_without_contract(KIM)
    contract = await contract_env.seed_contract(code, status="issued_new", start=date(2026, 1, 1))
    assert contract.license_end == date(2026, 12, 31)
    contract_env.clock.advance(
        (datetime(2027, 1, 10, tzinfo=UTC) - contract_env.clock.now()).total_seconds()
    )
    # when: 시계가 2027-01-10일 때 계약을 조회한다
    row = await contract_env.get.execute(contract.id)
    # then: 상태는 발급(신규) 그대로다
    assert row.contract.status is ContractStatus.ISSUED_NEW
    assert row.contract.ended_at is None


@pytest.mark.parametrize(
    ("name", "overrides", "message"),
    [
        (None, {}, "업로드할 파일을 선택하세요."),
        ("a.pdf", {"description": "가" * 101}, "설명은 100자 이내로 입력하세요."),
        (
            "a.pdf",
            {"declared_size": 104_857_601},
            "파일 크기가 100MB를 초과합니다. (최대 100MB)",
        ),
        ("setup.exe", {}, "실행·설치 파일(.exe)은 업로드할 수 없습니다."),
        ("SETUP.EXE", {}, "실행·설치 파일(.exe)은 업로드할 수 없습니다."),
        ("setup.exe. ", {}, "실행·설치 파일(.exe)은 업로드할 수 없습니다."),
        ("x.appimage", {}, "실행·설치 파일(.appimage)은 업로드할 수 없습니다."),
        ("..", {}, "사용할 수 없는 파일 이름입니다."),
        ("a/b.pdf", {}, "사용할 수 없는 파일 이름입니다."),
        ("a\x01b.pdf", {}, "사용할 수 없는 파일 이름입니다."),
    ],
)
async def test_upload_validation_failures_are_invalid_value_and_leave_nothing(
    contract_env: ContractEnv, name: str | None, overrides: dict[str, Any], message: str
) -> None:
    """업로드 검증 규칙을 어기면 422 해당(InvalidValueError)이고 첨부 행도 파일도 생기지 않는다.

    테스트 코드: LC-067
    """
    # given: 저장 위치가 있는 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    # when: 규칙을 어긴 파일을 올린다
    with raises_with(InvalidValueError, message):
        await contract_env.put_file(contract.id, KIM, name, **overrides)
    # then: 첨부 행과 디스크 파일이 없다
    assert await contract_env.files_of(contract.id) == []
    assert contract_env.storage.file_count() == 0


@pytest.mark.parametrize(
    ("name", "overrides"),
    [
        ("a.pdf", {"description": " " + "가" * 100 + " "}),
        ("a.pdf", {"declared_size": 104_857_600}),
    ],
)
async def test_upload_boundary_values_are_accepted(
    contract_env: ContractEnv, name: str, overrides: dict[str, Any]
) -> None:
    """설명 100자(앞뒤 공백 제외)와 크기 100MB 정확히는 올릴 수 있다.

    테스트 코드: LC-067
    """
    # given: 저장 위치가 있는 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)
    # when: 경계값으로 올린다
    outcome = await contract_env.put_file(contract.id, KIM, name, **overrides)
    # then: 업로드된다
    assert outcome.kind is UploadOutcomeKind.UPLOADED


async def test_deletion_impact_counts_contracts_but_not_contract_attachments(
    contract_env: ContractEnv,
) -> None:
    """Deal 삭제 영향은 계약 건수를 세고, 계약 첨부는 Deal 첨부 수에 세지 않는다.

    테스트 코드: LC-079
    """
    # given: 계약 2건(계약 첨부 1개)과 Deal 첨부 1개가 있는 Deal, 계약이 없는 Deal
    code = await contract_env.won_deal_without_contract(KIM)
    first = await contract_env.seed_contract(code)
    await contract_env.seed_contract(code, status="ended")
    await contract_env.seed_file(first)
    await contract_env.seed_deal_file(code)
    bare = await contract_env.won_deal_without_contract(KIM)
    # when: 각 Deal의 삭제 영향을 읽는다
    impact = await contract_env.env.impact.execute(code)
    bare_impact = await contract_env.env.impact.execute(bare)
    # then: 첫 Deal은 계약 2건·Deal 첨부 1개, 둘째는 계약 0건
    assert (impact.license_contract_count, impact.attachment_count) == (2, 1)
    assert bare_impact.license_contract_count == 0


async def test_form_update_that_keeps_won_leaves_the_issued_contract_and_count(
    contract_env: ContractEnv,
) -> None:
    """발급 계약이 있는 Won Deal의 금액만 바꾸는 폼 수정은 성공하고 계약은 그대로다.

    테스트 코드: LC-004
    """
    # given: 발급(신규) 계약이 있는 Won Deal
    code = await contract_env.won_deal_without_contract(KIM)
    issued = await contract_env.seed_contract(code, status="issued_new")
    # when: 금액만 바꾸는 폼 수정을 한다
    await contract_env.env.update.execute(code, make_patch(revenue_amount=123_000_000), KIM)
    # then: 요청은 성공하고 계약 수와 발급 계약은 그대로다
    contracts = await contract_env.contracts_of(code)
    assert [(c.id, c.status) for c in contracts] == [(issued.id, ContractStatus.ISSUED_NEW)]
    assert await contract_env.forecast_of(code) == "won"


async def test_registration_response_reports_the_contract_count_and_issued_flag(
    contract_env: ContractEnv,
) -> None:
    """Deal 등록 응답은 자동 생성된 계약 건수와 발급 여부를 담는다.

    테스트 코드: LC-001, LC-002
    """
    # given: KIM(sales)
    won = await contract_env.env.register.execute(
        make_create_input(status_key="contract_completed", forecast_key="won"), KIM
    )
    # when: Won Deal과 Won이 아닌 Deal을 각각 등록한다
    open_view = await contract_env.env.register.execute(make_create_input(), KIM)
    # then: Won Deal 응답은 계약 1건·발급 여부 false, 아닌 Deal 응답은 계약 0건이다
    assert (won.item.license_contract_count, won.item.has_issued_license_contract) == (1, False)
    assert open_view.item.license_contract_count == 0
