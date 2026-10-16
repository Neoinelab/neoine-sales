import { api } from '../../shared/api/client'
import type { SetupGateway } from '../types'
import { toDirectoryRequest } from './mappers/settings'
import { toMe } from './mappers/user'
import { unwrap } from './request'
import { notImplemented } from './unsupported'

export function createSetupHttp(): SetupGateway {
  return {
    // 파일 저장 위치 단계는 P2b 전까지 서버에 없다. 완료로 보고해 화면이 건너뛰게 한다.
    status: async () => {
      const config = await unwrap(api.GET('/api/v1/auth/config'))
      return {
        directoryDone: !config.needs_directory_setup,
        storageDone: true,
        adminDone: !config.needs_admin_setup,
      }
    },
    saveDirectory: async (input) => {
      await unwrap(api.PUT('/api/v1/auth/setup/directory', { body: toDirectoryRequest(input) }))
    },
    saveStorage: notImplemented,
    testStorage: notImplemented,
    registerAdmin: async (loginId, password) =>
      toMe(await unwrap(api.POST('/api/v1/auth/setup', { body: { login_id: loginId, password } }))),
  }
}
