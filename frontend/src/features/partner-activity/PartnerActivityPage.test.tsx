import { act, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { installIntersectionObserver, type IntersectionObserverStub } from '../../test/intersectionObserver'
import { renderAt } from '../../test/mockApp'
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

describe('목록', () => {
  // 쓰기 역할에게는 제목과 네 열 뒤에 관리 열이 보인다.
  // 테스트 코드: PA-049
  it('shows the heading and the four columns in order, ending with a management column for people who can write', async () => {
    // when: sales로 파트너 Activity 화면을 연다
    await renderAt(PAGE)
    // then: 제목과 네 열 머리글, 끝의 관리 열이 보인다
    expect(await screen.findByRole('heading', { level: 1, name: '파트너 Activity' })).toBeVisible()
    await waitForRows(10)
    const headers = within(meetingTable())
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.trim())
    expect(headers).toEqual([...COLUMNS, '관리'])
  })

  // 읽기 전용 사용자에게는 관리 열이 없다.
  // 테스트 코드: PA-049
  it('has no management column for a read-only user', async () => {
    // when: user 역할로 화면을 연다
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)
    // then: 네 열뿐이다
    const headers = within(meetingTable())
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.trim())
    expect(headers).toEqual([...COLUMNS])
  })

  // Deal 열은 없다.
  // 테스트 코드: PA-049
  it('has no deal column', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 머리글에 Deal이 없다
    const headers = within(meetingTable())
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.trim())
    expect(headers).not.toContain('Deal')
    expect(headers).toEqual(['파트너', '미팅 날짜', '미팅 내용', '작성자', '관리'])
  })

  // 기본 화면은 미팅 날짜 최신 10건이다.
  // 테스트 코드: PA-050
  it('lists the ten newest meetings first by meeting date (newest on top)', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    // then: 최신 10건이 날짜 내림차순으로 보인다
    await waitForRows(10)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  // 기본 화면의 주소에는 쿼리가 없다.
  // 테스트 코드: PA-050
  it('does not write any query string for the default view', async () => {
    // when: 화면을 연다
    const { location } = await renderAt(PAGE)
    await waitForRows(10)
    // then: 주소가 경로뿐이다
    expect(location()).toBe(PAGE)
  })

  // 칸은 회사명·날짜 YYYY-MM-DD·작성자이고 Deal 링크가 없다.
  // 테스트 코드: PA-051
  it('shows partner company, date as yyyy-mm-dd and the author name, with no deal link', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 한 행의 회사·날짜·작성자 칸이 보이고 링크가 없다
    const row = rowWithContent('ITDR 가격 협상')
    const cells = cellsOf(row)
    expect(cells[0]).toHaveTextContent('코어테크')
    expect(cells[1]).toHaveTextContent('2027-03-13')
    expect(cells[3]).toHaveTextContent('김영업')
    expect(within(row).queryByRole('link')).not.toBeInTheDocument()
  })

  // 내용의 줄바꿈이 유지된다.
  // 테스트 코드: PA-051
  it('keeps line breaks of the content', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 줄바꿈이 든 내용이 그대로 보인다
    expect(shownContents()).toContain('POC 결과 공유\n다음 주 재방문')
  })

  // 퇴사한 작성자는 "(퇴사)" 표시가 붙는다.
  // 테스트 코드: PA-051
  it('shows an author who resigned after writing with the resigned mark', async () => {
    // given: 목록이 열려 있고 작성자 김영업이 이후 퇴사 처리된다
    const view = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)
    await gateway.users.remove(USER_ID.kim)
    // when: 목록을 다시 읽는다
    await act(() => view.client.invalidateQueries())
    // then: 작성자 칸에 "김영업(퇴사)"가 보인다
    await waitFor(() => expect(cellsOf(rowWithContent('ITDR 가격 협상'))[3]).toHaveTextContent('김영업(퇴사)'))
  })

  // 기록이 없으면 빈 문구이고 더 보기 버튼이 없다.
  // 테스트 코드: PA-052
  it('shows the empty message and no more-button when there are no meetings', async () => {
    // when: 기록이 없는 시드로 화면을 연다
    await renderAt(PAGE, { seed: 'empty' })
    // then: 빈 문구가 보이고 행과 더 보기 버튼이 없다
    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
    expect(meetingRows()).toHaveLength(0)
    expect(screen.queryByRole('button', { name: '더 보기' })).not.toBeInTheDocument()
  })
})

