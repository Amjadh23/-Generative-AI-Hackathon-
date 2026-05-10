import type { OptimizationSummary } from '../lib/api'
import { currencyFormatter } from '../lib/format'

type ImpactCardProps = {
  summary: OptimizationSummary
}

export function ImpactCard({ summary }: ImpactCardProps) {
  const valuePrefix = summary.value_gain_rm >= 0 ? '+' : '-'
  const distancePrefix = summary.distance_saved_km >= 0 ? '-' : '+'

  return (
    <section aria-label="RouteIQ impact" className="impact-card">
      <div className="impact-header">
        <div>
          <span className="eyebrow">RouteIQ impact today</span>
          <h2>Better than the baseline route</h2>
        </div>
        <span className="impact-meta">{summary.routes_evaluated.toLocaleString('en-MY')} routes checked</span>
      </div>
      <p className="impact-summary">
        Compared with visiting 8 nearby territory customers in nearest-first order.
      </p>
      <div className="impact-grid">
        <article className="impact-tile primary">
          <span>Expected value gain</span>
          <strong>
            {valuePrefix}
            {currencyFormatter.format(Math.abs(summary.value_gain_rm))}
          </strong>
          <small>
            baseline was {currencyFormatter.format(summary.baseline_expected_return_rm)} ·{' '}
            {summary.value_uplift_pct.toFixed(0)}% more
          </small>
        </article>
        <article className="impact-tile">
          <span>Travel distance change</span>
          <strong>
            {distancePrefix}
            {Math.abs(summary.distance_saved_km).toFixed(1)} km
          </strong>
          <small>baseline was {summary.baseline_distance_km.toFixed(1)} km</small>
        </article>
      </div>
      <p className="impact-footnote">This card shows what the optimized plan adds or saves today.</p>
    </section>
  )
}
