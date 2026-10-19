import { takeId, type ActionTypeRecord } from '../store'
import type { SeedEnv } from './env'

/** 마이그레이션이 넣는 기본 Action 유형 8개(순서 고정). 서버 시드와 같은 이름·순서다. */
export const DEFAULT_ACTION_TYPE_NAMES = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'] as const

/** 기본 유형의 시드 id(`at-001`~`at-008`). 테스트가 이름으로 id를 찾을 때 쓴다. */
export function seedActionTypeId(name: (typeof DEFAULT_ACTION_TYPE_NAMES)[number]): string {
  return `at-${String(DEFAULT_ACTION_TYPE_NAMES.indexOf(name) + 1).padStart(3, '0')}`
}

export function seedActionTypes(env: SeedEnv, counters: Record<string, number>): ActionTypeRecord[] {
  const at = env.at(300, 9)
  return DEFAULT_ACTION_TYPE_NAMES.map((name) => ({
    id: takeId(counters, 'at'),
    name,
    isDefault: true,
    createdById: null,
    createdAt: at,
    updatedAt: at,
  }))
}
