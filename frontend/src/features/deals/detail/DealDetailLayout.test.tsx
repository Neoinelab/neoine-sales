import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { kvPairs, kvValue } from '../../../test/kvPairs'
import type { TestRole } from '../../../test/mockApp'

async function openDetail(no: number, title: string, role?: TestRole) {
  const view = await renderAt(await detailPath(no), role === undefined ? {} : { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

/** dl 안의 dt/dd를 [라벨, 값] 쌍으로 읽는다. */
const pairsOf = kvPairs

const INFO_LABELS = [
  'Deal code',
  'Owner',
  'Status',
  'Forecast',
  '금액(단위:원)',
  'Expected Close',
  'Next Action',
  '최종 업데이트',
  'Vendor',
  'Product',
  'Users count',
  '견적',
  'POC',
  '구매절차',
  '등록일',
]

const infoTile = () => screen.getByRole('region', { name: 'Deal 정보' })

describe('Deal 정보 타일 (상단 통합 영역)', () => {
  // Deal 정보 타일은 다른 타일처럼 제목이 있고 Vendor·Product·Users·견적·POC·구매절차를 보인다.
  // 테스트 코드: DD-066
  it('shows a deal info tile titled like the other tiles with vendor, product, users, quote, poc and procurement', async () => {
    // given: Vendor·Product·견적·POC가 있는 Deal
    await openDetail(1, '한빛은행 ITDR 도입')
    const heading = screen.getByRole('heading', { level: 2, name: 'Deal 정보' })
    // when: Deal 상세를 연다
    const bar = infoTile()
    // then: 'Deal 정보' 제목이 타일의 첫 제목이고 '현재 값' 영역은 없다
    expect(within(bar).getAllByRole('heading')[0]).toBe(heading)
    expect(screen.queryByRole('region', { name: '현재 값' })).not.toBeInTheDocument()
    const facts = Object.fromEntries(pairsOf(bar))
    expect(facts['Vendor']).toBe('Silverfort')
    expect(facts['Product']).toBe('ITDR')
    expect(facts['Users count']).toBe('1500')
    expect(facts['견적']).toMatch(/^제출/)
    expect(facts['POC']).toMatch(/^YES · 완료/)
    expect(facts['구매절차']).toBe('조달청 경쟁 입찰')
  })

  // Status·Forecast 편집 버튼이 다른 항목과 같은 Deal 정보 타일 안에 있다.
  // 테스트 코드: DD-066
  it('keeps status and forecast editors in the same top area as the facts', async () => {
    // given: 가격협상·Commit Deal
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const bar = infoTile()
    // then: Status·Forecast 버튼과 Vendor 항목이 같은 타일 안에 보인다
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('가격협상')
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit')
    expect(within(bar).getByText('Vendor')).toBeVisible()
  })

  // Owner와 Deal code는 머리가 아니라 Deal 정보 타일에 있다.
  // 테스트 코드: DD-066
  it('shows the owner and the deal code in the deal info tile, not in the header', async () => {
    // given: Deal 하나
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const header = screen.getByRole('heading', { level: 1 }).closest('header') as HTMLElement
    // then: 머리 글자에 Owner·Deal code가 없고 타일 항목에는 있다
    expect(header.textContent).not.toContain('Owner')
    expect(header.textContent).not.toContain('Deal code')
    const labels = pairsOf(infoTile()).map(([k]) => k)
    expect(labels).toContain('Owner')
    expect(labels).toContain('Deal code')
  })

  // Deal 정보 항목은 Deal code부터 등록일까지 정해진 순서다.
  // 테스트 코드: DD-066
  it('orders the deal info items from deal code and owner to the registration date', async () => {
    // given: Deal 하나
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const tile = infoTile()
    // then: 하나의 목록에 15개 항목이 문서 순서로 있다
    expect(tile.querySelectorAll('dl')).toHaveLength(1)
    expect(pairsOf(tile).map(([k]) => k)).toEqual(INFO_LABELS)
  })

  // Deal 정보·고객·파트너·BANT 타일이 2단계 제목과 함께 이 순서로 있다.
  // 테스트 코드: DD-066, DD-068
  it('titles the four tiles with level two headings in order', async () => {
    // given: Deal 하나
    await openDetail(1, '한빛은행 ITDR 도입')
    const names = ['Deal 정보', '고객', '파트너', 'BANT']
    // when: Deal 상세를 연다
    const tiles = names.map((name) => screen.getByRole('region', { name }))
    // then: 네 타일의 첫 요소가 h2이고 화면 순서가 맞다
    tiles.forEach((tile, i) => {
      const first = tile.firstElementChild as HTMLElement
      expect(first.tagName).toBe('H2')
      expect(first).toHaveTextContent(names[i] as string)
      const next = tiles[i + 1]
      if (next) expect(tile.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  // Deal code는 편집 버튼 없는 글자다.
  // 테스트 코드: DD-066
  it('shows the deal code as plain text without an edit button', async () => {
    // given: sales 사용자
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const code = kvValue(infoTile(), 'Deal code')
    // then: Deal code 값에 버튼이 없다
    expect(code.textContent).toMatch(/^\S+-D001$/)
    expect(screen.queryByRole('button', { name: 'Deal code 수정' })).not.toBeInTheDocument()
    expect(within(code).queryByRole('button')).not.toBeInTheDocument()
  })

  // Owner를 타일 안에서 선택해 바꾸면 알림이 보이고 이력에 남는다.
  // 테스트 코드: DD-079
  it('edits the owner in place inside the deal info tile', async () => {
    // given: sales 사용자와 Owner 후보
    const { user } = await openDetail(1, '한빛은행 ITDR 도입')
    // when: Owner 버튼을 눌러 다른 영업을 고른다
    await user.click(within(infoTile()).getByRole('button', { name: 'Owner 수정' }))
    await user.selectOptions(within(infoTile()).getByLabelText('Owner'), '박영업')
    // then: Owner 값이 바뀌고 'Owner가 변경되었습니다.' 알림과 Owner 이력이 있다
    await waitFor(() => expect(within(infoTile()).getByRole('button', { name: 'Owner 수정' })).toHaveTextContent('박영업'))
    expect(await screen.findByText('Owner가 변경되었습니다.')).toBeVisible()
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: Owner 이력 행이 보인다
    expect(await screen.findByRole('cell', { name: 'Owner' })).toBeVisible()
  })

  // user에게 Owner는 편집 버튼 없는 글자다.
  // 테스트 코드: DD-073
  it('shows the owner as plain text for a viewer', async () => {
    // given: user 역할 사용자
    await openDetail(1, '한빛은행 ITDR 도입', 'user')
    // when: Deal 상세를 연다
    const owner = kvValue(infoTile(), 'Owner')
    // then: Owner 값이 글자로만 보이고 편집 버튼이 없다
    expect(owner).toHaveTextContent(/^김영업$/)
    expect(screen.queryByRole('button', { name: 'Owner 수정' })).not.toBeInTheDocument()
  })

  // user의 읽기 전용 값도 편집 버튼과 같은 상자 모양이다.
  // 테스트 코드: DD-073
  it('wraps every read-only value of a viewer in the same box as the edit button', async () => {
    // when: Deal 상세를 연다 (전제: user 역할 사용자)
    await openDetail(1, '한빛은행 ITDR 도입', 'user')
    // then: Owner·Vendor·Budget 값이 kv-static 상자 안에 있다
    expect(kvValue(infoTile(), 'Owner').firstElementChild).toHaveClass('kv-static')
    expect(kvValue(infoTile(), 'Vendor').firstElementChild).toHaveClass('kv-static')
    expect(kvValue(screen.getByRole('region', { name: 'BANT' }), 'Budget').firstElementChild).toHaveClass('kv-static')
  })

  // 머리에는 Deal 이름, 목록 링크, 삭제 버튼만 있다.
  // 테스트 코드: DD-070
  it('keeps the header to the deal name and the list and delete buttons', async () => {
    // given: sales 사용자
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const header = screen.getByRole('heading', { level: 1 }).closest('header') as HTMLElement
    // then: 머리에 Deal code·Owner가 없고 조작은 이름 편집·'Deal 삭제'·'← 목록'뿐이다
    expect(header.textContent).not.toContain('Deal code')
    expect(header.textContent).not.toContain('Owner')
    const controls = Array.from(header.querySelectorAll('a, button')).map((el) => el.getAttribute('title') === 'Deal 이름 수정' ? 'title' : (el.getAttribute('aria-label') ?? el.textContent ?? '').trim())
    expect(controls.sort()).toEqual(['title', 'Deal 삭제', '← 목록'].sort())
  })
})

describe('고객 · 파트너 · BANT 타일 (라벨-값 한 줄 격자)', () => {
  // 고객·파트너·BANT 카드가 이 순서로 같은 부모 안에 있다.
  // 테스트 코드: DD-068
  it('renders the three tiles in DOM order customer, partner, BANT', async () => {
    // given: Deal 하나
    await openDetail(1, '한빛은행 ITDR 도입')
    const tiles = ['고객', '파트너', 'BANT'].map((name) => screen.getByRole('region', { name }))
    // when: Deal 상세를 연다
    const [customer, partner, bant] = tiles as [HTMLElement, HTMLElement, HTMLElement]
    // then: 세 카드의 DOM 순서가 고객, 파트너, BANT다
    expect(customer.compareDocumentPosition(partner) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(partner.compareDocumentPosition(bant) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(customer.parentElement).toBe(bant.parentElement)
  })

  // 고객·파트너 카드는 회사·담당자·직급·이메일·전화 5행의 이름-값 쌍이다.
  // 테스트 코드: DD-068
  it('renders customer and partner contents as label-value pairs', async () => {
    // given: 고객 한빛은행, 파트너 에이원시스템 Deal
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const customer = pairsOf(screen.getByRole('region', { name: '고객' }))
    // then: 두 카드의 항목 이름이 회사·담당자·직급·이메일·전화이고 고객 회사·담당자 값은 한빛은행·정민수다
    expect(customer.map(([k]) => k)).toEqual(['회사', '담당자', '직급', '이메일', '전화'])
    expect(customer.map(([, v]) => v).slice(0, 2)).toEqual(['한빛은행', '정민수'])
    const partner = pairsOf(screen.getByRole('region', { name: '파트너' }))
    expect(partner.map(([k]) => k)).toEqual(['회사', '담당자', '직급', '이메일', '전화'])
    expect(partner.map(([, v]) => v).slice(0, 1)).toEqual(['에이원시스템'])
  })

  // BANT 카드는 네 항목의 이름-값 쌍이고 값마다 클릭 편집 버튼이 있다.
  // 테스트 코드: DD-068
  it('renders the four BANT items as label-value pairs with a click-to-edit value each', async () => {
    // given: BANT가 있는 Deal
    await openDetail(1, '한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const bant = screen.getByRole('region', { name: 'BANT' })
    // then: Budget·Authority·Need·Timeline 네 행과 수정 버튼이 있다
    expect(pairsOf(bant).map(([k]) => k)).toEqual(['Budget', 'Authority', 'Need', 'Timeline'])
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보')
  })
})

describe('모든 타일의 dt dd 구조와 연락처 편집 세션', () => {
  // 네 타일의 모든 항목이 한 행 안의 dt·dd 쌍이다(구조, BDD 밖).
  it('renders every item of the four tiles as a dt dd pair in one row element', async () => {
    // when: Deal 상세를 연다 (전제: Deal 하나)
    await openDetail(1, '한빛은행 ITDR 도입')
    // then: 항목마다 kv-row 안에 dt, dd 순서로 있다
    for (const name of ['Deal 정보', '고객', '파트너', 'BANT']) {
      const tile = screen.getByRole('region', { name })
      const dl = tile.querySelector('dl') as HTMLElement
      const terms = Array.from(dl.querySelectorAll('dt'))
      expect(terms.length).toBeGreaterThan(0)
      for (const dt of terms) {
        const row = dt.parentElement as HTMLElement
        expect(row.classList.contains('kv-row')).toBe(true)
        expect(row.children[0]).toBe(dt)
        expect(row.children[1]?.tagName).toBe('DD')
        expect(row.parentElement).toBe(dl)
      }
    }
  })

  // 연락처 편집 세션은 짧은 라벨의 행으로 보이고 회사명 입력에 포커스가 간다.
  // 테스트 코드: DD-087
  it('shows the contact edit session as label rows with short visible labels', async () => {
    // given: sales 사용자
    const { user } = await openDetail(1, '한빛은행 ITDR 도입')
    const customer = () => screen.getByRole('region', { name: '고객' })
    // when: 고객 회사명 버튼을 누른다
    await user.click(within(customer()).getByRole('button', { name: '고객 회사명 수정' }))
    // then: 회사명 입력에 포커스가 있고 다섯 입력의 보이는 라벨이 회사·담당자·직급·이메일·전화다
    expect(within(customer()).getByRole('combobox', { name: '고객 회사명' })).toHaveFocus()
    const visible = [
      ['고객 회사명', '회사'],
      ['고객 담당자명', '담당자'],
      ['고객 직급', '직급'],
      ['고객 이메일', '이메일'],
      ['고객 전화', '전화'],
    ] as const
    for (const [accessible, shown] of visible) {
      // 회사명 입력에 포커스가 있으면 같은 이름의 목록(listbox)도 열려 있으므로 input만 고른다.
      const input = within(customer()).getAllByLabelText(accessible).find((el): el is HTMLInputElement => el instanceof HTMLInputElement)
      if (!input) throw new Error(`${accessible} 입력이 없습니다.`)
      expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain(shown)
    }
  })
})
