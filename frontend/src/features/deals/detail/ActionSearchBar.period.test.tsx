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

/** Action 검색의 수행일·기한 기간 프리셋 (AC-16~23). 서버 업무 날짜(Fake 시계)로 프리셋을 푼다. */

const TODAY_AT = '2026-10-22T09:00:00+09:00'
const NEXT_DAY_AT = '2026-10-23T09:00:00+09:00'

beforeEach(async () => {
  resetMock({ now: TODAY_AT })
  mockControl.resetData()
  await gateway.auth.quickLogin(USER_ID.kim)
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

describe('옵션 목록과 기본값 (AC-16, AC-17)', () => {
  it('lists the acted period options in order with 전체 selected', async () => {
    const { acted } = await renderBar()

    expect(optionNames(acted)).toEqual(['전체', '최근 2주', '최근 1개월', '최근 2개월', '최근 3개월', '최근 6개월', '직접 지정'])
    expect(acted).toHaveDisplayValue('전체')
  })

  it('lists the due period options in order with 전체 selected, including the upcoming ones', async () => {
    const { due } = await renderBar()

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

  it('has no upcoming options for the acted date', async () => {
    const { acted } = await renderBar()

    expect(within(acted).queryByRole('option', { name: /향후/ })).not.toBeInTheDocument()
  })

  it('shows no date input until 직접 지정 is chosen', async () => {
    const { form } = await renderBar()

    for (const label of ['수행일 시작', '수행일 끝', '기한 시작', '기한 끝']) {
      expect(within(form).queryByLabelText(label)).not.toBeInTheDocument()
    }
  })
})

describe('프리셋으로 검색 (AC-18)', () => {
  it.each([
    ['최근 2주', '2026-10-08'],
    ['최근 1개월', '2026-09-22'],
    ['최근 2개월', '2026-08-22'],
    ['최근 3개월', '2026-07-22'],
    ['최근 6개월', '2026-04-22'],
  ])('searches the acted date with the server dates of %s', async (label, from) => {
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)

    await user.selectOptions(acted, label)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: from, actedTo: '2026-10-22' })
    expect(lastQuery(onSearch)).not.toHaveProperty('dueFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('dueTo')
  })

  it.each([
    ['최근 2주', '2026-10-08', '2026-10-22'],
    ['최근 6개월', '2026-04-22', '2026-10-22'],
    ['향후 1개월', '2026-10-22', '2026-11-22'],
    ['향후 2개월', '2026-10-22', '2026-12-22'],
  ])('searches the due date with the server dates of %s', async (label, from, to) => {
    const { user, onSearch, form, due } = await renderBar()
    await presetsLoaded(due)

    await user.selectOptions(due, label)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: from, dueTo: to })
    expect(lastQuery(onSearch)).not.toHaveProperty('actedFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  it('falls back to the month end for the upcoming presets of a 31st', async () => {
    resetMock({ now: '2026-01-31T09:00:00+09:00' })
    const { user, onSearch, form, due } = await renderBar()
    await presetsLoaded(due)

    await user.selectOptions(due, '향후 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: '2026-01-31', dueTo: '2026-02-28' })
  })

  it('combines an acted preset and a due preset in one query', async () => {
    const { user, onSearch, form, acted, due } = await renderBar()
    await presetsLoaded(acted)

    await user.selectOptions(acted, '최근 1개월')
    await user.selectOptions(due, '향후 2개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({
      actedFrom: '2026-09-22',
      actedTo: '2026-10-22',
      dueFrom: '2026-10-22',
      dueTo: '2026-12-22',
    })
  })

  it('fetches presets fresh at search time', async () => {
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '최근 1개월')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-22', actedTo: '2026-10-22' })

    defaultMock.clock.setNow(NEXT_DAY_AT)
    await user.click(within(form).getByRole('button', { name: '검색' }))

    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(2))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-23', actedTo: '2026-10-23' })
  })

  it('does not ask the server for presets when no preset is chosen', async () => {
    const spy = vi.spyOn(gateway.deals, 'updatedPeriods')
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    const before = spy.mock.calls.length

    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls.length).toBe(before)
  })
})

