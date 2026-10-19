import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { AMOUNT_INPUT_MESSAGE } from '../../../shared/model/money'
import { renderAt } from '../../../test/mockApp'
import { save } from './testHelpers'

/** 시드 Deal의 금액을 300원으로 만든 뒤 그 수정 화면을 연다(표기는 0). */
async function openSmallAmountEdit() {
  const view = await renderAt('/deals?q=대한제조 NGFW')
  const code = (await gateway.deals.list({ keyword: '대한제조 NGFW', limit: 5 })).items[0]!.code
  await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 300 } })
  view.goTo(`/deals/${code}/edit`)
  await screen.findByRole('heading', { name: 'Deal 수정' })
  await waitFor(() => expect(screen.getByLabelText('금액(단위:천원)')).toHaveValue('0'))
  return { ...view, code }
}

describe('1~499원 금액 Deal 수정 (표기 0)', () => {
  it('saves a name change without touching the amount and keeps 300 won', async () => {
    const { user, code, location } = await openSmallAmountEdit()
    const name = screen.getByLabelText('Deal Name')
    await user.clear(name)
    await user.type(name, '대한제조 NGFW 개명')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect((await gateway.deals.get(code)).revenueAmount).toBe(300)
    expect((await gateway.deals.get(code)).name).toBe('대한제조 NGFW 개명')
  })

  it('still rejects an emptied amount', async () => {
    const { user, location } = await openSmallAmountEdit()
    await user.clear(screen.getByLabelText('금액(단위:천원)'))
    await save(user)
    expect(await screen.findByText(AMOUNT_INPUT_MESSAGE)).toBeVisible()
    expect(location()).toMatch(/\/edit$/)
  })
})
