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
 * Forecast는 실제 서버 API를 쓴다. 예전의 "준비 중"(501 전용 분기)은 없고,
 * 어떤 실패든(501 포함) 오류 배너로 보인다.
 */
describe('Forecast 오류 표시', () => {
  // 테스트 코드: FC-056
  it('서버 오류는 오류 배너로 보인다', async () => {
    // given: 500으로 실패하는 요약 조회
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(500, 'internal-error', '서버 오류가 발생했습니다.'))
    // when: 화면을 연다
    await renderAt('/forecast')

    // then: 서버 문구가 배너로 보이고 "준비 중" 문구는 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류가 발생했습니다.')
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-056
  it('501도 "준비 중"이 아니라 다른 실패처럼 오류 배너로 보인다', async () => {
    // given: 501로 실패하는 요약 조회
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(501, 'not-implemented', '아직 실제 서버와 연결되지 않은 기능입니다.'))
    // when: 화면을 연다
    await renderAt('/forecast')

    // then: 제목과 오류 배너가 보이고 "준비 중" 문구는 없다
    expect(await screen.findByRole('heading', { name: 'Forecast' })).toBeVisible()
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-056
  it('오류가 보이는 동안에도 필터는 남아 조건을 바꿀 수 있다', async () => {
    // given: 422로 실패하는 요약 조회
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(problemError(422, 'invalid-value', '조건이 올바르지 않습니다.'))
    // when: 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 배너가 보이고 필터 폼이 그대로 보인다
    await screen.findByRole('alert')
    expect(screen.getByRole('form', { name: 'Forecast 필터' })).toBeVisible()
  })

  // 테스트 코드: FC-056
  it('기본 게이트웨이에서는 "준비 중" 대신 실제 요약 표를 보인다', async () => {
    // when: 기본 게이트웨이로 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 합계 행이 보이고 "준비 중" 문구는 없다
    expect(await screen.findByRole('rowheader', { name: '합계' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })
})
