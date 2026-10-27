import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { usePermissions } from '../../data/auth'
import { saveFailure, useCopyReport, useDeleteReport, useSavedReports } from '../../data/reports'
import { formatStamp } from '../../shared/format'
import { userLabel } from '../../shared/model/period'
import type { Viewer } from '../../shared/model/permissions'
import type { SavedReportSummary } from '../../shared/model/reportTypes'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { kindLabel } from './chart/chartKinds'
import { filterReports } from './list/filterReports'
import { ReportRowMenu } from './list/ReportRowMenu'
import './reports.css'
import { SaveReportDialog } from './SaveReportDialog'

function ReportRow({ report, viewer, onCopy, onDelete }: { report: SavedReportSummary; viewer: Viewer; onCopy: () => void; onDelete: () => void }) {
  return (
    <tr>
      <td>
        <Link to={`/reports/${report.id}`}>{report.name}</Link>
        {report.visibility === 'private' && <span className="report-tag tag-private">비공개</span>}
      </td>
      <td className="report-desc">{report.description}</td>
      <td>
        <span className="report-tag tag-deal">Deal</span>
        {report.entities.includes('action') && <span className="report-tag tag-action">Actions</span>}
      </td>
      <td>{report.chartKind ? kindLabel(report.chartKind) : '—'}</td>
      <td>{userLabel(report.owner)}</td>
      <td>
        <span>{formatStamp(report.updatedAt)}</span>
        {report.updatedBy.id !== report.owner.id && <span className="hint report-edited-by"> 수정: {userLabel(report.updatedBy)}</span>}
      </td>
      <td>
        <ReportRowMenu report={report} viewer={viewer} onCopy={onCopy} onDelete={onDelete} />
      </td>
    </tr>
  )
}

/** `/reports`: 저장된 리포트 목록(검색·내가 만든 리포트 거르기는 주소 `?q=&mine=1`에 남는다). */
export function ReportsPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const { me, role } = usePermissions()
  const list = useSavedReports()
  const remove = useDeleteReport()
  const copy = useCopyReport()
  const [deleting, setDeleting] = useState<SavedReportSummary | null>(null)
  const [copying, setCopying] = useState<SavedReportSummary | null>(null)
  const [copyFailure, setCopyFailure] = useState<ReturnType<typeof saveFailure> | null>(null)
  const q = params.get('q') ?? ''
  const mine = params.get('mine') === '1'
  const viewer: Viewer | null = me && role ? { id: me.id, role } : null

  const update = (patch: { q?: string; mine?: boolean }) => {
    const next = new URLSearchParams()
    const nextQ = patch.q ?? q
    const nextMine = patch.mine ?? mine
    if (nextQ !== '') next.set('q', nextQ)
    if (nextMine) next.set('mine', '1')
    setParams(next, { replace: true })
  }

  if (list.isPending) return <p className="hint">불러오는 중…</p>
  const items = list.data ?? []
  const shown = viewer ? filterReports(items, { q, mine }, viewer.id) : items

  return (
    <section className="panel report-list">
      <div className="heading">
        <h1>Reports</h1>
        <Link to="/reports/new" className="button primary">
          + 새 리포트
        </Link>
      </div>
      <ErrorBanner error={list.error} />
      {items.length === 0 && !list.error && <p className="hint">아직 저장한 리포트가 없습니다. 새 리포트를 만들어 조건에 맞는 Deal을 조회해 보세요.</p>}
      {items.length > 0 && (
        <>
          <div className="filters report-filters">
            <div className="field">
              <label htmlFor="report-search">이름·설명 검색</label>
              <input id="report-search" type="text" value={q} onChange={(e) => update({ q: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="report-scope">리포트 범위</label>
              <select id="report-scope" value={mine ? 'mine' : 'all'} onChange={(e) => update({ mine: e.target.value === 'mine' })}>
                <option value="all">전체 리포트</option>
                <option value="mine">내가 만든 리포트</option>
              </select>
            </div>
          </div>
          {shown.length === 0 ? (
            <p className="hint">조건에 맞는 리포트가 없습니다.</p>
          ) : (
            <table>
              <caption className="report-sr">리포트 목록</caption>
              <thead>
                <tr>
                  <th scope="col">이름</th>
                  <th scope="col">설명</th>
                  <th scope="col">데이터</th>
                  <th scope="col">차트</th>
                  <th scope="col">만든 사람</th>
                  <th scope="col">최종 수정</th>
                  <th scope="col">
                    <span className="report-sr">작업</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {viewer &&
                  shown.map((report) => (
                    <ReportRow
                      key={report.id}
                      report={report}
                      viewer={viewer}
                      onCopy={() => {
                        setCopyFailure(null)
                        setCopying(report)
                      }}
                      onDelete={() => setDeleting(report)}
                    />
                  ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {deleting && (
        <ConfirmDialog
          title="리포트 삭제"
          message={`‘${deleting.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`}
          confirmLabel="삭제"
          cancelLabel="취소"
          danger
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
          onCancel={() => {
            remove.reset()
            setDeleting(null)
          }}
        >
          <ErrorBanner error={remove.error} />
        </ConfirmDialog>
      )}
      {copying && (
        <SaveReportDialog
          mode="copy"
          base={{ name: copying.name, description: copying.description, visibility: copying.visibility }}
          canChangeVisibility
          busy={copy.isPending}
          failure={copyFailure}
          onCancel={() => setCopying(null)}
          onSubmit={(meta) => {
            setCopyFailure(null)
            copy.mutate(
              { id: copying.id, meta },
              { onSuccess: (saved) => void navigate(`/reports/${saved.id}/edit`), onError: (error) => setCopyFailure(saveFailure(error)) },
            )
          }}
        />
      )}
    </section>
  )
}
