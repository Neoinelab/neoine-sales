/** P2 R2: mock Action을 서버 규칙(계획 2장 AC-02·03·10~12·15, 8.1 R-11·R-12·R-14·R-17)에 맞춘 회귀. */

import { describe, expect, it } from 'vitest'
import type { ActionInput, ActionUpdateInput } from '../../../shared/model/types'
import { dealCode, expectApiError, mockAs } from '../testing'

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

describe('Action 수정 권한 (AC-10, Q8)', () => {
  it('lets the owner sales edit their own action', async () => {
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    const updated = await gateway.actions.update(target.id, content({ progress: '본인 수정' }))

    expect(updated).toMatchObject({ id: target.id, progress: '본인 수정', actor: { id: 'u-kim' } })
  })

  it('refuses another sales with 403 and the Q8 message, changing nothing', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})
    await gateway.auth.quickLogin('u-park')

    await expectApiError(gateway.actions.update(target.id, content({ progress: '남의 것 수정' })), 403, FORBIDDEN_EDIT)

    expect(await firstAction(gateway, code)).toEqual(target)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  it('answers 403 before the validation error when another sales sends an empty progress', async () => {
    const { gateway } = await mockAs('park')
    const target = await firstAction(gateway, dealCode(1))

    await expectApiError(gateway.actions.update(target.id, content({ progress: '' })), 403, FORBIDDEN_EDIT)
  })

  it('answers 404 before 403 for an unknown action id even for another sales', async () => {
    const { gateway } = await mockAs('park')

    await expectApiError(gateway.actions.update('act-none', content()), 404, 'Action을 찾을 수 없습니다.')
  })

  it('answers the read-only 403 for the user role before looking for the action', async () => {
    const { gateway } = await mockAs('han')

    await expectApiError(gateway.actions.update('act-none', content()), 403)
  })

  it('lets admin edit the action of another user and logs admin as the changer, keeping the actor', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    const updated = await gateway.actions.update(target.id, content({ progress: '관리자 수정' }))

    expect(updated).toMatchObject({ progress: '관리자 수정', actor: { id: 'u-kim' }, actedAt: target.actedAt })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'action', by: { id: 'u-root' } })
  })

  it('validates in the server order for the owner (progress, Next Action, Due Date)', async () => {
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    await expectApiError(gateway.actions.update(target.id, content({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
    await expectApiError(gateway.actions.update(target.id, content({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
    await expectApiError(gateway.actions.update(target.id, content({ nextAction: ' ', dueDate: '2026-11-01' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
  })
})

describe('Action 삭제 권한 (AC-12, Q8)', () => {
  it('refuses another sales with 403 and the Q8 message, keeping the action and the history', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await gateway.actions.list(code, {})
    const historyBefore = await gateway.history.list(code, {})
    await gateway.auth.quickLogin('u-park')

    await expectApiError(gateway.actions.remove(before[0]?.id ?? ''), 403, FORBIDDEN_DELETE)

    expect(await gateway.actions.list(code, {})).toEqual(before)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  it('answers 404 before 403 for an unknown action id even for another sales', async () => {
    const { gateway } = await mockAs('park')

    await expectApiError(gateway.actions.remove('act-none'), 404, 'Action을 찾을 수 없습니다.')
  })

  it('lets admin delete the action of another user and logs admin as the changer', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    await gateway.actions.remove(target.id)

    expect((await gateway.actions.list(code, {})).some((a) => a.id === target.id)).toBe(false)
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'action', after: '삭제', by: { id: 'u-root' } })
  })

  it('lets the owner sales delete their own action', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)

    await gateway.actions.remove(target.id)

    expect((await gateway.actions.list(code, {})).some((a) => a.id === target.id)).toBe(false)
  })
})

describe('Action 내용 규칙 (AC-02, Q6, R-11)', () => {
  it('registers 5,000 / 5,000 / 20,000 character texts in full (no length check)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const progress = '가'.repeat(5000)
    const nextAction = '나'.repeat(5000)
    const memo = '😀'.repeat(20000)

    const created = await gateway.actions.create(code, input({ progress, nextAction, memo }))

    expect(created).toMatchObject({ progress, nextAction, memo })
    expect((await gateway.actions.list(code, {}))[0]).toMatchObject({ progress, nextAction, memo })
  })

  it('accepts the same long texts on update', async () => {
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    const updated = await gateway.actions.update(target.id, content({ progress: '가'.repeat(5000), nextAction: '나'.repeat(5000), memo: '다'.repeat(20000) }))

    expect(updated.progress).toHaveLength(5000)
    expect(updated.memo).toHaveLength(20000)
  })

  it('trims progress, Next Action and Memo before saving', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.actions.create(dealCode(2), input({ progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

    expect(created).toMatchObject({ progress: '진행', nextAction: '다음', memo: '메모' })
  })

  it('trims on update as well', async () => {
    const { gateway } = await mockAs('kim')
    const target = await firstAction(gateway, dealCode(1))

    const updated = await gateway.actions.update(target.id, content({ progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

    expect(updated).toMatchObject({ progress: '진행', nextAction: '다음', memo: '메모' })
  })

  it('treats a whitespace-only progress and Next Action as missing and checks the deal first (404 before 422)', async () => {
    const { gateway } = await mockAs('kim')
    const blank = input({ progress: ' ', nextAction: '  ', dueDate: '' })

    await expectApiError(gateway.actions.create('20000101-ZZZZ', blank), 404)
    await expectApiError(gateway.actions.create(dealCode(2), blank), 422, '진행사항 또는 Next Action을 입력하세요.')
  })

  it('stores nothing when the validation fails', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const count = (await gateway.actions.list(code, {})).length
    const history = (await gateway.history.list(code, {})).length

    await expectApiError(gateway.actions.create(code, input({ dueDate: '' })), 422, 'Due Date를 입력하세요.')

    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(await gateway.history.list(code, {})).toHaveLength(history)
  })
})

describe('Action 이력 문구 (AC-03·11·12, Q5, R-12)', () => {
  it('logs the registration without a Memo part when the memo is empty', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    await gateway.actions.create(code, input())

    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      category: 'action',
      target: 'Action',
      before: '',
      after: '등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22)',
    })
  })

  it('appends the trimmed Memo to the registration summary', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    await gateway.actions.create(code, input({ memo: ' 법무 의견 ' }))

    expect((await gateway.history.list(code, {}))[0]?.after).toBe(
      '등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 법무 의견',
    )
  })

  it('logs the update with the summary before and the "수정: " summary after, Memo included', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ memo: '이전 메모' }))

    await gateway.actions.update(created.id, content({ type: { name: '통화' }, progress: '전화', nextAction: '방문', dueDate: '2026-11-01', memo: '새 메모' }))

    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      category: 'action',
      before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 이전 메모',
      after: '수정: 통화 · 전화 / Next Action: 방문 (Due 2026-11-01) / Memo: 새 메모',
    })
  })

  it('logs the deletion with the summary before and "삭제" after', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ memo: '메모' }))

    await gateway.actions.remove(created.id)

    expect((await gateway.history.list(code, {}))[0]).toMatchObject({
      before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-10-22) / Memo: 메모',
      after: '삭제',
    })
  })

  it('clips a long registration summary to 1,000 code points ending with an ellipsis, keeping the action text whole', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const progress = '가'.repeat(2000)

    const created = await gateway.actions.create(code, input({ progress }))

    const entry = (await gateway.history.list(code, {}))[0]
    expect(Array.from(entry?.after ?? '')).toHaveLength(1000)
    expect(entry?.after.endsWith('…')).toBe(true)
    expect(entry?.after.startsWith('등록: 미팅 · 가')).toBe(true)
    expect(created.progress).toBe(progress)
  })

  it('clips the before and the after summary of a long update independently', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ progress: '가'.repeat(2000) }))

    await gateway.actions.update(created.id, content({ progress: '나'.repeat(2000) }))

    const entry = (await gateway.history.list(code, {}))[0]
    expect(Array.from(entry?.before ?? '')).toHaveLength(1000)
    expect(Array.from(entry?.after ?? '')).toHaveLength(1000)
    expect(entry?.before.endsWith('…')).toBe(true)
    expect(entry?.after.endsWith('…')).toBe(true)
  })

  it('leaves a summary of 1,000 code points or fewer untouched', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const head = '등록: 미팅 · '
    const tail = ' / Next Action: 견적 재전달 (Due 2026-10-22)'
    const progress = '가'.repeat(1000 - Array.from(head).length - Array.from(tail).length)

    await gateway.actions.create(code, input({ progress }))

    const after = (await gateway.history.list(code, {}))[0]?.after ?? ''
    expect(Array.from(after)).toHaveLength(1000)
    expect(after.endsWith('…')).toBe(false)
  })
})

