import { useReportFields } from '../../../data/reports'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import '../reports.css'
import { Designer } from './Designer'

/** `/reports/new`: 리포트 디자이너(로그인한 모든 역할). 필드 카탈로그를 불러온 뒤 화면을 보인다. */
export function ReportDesignerPage() {
  const fields = useReportFields()
  if (fields.data) return <Designer catalog={fields.data} mode={{ kind: 'new' }} />
  return (
    <section className="report-page">
      <h1>새 리포트</h1>
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
