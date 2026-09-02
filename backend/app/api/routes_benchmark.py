from fastapi import APIRouter

from app.schemas.benchmark_schema import ClimateStressPoint, LeaderboardEntry
from app.services.benchmark_service import get_climate_stress_results, get_leaderboard

router = APIRouter(tags=["benchmark"])


@router.get("/benchmark/climate-stress", response_model=list[ClimateStressPoint])
def get_climate_stress_route():
    return get_climate_stress_results()


@router.get("/benchmark/results", response_model=list[LeaderboardEntry])
def get_leaderboard_route():
    return get_leaderboard()
