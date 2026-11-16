import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { addDays, compactDate } from '../../../shared/model/dates'
import { DETAIL, bodyRows, fieldValue, openActionsTab, openDetail, type DetailView } from '../../../test/actionDetail'
import { resetMock } from '../../../test/fake/default'

/**
 * Action 상세 팝업의 수행일 칸(AC-R47·R50·R51). 서버 시계는 2026-11-13T14:30+09:00(오늘 2026-11-13)로 고정한다.
 * 시드 Deal 1은 한참 전에 등록되었고 김영업의 예전 Action "임원 보고용 ROI 자료 전달"이 있다.
 * 기준 행(Open Next Action)은 2026-11-11에 수행되었다.
 */
const NOW = '2026-11-13T14:30:00+09:00'
const TODAY = '2026-11-13'
const TARGET_PROGRESS = '임원 보고용 ROI 자료 전달'
const FUTURE = '수행일은 오늘 이후로 지정할 수 없습니다.'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })
const dotted = (day: string) => day.replaceAll('-', '.')

/** 수정 대상 Action(김영업의 예전 Action)의 상세 팝업을 열고 Deal 등록일을 함께 돌려준다. */
async function openTarget() {
  const view = await openActionsTab()
  const target = (await gateway.actions.list(view.code, {})).find((a) => a.progress === TARGET_PROGRESS)
  if (!target) throw new Error('시드 Action 없음')
  const registered = (await gateway.deals.get(view.code)).createdAt.slice(0, 10)
  const dialog = await openDetail(view, TARGET_PROGRESS)
  return { view, target, registered, dialog }
}

/** 수행일 편집을 열어 값을 바꾸고 Enter를 누른다(빈 문자열이면 비우기만). */
async function setActedOn(view: DetailView, text: string) {
  await view.user.click(within(detail()).getByRole('button', { name: '수행일 수정' }))
  const field = within(detail()).getByLabelText('수행일')
  await view.user.clear(field)
  await view.user.type(field, `${text}{Enter}`)
}

describe('수행일 값과 편집 칸', () => {
  // 목록 수행일 칸은 YYYY-MM-DD이고 시각이 없으며 상세 팝업 수행일 편집 칸은 같은 날짜(yyyy.mm.dd)다.
  // 테스트 코드: AC-116
  it('shows the acted day as YYYY-MM-DD without a time in the list and as the same date in the popup edit field', async () => {
    // given: 수행일이 2026-11-10인 김영업의 Action
    const view = await openActionsTab()
    const original = gateway.actions.list.bind(gateway.actions)
    vi.spyOn(gateway.actions, 'list').mockImplementation(async (code, query) =>
      (await original(code, query)).map((a, i) => (i === 0 ? { ...a, progress: '날짜 확인', actedOn: '2026-11-10' } : a)),
    )
    await view.client.invalidateQueries()
    await screen.findByText('날짜 확인')

    // when: 그 행을 눌러 팝업을 열고 "수행일 수정"을 누른다
    const dialog = await openDetail(view, '날짜 확인')
    await view.user.click(within(dialog).getByRole('button', { name: '수행일 수정' }))

    // then: 목록 수행일 칸은 "2026-11-10"이고 시:분이 없다
    expect(within(view.table).getAllByRole('columnheader')[0]).toHaveTextContent('수행일')
    expect(within(bodyRows(view.table)[0]!).getAllByRole('cell')[0]).toHaveTextContent(/^2026-11-10$/)
    expect(within(view.table).queryByText(/\d{1,2}:\d{2}/)).not.toBeInTheDocument()
    // then: 팝업 수행일 편집 칸은 그 날짜이고 시각은 어디에도 없다
    expect(within(dialog).getByLabelText('수행일')).toHaveValue('2026.11.10')
    expect(within(dialog).queryByText(/\d{1,2}:\d{2}/)).not.toBeInTheDocument()
  })
})

