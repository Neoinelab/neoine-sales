import { AmountInput } from '../../../shared/ui/AmountInput'
import { DateInput } from '../../../shared/ui/DateInput'
import type { ReportCatalog, ReportField } from '../../../shared/model/reportTypes'
import { ChoiceValueInput } from './ChoiceValueInput'
import { isMoneyField } from './state/columnRules'
import type { ConditionDraft } from './state/conditionDraft'
import { describe, idsOf, type Message } from './state/issueView'

interface ConditionValueInputProps {
  n: number
  draft: ConditionDraft
  field: ReportField
  catalog: ReportCatalog
  messages: readonly Message[]
  onChange: (draft: ConditionDraft) => void
}

/** 문구는 조건 행 아래에서 부모가 보이므로 DateInput에는 접근성 속성만 넘긴다. */
function dateProps(messages: readonly Message[], parts: readonly string[]): { invalid?: boolean; 'aria-describedby'?: string } {
  const attrs = describe(messages, parts)
  return { invalid: attrs['aria-invalid'], 'aria-describedby': attrs['aria-describedby'] }
}

/** 조건 값 입력. 연산자 모양(draft.shape)에 맞는 칸을 보인다. 금액 칸은 원 단위 자동 콤마 입력이다. */
export function ConditionValueInput({ n, draft, field, catalog, messages, onChange }: ConditionValueInputProps) {
  const money = isMoneyField(field)
  const unit = money ? <span className="field-hint">(원)</span> : null
  const name = `조건 ${n}`
  switch (draft.shape) {
    case 'none':
      return null
    case 'text':
      return (
        <input type="text" aria-label={`${name} 값`} maxLength={catalog.limits.textValueMax} value={draft.text} onChange={(e) => onChange({ shape: 'text', text: e.target.value })} {...describe(messages, ['value'])} />
      )
    case 'number':
      return (
        <>
          {money ? (
            <AmountInput aria-label={`${name} 값`} value={draft.text} onChange={(text) => onChange({ shape: 'number', text })} {...describe(messages, ['value'])} />
          ) : (
            <input type="text" inputMode="numeric" aria-label={`${name} 값`} value={draft.text} onChange={(e) => onChange({ shape: 'number', text: e.target.value })} {...describe(messages, ['value'])} />
          )}
          {unit}
        </>
      )
    case 'range':
      return (
        <>
          {money ? (
            <AmountInput aria-label={`${name} 시작`} value={draft.low} onChange={(low) => onChange({ ...draft, low })} {...describe(messages, ['low', 'value'])} />
          ) : (
            <input type="text" inputMode="numeric" aria-label={`${name} 시작`} value={draft.low} onChange={(e) => onChange({ ...draft, low: e.target.value })} {...describe(messages, ['low', 'value'])} />
          )}
          <span aria-hidden="true">~</span>
          {money ? (
            <AmountInput aria-label={`${name} 끝`} value={draft.high} onChange={(high) => onChange({ ...draft, high })} {...describe(messages, ['high'])} />
          ) : (
            <input type="text" inputMode="numeric" aria-label={`${name} 끝`} value={draft.high} onChange={(e) => onChange({ ...draft, high: e.target.value })} {...describe(messages, ['high'])} />
          )}
          {unit}
        </>
      )
    case 'date':
      return <DateInput quiet aria-label={`${name} 값`} value={draft.day} onChange={(day) => onChange({ shape: 'date', day })} {...dateProps(messages, ['day', 'value'])} />
    case 'date_range':
      return (
        <>
          <DateInput quiet aria-label={`${name} 시작`} value={draft.first} onChange={(first) => onChange({ ...draft, first })} {...dateProps(messages, ['first', 'value'])} />
          <span aria-hidden="true">~</span>
          <DateInput quiet aria-label={`${name} 끝`} value={draft.last} onChange={(last) => onChange({ ...draft, last })} {...dateProps(messages, ['last'])} />
        </>
      )
    case 'relative': {
      const needsDays = catalog.relativePeriods.find((p) => p.key === draft.period)?.needsDays ?? false
      return (
        <>
          <select
            aria-label={`${name} 기간`}
            value={draft.period}
            onChange={(e) => onChange({ ...draft, period: e.target.value as typeof draft.period })}
            {...describe(messages, ['period', 'value'])}
          >
            {catalog.relativePeriods.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}
              </option>
            ))}
          </select>
          {needsDays && (
            <input type="text" inputMode="numeric" aria-label={`${name} 일수`} value={draft.days} onChange={(e) => onChange({ ...draft, days: e.target.value })} {...describe(messages, ['days'])} />
          )}
        </>
      )
    }
    case 'list':
      return (
        <ChoiceValueInput
          field={field}
          n={n}
          values={draft.values}
          onChange={(values) => onChange({ shape: 'list', values })}
          describedBy={idsOf(messages.filter((m) => m.part === 'value'))}
        />
      )
  }
}
