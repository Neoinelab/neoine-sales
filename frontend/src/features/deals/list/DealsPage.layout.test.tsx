import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS } from './testHelpers'

/** 빠른 조건 줄(2026-10-26 개편, AC-15·17): 체크박스 3개와 검색·초기화 버튼은 다른 입력란 다음의 별도 한 줄에 있다. */

afterEach(() => vi.restoreAllMocks())

describe('빠른 조건 줄 (AC-15)', () => {
  it('puts the quick checks and the buttons on their own last row of the filter form', async () => {
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const form = screen.getByRole('search', { name: 'Deal 필터' })
    const row = within(form).getByRole('group', { name: '빠른 조건' })

    expect(within(row).getAllByRole('checkbox').map((c) => c.closest('label')?.textContent?.trim())).toEqual(['내 딜만', '기한초과', '미업데이트'])
    expect(within(row).getByRole('checkbox', { name: '내 딜만' })).toBeInTheDocument()
    expect(within(row).getByRole('checkbox', { name: '기한초과' })).toBeInTheDocument()
    expect(within(row).getByRole('checkbox', { name: '미업데이트' })).toBeInTheDocument()
    expect(within(row).getAllByRole('button').map((b) => b.textContent)).toEqual(['검색', '초기화'])
    expect(form.lastElementChild).toBe(row)
  })

  it('puts the buttons after the checkboxes and at the end of the row', async () => {
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const row = screen.getByRole('group', { name: '빠른 조건' })

    const search = within(row).getByRole('button', { name: '검색' })
    const stale = within(row).getByRole('checkbox', { name: '미업데이트' })
    expect(stale.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(row.lastElementChild).toContainElement(within(row).getByRole('button', { name: '초기화' }))
    expect(row.lastElementChild).toContainElement(search)
    expect(row.lastElementChild).not.toContainElement(stale)
  })

  it('keeps the other filters outside the quick row', async () => {
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const row = screen.getByRole('group', { name: '빠른 조건' })

    for (const label of ['연도', 'Quarter', '월', 'Status', 'Forecast', 'Vendor', '담당자', '키워드']) {
      expect(row).not.toContainElement(screen.getByLabelText(label))
    }
  })
})

describe('오류 배너 위치 (AC-17)', () => {
  it('shows a filter error above the quick row and outside it', async () => {
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' }),
    )
    await renderAt(ALL_DEALS)
    const alert = await screen.findByRole('alert')
    const row = screen.getByRole('group', { name: '빠른 조건' })

    expect(alert).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    expect(row).not.toContainElement(alert)
    expect(alert.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByLabelText('연도').compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
