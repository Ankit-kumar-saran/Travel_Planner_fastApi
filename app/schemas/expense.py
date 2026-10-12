from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# Literal means: the value must be exactly one of these strings (FastAPI returns 422 otherwise)
ExpenseCategory = Literal["Food", "Travel", "Shopping", "Tickets", "Other"]


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    category: ExpenseCategory = "Other"
    spent_date: date
    note: str | None = Field(default=None, max_length=255)


class ExpenseOut(BaseModel):
    id: int
    trip_id: int
    amount: float
    category: str | None = None
    spent_date: date
    note: str | None = None
