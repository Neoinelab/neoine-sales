import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { addDays, compactDate } from '../../../shared/model/dates'
import { openRegisterForm } from '../../../test/actionFormUtils'
import { detailPath } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 추가 팝업의 수행일 칸(AC-R40·R41·R42). 서버 시계는 2026-11-13T14:30+09:00(오늘 2026-11-13)로 고정한다.
 * 시드 Deal 1(한빛은행 ITDR 도입)은 오늘보다 한참 전에 등록되었고 기준 행(id 4)은 김영업의 Open Next Action이며
 * 이틀 전(2026-11-11)에 수행되었다.
 */
const NOW = '2026-11-13T14:30:00+09:00'
const TODAY = '2026-11-13'
const TITLE = '한빛은행 ITDR 도입'
const FUTURE = '수행일은 오늘 이후로 지정할 수 없습니다.'
const FILL = '이전 Next Action을 진행사항에 채우기'
const CHECKBOX = '저장 시 이전 Next Action을 종료(수행)로 바꿈'
const BASIS_ID = 4

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

type Form = Awaited<ReturnType<typeof openRegisterForm>>

const dateField = (form: HTMLElement) => within(form).getByLabelText('수행일')

/** 수행일 칸을 비우고 새 값을 친다(빈 문자열이면 비우기만). */
async function setActedOn(view: Form, text: string) {
  const field = dateField(view.form)
  await view.user.clear(field)
  if (text !== '') await view.user.type(field, text)
}

async function fillContent(view: Form) {
  await view.user.type(within(view.form).getByLabelText('유형'), '미팅')
  await view.user.type(within(view.form).getByLabelText('진행사항'), '수행일 확인')
}

const submit = (view: Form) => view.user.click(within(view.form).getByRole('button', { name: '등록' }))

/** 열려 있는 Deal 1의 등록일(서버 오프셋 벽시계 날짜). */
async function registeredDay(): Promise<string> {
  const code = await (await import('../../../test/detailTestUtils')).dealCodeOf(1)
  const deal = await gateway.deals.get(code)
  return deal.createdAt.slice(0, 10)
}

describe('시드 전제', () => {
  // 이 파일의 날짜 케이스가 기대는 시드 사실: 기준 행(id 4)의 수행일은 2026-11-11이고 Deal은 한참 전에 등록되었다.
  it('has the basis row performed on 2026-11-11 and a Deal registered well before it', async () => {
    // when: Deal 1의 Action 목록과 등록일을 읽는다
    const code = await (await import('../../../test/detailTestUtils')).dealCodeOf(1)
    const basis = (await gateway.actions.list(code, {})).find((a) => a.id === BASIS_ID)
    // then: 기준 행은 11-11에 수행되었고 등록일은 11-05보다 앞이다
    expect(basis?.actedOn).toBe('2026-11-11')
    expect((await registeredDay()) < '2026-11-05').toBe(true)
  })
})

