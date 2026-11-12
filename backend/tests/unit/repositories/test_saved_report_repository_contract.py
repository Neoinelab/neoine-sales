"""ReportRepository(저장 리포트) 계약: Fake와 SQL 구현에 같은 테스트.

SQL 구현은 실제 PostgreSQL이다.

이름은 모든 리포트 사이에서 고유하다(테스트마다 롤백되는 세션이라 이름이 겹치지 않는다).
목록은 `mine`으로 자기 행만 비교한다.
정렬 계약: `updated_at` 내림차순, 동률은 id 내림차순.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.saved_report.errors import DuplicateReportNameError, ReportNotFoundError
from app.domain.saved_report.values import ReportId, ReportListScope, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_content, make_report
from tests.support.ids import new_id
from tests.support.report_defs import col, cond, raw
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.saved_report_case import SavedReportCase

ALICE = uid("contract-alice")
BOB = uid("contract-bob")
CAROL = uid("contract-carol")


def _scope(viewer: int, *, see_all: bool = False) -> ReportListScope:
    return ReportListScope(viewer_id=viewer, see_all=see_all)  # type: ignore[arg-type]


async def test_add_and_get_round_trip_keeps_definition_json(
    saved_report_case: SavedReportCase,
) -> None:
    """저장한 리포트를 다시 읽어도 정의 JSON·설명·공개 범위·SQL·시각이 그대로다."""
    # given: 컬럼·조건·결합·행 수를 모두 쓴 정의의 비공개 리포트
    definition = raw(
        [
            col("deal.vendor", group=True, label="벤더 이름"),
            col("deal.amount", aggregate="sum", sort="desc"),
        ],
        [
            cond("deal.status", "in", ["prospecting", "introduction"]),
            cond("deal.amount", "between", [1000, 50000]),
            cond("deal.expected_close", "relative", {"period": "last_n_days", "days": 7}),
            cond("deal.name", "is_empty", None),
            cond("deal.vendor", "in", [1, 2]),
        ],
        combine="or",
        row_limit=10000,
    )
    report = make_report(
        "한글 이름 리포트",
        owner=ALICE,
        description="설명 줄1\n줄2",
        visibility="private",
        definition=definition,
        generated_sql="SELECT 1 -- 한글",
        revision=1,
    )
    await saved_report_case.add(report)
    # when: 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)
    # then: 저장한 값이 그대로다
    assert stored == report
    assert stored.name == "한글 이름 리포트"
    assert stored.description == "설명 줄1\n줄2"
    assert stored.visibility is ReportVisibility.PRIVATE
    assert stored.definition == definition
    assert stored.generated_sql == "SELECT 1 -- 한글"
    assert (stored.owner_user_id, stored.updated_by_user_id) == (ALICE, ALICE)
    assert stored.revision == 1
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)


async def test_empty_description_and_public_visibility_round_trip(
    saved_report_case: SavedReportCase,
) -> None:
    """빈 설명과 공개 범위 public도 그대로 저장된다."""
    # given: 설명이 빈 공개 리포트
    report = make_report("빈 설명", owner=ALICE, description="", visibility="public")
    await saved_report_case.add(report)
    # when: 다시 읽는다
    stored = await saved_report_case.reports.get(report.id)
    # then: 빈 설명과 public이다
    assert (stored.description, stored.visibility) == ("", ReportVisibility.PUBLIC)


async def test_get_missing_report_raises_not_found(saved_report_case: SavedReportCase) -> None:
    """없는 id를 읽으면 찾을 수 없음 오류다."""
    # when·then: 없는 id를 읽으면 오류다
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(ReportId(new_id()))


async def test_get_for_update_returns_the_same_report(saved_report_case: SavedReportCase) -> None:
    """잠금 읽기(for_update)도 같은 리포트를 돌려준다."""
    # given: 저장된 리포트
    report = await saved_report_case.add(make_report("잠금", owner=ALICE))
    # when: 잠금 읽기로 읽는다
    locked = await saved_report_case.reports.get(report.id, for_update=True)
    # then: 같은 리포트다
    assert locked.name == "잠금"


async def test_name_is_unique_ignoring_case_for_the_same_owner(
    saved_report_case: SavedReportCase,
) -> None:
    """같은 사람이 대소문자만 다른 이름으로 저장하면 이름 중복 오류다.

    테스트 코드: RS-008
    """
    # given: "Sales Report"가 저장되어 있다
    await saved_report_case.add(make_report("Sales Report", owner=ALICE))
    # when·then: 같은 사람이 "sales report"를 저장하면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.add(make_report("sales report", owner=ALICE))


async def test_name_is_unique_ignoring_case_across_owners_and_visibility(
    saved_report_case: SavedReportCase,
) -> None:
    """만든 사람·공개 범위와 무관하게 대소문자만 다른 이름은 이름 중복 오류다.

    테스트 코드: RS-008
    """
    # given: ALICE의 비공개 "Team Report"
    await saved_report_case.add(make_report("Team Report", owner=ALICE, visibility="private"))
    # when·then: BOB이 공개로 "TEAM REPORT"를 저장하면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.add(make_report("TEAM REPORT", owner=BOB, visibility="public"))


async def test_update_to_another_reports_name_of_the_same_owner_raises_duplicate(
    saved_report_case: SavedReportCase,
) -> None:
    """같은 사람의 다른 리포트 이름으로 바꿔 저장하면 이름 중복 오류다.

    테스트 코드: RS-022
    """
    # given: ALICE의 "첫째"와 "둘째", "둘째"를 "첫째"로 덮어쓴 엔티티
    await saved_report_case.add(make_report("첫째", owner=ALICE))
    second = await saved_report_case.add(make_report("둘째", owner=ALICE))
    second.overwrite(
        make_content("첫째"), editor=ALICE, role=Role.SALES, expected_revision=1, now=later(1)
    )
    # when·then: 저장하면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.reports.update(second)


async def test_update_to_the_name_of_another_owners_report_raises_duplicate(
    saved_report_case: SavedReportCase,
) -> None:
    """다른 사람의 리포트 이름으로 바꿔 저장해도 이름 중복 오류다.

    테스트 코드: RS-022
    """
    # given: ALICE의 "공통 이름"과 BOB의 "다른 이름"을 "공통 이름"으로 덮어쓴 엔티티
    await saved_report_case.add(make_report("공통 이름", owner=ALICE))
    mine = await saved_report_case.add(make_report("다른 이름", owner=BOB))
    mine.overwrite(
        make_content("공통 이름"), editor=BOB, role=Role.SALES, expected_revision=1, now=later(1)
    )
    # when·then: 저장하면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await saved_report_case.reports.update(mine)


async def test_renaming_a_report_to_its_own_name_in_another_case_is_stored(
    saved_report_case: SavedReportCase,
) -> None:
    """자기 이름을 대소문자만 바꿔 저장하는 것은 된다.

    테스트 코드: RS-009
    """
    # given: "sales"를 "SALES"로 덮어쓴 엔티티
    report = await saved_report_case.add(make_report("sales", owner=ALICE))
    report.overwrite(
        make_content("SALES"), editor=ALICE, role=Role.SALES, expected_revision=1, now=later(1)
    )
    # when: 저장한다
    await saved_report_case.reports.update(report)
    # then: 이름이 "SALES"로 저장된다
    assert (await saved_report_case.reports.get(report.id)).name == "SALES"


async def test_list_filters_by_scope_and_orders_by_updated_at_then_id(
    saved_report_case: SavedReportCase,
) -> None:
    """목록은 범위(공개·자기 것 / admin 전부)로 거르고 수정 시각 내림차순, 동률은 id 내림차순이다.

    테스트 코드: RS-010
    """
    # given: 공개·비공개와 동률 수정 시각이 섞인 리포트 여섯 개
    mine_private = make_report("내 비공개", owner=ALICE, visibility="private", updated_at=later(10))
    mine_public = make_report("내 공개", owner=ALICE, visibility="public", updated_at=later(30))
    bobs_public = make_report("밥 공개", owner=BOB, visibility="public", updated_at=later(20))
    bobs_private = make_report("밥 비공개", owner=BOB, visibility="private", updated_at=later(40))
    tie_low = make_report("동률 먼저", owner=CAROL, visibility="public", updated_at=later(20))
    tie_high = make_report("동률 나중", owner=CAROL, visibility="public", updated_at=later(20))
    assert tie_high.id > tie_low.id
    everything = [mine_private, mine_public, bobs_public, bobs_private, tie_low, tie_high]
    for report in everything:
        await saved_report_case.add(report)
    ids = {r.id for r in everything}
    # when: ALICE 범위와 admin 범위로 목록을 읽는다
    for_alice = await saved_report_case.mine(_scope(ALICE), ids)
    for_admin = await saved_report_case.mine(_scope(ALICE, see_all=True), ids)
    # then: 수정 시각 내림차순이고 같은 시각(20)은 id 내림차순이며 admin에게만 남의 비공개가 있다
    assert [r.name for r in for_alice] == [
        "내 공개",
        "동률 나중",
        "동률 먼저",
        "밥 공개",
        "내 비공개",
    ]
    assert [r.name for r in for_admin] == [
        "밥 비공개",
        "내 공개",
        "동률 나중",
        "동률 먼저",
        "밥 공개",
        "내 비공개",
    ]


async def test_list_hides_others_private_reports_from_a_non_admin_scope(
    saved_report_case: SavedReportCase,
) -> None:
    """남의 비공개 리포트는 admin이 아닌 범위의 목록에 없고 만든 사람에게는 있다.

    테스트 코드: RS-010
    """
    # given: BOB의 비공개 리포트
    hidden = await saved_report_case.add(make_report("숨김", owner=BOB, visibility="private"))
    # when: ALICE 범위와 BOB 범위로 조회한다
    alice_rows = await saved_report_case.mine(_scope(ALICE), {hidden.id})
    bob_rows = await saved_report_case.mine(_scope(BOB), {hidden.id})
    # then: ALICE 범위에는 없고 BOB 범위에는 있다
    assert alice_rows == []
    assert [r.id for r in bob_rows] == [hidden.id]


async def test_update_changes_all_editable_fields_and_keeps_owner_and_created_at(
    saved_report_case: SavedReportCase,
) -> None:
    """덮어쓴 엔티티를 저장하면 편집 필드가 모두 바뀌고 만든 사람·생성 시각은 그대로다.

    테스트 코드: RS-016
    """
    # given: ALICE의 공개 리포트와 BOB(admin)이 덮어쓴 엔티티
    report = await saved_report_case.add(
        make_report("원본", owner=ALICE, visibility="public", description="옛")
    )
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    await saved_report_case.prepare(BOB)
    report.overwrite(
        make_content(
            "수정본",
            description="새 설명",
            visibility="public",
            definition=definition,
            generated_sql="SELECT edited",
        ),
        editor=BOB,
        role=Role.ADMIN,
        expected_revision=1,
        now=later(100),
    )
    # when: 저장하고 다시 읽는다
    await saved_report_case.reports.update(report)
    stored = await saved_report_case.reports.get(report.id)
    # then: 편집 필드와 최종 수정자·revision·수정 시각이 바뀌고 만든 사람·생성 시각은 그대로다
    assert (stored.name, stored.description) == ("수정본", "새 설명")
    assert stored.definition == definition
    assert stored.generated_sql == "SELECT edited"
    assert stored.updated_by_user_id == BOB
    assert stored.revision == 2
    assert stored.updated_at == later(100)
    assert stored.owner_user_id == ALICE
    assert stored.created_at == NOW


async def test_update_stores_a_visibility_change(saved_report_case: SavedReportCase) -> None:
    """공개 범위 변경도 저장된다.

    테스트 코드: RS-020
    """
    # given: 공개 리포트를 private으로 덮어쓴 엔티티
    report = await saved_report_case.add(make_report("공개였음", owner=ALICE, visibility="public"))
    report.overwrite(
        make_content("공개였음", visibility="private"),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )
    # when: 저장한다
    await saved_report_case.reports.update(report)
    # then: 공개 범위가 private으로 저장된다
    assert (await saved_report_case.reports.get(report.id)).visibility is ReportVisibility.PRIVATE


async def test_delete_removes_only_that_report(saved_report_case: SavedReportCase) -> None:
    """삭제하면 그 리포트만 사라진다.

    테스트 코드: RS-024
    """
    # given: ALICE의 리포트 두 개
    gone = await saved_report_case.add(make_report("삭제", owner=ALICE))
    kept = await saved_report_case.add(make_report("유지", owner=ALICE))
    # when: 하나를 삭제한다
    await saved_report_case.reports.delete(gone.id)
    # then: 지운 것은 없고 나머지는 남는다
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(gone.id)
    assert (await saved_report_case.reports.get(kept.id)).name == "유지"


async def test_a_deleted_reports_name_can_be_used_again(
    saved_report_case: SavedReportCase,
) -> None:
    """지운 리포트의 이름은 다시 쓸 수 있다.

    테스트 코드: RS-009
    """
    # given: 저장했다가 지운 "재사용"
    gone = await saved_report_case.add(make_report("재사용", owner=ALICE))
    await saved_report_case.reports.delete(gone.id)
    # when: 같은 이름으로 다시 저장한다
    await saved_report_case.add(make_report("재사용", owner=ALICE))
    # then: 오류 없이 저장된다


async def test_missing_id_raises_not_found_for_get_update_and_delete(
    saved_report_case: SavedReportCase,
) -> None:
    """없는 id의 읽기·수정·삭제는 모두 찾을 수 없음 오류다.

    테스트 코드: RS-027
    """
    # given: 저장하지 않은 리포트
    ghost = make_report("유령", owner=ALICE)
    await saved_report_case.prepare(ALICE)
    # when·then: 읽기·수정·삭제가 모두 찾을 수 없음 오류다
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(ghost.id)
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.update(ghost)
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.delete(ghost.id)


async def test_resigned_owner_keeps_the_report(saved_report_case: SavedReportCase) -> None:
    """만든 사람이 퇴사해도 리포트는 남고 다른 사용자의 목록에도 있다.

    테스트 코드: RS-048
    """
    # given: CAROL의 공개 리포트
    report = await saved_report_case.add(make_report("퇴사자 것", owner=CAROL, visibility="public"))
    # when: CAROL이 퇴사 처리된다
    await saved_report_case.resign(CAROL, later(60))
    # then: 리포트는 만든 사람 그대로 남고 ALICE의 목록에 있다
    stored = await saved_report_case.reports.get(report.id)
    assert (stored.name, stored.owner_user_id) == ("퇴사자 것", CAROL)
    assert [r.id for r in await saved_report_case.mine(_scope(ALICE), {report.id})] == [report.id]


# ---- 깨진 저장 정의: 읽기 실패를 삼키지 않고 깨짐 상태 엔티티로 돌려준다 ----

BROKEN_JSON = ["{}", '{"columns": "oops"}', '{"columns": [{"field": 5}]}']


@pytest.mark.parametrize("raw_json", BROKEN_JSON)
async def test_get_returns_a_broken_report_when_the_stored_definition_is_unreadable(
    saved_report_case: SavedReportCase, raw_json: str
) -> None:
    """저장 정의를 읽을 수 없으면 실패하지 않고 정의가 None인 리포트로 읽는다.

    테스트 코드: RS-035
    """
    # given: 저장 정의 JSON이 망가진 리포트
    report = await saved_report_case.add(make_report("깨짐", owner=ALICE, description="설명"))
    await saved_report_case.corrupt_definition(report, raw_json)
    # when: 읽는다
    stored = await saved_report_case.reports.get(report.id)
    # then: 정의만 None이고 나머지 필드는 그대로이며 데이터(entities)는 비어 있다
    assert stored.definition is None
    assert (stored.name, stored.description, stored.revision) == ("깨짐", "설명", 1)
    assert stored.entities() == ()


async def test_list_does_not_fail_on_a_broken_report_and_keeps_the_healthy_ones(
    saved_report_case: SavedReportCase,
) -> None:
    """목록은 깨진 리포트가 있어도 실패하지 않고 정상 리포트와 함께 준다.

    테스트 코드: RS-035
    """
    # given: 정상 리포트와 정의가 망가진 리포트
    healthy = await saved_report_case.add(make_report("정상", owner=ALICE, updated_at=later(10)))
    broken = await saved_report_case.add(make_report("깨짐", owner=ALICE, updated_at=later(20)))
    await saved_report_case.corrupt_definition(broken, '{"columns": "oops"}')
    # when: 목록을 읽는다
    listed = await saved_report_case.mine(_scope(ALICE), {healthy.id, broken.id})
    # then: 둘 다 있고 깨진 리포트의 정의만 None이다
    assert [(r.name, r.definition is None) for r in listed] == [("깨짐", True), ("정상", False)]


async def test_update_with_a_new_definition_repairs_a_broken_report(
    saved_report_case: SavedReportCase,
) -> None:
    """깨진 리포트를 새 정의로 덮어써 저장하면 복구된다.

    테스트 코드: RS-037
    """
    # given: 정의가 망가진 리포트를 새 정의로 덮어쓴 엔티티
    report = await saved_report_case.add(make_report("복구 대상", owner=ALICE))
    await saved_report_case.corrupt_definition(report, "{}")
    broken = await saved_report_case.reports.get(report.id)
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    broken.overwrite(
        make_content("복구 대상", definition=definition),
        editor=ALICE,
        role=Role.SALES,
        expected_revision=1,
        now=later(1),
    )
    # when: 저장하고 다시 읽는다
    await saved_report_case.reports.update(broken)
    stored = await saved_report_case.reports.get(report.id)
    # then: 새 정의를 읽을 수 있고 revision 2다
    assert stored.definition == definition
    assert stored.revision == 2


async def test_delete_removes_a_broken_report(saved_report_case: SavedReportCase) -> None:
    """깨진 리포트도 삭제할 수 있다.

    테스트 코드: RS-037
    """
    # given: 정의가 망가진 리포트
    report = await saved_report_case.add(make_report("깨짐 삭제", owner=ALICE))
    await saved_report_case.corrupt_definition(report, "{}")
    # when: 삭제한다
    await saved_report_case.reports.delete(report.id)
    # then: 사라진다
    with pytest.raises(ReportNotFoundError):
        await saved_report_case.reports.get(report.id)
