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
 * - Solution은 Vendor 목록과 무관한 텍스트 입력이라 목록을 못 받아도 그대로 편집할 수 있다(AC-12).
 * - 오류일 때만 ErrorBanner(role="alert")를 보인다. 로딩 중에는 오류 안내가 없다.
 * - 저장하면 원래 vendorId가 그대로 유지되고 Solution은 입력한 값이 전송된다.
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
  it('shows the current vendor name read-only and keeps the solution editable', async () => {
    await openEditWith('fail')
    await screen.findByRole('alert')

    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.queryByRole('group', { name: 'Solution' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Solution')).toHaveValue('MFA')
    expect(screen.getByLabelText('Solution')).toBeEnabled()
  })

  it('shows an error banner and never offers the none option for the vendor', async () => {
    await openEditWith('fail')

    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    const area = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(area).getByRole('group', { name: 'Vendor' })).toBeInTheDocument()
    expect(within(area).queryByRole('combobox', { name: /^Vendor$/ })).not.toBeInTheDocument()
  })

  it('keeps the original vendor id and sends the edited solution text when saved', async () => {
    const { user, location, code } = await openEditWith('fail')
    await screen.findByRole('alert')
    const solution = screen.getByLabelText('Solution')
    await user.clear(solution)
    await user.type(solution, 'Identity Threat')

    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    cleanup()
    const saved = await gateway.deals.get(code)
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.solution).toBe('Identity Threat')
  })
})

describe('수정 폼: Vendor 목록 로딩 중', () => {
  it('shows the vendor read-only and the solution as an enabled text input while loading', async () => {
    await openEditWith('pending')

    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Solution')).toHaveValue('MFA')
    expect(screen.getByLabelText('Solution')).toBeEnabled()
  })

  it('shows no error banner while loading', async () => {
    await openEditWith('pending')

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
