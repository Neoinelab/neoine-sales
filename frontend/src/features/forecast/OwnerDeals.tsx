import { Link } from 'react-router'
import { useDeals } from '../../data/deals'
import { formatDate } from '../../shared/format'
import { AMOUNT_LABEL } from '../../shared/model/money'
import { NEXT_ACTION_STATUS_LABEL } from '../../shared/model/nextActionStatus'
import { AmountText } from '../../shared/ui/AmountText'
import { ForecastBadge, StatusBadge } from '../../shared/ui/Badges'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { queryOf, type ForecastFilters } from './forecastParams'

interface Props {
  ownerId: string
  ownerName: string
  filters: ForecastFilters
  onClear: () => void
}

/** 요약 표와 같은 기간·Vendor 조건에서 한 담당자의 Deal 목록(Forecast Review용). 읽기 전용. */
export function OwnerDeals({ ownerId, ownerName, filters, onClear }: Props) {
  const { year, quarter, vendorId } = queryOf(filters)
  const deals = useDeals({ ownerId, year, quarter, vendorId, sort: 'revenueDate', order: 'asc', limit: 1000 })
  const items = deals.data?.items ?? []
  const counted = items.filter((d) => d.forecastKey !== 'lost')
  const lostCount = items.length - counted.length
  const openSum = counted.filter((d) => d.forecastKey !== 'won')
  const openAmount = openSum.reduce((s, d) => s + d.revenueAmount, 0)

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
            Open {openSum.length}건 · {AMOUNT_LABEL} <AmountText amount={openAmount} />
            {lostCount > 0 && ` · Lost ${lostCount}건은 합계에서 제외`}
          </p>
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
