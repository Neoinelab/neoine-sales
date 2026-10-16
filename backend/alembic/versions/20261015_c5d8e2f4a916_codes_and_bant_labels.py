"""코드(Status·Forecast)와 BANT Label 테이블, 기본값 시드 (P0 M-P0, R1분)

Revision ID: c5d8e2f4a916
Revises: 0d248153ec93
Create Date: 2026-10-15 09:00:00.000000

expand 단계: 새 테이블 2개와 시드만 추가한다. 기존 테이블·데이터는 건드리지 않아 구 앱과 호환된다.

- codes: Status 7개, Forecast 6개(outcome, 확률 힌트는 EN DASH). 같은 종류 안에서 key와 lower(name) 유니크.
- bant_labels: 기본 Label 23개(created_by_user_id = NULL, default_order = 구분 안 1부터). 같은 구분 안에서
  lower(name) 유니크. created_by_user_id는 users.id FK(RESTRICT)라 Label 생성자는 삭제 대신 퇴사 처리된다.

시드 값은 tests/fakes/catalog_seed.py와 같다(functional test_catalog_seed가 대조). 코드 R2·R3의 스키마
변경이 같은 리비전에 합쳐질 때는 이 파일에 이어 붙인다.

downgrade: 두 테이블을 지워 구조를 복원한다(사용자가 만든 코드·Label 데이터는 사라진다).
"""

import uuid
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5d8e2f4a916"
down_revision: Union[str, Sequence[str], None] = "0d248153ec93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DASH = chr(0x2013)
# (key, 이름)
_STATUSES = (
    ("prospecting", "기회발굴"),
    ("introduction", "제품소개"),
    ("poc_preparation", "POC준비"),
    ("poc_completed", "POC완료"),
    ("technical_evaluation", "기술평가"),
    ("price_negotiation", "가격협상"),
    ("contract_completed", "계약완료"),
)
# (key, 이름, outcome, 확률 힌트)
_FORECASTS = (
    ("pipeline", "Pipeline", "open", f"0{_DASH}50"),
    ("best", "Best", "open", f"51{_DASH}75"),
    ("most_likely", "Most Likely", "open", f"75{_DASH}85"),
    ("commit", "Commit", "open", f"85{_DASH}100"),
    ("won", "Won", "won", None),
    ("lost", "Lost", "lost", None),
)
_LABELS = {
    "budget": (
        "단독 예산 확보",
        "풀 예산 확보",
        "잔여 예산 활용",
        "예산 작업중",
        "내년 예산",
        "예산 없음",
        "미확인",
    ),
    "authority": (
        "CEO 보고 완료",
        "CISO 보고 완료",
        "팀장 보고 완료",
        "팀장 검토",
        "담당자 검토",
        "모름",
    ),
    "need": ("보안 사고 발생", "CISO 지시", "보안 강화 요건", "컴플라이언스", "모름"),
    "timeline": ("금년 구매", "POC 후 일정수립", "기술평가만 진행", "내년구매", "미확정"),
}


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _create_codes() -> None:
    op.create_table(
        "codes",
        *_audit_columns(),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("probability_hint", sa.String(length=20), nullable=True),
        sa.CheckConstraint("kind in ('status', 'forecast')", name=op.f("ck_codes_kind_valid")),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]{0,49}$'", name=op.f("ck_codes_key_format")),
        sa.CheckConstraint("sort_order >= 1", name=op.f("ck_codes_order_positive")),
        sa.CheckConstraint(
            "outcome in ('open', 'won', 'lost')", name=op.f("ck_codes_outcome_valid")
        ),
        sa.CheckConstraint(
            "kind <> 'status' or outcome = 'open'", name=op.f("ck_codes_status_outcome_open")
        ),
        sa.CheckConstraint(
            "kind <> 'status' or probability_hint is null",
            name=op.f("ck_codes_hint_forecast_only"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codes")),
    )
    op.create_index("uq_codes_kind_key", "codes", ["kind", "key"], unique=True)
    op.create_index(
        "uq_codes_kind_name_lower", "codes", ["kind", sa.literal_column("lower(name)")], unique=True
    )
    op.create_index("ix_codes_kind_sort_order", "codes", ["kind", "sort_order"])


def _create_bant_labels() -> None:
    op.create_table(
        "bant_labels",
        *_audit_columns(),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("default_order", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "category in ('budget', 'authority', 'need', 'timeline')",
            name=op.f("ck_bant_labels_category_valid"),
        ),
        sa.CheckConstraint(
            "is_default = (default_order is not null)", name=op.f("ck_bant_labels_default_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_bant_labels_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bant_labels")),
    )
    op.create_index(
        "uq_bant_labels_category_name_lower",
        "bant_labels",
        ["category", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index("ix_bant_labels_created_by_user_id", "bant_labels", ["created_by_user_id"])


def _seed() -> None:
    now = datetime.now(UTC)
    audit = {"created_at": now, "updated_at": now}
    codes = sa.table(
        "codes",
        sa.column("id", sa.Uuid()),
        sa.column("kind", sa.String()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("outcome", sa.String()),
        sa.column("probability_hint", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = [
        {
            "id": uuid.uuid4(),
            "kind": "status",
            "key": key,
            "name": name,
            "sort_order": index,
            "outcome": "open",
            "probability_hint": None,
            **audit,
        }
        for index, (key, name) in enumerate(_STATUSES, start=1)
    ]
    rows += [
        {
            "id": uuid.uuid4(),
            "kind": "forecast",
            "key": key,
            "name": name,
            "sort_order": index,
            "outcome": outcome,
            "probability_hint": hint,
            **audit,
        }
        for index, (key, name, outcome, hint) in enumerate(_FORECASTS, start=1)
    ]
    op.bulk_insert(codes, rows)
    labels = sa.table(
        "bant_labels",
        sa.column("id", sa.Uuid()),
        sa.column("category", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("default_order", sa.Integer()),
        sa.column("created_by_user_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        labels,
        [
            {
                "id": uuid.uuid4(),
                "category": category,
                "name": name,
                "is_default": True,
                "default_order": index,
                "created_by_user_id": None,
                **audit,
            }
            for category, names in _LABELS.items()
            for index, name in enumerate(names, start=1)
        ],
    )


def upgrade() -> None:
    """Upgrade schema."""
    _create_codes()
    _create_bant_labels()
    _seed()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_bant_labels_created_by_user_id", table_name="bant_labels")
    op.drop_index("uq_bant_labels_category_name_lower", table_name="bant_labels")
    op.drop_table("bant_labels")
    op.drop_index("ix_codes_kind_sort_order", table_name="codes")
    op.drop_index("uq_codes_kind_name_lower", table_name="codes")
    op.drop_index("uq_codes_kind_key", table_name="codes")
    op.drop_table("codes")
