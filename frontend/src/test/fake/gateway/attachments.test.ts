import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, fakeFile, mockAs, TEST_NOW } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const MB = 1024 * 1024
const STORAGE_MSG = '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.'

describe('attachments.list / download', () => {
  // 테스트 코드: AT-054
  it('모든 역할이 조회하고 최신 업로드순이다', async () => {
    // given: user(han)로 연 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // when: Deal 1의 첨부 목록을 읽는다
    const list = await gateway.attachments.list(dealCode(1))
    // then: 세 파일이 있고 업로드 시각 내림차순이며 퇴사 업로더와 크기가 맞다
    expect(list.map((a) => a.fileName)).toEqual(expect.arrayContaining(['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']))
    const times = list.map((a) => Date.parse(a.uploadedAt))
    expect(times).toEqual([...times].sort((a, b) => b - a))
    expect(list.find((a) => a.fileName === '기술검토.xlsx')?.uploadedBy).toMatchObject({ name: '강퇴사', status: 'resigned' })
    expect(list.find((a) => a.fileName === '견적서_한빛은행_v2.pdf')?.size).toBe(2_400_000)
  })

  // 테스트 코드: AT-054
  it('다운로드는 파일명과 Blob을 돌려준다', async () => {
    // given: user로 연 Fake 게이트웨이와 첨부 하나
    const { gateway } = await mockAs('han')
    const first = (await gateway.attachments.list(dealCode(1)))[0]
    if (!first) throw new Error('none')
    // when: 첨부를 내려받는다
    const file = await gateway.attachments.download(first.id)
    // then: 파일 이름과 Blob이 돌아온다
    expect(file.fileName).toBe(first.fileName)
    expect(file.blob).toBeInstanceOf(Blob)
    // then: 없는 id는 404다
    await expectApiError(gateway.attachments.download(NO_SUCH_ID), 404)
  })
})

