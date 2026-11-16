import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'
import { codeOf, save } from './testHelpers'

/**
 * 수정 폼의 Vendor 목록 조회 실패·로딩 계약.
 * - 목록을 아직 못 받았거나(로딩) 받지 못하면(오류) Vendor select를 그리지 않는다.
 *   대신 현재 이름을 읽기 전용 role="group"(접근 가능한 이름 'Vendor')으로 보이고, 어디에도 '선택 안 함'이 없다.
 * - Product는 Vendor 목록과 무관한 텍스트 입력이라 목록을 못 받아도 그대로 편집할 수 있다.
 * - 오류일 때만 ErrorBanner(role="alert")를 보인다. 로딩 중에는 오류 안내가 없다.
 * - 저장하면 원래 vendorId가 그대로 유지되고 Product는 입력한 값이 전송된다.
 */
afterEach(() => vi.restoreAllMocks())

const failure = () =>
  new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: 'Vendor 목록을 불러오지 못했습니다.' })

async function openEditWith(listBehavior: 'fail' | 'pending') {
  const code = await codeOf('누리통신 MFA') // Silverfort / MFA
  const list = vi.spyOn(gateway.vendors, 'list')
  if (listBehavior === 'fail') list.mockRejectedValue(failure())
  else list.mockImplementation(() => new Promise(() => {}))
  const view = await renderAt(`/deals/${code}/edit`)
  await screen.findByRole('heading', { name: 'Deal 수정' })
  await screen.findByLabelText('Deal Name')
  return { ...view, code }
}

describe('수정 폼: Vendor 목록 조회 실패', () => {
  // Vendor 목록을 못 받으면 현재 Vendor를 읽기 전용으로 보이고 Product는 입력할 수 있다.
  // 테스트 코드: DE-091
  it('shows the current vendor name read-only and keeps the product editable', async () => {
    // given: Vendor 목록 조회가 실패한다.
    await openEditWith('fail')
    // when: 수정 화면을 연다.
    await screen.findByRole('alert')

    // then: Vendor가 이름의 읽기 전용 행이고 Product 칸은 활성이다.
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.queryByRole('group', { name: 'Product' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Product')).toHaveValue('MFA')
    expect(screen.getByLabelText('Product')).toBeEnabled()
  })

  // 오류 배너를 보이고 '선택 안 함'을 내놓지 않는다.
  // 테스트 코드: DE-091
  it('shows an error banner and never offers the none option for the vendor', async () => {
    // when: 수정 화면을 연다.
    await openEditWith('fail')

    // then: 오류 배너가 있고 선택 안 함 선택지가 없다.
    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    const area = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(area).getByRole('group', { name: 'Vendor' })).toBeInTheDocument()
    expect(within(area).queryByRole('combobox', { name: /^Vendor$/ })).not.toBeInTheDocument()
  })

  // 저장하면 원래 Vendor id와 고친 Product를 보낸다.
  // 테스트 코드: DE-091
  it('keeps the original vendor id and sends the edited product text when saved', async () => {
    // given: Vendor 목록 조회가 실패한다.
    const { user, location, code } = await openEditWith('fail')
    await screen.findByRole('alert')
    const product = screen.getByLabelText('Product')

    // when: Product를 고쳐 저장한다.
    await user.clear(product)
    await user.type(product, 'Identity Threat')
    await save(user)

    // then: 요청에 원래 Vendor id와 새 Product가 담긴다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    cleanup()
    const saved = await gateway.deals.get(code)
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.product).toBe('Identity Threat')
  })
})

describe('수정 폼: Vendor 목록 로딩 중', () => {
  // Vendor 목록 로딩 중에도 읽기 전용 Vendor와 입력 가능한 Product를 보인다.
  // 테스트 코드: DE-091
  it('shows the vendor read-only and the product as an enabled text input while loading', async () => {
    // when: 수정 화면을 연다 (전제: Vendor 목록이 아직 오지 않았다).
    await openEditWith('pending')

    // then: Vendor가 읽기 전용이고 Product가 입력 가능하다.
    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Product')).toHaveValue('MFA')
    expect(screen.getByLabelText('Product')).toBeEnabled()
  })

  // 로딩 중에는 오류 배너가 없다.
  // 테스트 코드: DE-091
  it('shows no error banner while loading', async () => {
    // when: 수정 화면을 연다 (전제: Vendor 목록이 아직 오지 않았다).
    await openEditWith('pending')

    // then: 오류 배너가 없다.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
