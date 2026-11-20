import type { UserOption } from './types'

/** 서버 한도: 담당자 이름 글자는 트림 뒤 1~100자. */
export const OWNER_NAME_MAX_LENGTH = 100

/** URL owner_name → 조회에 쓸 글자. 공백뿐이거나 한도를 넘으면 무시한다. */
export function validOwnerName(raw: string | null): string | undefined {
  const text = raw?.trim()
  return text && text.length <= OWNER_NAME_MAX_LENGTH ? text : undefined
}

/** 후보·칸 표시: 재직은 `이름 (아이디)`(이름이 아이디와 같으면 아이디만), 퇴사는 `이름(퇴사)`. */
export function ownerOptionText(user: UserOption): string {
  if (user.status === 'resigned') return `${user.name}(퇴사)`
  return user.name === user.loginId ? user.loginId : `${user.name} (${user.loginId})`
}

/** 새로 고를 수 있는 후보: 재직 sales만, 화면 이름 오름차순(한국어 순), 같으면 아이디 오름차순. */
export function ownerCandidates(users: readonly UserOption[]): UserOption[] {
  return users
    .filter((u) => u.status === 'active' && u.role === 'sales')
    .sort((a, b) => a.name.localeCompare(b.name, 'ko') || a.loginId.localeCompare(b.loginId))
}

export const UNKNOWN_OWNER_TEXT = '선택한 담당자'

/** URL(owner_name 우선, 없으면 owner id)에서 칸에 보일 글자. */
export function ownerFieldText(ownerName: string | null, ownerId: string | null, users: readonly UserOption[]): string {
  // 100자를 넘는 owner_name은 조회에서 무시되므로 칸에도 쓰지 않는다(owner id가 있으면 그것을 따른다).
  const name = validOwnerName(ownerName)
  if (name !== undefined) return ownerName ?? ''
  if (!ownerId) return ''
  const found = users.find((u) => String(u.id) === ownerId)
  return found ? ownerOptionText(found) : UNKNOWN_OWNER_TEXT
}
