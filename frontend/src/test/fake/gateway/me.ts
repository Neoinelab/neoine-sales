import type { MeGateway } from '../../../gateway/types'
import type { MyProfile } from '../../../shared/model/types'
import type { UserRecord } from '../store'
import { validation } from '../errors'
import { WRONG_CURRENT, checkPassword, modeOf, passwordOf, profilePatch, requireLocal, setPasswordOf } from './accountRules'
import { read, requireUser, write, type MockContext } from './context'

function profileOf(ctx: MockContext, user: UserRecord): MyProfile {
  const local = modeOf(ctx) === 'local'
  return {
    id: user.id,
    loginId: user.loginId,
    role: user.role,
    name: user.name,
    email: user.email,
    phone: user.phone,
    authMode: modeOf(ctx),
    editable: { name: local, email: local, phone: true, password: local },
  }
}

/** 내 정보: 로그인한 모든 역할(읽기 전용 user 포함)이 자기 프로필·비밀번호를 고친다. */
export function createMeGateway(ctx: MockContext): MeGateway {
  return {
    profile: () => read(ctx, () => profileOf(ctx, requireUser(ctx))),
    updateProfile: (change) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        const patch = profilePatch(modeOf(ctx), change)
        Object.assign(user, patch)
        return profileOf(ctx, user)
      }),
    changePassword: (current, next) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        requireLocal(ctx)
        checkPassword(next, user.loginId)
        if (current !== passwordOf(ctx.store.data, user.id)) throw validation(WRONG_CURRENT)
        setPasswordOf(ctx.store.data, user.id, next)
      }),
  }
}
