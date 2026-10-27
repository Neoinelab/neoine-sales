import type { ReportCatalog, ReportCombine, ReportField, ReportOperator } from '../../../shared/model/reportTypes'
import { ConditionValueInput } from './ConditionValueInput'
import type { ConditionDraft } from './state/conditionDraft'
import type { DesignerCondition } from './state/designerState'
import { describe, type Message } from './state/issueView'

interface ConditionRowProps {
  n: number
  condition: DesignerCondition
  field: ReportField
  /** 조건에 쓸 수 있는 필드(filterable). */
  fields: readonly ReportField[]
  catalog: ReportCatalog
  combine: ReportCombine
  messages: readonly Message[]
  onField: (field: ReportField) => void
  onOperator: (operator: ReportOperator) => void
  onDraft: (draft: ConditionDraft) => void
  onRemove: () => void
}

/** 조건 한 줄: 접속어 · 필드 · 연산자 · 값 · 삭제. 문구는 줄 아래에 보인다. */
export function ConditionRow({ n, condition, field, fields, catalog, combine, messages, onField, onOperator, onDraft, onRemove }: ConditionRowProps) {
  const name = `조건 ${n}`
  return (
    <div className="report-condition-item">
      <div className="report-condition">
        <span className="report-join">{n > 1 ? combine.toUpperCase() : ''}</span>
        <select
          aria-label={`${name} 필드`}
          value={condition.field}
          onChange={(e) => {
            const next = fields.find((f) => f.key === e.target.value)
            if (next) onField(next)
          }}
          {...describe(messages, ['field'])}
        >
          {fields.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}
            </option>
          ))}
        </select>
        <select aria-label={`${name} 연산자`} value={condition.operator} onChange={(e) => onOperator(e.target.value as ReportOperator)} {...describe(messages, ['operator'])}>
          {field.operators.map((key) => (
            <option key={key} value={key}>
              {catalog.operators.find((o) => o.key === key)?.label ?? key}
            </option>
          ))}
        </select>
        <div className="report-condition-value">
          <ConditionValueInput n={n} draft={condition.draft} field={field} catalog={catalog} messages={messages} onChange={onDraft} />
        </div>
        <button type="button" className="report-condition-remove" aria-label={`${name} 삭제`} onClick={onRemove}>
          ×
        </button>
      </div>
      {messages.map((m) => (
        <p key={m.id} id={m.id} className="field-error">
          {m.text}
        </p>
      ))}
    </div>
  )
}
