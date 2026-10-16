# Fake Port와 계약 테스트

## 목차

1. 왜 Fake인가
2. FakeUnitOfWork / FakeRepository 예
3. 유스케이스 단위 테스트 예
4. 계약 테스트 (Fake와 실제 구현에 같은 테스트)

## 1. 왜 Fake인가

Mock은 "어떤 메서드가 몇 번 호출됐나"를 검증해 구현 세부에 묶인다. Fake(실제로 동작하는 단순한 대체 구현)는 **결과 상태**를 검증하므로 리팩터링에 강하다. Port는 application이 소유하므로 Fake는 `tests/`에서 Port를 구현해 만든다.

## 2. FakeUnitOfWork / FakeRepository 예

```python
# tests/fakes.py  (공용 Fake. 길어지면 파일을 나눈다)
class FakeCustomerRepository:
    def __init__(self) -> None:
        self._items: dict[CustomerId, Customer] = {}

    async def get(self, customer_id: CustomerId) -> Customer:
        try:
            return self._items[customer_id]
        except KeyError:
            raise CustomerNotFoundError(customer_id) from None   # 실제 구현과 같은 계약

    async def add(self, customer: Customer) -> None:
        self._items[customer.id] = customer


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.customers = FakeCustomerRepository()
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if exc[0] is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False
```

Fake는 **실제 구현과 같은 계약**(없으면 `NotFoundError`, 중복이면 `AlreadyExistsError` 등)을 지켜야 한다. 계약이 다르면 단위 테스트가 통과해도 운영에서 실패한다.

## 3. 유스케이스 단위 테스트 예

```python
async def test_register_customer_persists_and_commits() -> None:
    uow = FakeUnitOfWork()
    use_case = RegisterCustomer(uow)

    customer_id = await use_case.execute(RegisterCustomerCommand(name="Kim", email="k@example.com"))

    assert uow.committed
    assert (await uow.customers.get(customer_id)).name == "Kim"
```

`asyncio_mode = "auto"`이므로 `async def` 테스트에 별도 마커가 필요 없다.

## 4. 계약 테스트 (Fake와 실제 구현에 같은 테스트)

Repository 클래스 하나를 검증하므로 **단위 테스트**로 분류하고 `tests/unit/repositories/`에 둔다(SQL 쪽은 실제 임시 DB를 쓰므로 `integration` 마커).

```python
# tests/unit/repositories/test_customer_repository_contract.py
@pytest.fixture(params=["fake", "sql"])
def repo(request: pytest.FixtureRequest, sql_session: AsyncSession) -> CustomerRepository:
    if request.param == "fake":
        return FakeCustomerRepository()
    return SqlCustomerRepository(sql_session)     # 통합 테스트용 임시 DB 필요(db-fixtures.md)


async def test_get_missing_customer_raises_not_found(repo: CustomerRepository) -> None:
    with pytest.raises(CustomerNotFoundError):
        await repo.get(CustomerId("missing"))
```

같은 스위트가 모든 구현을 통과해야 리스코프 치환이 성립한다. 새 Repository 구현을 추가할 때 `params`에 한 줄을 더한다. 실제 DB 구현은 `integration` 층에서만 실행되도록 마커로 분리한다.
