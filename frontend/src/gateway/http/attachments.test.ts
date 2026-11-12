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
  // 테스트 코드: AT-053
  it('Deal 첨부 목록을 읽어 각 항목을 바꾼다', async () => {
    // given: 첨부 한 건을 담은 목록 응답
    const { calls } = stubRequests(json({ items: [ATTACHMENT] }))

    // when: 목록을 읽는다
    const list = await createAttachmentsHttp().list(CODE)

    // then: GET 요청이 목록 경로로 가고 항목이 camelCase 첨부로 바뀐다
    expect(calls[0]?.method).toBe('GET')
    expect(pathOf(calls[0] as Request)).toBe(`/api/v1/deals/${CODE}/attachments`)
    expect(list).toEqual([MAPPED])
  })

  // 테스트 코드: AT-053
  it('서버가 보낸 순서(최신 순)를 유지한다', async () => {
    // given: id 20, 10 순서의 목록 응답
    stubRequests(json({ items: [{ ...ATTACHMENT, id: 20 }, { ...ATTACHMENT, id: 10 }] }))

    // when: 목록을 읽는다
    const list = await createAttachmentsHttp().list(CODE)

    // then: 서버 순서 그대로다
    expect(list.map((a) => a.id)).toEqual([20, 10])
  })

  // 테스트 코드: AT-053
  it('첨부가 없으면 빈 목록을 돌려준다', async () => {
    // given: 빈 items 응답
    stubRequests(json({ items: [] }))

    // when·then: 목록을 읽으면 빈 배열이다
    await expect(createAttachmentsHttp().list(CODE)).resolves.toEqual([])
  })

  // 테스트 코드: AT-053
  it('없는 Deal이면 서버 문구를 보인다', async () => {
    // given: 404 "Deal을 찾을 수 없습니다." 응답
    stubRequests(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 목록을 읽으면 404 not-found와 서버 문구의 오류다
    await expect(createAttachmentsHttp().list(CODE)).rejects.toMatchObject({
      status: 404,
      kind: 'not-found',
      message: 'Deal을 찾을 수 없습니다.',
    })
  })

  // 테스트 코드: AT-053
  it('서버에 닿지 않으면 네트워크 오류로 알린다', async () => {
    // given: fetch가 연결 실패(TypeError)를 내는 환경
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    // when·then: 목록을 읽으면 status 0의 오류다
    await expect(createAttachmentsHttp().list(CODE)).rejects.toMatchObject({ status: 0 })
  })
})

