import type { AuthGateway, SetupGateway } from '../../../gateway/types'
import type { DirectorySettingsInput, LoginResult, Me } from '../../../shared/model/types'
import { conflict, unauthorized, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import {
  checkLoginIdAllowed,
  isRetiredLoginId,
  checkPassword,
  cleanEmail,
  cleanName,
  cleanPhone,
  modeOf,
  passwordOf,
  setPasswordOf,
} from './accountRules'
import { read, requireUser, setSession, write, type MockContext } from './context'
import { checkBindPassword, checkDirectoryInput, checkDirectoryReachable, saveDirectoryRecord, validateStoragePath } from './settings'

/** 최초 설정 연결 테스트가 찾아 주는 Base DN(Fake). */
export const SETUP_FAKE_BASE_DN = 'dc=found,dc=test'
const LOGIN_FAILED = '아이디 또는 비밀번호가 올바르지 않습니다'

function meOf(user: UserRecord): Me {
  return { id: user.id, loginId: user.loginId, name: user.name, role: user.role }
}

function signIn(ctx: MockContext, user: UserRecord): Me {
  if (user.status === 'resigned') throw unauthorized(LOGIN_FAILED)
  user.lastLoginAt = ctx.clock.now()
  setSession(ctx, user.id)
  return meOf(user)
}

/** AD 설정 1단계가 끝나지 않은 상태에서 admin이 로그인하면 서버처럼 not_configured 경고를 싣는다. */
function loginResult(ctx: MockContext, me: Me, user: UserRecord): LoginResult {
  const unconfigured = user.role === 'admin' && !ctx.store.data.setup.directoryDone
  return {
    me,
    directoryWarning: unconfigured
      ? { stage: 'not_configured', message: 'AD 서버가 아직 설정되지 않아 이전에 로그인한 비밀번호로 로그인했습니다. 외부연동 설정에서 AD를 등록하세요.' }
      : null,
  }
}

const AUTH_MODE_FIRST = '먼저 인증 방식을 고르세요.'
const ADMIN_EXISTS_FOR_SETUP = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'
const SETUP_LOGIN_FAILED = '아이디 또는 비밀번호가 올바르지 않습니다'
const AD_PROFILE_FORBIDDEN = 'AD 연동에서는 이름·이메일·전화번호를 입력하지 않습니다(AD 값을 씁니다).'
const LOGIN_ID_FORMAT = /^[a-z0-9][a-z0-9._-]{0,63}$/
const setupState = (ctx: MockContext) => ctx.store.data.setup

export function createAuthGateway(ctx: MockContext): AuthGateway {
  const users = () => ctx.store.data.users
  return {
    me: () => read(ctx, () => meOf(requireUser(ctx))),
    login: (loginId, password): Promise<LoginResult> =>
      write(ctx, () => {
        // 서버처럼 빈 칸·예약 아이디·없는 아이디·퇴사자·틀린 비밀번호가 모두 같은 401 문구다(AD에 묻기 전 판정 포함).
        const id = loginId.trim()
        if (id === '' || password.trim() === '' || isRetiredLoginId(loginId)) throw unauthorized(LOGIN_FAILED)
        const account = users().find((u) => u.loginId === id && u.status === 'active')
        // AD 모드의 비밀번호 판정은 서버에서는 AD가 하지만, Fake는 같은 저장 비밀번호(없으면 시드 비밀번호)와 비교한다.
        if (!account || password !== passwordOf(ctx.store.data, account.id)) throw unauthorized(LOGIN_FAILED)
        if (modeOf(ctx) === 'local') return { me: signIn(ctx, account), directoryWarning: null }
        return loginResult(ctx, signIn(ctx, account), account)
      }),
    logout: () =>
      write(ctx, () => {
        setSession(ctx, null)
      }),
    // 서버처럼 AD 서버·파일 저장 위치·첫 관리자 중 하나라도 없으면 최초 설정이 필요하다.
    config: () =>
      read(ctx, () => {
        const { directoryDone, storageDone, adminDone, authMode } = setupState(ctx)
        return { authMode, needsSetup: !(directoryDone && storageDone && adminDone) }
      }),
  }
}

export function createSetupGateway(ctx: MockContext): SetupGateway {
  const setup = () => ctx.store.data.setup
  const users = () => ctx.store.data.users
  return {
    status: () => read(ctx, () => ({ ...setup() })),
    chooseAuthMode: (mode) =>
      write(ctx, () => {
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        if (mode !== 'ad' && mode !== 'local') throw validation('인증 방식은 ad 또는 local이어야 합니다.')
        setup().authMode = mode
        // local이면 AD 단계가 없다. AD이면 AD 서버가 이미 등록돼 있을 때만 그 단계가 끝난 것이다.
        setup().directoryDone = mode === 'local' || ctx.store.data.directory !== null
      }),
    saveDirectory: (input: DirectorySettingsInput) =>
      write(ctx, () => {
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        checkDirectoryInput(input)
        checkBindPassword(input, null)
        checkDirectoryReachable(input)
        saveDirectoryRecord(ctx, input, null)
        setup().authMode = 'ad'
        setup().directoryDone = true
      }),
    // 연결 테스트(SU-R20): 저장 없이 값 검사 → 닫힘 → 연결 확인. 실패는 게이트웨이가 바꾼 모양(422 확인 실패)으로 던진다.
    testDirectory: (input: DirectorySettingsInput) =>
      write(ctx, () => {
        checkDirectoryInput(input)
        checkBindPassword(input, null)
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        checkDirectoryReachable(input)
        return { baseDn: SETUP_FAKE_BASE_DN }
      }),
    saveStorage: (path) =>
      write(ctx, () => {
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        if (setup().authMode === null) throw conflict(AUTH_MODE_FIRST)
        if (!setup().directoryDone) throw conflict('먼저 AD 서버를 등록하세요')
        const normalized = validateStoragePath(path)
        ctx.store.data.storage = { path: normalized, updatedAt: ctx.clock.now(), updatedById: null }
        setup().storageDone = true
      }),
    testStorage: (path) =>
      write(ctx, () => {
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        validateStoragePath(path) // 서버는 경로 규칙·쓰기 확인만 하고 저장소 장애 503은 내지 않는다(SU-R8)
      }),
    registerAdmin: (loginId, password, profile) =>
      write(ctx, () => {
        // 서버 판정 순서(SU-R10 local / SU-R11 AD)를 따른다. Fake에 없는 단계(AD 인증·시도 제한·해시·방식 재확인)는 생략한다.
        // local: 비밀번호 빈칸 → 아이디 형식 → 예약 아이디 → 비밀번호 정책 → 이름 → 닫힘 → 저장 위치 → 중복
        // AD: 비밀번호 빈칸 401 → 프로필 입력 422 → 아이디 형식 401 → 예약 아이디 → 닫힘 → 저장 위치 → 중복
        const id = loginId.trim().toLowerCase()
        const local = setup().authMode === 'local'
        if (password.trim() === '') {
          if (local) throw validation('비밀번호는 비어 있을 수 없습니다')
          throw unauthorized(SETUP_LOGIN_FAILED) // AD 방식은 로그인 실패와 같은 문구(AD로 보내지 않음)
        }
        if (!local && profile) throw validation(AD_PROFILE_FORBIDDEN)
        if (!LOGIN_ID_FORMAT.test(id)) {
          if (!local) throw unauthorized(SETUP_LOGIN_FAILED)
          throw validation('로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다')
        }
        checkLoginIdAllowed(id)
        if (local) checkPassword(password, id)
        if (local && (profile?.name ?? '').trim() === '') throw validation('이름은(는) 비어 있을 수 없습니다')
        const fields = local
          ? { name: cleanName(profile?.name ?? ''), email: cleanEmail(profile?.email), phone: cleanPhone(profile?.phone) }
          : { name: id, email: null, phone: null }
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
        if (!setup().storageDone) throw conflict('파일 저장 위치를 먼저 설정하세요.')
        // 서버처럼 같은 아이디의 재직 사용자는 어느 방식에서도 admin으로 올리지 않고 거절한다(SU-R9).
        if (users().some((u) => u.loginId === id && u.status === 'active')) throw conflict(`이미 존재하는 사용자입니다: ${id}`)
        const now = ctx.clock.now()
        const user: UserRecord = {
          id: takeId(ctx.store.data.counters, 'u'),
          loginId: id,
          ...fields,
          role: 'admin',
          status: 'active',
          createdAt: now,
          lastLoginAt: null,
          resignedAt: null,
        }
        users().push(user)
        if (local) setPasswordOf(ctx.store.data, user.id, password)
        setup().adminDone = true
        return signIn(ctx, user)
      }),
  }
}
