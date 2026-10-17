import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'

async function openStorage(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/integrations', { role })
  const region = await screen.findByRole('region', { name: '파일 저장 위치' })
  await within(region).findByLabelText('저장 경로')
  return { ...view, storage: within(region) }
}

describe('외부연동 파일 저장 위치: 서버 규칙 (AC-05, AC-06, R-23)', () => {
  it('shows the production default location as the example', async () => {
    const { storage } = await openStorage()

    expect(storage.getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
    expect(storage.queryByText(/예: \/data\/neoine-sales\/files/)).not.toBeInTheDocument()
  })

  it('shows the normalised path as the current location after saving', async () => {
    const { user, storage } = await openStorage()
    const input = storage.getByLabelText('저장 경로')
    await user.clear(input)
    fireEvent.change(input, { target: { value: '  //data//files/  ' } })

    await user.click(storage.getByRole('button', { name: '저장' }))

    expect(await storage.findByText('현재 위치: /data/files')).toBeInTheDocument()
  })

  it('refuses a path with a parent segment with the absolute path message', async () => {
    const { user, storage } = await openStorage()
    const input = storage.getByLabelText('저장 경로')
    await user.clear(input)
    fireEvent.change(input, { target: { value: '/data/../etc' } })

    await user.click(storage.getByRole('button', { name: '저장' }))

    expect(await storage.findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(storage.getByText('현재 위치: /data/neoine-sales/files')).toBeInTheDocument()
  })

  it('refuses a path longer than 1024 characters with the server message', async () => {
    const { user, storage } = await openStorage()
    fireEvent.change(storage.getByLabelText('저장 경로'), { target: { value: `/${'a'.repeat(1024)}` } })

    await user.click(storage.getByRole('button', { name: '쓰기 테스트' }))

    expect(await storage.findByRole('alert')).toHaveTextContent('저장 경로는 1024자 이내로 입력하세요.')
  })
})
