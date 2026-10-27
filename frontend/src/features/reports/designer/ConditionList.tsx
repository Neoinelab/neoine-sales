import { useId } from 'react'
import type { ReportCatalog, ReportCombine } from '../../../shared/model/reportTypes'
import { ConditionRow } from './ConditionRow'
import { fieldByKey, filterableFields } from './state/columnRules'
import type { DesignerAction, DesignerState } from './state/designerState'
import { idsOf, type IssueView } from './state/issueView'
import type { ScopePrediction } from './state/scope'

interface ConditionListProps {
  state: DesignerState
  catalog: ReportCatalog
  scope: ScopePrediction
  issues: IssueView
  dispatch: (action: DesignerAction) => void
}

const COMBINES: { value: ReportCombine; label: string }[] = [
  { value: 'and', label: '모든 조건을 만족(AND)' },
  { value: 'or', label: '하나라도 만족(OR)' },
]

/** 조건 결합(AND/OR) 라디오와 조건 행 목록. 조건이 없으면 무엇이 대상인지 안내한다. */
export function ConditionList({ state, catalog, scope, issues, dispatch }: ConditionListProps) {
  const radioName = useId()
  const fields = filterableFields(catalog)
  const first = fields[0]
  const full = state.conditions.length >= catalog.limits.conditionsMax
  return (
    <section className="report-card" aria-labelledby="report-conditions-title">
      <h2 id="report-conditions-title">조건</h2>
      <fieldset className="report-combine" aria-describedby={idsOf(issues.combine)}>
        <legend>조건 결합</legend>
        {COMBINES.map((c) => (
          <label key={c.value} className="report-check">
            <input type="radio" name={radioName} value={c.value} checked={state.combine === c.value} onChange={() => dispatch({ type: 'setCombine', combine: c.value })} />
            {c.label}
          </label>
        ))}
      </fieldset>
      {issues.combine.map((m) => (
        <p key={m.id} id={m.id} className="field-error">
          {m.text}
        </p>
      ))}
      {state.conditions.length === 0 && <p className="hint">조건이 없으면 모든 {scope.rowScope === 'action' ? 'Action' : 'Deal'}이 대상입니다</p>}
      {state.conditions.map((condition, i) => {
        const field = fieldByKey(catalog, condition.field)
        if (!field) {
          // 지금 카탈로그에 없는 필드(저장 뒤 규칙이 바뀐 경우): 값을 편집할 수 없으니 알리고 지울 수 있게만 한다.
          return (
            <div key={condition.uid} className="report-condition-item">
              <div className="report-condition">
                <span className="report-join">{i > 0 ? state.combine.toUpperCase() : ''}</span>
                <span className="error">알 수 없는 필드: {condition.field}</span>
                <button type="button" className="report-condition-remove" aria-label={`조건 ${i + 1} 삭제`} onClick={() => dispatch({ type: 'removeCondition', uid: condition.uid })}>
                  ×
                </button>
              </div>
            </div>
          )
        }
        return (
          <ConditionRow
            key={condition.uid}
            n={i + 1}
            condition={condition}
            field={field}
            fields={fields}
            catalog={catalog}
            combine={state.combine}
            messages={issues.condition(condition.uid)}
            onField={(next) => dispatch({ type: 'changeConditionField', uid: condition.uid, field: next })}
            onOperator={(operator) => dispatch({ type: 'changeOperator', uid: condition.uid, operator })}
            onDraft={(draft) => dispatch({ type: 'changeDraft', uid: condition.uid, draft })}
            onRemove={() => dispatch({ type: 'removeCondition', uid: condition.uid })}
          />
        )
      })}
      {issues.conditions.map((m) => (
        <p key={m.id} id={m.id} className="field-error">
          {m.text}
        </p>
      ))}
      <button type="button" disabled={full || first === undefined} onClick={() => first && dispatch({ type: 'addCondition', field: first })}>
        + 조건 추가
      </button>
      {full && <p className="hint">조건은 최대 {catalog.limits.conditionsMax}개입니다</p>}
    </section>
  )
}
