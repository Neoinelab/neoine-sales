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
      gateway.attachments.upload(code, { file: fakeFile('제안서_ITDR.pptx', size), description: '새 설명', onExists })
    const countBefore = (await gateway.attachments.list(code)).length
    const historyBefore = (await gateway.history.list(code, {})).length
    const error = await expectApiError(upload('ask'), 409, '같은 이름의 파일이 이미 있습니다: 제안서_ITDR.pptx')
    expect(error.kind).toBe('file-exists')
    expect(await upload('skip')).toEqual({ outcome: 'skipped' })
    expect((await gateway.attachments.list(code)).length).toBe(countBefore)
    expect((await gateway.history.list(code, {})).length).toBe(historyBefore)
    const replaced = await upload('replace', 99)
    expect(replaced.outcome).toBe('replaced')
    const list = await gateway.attachments.list(code)
    expect(list).toHaveLength(countBefore)
    expect(list.find((a) => a.fileName === '제안서_ITDR.pptx')).toMatchObject({ size: 99, description: '새 설명', uploadedBy: { id: 'u-kim' } })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', after: '교체 제안서_ITDR.pptx' })
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
