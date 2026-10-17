import { useDealFacets } from '../../data/deals'
import { SelectField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import { useToday } from '../../data/today'
import type { ForecastFilters } from './forecastParams'

interface Props {
  filters: ForecastFilters
  onChange: (patch: Partial<ForecastFilters>) => void
}

/** 연도는 기준 연도(올해) ±1에 URL로 들어온 값을 더한다. */
function yearOptions(base: number, current: number): number[] {
  return [...new Set([base - 1, base, base + 1, current])].sort((a, b) => a - b)
}

/** Forecast 필터: 연도 / Quarter / 담당자 / Vendor. 값은 URL이 가진다(제어 컴포넌트). */
export function ForecastFilterBar({ filters, onChange }: Props) {
  const facets = useDealFacets()
  const { year: thisYear } = useToday()
  const vendors = new Set(facets.data?.vendors ?? [])
  if (filters.vendor) vendors.add(filters.vendor)

  return (
    <form className="filters fc-filters" aria-label="Forecast 필터" onSubmit={(e) => e.preventDefault()}>
      <SelectField label="연도" name="year" value={String(filters.year)} onChange={(v) => onChange({ year: Number(v) })}>
        {yearOptions(thisYear, filters.year).map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </SelectField>
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
      <UserSelect
        label="담당자"
        name="owner"
        value={filters.ownerId ?? ''}
        onChange={(v) => onChange({ ownerId: v || undefined })}
        includeResigned
      />
      <SelectField label="Vendor" name="vendor" value={filters.vendor ?? ''} onChange={(v) => onChange({ vendor: v || undefined })}>
        <option value="">전체</option>
        {[...vendors].map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </SelectField>
    </form>
  )
}
