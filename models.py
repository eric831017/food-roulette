from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    line_user_id: str
    display_name: Optional[str] = None
    location_1_lat: Optional[float] = None
    location_1_lng: Optional[float] = None
    location_1_name: Optional[str] = None
    location_2_lat: Optional[float] = None
    location_2_lng: Optional[float] = None
    location_2_name: Optional[str] = None
    onboard_complete: bool = False


@dataclass
class Restaurant:
    place_id: str
    name: str
    rating: float
    lat: float
    lng: float
    distance_meters: int
    price_level: Optional[int] = None
    photo_reference: Optional[str] = None
    types: list = field(default_factory=list)
    inferred_type: str = ""
    phone: Optional[str] = None


@dataclass
class PushLog:
    id: int
    line_user_id: str
    place_id: str
    place_name: str
    place_lat: float
    place_lng: float
    meal_type: str
    distance_meters: int
    is_adhoc: bool = False
