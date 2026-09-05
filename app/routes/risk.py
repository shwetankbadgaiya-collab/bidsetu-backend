from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from app.database.db import get_db
from app.models.models import Bid, Document, Verification, ComplianceResult, RiskResult
from app.schemas.schemas import RiskResultOut
from app.services.audit import log_action
from app.services.risk import assess_risk
from app.routes.auth import get_current_user

router = APIRouter()

class RunRiskRequest(BaseModel):
    bid_id: str

@router.post("/analyze", response_model=RiskResultOut)
def analyze_risk(req: RunRiskRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    bid = db.query(Bid).filter(Bid.bid_id == req.bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    doc_ids = [d.id for d in documents]
    
    verifications = db.query(Verification).filter(Verification.document_id.in_(doc_ids)).all()
    compliance_results = db.query(ComplianceResult).filter(ComplianceResult.tender_id == bid.tender_id, ComplianceResult.bidder_id == bid.bidder_id).all()
    
    ver_list = []
    for v in verifications:
        v_data = json.loads(v.matched_data) if v.matched_data else {}
        v_data['verification'] = v.status
        ver_list.append(v_data)
        
    comp_list = [{'status': c.status, 'requirement': c.requirement} for c in compliance_results]
    
    risk_analysis = assess_risk(ver_list, comp_list)
    
    db.query(RiskResult).filter(RiskResult.bidder_id == bid.bidder_id).delete()
    
    rr = RiskResult(
        bidder_id=bid.bidder_id,
        risk_level=risk_analysis['risk_level'],
        finding=json.dumps(risk_analysis['findings']),
        recommendation=risk_analysis['recommendation']
    )
    db.add(rr)
    bid.risk_level = risk_analysis['risk_level'].lower()
    db.commit()
    db.refresh(rr)
    
    user_id = current_user.get('id', 1) if isinstance(current_user, dict) else 1
    log_action(db, user_id, 'Ran Risk Analysis', 'bid', req.bid_id, f"Risk level: {rr.risk_level}")
    
    return RiskResultOut(
        id=rr.id,
        risk_level=rr.risk_level,
        finding=rr.finding,
        recommendation=rr.recommendation
    )

@router.get("/{bid_id}", response_model=RiskResultOut)
def get_risk(bid_id: str, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    rr = db.query(RiskResult).filter(RiskResult.bidder_id == bid.bidder_id).first()
    if not rr:
        req = RunRiskRequest(bid_id=bid_id)
        return analyze_risk(req, db, current_user={'id': 1})
        
    return RiskResultOut.model_validate(rr)
