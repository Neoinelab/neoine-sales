import { describe, expect, it } from 'vitest'
import { DEAL_CODE_PATTERN, QUICK_LOGIN_USERS } from '../../shared/model/constants'
import { isSyncConsistent } from '../../shared/model/sync'
import { dealCode, expectApiError, mockAs, newMock, TEST_NOW } from './testing'
import { NO_SUCH_ID, USER_ID } from './seed/ids'

async function allDeals(mock: Awaited<ReturnType<typeof mockAs>>) {
  const page = await mock.gateway.deals.list({ limit: 100 })
  return page.items
}

describe('시드 데이터(계획 4.3)', () => {
  it('사용자 7명: 퇴사자 1명(강퇴사), 빠른 로그인 id가 모두 존재한다', async () => {
    const mock = await mockAs('root')
    const users = await mock.gateway.users.list('all')
    expect(users).toHaveLength(7)
    expect(users.filter((u) => u.status === 'resigned').map((u) => u.name)).toEqual(['강퇴사'])
    const ids = users.map((u) => u.id)
    for (const q of QUICK_LOGIN_USERS) expect(ids).toContain(q.userId)
    expect(users.find((u) => u.id === USER_ID.root)?.role).toBe('admin')
    expect(users.find((u) => u.id === USER_ID.han)?.role).toBe('user')
  })

  it('Deal 24건, 모두 code 형식과 Status⇄Forecast 불변식을 지킨다', async () => {
    const mock = await mockAs('kim')
    const items = await allDeals(mock)
    expect(items).toHaveLength(24)
    for (const d of items) {
      expect(d.code).toMatch(DEAL_CODE_PATTERN)
      expect(isSyncConsistent(d)).toBe(true)
    }
    const page = await mock.gateway.deals.list({})
    expect(page.items).toHaveLength(20)
    expect(page.total).toBe(24)
  })

  it('Risk 시나리오: 기한초과(3) 미업데이트(4,14,23) 둘다(7) 오늘이 기한(18)·종결은 없음', async () => {
    const mock = await mockAs('kim')
    const risk = async (no: number) => (await mock.gateway.deals.get(dealCode(no))).risk
    expect(await risk(3)).toBe('overdue')
    expect(await risk(4)).toBe('stale')
    expect(await risk(14)).toBe('stale')
    expect(await risk(23)).toBe('stale')
    expect(await risk(7)).toBe('overdue_stale')
    expect(await risk(18)).toBeNull()
    expect(await risk(1)).toBeNull()
    expect(await risk(11)).toBeNull()
    expect(await risk(16)).toBeNull()
  })

  it('특징 Deal: 종결·퇴사자 Owner·파트너 교체 이력', async () => {
    const mock = await mockAs('kim')
    const d11 = await mock.gateway.deals.get(dealCode(11))
    expect([d11.statusKey, d11.forecastKey]).toEqual(['contract_completed', 'won'])
    const d16 = await mock.gateway.deals.get(dealCode(16))
    expect([d16.statusKey, d16.forecastKey]).toEqual(['price_negotiation', 'lost'])
    const d23 = await mock.gateway.deals.get(dealCode(23))
    expect(d23.owner).toMatchObject({ name: '강퇴사', status: 'resigned' })
    const d17 = await mock.gateway.deals.get(dealCode(17))
    expect(d17.activePartner?.company).toBe('에이원시스템')
    expect(d17.partnerHistory.map((p) => [p.contact.company, p.active])).toEqual([
      ['에이원시스템', true],
      ['코어테크', false],
    ])
    const history = await mock.gateway.history.list(dealCode(17), {})
    expect(history.some((h) => h.category === 'partner' && h.before.includes('코어테크') && h.after.includes('에이원시스템'))).toBe(true)
  })

  it('Action 약 70건, History 약 120건, 첨부 8건 안팎', async () => {
    const mock = await mockAs('kim')
    let actions = 0
    let history = 0
    let attachments = 0
    for (let no = 1; no <= 24; no += 1) {
      actions += (await mock.gateway.actions.list(dealCode(no), {})).length
      history += (await mock.gateway.history.list(dealCode(no), {})).length
      attachments += (await mock.gateway.attachments.list(dealCode(no))).length
    }
    expect(actions).toBeGreaterThanOrEqual(60)
    expect(actions).toBeLessThanOrEqual(80)
    expect(history).toBeGreaterThanOrEqual(100)
    expect(history).toBeLessThanOrEqual(160)
    expect(attachments).toBe(8)
    expect((await mock.gateway.attachments.list(dealCode(1))).map((a) => a.uploadedBy.name).sort()).toEqual(
      ['강퇴사', '김영업', '박영업'].sort(),
    )
  })

  it('연락처: 고객 12사·파트너 5사, 한 회사 3명, 동명이인, 이메일 없음, 공백 없음', async () => {
    const mock = await mockAs('root')
    const gw = mock.gateway
    expect(await gw.contacts.companies('customer')).toHaveLength(12)
    expect(await gw.contacts.companies('partner')).toHaveLength(5)
    expect(await gw.contacts.byCompany('customer', '한빛은행')).toHaveLength(3)
    const nuri = await gw.contacts.byCompany('customer', '누리통신')
    expect(nuri.filter((c) => c.name === '배성훈').map((c) => c.email).sort()).toEqual(['bae1@nuri.test', 'bae2@nuri.test'])
    expect((await gw.contacts.byCompany('customer', '미래전자'))[0]?.email).toBeNull()
    const all = await gw.contacts.list({ limit: 100 })
    expect(all.total).toBe(24)
    for (const c of all.items) expect(`${c.company}${c.name}`).not.toMatch(/\s/)
  })

  it('BANT Label 기본값 23개(Budget 7, Authority 6, Need 5, Timeline 5)와 Status/Forecast 코드', async () => {
    const mock = await mockAs('kim')
    const labels = await mock.gateway.labels.list()
    const count = (c: string) => labels.filter((l) => l.category === c).length
    expect([count('budget'), count('authority'), count('need'), count('timeline')]).toEqual([7, 6, 5, 5])
    expect(labels.every((l) => l.isDefault)).toBe(true)
    const codes = await mock.gateway.codes.all()
    expect(codes.statuses.map((c) => c.key)).toEqual([
      'prospecting', 'introduction', 'poc_preparation', 'poc_completed', 'technical_evaluation', 'price_negotiation', 'contract_completed',
    ])
    expect(codes.forecasts.map((c) => c.key)).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'won', 'lost'])
    expect(codes.statuses.filter((c) => c.locked).map((c) => c.key)).toEqual(['prospecting', 'contract_completed'])
    expect(codes.forecasts.filter((c) => c.locked).map((c) => c.key)).toEqual(['pipeline', 'won', 'lost'])
  })
})

