import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, meetingRows, paramsOf, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'
import { USER_ID } from '../../test/fake/seed/ids'

beforeEach(pinClock)
afterEach(unpinClock)

const bar = () => within(screen.getByRole('search', { name: '미팅 기록 검색' }))
/** 미팅 날짜 선택 상자에서 '직접 지정'을 골라 시작·끝 칸을 연다(Deals '최종 업데이트'와 같은 방식). */
const openCustomDates = (user: UserEvent) => user.selectOptions(bar().getByRole('combobox', { name: '미팅 날짜' }), '직접 지정')

describe('항목별 검색', () => {
  // 검색 폼은 Deal 없이 네 조건과 검색·초기화 버튼이다.
  // 테스트 코드: PA-058
  it('has the four conditions without a deal and the search and reset buttons', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 파트너·미팅 날짜·미팅 내용·작성자와 두 버튼이 있고 Deal 조건은 없다
    expect(bar().getByRole('textbox', { name: '파트너' })).toBeVisible()
    expect(bar().queryByRole('textbox', { name: 'Deal' })).not.toBeInTheDocument()
    expect(bar().getByRole('combobox', { name: '미팅 날짜' })).toHaveDisplayValue('전체')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 끝' })).not.toBeInTheDocument()
    expect(bar().getByRole('textbox', { name: '미팅 내용' })).toBeVisible()
    expect(bar().getByRole('combobox', { name: '작성자' })).toBeVisible()
    expect(bar().getByRole('button', { name: '검색' })).toBeVisible()
    expect(bar().getByRole('button', { name: '초기화' })).toBeVisible()
  })

  // 파트너 일부 글자로 검색하면 주소에 쓰인다.
  // 테스트 코드: PA-059
  it('searches the partner by part of the company name and writes it to the URL', async () => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 파트너 칸에 "코어"를 치고 검색을 누른다
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '코어')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 코어테크 기록만 보이고 주소에 partner가 쓰인다
    await waitFor(() => expect(shownContents()).toEqual(['ITDR 가격 협상', '견적서 전달', '킥오프 일정 협의']))
    expect(paramsOf(location()).get('partner')).toBe('코어')
  })

  // 텍스트 칸에서 Enter를 눌러도 검색된다.
  // 테스트 코드: PA-059
  it('searches when Enter is pressed in a text condition', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 미팅 내용 칸에 "협의"를 치고 Enter를 누른다
    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')
    // then: "협의"가 든 기록만 보인다
    await waitFor(() => expect(shownContents()).toEqual(['ZTNA 계약 조건 협의', '킥오프 일정 협의']))
  })

  // 직접 지정으로 시작·끝 날짜를 쳐 검색하면 양끝이 포함된다.
  // 테스트 코드: PA-071
  it('searches a date range through the date inputs, both ends included', async () => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 직접 지정을 골라 03-05 ~ 03-08을 치고 검색한다
    await openCustomDates(user)
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270305')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270308')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 양끝 날짜를 포함한 기록이 보이고 주소에 날짜가 쓰인다
    await waitFor(() => expect(shownContents()).toEqual(['견적 재요청', 'EDR 교체 일정', 'POC 결과 공유\n다음 주 재방문', 'ITDR 기술 설명']))
    expect(paramsOf(location()).get('from')).toBe('2027-03-05')
    expect(paramsOf(location()).get('to')).toBe('2027-03-08')
  })

  // 작성자로 검색하고 선택지에 퇴사자가 있다.
  // 테스트 코드: PA-060
  it('searches by author, with resigned users among the choices', async () => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    const select = bar().getByRole('combobox', { name: '작성자' })
    // then: 선택지에 퇴사자가 있다
    expect(within(select).getByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
    // when: 박영업을 골라 검색한다
    await user.selectOptions(select, '박영업')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 박영업의 기록만 보이고 주소에 author가 쓰인다
    await waitFor(() => expect(meetingRows()).toHaveLength(5))
    expect(shownContents()).toEqual(['계약 종료 후 정리', '수주 후 일정 점검', 'PAM 데모 진행', 'EDR 교체 일정', '견적서 전달'])
    expect(paramsOf(location()).get('author')).toBe(String(USER_ID.park))
  })

  // 조건은 AND다.
  // 테스트 코드: PA-061
  it('ands the conditions', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 파트너 "코어"와 작성자 박영업을 함께 걸어 검색한다
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '코어')
    await user.selectOptions(bar().getByRole('combobox', { name: '작성자' }), '박영업')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 둘 다 맞는 기록만 보인다
    await waitFor(() => expect(shownContents()).toEqual(['견적서 전달']))
  })

  // %와 _ 는 글자 그대로 찾는다.
  // 테스트 코드: PA-061
  it('treats % and _ as plain characters', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 미팅 내용에 "%"를 치고 Enter를 누른다
    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '%{Enter}')
    // then: 맞는 기록이 없어 빈 문구가 보인다
    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
    expect(meetingRows()).toHaveLength(0)
  })

  // 맞는 기록이 없으면 빈 문구가 보인다.
  // 테스트 코드: PA-061
  it('shows the empty message when nothing matches', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 없는 회사로 검색한다
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '없는회사{Enter}')
    // then: 빈 문구가 보인다
    expect(await screen.findByText('기록된 미팅이 없습니다.')).toBeVisible()
  })

  // 틀린 날짜면 검색하지 않고 칸 문구를 보인다.
  // 테스트 코드: PA-062
  it('does not search and marks the field when a date is wrong', async () => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 직접 지정에서 덜 친 시작 날짜로 검색한다
    await openCustomDates(user)
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '202703')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 칸이 틀렸다고 표시되고 주소·목록은 그대로다
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toBeInvalid()
    expect(await bar().findByRole('alert')).toBeVisible()
    expect(location()).toBe(PAGE)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  // 역전된 범위는 서버 문구를 배너로 보인다.
  // 테스트 코드: PA-062
  it('shows the server message when the start is later than the end', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 시작이 끝보다 늦은 범위로 검색한다
    await openCustomDates(user)
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270301')
    await user.click(bar().getByRole('button', { name: '검색' }))
    // then: 서버 문구가 보인다
    expect(await screen.findByText('미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')).toBeVisible()
  })

  // 검색하면 첫 쪽부터 다시 읽는다.
  // 테스트 코드: PA-063
  it('starts from the first page again after a search', async () => {
    // given: 12건을 모두 불러온 상태
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    await waitForRows(12)
    // when: "협의"로 검색한다
    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')
    // then: 검색 결과 2건만 보인다
    await waitFor(() => expect(meetingRows()).toHaveLength(2))
  })

  // 주소로 조건과 결과를 복원한다.
  // 테스트 코드: PA-063
  it('restores the conditions and the results from the URL', async () => {
    // when: 조건이 든 주소로 화면을 연다
    await renderAt(`${PAGE}?partner=${encodeURIComponent('코어')}&from=2027-03-10&author=${USER_ID.kim}`)
    // then: 결과와 검색 칸이 주소의 조건을 따른다
    await waitFor(() => expect(shownContents()).toEqual(['ITDR 가격 협상']))
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('코어')
    expect(bar().getByRole('combobox', { name: '미팅 날짜' })).toHaveDisplayValue('직접 지정')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.10')
    expect(bar().getByRole('combobox', { name: '작성자' })).toHaveValue(String(USER_ID.kim))
  })

  // 초기화는 모든 조건과 주소를 지운다.
  // 테스트 코드: PA-063
  it('clears every condition and the URL on reset', async () => {
    // given: 조건과 정렬이 걸린 주소로 연 화면
    const { user, location } = await renderAt(`${PAGE}?partner=${encodeURIComponent('코어')}&sort=partner&order=asc`)
    await waitFor(() => expect(meetingRows()).toHaveLength(3))
    // when: 초기화를 누른다
    await user.click(bar().getByRole('button', { name: '초기화' }))
    // then: 주소가 경로뿐이고 칸이 비며 기본 첫 10건이 보인다
    await waitForRows(10)
    expect(location()).toBe(PAGE)
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('')
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })
})

