/** local 계정 관리의 검증·비밀번호 저장. 서버(`password_policy`, `User.change_profile`)와 같은 문구·판정 순서를 지킨다. */

import { EMAIL_FORMAT_MESSAGE, PHONE_FORMAT_MESSAGE, isEmail, isPhone } from '../../../shared/model/contactRules'
import type { AuthMode, ProfileChange } from '../../../shared/model/types'
import { conflict, validation } from '../errors'
import type { SeedData } from '../store'
import { SEED_PASSWORD } from '../seed/users'
import type { MockContext } from './context'

export const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다'
export const LOCAL_ONLY = '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.'
export const NAME_REQUIRED = '이름을 입력하세요.'
export const WRONG_CURRENT = '현재 비밀번호가 올바르지 않습니다.'
const PASSWORD_MIN = 8
const PASSWORD_MAX = 256

/** 지금 시스템의 로그인 방식. 아직 고르지 않았으면 AD처럼 동작한다(비밀번호를 확인하지 않는다). */
export function modeOf(ctx: MockContext): AuthMode {
  return ctx.store.data.setup.authMode ?? 'ad'
}

export function requireLocal(ctx: MockContext): void {
  if (modeOf(ctx) !== 'local') throw conflict(LOCAL_ONLY)
}

export function cleanName(text: string): string {
  const name = text.trim()
  if (name === '') throw validation(NAME_REQUIRED)
  return name
}

export function cleanEmail(text: string | null | undefined): string | null {
  const email = (text ?? '').trim().toLowerCase()
  if (email === '') return null
  if (!isEmail(email)) throw validation(EMAIL_FORMAT_MESSAGE)
  return email
}

export function cleanPhone(text: string | null | undefined): string | null {
  const phone = (text ?? '').trim()
  if (phone === '') return null
  if (!isPhone(phone)) throw validation(PHONE_FORMAT_MESSAGE)
  return phone
}

/** 서버 `DEV_LOGIN_IDS`와 같은 예약어(`dev-*`)는 계정 아이디로 쓸 수 없다. */
export function checkLoginIdAllowed(loginId: string): void {
  if (loginId.toLowerCase().startsWith('dev-')) throw validation('개발 로그인 전용 아이디(dev-*)는 사용할 수 없습니다.')
}

export function checkPassword(password: string, loginId: string): void {
  if (password.length < PASSWORD_MIN) throw validation(`비밀번호는 ${PASSWORD_MIN}자 이상이어야 합니다.`)
  if (password.length > PASSWORD_MAX) throw validation(`비밀번호는 ${PASSWORD_MAX}자 이하여야 합니다.`)
  if (password.trim().toLowerCase() === loginId.toLowerCase()) throw validation('비밀번호는 아이디와 같을 수 없습니다.')
}

export function passwordOf(data: SeedData, userId: number): string {
  return data.passwords?.[userId] ?? SEED_PASSWORD
}

export function setPasswordOf(data: SeedData, userId: number, password: string): void {
  data.passwords = { ...data.passwords, [userId]: password }
}

export interface ProfilePatch {
  name?: string
  email?: string | null
  phone?: string | null
}

/**
 * 프로필 변경을 검증해 실제로 적용할 값만 돌려준다(아무것도 바꾸지 않는다).
 * AD 모드에서 이름·이메일을 주면 409, 이름은 비울 수 없다.
 */
export function profilePatch(mode: AuthMode, change: ProfileChange): ProfilePatch {
  if (mode === 'ad' && (change.name !== undefined || change.email !== undefined)) throw conflict(AD_MANAGED)
  const patch: ProfilePatch = {}
  if (change.name !== undefined) patch.name = cleanName(change.name)
  if (change.email !== undefined) patch.email = cleanEmail(change.email)
  if (change.phone !== undefined) patch.phone = cleanPhone(change.phone)
  return patch
}
