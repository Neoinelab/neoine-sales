import { describeScope, type ScopePrediction } from './state/scope'
import type { ReportCombine } from '../../../shared/model/reportTypes'

/** 행 단위(Deal/Action)와 조건·합계 규칙을 설계가 바뀔 때마다 보인다. 서버 규칙과 같은 판정은 `predictScope`가 한다. */
export function ScopeBar({ scope, combine }: { scope: ScopePrediction; combine: ReportCombine }) {
  const { headline, notes } = describeScope(scope, combine)
  return (
    <p role="status" className={`report-scope scope-${scope.rowScope}`}>
      <strong>{headline}</strong>
      {notes.map((note) => (
        <span key={note} className="report-scope-note">
          {' '}
          {note}
        </span>
      ))}
    </p>
  )
}
