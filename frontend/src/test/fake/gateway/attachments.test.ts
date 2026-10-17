import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, fakeFile, mockAs, TEST_NOW } from '../testing'

const MB = 1024 * 1024
const STORAGE_MSG = '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'

describe('attachments.list / download', () => {
  it('모든 역할이 조회하고 최신 업로드순이다', async () => {
    const { gateway } = await mockAs('han')
    const list = await gateway.attachments.list(dealCode(1))
    expect(list.map((a) => a.fileName)).toEqual(expect.arrayContaining(['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']))
    const times = list.map((a) => Date.parse(a.uploadedAt))
    expect(times).toEqual([...times].sort((a, b) => b - a))
    expect(list.find((a) => a.fileName === '기술검토.xlsx')?.uploadedBy).toMatchObject({ name: '강퇴사', status: 'resigned' })
    expect(list.find((a) => a.fileName === '견적서_한빛은행_v2.pdf')?.size).toBe(2_400_000)
  })

  it('다운로드는 파일명과 Blob을 돌려준다', async () => {
    const { gateway } = await mockAs('han')
    const first = (await gateway.attachments.list(dealCode(1)))[0]
    if (!first) throw new Error('none')
    const file = await gateway.attachments.download(first.id)
    expect(file.fileName).toBe(first.fileName)
    expect(file.blob).toBeInstanceOf(Blob)
    await expectApiError(gateway.attachments.download('att-none'), 404)
  })
})

describe('attachments.upload (T-FILE)', () => {
  it('user는 403', async () => {
    const { gateway } = await mockAs('han')
    await expectApiError(gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' }), 403)
  })

  it('규칙 위반은 422 문구(차단 확장자·100MB·설명 100자)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await expectApiError(
      gateway.attachments.upload(code, { file: fakeFile('setup.EXE'), description: '', onExists: 'ask' }),
      422,
      '실행·설치 파일(.exe)은 업로드할 수 없습니다.',
    )
    await expectApiError(
      gateway.attachments.upload(code, { file: fakeFile('big.bin', 100 * MB + 1), description: '', onExists: 'ask' }),
      422,
      '파일 크기가 100MB를 초과합니다. (최대 100MB)',
    )
    await expectApiError(
      gateway.attachments.upload(code, { file: fakeFile('a.pdf'), description: 'x'.repeat(101), onExists: 'ask' }),
      422,
      '설명은 100자 이내로 입력하세요.',
    )
    expect(await gateway.attachments.list(code)).toHaveLength(0)
  })

  it('경계값 100MB·설명 100자·a.tar.gz는 허용한다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const a = await gateway.attachments.upload(code, { file: fakeFile('big.bin', 100 * MB), description: 'x'.repeat(100), onExists: 'ask' })
    expect(a.outcome).toBe('uploaded')
    const b = await gateway.attachments.upload(code, { file: fakeFile('backup.tar.gz', 10), description: '', onExists: 'ask' })
    expect(b.outcome).toBe('uploaded')
  })

  it('업로드하면 목록·History·Deal 갱신 시각이 바뀐다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const result = await gateway.attachments.upload(code, { file: fakeFile('제안서.pdf', 1234), description: '1차 제안', onExists: 'ask' })
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment).toMatchObject({ fileName: '제안서.pdf', size: 1234, description: '1차 제안', uploadedBy: { id: 'u-kim' }, uploadedAt: TEST_NOW })
    expect(await gateway.attachments.list(code)).toHaveLength(1)
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', target: '첨부 파일', after: '업로드 제안서.pdf' })
    expect((await gateway.deals.get(code)).updatedAt).toBe(TEST_NOW)
  })

  it('같은 이름은 ask면 409(file-exists), replace는 교체, skip은 변화 없음', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const upload = (onExists: 'ask' | 'replace' | 'skip', size = 77) =>
      gateway.attachments.upload(code, { file: fakeFile('견적서_한빛은행_v2.pdf', size), description: '새 설명', onExists })
    const countBefore = (await gateway.attachments.list(code)).length
    const historyBefore = (await gateway.history.list(code, {})).length
    const error = await expectApiError(upload('ask'), 409, '같은 이름의 파일이 이미 있습니다: 견적서_한빛은행_v2.pdf')
    expect(error.kind).toBe('file-exists')
    expect(await upload('skip')).toEqual({ outcome: 'skipped' })
    expect((await gateway.attachments.list(code)).length).toBe(countBefore)
    expect((await gateway.history.list(code, {})).length).toBe(historyBefore)
    const replaced = await upload('replace', 99)
    expect(replaced.outcome).toBe('replaced')
    const list = await gateway.attachments.list(code)
    expect(list).toHaveLength(countBefore)
    expect(list.find((a) => a.fileName === '견적서_한빛은행_v2.pdf')).toMatchObject({ size: 99, description: '새 설명', uploadedBy: { id: 'u-kim' } })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', after: '교체 견적서_한빛은행_v2.pdf' })
  })

  it('저장소 장애 시뮬레이션이 켜져 있으면 503(storage-unavailable)이고 아무것도 저장되지 않는다', async () => {
    const mock = await mockAs('kim')
    mock.control.setStorageFailure(true)
    const error = await expectApiError(
      mock.gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' }),
      503,
      STORAGE_MSG,
    )
    expect(error.kind).toBe('storage-unavailable')
    expect(await mock.gateway.attachments.list(dealCode(2))).toHaveLength(0)
    mock.control.setStorageFailure(false)
    const ok = await mock.gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' })
    expect(ok.outcome).toBe('uploaded')
  })
})

