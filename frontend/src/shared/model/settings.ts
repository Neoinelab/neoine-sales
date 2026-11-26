/** 설정·최초 설정 모델(A-0 계약). `types.ts`가 재export한다. */

import type { AuthMode, Me, UserRef } from './types'

/** 보안 연결 방식: 없음(평문)·SSL(LDAPS)·StartTLS. */
export type DirectorySecurity = 'none' | 'ssl' | 'starttls'

/** 저장된 AD 설정. 바인드 비밀번호는 어떤 형태로도 없고, Base DN은 서버가 AD에서 찾은 읽기 전용 값이다. */
export interface DirectorySettings {
  host: string
  port: number
  security: DirectorySecurity
  userFilter: string
  connectTimeoutSeconds: number
  baseDn: string
  revision: number
  updatedAt: string
  updatedBy: UserRef | null
}

/** AD가 답하지 못해 대체 로그인으로 넘어간 이유(서버 `DirectoryWarningStage`와 같은 값). */
export type DirectoryWarningStage =
  | 'not_configured'
  | 'connect'
  | 'tls'
  | 'service_bind'
  | 'base_dn'
  | 'search'
  | 'credential_unreadable'
  | 'unknown'

/** 대체 로그인(AD 대신 저장된 비밀번호)을 한 admin에게 오는 AD 경고. */
export interface DirectoryWarning {
  stage: DirectoryWarningStage
  message: string
}

/** 로그인 결과: 사용자와, 있으면 AD 경고. */
export interface LoginResult {
  me: Me
  directoryWarning: DirectoryWarning | null
}

export interface StorageSettings {
  /** 절대 경로. */
  path: string
  updatedAt: string
  updatedBy: UserRef | null
}

export interface SetupState {
  /** 고른 인증 방식(아직 안 골랐으면 null). local이면 AD 단계가 없으므로 directoryDone이 true다. */
  authMode?: AuthMode | null
  directoryDone: boolean
  storageDone: boolean
  adminDone: boolean
}
