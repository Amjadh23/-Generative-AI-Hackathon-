import { useCallback, useState } from 'react'

import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import {
  logVisitSentiment,
  recapVisit,
  type VisitRecap as VisitRecapType,
  type VisitSentiment,
  type VisitSentimentResult,
} from '../lib/api'
import { Mascot } from './Mascot'

type VisitRecapProps = {
  customerId: string
  customerName: string
  salespersonId: string
  onPersisted: () => void
}

const SAMPLE_TRANSCRIPT =
  "Met with the project manager. They were happy with the recent anchor delivery and asked for a firestop quote for two more sites. Want me to send a formal proposal next Tuesday."

const QUICK_SENTIMENTS: { id: VisitSentiment; label: string }[] = [
  { id: 'very_negative', label: 'Very negative' },
  { id: 'negative', label: 'Negative' },
  { id: 'neutral', label: 'Neutral' },
  { id: 'positive', label: 'Positive' },
  { id: 'very_positive', label: 'Very positive' },
]

function sentimentTone(sentiment: string): 'positive' | 'neutral' | 'negative' {
  if (sentiment.includes('positive')) return 'positive'
  if (sentiment.includes('negative')) return 'negative'
  return 'neutral'
}

export function VisitRecapPanel({
  customerId,
  customerName,
  onPersisted,
  salespersonId,
}: VisitRecapProps) {
  const [transcript, setTranscript] = useState('')
  const [recap, setRecap] = useState<VisitRecapType | null>(null)
  const [quickResult, setQuickResult] = useState<VisitSentimentResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [quickSaving, setQuickSaving] = useState<VisitSentiment | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleResult = useCallback((text: string) => {
    setTranscript(text)
  }, [])

  const {
    error: speechError,
    listening,
    start: startListening,
    stop: stopListening,
    supported: speechSupported,
  } = useSpeechRecognition({ onResult: handleResult })

  const onMicClick = () => {
    if (!speechSupported) return
    if (listening) {
      stopListening()
    } else {
      startListening()
    }
  }

  const submit = async (persist: boolean) => {
    if (!transcript.trim() || loading) return
    stopListening()
    setLoading(true)
    setError(null)
    try {
      const result = await recapVisit({
        customerId,
        persist,
        salespersonId,
        transcript: transcript.trim(),
      })
      setRecap(result)
      setQuickResult(null)
      if (result.persisted) {
        onPersisted()
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Could not generate recap.'
      setError(
        message.includes('503')
          ? 'AI recap is offline. Make sure Ollama is running on localhost:11434.'
          : message,
      )
    } finally {
      setLoading(false)
    }
  }

  const submitQuickSentiment = async (sentiment: VisitSentiment) => {
    if (quickSaving || loading) return
    stopListening()
    setQuickSaving(sentiment)
    setError(null)
    try {
      const result = await logVisitSentiment({
        customerId,
        salespersonId,
        sentiment,
      })
      setQuickResult(result)
      setRecap(null)
      onPersisted()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save visit sentiment.')
    } finally {
      setQuickSaving(null)
    }
  }

  return (
    <section aria-label="AI visit recap" className="recap-card">
      <header className="recap-header">
        <Mascot mood="happy" size={36} />
        <div>
          <h3>AI visit recap</h3>
          <p>Speak or type your raw notes, and I'll structure them for the CRM.</p>
        </div>
      </header>

      <label className="notes-field recap-input">
        <span>Your notes about the visit with {customerName}</span>
        <textarea
          disabled={loading}
          onChange={(event) => setTranscript(event.target.value)}
          placeholder={listening ? 'Listening...' : SAMPLE_TRANSCRIPT}
          rows={4}
          value={transcript}
        />
      </label>

      <div className="recap-actions">
        <button
          aria-label={listening ? 'Stop voice input' : 'Speak your note'}
          className={listening ? 'chip-button danger' : 'chip-button'}
          disabled={!speechSupported || loading}
          onClick={onMicClick}
          type="button"
        >
          {listening ? '■ Stop' : speechSupported ? '🎤 Speak' : '🎤 Voice unsupported'}
        </button>
        <button
          className="chip-button"
          disabled={loading || transcript.trim().length === 0}
          onClick={() => submit(false)}
          type="button"
        >
          Preview only
        </button>
        <button
          className="chip-button primary"
          disabled={loading || transcript.trim().length === 0}
          onClick={() => submit(true)}
          type="button"
        >
          {loading ? 'Thinking...' : 'Recap & save'}
        </button>
      </div>

      <div className="quick-sentiment" aria-label="Quick visit sentiment">
        <span>Quick sentiment</span>
        <div className="quick-sentiment-grid">
          {QUICK_SENTIMENTS.map((option) => (
            <button
              className={`quick-sentiment-button quick-sentiment-button--${sentimentTone(option.id)}`}
              disabled={loading || quickSaving !== null}
              key={option.id}
              onClick={() => void submitQuickSentiment(option.id)}
              type="button"
            >
              {quickSaving === option.id ? 'Saving...' : option.label}
            </button>
          ))}
        </div>
      </div>

      {error || speechError ? <p className="status error">{error ?? speechError}</p> : null}

      {recap ? (
        <article className="recap-result">
          <header className="recap-result-header">
            <strong>{recap.persisted ? 'Saved to CRM' : 'Preview'}</strong>
            <span className={`sentiment-pill sentiment-${recap.sentiment}`}>
              {recap.sentiment}
            </span>
            <span className="confidence-pill">
              AI {Math.round(recap.confidence * 100)}%
            </span>
            <span className="confidence-pill">
              {Math.round(recap.sentiment_confidence_score * 100)}% customer confidence
            </span>
          </header>
          <p className="recap-summary">{recap.summary}</p>
          <dl className="recap-fields">
            <div>
              <dt>Outcome</dt>
              <dd>{recap.outcome.replace('_', ' ')}</dd>
            </div>
            <div>
              <dt>Next action</dt>
              <dd>{recap.next_action}</dd>
            </div>
            {recap.due_date ? (
              <div>
                <dt>Due</dt>
                <dd>{recap.due_date}</dd>
              </div>
            ) : null}
            {recap.products_mentioned.length > 0 ? (
              <div>
                <dt>Products</dt>
                <dd>
                  {recap.products_mentioned.map((product) => (
                    <span className="product-pill" key={product}>
                      {product.replace('_', ' ')}
                    </span>
                  ))}
                </dd>
              </div>
            ) : null}
          </dl>
        </article>
      ) : null}

      {quickResult ? (
        <article className="recap-result">
          <header className="recap-result-header">
            <strong>Visit sentiment saved</strong>
            <span className={`sentiment-pill sentiment-${sentimentTone(quickResult.sentiment)}`}>
              {quickResult.sentiment_label}
            </span>
            <span className="confidence-pill">
              {Math.round(quickResult.sentiment_confidence_score * 100)}% customer confidence
            </span>
          </header>
          <p className="recap-summary">
            Manager dashboard confidence moved from{' '}
            {Math.round(quickResult.previous_sentiment_confidence_score * 100)}% to{' '}
            {Math.round(quickResult.sentiment_confidence_score * 100)}%.
          </p>
        </article>
      ) : null}
    </section>
  )
}
