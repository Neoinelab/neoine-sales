import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { fillDirectoryForm } from '../../test/directoryForm'
import { openFreshSetup, openLocalStorageStep } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

function steps() {
  return within(screen.getByRole('list', { name: '설정 단계' }))
}

/** 서버가 던지는 ApiError 하나(로그아웃 상태의 me() → 401). */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}

describe('최초 설정 1단계: 인증 방식 (AC-1)', () => {
  it('asks for the auth mode first, with the three step labels', async () => {
    await openFreshSetup()

    expect(steps().getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '1. 인증 방식',
      '2. 파일 저장 위치',
      '3. 관리자 등록',
    ])
    expect(steps().getByText('1. 인증 방식').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByRole('button', { name: 'AD 연동' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '앱에서 직접 관리' })).toBeEnabled()
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('저장 경로')).not.toBeInTheDocument()
  })

  it('chooses the local mode on the server and moves to the storage step without any AD form', async () => {
    const { user } = await openFreshSetup()
    const choose = vi.spyOn(gateway.setup, 'chooseAuthMode')

    await user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))

    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(choose).toHaveBeenCalledTimes(1)
    expect(choose).toHaveBeenCalledWith('local')
    expect(steps().getByText('1. 인증 방식').closest('li')).toHaveTextContent('완료')
    expect(steps().getByText('2. 파일 저장 위치').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
    expect((await gateway.setup.status()).authMode).toBe('local')
  })

  it('shows the AD server form for "AD 연동" without calling the server yet', async () => {
    const { user } = await openFreshSetup()
    const choose = vi.spyOn(gateway.setup, 'chooseAuthMode')

    await user.click(screen.getByRole('button', { name: 'AD 연동' }))

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(choose).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: '인증 방식 다시 선택' })).toBeInTheDocument()
  })

  it('goes back from the AD form to the choice', async () => {
    const { user } = await openFreshSetup()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    await screen.findByRole('heading', { name: 'AD 서버 등록' })

    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))

    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
  })

  it('saving the AD server records the AD mode and moves to the storage step', async () => {
    const { user } = await openFreshSetup()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(await gateway.setup.status()).toMatchObject({ authMode: 'ad', directoryDone: true })
  })

  it('shows the server message and stays on the choice when choosing fails', async () => {
    const { user } = await openFreshSetup()
    vi.spyOn(gateway.setup, 'chooseAuthMode').mockRejectedValue(await serverError())

    await user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
    expect(screen.getByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
  })

  it('shows the already-closed message when the first admin exists', async () => {
    const { user } = await openFreshSetup()
    const closed = new ApiError(409, {
      type: 'https://sales.neoine.test/problems/invalid-state',
      title: 'Invalid State',
      status: 409,
      detail: '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다',
    })
    vi.spyOn(gateway.setup, 'chooseAuthMode').mockRejectedValue(closed)

    await user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다')
  })
})

describe('인증 방식 다시 선택', () => {
  it('goes back from the storage step to the choice and can switch to AD', async () => {
    const { user } = await openLocalStorageStep()

    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))

    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect((await gateway.setup.status()).authMode).toBe('ad')
  })

  it('opens the AD form directly when the server already knows the AD mode but has no AD server', async () => {
    const real = gateway.setup.status.bind(gateway.setup)
    vi.spyOn(gateway.setup, 'status').mockImplementation(async () => ({
      ...(await real()),
      authMode: 'ad',
      directoryDone: false,
      storageDone: false,
      adminDone: false,
    }))

    await renderAt('/setup', { role: null })

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '인증 방식 다시 선택' })).toBeInTheDocument()
  })

  it('moves a configured local system to the login page', async () => {
    const real = gateway.setup.status.bind(gateway.setup)
    vi.spyOn(gateway.setup, 'status').mockImplementation(async () => ({
      ...(await real()),
      authMode: 'local',
      directoryDone: true,
      storageDone: true,
      adminDone: true,
    }))
    const { location } = await renderAt('/setup', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })
})
