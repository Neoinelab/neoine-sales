import type { Schemas } from '../../../shared/api/client'
import type { Me, MyProfile, ProfileChange, User, UserRef } from '../../../shared/model/types'

export function toMe(principal: Schemas['PrincipalResponse']): Me {
  return { id: principal.user_id, loginId: principal.subject, name: principal.name, role: principal.role }
}

/** 서버 UserRef의 role을 그대로 사용한다. */
export function toUserRef(ref: Schemas['UserRef']): UserRef {
  return { id: ref.id, name: ref.name, role: ref.role, status: ref.resigned ? 'resigned' : 'active' }
}

/** 퇴사 사유 표기(서버는 enum 값만 준다). */
const RESIGN_REASONS: Readonly<Record<string, string>> = { resigned: '퇴사' }

export function toUser(row: Schemas['UserResponse']): User {
  return {
    id: row.id,
    loginId: row.login_id,
    name: row.display_name ?? row.login_id,
    role: row.role,
    status: row.status,
    email: row.email,
    phone: row.phone,
    createdAt: row.created_at,
    createdBy: toUserRef(row.created_by),
    lastLoginAt: row.last_login_at,
    resignedAt: row.deleted_at,
    resignReason: row.delete_reason === null ? null : (RESIGN_REASONS[row.delete_reason] ?? row.delete_reason),
  }
}

/** 준 키만 PATCH 본문에 싣는다(null은 비움). 아이디·역할은 보내지 않는다. */
export function toProfileBody(change: ProfileChange): { display_name?: string; email?: string | null; phone?: string | null } {
  return {
    ...(change.name !== undefined ? { display_name: change.name } : {}),
    ...(change.email !== undefined ? { email: change.email } : {}),
    ...(change.phone !== undefined ? { phone: change.phone } : {}),
  }
}

export function toMyProfile(row: Schemas['MyProfileResponse']): MyProfile {
  return {
    id: row.id,
    loginId: row.login_id,
    role: row.role,
    name: row.display_name ?? row.login_id,
    email: row.email,
    phone: row.phone,
    authMode: row.auth_mode,
    editable: {
      name: row.editable.display_name,
      email: row.editable.email,
      phone: row.editable.phone,
      password: row.editable.password,
    },
  }
}
