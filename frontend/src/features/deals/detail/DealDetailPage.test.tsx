import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { kvValue } from '../../../test/kvPairs'

async function heading(name: string) {
  return screen.findByRole('heading', { level: 1, name })
}

describe('Deal 상세 상단 (T-DETAIL-01)', () => {
  // Deal 정보 타일에 Status·Forecast·금액·Expected Close·Next Action 현재 값이 보인다.
  // 테스트 코드: DD-066
  it('shows the latest status, forecast, amount, expected close and next action in the summary bar', async () => {
    // given: 가격협상·Commit Deal
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    // then: Status·Forecast 버튼 값, 금액, Next Action, Expected Close 행이 보인다
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('가격협상')
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit')
    expect(within(bar).getByText('1,870,000,000')).toBeVisible()
    expect(within(bar).getByText(/계약서 초안 검토/)).toBeVisible()
    expect(within(bar).getByText('Expected Close')).toBeVisible()
  })

  // Deal 정보 타일 안에 Deal code와 Owner가 글자로 보인다.
  // 테스트 코드: DD-066
  it('shows the deal code and the owner inside the deal info tile', async () => {
    // given: Owner 김영업의 Deal
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const info = screen.getByRole('region', { name: 'Deal 정보' })
    // when: Deal 상세를 연다
    const code = kvValue(info, 'Deal code').textContent ?? ''
    // then: Deal code(-D001로 끝남)와 Owner 이름이 행 값으로 보인다
    expect(code).toMatch(/-D001$/)
    expect(code.startsWith('Deal code:')).toBe(false)
    expect(kvValue(info, 'Owner')).toHaveTextContent(/^김영업$/)
  })

  // 퇴사한 Owner는 '이름(퇴사)'로 보인다.
  // 테스트 코드: DD-069
  it('shows a resigned owner as 이름(퇴사)', async () => {
    // given: Owner가 퇴사한 Deal
    await renderAt(await detailPath(23))
    // when: Deal 상세를 연다
    await heading('한빛은행 PAM')
    // then: Owner 값이 '강퇴사(퇴사)'다
    expect(kvValue(screen.getByRole('region', { name: 'Deal 정보' }), 'Owner')).toHaveTextContent(/^강퇴사\(퇴사\)$/)
  })

  // 기한초과·미업데이트 Deal은 경고 배지 둘을 보인다(파생 값 표시는 RK).
  it('shows the risk badges of an overdue and stale deal', async () => {
    // given: 기한이 지나고 갱신이 없는 Deal
    await renderAt(await detailPath(7))
    await heading('하늘카드 AD 보안 강화')
    // when: Deal 상세를 연다
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    // then: '기한초과'와 '미업데이트' 배지가 보인다
    expect(within(bar).getByText('기한초과')).toBeVisible()
    expect(within(bar).getByText('미업데이트')).toBeVisible()
  })

  // Won Deal에는 Won 종결 안내가 보인다.
  // 테스트 코드: DD-067
  it('marks a won deal as closed and a lost deal as lost', async () => {
    // given: Forecast가 Won인 Deal
    await renderAt(await detailPath(11))
    // when: Deal 상세를 연다
    await heading('청명대학교 SSO/MFA')
    // then: 'Won으로 종결된 Deal입니다' 안내가 보인다
    expect(screen.getByText(/Won으로 종결된 Deal입니다/)).toBeVisible()
  })

  // Lost Deal에는 Lost 종결 안내가 보인다.
  // 테스트 코드: DD-067
  it('marks a lost deal', async () => {
    // given: Forecast가 Lost인 Deal
    await renderAt(await detailPath(16))
    // when: Deal 상세를 연다
    await heading('새론병원 SSO')
    // then: 'Lost로 종결된 Deal입니다' 안내가 보인다
    expect(screen.getByText(/Lost로 종결된 Deal입니다/)).toBeVisible()
  })
})

