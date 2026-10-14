import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { asMe, userRef } from '../../test/authFixtures'
import { DETAIL_CUSTOMER, DETAIL_DEAL, DETAIL_PARTNER, listPage } from '../../test/dealFixtures'
import { mockApi, renderApp, settled } from '../../test/utils'
import { DealDetailPage } from './DealDetailPage'

const ACTION = {
  id: 'a-1',
  deal_id: 'd-1',
  action_type: 'meeting',
  action: '킥오프 미팅',
  next_action: '제안서 전달',
  due_date: '2026-03-10',
  memo: '요구사항 정리',
  acted_at: '2026-03-02T01:00:00Z',
  actor: userRef('u-3', '박영업'),
  created_at: '2026-03-02T01:00:00Z',
  updated_at: '2026-03-02T01:00:00Z',
}

const routes = (role: 'admin' | 'sales' | 'user') => ({
  'GET /api/v1/auth/me': { body: asMe(role) },
  'GET /api/v1/deals/d-1': { body: DETAIL_DEAL },
  'GET /api/v1/customers/c-1': { body: DETAIL_CUSTOMER },
  'GET /api/v1/partners/p-1': { body: DETAIL_PARTNER },
  'GET /api/v1/deals/d-1/stage-changes': listPage([]),
  'GET /api/v1/deals/d-1/actions': listPage([ACTION]),
  'GET /api/v1/customers': listPage([DETAIL_CUSTOMER], 200),
  'GET /api/v1/partners': listPage([DETAIL_PARTNER], 200),
})

const renderDetail = () =>
  renderApp(
    <Routes>
      <Route path="/deals/:dealId" element={<DealDetailPage />} />
    </Routes>,
    '/deals/d-1',
  )

describe('DealDetailPage write controls by role (UI-9)', () => {
  it('shows a viewer the deal, the history and the activities without any write control', async () => {
    mockApi(routes('user'))
    renderDetail()
    await screen.findByText('킥오프 미팅')
    await settled()

    expect(screen.getByRole('heading', { name: /DEAL-001/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '활동 기록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '단계 변경' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '단계 변경' })).not.toBeInTheDocument()
  })

  it.each(['sales', 'admin'] as const)('keeps edit, stage change and activity controls for %s', async (role) => {
    mockApi(routes(role))
    renderDetail()

    expect(await screen.findByRole('region', { name: '단계 변경' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '활동 기록' })).toBeInTheDocument()
    // 딜 수정 버튼 1개 + 활동 행의 수정 버튼 1개
    expect(await screen.findAllByRole('button', { name: '수정' })).toHaveLength(2)
    expect(await screen.findByRole('button', { name: '삭제' })).toBeInTheDocument()
  })
})
