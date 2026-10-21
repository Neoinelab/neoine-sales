import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

function problemError(status: number, kind: string, detail: string): ApiError {
  return new ApiError(status, {
    type: `https://sales.neoine.test/problems/${kind}`,
    title: kind,
    status,
    detail,
  })
}

/**
 * P6 R1: Forecast는 실제 서버 API를 쓴다. 예전의 "준비 중"(501 전용 분기)은 없고,
 * 어떤 실패든(501 포함) 오류 배너로 보인다.
 */
describe('Forecast 오류 표시 (P6 AC-10)', () => {
  it('shows an error banner for a server failure', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(500, 'internal-error', '서버 오류가 발생했습니다.'))
    await renderAt('/forecast')

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  it('no longer treats a 501 as coming soon: it is an error banner like any other failure', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(501, 'not-implemented', '아직 실제 서버와 연결되지 않은 기능입니다.'))
    await renderAt('/forecast')

    expect(await screen.findByRole('heading', { name: 'Forecast' })).toBeVisible()
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  it('keeps the filter bar visible while an error is shown so the user can change the condition', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(422, 'invalid-value', '조건이 올바르지 않습니다.'))
    await renderAt('/forecast?year=2026')

    await screen.findByRole('alert')
    expect(screen.getByRole('form', { name: 'Forecast 필터' })).toBeVisible()
  })

  it('shows the real summary table instead of coming soon with the default gateway', async () => {
    await renderAt('/forecast?year=2026')

    expect(await screen.findByRole('rowheader', { name: '합계' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })
})
