/**
 * IntersectionObserver 대역(jsdom에는 없다). 무한 스크롤 테스트가 쓴다.
 *
 *   const io = installIntersectionObserver()   // 테스트 안에서(화면을 렌더하기 전에)
 *   ...
 *   io.triggerIntersect()                       // 관찰 중인 모든 대상이 화면에 들어온 것처럼 콜백을 부른다
 *   io.restore()                                // afterEach에서(원래 상태로)
 *
 * 구현은 `new IntersectionObserver(callback, options)` → `observe(target)` 규약만 쓰면 된다.
 * `disconnect()`/`unobserve()`된 대상에는 콜백이 가지 않는다. `created`는 만들어진 관찰자 수(재연결 확인용).
 */

import { act } from 'react'

type Callback = (entries: IntersectionObserverEntry[], observer: IntersectionObserver) => void

interface Fake {
  callback: Callback
  options: IntersectionObserverInit | undefined
  targets: Set<Element>
  instance: IntersectionObserver
}

export interface IntersectionObserverStub {
  /** 관찰 중인 대상마다 isIntersecting=true 항목을 만들어 콜백을 부른다. 내부에서 act로 감싼다. */
  triggerIntersect(): void
  /** 지금 관찰 중인 대상 수. */
  observedCount(): number
  /** 지금까지 만들어진 관찰자 수. */
  created(): number
  /** 만들어진 관찰자의 옵션(rootMargin 등). */
  optionsOfLast(): IntersectionObserverInit | undefined
  restore(): void
}

export function installIntersectionObserver(): IntersectionObserverStub {
  const original = (globalThis as { IntersectionObserver?: unknown }).IntersectionObserver
  const all: Fake[] = []

  class StubObserver {
    constructor(callback: Callback, options?: IntersectionObserverInit) {
      const record: Fake = { callback, options, targets: new Set(), instance: this as unknown as IntersectionObserver }
      all.push(record)
      Object.defineProperty(this, '__record', { value: record })
    }
    private get record(): Fake {
      return (this as unknown as { __record: Fake }).__record
    }
    observe(target: Element): void {
      this.record.targets.add(target)
    }
    unobserve(target: Element): void {
      this.record.targets.delete(target)
    }
    disconnect(): void {
      this.record.targets.clear()
    }
    takeRecords(): IntersectionObserverEntry[] {
      return []
    }
  }
  Object.defineProperty(globalThis, 'IntersectionObserver', { configurable: true, writable: true, value: StubObserver })

  return {
    triggerIntersect() {
      act(() => {
        for (const record of all) {
          if (record.targets.size === 0) continue
          const entries = [...record.targets].map((target) => ({ isIntersecting: true, intersectionRatio: 1, target }) as unknown as IntersectionObserverEntry)
          record.callback(entries, record.instance)
        }
      })
    },
    observedCount: () => all.reduce((sum, r) => sum + r.targets.size, 0),
    created: () => all.length,
    optionsOfLast: () => all.at(-1)?.options,
    restore() {
      if (original === undefined) Reflect.deleteProperty(globalThis, 'IntersectionObserver')
      else Object.defineProperty(globalThis, 'IntersectionObserver', { configurable: true, writable: true, value: original })
    },
  }
}
