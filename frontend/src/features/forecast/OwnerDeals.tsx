import { Link } from 'react-router'
import { useDeals } from '../../data/deals'
import { formatDate } from '../../shared/format'
import { AMOUNT_LABEL } from '../../shared/model/money'
import { NEXT_ACTION_STATUS_LABEL } from '../../shared/model/nextActionStatus'
import { AmountText } from '../../shared/ui/AmountText'
import { ForecastBadge, StatusBadge } from '../../shared/ui/Badges'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import type { ForecastCell } from '../../shared/model/types'
import { queryOf, type ForecastFilters } from './forecastParams'

interface Props {
  ownerId: number
  ownerName: string
  filters: ForecastFilters
  /** 요약 표 행의 Open 합계(서버 값). 목록에서 다시 계산하지 않는다. */
  openTotal: ForecastCell | undefined
  onClear: () => void
}

/** 서버 목록 한도(MAX_LIMIT)와 같다. 넘으면 422이므로 올리지 않는다. */
const DEAL_LIMIT = 200

/** 요약과 같은 조건의 Deals 목록 쿼리(담당자·기간·Vendor). */
function allDealsParams(ownerId: number, filters: ForecastFilters): string {
  const params = new URLSearchParams({ owner: String(ownerId), year: String(filters.year) })
  if (filters.quarter) params.set('quarter', String(filters.quarter))
  else if (filters.month) params.set('month', String(filters.month))
  if (filters.vendor) params.set('vendor', String(filters.vendor))
  return params.toString()
}

/** 요약 표와 같은 기간·Vendor 조건에서 한 담당자의 Deal 목록(Forecast Review용). 읽기 전용. */
export function OwnerDeals({ ownerId, ownerName, filters, openTotal, onClear }: Props) {
  const { year, quarter, month, vendorId } = queryOf(filters)
  const deals = useDeals({ ownerId, year, quarter, month, vendorId, sort: 'revenueDate', order: 'asc', limit: DEAL_LIMIT })
  const items = deals.data?.items ?? []
  const lostCount = items.filter((d) => d.forecastKey === 'lost').length
  const total = deals.data?.total ?? 0
  const limit = deals.data?.limit ?? DEAL_LIMIT
  const allLink = `/deals?${allDealsParams(ownerId, filters)}`

  return (
    <section className="fc-owner-deals" aria-labelledby="fc-owner-title">
      <div className="fc-owner-head">
        <h2 id="fc-owner-title">선택한 담당자: {ownerName}</h2>
        <button type="button" onClick={onClear}>
          선택 해제
        </button>
      </div>
      <ErrorBanner error={deals.error} />
      {deals.isPending && <p role="status" className="hint">불러오는 중…</p>}
      {deals.data && (
        <>
          <p className="hint">
            {openTotal && (
              <>
                Open {openTotal.count}건 · {AMOUNT_LABEL} <AmountText amount={openTotal.amount} />
              </>
            )}
            {lostCount > 0 && total <= limit && ` · Lost ${lostCount}건은 합계에서 제외`}
          </p>
          {total > limit && (
            <p className="hint">
              총 {total}건 중 {limit}건만 표시합니다. <Link to={allLink}>Deals 목록에서 모두 보기</Link>
            </p>
          )}
          {items.length === 0 ? (
            <p className="hint">조건에 맞는 Deal이 없습니다.</p>
          ) : (
            // 가로 스크롤 영역은 키보드로 스크롤할 수 있어야 하므로 포커스를 받는다(WCAG 2.1.1).
            // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
            <div className="fc-scroll" tabIndex={0} role="region" aria-label="Deal 목록 (가로 스크롤)">
              <table className="fc-table" aria-label={`${ownerName}의 Deal 목록`}>
                <thead>
                  <tr>
                    <th scope="col">Deal</th>
                    <th scope="col">Status</th>
                    <th scope="col">Forecast</th>
                    <th scope="col" className="fc-num">{AMOUNT_LABEL}</th>
                    <th scope="col">Expected Close</th>
                    <th scope="col">Next Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((d) => (
                    <tr key={d.code}>
                      <td>
                        <Link to={`/deals/${d.code}`}>{d.name}</Link>
                        <div className="hint fc-sub">{d.customer.company}</div>
                      </td>
                      <td>
                        <StatusBadge statusKey={d.statusKey} />
                      </td>
                      <td>
                        <ForecastBadge forecastKey={d.forecastKey} />
                      </td>
                      <td className="fc-num">
                        <AmountText amount={d.revenueAmount} />
                      </td>
                      <td>{formatDate(d.revenueDate)}</td>
                      <td>
                        {d.nextAction ? (
                          <>
                            {d.nextAction.text}
                            <div className="hint fc-sub">
                              {formatDate(d.nextAction.dueDate)} · {NEXT_ACTION_STATUS_LABEL[d.nextAction.status]}
                            </div>
                          </>
                        ) : (
                          <span className="fc-zero">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