describe('attachments.remove (FL-03 삭제 권한)', () => {
  const findId = async (gw: Awaited<ReturnType<typeof mockAs>>['gateway'], name: string) => {
    const found = (await gw.attachments.list(dealCode(1))).find((a) => a.fileName === name)
    if (!found) throw new Error(name)
    return found.id
  }

  it('본인 파일 O, 타인(재직) 파일 X, 퇴사 sales 파일 O, user X, admin 전체 O', async () => {
    const kim = await mockAs('kim')
    await expectApiError(kim.gateway.attachments.remove(await findId(kim.gateway, '제안서_ITDR.pptx')), 403, '본인이 올린 파일만 삭제할 수 있습니다.')
    await kim.gateway.attachments.remove(await findId(kim.gateway, '견적서_한빛은행_v2.pdf'))
    await kim.gateway.attachments.remove(await findId(kim.gateway, '기술검토.xlsx'))
    expect((await kim.gateway.attachments.list(dealCode(1))).map((a) => a.fileName)).toEqual(['제안서_ITDR.pptx'])

    const han = await mockAs('han')
    await expectApiError(han.gateway.attachments.remove(await findId(han.gateway, '기술검토.xlsx')), 403)

    const root = await mockAs('root')
    await root.gateway.attachments.remove(await findId(root.gateway, '제안서_ITDR.pptx'))
    expect(await root.gateway.attachments.list(dealCode(1))).toHaveLength(2)
  })

  it('삭제는 History에 남고 없는 id는 404', async () => {
    const { gateway } = await mockAs('kim')
    const id = await findId(gateway, '견적서_한빛은행_v2.pdf')
    await gateway.attachments.remove(id)
    expect((await gateway.history.list(dealCode(1), {}))[0]).toMatchObject({ category: 'attachment', after: '삭제 견적서_한빛은행_v2.pdf' })
    await expectApiError(gateway.attachments.remove(id), 404)
  })
})

type MockGateway = Awaited<ReturnType<typeof mockAs>>['gateway']
type UploadOptions = { description?: string; onExists?: 'ask' | 'replace' | 'skip'; size?: number }

const put = (gateway: MockGateway, code: string, name: string, options: UploadOptions = {}) =>
  gateway.attachments.upload(code, {
    file: fakeFile(name, options.size ?? 10),
    description: options.description ?? '',
    onExists: options.onExists ?? 'ask',
  })

const OWNER_ONLY_FRAGMENT = '본인이 올린 파일만'

