# Data Model

## Territory

- `id`: string
- `name`: string
- `center_lat`: number
- `center_lng`: number
- `radius_km`: number

## Salesperson

- `id`: string
- `name`: string
- `territory_id`: string
- `home_lat`: number
- `home_lng`: number
- `max_daily_stops`: integer

## Customer

- `id`: string
- `name`: string
- `segment`: enum (`contractor`, `distributor`, `project_site`, `maintenance`)
- `territory_id`: string
- `lat`: number
- `lng`: number
- `priority`: integer from 1 to 5
- `avg_order_value_rm`: number
- `open_pipeline_rm`: number
- `last_visit_days`: integer
- `reorder_probability`: number from 0 to 1

## VisitHistory

- `id`: string
- `customer_id`: string
- `salesperson_id`: string
- `visited_at`: datetime
- `outcome`: enum (`order`, `follow_up`, `no_interest`, `closed`)
- `notes`: string

## Order

- `id`: string
- `customer_id`: string
- `order_date`: date
- `amount_rm`: number
- `product_family`: enum (`anchors`, `power_tools`, `firestop`, `measuring`, `fasteners`)

## DayPlan

- `salesperson_id`: string
- `date`: date
- `total_expected_return_rm`: number
- `total_distance_km`: number
- `stops`: array of `DayPlanStop`

## DayPlanStop

- `sequence`: integer
- `customer_id`: string
- `customer_name`: string
- `lat`: number
- `lng`: number
- `score`: number
- `expected_return_rm`: number
- `distance_from_previous_km`: number
- `eta_minutes`: integer
- `reason`: string
