import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'

/**
 * 이전 Update 카드는 화면이 기준 행을 계산하지 않고 상세 `nextAction.actionId`의 Action을 따른다(AC-R26, RK-R1).
 * 서버(Fake) 시계는 2026-11-18. 시드 Deal 1(한빛은행 ITDR 도입)의 id 4는 김영업의 Open Next Action(Due 2026-11-21, 가장 최근 수행)이다.
 */
const NOW = '2026-11-18T09:00:00+09:00'
const TITLE = '한빛은행 ITDR 도입'
const FILL = '이전 Next Action을 진행사항에 채우기'
const CHECKBOX = '저장 시 이전 Next Action을 종료(수행)로 바꿈'
const NEW_ACTION = { type: { name: '미팅' }, comment: '' }

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

/** 서버 응답의 nextAction.actionId를 덮어쓰는 spy. null이면 실제 값을 그대로 둔다. */
function forceActionId(read: () => number | null) {
  const real = gateway.deals.get.bind(gateway.deals)
  vi.spyOn(gateway.deals, 'get').mockImplementation(async (code) => {
    const deal = await real(code)
    const id = read()
    return id === null || deal.nextAction === null ? deal : { ...deal, nextAction: { ...deal.nextAction, actionId: id } }
  })
}

async function openPage() {
  const path = await detailPath(1, '?tab=actions')
  const code = path.slice('/deals/'.length).split('?')[0] ?? ''
  const view = await renderAt(path, { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: TITLE })
  await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, code }
}

async function openForm(view: Awaited<ReturnType<typeof openPage>>) {
  await view.client.invalidateQueries()
  await view.user.click(await screen.findByRole('button', { name: 'Action 추가' }))
  const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })
  return { dialog, form: within(dialog).getByRole('form', { name: 'Action 추가' }) }
}

describe('이전 Update 카드의 기준 행', () => {
  // 기한초과 Deal의 카드는 서버가 준 기준 행(지난 Open 중 Due가 가장 이른 행)을 보이고 채우기·체크로 그 id를 보낸다.
  // 테스트 코드: AC-150, RK-088
  it('shows the server basis row of an overdue deal and sends its id when registering', async () => {
    // given: Deal 1에 Due가 지난 Open Next Action A(견적 발송)가 있어 서버 기준 행은 A이고, 더 최근 행(id 4)은 Due가 미래다
    const view = await openPage()
    const a = await gateway.actions.create(view.code, { ...NEW_ACTION, progress: '약속', nextAction: '견적 발송', dueDate: '2000-01-01', actedOn: '2026-11-01' })
    const create = vi.spyOn(gateway.actions, 'create')
    const { dialog, form } = await openForm(view)

    // when: 카드를 보고 채우기를 누른 뒤 유형을 입력하고 등록한다
    const card = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(within(card).getByText('견적 발송')).toBeVisible()
    expect(within(card).getByText('2000-01-01')).toBeVisible()
    expect(within(card).queryByText('계약서 초안 검토')).not.toBeInTheDocument()
    await view.user.click(within(dialog).getByRole('button', { name: FILL }))
    expect(within(dialog).getByLabelText('진행사항')).toHaveValue('견적 발송')
    expect(within(dialog).getByRole('checkbox', { name: CHECKBOX })).toBeChecked()
    await view.user.type(within(form).getByLabelText('유형'), '미팅')
    await view.user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 등록 요청이 A의 id를 닫도록 싣고, 알림이 나오며, 요약 바 Next Action은 남은 기준 행이 된다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1]).toMatchObject({ closePreviousNextActionId: a.id, progress: '견적 발송' })
    expect(await screen.findByText('Action이 등록되었습니다. 이전 Next Action을 종료(수행)로 바꿨습니다.')).toBeVisible()
    // then: A가 종료(수행)이고, Deal 상세 탭의 요약 바 Next Action은 남은 기준 행(id 4, Due 2026-11-21)이다
    await waitFor(async () => expect((await gateway.actions.list(view.code, {})).find((x) => x.id === a.id)?.nextActionStatus).toBe('done'))
    await view.user.click(await screen.findByRole('tab', { name: /Deal 상세/ }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await waitFor(() => expect(within(bar).getByText('Due 2026-11-21')).toBeVisible())
    expect(within(bar).getByText('계약서 초안 검토')).toBeVisible()
  })

  // 카드는 화면 시계나 목록의 최근 행이 아니라 상세 nextAction.actionId의 행을 따른다.
  // 테스트 코드: AC-152
  it('follows nextAction.actionId of the detail instead of the most recent row of the list', async () => {
    // given: 목록에는 가장 최근 Next Action 행 X(id 4)와 이전 Open 행 Y가 있고, 상세 응답의 actionId는 Y다
    let forced: number | null = null
    forceActionId(() => forced)
    const view = await openPage()
    const y = await gateway.actions.create(view.code, { ...NEW_ACTION, progress: '이전 약속', nextAction: '이전 일정', dueDate: '2026-12-01', actedOn: '2026-11-05' })
    forced = y.id

    // when: 추가 팝업을 연다
    const { dialog } = await openForm(view)

    // then: 카드는 X(계약서 초안 검토)가 아니라 Y의 Next Action을 보인다
    const card = within(dialog).getByRole('complementary', { name: '이전 Update' })
    expect(within(card).getByText('이전 일정')).toBeVisible()
    expect(within(card).queryByText('계약서 초안 검토')).not.toBeInTheDocument()
  })

  // 상세 actionId가 목록에 없으면 카드가 없고 등록 요청에 닫을 id가 없다.
  // 테스트 코드: AC-152
  it('shows no previous update card and sends no close id when the id is not in the list', async () => {
    // given: 상세 응답의 actionId가 Action 목록에 없는 값이다
    forceActionId(() => 987_654)
    const view = await openPage()
    const create = vi.spyOn(gateway.actions, 'create')

    // when: 추가 팝업을 열고 직접 입력해 등록한다
    const { dialog, form } = await openForm(view)
    expect(within(dialog).queryByRole('complementary', { name: '이전 Update' })).not.toBeInTheDocument()
    await view.user.type(within(form).getByLabelText('유형'), '미팅')
    await view.user.type(within(form).getByLabelText('진행사항'), '직접 입력')
    await view.user.click(within(form).getByRole('button', { name: '등록' }))

    // then: 이전 Update 카드(위에서 확인)와 채우기 버튼이 없고 요청에 닫을 id가 없다
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create.mock.calls[0]?.[1].closePreviousNextActionId).toBeUndefined()
  })
})
