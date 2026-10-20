import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useCodeSet } from '../../data/codes'
import {
  finalizePlan,
  planChange,
  type SyncApplied,
  type SyncChange,
  type SyncPlan,
  type SyncResolution,
  type SyncState,
} from '../model/sync'
import { ChoiceDialog } from './ChoiceDialog'
import { RevenueDialog } from './RevenueDialog'
import './sync.css'

/** 변경 대상 Deal의 현재 값. revenue*는 매출 확정 팝업의 미리 채움용(예상값). */
export interface SyncSubject extends SyncState {
  revenueAmount?: number
  revenueDate?: string
}

/** request의 선택 인자. from은 판정 기준 상태(기본: 훅의 subject), guard는 대화상자가 필요한 계획을 미리 막는다(문자열이면 거부 문구). */
export interface RequestOptions {
  from?: SyncSubject
  guard?: (plan: SyncPlan, state: SyncState) => string | null
}

type Interactive = Exclude<SyncPlan, { kind: 'independent' }>

interface Pending {
  plan: Interactive
  state: SyncState
  subject: SyncSubject
  resolve: (applied: SyncApplied | null) => void
}

/**
 * Status⇄Forecast 동기화 UI 훅(계획 7.2). 호출처는 `dialogs`를 화면에 렌더하고,
 * `request(change)`의 결과(SyncApplied, 취소는 null)를 즉시 저장 또는 draft 반영으로 적용한다.
 * 필요하면 매출 확정/함께 바꿀 값 선택 팝업을 띄우고, 거부 시 팝업 안에 문구를 보인다.
 * 코드표가 아직 없으면 request는 Error로 reject한다.
 */
export function useSyncedChange(subject: SyncSubject) {
  const codes = useCodeSet().data
  const [pending, setPending] = useState<Pending | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pendingRef = useRef<Pending | null>(null)

  const close = useCallback((result: SyncApplied | null) => {
    const current = pendingRef.current
    pendingRef.current = null
    setPending(null)
    setError(null)
    current?.resolve(result)
  }, [])

  useEffect(() => () => close(null), [close])

  const request = useCallback(
    (change: SyncChange, options?: RequestOptions): Promise<SyncApplied | null> => {
      if (!codes) return Promise.reject(new Error('코드 목록을 불러오지 못했습니다.'))
      const base = options?.from ?? subject
      const state: SyncState = { statusKey: base.statusKey, forecastKey: base.forecastKey }
      const plan = planChange(state, change, codes)
      if (plan.kind === 'independent') {
        const done = finalizePlan(state, plan, undefined, codes)
        return done.ok ? Promise.resolve(done.applied) : Promise.reject(new Error(done.message))
      }
      const blocked = options?.guard?.(plan, state)
      if (blocked) return Promise.reject(new Error(blocked))
      close(null)
      return new Promise((resolve) => {
        const next: Pending = { plan, state, subject: base, resolve }
        pendingRef.current = next
        setPending(next)
      })
    },
    [codes, subject, close],
  )

  function confirm(resolution: SyncResolution) {
    if (!pending || !codes) return
    const done = finalizePlan(pending.state, pending.plan, resolution, codes)
    if (done.ok) close(done.applied)
    else setError(done.message)
  }

  let dialogs: ReactNode = null
  if (pending && codes) {
    const { plan } = pending
    if (plan.kind === 'needRevenue') {
      dialogs = (
        <RevenueDialog
          notice={plan.notice}
          defaultAmount={pending.subject.revenueAmount}
          defaultDate={pending.subject.revenueDate}
          error={error}
          onConfirm={confirm}
          onCancel={() => close(null)}
        />
      )
    } else {
      const isStatus = plan.kind === 'askStatus'
      const list = isStatus ? codes.statuses : codes.forecasts
      dialogs = (
        <ChoiceDialog
          prompt={plan.prompt}
          options={plan.options.map((key) => ({ value: key, label: list.find((c) => c.key === key)?.name ?? key }))}
          defaultValue={isStatus ? plan.defaultKey : null}
          error={error}
          onConfirm={(value) => confirm(isStatus ? { statusKey: value } : { forecastKey: value })}
          onCancel={() => close(null)}
        />
      )
    }
  }

  return { request, dialogs }
}
