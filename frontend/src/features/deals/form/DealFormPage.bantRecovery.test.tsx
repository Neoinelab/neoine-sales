import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { codeOf, DETAIL_URL, openEdit, save } from './testHelpers'

/**
 * Deal 수정 폼의 BANT 보존(리뷰 후속): Label 목록 첫 조회가 실패한 뒤 회복돼도 선택이 지워지지 않고,
 * 건드리지 않은 항목은 처음 {id}로 전송된다(admin이 이름을 바꿔도 옛 이름으로 새 Label이 생기지 않는다).
 */
afterEach(() => vi.restoreAllMocks())

const NAME = '대한제조 MFA 확대'
const CATEGORIES = ['budget', 'authority', 'need', 'timeline'] as const

const asChoices = (bant: Record<(typeof CATEGORIES)[number], number | null>) =>
  Object.fromEntries(CATEGORIES.map((c) => [c, bant[c] ? { id: bant[c] } : null]))

const bantEntries = (code: string) => gateway.history.list(code, { category: 'bant' })

describe('Label 목록이 실패했다가 회복된 뒤의 저장', () => {
  it('keeps the four selections and writes no BANT history when only another field is edited', async () => {
    const code = await codeOf(NAME)
    const before = (await gateway.deals.get(code)).bant
    const historyBefore = (await bantEntries(code)).length
    const list = vi.spyOn(gateway.labels, 'list').mockRejectedValueOnce(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Label 목록을 불러오지 못했습니다.' }),
    )
    const { user, location, client } = await renderAt(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })
    const nameInput = await screen.findByLabelText('Deal Name')
    // 폼이 마운트되며 실패한 목록을 다시 조회하고, 그 재조회가 성공해 끝날 때까지 기다린다.
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThanOrEqual(2))
    await waitFor(() => expect(client.getQueryState(keys.labels)?.status).toBe('success'))
    await waitFor(() => expect(client.isFetching({ queryKey: keys.labels })).toBe(0))

    await user.type(nameInput, ' 수정')
    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(code)
    expect(saved.name).toBe(`${NAME} 수정`)
    expect(saved.bant).toEqual(before)
    expect(await bantEntries(code)).toHaveLength(historyBefore)
  })
})

describe('건드리지 않은 BANT는 처음 {id}로 전송된다', () => {
  it('sends the original ids and creates no label when an admin renamed the labels after the form was opened', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, location, code, client } = await openEdit(NAME, 'admin') // Label 이름 변경은 admin만
    const before = (await gateway.deals.get(code)).bant
    const labelsBefore = await gateway.labels.list()
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Budget' })).not.toHaveDisplayValue(''))
    for (const c of CATEGORIES) {
      const id = before[c]
      if (id) await gateway.labels.rename(id, `개명 ${c}`)
    }
    await client.invalidateQueries({ queryKey: keys.labels })
    await waitFor(() => expect(client.isFetching({ queryKey: keys.labels })).toBe(0))

    await user.type(screen.getByLabelText('Deal Name'), ' 수정')
    await save(user)

    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const sent = update.mock.calls[0]?.[1].bant
    expect(sent).toEqual(asChoices(before))
    expect(await gateway.labels.list()).toHaveLength(labelsBefore.length)
    expect((await gateway.deals.get(code)).bant).toEqual(before)
  })
})
