import { describe, expect, it } from 'vitest'
import type { ReportLayout } from '../../../shared/model/reportTypes'
import { initialQueue, isBusy, stepQueue, type QueueEvent, type QueueState, type QueueStep } from './layoutAutosaveQueue'

/**
 * 보기 화면 배치 자동 저장의 순수 상태 전이 (개정 1 AC22, AC22a, AC22c, AC22d).
 *
 * 계약(구현 담당이 맞춘다, 계획 7절 "layoutAutosaveQueue.ts의 리듀서"):
 * - `initialQueue(saved)`: 상태 `{ saved: { layout, revision }, inFlight: false, pending: null, status: 'idle' }`.
 *   status는 'idle' | 'saving' | 'saved' | 'conflict' | 'forbidden' | 'notFound' | 'failed'.
 * - `stepQueue(state, event)`는 `{ state, send }`를 돌려준다. send는 지금 서버로 보낼 요청 `{ layout, revision }` 또는 null이다.
 *   이벤트: change(사용자가 화면 배치를 바꿈, 수정 권한이 있을 때만 보낸다), succeeded(응답의 저장 값), rejected(409 → 'conflict',
 *   403 → 'forbidden', 404 → 'notFound', 그 외 → 'other'), retry(화면의 현재 배치로 다시 시도), reloaded(상세를 다시 읽은 최신 저장 값).
 * - (리뷰 Minor) 409 뒤에는 `reloading: true`(초기값 false)이고 `reloaded` 이벤트로 false가 된다. 다시 읽는 동안의 `change`는 보내지 않고
 *   버린다(상태 그대로). 다시 읽기가 끝나면 화면 배치가 최신 저장 값으로 바뀌므로 그 변경은 어차피 사라진다.
 * - `isBusy(state)`: 요청 중이거나 대기 값이 있으면 true(편집·복제 비활성 기준).
 */

const A: ReportLayout = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' }
const B: ReportLayout = { view: 'table', order: ['table', 'chart'], arrange: 'stacked' }
const C: ReportLayout = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' }
const D: ReportLayout = { view: 'both', order: ['chart', 'table'], arrange: 'side_by_side' }

const start = (layout: ReportLayout = A, revision = 1): QueueState => initialQueue({ layout, revision })
const step = (state: QueueState, event: QueueEvent): QueueStep => stepQueue(state, event)
const change = (state: QueueState, layout: ReportLayout): QueueStep => step(state, { type: 'change', layout })
const succeeded = (state: QueueState, layout: ReportLayout, revision: number): QueueStep => step(state, { type: 'succeeded', saved: { layout, revision } })
const rejected = (state: QueueState, reason: 'conflict' | 'forbidden' | 'notFound' | 'other'): QueueStep => step(state, { type: 'rejected', reason })

describe('처음 상태', () => {
  it('is idle with what the report was opened with and nothing to send', () => {
    const state = start(A, 3)

    expect(state).toMatchObject({ saved: { layout: A, revision: 3 }, inFlight: false, pending: null, status: 'idle' })
    expect(isBusy(state)).toBe(false)
  })
})

describe('바꿨을 때 (AC22)', () => {
  it('sends the changed layout with the saved revision and marks the request as running', () => {
    const { state, send } = change(start(A, 4), B)

    expect(send).toEqual({ layout: B, revision: 4 })
    expect(state).toMatchObject({ inFlight: true, pending: null, status: 'saving' })
    expect(isBusy(state)).toBe(true)
  })

  it('sends nothing when the layout equals what is saved', () => {
    const { state, send } = change(start(A), { ...A, order: ['table', 'chart'] })

    expect(send).toBeNull()
    expect(state).toMatchObject({ inFlight: false, pending: null, status: 'idle' })
    expect(isBusy(state)).toBe(false)
  })

  it('clears the saved mark when the layout is changed back to what is saved', () => {
    const afterSave = succeeded(change(start(A), B).state, B, 2).state
    expect(afterSave.status).toBe('saved')

    const { state, send } = change(afterSave, B)

    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })
})

