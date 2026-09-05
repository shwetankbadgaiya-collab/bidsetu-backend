import json
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.db import get_db
from app.models.models import Tender
from app.schemas.schemas import TenderCreate, TenderOut
from app.services.audit import log_action
from app.routes.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=TenderOut)
def create_tender(tender: TenderCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    tender_id = (tender.tender_id or "").strip()
    if not tender_id:
        tender_id = f"TDR-2026-{random.randint(100, 999)}"
    
    # Check if tender_id already exists, if so generate suffix
    existing = db.query(Tender).filter(Tender.tender_id == tender_id).first()
    if existing:
        tender_id = f"TDR-2026-{random.randint(100, 999)}"
        
    db_tender = Tender(
        tender_id=tender_id,
        title=tender.title,
        department=tender.department,
        requirements=json.dumps(tender.requirements or {})
    )
    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    
    user_id = current_user.get('id', 1) if isinstance(current_user, dict) else 1
    log_action(db, user_id, 'Created Tender', 'tender', tender_id, f"Created tender {tender.title} ({tender_id})")
    
    tender_out = TenderOut.model_validate(db_tender)
    tender_out.requirements = json.loads(db_tender.requirements) if db_tender.requirements else {}
    return tender_out

@router.get("/", response_model=List[TenderOut])
def get_tenders(db: Session = Depends(get_db)):
    tenders = db.query(Tender).order_by(Tender.id.desc()).all()
    results = []
    for t in tenders:
        t_out = TenderOut.model_validate(t)
        t_out.requirements = json.loads(t.requirements) if t.requirements else {}
        results.append(t_out)
    return results

@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    # Try query by string tender_id first, then by integer ID
    tender = db.query(Tender).filter(Tender.tender_id == tender_id).first()
    if not tender and tender_id.isdigit():
        tender = db.query(Tender).filter(Tender.id == int(tender_id)).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    t_out = TenderOut.model_validate(tender)
    t_out.requirements = json.loads(tender.requirements) if tender.requirements else {}
    return t_out
