import { useState } from 'react'
import { useNavigate } from 'react-router'
import { saveFailure, useCreateReport, useReportHandoff, useUpdateReport, type SaveFailure } from '../../../data/reports'
import { canChangeReportVisibility, type Viewer } from '../../../shared/model/permissions'
import type { ReportCatalog, ReportIssue, SavedReport, SavedReportMeta } from '../../../shared/model/reportTypes'
import { toChartInput } from '../chart/chartDraft'
import type { SaveMode } from '../SaveReportDialog'
import type { DesignerTab } from './DesignerTabs'
import type { DesignerRun } from './useDesignerRun'
import type { DesignerState } from './state/designerState'
import { toReportRequest } from './state/toRequest'

export interface SaveFlow {
  /** 열려 있는 대화상자의 모드(없으면 닫힘). */
  mode: SaveMode | null
  base: SavedReportMeta | null
  canChangeVisibility: boolean
  busy: boolean
  failure: SaveFailure | null
  open: (mode: SaveMode) => void
  close: () => void
  submit: (meta: SavedReportMeta) => Promise<void>
}

interface Args {
  catalog: ReportCatalog
  state: DesignerState
  run: DesignerRun
  /** 편집 중인 저장 리포트(새 리포트면 null). */
  report: SavedReport | null
  viewer: Viewer | null
  /** 덮어쓰기에 성공했을 때: 서버가 돌려준 저장된 리포트(기준선은 이것으로 계산한다). */
  onOverwritten: (saved: SavedReport) => void
  /** 지금 선택된 탭. 새 리포트를 저장해 편집 화면으로 넘어갈 때 그 탭으로 열도록 넘긴다. */
  tab: DesignerTab
  /** 저장이 정의 위반(422)으로 거절됐을 때: 위반 위치를 따라 탭을 옮길 수 있게 위반 목록을 알린다. */
  onInvalid: (issues: ReportIssue[]) => void
}

/**
 * 저장 대화상자 흐름. 새 리포트·다른 이름으로 저장은 만든 뒤 편집 화면으로 옮겨 가고(replace),
 * 덮어쓰기는 같은 화면에 남는다. 정의 위반(422)은 대화상자를 닫고 디자이너의 위반 표시로 보인다.
 */
export function useSaveFlow({ catalog, state, run, report, viewer, onOverwritten, tab, onInvalid }: Args): SaveFlow {
  const navigate = useNavigate()
  const create = useCreateReport()
  const update = useUpdateReport()
  const handoff = useReportHandoff()
  const [mode, setMode] = useState<SaveMode | null>(null)
  const [failure, setFailure] = useState<SaveFailure | null>(null)
  const base: SavedReportMeta | null = report ? { name: report.name, description: report.description, visibility: report.visibility } : null

  const submit = async (meta: SavedReportMeta): Promise<void> => {
    const built = toReportRequest(state, catalog)
    if (mode === null) return
    if (!('request' in built)) {
      setMode(null)
      run.showInputIssues(built.inputIssues)
      return
    }
    setFailure(null)
    // 차트는 불완전해도 그대로 보낸다(없는 참조는 null): 서버가 위치와 함께 거절한다. 수정에서 차트를 빼면 서버가 지우므로 항상 보낸다.
    const chart = state.chart ? toChartInput(state.chart, state.columns) : null
    // 결과 배치는 항상 보낸다(서버는 생략하면 만들기는 기본 배치, 수정은 저장된 배치를 유지한다).
    const layout = state.layout
    try {
      if (mode === 'overwrite' && report) {
        const saved = await update.mutateAsync({ id: report.id, input: { ...meta, definition: built.request, chart, layout, revision: report.revision } })
        onOverwritten(saved)
        setMode(null)
        return
      }
      const saved = await create.mutateAsync({ ...meta, definition: built.request, chart, layout })
      // 결과가 지금 설계와 같을 때만 넘긴다(아니면 새 편집 화면이 자동 조회한다).
      if (run.result && !run.stale && !run.running) handoff.stash(saved.id, run.result, tab)
      void navigate(`/reports/${saved.id}/edit`, { replace: true })
    } catch (error) {
      const failed = saveFailure(error)
      if (failed.kind === 'invalid') {
        setMode(null)
        run.showSaveIssues(failed.message, failed.issues)
        onInvalid(failed.issues)
      } else {
        setFailure(failed)
      }
    }
  }

  return {
    mode,
    base,
    canChangeVisibility: !report || !viewer || canChangeReportVisibility(viewer, report),
    busy: create.isPending || update.isPending,
    failure,
    open: (next) => {
      setFailure(null)
      setMode(next)
    },
    close: () => {
      setFailure(null)
      setMode(null)
    },
    submit,
  }
}
