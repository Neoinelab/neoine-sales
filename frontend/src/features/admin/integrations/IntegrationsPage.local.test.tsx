import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderLocalAt } from '../../../test/localAccounts'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 앱에서 계정을 직접 관리하는 시스템의 외부연동: AD 설정 대신 안내를 보인다. */
describe('외부연동: local 모드', () => {
  // 테스트 코드: IN-077
  it('AD 설정 섹션 대신 로그인 방식 안내 카드를 보인다', async () => {
    // when: admin이 외부연동 화면을 연다 (전제: 인증 방식이 local이다)
    await renderLocalAt('/admin/integrations', { role: 'admin' })

    // then: "로그인 방식" 안내가 보이고 AD 섹션과 호스트 칸은 없다
    expect(await screen.findByRole('heading', { name: '로그인 방식' })).toBeInTheDocument()
    expect(screen.getByText('이 시스템은 앱에서 계정을 직접 관리합니다. AD(LDAP) 서버 설정은 사용하지 않습니다.')).toBeInTheDocument()
    expect(screen.getByText('계정과 비밀번호는 사용자 관리에서 만들고 고칩니다.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AD(LDAP) 서버 설정' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^호스트/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-077
  it('AD 설정을 서버에 요청하지 않는다', async () => {
    // given: 인증 방식이 local이고 AD 설정 조회를 지켜본다
    const read = vi.spyOn(gateway.settings, 'getDirectory')

    // when: 외부연동 화면을 연다
    await renderLocalAt('/admin/integrations', { role: 'admin' })
    await screen.findByText(/앱에서 계정을 직접 관리합니다/)

    // then: AD 설정 조회 요청이 없었다(요청이 없다는 것 자체가 결과다)
    expect(read).not.toHaveBeenCalled()
    expect(screen.queryByLabelText(/^호스트/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-077
  it('파일 저장 위치 섹션은 그대로 보인다', async () => {
    // when: 외부연동 화면을 연다 (전제: 인증 방식이 local이다)
    await renderLocalAt('/admin/integrations', { role: 'admin' })

    // then: 저장 위치 섹션과 경로 칸이 보인다
    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(await screen.findByLabelText('저장 경로')).toBeInTheDocument()
  })

  // 테스트 코드: IN-077
  it('AD 모드에서는 안내 카드가 없고 AD 섹션이 보인다', async () => {
    // when: 외부연동 화면을 연다 (전제: 인증 방식이 AD다)
    await renderAt('/admin/integrations', { role: 'admin' })

    // then: AD 섹션이 보이고 local 안내는 없다
    expect(await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })).toBeInTheDocument()
    expect(screen.queryByText(/앱에서 계정을 직접 관리합니다/)).not.toBeInTheDocument()
  })
})
