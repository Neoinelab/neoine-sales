import type { SortOrder } from '../../shared/model/inputs'
import { SortableHeader } from '../../shared/ui/SortableHeader'
import { userLabel } from '../../shared/model/period'
import type { LicenseContract } from '../../shared/model/types'
import { EXPIRY_TITLES, expiryLevel } from './contractExpiry'
import type { ContractSort } from './contractFilter'
import { INSPECTION_LABELS, STATUS_LABELS, isIssuedStatus } from './contractLabels'

const COLUMNS: readonly { label: string; sort: ContractSort }[] = [
  { label: 'Deal 코드', sort: 'dealCode' },
  { label: '고객사명', sort: 'customer' },
  { label: 'Vendor', sort: 'vendor' },
  { label: '제품명', sort: 'product' },
  { label: '파트너사', sort: 'partner' },
  { label: '라이선스 시작일', sort: 'licenseStart' },
  { label: '라이선스 종료일', sort: 'licenseEnd' },
  { label: '상태', sort: 'status' },
  { label: '담당영업', sort: 'salesOwner' },
  { label: '기술담당', sort: 'techOwner' },
  { label: '점검주기', sort: 'inspection' },
  { label: 'Note', sort: 'note' },
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
                <td className="contract-code">{row.dealCode}</td>
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
                <td>{INSPECTION_LABELS[row.inspection]}</td>
                <td className="contract-note">{dash(row.note)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
