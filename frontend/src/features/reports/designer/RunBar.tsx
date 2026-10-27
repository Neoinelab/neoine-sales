import type { ReportCatalog, ReportSortDirection } from '../../../shared/model/reportTypes'
import { columnName } from './names'
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

/** 정렬 기준 이름: 같은 표시 이름이 둘 이상이면 컬럼 번호를 붙인다(예: 2. Expected Close). */
function sortLabels(state: DesignerState, catalog: ReportCatalog): { uid: number; text: string }[] {
  const names = state.columns.map((c) => columnName(c, catalog))
  return state.columns.map((c, i) => {
    const name = names[i] ?? ''
    return { uid: c.uid, text: names.filter((n) => n === name).length > 1 ? `${i + 1}. ${name}` : name }
  })
}

/** 정렬(컬럼 하나와 방향) · 최대 행 · 조회 버튼. */
export function RunBar({ state, catalog, issues, running, dispatch, onRun }: RunBarProps) {
  const direction = state.sort?.direction ?? 'asc'
  return (
    <section className="report-card report-run" aria-label="정렬과 조회">
      <div className="field">
        <label htmlFor="report-sort">정렬</label>
        <select
          id="report-sort"
          value={state.sort ? String(state.sort.uid) : ''}
          aria-describedby={idsOf(issues.sort)}
          aria-invalid={issues.sort.length > 0 ? true : undefined}
          onChange={(e) => dispatch({ type: 'setSort', sort: e.target.value === '' ? null : { uid: Number(e.target.value), direction } })}
        >
          <option value="">(정렬 없음)</option>
          {sortLabels(state, catalog).map((s) => (
            <option key={s.uid} value={String(s.uid)}>
              {s.text}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="report-sort-direction">정렬 방향</label>
        <select
          id="report-sort-direction"
          value={direction}
          disabled={state.sort === null}
          onChange={(e) => state.sort && dispatch({ type: 'setSort', sort: { uid: state.sort.uid, direction: e.target.value as ReportSortDirection } })}
        >
          <option value="asc">오름차순</option>
          <option value="desc">내림차순</option>
        </select>
      </div>
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
      {[...issues.sort, ...issues.rowLimit].map((m) => (
        <p key={m.id} id={m.id} className="field-error report-run-error">
          {m.text}
        </p>
      ))}
    </section>
  )
}
