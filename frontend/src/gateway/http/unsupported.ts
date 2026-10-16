/** 아직 서버가 없는 기능. 각 단계에서 해당 메서드를 실제 구현으로 바꾼다. */

import { ApiError } from '../../shared/api/problem'

export const NOT_IMPLEMENTED_MESSAGE = '아직 실제 서버와 연결되지 않은 기능입니다.'

/** 인자는 무시한다. 서버를 부르지 않고 501 problem으로 reject한다. */
export function notImplemented(): Promise<never> {
  return Promise.reject(
    new ApiError(501, {
      type: 'https://sales.neoine.test/problems/not-implemented',
      title: 'Not Implemented',
      status: 501,
      detail: NOT_IMPLEMENTED_MESSAGE,
    }),
  )
}
