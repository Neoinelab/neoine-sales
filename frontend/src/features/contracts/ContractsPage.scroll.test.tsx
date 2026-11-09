import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { installIntersectionObserver, type IntersectionObserverStub } from '../../test/intersectionObserver'
import { allContracts } from '../../test/licenseContracts'
import { renderAt } from '../../test/mockApp'
import { pinClock, unpinClock } from '../../test/partnerMeetings'

/** 계약관리 50건씩 무한 스크롤(AC19, D8): 서버 total 기준이며 겹친 행은 id로 한 번만 보인다. */
const LOAD = { timeout: 8000 }
const PAGE_SIZE = 50

let total = 0
let io: IntersectionObserverStub | null = null
beforeEach(async () => {
  pinClock()
  total = (await allContracts()).length
})
afterEach(() => {
  io?.restore()
  io = null
  unpinClock()
  vi.restoreAllMocks()
})

const rows = () => within(screen.getByRole('table', { name: '계약 목록' })).getAllByRole('row').slice(1)
const waitForRows = async (count: number) => {
  await screen.findByRole('table', { name: '계약 목록' }, LOAD)
  await waitFor(() => expect(rows()).toHaveLength(count), LOAD)
}

describe('무한 스크롤 (AC19)', () => {
  // 시드 계약이 한 쪽(50건)보다 많은지 확인한다.
  it('needs more than one page of seed contracts', () => {
    // given: Fake 게이트웨이의 시드 계약
    // when: 건수를 센다
    // then: 50건보다 많다
    expect(total).toBeGreaterThan(PAGE_SIZE)
  })

  // 50건씩 읽고 끝이 보이면 다음 50건을 잇는다.
  // 테스트 코드: LC-023
  it('reads fifty at a time with the total from the server and appends the next page when the end scrolls into view', async () => {
    // given: 서버에 계약이 50건보다 많다
    io = installIntersectionObserver()
    const list = vi.spyOn(gateway.licenseContracts, 'list')
    await renderAt('/contracts')
    // when: 목록 끝(감시 요소)이 화면에 들어온다
    await waitForRows(PAGE_SIZE)
    // then: 다음 50건이 이어 붙는다
    expect(list.mock.calls[0]?.slice(1)).toEqual([0, PAGE_SIZE])
    expect(screen.getByText(`전체 ${total}건`)).toBeVisible()
    expect(screen.queryByText(/모두 불러왔습니다/)).not.toBeInTheDocument()

    io.triggerIntersect()

    await waitForRows(Math.min(total, PAGE_SIZE * 2))
    expect(list.mock.calls.some((call) => call[1] === PAGE_SIZE && call[2] === PAGE_SIZE)).toBe(true)
  })

  // 감시 요소를 200px 여유로 관찰하고 다 읽으면 끝을 알린다.
  // 테스트 코드: LC-023
  it('observes a sentinel with a 200px root margin and says everything is loaded after the last page', async () => {
    // given: 서버에 계약이 여러 쪽 있다
    io = installIntersectionObserver()
    await renderAt('/contracts')
    // when: 마지막 쪽까지 읽는다
    await waitForRows(PAGE_SIZE)
    // then: 모두 불러왔습니다 (전체 N건)이 보인다
    expect(io.optionsOfLast()).toMatchObject({ rootMargin: '200px' })

    for (let page = 1; page * PAGE_SIZE < total; page += 1) {
      io.triggerIntersect()
      await waitForRows(Math.min(total, (page + 1) * PAGE_SIZE))
    }

    expect(await screen.findByText(`모두 불러왔습니다 (전체 ${total}건)`)).toBeVisible()
    io.triggerIntersect()
    expect(rows()).toHaveLength(total)
  })

  // 쪽 사이에 목록이 밀려 같은 id가 겹쳐도 한 번만 보인다.
  // 테스트 코드: LC-023
  it('shows each contract once even if the list shifts between pages', async () => {
    // given: 쪽 사이에 같은 계약이 겹쳐 오는 서버
    io = installIntersectionObserver()
    const original = gateway.licenseContracts.list.bind(gateway.licenseContracts)
    vi.spyOn(gateway.licenseContracts, 'list').mockImplementation(async (query, offset, limit) => {
      const page = await original(query, offset, limit)
      return offset === 0 ? page : await original(query, Math.max(0, offset - 3), limit) // 쪽 경계가 3건 밀린 응답
    })
    await renderAt('/contracts')
    // when: 다음 쪽을 읽는다
    await waitForRows(PAGE_SIZE)

    io.triggerIntersect()

    // then: 같은 id가 한 번만 보인다
    await waitForRows(Math.min(total, PAGE_SIZE * 2 - 3)) // 겹친 3건은 한 번만
  })

  // 다음 쪽이 있으면 더 보기 버튼이 보이고 누르면 읽는다.
  // 테스트 코드: LC-023
  it('shows a more-button while there is a next page and loads it on click', async () => {
    // given: 서버에 다음 쪽이 있다
    const { user } = await renderAt('/contracts')
    await waitForRows(PAGE_SIZE)

    // when: 더 보기를 누른다
    await user.click(screen.getByRole('button', { name: '더 보기' }))

    // then: 다음 쪽이 이어 붙고 마지막 쪽 뒤에는 버튼이 없다
    await waitForRows(Math.min(total, PAGE_SIZE * 2))
  })
})
