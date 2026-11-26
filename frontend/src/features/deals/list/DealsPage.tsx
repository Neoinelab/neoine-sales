import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMe, usePermissions } from '../../../data/auth'
import { useAlertSettings } from '../../../data/alerts'
import { useCodeSet } from '../../../data/codes'
import { useDeals, useExportDeals } from '../../../data/deals'
import { saveBlob } from '../detail/detailHelpers'
import { useVendors } from '../../../data/vendors'
import { rememberListSearch } from '../../../shared/model/dealListMemory'
import { effectiveVendorFilter } from '../../../shared/model/vendorFilter'
import type { DealSortKey } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Notice } from '../../../shared/ui/Notice'
import { Pager } from '../../../shared/ui/Pager'
import { useLocationNotice } from '../../../shared/ui/useLocationNotice'
import { DealFilterBar } from './DealFilterBar'
import { DealsTable } from './DealsTable'
import { currentPage, currentSort, defaultListParams, hasActiveFilter, hasListCondition, listQueryFromParams, nextSort, updateParams } from './listQuery'
import './list.css'

/** Deals 목록(`/deals`, 계획 6.3). 조건·정렬·페이지는 모두 URL 쿼리에 있다. */
export function DealsPage() {
  const [urlParams, setParams] = useSearchParams()
  const me = useMe().data
  const role = me?.role
  const codes = useCodeSet()
  const forecasts = codes.data?.forecasts
  const bare = !hasListCondition(urlParams)
  const needsForecasts = bare && forecasts === undefined
  const params = useMemo(() => (bare && forecasts ? defaultListParams(role, forecasts, urlParams) : urlParams), [bare, forecasts, role, urlParams])
  const { canWrite } = usePermissions()
  const meId = me?.id
  const vendors = useVendors().data
  const query = useMemo(() => {
    const { vendorId, ...rest } = listQueryFromParams(params)
    const effective = effectiveVendorFilter(vendors, vendorId)
    return { ...rest, ...(effective.vendorId && { vendorId: effective.vendorId }) }
  }, [params, vendors])
  const deals = useDeals(query, !needsForecasts)
  const alerts = useAlertSettings()
  // 기준을 아직 모르거나(로딩) 가져오지 못하면(오류) 숫자 없는 문구를 보인다.
  const staleDays = alerts.data?.staleDays
  const staleLegend = staleDays === undefined ? '기준일 이상 미업데이트' : `${staleDays}일 이상 미업데이트`
  const [notice, setNotice] = useLocationNotice()
  const sort = currentSort(params)
  const page = needsForecasts ? undefined : deals.data

  useEffect(() => {
    if (bare && forecasts) setParams(params, { replace: true })
  }, [bare, forecasts, params, setParams])

  // URL이 진실이다: 목록에 마지막으로 보인 조건을 기억한다(초기화하면 빈 조건이 기록되어 지워진다).
  useEffect(() => {
    if (meId && !needsForecasts) rememberListSearch(meId, params)
  }, [meId, needsForecasts, params])

  const exportDeals = useExportDeals()
  // CSV 오류는 요청한 목록 조건과 함께 보관해, 조건이 바뀌면 보이지 않는다(진행 중 요청은 끊지 않는다).
  const [exportFailure, setExportFailure] = useState<{ error: unknown; params: URLSearchParams } | null>(null)
  const exportError = exportFailure?.params === params ? exportFailure.error : null

  /** 지금 목록과 같은 조건·정렬로 전체 결과를 CSV로 받는다(페이지 정보 없이). 저장은 화면 상태와 무관하게 응답 때 한다. */
  function exportCsv() {
    if (exportDeals.isPending) return
    setExportFailure(null)
    exportDeals.mutateAsync(query).then(
      (file) => saveBlob(file.fileName, file.blob),
      (error: unknown) => setExportFailure({ error, params }),
    )
  }

  function change(patch: Record<string, string | undefined>) {
    setParams((prev) => {
      const next = updateParams(hasListCondition(prev) ? prev : defaultListParams(role, forecasts ?? [], prev), patch)
      // 사용자가 마지막 조건을 직접 지우면 기본값이 되살아나지 않고 연도 '전체'로 남긴다.
      return hasListCondition(next) ? next : updateParams(next, { year: 'all', page: next.get('page') ?? undefined })
    })
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

      {!(needsForecasts && codes.isPending) && (
        <DealFilterBar params={params} onChange={change} onReset={() => setParams(forecasts ? defaultListParams(role, forecasts) : new URLSearchParams())} />
      )}

      <ul className="risk-legend" aria-label="Risk 범례">
        <li>
          <span className="badge risk-overdue">기한초과</span>
          <span className="hint">Open인 Next Action의 Due Date가 지났습니다</span>
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
      <ErrorBanner error={needsForecasts ? codes.error : deals.error} />

      {deals.isPending && !(needsForecasts && codes.isError) && <p className="hint">불러오는 중…</p>}
      {page && (
        <>
          <div className="deals-count-row">
            <p className="hint deals-count">총 {page.total}건</p>
            <button
              type="button"
              className="icon-button"
              title="CSV 다운로드"
              aria-label="CSV 다운로드"
              disabled={page.total === 0 || exportDeals.isPending}
              onClick={exportCsv}
            >
              <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                <path d="M10 3v9m0 0-3.5-3.5M10 12l3.5-3.5M4 15v1.5h12V15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <ErrorBanner error={exportError} />
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