describe('Action 추가 팝업의 수행일 칸', () => {
  // 추가 팝업에는 오늘로 채운 수행일 칸이 안내 아래·3열 그룹 위에 있다.
  // 테스트 코드: AC-105, AC-074
  it('shows the performed-day field filled with today above the Status group', async () => {
    // when: sales가 추가 팝업을 연다 (전제: 서버 시계의 오늘은 2026-11-13)
    const view = await openRegisterForm(1, TITLE)

    // then: 안내 "담당자: 김영업"이 보이고 23:59 안내는 없다
    expect(within(view.dialog).getByText(/담당자: 김영업/)).toBeVisible()
    expect(within(view.dialog).queryByText(/23:59/)).not.toBeInTheDocument()
    // then: 수행일 칸이 오늘 날짜로 채워져 있다
    const field = dateField(view.form)
    expect(field).toHaveValue('2026.11.13')
    // then: 수행일 칸은 "Status · Forecast · 유형" 그룹보다 앞(위)에 있다
    const group = within(view.form).getByRole('group', { name: 'Status · Forecast · 유형' })
    expect(field.compareDocumentPosition(group) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  // 수정 팝업에는 수행일 칸이 없고 "수행일: YYYY-MM-DD" 안내가 있다.
  // 테스트 코드: AC-105
  it('has no performed-day field in the edit popup and shows the 수행일 date note', async () => {
    // given: sales가 Actions 탭을 연다
    const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
    await screen.findByRole('heading', { level: 1, name: TITLE })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    // when: 자기 행의 "수정"을 누른다
    const row = within(table).getAllByRole('row')[1] as HTMLElement
    await view.user.click(within(row).getByRole('button', { name: '수정' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 수정' })
    // then: 수행일 칸이 없고 "수행일: YYYY-MM-DD · 담당자: …" 안내가 있다
    expect(within(dialog).queryByLabelText('수행일')).not.toBeInTheDocument()
    expect(within(dialog).getByText(/수행일: \d{4}-\d{2}-\d{2} · 담당자: /)).toBeVisible()
  })
})

describe('수행일을 보내는 방식', () => {
  // 수행일을 그대로 두면 acted_on을 보내지 않는다.
  // 테스트 코드: AC-106
  it('does not send actedOn when the day is left as today', async () => {
    // given: 추가 팝업(요청 감시)에 내용을 채운다
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    await fillContent(view)
    // when: 수행일을 그대로 두고 등록한다
    await submit(view)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 요청에 actedOn이 없다
    expect(create.mock.calls[0]?.[1].actedOn).toBeUndefined()
  })

  // 지난 날짜를 yyyymmdd로 치면 그 ISO 날짜를 보내고 목록에 그 날짜(YYYY-MM-DD)로 보인다.
  // 테스트 코드: AC-106
  it('sends the past day as an ISO date and lists it as that date', async () => {
    // given: 추가 팝업(요청 감시)에 내용을 채운다
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    await fillContent(view)
    const past = addDays(TODAY, -5)
    expect(await registeredDay() < past).toBe(true) // 전제: 등록일이 수행일보다 앞선다
    // when: 수행일에 그 날짜를 치고 등록한다
    await setActedOn(view, compactDate(past))
    await submit(view)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 요청의 actedOn이 ISO 날짜다
    expect(create.mock.calls[0]?.[1]).toMatchObject({ actedOn: past })
    // then: 목록에 수행일 칸이 그 날짜 YYYY-MM-DD인 행이 보이고 시:분 표기가 없다
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await waitFor(() => expect(within(table).getByText(past)).toBeVisible())
    expect(within(table).queryByText(/23:59/)).not.toBeInTheDocument()
  })
})

describe('수행일 화면 검증', () => {
  const cases = [
    ['비움', '', '수행일을 입력하세요.'],
    ['덜 친 날짜', '2026.11', '날짜를 yyyymmdd 형식으로 입력하세요.'],
    ['내일', compactDate(addDays(TODAY, 1)), FUTURE],
  ] as const

  // 빈·틀린·미래 수행일은 문구와 함께 막고, 포커스가 수행일 칸이며, 요청하지 않는다(유형이 비어 있어도 수행일이 먼저).
  // 테스트 코드: AC-107, AC-075
  it.each(cases)('blocks %s with its message and focuses the field without a request', async (_name, typed, message) => {
    // given: 추가 팝업(요청 감시), 유형은 비어 있다
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    // when: 수행일을 바꾸고 등록을 누른다
    await setActedOn(view, typed)
    await submit(view)
    // then: 수행일 칸 아래에 문구가 보이고 오류 표시·포커스가 수행일 칸에 있다
    expect(await within(view.form).findByText(message)).toBeVisible()
    expect(dateField(view.form)).toHaveAttribute('aria-invalid', 'true')
    expect(dateField(view.form)).toHaveFocus()
    // then: 요청이 없고 팝업은 열려 있다
    expect(create).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
  })

  // Deal 등록일 전날은 등록일이 든 문구로 막는다.
  // 테스트 코드: AC-107
  it('blocks a day before the Deal registration day with the registration date in the message', async () => {
    // given: 추가 팝업(요청 감시)과 Deal 1의 등록일
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    const registered = await registeredDay()
    // when: 등록일 전날을 수행일로 치고 등록한다
    await setActedOn(view, compactDate(addDays(registered, -1)))
    await submit(view)
    // then: 등록일이 든 문구가 보이고 포커스가 수행일 칸이며 요청이 없다
    expect(await within(view.form).findByText(`수행일은 Deal 등록일(${registered}) 이전으로 지정할 수 없습니다.`)).toBeVisible()
    expect(dateField(view.form)).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
  })
})

describe('수행일과 이전 Next Action 종료', () => {
  const EARLY = '이전 Next Action의 수행일(2026-11-11)보다 앞선 날짜로는 이전 Next Action을 종료할 수 없습니다.'

  // 종료 체크가 켜진 채 기준 행보다 앞선 수행일이면 막고, 체크를 끄면 등록된다.
  // 테스트 코드: AC-108
  it('blocks an earlier day while the close checkbox is on and registers once it is off', async () => {
    // given: 이전 Next Action을 채워 종료 체크가 켜진 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    await view.user.click(within(view.dialog).getByRole('button', { name: FILL }))
    await view.user.type(within(view.form).getByLabelText('유형'), '미팅')
    const checkbox = within(view.dialog).getByRole('checkbox', { name: CHECKBOX })
    expect(checkbox).toBeChecked()
    // when: 수행일을 기준 행 전날(2026-11-10)로 바꾸고 등록한다
    await setActedOn(view, '20261110')
    await submit(view)
    // then: 기준 행 수행일이 든 문구가 수행일 칸 아래에 보이고 요청이 없다
    expect(await within(view.form).findByText(EARLY)).toBeVisible()
    expect(dateField(view.form)).toHaveFocus()
    expect(create).not.toHaveBeenCalled()

    // when: 체크를 끄고 다시 등록한다
    await view.user.click(checkbox)
    await submit(view)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 닫을 id 없이 actedOn 2026-11-10으로 등록된다
    const sent = create.mock.calls[0]?.[1]
    expect(sent?.actedOn).toBe('2026-11-10')
    expect(sent?.closePreviousNextActionId).toBeUndefined()
    // then: 기준 행은 Open 그대로다
    const basis = (await gateway.actions.list(create.mock.calls[0]?.[0] ?? '', {})).find((a) => a.id === BASIS_ID)
    expect(basis?.nextActionStatus).toBe('open')
  })

  // 기준 행과 같은 날 수행일은 체크가 켜진 채로도 등록된다.
  // 테스트 코드: AC-108
  it('registers on the same day as the basis row with the checkbox on and closes it', async () => {
    // given: 이전 Next Action을 채워 종료 체크가 켜진 추가 팝업(요청 감시)
    const create = vi.spyOn(gateway.actions, 'create')
    const view = await openRegisterForm(1, TITLE)
    await view.user.click(within(view.dialog).getByRole('button', { name: FILL }))
    await view.user.type(within(view.form).getByLabelText('유형'), '미팅')
    // when: 수행일을 기준 행과 같은 날(2026-11-11)로 바꾸고 등록한다
    await setActedOn(view, '20261111')
    await submit(view)
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    // then: 닫을 id와 actedOn을 함께 보낸다
    expect(create.mock.calls[0]?.[1]).toMatchObject({ actedOn: '2026-11-11', closePreviousNextActionId: BASIS_ID })
  })
})
