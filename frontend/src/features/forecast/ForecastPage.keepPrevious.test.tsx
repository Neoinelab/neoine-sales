import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

describe('Forecast 필터 전환 (keepPreviousData)', () => {
  it('keeps the previous summary on screen while the next filter loads', async () => {
    const { user, location } = await renderAt('/forecast')
    const table = await screen.findByRole('table')
    expect(table).toBeVisible()

    const original = gateway.forecast.summary.bind(gateway.forecast)
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.forecast, 'summary').mockImplementation(async (query) => {
      await gate
      return original(query)
    })

    await user.selectOptions(screen.getByLabelText('Quarter'), '2')
    expect(location()).toContain('quarter=2')

    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()

    release()
    expect((await screen.findAllByText(/2026 Q2/)).length).toBeGreaterThan(0)
  })
})