describe('attachments.upload', () => {
  // 테스트 코드: AT-054
  it('user는 403', async () => {
    // given: user로 연 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // when·then: 업로드하면 403이다
    await expectApiError(gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' }), 403)
  })

  // 테스트 코드: AT-054
  it('규칙 위반은 422 문구(차단 확장자·100MB·설명 100자)', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 차단 확장자·100MB 초과·설명 101자로 올리면 각각 422 문구다
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
    // then: 첨부는 하나도 생기지 않는다
    expect(await gateway.attachments.list(code)).toHaveLength(0)
  })

  // 테스트 코드: AT-054
  it('경계값 100MB·설명 100자·a.tar.gz는 허용한다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 정확히 100MB·설명 100자 파일을 올리고
    const a = await gateway.attachments.upload(code, { file: fakeFile('big.bin', 100 * MB), description: 'x'.repeat(100), onExists: 'ask' })
    // then: 업로드된다
    expect(a.outcome).toBe('uploaded')
    // when: 이어서 "backup.tar.gz"를 올리면
    const b = await gateway.attachments.upload(code, { file: fakeFile('backup.tar.gz', 10), description: '', onExists: 'ask' })
    // then: 이것도 업로드된다
    expect(b.outcome).toBe('uploaded')
  })

  // 테스트 코드: AT-054
  it('업로드하면 목록·History·Deal 갱신 시각이 바뀐다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 파일을 올린다
    const result = await gateway.attachments.upload(code, { file: fakeFile('제안서.pdf', 1234), description: '1차 제안', onExists: 'ask' })
    // then: 목록에 한 건, History에 "업로드 제안서.pdf", Deal 수정 시각이 현재 시각이다
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment).toMatchObject({ fileName: '제안서.pdf', size: 1234, description: '1차 제안', uploadedBy: { id: USER_ID.kim }, uploadedAt: TEST_NOW })
    expect(await gateway.attachments.list(code)).toHaveLength(1)
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', target: '첨부 파일', after: '업로드 제안서.pdf' })
    expect((await gateway.deals.get(code)).updatedAt).toBe(TEST_NOW)
  })

  // 테스트 코드: AT-054
  it('같은 이름은 ask면 409(file-exists), replace는 교체, skip은 변화 없음', async () => {
    // given: sales로 연 Fake 게이트웨이와 본인이 올린 "견적서_한빛은행_v2.pdf"
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const upload = (onExists: 'ask' | 'replace' | 'skip', size = 77) =>
      gateway.attachments.upload(code, { file: fakeFile('견적서_한빛은행_v2.pdf', size), description: '새 설명', onExists })
    const countBefore = (await gateway.attachments.list(code)).length
    const historyBefore = (await gateway.history.list(code, {})).length
    // when: ask로 같은 이름을 올린다
    const error = await expectApiError(upload('ask'), 409, '같은 이름의 파일이 이미 있습니다: 견적서_한빛은행_v2.pdf')
    // then: 409 file-exists다
    expect(error.kind).toBe('file-exists')
    // when: skip으로 올린다
    expect(await upload('skip')).toEqual({ outcome: 'skipped' })
    // then: skipped이고 목록·History가 그대로다
    expect((await gateway.attachments.list(code)).length).toBe(countBefore)
    expect((await gateway.history.list(code, {})).length).toBe(historyBefore)
    // when: replace로 올린다
    const replaced = await upload('replace', 99)
    // then: 교체되어 목록 수는 그대로이고 값이 새 값이며 History에 "교체"가 남는다
    expect(replaced.outcome).toBe('replaced')
    const list = await gateway.attachments.list(code)
    expect(list).toHaveLength(countBefore)
    expect(list.find((a) => a.fileName === '견적서_한빛은행_v2.pdf')).toMatchObject({ size: 99, description: '새 설명', uploadedBy: { id: USER_ID.kim } })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', after: '교체 견적서_한빛은행_v2.pdf' })
  })

  // 테스트 코드: AT-054
  it('저장소 장애 시뮬레이션이 켜져 있으면 503(storage-unavailable)이고 아무것도 저장되지 않는다', async () => {
    // given: 저장소 장애를 켠 Fake 게이트웨이
    const mock = await mockAs('kim')
    mock.control.setStorageFailure(true)
    // when: 업로드한다
    const error = await expectApiError(
      mock.gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' }),
      503,
      STORAGE_MSG,
    )
    // then: 503 storage-unavailable이고 목록이 비어 있다
    expect(error.kind).toBe('storage-unavailable')
    expect(await mock.gateway.attachments.list(dealCode(2))).toHaveLength(0)
    mock.control.setStorageFailure(false)
    // when: 장애를 끄고 다시 올린다
    const ok = await mock.gateway.attachments.upload(dealCode(2), { file: fakeFile('a.pdf'), description: '', onExists: 'ask' })
    // then: 업로드된다
    expect(ok.outcome).toBe('uploaded')
  })
})

