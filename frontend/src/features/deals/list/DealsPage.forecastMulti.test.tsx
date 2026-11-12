import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, findFilterBar, forecastButton, openForecastPanel, toggleForecast } from './testHelpers'

/**
 * 목록 Forecast 조건 다중 선택. 체크할 때마다 바로 조회하고, 선택은 URL `forecast`
 * (알파벳순·중복 제거·콤마 → `%2C`)가 정본이다. 시드(샘플 픽스처): '새론병원 SSO'만 Lost.
 */

afterEach(() => vi.restoreAllMocks())

const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
const forecastCells = () => screen.getAllByRole('button', { name: /Forecast 편집/ }).map((b) => b.textContent ?? '')

describe('selecting several forecasts', () => {
  // 체크한 Forecast 중 하나인 Deal을 보이고 정렬된 key를 URL에 쓴다
  // 테스트 코드: DL-073
  it('lists the deals of any checked forecast and puts the sorted keys in the URL', async () => {
    // given: 시드 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await toggleForecast(user, 'Pipeline')
    // when: Forecast 패널에서 여러 코드를 체크한다
    await toggleForecast(user, 'Best')

    // then: URL에 정렬된 key가 콤마로 쓰이고 해당 Deal이 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline'))
    expect(forecastButton('2개 선택')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['best', 'pipeline'] }))
    const expected = (await gateway.deals.list({ forecastKeys: ['best', 'pipeline'], limit: 20 })).items.length
    expect(expected).toBeGreaterThan(0)
    await waitFor(() => expect(dataRows()).toHaveLength(expected))
    for (const text of forecastCells()) expect(text).toMatch(/Pipeline|Best/)
  })

  // 하나만 체크하면 단일 값으로 쓴다
  // 테스트 코드: DL-073
  it('writes one key as a plain value', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt('/deals?year=2026')
    await screen.findByRole('search', { name: 'Deal 필터' })

    // when: 코드 하나를 체크한다
    await toggleForecast(user, 'Pipeline')

    // then: URL forecast가 그 key 하나다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&forecast=pipeline'))
    expect(forecastButton('Pipeline')).toBeInTheDocument()
  })

  // 하나를 해제해도 나머지는 남는다
  // 테스트 코드: DL-073
  it('removes a key again and keeps the others', async () => {
    // given: 두 코드를 체크한 목록
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })

    // when: 하나를 해제한다
    await toggleForecast(user, 'Pipeline')

    // then: 나머지 key만 URL에 남는다
    await waitFor(() => expect(location()).toBe('/deals?year=2026&forecast=best'))
  })

  // 선택이 바뀌면 1페이지로 돌아간다
  // 테스트 코드: DL-068
  it('goes back to page 1 when the selection changes', async () => {
    // given: 2페이지를 보던 목록
    const { user, location } = await renderAt('/deals?year=all&sort=revenueAmount&order=desc&page=2')
    await screen.findByRole('button', { name: '이전' })

    // when: Forecast를 체크한다
    await toggleForecast(user, 'Pipeline')

    // then: page 키가 사라진다
    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=revenueAmount&order=desc&forecast=pipeline'))
  })

  // Forecast 코드를 코드 순서의 체크박스로 보인다
  // 테스트 코드: DL-073
  it('lists the forecast codes in code order as checkboxes of the Forecast group', async () => {
    // given: Forecast 패널
    const { user } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 패널을 연다
    const panel = await openForecastPanel(user)

    // then: 현재 코드 순서대로 체크박스가 있다
    expect(panel.getAllByRole('checkbox').map((c) => c.getAttribute('value'))).toEqual([
      'pipeline',
      'best',
      'most_likely',
      'commit',
      'won',
      'lost',
    ])
  })

  // 체크한 순서와 무관하게 같은 URL이 된다
  // 테스트 코드: DL-073
  it('gives the same URL whatever order the boxes are checked in', async () => {
    // given: 시드 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await toggleForecast(user, 'Best')
    // when: Best 다음 Pipeline 순서로 체크한다
    await toggleForecast(user, 'Pipeline')
    // then: URL에 두 코드가 정렬돼 들어간다
    await waitFor(() => expect(location()).toContain('forecast=best%2Cpipeline'))
    const bestFirst = location()
    // when: 전체로 되돌린다
    await user.click((await openForecastPanel(user)).getByRole('button', { name: '전체' }))
    // then: 조건 없는 목록 주소가 된다
    await waitFor(() => expect(location()).toBe(ALL_DEALS))

    // when: 이번에는 Pipeline 다음 Best 순서로 체크한다
    await toggleForecast(user, 'Pipeline')
    await toggleForecast(user, 'Best')

    // then: URL이 앞선 순서의 결과와 같다
    await waitFor(() => expect(location()).toContain('forecast=best%2Cpipeline'))
    expect(location()).toBe(bestFirst)
    expect(bestFirst).toBe('/deals?year=all&forecast=best%2Cpipeline')
  })
})

