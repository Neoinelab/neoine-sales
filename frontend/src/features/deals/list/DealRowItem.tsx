import { Fragment, useState } from 'react'
import { Link } from 'react-router'
import { useToday } from '../../../data/today'
import { formatDate, formatRelativeTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { BantLabel, DealRow } from '../../../shared/model/types'
import { RiskBadge, riskRowClass } from '../../../shared/ui/RiskBadge'
import { bantSummary } from './bantSummary'
import { InlineCell } from './InlineCell'
import { QuickView } from './QuickView'

export const COLUMN_COUNT = 12

interface DealRowItemProps {
  row: DealRow
  labels: readonly BantLabel[]
  /** Label 조회 실패: BANT 칸에 이름을 만들 수 없다고 알린다(로딩 중은 '—'). */
  labelsFailed: boolean
  canWrite: boolean
  onSaved: (message: string) => void
}

function BantCell({ row, labels, failed }: { row: DealRow; labels: readonly BantLabel[]; failed: boolean }) {
  if (failed) return <>불러오지 못함</>
  const items = bantSummary(row.bant, labels)
  if (items.length === 0) return <>—</>
  return (
    <ul className="deal-bant-list">
      {items.map((item) => {
        const full = `${item.categoryName}: ${item.labelName}`
        return (
          <li key={item.category} className="deal-bant-item" title={full} aria-label={full}>
            <abbr aria-hidden="true">{item.abbr}</abbr> {item.labelName}
          </li>
        )
      })}
    </ul>
  )
}

function NextAction({ row }: { row: DealRow }) {
  if (!row.nextAction) return <>—</>
  const overdue = row.risk === 'overdue' || row.risk === 'overdue_stale'
  return (
    <>
      <span>{row.nextAction.text}</span>
      <small className={overdue ? 'due overdue' : 'due'}>Due {row.nextAction.dueDate}</small>
    </>
  )
}

/** 목록 한 줄(+ 펼친 빠른 보기). Risk 행 색은 배지 텍스트와 함께 쓴다(색만으로 구분하지 않음). */
export function DealRowItem({ row, labels, labelsFailed, canWrite, onSaved }: DealRowItemProps) {
  const [open, setOpen] = useState(false)
  const { now } = useToday()
  const lastUpdated = formatRelativeTime(row.lastUpdatedAt, now)
  const cell = (field: 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate') => (
    <InlineCell row={row} field={field} canWrite={canWrite} onSaved={onSaved} />
  )

  return (
    <Fragment>
      <tr className={riskRowClass(row.risk)}>
        <td>
          <div className="deal-name-cell">
          <button
            type="button"
            className="quick-toggle"
            aria-expanded={open}
            aria-label={`${row.name} 빠른 보기`}
            onClick={() => setOpen((v) => !v)}
          >
            <span aria-hidden="true">{open ? '▾' : '▸'}</span>
          </button>
          <span className="deal-name">
            <Link to={`/deals/${row.code}`}>{row.name}</Link>
            <RiskBadge risk={row.risk} />
          </span>
          </div>
        </td>
        <td>{userLabel(row.owner)}</td>
        <td>{row.customer.company}</td>
        <td>{row.activePartner?.company ?? '—'}</td>
        <td>{row.vendor?.name ?? '—'}</td>
        <td>{cell('statusKey')}</td>
        <td>{cell('forecastKey')}</td>
        <td className="bant-cell">
          <BantCell row={row} labels={labels} failed={labelsFailed} />
        </td>
        <td className="num">{cell('revenueAmount')}</td>
        <td>{cell('revenueDate')}</td>
        <td className="next-action">
          <NextAction row={row} />
        </td>
        <td>
          <time dateTime={row.lastUpdatedAt} title={`${formatDate(row.lastUpdatedAt)} ${row.lastUpdatedAt.slice(11, 16)}`}>
            {lastUpdated}
          </time>
        </td>
      </tr>
      {open && (
        <tr className="quick-view-row">
          <td colSpan={COLUMN_COUNT}>
            <QuickView row={row} />
          </td>
        </tr>
      )}
    </Fragment>
  )
}
