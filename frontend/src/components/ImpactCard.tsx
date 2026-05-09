import type { OptimizationSummary } from '../lib/api'
import { currencyFormatter } from '../lib/format'

type ImpactCardProps = {
  summary: OptimizationSummary
}

export function ImpactCard({ summary }: ImpactCardProps) {
  const valueLabel = summary.value_gain_rm >= 0 ? 'Extra value' : 'Value delta'
  const distanceLabel = summary.distance_saved_km >= 0 ? 'Distance saved' : 'Extra distance'

  return (
    <section aria-label="RouteIQ impact" className="impact-card">
      <div className="impact-header">
        <span className="eyebrow">RouteIQ impact today</span>
        <span className="impact-meta">
          {summary.routes_evaluated.toLocaleString('en-MY')} routes evaluated
        </span>
      </div>
      <div className="impact-grid">
        <article className="impact-tile primary">
          <span>{valueLabel}</span>
          <strong>{currencyFormatter.format(Math.abs(summary.value_gain_rm))}</strong>
          <small>+{summary.value_uplift_pct.toFixed(0)}% vs baseline</small>
        </article>
        <article className="impact-tile">
          <span>{distanceLabel}</span>
          <strong>{Math.abs(summary.distance_saved_km).toFixed(1)} km</strong>
          <small>baseline {summary.baseline_distance_km.toFixed(1)} km</small>
        </article>
      </div>
      <p className="impact-footnote">
        Baseline = visiting a random sample of {Math.max(1, Math.round(summary.baseline_distance_km > 0 ? 8 : 0))} territory customers in nearest-first order.
      </p>
    </section>
  )
}