describe('검색 칸', () => {
  // 텍스트 칸은 서버 길이(파트너 200자, 내용 100자)로 제한된다.
  // 테스트 코드: PA-058
  it('limits the text conditions to the server lengths', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 두 칸의 maxlength가 200·100이다
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveAttribute('maxlength', '200')
    expect(bar().getByRole('textbox', { name: '미팅 내용' })).toHaveAttribute('maxlength', '100')
  })

  // 정렬만 바뀌면 검색 전 입력이 남는다.
  // 테스트 코드: PA-064
  it('keeps what was typed but not searched yet when only the sort changes', async () => {
    // given: 파트너 칸과 시작 날짜 칸에 검색하지 않은 입력이 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.type(bar().getByRole('textbox', { name: '파트너' }), 'abc')
    await openCustomDates(user)
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '202703')
    // when: 작성자 열 머리글로 정렬한다
    await user.click(within(screen.getByRole('columnheader', { name: '작성자' })).getByRole('button'))
    // then: 정렬만 바뀌고 입력은 남으며 주소에는 조건이 없다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '작성자' })).toHaveAttribute('aria-sort', 'ascending'))
    expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('abc')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03')
    expect(paramsOf(location()).get('partner')).toBeNull() // 검색하지 않았으므로 URL에도 없다
  })

  // 주소가 바깥에서 바뀌면 칸이 따라간다.
  // 테스트 코드: PA-064
  it('still follows the URL when the conditions really change from outside', async () => {
    // given: 파트너 칸에 검색하지 않은 입력이 있다
    const { user, goTo } = await renderAt(PAGE)
    await waitForRows(10)
    await user.type(bar().getByRole('textbox', { name: '파트너' }), 'abc')
    // when: 주소가 바깥에서 조건이 든 주소로 바뀐다
    goTo(`${PAGE}?partner=${encodeURIComponent('코어')}`)
    // then: 파트너 칸이 주소의 값을 따른다
    await waitFor(() => expect(bar().getByRole('textbox', { name: '파트너' })).toHaveValue('코어'))
  })
})

