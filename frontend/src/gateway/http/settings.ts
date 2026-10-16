import { api } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import type { SettingsGateway } from '../types'
import { toDirectoryRequest, toDirectorySettings } from './mappers/settings'
import { unwrap } from './request'
import { notImplemented } from './unsupported'

const FAILED_TYPE = 'https://sales.neoine.test/problems/directory-verification-failed'

export function createSettingsHttp(): SettingsGateway {
  return {
    // 아직 등록되지 않은 설정(404)은 오류가 아니라 "없음"이다.
    getDirectory: async () => {
      try {
        return toDirectorySettings(await unwrap(api.GET('/api/v1/settings/directory')))
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    saveDirectory: async (input, auth) =>
      toDirectorySettings(
        await unwrap(
          api.PUT('/api/v1/settings/directory', {
            body: { ...toDirectoryRequest(input), password: auth.password, expected_revision: auth.expectedRevision },
          }),
        ),
      ),
    // 서버는 검증 실패도 200 { success: false }로 줄 수 있다. 화면이 한 가지 경로(오류)로 다루도록 422로 바꾼다.
    testDirectory: async (input, password) => {
      const result = await unwrap(
        api.POST('/api/v1/settings/directory/test', { body: { ...toDirectoryRequest(input), password } }),
      )
      if (result.success) return
      throw new ApiError(422, {
        type: FAILED_TYPE,
        title: 'Directory Verification Failed',
        status: 422,
        detail: result.message,
        ...(result.stage ? { stage: result.stage } : {}),
      })
    },
    getStorage: () => Promise.resolve(null),
    saveStorage: notImplemented,
    testStorage: notImplemented,
  }
}
