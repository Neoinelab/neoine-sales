/**
 * 시드 사용자의 고정 id(서버의 BIGINT id처럼 양의 정수). 테스트는 숫자 리터럴 대신 이 상수를 쓴다.
 * 순서는 `seedUsers`의 행 순서와 같다. 새로 등록하는 사용자는 이 번호 다음부터 받는다.
 */
export const USER_ID = {
  root: 1,
  kim: 2,
  park: 3,
  lee: 4,
  jung: 5,
  han: 6,
  old: 7,
} as const

export type SeedLoginId = keyof typeof USER_ID

/** 어디에도 없는 id(서버 허용 범위 1~2^53−1 안의 최댓값). 형식 오류가 아니라 '없음'(404 등)을 만든다. */
export const NO_SUCH_ID = Number.MAX_SAFE_INTEGER
