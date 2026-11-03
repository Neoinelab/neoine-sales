import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, paramsOf, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

/**
 * 미팅 날짜 검색은 Deals 목록의 '최종 업데이트'와 같은 조건이다(AC1~AC5).
 * 기준일 2027-03-15(시드 미팅은 1~12일 전). 서버 프리셋 2w = 2027-03-01 ~ 2027-03-15.
 */
beforeEach(pinClock)
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

const bar = () => within(screen.getByRole('search', { name: '미팅 기록 검색' }))
const select = () => bar().getByRole('combobox', { name: '미팅 날짜' })
const TWO_WEEKS = { from: '2027-03-01', to: '2027-03-15' }
/** 시드 중 2027-03-10 이후(1~5일 전)의 미팅 내용, 미팅 날짜 내림차순. */
const SINCE_MAR_10 = ['계약 종료 후 정리', 'ITDR 가격 협상', '수주 후 일정 점검', 'SSO 제안 설명', 'ZTNA 계약 조건 협의']

/** 서버 프리셋의 2w만 좁은 범위(03-10~03-15)로 바꿔 프리셋이 실제로 검색 범위로 쓰이는지 가른다. */
function narrowTwoWeeks(range = { from: '2027-03-10', to: '2027-03-15' }) {
  const original = gateway.deals.updatedPeriods.bind(gateway.deals)
  return vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
    const real = await original()
    return { ...real, periods: real.periods.map((p) => (p.key === '2w' ? { ...p, ...range } : p)) }
  })
}

const lastList = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>

describe('선택지 (AC1)', () => {
  it('replaces the two date inputs with one select offering the same seven options as Deals', async () => {
    await renderAt(PAGE)
    await waitForRows(10)

    expect(select()).toHaveDisplayValue('전체')
    const labels = within(select()).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 끝' })).not.toBeInTheDocument()
  })

  it('enables the presets the server returned and disables the one it did not', async () => {
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      const real = await original()
      return { ...real, periods: real.periods.filter((p) => p.key !== '6m') }
    })
    await renderAt(PAGE)
    await waitForRows(10)

    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    expect(within(select()).getByRole('option', { name: '최근 6개월' })).toBeDisabled()
    expect(within(select()).getByRole('option', { name: '직접 지정' })).toBeEnabled()
  })
})

describe('프리셋 선택 (AC2)', () => {
  it('sends the server preset range to the URL from/to and to the request after searching', async () => {
    narrowTwoWeeks()
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
    expect(paramsOf(location()).get('from')).toBe('2027-03-10')
    expect(paramsOf(location()).get('to')).toBe('2027-03-15')
    expect(lastList(list)).toMatchObject({ dateFrom: '2027-03-10', dateTo: '2027-03-15' })
  })

  it('writes dates, not the preset name, to the URL and shows the preset while it matches', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from))
    expect(paramsOf(location()).get('to')).toBe(TWO_WEEKS.to)
    expect(paramsOf(location()).has('period')).toBe(false)
    expect(select()).toHaveDisplayValue('최근 2주')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  it('asks the server for the presets again when one is chosen and uses the new dates', async () => {
    // 첫 응답은 화면을 열 때의 날짜, 이후는 자정이 지난 날짜(03-16 기준)로 응답한다.
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const nextDay = { from: '2027-03-02', to: '2027-03-16' }
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      const real = await original()
      if (spy.mock.calls.length === 1) return real
      return { ...real, today: nextDay.to, periods: real.periods.map((p) => (p.key === '2w' ? { ...p, ...nextDay } : p)) }
    })
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    const before = spy.mock.calls.length

    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(nextDay.from))
    expect(paramsOf(location()).get('to')).toBe(nextDay.to)
    expect(spy.mock.calls.length).toBeGreaterThan(before)
  })

  it('shows the error and keeps the URL dates when asking for the presets again fails', async () => {
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 다시 불러오지 못했습니다.',
    })
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (spy.mock.calls.length === 1) return original()
      throw failure
    })
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(await screen.findByText('기간 정보를 다시 불러오지 못했습니다.')).toBeVisible()
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).has('to')).toBe(false)
  })

  it('shows the error and disables every preset when the presets cannot be loaded', async () => {
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure)
    await renderAt(PAGE)
    await waitForRows(10)

    expect(await screen.findByText('기간 정보를 불러오지 못했습니다.')).toBeVisible()
    expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeDisabled()
    expect(within(select()).getByRole('option', { name: '직접 지정' })).toBeEnabled()
  })
})

describe('직접 지정 (AC3)', () => {
  it('shows the start and end inputs only after choosing 직접 지정', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.selectOptions(select(), '직접 지정')

    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toBeVisible()
  })

  it('searches with the start date only, leaving the end open', async () => {
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
    expect(paramsOf(location()).get('from')).toBe('2027-03-10')
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(lastList(list)).toMatchObject({ dateFrom: '2027-03-10' })
    expect(lastList(list)).not.toHaveProperty('dateTo')
  })

  it('searches with the end date only, both ends included', async () => {
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270304')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(shownContents()).toEqual(['견적서 전달', '킥오프 일정 협의'])) // 03-04(11일 전)·03-03(12일 전)
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).get('to')).toBe('2027-03-04')
    expect(lastList(list)).toMatchObject({ dateTo: '2027-03-04' })
    expect(lastList(list)).not.toHaveProperty('dateFrom')
  })

  it('shows the error when the start date is later than the end date', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270301')
    await user.click(bar().getByRole('button', { name: '검색' }))

    expect(await screen.findByText('미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')).toBeVisible()
  })

  it('hides the date inputs again when switching from 직접 지정 to a preset', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 1개월' })).toBeEnabled())
    await user.selectOptions(select(), '직접 지정')

    await user.selectOptions(select(), '최근 1개월')

    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })
})

