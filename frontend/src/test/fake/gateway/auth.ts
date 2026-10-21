import type { AuthGateway, SetupGateway } from '../../../gateway/types'
import type { DirectorySettingsInput, Me } from '../../../shared/model/types'
import { conflict, forbidden, unauthorized, validation } from '../errors'
import { takeId, type UserRecord } from '../store'
import { read, requireUser, setSession, write, type MockContext } from './context'
import { checkDirectoryInput, checkStorageWritable, saveDirectoryRecord, validateStoragePath } from './settings'

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

const ADMIN_EXISTS_FOR_SETUP = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'
const setupState = (ctx: MockContext) => ctx.store.data.setup

export function createAuthGateway(ctx: MockContext): AuthGateway {
  const users = () => ctx.store.data.users
  return {
    me: () => read(ctx, () => meOf(requireUser(ctx))),
    login: (loginId, password) =>
      write(ctx, () => {
        if (loginId.trim() === '' || password === '') throw validation('아이디와 비밀번호를 입력하세요.')
        const matches = users().filter((u) => u.loginId === loginId.trim())
        const active = matches.find((u) => u.status === 'active')
        if (active) return signIn(ctx, active)
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
        const { directoryDone, storageDone, adminDone } = setupState(ctx)
        return { quickLogin: true, needsSetup: !(directoryDone && storageDone && adminDone) }
      }),
  }
}

export function createSetupGateway(ctx: MockContext): SetupGateway {
  const setup = () => ctx.store.data.setup
  const users = () => ctx.store.data.users
  return {
    status: () => read(ctx, () => ({ ...setup() })),
    saveDirectory: (input: DirectorySettingsInput) =>
      write(ctx, () => {
        checkDirectoryInput(input)
        saveDirectoryRecord(ctx, input, null)
        setup().directoryDone = true
      }),
    saveStorage: (path) =>
      write(ctx, () => {
        if (setup().adminDone) throw conflict(ADMIN_EXISTS_FOR_SETUP)
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
    registerAdmin: (loginId, password) =>
      write(ctx, () => {
        if (!setup().storageDone) throw conflict('파일 저장 위치를 먼저 설정하세요.')
        if (setup().adminDone) throw conflict('이미 관리자가 등록되어 있습니다.')
        if (loginId.trim() === '' || password === '') throw validation('아이디와 비밀번호를 입력하세요.')
        const id = loginId.trim()
        let user = users().find((u) => u.loginId === id && u.status === 'active')
        if (user) {
          user.role = 'admin'
        } else {
          const now = ctx.clock.now()
          user = {
            id: takeId(ctx.store.data.counters, 'u'),
            loginId: id,
            name: id,
            role: 'admin',
            status: 'active',
            email: null,
            createdAt: now,
            createdById: null,
            lastLoginAt: null,
            resignedAt: null,
            resignReason: null,
          }
          users().push(user)
        }
        setup().adminDone = true
        return signIn(ctx, user)
      }),
  }
}
