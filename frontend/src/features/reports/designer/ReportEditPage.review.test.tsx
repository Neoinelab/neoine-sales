// 편집 화면의 덮어쓰기 revision, 다른 이름으로 저장의 결과 넘기기 같은 경계 동작을 고정하는 테스트.
// 편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { act, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { keys } from '../../../data/queryKeys'
import { gateway } from '../../../gateway'
import { mockControl } from '../../../test/fake/default'
import { showTab } from '../../../test/reportLayout'
import { addCountedColumn, openEditor, runQuery, saveButton, saveDialog, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, reportInput } from '../../../test/savedReports'

setupReportClock()

const COPY_NAME = `${MINE_PUBLIC.name} 복사본`
const dialogOf = async () => within(await saveDialog())
type Editor = Awaited<ReturnType<typeof openEditor>>

/** 다른 사용자가 먼저 저장한 상황을 같은 계정의 순차 호출로 만든다(현재 revision → +1). */
async function saveElsewhere(revision: number): Promise<void> {
  await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: MINE_PUBLIC.name, description: MINE_PUBLIC.description }), revision })
}

/** 재연결 등으로 상세 쿼리가 다시 조회되는 상황. */
async function refetchDetail(client: Editor['client']): Promise<void> {
  await act(async () => {
    await client.invalidateQueries({ queryKey: keys.savedReport(MINE_PUBLIC.id) })
  })
}

async function changeAndRun(user: Editor['user'], label: string): Promise<void> {
  await showTab(user, 'design')
  await addCountedColumn(user, label)
  await runQuery(user)
  await waitFor(() => expect(saveButton()).toBeEnabled())
}

describe('덮어쓰기 revision은 편집을 시작한 값을 따른다', () => {
  // 테스트 코드: RS-076
  it('다른 사람이 저장한 뒤 상세를 다시 받아도 저장은 충돌 경고다', async () => {
    // given: 설계를 바꿔 조회한 뒤 다른 사용자가 저장하고 상세가 다시 받아졌다
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await saveElsewhere(1)
    await refetchDetail(client)
    await user.click(saveButton())
    const dialog = await dialogOf()

    // when: 저장 창에서 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 처음 revision 1로 요청해 충돌 경고가 뜨고 서버는 revision 2다
    expect(await dialog.findByRole('alert')).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'update')).toMatchObject([{ body: { revision: 1 } }, { body: { revision: 1 } }])
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-076
  it('상세를 다시 받아도 저장 창 기본값은 처음 불러온 값이다', async () => {
    // given: 다른 사용자가 이름을 바꾸고 상세가 다시 받아졌다
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: '남이 바꾼 이름' }), revision: 1 })
    await refetchDetail(client)

    // when: 저장 창을 연다
    await user.click(saveButton())

    // then: 이름이 처음 불러온 이름이다
    expect((await dialogOf()).getByRole('textbox', { name: '이름' })).toHaveValue(MINE_PUBLIC.name)
  })

  // 테스트 코드: RS-076
  it('상세가 중간에 다시 받아져도 다음 저장은 내 덮어쓰기 응답의 revision을 쓴다', async () => {
    // given: 설계를 바꿔 조회한 편집 화면
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    // when: 첫 덮어쓰기를 저장하고 상세를 다시 받은 뒤 다시 바꿔 한 번 더 저장한다
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await refetchDetail(client)
    await changeAndRun(user, 'Deal 이름')
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    // then: 요청 revision이 1, 2이고 서버는 revision 3이다
    expect(mockControl.savedReportRequests().map((r) => (r.body as { revision: number }).revision)).toEqual([1, 2])
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 3 })
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-076
  it('내 덮어쓰기 뒤 다른 사람이 저장했으면 다음 저장은 충돌 경고다', async () => {
    // given: 내가 덮어쓴 뒤 다른 사용자가 저장하고 상세가 다시 받아졌다
    const { user, client } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await saveElsewhere(2)
    await refetchDetail(client)
    await changeAndRun(user, 'Deal 이름')
    await user.click(saveButton())
    const dialog = await dialogOf()

    // when: 다시 바꿔 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 충돌 경고가 뜨고 서버는 revision 3이다
    expect(await dialog.findByRole('alert')).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 3 })
  })
})

describe('다른 이름으로 저장은 지난 결과를 새 설계의 결과로 넘기지 않는다', () => {
  const headers = () => within(screen.getByRole('table', { name: '조회 결과' })).getAllByRole('columnheader')

  // 테스트 코드: RS-072
  it('마지막 조회 뒤 설계가 바뀌었으면 새 편집 화면이 다시 조회한다', async () => {
    // given: 조회 뒤 컬럼을 바꾼 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    expect(mockControl.reportQueries()).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    const dialog = await dialogOf()

    // when: 다른 이름으로 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 새 편집 화면이 지금 설계로 한 번 더 조회한다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await waitFor(() => expect(mockControl.reportQueries()).toHaveLength(2))
    expect(mockControl.reportQueries()[1]?.columns).toHaveLength(3)
    // when: 결과 탭을 연다
    await showTab(user, 'result') // 낡은 결과는 넘기지 않으므로 새 편집 화면은 작성 탭으로 열리고 자동 조회 결과는 결과 탭에 채워진다
    // then: 새 설계의 결과가 채워져 있다
    await waitFor(() => expect(headers()).toHaveLength(3))
    expect(screen.queryByText(UNSAVED_MARK)).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-072
  it('지금 설계로 조회한 결과면 다시 조회하지 않고 넘겨받는다', async () => {
    // given: 지금 설계로 조회를 마친 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await changeAndRun(user, 'Deal code')
    expect(mockControl.reportQueries()).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    // when: 다른 이름으로 저장한다
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))

    // then: 새 편집 화면이 그 결과를 넘겨받아 조회 횟수가 그대로다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(await screen.findByRole('heading', { level: 1, name: COPY_NAME })).toBeVisible()
    expect(headers()).toHaveLength(3)
    expect(mockControl.reportQueries()).toHaveLength(2)
  })
})

describe('다른 이름으로 저장의 입력 문제', () => {
  it('설계에 입력 문제가 있으면 조용히 끝내지 않고 알린다', async () => {
    // given: 금액 조건에 읽을 수 없는 값을 넣은 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    const amount = screen.getByDisplayValue('1,500,000')
    await user.clear(amount)
    await user.type(amount, 'abc')
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    // when: 다른 이름으로 저장한다
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))

    // then: 입력 문제 안내가 보이고 화면과 요청이 그대로다
    expect((await screen.findAllByText(/정수로 입력하세요/)).length).toBeGreaterThan(0)
    expect(location()).toBe(`/reports/${MINE_PUBLIC.id}/edit`)
    expect(mockControl.savedReportRequests()).toEqual([])
  })
})

describe('변경이 없을 때의 되돌리기', () => {
  // 테스트 코드: RS-079
  it('변경이 없으면 되돌리기는 아무것도 하지 않는다', async () => {
    // given: 변경 없이 조회가 끝난 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    await waitFor(() => expect(saveButton()).toBeEnabled())

    // when: 되돌리기를 누른다
    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    // then: 확인 창이 없고 결과와 켜진 저장 버튼이 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // when: 결과 탭으로 옮긴다
    await showTab(user, 'result')
    // then: 결과와 켜진 저장 버튼이 그대로다
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(saveButton()).toBeEnabled()
    expect(mockControl.reportQueries()).toHaveLength(1)
  })
})
