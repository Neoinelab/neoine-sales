import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

/** P2 이월 Q6(b)(c): Action 목록의 오류 순서와 keyword 길이 한도를 서버에 맞춘다. */
const UNKNOWN_DEAL = '20000101-ZZZZ'
const REQUEST_INVALID = '요청 형식이 올바르지 않습니다'

describe('actions.list: 오류 순서 (쿼리 검증 422 → 없는 Deal 404)', () => {
  it('answers 404 for an unknown deal with a valid query', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.actions.list(UNKNOWN_DEAL, {}), 404, 'Deal을 찾을 수 없습니다.')
  })

  it('answers 422 before 404 for a reversed acted range on an unknown deal', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.actions.list(UNKNOWN_DEAL, { actedFrom: '2026-10-20', actedTo: '2026-10-01' }),
      422,
      '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  it('answers 422 before 404 for a reversed due range on an unknown deal', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.actions.list(UNKNOWN_DEAL, { dueFrom: '2026-10-20', dueTo: '2026-10-01' }),
      422,
      'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  it('answers 422 before 404 for a too long keyword on an unknown deal', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.actions.list(UNKNOWN_DEAL, { keyword: 'k'.repeat(101) }), 422, REQUEST_INVALID)
  })
})

describe('actions.list: keyword 길이 (서버 스키마 max_length=100, 코드 포인트)', () => {
  it('accepts a 100 character keyword', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.actions.list(dealCode(1), { keyword: 'k'.repeat(100) })).resolves.toEqual([])
  })

  it('rejects a 101 character keyword with the request-validation message', async () => {
    const { gateway } = await mockAs('kim')

    const error = await expectApiError(gateway.actions.list(dealCode(1), { keyword: 'k'.repeat(101) }), 422, REQUEST_INVALID)

    expect(error.kind).toBe('validation')
  })

  it('counts an emoji as one character', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.actions.list(dealCode(1), { keyword: '😀'.repeat(100) })).resolves.toEqual([])
    await expectApiError(gateway.actions.list(dealCode(1), { keyword: '😀'.repeat(101) }), 422, REQUEST_INVALID)
  })

  it('still finds actions by an ordinary keyword', async () => {
    const { gateway } = await mockAs('kim')

    expect((await gateway.actions.list(dealCode(1), { keyword: 'ROI' })).length).toBeGreaterThan(0)
  })
})
