import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, forecastButton } from './testHelpers'

/**
 * Forecast 구분(outcome) 필터 폐지 (2026-10-26,). 입력란이 없고, URL의 outcome은 조회와 기억에 쓰이지 않는다.
 * 시드(샘플 픽스처): '새론병원 SSO'만 Lost다. outcome=lost가 먹히면 이 Deal 하나만 보인다.
 */

afterEach(() => vi.restoreAllMocks())

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('Forecast 구분 필터 폐지', () => {
  // Forecast 구분 필터는 없고 Forecast 코드 필터는 있다
  // 테스트 코드: DL-072
  it('does not offer the Forecast 구분 filter but keeps the Forecast code filter', async () => {
    // given: 목록 필터 바
    await renderAt(ALL_DEALS)
    // when: 화면을 확인한다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: Forecast 구분 선택은 없고 Forecast 버튼은 있다
    expect(screen.queryByLabelText('Forecast 구분')).not.toBeInTheDocument()
    expect(forecastButton('전체')).toBeInTheDocument()
  })
})

describe('URL의 outcome', () => {
  // 주소의 outcome은 무시하고 같은 목록을 보인다
  // 테스트 코드: DL-072
  it('ignores outcome in the query and lists the same deals as without it', async () => {
    // given: 예전 outcome 키가 붙은 주소
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 그 주소를 연다
    const all = await gateway.deals.list({ limit: 1 })
    // then: outcome 없는 주소와 같은 Deal이 보인다
    expect(all.total).toBeGreaterThan(1)

    await renderAt('/deals?outcome=lost&year=all')

    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
    expect(lastQuery(list)).not.toHaveProperty('forecastOutcome')
    expect(screen.getByRole('row', { name: /새론병원 SSO/ })).toBeVisible()
    expect(screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })).toBeVisible()
  })

  // outcome은 기억되는 조건에 쓰이지 않는다
  // 테스트 코드: DL-072
  it('does not write outcome to the remembered list condition', async () => {
    // given: outcome 키가 붙은 주소
    await renderAt('/deals?outcome=lost&year=all')
    // when: 목록을 본다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 저장된 기억에 outcome이 없다
    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=all'))
  })

  // outcome만 빼고 다른 조건은 기억한다
  // 테스트 코드: DL-072
  it('keeps the other conditions of the URL and drops only the outcome from the memory', async () => {
    // given: outcome과 다른 조건이 있는 주소
    await renderAt('/deals?outcome=not_lost&year=all&status=contract_completed')
    // when: 목록을 본다
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })

    // then: 기억에 다른 조건만 남는다
    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=all&status=contract_completed'))
  })
})
