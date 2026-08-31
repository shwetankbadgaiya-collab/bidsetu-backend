from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from app.database.db import get_db
from app.models.models import AuditLog, User
from app.schemas.schemas import AuditLogOut

router = APIRouter()

@router.get("/{bid_id}", response_model=List[AuditLogOut])
def get_bid_audit_logs(bid_id: str, db: Session = Depends(get_db)):
    logs_users = db.query(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id).filter(AuditLog.entity_id == bid_id).order_by(AuditLog.timestamp).all()
    
    results = []
    for log, user in logs_users:
        out = AuditLogOut.model_validate(log)
        out.user_name = user.name if user else 'System'
        results.append(out)
        
    return results

@router.get("/", response_model=List[AuditLogOut])
def get_all_audit_logs(db: Session = Depends(get_db)):
    logs_users = db.query(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id).order_by(desc(AuditLog.timestamp)).all()
    
    results = []
    for log, user in logs_users:
        out = AuditLogOut.model_validate(log)
        out.user_name = user.name if user else 'System'
        results.append(out)
        
    return results
