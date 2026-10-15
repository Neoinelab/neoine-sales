import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway, mockControl } from '../../gateway'
import { fillDirectoryForm } from '../../test/directoryForm'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 최초 설정 2단계(파일 저장 위치)까지 진행한 상태. */
async function openStorageStep() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  const view = await renderAt('/setup', { role: null })
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  fillDirectoryForm()
  await view.user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
  await screen.findByRole('heading', { name: '파일 저장 위치' })
  return view
}

describe('최초 설정 2단계: 쓰기 테스트', () => {
  it('reports success without saving or leaving the step', async () => {
    const { user } = await openStorageStep()
    await user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')

    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    expect(await screen.findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect((await gateway.setup.status()).storageDone).toBe(false)
  })

  it('shows the server message for an unwritable location and keeps the input', async () => {
    const { user } = await openStorageStep()
    await user.type(screen.getByLabelText('저장 경로'), '/readonly/files')

    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(screen.getByLabelText('저장 경로')).toHaveValue('/readonly/files')
  })

  it('shows the failure text while the storage failure simulation is on', async () => {
    const { user } = await openStorageStep()
    mockControl.setStorageFailure(true)
    await user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')

    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('파일 저장 위치를 사용할 수 없습니다.')
  })

  it('clears the previous result when the test is run again', async () => {
    const { user } = await openStorageStep()
    await user.type(screen.getByLabelText('저장 경로'), '/readonly/files')
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))
    await screen.findByRole('alert')

    await user.clear(screen.getByLabelText('저장 경로'))
    await user.type(screen.getByLabelText('저장 경로'), '/data/ok')
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    expect(await screen.findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
