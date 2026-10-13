import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { asMe } from '../../test/authFixtures'
import { mockApi, renderApp, settled } from '../../test/utils'
import { ActionList } from './ActionList'

const ACTION = {
  id: 'a-1',
  deal_id: 'd-1',
  action_type: 'meeting',
  action: '킥오프 미팅',
  next_action: '제안서 전달',
  due_date: '2026-03-10',
  memo: '요구사항 정리',
  acted_at: '2026-03-02T01:00:00Z',
  actor: '박영업',
  created_at: '2026-03-02T01:00:00Z',
  updated_at: '2026-03-02T01:00:00Z',
}
const routes = (role: 'admin' | 'sales' | 'user') => ({
  'GET /api/v1/auth/me': { body: asMe(role) },
  'GET /api/v1/deals/d-1/actions': { body: { items: [ACTION], offset: 0, limit: 20 } },
})

describe('ActionList write controls by role (UI-9)', () => {
  it('hides record, edit and delete from a viewer but still lists the activities', async () => {
    mockApi(routes('user'))
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')
    await settled()

    expect(screen.queryByRole('button', { name: '활동 기록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument()
  })

  it.each(['sales', 'admin'] as const)('keeps record, edit and delete for %s', async (role) => {
    mockApi(routes(role))
    renderApp(<ActionList dealId="d-1" />)

    expect(await screen.findByRole('button', { name: '활동 기록' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '수정' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '삭제' })).toBeInTheDocument()
  })
})
