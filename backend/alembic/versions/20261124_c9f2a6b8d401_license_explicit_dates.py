from typing import Final

import sqlalchemy as sa
from alembic import op

revision = "c9f2a6b8d401"
down_revision = "b3a8d1f6c527"
branch_labels = None
depends_on = None

_NEW: Final = (
    "(license_start is null) = (license_end is null)"
    " and (term_amount is null) = (term_unit is null)"
    " and (term_amount is null or license_start is not null)"
)
_OLD: Final = (
    "(license_start is null) = (license_end is null)"
    " and (license_start is null) = (term_amount is null)"
    " and (license_start is null) = (term_unit is null)"
)


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_license_contracts_term_complete"), "license_contracts", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_license_contracts_term_complete"), "license_contracts", _NEW
    )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "select count(*) from license_contracts where license_start is not null and term_amount is null"
            )
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "종료일을 직접 지정한 계약이 있어 이전 기간 방식으로 되돌릴 수 없습니다."
        )
    op.drop_constraint(
        op.f("ck_license_contracts_term_complete"), "license_contracts", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_license_contracts_term_complete"), "license_contracts", _OLD
    )
