import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, meetingRows, paramsOf, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'
import { USER_ID } from '../../test/fake/seed/ids'

beforeEach(pinClock)
afterEach(unpinClock)

const bar = () => within(screen.getByRole('search', { name: '미팅 기록 검색' }))

describe('항목별 검색 (AC3)', () => {
  it('has the five conditions and the search and reset buttons', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    expect(bar().getByRole('textbox', { name: '파트너' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: 'Deal' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: '미팅 내용' })).toBeVisible()
    expect(bar().getByRole('combobox', { name: '작성자' })).toBeVisible()
    expect(bar().getByRole('button', { name: '검색' })).toBeVisible()
    expect(bar().getByRole('button', { name: '초기화' })).toBeVisible()
  })

  it('searches the partner by part of the company name and writes it to the URL', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '파트너' }), '코어')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(['ITDR 가격 협상', '견적서 전달', '킥오프 일정 협의']))
    expect(paramsOf(location()).get('partner')).toBe('코어')
  })

  it('searches when Enter is pressed in a text condition', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')

    await waitFor(() => expect(shownContents()).toEqual(['ZTNA 계약 조건 협의', '킥오프 일정 협의']))
  })

  it('searches the deal by name or code and ignores case', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: 'Deal' }), 'itdr{Enter}')

    await waitFor(() => expect(shownContents()).toEqual(['ITDR 가격 협상', 'ITDR 기술 설명']))
    expect(paramsOf(location()).get('deal')).toBe('itdr')
  })

  it('searches a date range through the date inputs, both ends included', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270305')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270308')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(['견적 재요청', 'EDR 교체 일정', 'POC 결과 공유\n다음 주 재방문', 'ITDR 기술 설명']))
    expect(paramsOf(location()).get('from')).toBe('2027-03-05')
    expect(paramsOf(location()).get('to')).toBe('2027-03-08')
  })

  it('searches by author, with resigned users among the choices', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    const select = bar().getByRole('combobox', { name: '작성자' })

    expect(within(select).getByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
    await user.selectOptions(select, '박영업')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(meetingRows()).toHaveLength(5))
    expect(shownContents()).toEqual(['계약 종료 후 정리', '수주 후 일정 점검', 'PAM 데모 진행', 'EDR 교체 일정', '견적서 전달'])
    expect(paramsOf(location()).get('author')).toBe(String(USER_ID.park))
  })

  it('ands the conditions', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '파트너' }), '코어')
    await user.selectOptions(bar().getByRole('combobox', { name: '작성자' }), '박영업')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(['견적서 전달']))
  })

  it('treats % and _ as plain characters', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '%{Enter}')

    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
    expect(meetingRows()).toHaveLength(0)
  })

  it('shows the empty message when nothing matches', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '파트너' }), '없는회사{Enter}')

    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
  })

  it('does not search and marks the field when a date is wrong', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '202703')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toBeInvalid()
    expect(await bar().findByRole('alert')).toBeVisible()
    expect(location()).toBe(PAGE)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  it('shows the server message when the start is later than the end', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270301')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(await screen.findByText('미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')).toBeVisible()
  })

  it('starts from the first page again after a search', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    await waitForRows(12)

    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')

    await waitFor(() => expect(meetingRows()).toHaveLength(2))
  })

  it('restores the conditions and the results from the URL', async () => {
    await renderAt(`${PAGE}?partner=${encodeURIComponent('코어')}&from=2027-03-10&author=${USER_ID.kim}`)

    await waitFor(() => expect(shownContents()).toEqual(['ITDR 가격 협상']))
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('코어')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.10')
    expect(bar().getByRole('combobox', { name: '작성자' })).toHaveValue(String(USER_ID.kim))
  })

  it('clears every condition and the URL on reset', async () => {
    const { user, location } = await renderAt(`${PAGE}?partner=${encodeURIComponent('코어')}&sort=partner&order=asc`)
    await waitFor(() => expect(meetingRows()).toHaveLength(3))

    await user.click(bar().getByRole('button', { name: '초기화' }))

    await waitForRows(10)
    expect(location()).toBe(PAGE)
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('')
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })
})

