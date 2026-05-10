import 'maplibre-gl/dist/maplibre-gl.css'

import maplibregl, { type LngLatLike } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import {
  ManeuverIcon,
  MuteIcon,
  PlayIcon,
  StopIcon,
  VolumeIcon,
} from '../components/Icon'
import { Mascot } from '../components/Mascot'
import { MascotChat } from '../components/MascotChat'
import { useGeolocation } from '../hooks/useGeolocation'
import { speak, useTurnByTurn } from '../hooks/useTurnByTurn'
import type { DayPlan, Territory } from '../lib/api'
import { currencyFormatter } from '../lib/format'
import { fetchRouteGeometry, haversineKm, type RouteGeometry } from '../lib/routing'

type MapPageProps = {
  dayPlan: DayPlan | null
  territory: Territory | null
  onSelectCustomer: (customerId: string) => void
}

const HILTI_RED = '#d2051e'
const LIVE_BLUE = '#1d4ed8'
const POSITRON_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const ROUTE_LAYER = 'routeiq-route'
const ACCURACY_LAYER = 'routeiq-accuracy'
const KL_CENTER = { lat: 3.139, lng: 101.6869 }

function sameLngLat(a: [number, number] | undefined, b: [number, number]) {
  if (!a) return false
  return Math.abs(a[0] - b[0]) < 0.00001 && Math.abs(a[1] - b[1]) < 0.00001
}

function routeCoordinatesWithExactStops(
  geometry: RouteGeometry,
  waypoints: { lat: number; lng: number }[],
): [number, number][] {
  const coordinates = [...geometry.coordinates]
  if (waypoints.length === 0) return coordinates

  const start: [number, number] = [waypoints[0].lng, waypoints[0].lat]
  const endWaypoint = waypoints[waypoints.length - 1]
  const end: [number, number] = [endWaypoint.lng, endWaypoint.lat]

  if (!sameLngLat(coordinates[0], start)) {
    coordinates.unshift(start)
  }
  if (!sameLngLat(coordinates[coordinates.length - 1], end)) {
    coordinates.push(end)
  }
  return coordinates
}

function metersToCircle(centerLng: number, centerLat: number, radiusMeters: number) {
  const points = 64
  const coordinates: [number, number][] = []
  const distanceX = radiusMeters / (111320 * Math.cos((centerLat * Math.PI) / 180))
  const distanceY = radiusMeters / 110540
  for (let index = 0; index < points; index += 1) {
    const theta = (index / points) * (2 * Math.PI)
    coordinates.push([
      centerLng + distanceX * Math.cos(theta),
      centerLat + distanceY * Math.sin(theta),
    ])
  }
  coordinates.push(coordinates[0])
  return coordinates
}

function formatDistance(meters: number | null | undefined): string {
  if (meters == null) return '—'
  if (meters < 1000) return `${Math.round(meters / 10) * 10} m`
  return `${(meters / 1000).toFixed(1)} km`
}

function formatDuration(minutes: number): string {
  if (minutes < 1) return '<1 min'
  if (minutes < 60) return `${Math.round(minutes)} min`
  const hours = Math.floor(minutes / 60)
  const remainder = Math.round(minutes - hours * 60)
  return `${hours} h ${remainder} min`
}

