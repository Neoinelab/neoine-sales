# Port 설계 규칙과 코드 예

## 목차

1. Port 설계 규칙
2. Repository + Unit of Work 예
3. 외부 시스템 Gateway 예 (ACL 포함)
4. 조립 (container, web 의존성)
5. 흔한 실수

## 1. Port 설계 규칙

- **외부와의 통신은 전부 Port**: DB(Repository/UoW), 메일·메신저(Notifier), 결제·CRM 등 외부 API(Gateway), 파일 저장소, 시계(`Clock`), ID 생성기.
- **유스케이스 관점으로 이름 짓는다**: 기술이 아니라 필요로 정의한다. `SmtpClient`가 아니라 `Notifier`, `send_order_confirmation(...)`.
- **역할별로 작게 쪼갠다(ISP)**: 쓰기만 필요하면 `Writer`만 받는다.
- **입출력은 도메인 객체·DTO·원시 타입**: ORM 모델, HTTP 응답 객체, Pydantic 스키마는 Port 시그니처에 나타나지 않는다.
- **Repository는 Aggregate Root 단위**로만 정의한다.
- **Anti-Corruption Layer**: 외부 시스템의 모델·오류 체계는 infra 어댑터 안에서 도메인 언어로 번역한 뒤 Port로 반환한다.
- **계약 테스트**: Port마다 같은 테스트 스위트를 Fake와 실제 구현 모두에 실행한다(리스코프 치환 검증).
- 인터페이스 표현은 구조적 계약이 필요하면 `typing.Protocol`, 구현 강제가 필요하면 `abc.ABC`를 쓴다.

## 2. Repository + Unit of Work 예

```python
# application/ports/repositories.py  (Port는 application이 소유)
from typing import Protocol

from app.domain.customer.entities import Customer
from app.domain.customer.value_objects import CustomerId


class CustomerRepository(Protocol):
    async def get(self, customer_id: CustomerId) -> Customer: ...   # 없으면 CustomerNotFoundError
    async def add(self, customer: Customer) -> None: ...


# application/ports/unit_of_work.py
from typing import Protocol, Self


class UnitOfWork(Protocol):
    customers: CustomerRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

```python
# infra/db/repositories.py  (구현은 infra: application의 Port를 import하는 방향)
from sqlalchemy.ext.asyncio import AsyncSession


class SqlCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, customer_id: CustomerId) -> Customer:
        ...  # ORM 모델 -> 도메인 엔티티 변환은 여기서
```

```python
# application/customer/register_customer.py  (유스케이스는 Port만 안다)
class RegisterCustomer:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, command: RegisterCustomerCommand) -> CustomerId:
        async with self._uow:
            customer = Customer.register(command.name, command.email)   # 규칙은 도메인
            await self._uow.customers.add(customer)
            await self._uow.commit()
        return customer.id
```

## 3. 외부 시스템 Gateway 예 (ACL 포함)

```python
# application/ports/payment_gateway.py
class PaymentGateway(Protocol):
    async def charge(self, order_id: OrderId, amount: Money) -> PaymentResult: ...


# infra/external/payment.py
class HttpPaymentGateway:
    def __init__(self, base_url: str, api_key: SecretStr, client: httpx.AsyncClient) -> None: ...

    async def charge(self, order_id: OrderId, amount: Money) -> PaymentResult:
        response = await self._client.post(...)                  # 외부 응답 모델
        return self._to_result(response.json())                  # ACL: 도메인 언어로 번역
```

외부 오류 코드·필드명은 `_to_result` 안에서 `PaymentResult`/도메인 예외로 번역한다. `application`에는 외부 모델이 나타나지 않는다.

## 4. 조립 (container, web 의존성)

```python
# container.py  (유일하게 구현체를 선택하는 곳)
class Container:
    def __init__(self, settings: Settings) -> None:
        self._session_factory = create_session_factory(str(settings.database_url))

    def register_customer(self) -> RegisterCustomer:
        return RegisterCustomer(SqlUnitOfWork(self._session_factory))


# web/dependencies.py  (web은 infra를 import하지 않고 container에서 꺼낸다)
def get_register_customer(request: Request) -> RegisterCustomer:
    return request.app.state.container.register_customer()
```

테스트에서는 `Container` 대신 Fake Port(`FakeUnitOfWork`)로 유스케이스를 직접 만들거나 `app.dependency_overrides`로 교체한다.

## 5. 흔한 실수

| 실수 | 올바른 방법 |
| --- | --- |
| Port를 `infra`나 `domain`에 둔다 | `application/ports`에 둔다(이 프로젝트의 결정) |
| Port 시그니처에 `AsyncSession`, `Response`, Pydantic 모델 | 도메인 객체·DTO·원시 타입 |
| 하나의 거대한 `Storage`/`Repository` 인터페이스 | 역할별로 작게 분리 |
| 유스케이스에서 `SqlXxx()` 직접 생성 | 생성자 주입 + container 조립 |
| 외부 API 응답을 그대로 유스케이스에 전달 | infra 어댑터에서 번역(ACL) |
