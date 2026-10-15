import { describe, expect, it } from 'vitest'
import type { DirectorySettings } from '../model/types'
import { DEFAULT_DIRECTORY_FORM, formFromDirectory, inputFromForm } from './directoryForm'

const SAVED: DirectorySettings = {
  serverUrls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
  useStarttls: true,
  caCertPem: null,
  bindTemplate: 'CORP\\{login_id}',
  baseDn: 'dc=corp,dc=test',
  userFilter: '(sAMAccountName={login_id})',
  displayNameAttribute: 'displayName',
  emailAttribute: 'mail',
  connectTimeoutSeconds: 7,
  receiveTimeoutSeconds: 12,
  revision: 3,
  updatedAt: '2026-10-15T09:00:00+09:00',
  updatedBy: null,
}

describe('formFromDirectory', () => {
  it('joins server URLs one per line and turns numbers and a missing CA certificate into input text', () => {
    expect(formFromDirectory(SAVED)).toEqual({
      serverUrls: 'ldaps://dc1.corp.test\nldaps://dc2.corp.test',
      useStarttls: true,
      caCertPem: '',
      bindTemplate: 'CORP\\{login_id}',
      baseDn: 'dc=corp,dc=test',
      userFilter: '(sAMAccountName={login_id})',
      displayNameAttribute: 'displayName',
      emailAttribute: 'mail',
      connectTimeoutSeconds: '7',
      receiveTimeoutSeconds: '12',
    })
  })
})

describe('inputFromForm', () => {
  it('trims server URL lines, drops blank lines, sends an empty CA certificate as null and parses numbers', () => {
    const input = inputFromForm({
      ...DEFAULT_DIRECTORY_FORM,
      serverUrls: ' ldaps://a.test \n\n  \nldaps://b.test\n',
      caCertPem: '   ',
      connectTimeoutSeconds: '8',
      receiveTimeoutSeconds: '15',
    })
    expect(input.serverUrls).toEqual(['ldaps://a.test', 'ldaps://b.test'])
    expect(input.caCertPem).toBeNull()
    expect(input.connectTimeoutSeconds).toBe(8)
    expect(input.receiveTimeoutSeconds).toBe(15)
  })

  it('keeps a pasted CA certificate as it is', () => {
    const pem = '-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----'
    expect(inputFromForm({ ...DEFAULT_DIRECTORY_FORM, caCertPem: pem }).caCertPem).toBe(pem)
  })

  it('round-trips a saved setting through the form', () => {
    const input = inputFromForm(formFromDirectory(SAVED))
    expect(input).toEqual({
      serverUrls: SAVED.serverUrls,
      useStarttls: SAVED.useStarttls,
      caCertPem: null,
      bindTemplate: SAVED.bindTemplate,
      baseDn: SAVED.baseDn,
      userFilter: SAVED.userFilter,
      displayNameAttribute: SAVED.displayNameAttribute,
      emailAttribute: SAVED.emailAttribute,
      connectTimeoutSeconds: SAVED.connectTimeoutSeconds,
      receiveTimeoutSeconds: SAVED.receiveTimeoutSeconds,
    })
  })
})
