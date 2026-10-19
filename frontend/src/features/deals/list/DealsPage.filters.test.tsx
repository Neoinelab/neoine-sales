import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { seedSolutionId, seedVendorId } from '../../../test/fixtures/vendors'
import { dataRows, isoDay } from './testHelpers'

describe('필터와 정렬 (T-LIST-05~09)', () => {
  it('filters by keyword on submit and keeps it in the URL', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))
    expect(location()).toBe(`/deals?q=${encodeURIComponent('한빛은행')}`)
    await screen.findByRole('row', { name: /한빛은행 PAM/ })
    expect(dataRows()).toHaveLength(3)
  })

  it('filters by owner', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.selectOptions(await screen.findByLabelText('담당자'), '박영업')
    await screen.findByRole('row', { name: /미래전자 EDR 교체/ })
    expect(location()).toContain('owner=u-park')
    expect(dataRows()).toHaveLength(6)
  })

  it('offers resigned owners in the owner filter', async () => {
    const { user } = await renderAt('/deals')
    const owner = await screen.findByLabelText('담당자')
    await within(owner).findByRole('option', { name: '강퇴사(퇴사)' })
    await user.selectOptions(owner, '강퇴사(퇴사)')
    await screen.findByRole('row', { name: /한빛은행 PAM/ })
    expect(dataRows()).toHaveLength(1)
  })

  it('filters by vendor, status and forecast', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const vendor = await screen.findByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Silverfort' })
    await user.selectOptions(vendor, 'Silverfort')
    await screen.findByRole('row', { name: /도담건설 MFA/ })
    expect(dataRows()).toHaveLength(7)
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    await user.selectOptions(screen.getByLabelText('Status'), '계약완료')
    await screen.findByText(/도담건설 MFA/)
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('status=contract_completed')

    await user.selectOptions(screen.getByLabelText('Status'), '전체')
    await user.selectOptions(screen.getByLabelText('Vendor'), '전체')
    await user.selectOptions(screen.getByLabelText('Forecast'), 'Lost')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    expect(dataRows()).toHaveLength(1)
    expect(location()).toContain('forecast=lost')
  })

  it('filters by solution', async () => {
    const { user, location } = await renderAt('/deals')
    const solution = await screen.findByLabelText('Solution')
    await within(solution).findByRole('option', { name: 'Silverfort / ITDR' })
    await user.selectOptions(solution, 'Silverfort / ITDR')
    await screen.findByRole('row', { name: /미래전자 ITDR/ })
    expect(dataRows()).toHaveLength(4)
    expect(location()).toContain(`solution=${seedSolutionId('Silverfort', 'ITDR')}`)
  })

  it('filters by a BANT label of one category', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const budget = await screen.findByLabelText('Budget Label')
    await within(budget).findByRole('option', { name: '단독 예산 확보' })
    await user.selectOptions(budget, '단독 예산 확보')
    await screen.findByRole('row', { name: /우주항공연구원 ZTNA/ })
    expect(dataRows()).toHaveLength(2)
    expect(location()).toMatch(/budget=lb-/)
  })

  it('filters by an Expected Close period', async () => {
    const { location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    fireEvent.change(screen.getByLabelText('기간 시작'), { target: { value: isoDay(31) } })
    fireEvent.change(screen.getByLabelText('기간 끝'), { target: { value: isoDay(59) } })
    await screen.findByRole('row', { name: /세종에너지 취약점 진단/ })
    // 이전 결과가 새 결과가 올 때까지 남아 있으므로 건수가 바뀔 때까지 기다린다.
    await waitFor(() => expect(dataRows()).toHaveLength(4))
    expect(location()).toContain('from=')
    expect(location()).toContain('to=')
  })

  it('puts year and quarter in the URL', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const year = String(new Date().getFullYear())
    await user.selectOptions(screen.getByLabelText('연도'), year)
    await user.selectOptions(screen.getByLabelText('Quarter'), 'Q4')
    expect(location()).toContain(`year=${year}`)
    expect(location()).toContain('quarter=4')
  })

  it('shows only my deals with the my-deals toggle and removes the filter when turned off', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    expect(location()).toContain('mine=1')
    await screen.findByRole('row', { name: /새론병원 SSO/ })
    expect(dataRows()).toHaveLength(8)
    await user.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    expect(location()).toBe('/deals')
  })

  it('restores every control from the URL, as when coming back from a detail page', async () => {
    await renderAt('/deals?mine=1&status=contract_completed&sort=name&order=asc')
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })
    expect(dataRows()).toHaveLength(2)
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).toBeChecked()
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  it('clears every condition with the reset button', async () => {
    const { user, location } = await renderAt(`/deals?q=한빛&vendor=${seedVendorId('Okta')}&sort=name&order=asc`)
    await user.click(await screen.findByRole('button', { name: '초기화' }))
    expect(location()).toBe('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByLabelText('키워드')).toHaveValue('')
  })

  it('sorts by Expected Close and flips the direction', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    expect(location()).toContain('sort=revenueDate')
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'ascending'))
    expect(dataRows()[0]).toHaveTextContent('도담건설 MFA')
    await user.click(screen.getByRole('button', { name: 'Expected Close' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: 'Expected Close' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('대한제조 NGFW')
  })

  it('sorts by amount with the largest first and marks the default sort on the last update', async () => {
    const { user } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
    await user.click(screen.getByRole('button', { name: '금액(단위:천원)' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:천원)' })).toHaveAttribute('aria-sort', 'descending'))
    expect(dataRows()[0]).toHaveTextContent('한빛은행 ITDR 도입')
  })

  it('tells that nothing matches when a condition finds no deal', async () => {
    await renderAt('/deals?q=없는이름')
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})
