"""저장 리포트 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

팩토리는 정규화·권한·중복 검사를 거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가
팩토리에 기대지 않도록). 도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른
테스트의 수집이 막히지 않게).

계약(구현 담당이 맞춘다): `Report`는 키워드로 만들 수 있는 dataclass이고 필드는
id, name, description, visibility, owner_user_id, updated_by_user_id, definition,
generated_sql, revision, created_at, updated_at 이다.
"""

from typing import TYPE_CHECKING, Any

from tests.factories import NOW
from tests.support.ids import new_id
from tests.support.report_defs import col, raw

if TYPE_CHECKING:
    from app.domain.saved_report.entities import Report
    from app.domain.saved_report.values import ReportContent
    from app.domain.user.value_objects import UserId

DEFAULT_SQL = "SELECT deals.deal_code FROM deals"


def make_report(
    name: str = "분기 Pipeline",
    owner: UserId | None = None,
    **overrides: Any,  # noqa: ANN401 - 필드를 그대로 덮어쓴다
) -> Report:
    """저장하지 않은 Report. overrides: visibility('public'|'private'|ReportVisibility), editor,
    definition, generated_sql, revision, description, now, report_id.
    """
    from app.domain.saved_report.entities import Report  # noqa: PLC0415 - 지연 import(모듈 설명)
    from app.domain.saved_report.values import ReportId, ReportVisibility  # noqa: PLC0415
    from tests.support.user_ids import OWNER_ID  # noqa: PLC0415

    owner_id = owner if owner is not None else OWNER_ID
    now = overrides.pop("now", NOW)
    return Report(
        id=overrides.pop("report_id", ReportId(new_id())),
        name=name,
        description=overrides.pop("description", ""),
        visibility=ReportVisibility(overrides.pop("visibility", "public")),
        owner_user_id=owner_id,
        updated_by_user_id=overrides.pop("editor", owner_id),
        definition=overrides.pop("definition", raw([col("deal.code")])),
        generated_sql=overrides.pop("generated_sql", DEFAULT_SQL),
        revision=overrides.pop("revision", 1),
        created_at=now,
        updated_at=overrides.pop("updated_at", now),
    )


def make_broken_report(
    name: str = "깨진 리포트",
    owner: UserId | None = None,
    **overrides: Any,  # noqa: ANN401 - make_report와 같다
) -> Report:
    """저장된 정의 JSON을 읽을 수 없는 상태의 Report(`definition is None`).

    계약(계획 11.2, core가 맞춘다): `Report.definition`은 `RawReportDefinition | None`이고
    None이 "읽을 수 없는 저장 정의"다. 이 상태의 `entities()`는 빈 튜플이고, 정의가 필요한 연산
    `readable_definition()`은 ReportDefinitionError(stored-invalid, 위치 ("definition",))를 낸다.
    """
    return make_report(name, owner, definition=None, **overrides)


def make_content(name: str = "새 이름", **overrides: Any) -> ReportContent:  # noqa: ANN401
    """덮어쓰기·생성 입력용 ReportContent(정규화가 끝난 값). overrides: description, visibility,
    definition, generated_sql.
    """
    from app.domain.saved_report.values import (  # noqa: PLC0415
        ReportContent,
        ReportVisibility,
    )

    return ReportContent(
        name=name,
        description=overrides.pop("description", ""),
        visibility=ReportVisibility(overrides.pop("visibility", "public")),
        definition=overrides.pop("definition", raw([col("deal.code")])),
        generated_sql=overrides.pop("generated_sql", DEFAULT_SQL),
    )
