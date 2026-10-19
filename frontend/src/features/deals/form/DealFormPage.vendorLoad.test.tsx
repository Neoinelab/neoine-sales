import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'
import { codeOf, save } from './testHelpers'

/**
 * 수정 폼의 Vendor·Solution 목록 조회 실패·로딩 계약(계획 6절, 리뷰 Minor 1).
 * - 목록을 아직 못 받았거나(로딩) 받지 못하면(오류) Vendor·Solution select를 그리지 않는다.
 *   대신 현재 이름을 읽기 전용 role="group"(접근 가능한 이름 'Vendor' / 'Solution')으로 보이고, 어디에도 '선택 안 함'이 없다.
 * - 오류일 때만 ErrorBanner(role="alert")를 보인다. 로딩 중에는 오류 안내가 없다.
 * - 저장하면 원래 vendorId·solutionId가 그대로 유지된다.
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
  it('shows the current vendor and solution names read-only without selects', async () => {
    await openEditWith('fail')
    await screen.findByRole('alert')

    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Solution' })).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.getByRole('group', { name: 'Solution' })).toHaveTextContent('MFA')
  })

  it('shows an error banner and never offers the none option', async () => {
    await openEditWith('fail')

    expect(await screen.findByRole('alert')).toHaveTextContent('Vendor 목록을 불러오지 못했습니다.')
    // Vendor·Solution 행을 담은 'Deal 정보' 영역 안에서 확인한다(같은 영역의 견적 제출 등에는 '선택 안 함'이 원래 있어 이름으로 좁힌다).
    const area = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(area).getByRole('group', { name: 'Vendor' })).toBeInTheDocument()
    expect(within(area).getByRole('group', { name: 'Solution' })).toBeInTheDocument()
    expect(within(area).queryByRole('combobox', { name: /^(Vendor|Solution)$/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Solution' })).not.toBeInTheDocument()
  })

  it('keeps the original vendor and solution ids when saved', async () => {
    const { user, location, code } = await openEditWith('fail')
    await screen.findByRole('alert')

    await save(user)

    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    cleanup()
    const saved = await gateway.deals.get(code)
    expect(saved.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(saved.solution).toEqual({ id: seedSolutionId('Silverfort', 'MFA'), name: 'MFA' })
  })
})

describe('수정 폼: Vendor 목록 로딩 중', () => {
  it('shows the current names read-only instead of the none option while loading', async () => {
    await openEditWith('pending')

    expect(screen.getByRole('group', { name: 'Vendor' })).toHaveTextContent('Silverfort')
    expect(screen.getByRole('group', { name: 'Solution' })).toHaveTextContent('MFA')
    // Vendor·Solution 행을 담은 'Deal 정보' 영역 안에서 확인한다(같은 영역의 견적 제출 등에는 '선택 안 함'이 원래 있어 이름으로 좁힌다).
    const area = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(area).getByRole('group', { name: 'Vendor' })).toBeInTheDocument()
    expect(within(area).getByRole('group', { name: 'Solution' })).toBeInTheDocument()
    expect(within(area).queryByRole('combobox', { name: /^(Vendor|Solution)$/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Solution' })).not.toBeInTheDocument()
  })

  it('shows no error banner while loading', async () => {
    await openEditWith('pending')

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