export function MapPage({ dayPlan, onSelectCustomer, territory }: MapPageProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const stopMarkersRef = useRef<maplibregl.Marker[]>([])
  const liveMarkerRef = useRef<maplibregl.Marker | null>(null)
  const mascotMarkerRef = useRef<maplibregl.Marker | null>(null)
  const lastRoutedFromRef = useRef<{ lat: number; lng: number } | null>(null)
  const lastRouteKeyRef = useRef<string | null>(null)
  const mascotMarkup = useMemo(
    () => renderToStaticMarkup(<Mascot mood="happy" size={48} />),
    [],
  )

  const [followMe, setFollowMe] = useState(true)
  const [navigating, setNavigating] = useState(false)
  const [voiceEnabled, setVoiceEnabled] = useState(true)
  const [routeMeta, setRouteMeta] = useState<RouteGeometry | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const [showAllSteps, setShowAllSteps] = useState(false)

  const demoFallback = useMemo(() => {
    if (territory) return { lat: territory.home_lat, lng: territory.home_lng }
    return KL_CENTER
  }, [territory])

  const { error: geoError, position: detectedPosition, useDemoLocation: setDemoLocation, usingDemo } = useGeolocation({
    demoFallback,
    enabled: true,
  })

  const position = useMemo(() => {
    if (!detectedPosition) return null
    if (usingDemo) return detectedPosition.source === 'demo' ? detectedPosition : null
    return detectedPosition.source === 'gps' ? detectedPosition : null
  }, [detectedPosition, usingDemo])

  const routeStart = useMemo(() => {
    if (position) return { lat: position.lat, lng: position.lng, source: position.source }
    if (demoFallback) return { lat: demoFallback.lat, lng: demoFallback.lng, source: 'planned' as const }
    return null
  }, [position, demoFallback])

  const { currentStep, currentStepIndex, distanceToManeuverMeters, nextStep } = useTurnByTurn({
    active: navigating,
    position,
    steps: routeMeta?.steps ?? [],
    voiceEnabled,
  })

  const remainingMeters = useMemo(() => {
    const steps = routeMeta?.steps ?? []
    if (!steps.length) return 0
    return steps.slice(currentStepIndex).reduce((acc, step) => acc + step.distanceMeters, 0)
  }, [routeMeta, currentStepIndex])

  const remainingMinutes = useMemo(() => {
    const steps = routeMeta?.steps ?? []
    if (!steps.length) return 0
    return steps.slice(currentStepIndex).reduce((acc, step) => acc + step.durationSeconds, 0) / 60
  }, [routeMeta, currentStepIndex])

  useEffect(() => {
    const marker = mascotMarkerRef.current
    if (!marker) return
    const bubble = marker.getElement().querySelector('[data-bubble]') as HTMLElement | null
    if (!bubble) return

    if (navigating && (nextStep || currentStep)) {
      const step = nextStep ?? currentStep
      bubble.textContent = step ? step.instruction : ''
      bubble.classList.add('visible')
    } else {
      bubble.textContent = ''
      bubble.classList.remove('visible')
    }
  }, [navigating, nextStep, currentStep])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      center: [101.6869, 3.139],
      container: containerRef.current,
      style: POSITRON_STYLE,
      zoom: 11,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    const onLoad = () => {
      map.resize()
      setMapReady(true)
    }
    map.once('load', onLoad)

    const resizeFrame = window.requestAnimationFrame(() => map.resize())

    return () => {
      window.cancelAnimationFrame(resizeFrame)
      stopMarkersRef.current.forEach((marker) => marker.remove())
      stopMarkersRef.current = []
      liveMarkerRef.current?.remove()
      liveMarkerRef.current = null
      mascotMarkerRef.current?.remove()
      mascotMarkerRef.current = null
      map.remove()
      mapRef.current = null
      setMapReady(false)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !dayPlan) return

    const renderStops = () => {
      stopMarkersRef.current.forEach((marker) => marker.remove())
      stopMarkersRef.current = []

      dayPlan.stops.forEach((stop) => {
        const element = document.createElement('button')
        element.className = 'map-marker'
        element.type = 'button'
        element.textContent = String(stop.sequence)
        element.addEventListener('click', () => onSelectCustomer(stop.customer_id))
        const popup = new maplibregl.Popup({ closeButton: false, offset: 16 }).setHTML(
          `<strong>${stop.customer_name}</strong><br/>${currencyFormatter.format(
            stop.expected_return_rm,
          )} \u00b7 score ${Math.round(stop.score)}`,
        )
        const marker = new maplibregl.Marker({ element })
          .setLngLat([stop.lng, stop.lat])
          .setPopup(popup)
          .addTo(map)
        stopMarkersRef.current.push(marker)
      })
    }

    if (map.isStyleLoaded()) {
      renderStops()
    } else {
      map.once('load', renderStops)
    }
  }, [dayPlan, onSelectCustomer])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const renderLive = () => {
      if (!position) return

      if (!liveMarkerRef.current) {
        const dotElement = document.createElement('div')
        dotElement.className = 'live-marker'
        liveMarkerRef.current = new maplibregl.Marker({ element: dotElement })
          .setLngLat([position.lng, position.lat])
          .addTo(map)
      } else {
        liveMarkerRef.current.setLngLat([position.lng, position.lat])
      }

      if (!mascotMarkerRef.current) {
        const mascotElement = document.createElement('div')
        mascotElement.className = 'map-companion'
        mascotElement.innerHTML = `
          <div class="map-companion-bubble" data-bubble></div>
          <div class="map-companion-mascot">${mascotMarkup}</div>
        `
        mascotMarkerRef.current = new maplibregl.Marker({
          anchor: 'bottom',
          element: mascotElement,
          offset: [22, -12],
        })
          .setLngLat([position.lng, position.lat])
          .addTo(map)
      } else {
        mascotMarkerRef.current.setLngLat([position.lng, position.lat])
      }

      const accuracyData: GeoJSON.Feature<GeoJSON.Polygon> = {
        geometry: {
          coordinates: [metersToCircle(position.lng, position.lat, position.accuracyMeters)],
          type: 'Polygon',
        },
        properties: {},
        type: 'Feature',
      }

      const existing = map.getSource(ACCURACY_LAYER) as maplibregl.GeoJSONSource | undefined
      if (existing) {
        existing.setData(accuracyData)
      } else {
        map.addSource(ACCURACY_LAYER, { data: accuracyData, type: 'geojson' })
        map.addLayer({
          id: ACCURACY_LAYER,
          paint: { 'fill-color': LIVE_BLUE, 'fill-opacity': 0.12 },
          source: ACCURACY_LAYER,
          type: 'fill',
        })
      }

      if (followMe) {
        map.easeTo({
          center: [position.lng, position.lat],
          duration: 600,
          zoom: navigating ? 16 : Math.max(map.getZoom(), 13),
        })
      }
    }

    if (map.isStyleLoaded()) {
      renderLive()
    } else {
      map.once('load', renderLive)
    }
  }, [position, followMe, navigating, mascotMarkup])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    map.resize()
  }, [mapReady, dayPlan, routeMeta])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !dayPlan || !routeStart) return

    const waypoints = [
      { lat: routeStart.lat, lng: routeStart.lng },
      ...dayPlan.stops.map((stop) => ({ lat: stop.lat, lng: stop.lng })),
    ]
    const routeKey = waypoints
      .map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`)
      .join('|')

    const movedFar =
      !lastRoutedFromRef.current ||
      haversineKm(lastRoutedFromRef.current, { lat: routeStart.lat, lng: routeStart.lng }) > 0.1

    if (!movedFar && routeMeta && lastRouteKeyRef.current === routeKey) return

    let cancelled = false

    fetchRouteGeometry(waypoints).then((geometry) => {
      if (cancelled) return
      const visibleCoordinates = routeCoordinatesWithExactStops(geometry, waypoints)
      const visibleGeometry: RouteGeometry = {
        ...geometry,
        coordinates: visibleCoordinates,
      }
      setRouteMeta(visibleGeometry)
      lastRoutedFromRef.current = { lat: routeStart.lat, lng: routeStart.lng }
      lastRouteKeyRef.current = routeKey

      const renderRoute = () => {
        const data: GeoJSON.Feature<GeoJSON.LineString> = {
          geometry: { coordinates: visibleCoordinates, type: 'LineString' },
          properties: {},
          type: 'Feature',
        }

        const source = map.getSource(ROUTE_LAYER) as maplibregl.GeoJSONSource | undefined
        if (source) {
          source.setData(data)
        } else {
          map.addSource(ROUTE_LAYER, { data, type: 'geojson' })
          map.addLayer({
            id: ROUTE_LAYER,
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': HILTI_RED, 'line-opacity': 0.9, 'line-width': 5 },
            source: ROUTE_LAYER,
            type: 'line',
          })
        }

        if ((!followMe || routeStart.source === 'planned') && !navigating) {
          const bounds = visibleCoordinates.reduce(
            (acc, coordinate) => acc.extend(coordinate as LngLatLike),
            new maplibregl.LngLatBounds(
              visibleCoordinates[0] as LngLatLike,
              visibleCoordinates[0] as LngLatLike,
            ),
          )
          map.fitBounds(bounds, { duration: 600, padding: 60 })
        }
      }

      renderRoute()
    })

    return () => {
      cancelled = true
    }
  }, [routeStart, dayPlan, followMe, navigating, routeMeta, mapReady])

  const onStartNavigation = () => {
    setNavigating(true)
    setFollowMe(true)
    if (voiceEnabled) speak('Navigation started.')
  }

  const onStopNavigation = () => {
    setNavigating(false)
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
  }

  return (
    <section className="map-page">
      {navigating && currentStep ? (
        <div className="nav-banner">
          <div className="nav-icon">
            <ManeuverIcon modifier={nextStep?.modifier ?? currentStep.modifier} size={32} type={nextStep?.type ?? currentStep.type} />
          </div>
          <div className="nav-text">
            <p className="nav-distance">
              {nextStep ? `In ${formatDistance(distanceToManeuverMeters)}` : 'Now'}
            </p>
            <p className="nav-instruction">{(nextStep ?? currentStep).instruction}</p>
          </div>
        </div>
      ) : (
        <div className="map-header">
          <p className="eyebrow">Live route</p>
          <h2>
            {dayPlan
              ? routeMeta?.source === 'osrm'
                ? `${routeMeta.distanceKm.toFixed(1)} km \u00b7 ${formatDuration(routeMeta.durationMinutes)} driving`
                : `${dayPlan.stops.length} stops \u00b7 ${dayPlan.total_distance_km.toFixed(1)} km`
              : 'Loading...'}
          </h2>
        </div>
      )}

      <div className="map-controls">
        {!navigating ? (
          <button
            className="chip-button primary"
            disabled={!routeMeta || routeMeta.steps.length === 0}
            onClick={onStartNavigation}
            type="button"
          >
            <PlayIcon size={16} />
            <span>Start navigation</span>
          </button>
        ) : (
          <button className="chip-button danger" onClick={onStopNavigation} type="button">
            <StopIcon size={16} />
            <span>Stop</span>
          </button>
        )}
        <button
          aria-pressed={followMe}
          className={followMe ? 'chip-button active' : 'chip-button'}
          onClick={() => setFollowMe((current) => !current)}
          type="button"
        >
          Follow me
        </button>
        <button
          aria-pressed={voiceEnabled}
          className={voiceEnabled ? 'chip-button active' : 'chip-button'}
          onClick={() => setVoiceEnabled((current) => !current)}
          type="button"
        >
          {voiceEnabled ? <VolumeIcon size={16} /> : <MuteIcon size={16} />}
          <span>{voiceEnabled ? 'Voice on' : 'Voice off'}</span>
        </button>
        <button
          aria-pressed={usingDemo}
          className={usingDemo ? 'chip-button active' : 'chip-button'}
          onClick={() => setDemoLocation(!usingDemo)}
          type="button"
        >
          {usingDemo ? 'Demo location on' : 'Use demo location'}
        </button>
      </div>

      {geoError && !usingDemo ? (
        <p className="status error">
          {geoError} Tap "Use demo location" to drop a pin in central Kuala Lumpur.
        </p>
      ) : null}

      <div className="map-canvas" ref={containerRef} />

      {navigating && routeMeta?.source === 'osrm' ? (
        <div className="nav-summary">
          <article>
            <span>Remaining</span>
            <strong>{formatDistance(remainingMeters)}</strong>
          </article>
          <article>
            <span>ETA</span>
            <strong>{formatDuration(remainingMinutes)}</strong>
          </article>
          <article>
            <span>Stops left</span>
            <strong>{dayPlan?.stops.length ?? 0}</strong>
          </article>
        </div>
      ) : null}

      {navigating && routeMeta?.steps && routeMeta.steps.length > 0 ? (
        <div className="nav-steps">
          <button className="link-button" onClick={() => setShowAllSteps((current) => !current)} type="button">
            {showAllSteps ? 'Hide all turns' : `Show all ${routeMeta.steps.length} turns`}
          </button>
          {showAllSteps ? (
            <ol className="step-list">
              {routeMeta.steps.map((step, index) => {
                const active = index === currentStepIndex
                return (
                  <li className={active ? 'step-row active' : 'step-row'} key={`${step.location.lat}-${index}`}>
                    <span className="step-icon">
                      <ManeuverIcon modifier={step.modifier} size={20} type={step.type} />
                    </span>
                    <div>
                      <p>{step.instruction}</p>
                      <span>{formatDistance(step.distanceMeters)}</span>
                    </div>
                  </li>
                )
              })}
            </ol>
          ) : null}
        </div>
      ) : null}

      <p className="map-hint">
        {position
          ? position.source === 'demo'
            ? 'Showing simulated location for demo purposes.'
            : `Live GPS \u00b7 accuracy \u00b1${Math.round(position.accuracyMeters)} m`
          : 'Showing planned route from territory home while waiting for location permission.'}
      </p>

      {dayPlan ? (
        <MascotChat
          currentCustomerId={dayPlan.stops[0]?.customer_id ?? null}
          salespersonId={dayPlan.salesperson_id}
          voiceEnabled={voiceEnabled}
        />
      ) : null}
    </section>
  )
}
