export const currencyFormatter = new Intl.NumberFormat('en-MY', {
  currency: 'MYR',
  maximumFractionDigits: 0,
  style: 'currency',
})

export const percentFormatter = new Intl.NumberFormat('en-MY', {
  maximumFractionDigits: 0,
  style: 'percent',
})

export function formatSegment(segment: string): string {
  return segment.replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

export function googleMapsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
}

/** Matches backend `recommended_action_for_class` when API omits or caches an old payload. */
export function displayRecommendedAction(
  recommendedAction: string | undefined,
  priorityClass: string | undefined,
): string {
  const raw = recommendedAction?.trim()
  if (raw) return raw
  const pc = priorityClass?.trim() ?? ''
  return pc === 'Low' ? 'Schedule follow-up' : 'Visit today'
}
