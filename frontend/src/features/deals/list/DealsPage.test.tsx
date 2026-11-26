import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, rowOf } from './testHelpers'

const HEADERS = ['Deal', '담당자', 'Vendor', 'Forecast', '금액(단위:원)', 'Expected Close', '최종 업데이트', 'Next Action', 'Due Date', 'Next Action 상태']

afterEach(() => vi.restoreAllMocks())

describe('목록 표 (T-LIST-01~04)', () => {
  // 표는 PRD 열과 분리된 Next Action 열을 보인다
  // 테스트 코드: DL-058
  it('shows the PRD columns with the split Next Action columns', async () => {
    // given: 시드 Deal이 있는 목록
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: /deals?year=all을 연다
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())

    expect(headers).toEqual(HEADERS)
  })

  // 테스트 코드: DL-058
  it('places the owner before Vendor and aligns row cells with the headers', async () => {
    // given: 시드 Deal이 있는 목록
    await renderAt('/deals?q=누리통신 MFA')
    const row = await rowOf(/누리통신 MFA/)

    // when: /deals?year=all을 연다
    const cells = within(row).getAllByRole('cell')

    // then: 머리글과 첫 행의 칸 순서가 같다
    expect(cells).toHaveLength(HEADERS.length)
    expect(cells[HEADERS.indexOf('담당자')]).toHaveTextContent('이영업')
    expect(cells[HEADERS.indexOf('Vendor')]).toHaveTextContent('Silverfort')
  })

  // Vendor가 없는 Deal의 Vendor 칸은 '—'다
  // 테스트 코드: DL-058
  it('shows a dash in the Vendor cell of a deal without a vendor', async () => {
    // given: 서버 응답에서 Vendor가 null인 Deal 행(Vendor는 필수라 Fake로는 만들 수 없어 응답을 바꿔 받는다)
    const list = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => {
      const result = await list(query)
      return { ...result, items: result.items.map((item) => ({ ...item, vendor: null })) }
    })

    // when: 목록을 연다
    await renderAt('/deals?q=누리통신 MFA')

    // then: Vendor 칸에 '—'가 보인다
    await waitFor(() => expect(within(screen.getByRole('row', { name: /누리통신 MFA/ })).getAllByRole('cell')[HEADERS.indexOf('Vendor')]).toHaveTextContent(/^—$/))
  })

  // 한 페이지 20건이고 나머지는 둘째 페이지에 보인다
  // 테스트 코드: DL-061
  it('shows twenty deals on the first page and the rest on the second', async () => {
    // given: Deal이 20건을 넘는 목록
    const { user, location } = await renderAt(ALL_DEALS)

    // when: 1페이지를 본다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // then: 1페이지는 20행이다
    expect(dataRows()).toHaveLength(20)
    // when: 다음 페이지로 간다
    await user.click(screen.getByRole('button', { name: '다음' }))
    // then: 2페이지에 나머지가 보인다
    expect(location()).toBe('/deals?year=all&page=2')
    await screen.findByRole('button', { name: '이전' })
    expect(dataRows()).toHaveLength(4)
    // when: 이전 페이지로 돌아간다
    await user.click(screen.getByRole('button', { name: '이전' }))
    // then: 1페이지 주소로 돌아온다
    expect(location()).toBe('/deals?year=all')
  })

  // 테스트 코드: DL-058
  it('shows the owner and formatted amount without separate company cells', async () => {
    // given: 활성·해제 파트너가 섞인 Deal
    await renderAt('/deals?q=누리통신 MFA')

    // when: 목록을 연다
    const row = await rowOf(/누리통신 MFA/)

    expect(within(row).queryByText('누리통신')).not.toBeInTheDocument()
    expect(within(row).queryByText('에이원시스템')).not.toBeInTheDocument()
    expect(within(row).queryByText('코어테크')).not.toBeInTheDocument()
    expect(within(row).getByText('이영업')).toBeVisible()
    expect(within(row).getByText('330,000,000')).not.toHaveAttribute('title')
  })

  // 테스트 코드: DL-058
  it('shows the resigned owner label', async () => {
    await renderAt('/deals?q=한빛은행 PAM')
    expect(within(await rowOf(/한빛은행 PAM/)).getByText('강퇴사(퇴사)')).toBeVisible()
  })

  // 기한초과·미업데이트·둘 다 Deal을 배지 텍스트와 행 클래스로 구분한다.
  // 테스트 코드: RK-051
  // 기한초과·미업데이트·둘 다는 배지 문구와 행 클래스로 표시한다(RK 판정을 목록에 보임)
  it('marks overdue, not-updated and both with badge text and row classes', async () => {
    // given: 시드에 기한초과, 미업데이트, 둘 다인 Deal이 있다
    await renderAt('/deals?q=미래전자 EDR')

    // when: 각 Deal이 나오도록 목록을 연다
    const overdue = await rowOf(/미래전자 EDR 교체/)
    // then: 기한초과 행은 '기한초과'만·risk-overdue, 미업데이트 행은 '미업데이트'만·risk-stale, 둘 다는 두 배지가 보인다
    expect(within(overdue).getByText('기한초과')).toBeVisible()
    expect(within(overdue).queryByText('미업데이트')).not.toBeInTheDocument()
    expect(overdue).toHaveClass('risk-overdue')
    cleanup()

    await renderAt('/deals?q=새론병원 PAM')
    const stale = await rowOf(/새론병원 PAM/)
    expect(within(stale).getByText('미업데이트')).toBeVisible()
    expect(within(stale).queryByText('기한초과')).not.toBeInTheDocument()
    expect(stale).toHaveClass('risk-stale')
    cleanup()

    await renderAt('/deals?q=하늘카드 AD')
    const both = await rowOf(/하늘카드 AD 보안 강화/)
    expect(within(both).getByText('기한초과')).toBeVisible()
    expect(within(both).getByText('미업데이트')).toBeVisible()
  })

  // 정상 Deal과 종결 Deal에는 경고 배지와 클래스가 없다.
  // 테스트 코드: RK-051
  // 정상 Deal과 종결 Deal에는 경고 표시가 없다(RK)
  it('shows no risk on a healthy deal and on closed deals', async () => {
    // given: 경고가 없는 Deal과 Won Deal이 있다
    await renderAt('/deals?q=대한제조 MFA')

    // when: 각 Deal이 나오도록 목록을 연다
    const healthy = await rowOf(/대한제조 MFA 확대/)
    // then: 배지도 risk-overdue 클래스도 없다
    expect(within(healthy).queryByText('기한초과')).not.toBeInTheDocument()
    expect(within(healthy).queryByText('미업데이트')).not.toBeInTheDocument()
    cleanup()

    await renderAt('/deals?q=청명대학교 SSO')
    const won = await rowOf(/청명대학교 SSO\/MFA/)
    expect(won).not.toHaveClass('risk-overdue')
    expect(within(won).queryByText('기한초과')).not.toBeInTheDocument()
  })

  // 범례가 경고 색을 텍스트로 설명한다.
  // 테스트 코드: RK-052, RK-078
  // 경고 색을 색만이 아니라 범례 문구로 설명한다(RK)
  it('explains the risk colors with a legend, not by color alone', async () => {
    // when: Deals 목록을 연다 (전제: 경고 범례)
    await renderAt(ALL_DEALS)
    const legend = await screen.findByRole('list', { name: 'Risk 범례' })
    // then: 범례에 '기한초과' 배지와 '14일 이상 미업데이트'가 보인다
    expect(within(legend).getByText('기한초과')).toBeVisible()
    expect(await within(legend).findByText('14일 이상 미업데이트')).toBeVisible()
    // then: 기한초과 설명은 Open인 Next Action의 Due Date 기준이다
    expect(within(legend).getByText('Open인 Next Action의 Due Date가 지났습니다')).toBeVisible()
  })

  // Deal 이름은 상세 화면 링크다
  // 테스트 코드: DL-058
  it('links the deal name to its detail page', async () => {
    // given: 시드 Deal
    await renderAt('/deals?q=한빛은행 ITDR')

    // when: 목록을 연다
    const link = await screen.findByRole('link', { name: '한빛은행 ITDR 도입' })

    // then: 이름 링크의 주소가 /deals/<code>이다
    expect(link.getAttribute('href')).toMatch(/^\/deals\/\d{8}-[A-Z0-9]{4}$/)
  })
})

