import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

// 목록의 BANT 열은 제거되었다(deal-list-columns-plan AC1). 열 구조·BANT 없음 검증은 DealsPage.columns.test.tsx.
// 여기에는 BANT 열과 무관하게 남는 계약(정렬 가능 헤더, 필터에 BANT 없음)만 둔다.

describe('목록 헤더 정렬', () => {
  it('keeps the existing sortable headers sortable', async () => {
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    for (const name of ['Deal', 'Status', '금액(단위:천원)', 'Expected Close', '최종 업데이트']) {
      expect(within(screen.getByRole('columnheader', { name })).getByRole('button')).toBeVisible()
    }
  })
})

describe('목록 필터에는 BANT Label 선택이 없다 (AC-7)', () => {
  it('has no Budget, Authority, Need or Timeline Label select in the filter area', async () => {
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    const filters = screen.getByRole('search', { name: 'Deal 필터' })
    for (const name of ['Budget Label', 'Authority Label', 'Need Label', 'Timeline Label']) {
      expect(within(filters).queryByLabelText(name)).not.toBeInTheDocument()
    }
    expect(within(filters).queryAllByLabelText(/Label$/)).toEqual([])
  })

  it('lists every deal and keeps the page working with old BANT keys in the URL', async () => {
    const { location } = await renderAt('/deals?year=all&budget=1&authority=2&need=3&timeline=4')
    await rowOf(/한빛은행 ITDR 도입/)

    expect(screen.queryByText(/조건에 맞는 Deal이 없습니다/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(location()).toContain('budget=1') // URL은 건드리지 않는다
    expect(screen.getAllByRole('row').length).toBeGreaterThan(1)
  })

  it('does not treat the old BANT keys as an active filter for the empty message', async () => {
    await renderAt('/deals?year=all&budget=1&authority=2&need=3&timeline=4', { seed: 'empty' })

    expect(await screen.findByText('등록된 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })
})