describe('열 머리글 정렬', () => {
  const header = (name: string) => screen.getByRole('columnheader', { name })

  // 네 열 머리글로 정렬할 수 있고 기본은 미팅 날짜 내림차순이다.
  // 테스트 코드: PA-065
  it('makes the four columns sortable and starts on the meeting date, descending', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)
    // then: 네 열에 정렬 버튼이 있고 미팅 날짜만 내림차순이다
    for (const name of ['파트너', '미팅 날짜', '미팅 내용', '작성자']) {
      expect(within(header(name)).getByRole('button')).toBeVisible()
    }
    expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'descending')
    expect(header('파트너')).not.toHaveAttribute('aria-sort')
  })

  // 새 열은 오름차순으로 시작하고 다시 누르면 반대 방향이다.
  // 테스트 코드: PA-065
  it('sorts a text column ascending on the first click and flips on the second', async () => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 파트너 열 머리글을 누른다
    await user.click(within(header('파트너')).getByRole('button'))
    // then: 오름차순으로 정렬되고 주소에 쓰인다
    await waitFor(() => expect(header('파트너')).toHaveAttribute('aria-sort', 'ascending'))
    expect(shownContents().slice(0, 2)).toEqual(['견적 재요청', 'EDR 교체 일정']) // 넷브릿지: 같은 파트너는 미팅 날짜 내림차순
    expect(paramsOf(location()).get('sort')).toBe('partner')
    expect(paramsOf(location()).get('order')).toBe('asc')

    // when: 파트너 열 머리글을 다시 누른다
    await user.click(within(header('파트너')).getByRole('button'))
    // then: 내림차순으로 바뀌고 미팅 날짜 열의 정렬 표시는 사라진다
    await waitFor(() => expect(header('파트너')).toHaveAttribute('aria-sort', 'descending'))
    expect(shownContents().slice(0, 2)).toEqual(['ITDR 가격 협상', '견적서 전달']) // 코어테크
    expect(header('미팅 날짜')).not.toHaveAttribute('aria-sort')
  })

  // 미팅 날짜 열은 누르면 오름차순, 다시 누르면 내림차순이다.
  // 테스트 코드: PA-065
  it('flips the meeting date to ascending with a click and back to descending with another', async () => {
    // given: 목록이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 미팅 날짜 열 머리글을 누른다
    await user.click(within(header('미팅 날짜')).getByRole('button'))
    // then: 오름차순이고 가장 오래된 기록이 맨 위다
    await waitFor(() => expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'ascending'))
    expect(shownContents()[0]).toBe('킥오프 일정 협의')
    // when: 다시 누른다
    await user.click(within(header('미팅 날짜')).getByRole('button'))
    // then: 내림차순으로 돌아와 가장 최근 기록이 맨 위다
    await waitFor(() => expect(header('미팅 날짜')).toHaveAttribute('aria-sort', 'descending'))
    expect(shownContents()[0]).toBe('계약 종료 후 정리')
  })

  // 미팅 내용·작성자 열도 머리글로 정렬되고 주소에 쓰인다.
  // 테스트 코드: PA-065
  it.each([
    ['미팅 내용', 'content'],
    ['작성자', 'author'],
  ])('sorts by %s and writes sort=%s to the URL', async (label, value) => {
    // given: 목록이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 그 열 머리글을 누른다
    await user.click(within(header(label)).getByRole('button'))
    // then: 오름차순이 되고 주소에 sort가 쓰인다
    await waitFor(() => expect(header(label)).toHaveAttribute('aria-sort', 'ascending'))
    expect(paramsOf(location()).get('sort')).toBe(value)
  })

  // 더 불러온 뒤 정렬을 바꾸면 첫 10건부터 다시 읽는다.
  // 테스트 코드: PA-066
  it('restarts from the first ten when the sort changes after loading more', async () => {
    // given: 12건을 모두 불러온 상태
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(screen.getByRole('button', { name: '더 보기' }))
    await waitForRows(12)
    // when: 미팅 내용 열로 정렬한다
    await user.click(within(header('미팅 내용')).getByRole('button'))
    // then: 첫 10건만 보인다
    await waitFor(() => expect(meetingRows()).toHaveLength(10))
  })

  // 주소의 정렬을 복원한다.
  // 테스트 코드: PA-066
  it('restores the sort from the URL', async () => {
    // when: 정렬이 든 주소로 화면을 연다
    await renderAt(`${PAGE}?sort=content&order=asc`)
    // then: 그 정렬로 보인다
    await waitForRows(10)
    expect(header('미팅 내용')).toHaveAttribute('aria-sort', 'ascending')
    expect(shownContents()[0]).toBe('EDR 교체 일정')
  })

  // 검색해도 정렬이 유지된다.
  // 테스트 코드: PA-066
  it('keeps the sort when a condition is searched', async () => {
    // given: 파트너 오름차순으로 연 화면
    const { user, location } = await renderAt(`${PAGE}?sort=partner&order=asc`)
    await waitForRows(10)
    // when: 미팅 내용으로 검색한다
    await user.type(bar().getByRole('textbox', { name: '미팅 내용' }), '협의{Enter}')
    // then: 정렬이 주소와 머리글에 그대로다
    await waitFor(() => expect(meetingRows()).toHaveLength(2))
    expect(paramsOf(location()).get('sort')).toBe('partner')
    expect(header('파트너')).toHaveAttribute('aria-sort', 'ascending')
  })
})