describe('attachments.remove: 삭제 권한', () => {
  const findId = async (gw: Awaited<ReturnType<typeof mockAs>>['gateway'], name: string) => {
    const found = (await gw.attachments.list(dealCode(1))).find((a) => a.fileName === name)
    if (!found) throw new Error(name)
    return found.id
  }

  // 테스트 코드: AT-054
  it('본인 파일 O, 타인(재직) 파일 X, 퇴사 sales 파일 O, user X, admin 전체 O', async () => {
    // given: sales kim으로 연 Fake 게이트웨이
    const kim = await mockAs('kim')
    // when: 다른 sales의 파일을 지우면 403이고
    await expectApiError(kim.gateway.attachments.remove(await findId(kim.gateway, '제안서_ITDR.pptx')), 403, '본인이 올린 파일만 삭제할 수 있습니다.')
    // when: 본인·퇴사 sales의 파일은 지워진다
    await kim.gateway.attachments.remove(await findId(kim.gateway, '견적서_한빛은행_v2.pdf'))
    await kim.gateway.attachments.remove(await findId(kim.gateway, '기술검토.xlsx'))
    // then: 남은 파일은 다른 sales의 것뿐이다
    expect((await kim.gateway.attachments.list(dealCode(1))).map((a) => a.fileName)).toEqual(['제안서_ITDR.pptx'])

    // when: user는 지울 수 없고
    const han = await mockAs('han')
    await expectApiError(han.gateway.attachments.remove(await findId(han.gateway, '기술검토.xlsx')), 403)

    // when: admin은 남은 파일도 지운다
    const root = await mockAs('root')
    await root.gateway.attachments.remove(await findId(root.gateway, '제안서_ITDR.pptx'))
    // then: 두 파일이 남는다
    expect(await root.gateway.attachments.list(dealCode(1))).toHaveLength(2)
  })

  // 테스트 코드: AT-054
  it('삭제는 History에 남고 없는 id는 404', async () => {
    // given: sales로 연 Fake 게이트웨이와 본인 파일
    const { gateway } = await mockAs('kim')
    const id = await findId(gateway, '견적서_한빛은행_v2.pdf')
    // when: 파일을 지운다
    await gateway.attachments.remove(id)
    // then: History에 "삭제 …"가 남고
    expect((await gateway.history.list(dealCode(1), {}))[0]).toMatchObject({ category: 'attachment', after: '삭제 견적서_한빛은행_v2.pdf' })
    // then: 같은 id를 다시 지우면 404다
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

describe('attachments.upload: 설명 규칙 (서버와 같은 경계)', () => {
  // 테스트 코드: AT-054
  it('설명은 앞뒤 공백을 지우고 저장한다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when: 앞뒤 공백·줄바꿈이 든 설명으로 올린다
    const result = await put(gateway, dealCode(2), 'a.pdf', { description: '  견적  최종 \n' })
    // then: 저장된 설명은 앞뒤가 지워지고 안쪽 공백은 유지된다
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment.description).toBe('견적  최종')
    expect((await gateway.attachments.list(dealCode(2)))[0]?.description).toBe('견적  최종')
  })

  // 테스트 코드: AT-054
  it('공백을 덧댄 100자 설명은 받고 101자는 거절한다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 공백을 덧댄 100자 설명으로 올리면
    const padded = await put(gateway, code, 'a.pdf', { description: `  ${'가'.repeat(100)}  ` })

    // then: 업로드된다
    expect(padded.outcome).toBe('uploaded')

    // when·then: 101자 설명으로 올리면 422 설명 문구다
    await expectApiError(put(gateway, code, 'b.pdf', { description: '가'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
  })

  // 테스트 코드: AT-054
  it('이모지는 한 글자로 센다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 이모지 100개는 받고 101개는 422 설명 문구다
    expect((await put(gateway, code, 'a.pdf', { description: '😀'.repeat(100) })).outcome).toBe('uploaded')
    await expectApiError(put(gateway, code, 'b.pdf', { description: '😀'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
  })
})

describe('attachments.upload: 파일 이름 규칙', () => {
  // 테스트 코드: AT-054
  it.each(['a/b.pdf', 'a\\b.pdf', '..', 'a\tb.pdf', '견적\u202egpj.pdf', 'x\u2066y.pdf'])('쓸 수 없는 이름 %j는 서버 문구로 거절하고 아무것도 저장하지 않는다', async (name) => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 올리면 422 "사용할 수 없는 파일 이름입니다."다
    await expectApiError(put(gateway, code, name), 422, '사용할 수 없는 파일 이름입니다.')
    // then: 목록과 History에 첨부가 없다
    expect(await gateway.attachments.list(code)).toHaveLength(0)
    expect((await gateway.history.list(code, {})).some((h) => h.category === 'attachment')).toBe(false)
  })

  // 테스트 코드: AT-054
  it.each(['\ufeffa.pdf', 'a\u200bb.pdf', 'a.pdf\u200d', 'setup.exe\u200b', 'a\u00adb.pdf', '\u{1F468}\u200d\u{1F469}.png'])(
    '서식 문자가 든 이름 %j는 서버 문구로 거절하고 아무것도 저장하지 않는다',
    async (name) => {
      // given: sales로 연 Fake 게이트웨이
      const { gateway } = await mockAs('kim')
      const code = dealCode(2)
      // when·then: 올리면 422 이름 문구다
      await expectApiError(put(gateway, code, name), 422, '사용할 수 없는 파일 이름입니다.')
      // then: 목록에 첨부가 없다
      expect(await gateway.attachments.list(code)).toHaveLength(0)
    },
  )

  // 테스트 코드: AT-054
  it('끝에 BOM이 붙은 setup.exe도 거절하고 아무것도 저장하지 않는다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 올리면 422다
    await expectApiError(put(gateway, code, 'setup.exe\ufeff'), 422)
    // then: 목록에 첨부가 없다
    expect(await gateway.attachments.list(code)).toHaveLength(0)
  })

  // 테스트 코드: AT-054
  it('255 코드 포인트 이름은 받고 256은 거절한다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: 255자 이름은 uploaded, 256자 이름은 422 이름 문구다
    expect((await put(gateway, code, 'a'.repeat(255))).outcome).toBe('uploaded')
    await expectApiError(put(gateway, code, 'a'.repeat(256)), 422, '사용할 수 없는 파일 이름입니다.')
  })

  // 테스트 코드: AT-054
  it('이름 끝에 공백·점이 있어도 실행 파일을 막는다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when·then: 끝에 공백·점이 붙은 setup.exe를 올리면 모두 422 차단 문구다
    for (const name of ['setup.exe ', 'setup.exe.', 'setup.exe\u3000', 'setup.EXE . ']) {
      await expectApiError(put(gateway, dealCode(2), name), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
    }
  })

  // 테스트 코드: AT-054
  it.each(['vbs', 'vbe', 'wsf', 'wsh', 'hta', 'cpl', 'msp', 'mst', 'apk', 'appimage', 'run'])('추가된 차단 확장자 .%s를 막는다', async (ext) => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    // when·then: 올리면 422 차단 문구다
    await expectApiError(put(gateway, dealCode(2), `tool.${ext}`), 422, `실행·설치 파일(.${ext})은 업로드할 수 없습니다.`)
  })

  // 테스트 코드: AT-054
  it('서버와 같은 순서로 답한다: 읽기 전용 403, 없는 Deal 404, 규칙 422', async () => {
    // given: user와 sales의 Fake 게이트웨이
    const han = await mockAs('han')
    // when·then: user는 규칙 위반이어도 403이다
    await expectApiError(put(han.gateway, dealCode(2), 'a/b.pdf'), 403)
    const kim = await mockAs('kim')
    // when·then: 없는 Deal은 404다
    await expectApiError(put(kim.gateway, '20000101-ZZZZ', 'a/b.pdf'), 404, 'Deal을 찾을 수 없습니다.')
    // when·then: 설명·크기·차단 확장자 순으로 첫 위반 문구가 나온다
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe', { description: 'x'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe', { size: 100 * MB + 1 }), 422, '파일 크기가 100MB를 초과합니다. (최대 100MB)')
    await expectApiError(put(kim.gateway, dealCode(2), 'a/b.exe'), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
  })

  // 테스트 코드: AT-054
  it('저장소 장애는 규칙 오류 뒤, 같은 이름 판정 앞에서 판정한다', async () => {
    // given: 저장소 장애를 켠 Fake 게이트웨이
    const mock = await mockAs('kim')
    mock.control.setStorageFailure(true)
    // when·then: 쓸 수 없는 이름은 장애여도 422다
    await expectApiError(put(mock.gateway, dealCode(2), 'a/b.pdf'), 422, '사용할 수 없는 파일 이름입니다.')
    // when·then: 같은 이름은 503이다
    await expectApiError(put(mock.gateway, dealCode(1), '견적서_한빛은행_v2.pdf'), 503)
  })
})

describe('attachments.upload: NFC 이름', () => {
  const NFD = '한글.pdf'.normalize('NFD')
  const NFC = '한글.pdf'.normalize('NFC')

  // 테스트 코드: AT-054
  it('이름을 NFC로 저장·표시하고 History에도 NFC로 남긴다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: NFD 이름 파일을 올린다
    const result = await put(gateway, code, NFD)
    // then: 응답·History·다운로드 이름이 모두 NFC다
    if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
    expect(result.attachment.fileName).toBe(NFC)
    expect(result.attachment.fileName).not.toBe(NFD)
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ after: `업로드 ${NFC}` })
    expect((await gateway.attachments.download(result.attachment.id)).fileName).toBe(NFC)
  })

  // 테스트 코드: AT-054
  it('NFD와 NFC 표기는 같은 이름이다(409에 NFC 이름)', async () => {
    // given: sales로 연 Fake 게이트웨이와 NFC 이름 파일
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await put(gateway, code, NFC)
    // when·then: NFD 표기로 올리면 409 file-exists이고 NFC 이름이 문구에 든다
    const error = await expectApiError(put(gateway, code, NFD), 409, `같은 이름의 파일이 이미 있습니다: ${NFC}`)
    expect(error.kind).toBe('file-exists')
    // then: skip은 변화 없음, replace는 교체이며 파일은 하나뿐이다
    expect(await put(gateway, code, NFD, { onExists: 'skip' })).toEqual({ outcome: 'skipped' })
    expect((await put(gateway, code, NFD, { onExists: 'replace' })).outcome).toBe('replaced')
    expect(await gateway.attachments.list(code)).toHaveLength(1)
  })

  // 테스트 코드: AT-054
  it('대소문자만 다른 이름은 별개 파일로 둔다', async () => {
    // given: sales로 연 Fake 게이트웨이와 "Report.pdf"
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await put(gateway, code, 'Report.pdf')
    // when: "report.pdf"를 올린다
    expect((await put(gateway, code, 'report.pdf')).outcome).toBe('uploaded')
    // then: 새 업로드이고 파일은 둘이다
    expect(await gateway.attachments.list(code)).toHaveLength(2)
  })
})