describe('상세 팝업에서 수행일을 보내는 방식', () => {
  // 다른 칸 저장에는 acted_on이 없고, 수행일을 바꾸면 ISO 날짜로 보내며 행이 바뀐 날짜 자리에 보인다.
  // 테스트 코드: AC-129
  it('does not send actedOn for other fields and sends the ISO day when changed, moving the row to its new place', async () => {
    // given: 수정 요청을 감시하는 상세 팝업
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openTarget()

    // when: 진행사항만 고쳐 Enter를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const progress = within(dialog).getByLabelText('진행사항')
    await view.user.clear(progress)
    await view.user.type(progress, '수행일 그대로{Enter}')
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    // then: 요청에 actedOn이 없다
    expect(update.mock.calls[0]?.[1]).not.toHaveProperty('actedOn')
    await waitFor(() => expect(fieldValue(detail(), '진행사항')).toHaveTextContent('수행일 그대로'))

    // when: 이어서 수행일을 오늘로 바꿔 Enter를 누른다
    await setActedOn(view, compactDate(TODAY))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
    // then: 요청의 actedOn이 ISO 날짜이고 팝업 수행일도 그 날짜다
    expect(update.mock.calls[1]?.[1]).toMatchObject({ actedOn: TODAY })
    await waitFor(() => expect(fieldValue(detail(), '수행일')).toHaveTextContent(TODAY))
    expect(await screen.findByText('Action이 수정되었습니다.')).toBeVisible()

    // when: 팝업을 닫는다
    await view.user.click(within(detail()).getByRole('button', { name: '닫기' }))
    // then: 그 행이 오늘 날짜로 목록 맨 위에 보인다
    await waitFor(() => {
      const first = bodyRows(view.table)[0]!
      expect(first).toHaveTextContent('수행일 그대로')
      expect(within(first).getAllByRole('cell')[0]).toHaveTextContent(new RegExp(`^${TODAY}$`))
    })
  })
})

describe('상세 팝업 수행일 화면 검증', () => {
  const cases = [
    ['비움', () => '', '수행일을 입력하세요.'],
    ['덜 친 날짜', () => '2026.11', '날짜를 yyyymmdd 형식으로 입력하세요.'],
    ['내일', () => compactDate(addDays(TODAY, 1)), FUTURE],
  ] as const

  // 빈·틀린·미래 수행일은 칸 아래 문구로 막고 편집이 열린 채 요청하지 않는다.
  // 테스트 코드: AC-130
  it.each(cases)('blocks %s with its message under the field without a request', async (_name, typed, message) => {
    // given: 수정 요청을 감시하는 상세 팝업
    const update = vi.spyOn(gateway.actions, 'update')
    const { view } = await openTarget()

    // when: 수행일을 바꿔 Enter를 누른다
    await setActedOn(view, typed())

    // then: 문구가 보이고 편집이 열려 있으며 요청이 없다
    expect(await within(detail()).findByText(message)).toBeVisible()
    expect(within(detail()).getByLabelText('수행일')).toBeVisible()
    expect(update).not.toHaveBeenCalled()
  })

  // Deal 등록일 전날은 등록일이 든 문구로 막고, 등록일 당일은 기준 행보다 앞서도 보낸다.
  // 테스트 코드: AC-130
  it('blocks the day before the Deal registration day and lets the registration day through even though it is earlier than the basis row', async () => {
    // given: 수정 요청을 감시하는 상세 팝업 (전제: 등록일은 기준 행 수행일 11-11보다 앞선다)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, registered } = await openTarget()
    expect(registered < '2026-11-11').toBe(true)

    // when: 등록일 전날을 수행일로 쳐 Enter를 누른다
    await setActedOn(view, compactDate(addDays(registered, -1)))
    // then: 등록일이 든 문구가 보이고 요청이 없다
    expect(await within(detail()).findByText(`수행일은 Deal 등록일(${registered}) 이전으로 지정할 수 없습니다.`)).toBeVisible()
    expect(update).not.toHaveBeenCalled()

    // when: 등록일 당일(기준 행 11-11보다 앞선 날짜)로 고쳐 Enter를 누른다
    const field = within(detail()).getByLabelText('수행일')
    await view.user.clear(field)
    await view.user.type(field, `${compactDate(registered)}{Enter}`)
    // then: 기준 행과 비교하지 않고 그 ISO 날짜를 보낸다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ actedOn: registered })
  })
})

describe('상세 팝업 수행일 저장 실패', () => {
  // 서버가 수행일을 거절하면 수행일 칸 아래 서버 문구로 보이고 팝업과 입력이 남는다.
  // 테스트 코드: AC-141
  it('shows a server rejection of the performed day under the field and keeps the popup and the input', async () => {
    // given: 서버가 수정 요청을 수행일 오류로 거절한다
    const { view } = await openTarget()
    vi.spyOn(gateway.actions, 'update').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail: FUTURE }),
    )

    // when: 수행일을 오늘로 바꿔 Enter를 누른다
    await setActedOn(view, compactDate(TODAY))

    // then: 팝업 안에 서버 문구가 보이고 입력과 팝업이 남는다
    expect(await within(detail()).findByText(FUTURE)).toBeVisible()
    expect(within(detail()).getByLabelText('수행일')).toHaveValue(dotted(TODAY))
  })
})
