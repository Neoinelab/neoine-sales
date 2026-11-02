import type { AuthGateway, SetupGateway } from '../../../gateway/types'
import type { DirectorySettingsInput, LoginResult, Me } from '../../../shared/model/types'
import { conflict, forbidden, unauthorized, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import {
  checkLoginIdAllowed,
  checkPassword,
  cleanEmail,
  cleanName,
  cleanPhone,
  modeOf,
  passwordOf,
  setPasswordOf,
} from './accountRules'
import { read, requireUser, setSession, write, type MockContext } from './context'
import { checkBindPassword, checkDirectoryInput, checkDirectoryReachable, checkStorageWritable, saveDirectoryRecord, validateStoragePath } from './settings'

const LOGIN_FAILED = '아이디 또는 비밀번호가 올바르지 않습니다.'
const RESIGNED = '퇴사한 사용자는 로그인할 수 없습니다.'

function meOf(user: UserRecord): Me {
  return { id: user.id, loginId: user.loginId, name: user.name, role: user.role }
}

function signIn(ctx: MockContext, user: UserRecord): Me {
  if (user.status === 'resigned') throw forbidden(RESIGNED)
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
const setupState = (ctx: MockContext) => ctx.store.data.setup

export function createAuthGateway(ctx: MockContext): AuthGateway {
  const users = () => ctx.store.data.users
  return {
    me: () => read(ctx, () => meOf(requireUser(ctx))),
    login: (loginId, password): Promise<LoginResult> =>
      write(ctx, () => {
        if (loginId.trim() === '' || password === '') throw validation('아이디와 비밀번호를 입력하세요.')
        const matches = users().filter((u) => u.loginId === loginId.trim())
        if (modeOf(ctx) === 'local') {
          // 서버처럼 없는 아이디·퇴사자·틀린 비밀번호가 모두 같은 문구다.
          const account = matches.find((u) => u.status === 'active')
          if (!account || password !== passwordOf(ctx.store.data, account.id)) throw unauthorized(LOGIN_FAILED)
          return { me: signIn(ctx, account), directoryWarning: null }
        }
        const active = matches.find((u) => u.status === 'active')
        if (active) return loginResult(ctx, signIn(ctx, active), active)
        if (matches.length > 0) throw forbidden(RESIGNED)
        throw unauthorized(LOGIN_FAILED)
      }),
    quickLogin: (userId) =>
      write(ctx, () => {
        const user = users().find((u) => u.id === userId)
        if (!user) throw unauthorized(LOGIN_FAILED)
        return signIn(ctx, user)
      }),
    logout: () =>
      write(ctx, () => {
        setSession(ctx, null)
      }),
    // 서버처럼 AD 서버·파일 저장 위치·첫 관리자 중 하나라도 없으면 최초 설정이 필요하다.
    config: () =>
      read(ctx, () => {
        const { directoryDone, storageDone, adminDone, authMode } = setupState(ctx)
        return { quickLogin: true, authMode, needsSetup: !(directoryDone && storageDone && adminDone) }
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
        checkDirectoryInput(input)
        checkBindPassword(input, null)
        checkDirectoryReachable(input)
        saveDirectoryRecord(ctx, input, null)
        setup().authMode = 'ad'
        setup().directoryDone = true
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
        checkStorageWritable(ctx, path)
      }),
    registerAdmin: (loginId, password, profile) =>
      write(ctx, () => {
        if (!setup().storageDone) throw conflict('파일 저장 위치를 먼저 설정하세요.')
        if (setup().adminDone) throw conflict('이미 관리자가 등록되어 있습니다.')
        if (loginId.trim() === '' || password === '') throw validation('아이디와 비밀번호를 입력하세요.')
        const id = loginId.trim()
        const local = setup().authMode === 'local'
        if (!local && profile) throw validation('이름·이메일·전화번호는 앱에서 계정을 직접 관리할 때만 받습니다.')
        const fields = local
          ? { name: cleanName(profile?.name ?? ''), email: cleanEmail(profile?.email), phone: cleanPhone(profile?.phone) }
          : { name: id, email: null, phone: null }
        if (local) {
          checkLoginIdAllowed(id)
          checkPassword(password, id)
        }
        let user = users().find((u) => u.loginId === id && u.status === 'active')
        if (user && local) throw conflict('이미 사용 중인 아이디입니다.')
        if (user) {
          user.role = 'admin'
        } else {
          const now = ctx.clock.now()
          user = {
            id: takeId(ctx.store.data.counters, 'u'),
            loginId: id,
            ...fields,
            role: 'admin',
            status: 'active',
            createdAt: now,
            createdById: null,
            lastLoginAt: null,
            resignedAt: null,
            resignReason: null,
          }
          users().push(user)
          if (local) setPasswordOf(ctx.store.data, user.id, password)
        }
        setup().adminDone = true
        return signIn(ctx, user)
      }),
  }
}
