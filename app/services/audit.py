from sqlalchemy.orm import Session
from app.models.models import AuditLog
from datetime import datetime, timezone

def log_action(db: Session, user_id: int | None, action: str, entity: str, entity_id: str = None, details: str = None):
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
