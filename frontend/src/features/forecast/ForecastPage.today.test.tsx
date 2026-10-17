import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

beforeEach(() => resetMock({ now: '2030-06-15T09:00:00+09:00' }))
afterEach(() => resetMock({ now: null }))

describe('Forecast와 mock 시계 (useToday)', () => {
  it('defaults the year filter to the mock clock year and lists years around it', async () => {
    await renderAt('/forecast')
    const year = await screen.findByLabelText('연도')
    expect(year).toHaveValue('2030')
    expect(within(year).getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(within(year).queryByRole('option', { name: '2026' })).not.toBeInTheDocument()
  })

  it('keeps an explicit year from the URL', async () => {
    await renderAt('/forecast?year=2031')
    expect(await screen.findByLabelText('연도')).toHaveValue('2031')
  })
})
