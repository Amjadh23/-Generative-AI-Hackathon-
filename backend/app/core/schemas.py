from datetime import date

from pydantic import BaseModel, Field


class DayPlanStop(BaseModel):
    sequence: int
    customer_id: str
    customer_name: str
    segment: str
    lat: float
    lng: float
    score: float = Field(ge=0)
    expected_return_rm: float = Field(ge=0)
    distance_from_previous_km: float = Field(ge=0)
    eta_minutes: int = Field(ge=0)
    reason: str
    focus: str


class OptimizationSummary(BaseModel):
    routes_evaluated: int = Field(ge=0)
    baseline_expected_return_rm: float = Field(ge=0)
    baseline_distance_km: float = Field(ge=0)
    value_gain_rm: float
    distance_saved_km: float
    value_uplift_pct: float


class DayPlan(BaseModel):
    salesperson_id: str
    date: date
    total_expected_return_rm: float = Field(ge=0)
    total_distance_km: float = Field(ge=0)
    stops: list[DayPlanStop]
    optimization_summary: OptimizationSummary | None = None


class VisitCreate(BaseModel):
    customer_id: str
    salesperson_id: str
    outcome: str
    notes: str | None = None


class VisitCreated(BaseModel):
    id: str
    status: str


class AssistantRequest(BaseModel):
    salesperson_id: str
    question: str = Field(min_length=1, max_length=500)
    current_customer_id: str | None = None


class AssistantResponse(BaseModel):
    answer: str
    intent: str
    related_customer_id: str | None = None
    suggestions: list[str] = Field(default_factory=list)