describe('연속 변경 (AC22a)', () => {
  it('keeps only the last changed value while a request is running', () => {
    const running = change(start(A), B).state

    const first = change(running, C)
    const second = change(first.state, D)

    expect(first.send).toBeNull()
    expect(second.send).toBeNull()
    expect(first.state.pending).toEqual(C)
    expect(second.state.pending).toEqual(D)
    expect(second.state.inFlight).toBe(true)
    expect(isBusy(second.state)).toBe(true)
  })

  it('sends the waiting value with the revision of the response when the request succeeds', () => {
    const waiting = change(change(start(A, 1), B).state, C).state

    const { state, send } = succeeded(waiting, B, 2)

    expect(send).toEqual({ layout: C, revision: 2 })
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: true, pending: null, status: 'saving' })
  })

  it('ends saved when the last response had no waiting value', () => {
    const { state, send } = succeeded(change(start(A, 1), B).state, B, 2)

    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: false, pending: null, status: 'saved' })
    expect(isBusy(state)).toBe(false)
  })

  it('sends nothing more when the waiting value equals the saved response', () => {
    const waiting = change(change(change(start(A, 1), B).state, C).state, B).state

    const { state, send } = succeeded(waiting, B, 2)

    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: false, pending: null, status: 'saved' })
  })

  it('sends two requests in all for three changes during the first request', () => {
    const sent: (QueueStep['send'])[] = []
    let state = start(A, 1)
    for (const layout of [B, C, D]) {
      const next = change(state, layout)
      state = next.state
      sent.push(next.send)
    }
    const afterFirst = succeeded(state, B, 2)
    sent.push(afterFirst.send)
    const afterSecond = succeeded(afterFirst.state, D, 3)
    sent.push(afterSecond.send)

    expect(sent.filter((s) => s !== null)).toEqual([
      { layout: B, revision: 1 },
      { layout: D, revision: 2 },
    ])
    expect(afterSecond.state).toMatchObject({ saved: { layout: D, revision: 3 }, status: 'saved', inFlight: false, pending: null })
  })
})

