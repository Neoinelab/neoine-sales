/** 아직 제공하지 않는 화면의 "준비 중" 안내(Dashboard·Reports, 서버가 아직 없는 Forecast). */
export function ComingSoon({ title }: { title: string }) {
  return (
    <section className="panel">
      <h1>{title}</h1>
      <p>준비 중입니다.</p>
      <p className="hint">이 화면은 다음 단계에서 제공됩니다.</p>
    </section>
  )
}
