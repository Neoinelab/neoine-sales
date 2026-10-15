import { SelectField } from '../../../shared/ui/fields'
import { FormField } from './FormField'
import type { SectionProps } from './sectionTypes'

/** ⑦ 견적 ⑧ POC ⑨ 구매절차. 모두 선택 입력이다. */
export function QuoteSection({ state, set }: SectionProps) {
  return (
    <section className="form-section" aria-labelledby="sec-quote">
      <h2 id="sec-quote">견적 · POC · 구매절차</h2>
      <div className="form-grid">
        <SelectField
          label="견적 제출 여부"
          name="quoteSubmitted"
          value={state.quoteSubmitted}
          onChange={(v) => set('quoteSubmitted', v === 'YES' || v === 'NO' ? v : '')}
        >
          <option value="">선택 안 함</option>
          <option value="YES">YES</option>
          <option value="NO">NO</option>
        </SelectField>
        <FormField label="견적 제출일" name="quoteDate" type="date" value={state.quoteDate} onChange={(v) => set('quoteDate', v)} />
        <SelectField
          label="POC 여부"
          name="pocState"
          value={state.pocState}
          onChange={(v) => set('pocState', v === 'YES' || v === 'ING' || v === 'NO' ? v : '')}
        >
          <option value="">선택 안 함</option>
          <option value="YES">YES</option>
          <option value="ING">ING</option>
          <option value="NO">NO</option>
        </SelectField>
        <FormField label="POC 완료일" name="pocDate" type="date" value={state.pocDate} onChange={(v) => set('pocDate', v)} />
      </div>
      <FormField label="구매절차" name="procurement" value={state.procurement} onChange={(v) => set('procurement', v)} multiline />
    </section>
  )
}
