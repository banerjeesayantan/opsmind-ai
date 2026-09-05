"""Database models for the application.

This module's job is to force-import every SQLModel table class so it gets
registered with SQLModel.metadata, regardless of what else has or hasn't
been imported yet by the caller. User and Session are included explicitly
for this reason, even though app/services/database.py and app/api/v1/*.py
also import them directly elsewhere - relying on that incidental import
happening first is exactly the kind of import-order fragility this module
exists to prevent (relationships that forward-reference "User" as a string,
e.g. Approval.decider, fail to resolve at mapper-configuration time if
User was never imported by anything in the running process).

Note: Thread was previously registered here but has zero usages anywhere in
the codebase (confirmed during the Step 1 foundation cleanup) and has been
removed from this registry. The app/models/thread.py file itself has not
been deleted.
"""

from app.models.action_execution import ActionExecution
from app.models.approval import Approval
from app.models.diagnosis import Diagnosis
from app.models.evidence import Evidence
from app.models.hypothesis import Hypothesis
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.postmortem import Postmortem
from app.models.remediation import Remediation
from app.models.session import Session
from app.models.user import User
from app.models.verification import Verification

__all__ = [
    "ActionExecution",
    "Approval",
    "Diagnosis",
    "Evidence",
    "Hypothesis",
    "Incident",
    "IncidentEvent",
    "Postmortem",
    "Remediation",
    "Session",
    "User",
    "Verification",
]