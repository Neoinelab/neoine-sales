// @vitest-environment node
// 업로드 본문(multipart)을 실제 바이트로 확인하려면 브라우저 File·FormData와 undici Request가 같은 구현이어야 한다.
// jsdom의 File은 undici Request에서 빈 "blob"으로 직렬화되므로 이 파일만 node 환경에서 돌린다(client.ts가 읽는 window.location만 흉내 낸다).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { USER_ID } from '../../test/fake/seed/ids'

vi.hoisted(() => {
  Object.assign(globalThis, { window: { location: { origin: 'http://localhost:5173' } } })
})

import { createAttachmentsHttp } from './attachments'
import { json, noContent, problem, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const CODE = '20261017-A001'

const ATTACHMENT = {
  id: 7,
  deal_code: CODE,
  file_name: '견적서.pdf',
  description: '2차 견적',
  size: 4,
  mime: 'application/pdf',
  uploaded_by: userRefBody(USER_ID.kim, '김영업', false, 'sales'),
  uploaded_at: '2026-10-17T09:30:00+09:00',
}

const MAPPED = {
  id: 7,
  dealCode: CODE,
  fileName: '견적서.pdf',
  description: '2차 견적',
  size: 4,
  mime: 'application/pdf',
  uploadedBy: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
  uploadedAt: '2026-10-17T09:30:00+09:00',
}

/** 보낸 요청(Request)을 그대로 모으고 준비한 응답을 순서대로 돌려준다. 본문은 테스트가 필요할 때 읽는다. */
function stubRequests(...replies: Response[]): { calls: Request[] } {
  const calls: Request[] = []
  const queue = [...replies]
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      calls.push(request.clone())
      const next = queue.shift()
      if (!next) throw new Error('예상하지 못한 추가 요청')
      return next
    }),
  )
  return { calls }
}

const pathOf = (request: Request): string => {
  const url = new URL(request.url)
  return url.pathname + url.search
}

function pdf(name = '견적서.pdf', bytes: number[] = [1, 2, 3, 250], type = 'application/pdf'): File {
  return new File([new Uint8Array(bytes)], name, { type })
}

async function sentForm(request: Request): Promise<FormData> {
  return request.formData()
}

describe('attachments.list over HTTP', () => {
  it('reads the deal attachments and maps each item', async () => {
    const { calls } = stubRequests(json({ items: [ATTACHMENT] }))

    const list = await createAttachmentsHttp().list(CODE)

    expect(calls[0]?.method).toBe('GET')
    expect(pathOf(calls[0] as Request)).toBe(`/api/v1/deals/${CODE}/attachments`)
    expect(list).toEqual([MAPPED])
  })

  it('keeps the order the server sent (newest first)', async () => {
    stubRequests(json({ items: [{ ...ATTACHMENT, id: 20 }, { ...ATTACHMENT, id: 10 }] }))

    const list = await createAttachmentsHttp().list(CODE)

    expect(list.map((a) => a.id)).toEqual([20, 10])
  })

  it('returns an empty list when the deal has no files', async () => {
    stubRequests(json({ items: [] }))

    await expect(createAttachmentsHttp().list(CODE)).resolves.toEqual([])
  })

  it('shows the server message when the deal does not exist', async () => {
    stubRequests(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    await expect(createAttachmentsHttp().list(CODE)).rejects.toMatchObject({
      status: 404,
      kind: 'not-found',
      message: 'Deal을 찾을 수 없습니다.',
    })
  })

  it('reports an unreachable server as a network error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    await expect(createAttachmentsHttp().list(CODE)).rejects.toMatchObject({ status: 0 })
  })
})

