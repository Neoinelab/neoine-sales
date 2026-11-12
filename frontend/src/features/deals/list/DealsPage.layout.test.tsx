import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS } from './testHelpers'

/** 빠른 조건 줄(2026-10-26 개편): 체크박스 3개와 검색·초기화 버튼은 다른 입력란 다음의 별도 한 줄에 있다. */

afterEach(() => vi.restoreAllMocks())

describe('빠른 조건 줄', () => {
  // 빠른 조건 체크박스 3개와 검색·초기화 버튼은 필터 폼의 마지막 줄에 따로 있다.
  it('puts the quick checks and the buttons on their own last row of the filter form', async () => {
    // given: Deal 목록이 열려 있다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 필터 폼에서 빠른 조건 줄을 찾는다
    const form = screen.getByRole('search', { name: 'Deal 필터' })
    const row = within(form).getByRole('group', { name: '빠른 조건' })

    // then: 체크박스 3개와 버튼 2개가 있고 이 줄이 폼의 마지막이다
    expect(within(row).getAllByRole('checkbox').map((c) => c.closest('label')?.textContent?.trim())).toEqual(['내 딜만', '기한초과', '미업데이트'])
    expect(within(row).getByRole('checkbox', { name: '내 딜만' })).toBeInTheDocument()
    expect(within(row).getByRole('checkbox', { name: '기한초과' })).toBeInTheDocument()
    expect(within(row).getByRole('checkbox', { name: '미업데이트' })).toBeInTheDocument()
    expect(within(row).getAllByRole('button').map((b) => b.textContent)).toEqual(['검색', '초기화'])
    expect(form.lastElementChild).toBe(row)
  })

  // 버튼은 체크박스 뒤, 줄의 맨 끝에 있다.
  it('puts the buttons after the checkboxes and at the end of the row', async () => {
    // given: Deal 목록이 열려 있다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const row = screen.getByRole('group', { name: '빠른 조건' })

    // when: 검색 버튼과 마지막 체크박스를 찾는다
    const search = within(row).getByRole('button', { name: '검색' })
    const stale = within(row).getByRole('checkbox', { name: '미업데이트' })

    // then: 버튼이 체크박스 뒤, 줄의 마지막 요소 안에 있다
    expect(stale.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(row.lastElementChild).toContainElement(within(row).getByRole('button', { name: '초기화' }))
    expect(row.lastElementChild).toContainElement(search)
    expect(row.lastElementChild).not.toContainElement(stale)
  })

  // 다른 필터 입력란은 빠른 조건 줄 밖에 있다.
  it('keeps the other filters outside the quick row', async () => {
    // given: Deal 목록이 열려 있다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 빠른 조건 줄을 찾는다
    const row = screen.getByRole('group', { name: '빠른 조건' })

    // then: 연도~키워드 입력란이 그 줄 안에 없다
    for (const label of ['연도', 'Quarter', '월', 'Status', 'Forecast', 'Vendor', '담당자', '키워드']) {
      expect(row).not.toContainElement(screen.getByLabelText(label))
    }
  })
})

describe('오류 배너 위치', () => {
  // 필터 오류 배너는 빠른 조건 줄 밖, 그 위에 보인다.
  it('shows a filter error above the quick row and outside it', async () => {
    // given: Vendor 목록 조회가 실패한다
    vi.spyOn(gateway.vendors, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' }),
    )
    // when: 목록을 연다
    await renderAt(ALL_DEALS)
    const alert = await screen.findByRole('alert')
    const row = screen.getByRole('group', { name: '빠른 조건' })

    // then: 서버 문구의 배너가 연도 입력란 뒤, 빠른 조건 줄 앞에 있고 줄 안에는 없다
    expect(alert).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    expect(row).not.toContainElement(alert)
    expect(alert.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByLabelText('연도').compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
