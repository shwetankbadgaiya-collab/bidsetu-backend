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
    tender_id = f"TDR-2026-{random.randint(100, 999)}"
    
    db_tender = Tender(
        tender_id=tender_id,
        title=tender.title,
        department=tender.department,
        requirements=json.dumps(tender.requirements)
    )
    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    
    log_action(db, current_user['id'], 'Created Tender', 'tender', tender_id, f"Created tender {tender.title}")
    
    # Process requirements to dict for response
    tender_out = TenderOut.model_validate(db_tender)
    tender_out.requirements = json.loads(db_tender.requirements)
    return tender_out

@router.get("/", response_model=List[TenderOut])
def get_tenders(db: Session = Depends(get_db)):
    tenders = db.query(Tender).all()
    results = []
    for t in tenders:
        t_out = TenderOut.model_validate(t)
        t_out.requirements = json.loads(t.requirements)
        results.append(t_out)
    return results

@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.tender_id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    t_out = TenderOut.model_validate(tender)
    t_out.requirements = json.loads(tender.requirements)
    return t_out
