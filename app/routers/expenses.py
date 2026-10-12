from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.queries import expense_queries as eq
from app.routers.trips import get_own_trip
from app.schemas.expense import ExpenseCreate, ExpenseOut

router = APIRouter(prefix="/trips/{trip_id}/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def log_expense(body: ExpenseCreate, trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    new_id = eq.add_expense(conn, trip["trip_id"], body.amount, body.category,
                            body.spent_date, body.note)
    return eq.get_expense(conn, trip["trip_id"], new_id)


@router.get("", response_model=list[ExpenseOut])
def list_expenses(trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    return eq.list_expenses(conn, trip["trip_id"])


@router.get("/summary")
def expense_summary(trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    """Total spent per category (GROUP BY)."""
    rows = eq.expense_totals_by_category(conn, trip["trip_id"])
    return [{"category": r["category"], "total": float(r["total"])} for r in rows]


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_expense(expense_id: int, trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    if eq.get_expense(conn, trip["trip_id"], expense_id) is None:
        raise HTTPException(status_code=404, detail="Expense not found in this trip")
    eq.delete_expense(conn, expense_id)
