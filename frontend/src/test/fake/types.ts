/**
 * Fake 전용 제어(테스트가 사용). `default.ts`가 `mockControl`로 내보낸다.
 * 게이트웨이 메서드가 아니므로 권한·History와 무관하다.
 */
export interface MockControl {
  /** 시드로 복원(로그인 유지). 쿼리 캐시 무효화는 호출자가 `queryClient.invalidateQueries()`로 한다. */
  resetData(): void
  /** SetupState를 모두 false로 하고 로그아웃(세션 제거). */
  restartSetup(): void
  setStorageFailure(on: boolean): void
  isStorageFailure(): boolean
  /** 가짜 지연 on/off. 테스트 모드에서는 항상 0ms. */
  now(): string // Fake 시계의 지금(ISO). 화면은 `useToday()`(data/today.ts)로만 읽는다.
  setLatency(on: boolean): void
  isLatencyOn(): boolean
}
