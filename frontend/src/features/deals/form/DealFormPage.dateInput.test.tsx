import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { pickVendor } from '../../../test/vendorPick'
import { DETAIL_URL, pickPerson, save } from './testHelpers'

afterEach(() => vi.restoreAllMocks())

async function fillRequired(name: string) {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await screen.findByLabelText('Deal Name')
  await view.user.type(screen.getByLabelText('Deal Name'), name)
  await pickVendor(view.user)
  await pickPerson(view.user, '고객', '한빛은행', /정민수/)
  await view.user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
  await view.user.type(screen.getByLabelText('Product'), 'ITDR')
  await view.user.type(screen.getByLabelText('Users count'), '10')
  return view
}

describe('Deal 폼의 날짜 입력 (AC-D3, AC-D7)', () => {
  // Expected Close는 yyyymmdd로 입력해 저장된다.
  // 테스트 코드: DE-080
  it('types Expected Close as yyyymmdd and saves the ISO date', async () => {
    // when: Expected Close에 yyyymmdd를 입력하고 저장한다.
    const { user, location } = await fillRequired('날짜 직접 입력')
    await user.type(screen.getByLabelText('Expected Close'), '20270601')

    // then: ISO 날짜로 저장된다.
    expect(screen.getByLabelText('Expected Close')).toHaveValue('2027.06.01')
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.revenueDate).toBe('2027-06-01')
  })

  // 없는 날짜의 Expected Close는 저장을 막고 날짜 문구를 보인다.
  // 테스트 코드: DE-080
  it('blocks the save and shows the date message for a non-existing Expected Close', async () => {
    // when: 존재하지 않는 날짜를 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await fillRequired('틀린 날짜')
    await user.type(screen.getByLabelText('Expected Close'), '20271301')
    await save(user)

    // then: 날짜 문구가 나오고 저장되지 않는다.
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  // Expected Close가 비면 필수 문구를 유지한다.
  // 테스트 코드: DE-080
  it('keeps the required message when Expected Close is left empty', async () => {
    // when: Expected Close를 비우고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await fillRequired('날짜 비움')
    await save(user)

    // then: 'Expected Close를 입력하세요.'가 나온다.
    expect(await screen.findByText('Expected Close를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  // 견적일을 덜 쳤으면 저장을 막는다.
  // 테스트 코드: DE-080
  it('blocks the save when the quote date is only partly typed', async () => {
    // when: 견적일을 일부만 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await fillRequired('견적일 덜 침')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await user.type(screen.getByLabelText('견적 제출일'), '2027.1')
    await save(user)

    // then: 날짜 문구가 나오고 저장되지 않는다.
    expect(await screen.findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  // 틀린 POC 완료일은 저장을 막는다.
  // 테스트 코드: DE-080
  it('blocks the save for a wrong POC date', async () => {
    // when: 틀린 POC 날짜를 입력하고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user } = await fillRequired('POC일 틀림')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await user.type(screen.getByLabelText('POC 완료일'), '20270230')
    await save(user)

    // then: 날짜 문구가 나오고 저장되지 않는다.
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  // 빈 견적일은 날짜 없음으로 저장된다.
  // 테스트 코드: DE-080
  it('saves an empty quote date as no date', async () => {
    // when: 견적일을 비우고 저장한다.
    const { user, location } = await fillRequired('견적일 없음')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)

    // then: 견적 제출일이 없는 Deal이 저장된다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.quote.submittedDate).toBeNull()
  })
})
