import { useLabels } from '../../../data/labels'
import type { DealRow, DealSortKey } from '../../../shared/model/types'
import { DealRowItem } from './DealRowItem'
import type { SortState } from './listQuery'

interface Column {
  label: string
  sort?: DealSortKey
}

/** PRD DL-05의 11개 + BANT(LB-06) 컬럼. 정렬 가능한 열만 sort 키를 가진다. */
const COLUMNS: readonly Column[] = [
  { label: 'Deal', sort: 'name' },
  { label: '담당자' },
  { label: '고객사' },
  { label: '파트너사' },
  { label: 'Vendor' },
  { label: 'Status', sort: 'statusKey' },
  { label: 'Forecast' },
  { label: 'BANT' },
  { label: '금액', sort: 'revenueAmount' },
  { label: 'Expected Close', sort: 'revenueDate' },
  { label: 'Next Action' },
  { label: '최종 업데이트', sort: 'lastUpdatedAt' },
]

interface DealsTableProps {
  rows: readonly DealRow[]
  canWrite: boolean
  sort: SortState
  onSort: (key: DealSortKey) => void
  onSaved: (message: string) => void
}

export function DealsTable({ rows, canWrite, sort, onSort, onSaved }: DealsTableProps) {
  // Label 이름은 행마다 읽지 않고 한 번 읽어 넘긴다(목록 캐시와 별개로 Label 이름 변경은 keys.labels 무효화로 반영된다).
  const labelsQuery = useLabels()
  const labels = labelsQuery.data ?? []
  const labelsFailed = labelsQuery.isError
  return (
    <div className="table-scroll">
      <table className="deals-table">
        <thead>
          <tr>
            {COLUMNS.map((column) => {
              const active = column.sort !== undefined && column.sort === sort.sort
              return (
                <th
                  key={column.label}
                  scope="col"
                  aria-sort={active ? (sort.order === 'asc' ? 'ascending' : 'descending') : undefined}
                >
                  {column.sort ? (
                    <button
                      type="button"
                      className="th-sort"
                      data-dir={active ? sort.order : undefined}
                      onClick={() => column.sort && onSort(column.sort)}
                    >
                      {column.label}
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
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
