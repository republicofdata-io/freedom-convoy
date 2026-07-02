"""Pydantic models for structured extraction.

These are the shapes the model returns per page. Citation fields (volume,
chapter, page numbers, run metadata) are injected by the pipeline afterwards —
the model never generates a citation, only a verbatim source_quote that the
verifier checks against the page text.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ActorType = Literal[
    "protester",
    "organizer",
    "supporter",
    "counter_protester",
    "police",
    "government",
    "donor",
    "platform",
    "other",
]

EventType = Literal[
    "mobilization",
    "blockade",
    "occupation",
    "arrest",
    "escalation",
    "negotiation",
    "state_response",
    "other",
]

MovementPhase = Literal["buildup", "occupation", "state_response", "aftermath"]

ResponseType = Literal[
    "legislative",
    "policing",
    "financial",
    "judicial",
    "municipal",
    "provincial",
    "federal",
    "other",
]


class ExtractedActor(BaseModel):
    """A person, organization, agency, or platform involved in the events."""

    name: str = Field(description="Canonical full name as stated in the text")
    actor_type: ActorType
    actor_role: Optional[str] = Field(
        default=None, description="e.g. 'lead organizer', 'spokesperson', 'OPS Chief'"
    )
    affiliation: Optional[str] = Field(
        default=None, description="Organization, agency, or platform the actor belongs to"
    )
    jurisdiction: Optional[str] = Field(
        default=None, description="'federal', 'Ontario', 'Ottawa', 'Alberta', etc."
    )
    source_quote: str = Field(
        description="Verbatim sentence(s) from the page this actor fact comes from"
    )


class ExtractedLocation(BaseModel):
    """A place where protest activity or state response occurred."""

    name: str = Field(description="e.g. 'Ambassador Bridge', 'Parliament Hill', 'Coutts'")
    location_type: Optional[
        Literal["occupation_zone", "border_crossing", "city", "route", "building", "other"]
    ] = None
    city: Optional[str] = None
    province: Optional[str] = Field(default=None, description="Two-letter code: ON, AB, MB, BC…")
    source_quote: str


class ActorInvolvement(BaseModel):
    actor_name: str = Field(description="Must match a name in this page's actors list")
    involvement_role: Literal["organizer", "participant", "responder", "target", "other"]


class ExtractedEvent(BaseModel):
    """A discrete incident, escalation point, or action asserted as having happened."""

    title: str = Field(description="Short factual headline, e.g. 'Ambassador Bridge blockade begins'")
    description: str = Field(description="1-3 sentence factual summary from the text")
    event_type: EventType
    event_date: Optional[str] = Field(
        default=None, description="ISO date YYYY-MM-DD if a single day is asserted"
    )
    event_start_date: Optional[str] = Field(default=None, description="ISO date for multi-day events")
    event_end_date: Optional[str] = Field(default=None, description="ISO date for multi-day events")
    movement_phase: MovementPhase
    location_names: list[str] = Field(
        description="Names matching this page's locations list, where the event happened"
    )
    actor_involvements: list[ActorInvolvement]
    is_state_response: bool = False
    source_quote: str


class ExtractedStateResponse(BaseModel):
    """A government, police, judicial, or financial measure taken in response."""

    title: str = Field(description="e.g. 'Emergencies Act invocation'")
    response_type: ResponseType
    responding_actor_name: Optional[str] = None
    response_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD")
    legal_instrument: Optional[str] = Field(
        default=None, description="e.g. 'Emergencies Act', 'EMR', 'EEMO', 'OIC 2022-0392'"
    )
    description: str
    source_quote: str


class PageExtraction(BaseModel):
    """Everything evidentiary asserted on a single report page."""

    actors: list[ExtractedActor]
    locations: list[ExtractedLocation]
    events: list[ExtractedEvent]
    state_responses: list[ExtractedStateResponse]