describe('attachments.upload over HTTP', () => {
  // 테스트 코드: AT-053
  it('파일 바이트·이름·설명·on_exists를 multipart로 보낸다', async () => {
    // given: 201 응답을 준비하고 PDF 파일을 고른다
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    // when: 업로드한다
    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '2차 견적', onExists: 'ask' })

    // then: POST 요청이 multipart이고 CSRF 헤더가 있다
    const request = calls[0] as Request
    expect(request.method).toBe('POST')
    expect(pathOf(request)).toBe(`/api/v1/deals/${CODE}/attachments`)
    expect(request.headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/)
    expect(request.headers.get('x-requested-with')).toBe('neoine-web')
    // then: 파일의 바이트·원래 이름과 설명·on_exists가 폼에 실린다
    const form = await sentForm(request)
    const sent = form.get('file') as File
    expect(sent.name).toBe('견적서.pdf')
    expect(Array.from(new Uint8Array(await sent.arrayBuffer()))).toEqual([1, 2, 3, 250])
    expect(form.get('description')).toBe('2차 견적')
    expect(form.get('on_exists')).toBe('ask')
  })

  // 테스트 코드: AT-053
  it('설명은 가공 없이 보내 공백 제거는 서버가 정한다', async () => {
    // given: 201 응답을 준비한다
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    // when: 앞뒤 공백이 든 설명으로 업로드한다
    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '  앞뒤 공백  ', onExists: 'ask' })

    // then: 보낸 설명이 공백 그대로다
    expect((await sentForm(calls[0] as Request)).get('description')).toBe('  앞뒤 공백  ')
  })

  // 테스트 코드: AT-053
  it('빈 설명은 빠뜨리지 않고 빈 필드로 보낸다', async () => {
    // given: 201 응답을 준비한다
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    // when: 설명 없이 업로드한다
    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })

    // then: description 필드가 있고 값이 ''이다
    const form = await sentForm(calls[0] as Request)
    expect(form.has('description')).toBe(true)
    expect(form.get('description')).toBe('')
  })

  // 테스트 코드: AT-053
  it('0바이트 파일도 파일 파트로 보낸다', async () => {
    // given: 0바이트 첨부를 돌려주는 201 응답
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: { ...ATTACHMENT, size: 0 } }, 201))

    // when: 0바이트 파일을 업로드한다
    await createAttachmentsHttp().upload(CODE, { file: pdf('빈 파일.txt', [], 'text/plain'), description: '', onExists: 'ask' })

    // then: 파일 파트의 이름이 원래 이름이고 크기가 0이다
    const sent = (await sentForm(calls[0] as Request)).get('file') as File
    expect(sent.name).toBe('빈 파일.txt')
    expect(sent.size).toBe(0)
  })

  // 테스트 코드: AT-053
  it.each(['ask', 'replace', 'skip'] as const)('on_exists=%s를 보낸다', async (onExists) => {
    // given: 201 응답을 준비한다
    const { calls } = stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201))

    // when: on_exists를 지정해 업로드한다
    await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists })

    // then: 폼의 on_exists가 지정한 값이다
    expect((await sentForm(calls[0] as Request)).get('on_exists')).toBe(onExists)
  })

  // 테스트 코드: AT-053
  it('201은 uploaded와 바뀐 첨부로 옮긴다', async () => {
    // given: Location이 있는 201 uploaded 응답
    stubRequests(json({ outcome: 'uploaded', attachment: ATTACHMENT }, 201, { Location: '/api/v1/attachments/7' }))

    // when: 업로드한다
    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })

    // then: 결과가 uploaded와 camelCase 첨부다
    expect(result).toEqual({ outcome: 'uploaded', attachment: MAPPED })
  })

  // 테스트 코드: AT-053
  it('200 replaced는 replaced와 바뀐 첨부로 옮긴다', async () => {
    // given: 200 replaced 응답
    stubRequests(json({ outcome: 'replaced', attachment: ATTACHMENT }))

    // when: replace로 업로드한다
    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'replace' })

    // then: 결과가 replaced와 camelCase 첨부다
    expect(result).toEqual({ outcome: 'replaced', attachment: MAPPED })
  })

  // 테스트 코드: AT-053
  it('200 skipped는 첨부 없는 skipped로 옮긴다', async () => {
    // given: 200 skipped 응답
    stubRequests(json({ outcome: 'skipped', attachment: null }))

    // when: skip으로 업로드한다
    const result = await createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'skip' })

    // then: 결과가 첨부 없는 skipped다
    expect(result).toEqual({ outcome: 'skipped' })
  })

  // 테스트 코드: AT-053
  it.each(['uploaded', 'replaced'])('첨부 없는 %s 응답은 잘못된 응답으로 본다', async (outcome) => {
    // given: 첨부가 null인 uploaded 또는 replaced 응답
    stubRequests(json({ outcome, attachment: null }, outcome === 'uploaded' ? 201 : 200))

    // when·then: 업로드하면 502 malformed-response 오류다
    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 502,
      kind: 'malformed-response',
    })
  })

  // 테스트 코드: AT-053
  it('file-exists 종류와 서버 문구를 유지한다', async () => {
    // given: 409 file-exists 응답
    stubRequests(problem(409, 'file-exists', '같은 이름의 파일이 이미 있습니다: 견적서.pdf'))

    // when·then: 업로드하면 409 file-exists와 서버 문구의 오류다
    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 409,
      kind: 'file-exists',
      message: '같은 이름의 파일이 이미 있습니다: 견적서.pdf',
    })
  })

  // 테스트 코드: AT-053
  it('503이면 storage-unavailable 종류와 문구를 유지한다', async () => {
    // given: 503 storage-unavailable 응답
    stubRequests(
      problem(503, 'storage-unavailable', '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'),
    )

    // when·then: 업로드하면 503 storage-unavailable과 서버 문구의 오류다
    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status: 503,
      kind: 'storage-unavailable',
      message: '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.',
    })
  })

  // 테스트 코드: AT-053
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
  ])('업로드 오류 %s %s는 서버 문구를 그대로 보인다(종류 %s): %s', async (status, serverKind, kind, detail) => {
    // given: 서버가 보낸 문제 응답
    stubRequests(problem(status, serverKind, detail))

    // when·then: 업로드하면 상태·종류·서버 문구가 그대로 담긴 오류다
    await expect(createAttachmentsHttp().upload(CODE, { file: pdf(), description: '', onExists: 'ask' })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })
})