describe('직접 지정과 전체 (AC-19, AC-20)', () => {
  it('custom shows date inputs and sends only filled dates', async () => {
    const { user, onSearch, form, acted } = await renderBar()

    await user.selectOptions(acted, '직접 지정')
    expect(within(form).getByLabelText('수행일 시작')).toBeVisible()
    expect(within(form).getByLabelText('수행일 끝')).toBeVisible()
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-09-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-01' })
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  it('sends both custom dates of the due condition', async () => {
    const { user, onSearch, form, due } = await renderBar()

    await user.selectOptions(due, '직접 지정')
    await user.type(within(form).getByLabelText('기한 시작'), '2026-11-01')
    await user.type(within(form).getByLabelText('기한 끝'), '2026-11-30')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(lastQuery(onSearch)).toMatchObject({ dueFrom: '2026-11-01', dueTo: '2026-11-30' })
  })

  it('types the custom date as yyyymmdd and searches with the ISO date (AC-D1)', async () => {
    const { user, onSearch, form, acted } = await renderBar()

    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '20260901')
    expect(within(form).getByLabelText('수행일 시작')).toHaveValue('2026.09.01')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-09-01' })
  })

  it('does not search while a custom date is wrong and shows the message in the field (AC-D3)', async () => {
    const { user, onSearch, form, due } = await renderBar()

    await user.selectOptions(due, '직접 지정')
    await user.type(within(form).getByLabelText('기한 끝'), '20261340')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(onSearch).not.toHaveBeenCalled()
    expect(within(form).getByText('없는 날짜입니다.')).toBeVisible()
    expect(within(form).getByLabelText('기한 끝')).toHaveAttribute('aria-invalid', 'true')
  })

  it('does not search while a custom date is only partly typed (AC-D3)', async () => {
    const { user, onSearch, form, acted } = await renderBar()

    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026.09')
    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(onSearch).not.toHaveBeenCalled()
    expect(within(form).getByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  it('shows no message or aria-invalid while typing again after a successful search (AC-D3)', async () => {
    const { user, onSearch, form, acted } = await renderBar()
    await user.selectOptions(acted, '직접 지정')
    const from = within(form).getByLabelText('수행일 시작')
    await user.type(from, '20260901')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    expect(onSearch).toHaveBeenCalledTimes(1)

    await user.clear(from)
    await user.type(from, '2026.1')

    expect(within(form).queryByRole('alert')).not.toBeInTheDocument()
    expect(from).not.toHaveAttribute('aria-invalid')
  })

  it('shows the message again only after leaving the field following the successful search', async () => {
    const { user, form, acted } = await renderBar()
    await user.selectOptions(acted, '직접 지정')
    const from = within(form).getByLabelText('수행일 시작')
    await user.type(from, '20260901')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await user.clear(from)
    await user.type(from, '2026.1')
    await user.tab()

    expect(within(form).getByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  it('hides the inputs and ignores the typed dates after switching to a preset or to all', async () => {
    const { user, onSearch, form, acted } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-01-01')
    await user.type(within(form).getByLabelText('수행일 끝'), '2026-01-31')

    await user.selectOptions(acted, '최근 2주')
    expect(within(form).queryByLabelText('수행일 시작')).not.toBeInTheDocument()
    expect(within(form).queryByLabelText('수행일 끝')).not.toBeInTheDocument()
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08', actedTo: '2026-10-22' })

    await user.selectOptions(acted, '전체')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(2))
    expect(lastQuery(onSearch)).not.toHaveProperty('actedFrom')
    expect(lastQuery(onSearch)).not.toHaveProperty('actedTo')
  })

  it('all sends no date params', async () => {
    const { user, onSearch, form } = await renderBar()

    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(onSearch).toHaveBeenCalledTimes(1)
    for (const key of ['actedFrom', 'actedTo', 'dueFrom', 'dueTo']) expect(lastQuery(onSearch)).not.toHaveProperty(key)
  })
})

describe('프리셋을 받지 못한 경우 (AC-21, AC-22)', () => {
  const failure = () =>
    new ApiError(500, {
      type: 'https://sales.neoine.test/problems/internal',
      title: 'x',
      status: 500,
      detail: '기간 정보를 불러오지 못했습니다.',
    })

  it('disables presets until the presets load and shows the load error', async () => {
    vi.spyOn(gateway.deals, 'updatedPeriods').mockRejectedValue(failure())
    const { form, acted, due } = await renderBar()

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

  it('keeps presets disabled while loading and enables them after the response', async () => {
    let release: (value: UpdatedPeriods) => void = () => {}
    const original = gateway.deals.updatedPeriods.bind(gateway.deals)
    const loaded = original()
    vi.spyOn(gateway.deals, 'updatedPeriods').mockImplementation(
      () =>
        new Promise<UpdatedPeriods>((resolve) => {
          release = resolve
        }),
    )
    const { acted, due } = await renderBar()
    expect(within(acted).getByRole('option', { name: '최근 1개월' })).toBeDisabled()
    expect(within(due).getByRole('option', { name: '향후 1개월' })).toBeDisabled()
    expect(within(acted).getByRole('option', { name: '직접 지정' })).toBeEnabled()

    release(await loaded)

    await presetsLoaded(acted)
    expect(within(due).getByRole('option', { name: '향후 1개월' })).toBeEnabled()
  })

  it('keeps the previous query and shows the error when refreshing presets fails', async () => {
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
    failing = true

    await user.click(within(form).getByRole('button', { name: '검색' }))

    expect(await within(form).findByRole('alert')).toHaveTextContent('기간 정보를 불러오지 못했습니다.')
    expect(onSearch).toHaveBeenCalledTimes(1)
  })

  it('ignores a late preset response after reset', async () => {
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
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenLastCalledWith({})

    release()
    await new Promise((resolve) => setTimeout(resolve, 30))

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenLastCalledWith({})
  })

  it('ignores the late response of an earlier search when a newer search was made', async () => {
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
    await user.selectOptions(acted, '최근 2주')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(onSearch).toHaveBeenCalledTimes(1))
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08' })

    release()
    await new Promise((resolve) => setTimeout(resolve, 30))

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(lastQuery(onSearch)).toMatchObject({ actedFrom: '2026-10-08' })
  })
})

describe('초기화 (AC-23)', () => {
  it('reset returns both periods to all and clears the custom dates', async () => {
    const { user, onSearch, form, acted, due } = await renderBar()
    await presetsLoaded(acted)
    await user.selectOptions(acted, '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '2026-09-01')
    await user.selectOptions(due, '향후 1개월')

    await user.click(within(form).getByRole('button', { name: '초기화' }))

    expect(acted).toHaveDisplayValue('전체')
    expect(due).toHaveDisplayValue('전체')
    expect(within(form).queryByLabelText('수행일 시작')).not.toBeInTheDocument()
    expect(onSearch).toHaveBeenLastCalledWith({})
    await user.selectOptions(acted, '직접 지정')
    expect(within(form).getByLabelText('수행일 시작')).toHaveValue('')
    expect(within(form).getByLabelText('수행일 끝')).toHaveValue('')
  })
})
