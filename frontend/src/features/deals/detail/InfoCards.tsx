import type { DealDetail } from '../../../shared/model/types'
import { BantCard } from './BantCard'
import { CustomerCard, PartnerCard } from './ContactCards'
import './detail.css'

interface InfoCardsProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 고객 연락처 · 활성 파트너 · BANT 타일을 1열 세로로 쌓는다(각 타일 안은 가로). 편집은 sales/admin만. */
export function InfoCards({ deal, canWrite, onNotice }: InfoCardsProps) {
  return (
    <div className="dd-cards">
      <CustomerCard deal={deal} canWrite={canWrite} onNotice={onNotice} />
      <PartnerCard deal={deal} canWrite={canWrite} onNotice={onNotice} />
      <BantCard deal={deal} canWrite={canWrite} onNotice={onNotice} />
    </div>
  )
}