describe('attachments.upload: 교체 권한 = 삭제 권한', () => {
  // 테스트 코드: AT-054
  it('업로더 본인은 교체할 수 있다: 같은 id, 새 업로더 정보, History 한 건', async () => {
    // given: sales로 연 Fake 게이트웨이와 본인 파일
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = (await gateway.attachments.list(code)).find((a) => a.fileName === '견적서_한빛은행_v2.pdf')
    // when: replace로 올린다
    const result = await put(gateway, code, '견적서_한빛은행_v2.pdf', { onExists: 'replace', size: 55, description: '교체본' })
    // then: 같은 id에 새 값이 반영되고 History에 "교체"가 남으며 Deal 수정 시각이 바뀐다
    if (result.outcome !== 'replaced') throw new Error('expected replaced')
    expect(result.attachment).toMatchObject({ id: before?.id, size: 55, description: '교체본', uploadedBy: { id: USER_ID.kim }, uploadedAt: TEST_NOW })
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'attachment', after: '교체 견적서_한빛은행_v2.pdf' })
    expect((await gateway.deals.get(code)).updatedAt).toBe(TEST_NOW)
  })

  // 테스트 코드: AT-054
  it('다른 재직 sales의 교체는 403이고 아무것도 바뀌지 않는다', async () => {
    // given: sales로 연 Fake 게이트웨이와 변경 전 상태
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const listBefore = await gateway.attachments.list(code)
    const historyBefore = await gateway.history.list(code, {})
    const updatedBefore = (await gateway.deals.get(code)).updatedAt

    // when: 다른 sales의 파일을 replace로 올린다
    const error = await expectApiError(put(gateway, code, '제안서_ITDR.pptx', { onExists: 'replace', size: 1, description: '덮어쓰기' }), 403, '본인이 올린 파일만 교체할 수 있습니다.')

    // then: 403 forbidden이고 목록·History·Deal 시각이 그대로다
    expect(error.kind).toBe('forbidden')
    expect(await gateway.attachments.list(code)).toEqual(listBefore)
    expect(await gateway.history.list(code, {})).toEqual(historyBefore)
    expect((await gateway.deals.get(code)).updatedAt).toBe(updatedBefore)
  })

  // 테스트 코드: AT-054
  it('퇴사 sales의 파일은 다른 sales가 교체하고 업로더가 된다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // when: 퇴사 sales의 파일을 replace로 올린다
    const result = await put(gateway, code, '기술검토.xlsx', { onExists: 'replace' })
    // then: 교체되고 업로더가 요청자다
    if (result.outcome !== 'replaced') throw new Error('expected replaced')
    expect(result.attachment.uploadedBy).toMatchObject({ id: USER_ID.kim, name: '김영업' })
  })

  // 테스트 코드: AT-054
  it('admin은 모든 파일을 교체할 수 있다', async () => {
    // given: admin으로 연 Fake 게이트웨이
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    // when·then: 모든 파일을 replace로 올리면 교체되고 파일은 세 개 그대로다
    for (const name of ['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']) {
      expect((await put(gateway, code, name, { onExists: 'replace' })).outcome).toBe('replaced')
    }
    expect(await gateway.attachments.list(code)).toHaveLength(3)
  })

  // 테스트 코드: AT-054
  it('권한은 replace에서만 본다: ask는 409, skip은 변화 없음', async () => {
    // given: sales로 연 Fake 게이트웨이와 다른 sales의 파일
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // when·then: ask는 권한과 무관하게 409다
    await expectApiError(put(gateway, code, '제안서_ITDR.pptx', { onExists: 'ask' }), 409)
    // when·then: skip은 skipped다
    expect(await put(gateway, code, '제안서_ITDR.pptx', { onExists: 'skip' })).toEqual({ outcome: 'skipped' })
  })

  // 테스트 코드: AT-054
  it('같은 이름이 없으면 replace·skip도 새 업로드다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: replace와 skip으로 올리면 둘 다 uploaded다
    expect((await put(gateway, code, 'a.pdf', { onExists: 'replace' })).outcome).toBe('uploaded')
    expect((await put(gateway, code, 'b.pdf', { onExists: 'skip' })).outcome).toBe('uploaded')
  })

  // 테스트 코드: AT-054
  it('user는 무엇보다 먼저 403이다', async () => {
    // given: user로 연 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // when·then: replace로 올리면 403이고 교체 권한 문구가 아니다
    const error = await expectApiError(put(gateway, dealCode(1), '견적서_한빛은행_v2.pdf', { onExists: 'replace' }), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
  })
})