describe('인증', () => {
  it('로그인 전에는 모든 데이터 호출이 401이다', async () => {
    const mock = await mockAs(null)
    await expectApiError(mock.gateway.auth.me(), 401)
    await expectApiError(mock.gateway.deals.list({}), 401)
    await expectApiError(mock.gateway.codes.all(), 401)
  })

  it('로그인 오류 문구', async () => {
    const { auth } = (await mockAs(null)).gateway
    await expectApiError(auth.login('', 'pw'), 422, '아이디와 비밀번호를 입력하세요.')
    await expectApiError(auth.login('kim', ''), 422, '아이디와 비밀번호를 입력하세요.')
    await expectApiError(auth.login('nobody', 'pw'), 401, '아이디 또는 비밀번호가 올바르지 않습니다.')
    await expectApiError(auth.login('old', 'pw'), 403, '퇴사한 사용자는 로그인할 수 없습니다.')
    await expectApiError(auth.quickLogin(USER_ID.old), 403, '퇴사한 사용자는 로그인할 수 없습니다.')
    await expectApiError(auth.quickLogin(NO_SUCH_ID), 401)
  })

  it('아무 비밀번호나 통과하고 me가 사용자를 돌려주며 로그아웃하면 401이다', async () => {
    const { gateway } = await mockAs(null)
    const me = await gateway.auth.login('kim', 'anything')
    expect(me).toEqual({ id: USER_ID.kim, loginId: 'kim', name: '김영업', role: 'sales' })
    expect(await gateway.auth.me()).toEqual(me)
    await gateway.auth.logout()
    await expectApiError(gateway.auth.me(), 401)
  })

  it('로그인하면 lastLoginAt이 시계의 now로 갱신된다', async () => {
    const root = await mockAs('root')
    const users = await root.gateway.users.list('all')
    expect(users.find((u) => u.id === USER_ID.root)?.lastLoginAt).toBe(TEST_NOW)
  })
})

