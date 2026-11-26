import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DIRECTORY_SAVED } from '../../../test/directoryFixtures'
import { ApiError } from '../../../shared/api/problem'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

async function openIntegrations() {
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
  await screen.findByLabelText(/^호스트/)
  return view
}

function storage() {
  return within(screen.getByRole('region', { name: '파일 저장 위치' }))
}


describe('외부연동 파일 저장 위치', () => {
  // 테스트 코드: IN-083
  it('저장 위치 섹션은 현재 위치·마지막 수정·수동 이동 안내·예시를 보인다', async () => {
    // given: 최초 설정으로 저장된 위치 /data/a(저장자 없음)
    vi.spyOn(gateway.settings, 'getStorage').mockResolvedValue({ path: '/data/a', updatedAt: '2026-10-15T09:00:00+09:00', updatedBy: null })

    // when: 외부연동 화면을 연다
    await openIntegrations()

    // then: 현재 위치, 마지막 수정(저장자 -), 수동 이동 안내, 경로 칸 값, 예시가 보인다
    expect(await storage().findByText('현재 위치: /data/a')).toBeInTheDocument()
    expect(storage().getByText(/^마지막 수정: - · /)).toBeInTheDocument()
    expect(storage().getByText(/위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다. 기존 파일은 자동으로 옮겨지지 않습니다./)).toBeInTheDocument()
    expect(storage().getByLabelText('저장 경로')).toHaveValue('/data/a')
    expect(storage().getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
  })

  // 테스트 코드: IN-083
  it('저장 위치가 없으면 설정되지 않았다는 안내와 빈 경로 칸을 보인다', async () => {
    // given: 저장 위치가 없다
    vi.spyOn(gateway.settings, 'getStorage').mockResolvedValue(null)

    // when: 외부연동 화면을 연다
    await openIntegrations()

    // then: 안내 문구와 빈 경로 칸이 보인다
    expect(await storage().findByText('아직 저장 위치가 설정되지 않았습니다.')).toBeInTheDocument()
    expect(storage().getByLabelText('저장 경로')).toHaveValue('')
  })

  // 테스트 코드: IN-084
  it('저장 위치를 저장하면 서버가 정규화한 경로가 현재 위치가 된다', async () => {
    // given: 저장 위치 섹션이 보인다
    const { user } = await openIntegrations()
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, ' /data//files/ ')

    // when: 저장을 누른다
    await user.click(storage().getByRole('button', { name: '저장' }))

    // then: 저장했습니다와 정규화된 현재 위치가 보인다
    expect(await storage().findByRole('status')).toHaveTextContent('저장했습니다')
    expect(storage().getByText('현재 위치: /data/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-085
  it('상대 경로를 저장하면 서버의 절대 경로 문구가 보이고 현재 위치는 그대로다', async () => {
    // given: 저장 위치 섹션에 상대 경로를 넣었다
    const { user } = await openIntegrations()
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, 'data/files')

    // when: 저장을 누른다
    await user.click(storage().getByRole('button', { name: '저장' }))

    // then: 서버 문구가 오류 알림으로 보이고 현재 위치는 바뀌지 않는다
    expect(await storage().findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-086
  it('쓰기 테스트는 저장하지 않고 성공을 알린다', async () => {
    // given: 저장 위치 섹션이 보인다
    const { user } = await openIntegrations()
    const save = vi.spyOn(gateway.settings, 'saveStorage')
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/data/b')

    // when: 쓰기 테스트를 누른다
    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    // then: 성공 문구가 보이고 현재 위치는 그대로이며 저장 요청은 없었다
    expect(await storage().findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(storage().getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
  })

  // 테스트 코드: IN-086
  it('쓸 수 없는 경로의 쓰기 테스트는 저장하지 않고 서버 문구를 보인다', async () => {
    // given: 쓸 수 없는 경로를 넣었다
    const { user } = await openIntegrations()
    const save = vi.spyOn(gateway.settings, 'saveStorage')
    const input = await storage().findByLabelText('저장 경로')
    await user.clear(input)
    await user.type(input, '/readonly/files')

    // when: 쓰기 테스트를 누른다
    await user.click(storage().getByRole('button', { name: '쓰기 테스트' }))

    // then: 서버 문구가 오류 알림으로 보이고 저장 요청은 없었다
    expect(await storage().findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(save).not.toHaveBeenCalled()
  })
})

describe('AD 설정 조회', () => {
  // 테스트 코드: IN-060
  it('shows the revision, saving user and timestamp without credentials', async () => {
    vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, updatedBy: { id: 1, name: '관리자', role: 'admin', status: 'active' } })
    await openIntegrations()
    expect(screen.getByText('설정 버전 3')).toBeInTheDocument()
    expect(screen.getByText(/마지막 수정: 관리자 ·/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/바인드/)).not.toBeInTheDocument()
  })
  // 테스트 코드: IN-061
  it('shows a failed lookup without rendering the AD connection form', async () => {
    vi.spyOn(gateway.settings, 'getDirectory').mockRejectedValue(new ApiError(503, {
      type: 'https://sales.neoine.test/problems/unavailable', title: 'Unavailable', status: 503, detail: '설정 조회 실패',
    }))
    await renderAt('/admin/integrations', { role: 'admin' })
    expect(await screen.findByRole('alert')).toHaveTextContent('설정 조회 실패')
    expect(screen.queryByLabelText('호스트')).not.toBeInTheDocument()
  })
})
