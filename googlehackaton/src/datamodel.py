from pydantic import BaseModel, Field
from typing_extensions import TypedDict



class GraphState(TypedDict):
    """Represents the state of our graph.

    Attributes:
        question: question
        start: A dict containing start of the trip (name, lat, long) and starting time (and date)
        end: A dict containing end of the trip (name, lat, long) and ending time 
        stops: A list of dicts containing stops (name, lat, long) and time that goes between start and end
        mode_of_transport: A dict containing mode of transport (car, bus, train, etc) and time it takes to go from start to end
    """

    question: str
    origin: str
    origin_lat: float
    origin_long: float
    destination: str
    destination_lat: float
    destination_long: float
    handicap: str
    trip: dict



class FindUserData(BaseModel):
    """Binary score for relevance check on retrieved documents."""

    origin: str = Field(
        description="Where the user will travle from"
    )
    destination: str = Field(
        description="Where the user will travle to"
    )
    time: str = Field(
        description="When the user will travle, if not, Now"
    )
    handicap: str = Field(
        description="If the user uses a wheelchair or has reduced eyesight, if not, None"
    )