describe('검색 칸 (리뷰 후속)', () => {
  it('limits the text conditions to the server lengths', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveAttribute('maxlength', '200')
    expect(bar().getByRole('textbox', { name: 'Deal' })).toHaveAttribute('maxlength', '200')
    expect(bar().getByRole('textbox', { name: '미팅 내용' })).toHaveAttribute('maxlength', '100')
  })

  it('keeps what was typed but not searched yet when only the sort changes', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.type(bar().getByRole('textbox', { name: '파트너' }), 'abc')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '202703')

    await user.click(within(screen.getByRole('columnheader', { name: 'Deal' })).getByRole('button'))

    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Deal' })).toHaveAttribute('aria-sort', 'ascending'))
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('abc')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03')
    expect(paramsOf(location()).get('partner')).toBeNull() // 검색하지 않았으므로 URL에도 없다
  })

  it('still follows the URL when the conditions really change from outside', async () => {
    const { user, goTo } = await renderAt(PAGE)
    await waitForRows(10)
    await user.type(bar().getByRole('textbox', { name: '파트너' }), 'abc')

    goTo(`${PAGE}?partner=${encodeURIComponent('코어')}`)

    await waitFor(() => expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('코어'))
  })
})

describe('열 머리글 정렬 (AC4)', () => {
  const header = (name: string) => screen.getByRole('columnheader', { name })

  it('makes the five columns sortable and starts on the meeting date, descending', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    for (const name of ['파트너', 'Deal', '미팅 날짜', '미팅 내용', '작성자']) {
      expect(within(header(name)).getByRole('button')).toBeVisible()
    }
    expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'descending')
    expect(header('파트너')).not.toHaveAttribute('aria-sort')
  })

  it('sorts a text column ascending on the first click and flips on the second', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.click(within(header('파트너')).getByRole('button'))
    await waitFor(() => expect(header('파트너')).toHaveAttribute('aria-sort', 'ascending'))
    expect(shownContents().slice(0, 2)).toEqual(['견적 재요청', 'EDR 교체 일정']) // 넷브릿지: 같은 파트너는 미팅 날짜 내림차순
    expect(paramsOf(location()).get('sort')).toBe('partner')
    expect(paramsOf(location()).get('order')).toBe('asc')

    await user.click(within(header('파트너')).getByRole('button'))
    await waitFor(() => expect(header('파트너')).toHaveAttribute('aria-sort', 'descending'))
    expect(shownContents().slice(0, 2)).toEqual(['ITDR 가격 협상', '견적서 전달']) // 코어테크
    expect(header('미팅 날짜')).not.toHaveAttribute('aria-sort')
  })

  it('flips the meeting date to ascending with a click and back to descending with another', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.click(within(header('미팅 날짜')).getByRole('button'))
    await waitFor(() => expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'ascending'))
    expect(shownContents()[0]).toBe('킥오프 일정 협의')

    await user.click(within(header('미팅 날짜')).getByRole('button'))
    await waitFor(() => expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'descending'))
    expect(shownContents()[0]).toBe('계약 종료 후 정리')
  })

  it.each([
    ['Deal', 'deal'],
    ['미팅 내용', 'content'],
    ['작성자', 'author'],
  ])('sorts by %s and writes sort=%s to the URL', async (label, value) => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)

    await user.click(within(header(label)).getByRole('button'))

    await waitFor(() => expect(header(label)).toHaveAttribute('aria-sort', 'ascending'))
    expect(paramsOf(location()).get('sort')).toBe(value)
  })

  it('restarts from the first ten when the sort changes after loading more', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    await waitForRows(12)

    await user.click(within(header('미팅 내용')).getByRole('button'))

    await waitFor(() => expect(meetingRows()).toHaveLength(10))
  })

  it('restores the sort from the URL', async () => {
    await renderAt(`${PAGE}?sort=content&order=asc`)

    await waitForRows(10)
    expect(header('미팅 내용')).toHaveAttribute('aria-sort', 'ascending')
    expect(shownContents()[0]).toBe('EDR 교체 일정')
  })

  it('keeps the sort when a condition is searched', async () => {
    const { user, location } = await renderAt(`${PAGE}?sort=partner&order=asc`)
    await waitForRows(10)

    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')

    await waitFor(() => expect(meetingRows()).toHaveLength(2))
    expect(paramsOf(location()).get('sort')).toBe('partner')
    expect(header('파트너')).toHaveAttribute('aria-sort', 'ascending')
  })
})
