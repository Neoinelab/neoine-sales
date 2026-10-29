import { useCallback, useEffect, useRef, useState } from 'react'

interface InfiniteScrollOptions {
  hasNextPage: boolean
  isFetchingNextPage: boolean
  fetchNextPage: () => void
  /** 불러온 페이지 수. 바뀌면 관찰을 다시 연결해, 화면에 그대로 남은 sentinel이 한 번 더 신호를 낸다. */
  pages: number
}

/** 목록 아래 sentinel 요소가 화면 가까이(200px) 오면 다음 페이지를 요청한다. 돌려준 ref를 sentinel에 붙인다. */
export function useInfiniteScroll({ hasNextPage, isFetchingNextPage, fetchNextPage, pages }: InfiniteScrollOptions): (el: HTMLElement | null) => void {
  const [target, setTarget] = useState<HTMLElement | null>(null)
  // 교차 시점의 최신 상태를 읽도록 ref에 둔다(관찰자를 상태마다 다시 만들지 않는다).
  const latest = useRef({ hasNextPage, isFetchingNextPage, fetchNextPage })
  useEffect(() => {
    latest.current = { hasNextPage, isFetchingNextPage, fetchNextPage }
  })

  useEffect(() => {
    if (!target || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        const current = latest.current
        if (current.hasNextPage && !current.isFetchingNextPage) current.fetchNextPage()
      },
      { rootMargin: '200px' },
    )
    observer.observe(target)
    return () => observer.disconnect()
  }, [target, pages])

  return useCallback((el: HTMLElement | null) => setTarget(el), [])
}
