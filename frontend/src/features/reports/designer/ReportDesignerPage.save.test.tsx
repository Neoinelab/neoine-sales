// 저장 뒤 이동하는 편집 화면은 React.lazy 청크이므로 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import { arrangement, chooseView, dragTile, expectTab, showTab, tileOrder } from '../../../test/reportLayout'
import { addColumn, lastQuery, openAndRun, openDesigner, runQuery, saveButton, saveDialog, setupReportClock, typeName, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES } from '../../../test/savedReports'

setupReportClock()

const GUIDE = '저장 내용: 컬럼·조건·정렬·행 수·차트 설정과 생성 SQL. 결과 데이터는 저장하지 않고 열 때마다 다시 조회합니다.'
const CREATED = '/reports/16/edit'

/** 새 리포트에서 컬럼 하나를 넣고 조회해 저장할 수 있는 상태로 만든다. */
async function openReady(role: 'admin' | 'sales' | 'user' = 'sales') {
  const rendered = await openDesigner({ role, savedReports: SAVED_SAMPLES })
  await addColumn(rendered.user, 'Deal code')
  await runQuery(rendered.user)
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}

describe('저장 단추 활성 조건', () => {
  // 테스트 코드: RS-067
  it('저장은 지금 설계로 조회한 결과가 있을 때만 켜진다', async () => {
    // when: 조회 전 새 리포트 화면을 연다
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    // then: 저장이 꺼져 있고 "먼저 조회하세요" 안내다
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')

    // when: 컬럼을 넣는다 (아직 조회 전)
    await addColumn(user, 'Deal code')
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')

    // when: 조회한다
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })
    // then: 저장이 켜진다
    expect(saveButton()).toBeEnabled()
    expect(saveButton().getAttribute('title') ?? '').not.toMatch(/조회/)

    // when: 설계를 바꾼다
    await showTab(user, 'design')
    await addColumn(user, 'Deal 이름')
    // then: 저장이 꺼지고 다시 조회 안내다
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '바뀐 설계를 다시 조회한 뒤 저장하세요')

    // when: 다시 조회한다
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
  })

  // 테스트 코드: RS-067
  it('조회가 실패하면 저장은 꺼진 채다', async () => {
    // given: 새 리포트 화면
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    // when: 위반이 날 컬럼으로 조회한다
    await addColumn(user, 'Action 건수')

    await runQuery(user)

    // then: 오류가 보이고 저장이 꺼져 있다
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(saveButton()).toBeDisabled()
    expect(saveButton()).toHaveAttribute('title', '먼저 조회하세요')
  })

  // 테스트 코드: RS-067
  it('새 리포트에는 다른 이름으로 저장·되돌리기 버튼이 없다', async () => {
    // when: 조회를 마친 새 리포트 화면
    await openReady()

    // then: 다른 이름으로 저장·되돌리기는 없고 초기화가 있다
    expect(screen.queryByRole('button', { name: '다른 이름으로 저장' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '되돌리기' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '초기화' })).toBeVisible()
  })

  // 테스트 코드: RS-080
  it('설계가 빈 설계와 달라지면 바로 저장 안 됨이 붙는다', async () => {
    // given: 빈 새 리포트 화면
    const { user } = await openDesigner({ savedReports: SAVED_SAMPLES })
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()

    // when: 컬럼을 넣는다
    await addColumn(user, 'Deal code')

    // then: 저장 안 됨(status)이 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')
  })
})

