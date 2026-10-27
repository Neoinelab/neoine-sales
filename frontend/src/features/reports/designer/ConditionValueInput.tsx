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

/** 조건 값 입력. 연산자 모양(draft.shape)에 맞는 칸을 보인다. 금액은 천원 단위로 입력받는다. */
export function ConditionValueInput({ n, draft, field, catalog, messages, onChange }: ConditionValueInputProps) {
  const unit = isMoneyField(field) ? <span className="field-hint">(천원)</span> : null
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
          <input type="text" inputMode="numeric" aria-label={`${name} 값`} value={draft.text} onChange={(e) => onChange({ shape: 'number', text: e.target.value })} {...describe(messages, ['value'])} />
          {unit}
        </>
      )
    case 'range':
      return (
        <>
          <input type="text" inputMode="numeric" aria-label={`${name} 시작`} value={draft.low} onChange={(e) => onChange({ ...draft, low: e.target.value })} {...describe(messages, ['low', 'value'])} />
          <span aria-hidden="true">~</span>
          <input type="text" inputMode="numeric" aria-label={`${name} 끝`} value={draft.high} onChange={(e) => onChange({ ...draft, high: e.target.value })} {...describe(messages, ['high'])} />
          {unit}
        </>
      )
    case 'date':
      return <input type="date" aria-label={`${name} 값`} value={draft.day} onChange={(e) => onChange({ shape: 'date', day: e.target.value })} {...describe(messages, ['day', 'value'])} />
    case 'date_range':
      return (
        <>
          <input type="date" aria-label={`${name} 시작`} value={draft.first} onChange={(e) => onChange({ ...draft, first: e.target.value })} {...describe(messages, ['first', 'value'])} />
          <span aria-hidden="true">~</span>
          <input type="date" aria-label={`${name} 끝`} value={draft.last} onChange={(e) => onChange({ ...draft, last: e.target.value })} {...describe(messages, ['last'])} />
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