describe('전체 (AC4)', () => {
  it('removes from and to from the URL and the request when 전체 is chosen after a dated search', async () => {
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(`${PAGE}?from=2027-03-10&to=2027-03-15&sort=partner&order=asc`)
    await waitFor(() => expect(bar().getByRole('combobox', { name: '미팅 날짜' })).toHaveDisplayValue('직접 지정'))

    await user.selectOptions(select(), '전체')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).has('from')).toBe(false))
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(paramsOf(location()).get('sort')).toBe('partner')
    await waitForRows(10)
    expect(lastList(list)).not.toHaveProperty('dateFrom')
    expect(lastList(list)).not.toHaveProperty('dateTo')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  it('drops a preset back to no date condition when 전체 is chosen', async () => {
    const { user, location } = await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)
    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))

    await user.selectOptions(select(), '전체')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(location()).toBe(PAGE))
    await waitForRows(10)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  it('goes back to 전체 on reset', async () => {
    const { user, location } = await renderAt(`${PAGE}?from=2027-03-10&to=2027-03-15`)
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))

    await user.click(bar().getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(location()).toBe(PAGE))
    expect(select()).toHaveDisplayValue('전체')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })
})

describe('주소로 열기 (AC5)', () => {
  it('shows the preset when the URL dates equal the server preset', async () => {
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  it('shows 직접 지정 with the dates when they match no preset of today', async () => {
    await renderAt(`${PAGE}?from=2027-03-02&to=2027-03-15`)

    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.02')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  it('shows 직접 지정 when only one side is in the URL', async () => {
    await renderAt(`${PAGE}?to=2027-03-15`)

    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  it('shows 직접 지정 for the dates of a preset saved on an earlier day', async () => {
    // 어제 저장한 최근 2주 주소(03-14 기준)는 오늘의 프리셋(03-01~03-15)과 달라 직접 지정으로 보인다.
    await renderAt(`${PAGE}?from=2027-02-28&to=2027-03-14`)

    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.02.28')
  })

  it('shows 직접 지정 with the dates and keeps searching them when the presets cannot be loaded', async () => {
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(new Error('down'))
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.01')
    await waitFor(() => expect(lastList(list)).toMatchObject({ dateFrom: TWO_WEEKS.from, dateTo: TWO_WEEKS.to }))
  })

  it('opens the old URL with the same results', async () => {
    await renderAt(`${PAGE}?from=2027-03-10`)

    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
  })
})

/** 리뷰 후속(Minor 1·2): Deals '최종 업데이트'(DealFilterBar)와 같은 동작. */
describe('직접 지정 유지와 프리셋 키 없음 (리뷰 후속)', () => {
  it('keeps 직접 지정 and the date inputs after searching dates equal to a preset range', async () => {
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    await user.selectOptions(select(), '직접 지정')

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270301')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270315')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from))
    expect(select()).toHaveDisplayValue('직접 지정')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.01')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  it('sends typed dates as they are, not re-resolved as a preset, when only another condition changes', async () => {
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const nextDay = { from: '2027-03-02', to: '2027-03-16' }
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      const real = await original()
      if (spy.mock.calls.length === 1) return real
      return { ...real, today: nextDay.to, periods: real.periods.map((p) => (p.key === '2w' ? { ...p, ...nextDay } : p)) }
    })
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    await user.selectOptions(select(), '직접 지정')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270301')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270315')
    await user.click(bar().getByRole('button', { name: '검색' }))
    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from))

    await user.type(bar().getByRole('textbox', { name: '파트너' }), '네')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).get('partner')).toBe('네'))
    expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from)
    expect(paramsOf(location()).get('to')).toBe(TWO_WEEKS.to)
    expect(lastList(list)).toMatchObject({ dateFrom: TWO_WEEKS.from, dateTo: TWO_WEEKS.to })
    expect(select()).toHaveDisplayValue('직접 지정')
  })

  it('still shows the preset when an externally opened URL equals the preset range', async () => {
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  it('searches the other conditions without dates when the re-fetched presets lack the chosen key', async () => {
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      const real = await original()
      if (spy.mock.calls.length === 1) return real
      return { ...real, periods: real.periods.filter((p) => p.key !== '6m') }
    })
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(`${PAGE}?from=2027-03-02&to=2027-03-15`)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 6개월' })).toBeEnabled())

    await user.selectOptions(select(), '최근 6개월')
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '네')
    await user.click(bar().getByRole('button', { name: '검색' }))

    await waitFor(() => expect(paramsOf(location()).get('partner')).toBe('네'))
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(lastList(list)).toMatchObject({ partner: '네' })
    expect(lastList(list)).not.toHaveProperty('dateFrom')
    expect(lastList(list)).not.toHaveProperty('dateTo')
  })
})
