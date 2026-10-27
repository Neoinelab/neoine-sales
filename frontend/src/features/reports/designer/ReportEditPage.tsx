import { useState } from 'react'
import { useParams } from 'react-router'
import { usePermissions } from '../../../data/auth'
import { saveFailure, useReportFields, useReportHandoff, useSavedReport } from '../../../data/reports'
import { parseId } from '../../../shared/model/ids'
import { canEditReport, type Viewer } from '../../../shared/model/permissions'
import type { ReportCatalog, SavedReport } from '../../../shared/model/reportTypes'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Link } from 'react-router'
import '../reports.css'
import { ReportNotFound } from '../ReportNotFound'
import { Designer } from './Designer'
import { fromSavedReport } from './state/fromRequest'

/** 불러온 리포트로 디자이너를 연다. 처음 설계는 한 번만 만든다(이후 리포트 데이터가 갱신돼도 편집 중인 설계는 그대로). */
function Loaded({ catalog, report }: { catalog: ReportCatalog; report: SavedReport }) {
  const handoff = useReportHandoff()
  const [start] = useState(() => ({
    initial: fromSavedReport(report, catalog, catalog.limits),
    seed: handoff.peek(report.id) ?? null,
  }))
  return <Designer catalog={catalog} mode={{ kind: 'edit', report, initial: start.initial, seed: start.seed }} />
}

/** `/reports/:id/edit`: 저장된 리포트를 디자이너에 불러와 한 번 조회한다. 수정 권한이 없으면 보기로 안내한다. */
export function ReportEditPage() {
  const { id: raw } = useParams()
  const id = parseId(raw)
  const fields = useReportFields()
  const report = useSavedReport(id)
  const { me, role } = usePermissions()
  const viewer: Viewer | null = me && role ? { id: me.id, role } : null

  if (id === undefined || (report.error && saveFailure(report.error).kind === 'notFound')) return <ReportNotFound />
  const error = report.error ?? fields.error
  if (error) {
    return (
      <section className="report-page">
        <ErrorBanner error={error} />
      </section>
    )
  }
  if (!report.data || !fields.data || !viewer) return <p className="hint">불러오는 중…</p>
  if (!canEditReport(viewer, report.data)) {
    return (
      <section className="panel report-list">
        <h1>{report.data.name}</h1>
        <p>수정 권한이 없습니다.</p>
        <p>
          <Link to={`/reports/${report.data.id}`}>리포트 보기</Link>
        </p>
      </section>
    )
  }
  return <Loaded key={report.data.id} catalog={fields.data} report={report.data} />
}
