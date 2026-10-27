import { Link } from 'react-router'

/** 없거나 볼 수 없는 리포트(서버가 둘을 구분하지 않는다)나 잘못된 주소의 안내. */
export function ReportNotFound() {
  return (
    <section className="panel report-list">
      <h1>Reports</h1>
      <p>리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.</p>
      <p>
        <Link to="/reports">리포트 목록</Link>
      </p>
    </section>
  )
}