describe('attachments.upload over HTTP', () => {
  it('posts multipart form data with the file bytes, its name, description and on_exists', async () => {
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '2차 견적', onExists: 'ask' })

    const request = calls[0] as Request
    expect(request.method).toBe('POST')
    expect(pathOf(request)).toBe(`/api/v1/deals/${CODE}/attachments`)
    expect(request.headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/)
    expect(request.headers.get('x-requested-with')).toBe('neoine-web')
    const form = await sentForm(request)
    const sent = form.get('file') as File
    expect(sent.name).toBe('견적서.pdf')
    expect(Array.from(new Uint8Array(await sent.arrayBuffer()))).toEqual([1, 2, 3, 250])
    expect(form.get('description')).toBe('2차 견적')
    expect(form.get('on_exists')).toBe('ask')
  })

  it('sends the description untouched so the server decides on trimming', async () => {
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '  앞뒤 공백  ', onExists: 'ask' })

    expect((await sentForm(calls[0] as Request)).get('description')).toBe('  앞뒤 공백  ')
  })

  it('sends an empty description as an empty field, not as a missing one', async () => {
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })

    const form = await sentForm(calls[0] as Request)
    expect(form.has('description')).toBe(true)
    expect(form.get('description')).toBe('')
  })

  it('sends a zero byte file as a file part', async () => {
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: { ...ATTACHMENT, size: 0 } }, 201))

    await createAttachmentsHttp().upload(CODE, { file: pdf('빈 파일.txt', [], 'text/plain'), description: '', onExists: 'ask' })

    const sent = (await sentForm(calls[0] as Request)).get('file') as File
    expect(sent.name).toBe('빈 파일.txt')
    expect(sent.size).toBe(0)
  })

  it.each(['ask', 'replace', 'skip'] as const)('sends on_exists=%s', async (onExists) => {
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists })

    expect((await sentForm(calls[0] as Request)).get('on_exists')).toBe(onExists)
  })

  it('maps 201 to outcome uploaded with the mapped attachment', async () => {
    stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201, { Location: '/api/v1/attachments/7' }))

    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })

    expect(result).toEqual({ outcome: 'uploaded', attachment: MAPPED })
  })

  it('maps 200 replaced to outcome replaced with the mapped attachment', async () => {
    stubRequests(json({ outcome: 'replaced', attachment: ATTACHMENT }))

    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'replace' })

    expect(result).toEqual({ outcome: 'replaced', attachment: MAPPED })
  })

  it('maps 200 skipped to outcome skipped without any attachment', async () => {
    stubRequests(json({ outcome: 'skipped', attachment: null }))

    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'skip' })

    expect(result).toEqual({ outcome: 'skipped' })
  })

  it.each(['uploaded', 'replaced'])('treats outcome %s without an attachment as a malformed response', async (outcome) => {
    stubRequests(json({ outcome, attachment: null }, outcome === 'uploaded' ? 201 : 200))

    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 502,
      kind: 'malformed-response',
    })
  })

  it('keeps the file-exists kind and the server message for the replace or skip choice', async () => {
    stubRequests(problem(409, 'file-exists', '같은 이름의 파일이 이미 있습니다: 견적서.pdf'))

    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 409,
      kind: 'file-exists',
      message: '같은 이름의 파일이 이미 있습니다: 견적서.pdf',
    })
  })

  it('keeps the storage-unavailable kind and message on 503', async () => {
    stubRequests(
      problem(503, 'storage-unavailable', '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'),
    )

    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 503,
      kind: 'storage-unavailable',
      message: '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.',
    })
  })

  it.each([
    [403, 'forbidden', 'forbidden', '본인이 올린 파일만 교체할 수 있습니다.'],
    [403, 'forbidden', 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)'],
    [404, 'not-found', 'not-found', 'Deal을 찾을 수 없습니다.'],
    [422, 'invalid-value', 'validation', '업로드할 파일을 선택하세요.'],
    [422, 'invalid-value', 'validation', '설명은 100자 이내로 입력하세요.'],
    [422, 'invalid-value', 'validation', '파일 크기가 100MB를 초과합니다. (최대 100MB)'],
    [422, 'invalid-value', 'validation', '실행·설치 파일(.exe)은 업로드할 수 없습니다.'],
    [422, 'invalid-value', 'validation', '사용할 수 없는 파일 이름입니다.'],
    [422, 'request-validation', 'validation', '요청 형식이 올바르지 않습니다'],
  ])('shows the server message for %s %s (kind %s): %s', async (status, serverKind, kind, detail) => {
    stubRequests(problem(status, serverKind, detail))

    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })
})

describe('attachments.remove over HTTP', () => {
  it('deletes the attachment by id and resolves with nothing on 204', async () => {
    const { calls } = stubRequests(noContent())

    await expect(createAttachmentsHttp().remove(7)).resolves.toBeUndefined()

    expect(calls[0]?.method).toBe('DELETE')
    expect(pathOf(calls[0] as Request)).toBe('/api/v1/attachments/7')
  })

  it.each([
    [403, 'forbidden', '본인이 올린 파일만 삭제할 수 있습니다.'],
    [403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)'],
    [404, 'not-found', '첨부 파일을 찾을 수 없습니다.'],
  ])('shows the server message for %s %s: %s', async (status, kind, detail) => {
    stubRequests(problem(status, kind, detail))

    await expect(createAttachmentsHttp().remove(7)).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('attachments.download over HTTP', () => {
  const header = `attachment; filename="___.pdf"; filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C.pdf`

  function binary(headers: Record<string, string>): Response {
    return new Response(new Uint8Array([0, 1, 2, 255, 128]), {
      status: 200,
      headers: { 'Content-Type': 'application/octet-stream', ...headers },
    })
  }

  it('gets the bytes as a blob and names the file from the UTF-8 Content-Disposition', async () => {
    const { calls } = stubRequests(binary({ 'Content-Disposition': header }))

    const file = await createAttachmentsHttp().download(7)

    expect(calls[0]?.method).toBe('GET')
    expect(pathOf(calls[0] as Request)).toBe('/api/v1/attachments/7/download')
    expect(file.fileName).toBe('견적서.pdf')
    expect(file.blob).toBeInstanceOf(Blob)
    expect(Array.from(new Uint8Array(await file.blob.arrayBuffer()))).toEqual([0, 1, 2, 255, 128])
  })

  it('uses the plain filename when there is no filename*', async () => {
    stubRequests(binary({ 'Content-Disposition': 'attachment; filename="report.pdf"' }))

    await expect(createAttachmentsHttp().download(7)).resolves.toMatchObject({ fileName: 'report.pdf' })
  })

  it('names the file download when the server sent no Content-Disposition', async () => {
    stubRequests(binary({}))

    await expect(createAttachmentsHttp().download(7)).resolves.toMatchObject({ fileName: 'download' })
  })

  it('downloads a zero byte file as an empty blob', async () => {
    stubRequests(new Response(new Uint8Array([]), { status: 200, headers: { 'Content-Disposition': header } }))

    const file = await createAttachmentsHttp().download(7)

    expect(file.blob.size).toBe(0)
  })

  it.each([
    [404, 'not-found', '첨부 파일을 찾을 수 없습니다.'],
    [404, 'not-found', '첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요.'],
    [503, 'storage-unavailable', '파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.'],
  ])('shows the problem message for %s %s even though success is binary: %s', async (status, kind, detail) => {
    stubRequests(problem(status, kind, detail))

    await expect(createAttachmentsHttp().download(7)).rejects.toMatchObject({ status, kind, message: detail })
  })
})
