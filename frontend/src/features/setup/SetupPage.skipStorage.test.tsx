import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway, mockControl } from '../../gateway'
import { fillDirectoryForm } from '../../test/directoryForm'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 서버가 저장 위치 단계를 이미 끝난 것으로 알려 주는 상황(http 모드의 최초 설정, P2b 전까지). */
async function openSetupWithStorageDone() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  const real = gateway.setup.status.bind(gateway.setup)
  vi.spyOn(gateway.setup, 'status').mockImplementation(async () => ({ ...(await real()), storageDone: true }))
  const view = await renderAt('/setup', { role: null })
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  return view
}

describe('최초 설정: 저장 위치 단계가 이미 완료된 경우 (AC-27)', () => {
  it('shows the storage step as done from the start', async () => {
    await openSetupWithStorageDone()

    const steps = within(screen.getByRole('list', { name: '설정 단계' }))
    const storage = steps.getByText('2. 파일 저장 위치').closest('li')
    expect(storage).toHaveAttribute('data-done', 'true')
    expect(within(storage as HTMLElement).getByText('완료')).toBeInTheDocument()
    expect(steps.getByText('1. AD 서버 등록').closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('goes from the AD server step straight to the admin step', async () => {
    const { user } = await openSetupWithStorageDone()

    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('heading', { name: '관리자 등록' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: '파일 저장 위치' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('저장 경로')).not.toBeInTheDocument()
  })

  it('never asks for the storage path on the way back either', async () => {
    const { user } = await openSetupWithStorageDone()
    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('heading', { name: '관리자 등록' })

    await user.click(screen.getByRole('button', { name: 'AD 서버 다시 등록' }))

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: '파일 저장 위치' })).not.toBeInTheDocument()
  })
})