describe('Deal 상세 정보 카드 (T-DETAIL-02)', () => {
  // 고객 카드에 회사·담당자·직급·이메일·전화가 보인다.
  // 테스트 코드: DD-068
  it('shows the customer contact with title, email and phone', async () => {
    // given: 고객 연락처가 있는 Deal
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const card = screen.getByRole('region', { name: '고객' })
    // then: 고객 카드 5행에 값이 보인다
    expect(within(card).getByText('한빛은행')).toBeVisible()
    expect(within(card).getByText('정민수')).toBeVisible()
    expect(within(card).getByText('과장')).toBeVisible()
  })

  // 활성 파트너만 보이고 교체된 파트너는 접힌 '이전 파트너 이력' 안에 있다.
  // 테스트 코드: DD-068
  it('shows only the active partner and hides the replaced one inside a collapsed history', async () => {
    // given: 파트너가 교체된 Deal
    await renderAt(await detailPath(17))
    await heading('누리통신 MFA')
    // when: Deal 상세를 연다
    const card = screen.getByRole('region', { name: '파트너' })
    // then: 활성 파트너만 카드에 보이고 이전 파트너는 접힌 이력 안에 연결·해제일과 함께 있다
    expect(within(card).getAllByText('에이원시스템')[0]).toBeVisible()
    const history = within(card).getByText(/이전 파트너 이력/)
    expect(history.closest('details')).not.toHaveAttribute('open')
    expect(within(card).getByText(/코어테크/)).not.toBeVisible()
  })

  // 파트너가 없으면 '파트너 없음' 글자 없이 5행이 모두 '—'다.
  // 테스트 코드: DD-068
  it('shows em dashes instead of a "no partner" text when the deal has none', async () => {
    // given: 파트너가 없는 Deal
    await renderAt(await detailPath(5))
    await heading('누리통신 NGFW 갱신')
    // when: Deal 상세를 연다
    const card = screen.getByRole('region', { name: '파트너' })
    // then: 파트너 카드에 '—' 5개가 있고 '파트너 없음' 글자는 없다
    expect(within(card).queryByText('파트너 없음')).not.toBeInTheDocument()
    expect(within(card).getAllByText('—')).toHaveLength(5)
  })

  // BANT 카드에 네 구분 Label이 보이고 견적·POC·구매절차도 보인다.
  // 테스트 코드: DD-068
  it('shows the four BANT labels, the quote, the POC and the procurement', async () => {
    // given: BANT·견적·POC·구매절차가 있는 Deal
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // when: Deal 상세를 연다
    const bant = screen.getByRole('region', { name: 'BANT' })
    // then: BANT 네 행의 Label과 나머지 항목 값이 보인다
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보')
    expect(within(bant).getByRole('button', { name: 'Authority 수정' })).toHaveTextContent('CISO 보고 완료')
    expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('보안 강화 요건')
    expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('금년 구매')
    const info = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(info).getByText(/조달청 경쟁 입찰/)).toBeVisible()
    expect(within(info).getByText('견적')).toBeVisible()
    expect(within(info).getByText('POC')).toBeVisible()
  })

  // 쓰기 권한자는 BANT Label을 자동완성 입력에서 비워 '선택 안 함'으로 바꾸고 이력에 남긴다.
  // 테스트 코드: DD-086
  it('lets a writer clear a BANT label with the autocomplete and records it in the history', async () => {
    // given: Budget Label이 선택된 Deal과 sales 사용자
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const bant = screen.getByRole('region', { name: 'BANT' })
    // when: Budget 값을 비우고 확정한다
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.keyboard('{Enter}')
    // then: 값이 '—'로 바뀐다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))

    // when: Deal History 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))

    // then: BANT 이력이 남아 있다
    expect(await screen.findByRole('cell', { name: 'BANT Label: Timeline' })).toBeVisible()
  })

  // BANT 자동완성에 새 이름을 입력하고 Enter로 저장하면 그 Label이 선택된다.
  // 테스트 코드: DD-085
  it('saves a typed new BANT label with Enter and selects it', async () => {
    // given: 대한제조 MFA 확대 Deal의 BANT 카드
    const { user } = await renderAt(await detailPath(2))
    await heading('대한제조 MFA 확대')
    const bant = screen.getByRole('region', { name: 'BANT' })
    // when: Need에 '신규 요건'을 입력하고 Enter를 누른다
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.type(within(bant).getByRole('combobox', { name: 'Need' }), '신규 요건{Enter}')
    // then: Need가 '신규 요건'으로 바뀌고 'BANT Need Label이 변경되었습니다.' 알림이 보인다
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('신규 요건'))
    expect(await screen.findByText('BANT Need Label이 변경되었습니다.')).toBeVisible()
  })

  // 고객 직급을 그 자리에서 고치면 같은 카드의 다른 필드는 그대로다.
  // 테스트 코드: DD-092
  it('edits the customer contact with the contact picker and keeps the other fields', async () => {
    // given: 고객 연락처가 있는 Deal
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '고객' })
    await user.click(within(card).getByRole('button', { name: '고객 직급 수정' }))
    // given: 직급을 눌러 연 것도 5칸 연락처 편집 세션이고 직급 입력에 포커스가 있다
    const session = within(card).getByRole('group', { name: '고객 연락처 편집' })
    const title = within(session).getByLabelText('고객 직급')
    expect(title).toHaveFocus()
    // when: 고객 직급을 눌러 '팀장'으로 고치고 Enter를 누른다
    await user.clear(title)
    await user.type(title, '팀장')
    await user.keyboard('{Enter}')
    // then: 직급만 바뀌고 담당자 이름은 그대로다
    await waitFor(() => expect(within(card).getByText('팀장')).toBeVisible())
    expect(within(card).getByText('정민수')).toBeVisible()
  })

  // 파트너 교체는 기존 파트너가 비활성이 된다는 안내 뒤에 된다.
  // 테스트 코드: DD-095
  it('replaces the partner after warning that the current one becomes inactive', async () => {
    // given: 활성 파트너가 있는 Deal
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '파트너' })
    // when: 파트너 회사명 수정을 누른다
    await user.click(within(card).getByRole('button', { name: '파트너 회사명 수정' }))
    // then: 기존 파트너가 비활성이 된다는 안내 문구가 보인다
    expect(within(card).getByText(/이력으로 남고 비활성이 됩니다/)).toBeVisible()

    // when: 회사명을 코어테크로 바꾸고 담당자 민지훈을 고른다
    const company = within(card).getByRole('combobox', { name: '파트너 회사명' })
    await user.clear(company)
    await user.type(company, '코어테크')
    const person = within(card).getByRole('combobox', { name: '파트너 담당자명' })
    await user.clear(person)
    await user.type(person, '민지훈')
    await user.click(within(card).getByRole('option', { name: /민지훈/ }))
    // then: 새 파트너가 활성이며 교체 알림이 나온다
    await waitFor(() => expect(within(card).getAllByText('코어테크').length).toBeGreaterThan(0))
    expect(within(card).getByText(/이전 파트너 이력/)).toBeVisible()
  })

  // 활성 파트너를 확인 뒤 제거한다.
  // 테스트 코드: DD-096
  it('removes the active partner', async () => {
    // given: 활성 파트너가 있는 Deal
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '파트너' })
    // when: '파트너 제거'를 누르고 확인한다
    await user.click(within(card).getByRole('button', { name: '파트너 제거' }))
    await user.click(within(await screen.findByRole('dialog', { name: '파트너 제거' })).getByRole('button', { name: '제거' }))
    // then: 파트너 카드가 비고 제거 알림이 나온다
    await waitFor(() => expect(within(card).getAllByText('—')).toHaveLength(5))
    expect(within(card).queryByText('파트너 없음')).not.toBeInTheDocument()
  })
})

