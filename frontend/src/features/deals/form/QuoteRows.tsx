import { useId, type ReactNode } from 'react'
import { DateInput } from '../../../shared/ui/DateInput'
import { FormField } from './FormField'
import type { SectionProps } from './sectionTypes'

/** 견적·POC 한 줄: 행 라벨 하나 아래 여부(select)와 날짜(date)를 나란히 둔다. */
function PairRow({ label, children }: { label: string; children: ReactNode }) {
  const id = useId()
  return (
    <div className="kv-row field">
      <span id={id}>{label}</span>
      <div className="kv-inline" role="group" aria-labelledby={id}>
        {children}
      </div>
    </div>
  )
}

/** Deal 정보 타일의 견적·POC·구매절차 행. 모두 선택 입력이다. */
export function QuoteRows({ state, set, errors }: SectionProps) {
  return (
    <>
      <PairRow label="견적">
        <select
          name="quoteSubmitted"
          aria-label="견적 제출여부"
          value={state.quoteSubmitted}
          onChange={(e) => set('quoteSubmitted', e.target.value === 'YES' || e.target.value === 'NO' ? e.target.value : '')}
        >
          <option value="">선택 안 함</option>
          <option value="YES">YES</option>
          <option value="NO">NO</option>
        </select>
        <DateInput name="quoteDate" aria-label="견적 제출일" value={state.quoteDate} onChange={(v) => set('quoteDate', v)} error={errors.quoteDate} />
      </PairRow>
      <PairRow label="POC">
        <select
          name="pocState"
          aria-label="POC 여부"
          value={state.pocState}
          onChange={(e) => set('pocState', e.target.value === 'YES' || e.target.value === 'ING' || e.target.value === 'NO' ? e.target.value : '')}
        >
          <option value="">선택 안 함</option>
          <option value="YES">YES</option>
          <option value="ING">ING</option>
          <option value="NO">NO</option>
        </select>
        <DateInput name="pocDate" aria-label="POC 완료일" value={state.pocDate} onChange={(v) => set('pocDate', v)} error={errors.pocDate} />
      </PairRow>
      <FormField label="구매절차" name="procurement" value={state.procurement} onChange={(v) => set('procurement', v)} />
    </>
  )
}
