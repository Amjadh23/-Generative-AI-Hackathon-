import type { DayPlanStop } from '../lib/api'
import { currencyFormatter, formatSegment } from '../lib/format'

type StopCardProps = {
  stop: DayPlanStop
  onSelect: (customerId: string) => void
}

export function StopCard({ stop, onSelect }: StopCardProps) {
  return (
    <button className="stop-card" onClick={() => onSelect(stop.customer_id)} type="button">
      <div className="sequence">{stop.sequence}</div>
      <div className="stop-body">
        <div className="stop-title">
          <h3>{stop.customer_name}</h3>
          <span>{Math.round(stop.score)}</span>
        </div>
        <p className="stop-segment">{formatSegment(stop.segment)}</p>
        <p>{stop.focus}</p>
        <div className="stop-meta">
          <span>{currencyFormatter.format(stop.expected_return_rm)}</span>
          <span>{stop.distance_from_previous_km.toFixed(1)} km</span>
          <span>{stop.eta_minutes} min</span>
        </div>
      </div>
    </button>
  )
}
