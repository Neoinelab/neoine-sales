import { useYearOptions } from '../../data/dealYears'
import { useVendors } from '../../data/vendors'
import { parseId } from '../../shared/model/ids'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import type { DashboardFilters } from './dashboardParams'

interface Props {
  filters: DashboardFilters
  onChange: (patch: Partial<DashboardFilters>) => void
}

const textOf = (id: number | undefined): string => (id === undefined ? '' : String(id))

/** Dashboard 필터: 연도 / Quarter(Status 탭만) / 담당자 / Vendor(기간은 Expected Close 기준). 값은 URL이 가진다(제어 컴포넌트). */
export function DashboardFilterBar({ filters, onChange }: Props) {
  const yearOptions = useYearOptions(filters.year)
  const vendorsQuery = useVendors()
  const vendors = vendorsQuery.data ?? []
  const loaded = vendorsQuery.data !== undefined
  // 목록이 로드된 뒤 목록에 없는 id는 '전체'로 보인다. 목록이 없는 동안(로딩·오류)에는 URL 값을 '선택한 Vendor'로 보인다.
  const vendorValue = !loaded ? textOf(filters.vendor) : vendors.some((v) => v.id === filters.vendor) ? textOf(filters.vendor) : ''

  return (
    <form className="filters db-filters" aria-label="Dashboard 필터" onSubmit={(e) => e.preventDefault()}>
      <SelectField label="연도" name="year" value={String(filters.year)} onChange={(v) => onChange({ year: Number(v) })}>
        {yearOptions.years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </SelectField>
      {filters.tab === 'status' && (
        <SelectField
          label="Quarter"
          name="quarter"
          value={filters.quarter ? String(filters.quarter) : ''}
          onChange={(v) => onChange({ quarter: v ? (Number(v) as 1 | 2 | 3 | 4) : undefined })}
        >
          <option value="">전체</option>
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={q}>{`Q${q}`}</option>
          ))}
        </SelectField>
      )}
      <UserSelect label="담당자" name="owner" value={textOf(filters.ownerId)} onChange={(v) => onChange({ ownerId: parseId(v) })} includeResigned />
      <SelectField label="Vendor" name="vendor" value={vendorValue} onChange={(v) => onChange({ vendor: parseId(v) })}>
        <option value="">전체</option>
        {!loaded && vendorValue && <option value={vendorValue}>선택한 Vendor</option>}
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </SelectField>
      <ErrorBanner error={yearOptions.error} />
      <ErrorBanner error={vendorsQuery.error} />
    </form>
  )
}
