import type { Schemas } from '../../../shared/api/client'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../../../shared/model/types'
import { toUserRef } from './user'

/** 저장과 테스트가 공통으로 보내는 접속 정보 다섯 개. */
export function toDirectoryRequest(input: DirectorySettingsInput) {
  return {
    host: input.host,
    port: input.port,
    security: input.security,
    user_filter: input.userFilter,
    connect_timeout_seconds: input.connectTimeoutSeconds,
  }
}

export function toDirectorySettings(row: Schemas['DirectorySettingsResponse']): DirectorySettings {
  return {
    host: row.host,
    port: row.port,
    security: row.security,
    userFilter: row.user_filter,
    connectTimeoutSeconds: row.connect_timeout_seconds,
    baseDn: row.base_dn,
    revision: row.revision,
    updatedAt: row.updated_at,
    updatedBy: row.updated_by === null ? null : toUserRef(row.updated_by),
  }
}

export function toStorageSettings(row: Schemas['StorageSettingsResponse']): StorageSettings {
  return {
    path: row.path,
    updatedAt: row.updated_at,
    updatedBy: row.updated_by === null ? null : toUserRef(row.updated_by),
  }
}
