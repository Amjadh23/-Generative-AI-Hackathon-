# Feature Spec: Hilti RouteIQ

## Product Summary

Hilti RouteIQ is an AI-powered sales visit copilot for Hilti field salespeople and account managers.

Google Maps tells the salesperson the shortest route. RouteIQ tells the salesperson the most valuable route.

It helps answer:

- Which customers should I visit today?
- Which customers are most valuable or urgent?
- What is the best route order?
- Why is this route better than another route?
- What should I focus on when meeting each customer?
- What happened after each visit?

## Problem

Hilti salespeople manage many assigned customers within a territory, but they have limited visit time each day. They may waste time visiting nearby low-value customers while missing high-value or urgent customers. RouteIQ balances expected sales return, urgency, location proximity, follow-up needs, and travel efficiency.

## Users

- Field salesperson: wants a clear route for today on a phone.
- Sales manager: wants better coverage of high-value accounts, route efficiency, and visibility into missed opportunities.
- Admin: optional setup user for demo/customer uploads, salesperson assignments, and territory maintenance.
- Hackathon judge: wants to see the AI decision, route optimization, and business value clearly.

## Workflow

1. Salesperson opens RouteIQ.
2. System loads the assigned customer portfolio.
3. Salesperson sets daily constraints.
4. System scores customers by value and urgency.
5. System selects the best customers to visit today.
6. System optimizes route order.
7. GenAI-style explanations describe route and customer choices.
8. Salesperson follows the visit plan.
9. Salesperson records outcomes and next actions.
10. Manager dashboard shows business impact.

## User Stories

1. As a salesperson, I can open the app and see today's recommended visit order.
2. As a salesperson, I can view the recommended route on a map with numbered stops.
3. As a salesperson, I can understand why each customer was selected.
4. As a salesperson, I can open navigation to the next customer in Google Maps.
5. As a salesperson, I can mark a visit as completed and see the plan update.
6. As a salesperson, I can see the recommended focus for each customer meeting.
7. As a manager, I can see route value, coverage, and visit outcomes.

## Acceptance Criteria

- The app generates a day plan for one salesperson from synthetic data.
- The day plan contains 5-8 ordered stops by default.
- Each stop includes customer name, location, expected return, score, ETA, and explanation.
- The route respects a salesperson's assigned territory.
- The API response for the demo salesperson returns in under two seconds.
- The frontend is mobile-first and installable as a PWA.
- The demo works without real Hilti data.

## Out of Scope for Hackathon

- Real CRM integration.
- Real authentication and role management.
- Production-grade road-network travel times.
- App store deployment.
- Multi-day workforce scheduling.
