import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { mockControl } from '../../test/fake/default'
import { fillDirectoryForm } from '../../test/directoryForm'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 최초 설정이 아직 안 된 상태(MockPanel의 "최초 설정 다시 시작"과 같다)로 /setup을 연다. */
async function openSetup() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  return renderAt('/setup', { role: null })
}

describe('최초 설정 3단계 흐름 (AC-19, AC-20, R-24)', () => {
  it('shows the production default location as the example on the storage step', async () => {
    const { user } = await openSetup()
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    await screen.findByRole('heading', { name: '파일 저장 위치' })
    expect(screen.getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
    expect(screen.queryByText(/\/data\/neoine-sales\/files/)).not.toBeInTheDocument()
  })

  it('opens at the storage step when the server says the AD server is registered but the location is not', async () => {
    vi.spyOn(gateway.setup, 'status').mockResolvedValue({ directoryDone: true, storageDone: false, adminDone: false })
    await renderAt('/setup', { role: null })

    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeVisible()
    const steps = within(screen.getByRole('list', { name: '설정 단계' }))
    expect(steps.getByText('1. AD 서버 등록').closest('li')).toHaveAttribute('data-done', 'true')
    expect(steps.getByText('2. 파일 저장 위치').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(steps.getByText('3. 관리자 등록').closest('li')).not.toHaveAttribute('data-done', 'true')
  })

  it('keeps the admin step closed until the location is saved: step 3 appears only after step 2', async () => {
    const { user } = await openSetup()
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('heading', { name: '파일 저장 위치' })
    expect(screen.queryByRole('heading', { name: '관리자 등록' })).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('저장 경로'), '/var/lib/neoine-sales/files')
    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    expect(await screen.findByRole('heading', { name: '관리자 등록' })).toBeVisible()
  })

  it('shows the path rule message for a path with parent segments and stays on the step', async () => {
    const { user } = await openSetup()
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('heading', { name: '파일 저장 위치' })

    await user.type(screen.getByLabelText('저장 경로'), '/var/lib/../etc')
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })
})
