from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.db import get_db
from app.models.models import Bid, OfficerDecision, User
from app.schemas.schemas import DecisionRequest, DecisionOut
from app.services.audit import log_action
from app.routes.auth import get_current_user

router = APIRouter()

@router.post("/decision", response_model=DecisionOut)
def make_decision(req: DecisionRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    bid = db.query(Bid).filter(Bid.bid_id == req.bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    # Update bid status
    if req.decision == 'qualify':
        bid.status = 'qualified'
    elif req.decision == 'disqualify':
        bid.status = 'disqualified'
    elif req.decision == 'review':
        bid.status = 'pending_review'
        
    # Create decision record
    decision = OfficerDecision(
        bidder_id=bid.bidder_id,
        officer_id=current_user['id'],
        bid_id=bid.id,
        decision=req.decision,
        comments=req.comments
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    
    log_action(db, current_user['id'], 'Officer Decision', 'bid', req.bid_id, f"Decision: {req.decision}")
    
    out = DecisionOut.model_validate(decision)
    out.officer_name = current_user['name']
    return out

@router.get("/decisions/{bid_id}", response_model=List[DecisionOut])
def get_decisions(bid_id: str, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    decisions = db.query(OfficerDecision, User).join(User, OfficerDecision.officer_id == User.id).filter(OfficerDecision.bid_id == bid.id).all()
    
    results = []
    for d, u in decisions:
        out = DecisionOut.model_validate(d)
        out.officer_name = u.name
        results.append(out)
        
    return results
