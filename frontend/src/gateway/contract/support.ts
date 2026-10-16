/**
 * 게이트웨이 계약 스위트의 공통 도구. 스위트는 구현(mock·HTTP)을 모르고 `MakeGateway`만 받는다.
 * 실제 서버에 돌려도 서로 부딪히지 않도록 이름은 호출마다 고유하게 만든다(스위트는 만든 것을 스스로 치운다).
 */

import { expect } from 'vitest'
import type { Gateway } from '../types'
import type { ApiError } from '../../shared/api/problem'

export type ContractRole = 'admin' | 'sales' | 'user'

/**
 * 해당 역할로 로그인한 게이트웨이를 만든다. 한 테스트 안의 호출들은 같은 데이터를 본다.
 * mock은 세션이 하나라 마지막으로 만든 역할이 유효하다: 역할을 바꾼 뒤에는 이전 게이트웨이를 쓰지 말고 `make`를 다시 부른다.
 */
export type MakeGateway = (role: ContractRole) => Promise<Gateway>

let sequence = 0

/** 호출마다 다른 한 단어(공백 없음) 이름. 영문 소문자·숫자만 써서 코드 key 규칙에도 맞는다. */
export function unique(prefix: string): string {
  sequence += 1
  return `${prefix}${Date.now().toString(36)}${sequence}`.toLowerCase()
}

/** reject를 기다려 ApiError의 상태와 문구를 확인한다. */
export async function expectRejects(promise: Promise<unknown>, status: number, message?: string): Promise<ApiError> {
  let caught: unknown
  try {
    await promise
  } catch (error) {
    caught = error
  }
  if (caught === undefined) throw new Error('reject되어야 하는데 성공했습니다.')
  const error = caught as ApiError
  expect(error.status).toBe(status)
  if (message !== undefined) expect(error.message).toBe(message)
  return error
}