describe('옛 주소의 Deal 조건', () => {
  // 예전 주소의 deal은 무시하고 sort=deal은 기본 정렬로 열며 Deal을 서버에 보내지 않는다.
  // 테스트 코드: PA-067
  it('ignores ?deal= and opens ?sort=deal with the default sort, sending no deal to the server', async () => {
    // given: 목록 요청을 관찰한다
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    // when: 예전 deal·sort=deal이 든 주소로 화면을 연다
    await renderAt(`${PAGE}?deal=itdr&sort=deal&order=asc`)
    // then: 조건 없이 기본 정렬로 보이고 요청에 deal이 없다
    await waitForRows(10)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10)) // 조건 없이 기본 정렬(미팅 날짜 내림차순)
    expect(screen.getByRole('columnheader', { name: '미팅 날짜' })).toHaveAttribute('aria-sort', 'descending')
    for (const call of list.mock.calls) {
      expect(Object.keys(call[0])).not.toContain('deal')
      expect(call[0].sort).not.toBe('deal')
    }
    list.mockRestore()
  })

  // 검색해도 주소에 deal을 쓰지 않는다.
  // 테스트 코드: PA-067
  it('does not write deal to the URL when a search is made', async () => {
    // given: 예전 deal이 든 주소로 연 화면
    const { user, location } = await renderAt(`${PAGE}?deal=itdr`)
    await waitForRows(10)
    // when: 파트너로 검색한다
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '코어{Enter}')
    // then: 주소에 partner만 있고 deal은 없다
    await waitFor(() => expect(paramsOf(location()).get('partner')).toBe('코어'))
    expect(paramsOf(location()).has('deal')).toBe(false)
  })
})