describe('409 (AC22c)', () => {
  it('stops without a retry, drops the waiting value and reports the conflict', () => {
    const waiting = change(change(start(A, 1), B).state, C).state

    const { state, send } = rejected(waiting, 'conflict')

    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: A, revision: 1 }, inFlight: false, pending: null, status: 'conflict' })
    expect(isBusy(state)).toBe(false)
  })

  it('takes the latest saved value after the reload and keeps the conflict message', () => {
    const conflicted = rejected(change(start(A, 1), B).state, 'conflict').state

    const { state, send } = step(conflicted, { type: 'reloaded', saved: { layout: D, revision: 5 } })

    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: D, revision: 5 }, status: 'conflict', inFlight: false, pending: null })
  })

  it('saves again with the new revision when the user changes the layout after the reload', () => {
    const reloaded = step(rejected(change(start(A, 1), B).state, 'conflict').state, { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    const { state, send } = change(reloaded, C)

    expect(send).toEqual({ layout: C, revision: 5 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  it('goes idle when the user puts the layout back to the reloaded one', () => {
    const reloaded = step(rejected(change(start(A, 1), B).state, 'conflict').state, { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    const { state, send } = change(reloaded, D)

    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })
})

describe('403과 404 (AC22d)', () => {
  it.each(['forbidden', 'notFound'] as const)('stops for good after %s: later changes send nothing', (reason) => {
    const stopped = rejected(change(start(A, 1), B).state, reason).state
    expect(stopped).toMatchObject({ status: reason, inFlight: false, pending: null })
    expect(isBusy(stopped)).toBe(false)

    const again = change(stopped, C)

    expect(again.send).toBeNull()
    expect(again.state).toEqual(stopped)
  })

  it.each(['forbidden', 'notFound'] as const)('drops the waiting value after %s', (reason) => {
    const waiting = change(change(start(A, 1), B).state, C).state

    const { state } = rejected(waiting, reason)

    expect(state.pending).toBeNull()
    expect(state.inFlight).toBe(false)
  })
})

describe('그 밖의 실패와 다시 시도 (AC22d)', () => {
  const failedState = (): QueueState => rejected(change(start(A, 1), B).state, 'other').state

  it('keeps the confirmed value and has no waiting value', () => {
    const state = failedState()

    expect(state).toMatchObject({ saved: { layout: A, revision: 1 }, inFlight: false, pending: null, status: 'failed' })
    expect(isBusy(state)).toBe(false)
  })

  it('retries the layout on the screen with the last confirmed revision', () => {
    const { state, send } = step(failedState(), { type: 'retry', layout: B })

    expect(send).toEqual({ layout: B, revision: 1 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  it('retries with the layout the screen shows now, not with the one that failed', () => {
    const { send } = step(failedState(), { type: 'retry', layout: C })

    expect(send).toEqual({ layout: C, revision: 1 })
  })

  it('sends nothing when the screen layout equals the confirmed one', () => {
    const { state, send } = step(failedState(), { type: 'retry', layout: A })

    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })

  it('sends the next change with the last confirmed revision', () => {
    const { state, send } = change(failedState(), C)

    expect(send).toEqual({ layout: C, revision: 1 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  it('ends saved after a successful retry', () => {
    const retrying = step(failedState(), { type: 'retry', layout: B }).state

    const { state } = succeeded(retrying, B, 2)

    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, status: 'saved', inFlight: false })
  })

  it('ignores a retry when the state is not failed', () => {
    const running = change(start(A, 1), B).state

    const { state, send } = step(running, { type: 'retry', layout: C })

    expect(send).toBeNull()
    expect(state).toEqual(running)
  })

  it('drops the waiting value when the request that was running fails', () => {
    const waiting = change(change(start(A, 1), B).state, C).state

    const { state, send } = rejected(waiting, 'other')

    expect(send).toBeNull()
    expect(state).toMatchObject({ pending: null, inFlight: false, status: 'failed' })
  })
})

describe('409 뒤 다시 읽는 동안 (리뷰 Minor)', () => {
  const conflicted = (): QueueState => rejected(change(start(A, 1), B).state, 'conflict').state

  it('starts as not reloading and is reloading after a conflict', () => {
    expect(start().reloading).toBe(false)
    expect(conflicted().reloading).toBe(true)
  })

  it('does not send a change made before the reload answer arrives and leaves the state as it is', () => {
    const waiting = conflicted()

    const { state, send } = change(waiting, C)

    expect(send).toBeNull()
    expect(state).toEqual(waiting)
    expect(isBusy(state)).toBe(false)
  })

  it('ends the reloading with the reloaded value and keeps the conflict message', () => {
    const { state, send } = step(conflicted(), { type: 'reloaded', saved: { layout: D, revision: 5 } })

    expect(send).toBeNull()
    expect(state).toMatchObject({ reloading: false, status: 'conflict', saved: { layout: D, revision: 5 } })
  })

  it('sends a change made after the reload with the new revision', () => {
    const reloaded = step(conflicted(), { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    const { send } = change(reloaded, C)

    expect(send).toEqual({ layout: C, revision: 5 })
  })

  it('discards the change made while reloading instead of sending it with the stale revision after the reload', () => {
    const ignored = change(conflicted(), C).state

    const reloaded = step(ignored, { type: 'reloaded', saved: { layout: D, revision: 5 } })

    expect(reloaded.send).toBeNull()
    expect(reloaded.state.pending).toBeNull()
    expect(reloaded.state.inFlight).toBe(false)
  })
})
