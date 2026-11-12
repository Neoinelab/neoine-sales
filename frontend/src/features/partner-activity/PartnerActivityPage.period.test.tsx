import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, paramsOf, pinClock, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

/**
 * 미팅 날짜 검색은 Deals 목록의 '최종 업데이트'와 같은 조건이다.
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

describe('선택지', () => {
  // 미팅 날짜는 Deals와 같은 일곱 선택지의 선택 상자이고 시작·끝 칸은 없다.
  // 테스트 코드: PA-068
  it('replaces the two date inputs with one select offering the same seven options as Deals', async () => {
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)

    // then: 기본 '전체'와 일곱 선택지가 보이고 날짜 칸은 없다
    expect(select()).toHaveDisplayValue('전체')
    const labels = within(select()).getAllByRole('option').map((o) => o.textContent)
    expect(labels).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 끝' })).not.toBeInTheDocument()
  })

  // 서버가 준 프리셋만 선택할 수 있고 없는 키는 비활성이다.
  // 테스트 코드: PA-068
  it('enables the presets the server returned and disables the one it did not', async () => {
    // given: 서버 프리셋에서 6개월이 빠진다
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      const real = await original()
      return { ...real, periods: real.periods.filter((p) => p.key !== '6m') }
    })
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)

    // then: 최근 2주는 선택할 수 있고 6개월은 비활성이며 직접 지정은 항상 선택할 수 있다
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    expect(within(select()).getByRole('option', { name: '최근 6개월' })).toBeDisabled()
    expect(within(select()).getByRole('option', { name: '직접 지정' })).toBeEnabled()
  })
})

describe('프리셋 선택', () => {
  // 프리셋을 골라 검색하면 서버가 준 날짜를 URL과 요청에 쓴다.
  // 테스트 코드: PA-069
  it('sends the server preset range to the URL from/to and to the request after searching', async () => {
    // given: 서버의 2주 프리셋이 03-10~03-15이다
    narrowTwoWeeks()
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    // when: 최근 2주를 골라 검색한다
    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 그 범위의 기록이 보이고 URL과 요청이 서버 날짜를 쓴다
    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
    expect(paramsOf(location()).get('from')).toBe('2027-03-10')
    expect(paramsOf(location()).get('to')).toBe('2027-03-15')
    expect(lastList(list)).toMatchObject({ dateFrom: '2027-03-10', dateTo: '2027-03-15' })
  })

  // URL에는 프리셋 이름이 아닌 날짜를 쓰고 그 날짜가 오늘의 프리셋이면 프리셋으로 보인다.
  // 테스트 코드: PA-069
  it('writes dates, not the preset name, to the URL and shows the preset while it matches', async () => {
    // given: 화면이 열려 있다
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())

    // when: 최근 2주를 골라 검색한다
    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: URL은 날짜이고 선택 상자는 최근 2주, 날짜 칸은 없다
    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from))
    expect(paramsOf(location()).get('to')).toBe(TWO_WEEKS.to)
    expect(paramsOf(location()).has('period')).toBe(false)
    expect(select()).toHaveDisplayValue('최근 2주')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  // 프리셋을 고르면 서버에 다시 물어 새 날짜를 쓴다.
  // 테스트 코드: PA-069
  it('asks the server for the presets again when one is chosen and uses the new dates', async () => {
    // given: 첫 응답은 화면을 열 때의 날짜, 이후는 하루 지난 날짜로 응답한다
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

    // when: 최근 2주를 골라 검색한다
    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 새로 받은 날짜가 URL에 쓰이고 서버에 다시 물었다
    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(nextDay.from))
    expect(paramsOf(location()).get('to')).toBe(nextDay.to)
    expect(spy.mock.calls.length).toBeGreaterThan(before)
  })

  // 프리셋 다시 묻기가 실패하면 배너를 보이고 조건을 바꾸지 않는다.
  // 테스트 코드: PA-070
  it('shows the error and keeps the URL dates when asking for the presets again fails', async () => {
    // given: 첫 응답은 정상이고 다시 묻는 요청은 실패한다
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

    // when: 최근 2주를 골라 검색한다
    await user.selectOptions(select(), '최근 2주')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 오류 문구가 보이고 URL에 날짜가 쓰이지 않는다
    expect(await screen.findByText('기간 정보를 다시 불러오지 못했습니다.')).toBeVisible()
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).has('to')).toBe(false)
  })

  // 프리셋을 못 읽으면 오류를 보이고 프리셋이 모두 비활성이다.
  // 테스트 코드: PA-070
  it('shows the error and disables every preset when the presets cannot be loaded', async () => {
    // given: 프리셋 조회가 실패한다
    const failure = new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure)
    // when: 화면을 연다
    await renderAt(PAGE)
    await waitForRows(10)

    // then: 오류 문구가 보이고 프리셋은 비활성, 직접 지정은 선택할 수 있다
    expect(await screen.findByText('기간 정보를 불러오지 못했습니다.')).toBeVisible()
    expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeDisabled()
    expect(within(select()).getByRole('option', { name: '직접 지정' })).toBeEnabled()
  })
})

describe('직접 지정', () => {
  // 직접 지정을 골라야 시작·끝 날짜 칸이 보인다.
  // 테스트 코드: PA-071
  it('shows the start and end inputs only after choosing 직접 지정', async () => {
    // given: 화면이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    // when: 직접 지정을 고른다
    await user.selectOptions(select(), '직접 지정')

    // then: 시작·끝 칸이 보인다
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toBeVisible()
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toBeVisible()
  })

  // 시작 날짜만으로 검색하면 끝은 열어 둔다.
  // 테스트 코드: PA-071
  it('searches with the start date only, leaving the end open', async () => {
    // given: 직접 지정을 고른 화면
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    // when: 시작 날짜만 치고 검색한다
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 03-10 이후 기록이 보이고 URL·요청에 끝 날짜가 없다
    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
    expect(paramsOf(location()).get('from')).toBe('2027-03-10')
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(lastList(list)).toMatchObject({ dateFrom: '2027-03-10' })
    expect(lastList(list)).not.toHaveProperty('dateTo')
  })

  // 끝 날짜만으로 검색하면 양끝이 포함된다.
  // 테스트 코드: PA-071
  it('searches with the end date only, both ends included', async () => {
    // given: 직접 지정을 고른 화면
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    // when: 끝 날짜만 치고 검색한다
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270304')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 03-04 이전 기록이 보이고 URL·요청에 시작 날짜가 없다
    await waitFor(() => expect(shownContents()).toEqual(['견적서 전달', '킥오프 일정 협의'])) // 03-04(11일 전)·03-03(12일 전)
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).get('to')).toBe('2027-03-04')
    expect(lastList(list)).toMatchObject({ dateTo: '2027-03-04' })
    expect(lastList(list)).not.toHaveProperty('dateFrom')
  })

  // 시작이 끝보다 늦으면 서버 문구를 보인다.
  // 테스트 코드: PA-062
  it('shows the error when the start date is later than the end date', async () => {
    // given: 직접 지정을 고른 화면
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.selectOptions(select(), '직접 지정')

    // when: 시작이 끝보다 늦은 범위로 검색한다
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270310')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270301')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 서버 문구가 보인다
    expect(await screen.findByText('미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')).toBeVisible()
  })

  // 직접 지정에서 프리셋으로 바꾸면 날짜 칸이 사라진다.
  // 테스트 코드: PA-071
  it('hides the date inputs again when switching from 직접 지정 to a preset', async () => {
    // given: 직접 지정을 골라 날짜 칸이 보이는 화면
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 1개월' })).toBeEnabled())
    await user.selectOptions(select(), '직접 지정')

    // when: 최근 1개월로 바꾼다
    await user.selectOptions(select(), '최근 1개월')

    // then: 날짜 칸이 사라진다
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })
})

describe('전체', () => {
  // 전체를 고르면 URL과 요청에서 날짜가 빠진다.
  // 테스트 코드: PA-072
  it('removes from and to from the URL and the request when 전체 is chosen after a dated search', async () => {
    // given: 날짜와 정렬이 든 주소로 연 화면
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    const { user, location } = await renderAt(`${PAGE}?from=2027-03-10&to=2027-03-15&sort=partner&order=asc`)
    await waitFor(() => expect(bar().getByRole('combobox', { name: '미팅 날짜' })).toHaveDisplayValue('직접 지정'))

    // when: 전체를 골라 검색한다
    await user.selectOptions(select(), '전체')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 날짜가 URL·요청에서 빠지고 정렬은 남으며 날짜 칸이 사라진다
    await waitFor(() => expect(paramsOf(location()).has('from')).toBe(false))
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(paramsOf(location()).get('sort')).toBe('partner')
    await waitForRows(10)
    expect(lastList(list)).not.toHaveProperty('dateFrom')
    expect(lastList(list)).not.toHaveProperty('dateTo')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  // 프리셋이 걸린 상태에서 전체를 고르면 날짜 조건이 없다.
  // 테스트 코드: PA-072
  it('drops a preset back to no date condition when 전체 is chosen', async () => {
    // given: 최근 2주 프리셋으로 열린 화면
    const { user, location } = await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)
    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))

    // when: 전체를 골라 검색한다
    await user.selectOptions(select(), '전체')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 주소가 경로뿐이고 기본 10건이 보인다
    await waitFor(() => expect(location()).toBe(PAGE))
    await waitForRows(10)
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  // 초기화하면 전체로 돌아간다.
  // 테스트 코드: PA-072
  it('goes back to 전체 on reset', async () => {
    // given: 날짜가 걸려 직접 지정으로 열린 화면
    const { user, location } = await renderAt(`${PAGE}?from=2027-03-10&to=2027-03-15`)
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))

    // when: 초기화를 누른다
    await user.click(bar().getByRole('button', { name: '초기화' }))

    // then: 주소가 경로뿐이고 선택 상자가 전체이며 날짜 칸이 없다
    await waitFor(() => expect(location()).toBe(PAGE))
    expect(select()).toHaveDisplayValue('전체')
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })
})

describe('주소로 열기', () => {
  // 주소의 날짜가 오늘의 프리셋과 같으면 프리셋으로 보인다.
  // 테스트 코드: PA-073
  it('shows the preset when the URL dates equal the server preset', async () => {
    // when: 프리셋과 같은 날짜가 든 주소로 연다
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    // then: 최근 2주로 보이고 날짜 칸은 없다
    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  // 프리셋과 맞지 않는 날짜는 직접 지정으로 보인다.
  // 테스트 코드: PA-073
  it('shows 직접 지정 with the dates when they match no preset of today', async () => {
    // when: 어떤 프리셋과도 다른 날짜가 든 주소로 연다
    await renderAt(`${PAGE}?from=2027-03-02&to=2027-03-15`)

    // then: 직접 지정과 날짜 칸이 보인다
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.02')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  // 한쪽 날짜만 있으면 직접 지정으로 보인다.
  // 테스트 코드: PA-073
  it('shows 직접 지정 when only one side is in the URL', async () => {
    // when: 끝 날짜만 든 주소로 연다
    await renderAt(`${PAGE}?to=2027-03-15`)

    // then: 직접 지정이고 시작 칸은 비어 있다
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  // 어제 저장한 프리셋 날짜는 오늘의 프리셋과 달라 직접 지정으로 보인다.
  // 테스트 코드: PA-073
  it('shows 직접 지정 for the dates of a preset saved on an earlier day', async () => {
    // 어제 저장한 최근 2주 주소(03-14 기준)는 오늘의 프리셋(03-01~03-15)과 달라 직접 지정으로 보인다.
    // when: 어제 기준 최근 2주 날짜가 든 주소로 연다
    await renderAt(`${PAGE}?from=2027-02-28&to=2027-03-14`)

    // then: 직접 지정과 그 날짜가 보인다
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.02.28')
  })

  // 프리셋을 못 읽어도 직접 지정으로 보이고 그 날짜로 검색한다.
  // 테스트 코드: PA-073
  it('shows 직접 지정 with the dates and keeps searching them when the presets cannot be loaded', async () => {
    // given: 프리셋 조회가 실패한다
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(new Error('down'))
    const list = vi.spyOn(gateway.partnerMeetings, 'list')
    // when: 날짜가 든 주소로 연다
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    // then: 직접 지정이고 그 날짜로 검색한다
    await waitFor(() => expect(select()).toHaveDisplayValue('직접 지정'))
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.01')
    await waitFor(() => expect(lastList(list)).toMatchObject({ dateFrom: TWO_WEEKS.from, dateTo: TWO_WEEKS.to }))
  })

  // 예전 주소도 같은 결과로 열린다.
  // 테스트 코드: PA-073
  it('opens the old URL with the same results', async () => {
    // when: 시작 날짜만 든 예전 주소로 연다
    await renderAt(`${PAGE}?from=2027-03-10`)

    // then: 03-10 이후 기록이 보인다
    await waitFor(() => expect(shownContents()).toEqual(SINCE_MAR_10))
  })
})

/** Deals '최종 업데이트'(DealFilterBar)와 같은 동작. */
describe('직접 지정 유지와 프리셋 키 없음', () => {
  // 프리셋 범위와 같은 날짜를 직접 지정으로 검색해도 직접 지정으로 남는다.
  // 테스트 코드: PA-074
  it('keeps 직접 지정 and the date inputs after searching dates equal to a preset range', async () => {
    // given: 직접 지정을 고를 수 있는 화면
    const { user, location } = await renderAt(PAGE)
    await waitForRows(10)
    await waitFor(() => expect(within(select()).getByRole('option', { name: '최근 2주' })).toBeEnabled())
    // when: 직접 지정에서 프리셋과 같은 범위를 쳐 검색한다
    await user.selectOptions(select(), '직접 지정')

    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 시작' }), '20270301')
    await user.type(bar().getByRole('textbox', { name: '미팅 날짜 끝' }), '20270315')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 선택 상자는 직접 지정이고 날짜 칸이 남는다
    await waitFor(() => expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from))
    expect(select()).toHaveDisplayValue('직접 지정')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 시작' })).toHaveValue('2027.03.01')
    expect(bar().getByRole('textbox', { name: '미팅 날짜 끝' })).toHaveValue('2027.03.15')
  })

  // 직접 지정한 날짜는 다른 조건만 바꿔도 프리셋으로 다시 풀지 않고 그대로 보낸다.
  // 테스트 코드: PA-074
  it('sends typed dates as they are, not re-resolved as a preset, when only another condition changes', async () => {
    // given: 하루 뒤 프리셋을 줄 서버와, 직접 지정으로 검색한 상태
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

    // when: 파트너 조건만 더해 다시 검색한다
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '네')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 날짜는 쳤던 그대로 URL·요청에 남고 직접 지정이 유지된다
    await waitFor(() => expect(paramsOf(location()).get('partner')).toBe('네'))
    expect(paramsOf(location()).get('from')).toBe(TWO_WEEKS.from)
    expect(paramsOf(location()).get('to')).toBe(TWO_WEEKS.to)
    expect(lastList(list)).toMatchObject({ dateFrom: TWO_WEEKS.from, dateTo: TWO_WEEKS.to })
    expect(select()).toHaveDisplayValue('직접 지정')
  })

  // 바깥에서 연 주소가 프리셋 범위와 같으면 여전히 프리셋으로 보인다.
  // 테스트 코드: PA-073
  it('still shows the preset when an externally opened URL equals the preset range', async () => {
    // when: 프리셋과 같은 날짜가 든 주소로 연다
    await renderAt(`${PAGE}?from=${TWO_WEEKS.from}&to=${TWO_WEEKS.to}`)

    // then: 최근 2주로 보이고 날짜 칸은 없다
    await waitFor(() => expect(select()).toHaveDisplayValue('최근 2주'))
    expect(bar().queryByRole('textbox', { name: '미팅 날짜 시작' })).not.toBeInTheDocument()
  })

  // 다시 받은 프리셋에 키가 없으면 날짜 없이 다른 조건만 검색한다.
  // 테스트 코드: PA-074
  it('searches the other conditions without dates when the re-fetched presets lack the chosen key', async () => {
    // given: 다시 묻는 응답에서 6개월이 빠지는 서버
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

    // when: 최근 6개월을 고르고 파트너 조건을 더해 검색한다
    await user.selectOptions(select(), '최근 6개월')
    await user.type(bar().getByRole('textbox', { name: '파트너' }), '네')
    await user.click(bar().getByRole('button', { name: '검색' }))

    // then: 파트너 조건만 쓰이고 URL·요청에 날짜가 없다
    await waitFor(() => expect(paramsOf(location()).get('partner')).toBe('네'))
    expect(paramsOf(location()).has('from')).toBe(false)
    expect(paramsOf(location()).has('to')).toBe(false)
    expect(lastList(list)).toMatchObject({ partner: '네' })
    expect(lastList(list)).not.toHaveProperty('dateFrom')
    expect(lastList(list)).not.toHaveProperty('dateTo')
  })
})
