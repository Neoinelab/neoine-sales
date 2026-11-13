import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { addDays, compactDate } from '../../../shared/model/dates'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 수정 팝업의 수행일 칸(AC-R30·R40·R45~R47). 서버 시계는 2026-11-13T14:30+09:00(오늘 2026-11-13)로 고정한다.
 * 시드 Deal 1은 한참 전에 등록되었고 김영업의 예전 Action "임원 보고용 ROI 자료 전달"이 있다.
 * 기준 행(id 4, Open Next Action)은 2026-11-11에 수행되었다.
 */
const NOW = '2026-11-13T14:30:00+09:00'
const TODAY = '2026-11-13'
const TITLE = '한빛은행 ITDR 도입'
const TARGET_PROGRESS = '임원 보고용 ROI 자료 전달'
const FUTURE = '수행일은 오늘 이후로 지정할 수 없습니다.'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

/** 시드의 수정 대상 Action(김영업의 예전 Action)과 Deal 1의 등록일. */
async function seedTarget() {
  const code = await dealCodeOf(1)
  const target = (await gateway.actions.list(code, {})).find((a) => a.progress === TARGET_PROGRESS)
  if (!target) throw new Error('시드 Action 없음')
  const registered = (await gateway.deals.get(code)).createdAt.slice(0, 10)
  return { code, target, registered }
}

const dotted = (day: string) => day.replaceAll('-', '.')

/** sales가 Actions 탭에서 수정 대상 행의 "수정" 팝업을 연다. */
async function openEdit() {
  const seed = await seedTarget()
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: TITLE })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  const row = within(table).getByText(TARGET_PROGRESS).closest('tr') as HTMLElement
  await view.user.click(within(row).getByRole('button', { name: '수정' }))
  const dialog = await screen.findByRole('dialog', { name: 'Action 수정' })
  const form = within(dialog).getByRole('form', { name: 'Action 수정' })
  return { ...view, ...seed, table, dialog, form }
}

type Edit = Awaited<ReturnType<typeof openEdit>>

const dateField = (edit: Edit) => within(edit.form).getByLabelText('수행일')
const save = (edit: Edit) => edit.user.click(within(edit.form).getByRole('button', { name: '저장' }))

/** 수행일 칸을 비우고 새 값을 친다(빈 문자열이면 비우기만). */
async function setActedOn(edit: Edit, text: string) {
  const field = dateField(edit)
  await edit.user.clear(field)
  if (text !== '') await edit.user.type(field, text)
}

