"""업무 테이블을 비우는 도우미(테스트 사이 격리용).

스키마 마이그레이션 테스트 중에는 `contacts`가 없을 수 있어, 지금 DB에 있는 테이블만 이름에 넣는다.
이름은 모두 이 모듈의 상수다.
`users`를 CASCADE로 비우면 users를 참조하는 테이블(deals, 활동, Label 등)까지 비워지지만,
연락처 테이블은 Deal이 참조하는 쪽이라 따로 비워야 한다.
"""

from typing import TYPE_CHECKING, Final

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

ALWAYS: Final = (
    "auth_sessions",
    "users",
    "login_failures",
    "directory_settings",
    "deal_actions",
    "deals",
)
CONTACT_TABLES: Final = ("contacts",)
# P1 새 Deal 모델의 소속 테이블. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다.
DEAL_TABLES: Final = ("deal_history", "deal_partners", "deal_bant_labels")
# P2b 파일 테이블. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(users CASCADE로도 비워진다).
FILE_TABLES: Final = ("deal_attachments", "storage_settings")
# P3 경고 기준. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(users CASCADE로도 비워진다).
ALERT_TABLES: Final = ("alert_settings",)
# Vendor 관리. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(deals가 참조).
# `solutions`는 Solution 텍스트 리비전이 지웠지만 그 아래 리비전 DB(과거 스키마 테스트)엔 있다.
VENDOR_TABLES: Final = ("solutions", "vendors")
# Forecast 월말 스냅숏(P6 R2). 셀은 users CASCADE로 비워지지만 열·헤더는 아니므로 함께 비운다.
FORECAST_TABLES: Final = (
    "forecast_snapshot_cells",
    "forecast_snapshot_columns",
    "forecast_snapshots",
)
# 마이그레이션이 기본 행을 심는 users 참조 테이블(기본 행은 created_by_user_id가 없어 되살린다).
SEEDED_TABLES: Final = ("bant_labels", "action_types")


async def existing_tables(connection: AsyncConnection) -> set[str]:
    rows = await connection.execute(
        text("select tablename from pg_tables where schemaname = 'public'")
    )
    return {str(row[0]) for row in rows}


async def truncate_business_tables(connection: AsyncConnection) -> None:
    """사용자·Deal·활동·연락처 테이블을 비운다.

    `bant_labels.created_by_user_id`·`action_types.created_by_user_id`가 users를 참조해 CASCADE가
    Label·Action 유형까지 비우므로, 마이그레이션이 심은 기본 행(created_by_user_id 없음)은 비운 뒤
    되살린다. 이 DB는 세션 전체가 공유해서 기본 행이 사라지면 뒤에 도는 스키마 테스트가 시드를
    못 찾는다. (deal_actions는 이 truncate로 함께 비워지므로 유형을 되살려도 참조가 남지 않는다.)
    """
    present = await existing_tables(connection)
    optional = (
        *DEAL_TABLES,
        *FILE_TABLES,
        *ALERT_TABLES,
        *VENDOR_TABLES,
        *FORECAST_TABLES,
        *CONTACT_TABLES,
    )
    names = [*ALWAYS, *(name for name in optional if name in present)]
    kept = [table for table in SEEDED_TABLES if table in present]
    for table in kept:
        await connection.execute(
            text(
                f"create temp table _seed_{table} on commit drop as"  # noqa: S608 - 상수 이름
                f" select * from {table} where created_by_user_id is null"
            )
        )
    await connection.execute(text(f"truncate {', '.join(names)} cascade"))
    for table in kept:
        await connection.execute(text(f"insert into {table} select * from _seed_{table}"))  # noqa: S608
