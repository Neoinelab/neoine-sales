import { act, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { defaultDealsUrl } from '../../../test/dealsUrl'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'
// 기록 테스트는 /dashboard에서 시작한다. App은 DashboardPage를 React.lazy로 불러오므로 청크 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import '../../dashboard/DashboardPage'

/**
 * 기본 기간 = 올해만, Quarter는 전체(AC-04~09). 조건이 하나도 없는 주소로 목록에 들어오거나 초기화할 때만 적용한다.
 * 올해는 앱 시계(서버 동기 시계) 기준이다. 시드 날짜는 기준일 상대값이라 기준일을 고정한다.
 */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const mainMenu = () => within(screen.getByRole('navigation', { name: '주 메뉴' }))

describe('조건 없는 목록 진입 (AC-04, AC-05)', () => {
  it('replaces the bare list url with this year and no quarter', async () => {
    const { location } = await renderAt('/deals')

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(await screen.findByLabelText('연도')).toHaveDisplayValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(optionNames(screen.getByLabelText('월'))).toHaveLength(13)
  })

  it('never asks the server for the whole list: every request carries the default year and no quarter', async () => {
    const list = vi.spyOn(gateway.deals, 'list')

    await renderAt('/deals')
    await screen.findByText(/총 \d+건/)

    expect(list.mock.calls.length).toBeGreaterThan(0)
    for (const [query] of list.mock.calls) {
      expect(query).toMatchObject({ year: 2026 })
      expect(query).not.toHaveProperty('quarter')
    }
  })

  it('lists the deals of this year only', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const expected = await gateway.deals.list({ year: 2026, limit: 1 })
    const all = await gateway.deals.list({ limit: 1 })
    expect(expected.total).toBeGreaterThan(0)
    expect(expected.total).toBeLessThan(all.total)
    expect(await screen.findByText(`총 ${expected.total}건`)).toBeVisible()
  })

  it('treats an empty value and a blank value as no condition', async () => {
    const { location } = await renderAt('/deals?q=&solution=%20')

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })

  it('keeps the sort and drops the page and unknown keys when it fills the default', async () => {
    const { location } = await renderAt('/deals?sort=owner&order=asc&page=3&outcome=open')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&sort=owner&order=asc'))
    expect(await screen.findByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'ascending')
  })

  it('does not leave the bare list in the browser history', async () => {
    const { user, location, goTo } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: 'Dashboard' })

    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    goTo(-1)

    await waitFor(() => expect(location()).toBe('/dashboard'))
  })
})

describe('앱 시계 기준 (AC-06)', () => {
  it.each([
    ['2030-06-15T09:00:00+09:00', '/deals?year=2030'],
    ['2027-01-01T00:10:00+09:00', '/deals?year=2027'],
    ['2026-12-31T23:50:00+09:00', '/deals?year=2026'],
  ])('uses the app clock %s', async (now, expected) => {
    resetMock({ now })

    const { location } = await renderAt('/deals')

    await waitFor(() => expect(location()).toBe(expected))
    expect(expected).toBe(defaultDealsUrl(now))
  })
})

describe('여러 진입점 (AC-04)', () => {
  it('applies the default from the root address', async () => {
    const { location } = await renderAt('/')

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })

  it('applies the default right after a login', async () => {
    const { user, location } = await renderAt('/login', { role: null })
    await screen.findByRole('button', { name: '로그인' })

    await user.click(screen.getByRole('button', { name: '영업' }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })

  it('applies the default when the top menu has no remembered condition', async () => {
    const { user, location } = await renderAt('/forecast')
    await screen.findByRole('heading', { name: 'Forecast' })
    expect(mainMenu().getByRole('link', { name: 'Deals' })).toHaveAttribute('href', '/deals')

    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })

  it('applies the default when the remembered search has only an old outcome', async () => {
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'outcome=open')
    const { user, location } = await renderAt('/deals/20000101-ZZZZ')
    const back = await screen.findByRole('link', { name: 'Deal 목록으로' })
    expect(back).toHaveAttribute('href', '/deals')

    await user.click(back)

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })

  it('applies the default to the back link of the detail page when nothing is remembered', async () => {
    const { user, location } = await renderAt('/deals/20000101-ZZZZ')

    await user.click(await screen.findByRole('link', { name: 'Deal 목록으로' }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
  })
})

describe('초기화 (AC-07)', () => {
  it('goes to this year (all quarters) as a new history entry and remembers it', async () => {
    const start = '/deals?year=all&status=contract_completed&sort=name&order=asc'
    const { user, location, goTo } = await renderAt(start)
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })

    await user.click(screen.getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveDisplayValue('전체')
    expect(await screen.findByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026')

    goTo(-1)

    await waitFor(() => expect(location()).toBe(start))
  })
})

describe('조건이 있는 주소는 그대로 (AC-08)', () => {
  it.each(['/deals?overdue=1', '/deals?quarter=4', '/deals?month=3', '/deals?status=contract_completed'])('keeps %s as it is', async (url) => {
    const { location } = await renderAt(url)
    await screen.findByText(/총 \d+건/)
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })

    expect(location()).toBe(url)
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })

  it('does not ask the server with an added period for an address that has a condition', async () => {
    const list = vi.spyOn(gateway.deals, 'list')

    await renderAt('/deals?overdue=1')
    await screen.findByText(/총 \d+건/)

    for (const [query] of list.mock.calls) {
      expect(query).not.toHaveProperty('year')
      expect(query).not.toHaveProperty('quarter')
    }
  })
})

describe('필터 바에서 마지막 조건을 지울 때 (AC-09)', () => {
  it('keeps all years instead of bringing the default year back', async () => {
    const { user, location } = await renderAt('/deals?overdue=1')
    await waitFor(() => expect(screen.getByRole('checkbox', { name: '기한초과' })).toBeChecked())

    await user.click(screen.getByRole('checkbox', { name: '기한초과' }))

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })
    expect(location()).toBe('/deals?year=all')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })
})

describe('연도 전체 (AC-09)', () => {
  it('keeps all years when year and quarter are both cleared', async () => {
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await user.selectOptions(screen.getByLabelText('연도'), '전체')
    await waitFor(() => expect(location()).toBe('/deals?year=all&quarter=4'))
    await user.selectOptions(screen.getByLabelText('Quarter'), '전체')

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })
    expect(location()).toBe('/deals?year=all')
    const all = await gateway.deals.list({ limit: 1 })
    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
    expect(dataRows()).toHaveLength(20)
  })

  it('sends no year when all years are chosen', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByText(/총 \d+건/)

    await user.selectOptions(screen.getByLabelText('연도'), '전체')

    await waitFor(() => expect(list.mock.calls.at(-1)?.[0]).toEqual({ offset: 0, limit: 20, quarter: 4 }))
  })

  it('restores all years after a detail round trip', async () => {
    const { user, location } = await renderAt('/deals?year=all')
    const first = await rowOf(/한빛은행 ITDR 도입/)
    const link = within(first).getByRole('link', { name: '한빛은행 ITDR 도입' })
    const name = link.textContent ?? ''
    await user.click(link)
    await screen.findByRole('heading', { level: 1, name })

    await user.click(screen.getByRole('link', { name: '← 목록' }))

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(await screen.findByLabelText('연도')).toHaveDisplayValue('전체')
  })

  it('restores all years from the top menu after leaving the list', async () => {
    const { user, location } = await renderAt('/deals?year=all')
    await screen.findByText(/총 \d+건/)
    await user.click(mainMenu().getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })

    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })
})
