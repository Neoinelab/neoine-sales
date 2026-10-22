import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'

const RANGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

async function openAlerts(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/deal', { role })
  await view.user.click(await screen.findByRole('tab', { name: '경고 기준' }))
  const input = await screen.findByLabelText('미업데이트 기준(일)')
  return { ...view, input }
}

const saveButton = () => screen.getByRole('button', { name: '저장' })

describe('경고 기준 탭 (AC-14)', () => {
  it('is the last (sixth) tab of Deal management, after the Vendor tab', async () => {
    await renderAt('/admin/deal', { role: 'admin' })

    const names = (await screen.findAllByRole('tab')).map((t) => t.textContent)

    expect(names).toEqual(['Status 코드', 'Forecast 코드', 'BANT Label', 'Action 유형', 'Vendor', '경고 기준'])
  })

  it('shows the current threshold (default 14) and that nothing was saved yet', async () => {
    const { input } = await openAlerts()

    expect(input).toHaveValue(14)
    expect(screen.queryByText(/마지막 저장/)).not.toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  it('saves a new value, shows who saved it and keeps the value after reload', async () => {
    const { user, input } = await openAlerts()

    await user.clear(input)
    await user.type(input, '30')
    await user.click(saveButton())

    expect(await screen.findByText(/마지막 저장/)).toHaveTextContent('최관리')
    expect(input).toHaveValue(30)
    expect((await gateway.alerts.get()).staleDays).toBe(30)
  })

  it.each(['0', '366'])('disables save and explains the range for %s', async (value) => {
    const { user, input } = await openAlerts()

    await user.clear(input)
    await user.type(input, value)

    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(RANGE)).toBeVisible()
    expect((await gateway.alerts.get()).staleDays).toBe(14)
  })

  it('disables save and explains the range for an empty input', async () => {
    const { user, input } = await openAlerts()

    await user.clear(input)

    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(RANGE)).toBeVisible()
  })

  it.each(['1', '365'])('allows the boundary %s', async (value) => {
    const { user, input } = await openAlerts()

    await user.clear(input)
    await user.type(input, value)
    await user.click(saveButton())

    await waitFor(async () => expect((await gateway.alerts.get()).staleDays).toBe(Number(value)))
  })

  it('shows the server sentence when the server refuses the value', async () => {
    const { user, input } = await openAlerts()
    vi.spyOn(gateway.alerts, 'save').mockRejectedValueOnce(
      new ApiError(422, {
        type: 'https://sales.neoine.test/problems/validation',
        title: 'Validation',
        status: 422,
        detail: RANGE,
      }),
    )

    await user.clear(input)
    await user.type(input, '20')
    await user.click(saveButton())

    expect(await within(await screen.findByRole('alert')).findByText(RANGE)).toBeVisible()
    vi.restoreAllMocks()
  })

  it('is hidden from sales: the tab and the form do not exist', async () => {
    await renderAt('/admin/deal?tab=alert', { role: 'sales' })

    await waitFor(() => expect(screen.queryByRole('tab', { name: '경고 기준' })).not.toBeInTheDocument())
    expect(screen.queryByLabelText('미업데이트 기준(일)')).not.toBeInTheDocument()
  })

  it('opens directly from ?tab=alert for the admin', async () => {
    await renderAt('/admin/deal?tab=alert', { role: 'admin' })

    expect(await screen.findByLabelText('미업데이트 기준(일)')).toHaveValue(14)
  })
})
