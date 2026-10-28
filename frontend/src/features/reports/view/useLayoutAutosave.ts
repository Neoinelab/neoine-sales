import { useEffect, useRef, useState } from 'react'
import { saveFailure, useReloadSavedReport, useSaveReportLayout } from '../../../data/reports'
import type { ReportLayout, SavedReport } from '../../../shared/model/reportTypes'
import { initialQueue, isBusy, stepQueue, type QueueEvent, type QueueStatus, type RejectReason, type SavedLayout } from './layoutAutosaveQueue'

export interface LayoutAutosave {
  /** 화면에 그릴 배치(저장 응답으로 덮어쓰지 않는다: 그 사이 바꾼 값이 사라지지 않게). */
  layout: ReportLayout
  /** 보기 선택·타일 놓기에서 호출한다. */
  change: (next: ReportLayout) => void
  status: QueueStatus
  /** 요청 중이거나 대기 값이 있다(편집·복제 비활성). */
  busy: boolean
  /** 실패(failed) 뒤 화면의 배치를 마지막으로 확인된 revision으로 다시 저장한다. */
  retry: () => void
  /** 이 화면에서 저장할 수 있다(수정 권한이 있고 403·404로 멈추지 않았다). */
  canSave: boolean
}

function rejectReason(error: unknown): RejectReason {
  switch (saveFailure(error).kind) {
    case 'conflict':
      return 'conflict'
    case 'forbidden':
      return 'forbidden'
    case 'notFound':
      return 'notFound'
    default:
      return 'other'
  }
}

/**
 * 보기 화면의 배치 자동 저장. 수정 권한이 있으면 배치를 바꿀 때마다 `PUT .../layout`으로 저장하고
 * (요청은 한 번에 1개, 요청 중 바뀐 값은 마지막 것만 이어서 보냄), 권한이 없으면 화면에서만 바꾼다.
 * 409는 최신 리포트를 다시 읽어 화면 배치를 그 값으로 바꾸고 `onReloaded`(결과 다시 조회)를 부른다. 자동 재시도는 없다.
 */
export function useLayoutAutosave(report: SavedReport, canEdit: boolean, onReloaded: () => void): LayoutAutosave {
  const save = useSaveReportLayout()
  const reload = useReloadSavedReport()
  const [layout, setLayout] = useState(report.layout)
  const screenLayout = useRef(report.layout)
  const [queue, setQueue] = useState(() => initialQueue({ layout: report.layout, revision: report.revision }))
  // 상태 전이는 이벤트 핸들러·비동기 응답에서 바로 이어 읽어야 하므로(렌더를 기다리지 않는다) 같은 값을 ref에도 둔다.
  const queueRef = useRef(queue)
  const alive = useRef(false)
  const reloadedRef = useRef(onReloaded)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])
  useEffect(() => {
    reloadedRef.current = onReloaded
  })

  const apply = (event: QueueEvent): void => {
    const { state, send } = stepQueue(queueRef.current, event)
    queueRef.current = state
    setQueue(state)
    if (send) void post(send)
  }

  /** 충돌·권한 변경 뒤 서버의 최신 값을 가져온다. 충돌이면 화면 배치도 그 값으로 바꾸고 결과를 다시 조회한다. */
  const reloadLatest = async (replaceScreen: boolean): Promise<void> => {
    const latest = await reload(report.id).catch(() => null)
    // 그 사이 사용자가 다시 바꿨으면(요청 중) 그 요청의 응답이 기준을 정한다.
    if (!alive.current) return
    if (latest === null) {
      // 다시 읽기 실패: 다시 바꿀 수 있게 풀어 준다(기준 revision은 그대로라 다음 저장이 409면 다시 읽는다).
      if (queueRef.current.reloading) apply({ type: 'reloaded', saved: queueRef.current.saved })
      return
    }
    if (isBusy(queueRef.current)) return
    apply({ type: 'reloaded', saved: { layout: latest.layout, revision: latest.revision } })
    if (!replaceScreen) return
    screenLayout.current = latest.layout
    setLayout(latest.layout)
    reloadedRef.current()
  }

  const post = async (request: SavedLayout): Promise<void> => {
    try {
      const saved = await save.mutateAsync({ id: report.id, layout: request.layout, revision: request.revision })
      if (alive.current) apply({ type: 'succeeded', saved: { layout: saved.layout, revision: saved.revision } })
    } catch (error) {
      if (!alive.current) return
      const reason = rejectReason(error)
      apply({ type: 'rejected', reason })
      if (reason === 'conflict' || reason === 'forbidden') void reloadLatest(reason === 'conflict')
    }
  }

  const change = (next: ReportLayout): void => {
    screenLayout.current = next
    setLayout(next)
    if (canEdit) apply({ type: 'change', layout: next })
  }

  return {
    layout,
    change,
    status: queue.status,
    busy: isBusy(queue),
    retry: () => apply({ type: 'retry', layout: screenLayout.current }),
    canSave: canEdit && queue.status !== 'forbidden' && queue.status !== 'notFound',
  }
}