describe('내용이 바뀌지 않은 수정 (AC-11, Q4)', () => {
  it('writes no history and changes nothing when the content is the same', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})

    const result = await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: target.progress ?? '', nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: target.memo }),
    )

    expect(result).toEqual(target)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  it('treats a change of only the surrounding whitespace as no change', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const historyBefore = await gateway.history.list(code, {})

    await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: `  ${target.progress ?? ''}  `, nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: target.memo }),
    )

    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
  })

  it('still logs one entry when only the memo changes', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const target = await firstAction(gateway, code)
    const base = (await gateway.history.list(code, {})).length

    await gateway.actions.update(
      target.id,
      content({ type: { id: target.typeId }, progress: target.progress ?? '', nextAction: target.nextAction ?? '', dueDate: target.dueDate ?? '', memo: `${target.memo}!` }),
    )

    expect(await gateway.history.list(code, {})).toHaveLength(base + 1)
  })
})

describe('Action 검색 날짜와 범위 (AC-15, Q2, R-14)', () => {
  /** 서버·mock이 같이 쓰는 "업무 날짜"는 실행 환경의 로컬 날짜다. */
  const localDate = (iso: string): string => {
    const d = new Date(iso)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  }
  const nextDay = (day: string): string => {
    const d = new Date(`${day}T12:00:00`)
    d.setDate(d.getDate() + 1)
    return localDate(d.toISOString())
  }

  it('compares the acted date by the local calendar day of the instant, not by the offset text', async () => {
    const mock = await mockAs('kim')
    const code = dealCode(2)
    // -12:00 오프셋의 10-15 20:00 = UTC 10-16 08:00. 문자열의 날짜 부분(10-15)은 어떤 시간대에서도 로컬 날짜와 다르다.
    const at = '2026-10-15T20:00:00-12:00'
    mock.clock.setNow(at)
    const created = await mock.gateway.actions.create(code, input())
    const day = localDate(at)
    expect(day).not.toBe('2026-10-15')

    const found = await mock.gateway.actions.list(code, { actedFrom: day, actedTo: day })
    const wrongDay = await mock.gateway.actions.list(code, { actedFrom: '2026-10-15', actedTo: '2026-10-15' })

    expect(found.map((a) => a.id)).toContain(created.id)
    expect(wrongDay.map((a) => a.id)).not.toContain(created.id)
  })

  it('includes both ends of the acted date range and excludes the neighbours', async () => {
    const mock = await mockAs('kim')
    const code = dealCode(2)
    mock.clock.setNow('2026-10-15T09:00:00+09:00')
    const created = await mock.gateway.actions.create(code, input())
    const day = localDate('2026-10-15T09:00:00+09:00')

    const ids = async (from: string, to: string) => (await mock.gateway.actions.list(code, { actedFrom: from, actedTo: to })).map((a) => a.id)

    expect(await ids(day, day)).toContain(created.id)
    expect(await ids(nextDay(day), nextDay(day))).not.toContain(created.id)
  })

  it('includes both ends of the due date range', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input({ dueDate: '2026-12-24' }))

    const ids = async (from?: string, to?: string) => (await gateway.actions.list(code, { dueFrom: from, dueTo: to })).map((a) => a.id)

    expect(await ids('2026-12-24', '2026-12-24')).toContain(created.id)
    expect(await ids('2026-12-25', undefined)).not.toContain(created.id)
    expect(await ids(undefined, '2026-12-23')).not.toContain(created.id)
  })

  it('rejects a reversed acted date range with the server message', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.actions.list(dealCode(1), { actedFrom: '2026-10-20', actedTo: '2026-10-01' }),
      422,
      '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  it('rejects a reversed due date range with the server message', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.actions.list(dealCode(1), { dueFrom: '2026-10-20', dueTo: '2026-10-01' }),
      422,
      'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  it('accepts a range whose start and end are the same day', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.actions.list(dealCode(1), { dueFrom: '2026-10-20', dueTo: '2026-10-20' })).resolves.toBeDefined()
  })

  it('answers 404 for the list of an unknown deal', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.actions.list('20000101-ZZZZ', {}), 404)
  })
})
