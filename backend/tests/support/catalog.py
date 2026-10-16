"""코드·Label 단위 테스트 공통 도우미: key·이름으로 조회, Status별 Deal 준비."""

from typing import TYPE_CHECKING

from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.domain.bant.entities import BantLabel
    from app.domain.bant.values import BantCategory
    from app.domain.code.entities import Code
    from app.domain.code.values import CodeKind
    from tests.fakes.unit_of_work import FakeUnitOfWork

WON_STATUS = "contract_completed"  # 계약완료는 Forecast Won과 함께만 존재한다(동기화 불변식)


async def code_by_key(uow: FakeUnitOfWork, kind: CodeKind, key: str) -> Code:
    codes = [c for c in await uow.codes.list(kind) if c.key.value == key]
    assert len(codes) == 1, (kind, key)
    return codes[0]


async def label_by_name(uow: FakeUnitOfWork, category: BantCategory, name: str) -> BantLabel:
    labels = [x for x in await uow.bant_labels.list(category) if x.name == name]
    assert len(labels) == 1, (category, name)
    return labels[0]


async def add_deals_with_status(uow: FakeUnitOfWork, status_key: str, count: int) -> None:
    """Status 사용 수는 deals.status_key 기준이다. 해당 Status의 Deal을 count건 저장한다.

    Deal이 참조하는 고객 연락처도 함께 저장한다. 계약완료는 동기화 불변식 때문에 Forecast를
    Won으로 둔다.
    """
    from tests.factories_contact import make_customer  # noqa: PLC0415 - 연락처 구현 지연 import

    forecast_key = "won" if status_key == WON_STATUS else "pipeline"
    for _ in range(count):
        number = len(uow.deals._items) + 1
        customer = make_customer(company=f"고객{number}")
        await uow.contacts.add(customer)
        await uow.deals.add(
            make_deal(
                later(number),
                code=f"20261016-{number:04d}",
                customer_id=customer.id,
                status_key=status_key,
                forecast_key=forecast_key,
            )
        )
