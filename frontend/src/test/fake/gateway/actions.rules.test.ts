/** mock Action을 서버 규칙(권한·내용·이력·무변경 수정)에 맞춘 회귀. */

import { describe, expect, it } from 'vitest'
import type { ActionInput, ActionUpdateInput } from '../../../shared/model/types'
import { addDays } from '../../../shared/model/dates'
import { dealCode, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

const content = (over: Partial<ActionUpdateInput> = {}): ActionUpdateInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

const FORBIDDEN_EDIT = '본인 Action 또는 admin만 수정할 수 있습니다.'
const FORBIDDEN_DELETE = '본인 Action 또는 admin만 삭제할 수 있습니다.'

/** 시드 Deal 1의 Action은 모두 김영업(u-kim)이 담당자다. */
async function firstAction(gateway: Awaited<ReturnType<typeof mockAs>>['gateway'], code: string) {
  const first = (await gateway.actions.list(code, {}))[0]
  if (!first) throw new Error('no action')
  return first
}

describe('Action 수정 권한', () => {
  // 담당자 본인 sales는 자기 Action을 고칠 수 있다.
  // 테스트 코드: AC-090
  it('lets the owner sales edit their own action', async () => {
    // given: 담당자 본인(kim)과 그의 Action
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    // when: 진행사항을 고친다
    const updated = await gateway.actions.update(target.id, content({ progress: '본인 수정' }))

    // then: 고쳐지고 담당자는 그대로다
    expect(updated).toMatchObject({ id: target.id, progress: '본인 수정', actor: { id: USER_ID.kim } })
  })

  // 다른 sales의 수정은 고정 문구 403이고 아무것도 바뀌지 않는다.
  // 테스트 코드: AC-090
  it('refuses another sales with 403 and the fixed message, changing nothing', async () => {
    // given: kim이 남긴 Action과 수정 전 History
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})
    // given: 다른 sales(park)로 로그인한다
    await mock.signInAs(USER_ID.park)

    // when·then: 고치면 수정 권한 403이다
    await expectApiError(gateway.actions.update(target.id, content({ progress: '남의 것 수정' })), 403, FORBIDDEN_EDIT)

    // then: Action과 History가 그대로다
    expect(await firstAction(gateway, code)).toEqual(target)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  // 다른 sales가 빈 진행사항으로 고쳐도 검증 오류보다 403이 먼저다.
  // 테스트 코드: AC-090
  it('answers 403 before the validation error when another sales sends an empty progress', async () => {
    // given: 다른 sales(park)와 남의 Action
    const { gateway } = await mockAs('park')
    const target = await firstAction(gateway, dealCode(1))

    // when·then: 진행사항을 비워 고치면 403이다
    await expectApiError(gateway.actions.update(target.id, content({ progress: '' })), 403, FORBIDDEN_EDIT)
  })

  // 없는 Action id는 다른 sales에게도 403보다 먼저 404다.
  // 테스트 코드: AC-090
  it('answers 404 before 403 for an unknown action id even for another sales', async () => {
    // given: 다른 sales(park)
    const { gateway } = await mockAs('park')

    // when·then: 없는 id를 고치면 404다
    await expectApiError(gateway.actions.update(NO_SUCH_ID, content()), 404, 'Action을 찾을 수 없습니다.')
  })

  // user는 Action을 찾기 전에 읽기 전용 403이다.
  // 테스트 코드: AC-090
  it('answers the read-only 403 for the user role before looking for the action', async () => {
    // given: user(han)
    const { gateway } = await mockAs('han')

    // when·then: 없는 id를 고쳐도 403이다
    await expectApiError(gateway.actions.update(NO_SUCH_ID, content()), 403)
  })

  // admin은 남의 Action을 고치고 변경자는 admin이며 담당자는 그대로다.
  // 테스트 코드: AC-090
  it('lets admin edit the action of another user and logs admin as the changer, keeping the actor', async () => {
    // given: admin(root)과 kim의 Action
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    // when: 진행사항을 고친다
    const updated = await gateway.actions.update(target.id, content({ progress: '관리자 수정' }))

    // then: 담당자·수행일은 그대로다
    expect(updated).toMatchObject({ progress: '관리자 수정', actor: { id: USER_ID.kim }, actedOn: target.actedOn })
    // then: History 변경자는 admin이다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'action', by: { id: USER_ID.root } })
  })

  // 담당자는 서버 순서(진행사항, Next Action, Due Date)로 검증된다.
  // 테스트 코드: AC-090
  it('validates in the server order for the owner (progress, Next Action, Due Date)', async () => {
    // given: 담당자 본인(kim)과 그의 Action
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    // when·then: 둘 다 비우면 진행사항 문구 422다
    await expectApiError(gateway.actions.update(target.id, content({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
    // when·then: Due가 비면 Due 필수 422다
    await expectApiError(gateway.actions.update(target.id, content({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
    // when·then: Next Action 없이 Due가 있으면 Due 금지 422다
    await expectApiError(gateway.actions.update(target.id, content({ nextAction: ' ', dueDate: '2026-11-01' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
  })
})

describe('Action 삭제 권한', () => {
  // 다른 sales의 삭제는 고정 문구 403이고 Action·History가 그대로다.
  // 테스트 코드: AC-090
  it('refuses another sales with 403 and the fixed message, keeping the action and the history', async () => {
    // given: kim의 Action 목록과 삭제 전 History
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const before = await gateway.actions.list(code, {})
    const historyBefore = await gateway.history.list(code, {})
    // given: 다른 sales(park)로 로그인한다
    await mock.signInAs(USER_ID.park)

    // when·then: 지우면 삭제 권한 403이다
    await expectApiError(gateway.actions.remove(before[0]?.id ?? NO_SUCH_ID), 403, FORBIDDEN_DELETE)

    // then: 목록과 History가 그대로다
    expect(await gateway.actions.list(code, {})).toEqual(before)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  // 없는 Action id의 삭제는 다른 sales에게도 404다.
  // 테스트 코드: AC-090
  it('answers 404 before 403 for an unknown action id even for another sales', async () => {
    // given: 다른 sales(park)
    const { gateway } = await mockAs('park')

    // when·then: 없는 id를 지우면 404다
    await expectApiError(gateway.actions.remove(NO_SUCH_ID), 404, 'Action을 찾을 수 없습니다.')
  })

  // admin은 남의 Action을 지우고 변경자는 admin이다.
  // 테스트 코드: AC-090
  it('lets admin delete the action of another user and logs admin as the changer', async () => {
    // given: admin(root)과 kim의 Action
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    // when: 지운다
    await gateway.actions.remove(target.id)

    // then: Action이 사라진다
    expect((await gateway.actions.list(code, {})).some((a) => a.id === target.id)).toBe(false)
    // then: History 맨 위는 "삭제"이고 변경자는 admin이다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'action', after: '삭제', by: { id: USER_ID.root } })
  })

  // 담당자 본인 sales는 자기 Action을 지울 수 있다.
  // 테스트 코드: AC-090
  it('lets the owner sales delete their own action', async () => {
    // given: 담당자 본인(kim)과 그의 Action
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    // when: 지운다
    await gateway.actions.remove(target.id)

    // then: Action이 사라진다
    expect((await gateway.actions.list(code, {})).some((a) => a.id === target.id)).toBe(false)
  })
})

describe('Action 내용 규칙', () => {
  // 길이 상한 없이 5,000/5,000/20,000자 텍스트를 그대로 등록한다.
  // 테스트 코드: AC-090
  it('registers 5,000 / 5,000 / 20,000 character texts in full (no length check)', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const progress = '가'.repeat(5000)
    const nextAction = '나'.repeat(5000)
    const memo = '😀'.repeat(20000)

    // when: 긴 텍스트로 등록한다
    const created = await gateway.actions.create(code, input({ progress, nextAction, memo }))

    // then: 응답과 목록 모두 잘리지 않는다
    expect(created).toMatchObject({ progress, nextAction, memo })
    expect((await gateway.actions.list(code, {}))[0]).toMatchObject({ progress, nextAction, memo })
  })

  // 수정도 같은 긴 텍스트를 받는다.
  // 테스트 코드: AC-090
  it('accepts the same long texts on update', async () => {
    // given: 담당자 본인(kim)과 그의 Action
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    // when: 긴 텍스트로 수정한다
    const updated = await gateway.actions.update(target.id, content({ progress: '가'.repeat(5000), nextAction: '나'.repeat(5000), memo: '다'.repeat(20000) }))

    // then: 길이가 그대로다
    expect(updated.progress).toHaveLength(5000)
    expect(updated.memo).toHaveLength(20000)
  })

  // 등록 때 진행사항·Next Action·Memo의 앞뒤 공백을 지운다.
  // 테스트 코드: AC-090
  it('trims progress, Next Action and Memo before saving', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')

    // when: 공백이 낀 텍스트로 등록한다
    const created = await gateway.actions.create(dealCode(2), input({ progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

    // then: 공백이 지워진다
    expect(created).toMatchObject({ progress: '진행', nextAction: '다음', memo: '메모' })
  })

  // 수정 때도 앞뒤 공백을 지운다.
  // 테스트 코드: AC-090
  it('trims on update as well', async () => {
    // given: 담당자 본인(kim)과 그의 Action
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    // when: 공백이 낀 텍스트로 수정한다
    const updated = await gateway.actions.update(target.id, content({ progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

    // then: 공백이 지워진다
    expect(updated).toMatchObject({ progress: '진행', nextAction: '다음', memo: '메모' })
  })

  // 공백뿐인 내용은 없는 것으로 보되 없는 Deal 404가 먼저다.
  // 테스트 코드: AC-090
  it('treats a whitespace-only progress and Next Action as missing and checks the deal first (404 before 422)', async () => {
    // given: sales(kim)와 공백뿐인 입력
    const { gateway } = await mockAs('kim')
    const blank = input({ progress: ' ', nextAction: '  ', dueDate: '' })

    // when·then: 없는 Deal이면 404다
    await expectApiError(gateway.actions.create('20000101-ZZZZ', blank), 404)
    // when·then: 있는 Deal이면 진행사항 문구 422다
    await expectApiError(gateway.actions.create(dealCode(2), blank), 422, '진행사항 또는 Next Action을 입력하세요.')
  })

  // 검증에 실패하면 Action도 History도 늘지 않는다.
  // 테스트 코드: AC-090
  it('stores nothing when the validation fails', async () => {
    // given: sales(kim)와 등록 전 Action·History 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const count = (await gateway.actions.list(code, {})).length
    const history = (await gateway.history.list(code, {})).length

    // when·then: Due 없이 등록하면 Due 필수 422다
    await expectApiError(gateway.actions.create(code, input({ dueDate: '' })), 422, 'Due Date를 입력하세요.')

    // then: Action과 History가 늘지 않는다
    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(await gateway.history.list(code, {})).toHaveLength(history)
  })
})

describe('Action 이력 문구', () => {
  // Memo가 비어 있으면 등록 이력에 Memo 부분이 없다.
  // 테스트 코드: AC-090
  it('logs the registration without a Memo part when the memo is empty', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: Memo 없이 등록한다
    await gateway.actions.create(code, input())

    // then: 이력은 "등록: <요약>"이고 Memo 부분이 없다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      category: 'action',
      target: 'Action',
      before: '',
      after: '등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22)',
    })
  })

  // 등록 이력 요약에는 다듬은 Memo가 붙는다.
  // 테스트 코드: AC-090
  it('appends the trimmed Memo to the registration summary', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: 공백이 낀 Memo로 등록한다
    await gateway.actions.create(code, input({ memo: ' 법무 의견 ' }))

    // then: 이력 요약 끝에 다듬은 Memo가 붙는다
    expect((await gateway.history.list(code, {}))[0]?.after).toBe(
      '등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 법무 의견',
    )
  })

  // 수정 이력은 수정 전 요약과 "수정: " 요약을 Memo까지 담는다.
  // 테스트 코드: AC-090
  it('logs the update with the summary before and the "수정: " summary after, Memo included', async () => {
    // given: Memo가 있는 Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ memo: '이전 메모' }))
// when: 유형·내용을 고친다

    await gateway.actions.update(created.id, content({ type: { name: '통화' }, progress: '전화', nextAction: '방문', dueDate: '2026-11-01', memo: '새 메모' }))

    // then: 이력 변경 전·후에 요약이 있다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      category: 'action',
      before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 이전 메모',
      after: '수정: 통화 · 전화 / Next Action: 방문 (Due 2026-11-01) / Memo: 새 메모',
    })
  })

  // 삭제 이력은 변경 전에 요약, 변경 후에 "삭제"를 담는다.
  // 테스트 코드: AC-090
  it('logs the deletion with the summary before and "삭제" after', async () => {
    // given: Memo가 있는 Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ memo: '메모' }))

    // when: 지운다
    await gateway.actions.remove(created.id)

    // then: 이력 변경 전은 요약이고 변경 후는 "삭제"다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 메모',
      after: '삭제',
    })
  })

  // 긴 등록 요약은 이력에서만 1,000자로 잘리고 Action 원문은 그대로다.
  // 테스트 코드: AC-090
  it('clips a long registration summary to 1,000 code points ending with an ellipsis, keeping the action text whole', async () => {
    // given: sales(kim)
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const progress = '가'.repeat(2000)

    // when: 진행사항 2,000자로 등록한다
    const created = await gateway.actions.create(code, input({ progress }))

    // then: 이력은 1,000자에서 "…"로 끝나고 원문은 그대로다
    const entry = (await gateway.history.list(code, {}))[0]
    expect(Array.from(entry?.after ?? '')).toHaveLength(1000)
    expect(entry?.after.endsWith('…')).toBe(true)
    expect(entry?.after.startsWith('등록: 미팅 · 가')).toBe(true)
    expect(created.progress).toBe(progress)
  })

  // 긴 수정의 변경 전·후 요약은 각각 1,000자로 잘린다.
  // 테스트 코드: AC-090
  it('clips the before and the after summary of a long update independently', async () => {
    // given: 진행사항 2,000자인 Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ progress: '가'.repeat(2000) }))

    // when: 다른 2,000자로 고친다
    await gateway.actions.update(created.id, content({ progress: '나'.repeat(2000) }))

    // then: 변경 전·후가 각각 1,000자에서 "…"로 끝난다
    const entry = (await gateway.history.list(code, {}))[0]
    expect(Array.from(entry?.before ?? '')).toHaveLength(1000)
    expect(Array.from(entry?.after ?? '')).toHaveLength(1000)
    expect(entry?.before.endsWith('…')).toBe(true)
    expect(entry?.after.endsWith('…')).toBe(true)
  })

  // 1,000자 이하 요약은 자르지 않는다.
  // 테스트 코드: AC-090
  it('leaves a summary of 1,000 code points or fewer untouched', async () => {
    // given: 정확히 1,000자가 되는 진행사항
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const head = '등록: 미팅 · '
    const tail = ' / Next Action: 견적 재전달 (Due 2026-10-22)'
    const progress = '가'.repeat(1000 - Array.from(head).length - Array.from(tail).length)

    // when: 등록한다
    await gateway.actions.create(code, input({ progress }))

    // then: 1,000자이고 "…"로 끝나지 않는다
    const after = (await gateway.history.list(code, {}))[0]?.after ?? ''
    expect(Array.from(after)).toHaveLength(1000)
    expect(after.endsWith('…')).toBe(false)
  })
})

describe('내용이 바뀌지 않은 수정', () => {
  // 내용이 같은 수정은 이력도 값도 바꾸지 않는다.
  // 테스트 코드: AC-090
  it('writes no history and changes nothing when the content is the same', async () => {
    // given: 담당자 본인(kim)과 그의 Action·History
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})

    // when: 같은 내용으로 수정한다
    const result = await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: target.progress ?? '', nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: target.memo }),
    )

    // then: 결과가 그대로고 History가 늘지 않는다
    expect(result).toEqual(target)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  // 앞뒤 공백만 다른 수정은 변경이 아니다.
  // 테스트 코드: AC-090
  it('treats a change of only the surrounding whitespace as no change', async () => {
    // given: 담당자 본인(kim)과 그의 Action·History
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})

    // when: 진행사항에 공백만 붙여 수정한다
    await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: `  ${target.progress ?? ''}  `, nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: target.memo }),
    )

    // then: History가 늘지 않는다
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  // Memo만 바뀌어도 이력이 1건 남는다.
  // 테스트 코드: AC-090
  it('still logs one entry when only the memo changes', async () => {
    // given: 담당자 본인(kim)과 그의 Action·History 건수
    const mock = await mockAs('kim')
    const { gateway } = mock
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const base = (await gateway.history.list(code, {})).length

    // when: Memo만 바꿔 수정한다
    await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: target.progress ?? '', nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: `${target.memo}!` }),
    )

    // then: History가 1건 늘었다
    expect(await gateway.history.list(code, {})).toHaveLength(base + 1)
  })
})

describe('Action 검색 날짜와 범위', () => {
  /** 업무 날짜는 서버 시간대(Fake 서버 시계의 오프셋)의 달력 날짜다. 브라우저 시간대에는 의존하지 않는다. */
  const SERVER_NOW = '2026-10-16T10:00:00+09:00'
  const nextDay = (day: string): string => addDays(day, 1)

  // 수행일은 등록 요청의 업무 날짜로 저장된 날짜이고, 검색은 그 저장된 날짜로 비교한다(이후 시계가 바뀌어도 그대로).
  // 테스트 코드: NA-068, NA-029
  it('수행일 조건은 등록 때 저장된 업무 날짜로 비교한다', async () => {
    // given: 서버 시계 10-15 20:00(-12:00)에 등록된 Action(수행일 2026-10-15)이 있고 시계가 이후 10-16로 갔다
    const mock = await mockAs('kim')
    const code = dealCode(2)
    mock.clock.setNow('2026-10-15T20:00:00-12:00')
    const created = await mock.gateway.actions.create(code, input())
    mock.clock.setNow(SERVER_NOW)
    const saved = '2026-10-15'

    // when: 저장된 수행일 10-15와 시계 날짜 10-16으로 각각 검색한다
    const found = await mock.gateway.actions.list(code, { actedFrom: saved, actedTo: saved })
    const wrongDay = await mock.gateway.actions.list(code, { actedFrom: '2026-10-16', actedTo: '2026-10-16' })

    // then: 10-15 검색에만 나온다
    expect(found.map((a) => a.id)).toContain(created.id)
    expect(wrongDay.map((a) => a.id)).not.toContain(created.id)
  })

  // 수행일 범위는 양끝 날짜를 포함하고 이웃 날짜는 제외한다.
  // 테스트 코드: NA-068, NA-029
  it('수행일 범위는 양끝을 포함하고 이웃 날짜는 제외한다', async () => {
    // given: 10-15에 등록된 Action
    const mock = await mockAs('kim')
    const code = dealCode(2)
    mock.clock.setNow('2026-10-15T09:00:00+09:00')
    const created = await mock.gateway.actions.create(code, input())
    const day = '2026-10-15'
    const ids = async (from: string, to: string) => (await mock.gateway.actions.list(code, { actedFrom: from, actedTo: to })).map((a) => a.id)

    // when: 같은 날 범위와 다음 날 범위로 검색한다
    const sameDay = await ids(day, day)
    const following = await ids(nextDay(day), nextDay(day))

    // then: 같은 날 범위에만 나온다
    expect(sameDay).toContain(created.id)
    expect(following).not.toContain(created.id)
  })

  // Due Date 범위는 양끝 날짜를 포함하고 밖의 날짜는 제외한다.
  // 테스트 코드: NA-068, NA-030
  it('Due Date 범위는 양끝을 포함하고 밖의 날짜는 제외한다', async () => {
    // given: Due Date가 12-24인 Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ dueDate: '2026-12-24' }))
    const ids = async (from?: string, to?: string) => (await gateway.actions.list(code, { dueFrom: from, dueTo: to })).map((a) => a.id)

    // when: 12-24 하루 범위, 12-25 이후, 12-23 이전으로 각각 검색한다
    const exact = await ids('2026-12-24', '2026-12-24')
    const after = await ids('2026-12-25', undefined)
    const before = await ids(undefined, '2026-12-23')

    // then: 하루 범위에만 나온다
    expect(exact).toContain(created.id)
    expect(after).not.toContain(created.id)
    expect(before).not.toContain(created.id)
  })

  // 시작이 끝보다 늦은 수행일 범위는 서버 문구의 422다.
  // 테스트 코드: NA-068, NA-031
  it('거꾸로 된 수행일 범위는 서버 문구의 422로 거절한다', async () => {
    // given: 김영업으로 로그인했다
    const { gateway } = await mockAs('kim')

    // when·then: 시작이 끝보다 늦은 수행일 범위로 검색하면 수행일 범위 문구의 422다
    await expectApiError(
      gateway.actions.list(dealCode(1), { actedFrom: '2026-10-20', actedTo: '2026-10-01' }),
      422,
      '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  // 시작이 끝보다 늦은 Due Date 범위는 서버 문구의 422다.
  // 테스트 코드: NA-068, NA-031
  it('거꾸로 된 Due Date 범위는 서버 문구의 422로 거절한다', async () => {
    // given: 김영업으로 로그인했다
    const { gateway } = await mockAs('kim')

    // when·then: 시작이 끝보다 늦은 Due Date 범위로 검색하면 Due Date 범위 문구의 422다
    await expectApiError(
      gateway.actions.list(dealCode(1), { dueFrom: '2026-10-20', dueTo: '2026-10-01' }),
      422,
      'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  // 시작과 끝이 같은 날인 범위는 허용한다.
  // 테스트 코드: NA-068, NA-031
  it('시작과 끝이 같은 날인 범위는 허용한다', async () => {
    // given: 김영업으로 로그인했다
    const { gateway } = await mockAs('kim')

    // when·then: 같은 날 Due Date 범위로 검색하면 오류 없이 목록이 온다
    await expect(gateway.actions.list(dealCode(1), { dueFrom: '2026-10-20', dueTo: '2026-10-20' })).resolves.toBeDefined()
  })

  // 없는 Deal의 Action 목록은 404다.
  // 테스트 코드: NA-068, NA-021
  it('없는 Deal의 Action 목록은 404다', async () => {
    // given: 김영업으로 로그인했다
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal의 목록을 부르면 404다
    await expectApiError(gateway.actions.list('20000101-ZZZZ', {}), 404)
  })
})
