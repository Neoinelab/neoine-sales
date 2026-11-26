"""10열 계약 Excel을 DB에 넣기 전 검증된 행으로 변환한다."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

if TYPE_CHECKING:
    from pathlib import Path

TEXT_MAX: Final = 200
TECH_MAX: Final = 100
NOTE_MAX: Final = 2000
WORKBOOK_MAX: Final = 50_000_000

HEADERS: Final = (
    "고객사명",
    "제조사",
    "제품명",
    "파트너사",
    "시작일",
    "종료일",
    "상태",
    "영업담당",
    "기술담당",
    "점검주기",
)
NS: Final = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CYCLES: Final = {
    "": "none",
    "없음": "none",
    "파트너사 수행": "none",
    "월점검": "monthly",
    "분기점검": "quarterly",
    "반기점검": "semiannual",
    "연점검": "yearly",
    "년점검": "yearly",
    "연간점검": "yearly",
}


class ContractImportError(Exception):
    def __init__(self, row: int, reason: str) -> None:
        self.row = row
        self.reason = reason
        super().__init__(f"{row}행: {reason}" if row else reason)


@dataclass(frozen=True, slots=True)
class ContractInput:
    row: int
    customer: str
    vendor: str
    product: str
    partner: str
    start: date
    end: date
    note: str
    owner: str
    tech_owner: str
    inspection: str

    @property
    def deal_name(self) -> str:
        return f"유지보수-{self.customer}-{self.product}"


def _date(raw: str, row: int, epoch: date) -> date:
    try:
        if "-" in raw:
            value = date.fromisoformat(raw)
        else:
            serial = Decimal(raw)
            if not serial.is_finite() or serial != serial.to_integral_value():
                raise ContractImportError(row, "날짜에는 시간 또는 소수 값을 넣을 수 없습니다.")
            value = epoch + timedelta(days=int(serial))
    except ValueError, InvalidOperation, OverflowError:
        raise ContractImportError(row, "날짜는 Excel 날짜 또는 YYYY-MM-DD여야 합니다.") from None
    if not date(1900, 1, 1) <= value <= date(2999, 12, 31):
        raise ContractImportError(row, "날짜는 1900~2999년 범위여야 합니다.")
    return value


def _parse(number: int, values: list[str], epoch: date) -> ContractInput:
    company, vendor, product, partner, start, end, note, owner, tech, cycle = values
    for label, value, limit in (
        ("고객사명", company, 200),
        ("제조사", vendor, 100),
        ("제품명", product, 200),
        ("영업담당", owner, 200),
        ("시작일", start, 100),
        ("종료일", end, 100),
    ):
        if not value or len(value) > limit:
            raise ContractImportError(number, f"{label}: 필수이며 {limit}자 이내여야 합니다.")
    if cycle not in CYCLES:
        raise ContractImportError(number, f"지원하지 않는 점검주기: {cycle}")
    result = ContractInput(
        number,
        company,
        vendor,
        product,
        partner,
        _date(start, number, epoch),
        _date(end, number, epoch),
        note,
        owner,
        tech,
        CYCLES[cycle],
    )
    if result.end < result.start:
        raise ContractImportError(number, "종료일은 시작일보다 빠를 수 없습니다.")
    if any(
        len(value) > limit
        for value, limit in (
            (result.deal_name, TEXT_MAX),
            (partner, TEXT_MAX),
            (tech, TECH_MAX),
            (note, NOTE_MAX),
        )
    ):
        raise ContractImportError(
            number, "Deal명/파트너사 200자, 기술담당 100자, Note 2000자 제한 초과"
        )
    return result


def _xml(archive: ZipFile, name: str) -> ET.Element:
    raw = archive.read(name).decode("utf-8-sig")
    if "<!DOCTYPE" in raw or "<!ENTITY" in raw:
        raise ContractImportError(0, "XML DTD/ENTITY는 허용하지 않습니다.")
    return ET.fromstring(raw)  # noqa: S314 - UTF-8 only, bounded ZIP size, DTD/ENTITY rejected above.


def _cell(cell: ET.Element, shared: list[str], number: int) -> str:
    kind = cell.get("t", "n")
    raw = cell.findtext(f"{NS}v", "")
    if cell.find(f"{NS}f") is not None and not raw:
        raise ContractImportError(number, "수식 결과가 없습니다. Excel에서 계산 후 저장하세요.")
    if kind == "e":
        raise ContractImportError(number, "Excel 셀에 오류가 있습니다.")
    if kind == "s":
        raw = shared[int(raw)]
    elif kind == "inlineStr":
        raw = "".join(t.text or "" for t in cell.iter(f"{NS}t"))
    if "\x00" in raw:
        raise ContractImportError(number, "NUL 문자는 허용하지 않습니다.")
    return raw.strip()


def _sheet_rows(archive: ZipFile, target: str, shared: list[str]) -> list[tuple[int, list[str]]]:
    rows = []
    for row in _xml(archive, target).iter(f"{NS}row"):
        number = int(row.get("r", "0"))
        values = [""] * len(HEADERS)
        for cell in row.findall(f"{NS}c"):
            column = 0
            for char in cell.get("r", ""):
                if char.isdigit():
                    break
                column = column * 26 + ord(char) - ord("A") + 1
            value = _cell(cell, shared, number)
            if value and not 1 <= column <= len(HEADERS):
                raise ContractImportError(number, "지원하지 않는 추가 열이 있습니다.")
            if 1 <= column <= len(HEADERS):
                values[column - 1] = value
        if any(values):
            rows.append((number, values))
    return rows


def read_workbook(path: Path) -> list[ContractInput]:
    """첫 워크시트의 고정 헤더 10개와 모든 데이터 행을 검증한다."""
    try:
        with ZipFile(path) as archive:
            if sum(info.file_size for info in archive.infolist()) > WORKBOOK_MAX:
                raise ContractImportError(0, "Excel 압축 해제 크기가 50MB를 초과합니다.")
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = [
                    "".join(t.text or "" for t in item.iter(f"{NS}t"))
                    for item in _xml(archive, "xl/sharedStrings.xml")
                ]
            workbook = _xml(archive, "xl/workbook.xml")
            sheet = workbook.find(f"{NS}sheets/{NS}sheet")
            if sheet is None:
                raise ContractImportError(0, "워크시트가 없습니다.")
            rels = {
                item.get("Id"): item.get("Target", "")
                for item in _xml(archive, "xl/_rels/workbook.xml.rels")
            }
            target = rels[sheet.get(f"{REL}id")]
            target = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            rows = _sheet_rows(archive, target, shared)
            props = workbook.find(f"{NS}workbookPr")
            epoch = (
                date(1904, 1, 1)
                if props is not None and props.get("date1904") in {"1", "true"}
                else date(1899, 12, 30)
            )
    except (BadZipFile, ET.ParseError, KeyError, IndexError, ValueError, OSError) as error:
        raise ContractImportError(0, f"Excel 읽기 실패 ({type(error).__name__})") from None
    if not rows or tuple(rows[0][1]) != HEADERS:
        raise ContractImportError(1, "헤더가 맞지 않습니다: " + ", ".join(HEADERS))
    result = [_parse(number, values, epoch) for number, values in rows[1:]]
    if not result:
        raise ContractImportError(0, "가져올 데이터 행이 없습니다.")
    names: set[str] = set()
    for item in result:
        key = item.deal_name.casefold()
        if key in names:
            raise ContractImportError(
                item.row, "Excel에 같은 고객사·제품명의 Deal이 중복되어 있습니다."
            )
        names.add(key)
    return result
