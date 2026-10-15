import { useState } from 'react'
import { useDealFacets } from '../../../data/deals'
import { useCodeSet } from '../../../data/codes'
import { useLabels } from '../../../data/labels'
import { useToday } from '../../../data/today'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import { CheckboxField, SelectField, TextField } from '../../../shared/ui/fields'
import { UserSelect } from '../../../shared/ui/UserSelect'

interface DealFilterBarProps {
  params: URLSearchParams
  /** URL 쿼리 일부를 바꾼다(빈 문자열은 삭제). */
  onChange: (patch: Record<string, string | undefined>) => void
  onReset: () => void
}

const QUARTERS = [1, 2, 3, 4] as const

function yearOptions(year: number): number[] {
  return [year - 1, year, year + 1, year + 2]
}

/** Deal 목록 필터(DL-04, LB-06). 키워드는 검색 버튼, 나머지는 바꾸는 즉시 URL에 반영한다. */
export function DealFilterBar({ params, onChange, onReset }: DealFilterBarProps) {
  const { year: thisYear } = useToday()
  const codes = useCodeSet().data
  const facets = useDealFacets().data
  const labels = useLabels().data ?? []
  const q = params.get('q') ?? ''
  const [keyword, setKeyword] = useState(q)
  const [seenQ, setSeenQ] = useState(q)
  if (q !== seenQ) {
    setSeenQ(q)
    setKeyword(q)
  }
  const value = (key: string) => params.get(key) ?? ''
  const hasYear = value('year') !== ''

  return (
    <form
      className="deal-filters"
      role="search"
      aria-label="Deal 필터"
      onSubmit={(event) => {
        event.preventDefault()
        onChange({ q: keyword.trim() })
      }}
    >
      <TextField label="키워드" name="keyword" value={keyword} onChange={setKeyword} />
      <UserSelect label="담당자" name="owner" value={value('owner')} onChange={(owner) => onChange({ owner })} includeResigned />
      <SelectField label="Vendor" name="vendor" value={value('vendor')} onChange={(vendor) => onChange({ vendor })}>
        <option value="">전체</option>
        {facets?.vendors.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </SelectField>
      <SelectField label="Solution" name="solution" value={value('solution')} onChange={(solution) => onChange({ solution })}>
        <option value="">전체</option>
        {facets?.solutions.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </SelectField>
      <SelectField label="Status" name="status" value={value('status')} onChange={(status) => onChange({ status })}>
        <option value="">전체</option>
        {codes?.statuses.map((c) => (
          <option key={c.key} value={c.key}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="Forecast" name="forecast" value={value('forecast')} onChange={(forecast) => onChange({ forecast })}>
        <option value="">전체</option>
        {codes?.forecasts.map((c) => (
          <option key={c.key} value={c.key}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <SelectField
        label="연도"
        name="year"
        value={value('year')}
        onChange={(year) => onChange({ year, quarter: year ? value('quarter') : '' })}
      >
        <option value="">전체</option>
        {yearOptions(thisYear).map((y) => (
          <option key={y} value={String(y)}>
            {y}
          </option>
        ))}
      </SelectField>
      <label className="field">
        <span>Quarter</span>
        <select name="quarter" value={value('quarter')} disabled={!hasYear} onChange={(e) => onChange({ quarter: e.target.value })}>
          <option value="">전체</option>
          {QUARTERS.map((n) => (
            <option key={n} value={String(n)}>
              Q{n}
            </option>
          ))}
        </select>
      </label>
      <TextField label="기간 시작" name="from" type="date" value={value('from')} onChange={(from) => onChange({ from })} />
      <TextField label="기간 끝" name="to" type="date" value={value('to')} onChange={(to) => onChange({ to })} />
      {BANT_CATEGORIES.map((category) => (
        <SelectField
          key={category}
          label={`${BANT_CATEGORY_NAMES[category]} Label`}
          name={category}
          value={value(category)}
          onChange={(id) => onChange({ [category]: id })}
        >
          <option value="">전체</option>
          {labels
            .filter((l) => l.category === category)
            .map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
        </SelectField>
      ))}
      <CheckboxField label="내 딜만" name="mine" checked={value('mine') === '1'} onChange={(on) => onChange({ mine: on ? '1' : '' })} />
      <div className="filter-buttons">
        <button type="submit" className="primary">
          검색
        </button>
        <button type="button" onClick={onReset}>
          초기화
        </button>
      </div>
    </form>
  )
}