describe('clearing the selection', () => {
  // 모두 끄면 '전체'이고 URL에서 키가 지워진다
  // 테스트 코드: DL-073
  it('shows 전체 and drops forecast from the URL when every box is off', async () => {
    // given: 코드를 체크한 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })

    await toggleForecast(user, 'Best')
    // when: 모두 해제한다
    await toggleForecast(user, 'Pipeline')

    // then: 요약이 전체이고 forecast 키가 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(forecastButton('전체')).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).not.toHaveProperty('forecastKeys'))
  })

  // 패널의 전체 버튼으로 지운다
  // 테스트 코드: DL-073
  it('clears with the 전체 button of the panel', async () => {
    // given: 코드를 체크한 목록
    const { user, location } = await renderAt('/deals?year=2026&forecast=best%2Cpipeline')
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })
    const panel = await openForecastPanel(user)

    // when: 전체 버튼을 누른다
    await user.click(panel.getByRole('button', { name: '전체' }))

    // then: forecast 키가 지워진다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(forecastButton('전체')).toBeInTheDocument()
  })

  // 마지막 조건을 지우면 year=all로 남는다
  // 테스트 코드: DL-069
  it('leaves year=all when the last condition is removed', async () => {
    // given: Forecast만 걸린 목록
    const { user, location } = await renderAt('/deals?forecast=best')
    await screen.findByRole('button', { name: 'Forecast Best' })

    // when: Forecast를 모두 해제한다
    await toggleForecast(user, 'Best')

    // then: 주소가 year=all이다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 패널 전체 버튼으로 마지막 조건을 지워도 year=all이다
  // 테스트 코드: DL-069
  it('leaves year=all after the panel 전체 button removes the only condition', async () => {
    // given: Forecast만 걸린 목록
    const { user, location } = await renderAt('/deals?year=all&forecast=best')
    await screen.findByRole('button', { name: 'Forecast Best' })
    const panel = await openForecastPanel(user)

    // when: 패널의 전체 버튼을 누른다
    await user.click(panel.getByRole('button', { name: '전체' }))

    // then: 주소가 year=all이다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })
})

describe('summary text', () => {
  const NOT_LOST = 'best%2Ccommit%2Cmost_likely%2Cpipeline%2Cwon'
  const OPEN = 'best%2Ccommit%2Cmost_likely%2Cpipeline'

  // 선택에 따라 Forecast 버튼 요약 문구가 달라진다
  // 테스트 코드: DL-074
  it.each([
    ['Lost 제외', NOT_LOST],
    ['Open 전체', OPEN],
    ['모두 선택', `${NOT_LOST}%2Clost`],
    ['3개 선택', 'best%2Ccommit%2Clost'],
  ])('shows %s', async (summary, value) => {
    // when: 그 주소를 연다
    await renderAt(`/deals?year=all&forecast=${value}`)

    // then: 버튼 요약이 기대한 문구다
    expect(await (await findFilterBar()).findByRole('button', { name: `Forecast ${summary}` })).toBeInTheDocument()
  })

  // Lost 제외 URL이면 해당 체크박스가 체크된다
  // 테스트 코드: DL-074
  it('checks the matching boxes for the Lost 제외 URL', async () => {
    // given: Lost 제외를 뜻하는 주소
    const { user } = await renderAt(`/deals?year=all&forecast=${NOT_LOST}`)
    // when: 패널을 연다
    const panel = await openForecastPanel(user)

    // then: Lost가 아닌 코드가 모두 체크돼 있다
    expect(panel.getByRole('checkbox', { name: 'Won' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Lost' })).not.toBeChecked()
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(5)
  })
})

describe('old and malformed addresses', () => {
  // 예전 단일 값은 코드 하나가 체크된 상태로 연다
  // 테스트 코드: DL-075
  it('opens an old single value as one checked code', async () => {
    // given: forecast=won 주소
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 그 주소를 연다
    const { user } = await renderAt('/deals?year=all&forecast=commit')

    // then: 코드 하나가 체크돼 있다
    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast Commit' })).toBeInTheDocument()
    const panel = await openForecastPanel(user)
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(1)
    expect(panel.getByRole('checkbox', { name: 'Commit' })).toBeChecked()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['commit'] }))
  })

  // 형식이 틀린 항목은 버리고 나머지는 쓴다
  // 테스트 코드: DL-075
  it('drops a key with a wrong format and keeps the rest', async () => {
    // given: 틀린 key가 섞인 주소
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 그 주소를 연다
    await renderAt('/deals?year=all&forecast=Commit%2Cbest')

    // then: 올바른 key만 조건으로 쓰인다
    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast Best' })).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['best'] }))
  })

  // 형식은 맞지만 코드에 없는 key는 그대로 보낸다
  // 테스트 코드: DL-075
  it('sends a well formed key that no code has, shows it only in the summary', async () => {
    // given: 없는 코드 key가 든 주소
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 그 주소를 연다
    const { user } = await renderAt('/deals?year=all&forecast=no_such')

    // then: 요약에만 보이고 조회에는 실린다
    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast no_such' })).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(list)).toMatchObject({ forecastKeys: ['no_such'] }))
    expect(await screen.findByText('총 0건')).toBeVisible()
    const panel = await openForecastPanel(user)
    expect(panel.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)).toHaveLength(0)
  })

  // 서로 다른 key가 100개를 넘으면 조건 전체를 무시한다
  // 테스트 코드: DL-075
  it('ignores the whole condition above one hundred distinct keys', async () => {
    // given: key가 101개인 주소
    const list = vi.spyOn(gateway.deals, 'list')
    const many = Array.from({ length: 101 }, (_, i) => `k${i}`).join('%2C')
    // when: 그 주소를 연다
    await renderAt(`/deals?year=all&forecast=${many}`)

    // then: forecast 조건이 조회에 실리지 않는다
    expect(await (await findFilterBar()).findByRole('button', { name: 'Forecast 전체' })).toBeInTheDocument()
    await waitFor(() => expect(list).toHaveBeenCalled())
    expect(lastQuery(list)).not.toHaveProperty('forecastKeys')
  })
})

describe('list memory', () => {
  // 선택을 기억해 상세에 다녀와도 같은 체크가 복원된다
  // 테스트 코드: DL-096
  it('remembers the selection and restores the same boxes after a detail round trip', async () => {
    // given: Forecast를 고른 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await toggleForecast(user, 'Pipeline')
    // when: Best도 체크한다
    await toggleForecast(user, 'Best')
    // then: 주소와 기억에 두 코드가 담긴다
    await waitFor(() => expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline'))
    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toContain('forecast=best%2Cpipeline'))
    // when: 패널을 닫고 상세에 갔다가 목록으로 돌아온다
    await user.keyboard('{Escape}')
    const row = dataRows()[0] as HTMLElement
    await user.click(within(row).getAllByRole('link')[0] as HTMLElement)
    await user.click(await screen.findByRole('link', { name: '← 목록' }))

    // then: 같은 체크박스가 체크돼 있다
    await screen.findByRole('button', { name: 'Forecast 2개 선택' })
    expect(location()).toBe('/deals?year=all&forecast=best%2Cpipeline')
    const panel = await openForecastPanel(user)
    expect(panel.getByRole('checkbox', { name: 'Pipeline' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Best' })).toBeChecked()
    expect(panel.getByRole('checkbox', { name: 'Commit' })).not.toBeChecked()
  })
})

describe('closing the panel', () => {
  // Escape로 닫으면 포커스가 Forecast 버튼으로 돌아온다
  // 테스트 코드: DL-073
  it('closes with Escape and returns the focus to the Forecast button', async () => {
    // given: 열린 Forecast 패널
    const { user } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await openForecastPanel(user)

    // when: Escape를 누른다
    await user.keyboard('{Escape}')

    // then: 패널이 닫히고 포커스가 Forecast 버튼이다
    expect(screen.queryByRole('group', { name: 'Forecast' })).not.toBeInTheDocument()
    expect(forecastButton()).toHaveFocus()
  })
})
