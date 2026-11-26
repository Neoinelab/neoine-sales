import { AMOUNT_LABEL } from '../../../shared/model/money'
import type { DealRow, DealSortKey } from '../../../shared/model/types'
import { SortableHeader } from '../../../shared/ui/SortableHeader'
import { DealRowItem } from './DealRowItem'
import type { SortState } from './listQuery'

interface Column {
  label: string
  sort?: DealSortKey
  widthClass?: string
}

/** PRD DL-05의 목록 컬럼(Next Action은 Next Action·Due·상태 3열). 정렬 가능한 열만 sort 키를 가진다. */
const COLUMNS: readonly Column[] = [
  { label: 'Deal', sort: 'name', widthClass: 'deal-list-name' },
  { label: '담당자', sort: 'owner', widthClass: 'deal-list-owner' },
  { label: 'Vendor', sort: 'vendor', widthClass: 'deal-list-vendor' },
  { label: 'Forecast', sort: 'forecastKey', widthClass: 'deal-list-forecast' },
  { label: AMOUNT_LABEL, sort: 'revenueAmount' },
  { label: 'Expected Close', sort: 'revenueDate' },
  { label: '최종 업데이트', sort: 'lastUpdatedAt', widthClass: 'deal-list-updated' },
  { label: 'Next Action' },
  { label: 'Due Date' },
  { label: 'Next Action 상태' },
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
    <div className="table-scroll deal-list-scroll">
      <table className="deals-table">
        <colgroup>
          {COLUMNS.map(({ label, widthClass }) => <col key={label} className={widthClass} />)}
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
