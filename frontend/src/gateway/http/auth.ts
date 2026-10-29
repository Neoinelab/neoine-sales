import { api } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import { QUICK_LOGIN_USERS } from '../../shared/model/constants'
import type { AuthGateway } from '../types'
import { toMe } from './mappers/user'
import { unwrap, unwrapVoid } from './request'

const UNKNOWN_QUICK_LOGIN = '빠른 로그인 사용자를 찾을 수 없습니다.'

export function createAuthHttp(): AuthGateway {
  return {
    me: async () => toMe(await unwrap(api.GET('/api/v1/auth/me'))),
    // 로그인 응답이 곧 로그인한 사용자다(쿠키는 이 응답이 심는다). AD 경고 키가 없으면 경고 없음이다.
    login: async (loginId, password) => {
      const response = await unwrap(api.POST('/api/v1/auth/login', { body: { login_id: loginId, password } }))
      const warning = response.directory_warning
      return { me: toMe(response), directoryWarning: warning ? { stage: warning.stage, message: warning.message } : null }
    },
    quickLogin: async (userId) => {
      const quick = QUICK_LOGIN_USERS.find((u) => u.userId === userId)
      if (!quick) {
        throw new ApiError(401, {
          type: 'https://sales.neoine.test/problems/unauthorized',
          title: 'Unauthorized',
          status: 401,
          detail: UNKNOWN_QUICK_LOGIN,
        })
      }
      return toMe(await unwrap(api.POST('/api/v1/auth/dev-login', { body: { role: quick.role } })))
    },
    logout: () => unwrapVoid(api.POST('/api/v1/auth/logout')),
    config: async () => {
      const config = await unwrap(api.GET('/api/v1/auth/config'))
      return {
        quickLogin: config.dev_login,
        needsSetup: config.needs_directory_setup || config.needs_storage_setup || config.needs_admin_setup,
      }
    },
  }
}