describe('빠른 보기 (T-LIST-10)', () => {
  // 빠른 보기가 견적·POC·고객 담당자·파트너 영업대표·BANT를 행 아래에 펼친다
  // 테스트 코드: DL-091
  it('expands quote, POC, customer contact, partner sales rep and BANT under the row', async () => {
    // given: 시드 Deal 행
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)

    const toggle = within(row).getByRole('button', { name: /빠른 보기/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // when: 빠른 보기 토글을 누른다
    await user.click(toggle)
    // then: 견적·POC·고객 담당자·파트너 영업대표가 행 아래에 보인다
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const view = screen.getByRole('region', { name: /빠른 보기.*한빛은행 ITDR 도입/ })
    expect(within(view).getByText('견적')).toBeVisible()
    expect(within(view).getByText('POC')).toBeVisible()
    expect(within(view).getByText('고객 담당자')).toBeVisible()
    expect(within(view).getByText(/정민수/)).toBeVisible()
    expect(within(view).getByText('파트너 영업대표')).toBeVisible()
    expect(within(view).getByText(/표성호/)).toBeVisible()
    expect(within(view).getByText('단독 예산 확보')).toBeVisible()
    expect(within(view).getByText('조달청 경쟁 입찰')).toBeVisible()
    expect(within(view).getByRole('link', { name: '상세 보기' })).toBeVisible()
    // when: 토글을 다시 누른다
    await user.click(toggle)
    // then: 빠른 보기가 접힌다
    expect(screen.queryByRole('region', { name: /빠른 보기/ })).not.toBeInTheDocument()
  })

  // 파트너 없는 Deal의 빠른 보기는 '파트너 없음'을 보인다
  // 테스트 코드: DL-091
  it('says there is no partner in the quick view of a deal without one', async () => {
    // given: 파트너 없는 Deal 행
    const { user } = await renderAt('/deals?q=대한제조 NGFW')
    const row = await rowOf(/대한제조 NGFW/)

    // when: 빠른 보기를 연다
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = screen.getByRole('region', { name: /빠른 보기/ })

    // then: '파트너 없음'이 보인다
    expect(within(view).getByText('파트너 없음')).toBeVisible()
  })
})

describe('권한 (T-LIST-11)', () => {
  // user에게는 등록 링크와 편집 버튼이 없다
  // 테스트 코드: DL-064
  it('gives a viewer the list without register or edit controls', async () => {
    // given: user 역할로 로그인
    await renderAt(ALL_DEALS, { role: 'user' })

    // when: 목록을 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: '+ Deal 등록' 링크와 편집 버튼이 없다
    expect(screen.queryByRole('link', { name: /Deal 등록/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /편집/ })).not.toBeInTheDocument()
  })

  // sales·admin에게는 등록 링크와 편집 버튼이 보인다
  // 테스트 코드: DL-093
  it.each(['sales', 'admin'] as const)('shows the register link and edit buttons to %s', async (role) => {
    // given: sales 또는 admin으로 로그인
    await renderAt(ALL_DEALS, { role })

    // when: 목록을 연다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: '+ Deal 등록' 링크와 편집 버튼이 보인다
    expect(screen.getByRole('link', { name: '+ Deal 등록' })).toHaveAttribute('href', '/deals/new')
    expect(screen.getAllByRole('button', { name: /Forecast 편집/ }).length).toBeGreaterThan(0)
  })
})
