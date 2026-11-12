import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

/** Action 목록의 오류 순서와 keyword 길이 한도를 서버에 맞춘 Fake의 규칙. */
const UNKNOWN_DEAL = '20000101-ZZZZ'
const REQUEST_INVALID = '요청 형식이 올바르지 않습니다'

describe('actions.list: 오류 순서 (쿼리 검증 422 → 없는 Deal 404)', () => {
  // 올바른 조건이어도 없는 Deal은 404다.
  // 테스트 코드: NA-068, NA-021
  it('answers 404 for an unknown deal with a valid query', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal의 목록을 부르면 404 "Deal을 찾을 수 없습니다."다.
    await expectApiError(gateway.actions.list(UNKNOWN_DEAL, {}), 404, 'Deal을 찾을 수 없습니다.')
  })

  // 없는 Deal이어도 거꾸로 된 수행일 범위는 404보다 먼저 422다.
  // 테스트 코드: NA-068
  it('answers 422 before 404 for a reversed acted range on an unknown deal', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal에 거꾸로 된 수행일 범위를 보내면 422 수행일 범위 문구다.
    await expectApiError(
      gateway.actions.list(UNKNOWN_DEAL, { actedFrom: '2026-10-20', actedTo: '2026-10-01' }),
      422,
      '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  // 없는 Deal이어도 거꾸로 된 Due Date 범위는 404보다 먼저 422다.
  // 테스트 코드: NA-068
  it('answers 422 before 404 for a reversed due range on an unknown deal', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal에 거꾸로 된 Due Date 범위를 보내면 422 Due Date 범위 문구다.
    await expectApiError(
      gateway.actions.list(UNKNOWN_DEAL, { dueFrom: '2026-10-20', dueTo: '2026-10-01' }),
      422,
      'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.',
    )
  })

  // 없는 Deal이어도 101자 검색어는 404보다 먼저 422다.
  // 테스트 코드: NA-068
  it('answers 422 before 404 for a too long keyword on an unknown deal', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal에 101자 검색어를 보내면 422 request-validation 문구다.
    await expectApiError(gateway.actions.list(UNKNOWN_DEAL, { keyword: 'k'.repeat(101) }), 422, REQUEST_INVALID)
  })
})

describe('actions.list: keyword 길이 (서버 스키마 max_length=100, 코드 포인트)', () => {
  // 100자 검색어는 받아들인다.
  // 테스트 코드: NA-068, NA-028
  it('accepts a 100 character keyword', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 100자 검색어로 목록을 부르면 오류 없이 빈 목록이다.
    await expect(gateway.actions.list(dealCode(1), { keyword: 'k'.repeat(100) })).resolves.toEqual([])
  })

  // 101자 검색어는 request-validation 문구의 422로 거절한다.
  // 테스트 코드: NA-068, NA-028
  it('rejects a 101 character keyword with the request-validation message', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when: 101자 검색어로 목록을 부른다.
    const error = await expectApiError(gateway.actions.list(dealCode(1), { keyword: 'k'.repeat(101) }), 422, REQUEST_INVALID)

    // then: validation 종류의 422다.
    expect(error.kind).toBe('validation')
  })

  // 이모지는 한 글자로 센다(코드 포인트 기준).
  // 테스트 코드: NA-068, NA-028
  it('counts an emoji as one character', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: 이모지 100개는 받아들인다.
    await expect(gateway.actions.list(dealCode(1), { keyword: '😀'.repeat(100) })).resolves.toEqual([])
    // when·then: 이모지 101개는 422로 거절한다.
    await expectApiError(gateway.actions.list(dealCode(1), { keyword: '😀'.repeat(101) }), 422, REQUEST_INVALID)
  })

  // 일반 검색어로는 Action을 찾는다.
  // 테스트 코드: NA-068
  it('still finds actions by an ordinary keyword', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')

    // when·then: "ROI"로 목록을 부르면 한 건 이상 나온다.
    expect((await gateway.actions.list(dealCode(1), { keyword: 'ROI' })).length).toBeGreaterThan(0)
  })
})
