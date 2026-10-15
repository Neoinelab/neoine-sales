/** 설정·최초 설정 모델(A-0 계약). `types.ts`가 재export한다. */

import type { UserRef } from './types'

export interface DirectorySettings {
  serverUrls: string[]
  useStarttls: boolean
  caCertPem: string | null
  bindTemplate: string
  baseDn: string
  userFilter: string
  displayNameAttribute: string
  emailAttribute: string
  connectTimeoutSeconds: number
  receiveTimeoutSeconds: number
  revision: number
  updatedAt: string
  updatedBy: UserRef | null
}

export interface StorageSettings {
  /** 절대 경로. */
  path: string
  updatedAt: string
  updatedBy: UserRef | null
}

export interface SetupState {
  directoryDone: boolean
  storageDone: boolean
  adminDone: boolean
}
