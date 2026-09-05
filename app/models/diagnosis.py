"""This file contains the Diagnosis model - the validated root cause for an incident."""

from datetime import datetime, UTC
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.hypothesis import Hypothesis
    from app.models.incident import Incident
    from app.models.remediation import Remediation


class Diagnosis(BaseModel, table=True):
    """The validated root cause for an incident, promoted from a Hypothesis.

    A diagnosis is what a hypothesis becomes once it has been checked
    against the actual evidence and accepted as the working explanation.
    It carries its own confidence and impact assessment rather than simply
    referencing the hypothesis's, because validation can adjust either
    (e.g. confidence typically rises once a hypothesis is confirmed against
    fresh evidence, or the assessed impact may be refined once the full
    picture is available).

    An incident may accumulate more than one diagnosis over time if an
    earlier one is superseded (e.g. new evidence changes the picture);
    is_active marks which one is the current working diagnosis.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        hypothesis_id: Foreign key to the hypothesis this diagnosis was
            promoted from.
        probable_cause: The finalized root-cause statement.
        confidence: Confidence in this diagnosis, from 0.0 to 1.0.
        impact: Description of the incident's actual or assessed impact
            (e.g. "increased API response time for 12 minutes").
        is_active: Whether this is the current working diagnosis for the
            incident. False once superseded by a later diagnosis.
        diagnosed_at: When this diagnosis was reached.
        incident: Relationship back to the parent incident.
        hypothesis: Relationship to the source hypothesis.
        remediations: Recommended remediation actions for this diagnosis.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    hypothesis_id: int = Field(foreign_key="hypothesis.id")
    probable_cause: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    impact: str = Field(default="")
    is_active: bool = Field(default=True, index=True)
    diagnosed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    incident: "Incident" = Relationship(back_populates="diagnoses")
    hypothesis: "Hypothesis" = Relationship(back_populates="diagnosis")
    remediations: List["Remediation"] = Relationship(back_populates="diagnosis")
