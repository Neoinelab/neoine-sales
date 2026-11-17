import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { dealCode, expectApiError, mockAs } from '../testing'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  comment: '',
  ...over,
})

const REQUEST_FORMAT = '요청 형식이 올바르지 않습니다'

describe('Fake actions: 서버와 같은 NUL·날짜 형식 규칙(AC-R33)', () => {
  const nulCases = [
    ['진행사항', { progress: '가\0나' }],
    ['Next Action', { nextAction: '가\0나' }],
  ] as const
  const createOnly = [...nulCases, ['Comment', { comment: '가\0나' }]] as const

  // 진행사항·Next Action·등록 Comment의 NUL은 칸 이름이 든 422로 거절한다(등록).
  // 테스트 코드: AC-090, CM-082
  it.each(createOnly)('등록: %s에 NUL이 있으면 422 NUL 문구이고 Action이 늘지 않는다', async (label, over) => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이와 등록 전 Action 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = (await gateway.actions.list(code, {})).length
    // when·then: 한 칸에 NUL을 넣어 등록하면 그 칸 이름이 든 422다
    await expectApiError(gateway.actions.create(code, input(over)), 422, `${label}에는 NUL 문자를 쓸 수 없습니다`)
    // then: Action이 늘지 않는다
    expect(await gateway.actions.list(code, {})).toHaveLength(before)
  })

  // 진행사항·Next Action의 NUL은 칸 이름이 든 422로 거절한다(수정).
  // 테스트 코드: AC-090
  it.each(nulCases)('수정: %s에 NUL이 있으면 422 NUL 문구이고 Action은 그대로다', async (label, over) => {
    // given: 담당자 본인(kim)과 가장 오래된 Action
    const { gateway } = await mockAs('kim')
    const old = (await gateway.actions.list(dealCode(1), {})).at(-1)
    if (!old) throw new Error('no action')
    // when·then: 한 칸에 NUL을 넣어 수정하면 그 칸 이름이 든 422다
    await expectApiError(gateway.actions.update(old.id, input(over)), 422, `${label}에는 NUL 문자를 쓸 수 없습니다`)
    // then: Action은 그대로다
    expect((await gateway.actions.list(dealCode(1), {})).at(-1)).toEqual(old)
  })

  // 진행사항·Next Action의 NUL 검사는 둘 다 빔 검사보다 먼저이고, 등록 Comment의 NUL은 내용 오류 다음에 판정한다.
  // 테스트 코드: AC-090, CM-082
  it('NUL은 진행사항·Next Action이 모두 비어 있다는 오류보다 먼저 알리고 Comment NUL은 그 다음이다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when·then: 진행사항에 NUL이 있고 Next Action이 비면 NUL 문구다
    await expectApiError(
      gateway.actions.create(dealCode(2), input({ progress: '가\0나', nextAction: '', dueDate: '' })),
      422,
      '진행사항에는 NUL 문자를 쓸 수 없습니다',
    )
    // when·then: 진행사항·Next Action이 비고 Comment에 NUL이 있으면 내용 오류가 먼저다
    await expectApiError(
      gateway.actions.create(dealCode(2), input({ progress: '', nextAction: '', dueDate: '', comment: '가\0나' })),
      422,
      '진행사항 또는 Next Action을 입력하세요.',
    )
  })

  // 달력에 없는 Due Date는 입력 칸 안내가 아니라 요청 형식 오류(422)다.
  // 테스트 코드: AC-090
  it.each(['2027-13-01', '2027-02-31', '내일', '20270115', '2027-1-5'])(
    '등록·수정: 달력 날짜가 아닌 Due Date %s는 422 요청 형식 오류이고 아무것도 바뀌지 않는다',
    async (due) => {
      // given: 담당자 본인(kim)과 등록 전 Action 건수
      const { gateway } = await mockAs('kim')
      const code = dealCode(1)
      const list = await gateway.actions.list(code, {})
      const old = list.at(-1)
      if (!old) throw new Error('no action')
      // when·then: 등록하면 요청 형식 422다
      await expectApiError(gateway.actions.create(code, input({ dueDate: due })), 422, REQUEST_FORMAT)
      // when·then: 수정해도 요청 형식 422다
      await expectApiError(gateway.actions.update(old.id, input({ dueDate: due })), 422, REQUEST_FORMAT)
      // then: Action이 늘지도 바뀌지도 않는다
      expect(await gateway.actions.list(code, {})).toEqual(list)
    },
  )

  // 요청 형식 오류는 없는 Deal 404보다 먼저이고, 진행사항이 비어 있어도 Due Date 형식이 먼저다.
  // 테스트 코드: AC-090
  it('요청 형식 오류는 없는 Deal·내용 오류보다 먼저 판정된다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when·then: 없는 Deal에 달력에 없는 Due를 주면 404가 아니라 요청 형식 422다
    await expectApiError(gateway.actions.create('20000101-ZZZZ', input({ dueDate: '2027-13-01' })), 422, REQUEST_FORMAT)
    // when·then: 내용이 비어 있어도 달력에 없는 Due면 요청 형식 422다
    await expectApiError(
      gateway.actions.create(dealCode(2), input({ progress: '', nextAction: '', dueDate: '2027-13-01' })),
      422,
      REQUEST_FORMAT,
    )
  })

  // 달력에 있는 날짜(윤일 포함)는 받는다.
  it('달력에 있는 Due Date는 윤일도 받는다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when: 윤일 Due로 등록한다
    const created = await gateway.actions.create(dealCode(2), input({ dueDate: '2028-02-29' }))
    // then: 그대로 저장된다
    expect(created.dueDate).toBe('2028-02-29')
  })

  // 검색어 NUL과 1900~2999 밖의 수행일은 조건 값 오류(422)다. Due Date 범위는 이 검사를 하지 않는다.
  it('검색: 검색어 NUL과 범위 밖 수행일은 422이고 Due 범위는 검사하지 않는다', async () => {
    // given: sales(kim)로 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // when·then: 검색어에 NUL이 있으면 422다
    await expectApiError(gateway.actions.list(code, { keyword: '가\0나' }), 422, '검색어에는 NUL 문자를 쓸 수 없습니다')
    // when·then: 1899-12-31, 3000-01-01 수행일은 범위 문구의 422다
    await expectApiError(gateway.actions.list(code, { actedFrom: '1899-12-31' }), 422, 'acted_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다')
    await expectApiError(gateway.actions.list(code, { actedTo: '3000-01-01' }), 422, 'acted_to은(는) 1900-01-01부터 2999-12-31 사이여야 합니다')
    // when: 양 끝 날짜와 범위 밖 Due Date로 조회한다
    const edge = await gateway.actions.list(code, { actedFrom: '1900-01-01', actedTo: '2999-12-31', dueFrom: '1000-01-01', dueTo: '9999-12-31' })
    // then: 오류 없이 조회된다
    expect(edge.length).toBeGreaterThan(0)
  })
})
