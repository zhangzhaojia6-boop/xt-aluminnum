"""Global configuration endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/config", tags=["config"])

ALLOY_GRADES = [
    "1060",
    "1100",
    "3003",
    "3004",
    "3A21",
    "5052",
    "5083",
    "5754",
    "6061",
    "6063",
    "6082",
    "8011",
    "8079",
]

MATERIAL_STATES = [
    "O",
    "H12",
    "H14",
    "H16",
    "H18",
    "H22",
    "H24",
    "H26",
    "H32",
    "T4",
    "T6",
]


@router.get("/alloy-grades")
def get_alloy_grades():
    return ALLOY_GRADES


@router.get("/material-states")
def get_material_states():
    return MATERIAL_STATES
