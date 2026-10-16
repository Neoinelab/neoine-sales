/** P0 R3: 서버 계약과 맞춘 mock 동작(AC-28 계약 변경분). */

import { describe, expect, it } from 'vitest'
import { LOCKED_KEYS, QUICK_LOGIN_USERS } from '../../shared/model/constants'
import { expectApiError, mockAs } from '../testing'

describe('빠른 로그인 사용자', () => {
  it('역할을 함께 가진다(서버 dev-login은 역할로 로그인한다)', () => {
    expect(QUICK_LOGIN_USERS.map((u) => [u.userId, u.role])).toEqual([
      ['u-root', 'admin'],
      ['u-kim', 'sales'],
      ['u-park', 'sales'],
      ['u-han', 'user'],
    ])
  })
})

describe('auth.config', () => {
  it('mock은 빠른 로그인을 켠다', async () => {
    const { gateway } = await mockAs(null)

    expect(await gateway.auth.config()).toEqual({ quickLogin: true, needsSetup: false })
  })

  it('mock은 최초 설정이 끝나지 않았으면 needsSetup을 켠다', async () => {
    const { gateway, control } = await mockAs(null)
    control.restartSetup()
    // restartSetup은 로그아웃도 하므로 config는 로그인 전에도 읽힌다

    expect(await gateway.auth.config()).toEqual({ quickLogin: true, needsSetup: true })
  })
})

describe('잠긴 코드 5개', () => {
  it('서버와 같은 key 집합이다', () => {
    expect(LOCKED_KEYS).toEqual({
      status: ['prospecting', 'contract_completed'],
      forecast: ['pipeline', 'won', 'lost'],
    })
  })

  it('시드에서 정확히 이 5개만 locked다', async () => {
    const { gateway } = await mockAs('root')
    const all = await gateway.codes.all()

    const locked = [...all.statuses, ...all.forecasts].filter((c) => c.locked).map((c) => `${c.kind}:${c.key}`)

    expect(locked.sort()).toEqual(['forecast:lost', 'forecast:pipeline', 'forecast:won', 'status:contract_completed', 'status:prospecting'])
  })

  it.each([
    ['status', 'prospecting'],
    ['forecast', 'pipeline'],
    ['forecast', 'lost'],
  ] as const)('%s %s 삭제는 409(시스템 연결)', async (kind, key) => {
    const { gateway } = await mockAs('root')
    const code = (await gateway.codes.list(kind)).find((c) => c.key === key)
    if (!code) throw new Error(key)

    await expectApiError(gateway.codes.remove(code.id), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
  })
})

describe('코드 key 생성', () => {
  it.each([
    ['2nd', 'c_2nd'],
    ['Most Likely 2', 'most_likely_2'],
    ['보류', 'code_1'],
  ])('이름 "%s"의 key는 %s', async (name, key) => {
    const { gateway } = await mockAs('root')

    const created = await gateway.codes.create({ kind: 'status', name })

    expect(created.key).toBe(key)
  })

  it('같은 key가 이미 있으면 _2를 붙인다', async () => {
    const { gateway } = await mockAs('root')

    const created = await gateway.codes.create({ kind: 'forecast', name: 'best!' })

    expect(created.key).toBe('best_2')
  })
})

describe('contacts.list는 admin 전용', () => {
  it.each(['kim', 'han'] as const)('%s는 403', async (key) => {
    const { gateway } = await mockAs(key)

    await expectApiError(gateway.contacts.list({}), 403)
  })

  it('companies·byCompany는 모든 역할이 쓴다', async () => {
    const { gateway } = await mockAs('han')

    expect((await gateway.contacts.companies('customer')).length).toBeGreaterThan(0)
    expect((await gateway.contacts.byCompany('customer', '한빛은행')).length).toBeGreaterThan(0)
  })
})

describe('AD 설정 저장·테스트 인자', () => {
  const input = {
    serverUrls: ['ldaps://dc.corp.test'],
    useStarttls: false,
    caCertPem: null,
    bindTemplate: 'CORP\\{login_id}',
    baseDn: 'dc=corp,dc=test',
    userFilter: '(x)',
    displayNameAttribute: 'displayName',
    emailAttribute: 'mail',
    connectTimeoutSeconds: 5,
    receiveTimeoutSeconds: 10,
  }

  it('saveDirectory는 비밀번호와 expectedRevision을 받기만 하고 revision을 올린다', async () => {
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()

    const saved = await gateway.settings.saveDirectory(input, { password: 'pw', expectedRevision: before?.revision ?? 1 })

    expect(saved.revision).toBe((before?.revision ?? 0) + 1)
  })

  it('testDirectory는 비밀번호를 받는다', async () => {
    const { gateway } = await mockAs('root')

    await expect(gateway.settings.testDirectory(input, 'pw')).resolves.toBeUndefined()
    await expectApiError(gateway.settings.testDirectory({ ...input, serverUrls: ['ldaps://fail.test'] }, null), 422)
  })
})
