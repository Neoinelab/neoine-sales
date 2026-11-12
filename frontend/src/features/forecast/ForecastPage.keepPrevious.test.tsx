import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

describe('Forecast 필터 전환 (keepPreviousData)', () => {
  // 테스트 코드: FC-057
  it('조건을 바꿔 다시 읽는 동안 이전 요약을 그대로 보인다', async () => {
    // given: 요약 표가 열려 있고 다음 조회는 풀어 줄 때까지 멈춘 상태
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

    // when: Quarter를 2로 바꾼다
    await user.selectOptions(screen.getByLabelText('Quarter'), '2')
    // then: URL이 바뀌어도 이전 표가 보이고 로딩 문구는 없다
    expect(location()).toContain('quarter=2')

    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()

    // when: 멈춘 조회를 풀어 준다
    release()
    // then: 새 기간의 요약으로 바뀐다
    expect((await screen.findAllByText(/2026 Q2/)).length).toBeGreaterThan(0)
  })
})