describe('attachments.upload: 설명 규칙 (AC-08, 서버와 같은 경계)', () => {
  it('trims the description before saving it', async () => {
    const { gateway } = await mockAs('kim')
    const result = await put(gateway, dealCode(2), 'a.pdf', { description: '  견적  최종 \n' })
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment.description).toBe('견적  최종')
    expect((await gateway.attachments.list(dealCode(2)))[0]?.description).toBe('견적  최종')
  })

  it('accepts a 100 code point description padded with spaces and rejects 101', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    expect((await put(gateway, code, 'a.pdf', { description: `  ${'가'.repeat(100)}  ` })).outcome).toBe('uploaded')
    await expectApiError(put(gateway, code, 'b.pdf', { description: '가'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
  })

  it('counts an emoji as one character', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    expect((await put(gateway, code, 'a.pdf', { description: '😀'.repeat(100) })).outcome).toBe('uploaded')
    await expectApiError(put(gateway, code, 'b.pdf', { description: '😀'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
  })
})

describe('attachments.upload: 파일 이름 규칙 (AC-08, 12.2-3)', () => {
  it.each(['a/b.pdf', 'a\\b.pdf', '..', 'a\tb.pdf', '견적\u202egpj.pdf', 'x\u2066y.pdf'])('rejects the name %j with the server message and saves nothing', async (name) => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await expectApiError(put(gateway, code, name), 422, '사용할 수 없는 파일 이름입니다.')
    expect(await gateway.attachments.list(code)).toHaveLength(0)
    expect((await gateway.history.list(code, {})).some((h) => h.category === 'attachment')).toBe(false)
  })

  it.each(['\ufeffa.pdf', 'a\u200bb.pdf', 'a.pdf\u200d', 'setup.exe\u200b', 'a\u00adb.pdf', '\u{1F468}\u200d\u{1F469}.png'])(
    'rejects the format character in %j with the server message and saves nothing',
    async (name) => {
      const { gateway } = await mockAs('kim')
      const code = dealCode(2)
      await expectApiError(put(gateway, code, name), 422, '사용할 수 없는 파일 이름입니다.')
      expect(await gateway.attachments.list(code)).toHaveLength(0)
    },
  )

  it('still refuses setup.exe followed by a BOM and saves nothing', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await expectApiError(put(gateway, code, 'setup.exe\ufeff'), 422)
    expect(await gateway.attachments.list(code)).toHaveLength(0)
  })

  it('accepts a 255 code point name and rejects 256', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    expect((await put(gateway, code, 'a'.repeat(255))).outcome).toBe('uploaded')
    await expectApiError(put(gateway, code, 'a'.repeat(256)), 422, '사용할 수 없는 파일 이름입니다.')
  })

  it('blocks an executable whose name ends with spaces or dots', async () => {
    const { gateway } = await mockAs('kim')
    for (const name of ['setup.exe ', 'setup.exe.', 'setup.exe\u3000', 'setup.EXE . ']) {
      await expectApiError(put(gateway, dealCode(2), name), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
    }
  })

  it.each(['vbs', 'vbe', 'wsf', 'wsh', 'hta', 'cpl', 'msp', 'mst', 'apk', 'appimage', 'run'])('blocks the added extension .%s', async (ext) => {
    const { gateway } = await mockAs('kim')
    await expectApiError(put(gateway, dealCode(2), `tool.${ext}`), 422, `실행·설치 파일(.${ext})은 업로드할 수 없습니다.`)
  })

  it('answers in the server order: read-only 403, then unknown deal 404, then the rule errors', async () => {
    const han = await mockAs('han')
    await expectApiError(put(han.gateway, dealCode(2), 'a/b.pdf'), 403)
    const kim = await mockAs('kim')
    await expectApiError(put(kim.gateway, '20000101-ZZZZ', 'a/b.pdf'), 404, 'Deal을 찾을 수 없습니다.')
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe', { description: 'x'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe', { size: 100 * MB + 1 }), 422, '파일 크기가 100MB를 초과합니다. (최대 100MB)')
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe'), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
  })

  it('judges the storage failure after the rule errors and before the same-name check', async () => {
    const mock = await mockAs('kim')
    mock.control.setStorageFailure(true)
    await expectApiError(put(mock.gateway, dealCode(2), 'a/b.pdf'), 422, '사용할 수 없는 파일 이름입니다.')
    await expectApiError(put(mock.gateway, dealCode(1), '견적서_한빛은행_v2.pdf'), 503)
  })
})

describe('attachments.upload: NFC 이름 (12.2-3)', () => {
  const NFD = '한글.pdf'.normalize('NFD')
  const NFC = '한글.pdf'.normalize('NFC')

  it('stores and shows the name in NFC and records it in the history', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const result = await put(gateway, code, NFD)
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment.fileName).toBe(NFC)
    expect(result.attachment.fileName).not.toBe(NFD)
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ after: `업로드 ${NFC}` })
    expect((await gateway.attachments.download(result.attachment.id)).fileName).toBe(NFC)
  })

  it('treats the NFD and NFC spellings as the same name (409 with the NFC name)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await put(gateway, code, NFC)
    const error = await expectApiError(put(gateway, code, NFD), 409, `같은 이름의 파일이 이미 있습니다: ${NFC}`)
    expect(error.kind).toBe('file-exists')
    expect(await put(gateway, code, NFD, { onExists: 'skip' })).toEqual({ outcome: 'skipped' })
    expect((await put(gateway, code, NFD, { onExists: 'replace' })).outcome).toBe('replaced')
    expect(await gateway.attachments.list(code)).toHaveLength(1)
  })

  it('keeps names that differ only by case as different files', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await put(gateway, code, 'Report.pdf')
    expect((await put(gateway, code, 'report.pdf')).outcome).toBe('uploaded')
    expect(await gateway.attachments.list(code)).toHaveLength(2)
  })
})