describe('무한 스크롤', () => {
  let io: IntersectionObserverStub | null = null
  afterEach(() => {
    io?.restore()
    io = null
  })

  // 목록 끝이 보이면 10건씩 붙이고 다 읽으면 끝 문구를 보인다.
  // 테스트 코드: PA-053
  it('appends the next ten when the end of the list scrolls into view, then says everything is loaded', async () => {
    // given: 첫 10건이 보인다
    io = installIntersectionObserver()
    await renderAt(PAGE)
    await waitForRows(10)
    expect(screen.queryByText(/모두 불러왔습니다/)).not.toBeInTheDocument()
    // when: 목록 끝이 화면에 들어온다
    io.triggerIntersect()
    // then: 나머지 2건이 붙고 끝 문구가 보인다
    await waitForRows(12)
    expect(shownContents()).toEqual([...SEED_CONTENTS])
    expect(await screen.findByText('모두 불러왔습니다 (전체 12건)')).toBeVisible()
  })

  // 끝 감시 지점은 200px 여유로 관찰하고 다 읽은 뒤에는 더 읽지 않는다.
  // 테스트 코드: PA-053
  it('observes a sentinel with a 200px root margin and does not load again once everything is loaded', async () => {
    // given: 첫 10건이 보인다
    io = installIntersectionObserver()
    await renderAt(PAGE)
    await waitForRows(10)
    expect(io.optionsOfLast()).toMatchObject({ rootMargin: '200px' })
    // when: 끝이 보여 모두 읽은 뒤 끝이 다시 두 번 보인다
    io.triggerIntersect()
    await waitForRows(12)
    await screen.findByText('모두 불러왔습니다 (전체 12건)')
    io.triggerIntersect()
    io.triggerIntersect()
    // then: 행은 12건 그대로이고 끝 문구는 하나다
    expect(meetingRows()).toHaveLength(12)
    expect(screen.getAllByText('모두 불러왔습니다 (전체 12건)')).toHaveLength(1)
  })

  // 열 건만 보일 때는 끝 문구가 없다.
  // 테스트 코드: PA-053
  it('does not show the end message while ten of twelve are shown', async () => {
    // when: 10건이 보인다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 끝 문구가 없다
    expect(screen.queryByText('모두 불러왔습니다 (전체 12건)')).not.toBeInTheDocument()
  })

  // 다음 쪽이 있는 동안 더 보기 버튼이 있고 누르면 다음 쪽을 읽는다.
  // 테스트 코드: PA-054
  it('shows a more-button while there is a next page and loads it on click', async () => {
    // given: 첫 10건이 보인다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 더 보기를 누른다
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    // then: 12건이 되고 버튼은 사라지며 끝 문구가 보인다
    await waitForRows(12)
    expect(screen.queryByRole('button', { name: '더 보기' })).not.toBeInTheDocument()
    expect(await screen.findByText('모두 불러왔습니다 (전체 12건)')).toBeVisible()
  })

  // 쪽 사이에 다른 사용자가 기록을 더해도 같은 기록은 한 번만 보인다.
  // 테스트 코드: PA-055
  it('shows each meeting once even when another user adds one between the pages', async () => {
    // given: 첫 10건이 보인 뒤 다른 사용자가 새 기록을 더한다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await gateway.partnerMeetings.create([{ partnerCompany: '코어테크', meetingDate: '2027-03-15', content: '그 사이 새로 등록' }])
    // when: 더 보기를 누른다
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    // then: 중복 없이 12건이고 끼어든 기록은 보이지 않는다
    await waitFor(() => expect(meetingRows().length).toBeGreaterThan(10))
    const shown = shownContents()
    expect(new Set(shown).size).toBe(shown.length)
    expect(shown).toHaveLength(12)
    expect(shown).not.toContain('그 사이 새로 등록')
  })
})

describe('역할별 버튼', () => {
  // 수정·삭제 버튼은 sales 본인 행에만 있다.
  // 테스트 코드: PA-056
  it('shows edit and delete only on the rows the viewer may change', async () => {
    // when: sales(kim)로 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: kim의 행에는 버튼이 있고 park·root의 행에는 없다
    const own = rowWithContent('ITDR 가격 협상')
    const other = rowWithContent('수주 후 일정 점검')
    const admin = rowWithContent('견적 재요청')
    expect(within(own).getByRole('button', { name: '수정' })).toBeVisible()
    expect(within(own).getByRole('button', { name: '삭제' })).toBeVisible()
    for (const row of [other, admin]) {
      expect(within(row).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
      expect(within(row).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    }
  })

  // admin은 모든 행에 수정·삭제 버튼이 있다.
  // 테스트 코드: PA-056
  it('shows edit and delete on every row for admin', async () => {
    // when: admin으로 화면을 연다
    await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)
    // then: 모든 행에 수정·삭제 버튼이 있다
    for (const row of meetingRows()) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeVisible()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeVisible()
    }
  })

  // user에게는 입력 버튼을 포함해 아무 버튼도 없다.
  // 테스트 코드: PA-056, PA-075
  it('shows no buttons at all to a read-only user, not even the entry button', async () => {
    // when: user 역할로 화면을 연다
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)
    // then: 입력·수정·삭제 버튼이 모두 없다
    expect(screen.queryByRole('button', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })

  // sales와 admin에게는 입력 버튼이 보인다.
  // 테스트 코드: PA-075
  it('shows the entry button to sales and admin', async () => {
    for (const role of ['sales', 'admin'] as const) {
      // when: 역할별로 화면을 연다
      const view = await renderAt(PAGE, { role })
      // then: 입력 버튼이 보인다
      expect(await screen.findByRole('button', { name: '미팅 내용 입력' })).toBeVisible()
      view.unmount()
    }
  })
})

describe('접근', () => {
  // 로그인하지 않으면 로그인 화면으로 간다.
  // 테스트 코드: PA-057
  it('sends a visitor who is not logged in to the login page', async () => {
    // when: 로그인하지 않고 화면을 연다
    const { location } = await renderAt(PAGE, { role: null })
    // then: 로그인 화면으로 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/login/))
  })

  // 상단 메뉴로 화면에 온다.
  // 테스트 코드: PA-057
  it('reaches the page from the main menu', async () => {
    // given: Deals 화면이 열려 있다
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // when: 주 메뉴의 파트너 Activity 링크를 누른다
    await user.click(within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: '파트너 Activity' }))
    // then: 파트너 Activity 화면으로 이동한다
    await waitFor(() => expect(location()).toBe(PAGE))
    expect(await screen.findByRole('heading', { level: 1, name: '파트너 Activity' })).toBeVisible()
  })
})
