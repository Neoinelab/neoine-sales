import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import type { ActionQuery, UpdatedPeriods } from '../../../shared/model/types'
import { defaultMock, mockControl, resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { ActionSearchBar } from './ActionSearchBar'

/** Action 검색의 수행일·기한 기간 프리셋. 서버 업무 날짜(Fake 시계)로 프리셋을 푼다. */

const TODAY_AT = '2026-10-22T09:00:00+09:00'
const NEXT_DAY_AT = '2026-10-23T09:00:00+09:00'

beforeEach(async () => {
  resetMock({ now: TODAY_AT })
  mockControl.resetData()
  await defaultMock.signInAs(USER_ID.kim)
})
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function renderBar() {
  const onSearch = vi.fn<(query: ActionQuery) => void>()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={client}>
      <ActionSearchBar onSearch={onSearch} />
    </QueryClientProvider>,
  )
  const form = screen.getByRole('search', { name: 'Action 검색' })
  return { user, onSearch, form, acted: within(form).getByLabelText('수행일'), due: within(form).getByLabelText('기한') }
}

/** 프리셋이 로드되어 프리셋 옵션이 활성이 될 때까지 기다린다. */
async function presetsLoaded(select: HTMLElement) {
  await waitFor(() => expect(within(select).getByRole('option', { name: '최근 1개월' })).toBeEnabled())
}

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
const lastQuery = (onSearch: { mock: { calls: unknown[][] } }) => onSearch.mock.calls.at(-1)?.[0] as ActionQuery

describe('옵션 목록과 기본값', () => {
  // 수행일 선택지는 전체·최근 2주~6개월·직접 지정이고 처음은 "전체"다.
  // 테스트 코드: NA-055
  it('lists the acted period options in order with 전체 selected', async () => {
    // when: 검색 바를 렌더한다.
    const { acted } = await renderBar()

    // then: 선택지 순서가 정해진 대로이고 "전체"가 선택돼 있다.
    expect(optionNames(acted)).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(acted).toHaveDisplayValue('전체')
  })

  // 기한 선택지는 수행일 선택지에 향후 1·2개월이 "직접 지정" 앞에 더해지고 처음은 "전체"다.
  // 테스트 코드: NA-055
  it('lists the due period options in order with 전체 selected, including the upcoming ones', async () => {
    // when: 검색 바를 렌더한다.
    const { due } = await renderBar()

    // then: 기한 선택지 순서가 정해진 대로이고 "전체"가 선택돼 있다.
    expect(optionNames(due)).toEqual([
      '전체',
      '최근 2주',
      '최근 1개월',
      '최근 2개월',
      '최근 3개월',
      '최근 6개월',
      '향후 1개월',
      '향후 2개월',
      '직접 지정',
    ])
    expect(due).toHaveDisplayValue('전체')
  })

  // 수행일 선택지에는 향후 항목이 없다.
  // 테스트 코드: NA-055
  it('has no upcoming options for the acted date', async () => {
    // when: 검색 바를 렌더한다.
    const { acted } = await renderBar()

    // then: 수행일에는 "향후" 선택지가 없다.
    expect(within(acted).queryByRole('option', { name: /향후/ })).not.toBeInTheDocument()
  })

  // "직접 지정"을 고르기 전에는 날짜 칸이 없다.
  // 테스트 코드: NA-055
  it('shows no date input until 직접 지정 is chosen', async () => {
    // when: 검색 바를 렌더한다.
    const { form } = await renderBar()

    // then: 시작·끝 날짜 칸이 하나도 없다.
    for (const label of ['수행일 시작', '수행일 끝', '기한 시작', '기한 끝']) {
      expect(within(form).queryByLabelText(label)).not.toBeInTheDocument()
    }
  })
})

