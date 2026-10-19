import { useSearchParams } from 'react-router'
import { useForecastSummary } from '../../data/forecast'
import { useVendors } from '../../data/vendors'
import { useToday } from '../../data/today'
import { ComingSoon } from '../../shared/ui/ComingSoon'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { effectiveVendorFilter } from '../../shared/model/vendorFilter'
import { ForecastFilterBar } from './ForecastFilters'
import { filtersFromParams, paramsFromFilters, queryOf, type ForecastFilters } from './forecastParams'
import { OwnerDeals } from './OwnerDeals'
import { QuarterCards } from './QuarterCards'
import { SummaryTable } from './SummaryTable'
import './forecast.css'

/**
 * Forecast `/forecast`. 6.6
 * 필터는 URL 쿼리가 가진다. 담당자 선택(`sel`)도 URL에 두어 Deal 상세에서 돌아와도 유지된다.
 * 모든 로그인 사용자가 조회하고 쓰기 동작은 없다.
 */
export function ForecastPage() {
  const [params, setParams] = useSearchParams()
  const { year: thisYear } = useToday()
  const filters = filtersFromParams(params, thisYear)
  const vendors = useVendors().data
  // 표시와 조회 조건을 맞춘다: 목록에 없는 Vendor는 조회에서 제외한다.
  const queryFilters = { ...filters, vendor: effectiveVendorFilter(vendors, filters.vendor).vendorId }
  const summary = useForecastSummary(queryOf(queryFilters))

  const update = (patch: Partial<ForecastFilters>) => {
    setParams(paramsFromFilters({ ...filters, ...patch }))
  }

  // 서버에 Forecast 집계가 아직 없으면(501) 화면 대신 "준비 중"만 보인다. 다른 오류는 배너.
  if (summary.error?.kind === 'not-implemented') return <ComingSoon title="Forecast" />

  const data = summary.data
  const isEmpty = data !== undefined && data.rows.length === 0
  const selectedName = data?.rows.find((r) => r.ownerId === filters.selectedId)?.ownerName

  return (
    <section className="fc-page">
      <h1>Forecast</h1>
      <ForecastFilterBar filters={filters} onChange={update} />
      <ErrorBanner error={summary.error} />
      {summary.isPending && (
        <p role="status" className="hint">
          불러오는 중…
        </p>
      )}
      {data && !isEmpty && (
        <>
          <QuarterCards summary={data} filters={filters} />
          <SummaryTable summary={data} selectedId={filters.selectedId} onSelect={(selectedId) => update({ selectedId })} />
        </>
      )}
      {isEmpty && <p className="fc-empty">조건에 맞는 Deal이 없습니다.</p>}
      {filters.selectedId && data && (
        <OwnerDeals
          ownerId={filters.selectedId}
          ownerName={selectedName ?? '선택한 담당자'}
          filters={queryFilters}
          onClear={() => update({ selectedId: undefined })}
        />
      )}
    </section>
  )
}
