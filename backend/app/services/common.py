from sqlalchemy.orm import Session

from ..models.core import AuditLog, Notification


def audit(db: Session, actor_id, action: str, entity_type: str, entity_id=None, before=None, after=None):
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id is not None else None,
                    before=before, after=after))


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", link: str | None = None):
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, link=link))