describe('저장 대화상자', () => {
  // 테스트 코드: RS-068
  it('저장 창은 제목·칸·기본값·안내와 함께 열린다', async () => {
    // given: 조회를 마친 새 리포트 화면
    const { user } = await openReady()

    // when: 저장을 누른다
    await user.click(saveButton())

    // then: 이름·설명은 비어 있고 공개 범위는 "모든 사용자에게 보임"이며 안내 문구가 보인다
    const dialog = await saveDialog()
    const name = within(dialog).getByRole('textbox', { name: '이름' })
    expect(name).toHaveValue('')
    expect(name).toBeRequired()
    expect(name).toHaveAttribute('maxlength', '100')
    expect(within(dialog).getByRole('textbox', { name: '설명' })).toHaveAttribute('maxlength', '1000')
    const visibility = within(dialog).getByRole('combobox', { name: '공개 범위' })
    expect(visibility).toHaveDisplayValue('모든 사용자에게 보임')
    expect(within(visibility).getAllByRole('option').map((o) => o.textContent)).toEqual(['모든 사용자에게 보임', '나만 보기'])
    expect(dialog).toHaveTextContent(GUIDE)
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeEnabled()
  })

  // 테스트 코드: RS-068, RS-070
  it('이름을 검사하고 이름 중복은 이름 칸 아래에 보인다', async () => {
    // given: 저장 창을 연다
    const { user } = await openReady()
    await user.click(saveButton())
    const dialog = await saveDialog()

    // when: 이름 없이 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 요청 없이 안내가 보인다
    expect(within(dialog).getByText('이름을 입력하세요')).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])

    // when: 공백만 넣어 저장한다
    await typeName(user, dialog, '   ')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(within(dialog).getByText('이름을 입력하세요')).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])

    // when: 이미 있는 이름으로 저장한다
    await typeName(user, dialog, MINE_PUBLIC.name.toLowerCase())
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 이름 중복 문구가 이름 칸 아래에 보이고 창이 남으며 저장 안 됨도 남는다
    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(within(dialog).queryByText('이름을 입력하세요')).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['create'])
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-068
  it('취소하면 요청 없이 닫힌다', async () => {
    // given: 저장 창을 연다
    const { user } = await openReady()
    await user.click(saveButton())

    // when: 취소를 누른다
    await user.click(within(await saveDialog()).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  // 테스트 코드: RS-071
  it('서버가 정의를 거절하면 창을 닫고 디자이너에 위반을 보인다', async () => {
    // given: 서버가 정의 위반을 돌려주는 설계의 저장 창
    const result = resultOf({ columns: [resultColumn({ field: 'action.count', label: 'Action 건수', type: 'number', valueType: 'integer' })], rows: [[3]] })
    const { user } = await openAndRun(result, 'Action 건수')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '위반 리포트')

    // when: 이름을 넣고 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 창이 닫히고 작성 탭에 위반이 보이며 만들기 요청만 갔다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '리포트 저장' })).not.toBeInTheDocument())
    expect((await screen.findAllByText(/이 컬럼은 그룹핑할 때만 쓸 수 있습니다/)).length).toBeGreaterThan(0)
    expectTab('design') // 첫 위반이 차트가 아니면 작성 탭으로 옮겨 위반 위치를 보인다 
    expect(screen.getByRole('alert')).toHaveTextContent('이 컬럼은 그룹핑할 때만 쓸 수 있습니다')
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['create'])
  })
})

describe('새 리포트 저장', () => {
  // 테스트 코드: RS-069
  it('새 리포트를 저장하면 편집 화면으로 바뀌고 저장 안 됨이 없다', async () => {
    // given: 조회를 마친 새 리포트 화면
    const { user, location } = await openReady()
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 이름·설명·공개 범위를 정해 저장한다
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '  내가 만든 첫 리포트  ')
    await user.type(within(dialog).getByRole('textbox', { name: '설명' }), '설명입니다')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: '공개 범위' }), '나만 보기')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 편집 화면으로 가고 제목·요청 본문이 맞으며 저장 안 됨이 없다
    await waitFor(() => expect(location()).toBe(CREATED))
    expect(await screen.findByRole('heading', { level: 1, name: '내가 만든 첫 리포트' })).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
    const requests = mockControl.savedReportRequests()
    expect(requests).toHaveLength(1)
    expect(requests[0]).toMatchObject({ op: 'create', id: null, body: { description: '설명입니다', visibility: 'private', definition: lastQuery() } })
    expect((requests[0]?.body as { name: string }).name.trim()).toBe('내가 만든 첫 리포트')
  })

  // 테스트 코드: RS-069
  it('이동한 뒤 편집 버튼이 보이고 결과가 남는다', async () => {
    // given: 새 리포트를 저장해 편집 화면으로 넘어간다
    const { user, location } = await openReady()
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '편집으로 이동')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    // when: 이동을 기다린다
    await waitFor(() => expect(location()).toBe(CREATED))

    // then: 편집 버튼이 보이고 초기화는 없으며 결과 표가 남는다
    expect(await screen.findByRole('button', { name: '다른 이름으로 저장' })).toBeVisible()
    expect(screen.getByRole('button', { name: '되돌리기' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})

describe('user 역할 저장', () => {
  // 테스트 코드: RS-069
  it('user 역할도 리포트를 저장한다', async () => {
    // given: user 역할의 조회를 마친 새 리포트 화면
    const { user, location } = await openReady('user')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '조회 담당 리포트')

    // when: 이름을 넣고 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 편집 화면으로 가고 공개로 저장된다
    await waitFor(() => expect(location()).toBe(CREATED))
    expect(await screen.findByRole('heading', { level: 1, name: '조회 담당 리포트' })).toBeVisible()
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'create', body: { name: '조회 담당 리포트', visibility: 'public' } })
  })

  // 테스트 코드: RS-070
  it('다른 사람이 쓰는 이름이면 디자이너에 머문다', async () => {
    // given: user 역할의 저장 창에 다른 사람이 쓰는 이름을 넣는다
    const { user, location } = await openReady('user')
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, MINE_PUBLIC.name)

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 중복 문구가 보이고 주소는 /reports/new 그대로다
    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(location()).toBe('/reports/new')
  })
})