describe('Deal 상세 탭 (T-DETAIL-03)', () => {
  // 탭 3개가 Deal 상세, Actions, Deal History 순서이고 Deal 상세가 선택돼 있다.
  // 테스트 코드: DD-062
  it('has three tabs in order and starts on Deal 상세', async () => {
    // when: Deal 상세를 연다
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // then: 탭 목록이 세 탭 순서이고 Deal 상세만 선택 상태다
    const tabs = within(screen.getByRole('tablist', { name: '상세 탭' })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Deal 상세', 'Actions', 'Deal History'])
    expect(screen.getByRole('tab', { name: 'Deal 상세' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'false')
  })

  // Deal 정보·카드·첨부는 Deal 상세 탭에만 보인다.
  // 테스트 코드: DD-064
  it('shows info cards and attachments only on the Deal 상세 tab', async () => {
    // when: 기본 탭을 연다
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // then: BANT·고객·파트너 카드와 첨부 파일이 보이고 Action 목록·이력 필터는 없다
    expect(await screen.findByRole('region', { name: 'BANT' })).toBeVisible()
    expect(screen.getByRole('region', { name: '고객' })).toBeVisible()
    expect(screen.getByRole('region', { name: '파트너' })).toBeVisible()
    expect(screen.getByRole('heading', { name: '첨부 파일' })).toBeVisible()
    expect(screen.queryByRole('table', { name: 'Action 목록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('search', { name: 'Action 검색' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('변경 대상')).not.toBeInTheDocument()
  })

  // Actions 탭에는 Action 목록·검색만 있고 카드·첨부는 없다.
  // 테스트 코드: DD-064
  it('shows the Actions list and search but not the info cards on the Actions tab', async () => {
    // when: ?tab=actions로 연다
    await renderAt(await detailPath(1, '?tab=actions'))
    await heading('한빛은행 ITDR 도입')
    // then: Action 목록과 검색이 보이고 BANT 카드·첨부 파일은 없다
    expect(await screen.findByRole('table', { name: 'Action 목록' })).toBeVisible()
    expect(screen.getByRole('search', { name: 'Action 검색' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'BANT' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '첨부 파일' })).not.toBeInTheDocument()
  })

  // Deal History 탭에는 이력 필터만 있고 카드·Action 목록은 없다.
  // 테스트 코드: DD-064
  it('shows the history but not the info cards on the Deal History tab', async () => {
    // when: ?tab=history로 연다
    await renderAt(await detailPath(1, '?tab=history'))
    await heading('한빛은행 ITDR 도입')
    // then: '변경 대상' 필터가 보이고 BANT 카드·Action 목록은 없다
    expect(await screen.findByLabelText('변경 대상')).toBeVisible()
    expect(screen.queryByRole('region', { name: 'BANT' })).not.toBeInTheDocument()
    expect(screen.queryByRole('table', { name: 'Action 목록' })).not.toBeInTheDocument()
  })

  // 머리(이름·목록·삭제)는 모든 탭 위에 있고 탭 목록이 그 바로 아래다.
  // 테스트 코드: DD-062
  it('keeps the header above every tab with the tab list right below it', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    for (const tab of ['Deal 상세', 'Actions', 'Deal History']) {
      // when: 탭을 누른다
      await user.click(screen.getByRole('tab', { name: tab }))
      // then: Deal 이름·'← 목록'·'Deal 삭제'가 보이고 탭 목록이 머리 바로 다음에 있다
      const title = screen.getByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
      expect(title).toBeVisible()
      expect(screen.getByRole('link', { name: '← 목록' })).toBeVisible()
      expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeVisible()
      const afterHeader = title.closest('header')?.nextElementSibling
      expect(afterHeader?.querySelector('[role="tablist"]')).toBe(screen.getByRole('tablist', { name: '상세 탭' }))
    }
  })

  // Deal 정보 타일은 Deal 상세 탭 패널 안에만 있다.
  // 테스트 코드: DD-064
  it('shows the deal info tile only inside the Deal 상세 tab', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    // then: Deal 상세 탭에서는 Deal 정보 영역이 보인다
    expect(within(screen.getByRole('tabpanel')).getByRole('region', { name: 'Deal 정보' })).toBeVisible()
    for (const tab of ['Actions', 'Deal History']) {
      // when: 다른 탭으로 옮긴다
      await user.click(screen.getByRole('tab', { name: tab }))
      // then: Deal 정보 영역이 없다
      expect(screen.queryByRole('region', { name: 'Deal 정보' })).not.toBeInTheDocument()
    }
  })

  // 고른 탭이 주소 tab에 남고 Deal 상세로 오면 tab만 지운다(다른 쿼리는 유지).
  // 테스트 코드: DD-063
  it('keeps the selected tab in the url', async () => {
    // given: ?x=1이 붙은 주소
    const { user, location } = await renderAt(await detailPath(1, '?x=1'))
    await heading('한빛은행 ITDR 도입')

    // when: Actions 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Actions' }))
    // then: 주소가 tab=actions로 바뀐다
    expect(location()).toMatch(/\?(x=1&tab=actions|tab=actions&x=1)$/)

    // when: Deal History 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: 주소가 tab=history로 바뀐다
    expect(location()).toMatch(/\?(x=1&tab=history|tab=history&x=1)$/)

    // when: Deal 상세 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    // then: ?x=1만 남는다
    expect(location()).toMatch(/\?x=1$/)
  })

  // Deal 상세로 돌아오면 tab 파라미터가 완전히 지워진다.
  // 테스트 코드: DD-063
  it('drops the tab parameter completely when returning to Deal 상세', async () => {
    // given: ?tab=actions로 연 화면
    const { user, location } = await renderAt(await detailPath(1, '?tab=actions'))
    await heading('한빛은행 ITDR 도입')

    // when: Deal 상세 탭을 누른다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))

    // then: 주소에 tab이 없고 Deal 상세가 선택된다
    expect(location()).not.toContain('tab=')
    expect(screen.getByRole('tab', { name: 'Deal 상세' })).toHaveAttribute('aria-selected', 'true')
  })

  // 주소의 tab 값으로 탭이 바로 열리고 모르는 값은 Deal 상세다.
  // 테스트 코드: DD-063
  it.each([
    ['?tab=actions', 'Actions'],
    ['?tab=history', 'Deal History'],
    ['?tab=foo', 'Deal 상세'],
    ['?tab=info', 'Deal 상세'],
  ])('opens a tab straight from the url %s -> %s', async (query, selected) => {
    // given: tab 값이 actions·history·foo·info인 주소
    await renderAt(await detailPath(1, query))
    // when: 화면을 연다
    await heading('한빛은행 ITDR 도입')
    // then: actions·history는 해당 탭, 모르는 값은 Deal 상세가 선택된다
    expect(screen.getByRole('tab', { name: selected })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('Deal 상세 역할별 버튼과 오류 (T-DETAIL-04)', () => {
  // Owner 영업에게는 값 클릭 편집과 켜진 삭제 버튼이 있고 수정 링크는 없다.
  // 테스트 코드: DD-070
  it('gives the owner click-to-edit fields and a delete button, with no edit link', async () => {
    // given: Owner 본인 sales
    await renderAt(await detailPath(1))
    // when: Deal 상세를 연다
    await heading('한빛은행 ITDR 도입')
    // then: '수정' 링크가 없고 이름 편집 버튼과 켜진 'Deal 삭제'가 있으며 '← 목록'은 /deals로 간다
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', '/deals')
  })

  // Owner가 아닌 영업은 삭제가 꺼져 이유가 보이지만 편집은 된다.
  // 테스트 코드: DD-071
  it('disables delete with a reason for a sales user who is not the owner, but keeps edit', async () => {
    // given: 다른 영업의 Deal
    await renderAt(await detailPath(3))
    await heading('미래전자 EDR 교체')
    // when: Deal 상세를 연다
    const del = screen.getByRole('button', { name: 'Deal 삭제' })
    // then: 삭제 버튼이 비활성이고 title에 이유가 있으며 이름 편집 버튼은 보인다
    expect(del).toBeDisabled()
    expect(del).toHaveAttribute('title', '본인 Deal 또는 admin만 삭제할 수 있습니다.')
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
  })

  // admin은 남의 Deal도 삭제 버튼이 켜져 있다.
  // 테스트 코드: DD-072
  it('lets admin delete anyone s deal', async () => {
    // given: 다른 영업의 Deal과 admin
    await renderAt(await detailPath(3), { role: 'admin' })
    // when: Deal 상세를 연다
    await heading('미래전자 EDR 교체')
    // then: 삭제 버튼이 활성이다
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
  })

  // user는 값만 보고 편집·삭제·입력 버튼이 없다.
  // 테스트 코드: DD-073
  it('shows a viewer the deal without any write control', async () => {
    // given: user 역할 사용자
    await renderAt(await detailPath(1), { role: 'user' })
    // when: Deal 상세를 연다
    await heading('한빛은행 ITDR 도입')
    // then: 수정 링크·삭제·편집 버튼·Action 추가·연락처 입력이 없고 값은 글자로 보인다
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Deal 삭제' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '금액(단위:원) 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Action 추가' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '고객 회사명 수정' })).not.toBeInTheDocument()
    expect(screen.queryByTitle('Deal 이름 수정')).not.toBeInTheDocument()
    const bant = screen.getByRole('region', { name: 'BANT' })
    expect(within(bant).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(bant).getByText('단독 예산 확보')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Deal 정보' })).toHaveTextContent('가격협상')
  })

  // 없는 Deal은 서버 문구 오류와 'Deal 목록으로' 링크를 보인다.
  // 테스트 코드: DD-065
  it('shows the not found message with a way back', async () => {
    // when: 화면을 연다 (전제: 없는 Deal 주소)
    await renderAt('/deals/20000101-ZZZZ')
    // then: 'Deal을 찾을 수 없습니다.' 알림과 /deals로 가는 링크가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', '/deals')
  })
})
