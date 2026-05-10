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
    visit_likelihood_score: float = Field(ge=0, le=1)
    priority_class: str
    recommended_action: str
    top_reasons: list[str] = Field(default_factory=list)
    expected_return_rm: float = Field(ge=0)
    distance_from_previous_km: float = Field(ge=0)
    eta_minutes: int = Field(ge=0)
    visit_duration_minutes: int = Field(ge=0, description="Estimated on-site visit time (Submodule 2).")
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
    max_stops: int | None = Field(default=None, ge=1, le=10)


class AssistantResponse(BaseModel):
    answer: str
    intent: str
    related_customer_id: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class VisitRecapRequest(BaseModel):
    customer_id: str
    salesperson_id: str
    transcript: str = Field(min_length=1, max_length=4000)
    persist: bool = True


class VisitRecapResponse(BaseModel):
    visit_id: str | None = None
    persisted: bool = False
    summary: str
    outcome: str
    next_action: str
    due_date: str | None = None
    products_mentioned: list[str] = Field(default_factory=list)
    sentiment: str
    confidence: float = Field(ge=0, le=1)
    previous_sentiment_confidence_score: float | None = Field(default=None, ge=0, le=1)
    sentiment_confidence_score: float = Field(ge=0, le=1)
    raw_transcript: str


class VisitSentimentRequest(BaseModel):
    customer_id: str
    salesperson_id: str
    sentiment: str = Field(min_length=1, max_length=32)


class VisitSentimentResponse(BaseModel):
    visit_id: str
    status: str
    sentiment: str
    sentiment_label: str
    outcome: str
    previous_sentiment_confidence_score: float = Field(ge=0, le=1)
    sentiment_confidence_score: float = Field(ge=0, le=1)


class CustomerAssignmentPayload(BaseModel):
    salesperson_id: str


class CustomerAssignmentResult(BaseModel):
    customer_id: str
    salesperson_id: str
    territory_id: str
