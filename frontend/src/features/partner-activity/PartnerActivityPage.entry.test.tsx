import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  TODAY_TEXT,
  choosePartner,
  entryGroup,
  fieldsOf,
  openEntryDialog,
  pinClock,
  unpinClock,
  waitForRows,
} from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

describe('미팅 내용 입력 팝업 열기', () => {
  // 입력 팝업은 빈 행 하나·파트너 포커스·오늘 날짜로 열린다.
  // 테스트 코드: PA-075, PA-094
  it('opens a dialog with one empty row, focus on the partner, and today as the default date', async () => {
    // given: sales로 연 목록 화면
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    // when: 미팅 내용 입력 버튼을 눌러 팝업을 연다
    const dialog = await openEntryDialog(user)

    // then: 빈 행 하나, 파트너 칸 포커스, 오늘 날짜이고 저장·취소만 제공한다
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    const { partner, date, content } = fieldsOf(dialog, 1)
    await waitFor(() => expect(partner).toHaveFocus())
    expect(partner).toHaveValue('')
    expect(date).toHaveValue(TODAY_TEXT)
    expect(content).toHaveValue('')
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeEnabled()
    expect(within(dialog).getByRole('button', { name: '취소' })).toBeVisible()
    expect(within(dialog).queryByRole('button', { name: '행 추가' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: '행 삭제' })).not.toBeInTheDocument()
  })

  // admin도 팝업을 연다.
  // 테스트 코드: PA-075
  it('gives the dialog to admin as well', async () => {
    // given: admin으로 연 목록 화면
    const { user } = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)

    // when: 입력 버튼을 눌러 팝업을 연다
    const dialog = await openEntryDialog(user)
    // then: 팝업이 보인다
    expect(dialog).toBeVisible()
  })

  // user에게는 입력 버튼이 없어 팝업을 열 수 없다.
  // 테스트 코드: PA-075
  it('does not open for a read-only user because the button is not there', async () => {
    // when: user 역할로 목록 화면을 연다
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)

    // then: 입력 버튼이 없다
    expect(screen.queryByRole('button', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
  })
})

describe('파트너 선택', () => {
  // 파트너 칸은 등록된 회사 목록을 보여 준다.
  // 테스트 코드: PA-077
  it('lists the registered partner companies', async () => {
    // given: 입력 팝업이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    // when: 파트너 칸을 연다
    await user.click(fieldsOf(dialog, 1).partner)

    // then: 등록된 파트너 회사 다섯 곳이 목록에 있다
    const names = within(await within(dialog).findByRole('listbox', { name: '파트너' }))
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect([...names].sort()).toEqual(['넷브릿지', '디지털웨이', '시큐어원', '에이원시스템', '코어테크'])
  })

  // 친 글자로 파트너 목록이 좁혀진다.
  // 테스트 코드: PA-077
  it('narrows the partner list by what is typed', async () => {
    // given: 입력 팝업이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    // when: 파트너 칸에 "코어"를 친다
    await user.type(fieldsOf(dialog, 1).partner, '코어')

    // then: 목록이 한 곳으로 좁혀진다
    expect(within(await within(dialog).findByRole('listbox', { name: '파트너' })).getAllByRole('option')).toHaveLength(1)
  })

  // 행에는 Deal 칸이 없다.
  // 테스트 코드: PA-077
  it('has no Deal field and the row order is partner, date, content', async () => {
    // given: 입력 팝업이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    // when: 입력 팝업을 연다
    const dialog = await openEntryDialog(user)
    // then: 행의 칸에 Deal이 없다
    expect(within(dialog).queryByRole('combobox', { name: 'Deal' })).not.toBeInTheDocument()
    const names = within(entryGroup(dialog, 1))
      .getAllByRole('combobox')
      .concat(within(entryGroup(dialog, 1)).getAllByRole('textbox'))
      .map((el) => el.getAttribute('aria-label') ?? el.getAttribute('name') ?? '')
    expect(names).not.toContain('Deal')
  })

  // 파트너를 고르면 날짜 칸으로 포커스가 간다.
  // 테스트 코드: PA-077
  it('moves the focus to the date field once a partner is chosen', async () => {
    // given: 입력 팝업이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    // when: 파트너를 고른다
    await choosePartner(user, dialog, 1, '코어테크')

    // then: 날짜 칸에 포커스가 있다
    await waitFor(() => expect(fieldsOf(dialog, 1).date).toHaveFocus())
  })

})
