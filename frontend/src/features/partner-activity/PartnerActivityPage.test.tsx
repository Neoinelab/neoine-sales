import { act, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { installIntersectionObserver, type IntersectionObserverStub } from '../../test/intersectionObserver'
import { renderAt } from '../../test/mockApp'
import { dealCodeOf } from '../../test/detailTestUtils'
import {
  COLUMNS,
  PAGE,
  SEED_CONTENTS,
  cellsOf,
  meetingRows,
  meetingTable,
  pinClock,
  rowWithContent,
  shownContents,
  unpinClock,
  waitForRows,
} from '../../test/partnerMeetings'
import { USER_ID } from '../../test/fake/seed/ids'

beforeEach(pinClock)
afterEach(unpinClock)

describe('목록 (AC1)', () => {
  it('shows the heading and the five columns in order, ending with a management column for people who can write', async () => {
    await renderAt(PAGE)

    expect(await screen.findByRole('heading', { level: 1, name: '파트너 Activity' })).toBeVisible()
    await waitForRows(10)
    const headers = within(meetingTable())
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.trim())
    expect(headers).toEqual([...COLUMNS, '관리'])
  })

  it('has no management column for a read-only user', async () => {
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)

    const headers = within(meetingTable())
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.trim())
    expect(headers).toEqual([...COLUMNS])
  })

  it('lists the ten newest meetings first by meeting date (newest on top)', async () => {
    await renderAt(PAGE)

    await waitForRows(10)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  it('shows partner company, deal name as a link to the deal, date as yyyy-mm-dd and the author name', async () => {
    const code = await dealCodeOf(15)
    await renderAt(PAGE)
    await waitForRows(10)

    const cells = cellsOf(rowWithContent('ITDR 가격 협상'))
    expect(cells[0]).toHaveTextContent('코어테크')
    expect(within(cells[1] as HTMLElement).getByRole('link', { name: '미래전자 ITDR' })).toHaveAttribute('href', `/deals/${code}`)
    expect(cells[2]).toHaveTextContent('2027-03-13')
    expect(cells[4]).toHaveTextContent('김영업')
  })

  it('keeps line breaks of the content', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    expect(shownContents()).toContain('POC 결과 공유\n다음 주 재방문')
  })

  it('shows an author who resigned after writing with the resigned mark', async () => {
    const view = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)
    await gateway.users.remove(USER_ID.kim)

    await act(() => view.client.invalidateQueries())

    await waitFor(() => expect(cellsOf(rowWithContent('ITDR 가격 협상'))[4]).toHaveTextContent('김영업(퇴사)'))
  })

  it('shows the empty message and no more-button when there are no meetings', async () => {
    await renderAt(PAGE, { seed: 'empty' })

    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
    expect(meetingRows()).toHaveLength(0)
    expect(screen.queryByRole('button', { name: '더 보기' })).not.toBeInTheDocument()
  })

  it('does not write any query string for the default view', async () => {
    const { location } = await renderAt(PAGE)
    await waitForRows(10)

    expect(location()).toBe(PAGE)
  })
})

describe('무한 스크롤 (AC2)', () => {
  let io: IntersectionObserverStub | null = null
  afterEach(() => {
    io?.restore()
    io = null
  })

  it('appends the next ten when the end of the list scrolls into view, then says everything is loaded', async () => {
    io = installIntersectionObserver()
    await renderAt(PAGE)
    await waitForRows(10)
    expect(screen.queryByText(/모두 불러왔습니다/)).not.toBeInTheDocument()

    io.triggerIntersect()

    await waitForRows(12)
    expect(shownContents()).toEqual([...SEED_CONTENTS])
    expect(await screen.findByText('모두 불러왔습니다 (전체 12건)')).toBeVisible()
  })

  it('observes a sentinel with a 200px root margin and does not load again once everything is loaded', async () => {
    io = installIntersectionObserver()
    await renderAt(PAGE)
    await waitForRows(10)

    expect(io.optionsOfLast()).toMatchObject({ rootMargin: '200px' })
    io.triggerIntersect()
    await waitForRows(12)
    await screen.findByText('모두 불러왔습니다 (전체 12건)')
    io.triggerIntersect()
    io.triggerIntersect()

    expect(meetingRows()).toHaveLength(12)
    expect(screen.getAllByText('모두 불러왔습니다 (전체 12건)')).toHaveLength(1)
  })

  it('shows a more-button while there is a next page and loads it on click', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.click(screen.getByRole('button', { name: '더 보기' }))

    await waitForRows(12)
    expect(screen.queryByRole('button', { name: '더 보기' })).not.toBeInTheDocument()
    expect(await screen.findByText('모두 불러왔습니다 (전체 12건)')).toBeVisible()
  })

  it('does not show the end message while ten of twelve are shown', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    expect(screen.queryByText('모두 불러왔습니다 (전체 12건)')).not.toBeInTheDocument()
  })

  it('shows each meeting once even when another user adds one between the pages', async () => {
    const code = await dealCodeOf(2)
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await gateway.partnerMeetings.create([{ partnerCompany: '코어테크', dealCode: code, meetingDate: '2027-03-15', content: '그 사이 새로 등록' }])
    await user.click(screen.getByRole('button', { name: '더 보기' }))

    await waitFor(() => expect(meetingRows().length).toBeGreaterThan(10))
    const shown = shownContents()
    expect(new Set(shown).size).toBe(shown.length)
    expect(shown).toHaveLength(12)
    expect(shown).not.toContain('그 사이 새로 등록')
  })
})

describe('역할별 버튼 (AC6, AC14)', () => {
  it('shows edit and delete only on the rows the viewer may change', async () => {
    await renderAt(PAGE) // kim(sales)
    await waitForRows(10)

    const own = rowWithContent('ITDR 가격 협상') // kim 작성
    const other = rowWithContent('수주 후 일정 점검') // park 작성
    const admin = rowWithContent('견적 재요청') // root 작성
    expect(within(own).getByRole('button', { name: '수정' })).toBeVisible()
    expect(within(own).getByRole('button', { name: '삭제' })).toBeVisible()
    for (const row of [other, admin]) {
      expect(within(row).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
      expect(within(row).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    }
  })

  it('shows edit and delete on every row for admin', async () => {
    await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)

    for (const row of meetingRows()) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeVisible()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeVisible()
    }
  })

  it('shows no buttons at all to a read-only user, not even the entry button', async () => {
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)

    expect(screen.queryByRole('button', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })

  it('shows the entry button to sales and admin', async () => {
    for (const role of ['sales', 'admin'] as const) {
      const view = await renderAt(PAGE, { role })
      expect(await screen.findByRole('button', { name: '미팅 내용 입력' })).toBeVisible()
      view.unmount()
    }
  })
})

describe('접근', () => {
  it('sends a visitor who is not logged in to the login page', async () => {
    const { location } = await renderAt(PAGE, { role: null })

    await waitFor(() => expect(location()).toMatch(/^\/login/))
  })

  it('reaches the page from the main menu', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('navigation', { name: '주 메뉴' })

    await user.click(within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: '파트너 Activity' }))

    await waitFor(() => expect(location()).toBe(PAGE))
    expect(await screen.findByRole('heading', { level: 1, name: '파트너 Activity' })).toBeVisible()
  })
})
