import type { ReportCatalog } from '../../../shared/model/reportTypes'
import type { DesignerAction, DesignerState } from './state/designerState'
import { idsOf, type IssueView } from './state/issueView'

interface RunBarProps {
  state: DesignerState
  catalog: ReportCatalog
  issues: IssueView
  running: boolean
  dispatch: (action: DesignerAction) => void
  onRun: () => void
}

/** 최대 행 · 조회 버튼(정렬은 컬럼 설정에서 컬럼마다 정한다). */
export function RunBar({ state, catalog, issues, running, dispatch, onRun }: RunBarProps) {
  return (
    <section className="report-card report-run" aria-label="최대 행과 조회">
      <div className="field">
        <label htmlFor="report-row-limit">최대 행</label>
        <select
          id="report-row-limit"
          value={String(state.rowLimit)}
          aria-describedby={idsOf(issues.rowLimit)}
          aria-invalid={issues.rowLimit.length > 0 ? true : undefined}
          onChange={(e) => dispatch({ type: 'setRowLimit', rowLimit: Number(e.target.value) })}
        >
          {catalog.limits.rowLimits.map((limit) => (
            <option key={limit} value={String(limit)}>
              {limit.toLocaleString('en-US')}
            </option>
          ))}
        </select>
      </div>
      <button type="button" className="primary" disabled={state.columns.length === 0 || running} onClick={onRun}>
        {running ? '조회 중…' : '조회'}
      </button>
      {issues.rowLimit.map((m) => (
        <p key={m.id} id={m.id} className="field-error report-run-error">
          {m.text}
        </p>
      ))}
    </section>
  )
}
