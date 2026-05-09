import { useEffect, useState } from 'react'

import { Mascot } from './Mascot'

const STORAGE_KEY = 'routeiq.onboarding.v1'

const STEPS = [
  {
    title: "Hi, I'm RIQ",
    body: "I'm your AI sales copilot. I rank your customers by value, urgency, and proximity, then plan the most valuable visit route for today.",
  },
  {
    title: 'Today shows your plan',
    body: 'See the ordered visit list with expected return, score, and the focus for each meeting. Tap a customer to see the full breakdown.',
  },
  {
    title: 'Map handles the navigation',
    body: 'Live GPS, real-road routing, voice turn-by-turn. Tap Start navigation and I will guide you between customers.',
  },
]

export function Onboarding() {
  const [step, setStep] = useState(0)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const seen = window.localStorage.getItem(STORAGE_KEY)
    if (!seen) setOpen(true)
  }, [])

  if (!open) return null

  const dismiss = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, '1')
    }
    setOpen(false)
  }

  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div aria-modal="true" className="onboarding" role="dialog">
      <div className="onboarding-card">
        <button aria-label="Skip" className="onboarding-close" onClick={dismiss} type="button">
          <svg
            aria-hidden="true"
            fill="none"
            height="20"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
            width="20"
          >
            <path d="m6 6 12 12M18 6 6 18" />
          </svg>
        </button>

        <div className="onboarding-mascot">
          <Mascot mood="happy" size={120} waving={step === 0} />
        </div>
        <span className="onboarding-step">
          Step {step + 1} of {STEPS.length}
        </span>
        <h2>{current.title}</h2>
        <p>{current.body}</p>

        <div className="onboarding-dots">
          {STEPS.map((dotStep, index) => (
            <span
              aria-current={index === step ? 'step' : undefined}
              className={index === step ? 'dot active' : 'dot'}
              key={dotStep.title}
            />
          ))}
        </div>

        <button
          className="primary-action onboarding-primary"
          onClick={() => (isLast ? dismiss() : setStep((current) => current + 1))}
          type="button"
        >
          {isLast ? "Let's go" : 'Next'}
        </button>
      </div>
    </div>
  )
}
