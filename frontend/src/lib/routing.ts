export type Waypoint = { lat: number; lng: number }

export type ManeuverStep = {
  instruction: string
  type: string
  modifier?: string
  roadName: string
  distanceMeters: number
  durationSeconds: number
  location: { lat: number; lng: number }
  destinationStopIndex: number
}

export type RouteGeometry = {
  coordinates: [number, number][]
  distanceKm: number
  durationMinutes: number
  steps: ManeuverStep[]
  source: 'osrm' | 'fallback'
}

const OSRM_BASE = 'https://router.project-osrm.org/route/v1/driving'

const MODIFIER_PHRASING: Record<string, string> = {
  left: 'left',
  right: 'right',
  'sharp left': 'sharp left',
  'sharp right': 'sharp right',
  'slight left': 'slight left',
  'slight right': 'slight right',
  straight: 'straight',
  uturn: 'a U-turn',
}

function withRoad(road: string, fallback: string): string {
  return road ? `${fallback} onto ${road}` : fallback
}

export function composeInstruction(
  type: string,
  modifier: string | undefined,
  roadName: string,
): string {
  const heading = modifier ? MODIFIER_PHRASING[modifier] ?? modifier : ''
  switch (type) {
    case 'depart':
      return roadName ? `Head onto ${roadName}` : 'Start driving'
    case 'arrive':
      return 'Arrive at the customer'
    case 'turn':
      return withRoad(roadName, `Turn ${heading}`)
    case 'continue':
      return roadName ? `Continue on ${roadName}` : 'Continue straight'
    case 'merge':
      return withRoad(roadName, `Merge ${heading || ''}`.trim())
    case 'on ramp':
      return roadName ? `Take the ramp onto ${roadName}` : 'Take the on-ramp'
    case 'off ramp':
      return roadName ? `Take the exit toward ${roadName}` : 'Take the off-ramp'
    case 'fork':
      return withRoad(roadName, `Keep ${heading || 'straight'} at the fork`)
    case 'roundabout':
    case 'rotary':
      return roadName ? `Take the roundabout onto ${roadName}` : 'Take the roundabout'
    case 'new name':
      return roadName ? `Continue onto ${roadName}` : 'Continue ahead'
    case 'end of road':
      return withRoad(roadName, `Turn ${heading}`)
    default:
      return roadName ? `Continue on ${roadName}` : 'Continue'
  }
}

function straightLineFallback(waypoints: Waypoint[]): RouteGeometry {
  return {
    coordinates: waypoints.map((point) => [point.lng, point.lat]),
    distanceKm: 0,
    durationMinutes: 0,
    source: 'fallback',
    steps: [],
  }
}

export async function fetchRouteGeometry(waypoints: Waypoint[]): Promise<RouteGeometry> {
  if (waypoints.length < 2) {
    return straightLineFallback(waypoints)
  }

  const coordinatePath = waypoints
    .map((point) => `${point.lng.toFixed(6)},${point.lat.toFixed(6)}`)
    .join(';')
  const url = `${OSRM_BASE}/${coordinatePath}?overview=full&geometries=geojson&steps=true`

  try {
    const response = await fetch(url)
    if (!response.ok) {
      return straightLineFallback(waypoints)
    }
    const payload = (await response.json()) as {
      routes?: {
        distance: number
        duration: number
        geometry: { coordinates: [number, number][] }
        legs: {
          steps: {
            distance: number
            duration: number
            name?: string
            maneuver: {
              type: string
              modifier?: string
              location: [number, number]
            }
          }[]
        }[]
      }[]
    }
    const route = payload.routes?.[0]
    if (!route) {
      return straightLineFallback(waypoints)
    }

    const steps: ManeuverStep[] = []
    route.legs.forEach((leg, legIndex) => {
      leg.steps.forEach((step) => {
        const roadName = step.name ?? ''
        steps.push({
          destinationStopIndex: legIndex,
          distanceMeters: step.distance,
          durationSeconds: step.duration,
          instruction: composeInstruction(step.maneuver.type, step.maneuver.modifier, roadName),
          location: { lat: step.maneuver.location[1], lng: step.maneuver.location[0] },
          modifier: step.maneuver.modifier,
          roadName,
          type: step.maneuver.type,
        })
      })
    })

    return {
      coordinates: route.geometry.coordinates,
      distanceKm: route.distance / 1000,
      durationMinutes: route.duration / 60,
      source: 'osrm',
      steps,
    }
  } catch {
    return straightLineFallback(waypoints)
  }
}

export function haversineKm(a: Waypoint, b: Waypoint): number {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h))
}

export function haversineMeters(a: Waypoint, b: Waypoint): number {
  return haversineKm(a, b) * 1000
}
