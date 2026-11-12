import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'

async function openStorage(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/integrations', { role })
  const region = await screen.findByRole('region', { name: '파일 저장 위치' })
  await within(region).findByLabelText('저장 경로')
  return { ...view, storage: within(region) }
}

describe('외부연동 파일 저장 위치: 서버 규칙', () => {
  // 테스트 코드: IN-083
  it('운영 기본 위치를 입력 예시로 보이고 개발용 예시는 보이지 않는다', async () => {
    // when: 안내 문구를 본다 (전제: 저장 위치 섹션이 열려 있다)
    const { storage } = await openStorage()

    // then: 예시는 /var/lib/neoine-sales/files이다
    expect(storage.getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
    expect(storage.queryByText(/예: \/data\/neoine-sales\/files/)).not.toBeInTheDocument()
  })

  // 테스트 코드: IN-084
  it('저장한 뒤에는 서버가 정규화한 경로를 현재 위치로 보인다', async () => {
    // given: 경로 칸에 공백과 중복 슬래시가 든 경로를 넣었다
    const { user, storage } = await openStorage()
    const input = storage.getByLabelText('저장 경로')
    await user.clear(input)
    fireEvent.change(input, { target: { value: '  //data//files/  ' } })

    // when: 저장을 누른다
    await user.click(storage.getByRole('button', { name: '저장' }))

    // then: 정규화된 현재 위치가 보인다
    expect(await storage.findByText('현재 위치: /data/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-085
  it('상위 조각(..)이 든 경로는 서버의 절대 경로 문구로 거절되고 현재 위치는 그대로다', async () => {
    // given: 경로 칸에 /data/../etc를 넣었다
    const { user, storage } = await openStorage()
    const input = storage.getByLabelText('저장 경로')
    await user.clear(input)
    fireEvent.change(input, { target: { value: '/data/../etc' } })

    // when: 저장을 누른다
    await user.click(storage.getByRole('button', { name: '저장' }))

    // then: 서버 문구가 보이고 현재 위치는 바뀌지 않는다
    expect(await storage.findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(storage.getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
  })

  // 테스트 코드: IN-085
  it('정규화 뒤 1025자 경로는 서버의 길이 문구로 거절된다', async () => {
    // given: 경로 칸에 1025자 경로를 넣었다
    const { user, storage } = await openStorage()
    fireEvent.change(storage.getByLabelText('저장 경로'), { target: { value: `/${'a'.repeat(1024)}` } })

    // when: 저장을 누른다
    await user.click(storage.getByRole('button', { name: '저장' }))

    // then: 길이 문구가 오류 알림으로 보인다
    expect(await storage.findByRole('alert')).toHaveTextContent('저장 경로는 1024자 이내로 입력하세요.')
  })
})
