import { useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMe, usePermissions } from '../../../data/auth'
import { useAlertSettings } from '../../../data/alerts'
import { useDeals } from '../../../data/deals'
import { rememberListSearch } from '../../../shared/model/dealListMemory'
import type { DealSortKey } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Notice } from '../../../shared/ui/Notice'
import { Pager } from '../../../shared/ui/Pager'
import { useLocationNotice } from '../../../shared/ui/useLocationNotice'
import { DealFilterBar } from './DealFilterBar'
import { DealsTable } from './DealsTable'
import { currentPage, currentSort, hasActiveFilter, listQueryFromParams, nextSort, updateParams } from './listQuery'
import './list.css'

/** Deals 목록(`/deals`, 계획 6.3). 조건·정렬·페이지는 모두 URL 쿼리에 있다. */
export function DealsPage() {
  const [params, setParams] = useSearchParams()
  const { canWrite } = usePermissions()
  const meId = useMe().data?.id
  const query = useMemo(() => listQueryFromParams(params), [params])
  const deals = useDeals(query)
  const alerts = useAlertSettings()
  // 기준을 아직 모르거나(로딩) 가져오지 못하면(오류) 숫자 없는 문구를 보인다.
  const staleDays = alerts.data?.staleDays
  const staleLegend = staleDays === undefined ? '기준일 이상 미업데이트' : `${staleDays}일 이상 미업데이트`
  const [notice, setNotice] = useLocationNotice()
  const sort = currentSort(params)
  const page = deals.data

  // URL이 진실이다: 목록에 마지막으로 보인 조건을 기억한다(초기화하면 빈 조건이 기록되어 지워진다).
  useEffect(() => {
    if (meId) rememberListSearch(meId, params)
  }, [meId, params])

  function change(patch: Record<string, string | undefined>) {
    setParams(updateParams(params, patch))
  }

  function onSort(key: DealSortKey) {
    const next = nextSort(sort, key)
    change({ sort: next.sort, order: next.order })
  }

  return (
    <div className="deals-page">
      <div className="heading">
        <h1>Deals</h1>
        {canWrite && (
          <Link to="/deals/new" className="button primary">
            + Deal 등록
          </Link>
        )}
      </div>

      <DealFilterBar params={params} onChange={change} onReset={() => setParams(new URLSearchParams())} />

      <ul className="risk-legend" aria-label="Risk 범례">
        <li>
          <span className="badge risk-overdue">기한초과</span>
          <span className="hint">Next Action의 Due Date가 지났습니다</span>
        </li>
        <li>
          <span className="badge risk-stale">미업데이트</span>
          <span className="hint">{staleLegend}</span>
        </li>
      </ul>

      {notice && (
        <Notice kind="success" onClose={() => setNotice(null)}>
          {notice}
        </Notice>
      )}
      <ErrorBanner error={deals.error} />

      {deals.isPending && <p className="hint">불러오는 중…</p>}
      {page && (
        <>
          <p className="hint deals-count">총 {page.total}건</p>
          {page.total === 0 && (
            <p className="deals-empty">{hasActiveFilter(params) ? '조건에 맞는 Deal이 없습니다.' : '등록된 Deal이 없습니다.'}</p>
          )}
          {page.total > 0 && page.items.length === 0 && (
            <p className="deals-empty">
              {currentPage(params)}페이지에는 Deal이 없습니다.{' '}
              <button type="button" onClick={() => change({ page: '1' })}>
                첫 페이지로
              </button>
            </p>
          )}
          {page.items.length > 0 && (
            <DealsTable rows={page.items} canWrite={canWrite} sort={sort} onSort={onSort} onSaved={setNotice} />
          )}
          {page.total > 0 && (
            <Pager
              offset={page.offset}
              limit={page.limit}
              total={page.total}
              onChange={(offset) => change({ page: String(offset / page.limit + 1) })}
            />
          )}
        </>
      )}
    </div>
  )
}
