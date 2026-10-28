import type { ReportLayout } from '../../../shared/model/reportTypes'
import { sameLayout } from '../result/layout'

/**
 * 보기 화면 배치 자동 저장의 순수 상태 전이(화면·네트워크 없음).
 * 규칙: 요청은 동시에 1개. 요청 중 바뀐 값은 "대기 값" 하나로만 기억(중간 값은 버림)하고,
 * 성공 응답의 revision으로 이어서 보낸다. 409·403·404는 멈추고(재시도 없음), 그 밖의 실패는 '다시 시도'로만 다시 보낸다.
 */

export interface SavedLayout {
  layout: ReportLayout
  revision: number
}

export type QueueStatus = 'idle' | 'saving' | 'saved' | 'conflict' | 'forbidden' | 'notFound' | 'failed'
export type RejectReason = 'conflict' | 'forbidden' | 'notFound' | 'other'

export interface QueueState {
  /** 서버가 마지막으로 확인한 값. */
  saved: SavedLayout
  inFlight: boolean
  /** 요청 중에 바뀐 마지막 값(없으면 null). */
  pending: ReportLayout | null
  status: QueueStatus
  /** 409 뒤 최신 값을 다시 읽는 중(이 동안 바뀐 값은 낡은 revision으로 보내지 않고 버린다). */
  reloading: boolean
}

export type QueueEvent =
  | { type: 'change'; layout: ReportLayout }
  | { type: 'succeeded'; saved: SavedLayout }
  | { type: 'rejected'; reason: RejectReason }
  | { type: 'retry'; layout: ReportLayout }
  | { type: 'reloaded'; saved: SavedLayout }

export interface QueueStep {
  state: QueueState
  /** 지금 서버로 보낼 요청(없으면 null). */
  send: SavedLayout | null
}

export const initialQueue = (saved: SavedLayout): QueueState => ({ saved, inFlight: false, pending: null, status: 'idle', reloading: false })

/** 요청 중이거나 대기 값이 있다(편집·복제를 막는 기준). */
export const isBusy = (state: QueueState): boolean => state.inFlight || state.pending !== null

const REJECTED: Record<RejectReason, QueueStatus> = { conflict: 'conflict', forbidden: 'forbidden', notFound: 'notFound', other: 'failed' }

/** 서버 값과 같으면 보내지 않고 idle, 다르면 서버가 확인한 revision으로 보낸다. */
function sendIfChanged(state: QueueState, layout: ReportLayout): QueueStep {
  if (sameLayout(layout, state.saved.layout)) return { state: { ...state, pending: null, inFlight: false, status: 'idle' }, send: null }
  return { state: { ...state, pending: null, inFlight: true, status: 'saving' }, send: { layout, revision: state.saved.revision } }
}

export function stepQueue(state: QueueState, event: QueueEvent): QueueStep {
  switch (event.type) {
    case 'change':
      if (state.reloading) return { state, send: null }
      // 403·404 뒤에는 저장하지 않는다(화면 배치만 바뀐다).
      if (state.status === 'forbidden' || state.status === 'notFound') return { state, send: null }
      if (state.inFlight) return { state: { ...state, pending: event.layout }, send: null }
      return sendIfChanged(state, event.layout)
    case 'succeeded': {
      const saved = event.saved
      const settled: QueueState = { ...state, saved, inFlight: false, pending: null }
      if (state.pending !== null && !sameLayout(state.pending, saved.layout)) return sendIfChanged(settled, state.pending)
      return { state: { ...settled, status: 'saved' }, send: null }
    }
    case 'rejected':
      return { state: { ...state, inFlight: false, pending: null, status: REJECTED[event.reason], reloading: event.reason === 'conflict' }, send: null }
    case 'retry':
      if (state.status !== 'failed') return { state, send: null }
      return sendIfChanged(state, event.layout)
    case 'reloaded':
      // 요청 중이면 그 응답이 기준을 정한다.
      if (state.inFlight) return { state, send: null }
      return { state: { ...state, saved: event.saved, pending: null, reloading: false }, send: null }
  }
}
