import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { defaultDealsUrlPattern } from './dealsUrl'
import { renderAt } from './mockApp'

const EMPTY = { seed: 'empty' } as const
const DETAIL_URL = /^\/deals\/\d{8}-[A-Z0-9]{4}$/

describe('업무 데이터가 없는 첫 실행 상태', () => {
  // 테스트 코드: UI-056
  it('연도를 전체로 고르면 Deal 목록이 등록 안내와 등록 링크를 보인다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: /deals?year=all을 연다
    await renderAt('/deals?year=all', EMPTY)
    // then: 등록 안내 문구와 "+ Deal 등록" 링크가 보인다
    expect(await screen.findByText('등록된 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('link', { name: '+ Deal 등록' })).toBeVisible()
  })

  // 테스트 코드: UI-056
  it('기본 연도 조건에서는 빈 문구가 조건 문구이고 주소에 올해가 들어간다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: /deals를 연다
    const { location } = await renderAt('/deals', EMPTY)
    // then: 조건 문구가 보이고 등록 안내 문구는 없다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByText('등록된 Deal이 없습니다.')).not.toBeInTheDocument()
    // 조회는 첫 렌더부터 기본 조건으로 하고 주소는 렌더 뒤 replace로 맞춘다. 부하 시 문구가 주소보다 먼저 보일 수 있어 주소 반영을 기다린다.
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))
  })

  // 테스트 코드: UI-057
  it('Deal이 없어도 Forecast 화면이 오류 없이 빈 문구를 보인다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: /forecast?year=2026을 연다
    await renderAt('/forecast?year=2026', EMPTY)
    // then: 빈 문구가 보이고 alert는 없다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 테스트 코드: UI-057
  it('admin의 연락처 목록이 빈 문구를 보인다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: admin으로 /admin/contacts를 연다
    await renderAt('/admin/contacts', { role: 'admin', ...EMPTY })
    // then: 빈 문구가 보인다
    expect(await screen.findByText('등록된 연락처가 없습니다.')).toBeVisible()
  })

  // 테스트 코드: UI-057
  it('Deal 관리에는 기본 코드와 BANT Label이 그대로 보인다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: admin으로 /admin/deal을 연다
    const { user } = await renderAt('/admin/deal', { role: 'admin', ...EMPTY })
    // then: Status 코드 "기회발굴" 행이 보인다
    expect(await screen.findByRole('row', { name: /기회발굴/ })).toBeVisible()
    // when: Forecast 코드 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Forecast 코드' }))
    // then: Commit 행이 보인다
    expect(await screen.findByRole('row', { name: /Commit/ })).toBeVisible()
    // when: BANT Label 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'BANT Label' }))
    // then: Budget의 "단독 예산 확보"가 보인다
    const budget = within(await screen.findByRole('region', { name: 'Budget' }))
    expect(await budget.findByText('단독 예산 확보')).toBeVisible()
  })

  // 테스트 코드: UI-057
  it('사용자 관리에는 로그인 계정이 그대로 보인다', async () => {
    // given: 업무 데이터가 없는 Fake
    // when: admin으로 /admin/users를 연다
    await renderAt('/admin/users', { role: 'admin', ...EMPTY })
    // then: kim(sales 김영업)과 root(admin 최관리) 행이 보인다
    expect(await screen.findByRole('row', { name: /^kim sales 김영업/ })).toBeVisible()
    expect(screen.getByRole('row', { name: /^root admin 최관리/ })).toBeVisible()
  })

  // 테스트 코드: UI-058
  it('빈 상태에서 첫 Deal을 직접 입력한 고객·파트너로 등록하고 Action과 첨부를 더하면 History에 이어진다', async () => {
    // given: 업무 데이터가 없는 Fake의 Deal 등록 화면
    const { user, location } = await renderAt('/deals/new', EMPTY)
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: 고객·파트너·금액 등을 입력해 저장한다
    await user.type(screen.getByLabelText('Deal Name'), '첫 Deal')
    await user.type(screen.getByLabelText('고객 회사명'), '신규고객사')
    await user.type(screen.getByLabelText('고객 담당자명'), '홍길동')
    await user.type(screen.getByLabelText('파트너 회사명'), '신규파트너')
    await user.type(screen.getByLabelText('파트너 담당자명'), '김파트')
    await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-03-01' } })
    await user.click(screen.getByRole('button', { name: '저장' }))
    // then: 상세 주소와 제목 "첫 Deal"이 보인다
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(await screen.findByRole('heading', { level: 1, name: '첫 Deal' })).toBeVisible()

    // when: Actions 탭에서 Action을 등록한다 (기본 탭은 Deal 상세라 Actions 탭으로 옮긴다)
    await user.click(await screen.findByRole('tab', { name: 'Actions' }))
    await user.click(await screen.findByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    await user.type(within(form).getByLabelText('유형'), '미팅')
    await user.type(within(form).getByLabelText('진행사항'), '킥오프 미팅')
    await user.type(within(form).getByLabelText('Next Action'), '제안서 전달')
    fireEvent.change(within(form).getByLabelText('Due Date'), { target: { value: '2026-12-01' } })
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: Action 목록에 "킥오프 미팅"이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument())
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    expect(await within(table).findByText('킥오프 미팅')).toBeVisible()

    // when: Deal 상세 탭을 연다 (첨부 파일은 Deal 상세 탭에 있다)
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const panel = await screen.findByRole('region', { name: '첨부 파일' })
    // then: 첨부 전 "첨부된 파일이 없습니다."가 보인다
    expect(await within(panel).findByText('첨부된 파일이 없습니다.')).toBeVisible()
    // when: 제안서.pdf를 올린다
    await user.upload(within(panel).getByLabelText('파일'), new File(['x'], '제안서.pdf', { type: 'application/pdf' }))
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    // then: 올린 파일 버튼이 보인다
    expect(await within(panel).findByRole('button', { name: '제안서.pdf' })).toBeVisible()

    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const history = await screen.findByRole('table', { name: 'Deal History' })
    // then: History에 제안서.pdf 행이 보인다
    expect(await within(history).findByText(/제안서\.pdf/)).toBeVisible()
    expect(within(history).getAllByRole('row').length).toBeGreaterThan(2)
  })
})
