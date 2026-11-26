import { Fragment, useState } from 'react'
import { Link } from 'react-router'
import { useToday } from '../../../data/today'
import { formatRelativeDays } from '../../../shared/format'
import { NEXT_ACTION_STATUS_LABEL } from '../../../shared/model/nextActionStatus'
import { isOverdueRow } from '../../../shared/model/risk'
import { userLabel } from '../../../shared/model/period'
import type { DealRow } from '../../../shared/model/types'
import { CommentBadge } from '../../../shared/ui/CommentBadge'
import { RiskBadge, riskRowClass } from '../../../shared/ui/RiskBadge'
import { InlineCell } from './InlineCell'
import { QuickView } from './QuickView'
import { NextActionDueDate } from './NextActionDueDate'

interface DealRowItemProps {
  row: DealRow
  columnCount: number
  canWrite: boolean
  onSaved: (message: string) => void
}

function NextActionCells({ row, today, canWrite, onSaved }: { row: DealRow; today: string; canWrite: boolean; onSaved: (message: string) => void }) {
  const next = row.nextAction
  if (!next) {
    return (
      <>
        <td className="next-action">—</td>
        <td>—</td>
        <td>—</td>
      </>
    )
  }
  const overdue = (row.risk === 'overdue' || row.risk === 'overdue_stale') && isOverdueRow(next.status, next.dueDate, today)
  return (
    <>
      <td className="next-action">
        <Link to={`/deals/${row.code}?tab=actions`}>{next.text}</Link>
      </td>
      <td className={overdue ? 'due overdue' : 'due'}>
        <NextActionDueDate dealCode={row.code} next={next} canWrite={canWrite} onSaved={onSaved} />
      </td>
      <td>{NEXT_ACTION_STATUS_LABEL[next.status]}</td>
    </>
  )
}

/** 목록 한 줄(+ 펼친 빠른 보기). Risk 행 색은 배지 텍스트와 함께 쓴다(색만으로 구분하지 않음). */
export function DealRowItem({ row, columnCount, canWrite, onSaved }: DealRowItemProps) {
  const [open, setOpen] = useState(false)
  const { now, today } = useToday()
  const lastUpdated = formatRelativeDays(row.lastUpdatedOn, now)
  const cell = (field: 'forecastKey' | 'revenueAmount' | 'revenueDate') => (
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
            <CommentBadge count={row.unreadCommentCount} />
            <RiskBadge risk={row.risk} />
          </span>
          </div>
        </td>
        <td>{userLabel(row.owner)}</td>
        <td>{row.vendor?.name ?? '—'}</td>
        <td>{cell('forecastKey')}</td>
        <td className="num">{cell('revenueAmount')}</td>
        <td>{cell('revenueDate')}</td>
        <td>
          <time dateTime={row.lastUpdatedOn} title={row.lastUpdatedOn}>
            {lastUpdated}
          </time>
        </td>
        <NextActionCells row={row} today={today} canWrite={canWrite} onSaved={onSaved} />
      </tr>
      {open && (
        <tr className="quick-view-row">
          <td colSpan={columnCount}>
            <QuickView row={row} />
          </td>
        </tr>
      )}
    </Fragment>
  )
}