describe('프리셋으로 검색', () => {
  // 수행일 프리셋은 서버가 준 날짜로 검색하고 기한 조건은 보내지 않는다.
  // 테스트 코드: NA-056
  it.each([
    ['최근 2주', '2026-10-08'],
    ['최근 1개월', '2026-09-22'],
    ['최근 2개월', '2026-08-22'],
    ['최근 3개월', '2026-07-22'],
    ['최근 6개월', '2026-04-22'],
  ])('searches the acted date with the server dates of %s', async (label, from) => {
    // given: 서버 날짜가 2026-10-22이고 프리셋 응답이 왔다.
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)

    // when: 수행일 프리셋을 골라 "검색"을 누른다.
    await user.selectOptions(acted, label)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 수행일 시작·끝이 서버 날짜 기준이고 기한 조건은 없다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: from, actedTo: '2026-10-22' })
    expect(lastQuery(onSearch)).not.toHaveProperty('dueFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('dueTo')
  })

  // 기한 프리셋은 서버가 준 날짜로 검색하고 수행일 조건은 보내지 않는다.
  // 테스트 코드: NA-056
  it.each([
    ['최근 2주', '2026-10-08', '2026-10-22'],
    ['최근 6개월', '2026-04-22', '2026-10-22'],
    ['향후 1개월', '2026-10-22', '2026-11-22'],
    ['향후 2개월', '2026-10-22', '2026-12-22'],
  ])('searches the due date with the server dates of %s', async (label, from, to) => {
    // given: 서버 날짜가 2026-10-22이고 프리셋 응답이 왔다.
    const { user, onSearch, form, due } = await renderBar()
    await presetsLoaded(due)

    // when: 기한 프리셋을 골라 "검색"을 누른다.
    await user.selectOptions(due, label)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 기한 시작·끝이 서버 날짜 기준이고 수행일 조건은 없다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: from, dueTo: to })
    expect(lastQuery(onSearch)).not.toHaveProperty('actedFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  // 31일에서 "향후 1개월"은 다음 달 말일까지로 바뀐다.
  // 테스트 코드: NA-056
  it('falls back to the month end for the upcoming presets of a 31st', async () => {
    // given: 서버 날짜가 2026-01-31이다.
    resetMock({ now: '2026-01-31T09:00:00+09:00' })
    const { user, onSearch, form, due } = await renderBar()
    await presetsLoaded(due)

    // when: 기한 "향후 1개월"로 검색한다.
    await user.selectOptions(due, '향후 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 기한이 2026-01-31 ~ 2026-02-28이다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: '2026-01-31', dueTo: '2026-02-28' })
  })

  // 수행일 프리셋과 기한 프리셋을 함께 고르면 한 질의에 모두 담긴다.
  // 테스트 코드: NA-056
  it('combines an acted preset and a due preset in one query', async () => {
    // given: 서버 날짜가 2026-10-22이고 프리셋 응답이 왔다.
    const { user, onSearch, form, acted, due } = await renderBar()
    await presetsLoaded(acted)

    // when: 수행일 "최근 1개월"과 기한 "향후 2개월"을 골라 검색한다.
    await user.selectOptions(acted, '최근 1개월')
    await user.selectOptions(due, '향후 2개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 한 질의에 수행일·기한 날짜가 모두 있다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({
      actedFrom: '2026-09-22',
      actedTo: '2026-10-22',
      dueFrom: '2026-10-22',
      dueTo: '2026-12-22',
    })
  })

  // 프리셋을 고른 채 검색하면 그때 서버에서 프리셋을 새로 받아 날짜를 보낸다.
  // 테스트 코드: NA-056
  it('fetches presets fresh at search time', async () => {
    // given: "최근 1개월"로 한 번 검색했다(2026-09-22 ~ 10-22).
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '최근 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-22', actedTo: '2026-10-22' })

    // when: 서버 날짜가 다음 날로 바뀐 뒤 다시 "검색"을 누른다.
    defaultMock.clock.setNow(NEXT_DAY_AT)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 질의 날짜가 하루씩 뒤로 간다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(2))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-23', actedTo: '2026-10-23' })
  })

  // 프리셋을 고르지 않았으면 검색할 때 서버에 프리셋을 다시 묻지 않는다.
  // 테스트 코드: NA-056
  it('does not ask the server for presets when no preset is chosen', async () => {
    // given: 프리셋 조회를 감시하고 프리셋 응답이 왔다. 프리셋은 고르지 않았다.
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods')
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    const before = spy.mock.calls.length

    // when: "검색"을 누른다.
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 검색은 되었고 프리셋 조회 횟수는 그대로다(프리셋을 묻는지 자체가 사용자 결과).
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls.length).toBe(before)
  })
})

