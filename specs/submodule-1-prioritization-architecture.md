# Hilti RouteIQ — Submodule 1 Architecture
## Customer Visit Prioritization + Explainability Module

## 1. Purpose

Submodule 1 answers:

> **Which assigned customers are most worth visiting today, and why?**

It takes assigned customer data, predicts a **visit likelihood score**, converts that score into **Low / Medium / High priority**, then prepares SHAP-based explanation reasons for the LLM.

This module does **not** optimize the travel route. Route optimization happens in Submodule 2.

---

## 2. High-Level Flow

```text
Assigned customer data
↓
Feature engineering
↓
XGBoost regression scoring engine
↓
visit_likelihood_score: 0.0–1.0
↓
priority_class binning: Low / Medium / High
↓
SHAP local explanation
↓
feature_meanings.json sentence rendering
↓
LLM explanation payload
↓
Salesperson-facing recommendation
```

---

## 3. Critical Instruction: Remove `priority` as an Input Feature

The raw dataset contains a `priority` column, but **do not use it as a model input**.

Reason:

```text
Input priority → model → output priority
```

This is confusing and circular.

Correct approach:

```text
Customer features
→ XGBoost predicts visit_likelihood_score
→ priority_class is generated from the score
```

So:

```text
DO NOT use `priority` in:
- model input features
- SHAP feature list
- feature_meanings.json
- LLM explanation payload
```

`priority_class` is allowed only as an **output**, not an input.

---

## 4. Dataset Inputs

### 4.1 Customer data

From `customers.csv`, use:

```text
id
name
segment
territory_id
assigned_salesperson_id
lat
lng
avg_order_value_rm
open_pipeline_rm
last_visit_days
reorder_probability
```

Exclude:

```text
priority
```

### 4.2 Visit history

From `visit_history.csv`, use:

```text
customer_id
salesperson_id
visited_at
outcome
notes
```

Possible outcomes:

```text
order
closed
follow_up
no_interest
```

### 4.3 Order history

From `orders.csv`, use:

```text
customer_id
order_date
amount_rm
product_family
```

### 4.4 Salesperson data

From `salespeople.csv`, use:

```text
id
territory_id
home_lat
home_lng
max_daily_stops
```

---

## 5. Feature Engineering Layer

### 5.1 Direct model features

Use directly:

```text
segment
territory_id
assigned_salesperson_id
lat
lng
avg_order_value_rm
open_pipeline_rm
last_visit_days
reorder_probability
```

### 5.2 Derived model features

Engineer these:

```text
past_order_count
total_order_value_rm
days_since_last_order
visit_count
last_visit_outcome
distance_from_salesperson_home_km
nearby_customer_count
open_pipeline_band
avg_order_value_band
total_order_value_band
```

### 5.3 Recommended final feature set

```text
segment_encoded
territory_id_encoded
avg_order_value_band_encoded
open_pipeline_band_encoded
last_visit_days
reorder_probability
past_order_count
total_order_value_band_encoded
days_since_last_order
visit_count
last_visit_outcome_encoded
distance_from_salesperson_home_km
nearby_customer_count
```

Again: **no `priority` feature**.

---

## 6. Target Concept

The model predicts:

> **How likely this customer is to produce a worthwhile sales outcome if visited today.**

Worthwhile outcome:

```text
order
closed
follow_up
```

Negative outcome:

```text
no_interest
```

Model output:

```text
visit_likelihood_score = 0.0 to 1.0
```

---

## 7. Scoring Engine

The scoring engine is:

```text
XGBoost regression model
→ predicts visit_likelihood_score
```

Example:

```text
Customer A → 0.86
Customer B → 0.54
Customer C → 0.22
```

Meaning:

```text
0.86 = highly worth visiting
0.54 = moderately worth visiting
0.22 = low worthiness
```

Then bin the score:

```text
0.00–0.39 = Low Priority
0.40–0.69 = Medium Priority
0.70–1.00 = High Priority
```

Output fields:

```text
visit_likelihood_score
priority_class
```

---

## 8. Deal Value Handling

The model should not blindly prioritize the biggest deal.

Correct logic:

```text
Deal value is one feature.
It is not the target.
```

The model uses deal value together with other signals:

```text
open_pipeline_band
avg_order_value_band
reorder_probability
last_visit_days
past_order_count
last_visit_outcome
```

Then SHAP explains whether the deal value range helped the prediction.

Good explanation style:

```text
This customer's open pipeline is in the RM50k–RM100k range, and this increased the predicted visit priority.
```

Avoid:

```text
This customer is worth visiting only because the deal is RM100k.
```

---

## 9. SHAP Explanation Layer

After prediction, SHAP identifies which features pushed the score up or down.

For salesperson explanation, keep the top positive contributors:

```text
feature name
actual value
SHAP value
effect: increased_priority / decreased_priority
meaning sentence
```

Example:

```json
{
  "feature": "reorder_probability",
  "actual_value": 0.82,
  "shap_value": 0.18,
  "effect": "increased_priority",
  "meaning": "This customer has an 82% reorder probability, which increased the predicted visit priority."
}
```

---

## 10. feature_meanings.json

Purpose:

```text
Convert raw SHAP features into human-readable explanation sentences.
```

Recommended version:

