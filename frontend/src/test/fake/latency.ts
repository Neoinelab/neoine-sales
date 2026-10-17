/** 가짜 응답 지연. 개발 서버에서는 읽기 150~300ms, 쓰기 300~600ms. 테스트(enabled=false)에서는 항상 0ms. */

export type LatencyKind = 'read' | 'write'

export interface Latency {
  /**
   * fn을 실행한 뒤(상태 변경은 즉시, 호출 순서대로) 지연이 지나서 결과를 돌려준다.
   * fn이 던지면 같은 지연 뒤에 reject한다.
   */
  run<T>(kind: LatencyKind, fn: () => T): Promise<T>
  setOn(on: boolean): void
  isOn(): boolean
}

const RANGES: Record<LatencyKind, readonly [number, number]> = {
  read: [150, 300],
  write: [300, 600],
}

/**
 * `available=false`(테스트)면 on/off 표시는 바뀌어도 실제 지연은 항상 0ms다.
 * on 표시는 켜진 상태를 보여주기 위한 값이다.
 */
export function createLatency(available: boolean, random: () => number = Math.random): Latency {
  let on = true
  const wait = (kind: LatencyKind): Promise<void> => {
    if (!available || !on) return Promise.resolve()
    const [min, max] = RANGES[kind]
    return new Promise((resolve) => setTimeout(resolve, min + random() * (max - min)))
  }
  return {
    async run(kind, fn) {
      let result: ReturnType<typeof fn>
      try {
        result = fn()
      } catch (error) {
        await wait(kind)
        throw error
      }
      await wait(kind)
      return result
    },
    setOn(next) {
      on = next
    },
    isOn: () => on,
  }
}
