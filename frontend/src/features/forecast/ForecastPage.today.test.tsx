import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'

beforeEach(() => resetMock({ now: '2030-06-15T09:00:00+09:00' }))
afterEach(() => resetMock({ now: null }))

describe('Forecast와 mock 시계 (useToday)', () => {
  // 테스트 코드: FC-048
  it('연도를 주지 않으면 앱 시계의 올해로 열리고 그 주변 연도를 보인다', async () => {
    // when: year 없이 화면을 연다 (전제: 앱 시계 2030-06-15)
    await renderAt('/forecast')
    // then: 연도 칸이 2030이고 2031 선택지가 있으며 2026은 없다
    const year = await screen.findByLabelText('연도')
    expect(year).toHaveValue('2030')
    expect(within(year).getByRole('option', { name: '2031' })).toBeInTheDocument()
    expect(within(year).queryByRole('option', { name: '2026' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-048
  it('URL의 연도는 그대로 쓴다', async () => {
    // when: year=2031로 화면을 연다 (전제: 앱 시계 2030-06-15)
    await renderAt('/forecast?year=2031')
    // then: 연도 칸이 2031이다
    expect(await screen.findByLabelText('연도')).toHaveValue('2031')
  })
})