```json
{
  "reorder_probability": "This customer has a {percent_value}% reorder probability, which increased the predicted visit priority.",
  "last_visit_days": "This customer has not been visited for {int_value} day(s), which may indicate a timely follow-up opportunity.",
  "open_pipeline_band_encoded": "This customer's open pipeline is in the {band_value} range, and this contributed to the visit-likelihood score.",
  "avg_order_value_band_encoded": "This customer's usual order value is in the {band_value} range, and this contributed to the visit-likelihood score.",
  "total_order_value_band_encoded": "This customer's total historical order value is in the {band_value} range, and this contributed to the visit-likelihood score.",
  "past_order_count": "This customer has placed {int_value} past order(s), showing existing buying history.",
  "days_since_last_order": "This customer has not placed an order for {int_value} day(s).",
  "visit_count": "This customer has been visited {int_value} time(s) before.",
  "last_visit_outcome_encoded": "The previous visit outcome contributed to the model's visit-likelihood estimate.",
  "distance_from_salesperson_home_km": "This customer is {value_rounded} km away from the salesperson's starting location.",
  "nearby_customer_count": "There are {int_value} nearby customers in the same area.",
  "segment_encoded": "This customer's segment contributed to the model's visit-likelihood estimate.",
  "territory_id_encoded": "This customer's territory contributed to the model's visit-likelihood estimate."
}
```

Do **not** include:

```json
"priority": "..."
```

---

## 11. LLM Payload

The LLM receives structured model output. It does not invent reasons.

Example:

```json
{
  "customer_id": "cust-0001",
  "customer_name": "Apex Construction 001",
  "visit_likelihood_score": 0.86,
  "priority_class": "High",
  "recommended_action": "Visit today",
  "xgboost_explanation_payload": {
    "base_value": 0.43,
    "top_priority_reasons": [
      {
        "feature": "reorder_probability",
        "actual_value": 0.776,
        "shap_value": 0.19,
        "effect": "increased_priority",
        "meaning": "This customer has a 78% reorder probability, which increased the predicted visit priority."
      },
      {
        "feature": "last_visit_days",
        "actual_value": 99,
        "shap_value": 0.14,
        "effect": "increased_priority",
        "meaning": "This customer has not been visited for 99 day(s), which may indicate a timely follow-up opportunity."
      },
      {
        "feature": "open_pipeline_band_encoded",
        "actual_value": "RM10k–RM30k",
        "shap_value": 0.09,
        "effect": "increased_priority",
        "meaning": "This customer's open pipeline is in the RM10k–RM30k range, and this contributed to the visit-likelihood score."
      }
    ]
  }
}
```

---

## 12. What the LLM Does

The LLM converts the payload into simple bullets.

Example output:

```text
Apex Construction 001 is a high-priority visit today because:

- They have a strong reorder probability of 78%.
- They have not been visited for 99 days, making follow-up timely.
- Their open pipeline is in the RM10k–RM30k range, which contributed positively to the model's score.

Suggested focus:
- Visit today and focus on moving the open pipeline toward an order.
```

The LLM must not:

```text
invent new reasons
change the score
change the priority class
override the XGBoost prediction
claim the customer will definitely buy
```

---

## 13. Salesperson Impact

This matters because the salesperson needs more than a route.

They need:

```text
who to visit
why that customer is worth visiting
what to focus on during the meeting
whether the recommendation makes sense
```

Without explanation:

```text
Visit Apex Construction first.
```

With explanation:

```text
Visit Apex Construction first because they have 78% reorder probability,
have not been visited for 99 days, and have a promising open pipeline range.
```

The second version helps the salesperson prepare and trust the recommendation.

---

## 14. Final Output of Submodule 1

```json
[
  {
    "customer_id": "cust-0001",
    "customer_name": "Apex Construction 001",
    "visit_likelihood_score": 0.86,
    "priority_class": "High",
    "recommended_action": "Visit today",
    "top_reasons": [
      "This customer has a 78% reorder probability.",
      "This customer has not been visited for 99 day(s).",
      "This customer's open pipeline is in the RM10k–RM30k range."
    ],
    "coordinates": {
      "lat": 3.174344,
      "lng": 101.651225
    }
  }
]
```

This output goes to Submodule 2:

```text
Route Optimizer
```

Submodule 2 uses:

```text
selected customers
coordinates
priority_class
max_daily_stops
estimated visit duration
```

to decide the best visit order.

---

## 15. Kiro / Codex Instruction

Implement Submodule 1 using the architecture above.

Mandatory correction:

```text
Remove `priority` from all model input features.
Do not include `priority` in feature_columns.json.
Do not include `priority` in feature_meanings.json.
Do not include `priority` in SHAP reasons.
Do not include `priority` in the LLM explanation payload.
Only use `priority_class` as the generated output after binning `visit_likelihood_score`.
```

Final flow:

```text
customer features without priority
→ XGBoost regression likelihood score
→ Low / Medium / High priority_class
→ SHAP explanation
→ feature_meanings.json rendering
→ LLM explanation
→ ranked customer list
```

---

## 16. One-Line Pitch

> **Submodule 1 predicts which customers are worth visiting today, explains the reasons using SHAP, and gives the salesperson a clear AI-generated rationale before the route is optimized.**
