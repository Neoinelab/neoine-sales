import { api } from '../../shared/api/client'
import type { SetupGateway } from '../types'
import { toDirectoryRequest } from './mappers/settings'
import { toMe } from './mappers/user'
import { unwrap, unwrapVoid } from './request'

export function createSetupHttp(): SetupGateway {
  return {
    // 서버는 AD·저장 위치가 모두 있을 때만 needs_admin_setup=true를 준다. 앞 단계가 남았으면 관리자 단계도 끝난 것이 아니다.
    status: async () => {
      const config = await unwrap(api.GET('/api/v1/auth/config'))
      return {
        authMode: config.auth_mode ?? null,
        directoryDone: !config.needs_directory_setup,
        storageDone: !config.needs_storage_setup,
        adminDone: !(config.needs_directory_setup || config.needs_storage_setup || config.needs_admin_setup),
      }
    },
    saveDirectory: async (input) => {
      await unwrap(api.PUT('/api/v1/auth/setup/directory', { body: { ...toDirectoryRequest(input), bind_password: input.bindPassword ?? '' } }))
    },
    chooseAuthMode: (mode) => unwrapVoid(api.PUT('/api/v1/auth/setup/auth-mode', { body: { mode } })),
    saveStorage: (path) => unwrapVoid(api.PUT('/api/v1/auth/setup/storage', { body: { path } })),
    testStorage: (path) => unwrapVoid(api.POST('/api/v1/auth/setup/storage/test', { body: { path } })),
    // 프로필은 local 모드에서만 온다. 빈 이메일·전화는 키를 보내지 않는다.
    registerAdmin: async (loginId, password, profile) =>
      toMe(
        await unwrap(
          api.POST('/api/v1/auth/setup', {
            body: {
              login_id: loginId,
              password,
              ...(profile
                ? {
                    display_name: profile.name,
                    ...(profile.email ? { email: profile.email } : {}),
                    ...(profile.phone ? { phone: profile.phone } : {}),
                  }
                : {}),
            },
          }),
        ),
      ),
  }
}
