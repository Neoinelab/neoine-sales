/** P0 R3: 서버 계약과 맞춘 mock 동작(계약 변경분). */

import { describe, expect, it } from 'vitest'
import { LOCKED_KEYS } from '../../../shared/model/constants'
import { expectApiError, mockAs } from '../testing'
import { BIND_PASSWORD } from '../../directoryFixtures'

describe('auth.config', () => {
  it('mock은 설정이 끝난 시스템의 인증 방식만 알려 준다(빠른 로그인 항목 없음)', async () => {
    // given: 로그인하지 않은 mock
    const { gateway } = await mockAs(null)

    // when: 인증 설정을 조회한다
    const result = await gateway.auth.config()

    // then: needsSetup이 false이고 authMode가 ad다
    expect(result).toEqual({ needsSetup: false, authMode: 'ad' })
  })

  it('mock은 최초 설정이 끝나지 않았으면 needsSetup을 켠다', async () => {
    // given: 최초 설정을 다시 시작한 mock
    const { gateway, control } = await mockAs(null)
    control.restartSetup()
    // restartSetup은 로그아웃도 하므로 config는 로그인 전에도 읽힌다

    // when: 인증 설정을 조회한다 (restartSetup은 로그아웃도 하므로 로그인 전에도 읽힌다)
    const result = await gateway.auth.config()

    // then: needsSetup이 true이고 authMode가 null이다
    expect(result).toEqual({ needsSetup: true, authMode: null })
  })
})

describe('잠긴 코드 5개', () => {
  it('잠긴 코드 key 집합이 서버와 같다', () => {
    // when·then: 잠긴 key 상수가 서버와 같은 Status·Forecast 집합이다
    expect(LOCKED_KEYS).toEqual({
      status: ['prospecting', 'contract_completed'],
      forecast: ['pipeline', 'won', 'lost'],
    })
  })

  it('시드에서 정확히 이 5개만 locked다', async () => {
    // given: 관리자로 로그인해 전체 코드를 읽었다
    const { gateway } = await mockAs('root')
    const all = await gateway.codes.all()

    // when: 시드 코드 중 locked인 것을 모은다
    const locked = [...all.statuses, ...all.forecasts].filter((c) => c.locked).map((c) => `${c.kind}:${c.key}`)

    // then: locked 코드가 이 다섯 개뿐이다
    expect(locked.sort()).toEqual(['forecast:lost', 'forecast:pipeline', 'forecast:won', 'status:contract_completed', 'status:prospecting'])
  })

  it.each([
    ['status', 'prospecting'],
    ['forecast', 'pipeline'],
    ['forecast', 'lost'],
  ] as const)('%s %s 삭제는 409(시스템 연결)', async (kind, key) => {
    // given: 관리자로 로그인한 mock과 시스템에 연결된 코드
    const { gateway } = await mockAs('root')
    const code = (await gateway.codes.list(kind)).find((c) => c.key === key)
    if (!code) throw new Error(key)

    // when·then: 그 코드를 삭제하면 시스템 연결 문구와 함께 409다
    await expectApiError(gateway.codes.remove(code.id), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
  })
})

describe('코드 key 생성', () => {
  it.each([
    ['2nd', 'c_2nd'],
    ['Most Likely 2', 'most_likely_2'],
    ['보류', 'code_1'],
  ])('이름 "%s"의 key는 %s', async (name, key) => {
    // given: 관리자로 로그인한 mock
    const { gateway } = await mockAs('root')

    // when: 코드를 만든다
    const created = await gateway.codes.create({ kind: 'status', name })

    // then: key가 규칙대로 만들어진다
    expect(created.key).toBe(key)
  })

  it('같은 key가 이미 있으면 _2를 붙인다', async () => {
    // given: 관리자로 로그인한 mock
    const { gateway } = await mockAs('root')

    // when: 이미 있는 key가 되는 이름으로 코드를 만든다
    const created = await gateway.codes.create({ kind: 'forecast', name: 'best!' })

    // then: key가 best_2다
    expect(created.key).toBe('best_2')
  })
})

describe('contacts.list는 admin 전용', () => {
  it.each(['kim', 'han'] as const)('%s는 403이다', async (key) => {
    // given: 영업 또는 조회자로 로그인한 mock
    const { gateway } = await mockAs(key)

    // when·then: 연락처 목록을 조회하면 403이다
    await expectApiError(gateway.contacts.list({}), 403)
  })

  it('companies·byCompany는 모든 역할이 쓴다', async () => {
    // given: 조회자로 로그인한 mock
    const { gateway } = await mockAs('han')

    // when: 조회자가 고객 회사 목록과 회사별 연락처를 조회한다
    const result1 = (await gateway.contacts.companies('customer')).length
    const result2 = (await gateway.contacts.byCompany('customer', '한빛은행')).length

    // then: 둘 다 한 건 이상이다
    expect(result1).toBeGreaterThan(0)
    expect(result2).toBeGreaterThan(0)
  })
})

describe('AD 설정 저장·테스트 인자', () => {
  const input = { host: 'dc1.corp.test', port: 636, security: 'ssl' as const, bindAccount: 'CORP\\svc-sales', bindPassword: BIND_PASSWORD, userFilter: '(sAMAccountName={login_id})', connectTimeoutSeconds: 5 }

  it('saveDirectory는 비밀번호와 expectedRevision을 받기만 하고 revision을 올린다', async () => {
    // given: 관리자로 로그인한 mock과 현재 AD 설정
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()

    // when: 비밀번호와 expectedRevision을 넘겨 저장한다
    const saved = await gateway.settings.saveDirectory({ ...input, ...await gateway.settings.testDirectory(input) }, { expectedRevision: before?.revision ?? 1 })

    // then: revision이 1 오른다
    expect(saved.revision).toBe((before?.revision ?? 0) + 1)
  })

  it('testDirectory는 비밀번호를 받는다', async () => {
    // given: 관리자로 로그인한 mock
    const { gateway } = await mockAs('root')

    // when: 비밀번호와 함께 테스트한다
    const result = await gateway.settings.testDirectory(input)

    // then: baseDn이 돌아온다
    expect(result).toEqual({ baseDn: expect.any(String), testToken: expect.any(String) })

    // when·then: 실패하는 호스트로 테스트하면 422다
    await expectApiError(gateway.settings.testDirectory({ ...input, host: 'fail.test' }), 422)
  })
})
