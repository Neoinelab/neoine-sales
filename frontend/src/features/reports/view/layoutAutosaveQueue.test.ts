import { describe, expect, it } from 'vitest'
import type { ReportLayout } from '../../../shared/model/reportTypes'
import { initialQueue, isBusy, stepQueue, type QueueEvent, type QueueState, type QueueStep } from './layoutAutosaveQueue'

/**
 * 보기 화면 배치 자동 저장의 순수 상태 전이.
 *
 * 계약:
 * - `initialQueue(saved)`: 상태 `{ saved: { layout, revision }, inFlight: false, pending: null, status: 'idle' }`.
 *   status는 'idle' | 'saving' | 'saved' | 'conflict' | 'forbidden' | 'notFound' | 'failed'.
 * - `stepQueue(state, event)`는 `{ state, send }`를 돌려준다. send는 지금 서버로 보낼 요청 `{ layout, revision }` 또는 null이다.
 *   이벤트: change(사용자가 화면 배치를 바꿈, 수정 권한이 있을 때만 보낸다), succeeded(응답의 저장 값), rejected(409 → 'conflict',
 *   403 → 'forbidden', 404 → 'notFound', 그 외 → 'other'), retry(화면의 현재 배치로 다시 시도), reloaded(상세를 다시 읽은 최신 저장 값).
 * - 409 뒤에는 `reloading: true`(초기값 false)이고 `reloaded` 이벤트로 false가 된다. 다시 읽는 동안의 `change`는 보내지 않고
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
  it('처음에는 연 리포트의 배치로 놀고 있고 보낼 것이 없다', () => {
    // when: 리포트를 연 배치(revision 3)로 시작한다
    const state = start(A, 3)

    // then: 확인된 값이 그 배치이고 요청 중이 아니며 바쁘지 않다
    expect(state).toMatchObject({ saved: { layout: A, revision: 3 }, inFlight: false, pending: null, status: 'idle' })
    expect(isBusy(state)).toBe(false)
  })
})

describe('바꿨을 때', () => {
  // 테스트 코드: RS-094
  it('바꾼 배치를 확인된 revision으로 보내고 요청 중으로 표시한다', () => {
    // when: 확인된 배치(revision 4)에서 다른 배치로 바꾼다
    const { state, send } = change(start(A, 4), B)

    // then: 바꾼 배치와 revision 4를 보내고 요청 중(saving)이다
    expect(send).toEqual({ layout: B, revision: 4 })
    expect(state).toMatchObject({ inFlight: true, pending: null, status: 'saving' })
    expect(isBusy(state)).toBe(true)
  })

  // 테스트 코드: RS-095
  it('확인된 배치와 같으면 보내지 않는다', () => {
    // when: 확인된 배치와 같은 값으로 바꾼다
    const { state, send } = change(start(A), { ...A, order: ['table', 'chart'] })

    // then: 보내지 않고 놀고 있다
    expect(send).toBeNull()
    expect(state).toMatchObject({ inFlight: false, pending: null, status: 'idle' })
    expect(isBusy(state)).toBe(false)
  })

  // 테스트 코드: RS-095
  it('확인된 배치로 되돌리면 저장함 표시가 지워진다', () => {
    // given: 배치를 저장해 saved 상태가 된 큐
    const afterSave = succeeded(change(start(A), B).state, B, 2).state
    expect(afterSave.status).toBe('saved')

    // when: 저장된 배치와 같은 값으로 바꾼다
    const { state, send } = change(afterSave, B)

    // then: 보내지 않고 idle로 돌아간다
    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })
})

describe('연속 변경', () => {
  // 테스트 코드: RS-096
  it('요청 중에는 마지막으로 바꾼 값만 대기 값으로 기억한다', () => {
    // given: 요청 중인 큐
    const running = change(start(A), B).state

    // when: 요청 중에 두 번 바꾼다
    const first = change(running, C)
    const second = change(first.state, D)

    // then: 아무것도 보내지 않고 대기 값은 마지막 값이다
    expect(first.send).toBeNull()
    expect(second.send).toBeNull()
    expect(first.state.pending).toEqual(C)
    expect(second.state.pending).toEqual(D)
    expect(second.state.inFlight).toBe(true)
    expect(isBusy(second.state)).toBe(true)
  })

  // 테스트 코드: RS-096
  it('요청이 성공하면 대기 값을 응답의 revision으로 보낸다', () => {
    // given: 요청 중에 대기 값이 생긴 큐
    const waiting = change(change(start(A, 1), B).state, C).state

    // when: 첫 요청이 revision 2로 성공한다
    const { state, send } = succeeded(waiting, B, 2)

    // then: 대기 값을 revision 2로 보내고 요청 중이다
    expect(send).toEqual({ layout: C, revision: 2 })
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: true, pending: null, status: 'saving' })
  })

  // 테스트 코드: RS-096
  it('대기 값 없이 응답이 오면 저장함으로 끝난다', () => {
    // when: 대기 값 없이 요청이 성공한다
    const { state, send } = succeeded(change(start(A, 1), B).state, B, 2)

    // then: 더 보내지 않고 saved이며 바쁘지 않다
    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: false, pending: null, status: 'saved' })
    expect(isBusy(state)).toBe(false)
  })

  // 테스트 코드: RS-096
  it('대기 값이 응답 배치와 같으면 더 보내지 않는다', () => {
    // given: 대기 값이 첫 요청의 값과 같아진 큐
    const waiting = change(change(change(start(A, 1), B).state, C).state, B).state

    // when: 첫 요청이 성공한다
    const { state, send } = succeeded(waiting, B, 2)

    // then: 더 보내지 않고 saved다
    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, inFlight: false, pending: null, status: 'saved' })
  })

  // 테스트 코드: RS-096
  it('요청 중의 세 번 변경은 전체 두 번의 요청으로 나간다', () => {
    // given: 아무것도 보내지 않은 큐
    const sent: (QueueStep['send'])[] = []
    let state = start(A, 1)
    // when: 첫 요청 중에 배치를 세 번 바꾼다
    for (const layout of [B, C, D]) {
      const next = change(state, layout)
      state = next.state
      sent.push(next.send)
    }
    // when: 첫 응답과 둘째 응답을 차례로 받는다
    const afterFirst = succeeded(state, B, 2)
    sent.push(afterFirst.send)
    const afterSecond = succeeded(afterFirst.state, D, 3)
    sent.push(afterSecond.send)

    // then: 보낸 요청은 첫 값과 마지막 값(revision 2) 둘이고 마지막은 saved다
    expect(sent.filter((s) => s !== null)).toEqual([
      { layout: B, revision: 1 },
      { layout: D, revision: 2 },
    ])
    expect(afterSecond.state).toMatchObject({ saved: { layout: D, revision: 3 }, status: 'saved', inFlight: false, pending: null })
  })
})

describe('409', () => {
  // 테스트 코드: RS-099
  it('409면 재시도 없이 멈추고 대기 값을 버리며 충돌을 알린다', () => {
    // given: 요청 중에 대기 값이 있는 큐
    const waiting = change(change(start(A, 1), B).state, C).state

    // when: 요청이 409로 거절된다
    const { state, send } = rejected(waiting, 'conflict')

    // then: 보내지 않고 conflict이며 대기 값이 없다
    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: A, revision: 1 }, inFlight: false, pending: null, status: 'conflict' })
    expect(isBusy(state)).toBe(false)
  })

  // 테스트 코드: RS-099
  it('다시 읽으면 최신 저장 값을 받고 충돌 안내는 유지한다', () => {
    // given: 409를 받은 큐
    const conflicted = rejected(change(start(A, 1), B).state, 'conflict').state

    // when: 최신 저장 값(revision 5)을 다시 읽는다
    const { state, send } = step(conflicted, { type: 'reloaded', saved: { layout: D, revision: 5 } })

    // then: 확인된 값이 최신 값이 되고 충돌 상태는 그대로다
    expect(send).toBeNull()
    expect(state).toMatchObject({ saved: { layout: D, revision: 5 }, status: 'conflict', inFlight: false, pending: null })
  })

  // 테스트 코드: RS-099
  it('다시 읽은 뒤의 변경은 새 revision으로 저장한다', () => {
    // given: 409 뒤 최신 값을 다시 읽은 큐
    const reloaded = step(rejected(change(start(A, 1), B).state, 'conflict').state, { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    // when: 사용자가 배치를 바꾼다
    const { state, send } = change(reloaded, C)

    // then: 새 revision 5로 보내고 요청 중이다
    expect(send).toEqual({ layout: C, revision: 5 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  // 테스트 코드: RS-099
  it('다시 읽은 배치로 되돌리면 놀고 있는 상태가 된다', () => {
    // given: 409 뒤 최신 값을 다시 읽은 큐
    const reloaded = step(rejected(change(start(A, 1), B).state, 'conflict').state, { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    // when: 다시 읽은 배치와 같은 값으로 바꾼다
    const { state, send } = change(reloaded, D)

    // then: 보내지 않고 idle이다
    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })
})

describe('403과 404', () => {
  // 테스트 코드: RS-100
  it.each(['forbidden', 'notFound'] as const)('%s 뒤에는 영원히 멈추고 이후 변경은 아무것도 보내지 않는다', (reason) => {
    // given: 요청이 해당 사유로 거절되어 멈춘 큐
    const stopped = rejected(change(start(A, 1), B).state, reason).state
    expect(stopped).toMatchObject({ status: reason, inFlight: false, pending: null })
    expect(isBusy(stopped)).toBe(false)

    // when: 이후에 배치를 바꾼다
    const again = change(stopped, C)

    // then: 보내지 않고 상태가 그대로다
    expect(again.send).toBeNull()
    expect(again.state).toEqual(stopped)
  })

  // 테스트 코드: RS-100
  it.each(['forbidden', 'notFound'] as const)('%s 뒤에는 대기 값을 버린다', (reason) => {
    // given: 요청 중에 대기 값이 있는 큐
    const waiting = change(change(start(A, 1), B).state, C).state

    // when: 요청이 해당 사유로 거절된다
    const { state } = rejected(waiting, reason)

    // then: 대기 값이 없고 요청 중이 아니다
    expect(state.pending).toBeNull()
    expect(state.inFlight).toBe(false)
  })
})

describe('그 밖의 실패와 다시 시도', () => {
  const failedState = (): QueueState => rejected(change(start(A, 1), B).state, 'other').state

  // 테스트 코드: RS-101
  it('실패하면 확인된 값을 유지하고 대기 값이 없다', () => {
    // when: 요청이 그 밖의 사유로 실패한다
    const state = failedState()

    // then: 확인된 값은 그대로이고 failed이며 바쁘지 않다
    expect(state).toMatchObject({ saved: { layout: A, revision: 1 }, inFlight: false, pending: null, status: 'failed' })
    expect(isBusy(state)).toBe(false)
  })

  // 테스트 코드: RS-101
  it('다시 시도는 화면 배치를 마지막 확인 revision으로 보낸다', () => {
    // when: failed 상태에서 다시 시도한다
    const { state, send } = step(failedState(), { type: 'retry', layout: B })

    // then: 화면 배치를 revision 1로 보내고 요청 중이다
    expect(send).toEqual({ layout: B, revision: 1 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  // 테스트 코드: RS-101
  it('다시 시도는 실패한 값이 아니라 지금 화면의 배치를 보낸다', () => {
    // when: failed 상태에서 화면이 다른 배치일 때 다시 시도한다
    const { send } = step(failedState(), { type: 'retry', layout: C })

    // then: 지금 화면 배치를 보낸다
    expect(send).toEqual({ layout: C, revision: 1 })
  })

  // 테스트 코드: RS-101
  it('화면 배치가 확인된 값과 같으면 다시 시도해도 보내지 않는다', () => {
    // when: failed 상태에서 화면 배치가 확인된 값과 같다
    const { state, send } = step(failedState(), { type: 'retry', layout: A })

    // then: 보내지 않고 idle이다
    expect(send).toBeNull()
    expect(state.status).toBe('idle')
  })

  // 테스트 코드: RS-101
  it('실패 뒤 다음 변경은 마지막 확인 revision으로 보낸다', () => {
    // when: failed 상태에서 배치를 바꾼다
    const { state, send } = change(failedState(), C)

    // then: 마지막 확인 revision 1로 보내고 요청 중이다
    expect(send).toEqual({ layout: C, revision: 1 })
    expect(state).toMatchObject({ inFlight: true, status: 'saving' })
  })

  // 테스트 코드: RS-101
  it('다시 시도가 성공하면 저장함으로 끝난다', () => {
    // given: 다시 시도 중인 큐
    const retrying = step(failedState(), { type: 'retry', layout: B }).state

    // when: 다시 시도가 revision 2로 성공한다
    const { state } = succeeded(retrying, B, 2)

    // then: saved이고 확인된 값이 갱신된다
    expect(state).toMatchObject({ saved: { layout: B, revision: 2 }, status: 'saved', inFlight: false })
  })

  // 테스트 코드: RS-101
  it('실패 상태가 아니면 다시 시도를 무시한다', () => {
    // given: 요청 중인 큐
    const running = change(start(A, 1), B).state

    // when: 다시 시도 이벤트를 받는다
    const { state, send } = step(running, { type: 'retry', layout: C })

    // then: 보내지 않고 상태가 그대로다
    expect(send).toBeNull()
    expect(state).toEqual(running)
  })

  // 테스트 코드: RS-101
  it('실행 중이던 요청이 실패하면 대기 값을 버린다', () => {
    // given: 요청 중에 대기 값이 있는 큐
    const waiting = change(change(start(A, 1), B).state, C).state

    // when: 요청이 그 밖의 사유로 실패한다
    const { state, send } = rejected(waiting, 'other')

    // then: 보내지 않고 대기 값이 없는 failed다
    expect(send).toBeNull()
    expect(state).toMatchObject({ pending: null, inFlight: false, status: 'failed' })
  })
})

describe('409 뒤 다시 읽는 동안', () => {
  const conflicted = (): QueueState => rejected(change(start(A, 1), B).state, 'conflict').state

  // 테스트 코드: RS-099
  it('처음에는 다시 읽는 중이 아니고 409 뒤에는 다시 읽는 중이다', () => {
    // when: 시작 상태와 충돌 상태의 다시 읽기 여부를 읽는다
    const actual = start().reloading
    const actual2 = conflicted().reloading
    // then: 처음은 false, 409 뒤는 true다
    expect(actual).toBe(false)
    expect(actual2).toBe(true)
  })

  // 테스트 코드: RS-099
  it('다시 읽기 응답 전의 변경은 보내지 않고 상태를 그대로 둔다', () => {
    // given: 409 뒤 다시 읽는 중인 큐
    const waiting = conflicted()

    // when: 사용자가 배치를 바꾼다
    const { state, send } = change(waiting, C)

    // then: 보내지 않고 상태가 그대로이며 바쁘지 않다
    expect(send).toBeNull()
    expect(state).toEqual(waiting)
    expect(isBusy(state)).toBe(false)
  })

  // 테스트 코드: RS-099
  it('다시 읽기가 끝나면 최신 값을 받고 충돌 안내는 유지한다', () => {
    // when: 다시 읽는 중인 큐가 최신 값(revision 5)을 받는다
    const { state, send } = step(conflicted(), { type: 'reloaded', saved: { layout: D, revision: 5 } })

    // then: 다시 읽는 중이 끝나고 충돌 상태·최신 값이 유지된다
    expect(send).toBeNull()
    expect(state).toMatchObject({ reloading: false, status: 'conflict', saved: { layout: D, revision: 5 } })
  })

  // 테스트 코드: RS-099
  it('다시 읽은 뒤의 변경은 새 revision으로 보낸다', () => {
    // given: 다시 읽기를 마친 큐
    const reloaded = step(conflicted(), { type: 'reloaded', saved: { layout: D, revision: 5 } }).state

    // when: 사용자가 배치를 바꾼다
    const { send } = change(reloaded, C)

    // then: 새 revision 5로 보낸다
    expect(send).toEqual({ layout: C, revision: 5 })
  })

  // 테스트 코드: RS-099
  it('다시 읽는 중의 변경은 낡은 revision으로 보내지 않고 버린다', () => {
    // given: 다시 읽는 중에 바꾼 변경이 버려진 큐
    const ignored = change(conflicted(), C).state

    // when: 다시 읽기가 끝난다
    const reloaded = step(ignored, { type: 'reloaded', saved: { layout: D, revision: 5 } })

    // then: 보내지 않고 대기 값이 없다
    expect(reloaded.send).toBeNull()
    expect(reloaded.state.pending).toBeNull()
    expect(reloaded.state.inFlight).toBe(false)
  })
})
