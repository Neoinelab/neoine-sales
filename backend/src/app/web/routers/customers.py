from typing import Annotated
from uuid import UUID

from fastapi import Query, Response, status

from app.domain.customer.value_objects import CustomerId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import READ_ERRORS, WRITE_ERRORS
from app.web.schemas.customer import (
    CustomerPage,
    CustomerRequest,
    CustomerResponse,
    CustomerSearchParams,
)

router = BusinessRouter(prefix="/api/v1/customers", tags=["customers"])


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=CustomerResponse, responses=WRITE_ERRORS
)
async def register_customer(
    body: CustomerRequest, response: Response, provider: Provider
) -> CustomerResponse:
    customer = await provider.register_customer().execute(body.to_input())
    response.headers["Location"] = f"{router.prefix}/{customer.id}"
    return CustomerResponse.from_entity(customer)


@router.get("", response_model=CustomerPage, responses=READ_ERRORS)
async def list_customers(
    params: Annotated[CustomerSearchParams, Query()], provider: Provider
) -> CustomerPage:
    query = params.to_query()
    customers = await provider.list_customers().execute(query)
    items = [CustomerResponse.from_entity(c) for c in customers]
    return CustomerPage(items=items, offset=query.offset, limit=query.limit)


@router.get("/{customer_id}", response_model=CustomerResponse, responses=READ_ERRORS)
async def get_customer(customer_id: UUID, provider: Provider) -> CustomerResponse:
    customer = await provider.get_customer().execute(CustomerId(customer_id))
    return CustomerResponse.from_entity(customer)


@router.put("/{customer_id}", response_model=CustomerResponse, responses=WRITE_ERRORS)
async def update_customer(
    customer_id: UUID, body: CustomerRequest, provider: Provider
) -> CustomerResponse:
    customer = await provider.update_customer().execute(CustomerId(customer_id), body.to_input())
    return CustomerResponse.from_entity(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE_ERRORS)
async def delete_customer(customer_id: UUID, provider: Provider) -> None:
    await provider.delete_customer().execute(CustomerId(customer_id))
