import { useEffect, useMemo, useRef, useState } from 'react'

import type { LivePosition } from './useGeolocation'
import { haversineMeters, type ManeuverStep } from '../lib/routing'

type UseTurnByTurnOptions = {
  active: boolean
  position: LivePosition | null
  steps: ManeuverStep[]
  voiceEnabled: boolean
  onArrivedAtStop?: (stopIndex: number) => void
  onArrivedAtFinal?: () => void
}

export function speak(text: string) {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  try {
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-US'
    utterance.rate = 1.05
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  } catch {
    // ignore speech failures silently
  }
}

export function useTurnByTurn({
  active,
  position,
  steps,
  voiceEnabled,
  onArrivedAtStop,
  onArrivedAtFinal,
}: UseTurnByTurnOptions) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const lastSpokenStepRef = useRef<number>(-1)
  const lastCountdownAnnouncedRef = useRef<number>(-1)

  useEffect(() => {
    if (!active) {
      setCurrentStepIndex(0)
      lastSpokenStepRef.current = -1
      lastCountdownAnnouncedRef.current = -1
    }
  }, [active])

  useEffect(() => {
    if (!active || !position || steps.length === 0) return

    let nearestIndex = currentStepIndex
    let nearestDistance = Number.POSITIVE_INFINITY
    for (let index = currentStepIndex; index < steps.length; index += 1) {
      const distance = haversineMeters(position, steps[index].location)
      if (distance < nearestDistance) {
        nearestDistance = distance
        nearestIndex = index
      }
    }

    if (nearestIndex !== currentStepIndex) {
      setCurrentStepIndex(nearestIndex)
    }
  }, [position, active, steps, currentStepIndex])

  const currentStep = steps[currentStepIndex]
  const nextStep = steps[currentStepIndex + 1]

  const distanceToManeuverMeters = useMemo(() => {
    if (!position || !nextStep) return null
    return haversineMeters(position, nextStep.location)
  }, [position, nextStep])

  useEffect(() => {
    if (!active || !currentStep) return
    if (lastSpokenStepRef.current === currentStepIndex) return
    if (!voiceEnabled) {
      lastSpokenStepRef.current = currentStepIndex
      return
    }
    speak(currentStep.instruction)
    lastSpokenStepRef.current = currentStepIndex
    lastCountdownAnnouncedRef.current = -1
  }, [active, currentStep, currentStepIndex, voiceEnabled])

  useEffect(() => {
    if (!active || !voiceEnabled || !nextStep || distanceToManeuverMeters == null) return
    const countdownThresholds = [200, 100, 40]
    for (const threshold of countdownThresholds) {
      if (
        distanceToManeuverMeters <= threshold &&
        lastCountdownAnnouncedRef.current > threshold
      ) {
        speak(`In ${threshold} meters, ${nextStep.instruction.toLowerCase()}`)
        lastCountdownAnnouncedRef.current = threshold
        break
      }
    }
    if (lastCountdownAnnouncedRef.current < 0 && distanceToManeuverMeters > 250) {
      lastCountdownAnnouncedRef.current = 250
    }
  }, [distanceToManeuverMeters, nextStep, active, voiceEnabled])

  const arrivedStopIndexRef = useRef<number>(-1)
  useEffect(() => {
    if (!active || !position || steps.length === 0) return
    const finalStep = steps[steps.length - 1]
    const distanceToFinal = haversineMeters(position, finalStep.location)

    if (distanceToFinal < 60 && arrivedStopIndexRef.current < finalStep.destinationStopIndex) {
      arrivedStopIndexRef.current = finalStep.destinationStopIndex
      if (voiceEnabled) speak('You have arrived at the customer.')
      onArrivedAtFinal?.()
    }

    let arrivedAt = arrivedStopIndexRef.current
    for (let index = currentStepIndex; index < steps.length; index += 1) {
      const step = steps[index]
      if (step.type === 'arrive' && haversineMeters(position, step.location) < 60) {
        if (step.destinationStopIndex > arrivedAt) {
          arrivedAt = step.destinationStopIndex
          arrivedStopIndexRef.current = arrivedAt
          if (voiceEnabled) speak(`Arrived at stop ${step.destinationStopIndex + 1}.`)
          onArrivedAtStop?.(step.destinationStopIndex)
        }
      }
    }
  }, [active, position, steps, currentStepIndex, voiceEnabled, onArrivedAtStop, onArrivedAtFinal])

  return {
    currentStep,
    currentStepIndex,
    distanceToManeuverMeters,
    nextStep,
  }
}
