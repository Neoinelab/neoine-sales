import { ActionList } from './ActionList'

export function ActionsSearchPage() {
  return (
    <section>
      <h1>활동 검색</h1>
      <p className="hint">모든 딜의 활동 이력을 조건으로 찾습니다.</p>
      <ActionList />
    </section>
  )
}
