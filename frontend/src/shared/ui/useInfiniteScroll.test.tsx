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
  it('observes the sentinel with a 200px root margin', () => {
    io = installIntersectionObserver()

    render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)

    expect(io.observedCount()).toBe(1)
    expect(io.optionsOfLast()).toMatchObject({ rootMargin: '200px' })
  })

  it('asks for the next page when the sentinel comes into view', () => {
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)

    io.triggerIntersect()

    expect(fetchNextPage).toHaveBeenCalledTimes(1)
  })

  it('does nothing when there is no next page', () => {
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage={false} isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)

    io.triggerIntersect()

    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  it('does nothing while a page is already being fetched', () => {
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    render(<Harness hasNextPage isFetchingNextPage fetchNextPage={fetchNextPage} />)

    io.triggerIntersect()

    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  it('uses the latest state at the moment of intersection (no stale closure)', () => {
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)

    view.rerender(<Harness hasNextPage={false} isFetchingNextPage={false} fetchNextPage={fetchNextPage} />)
    io.triggerIntersect()

    expect(fetchNextPage).not.toHaveBeenCalled()
  })

  it('connects again when the number of pages changes so a sentinel that stayed in view fires once more', () => {
    io = installIntersectionObserver()
    const fetchNextPage = vi.fn()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} pages={1} />)
    const before = io.created()

    view.rerender(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={fetchNextPage} pages={2} />)

    expect(io.created()).toBeGreaterThan(before)
    expect(io.observedCount()).toBe(1) // 이전 관찰은 끊겼다
  })

  it('stops observing when unmounted', () => {
    io = installIntersectionObserver()
    const view = render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)

    view.unmount()

    expect(io.observedCount()).toBe(0)
  })

  it('does not throw without IntersectionObserver', () => {
    expect(() => render(<Harness hasNextPage isFetchingNextPage={false} fetchNextPage={vi.fn()} />)).not.toThrow()
  })
})
