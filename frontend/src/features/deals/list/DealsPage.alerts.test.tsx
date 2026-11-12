import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

describe('목록과 경고 기준', () => {
  // 경고 기준을 저장하면 목록 범례와 행 경고가 새 기준으로 바뀐다.
  // 테스트 코드: RK-053
  it('writes the saved threshold into the legend and recolors rows after the save', async () => {
    // given: admin이 연 목록에서 새론병원 PAM 행이 미업데이트다
    const { client } = await renderAt('/deals?q=새론병원 PAM', { role: 'admin' })
    const row = await rowOf(/새론병원 PAM/)
    expect(within(row).getByText('미업데이트')).toBeVisible()

    // when: 경고 기준을 30일로 저장하고 캐시를 무효화한다
    await gateway.alerts.save(30)
    await client.invalidateQueries()

    // then: 범례가 '30일 이상 미업데이트'가 되고 그 행의 미업데이트 배지가 사라진다
    const legend = await screen.findByRole('list', { name: 'Risk 범례' })
    await waitFor(() => expect(within(legend).getByText('30일 이상 미업데이트')).toBeVisible())
    await waitFor(async () => expect(within(await rowOf(/새론병원 PAM/)).queryByText('미업데이트')).not.toBeInTheDocument())
  })

  // 목록에는 체류 일수 열이나 문구가 없다.
  // 테스트 코드: RK-054
  it('has no stay-days column or text in the list (the stay is shown on the detail only)', async () => {
    // when: Deals 목록을 연다
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    // then: '체류' 열 머리글도 'N일째' 문구도 없고 열은 13개다
    expect(screen.queryByRole('columnheader', { name: /체류/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/\d+일째/)).not.toBeInTheDocument()
    expect(screen.getAllByRole('columnheader')).toHaveLength(13)
  })
})

describe('범례 로딩 (R3 Minor 3)', () => {
  // 경고 기준을 읽는 동안 범례에 숫자를 빼고 응답이 오면 저장된 숫자를 보인다.
  // 테스트 코드: RK-052
  it('omits the threshold number while the alert settings are loading, then shows the saved one', async () => {
    // given: 경고 기준 응답이 아직 오지 않았다(보류 중인 Promise)
    let release: (value: Awaited<ReturnType<typeof gateway.alerts.get>>) => void = () => {}
    const pending = new Promise<Awaited<ReturnType<typeof gateway.alerts.get>>>((resolve) => {
      release = resolve
    })
    const spy = vi.spyOn(gateway.alerts, 'get').mockReturnValue(pending)
    try {
      // when: Deals 목록을 연다
      await renderAt(ALL_DEALS)
      const legend = await screen.findByRole('list', { name: 'Risk 범례' })
      // then: 범례는 '기준일 이상 미업데이트'이고 응답(30일)이 오면 '30일 이상 미업데이트'가 된다
      expect(within(legend).getByText('기준일 이상 미업데이트')).toBeVisible()
      expect(within(legend).queryByText(/\d+일 이상 미업데이트/)).not.toBeInTheDocument()

      release({ staleDays: 30, updatedAt: null, updatedBy: null })
      expect(await within(legend).findByText('30일 이상 미업데이트')).toBeVisible()
    } finally {
      spy.mockRestore()
    }
  })
})