describe('attachments.remove: 판정 순서', () => {
  // 테스트 코드: AT-054
  it('user의 삭제는 없는 id여도 404가 아니라 403이다', async () => {
    // given: user로 연 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    // when·then: 없는 id를 지우면 403이고 권한 문구가 아니다
    const error = await expectApiError(gateway.attachments.remove(NO_SUCH_ID), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
  })

  // 테스트 코드: AT-054
  it('user의 삭제는 있는 파일이어도 읽기 전용 403이다', async () => {
    // given: user로 연 Fake 게이트웨이
    const { gateway } = await mockAs('han')
    const id = (await gateway.attachments.list(dealCode(1)))[0]?.id ?? NO_SUCH_ID
    // when·then: 있는 파일을 지우면 403이고 삭제 권한 문구가 아니다
    const error = await expectApiError(gateway.attachments.remove(id), 403)
    expect(error.message).not.toContain(OWNER_ONLY_FRAGMENT)
    // then: 파일은 그대로 3개다
    expect(await gateway.attachments.list(dealCode(1))).toHaveLength(3)
  })

  // 테스트 코드: AT-054
  it('sales와 admin의 없는 id 삭제는 권한 판정 전에 404다', async () => {
    // given: sales와 admin의 Fake 게이트웨이
    for (const key of ['kim', 'root'] as const) {
      const { gateway } = await mockAs(key)
      // when·then: 없는 id를 지우면 404 문구다
      await expectApiError(gateway.attachments.remove(NO_SUCH_ID), 404, '첨부 파일을 찾을 수 없습니다.')
    }
  })

  // 테스트 코드: AT-054
  it('다른 sales 파일의 삭제는 삭제 문구의 403이고 파일이 남는다', async () => {
    // given: sales로 연 Fake 게이트웨이
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // given: 다른 sales의 파일 id
    const id = (await gateway.attachments.list(code)).find((a) => a.fileName === '제안서_ITDR.pptx')?.id ?? NO_SUCH_ID
    // when·then: 삭제하면 삭제 권한 문구의 403이다
    await expectApiError(gateway.attachments.remove(id), 403, '본인이 올린 파일만 삭제할 수 있습니다.')
    // then: 파일이 그대로 3개다
    expect(await gateway.attachments.list(code)).toHaveLength(3)
  })
})