describe('직접 지정과 전체', () => {
  // "직접 지정"은 날짜 칸을 보이고 채운 날짜만 보낸다.
  // 테스트 코드: NA-057
  it('custom shows date inputs and sends only filled dates', async () => {
    // given: 검색 바가 있다.
    const { user, onSearch, form, acted } = await renderBar()

    // when: 수행일을 "직접 지정"으로 고른다.
    await user.selectOptions(acted, '직접 지정')
    // then: 시작·끝 날짜 칸이 나타난다.
    expect(within(form).getByLabelText('수행일 시작')).toBeVisible()
    expect(within(form).getByLabelText('수행일 끝')).toBeVisible()
    // when: 시작만 쓰고 "검색"을 누른다.
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-09-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 질의에 시작 날짜만 있다.
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-01' })
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  // 기한 직접 지정은 시작과 끝을 모두 보낸다.
  // 테스트 코드: NA-057
  it('sends both custom dates of the due condition', async () => {
    // given: 검색 바가 있다.
    const { user, onSearch, form, due } = await renderBar()

    // when: 기한을 "직접 지정"으로 하고 시작·끝을 쓴 뒤 검색한다.
    await user.selectOptions(due, '직접 지정')
    await user.type(within(form).getByLabelText('기한 시작'), '2026-11-01')
    await user.type(within(form).getByLabelText('기한 끝'), '2026-11-30')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 질의에 기한 시작·끝이 모두 있다.
    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: '2026-11-01', dueTo: '2026-11-30' })
  })

  // 날짜를 yyyymmdd로 쓰면 yyyy.mm.dd로 표시되고 ISO 날짜로 검색한다.
  // 테스트 코드: NA-057
  it('types the custom date as yyyymmdd and searches with the ISO date', async () => {
    // given: 검색 바가 있다.
    const { user, onSearch, form, acted } = await renderBar()

    // when: 수행일 시작에 `20260901`을 쓴다.
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '20260901')
    // then: 칸에는 2026.09.01로 표시된다.
    expect(within(form).getByLabelText('수행일 시작')).toHaveValue('2026.09.01')
    // when: "검색"을 누른다.
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 질의에는 2026-09-01로 들어간다.
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-01' })
  })

  // 틀린 날짜가 있으면 검색하지 않고 그 칸에 문구를 보인다.
  // 테스트 코드: NA-057
  it('does not search while a custom date is wrong and shows the message in the field', async () => {
    // given: 검색 바가 있다.
    const { user, onSearch, form, due } = await renderBar()

    // when: 기한 끝에 없는 날짜 `20261340`을 쓰고 "검색"을 누른다.
    await user.selectOptions(due, '직접 지정')
    await user.type(within(form).getByLabelText('기한 끝'), '20261340')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 검색하지 않고 칸에 "없는 날짜입니다."가 보인다.
    expect(onSearch).not.toHaveBeenCalled()
    expect(within(form).getByText('없는 날짜입니다.')).toBeVisible()
    expect(within(form).getByLabelText('기한 끝')).toHaveAttribute('aria-invalid', 'true')
  })

  // 덜 친 날짜가 있으면 검색하지 않고 칸에 안내 문구를 보인다.
  // 테스트 코드: NA-057
  it('does not search while a custom date is only partly typed', async () => {
    // given: 검색 바가 있다.
    const { user, onSearch, form, acted } = await renderBar()

    // when: 수행일 시작에 `2026.09`만 쓰고 "검색"을 누른다.
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026.09')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 검색하지 않고 형식 안내 문구가 보인다.
    expect(onSearch).not.toHaveBeenCalled()
    expect(within(form).getByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  // 성공한 검색 뒤 다시 고치기 시작하면 문구와 오류 표시를 지운다.
  // 테스트 코드: NA-057
  it('shows no message or aria-invalid while typing again after a successful search', async () => {
    // given: `20260901`로 성공적으로 검색했다.
    const { user, onSearch, form, acted } = await renderBar()
    await user.selectOptions(acted, '직접 지정')
    const from = within(form).getByLabelText('수행일 시작')
    await user.type(from, '20260901')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    expect(onSearch).toHaveBeenCalledTimes(1)

    // when: 시작 칸을 지우고 `2026.1`을 다시 쓰기 시작한다.
    await user.clear(from)
    await user.type(from, '2026.1')

    // then: 문구도 aria-invalid도 없다.
    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(from).not.toHaveAttribute('aria-invalid')
  })

  // 다시 고치던 칸을 떠나면 그때 문구가 다시 보인다.
  // 테스트 코드: NA-057
  it('shows the message again only after leaving the field following the successful search', async () => {
    // given: `20260901`로 성공적으로 검색한 뒤 시작 칸을 지우고 `2026.1`을 썼다.
    const { user, form, acted } = await renderBar()
    await user.selectOptions(acted, '직접 지정')
    const from = within(form).getByLabelText('수행일 시작')
    await user.type(from, '20260901')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await user.clear(from)
    await user.type(from, '2026.1')
    // when: 칸을 떠난다.
    await user.tab()

    // then: 형식 안내 문구가 다시 보인다.
    expect(within(form).getByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  // 프리셋·전체로 바꾸면 날짜 칸을 숨기고 입력한 날짜는 질의에 쓰지 않는다.
  // 테스트 코드: NA-057
  it('hides the inputs and ignores the typed dates after switching to a preset or to all', async () => {
    // given: 수행일 "직접 지정"에 시작·끝 날짜를 써 두었다.
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-01-01')
    await user.type(within(form).getByLabelText('수행일 끝'), '2026-01-31')

    // when: "최근 2주"로 바꾼다.
    await user.selectOptions(acted, '최근 2주')
    // then: 날짜 칸이 사라진다.
    expect(within(form).queryByLabelText('수행일 시작')).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('수행일 끝')).not.toBeInTheDocument()
    // when: "검색"을 누른다.
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    // then: 프리셋 날짜가 질의에 들어가고 입력했던 날짜는 없다.
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08', actedTo: '2026-10-22' })

    // when: "전체"로 바꿔 검색한다.
    await user.selectOptions(acted, '전체')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(2))
    // then: 수행일 조건이 질의에 없다.
    expect(lastQuery(onSearch)).not.toHaveProperty('actedFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  // "전체"는 날짜 조건을 보내지 않는다.
  // 테스트 코드: NA-057
  it('all sends no date params', async () => {
    // given: 검색 바가 처음 상태(전체)다.
    const { user, onSearch, form } = await renderBar()

    // when: "검색"을 누른다.
    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 날짜 조건이 질의에 하나도 없다.
    expect(onSearch).toHaveBeenCalledTimes(1)
    for (const key of ['actedFrom', 'actedTo', 'dueFrom', 'dueTo']) expect(lastQuery(onSearch)).not.toHaveProperty(key)
  })
})

describe('프리셋을 받지 못한 경우', () => {
  const failure = () =>
    new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })

  // 프리셋을 읽지 못하면 프리셋 선택지가 비활성이고 오류 배너를 보인다.
  // 테스트 코드: NA-058
  it('disables presets until the presets load and shows the load error', async () => {
    // given: 프리셋 응답이 실패한다.
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure())
    // when: 검색 바를 렌더한다.
    const { form, acted, due } = await renderBar()

    // then: 오류 배너가 보이고 프리셋 선택지는 비활성이며 "전체"·"직접 지정"은 활성이다.
    expect(await within(form).findByRole('alert')).toHaveTextContent('기간 정보를 불러오지 못했습니다.')
    for (const select of [acted, due]) {
      for (const name of ['최근 2주', '최근 1개월', '최근 6개월']) {
        expect(within(select).getByRole('option', { name })).toBeDisabled()
      }
      expect(within(select).getByRole('option', { name: '전체' })).toBeEnabled()
      expect(within(select).getByRole('option', { name: '직접 지정' })).toBeEnabled()
    }
    expect(within(due).getByRole('option', { name: '향후 1개월' })).toBeDisabled()
    expect(within(due).getByRole('option', { name: '향후 2개월' })).toBeDisabled()
  })

  // 프리셋 응답이 오기 전에는 비활성이고 응답이 오면 활성이 된다.
  // 테스트 코드: NA-058
  it('keeps presets disabled while loading and enables them after the response', async () => {
    // given: 프리셋 응답이 아직 오지 않았다.
    let release: (value: UpdatedPeriods) => void = () => {}
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const loaded = original()
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(
      () =>
        new Promise<UpdatedPeriods>((resolve) => {
          release = resolve
        }),
    )
    // when: 검색 바를 렌더한다.
    const { acted, due } = await renderBar()
    // then: 프리셋 선택지는 비활성이고 "직접 지정"은 활성이다.
    expect(within(acted).getByRole('option', { name: '최근 1개월' })).toBeDisabled()
    expect(within(due).getByRole('option', { name: '향후 1개월' })).toBeDisabled()
    expect(within(acted).getByRole('option', { name: '직접 지정' })).toBeEnabled()

    // when: 응답이 도착한다.
    release(await loaded)

    // then: 프리셋 선택지가 활성이 된다.
    await presetsLoaded(acted)
    expect(within(due).getByRole('option', { name: '향후 1개월' })).toBeEnabled()
  })

  // 검색할 때 프리셋 새로 받기가 실패하면 이전 질의를 유지하고 오류 배너를 보인다.
  // 테스트 코드: NA-058
  it('keeps the previous query and shows the error when refreshing presets fails', async () => {
    // given: "최근 1개월"로 한 번 검색했고 이후 프리셋 새로 받기가 실패한다.
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    let failing = false
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      if (failing) throw failure()
      return original()
    })
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '최근 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    // when: 프리셋 새로 받기가 실패하도록 한 뒤 "검색"을 다시 누른다.
    failing = true

    await user.click(within(form).getByRole('button', { name: '검색' }))

    // then: 오류 배너가 보이고 질의는 이전 한 번뿐이다.
    expect(await within(form).findByRole('alert')).toHaveTextContent('기간 정보를 불러오지 못했습니다.')
    expect(onSearch).toHaveBeenCalledTimes(1)
  })

  // 초기화 뒤에 늦게 온 프리셋 응답은 버린다.
  // 테스트 코드: NA-058
  it('ignores a late preset response after reset', async () => {
    // given: 검색 시점의 프리셋 새로 받기가 늦게 응답한다.
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let calls = 0
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      calls += 1
      if (calls > 1) await gate // 첫 호출(화면 로딩)은 즉시, 검색 시점의 새로 받기는 늦게
      return original()
    })
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '최근 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // when: "최근 1개월"로 검색한 직후 "초기화"를 누른다.
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    // then: 초기화 질의 `{}`만 보냈다.
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenLastCalledWith({})

    // when: 늦은 응답이 도착한다.
    release()
    await new Promise((resolve) => setTimeout(resolve, 30))

    // then: 질의는 바뀌지 않는다.
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenLastCalledWith({})
  })

  // 더 새로운 검색이 있으면 먼저 한 검색의 늦은 응답은 버린다.
  // 테스트 코드: NA-058
  it('ignores the late response of an earlier search when a newer search was made', async () => {
    // given: 첫 검색의 프리셋 새로 받기만 늦게 응답한다.
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    let calls = 0
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(async () => {
      calls += 1
      if (calls === 2) await gate // 첫 검색의 새로 받기만 늦게
      return original()
    })
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '최근 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // when: "최근 1개월"로 검색한 뒤 "최근 2주"로 다시 검색한다.
    await user.selectOptions(acted, '최근 2주')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: 새 검색의 질의(2026-10-08)가 나갔다.
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08' })

    // when: 늦은 응답이 도착한다.
    release()
    await new Promise((resolve) => setTimeout(resolve, 30))

    // then: 질의는 바뀌지 않는다.
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08' })
  })
})

