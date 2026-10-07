import { describe, expect, it } from 'vitest'
import { ApiError, call, errorMessage } from './problem'

const res = (status: number) => new Response(null, { status })

describe('call', () => {
  it('returns the data of a successful response', async () => {
    const data = await call(Promise.resolve({ data: { id: '1' }, response: res(200) }))

    expect(data).toEqual({ id: '1' })
  })

  it('throws an ApiError carrying the problem document', async () => {
    const error = {
      type: 'https://x/problems/invalid-state',
      title: 't',
      status: 409,
      detail: '진행 중인 Deal이 있는 고객은 삭제할 수 없습니다',
    }

    const failure = call(Promise.resolve({ error, response: res(409) }))

    await expect(failure).rejects.toMatchObject({ status: 409, kind: 'invalid-state' })
    await expect(failure).rejects.toThrow('진행 중인 Deal')
  })

  it('lists field errors of a request validation problem without the body prefix', () => {
    const error = new ApiError(422, {
      type: 'https://x/problems/request-validation',
      title: 't',
      status: 422,
      detail: '요청 형식이 올바르지 않습니다',
      errors: [{ loc: ['body', 'company_name'], msg: 'Field required' }],
    })

    expect(error.message).toBe('요청 형식이 올바르지 않습니다 — company_name: Field required')
  })

  it('falls back to a generic message when the body is not a problem document', async () => {
    const failure = call(Promise.resolve({ error: 'oops', response: res(502) }))

    await expect(failure).rejects.toThrow('요청에 실패했습니다 (502)')
  })
})

describe('errorMessage', () => {
  it('hides unexpected error details', () => {
    expect(errorMessage(new TypeError('Failed to fetch'))).toContain('네트워크 오류')
  })
})
