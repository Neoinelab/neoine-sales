"""Excel 입력 경계의 날짜·헤더·누락 값 검증."""

from datetime import date
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZipFile

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from contract_workbook import HEADERS, ContractImportError, read_workbook


def workbook(path: Path, *, end: str = "46367", inspection: str = "파트너사 수행") -> Path:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    root = Element("worksheet", xmlns=ns)
    data = SubElement(root, "sheetData")
    values = [
        list(HEADERS),
        [
            "SK AX",
            "Microsoft",
            "M365 (17EA)",
            "파트너 A",
            "46082",
            end,
            "갱신약속",
            "김영업(Neo Kim)",
            "김기술",
            inspection,
        ],
    ]
    for number, items in enumerate(values, 1):
        row = SubElement(data, "row", r=str(number))
        for index, value in enumerate(items):
            cell = SubElement(row, "c", r=f"{chr(65 + index)}{number}")
            if number == 2 and index in (4, 5):
                SubElement(cell, "v").text = value
            else:
                cell.set("t", "inlineStr")
                SubElement(SubElement(cell, "is"), "t").text = value
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="'
            + ns
            + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="계약" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", tostring(root))
    return path


def test_workbook_maps_dates_and_preserves_names(tmp_path: Path) -> None:
    """엑셀 날짜를 변환하고 회사 공백과 상태를 유지한다."""
    # given: 실제 입력과 같은 10열 Excel
    path = workbook(tmp_path / "contracts.xlsx")
    # when: 행을 읽는다
    (row,) = read_workbook(path)
    # then: 회사·제품·Note와 최소 Deal 명명 규칙을 보존한다
    assert row.deal_name == "유지보수-SK AX-M365 (17EA)"
    assert row.start == date(2026, 3, 1)
    assert row.end == date(2026, 12, 11)
    assert row.note == "갱신약속"
    assert row.inspection == "none"
    assert row.partner == "파트너 A"


def test_reversed_period_is_rejected(tmp_path: Path) -> None:
    """종료일이 시작일보다 빠르면 행 번호와 함께 거절한다."""
    # given: 거꾸로 된 기간
    path = workbook(tmp_path / "contracts.xlsx", end="46000")
    # when·then: 파싱이 2행 오류를 반환한다
    with pytest.raises(ContractImportError, match=r"2행.*종료일"):
        read_workbook(path)


def test_unknown_inspection_is_rejected(tmp_path: Path) -> None:
    """알 수 없는 점검주기를 조용히 버리지 않는다."""
    # given: 지원하지 않는 주기
    path = workbook(tmp_path / "contracts.xlsx", inspection="매주")
    # when·then: 점검주기 오류가 발생한다
    with pytest.raises(ContractImportError, match="점검주기"):
        read_workbook(path)
