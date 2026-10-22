import { AMOUNT_LABEL } from '../../../shared/model/money'
import type { BantLabel, DealRow, DealSortKey } from '../../../shared/model/types'
import { SortableHeader } from '../../../shared/ui/SortableHeader'
import { DealRowItem } from './DealRowItem'
import type { SortState } from './listQuery'

interface Column {
  label: string
  sort?: DealSortKey
}

/** PRD DL-05의 11개 + BANT(LB-06) 컬럼. 정렬 가능한 열만 sort 키를 가진다. */
const COLUMNS: readonly Column[] = [
  { label: 'Deal', sort: 'name' },
  { label: '담당자', sort: 'owner' },
  { label: '고객사', sort: 'customer' },
  { label: '파트너사', sort: 'partner' },
  { label: 'Vendor', sort: 'vendor' },
  { label: 'Status', sort: 'statusKey' },
  { label: 'Forecast', sort: 'forecastKey' },
  { label: 'BANT' },
  { label: AMOUNT_LABEL, sort: 'revenueAmount' },
  { label: 'Expected Close', sort: 'revenueDate' },
  { label: 'Next Action' },
  { label: '최종 업데이트', sort: 'lastUpdatedAt' },
]

interface DealsTableProps {
  rows: readonly DealRow[]
  labels: readonly BantLabel[]
  /** Label 조회 실패: BANT 칸에 이름을 만들 수 없다고 알린다. */
  labelsFailed: boolean
  canWrite: boolean
  sort: SortState
  onSort: (key: DealSortKey) => void
  onSaved: (message: string) => void
}

export function DealsTable({ rows, labels, labelsFailed, canWrite, sort, onSort, onSaved }: DealsTableProps) {
  return (
    <div className="table-scroll">
      <table className="deals-table">
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
            <DealRowItem key={row.code} row={row} labels={labels} labelsFailed={labelsFailed} canWrite={canWrite} onSaved={onSaved} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
