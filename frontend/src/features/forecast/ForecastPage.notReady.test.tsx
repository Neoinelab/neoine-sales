import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** gateway/http/unsupported.ts와 같은 모양의 501 오류. */
function notImplementedError(): ApiError {
  return new ApiError(501, {
    type: 'https://sales.neoine.test/problems/not-implemented',
    title: 'Not Implemented',
    status: 501,
    detail: '아직 실제 서버와 연결되지 않은 기능입니다.',
  })
}

function serverError(): ApiError {
  return new ApiError(500, {
    type: 'https://sales.neoine.test/problems/internal-error',
    title: 'Internal Server Error',
    status: 500,
    detail: '서버 오류가 발생했습니다.',
  })
}

describe('Forecast 준비 중 (P8 AC-07)', () => {
  it('shows coming soon when the server has no forecast yet', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(notImplementedError())
    await renderAt('/forecast')

    expect(await screen.findByRole('heading', { name: 'Forecast' })).toBeVisible()
    expect(await screen.findByText(/준비 중입니다/)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Forecast 필터' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('목업')
  })

  it('still shows an error banner for other failures', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(serverError())
    await renderAt('/forecast')

    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })
})
