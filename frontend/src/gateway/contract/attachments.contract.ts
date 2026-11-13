/**
 * 첨부 파일 계약(R-18~R-22). mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다(Deal 삭제가 첨부를 함께 지운다). 시드에 기대지 않는다.
 * 이 스위트에 없는 것: 100MB 초과(실제 100MB를 보내야 함 → mock·단위 테스트가 맡는다), 저장 위치 미설정 503(실서버 설정을
 * 바꾸므로 mock 시뮬레이션만), 다른 재직 sales의 교체·삭제 403(sales 세션이 하나뿐 → mock 단위 테스트와 백엔드 단위 테스트).
 */

import { describe, expect, it } from 'vitest'
import type { DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID, anyVendorId } from './support'

const NOT_FOUND = '첨부 파일을 찾을 수 없습니다.'

async function newDeal(gateway: Gateway) {
  const me = await gateway.auth.me()
  const input: DealInput = {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: await anyVendorId(gateway),
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
    // 새 파일을 올리면 요청자가 업로더로 기록되고 목록·다운로드에서 바이트가 그대로 나온다.
    // 테스트 코드: AT-001
    it('새 파일을 올리면 요청자가 업로더로 기록되고 바이트가 그대로 보존된다', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)

      // when: 설명과 함께 새 파일을 올린다
      const result = await put(sales, deal.code, `견적서-${unique('f')}.pdf`, { description: '2차 견적' })

      // then: 업로드되어 요청자·설명·크기가 기록되고 목록과 다운로드 바이트가 같다
      if (result.outcome !== 'uploaded') throw new Error(`expected uploaded, got ${result.outcome}`)
      expect(result.attachment).toMatchObject({ dealCode: deal.code, description: '2차 견적', size: 4, uploadedBy: { id: me.id, role: 'sales' } })
      expect(Number.isNaN(Date.parse(result.attachment.uploadedAt))).toBe(false)
      expect(await sales.attachments.list(deal.code)).toEqual([result.attachment])
      const downloaded = await sales.attachments.download(result.attachment.id)
      expect(downloaded.fileName).toBe(result.attachment.fileName)
      expect(await bytesOf(downloaded.blob)).toEqual([1, 2, 3, 250])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 공백·한글·이모지가 든 이름은 그대로 저장되어 내려받을 때 같은 이름이고 설명은 앞뒤 공백을 뺀다.
    // 테스트 코드: AT-001
    it('공백·한글·이모지가 든 이름은 그대로 보존되고 설명은 앞뒤 공백이 지워진다', async () => {
      // given: 새 Deal과 특수 문자가 든 파일 이름
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = '견적서 최종 😀 (v2) #1.pdf'

      // when: 앞뒤 공백이 있는 설명과 함께 올린다
      const result = await put(sales, deal.code, name, { description: '  앞뒤 공백  ' })

      // then: 이름은 그대로, 설명은 공백이 지워지고 다운로드 이름도 같다
      if (result.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(result.attachment).toMatchObject({ fileName: name, description: '앞뒤 공백' })
      expect((await sales.attachments.download(result.attachment.id)).fileName).toBe(name)
      await sales.deals.remove(deal.code, deal.code)
    })

    // NFD 이름은 NFC로 저장되고 두 표기는 같은 파일로 취급된다.
    // 테스트 코드: AT-010, AT-021
    it('NFD 이름은 NFC로 저장되고 두 표기는 같은 파일로 취급된다', async () => {
      // given: NFD 표기로 올린 파일
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const nfc = `한글-${unique('n')}.pdf`.normalize('NFC')
      const nfd = nfc.normalize('NFD')
      const first = await put(sales, deal.code, nfd)

      // then: 이름이 NFC로 저장되었다
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(first.attachment.fileName).toBe(nfc)
      // when·then: NFC 표기로 같은 이름을 올리면 409 file-exists다
      const error = await expectRejects(put(sales, deal.code, nfc), 409, `같은 이름의 파일이 이미 있습니다: ${nfc}`)
      expect(error.kind).toBe('file-exists')
      await sales.deals.remove(deal.code, deal.code)
    })

    // 대소문자만 다른 이름은 별개 파일이다.
    // 테스트 코드: AT-021
    it('대소문자만 다른 이름은 별개 파일 둘로 보존된다', async () => {
      // given: 이름이 소문자인 파일이 올라간 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const stem = unique('Case')
      await put(sales, deal.code, `${stem}.pdf`)

      // when: 대문자로만 다른 이름을 올린다
      const second = await put(sales, deal.code, `${stem.toUpperCase()}.pdf`)

      // then: 새 파일로 올라가 목록에 둘이다
      expect(second.outcome).toBe('uploaded')
      expect(await sales.attachments.list(deal.code)).toHaveLength(2)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 경계값 파일(설명 100자, 이중 확장자, 확장자 없음, 0바이트)은 올라간다.
    // 테스트 코드: AT-005
    it('설명 100자·이중 확장자·확장자 없음·0바이트 파일은 모두 올라간다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 설명 100자, a.tar.gz, 확장자 없는 이름은 올라간다
      expect((await put(sales, deal.code, 'a.pdf', { description: `  ${'가'.repeat(100)}  ` })).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 'a.tar.gz')).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 'README')).outcome).toBe('uploaded')
      // when: 0바이트 파일을 올린다
      const empty = await put(sales, deal.code, 'empty.txt', { bytes: [] })
      // then: 크기 0으로 올라가고 내려받아도 비어 있다
      if (empty.outcome !== 'uploaded') throw new Error('expected uploaded')
      expect(empty.attachment.size).toBe(0)
      expect(await bytesOf((await sales.attachments.download(empty.attachment.id)).blob)).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 이름을 ask로 올리면 409 file-exists이고 아무것도 바뀌지 않는다.
    // 테스트 코드: AT-017
    it('같은 이름을 ask로 올리면 409 file-exists이고 목록·이력이 그대로다', async () => {
      // given: same.pdf가 올라간 Deal과 그 목록·이력
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await put(sales, deal.code, 'same.pdf', { bytes: [1] })
      const listBefore = await sales.attachments.list(deal.code)
      const historyBefore = await sales.history.list(deal.code, {})

      // when·then: 같은 이름을 ask로 올리면 409 file-exists다
      const error = await expectRejects(put(sales, deal.code, 'same.pdf', { bytes: [9, 9] }), 409, '같은 이름의 파일이 이미 있습니다: same.pdf')

      // then: 목록과 이력이 그대로다
      expect(error.kind).toBe('file-exists')
      expect(await sales.attachments.list(deal.code)).toEqual(listBefore)
      expect(await sales.history.list(deal.code, {})).toEqual(historyBefore)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 이름을 skip으로 올리면 skipped이고 파일·목록·이력이 그대로다.
    // 테스트 코드: AT-018
    it('같은 이름을 skip으로 올리면 skipped이고 파일·목록·이력이 그대로다', async () => {
      // given: same.pdf가 올라간 Deal과 그 이력
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const first = await put(sales, deal.code, 'same.pdf', { bytes: [1] })
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      const historyBefore = await sales.history.list(deal.code, {})

      // when: 같은 이름을 skip으로 올린다
      const result = await put(sales, deal.code, 'same.pdf', { bytes: [9, 9], onExists: 'skip', description: '무시' })

      // then: skipped이고 목록·내용·이력이 그대로다
      expect(result).toEqual({ outcome: 'skipped' })
      expect(await sales.attachments.list(deal.code)).toEqual([first.attachment])
      expect(await bytesOf((await sales.attachments.download(first.attachment.id)).blob)).toEqual([1])
      expect(await sales.history.list(deal.code, {})).toEqual(historyBefore)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 이름을 replace로 올리면 id는 그대로이고 내용·크기·설명이 바뀐다.
    // 테스트 코드: AT-019
    it('같은 이름을 replace로 올리면 같은 id에 새 내용·크기·설명이 담긴다', async () => {
      // given: same.pdf가 올라간 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const first = await put(sales, deal.code, 'same.pdf', { bytes: [1], description: '이전' })
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')

      // when: 같은 이름을 replace로 올린다
      const result = await put(sales, deal.code, 'same.pdf', { bytes: [7, 8, 9], description: '새 설명', onExists: 'replace' })

      // then: replaced이고 id는 같으며 내용·크기·설명이 새 값이다
      if (result.outcome !== 'replaced') throw new Error(`expected replaced, got ${result.outcome}`)
      expect(result.attachment).toMatchObject({ id: first.attachment.id, size: 3, description: '새 설명' })
      expect(await sales.attachments.list(deal.code)).toEqual([result.attachment])
      expect(await bytesOf((await sales.attachments.download(first.attachment.id)).blob)).toEqual([7, 8, 9])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 이름이 없으면 replace·skip을 골라도 새 업로드다.
    // 테스트 코드: AT-020
    it('같은 이름이 없으면 replace나 skip을 골라도 새 파일로 올라간다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 없는 이름을 replace·skip으로 올리면 둘 다 uploaded다
      expect((await put(sales, deal.code, 'r.pdf', { onExists: 'replace' })).outcome).toBe('uploaded')
      expect((await put(sales, deal.code, 's.pdf', { onExists: 'skip' })).outcome).toBe('uploaded')
      await sales.deals.remove(deal.code, deal.code)
    })

    // admin은 sales가 올린 파일을 교체할 수 있고 업로더가 admin으로 바뀐다.
    // 테스트 코드: AT-022
    it('admin은 sales가 올린 파일을 교체하고 업로더가 admin으로 바뀐다', async () => {
      // given: sales가 올린 same.pdf와 admin 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await put(sales, deal.code, 'same.pdf')
      const admin = await make('admin')
      const adminMe = await admin.auth.me()

      // when: admin이 같은 이름을 replace로 올린다
      const result = await put(admin, deal.code, 'same.pdf', { onExists: 'replace', bytes: [5] })

      // then: 교체되고 업로더가 admin이다
      if (result.outcome !== 'replaced') throw new Error('expected replaced')
      expect(result.attachment.uploadedBy.id).toBe(adminMe.id)
      await admin.deals.remove(deal.code, deal.code)
    })

    // 업로드·교체·삭제마다 이력이 한 건씩 남고 Deal 수정 시각이 앞서지 않는다.
    // 테스트 코드: AT-003, AT-019, AT-036
    it('업로드·교체·삭제마다 이력이 한 건씩 남고 Deal 수정 시각이 뒤로 가지 않는다', async () => {
      // given: 새 Deal과 그 수정 시각
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = `h-${unique('h')}.pdf`
      const before = (await sales.deals.get(deal.code)).updatedAt

      // when: 업로드하고 교체한 뒤 삭제한다
      const first = await put(sales, deal.code, name)
      if (first.outcome !== 'uploaded') throw new Error('expected uploaded')
      await put(sales, deal.code, name, { onExists: 'replace' })
      await sales.attachments.remove(first.attachment.id)

      // then: 첨부 이력이 삭제·교체·업로드 순으로 한 건씩 있고 수정 시각이 뒤로 가지 않았다
      const entries = (await sales.history.list(deal.code, {})).filter((h) => h.category === 'attachment')
      expect(entries.map((h) => [h.target, h.before, h.after])).toEqual([
        ['첨부 파일', '', `삭제 ${name}`],
        ['첨부 파일', '', `교체 ${name}`],
        ['첨부 파일', '', `업로드 ${name}`],
      ])
      expect(Date.parse((await sales.deals.get(deal.code)).updatedAt)).toBeGreaterThanOrEqual(Date.parse(before))
      await sales.deals.remove(deal.code, deal.code)
    })

    // 규칙 위반은 서버 순서의 첫 위반만 알리고 아무것도 저장하지 않는다.
    // 테스트 코드: AT-006, AT-008, AT-013
    it('규칙 위반은 서버 순서의 첫 위반만 알리고 아무것도 저장하지 않는다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 없는 Deal이 설명·이름 위반보다 먼저 404다
      await expectRejects(put(sales, '20000101-ZZZZ', 'a/b.exe', { description: 'x'.repeat(101) }), 404, 'Deal을 찾을 수 없습니다.')
      // when·then: 설명 길이 → 차단 확장자 → 쓸 수 없는 이름 순으로 첫 위반만 알린다
      await expectRejects(put(sales, deal.code, 'a/b.exe', { description: 'x'.repeat(101) }), 422, '설명은 100자 이내로 입력하세요.')
      await expectRejects(put(sales, deal.code, 'a/b.exe'), 422, '실행·설치 파일(.exe)은 업로드할 수 없습니다.')
      await expectRejects(put(sales, deal.code, 'a/b.pdf'), 422, '사용할 수 없는 파일 이름입니다.')
      // then: 목록과 이력에 아무것도 남지 않는다
      expect(await sales.attachments.list(deal.code)).toEqual([])
      expect((await sales.history.list(deal.code, {})).some((h) => h.category === 'attachment')).toBe(false)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 차단 확장자는 끝 공백·점을 걷고 대소문자 없이 판정하며 문구는 소문자 확장자다.
    // 테스트 코드: AT-009
    it.each(['setup.exe', 'SETUP.EXE', 'setup.exe ', 'setup.exe.', 'setup.EXE . ', 'tool.vbs', 'app.appimage'])(
      '실행 파일 이름 %j은 차단 확장자로 거절한다',
      async (name) => {
        // given: 새 Deal과 기대하는 소문자 확장자
        const sales = await make('sales')
        const deal = await newDeal(sales)
        const extension = name.trim().replace(/[\s.]+$/, '').split('.').pop()?.toLowerCase() ?? ''

        // when·then: 그 이름으로 올리면 소문자 확장자가 든 422 문구다
        await expectRejects(put(sales, deal.code, name), 422, `실행·설치 파일(.${extension})은 업로드할 수 없습니다.`)

        await sales.deals.remove(deal.code, deal.code)
      },
    )

    // 쓸 수 없는 파일 이름은 서버 문구의 422다.
    // 테스트 코드: AT-010
    it.each(['a/b.pdf', 'a\\b.pdf', '..', 'a\tb.pdf', '견적\u202egpj.pdf', 'x\u2066y.pdf', 'a'.repeat(256)])(
      '쓸 수 없는 파일 이름 %j은 서버 문구의 422로 거절한다',
      async (name) => {
        // given: 새 Deal
        const sales = await make('sales')
        const deal = await newDeal(sales)

        // when·then: 그 이름으로 올리면 "사용할 수 없는 파일 이름입니다." 422다
        await expectRejects(put(sales, deal.code, name), 422, '사용할 수 없는 파일 이름입니다.')

        await sales.deals.remove(deal.code, deal.code)
      },
    )

    // user는 목록·다운로드는 되지만 업로드는 403이다.
    // 테스트 코드: AT-016, AT-026, AT-030
    it('user 역할은 목록과 다운로드는 되고 업로드는 403이다', async () => {
      // given: sales가 올린 파일이 있는 Deal과 user 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'readable.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const user = await make('user')

      // when·then: user가 목록과 다운로드를 하면 파일이 보이고 내려받아진다
      expect((await user.attachments.list(deal.code)).map((a) => a.fileName)).toEqual(['readable.pdf'])
      expect((await user.attachments.download(uploaded.attachment.id)).fileName).toBe('readable.pdf')
      // when·then: user가 업로드하면 403이다
      await expectRejects(put(user, deal.code, 'new.pdf'), 403)

      // then: 목록은 그대로 하나다
      const again = await make('sales')
      expect(await again.attachments.list(deal.code)).toHaveLength(1)
      await again.deals.remove(deal.code, deal.code)
    })

    // 없는 Deal의 목록과 없는 첨부의 다운로드는 404다.
    // 테스트 코드: AT-028, AT-033
    it('없는 Deal의 목록과 없는 id의 다운로드는 404다', async () => {
      // given: sales 세션
      const sales = await make('sales')

      // when·then: 없는 Deal의 목록은 Deal 404다
      await expectRejects(sales.attachments.list('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
      // when·then: 없는 id의 다운로드는 첨부 404다
      await expectRejects(sales.attachments.download(NO_SUCH_ID), 404, NOT_FOUND)
    })

    // 업로더가 지우면 목록과 다운로드에서 사라진다.
    // 테스트 코드: AT-036
    it('업로더가 지우면 목록과 다운로드에서 사라진다', async () => {
      // given: sales가 올린 파일
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'gone.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')

      // when: 업로더가 그 파일을 지운다
      await sales.attachments.remove(uploaded.attachment.id)

      // then: 목록이 비고 다운로드·재삭제는 404다
      expect(await sales.attachments.list(deal.code)).toEqual([])
      await expectRejects(sales.attachments.download(uploaded.attachment.id), 404, NOT_FOUND)
      await expectRejects(sales.attachments.remove(uploaded.attachment.id), 404, NOT_FOUND)
      await sales.deals.remove(deal.code, deal.code)
    })

    // admin은 sales가 올린 파일도 지울 수 있다.
    // 테스트 코드: AT-037
    it('admin은 sales가 올린 파일도 지울 수 있다', async () => {
      // given: sales가 올린 파일과 admin 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'by-sales.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const admin = await make('admin')

      // when: admin이 그 파일을 지운다
      await admin.attachments.remove(uploaded.attachment.id)

      // then: 목록이 비어 있다
      expect(await admin.attachments.list(deal.code)).toEqual([])
      await admin.deals.remove(deal.code, deal.code)
    })

    // user의 삭제는 없는 id여도 403이고 sales의 없는 id는 404다.
    // 테스트 코드: AT-038
    it('user의 삭제는 없는 id여도 같은 403이고 sales의 없는 id 삭제는 404다', async () => {
      // given: sales가 올린 파일과 user 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'keep.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      const user = await make('user')

      // when·then: user는 없는 id와 있는 id 모두 같은 403 문구를 받는다
      const unknown = await expectRejects(user.attachments.remove(NO_SUCH_ID), 403)
      const existing = await expectRejects(user.attachments.remove(uploaded.attachment.id), 403)
      expect(unknown.message).not.toBe('본인이 올린 파일만 삭제할 수 있습니다.')
      expect(existing.message).toBe(unknown.message)

      // when·then: sales가 없는 id를 지우면 404이고 파일은 그대로다
      const again = await make('sales')
      await expectRejects(again.attachments.remove(NO_SUCH_ID), 404, NOT_FOUND)
      expect(await again.attachments.list(deal.code)).toHaveLength(1)
      await again.deals.remove(deal.code, deal.code)
    })

    // Deal을 지우면 첨부도 함께 지워지고 삭제 영향의 첨부 수는 현재 행 수다.
    // 테스트 코드: AT-040
    it('Deal을 지우면 첨부가 함께 지워지고 삭제 영향의 첨부 수는 현재 첨부 수다', async () => {
      // given: 첨부 하나가 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const uploaded = await put(sales, deal.code, 'with-deal.pdf')
      if (uploaded.outcome !== 'uploaded') throw new Error('expected uploaded')
      // then: 삭제 영향의 첨부 수가 1이다
      expect((await sales.deals.impact(deal.code)).attachmentCount).toBe(1)

      // when: Deal을 지운다
      await sales.deals.remove(deal.code, deal.code)

      // then: 첨부 다운로드가 404다
      await expectRejects(sales.attachments.download(uploaded.attachment.id), 404, NOT_FOUND)
    })
  })
}
