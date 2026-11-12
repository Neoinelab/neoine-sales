import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'

const RANGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

async function openAlerts(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/deal', { role })
  await view.user.click(await screen.findByRole('tab', { name: '경고 기준' }))
  const input = await screen.findByLabelText('미업데이트 기준(일)')
  return { ...view, input }
}

const saveButton = () => screen.getByRole('button', { name: '저장' })

describe('경고 기준 탭', () => {
  // 경고 기준은 Deal 관리의 마지막(여섯 번째) 탭이다.
  // 테스트 코드: RK-060
  it('is the last (sixth) tab of Deal management, after the Vendor tab', async () => {
    // when: admin이 Deal 관리를 연다
    await renderAt('/admin/deal', { role: 'admin' })

    const names = (await screen.findAllByRole('tab')).map((t) => t.textContent)

    // then: 탭 순서 끝에 '경고 기준'이 있다
    expect(names).toEqual(['Status 코드', 'Forecast 코드', 'BANT Label', 'Action 유형', 'Vendor', '경고 기준'])
  })

  // 현재 값(기본 14)을 보이고 저장 기록이 없음을 보인다.
  // 테스트 코드: RK-060
  it('shows the current threshold (default 14) and that nothing was saved yet', async () => {
    // when: 경고 기준 탭을 연다
    const { input } = await openAlerts()

    // then: 칸이 14이고 '마지막 저장' 문구가 없으며 저장이 비활성이다
    expect(input).toHaveValue(14)
    expect(screen.queryByText(/마지막 저장/)).not.toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  // 새 값을 저장하면 저장자와 시각을 보이고 다시 읽어도 유지된다.
  // 테스트 코드: RK-061
  it('saves a new value, shows who saved it and keeps the value after reload', async () => {
    // given: admin이 경고 기준 탭을 열었다
    const { user, input } = await openAlerts()

    // when: 30을 입력하고 저장을 누른다
    await user.clear(input)
    await user.type(input, '30')
    await user.click(saveButton())

    // then: '마지막 저장 … 최관리'가 보이고 칸이 30이며 다시 읽어도 30이다
    expect(await screen.findByText(/마지막 저장/)).toHaveTextContent('최관리')
    expect(input).toHaveValue(30)
    expect((await gateway.alerts.get()).staleDays).toBe(30)
  })

  // 범위 밖 값은 안내 문구를 보이고 저장을 막는다.
  // 테스트 코드: RK-062
  it.each(['0', '366'])('disables save and explains the range for %s', async (value) => {
    // given: admin이 경고 기준 탭을 열었다
    const { user, input } = await openAlerts()

    await user.clear(input)
    // when: 0 또는 366을 입력한다
    await user.type(input, value)

    // then: 저장이 비활성이고 범위 안내가 보이며 저장된 값은 14 그대로다
    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(RANGE)).toBeVisible()
    expect((await gateway.alerts.get()).staleDays).toBe(14)
  })

  // 빈 값은 안내 문구를 보이고 저장을 막는다.
  // 테스트 코드: RK-062
  it('disables save and explains the range for an empty input', async () => {
    // given: admin이 경고 기준 탭을 열었다
    const { user, input } = await openAlerts()

    // when: 입력을 비운다
    await user.clear(input)

    // then: 저장이 비활성이고 범위 안내가 보인다
    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(RANGE)).toBeVisible()
  })

  // 경계값 1과 365는 저장할 수 있다.
  // 테스트 코드: RK-062
  it.each(['1', '365'])('allows the boundary %s', async (value) => {
    // given: admin이 경고 기준 탭을 열었다
    const { user, input } = await openAlerts()

    // when: 1 또는 365를 입력하고 저장한다
    await user.clear(input)
    await user.type(input, value)
    await user.click(saveButton())

    // then: 저장된 값이 그 경계값이다
    await waitFor(async () => expect((await gateway.alerts.get()).staleDays).toBe(Number(value)))
  })

  // 저장된 값과 같으면 저장이 비활성이고 다른 유효한 값이면 활성이다.
  // 테스트 코드: RK-062
  it('keeps save disabled while the input equals the saved value and enables it for another valid value', async () => {
    // given: admin이 경고 기준 탭을 열었고 저장된 값은 14다
    const { user, input } = await openAlerts()
    expect(saveButton()).toBeDisabled()


    // when: 21을 입력한다
    await user.clear(input)
    await user.type(input, '21')
    // then: 저장이 활성이고 aria-invalid는 false다
    expect(saveButton()).toBeEnabled()
    expect(input).toHaveAttribute('aria-invalid', 'false')

    // when: 14로 되돌린다
    await user.clear(input)
    await user.type(input, '14')
    // then: 저장이 비활성이고 범위 오류가 없다
    expect(saveButton()).toBeDisabled()
    expect(screen.queryByText(RANGE)).not.toBeInTheDocument()

    // when: 366을 입력한다
    await user.clear(input)
    await user.type(input, '366')
    // then: aria-invalid가 true다
    expect(input).toHaveAttribute('aria-invalid', 'true')
  })

  // 서버가 거절하면 서버 문구를 오류 배너에 보인다.
  // 테스트 코드: RK-063
  it('shows the server sentence when the server refuses the value', async () => {
    const { user, input } = await openAlerts()
    // given: 서버가 저장을 422로 거절한다
    vi.spyOn(gateway.alerts, 'save').mockRejectedValueOnce(
      new ApiError(422, {
        type: 'https://sales.neoine.test/problems/validation',
        title: 'Validation',
        status: 422,
        detail: RANGE,
      }),
    )

    await user.clear(input)
    await user.type(input, '20')
    // when: 20을 입력하고 저장을 누른다
    await user.click(saveButton())

    // then: 오류 배너에 서버 문구가 보인다
    expect(await within(await screen.findByRole('alert')).findByText(RANGE)).toBeVisible()
    vi.restoreAllMocks()
  })

  // sales에게는 경고 기준 탭과 폼이 없다.
  // 테스트 코드: RK-064
  it('is hidden from sales: the tab and the form do not exist', async () => {
    // when: ?tab=alert 주소를 연다 (전제: sales로 로그인했다)
    await renderAt('/admin/deal?tab=alert', { role: 'sales' })

    // then: '경고 기준' 탭도 폼도 없다
    await waitFor(() => expect(screen.queryByRole('tab', { name: '경고 기준' })).not.toBeInTheDocument())
    expect(screen.queryByLabelText('미업데이트 기준(일)')).not.toBeInTheDocument()
  })

  // admin은 ?tab=alert 주소로 경고 기준 탭을 바로 연다.
  // 테스트 코드: RK-060
  it('opens directly from ?tab=alert for the admin', async () => {
    // when: ?tab=alert 주소를 연다
    await renderAt('/admin/deal?tab=alert', { role: 'admin' })

    // then: 미업데이트 기준 칸이 14다
    expect(await screen.findByLabelText('미업데이트 기준(일)')).toHaveValue(14)
  })
})
