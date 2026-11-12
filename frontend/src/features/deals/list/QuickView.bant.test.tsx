import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

/** 목록은 Label을 미리 읽지 않으므로 빠른 보기가 Label 로딩·실패를 스스로 보인다(리뷰 Minor, 2026-10-23). */

const DEAL = /한빛은행 ITDR 도입/

afterEach(() => vi.restoreAllMocks())

/** 목록을 띄운 뒤(Fake는 로그인 후에만 응답) 한빛은행 Deal의 Budget에 Label 하나를 고르고, Label 조회 동작을 바꿔 빠른 보기를 연다. */
async function openQuickView(labels?: () => void) {
  const view = await renderAt('/deals?q=한빛은행 ITDR')
  const page = await gateway.deals.list({ keyword: '한빛은행 ITDR', offset: 0, limit: 10 })
  const code = page.items[0]?.code ?? ''
  const label = (await gateway.labels.list()).find((l) => l.category === 'budget')
  if (!label) throw new Error('seed has no budget label')
  await gateway.deals.update(code, { bant: { budget: { id: label.id }, authority: null, need: null, timeline: null } })
  await view.client.invalidateQueries()
  labels?.()
  await waitFor(async () => expect(within(await rowOf(DEAL)).getByRole('button', { name: /빠른 보기/ })).toBeVisible())
  await view.user.click(within(await rowOf(DEAL)).getByRole('button', { name: /빠른 보기/ }))
  const region = await screen.findByRole('region', { name: /빠른 보기/ })
  const item = (name: string) => within(region).getByText(name).closest('div') as HTMLElement
  return { name: label.name, budget: () => item('Budget'), authority: () => item('Authority') }
}

const pending = () => vi.spyOn(gateway.labels, 'list').mockReturnValue(new Promise(() => {}))

describe('빠른 보기의 BANT Label 표시', () => {
  // Label 목록이 오면 Label 이름을 보인다
  // 테스트 코드: DL-092
  it('shows the label name once the label list arrives', async () => {
    // when: 빠른 보기를 연다 (전제: Label 조회가 정상인 빠른 보기)
    const { name, budget } = await openQuickView()

    // then: Label 이름이 보인다
    await waitFor(() => expect(budget()).toHaveTextContent(name))
  })

  // Label 목록을 읽는 동안 '불러오는 중…'을 보인다
  // 테스트 코드: DL-092
  it('shows loading instead of a dash while the label list is pending', async () => {
    // when: 빠른 보기를 연다 (전제: Label 조회가 대기 중인 Fake)
    const { budget } = await openQuickView(pending)

    // then: '불러오는 중…'이 보인다
    expect(budget()).toHaveTextContent('불러오는 중…')
  })

  // Label 조회가 실패하면 '불러오지 못함'을 보인다
  // 테스트 코드: DL-092
  it('tells that the name could not be read when the label list fails', async () => {
    // when: 빠른 보기를 연다 (전제: Label 조회가 실패하는 Fake)
    const { budget } = await openQuickView(() =>
      vi
        .spyOn(gateway.labels, 'list')
        .mockRejectedValue(new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Label 목록을 불러오지 못했습니다.' })),
    )

    // then: '불러오지 못함'이 보인다
    await waitFor(() => expect(budget()).toHaveTextContent('불러오지 못함'))
  })

  // 고르지 않은 구분은 읽는 중에도 '—'다
  // 테스트 코드: DL-092
  it('keeps a dash for a category with no label even while loading', async () => {
    // when: 빠른 보기를 연다 (전제: Label을 고르지 않은 구분)
    const { authority } = await openQuickView(pending)

    // then: '—'가 보인다
    expect(authority()).toHaveTextContent('—')
  })
})
