import { describe, expect, it } from 'vitest'
import { dealInput } from './testing'
import { createClock } from './clock'
import { createMockGateway } from './index'
import { emptyBusinessSeed } from './seed'
import { USER_ID } from './seed/ids'

const NOW = '2026-10-15T09:00:00+09:00'

/** 테스트 도우미(`newMock`)를 거치지 않은 "앱 기본" 게이트웨이(시드 옵션 없음). */
async function appDefault() {
  const mock = createMockGateway({ now: NOW, latency: false })
  await mock.signInAs(USER_ID.root)
  return mock
}

describe('앱 기본 시드에는 샘플 업무 데이터가 없다', () => {
  it('기본 시드에는 Deal·연락처·Action·이력·첨부가 없다', () => {
    // when: 기본 업무 시드를 만든다
    const data = emptyBusinessSeed(createClock(NOW))
    // then: 업무 데이터 배열이 모두 비어 있다
    expect(data.deals).toEqual([])
    expect(data.contacts).toEqual([])
    expect(data.actions).toEqual([])
    expect(data.history).toEqual([])
    expect(data.attachments).toEqual([])
  })

  it('기본 인스턴스의 게이트웨이로는 아무것도 조회되지 않는다', async () => {
    // given: 앱 기본 게이트웨이
    const { gateway } = await appDefault()

    // when: Deal·연락처·회사 목록을 조회한다
    const deals = await gateway.deals.list({ limit: 100 })
    const contacts = await gateway.contacts.list({ limit: 100 })
    // then: 모두 비어 있다
    expect(deals.items).toEqual([])
    expect(deals.total).toBe(0)
    expect(contacts.items).toEqual([])
    expect(await gateway.contacts.companies('customer')).toEqual([])
    expect(await gateway.contacts.companies('partner')).toEqual([])
  })

  it('기본 코드·BANT Label·로그인 계정은 남아 있다', async () => {
    // given: 앱 기본 게이트웨이
    const { gateway } = await appDefault()

    // when: 코드·Label·사용자 목록을 읽는다
    const codes = await gateway.codes.all()
    const labels = await gateway.labels.list()
    const users = await gateway.users.list('all')
    // then: Status 7개·Forecast 6개, Label이 있고 기본 로그인 계정이 있다
    expect(codes.statuses).toHaveLength(7)
    expect(codes.forecasts).toHaveLength(6)
    expect(labels.length).toBeGreaterThan(0)
    expect(users.map((u) => u.loginId)).toEqual(expect.arrayContaining(['root', 'kim', 'park', 'han', 'old']))
  })

  it('업무 데이터가 없어도 기본 Action 유형 8개는 남아 있다', async () => {
    // given: 앱 기본 게이트웨이
    const { gateway } = await appDefault()

    // when: Action 유형 이름 목록을 읽는다
    const names = (await gateway.actionTypes.list()).map((t) => t.name)

    // then: 기본 8개가 순서대로 있다
    expect(names).toEqual(['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'])
  })

  it('데이터를 초기화하면 만든 Action 유형이 사라진다', async () => {
    // given: Action 유형 '웨비나'를 만든 게이트웨이
    const { gateway, control } = await appDefault()
    await gateway.actionTypes.create('웨비나')
    // when: 데이터를 초기화한다
    control.resetData()
    // then: 만든 유형이 목록에 없다
    expect((await gateway.actionTypes.list()).some((t) => t.name === '웨비나')).toBe(false)
  })

  it('Deal을 만든 뒤 데이터를 초기화하면 빈 업무 데이터로 돌아간다', async () => {
    // given: Deal 하나를 만든 게이트웨이
    const { gateway, control } = await appDefault()
    await gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null }))

    // when: 초기화 전에 Deal 목록을 읽는다
    const before = await gateway.deals.list({ limit: 100 })
    // then: Deal이 1건이다
    expect(before.total).toBe(1)

    // when: 데이터를 초기화한다
    control.resetData()
    // then: Deal이 0건이고 고객 회사 목록도 비어 있다
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(0)
    expect(await gateway.contacts.companies('customer')).toEqual([])
  })
})
