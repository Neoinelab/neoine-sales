import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, forecastButton } from './testHelpers'

/**
 * Forecast 구분(outcome) 필터 폐지(2026-10-26, AC-01·02). 입력란이 없고, URL의 outcome은 조회와 기억에 쓰이지 않는다.
 * 시드(샘플 픽스처): '새론병원 SSO'만 Lost다. outcome=lost가 먹히면 이 Deal 하나만 보인다.
 */

afterEach(() => vi.restoreAllMocks())

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('Forecast 구분 필터 폐지 (AC-01)', () => {
  it('does not offer the Forecast 구분 filter but keeps the Forecast code filter', async () => {
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(screen.queryByLabelText('Forecast 구분')).not.toBeInTheDocument()
    expect(forecastButton('전체')).toBeInTheDocument()
  })
})

describe('URL의 outcome (AC-02)', () => {
  it('ignores outcome in the query and lists the same deals as without it', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    const all = await gateway.deals.list({ limit: 1 })
    expect(all.total).toBeGreaterThan(1)

    await renderAt('/deals?outcome=lost&year=all')

    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
    expect(lastQuery(list)).not.toHaveProperty('forecastOutcome')
    expect(screen.getByRole('row', { name: /새론병원 SSO/ })).toBeVisible()
    expect(screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })).toBeVisible()
  })

  it('does not write outcome to the remembered list condition', async () => {
    await renderAt('/deals?outcome=lost&year=all')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=all'))
  })

  it('keeps the other conditions of the URL and drops only the outcome from the memory', async () => {
    await renderAt('/deals?outcome=not_lost&year=all&status=contract_completed')
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })

    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=all&status=contract_completed'))
  })
})
