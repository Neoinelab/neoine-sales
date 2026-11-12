import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
})

/** renderAt이 데이터를 초기화하므로, 초기화 뒤에 최초 설정이 안 된 상태로 되돌린다. */
function needSetup() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
}

describe('로그인 화면의 서버 설정 반영', () => {
  // 빠른 로그인 영역과 역할 버튼, 최초 설정 링크 없이 아이디·비밀번호 폼만 보인다.
  // 테스트 코드: AU-067
  it('shows no quick login area, only the id and password form', async () => {
    // when: 로그인하지 않은 채 로그인 화면을 연다
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    // then: 빠른 로그인·역할 버튼·최초 설정 링크는 없고 아이디 칸은 보인다
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '관리자' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '조회자' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('아이디')).toBeVisible()
    expect(screen.queryByRole('link', { name: /최초 설정/ })).not.toBeInTheDocument()
  })

  // 서버가 최초 설정을 요구하면 로그인 화면 대신 항상 최초 설정 화면으로 보낸다.
  it('서버가 최초 설정을 요구하면 로그인 화면이 최초 설정으로 이동한다', async () => {
    // given: 최초 설정이 안 된 서버
    needSetup()
    // when: 로그인하지 않은 채 로그인 화면을 연다
    const { location } = await renderAt('/login', { role: null })

    // then: /setup으로 이동하고 로그인 폼·빠른 로그인은 보이지 않는다
    await waitFor(() => expect(location()).toBe('/setup'))
    expect(screen.queryByLabelText('아이디')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
  })

  // 아이디·비밀번호 칸이 브라우저 자동 완성에 맞는 autocomplete를 가진다.
  // 테스트 코드: AU-067
  it('asks the browser for the right autofill on the login fields', async () => {
    // when: 로그인하지 않은 채 로그인 화면을 연다
    await renderAt('/login', { role: null })

    // then: 아이디는 username, 비밀번호는 current-password다
    expect(await screen.findByLabelText('아이디')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'current-password')
  })

  // 인증 설정을 읽지 못해도 폼과 오류 문구가 보인다.
  // 테스트 코드: AU-069
  it('still shows the form and the reason when the config cannot be read', async () => {
    // given: 인증 설정 조회가 '로그인이 필요합니다' 오류로 실패한다
    await gateway.auth.logout()
    const error = await gateway.auth.me().catch((e: unknown) => e)
    vi.spyOn(gateway.auth, 'config').mockRejectedValue(error)
    // when: 로그인 화면을 연다
    await renderAt('/login', { role: null })

    // then: 오류 문구가 배너에 보이고 로그인 폼도 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
    expect(screen.getByRole('button', { name: '로그인' })).toBeVisible()
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
  })

  // 아무 비밀번호나 된다는 안내가 없다.
  // 테스트 코드: AU-067
  it('never says any password works', async () => {
    // when: 로그인하지 않은 채 로그인 화면을 연다
    await renderAt('/login', { role: null })

    await screen.findByRole('button', { name: '로그인' })
    // then: 안내 문구가 없다
    expect(screen.queryByText(/아무 비밀번호나 입력해도 됩니다/)).not.toBeInTheDocument()
  })
})
