import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { formatWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { dealInput } from '../../test/fake/testing'
import { snapshotNotFoundMessage } from '../../test/fake/gateway/forecastSnapshots'
import { USER_ID } from '../../test/fake/seed/ids'
import { SNAPSHOT_COMMIT_NAME, SNAPSHOT_PERIOD } from '../../test/fixtures/forecastSnapshot'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'

/**
 * 화면 "기준 시점" 선택. 지금(실시간) 또는 월말 스냅숏을 고르면 표·카드가 스냅숏 값으로 바뀌고
 * "기준: 2026-09 월말(생성 …)"이 보이며, Vendor 필터는 비활성(안내), 담당자 Deal 목록은 숨겨진다.
 * 선택은 URL `snap=2026-09`로 유지된다. 스냅숏 값은 `test/fixtures/forecastSnapshot.ts`의 고정값이다.
 */
const NOW = '2026-10-15T09:00:00+09:00'
const Q3 = '/forecast?year=2026&quarter=3'
const SNAP_Q3 = `${Q3}&snap=${SNAPSHOT_PERIOD}`
const VENDOR_NOTICE = '스냅숏에서는 Vendor 필터를 사용할 수 없습니다.'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const cellText = (count: number, amount: number): string => (count === 0 ? '—' : `${count}건 · ${formatWon(amount)}`)

// 생성 시각은 서버 문자열의 오프셋 벽시계 그대로 보인다(SNAPSHOT_TAKEN_AT = 2026-10-01T00:05:00+09:00). 브라우저 시간대로 바꾸지 않는다.
const SNAPSHOT_BASIS = `기준: ${SNAPSHOT_PERIOD} 월말(생성 2026-10-01 00:05)`

/** 표의 행(rowheader 이름)에서 셀 텍스트를 읽는다. */
function readRow(name: string | RegExp): string[] {
  const tr = screen.getByRole('rowheader', { name }).closest('tr')
  if (!tr) throw new Error('행을 찾지 못했습니다.')
  return within(tr)
    .getAllByRole('cell')
    .map((c) => c.textContent?.trim() ?? '')
}

describe('기준 시점 선택', () => {
  // 테스트 코드: FC-073
  it('"지금"과 저장된 스냅숏마다 선택지를 보이고 기본은 "지금"이다', async () => {
    // when: 저장된 스냅숏이 있는 화면을 연다
    await renderAt(Q3)
    const select = await screen.findByLabelText('기준 시점')

    // then: 선택지가 "지금"과 "2026-09 월말"이고 기본 값은 "지금"이다
    await waitFor(() =>
      expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['지금', `${SNAPSHOT_PERIOD} 월말`]),
    )
    expect(select).toHaveValue('')
  })

  // 테스트 코드: FC-073
  it('스냅숏이 없으면 "지금"만 보인다', async () => {
    // when: 스냅숏이 없는 시드로 화면을 연다
    await renderAt(Q3, { seed: 'empty' })
    const select = await screen.findByLabelText('기준 시점')

    // then: 선택지가 "지금"뿐이다
    await screen.findByText(/^기준: 지금\(/)
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['지금'])
  })

  // 테스트 코드: FC-074
  it('스냅숏을 고르면 URL에 snap이 생기고 다른 필터는 유지된다', async () => {
    // given: 담당자가 걸린 2026 Q3 화면과 읽어 온 스냅숏 목록
    const { user, location } = await renderAt(`${Q3}&owner=${USER_ID.kim}`)
    await screen.findByRole('rowheader', { name: '합계' })
    await waitFor(() => expect(within(screen.getByLabelText('기준 시점')).getAllByRole('option')).toHaveLength(2))

    // when: "2026-09 월말"을 고른다
    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)

    // then: URL에 snap이 생기고 연도·분기·담당자는 그대로이며 선택값이 스냅숏이다
    await waitFor(() => expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`))
    expect(location()).toContain('year=2026')
    expect(location()).toContain('quarter=3')
    expect(location()).toContain(`owner=${USER_ID.kim}`)
    expect(screen.getByLabelText('기준 시점')).toHaveValue(SNAPSHOT_PERIOD)
  })

  // 테스트 코드: FC-074
  it('"지금"을 다시 고르면 snap이 지워지고 실시간 기준 문구가 나온다', async () => {
    // given: 스냅숏 기준으로 열린 화면
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByText(SNAPSHOT_BASIS)

    // when: "지금"을 고른다
    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')

    // then: URL에 snap이 없고 "기준: 지금(…)" 문구가 나오며 스냅숏 기준 문구는 사라진다
    await waitFor(() => expect(location()).not.toContain('snap='))
    expect(await screen.findByText(/^기준: 지금\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}\)$/)).toBeVisible()
    expect(screen.queryByText(SNAPSHOT_BASIS)).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-074
  it('URL의 snap으로 바로 스냅숏이 열린다', async () => {
    // when: snap이 담긴 URL로 화면을 연다
    await renderAt(SNAP_Q3)

    // then: 스냅숏 기준 문구가 보이고 선택값이 그 기준 월이다
    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('기준 시점')).toHaveValue(SNAPSHOT_PERIOD))
  })
})

describe('스냅숏 요약 표', () => {
  // 테스트 코드: FC-075
  it('저장된 열과 저장 당시 이름을 보이고 Deal 없던 저장 코드는 0건 열로 보인다', async () => {
    // when: 스냅숏 기준 2026 Q3 화면을 연다
    await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    // then: 머리글에 저장 당시 이름(확정(당시))과 Most Likely 열이 있고 현재 코드 이름은 없다
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)

    expect(headers).toEqual(['담당자', SNAPSHOT_COMMIT_NAME, 'Most Likely', 'Best', 'Pipeline', 'Total(Open)', 'Won'])
  })

  // 테스트 코드: FC-076
  it('담당자별·합계 행에 저장값을 보이고 저장된 Lost Deal은 보이지 않는다', async () => {
    // when: 스냅숏 기준 2026 Q3 화면을 연다
    await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    // then: 담당자·합계 행의 셀이 저장값이고 Lost 금액은 어디에도 없다
    expect(readRow('김영업')).toEqual([
      cellText(1, 50_000_000),
      cellText(0, 0),
      cellText(0, 0),
      cellText(2, 200_000_000),
      cellText(3, 250_000_000),
      cellText(1, 700_000_000),
    ])
    expect(readRow('박영업')).toEqual([
      cellText(0, 0),
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(0, 0),
    ])
    expect(readRow('합계')).toEqual([
      cellText(1, 50_000_000),
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(2, 200_000_000),
      cellText(4, 280_000_000),
      cellText(1, 700_000_000),
    ])
    expect(screen.queryByText(new RegExp(formatWon(999_000_000)))).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-076
  it('Deal을 추가해도 스냅숏 값은 그대로이고 실시간 표는 바뀐다', async () => {
    // given: 스냅숏 기준 화면의 저장값과 그 뒤 추가된 Deal
    const { user } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })
    const stored = readRow('합계')
    await gateway.deals.create(
      dealInput(USER_ID.kim, { name: '스냅숏 뒤 Deal', revenueDate: '2026-08-20', forecastKey: 'commit', revenueAmount: 9_000_000 }),
    )

    // when: "지금"으로 바꾼다
    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')
    await screen.findByText(/^기준: 지금\(/)
    // then: 실시간 표는 저장값과 다르다
    await waitFor(() => expect(readRow('합계')).not.toEqual(stored))
    // when: 다시 스냅숏으로 바꾼다
    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)
    await screen.findByText(SNAPSHOT_BASIS)

    // then: 저장값 그대로다
    await waitFor(() => expect(readRow('합계')).toEqual(stored))
  })

  // 테스트 코드: FC-077
  it('스냅숏 안에서도 기간 조건이 저장값을 거른다', async () => {
    // given: 스냅숏 기준 2026 Q3 화면
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    // when: Quarter를 4로 바꾼다
    await user.selectOptions(screen.getByLabelText('Quarter'), '4')

    // then: Q4 저장값(11월 셀)만 보이고 snap은 유지된다
    await waitFor(() => expect(readRow('합계')).toEqual([
      cellText(0, 0),
      cellText(0, 0),
      cellText(0, 0),
      cellText(1, 5_000_000),
      cellText(1, 5_000_000),
      cellText(0, 0),
    ]))
    expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`)
  })

  // 테스트 코드: FC-077
  it('스냅숏 안에서도 담당자 조건이 저장값을 거른다', async () => {
    // when: 담당자 조건이 걸린 스냅숏 화면을 연다
    await renderAt(`${SNAP_Q3}&owner=${USER_ID.park}`)
    await screen.findByRole('rowheader', { name: '합계' })

    // then: 그 담당자 행만 있다
    expect(screen.getByRole('rowheader', { name: '박영업' })).toBeInTheDocument()
    expect(screen.queryByRole('rowheader', { name: '김영업' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-078
  it('스냅숏 기준 문구는 기준 월과 생성 시각을 보인다', async () => {
    // when: 스냅숏 기준 화면을 연다
    await renderAt(SNAP_Q3)

    // then: "기준: 2026-09 월말(생성 …)"이 보이고 실시간 기준 문구는 없다
    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    expect(screen.queryByText(/^기준: 지금\(/)).not.toBeInTheDocument()
  })
})

describe('스냅숏에서는 Vendor 필터와 담당자 Deal 목록을 쓰지 않는다', () => {
  // 테스트 코드: FC-079
  it('Vendor 칸을 비활성으로 하고 이유를 안내한다', async () => {
    // when: 스냅숏 기준 화면을 연다
    await renderAt(SNAP_Q3)
    // then: Vendor 칸이 비활성이고 안내 문구가 보인다
    await screen.findByText(SNAPSHOT_BASIS)

    expect(screen.getByLabelText('Vendor')).toBeDisabled()
    expect(screen.getByText(VENDOR_NOTICE)).toBeVisible()
  })

  // 테스트 코드: FC-079
  it('실시간에서는 Vendor 칸이 활성이고 안내가 없다', async () => {
    // when: 실시간 화면을 연다
    await renderAt(Q3)
    // then: Vendor 칸이 활성이고 안내 문구가 없다
    await screen.findByText(/^기준: 지금\(/)

    expect(screen.getByLabelText('Vendor')).toBeEnabled()
    expect(screen.queryByText(VENDOR_NOTICE)).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-079
  it('URL의 Vendor를 스냅숏 요청에 보내지 않는다 (서버는 422로 거절한다)', async () => {
    // when: Vendor가 담긴 URL로 스냅숏 화면을 연다
    await renderAt(`${SNAP_Q3}&vendor=${seedVendorId('Silverfort')}`)

    // then: 오류 배너 없이 저장값 그대로의 표가 보인다
    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(readRow('합계')).toEqual([
      cellText(1, 50_000_000),
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(2, 200_000_000),
      cellText(4, 280_000_000),
      cellText(1, 700_000_000),
    ])
  })

  // 테스트 코드: FC-080
  it('URL이 담당자를 골라도 담당자 Deal 목록을 숨긴다', async () => {
    // when: 담당자가 선택된 URL로 스냅숏 화면을 연다
    await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    // then: 담당자 영역이 없다
    await screen.findByText(SNAPSHOT_BASIS)

    expect(screen.queryByRole('region', { name: /^선택한 담당자/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-080
  it('실시간에서는 담당자 Deal 목록이 그대로 나온다 (대조)', async () => {
    // when: 담당자가 선택된 실시간 화면을 연다
    await renderAt(`${Q3.replace('quarter=3', 'quarter=4')}&sel=${USER_ID.kim}`)

    // then: 담당자 영역이 보인다
    expect(await screen.findByRole('region', { name: '선택한 담당자: 김영업' })).toBeVisible()
  })
})

describe('스냅숏에서는 요약 표의 담당자를 선택할 수 없다', () => {
  // 테스트 코드: FC-080
  it('담당자 이름이 버튼이 아닌 글자로 보인다', async () => {
    // when: 스냅숏 기준 화면을 연다
    await renderAt(SNAP_Q3)
    // then: 이름이 행 머리글이고 버튼은 없다
    await screen.findByRole('rowheader', { name: '합계' })

    expect(screen.getByRole('rowheader', { name: '김영업' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '김영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '박영업' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-080
  it('담당자 이름을 눌러도 URL에 sel이 생기지 않는다', async () => {
    // given: 스냅숏 기준 화면
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    // when: 담당자 이름을 누른다
    await user.click(within(screen.getByRole('table', { name: '담당자별 Forecast 요약' })).getByText('김영업'))

    // then: URL에 sel이 없고 snap은 그대로다
    expect(location()).not.toContain('sel=')
    expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`)
  })

  // 테스트 코드: FC-080
  it('URL에 sel이 있어도 선택 표시를 하지 않는다', async () => {
    // when: sel이 담긴 URL로 스냅숏 화면을 연다
    await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    // then: 선택 표시(aria-pressed, 강조 행)가 없다
    await screen.findByText(SNAPSHOT_BASIS)

    expect(document.querySelector('[aria-pressed]')).toBeNull()
    expect(document.querySelector('tr.fc-selected')).toBeNull()
  })

  // 테스트 코드: FC-080
  it('실시간에서는 담당자를 고를 수 있다 (대조)', async () => {
    // given: 실시간 화면
    const { user, location } = await renderAt(Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    // when: 담당자 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '김영업' }))

    // then: URL에 sel이 생긴다
    await waitFor(() => expect(location()).toContain(`sel=${USER_ID.kim}`))
  })

  // 테스트 코드: FC-080
  it('실시간에서 스냅숏으로 바꾸면 선택한 담당자가 지워진다', async () => {
    // given: 담당자가 선택된 실시간 화면
    const { user, location } = await renderAt(`${Q3}&sel=${USER_ID.kim}`)
    await screen.findByRole('rowheader', { name: '합계' })
    await waitFor(() => expect(within(screen.getByLabelText('기준 시점')).getAllByRole('option')).toHaveLength(2))

    // when: 스냅숏을 고른다
    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)

    // then: URL에 snap이 있고 sel은 없다
    await waitFor(() => expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`))
    expect(location()).not.toContain('sel=')
  })

  // 테스트 코드: FC-080
  it('다시 "지금"으로 돌아와도 담당자 목록이 열리지 않는다', async () => {
    // given: sel이 담긴 URL의 스냅숏 화면
    const { user, location } = await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    await screen.findByText(SNAPSHOT_BASIS)

    // when: "지금"을 고른다
    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')

    // then: URL에 sel이 없고 담당자 영역도 없다
    await screen.findByText(/^기준: 지금\(/)
    expect(location()).not.toContain('sel=')
    expect(screen.queryByRole('region', { name: /^선택한 담당자/ })).not.toBeInTheDocument()
  })
})

describe('스냅숏 오류', () => {
  // 테스트 코드: FC-081
  it('스냅숏 목록을 읽지 못하면 필터 안에 오류 배너를 보이고 실시간 요약은 그대로 보인다', async () => {
    // given: 실패하는 스냅숏 목록 조회
    vi.spyOn(gateway.forecast, 'snapshots').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '스냅숏 목록을 불러오지 못했습니다.' }),
    )
    // when: 실시간 화면을 연다
    await renderAt(Q3)

    // then: 서버 문구의 배너, 실시간 기준 문구, 필터 안의 배너가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('스냅숏 목록을 불러오지 못했습니다.')
    expect(await screen.findByText(/^기준: 지금\(/)).toBeVisible()
    expect(within(screen.getByRole('form', { name: 'Forecast 필터' })).getByRole('alert')).toBeVisible()
  })

  // 테스트 코드: FC-081
  it('없는 기준 월이면 서버 404 문구를 배너로 보인다', async () => {
    // when: 저장되지 않은 기준 월로 화면을 연다
    await renderAt(`${Q3}&snap=2026-08`)

    // then: "…스냅숏이 없습니다: 2026-08"이 배너로 보이고 필터는 그대로다
    expect(await screen.findByRole('alert')).toHaveTextContent(snapshotNotFoundMessage('2026-08'))
    expect(screen.getByRole('form', { name: 'Forecast 필터' })).toBeVisible()

    // then: 기준 시점에 목록에 없는 "2026-08 월말"이 선택지로 더해져 선택되어 있다
    const snap = screen.getByLabelText('기준 시점')
    expect(within(snap).getByRole('option', { name: '2026-08 월말' })).toBeInTheDocument()
    expect(snap).toHaveValue('2026-08')
  })

  // 테스트 코드: FC-081
  it('형식이 틀린 snap 값은 무시하고 실시간으로 보인다', async () => {
    // when: 형식이 틀린 snap으로 화면을 연다
    await renderAt(`${Q3}&snap=2026-9`)

    // then: 실시간 기준 문구가 보이고 오류 배너는 없다
    expect(await screen.findByText(/^기준: 지금\(/)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