describe('초기화', () => {
  // 초기화는 두 기간을 "전체"로 돌리고 직접 지정 날짜를 비우며 조건 없이 다시 조회한다.
  // 테스트 코드: NA-059
  it('reset returns both periods to all and clears the custom dates', async () => {
    // given: 수행일 "직접 지정" 시작과 기한 "향후 1개월"을 골라 두었다.
    const { user, onSearch, form, acted, due } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-09-01')
    await user.selectOptions(due, '향후 1개월')

    // when: "초기화"를 누른다.
    await user.click(within(form).getByRole('button', { name: '초기화' }))

    // then: 두 기간이 "전체"이고 날짜 칸이 사라지며 조건 없이 조회한다.
    expect(acted).toHaveDisplayValue('전체')
    expect(due).toHaveDisplayValue('전체')
    expect(within(form).queryByLabelText('수행일 시작')).not.toBeInTheDocument()
    expect(onSearch).toHaveBeenLastCalledWith({})
    // when: 수행일을 다시 "직접 지정"으로 고른다.
    await user.selectOptions(acted, '직접 지정')
    // then: 입력했던 날짜는 비어 있다.
    expect(within(form).getByLabelText('수행일 시작')).toHaveValue('')
    expect(within(form).getByLabelText('수행일 끝')).toHaveValue('')
  })
})
