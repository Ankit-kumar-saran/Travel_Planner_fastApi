from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.database import get_db
from app.queries import place_queries as pq
from app.queries import trip_queries as tq
from app.schemas.trip import (
    BudgetSummary,
    OptimizeRequest,
    ReorderRequest,
    StopCreate,
    StopOut,
    StopUpdate,
    TripCreate,
    TripDetailOut,
    TripOut,
)

router = APIRouter(prefix="/trips", tags=["trips"])


def get_own_trip(trip_id: int, conn=Depends(get_db), user: dict = Depends(get_current_user)) -> dict:
    """Dependency used by every route with {trip_id} in the path.
    404 if the trip does not exist, 403 if it belongs to somebody else."""
    trip = tq.get_trip(conn, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="This trip belongs to another user")
    return trip


def _budget(conn, trip_id: int) -> BudgetSummary:
    row = tq.get_budget_summary(conn, trip_id)
    planned = float(row["planned_budget"] or 0)
    actual = float(row["actual_spent"])
    return BudgetSummary(
        planned_budget=planned,
        itinerary_cost=float(row["itinerary_cost"]),
        actual_spent=actual,
        remaining=planned - actual,
        percent_spent=round(actual / planned * 100, 1) if planned > 0 else 0.0,
    )


# ---------- Trips ----------

@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED)
def create_trip(body: TripCreate, conn=Depends(get_db), user: dict = Depends(get_current_user)):
    if pq.get_city_by_id(conn, body.city_id) is None:
        raise HTTPException(status_code=404, detail="City not found")
    new_id = tq.create_trip(conn, user["user_id"], body.city_id, body.planned_budget,
                            body.start_date, body.end_date)
    return tq.get_trip(conn, new_id)


@router.get("", response_model=list[TripOut])
def my_trips(conn=Depends(get_db), user: dict = Depends(get_current_user)):
    return tq.list_trips(conn, user["user_id"])


@router.get("/{trip_id}", response_model=TripDetailOut)
def trip_detail(trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    return TripDetailOut(
        trip=trip, budget=_budget(conn, trip["trip_id"]), stops=tq.list_stops(conn, trip["trip_id"])
    )


@router.get("/{trip_id}/budget", response_model=BudgetSummary)
def trip_budget(trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    return _budget(conn, trip["trip_id"])


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_trip(trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    tq.delete_trip(conn, trip["trip_id"])


# ---------- Stops ----------

@router.post("/{trip_id}/places", response_model=StopOut, status_code=status.HTTP_201_CREATED)
def add_stop(body: StopCreate, trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    place = pq.get_place_by_id(conn, body.place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    trip_id = trip["trip_id"]
    # If no cost was sent, use the place's average cost as the planned cost
    cost = body.planned_cost if body.planned_cost is not None else place["avg_cost"]
    if body.visit_order is None:
        order = tq.next_visit_order(conn, trip_id, body.day_number)
    else:
        # Inserting in the middle: push the later stops down by one first
        order = body.visit_order
        tq.shift_orders_from(conn, trip_id, body.day_number, order)
    stop_id = tq.insert_stop(conn, trip_id, body.place_id, body.day_number, order, cost)
    conn.commit()
    return tq.get_stop(conn, trip_id, stop_id)


@router.patch("/{trip_id}/places/{stop_id}", response_model=StopOut)
def edit_stop(stop_id: int, body: StopUpdate, trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    trip_id = trip["trip_id"]
    stop = tq.get_stop(conn, trip_id, stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail="Stop not found in this trip")

    new_day = body.day_number if body.day_number is not None else stop["day_number"]
    new_cost = body.planned_cost if body.planned_cost is not None else stop["planned_cost"]
    old_day = stop["day_number"]

    if body.day_number is not None and new_day != old_day:
        # Moved to another day: goes to the end of that day unless an order was given
        new_order = body.visit_order or tq.next_visit_order(conn, trip_id, new_day)
        if body.visit_order is not None:
            tq.shift_orders_from(conn, trip_id, new_day, new_order)
    else:
        new_order = body.visit_order if body.visit_order is not None else stop["visit_order"]
        if body.visit_order is not None and body.visit_order != stop["visit_order"]:
            tq.shift_orders_from(conn, trip_id, new_day, new_order)

    tq.update_stop_fields(conn, stop_id, new_day, new_order, new_cost)
    # Tidy both days so visit_order is always 1, 2, 3 ... with no gaps or duplicates
    tq.renumber_day(conn, trip_id, new_day)
    if new_day != old_day:
        tq.renumber_day(conn, trip_id, old_day)
    conn.commit()
    return tq.get_stop(conn, trip_id, stop_id)


@router.delete("/{trip_id}/places/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stop(stop_id: int, trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    stop = tq.get_stop(conn, trip["trip_id"], stop_id)
    if stop is None:
        raise HTTPException(status_code=404, detail="Stop not found in this trip")
    tq.delete_stop(conn, stop_id)
    tq.renumber_day(conn, trip["trip_id"], stop["day_number"])
    conn.commit()


@router.put("/{trip_id}/days/{day_number}/order", response_model=list[StopOut])
def reorder_day(day_number: int, body: ReorderRequest, trip: dict = Depends(get_own_trip),
                conn=Depends(get_db)):
    """Manual reordering: send ALL stop ids of that day in the order you want."""
    trip_id = trip["trip_id"]
    current = [s["id"] for s in tq.list_stops(conn, trip_id) if s["day_number"] == day_number]
    if sorted(current) != sorted(body.stop_ids):
        raise HTTPException(
            status_code=400,
            detail="stop_ids must contain exactly the stops of this day (each one once)",
        )
    tq.set_day_order(conn, body.stop_ids)
    conn.commit()
    return [s for s in tq.list_stops(conn, trip_id) if s["day_number"] == day_number]


@router.post("/{trip_id}/days/{day_number}/optimize", response_model=list[StopOut])
def optimize_day(day_number: int, body: OptimizeRequest | None = None,
                 trip: dict = Depends(get_own_trip), conn=Depends(get_db)):
    """One-click 'optimise by distance': re-orders the stops of a day by Haversine distance."""
    trip_id = trip["trip_id"]
    first = tq.get_first_stop_coords(conn, trip_id, day_number)
    if first is None:
        raise HTTPException(status_code=404, detail="No stops on that day")
    if body is not None and body.ref_lat is not None:
        ref_lat, ref_lng = body.ref_lat, body.ref_lng
    else:
        # No reference point sent: start from the first stop of the day
        ref_lat, ref_lng = first["latitude"], first["longitude"]
    tq.optimize_day_by_distance(conn, trip_id, day_number, ref_lat, ref_lng)
    return [s for s in tq.list_stops(conn, trip_id) if s["day_number"] == day_number]
