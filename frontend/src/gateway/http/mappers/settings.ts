import type { Schemas } from '../../../shared/api/client'
import type { DirectorySettings, DirectorySettingsInput, StorageSettings } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toDirectoryRequest(input: DirectorySettingsInput): Schemas['DirectorySettingsRequest'] {
  return {
    server_urls: input.serverUrls,
    use_starttls: input.useStarttls,
    ca_cert_pem: input.caCertPem,
    bind_template: input.bindTemplate,
    base_dn: input.baseDn,
    user_filter: input.userFilter,
    display_name_attribute: input.displayNameAttribute,
    email_attribute: input.emailAttribute,
    connect_timeout_seconds: input.connectTimeoutSeconds,
    receive_timeout_seconds: input.receiveTimeoutSeconds,
  }
}

export function toDirectorySettings(row: Schemas['DirectorySettingsResponse']): DirectorySettings {
  return {
    serverUrls: row.server_urls,
    useStarttls: row.use_starttls,
    caCertPem: row.ca_cert_pem,
    bindTemplate: row.bind_template,
    baseDn: row.base_dn,
    userFilter: row.user_filter,
    displayNameAttribute: row.display_name_attribute,
    emailAttribute: row.email_attribute,
    connectTimeoutSeconds: row.connect_timeout_seconds,
    receiveTimeoutSeconds: row.receive_timeout_seconds,
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
