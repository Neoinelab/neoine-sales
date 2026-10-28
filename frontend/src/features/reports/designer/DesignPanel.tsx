import type { ReportCatalog } from '../../../shared/model/reportTypes'
import { ColumnShelf } from './ColumnShelf'
import { ConditionList } from './ConditionList'
import { FieldPanel } from './FieldPanel'
import { RunBar } from './RunBar'
import { RunFailure } from './RunFailure'
import { ScopeBar } from './ScopeBar'
import type { DesignerAction, DesignerState } from './state/designerState'
import { predictScope } from './state/scope'
import type { DesignerRun } from './useDesignerRun'

interface DesignPanelProps {
  state: DesignerState
  catalog: ReportCatalog
  run: DesignerRun
  dispatch: (action: DesignerAction) => void
  onRun: () => void
}

/** 작성 탭: 필드 목록 · 범위 표시 · 컬럼 · 조건 · 최대 행과 조회 · 조회 실패 알림. */
export function DesignPanel({ state, catalog, run, dispatch, onRun }: DesignPanelProps) {
  const scope = predictScope(state, catalog)
  return (
    <div className="report-designer">
      <FieldPanel
        catalog={catalog}
        usedFields={new Set(state.columns.map((c) => c.field))}
        columnsFull={state.columns.length >= catalog.limits.columnsMax}
        conditionsFull={state.conditions.length >= catalog.limits.conditionsMax}
        onAddColumn={(field) => dispatch({ type: 'addColumn', field })}
        onAddCondition={(field) => dispatch({ type: 'addCondition', field })}
      />
      <div className="report-work">
        <ScopeBar scope={scope} combine={state.combine} />
        <ColumnShelf state={state} catalog={catalog} issues={run.issues} dispatch={dispatch} />
        <ConditionList state={state} catalog={catalog} scope={scope} issues={run.issues} dispatch={dispatch} />
        <RunBar state={state} catalog={catalog} issues={run.issues} running={run.running} dispatch={dispatch} onRun={onRun} />
        {run.failure && <RunFailure failure={run.failure} summary={run.summary} />}
      </div>
    </div>
  )
}
