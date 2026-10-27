import { Link } from 'react-router'
import './reports.css'

/** `/reports`: 리포트 목록 자리. 저장 기능이 아직 없어 빈 목록 안내와 "+ 새 리포트"만 보인다(모든 역할). */
export function ReportsPage() {
  return (
    <section className="panel report-list">
      <div className="heading">
        <h1>Reports</h1>
        <Link to="/reports/new" className="button primary">
          + 새 리포트
        </Link>
      </div>
      <p className="hint">아직 저장한 리포트가 없습니다. 새 리포트를 만들어 조건에 맞는 Deal을 조회해 보세요.</p>
    </section>
  )
}