describe('attachments.upload: 교체 권한 = 삭제 권한 (AC-10, AC-11, Q2)', () => {
  it('lets the uploader replace her own file: same id, new uploader data and one history row', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = (await gateway.attachments.list(code)).find((a) => a.fileName === '견적서_한빛은행_v2.pdf')
    const result = await put(gateway, code, '견적서_한빛은행_v2.pdf', { onExists: 'replace', size: 55, description: '교체본' })
    if (result.outcome !== 'replaced') throw new Error('expected replaced')
    expect(result.attachment).toMatchObject({ id: before?.id, size: 55, description: '교체본', uploadedBy: { id: 'u-kim' }, uploadedAt: TEST_NOW })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', after: '교체 견적서_한빛은행_v2.pdf' })
    expect((await gateway.deals.get(code)).updatedAt).toBe(TEST_NOW)
  })

  it('refuses another active sales with 403 and changes nothing', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const listBefore = await gateway.attachments.list(code)
    const historyBefore = await gateway.history.list(code, {})
    const updatedBefore = (await gateway.deals.get(code)).updatedAt

    const error = await expectApiError(put(gateway, code, '제안서_ITDR.pptx', { onExists: 'replace', size: 1, description: '덮어쓰기' }), 403, '본인이 올린 파일만 교체할 수 있습니다.')

    expect(error.kind).toBe('forbidden')
    expect(await gateway.attachments.list(code)).toEqual(listBefore)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
    expect((await gateway.deals.get(code)).updatedAt).toBe(updatedBefore)
  })

  it('lets any sales replace the file of a resigned sales and makes her the uploader', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const result = await put(gateway, code, '기술검토.xlsx', { onExists: 'replace' })
    if (result.outcome !== 'replaced') throw new Error('expected replaced')
    expect(result.attachment.uploadedBy).toMatchObject({ id: 'u-kim', name: '김영업' })
  })

  it('lets admin replace every file', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    for (const name of ['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']) {
      expect((await put(gateway, code, name, { onExists: 'replace' })).outcome).toBe('replaced')
    }
    expect(await gateway.attachments.list(code)).toHaveLength(3)
  })

  it('checks the permission only for replace: ask still answers 409 and skip still skips', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    await expectApiError(put(gateway, code, '제안서_ITDR.pptx', { onExists: 'ask' }), 409)
    expect(await put(gateway, code, '제안서_ITDR.pptx', { onExists: 'skip' })).toEqual({ outcome: 'skipped' })
  })

  it('uploads a new file for replace and skip when the name does not exist yet', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    expect((await put(gateway, code, 'a.pdf', { onExists: 'replace' })).outcome).toBe('uploaded')
    expect((await put(gateway, code, 'b.pdf', { onExists: 'skip' })).outcome).toBe('uploaded')
  })

  it('rejects a read-only user before anything else', async () => {
    const { gateway } = await mockAs('han')
    const error = await expectApiError(put(gateway, dealCode(1), '견적서_한빛은행_v2.pdf', { onExists: 'replace' }), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
  })
})

describe('attachments.remove: 판정 순서 (AC-14)', () => {
  it('answers a read-only user 403 even for an unknown id (not 404)', async () => {
    const { gateway } = await mockAs('han')
    const error = await expectApiError(gateway.attachments.remove('att-none'), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
  })

  it('answers a read-only user 403 before the permission message for an existing file', async () => {
    const { gateway } = await mockAs('han')
    const id = (await gateway.attachments.list(dealCode(1)))[0]?.id ?? ''
    const error = await expectApiError(gateway.attachments.remove(id), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
    expect(await gateway.attachments.list(dealCode(1))).toHaveLength(3)
  })

  it('answers an unknown id 404 for sales and admin before any permission check', async () => {
    for (const key of ['kim', 'root'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.attachments.remove('att-none'), 404, '첨부 파일을 찾을 수 없습니다.')
    }
  })

  it('answers 403 with the delete message for another sales file and keeps it', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const id = (await gateway.attachments.list(code)).find((a) => a.fileName === '제안서_ITDR.pptx')?.id ?? ''
    await expectApiError(gateway.attachments.remove(id), 403, '본인이 올린 파일만 삭제할 수 있습니다.')
    expect(await gateway.attachments.list(code)).toHaveLength(3)
  })
})
