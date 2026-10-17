import type { Role } from '../../../shared/model/types'
import type { UserRecord } from '../store'
import type { SeedEnv } from './env'

/** [loginId, 이름, 역할, 등록 며칠 전, 마지막 로그인 며칠 전]. 사용자 id는 `u-<loginId>`. */
const ROWS: readonly (readonly [string, string, Role, number, number | null])[] = [
  ['root', '최관리', 'admin', 200, 0],
  ['kim', '김영업', 'sales', 190, 1],
  ['park', '박영업', 'sales', 185, 2],
  ['lee', '이영업', 'sales', 180, 3],
  ['jung', '정영업', 'sales', 120, 5],
  ['han', '한조회', 'user', 100, 7],
  ['old', '강퇴사', 'sales', 170, 20],
]

export function seedUsers(env: SeedEnv): UserRecord[] {
  return ROWS.map(([loginId, name, role, createdAgo, loginAgo]) => {
    const resigned = loginId === 'old'
    return {
      id: `u-${loginId}`,
      loginId,
      name,
      role,
      status: resigned ? 'resigned' : 'active',
      email: `${loginId}@neoine.test`,
      createdAt: env.at(createdAgo, 9),
      createdById: loginId === 'root' ? null : 'u-root',
      lastLoginAt: loginAgo === null ? null : env.at(loginAgo, 9),
      resignedAt: resigned ? env.at(15, 18) : null,
      resignReason: resigned ? '개인 사정으로 퇴사' : null,
    }
  })
}
