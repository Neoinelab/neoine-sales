import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, pickPerson, save } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

async function fillRequired(name: string) {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await screen.findByLabelText('Deal Name')
  await view.user.type(screen.getByLabelText('Deal Name'), name)
  await pickPerson(view.user, '고객', '한빛은행', /정민수/)
  await view.user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
  await view.user.type(screen.getByLabelText('Solution'), 'ITDR')
  await view.user.type(screen.getByLabelText('Users'), '10')
  return view
}

describe('Deal 폼의 날짜 입력 (AC-D3, AC-D7)', () => {
  it('types Expected Close as yyyymmdd and saves the ISO date', async () => {
    const { user, location } = await fillRequired('날짜 직접 입력')
    await user.type(screen.getByLabelText('Expected Close'), '20270601')
    expect(screen.getByLabelText('Expected Close')).toHaveValue('2027.06.01')
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.revenueDate).toBe('2027-06-01')
  })

  it('blocks the save and shows the date message for a non-existing Expected Close', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await fillRequired('틀린 날짜')
    await user.type(screen.getByLabelText('Expected Close'), '20271301')
    await save(user)
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  it('keeps the required message when Expected Close is left empty', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await fillRequired('날짜 비움')
    await save(user)
    expect(await screen.findByText('Expected Close를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  it('blocks the save when the quote date is only partly typed', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await fillRequired('견적일 덜 침')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await user.type(screen.getByLabelText('견적 제출일'), '2027.1')
    await save(user)
    expect(await screen.findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  it('blocks the save for a wrong POC date', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await fillRequired('POC일 틀림')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await user.type(screen.getByLabelText('POC 완료일'), '20270230')
    await save(user)
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  it('saves an empty quote date as no date', async () => {
    const { user, location } = await fillRequired('견적일 없음')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.quote.submittedDate).toBeNull()
  })
})
