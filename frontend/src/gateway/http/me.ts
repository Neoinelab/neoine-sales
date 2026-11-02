import { api } from '../../shared/api/client'
import type { MeGateway } from '../types'
import { toMyProfile, toProfileBody } from './mappers/user'
import { unwrap, unwrapVoid } from './request'

/** 내 정보: 로그인한 사용자 자신의 프로필과 비밀번호(local 모드). 비밀번호는 응답에 없고 요청에만 싣는다. */
export function createMeHttp(): MeGateway {
  return {
    profile: async () => toMyProfile(await unwrap(api.GET('/api/v1/me/profile'))),
    updateProfile: async (change) => toMyProfile(await unwrap(api.PATCH('/api/v1/me/profile', { body: toProfileBody(change) }))),
    changePassword: (current, next) =>
      unwrapVoid(api.PUT('/api/v1/me/password', { body: { current_password: current, new_password: next } })),
  }
}
