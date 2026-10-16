import { afterEach, describe, expect, it, vi } from 'vitest'
import { gatewayMode } from './mode'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('gatewayMode', () => {
  it('is mock by default', () => {
    vi.stubEnv('VITE_GATEWAY', '')
    expect(gatewayMode()).toBe('mock')
  })

  it('is http only for the exact value http', () => {
    vi.stubEnv('VITE_GATEWAY', 'http')
    expect(gatewayMode()).toBe('http')
    vi.stubEnv('VITE_GATEWAY', 'HTTP')
    expect(gatewayMode()).toBe('mock')
    vi.stubEnv('VITE_GATEWAY', 'mock')
    expect(gatewayMode()).toBe('mock')
  })
})

describe('gateway selection', () => {
  it('uses the in-memory mock in mock mode', async () => {
    vi.stubEnv('VITE_GATEWAY', 'mock')
    vi.resetModules()
    const { gateway } = await import('./index')
    const { defaultMock } = await import('../mock/default')

    expect(gateway).toBe(defaultMock.gateway)
  })

  it('uses the HTTP gateway in http mode, where unbuilt domains answer 501', async () => {
    vi.stubEnv('VITE_GATEWAY', 'http')
    vi.resetModules()
    const { gateway } = await import('./index')
    const { defaultMock } = await import('../mock/default')

    expect(gateway).not.toBe(defaultMock.gateway)
    await expect(gateway.attachments.list('20261016-A001')).rejects.toMatchObject({
      status: 501,
      message: '아직 실제 서버와 연결되지 않은 기능입니다.',
    })
  })
})
