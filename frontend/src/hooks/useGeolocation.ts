import { useEffect, useRef, useState } from 'react'

export type LivePosition = {
  lat: number
  lng: number
  accuracyMeters: number
  source: 'gps' | 'demo'
  timestamp: number
}

type UseGeolocationOptions = {
  enabled: boolean
  demoFallback?: { lat: number; lng: number } | null
}

const KL_CENTER = { lat: 3.139, lng: 101.6869 }

export function useGeolocation({ demoFallback, enabled }: UseGeolocationOptions) {
  const [position, setPosition] = useState<LivePosition | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [usingDemo, setUsingDemo] = useState(false)
  const watchIdRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled) return
    if (usingDemo) {
      const fallback = demoFallback ?? KL_CENTER
      setPosition({
        accuracyMeters: 30,
        lat: fallback.lat,
        lng: fallback.lng,
        source: 'demo',
        timestamp: Date.now(),
      })
      return
    }

    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setError('Geolocation is not supported in this browser.')
      return
    }

    const id = navigator.geolocation.watchPosition(
      (geo) => {
        setError(null)
        setPosition({
          accuracyMeters: geo.coords.accuracy,
          lat: geo.coords.latitude,
          lng: geo.coords.longitude,
          source: 'gps',
          timestamp: geo.timestamp,
        })
      },
      (caught) => {
        setError(caught.message || 'Unable to read location')
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    )
    watchIdRef.current = id

    return () => {
      if (watchIdRef.current != null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current)
      }
      watchIdRef.current = null
    }
  }, [enabled, usingDemo, demoFallback])

  const useDemoLocation = (toggle: boolean) => {
    setUsingDemo(toggle)
  }

  return { error, position, useDemoLocation, usingDemo }
}
