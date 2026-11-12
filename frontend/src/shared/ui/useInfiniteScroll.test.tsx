import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { installIntersectionObserver, type IntersectionObserverStub } from '../../test/intersectionObserver'
import { useInfiniteScroll } from './useInfiniteScroll'

interface HarnessProps {
  hasNextPage: boolean
  isFetchingNextPage: boolean
  fetchNextPage: () => void
  pages?: number
}

function Harness({ hasNextPage, isFetchingNextPage, fetchNextPage, pages = 1 }: HarnessProps) {
  const sentinelRef = useInfiniteScroll({ hasNextPage, isFetchingNextPage, fetchNextPage, pages })
  return <div ref={sentinelRef} data-testid="sentinel" />
}

let io: IntersectionObserverStub | null = null
afterEach(() => {
  io?.restore()
  io = null
})

describe('useInfiniteScroll', () => {
  // 테스트 코드: UI-049
  it('표지를 200px 바깥 여백으로 관찰한다', () => {
    // given: 다음 페이지가 있고 읽는 중이 아닌 목록 (전제: IntersectionObserver 스텁)
    io = installIntersectionObserver()
    // when: 그린다
    render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)
    // then: 관찰 대상은 하나이고 rootMargin은 200px이다
    expect(io.observedCount()).toBe(1)
    expect(io.optionsOfLast()).toMatchObject({ rootMargin: '200px' })
  })

  // 테스트 코드: UI-049
  it('표지가 화면 가까이 들어오면 다음 페이지를 한 번 요청한다', () => {
    // given: 다음 페이지가 있고 읽는 중이 아닌 목록
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)
    // when: 표지가 들어온다
    io.triggerIntersect()
    // then: fetchNextPage가 한 번 불린다
    expect(fetchNextPage).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-050
  it('다음 페이지가 없으면 요청하지 않는다', () => {
    // given: 다음 페이지가 없는 목록
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage={false} isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)
    // when: 표지가 들어온다
    io.triggerIntersect()
    // then: 요청이 없다
    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-050
  it('이미 읽는 중이면 요청하지 않는다', () => {
    // given: 다음 페이지를 읽는 중인 목록
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage isFetchingNextPage fetchNextPage={fetchNextPage} />)
    // when: 표지가 들어온다
    io.triggerIntersect()
    // then: 요청이 없다
    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-050
  it('교차하는 순간의 최신 상태를 쓴다', () => {
    // given: 처음엔 다음 페이지가 있었지만 다시 그릴 때 없어진 목록
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)
    view.rerender(<Harness hasNextPage={false} isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)
    // when: 표지가 들어온다
    io.triggerIntersect()
    // then: 요청이 없다
    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-051
  it('불러온 페이지 수가 바뀌면 관찰을 다시 건다', () => {
    // given: 페이지 1을 관찰 중인 표지
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} pages={1} />)
    const before = io.created()
    // when: 페이지 수가 2가 된다
    view.rerender(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} pages={2} />)
    // then: 관찰자가 새로 만들어지고 관찰 대상은 여전히 하나다
    expect(io.created()).toBeGreaterThan(before)
    expect(io.observedCount()).toBe(1) // 이전 관찰은 끊겼다
  })

  // 테스트 코드: UI-051
  it('화면을 떠나면 관찰을 끊는다', () => {
    // given: 표지를 관찰 중인 목록
    io = installIntersectionObserver()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)
    // when: 화면을 떠난다
    view.unmount()
    // then: 관찰 대상이 0이다
    expect(io.observedCount()).toBe(0)
  })

  // 테스트 코드: UI-051
  it('IntersectionObserver가 없어도 오류 없이 그려진다', () => {
    // when·then: IntersectionObserver가 없는 환경에서 그려도 예외가 없다 (전제: 스텁을 설치하지 않음)
    expect(() => render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)).not.toThrow()
  })
})
