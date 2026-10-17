import { ComingSoon } from '../../shared/ui/ComingSoon'

/** Dashboard·Reports처럼 아직 제공하지 않는 메뉴의 "준비 중" 화면. */
export function ComingSoonPage({ title }: { title: string }) {
  return <ComingSoon title={title} />
}