describe('attachments.remove over HTTP', () => {
  // 테스트 코드: AT-053
  it('id로 삭제하고 204면 값 없이 끝난다', async () => {
    // given: 204 응답
    const { calls } = stubRequests(noContent())

    // when·then: 삭제하면 값 없이 끝난다
    await expect(createAttachmentsHttp().remove(7)).resolves.toBeUndefined()

    // then: DELETE 요청이 첨부 경로로 갔다
    expect(calls[0]?.method).toBe('DELETE')
    expect(pathOf(calls[0] as Request)).toBe('/api/v1/attachments/7')
  })

  // 테스트 코드: AT-053
  it.each([
    [403, 'forbidden', '본인이 올린 파일만 삭제할 수 있습니다.'],
    [403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)'],
    [404, 'not-found', '첨부 파일을 찾을 수 없습니다.'],
  ])('삭제 오류 %s %s는 서버 문구를 그대로 보인다: %s', async (status, kind, detail) => {
    // given: 서버가 보낸 문제 응답
    stubRequests(problem(status, kind, detail))

    // when·then: 삭제하면 상태·종류·서버 문구가 담긴 오류다
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

  // 테스트 코드: AT-053
  it('blob으로 받고 UTF-8 Content-Disposition에서 이름을 얻는다', async () => {
    // given: 바이너리 본문과 UTF-8 Content-Disposition 응답
    const { calls } = stubRequests(binary({ 'Content-Disposition': header }))

    // when: 내려받는다
    const file = await createAttachmentsHttp().download(7)

    // then: GET 요청이 다운로드 경로로 가고 이름이 한글이며 blob 바이트가 그대로다
    expect(calls[0]?.method).toBe('GET')
    expect(pathOf(calls[0] as Request)).toBe('/api/v1/attachments/7/download')
    expect(file.fileName).toBe('견적서.pdf')
    expect(file.blob).toBeInstanceOf(Blob)
    expect(Array.from(new Uint8Array(await file.blob.arrayBuffer()))).toEqual([0, 1, 2, 255, 128])
  })

  // 테스트 코드: AT-053
  it('filename*가 없으면 일반 filename을 쓴다', async () => {
    // given: filename만 있는 응답
    stubRequests(binary({ 'Content-Disposition': 'attachment; filename="report.pdf"' }))

    // when·then: 내려받으면 그 이름이다
    await expect(createAttachmentsHttp().download(7)).resolves.toMatchObject({ fileName: 'report.pdf' })
  })

  // 테스트 코드: AT-053
  it('Content-Disposition이 없으면 "download"로 이름 짓는다', async () => {
    // given: Content-Disposition 없는 응답
    stubRequests(binary({}))

    // when·then: 내려받으면 이름이 "download"다
    await expect(createAttachmentsHttp().download(7)).resolves.toMatchObject({ fileName: 'download' })
  })

  // 테스트 코드: AT-053
  it('0바이트 파일은 빈 blob으로 받는다', async () => {
    // given: 빈 본문 응답
    stubRequests(new Response(new Uint8Array([]), { status: 200, headers: { 'Content-Disposition': header } }))

    // when: 내려받는다
    const file = await createAttachmentsHttp().download(7)

    // then: blob 크기가 0이다
    expect(file.blob.size).toBe(0)
  })

  // 테스트 코드: AT-053
  it.each([
    [404, 'not-found', '첨부 파일을 찾을 수 없습니다.'],
    [404, 'not-found', '첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요.'],
    [503, 'storage-unavailable', '파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.'],
  ])('성공이 바이너리여도 오류 %s %s는 문제 문구를 보인다: %s', async (status, kind, detail) => {
    // given: 서버가 보낸 문제 응답
    stubRequests(problem(status, kind, detail))

    // when·then: 내려받으면 상태·종류·서버 문구가 담긴 오류다
    await expect(createAttachmentsHttp().download(7)).rejects.toMatchObject({ status, kind, message: detail })
  })
})
