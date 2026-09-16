"""Domain models package.

Importing any single model module (e.g. app.models.remediation) is not
enough for SQLAlchemy to resolve its string-based Relationship()
references to other models (e.g. Remediation.incident: "Incident") -
those names only resolve once every referenced class has actually been
imported and registered on the shared SQLModel metaclass registry.

Importing this package eagerly imports every model module exactly once,
so any code that does `import app.models.<anything>` gets a fully
resolvable set of relationships, regardless of which specific model
module it imported.
"""

from app.models import (  # noqa: F401
    action_execution,
    approval,
    diagnosis,
    evidence,
    hypothesis,
    incident,
    incident_event,
    postmortem,
    remediation,
    session,
    user,
    verification,
)

__all__ = [
    "action_execution",
    "approval",
    "diagnosis",
    "evidence",
    "hypothesis",
    "incident",
    "incident_event",
    "postmortem",
    "remediation",
    "session",
    "user",
    "verification",
]
