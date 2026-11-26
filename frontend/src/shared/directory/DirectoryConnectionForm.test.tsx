import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DirectoryTestResult } from '../../gateway/types'
import { DIRECTORY_SAVED } from '../../test/directoryFixtures'
import { DirectoryConnectionForm } from './DirectoryConnectionForm'

const proof: DirectoryTestResult = { baseDn: 'dc=corp,dc=test', testToken: 'opaque-proof' }

function openForm() {
  const save = vi.fn().mockResolvedValue(undefined)
  const test = vi.fn().mockResolvedValue(proof)
  render(<StrictMode><DirectoryConnectionForm setup saved={DIRECTORY_SAVED} save={save} test={test} /></StrictMode>)
  return { user: userEvent.setup(), save, test }
}

async function testConnection(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '연결 테스트' }))
  await user.type(screen.getByLabelText('바인드 계정'), 'operator')
  await user.type(screen.getByLabelText('바인드 비밀번호'), 'temporary-password')
  await user.click(screen.getByRole('button', { name: '테스트 실행' }))
}

describe('AD 연결 테스트와 저장 경계', () => {
  // 테스트 코드: SU-052, SU-073
  it('registers with a proof after testing and never includes credentials in the save', async () => {
    const { user, save } = openForm()
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
    await testConnection(user)
    await screen.findByText(/연결 테스트에 성공했습니다/)
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await waitFor(() => expect(save).toHaveBeenCalledOnce())
    expect(save.mock.calls[0]?.[0]).toEqual({
      host: DIRECTORY_SAVED.host, port: 636, security: 'ssl',
      userFilter: DIRECTORY_SAVED.userFilter, connectTimeoutSeconds: 5, testToken: proof.testToken,
    })
  })
  // 테스트 코드: SU-053
  it('requires both credentials before calling the connection test', async () => {
    const { user, test } = openForm()
    await user.click(screen.getByRole('button', { name: '연결 테스트' }))
    await user.click(screen.getByRole('button', { name: '테스트 실행' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('바인드 계정과 비밀번호를 입력하세요.')
    expect(test).not.toHaveBeenCalled()
  })
  // 테스트 코드: SU-054, IN-068
  it('keeps the endpoint and requires retesting after a failed save', async () => {
    const { user, save } = openForm()
    save.mockRejectedValueOnce(new Error('저장 실패'))
    await testConnection(user)
    await screen.findByText(/연결 테스트에 성공했습니다/)
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('alert')
    expect(screen.getByLabelText('호스트')).toHaveValue(DIRECTORY_SAVED.host)
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
  })
  // 테스트 코드: SU-074, IN-073
  it.each(['호스트', '사용자 검색 필터', '연결 제한 시간(초)', '포트'])('invalidates the proof when %s changes', async (label) => {
    const { user } = openForm()
    await testConnection(user)
    await screen.findByText(/연결 테스트에 성공했습니다/)
    fireEvent.change(screen.getByLabelText(label), { target: { value: label === '호스트' ? 'other.corp.test' : '9' } })
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
  })
  // 테스트 코드: SU-075, IN-064, IN-066, IN-078
  it('clears test credentials after a failure and keeps the endpoint', async () => {
    const { user, test } = openForm()
    test.mockRejectedValueOnce(new Error('AD 연결 실패'))
    await testConnection(user)
    await screen.findByRole('alert')
    expect(screen.getByLabelText('바인드 계정')).toHaveValue('')
    expect(screen.getByLabelText('바인드 비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('바인드 비밀번호')).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText('호스트')).toHaveValue(DIRECTORY_SAVED.host)
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
  })
  // 테스트 코드: SU-076, SU-078
  it('disables repeat requests and ignores a late result after cancelling', async () => {
    const { user, test } = openForm()
    let finish: (value: DirectoryTestResult) => void = () => { throw new Error('request not started') }
    test.mockImplementationOnce(() => new Promise<DirectoryTestResult>((resolve) => { finish = resolve }))
    await testConnection(user)
    expect(screen.getByRole('button', { name: '연결 테스트' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '테스트 중…' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '취소' }))
    fireEvent.change(screen.getByLabelText('호스트'), { target: { value: 'other.corp.test' } })
    await act(async () => { finish(proof) })
    expect(screen.queryByText(/연결 테스트에 성공했습니다/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
  })
  // 테스트 코드: SU-077
  it('does not submit the form before a successful test', () => {
    const { save } = openForm()
    const form = screen.getByLabelText('호스트').closest('form')
    if (!form) throw new Error('form missing')
    fireEvent.submit(form)
    expect(save).not.toHaveBeenCalled()
  })
})