describe('최초 설정(setup)', () => {
  it('시드는 모두 완료 상태이고 restartSetup은 모두 false로 만들고 로그아웃한다', async () => {
    const mock = await mockAs('root')
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: true, storageDone: true, adminDone: true })
    mock.control.restartSetup()
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false })
    await expectApiError(mock.gateway.auth.me(), 401)
  })

  it('T-SETUP 순서 위반은 409, 단계별 검증, 완료하면 관리자로 로그인된다', async () => {
    const mock = newMock()
    const { setup, auth, settings } = mock.gateway
    mock.control.restartSetup()
    await expectApiError(setup.saveStorage('/data/files'), 409)
    await expectApiError(setup.registerAdmin('root', 'pw'), 409)
    const input = {
      serverUrls: ['ldaps://dc1.corp.test'], useStarttls: false, caCertPem: null, bindTemplate: 'CORP\\{login_id}',
      baseDn: 'dc=corp,dc=test', userFilter: '(sAMAccountName={login_id})', displayNameAttribute: 'displayName',
      emailAttribute: 'mail', connectTimeoutSeconds: 5, receiveTimeoutSeconds: 10,
    }
    await setup.saveDirectory(input)
    expect((await setup.status()).directoryDone).toBe(true)
    await expectApiError(setup.saveStorage('relative/path'), 422, '절대 경로를 입력하세요.')
    await expectApiError(setup.saveStorage('/readonly/files'), 422, '해당 위치에 쓸 수 없습니다.')
    await setup.saveStorage('/data/neoine/files')
    await expectApiError(setup.registerAdmin('', 'pw'), 422)
    const me = await setup.registerAdmin('root', 'pw')
    expect(me.role).toBe('admin')
    expect(await auth.me()).toEqual(me)
    expect(await setup.status()).toEqual({ directoryDone: true, storageDone: true, adminDone: true })
    await expectApiError(setup.registerAdmin('root', 'pw'), 409)
    expect((await settings.getStorage())?.path).toBe('/data/neoine/files')
  })
})

describe('T-MOCK 초기화·격리·시계', () => {
  it('T-MOCK-01 resetData는 변경을 시드로 되돌리고 로그인은 유지한다', async () => {
    const mock = await mockAs('root')
    const { gateway, control } = mock
    await gateway.deals.remove(dealCode(11), dealCode(11))
    await gateway.labels.create('budget', '새 라벨')
    expect(await allDeals(mock)).toHaveLength(23)
    control.resetData()
    expect(await allDeals(mock)).toHaveLength(24)
    expect((await gateway.labels.list()).some((l) => l.name === '새 라벨')).toBe(false)
    expect((await gateway.auth.me()).id).toBe(USER_ID.root)
  })

  it('T-MOCK-02 서로 다른 인스턴스는 상태를 공유하지 않는다', async () => {
    const a = await mockAs('root')
    const b = await mockAs('root')
    await a.gateway.deals.remove(dealCode(12), dealCode(12))
    expect(await allDeals(a)).toHaveLength(23)
    expect(await allDeals(b)).toHaveLength(24)
  })

  it('T-MOCK-03 고정 시계: 변경 시각은 항상 now이고 advance로만 흐른다', async () => {
    const mock = await mockAs('kim')
    expect(mock.clock.now()).toBe(TEST_NOW)
    expect(mock.clock.today()).toBe('2026-10-15')
    await mock.gateway.actions.create(dealCode(2), { type: { name: '통화' }, progress: '확인', nextAction: '회신', dueDate: '2026-10-20', memo: '' })
    const first = (await mock.gateway.history.list(dealCode(2), {}))[0]
    expect(first?.at).toBe(TEST_NOW)
    mock.clock.advance(60 * 60 * 1000)
    expect(mock.clock.now()).toBe('2026-10-15T10:00:00+09:00')
  })

  it('저장소 장애·지연 플래그는 제어 객체로 켜고 끈다', () => {
    const { control } = newMock()
    expect(control.isStorageFailure()).toBe(false)
    control.setStorageFailure(true)
    expect(control.isStorageFailure()).toBe(true)
    control.setLatency(false)
    expect(control.isLatencyOn()).toBe(false) // 토글 표시만 바뀐다(latency:false이면 실제 지연은 항상 0ms)
    control.setLatency(true)
    expect(control.isLatencyOn()).toBe(true)
  })
})
