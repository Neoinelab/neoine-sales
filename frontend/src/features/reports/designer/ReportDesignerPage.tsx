import { useCallback, useReducer, useState } from 'react'
import { Link } from 'react-router'
import { useReportFields } from '../../../data/reports'
import type { ReportCatalog } from '../../../shared/model/reportTypes'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import '../reports.css'
import { ColumnShelf } from './ColumnShelf'
import { ConditionList } from './ConditionList'
import { FieldPanel } from './FieldPanel'
import { ResultCard } from './ResultCard'
import { RunBar } from './RunBar'
import { ScopeBar } from './ScopeBar'
import { designerReducer, initialDesignerState, isDirty, type DesignerAction, type DesignerState } from './state/designerState'
import { predictScope } from './state/scope'
import { useDesignerRun } from './useDesignerRun'
import { useLeaveGuard } from './useLeaveGuard'

function Heading({ onReset }: { onReset?: () => void }) {
  return (
    <header className="heading report-heading">
      <div>
        <nav aria-label="경로" className="report-crumb">
          <Link to="/reports">Reports</Link>
          <span aria-hidden="true"> ›</span>
        </nav>
        <h1>새 리포트</h1>
      </div>
      {onReset && (
        <button type="button" onClick={onReset}>
          초기화
        </button>
      )}
    </header>
  )
}

/** 카탈로그가 준비된 뒤의 디자이너. 설계는 이 화면의 상태에만 둔다(URL·저장소에 두지 않는다). */
function Designer({ catalog }: { catalog: ReportCatalog }) {
  const reducer = useCallback((state: DesignerState, action: DesignerAction) => designerReducer(state, action, catalog), [catalog])
  const [state, dispatch] = useReducer(reducer, catalog.limits, initialDesignerState)
  const run = useDesignerRun(state, catalog)
  const dirty = isDirty(state, catalog.limits)
  const leave = useLeaveGuard(dirty)
  const [confirmingReset, setConfirmingReset] = useState(false)
  const { noteEdit } = run
  const edit = useCallback(
    (action: DesignerAction) => {
      noteEdit(action)
      dispatch(action)
    },
    [noteEdit],
  )
  const scope = predictScope(state, catalog)
  const reset = () => {
    setConfirmingReset(false)
    run.clear()
    dispatch({ type: 'reset' })
  }

  return (
    <section className="report-page">
      <Heading onReset={() => (dirty ? setConfirmingReset(true) : reset())} />
      <div className="report-designer">
        <FieldPanel
          catalog={catalog}
          usedFields={new Set(state.columns.map((c) => c.field))}
          columnsFull={state.columns.length >= catalog.limits.columnsMax}
          conditionsFull={state.conditions.length >= catalog.limits.conditionsMax}
          onAddColumn={(field) => edit({ type: 'addColumn', field })}
          onAddCondition={(field) => edit({ type: 'addCondition', field })}
        />
        <div className="report-work">
          <ScopeBar scope={scope} combine={state.combine} />
          <ColumnShelf state={state} catalog={catalog} issues={run.issues} dispatch={edit} />
          <ConditionList state={state} catalog={catalog} scope={scope} issues={run.issues} dispatch={edit} />
          <RunBar state={state} catalog={catalog} issues={run.issues} running={run.running} dispatch={edit} onRun={() => void run.run()} />
          <ResultCard key={run.runId} result={run.result} failure={run.failure} summary={run.summary} stale={run.stale} sql={run.result?.sql ?? null} />
        </div>
      </div>
      {leave.pending !== null && (
        <ConfirmDialog
          title="리포트 설계를 떠날까요?"
          message="작성 중인 리포트 설계가 사라집니다. 이 화면을 떠날까요?"
          confirmLabel="떠나기"
          cancelLabel="머물기"
          danger
          onConfirm={leave.confirm}
          onCancel={leave.cancel}
        />
      )}
      {confirmingReset && (
        <ConfirmDialog
          title="설계를 모두 지울까요?"
          message="컬럼과 조건이 모두 사라집니다."
          confirmLabel="초기화"
          cancelLabel="취소"
          danger
          onConfirm={reset}
          onCancel={() => setConfirmingReset(false)}
        />
      )}
    </section>
  )
}

/** `/reports/new`: 리포트 디자이너(로그인한 모든 역할, 조회만). 필드 카탈로그를 불러온 뒤 화면을 보인다. */
export function ReportDesignerPage() {
  const fields = useReportFields()
  if (fields.data) return <Designer catalog={fields.data} />
  return (
    <section className="report-page">
      <Heading />
      {fields.isError ? (
        <>
          <ErrorBanner error={fields.error} />
          <div>
            <button type="button" onClick={() => void fields.refetch()}>
              다시 시도
            </button>
          </div>
        </>
      ) : (
        <p className="hint">불러오는 중…</p>
      )}
    </section>
  )
}
