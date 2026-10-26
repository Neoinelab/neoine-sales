import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { formatThousandWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { dealInput } from '../../test/fake/testing'
import { SNAPSHOT_NOT_FOUND } from '../../test/fake/gateway/forecastSnapshots'
import { USER_ID } from '../../test/fake/seed/ids'
import { SNAPSHOT_COMMIT_NAME, SNAPSHOT_PERIOD } from '../../test/fixtures/forecastSnapshot'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'

/**
 * P6 R2 AC-18: 화면 "기준 시점" 선택. 지금(실시간) 또는 월말 스냅숏을 고르면 표·카드가 스냅숏 값으로 바뀌고
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

const cellText = (count: number, amount: number): string => (count === 0 ? '—' : `${count}건 · ${formatThousandWon(amount)}`)

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
  it('offers 지금 and each stored snapshot, and starts on 지금', async () => {
    await renderAt(Q3)
    const select = await screen.findByLabelText('기준 시점')

    await waitFor(() =>
      expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['지금', `${SNAPSHOT_PERIOD} 월말`]),
    )
    expect(select).toHaveValue('')
  })

  it('offers only 지금 when no snapshot is stored', async () => {
    await renderAt(Q3, { seed: 'empty' })
    const select = await screen.findByLabelText('기준 시점')

    await screen.findByText(/^기준: 지금\(/)
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['지금'])
  })

  it('selecting a snapshot puts snap in the URL and keeps the other filters', async () => {
    const { user, location } = await renderAt(`${Q3}&owner=${USER_ID.kim}`)
    await screen.findByRole('rowheader', { name: '합계' })
    await waitFor(() => expect(within(screen.getByLabelText('기준 시점')).getAllByRole('option')).toHaveLength(2))

    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)

    await waitFor(() => expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`))
    expect(location()).toContain('year=2026')
    expect(location()).toContain('quarter=3')
    expect(location()).toContain(`owner=${USER_ID.kim}`)
    expect(screen.getByLabelText('기준 시점')).toHaveValue(SNAPSHOT_PERIOD)
  })

  it('selecting 지금 again removes snap and shows the live as-of line', async () => {
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByText(SNAPSHOT_BASIS)

    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')

    await waitFor(() => expect(location()).not.toContain('snap='))
    expect(await screen.findByText(/^기준: 지금\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}\)$/)).toBeVisible()
    expect(screen.queryByText(SNAPSHOT_BASIS)).not.toBeInTheDocument()
  })

  it('opens straight on the snapshot named by the URL', async () => {
    await renderAt(SNAP_Q3)

    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('기준 시점')).toHaveValue(SNAPSHOT_PERIOD))
  })
})

describe('스냅숏 요약 표', () => {
  it('shows the stored columns, the stored name and no column for codes the snapshot never used', async () => {
    await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)

    expect(headers).toEqual(['담당자', SNAPSHOT_COMMIT_NAME, 'Best', 'Pipeline', 'Total(Open)', 'Won'])
  })

  it('shows the stored values per owner and in the total row, without the stored Lost deals', async () => {
    await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    expect(readRow('김영업')).toEqual([
      cellText(1, 50_000_000),
      cellText(0, 0),
      cellText(2, 200_000_000),
      cellText(3, 250_000_000),
      cellText(1, 700_000_000),
    ])
    expect(readRow('박영업')).toEqual([
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(0, 0),
      cellText(1, 30_000_000),
      cellText(0, 0),
    ])
    expect(readRow('합계')).toEqual([
      cellText(1, 50_000_000),
      cellText(1, 30_000_000),
      cellText(2, 200_000_000),
      cellText(4, 280_000_000),
      cellText(1, 700_000_000),
    ])
    expect(screen.queryByText(new RegExp(formatThousandWon(999_000_000)))).not.toBeInTheDocument()
  })

  it('keeps the stored values after a deal is added, while the live table changes', async () => {
    const { user } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })
    const stored = readRow('합계')
    await gateway.deals.create(
      dealInput(USER_ID.kim, { name: '스냅숏 뒤 Deal', revenueDate: '2026-08-20', forecastKey: 'commit', revenueAmount: 9_000_000 }),
    )

    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')
    await screen.findByText(/^기준: 지금\(/)
    await waitFor(() => expect(readRow('합계')).not.toEqual(stored))
    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)
    await screen.findByText(SNAPSHOT_BASIS)

    await waitFor(() => expect(readRow('합계')).toEqual(stored))
  })

  it('follows the period filters inside the snapshot', async () => {
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    await user.selectOptions(screen.getByLabelText('Quarter'), '4')

    await waitFor(() => expect(readRow('합계')).toEqual([
      cellText(0, 0),
      cellText(0, 0),
      cellText(1, 5_000_000),
      cellText(1, 5_000_000),
      cellText(0, 0),
    ]))
    expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`)
  })

  it('narrows to one owner inside the snapshot', async () => {
    await renderAt(`${SNAP_Q3}&owner=${USER_ID.park}`)
    await screen.findByRole('rowheader', { name: '합계' })

    expect(screen.getByRole('rowheader', { name: '박영업' })).toBeInTheDocument()
    expect(screen.queryByRole('rowheader', { name: '김영업' })).not.toBeInTheDocument()
  })

  it('shows the snapshot basis instead of the live as-of line', async () => {
    await renderAt(SNAP_Q3)

    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    expect(screen.queryByText(/^기준: 지금\(/)).not.toBeInTheDocument()
  })
})

describe('스냅숏에서는 Vendor 필터와 담당자 Deal 목록을 쓰지 않는다', () => {
  it('disables the Vendor filter and says why', async () => {
    await renderAt(SNAP_Q3)
    await screen.findByText(SNAPSHOT_BASIS)

    expect(screen.getByLabelText('Vendor')).toBeDisabled()
    expect(screen.getByText(VENDOR_NOTICE)).toBeVisible()
  })

  it('keeps the Vendor filter enabled and silent for the live view', async () => {
    await renderAt(Q3)
    await screen.findByText(/^기준: 지금\(/)

    expect(screen.getByLabelText('Vendor')).toBeEnabled()
    expect(screen.queryByText(VENDOR_NOTICE)).not.toBeInTheDocument()
  })

  it('does not send the Vendor of the URL to a snapshot request (the server answers 422)', async () => {
    await renderAt(`${SNAP_Q3}&vendor=${seedVendorId('Silverfort')}`)

    expect(await screen.findByText(SNAPSHOT_BASIS)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(readRow('합계')).toEqual([
      cellText(1, 50_000_000),
      cellText(1, 30_000_000),
      cellText(2, 200_000_000),
      cellText(4, 280_000_000),
      cellText(1, 700_000_000),
    ])
  })

  it('hides the owner deal list even when the URL selects an owner', async () => {
    await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    await screen.findByText(SNAPSHOT_BASIS)

    expect(screen.queryByRole('region', { name: /^선택한 담당자/ })).not.toBeInTheDocument()
  })

  it('still shows the owner deal list for the live view (control)', async () => {
    await renderAt(`${Q3.replace('quarter=3', 'quarter=4')}&sel=${USER_ID.kim}`)

    expect(await screen.findByRole('region', { name: '선택한 담당자: 김영업' })).toBeVisible()
  })
})

describe('스냅숏에서는 요약 표의 담당자를 선택할 수 없다', () => {
  it('shows owner names as plain text, not as buttons', async () => {
    await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    expect(screen.getByRole('rowheader', { name: '김영업' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '김영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '박영업' })).not.toBeInTheDocument()
  })

  it('does not put sel in the URL when an owner name is clicked', async () => {
    const { user, location } = await renderAt(SNAP_Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    await user.click(within(screen.getByRole('table', { name: '담당자별 Forecast 요약' })).getByText('김영업'))

    expect(location()).not.toContain('sel=')
    expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`)
  })

  it('does not mark a row as selected even when the URL carries sel', async () => {
    await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    await screen.findByText(SNAPSHOT_BASIS)

    expect(document.querySelector('[aria-pressed]')).toBeNull()
    expect(document.querySelector('tr.fc-selected')).toBeNull()
  })

  it('still lets the live view select an owner (control)', async () => {
    const { user, location } = await renderAt(Q3)
    await screen.findByRole('rowheader', { name: '합계' })

    await user.click(screen.getByRole('button', { name: '김영업' }))

    await waitFor(() => expect(location()).toContain(`sel=${USER_ID.kim}`))
  })

  it('clears the selected owner when the basis moves from live to a snapshot', async () => {
    const { user, location } = await renderAt(`${Q3}&sel=${USER_ID.kim}`)
    await screen.findByRole('rowheader', { name: '합계' })
    await waitFor(() => expect(within(screen.getByLabelText('기준 시점')).getAllByRole('option')).toHaveLength(2))

    await user.selectOptions(screen.getByLabelText('기준 시점'), `${SNAPSHOT_PERIOD} 월말`)

    await waitFor(() => expect(location()).toContain(`snap=${SNAPSHOT_PERIOD}`))
    expect(location()).not.toContain('sel=')
  })

  it('does not reopen an owner list when the basis returns to live', async () => {
    const { user, location } = await renderAt(`${SNAP_Q3}&sel=${USER_ID.kim}`)
    await screen.findByText(SNAPSHOT_BASIS)

    await user.selectOptions(screen.getByLabelText('기준 시점'), '지금')

    await screen.findByText(/^기준: 지금\(/)
    expect(location()).not.toContain('sel=')
    expect(screen.queryByRole('region', { name: /^선택한 담당자/ })).not.toBeInTheDocument()
  })
})

describe('스냅숏 오류', () => {
  it('shows an error banner when the snapshot list cannot be loaded, and keeps the live view', async () => {
    vi.spyOn(gateway.forecast, 'snapshots').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '스냅숏 목록을 불러오지 못했습니다.' }),
    )
    await renderAt(Q3)

    expect(await screen.findByRole('alert')).toHaveTextContent('스냅숏 목록을 불러오지 못했습니다.')
    expect(await screen.findByText(/^기준: 지금\(/)).toBeVisible()
    expect(within(screen.getByRole('form', { name: 'Forecast 필터' })).getByRole('alert')).toBeVisible()
  })

  it('shows the server message when the chosen period has no snapshot', async () => {
    await renderAt(`${Q3}&snap=2025-01`)

    expect(await screen.findByRole('alert')).toHaveTextContent(SNAPSHOT_NOT_FOUND)
    expect(screen.getByRole('form', { name: 'Forecast 필터' })).toBeVisible()
  })

  it('ignores a malformed snap value and shows the live view', async () => {
    await renderAt(`${Q3}&snap=2026-9`)

    expect(await screen.findByText(/^기준: 지금\(/)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
