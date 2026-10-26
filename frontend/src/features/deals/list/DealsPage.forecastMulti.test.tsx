import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, findFilterBar, forecastButton, openForecastPanel, toggleForecast } from './testHelpers'

/**
 * 목록 Forecast 조건 다중 선택(AC-07~13). 체크할 때마다 바로 조회하고, 선택은 URL `forecast`
 * (알파벳순·중복 제거·콤마 → `%2C`)가 정본이다. 시드(샘플 픽스처): '새론병원 SSO'만 Lost.
 */

afterEach(() => vi.restoreAllMocks())

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
const forecastCells = () => screen.getAllByRole('button', { name: /Forecast 편집/ }).map((b) => b.textContent ?? '')

describe('selecting several forecasts (AC-07·08)', () => {
  it('lists the deals of any checked forecast and puts the sorted keys in the URL', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await toggleForecast(user, 'Pipeline')
    await toggleForecast(user, 'Best')

    await waitFor(() => expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline'))
    expect(forecastButton('2개 선택')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['best', 'pipeline'] }))
    const expected = (await gateway.deals.list({ forecastKeys: ['best', 'pipeline'], limit: 20 })).items.length
    expect(expected).toBeGreaterThan(0)
    await waitFor(() => expect(dataRows()).toHaveLength(expected))
    for (const text of forecastCells()) expect(text).toMatch(/Pipeline|Best/)
  })

  it('writes one key as a plain value', async () => {
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    await toggleForecast(user, 'Pipeline')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&forecast=pipeline'))
    expect(forecastButton('Pipeline')).toBeInTheDocument()
  })

  it('removes a key again and keeps the others', async () => {
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })

    await toggleForecast(user, 'Pipeline')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&forecast=best'))
  })

  it('goes back to page 1 when the selection changes', async () => {
    const { user, location } = await renderAt('/deals?year=all&sort=revenueAmount&order=desc&page=2')
    await screen.findByRole('button', { name: '이전' })

    await toggleForecast(user, 'Pipeline')

    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=revenueAmount&order=desc&forecast=pipeline'))
  })

  it('lists the forecast codes in code order as checkboxes of the Forecast group', async () => {
    const { user } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    const panel = await openForecastPanel(user)

    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual([
      'pipeline',
      'best',
      'most_likely',
      'commit',
      'won',
      'lost',
    ])
  })

  it('gives the same URL whatever order the boxes are checked in (AC-08)', async () => {
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await toggleForecast(user, 'Best')
    await toggleForecast(user, 'Pipeline')
    await waitFor(() => expect(location()).toContain('forecast=best%2Cpipeline'))
    const bestFirst = location()
    await user.click((await openForecastPanel(user)).getByRole('button', { name: '전체' }))
    await waitFor(() => expect(location()).toBe(ALL_DEALS))

    await toggleForecast(user, 'Pipeline')
    await toggleForecast(user, 'Best')

    await waitFor(() => expect(location()).toContain('forecast=best%2Cpipeline'))
    expect(location()).toBe(bestFirst)
    expect(bestFirst).toBe('/deals?year=all&forecast=best%2Cpipeline')
  })
})

describe('clearing the selection (AC-09)', () => {
  it('shows 전체 and drops forecast from the URL when every box is off', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })

    await toggleForecast(user, 'Best')
    await toggleForecast(user, 'Pipeline')

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(forecastButton('전체')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).not.toHaveProperty('forecastKeys'))
  })

  it('clears with the 전체 button of the panel', async () => {
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })
    const panel = await openForecastPanel(user)

    await user.click(panel.getByRole('button', { name: '전체' }))

    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(forecastButton('전체')).toBeInTheDocument()
  })

  it('leaves year=all when the last condition is removed', async () => {
    const { user, location } = await renderAt('/deals?forecast=best')
    await screen.findByRole('button', { name: 'Forecast Best' })

    await toggleForecast(user, 'Best')

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  it('leaves year=all after the panel 전체 button removes the only condition', async () => {
    const { user, location } = await renderAt('/deals?year=all&forecast=best')
    await screen.findByRole('button', { name: 'Forecast Best' })
    const panel = await openForecastPanel(user)

    await user.click(panel.getByRole('button', { name: '전체' }))

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })
})

describe('summary text (AC-10)', () => {
  const NOT_LOST = 'best%2Ccommit%2Cmost_likely%2Cpipeline%2Cwon'
  const OPEN = 'best%2Ccommit%2Cmost_likely%2Cpipeline'

  it.each([
    ['Lost 제외', NOT_LOST],
    ['Open 전체', OPEN],
    ['모두 선택', `${NOT_LOST}%2Clost`],
    ['3개 선택', 'best%2Ccommit%2Clost'],
  ])('shows %s', async (summary, value) => {
    await renderAt(`/deals?year=all&forecast=${value}`)

    expect(await (await findFilterBar()).findByRole('button', { name: `Forecast ${summary}` })).toBeInTheDocument()
  })

  it('checks the matching boxes for the Lost 제외 URL', async () => {
    const { user } = await renderAt(`/deals?year=all&forecast=${NOT_LOST}`)
    const panel = await openForecastPanel(user)

    expect(panel.getByRole('checkbox', { name: 'Won' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Lost' })).not.toBeChecked()
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(5)
  })
})

describe('old and malformed addresses (AC-11·12)', () => {
  it('opens an old single value as one checked code', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user } = await renderAt('/deals?year=all&forecast=commit')

    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast Commit' })).toBeInTheDocument()
    const panel = await openForecastPanel(user)
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(1)
    expect(panel.getByRole('checkbox', { name: 'Commit' })).toBeChecked()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['commit'] }))
  })

  it('drops a key with a wrong format and keeps the rest', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt('/deals?year=all&forecast=Commit%2Cbest')

    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast Best' })).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['best'] }))
  })

  it('sends a well formed key that no code has, shows it only in the summary', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const { user } = await renderAt('/deals?year=all&forecast=no_such')

    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast no_such' })).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['no_such'] }))
    expect(await screen.findByText('총 0건')).toBeVisible()
    const panel = await openForecastPanel(user)
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(0)
  })

  it('ignores the whole condition above one hundred distinct keys', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const many = Array.from({ length: 101 }, (_, i) => `k${i}`).join('%2C')
    await renderAt(`/deals?year=all&forecast=${many}`)

    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast 전체' })).toBeInTheDocument()
    await waitFor(() => expect(list).toHaveBeenCalled())
    expect(lastQuery(list)).not.toHaveProperty('forecastKeys')
  })
})

describe('list memory (AC-13)', () => {
  it('remembers the selection and restores the same boxes after a detail round trip', async () => {
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await toggleForecast(user, 'Pipeline')
    await toggleForecast(user, 'Best')
    await waitFor(() => expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline'))
    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toContain('forecast=best%2Cpipeline'))
    await user.keyboard('{Escape}')

    const row = dataRows()[0] as HTMLElement
    await user.click(within(row).getAllByRole('link')[0] as HTMLElement)
    await user.click(await screen.findByRole('link', { name: '← 목록' }))

    await screen.findByRole('button', { name: 'Forecast 2개 선택' })
    expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline')
    const panel = await openForecastPanel(user)
    expect(panel.getByRole('checkbox', { name: 'Pipeline' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Best' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Commit' })).not.toBeChecked()
  })
})

describe('closing the panel (AC-07)', () => {
  it('closes with Escape and returns the focus to the Forecast button', async () => {
    const { user } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await openForecastPanel(user)

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(forecastButton()).toHaveFocus()
  })
})
