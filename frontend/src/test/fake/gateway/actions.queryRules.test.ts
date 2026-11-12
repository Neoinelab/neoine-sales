import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

/** Fake 게이트웨이 Action 검색의 값 검사(NA-R14·R15·R20): 서버와 같은 422 invalid-value와 판정 순서. */
const UNKNOWN_DEAL = '20000101-ZZZZ'
const NUL_MESSAGE = '검색어에는 NUL 문자를 쓸 수 없습니다'

describe('actions.list: 검색어 NUL', () => {
  // 검색어에 NUL이 있으면 서버와 같은 문구의 422 invalid-value이고 없는 Deal 404보다 먼저 판정한다.
  // 테스트 코드: NA-068, NA-028
  it('rejects a keyword with NUL as a validation error before the unknown deal check', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 검색어 "a\0b"로 목록을 부르면 422 NUL 문구다.
    const error = await expectApiError(gateway.actions.list(dealCode(1), { keyword: 'a\u0000b' }), 422, NUL_MESSAGE)
    expect(error.kind).toBe('validation')
    // when·then: 없는 Deal이어도 404가 아니라 같은 422다.
    await expectApiError(gateway.actions.list(UNKNOWN_DEAL, { keyword: 'a\u0000b' }), 422, NUL_MESSAGE)
  })
})

describe('actions.list: 수행일 1900~2999 범위', () => {
  // 범위 밖 수행일은 서버와 같은 문구의 422 invalid-value다(시작·끝 모두).
  // 테스트 코드: NA-068, NA-032
  it.each(['1899-12-31', '3000-01-01', '0001-01-01', '9999-12-31'])('rejects the acted date %s outside 1900-01-01 ~ 2999-12-31', async (day) => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: acted_from 또는 acted_to로 보내면 각 필드 이름의 422 문구다.
    await expectApiError(
      gateway.actions.list(dealCode(1), { actedFrom: day }),
      422,
      'acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다',
    )
    await expectApiError(
      gateway.actions.list(dealCode(1), { actedTo: day }),
      422,
      'acted_to은(는) 1900-01-01부터 2999-12-31 사이여야 합니다',
    )
  })

  // 허용 범위의 양 끝 날짜는 조회된다.
  // 테스트 코드: NA-068, NA-032
  it.each(['1900-01-01', '2999-12-31'])('accepts the edge acted date %s', async (day) => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 양 끝 날짜로 조회하면 오류 없이 목록이 온다.
    await expect(gateway.actions.list(dealCode(1), { actedFrom: day, actedTo: day })).resolves.toBeInstanceOf(Array)
  })

  // 범위 밖 수행일은 없는 Deal 404보다 먼저 판정한다.
  // 테스트 코드: NA-068
  it('answers 422 before 404 for an out-of-range acted date on an unknown deal', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 없는 Deal에 범위 밖 수행일을 보내면 422다.
    await expectApiError(
      gateway.actions.list(UNKNOWN_DEAL, { actedFrom: '1899-12-31' }),
      422,
      'acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다',
    )
  })

  // Due Date 범위에는 1900~2999 검사가 없다(현행 유지).
  // 테스트 코드: NA-068
  it('does not apply the 1900 ~ 2999 check to the due date range', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 범위 밖 Due Date로 조회해도 오류 없이 빈 목록이다.
    await expect(gateway.actions.list(dealCode(1), { dueFrom: '1899-12-31', dueTo: '3000-01-01' })).resolves.toBeInstanceOf(Array)
  })
})

describe('actions.list: 값 검사 순서 (서버와 같게)', () => {
  // 수행일 범위 오류는 검색어 NUL보다 먼저 판정한다.
  // 테스트 코드: NA-068
  it('reports the acted date range error before the keyword NUL', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: NUL 검색어와 범위 밖 수행일을 함께 보내면 수행일 범위 문구의 422다.
    await expectApiError(
      gateway.actions.list(dealCode(1), { keyword: 'a\u0000b', actedFrom: '1899-12-31' }),
      422,
      'acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다',
    )
  })

  // 형식이 틀린 Deal code는 조건 값 검사(422)보다 먼저 404다.
  // 테스트 코드: NA-068
  it('answers 404 for a malformed deal code before the range validation', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 형식이 틀린 code와 거꾸로 된 수행일 범위를 보내면 404다.
    await expectApiError(
      gateway.actions.list('bad', { actedFrom: '2026-10-20', actedTo: '2026-10-01' }),
      404,
      'Deal을 찾을 수 없습니다.',
    )
  })
})