describe('Action 수정 팝업의 수행일 칸', () => {
  // 수정 팝업에는 그 Action의 수행일로 채운 수행일 칸이 유형 칸 위에 있고 안내는 담당자만 보인다.
  // 테스트 코드: AC-128, AC-116
  it('shows the performed-day field filled with the action day above the type field, with only the actor in the note', async () => {
    // given: sales가 예전 Action의 수정 팝업을 연다 (전제: 서버 시계의 오늘은 2026-11-13)
    const edit = await openEdit()
    expect(edit.target.actedOn).not.toBe(TODAY) // 전제: 오늘이 아닌 예전 수행일이다

    // then: 수행일 칸이 그 Action의 수행일(yyyy.mm.dd)로 채워져 있다
    const field = dateField(edit)
    expect(field).toHaveValue(dotted(edit.target.actedOn))
    // then: 수행일 칸은 유형 칸보다 앞(위)에 있다
    const typeField = within(edit.form).getByLabelText('유형')
    expect(field.compareDocumentPosition(typeField) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // then: 안내는 담당자와 History 문구뿐이고 "수행일: YYYY-MM-DD" 글은 없다
    expect(within(edit.dialog).getByText(/담당자: 김영업/)).toBeVisible()
    expect(within(edit.dialog).getByText(/Deal History에 기록됩니다/)).toBeVisible()
    expect(within(edit.dialog).queryByText(/수행일: \d{4}-\d{2}-\d{2}/)).not.toBeInTheDocument()
  })
})

describe('수정에서 수행일을 보내는 방식', () => {
  // 수행일을 그대로 두면 acted_on을 보내지 않고, 바꾸면 ISO 날짜로 보내며 행이 바뀐 날짜 자리에 보인다.
  // 테스트 코드: AC-129
  it('does not send actedOn when left as is, and sends the ISO day when changed, moving the row to its new place', async () => {
    // given: 수정 요청을 감시하는 수정 팝업, 진행사항만 고친다
    const update = vi.spyOn(gateway.actions, 'update')
    const edit = await openEdit()
    const progress = within(edit.form).getByLabelText('진행사항')
    await edit.user.clear(progress)
    await edit.user.type(progress, '수행일 그대로')
    // when: 수행일을 그대로 두고 저장한다
    await save(edit)
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    // then: 요청에 actedOn이 없다
    expect(update.mock.calls[0]?.[1]).not.toHaveProperty('actedOn')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 수정' })).not.toBeInTheDocument())

    // when: 다시 그 행을 열어 수행일을 오늘로 바꾸고 저장한다
    const row = within(edit.table).getByText('수행일 그대로').closest('tr') as HTMLElement
    await edit.user.click(within(row).getByRole('button', { name: '수정' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 수정' })
    const field = within(dialog).getByLabelText('수행일')
    await edit.user.clear(field)
    await edit.user.type(field, compactDate(TODAY))
    await edit.user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
    // then: 요청의 actedOn이 ISO 날짜다
    expect(update.mock.calls[1]?.[1]).toMatchObject({ actedOn: TODAY })
    // then: 알림이 보이고 그 행이 오늘 날짜로 목록 맨 위에 보인다
    expect(await screen.findByText('Action이 수정되었습니다.')).toBeVisible()
    await waitFor(() => {
      const first = within(edit.table).getAllByRole('row')[1] as HTMLElement
      expect(first).toHaveTextContent('수행일 그대로')
      expect(within(first).getAllByRole('cell')[0]).toHaveTextContent(new RegExp(`^${TODAY}$`))
    })
  })
})

describe('수정 수행일 화면 검증', () => {
  const cases = [
    ['비움', () => '', '수행일을 입력하세요.'],
    ['덜 친 날짜', () => '2026.11', '날짜를 yyyymmdd 형식으로 입력하세요.'],
    ['내일', () => compactDate(addDays(TODAY, 1)), FUTURE],
  ] as const

  // 빈·틀린·미래 수행일은 문구와 함께 막고, 포커스가 수행일 칸이며, 요청하지 않는다.
  // 테스트 코드: AC-130
  it.each(cases)('blocks %s with its message and focuses the field without a request', async (_name, typed, message) => {
    // given: 수정 요청을 감시하는 수정 팝업
    const update = vi.spyOn(gateway.actions, 'update')
    const edit = await openEdit()
    // when: 수행일을 바꾸고 저장한다
    await setActedOn(edit, typed())
    await save(edit)
    // then: 문구가 보이고 오류 표시·포커스가 수행일 칸에 있다
    expect(await within(edit.form).findByText(message)).toBeVisible()
    expect(dateField(edit)).toHaveAttribute('aria-invalid', 'true')
    expect(dateField(edit)).toHaveFocus()
    // then: 요청이 없고 팝업은 열려 있다
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog', { name: 'Action 수정' })).toBeVisible()
  })

  // Deal 등록일 전날은 등록일이 든 문구로 막고, 등록일 당일은 기준 행보다 앞서도 보낸다.
  // 테스트 코드: AC-130
  it('blocks the day before the Deal registration day and lets the registration day through even though it is earlier than the basis row', async () => {
    // given: 수정 요청을 감시하는 수정 팝업 (전제: 등록일은 기준 행 수행일 11-11보다 앞선다)
    const update = vi.spyOn(gateway.actions, 'update')
    const edit = await openEdit()
    expect(edit.registered < '2026-11-11').toBe(true)
    // when: 등록일 전날을 수행일로 치고 저장한다
    await setActedOn(edit, compactDate(addDays(edit.registered, -1)))
    await save(edit)
    // then: 등록일이 든 문구가 보이고 포커스가 수행일 칸이며 요청이 없다
    expect(await within(edit.form).findByText(`수행일은 Deal 등록일(${edit.registered}) 이전으로 지정할 수 없습니다.`)).toBeVisible()
    expect(dateField(edit)).toHaveFocus()
    expect(update).not.toHaveBeenCalled()

    // when: 등록일 당일(기준 행 11-11보다 앞선 날짜)로 고쳐 다시 저장한다
    await setActedOn(edit, compactDate(edit.registered))
    await save(edit)
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    // then: 기준 행과 비교하지 않고 그 ISO 날짜를 보낸다
    expect(update.mock.calls[0]?.[1]).toMatchObject({ actedOn: edit.registered })
  })

  // 서버가 수행일을 거절하면 팝업 안 오류 배너로 보인다.
  // 테스트 코드: AC-130
  it('shows a server rejection of the performed day as an error banner inside the popup', async () => {
    // given: 서버가 수정 요청을 수행일 오류로 거절한다
    const edit = await openEdit()
    const { ApiError } = await import('../../../shared/api/problem')
    vi.spyOn(gateway.actions, 'update').mockRejectedValue(
      new ApiError(422, { type: 'https://sales.neoine.test/problems/invalid-value', title: 'x', status: 422, detail: FUTURE }),
    )
    // when: 수행일을 오늘로 바꿔 저장한다
    await setActedOn(edit, compactDate(TODAY))
    await save(edit)
    // then: 팝업 안에 오류 문구가 보이고 팝업은 열려 있다
    expect(await within(edit.dialog).findByText(FUTURE)).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Action 수정' })).toBeVisible()
  })
})
