import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { Link } from 'react-router'
import { usePermissions } from '../../../data/auth'
import { useReportHandoff } from '../../../data/reports'
import type { Viewer } from '../../../shared/model/permissions'
import type { ReportCatalog, ReportResult, SavedReport } from '../../../shared/model/reportTypes'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import '../reports.css'
import { SaveReportDialog } from '../SaveReportDialog'
import { ColumnShelf } from './ColumnShelf'
import { ConditionList } from './ConditionList'
import { FieldPanel } from './FieldPanel'
import { ResultCard } from './ResultCard'
import { RunBar } from './RunBar'
import { ScopeBar } from './ScopeBar'
import { designKey } from './state/designKey'
import { designerReducer, initialDesignerState, isDirty, type DesignerAction, type DesignerState } from './state/designerState'
import { fromReportRequest } from './state/fromRequest'
import { predictScope } from './state/scope'
import { useDesignerRun } from './useDesignerRun'
import { useLeaveGuard } from './useLeaveGuard'
import { useSaveFlow } from './useSaveFlow'

/** new: `/reports/new` · edit: 저장된 리포트를 불러온 `/reports/:id/edit`. */
export type DesignerMode =
  | { kind: 'new' }
  | { kind: 'edit'; report: SavedReport; initial: DesignerState; seed: ReportResult | null }

interface HeadingProps {
  title: string
  unsaved: boolean
  edit: boolean
  canSave: boolean
  saveTitle: string | undefined
  onReset: () => void
  onSaveAs: () => void
  onSave: () => void
}

function Heading({ title, unsaved, edit, canSave, saveTitle, onReset, onSaveAs, onSave }: HeadingProps) {
  return (
    <header className="heading report-heading">
      <div>
        <nav aria-label="경로" className="report-crumb">
          <Link to="/reports">Reports</Link>
          <span aria-hidden="true"> ›</span>
        </nav>
        <div className="report-title">
          <h1>{title}</h1>
          {unsaved && (
            <span role="status" className="report-unsaved">
              ● 저장 안 됨
            </span>
          )}
        </div>
      </div>
      <div className="report-heading-actions">
        <button type="button" onClick={onReset}>
          {edit ? '되돌리기' : '초기화'}
        </button>
        {edit && (
          <button type="button" onClick={onSaveAs}>
            다른 이름으로 저장
          </button>
        )}
        <button type="button" className="primary" disabled={!canSave} title={saveTitle} onClick={onSave}>
          저장
        </button>
      </div>
    </header>
  )
}

/** 카탈로그가 준비된 뒤의 디자이너. 설계는 이 화면의 상태에만 둔다(저장 전에는 URL·저장소에 두지 않는다). */
export function Designer({ catalog, mode }: { catalog: ReportCatalog; mode: DesignerMode }) {
  // 편집 기준 리포트(revision·기본 메타)는 불러온 값에 고정하고, 내 덮어쓰기 성공 응답으로만 갱신한다(남의 저장으로 캐시가 바뀌어도 따라가지 않는다).
  const [report, setReport] = useState<SavedReport | null>(mode.kind === 'edit' ? mode.report : null)
  const reducer = useCallback((state: DesignerState, action: DesignerAction) => designerReducer(state, action, catalog), [catalog])
  const [state, dispatch] = useReducer(reducer, mode, (m) => (m.kind === 'edit' ? m.initial : initialDesignerState(catalog.limits)))
  const run = useDesignerRun(state, catalog, mode.kind === 'edit' ? mode.seed : null)
  // 편집 화면의 "저장된 설계": 처음 불러온 정의, 덮어쓰기 뒤에는 그때 저장한 정의.
  const [saved, setSaved] = useState(() => ({ key: mode.kind === 'edit' ? designKey(mode.initial, catalog) : '', definition: report?.definition ?? null }))
  const { me, role } = usePermissions()
  const viewer: Viewer | null = me && role ? { id: me.id, role } : null
  const flow = useSaveFlow({
    catalog,
    state,
    run,
    report,
    viewer,
    onOverwritten: (savedReport, key) => {
      setReport(savedReport)
      setSaved({ key, definition: savedReport.definition })
    },
  })
  const handoff = useReportHandoff()
  const dirty = mode.kind === 'edit' ? designKey(state, catalog) !== saved.key : isDirty(state, catalog.limits)
  const leave = useLeaveGuard(dirty)
  const [confirming, setConfirming] = useState(false)
  const { noteEdit } = run
  const edit = useCallback(
    (action: DesignerAction) => {
      noteEdit(action)
      dispatch(action)
    },
    [noteEdit],
  )

  // 저장된 설계를 열면 한 번 자동 조회한다(저장 직후 넘겨 받은 결과가 있으면 다시 조회하지 않는다).
  const autoRun = useRef(false)
  useEffect(() => {
    if (mode.kind !== 'edit' || autoRun.current) return
    autoRun.current = true
    if (mode.seed) handoff.drop(mode.report.id)
    else void run.run()
    // 마운트 때 한 번만.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const scope = predictScope(state, catalog)
  const resetDesign = () => {
    setConfirming(false)
    run.clear()
    if (mode.kind === 'edit' && saved.definition) dispatch({ type: 'load', state: fromReportRequest(saved.definition, catalog, catalog.limits) })
    else dispatch({ type: 'reset' })
  }
  const canSave = run.result !== null && !run.stale && !run.running
  const saveTitle = canSave ? undefined : run.result === null ? '먼저 조회하세요' : '바뀐 설계를 다시 조회한 뒤 저장하세요'

  return (
    <section className="report-page">
      <Heading
        title={report?.name ?? '새 리포트'}
        unsaved={dirty}
        edit={mode.kind === 'edit'}
        canSave={canSave}
        saveTitle={saveTitle}
        onReset={() => {
          if (dirty) setConfirming(true)
          else if (mode.kind !== 'edit') resetDesign() // 편집 화면은 변경이 없으면 되돌릴 것이 없다.
        }}
        onSaveAs={() => flow.open('saveAs')}
        onSave={() => flow.open(mode.kind === 'edit' ? 'overwrite' : 'create')}
      />
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
          title="저장하지 않은 변경이 있습니다"
          message="저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?"
          confirmLabel="떠나기"
          cancelLabel="머물기"
          danger
          onConfirm={leave.confirm}
          onCancel={leave.cancel}
        />
      )}
      {confirming && (
        <ConfirmDialog
          title={mode.kind === 'edit' ? '저장된 설계로 되돌릴까요?' : '설계를 모두 지울까요?'}
          message={mode.kind === 'edit' ? '저장하지 않은 변경이 사라집니다.' : '컬럼과 조건이 모두 사라집니다.'}
          confirmLabel={mode.kind === 'edit' ? '되돌리기' : '초기화'}
          cancelLabel="취소"
          danger
          onConfirm={resetDesign}
          onCancel={() => setConfirming(false)}
        />
      )}
      {flow.mode && (
        <SaveReportDialog
          mode={flow.mode}
          base={flow.base}
          canChangeVisibility={flow.canChangeVisibility}
          busy={flow.busy}
          failure={flow.failure}
          onSubmit={(meta) => void flow.submit(meta)}
          onCancel={flow.close}
          onSaveAs={() => flow.open('saveAs')}
        />
      )}
    </section>
  )
}
