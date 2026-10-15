import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stageMessage } from '../../../shared/directory/messages'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { setField } from '../../../test/directoryForm'

afterEach(() => vi.restoreAllMocks())

/** 게이트웨이가 실제로 던지는 ApiError 하나(로그아웃 상태의 me() → 401). 로그인 전에 얻는다. */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}

async function openIntegrations() {
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
  await screen.findByLabelText(/서버 URL/)
  return view
}

function directory() {
  return within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' }))
}

function storage() {
  return within(screen.getByRole('region', { name: '파일 저장 위치' }))
}

describe('외부연동 AD 설정 (T-ADMIN-11)', () => {
  it('shows the saved settings in the edit form', async () => {
    await openIntegrations()

    expect(screen.getByLabelText(/서버 URL/)).toHaveValue('ldaps://dc1.corp.test\nldaps://dc2.corp.test')
    expect(screen.getByLabelText(/Base DN/)).toHaveValue('dc=corp,dc=test')
    expect(screen.getByLabelText(/StartTLS/)).toHaveAttribute('type', 'checkbox')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
  })

  it('shows who changed the settings last and the revision', async () => {
    await openIntegrations()

    expect(directory().getByText(/마지막 수정: .+ · /)).toBeInTheDocument()
    expect(directory().getByText(/설정 버전 \d+/)).toBeInTheDocument()
  })

  it('shows the message when the settings cannot be loaded', async () => {
    vi.spyOn(gateway.settings, 'getDirectory').mockRejectedValue(await serverError())
    await renderAt('/admin/integrations', { role: 'admin' })

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  })

  it('shows a result and the who/when after saving, and raises the revision', async () => {
    const { user } = await openIntegrations()
    const before = Number(/설정 버전 (\d+)/.exec(directory().getByText(/설정 버전 \d+/).textContent ?? '')?.[1])
    setField(/Base DN/, 'dc=new,dc=test')

    await user.click(directory().getByRole('button', { name: '저장' }))

    expect(await directory().findByText('저장했습니다')).toBeInTheDocument()
    expect(directory().getByText(`설정 버전 ${before + 1}`)).toBeInTheDocument()
    expect(directory().getByText(/마지막 수정: 최관리 · /)).toBeInTheDocument()
    expect(screen.getByLabelText(/Base DN/)).toHaveValue('dc=new,dc=test')
  })

  it('shows the server message for a missing required value', async () => {
    const { user } = await openIntegrations()
    setField(/바인드 템플릿/, '')

    await user.click(directory().getByRole('button', { name: '저장' }))

    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 템플릿을 입력하세요.')
  })

  it('tests the form values without saving', async () => {
    const { user } = await openIntegrations()
    setField(/Base DN/, 'dc=probe,dc=test')
    const save = vi.spyOn(gateway.settings, 'saveDirectory')

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    expect(await directory().findByRole('status')).toHaveTextContent('연결 테스트에 성공했습니다.')
    expect(save).not.toHaveBeenCalled()
  })

  it('explains the failed stage when the connection test fails', async () => {
    const { user } = await openIntegrations()
    setField(/서버 URL/, 'ldaps://fail.corp.test')

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    expect(await directory().findByRole('alert')).toHaveTextContent('AD 서버에 연결할 수 없습니다. 서버 URL과 네트워크를 확인하세요.')
  })

  it('clears the previous result when the next action starts', async () => {
    const { user } = await openIntegrations()
    await user.click(directory().getByRole('button', { name: '연결 테스트' }))
    await directory().findByRole('status')
    setField(/서버 URL/, 'ldaps://fail.corp.test')

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    await directory().findByRole('alert')
    expect(directory().queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('AD 검증 실패 단계 문구 (옛 settings·setup it.each 이관)', () => {
  it.each([
    ['connect', 'AD 서버에 연결할 수 없습니다'],
    ['tls', 'TLS 연결을 확인하지 못했습니다'],
    ['bind', '바인드 템플릿'],
    ['search', '사용자 검색에 실패했습니다'],
  ])('explains the %s stage', (stage, text) => {
    expect(stageMessage(stage)).toContain(text)
  })
})

describe('외부연동 파일 저장 위치 (T-ADMIN-12)', () => {
  it('shows the current location and the manual-move notice', async () => {
    await openIntegrations()

    expect(await storage().findByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
    expect(storage().getByLabelText('저장 경로')).toHaveValue('/data/neoine-sales/files')
    expect(storage().getByText(/위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다/)).toBeInTheDocument()
  })

  it('saves a new location and shows it as the current one', async () => {
    const { user } = await openIntegrations()
    const input = storage().getByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/data/neoine-sales/files-v2')

    await user.click(storage().getByRole('button', { name: '저장' }))

    expect(await storage().findByRole('status')).toHaveTextContent('저장했습니다')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files-v2')).toBeInTheDocument()
  })

  it('rejects a relative path', async () => {
    const { user } = await openIntegrations()
    const input = storage().getByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, 'data/files')

    await user.click(storage().getByRole('button', { name: '저장' }))

    expect(await storage().findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
  })

  it('runs the write test without saving and reports an unwritable location', async () => {
    const { user } = await openIntegrations()
    const input = storage().getByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/readonly/files')
    const save = vi.spyOn(gateway.settings, 'saveStorage')

    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    expect(await storage().findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(save).not.toHaveBeenCalled()
  })

  it('reports a successful write test', async () => {
    const { user } = await openIntegrations()

    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    expect(await storage().findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
  })
})
