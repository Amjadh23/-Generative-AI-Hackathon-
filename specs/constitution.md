# Hilti Sales Router Constitution

## Principles

1. Mobile-first field workflow
   - The primary user is a salesperson using a phone between customer visits.
   - Core actions must be reachable with large tap targets and minimal typing.

2. Demo resilience
   - The app must work with synthetic data and no external paid services.
   - The latest generated day plan should remain visible offline in the PWA.

3. Explainable recommendations
   - Every recommended visit must include a short reason tied to score, proximity, and sales potential.
   - Avoid black-box output without human-readable evidence.

4. Fast enough for a live demo
   - The day-plan API should respond in under two seconds for the demo dataset.
   - The route should optimize a salesperson's top candidate customers, not every customer in the database.

5. Spec before code
   - User stories, data model, and API contracts are the source of truth.
   - Implementation changes should update the spec artifacts when behavior changes.
