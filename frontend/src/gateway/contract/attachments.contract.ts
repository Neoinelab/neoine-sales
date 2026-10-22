/**
 * 첨부 파일 계약(P2b AC-07~14, AC-20, R-18~R-22). mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다(Deal 삭제가 첨부를 함께 지운다). 시드에 기대지 않는다.
 * 이 스위트에 없는 것: 100MB 초과(실제 100MB를 보내야 함 → mock·단위 테스트가 맡는다), 저장 위치 미설정 503(실서버 설정을
 * 바꾸므로 mock 시뮬레이션만), 다른 재직 sales의 교체·삭제 403(sales 세션이 하나뿐 → mock 단위 테스트와 백엔드 functional).
 */

import { describe, expect, it } from 'vitest'
import type { DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const NOT_FOUND = '첨부 파일을 찾을 수 없습니다.'

async function newDeal(gateway: Gateway) {
  const me = await gateway.auth.me()
  const input: DealInput = {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: null,
    solution: 'ITDR',
    users: 10,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 1_000_000,
    revenueDate: '2027-02-15',
    customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
  }
  return gateway.deals.create(input)
}

function file(name: string, bytes: number[] = [1, 2, 3, 250], type = 'application/pdf'): File {
  return new File([new Uint8Array(bytes)], name, { type })
}

const bytesOf = async (blob: Blob): Promise<number[]> => Array.from(new Uint8Array(await blob.arrayBuffer()))

type Put = { description?: string; onExists?: 'ask' | 'replace' | 'skip'; bytes?: number[] }
const put = (gateway: Gateway, code: string, name: string, options: Put = {}) =>
  gateway.attachments.upload(code, {
    file: file(name, options.bytes),
    description: options.description ?? '',
    onExists: options.onExists ?? 'ask',
  })

export function attachmentsContract(make: MakeGateway): void {
  describe('attachments 계약', () => {
    it('uploads a new file as the requester and lists it with the bytes kept', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)

      const result = await put(sales, deal.code, `견적서-${unique('f')}.pdf`, { description: '2차 견적' })

      if (result.outcome !== 'uploaded') throw new Error(`expected uploaded, got ${result.outcome}`)
      expect(result.attachment).toMatchObject({ dealCode: deal.code, description: '2차 견적', size: 4, uploadedBy: { id: me.id, role: 'sales' } })
      expect(Number.isNaN(Date.parse(result.attachment.uploadedAt))).toBe(false)
      expect(await sales.attachments.list(deal.code)).toEqual([result.attachment])
      const downloaded = await sales.attachments.download(result.attachment.id)
      expect(downloaded.fileName).toBe(result.attachment.fileName)
      expect(await bytesOf(downloaded.blob)).toEqual([1, 2, 3, 250])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('keeps a name with spaces, Korean and an emoji for the download and trims the description', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = '견적서 최종 😀 (v2) #1.pdf'

      const result = await put(sales, deal.code, name, { description: '  앞뒤 공백  ' })

      if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(result.attachment).toMatchObject({ fileName: name, description: '앞뒤 공백' })
      expect((await sales.attachments.download(result.attachment.id)).fileName).toBe(name)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('stores an NFD name in NFC and treats both spellings as the same file', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const nfc = `한글-${unique('n')}.pdf`.normalize('NFC')
      const nfd = nfc.normalize('NFD')

      const first = await put(sales, deal.code, nfd)
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(first.attachment.fileName).toBe(nfc)
      const error = await expectRejects(put(sales, deal.code, nfc), 409, `같은 이름의 파일이 이미 있습니다: ${nfc}`)
      expect(error.kind).toBe('file-exists')
      await sales.deals.remove(deal.code, deal.code)
    })

    it('keeps names that differ only by case as two files', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const stem = unique('Case')

      await put(sales, deal.code, `${stem}.pdf`)
      const second = await put(sales, deal.code, `${stem.toUpperCase()}.pdf`)

      expect(second.outcome).toBe('uploaded')
      expect(await sales.attachments.list(deal.code)).toHaveLength(2)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('accepts the boundaries: a 100 character description, a.tar.gz, a name without extension and a zero byte file', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      expect((await put(sales, deal.code, 'a.pdf', { description: `  ${'가'.repeat(100)}  ` })).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 'a.tar.gz')).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 'README')).outcome).toBe('uploaded')
      const empty = await put(sales, deal.code, 'empty.txt', { bytes: [] })
      if (empty.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(empty.attachment.size).toBe(0)
      expect(await bytesOf((await sales.attachments.download(empty.attachment.id)).blob)).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('asks (409 file-exists) for the same name and changes nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await put(sales, deal.code, 'same.pdf', { bytes: [1] })
      const listBefore = await sales.attachments.list(deal.code)
      const historyBefore = await sales.history.list(deal.code, {})

      const error = await expectRejects(put(sales, deal.code, 'same.pdf', { bytes: [9, 9] }), 409, '같은 이름의 파일이 이미 있습니다: same.pdf')

      expect(error.kind).toBe('file-exists')
      expect(await sales.attachments.list(deal.code)).toEqual(listBefore)
      expect(await sales.history.list(deal.code, {})).toEqual(historyBefore)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('skips the same name without touching the file, the list or the history', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const first = await put(sales, deal.code, 'same.pdf', { bytes: [1] })
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      const historyBefore = await sales.history.list(deal.code, {})

      const result = await put(sales, deal.code, 'same.pdf', { bytes: [9, 9], onExists: 'skip', description: '무시' })

      expect(result).toEqual({ outcome: 'skipped' })
      expect(await sales.attachments.list(deal.code)).toEqual([first.attachment])
      expect(await bytesOf((await sales.attachments.download(first.attachment.id)).blob)).toEqual([1])
      expect(await sales.history.list(deal.code, {})).toEqual(historyBefore)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('replaces the same name keeping the id, with the new content, size and description', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const first = await put(sales, deal.code, 'same.pdf', { bytes: [1], description: '이전' })
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')

      const result = await put(sales, deal.code, 'same.pdf', { bytes: [7, 8, 9], description: '새 설명', onExists: 'replace' })

      if (result.outcome !== 'replaced') throw new Error(`expected replaced, got ${result.outcome}`)
      expect(result.attachment).toMatchObject({ id: first.attachment.id, size: 3, description: '새 설명' })
      expect(await sales.attachments.list(deal.code)).toEqual([result.attachment])
      expect(await bytesOf((await sales.attachments.download(first.attachment.id)).blob)).toEqual([7, 8, 9])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('uploads a new file when replace or skip is chosen but the name does not exist', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      expect((await put(sales, deal.code, 'r.pdf', { onExists: 'replace' })).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 's.pdf', { onExists: 'skip' })).outcome).toBe('uploaded')
      await sales.deals.remove(deal.code, deal.code)
    })

    it('lets admin replace a file uploaded by a sales user and become its uploader', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await put(sales, deal.code, 'same.pdf')
      const admin = await make('admin')
      const adminMe = await admin.auth.me()

      const result = await put(admin, deal.code, 'same.pdf', { onExists: 'replace', bytes: [5] })

      if (result.outcome !== 'replaced') throw new Error('expected replaced')
      expect(result.attachment.uploadedBy.id).toBe(adminMe.id)
      await admin.deals.remove(deal.code, deal.code)
    })

    it('writes one history entry per upload, replace and delete, and moves the deal update time', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = `h-${unique('h')}.pdf`
      const before = (await sales.deals.get(deal.code)).updatedAt

      const first = await put(sales, deal.code, name)
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      await put(sales, deal.code, name, { onExists: 'replace' })
      await sales.attachments.remove(first.attachment.id)

      const entries = (await sales.history.list(deal.code, {})).filter((h) => h.category === 'attachment')
      expect(entries.map((h) => [h.target, h.before, h.after])).toEqual([
        ['첨부 파일', '', `삭제 ${name}`],
        ['첨부 파일', '', `교체 ${name}`],
        ['첨부 파일', '', `업로드 ${name}`],
      ])
      expect(Date.parse((await sales.deals.get(deal.code)).updatedAt)).toBeGreaterThanOrEqual(Date.parse(before))
      await sales.deals.remove(deal.code, deal.code)
    })

    it('checks the rules in the server order and stores nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(put(sales, '20000101-ZZZZ', 'a/b.exe', { description: 'x'.repeat(101) }), 404, 'Deal을 찾을 수 없습니다.')
      await expectRejects(put(sales, deal.code, 'a/b.exe', { description: 'x'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
      await expectRejects(put(sales, deal.code, 'a/b.exe'), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
      await expectRejects(put(sales, deal.code, 'a/b.pdf'), 422, '사용할 수 없는 파일 이름입니다.')
      expect(await sales.attachments.list(deal.code)).toEqual([])
      expect((await sales.history.list(deal.code, {})).some((h) => h.category === 'attachment')).toBe(false)
      await sales.deals.remove(deal.code, deal.code)
    })

    it.each(['setup.exe', 'SETUP.EXE', 'setup.exe ', 'setup.exe.', 'setup.EXE . ', 'tool.vbs', 'app.appimage'])(
      'blocks the executable name %j',
      async (name) => {
        const sales = await make('sales')
        const deal = await newDeal(sales)
        const extension = name.trim().replace(/[\s.]+$/, '').split('.').pop()?.toLowerCase() ?? ''

        await expectRejects(put(sales, deal.code, name), 422, `실행·설치 파일(.${extension})은 업로드할 수 없습니다.`)

        await sales.deals.remove(deal.code, deal.code)
      },
    )

    it.each(['a/b.pdf', 'a\\b.pdf', '..', 'a\tb.pdf', '견적‮gpj.pdf', 'x⁦y.pdf', 'a'.repeat(256)])(
      'refuses the unusable file name %j with the server message',
      async (name) => {
        const sales = await make('sales')
        const deal = await newDeal(sales)

        await expectRejects(put(sales, deal.code, name), 422, '사용할 수 없는 파일 이름입니다.')

        await sales.deals.remove(deal.code, deal.code)
      },
    )

    it('lets the user role list and download but refuses the upload with 403', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'readable.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const user = await make('user')

      expect((await user.attachments.list(deal.code)).map((a) => a.fileName)).toEqual(['readable.pdf'])
      expect((await user.attachments.download(uploaded.attachment.id)).fileName).toBe('readable.pdf')
      await expectRejects(put(user, deal.code, 'new.pdf'), 403)

      const again = await make('sales')
      expect(await again.attachments.list(deal.code)).toHaveLength(1)
      await again.deals.remove(deal.code, deal.code)
    })

    it('answers 404 for the list of an unknown deal and for the download of an unknown id', async () => {
      const sales = await make('sales')

      await expectRejects(sales.attachments.list('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
      await expectRejects(sales.attachments.download(NO_SUCH_ID), 404, NOT_FOUND)
    })

    it('lets the uploader delete her file: gone from the list and the download', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'gone.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')

      await sales.attachments.remove(uploaded.attachment.id)

      expect(await sales.attachments.list(deal.code)).toEqual([])
      await expectRejects(sales.attachments.download(uploaded.attachment.id), 404, NOT_FOUND)
      await expectRejects(sales.attachments.remove(uploaded.attachment.id), 404, NOT_FOUND)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('lets admin delete a file of a sales user', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'by-sales.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const admin = await make('admin')

      await admin.attachments.remove(uploaded.attachment.id)

      expect(await admin.attachments.list(deal.code)).toEqual([])
      await admin.deals.remove(deal.code, deal.code)
    })

    it('judges the delete of the user role as 403 before 404, and an unknown id as 404 for sales', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'keep.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const user = await make('user')

      const unknown = await expectRejects(user.attachments.remove(NO_SUCH_ID), 403)
      const existing = await expectRejects(user.attachments.remove(uploaded.attachment.id), 403)
      expect(unknown.message).not.toBe('본인이 올린 파일만 삭제할 수 있습니다.')
      expect(existing.message).toBe(unknown.message)

      const again = await make('sales')
      await expectRejects(again.attachments.remove(NO_SUCH_ID), 404, NOT_FOUND)
      expect(await again.attachments.list(deal.code)).toHaveLength(1)
      await again.deals.remove(deal.code, deal.code)
    })

    it('deletes the files together with the deal', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'with-deal.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect((await sales.deals.impact(deal.code)).attachmentCount).toBe(1)

      await sales.deals.remove(deal.code, deal.code)

      await expectRejects(sales.attachments.download(uploaded.attachment.id), 404, NOT_FOUND)
    })
  })
}
