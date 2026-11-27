import { AMOUNT_LABEL } from '../../../shared/model/money'
import type { DealRow, DealSortKey } from '../../../shared/model/types'
import { SortableHeader } from '../../../shared/ui/SortableHeader'
import { DealRowItem } from './DealRowItem'
import type { SortState } from './listQuery'

interface Column {
  label: string
  sort?: DealSortKey
  width: number
}

/** PRD DL-05의 목록 컬럼(Next Action은 Next Action·Due·상태 3열). 정렬 가능한 열만 sort 키를 가진다. */
const COLUMNS: readonly Column[] = [
  { label: 'Deal', sort: 'name', width: 20.8 },
  { label: '담당자', sort: 'owner', width: 6.57 },
  { label: 'Vendor', sort: 'vendor', width: 6.58 },
  { label: 'Forecast', sort: 'forecastKey', width: 6.58 },
  { label: AMOUNT_LABEL, sort: 'revenueAmount', width: 6.58 },
  { label: 'Expected Close', sort: 'revenueDate', width: 6.58 },
  { label: '최종 업데이트', sort: 'lastUpdatedAt', width: 6.58 },
  { label: 'Next Action', width: 26.57 },
  { label: 'Due Date', width: 6.58 },
  { label: 'Next Action 상태', width: 6.58 },
]

interface DealsTableProps {
  rows: readonly DealRow[]
  canWrite: boolean
  sort: SortState
  onSort: (key: DealSortKey) => void
  onSaved: (message: string) => void
}

export function DealsTable({ rows, canWrite, sort, onSort, onSaved }: DealsTableProps) {
  return (
    <div className="table-scroll">
      <table className="deals-table">
        <colgroup>
          {COLUMNS.map(({ label, width }) => <col key={label} style={{ width: `${width}%` }} />)}
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map((column) => {
              const active = column.sort !== undefined && column.sort === sort.sort
              return (
                <SortableHeader
                  key={column.label}
                  label={column.label}
                  active={active}
                  order={sort.order}
                  onSort={column.sort ? () => column.sort && onSort(column.sort) : undefined}
                />
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <DealRowItem key={row.code} row={row} columnCount={COLUMNS.length} canWrite={canWrite} onSaved={onSaved} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
