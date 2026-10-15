/** Dashboard·Reports처럼 이번 목업 범위 밖인 메뉴의 "준비 중" 화면(계획 6.2). */
export function ComingSoonPage({ title }: { title: string }) {
  return (
    <section className="panel">
      <h1>{title}</h1>
      <p>준비 중입니다. 이 화면은 이번 목업 범위에 없습니다.</p>
      <p className="hint">메뉴 구조(Dashboard / Deals / Forecast / Reports) 확인용으로만 연결되어 있습니다.</p>
    </section>
  )
}
