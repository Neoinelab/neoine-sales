import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { usePermissions } from '../../../data/auth'
import { reportRunFailure, saveFailure, useCopyReport, useDeleteReport, useRunSavedReport, useSavedReport } from '../../../data/reports'
import { formatStamp } from '../../../shared/format'
import { parseId } from '../../../shared/model/ids'
import { canDeleteReport, canEditReport, type Viewer } from '../../../shared/model/permissions'
import { userLabel } from '../../../shared/model/period'
import type { ReportRunFailure, SavedReport } from '../../../shared/model/reportTypes'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { ResultCard } from '../designer/ResultCard'
import '../reports.css'
import { ReportNotFound } from '../ReportNotFound'
import { SaveReportDialog } from '../SaveReportDialog'

function metaLine(report: SavedReport): string {
  const edited = report.updatedBy.id !== report.owner.id ? ` (수정: ${userLabel(report.updatedBy)})` : ''
  return `${userLabel(report.owner)} · ${formatStamp(report.updatedAt)}${edited}`
}

/** 저장된 정의가 지금 규칙과 맞지 않거나(편집에서 고쳐야 함) 시간 초과 등으로 실행하지 못했을 때. */
function RunFailure({ failure }: { failure: ReportRunFailure }) {
  if (failure.kind !== 'invalid') {
    return (
      <p role="alert" className="error">
        {failure.message}
      </p>
    )
  }
  return (
    <div role="alert" className="report-summary">
      <p>저장된 설계가 지금 규칙과 맞지 않습니다. 편집에서 고치세요</p>
      <ul>
        {failure.issues.length > 0 ? failure.issues.map((issue, i) => <li key={i}>{issue.message}</li>) : <li>{failure.message}</li>}
      </ul>
    </div>
  )
}

/** `/reports/:id`: 저장된 리포트를 열 때마다 다시 조회해 결과 표와 생성 SQL(읽기 전용)을 보인다. */
export function ReportViewPage() {
  const { id: raw } = useParams()
  const id = parseId(raw)
  const navigate = useNavigate()
  const { me, role } = usePermissions()
  const report = useSavedReport(id)
  // 보이지 않는 리포트는 실행 요청도 보내지 않는다(없는 id와 똑같이 404).
  const run = useRunSavedReport(report.data ? id : undefined)
  const remove = useDeleteReport()
  const copy = useCopyReport()
  const [deleting, setDeleting] = useState(false)
  const [copying, setCopying] = useState(false)
  const [copyFailure, setCopyFailure] = useState<ReturnType<typeof saveFailure> | null>(null)
  const viewer: Viewer | null = me && role ? { id: me.id, role } : null

  if (id === undefined || (report.error && saveFailure(report.error).kind === 'notFound')) return <ReportNotFound />
  if (report.error) return <ErrorBanner error={report.error} />
  const data = report.data
  if (!data || !viewer) return <p className="hint">불러오는 중…</p>
  const failure = run.error ? reportRunFailure(run.error) : null

  return (
    <section className="report-page">
      <header className="heading report-heading">
        <div>
          <nav aria-label="경로" className="report-crumb">
            <Link to="/reports">Reports</Link>
            <span aria-hidden="true"> ›</span>
          </nav>
          <div className="report-title">
            <h1>{data.name}</h1>
            {data.visibility === 'private' && <span className="report-tag tag-private">비공개</span>}
          </div>
          {data.description !== '' && <p>{data.description}</p>}
          <p className="hint">{metaLine(data)}</p>
        </div>
        <div className="report-heading-actions">
          <button type="button" disabled={run.isFetching} onClick={() => void run.refetch()}>
            다시 조회
          </button>
          {canEditReport(viewer, data) && (
            <Link to={`/reports/${data.id}/edit`} className="button">
              편집
            </Link>
          )}
          <button
            type="button"
            onClick={() => {
              setCopyFailure(null)
              setCopying(true)
            }}
          >
            복제
          </button>
          {canDeleteReport(viewer, data) && (
            <button type="button" className="danger" onClick={() => setDeleting(true)}>
              삭제
            </button>
          )}
        </div>
      </header>
      {failure && <RunFailure failure={failure} />}
      {run.data ? <ResultCard result={run.data} failure={null} summary={[]} stale={false} sql={run.data.sql} /> : !failure && <p className="hint">불러오는 중…</p>}
      {deleting && (
        <ConfirmDialog
          title="리포트 삭제"
          message={`‘${data.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`}
          confirmLabel="삭제"
          cancelLabel="취소"
          danger
          busy={remove.isPending}
          onConfirm={() => remove.mutate(data.id, { onSuccess: () => void navigate('/reports') })}
          onCancel={() => {
            remove.reset()
            setDeleting(false)
          }}
        >
          <ErrorBanner error={remove.error} />
        </ConfirmDialog>
      )}
      {copying && (
        <SaveReportDialog
          mode="copy"
          base={{ name: data.name, description: data.description, visibility: data.visibility }}
          canChangeVisibility
          busy={copy.isPending}
          failure={copyFailure}
          onCancel={() => setCopying(false)}
          onSubmit={(meta) => {
            setCopyFailure(null)
            copy.mutate(
              { id: data.id, meta },
              { onSuccess: (saved) => void navigate(`/reports/${saved.id}/edit`), onError: (error) => setCopyFailure(saveFailure(error)) },
            )
          }}
        />
      )}
    </section>
  )
}
