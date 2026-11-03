import { api } from '../../shared/api/client'
import type { AuthGateway } from '../types'
import { toMe } from './mappers/user'
import { unwrap, unwrapVoid } from './request'

export function createAuthHttp(): AuthGateway {
  return {
    me: async () => toMe(await unwrap(api.GET('/api/v1/auth/me'))),
    // 로그인 응답이 곧 로그인한 사용자다(쿠키는 이 응답이 심는다). AD 경고 키가 없으면 경고 없음이다.
    login: async (loginId, password) => {
      const response = await unwrap(api.POST('/api/v1/auth/login', { body: { login_id: loginId, password } }))
      const warning = response.directory_warning
      return { me: toMe(response), directoryWarning: warning ? { stage: warning.stage, message: warning.message } : null }
    },
    logout: () => unwrapVoid(api.POST('/api/v1/auth/logout')),
    config: async () => {
      const config = await unwrap(api.GET('/api/v1/auth/config'))
      return {
        authMode: config.auth_mode ?? null,
        needsSetup: config.needs_directory_setup || config.needs_storage_setup || config.needs_admin_setup,
      }
    },
  }
}
