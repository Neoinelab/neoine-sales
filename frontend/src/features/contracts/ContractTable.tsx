import type { SortOrder } from '../../shared/model/inputs'
import { SortableHeader } from '../../shared/ui/SortableHeader'
import { userLabel } from '../../shared/model/period'
import type { LicenseContract } from '../../shared/model/types'
import { EXPIRY_TITLES, expiryLevel } from './contractExpiry'
import type { ContractSort } from './contractFilter'
import { STATUS_LABELS, isIssuedStatus } from './contractLabels'

const COLUMNS: readonly { label: string; sort: ContractSort; width: number }[] = [
  { label: 'Deal명', sort: 'dealName', width: 22 },
  { label: '고객사명', sort: 'customer', width: 8 },
  { label: 'Vendor', sort: 'vendor', width: 10 },
  { label: '제품명', sort: 'product', width: 12 },
  { label: '파트너사', sort: 'partner', width: 8 },
  { label: '라이선스 시작일', sort: 'licenseStart', width: 8 },
  { label: '라이선스 종료일', sort: 'licenseEnd', width: 8 },
  { label: '상태', sort: 'status', width: 8 },
  { label: '담당영업', sort: 'salesOwner', width: 8 },
  { label: '기술담당', sort: 'techOwner', width: 8 },
]

interface ContractTableProps {
  rows: readonly LicenseContract[]
  sort: ContractSort
  order: SortOrder
  onSort: (column: ContractSort) => void
  /** 서버 시계의 오늘('YYYY-MM-DD'). 만료 임박 색 기준. */
  today: string
  onEdit: (row: LicenseContract) => void
}

const dash = (value: string | null) => (value === null || value === '' ? '-' : value)

export function ContractTable({ rows, sort, order, onSort, today, onEdit }: ContractTableProps) {
  return (
    <div className="table-scroll">
      <table className="contract-table" aria-label="계약 목록">
        <colgroup>
          {COLUMNS.map(({ sort, width }) => <col key={sort} style={{ width: `${width}%` }} />)}
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <SortableHeader key={column.sort} label={column.label} active={sort === column.sort} order={order} onSort={() => onSort(column.sort)} />
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const level = expiryLevel(row.licenseEnd, row.status, today)
            const dateClass = ['contract-date', level ? `expiry-${level}` : ''].filter(Boolean).join(' ')
            const dateTitle = level ? EXPIRY_TITLES[level] : undefined
            const statusClass = isIssuedStatus(row.status) ? 'status-issued' : row.status === 'ended' ? 'status-ended' : undefined
            return (
              // 행 전체가 '계약 수정'을 연다: 마우스는 칸 클릭, 키보드는 행에 포커스한 뒤 Enter·Space.
              <tr
                key={row.id}
                className="contract-row"
                tabIndex={0}
                onClick={() => onEdit(row)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onEdit(row)
                  }
                }}
              >
                <td className="contract-deal-name" title={row.dealCode}>{row.dealName}</td>
                <td>{row.customer}</td>
                <td>{dash(row.vendor?.name ?? null)}</td>
                <td>{row.product}</td>
                <td>{dash(row.partner)}</td>
                <td className={dateClass} title={dateTitle}>
                  {dash(row.licenseStart)}
                </td>
                <td className={dateClass} title={dateTitle}>
                  {dash(row.licenseEnd)}
                </td>
                <td className={statusClass}>
                  <span className="contract-status-cell">
                    <span className="badge contract-status" data-status={row.status}>
                      {STATUS_LABELS[row.status]}
                    </span>
                  </span>
                </td>
                <td>{userLabel(row.salesOwner)}</td>
                <td>{dash(row.techOwner)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
