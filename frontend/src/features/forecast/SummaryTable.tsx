import type { ForecastCell, ForecastColumn, ForecastSummary, ForecastSummaryRow } from '../../shared/model/types'
import { AMOUNT_LABEL } from '../../shared/model/money'
import { AmountText } from '../../shared/ui/AmountText'

/** 표시 순서: Open은 확률이 높은 순(Commit → Pipeline), Won은 마지막 별도 열. 게이트웨이는 코드 order(Pipeline → Commit)로 준다. */
export function displayColumns(columns: ForecastColumn[]): { open: ForecastColumn[]; won: ForecastColumn[] } {
  return {
    open: columns.filter((c) => c.outcome === 'open').reverse(),
    won: columns.filter((c) => c.outcome === 'won'),
  }
}

export function CellValue({ cell }: { cell: ForecastCell | undefined }) {
  if (!cell || cell.count === 0) return <span className="fc-zero">—</span>
  return (
    <>
      {cell.count}건 · <AmountText amount={cell.amount} />
    </>
  )
}

interface Props {
  summary: ForecastSummary
  selectedId: number | undefined
  onSelect: (ownerId: number | undefined) => void
}

interface RowProps {
  row: ForecastSummaryRow
  open: ForecastColumn[]
  won: ForecastColumn[]
  selected: boolean
  onSelect: () => void
}

function OwnerRow({ row, open, won, selected, onSelect }: RowProps) {
  return (
    <tr className={selected ? 'fc-selected' : undefined}>
      <th scope="row">
        <button type="button" className="fc-owner" aria-pressed={selected} onClick={onSelect}>
          {row.ownerName}
        </button>
      </th>
      {open.map((c) => (
        <td key={c.key} className="fc-num">
          <CellValue cell={row.cells[c.key]} />
        </td>
      ))}
      <td className="fc-num fc-total">
        <CellValue cell={row.total} />
      </td>
      {won.map((c) => (
        <td key={c.key} className="fc-num">
          <CellValue cell={row.cells[c.key]} />
        </td>
      ))}
    </tr>
  )
}

/** 담당자별 요약 표. 열: Commit / Most Likely / Best / Pipeline / Total(Open) / Won. 좁은 화면에서는 가로 스크롤. */
export function SummaryTable({ summary, selectedId, onSelect }: Props) {
  const { open, won } = displayColumns(summary.columns)
  const { totalRow } = summary
  return (
    // 가로 스크롤 영역은 키보드로 스크롤할 수 있어야 하므로 포커스를 받는다(WCAG 2.1.1).
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div className="fc-scroll" tabIndex={0} role="region" aria-label="담당자별 Forecast 표 (가로 스크롤)">
      <table className="fc-table" aria-label="담당자별 Forecast 요약">
        <caption className="hint">셀 값: 건수 · {AMOUNT_LABEL}</caption>
        <thead>
          <tr>
            <th scope="col">담당자</th>
            {open.map((c) => (
              <th key={c.key} scope="col" className="fc-num">
                {c.name}
              </th>
            ))}
            <th scope="col" className="fc-num fc-total">
              Total(Open)
            </th>
            {won.map((c) => (
              <th key={c.key} scope="col" className="fc-num">
                {c.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {summary.rows.map((row) => (
            <OwnerRow
              key={row.ownerId ?? 'none'}
              row={row}
              open={open}
              won={won}
              selected={row.ownerId === selectedId}
              onSelect={() => onSelect(row.ownerId === selectedId ? undefined : (row.ownerId ?? undefined))}
            />
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">합계</th>
            {open.map((c) => (
              <td key={c.key} className="fc-num">
                <CellValue cell={totalRow.cells[c.key]} />
              </td>
            ))}
            <td className="fc-num fc-total">
              <CellValue cell={totalRow.total} />
            </td>
            {won.map((c) => (
              <td key={c.key} className="fc-num">
                <CellValue cell={totalRow.cells[c.key]} />
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
