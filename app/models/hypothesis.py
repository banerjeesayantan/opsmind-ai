"""This file contains the Hypothesis model - AI-generated candidate root causes."""

from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

from sqlmodel import (
    Column,
    Field,
    JSON,
    Relationship,
)

from app.models.base import BaseModel
from app.models.incident_enums import HypothesisStatus

if TYPE_CHECKING:
    from app.models.diagnosis import Diagnosis
    from app.models.incident import Incident


class Hypothesis(BaseModel, table=True):
    """A single AI-generated candidate explanation for an incident.

    A hypothesis is explicitly the model's interpretation, not an observed
    fact - it points at the Evidence rows that support it rather than
    embedding evidence content directly, so the claim can be checked against
    what was actually observed. A hypothesis that survives validation is
    promoted to a Diagnosis; one that doesn't is left with status REJECTED
    and kept for the record rather than deleted.

    Attributes:
        id: The primary key.
        incident_id: Foreign key to the parent incident.
        statement: The candidate root-cause explanation, in plain language.
        reasoning: Optional longer explanation of how the model arrived at
            this statement from the supporting evidence.
        confidence: The model's confidence in this hypothesis, from 0.0 to
            1.0. A numeric score rather than a qualitative label so it can
            be tracked and regression-tested over time.
        status: Whether this hypothesis is still proposed, has been
            validated against evidence, or was rejected.
        supporting_evidence_ids: IDs of the Evidence rows this hypothesis
            cites. Stored as a JSON list rather than a many-to-many join
            table to keep the schema simple at this project's scale - still
            fully queryable, still enforces that a hypothesis names its
            evidence rather than asserting a cause with nothing behind it.
        incident: Relationship back to the parent incident.
        diagnosis: The diagnosis this hypothesis was promoted to, if any.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: str = Field(foreign_key="incident.id", index=True)
    statement: str
    reasoning: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: HypothesisStatus = Field(default=HypothesisStatus.PROPOSED, index=True)
    supporting_evidence_ids: List[int] = Field(default_factory=list, sa_column=Column(JSON))

    incident: "Incident" = Relationship(back_populates="hypotheses")
    diagnosis: Optional["Diagnosis"] = Relationship(back_populates="hypothesis")