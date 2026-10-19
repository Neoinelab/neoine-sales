import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { dataRows, rowOf } from './testHelpers'

/**
 * DL-06 목록 조회 조건 유지(P5): 화면 안 링크·버튼으로 목록에 돌아오면 직전의 필터·정렬·페이지가 그대로다.
 * 시드(샘플 픽스처) 기준: mine=1&status=contract_completed 는 김영업의 청명대학교 SSO/MFA·도담건설 MFA 2건.
 */

const CONDITION = '/deals?mine=1&status=contract_completed&sort=name&order=asc'
const PAGED = '/deals?sort=revenueAmount&order=desc&page=2'
const NOT_FOUND = '/deals/20000101-ZZZZ'
const QINGMYEONG = /청명대학교 SSO\/MFA/

type View = Awaited<ReturnType<typeof renderAt>>

/** 조건 목록에서 청명대학교 SSO/MFA의 상세 화면까지 들어간다. */
async function openDetailFrom(url: string): Promise<View> {
  const view = await renderAt(url)
  const row = await rowOf(QINGMYEONG)
  await view.user.click(within(row).getByRole('link', { name: '청명대학교 SSO/MFA' }))
  await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })
  return view
}

async function expectConditionList(view: View, url: string) {
  await screen.findByRole('row', { name: QINGMYEONG })
  expect(view.location()).toBe(url)
  expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  expect(screen.getByRole('columnheader', { name: 'Deal' })).toHaveAttribute('aria-sort', 'ascending')
  expect(dataRows()).toHaveLength(2)
}

describe('상세에서 목록으로 (AC-01, AC-02, AC-03, AC-11)', () => {
  it('back link on detail returns to the filtered sorted page', async () => {
    const view = await openDetailFrom(CONDITION)

    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', CONDITION)
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await expectConditionList(view, CONDITION)
  })

  it('back link on detail keeps the page number', async () => {
    const view = await renderAt(PAGED)
    await screen.findByRole('button', { name: '이전' })
    const firstRow = dataRows()[0] as HTMLElement
    const link = within(firstRow).getAllByRole('link')[0] as HTMLElement
    const name = link.textContent ?? ''
    await view.user.click(link)
    await screen.findByRole('heading', { level: 1, name })

    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await screen.findByRole('button', { name: '이전' })
    expect(view.location()).toBe(PAGED)
    expect(dataRows()).toHaveLength(4)
    expect(screen.getByRole('columnheader', { name: '금액(단위:천원)' })).toHaveAttribute('aria-sort', 'descending')
  })

  it('quick view detail link round trip keeps conditions', async () => {
    const view = await renderAt(CONDITION)
    const row = await rowOf(QINGMYEONG)
    await view.user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    await view.user.click(within(screen.getByRole('region', { name: /빠른 보기/ })).getByRole('link', { name: '상세 보기' }))
    await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })

    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await expectConditionList(view, CONDITION)
  })

  it('conditions survive detail edit save detail chain', async () => {
    const view = await openDetailFrom(CONDITION)
    const code = view.location().replace('/deals/', '')
    view.goTo(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })
    await screen.findByLabelText('Deal Name')
    await view.user.click(screen.getByRole('button', { name: '저장' }))
    await waitFor(() => expect(view.location()).toBe(`/deals/${code}`))

    await view.user.click(await screen.findByRole('link', { name: '← 목록' }))

    await expectConditionList(view, CONDITION)
  })

  it('browser back still restores the url', async () => {
    const view = await openDetailFrom(CONDITION)

    view.goTo(-1)

    await expectConditionList(view, CONDITION)
  })
})

describe('삭제와 등록·수정 취소 (AC-04, AC-05)', () => {
  it('deleting a deal returns to remembered list with notice once', async () => {
    const code = await dealCodeOf(11)
    const view = await openDetailFrom(CONDITION)
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)).toBeVisible()
    expect(view.location()).toBe(CONDITION)
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')

    await view.user.click(screen.getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(screen.getByRole('link', { name: 'Deals' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await screen.findByRole('row', { name: /도담건설 MFA/ })
    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  it('cancel on new deal form returns to remembered list', async () => {
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    await view.user.click(screen.getByRole('link', { name: '+ Deal 등록' }))
    await screen.findByRole('heading', { name: 'Deal 등록' })

    await view.user.click(screen.getByRole('button', { name: '취소' }))

    await expectConditionList(view, CONDITION)
  })

  it('cancel on edit form still returns to detail', async () => {
    const view = await openDetailFrom(CONDITION)
    const code = view.location().replace('/deals/', '')
    view.goTo(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })

    await view.user.click(screen.getByRole('button', { name: '취소' }))

    expect(view.location()).toBe(`/deals/${code}`)
  })
})

describe('오류 화면의 목록 링크 (AC-06)', () => {
  it('detail error page link uses the remembered list', async () => {
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    view.goTo(NOT_FOUND)

    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', CONDITION)
  })

  it('edit error page link uses the remembered list', async () => {
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    view.goTo(`${NOT_FOUND}/edit`)

    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: '목록으로' })).toHaveAttribute('href', CONDITION)
  })
})

