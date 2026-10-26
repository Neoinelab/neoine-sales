import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

describe('목록과 경고 기준 (AC-13)', () => {
  it('writes the saved threshold into the legend and recolors rows after the save', async () => {
    const { client } = await renderAt('/deals?q=새론병원 PAM', { role: 'admin' })
    const row = await rowOf(/새론병원 PAM/)
    expect(within(row).getByText('미업데이트')).toBeVisible()

    await gateway.alerts.save(30)
    await client.invalidateQueries()

    const legend = await screen.findByRole('list', { name: 'Risk 범례' })
    await waitFor(() => expect(within(legend).getByText('30일 이상 미업데이트')).toBeVisible())
    await waitFor(async () => expect(within(await rowOf(/새론병원 PAM/)).queryByText('미업데이트')).not.toBeInTheDocument())
  })

  it('has no stay-days column or text in the list (the stay is shown on the detail only)', async () => {
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    expect(screen.queryByRole('columnheader', { name: /체류/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/\d+일째/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('columnheader')).toHaveLength(13)
  })
})

describe('범례 로딩 (R3 Minor 3)', () => {
  it('omits the threshold number while the alert settings are loading, then shows the saved one', async () => {
    let release: (value: Awaited<ReturnType<typeof gateway.alerts.get>>) => void = () => {}
    const pending = new Promise<Awaited<ReturnType<typeof gateway.alerts.get>>>((resolve) => {
      release = resolve
    })
    const spy = vi.spyOn(gateway.alerts, 'get').mockReturnValue(pending)
    try {
      await renderAt(ALL_DEALS)
      const legend = await screen.findByRole('list', { name: 'Risk 범례' })
      expect(within(legend).getByText('기준일 이상 미업데이트')).toBeVisible()
      expect(within(legend).queryByText(/\d+일 이상 미업데이트/)).not.toBeInTheDocument()

      release({ staleDays: 30, updatedAt: null, updatedBy: null })
      expect(await within(legend).findByText('30일 이상 미업데이트')).toBeVisible()
    } finally {
      spy.mockRestore()
    }
  })
})
