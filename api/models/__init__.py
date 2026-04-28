"""Import all model modules so SQLAlchemy metadata is populated."""

from api.models.assignment import Assignment
from api.models.audit import PostEventAudit
from api.models.document import DocumentUpload
from api.models.event import Event
from api.models.ngo import NGO
from api.models.skill import SkillCertificate
from api.models.user import User
from api.models.volunteer import Volunteer

__all__ = [
	"Assignment",
	"PostEventAudit",
	"DocumentUpload",
	"Event",
	"NGO",
	"SkillCertificate",
	"User",
	"Volunteer",
]
