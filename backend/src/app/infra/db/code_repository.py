"""CodeRepository Port의 SQLAlchemy 구현. 이름·key 고유성은 DB 유니크 인덱스가 보장한다."""

from typing import TYPE_CHECKING

from sqlalchemy import case, func, select, text

from app.domain.code.entities import Code
from app.domain.code.errors import CodeInUseError, CodeNotFoundError, DuplicateCodeNameError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import AlreadyExistsError
from app.infra.db.base_repository import ConstraintErrors, SqlRepository
from app.infra.db.models import DealActionRow
from app.infra.db.models_catalog import CodeRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy.orm import InstrumentedAttribute

# 코드 종류별 트랜잭션 advisory lock 키. 명단 잠금(7_301_001)과 다른 대역을 쓰고, 종류마다
# 명시한 고정 키를 갖는다(CodeKind 선언 순서가 바뀌어도 키가 바뀌지 않는다).
KIND_LOCK_KEYS: Mapping[CodeKind, int] = {
    CodeKind.STATUS: 7_302_001,
    CodeKind.FORECAST: 7_302_002,
}
_IN_USE_CONSTRAINTS = (
    "fk_deals_status_code",
    "fk_deals_forecast_code",
    "fk_deal_actions_status_code",
    "fk_deal_actions_forecast_code",
)
_KIND_ORDER = case({kind.value: index for index, kind in enumerate(CodeKind)}, value=CodeRow.kind)


def _to_row(code: Code) -> CodeRow:
    return CodeRow(
        id=code.id,
        kind=code.kind.value,
        key=code.key.value,
        name=code.name,
        sort_order=code.order,
        outcome=code.outcome.value,
        probability_hint=code.probability_hint,
        created_at=code.created_at,
        updated_at=code.updated_at,
    )


def _to_entity(row: CodeRow) -> Code:
    return Code(
        id=CodeId(row.id),
        kind=CodeKind(row.kind),
        key=CodeKey(row.key),
        name=row.name,
        order=row.sort_order,
        outcome=ForecastOutcome(row.outcome),
        probability_hint=row.probability_hint,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _write_errors(code: Code) -> ConstraintErrors:
    return {
        "uq_codes_kind_name_lower": lambda: DuplicateCodeNameError(code.name),
        "uq_codes_kind_key": lambda: AlreadyExistsError("코드 key", code.key.value),
        "pk_codes": lambda: AlreadyExistsError("코드", code.id),
    }


class SqlCodeRepository(SqlRepository[CodeRow]):
    row_type = CodeRow

    async def list(
        self, kind: CodeKind | None = None, *, for_update: bool = False
    ) -> Sequence[Code]:
        statement = select(CodeRow).order_by(_KIND_ORDER, CodeRow.sort_order, CodeRow.id)
        if kind is not None:
            statement = statement.where(CodeRow.kind == kind.value)
        if for_update:
            statement = statement.with_for_update()
        rows = (
            await self._session.scalars(statement.execution_options(populate_existing=True))
        ).all()
        return [_to_entity(row) for row in rows]

    async def lock_kind(self, kind: CodeKind) -> None:
        await self._session.execute(
            text("select pg_advisory_xact_lock(:key)"), {"key": KIND_LOCK_KEYS[kind]}
        )

    async def get(self, code_id: CodeId) -> Code:
        row = await self._find(code_id)
        if row is None:
            raise CodeNotFoundError(code_id)
        return _to_entity(row)

    async def add(self, code: Code) -> None:
        await self._insert(_to_row(code), _write_errors(code))

    async def update(self, code: Code) -> None:
        row = await self._find(code.id)
        if row is None:
            raise CodeNotFoundError(code.id)
        # 이름 변경·순서 변경이 쓰는 열만 쓴다. outcome·probability_hint는 변경 경로가 없으므로
        # 낡은 엔티티 값으로 다른 트랜잭션의 결과를 덮어쓰지 않도록 건드리지 않는다.
        row.name = code.name
        row.sort_order = code.order
        row.updated_at = code.updated_at
        await self._save(_write_errors(code), not_found=lambda: CodeNotFoundError(code.id))

    async def delete(self, code_id: CodeId) -> None:
        row = await self._find(code_id)
        if row is None:
            raise CodeNotFoundError(code_id)
        in_use: ConstraintErrors = {name: lambda: CodeInUseError(1) for name in _IN_USE_CONSTRAINTS}
        kind, key = row.kind, row.key
        try:
            await self._remove(row, in_use)
        except CodeInUseError:
            # Deal이 쓰면 Deal 수가 먼저, Deal은 없고 Action만 쓰면 Action 수.
            deals = await self._linked(DealRow.status_key, DealRow.forecast_key, kind, key)
            if deals:
                raise CodeInUseError(deals) from None
            actions = await self._linked(
                DealActionRow.status_key, DealActionRow.forecast_key, kind, key
            )
            raise CodeInUseError(max(actions, 1), "Action" if actions else "Deal") from None

    async def _linked(
        self,
        status_column: InstrumentedAttribute[str],
        forecast_column: InstrumentedAttribute[str],
        kind: str,
        key: str,
    ) -> int:
        column = status_column if kind == CodeKind.STATUS.value else forecast_column
        table = column.class_
        count = select(func.count()).select_from(table).where(column == key)
        return int(await self._session.scalar(count) or 0)
