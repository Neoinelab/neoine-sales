import type { Schemas } from '../../../shared/api/client'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../../../shared/model/types'
import { toUserRef } from './user'

/** 설정 저장·연결 테스트 본문의 접속 정보 7개. `bindPassword`가 null이면 키를 아예 보내지 않아 저장된 값을 유지한다. */
export function toDirectoryRequest(
  input: DirectorySettingsInput,
): Omit<Schemas['DirectorySettingsRequest'], 'bind_password'> & { bind_password?: string } {
  return {
    host: input.host,
    port: input.port,
    security: input.security,
    bind_account: input.bindAccount,
    ...(input.bindPassword === null ? {} : { bind_password: input.bindPassword }),
    user_filter: input.userFilter,
    connect_timeout_seconds: input.connectTimeoutSeconds,
  }
}

export function toDirectorySettings(row: Schemas['DirectorySettingsResponse']): DirectorySettings {
  return {
    host: row.host,
    port: row.port,
    security: row.security,
    bindAccount: row.bind_account,
    bindCredentialStatus: row.bind_credential_status,
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
