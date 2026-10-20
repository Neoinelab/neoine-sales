import { useId, useState } from 'react'
import { useCodeSet } from '../../../data/codes'
import { useLabels } from '../../../data/labels'
import { useToday } from '../../../data/today'
import { useVendors } from '../../../data/vendors'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import { NEXT_ACTION_STATUS_FILTER_OPTIONS, nextActionStatusFromParam, nextActionStatusToParam } from '../../../shared/model/nextActionStatus'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
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
  const vendorsQuery = useVendors()
  const vendors = vendorsQuery.data ?? []
  const loaded = vendorsQuery.data !== undefined
  const hintId = useId()
  const labels = useLabels().data ?? []
  const q = params.get('q') ?? ''
  const [keyword, setKeyword] = useState(q)
  const [seenQ, setSeenQ] = useState(q)
  if (q !== seenQ) {
    setSeenQ(q)
    setKeyword(q)
  }
  const value = (key: string) => params.get(key) ?? ''
  // 모르는 값은 '전체'로 보이고 조회에도 쓰이지 않는다(listQueryFromParams와 같은 판정).
  const nextStatus = nextActionStatusFromParam(params.get('next_status'))
  const hasQuarter = value('quarter') !== ''
  const hasYear = value('year') !== ''
  // 목록이 로드된 뒤 목록에 없는 id(예전 이름 값 등)·소속이 맞지 않는 Solution은 '전체'로 보인다.
  // 조건 형식은 listQueryFromParams가, 목록 없는 id·소속 불일치는 DealsPage의 effectiveVendorFilter가 판정한다.
  // 목록이 없는 동안(로딩·오류)에는 URL 값이 조회에 쓰이므로 '선택한 …' 옵션 하나로 선택 상태를 보인다.
  const vendorId = !loaded ? value('vendor') : vendors.some((v) => v.id === value('vendor')) ? value('vendor') : ''
  const chosenVendor = vendors.find((v) => v.id === vendorId)
  const solutionOptions = chosenVendor
    ? chosenVendor.solutions.map((s) => ({ id: s.id, label: s.name }))
    : vendors.flatMap((v) => v.solutions.map((s) => ({ id: s.id, label: `${v.name} / ${s.name}` })))
  const solutionId = !loaded ? value('solution') : solutionOptions.some((s) => s.id === value('solution')) ? value('solution') : ''

  /** Vendor를 바꾸면 새 Vendor 소속이 아닌 Solution 조건은 지운다. 전체로 돌리면 유지한다. */
  function changeVendor(next: string) {
    const target = vendors.find((v) => v.id === next)
    const keep = !target || target.solutions.some((s) => s.id === value('solution'))
    onChange({ vendor: next, ...(keep ? {} : { solution: '' }) })
  }

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
      <SelectField label="Vendor" name="vendor" value={vendorId} onChange={changeVendor}>
        <option value="">전체</option>
        {!loaded && vendorId && <option value={vendorId}>선택한 Vendor</option>}
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="Solution" name="solution" value={solutionId} onChange={(solution) => onChange({ solution })}>
        <option value="">전체</option>
        {!loaded && solutionId && <option value={solutionId}>선택한 Solution</option>}
        {solutionOptions.map((s) => (
          <option key={s.id} value={s.id}>
            {s.label}
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
        label="Next Action 상태"
        name="next_status"
        value={nextStatus ? nextActionStatusToParam(nextStatus) : ''}
        onChange={(next_status) => onChange({ next_status })}
      >
        {NEXT_ACTION_STATUS_FILTER_OPTIONS.map((o) => (
          <option key={o.value} value={o.value === '' ? '' : nextActionStatusToParam(o.value)}>
            {o.label}
          </option>
        ))}
      </SelectField>
      <SelectField
        label="연도"
        name="year"
        value={value('year')}
        onChange={(year) => onChange({ year })}
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
        <select
          name="quarter"
          aria-label="Quarter"
          aria-describedby={hasQuarter && !hasYear ? hintId : undefined}
          value={value('quarter')}
          onChange={(e) => onChange({ quarter: e.target.value })}
        >
          <option value="">전체</option>
          {QUARTERS.map((n) => (
            <option key={n} value={String(n)}>
              Q{n}
            </option>
          ))}
        </select>
        {hasQuarter && !hasYear && (
          <small id={hintId} className="field-hint">
            연도를 고르지 않으면 올해({thisYear}) 기준입니다.
          </small>
        )}
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
      <ErrorBanner error={vendorsQuery.error} />
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
