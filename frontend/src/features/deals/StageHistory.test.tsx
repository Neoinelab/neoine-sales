import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { listPage, stageChange } from '../../test/dealFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { StageHistory } from './StageHistory'

describe('StageHistory', () => {
  it('lists changes latest first with labels, changer and reason', async () => {
    // API는 changed_at 내림차순으로 준다. 화면은 그 순서를 그대로 보여 준다(B-6).
    const requests = mockApi({
      'GET /api/v1/deals/d-1/stage-changes': listPage([
        stageChange({
          id: 'h-2',
          from_stage: 'introduction',
          to_stage: 'lost',
          reason: '예산 부족',
          changed_by_name: '최영업',
          changed_at: '2026-03-05T01:00:00Z',
        }),
        stageChange({ id: 'h-1', changed_by_name: '박영업', changed_at: '2026-03-02T01:00:00Z' }),
      ]),
    })

    renderApp(<StageHistory dealId="d-1" />)

    const region = await screen.findByRole('region', { name: '단계 이력' })
    const items = within(region).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('제품소개 → 실주')
    expect(items[0]).toHaveTextContent('최영업')
    expect(items[0]).toHaveTextContent('예산 부족')
    expect(items[1]).toHaveTextContent('기회발굴 → 제품소개')
    expect(items[1]).toHaveTextContent('박영업')
    expect(requests[0]!.path).toBe('/api/v1/deals/d-1/stage-changes')
  })

  it('shows the time of each change', async () => {
    mockApi({ 'GET /api/v1/deals/d-1/stage-changes': listPage([stageChange()]) })

    renderApp(<StageHistory dealId="d-1" />)

    const item = await screen.findByRole('listitem')
    const expected = new Date('2026-03-02T01:00:00Z').toLocaleString('ko-KR', {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
    expect(item).toHaveTextContent(expected)
  })

  it('shows an empty message when there are no changes', async () => {
    mockApi({ 'GET /api/v1/deals/d-1/stage-changes': listPage([]) })

    renderApp(<StageHistory dealId="d-1" />)

    expect(await screen.findByText('단계 변경 이력이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('shows a server error inside the history region', async () => {
    mockApi({ 'GET /api/v1/deals/d-1/stage-changes': problem(404, 'not-found', '딜을 찾을 수 없습니다') })

    renderApp(<StageHistory dealId="d-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('딜을 찾을 수 없습니다')
  })

  it('requests the latest 50 changes', async () => {
    const requests = mockApi({ 'GET /api/v1/deals/d-1/stage-changes': listPage([stageChange()], 50) })

    renderApp(<StageHistory dealId="d-1" />)

    await screen.findByRole('listitem')
    expect(requests[0]!.query.get('limit')).toBe('50')
    expect(requests[0]!.query.get('offset')).toBe('0')
  })

  it('tells the user only the latest 50 are shown when the page is full', async () => {
    const items = Array.from({ length: 50 }, (_, i) => stageChange({ id: `h-${i}` }))
    mockApi({ 'GET /api/v1/deals/d-1/stage-changes': listPage(items, 50) })

    renderApp(<StageHistory dealId="d-1" />)

    const region = await screen.findByRole('region', { name: '단계 이력' })
    expect(within(region).getAllByRole('listitem')).toHaveLength(50)
    expect(region).toHaveTextContent(/최근.*50/)
  })

  it('shows no truncation notice when fewer than 50 changes exist', async () => {
    const items = Array.from({ length: 49 }, (_, i) => stageChange({ id: `h-${i}` }))
    mockApi({ 'GET /api/v1/deals/d-1/stage-changes': listPage(items, 50) })

    renderApp(<StageHistory dealId="d-1" />)

    const region = await screen.findByRole('region', { name: '단계 이력' })
    expect(within(region).getAllByRole('listitem')).toHaveLength(49)
    expect(region).not.toHaveTextContent('최근')
  })
})