describe('상단 메뉴와 초기화 (AC-07, AC-08)', () => {
  it('top menu deals opens remembered list', async () => {
    const adminList = '/deals?status=contract_completed&sort=name&order=asc'
    const view = await renderAt(adminList, { role: 'admin' })
    await screen.findByRole('row', { name: QINGMYEONG })
    await view.user.click(screen.getByRole('link', { name: 'Admin' }))
    await waitFor(() => expect(view.location()).toMatch(/^\/admin/))

    await view.user.click(screen.getByRole('link', { name: 'Deals' }))

    await screen.findByRole('row', { name: QINGMYEONG })
    expect(view.location()).toBe(adminList)
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  it('reset clears remembered conditions', async () => {
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    await view.user.click(screen.getByRole('button', { name: '초기화' }))
    await waitFor(() => expect(view.location()).toBe('/deals'))
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await view.user.click(within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('link', { name: '한빛은행 ITDR 도입' }))
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', '/deals')
  })
})

describe('탭·사용자 단위 기억 (AC-10)', () => {
  it('another user does not inherit conditions', async () => {
    const first = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    first.unmount()

    // u-kim의 기억이 sessionStorage에 남은 채, u-park는 목록이 아닌 화면에서 시작한다(단일 키 구현이면 u-kim 조건이 보인다).
    await renderAt(NOT_FOUND, { userId: 'u-park' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')

    expect(screen.getByRole('link', { name: 'Deals' })).toHaveAttribute('href', '/deals')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', '/deals')
  })

  it('the same user keeps conditions after a reload', async () => {
    const first = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    first.unmount()

    const view = await renderAt('/deals/20000101-ZZZZ')
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', CONDITION)
    expect(view.location()).toBe(NOT_FOUND)
  })
})

describe('목록에 머무는 동안 상단 메뉴 (AC-07, 리뷰 Major)', () => {
  const deals = () => screen.getByRole('link', { name: 'Deals' })

  it('menu deals href is the bare list right after reset', async () => {
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })

    await view.user.click(screen.getByRole('button', { name: '초기화' }))
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(view.location()).toBe('/deals')
    expect(deals()).toHaveAttribute('href', '/deals')
  })

  it('menu deals href follows a filter change immediately', async () => {
    const view = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await view.user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByRole('row', { name: QINGMYEONG })

    expect(view.location()).toBe('/deals?status=contract_completed')
    expect(deals()).toHaveAttribute('href', '/deals?status=contract_completed')
  })

  it('menu deals href follows a sort change immediately', async () => {
    const view = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await view.user.click(screen.getByRole('button', { name: '금액(단위:천원)' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:천원)' })).toHaveAttribute('aria-sort', 'descending'))

    expect(view.location()).toContain('sort=revenueAmount')
    expect(deals()).toHaveAttribute('href', view.location())
  })

  it('menu deals href follows a page change immediately', async () => {
    const view = await renderAt(PAGED)
    await view.user.click(await screen.findByRole('button', { name: '이전' }))
    await waitFor(() => expect(view.location()).not.toContain('page=2'))

    expect(deals()).toHaveAttribute('href', view.location())
  })
})

describe('Quarter만 있는 조건의 기억 (AC-20)', () => {
  beforeEach(() => resetMock({ now: '2026-10-15T09:00:00+09:00' }))
  afterEach(() => resetMock({ now: null }))

  it('remembers a quarter-only search as it is and restores it when coming back from a detail page', async () => {
    const view = await renderAt('/deals?quarter=4')
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    expect(window.sessionStorage.getItem(listMemoryKey('u-kim'))).toBe('quarter=4')

    const link = within(dataRows()[0] as HTMLElement).getAllByRole('link')[0] as HTMLElement
    const name = link.textContent ?? ''
    await view.user.click(link)
    await screen.findByRole('heading', { level: 1, name })
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', '/deals?quarter=4')
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await screen.findByRole('button', { name: '초기화' })
    expect(view.location()).toBe('/deals?quarter=4')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('Q4')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })
})
