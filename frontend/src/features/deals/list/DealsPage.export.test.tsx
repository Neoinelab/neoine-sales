import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'

/** Deals 목록의 CSV 다운로드 버튼(DL-R37). 앱 시계는 서버 업무 날짜 2026-10-15다. */
const NOW = '2026-10-15T12:00:00+09:00'
const FILE_NAME = 'Deals_20261015.csv'
const LIMIT_MESSAGE = '내려받을 Deal이 10,000건을 넘습니다(10,001건). 조건을 좁혀 다시 시도하세요.'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(URL, 'createObjectURL')
  Reflect.deleteProperty(URL, 'revokeObjectURL')
  resetMock({ now: null })
})

const exportButton = () => screen.getByRole('button', { name: 'CSV 다운로드' })

/** jsdom에는 파일 저장이 없어 객체 URL 생성과 링크 클릭을 가로채 "저장 시작"을 기록한다. */
function interceptSaving(): { name: string }[] {
  const saved: { name: string }[] = []
  Object.assign(URL, { createObjectURL: () => 'blob:fake', revokeObjectURL: () => undefined })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    saved.push({ name: this.download })
  })
  return saved
}

describe('Deals 목록 CSV 다운로드', () => {
  // 총 N건 줄의 마지막 요소인 버튼이 지금 조건·정렬(페이지 정보 없이)로 내보내기를 요청하고 응답의 파일 이름으로 저장한다
  // 테스트 코드: DL-120
  it('exports the whole current result with the current sort and no paging, from the last element of the count line', async () => {
    // given: viewer(user)가 금액 오름차순 2페이지 목록을 연다. 파일 저장은 가로챈다
    const saved = interceptSaving()
    const spy = vi.spyOn(gateway.deals, 'exportCsv')
    const { user, location } = await renderAt('/deals?year=all&sort=revenueAmount&order=asc&page=2', { role: 'user' })
    const count = await screen.findByText(/^총 \d+건$/)
    const rowsBefore = dataRows().length
    const urlBefore = location()

    // when: "CSV 다운로드"를 누른다
    // then: 버튼은 "총 N건"과 같은 줄의 마지막 요소다
    expect(count.parentElement?.lastElementChild).toBe(exportButton())
    expect(exportButton()).toHaveAttribute('title', 'CSV 다운로드')
    await user.click(exportButton())

    // then: 내보내기 요청이 한 번이고 조건에 정렬이 있으며 offset·limit이 없다
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(spy).toHaveBeenCalledTimes(1)
    const query = spy.mock.calls[0]?.[0]
    expect(query).toMatchObject({ sort: 'revenueAmount', order: 'asc' })
    expect(query).not.toHaveProperty('offset')
    expect(query).not.toHaveProperty('limit')
    // then: 응답의 파일 이름으로 저장되고 주소와 목록은 그대로다
    expect(saved[0]?.name).toBe(FILE_NAME)
    expect(location()).toBe(urlBefore)
    expect(dataRows()).toHaveLength(rowsBefore)
  })

  // 요청 중에는 비활성이고 다시 눌러도 요청이 늘지 않으며 끝나면 다시 활성이다
  // 테스트 코드: DL-121
  it('disables the button while the request is pending and enables it again afterwards', async () => {
    // given: 응답이 늦게 오는 내보내기
    const saved = interceptSaving()
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const spy = vi.spyOn(gateway.deals, 'exportCsv').mockImplementation(async () => {
      await gate
      return { fileName: FILE_NAME, blob: new Blob(['x']) }
    })
    const { user } = await renderAt('/deals?year=all', { role: 'admin' })
    await screen.findByText(/^총 \d+건$/)

    // when: 누르고 응답 전에 다시 누른다
    await user.click(exportButton())
    // then: 요청 중에는 버튼이 비활성이고 요청은 한 번이다
    await waitFor(() => expect(exportButton()).toBeDisabled())
    await user.click(exportButton())
    expect(spy).toHaveBeenCalledTimes(1)

    // when: 응답이 온다
    release()
    // then: 저장이 시작되고 버튼은 다시 활성이다
    await waitFor(() => expect(saved).toHaveLength(1))
    await waitFor(() => expect(exportButton()).toBeEnabled())
  })

  // 실패하면 서버 문구의 오류 배너를 보이고 목록은 그대로이며 다시 성공하면 배너가 사라진다
  // 테스트 코드: DL-121
  it('shows the server message in an error banner on failure, keeps the list, and clears the banner on the next success', async () => {
    // given: 상한 초과(422)로 실패하는 내보내기
    const saved = interceptSaving()
    const problem = { type: 'https://neoine-sales/problems/invalid-value', title: 'Invalid Value', status: 422, detail: LIMIT_MESSAGE }
    const spy = vi.spyOn(gateway.deals, 'exportCsv').mockRejectedValueOnce(new ApiError(422, problem))
    const { user, location } = await renderAt('/deals?year=all', { role: 'admin' })
    await rowOf(/한빛은행 ITDR 도입/)
    const rowsBefore = dataRows().length
    const urlBefore = location()

    // when: "CSV 다운로드"를 누른다
    await user.click(exportButton())

    // then: 서버 문구의 오류 배너가 보이고 목록·주소는 그대로이며 버튼은 다시 활성이다
    expect(await screen.findByRole('alert')).toHaveTextContent(LIMIT_MESSAGE)
    expect(saved).toHaveLength(0)
    expect(dataRows()).toHaveLength(rowsBefore)
    expect(location()).toBe(urlBefore)
    expect(exportButton()).toBeEnabled()

    // when: 이어서 성공하도록 두고 다시 누른다(원래 Fake 구현으로 돌아간다)
    spy.mockRestore()
    await user.click(exportButton())
    // then: 배너가 사라지고 파일이 내려받아진다
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(saved[0]?.name).toBe(FILE_NAME)
  })

  // 0건이면 비활성이고 첫 응답 전에는 버튼이 없다
  // 테스트 코드: DL-122
  it('has no button before the first response and a disabled one when the total is zero', async () => {
    // given: 응답이 늦게 오는 목록과 조건에 맞는 Deal이 없는 주소
    const original = gateway.deals.list.bind(gateway.deals)
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      await gate
      return original(query)
    })

    // when: /deals?year=all&status=zz를 연다
    await renderAt('/deals?year=all&status=zz', { role: 'sales' })

    // then: 응답 전("불러오는 중…")에는 버튼이 없다
    expect(await screen.findByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'CSV 다운로드' })).not.toBeInTheDocument()

    // when: 응답이 온다
    release()
    // then: "총 0건" 줄의 버튼은 비활성이다
    const count = await screen.findByText('총 0건')
    expect(within(count.parentElement as HTMLElement).getByRole('button', { name: 'CSV 다운로드' })).toBeDisabled()
  })

  // 오류 배너는 목록 조건을 바꿔 검색하면 사라지고 새 조건의 목록과 버튼이 보인다
  // 테스트 코드: DL-124
  it('clears the error banner when the list conditions change and keeps the export button', async () => {
    // given: 상한 초과(422)로 실패해 오류 배너가 보이는 목록
    interceptSaving()
    const problem = { type: 'https://neoine-sales/problems/invalid-value', title: 'Invalid Value', status: 422, detail: LIMIT_MESSAGE }
    vi.spyOn(gateway.deals, 'exportCsv').mockRejectedValueOnce(new ApiError(422, problem))
    const { user } = await renderAt('/deals?year=all', { role: 'admin' })
    await rowOf(/한빛은행 ITDR 도입/)
    await user.click(exportButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(LIMIT_MESSAGE)

    // when: 키워드 조건을 바꿔 검색한다
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: 오류 배너가 사라지고 새 조건의 목록과 CSV 다운로드 버튼이 보인다
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    await rowOf(/한빛은행 ITDR 도입/)
    expect(exportButton()).toBeEnabled()
  })

  // 응답 전에 조건을 바꿔도 응답까지 버튼은 비활성이고 응답이 오면 파일이 저장된다
  // 테스트 코드: DL-125
  it('keeps the button disabled until the response and still saves the file when conditions change while pending', async () => {
    // given: 응답이 늦게 오는 내보내기
    const saved = interceptSaving()
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.spyOn(gateway.deals, 'exportCsv').mockImplementation(async () => {
      await gate
      return { fileName: FILE_NAME, blob: new Blob(['x']) }
    })
    const { user } = await renderAt('/deals?year=all', { role: 'admin' })
    await rowOf(/한빛은행 ITDR 도입/)
    await user.click(exportButton())
    await waitFor(() => expect(exportButton()).toBeDisabled())

    // when: 응답 전에 키워드 조건을 바꿔 검색한다
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.click(screen.getByRole('button', { name: '검색' }))
    await rowOf(/한빛은행 ITDR 도입/)

    // then: 응답 전이라 버튼은 여전히 비활성이고 저장은 없다
    expect(exportButton()).toBeDisabled()
    expect(saved).toHaveLength(0)

    // when: 응답이 온다
    release()
    // then: 파일이 저장되고 버튼은 다시 활성이며 오류 배너는 없다
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]?.name).toBe(FILE_NAME)
    await waitFor(() => expect(exportButton()).toBeEnabled())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
