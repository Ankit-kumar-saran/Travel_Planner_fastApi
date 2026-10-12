from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class TripCreate(BaseModel):
    city_id: int
    planned_budget: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self):
        # A model_validator runs after all fields are validated, so we can compare two fields
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class TripOut(BaseModel):
    trip_id: int
    user_id: int
    city_id: int
    city: str
    planned_budget: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime | None = None


class StopCreate(BaseModel):
    """Add a place to a trip. If visit_order is left empty it goes to the end of that day."""
    place_id: int
    day_number: int = Field(ge=1)
    visit_order: int | None = Field(default=None, ge=1)
    planned_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class StopUpdate(BaseModel):
    """Every field is optional: only the fields you send are changed."""
    day_number: int | None = Field(default=None, ge=1)
    visit_order: int | None = Field(default=None, ge=1)
    planned_cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class StopOut(BaseModel):
    id: int
    trip_id: int
    place_id: int
    place_name: str
    category: str
    latitude: float
    longitude: float
    day_number: int
    visit_order: int
    planned_cost: float | None = None


class ReorderRequest(BaseModel):
    """The stop ids of one day, in the new order you want (first id becomes visit_order 1)."""
    stop_ids: list[int] = Field(min_length=1)


class OptimizeRequest(BaseModel):
    """Reference point for 'optimise by distance'. If both are empty, we start from the
    first stop of that day."""
    ref_lat: Decimal | None = Field(default=None, ge=-90, le=90)
    ref_lng: Decimal | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def both_or_none(self):
        if (self.ref_lat is None) != (self.ref_lng is None):
            raise ValueError("Send both ref_lat and ref_lng, or neither")
        return self


class BudgetSummary(BaseModel):
    planned_budget: float
    itinerary_cost: float
    actual_spent: float
    remaining: float
    # Percentage of the planned budget already spent (0 if the budget is 0)
    percent_spent: float


class TripDetailOut(BaseModel):
    trip: TripOut
    budget: BudgetSummary
    stops: list[StopOut]
