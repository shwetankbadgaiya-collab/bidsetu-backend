import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.db import get_db
from app.models.models import Bid, Tender, ComplianceResult, Document, Verification
from app.schemas.schemas import ComplianceAnalysis, ComplianceResultOut
from app.services.audit import log_action
from app.services.compliance import evaluate_compliance
from app.routes.auth import get_current_user

router = APIRouter()

class RunComplianceRequest(BaseModel):
    bid_id: str

@router.post("/analyze", response_model=ComplianceAnalysis)
def analyze_compliance(req: RunComplianceRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    bid = db.query(Bid).filter(Bid.bid_id == req.bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    tender = db.query(Tender).filter(Tender.id == bid.tender_id).first()
    tender_reqs = json.loads(tender.requirements) if tender and tender.requirements else {"gst_valid": True, "udyam_valid": True, "pan_required": True, "authorization_required": True}
    
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    doc_ids = [d.id for d in documents]
    verifications = db.query(Verification).filter(Verification.document_id.in_(doc_ids)).all()
    
    verification_results = []
    for v in verifications:
        v_data = json.loads(v.matched_data) if v.matched_data else {}
        v_data['verification'] = v.status
        v_data['document_id'] = v.document_id
        verification_results.append(v_data)
        
    analysis = evaluate_compliance(tender_reqs, verification_results, {})
    
    # Save results
    tender_db_id = tender.id if tender else bid.tender_id
    db.query(ComplianceResult).filter(ComplianceResult.tender_id == tender_db_id, ComplianceResult.bidder_id == bid.bidder_id).delete()
    
    saved_results = []
    for r in analysis['results']:
        cr = ComplianceResult(
            tender_id=tender_db_id,
            bidder_id=bid.bidder_id,
            requirement=r['requirement'],
            status=r['status'],
            evidence=r.get('evidence', '')
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        saved_results.append(ComplianceResultOut.model_validate(cr))
        
    bid.compliance_score = analysis['score']
    db.commit()
    
    user_id = current_user.get('id', 1) if isinstance(current_user, dict) else 1
    log_action(db, user_id, 'Ran Compliance Analysis', 'bid', req.bid_id, f"Compliance score: {analysis['score']}")
    
    return ComplianceAnalysis(
        score=analysis['score'],
        risk_level=analysis.get('risk_level', 'LOW'),
        results=saved_results,
        recommendation=analysis['recommendation']
    )

@router.get("/{bid_id}", response_model=ComplianceAnalysis)
def get_compliance(bid_id: str, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    results = db.query(ComplianceResult).filter(
        ComplianceResult.tender_id == bid.tender_id, 
        ComplianceResult.bidder_id == bid.bidder_id
    ).all()
    
    if not results:
        # Run compliance analysis on the fly
        req = RunComplianceRequest(bid_id=bid_id)
        return analyze_compliance(req, db, current_user={'id': 1})
        
    saved_results = [ComplianceResultOut.model_validate(r) for r in results]
    
    fails = sum(1 for r in results if r.status == 'fail')
    reviews = sum(1 for r in results if r.status == 'review')
    
    risk_level = 'HIGH' if fails > 0 else ('MEDIUM' if reviews > 0 else 'LOW')
    if bid.compliance_score >= 90:
        recommendation = "All documents verified. Bid meets all tender requirements."
    elif bid.compliance_score < 60:
        recommendation = "Critical compliance failures detected. Mismatched or expired documents found."
    else:
        recommendation = "Bid requires officer review due to one unverified requirement or document variation."
        
    return ComplianceAnalysis(
        score=bid.compliance_score,
        risk_level=risk_level,
        results=saved_results,
        recommendation=recommendation
    )