describe('결과 배치 저장', () => {
  const SIDE_CHART_FIRST = { view: 'both', order: ['chart', 'table'], arrange: 'side_by_side' }

  async function saveAs(user: Awaited<ReturnType<typeof openReady>>['user'], name: string): Promise<void> {
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, name)
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
  }

  // 테스트 코드: RS-090
  it('배치에 손대지 않으면 기본 배치를 만들기 요청에 싣는다', async () => {
    // given: 배치에 손대지 않은 새 리포트 화면
    const { user } = await openReady()

    // when: 저장한다
    await saveAs(user, '기본 배치')

    // then: 만들기 요청의 배치가 기본 배치다
    await waitFor(() => expect(mockControl.savedReportRequests()).toHaveLength(1))
    expect(mockControl.savedReportRequests()[0]).toMatchObject({
      op: 'create',
      body: { layout: { view: 'both', order: ['table', 'chart'], arrange: 'stacked' } },
    })
  })

  // 테스트 코드: RS-090
  it('고른 보기·순서·배치를 만들기 요청에 싣는다', async () => {
    // given: 조회를 마친 새 리포트 화면
    const { user } = await openReady()
    // when: 타일을 옮기고 차트만을 골라 저장한다
    dragTile('표', '차트', 'right')
    await chooseView(user, '차트만')

    await saveAs(user, '내 배치')

    // then: 만들기 요청에 고른 배치가 실린다
    await waitFor(() => expect(mockControl.savedReportRequests()).toHaveLength(1))
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'create', body: { layout: { ...SIDE_CHART_FIRST, view: 'chart' } } })
  })

  // 테스트 코드: RS-090
  it('새 편집 화면은 저장한 배치 그대로 열린다', async () => {
    // given: 타일을 옮긴 새 리포트 화면
    const { user, location } = await openReady()
    dragTile('표', '차트', 'right')

    // when: 저장한다
    await saveAs(user, '배치 그대로')

    // then: 새 편집 화면의 결과 탭이 저장한 배치이고 저장 안 됨이 없다
    await waitFor(() => expect(location()).toBe(CREATED))
    expect(await screen.findByRole('heading', { level: 1, name: '배치 그대로' })).toBeVisible()
    expect(tileOrder()).toEqual(['차트', '표'])
    expect(arrangement()).toBe('side')
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-072
  it('결과 탭을 보다 저장하면 새 편집 화면이 결과 탭으로 열린다', async () => {
    // given: 결과 탭을 보고 있는 새 리포트 화면
    const { user, location } = await openReady()
    expectTab('result')

    // when: 저장한다
    await saveAs(user, '결과 탭에서 저장')

    // then: 새 편집 화면이 결과 탭으로 열리고 다시 조회하지 않는다
    await waitFor(() => expect(location()).toBe(CREATED))
    await screen.findByRole('heading', { level: 1, name: '결과 탭에서 저장' })
    expectTab('result')
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(mockControl.reportQueries()).toHaveLength(1) // 결과를 넘겨 받으므로 다시 조회하지 않는다
  })

  // 테스트 코드: RS-072
  it('작성 탭을 보다 저장하면 새 편집 화면이 작성 탭으로 열린다', async () => {
    // given: 작성 탭을 보고 있는 새 리포트 화면
    const { user, location } = await openReady()
    await showTab(user, 'design')

    // when: 저장한다
    await saveAs(user, '작성 탭에서 저장')

    // then: 새 편집 화면이 작성 탭으로 열리고 다시 조회하지 않으며 결과 탭에 결과가 채워져 있다
    await waitFor(() => expect(location()).toBe(CREATED))
    await screen.findByRole('heading', { level: 1, name: '작성 탭에서 저장' })
    expectTab('design')
    expect(mockControl.reportQueries()).toHaveLength(1)

    // when: 결과 탭으로 옮긴다
    await showTab(user, 'result')
    // then: 결과 표가 채워져 있다
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
  })
})
