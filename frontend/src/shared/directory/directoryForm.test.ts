import { describe, expect, it } from 'vitest'
import { changeSecurity, DEFAULT_DIRECTORY_FORM, formFromDirectory, inputFromForm, validateForm } from './directoryForm'
import { DIRECTORY_SAVED } from '../../test/directoryFixtures'

describe('AD 접속 정보와 테스트 계정 분리', () => {
  it('loads saved endpoints without restoring an account or a password', () => {
    const values = formFromDirectory(DIRECTORY_SAVED)
    expect(inputFromForm(values)).toEqual({
      host: DIRECTORY_SAVED.host, port: 636, security: 'ssl',
      userFilter: DIRECTORY_SAVED.userFilter, connectTimeoutSeconds: 5,
    })
  })
  it.each(['none', 'starttls', 'ssl'] as const)('chooses the default port for %s and preserves custom ports', (mode) => {
    expect(changeSecurity(DEFAULT_DIRECTORY_FORM, mode).port).toBe(mode === 'ssl' ? '636' : '389')
    expect(changeSecurity({ ...DEFAULT_DIRECTORY_FORM, port: '3269' }, mode).port).toBe('3269')
  })
  it.each([
    { host: '' }, { port: '' }, { port: '0' }, { port: '65536' },
    { userFilter: '' }, { connectTimeoutSeconds: '0' }, { connectTimeoutSeconds: '31' },
  ])('rejects invalid endpoint values %j', (change) => {
    expect(validateForm({ ...formFromDirectory(DIRECTORY_SAVED), ...change })).not.toBeNull()
  })
  it('does not require credentials on the settings form', () => {
    expect(validateForm(formFromDirectory(DIRECTORY_SAVED))).toBeNull()
  })
})
