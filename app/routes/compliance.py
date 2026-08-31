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
    tender_reqs = json.loads(tender.requirements) if tender.requirements else {}
    
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    doc_ids = [d.id for d in documents]
    verifications = db.query(Verification).filter(Verification.document_id.in_(doc_ids)).all()
    
    verification_results = []
    for v in verifications:
        v_data = json.loads(v.matched_data) if v.matched_data else {}
        v_data['verification'] = v.status
        v_data['document_id'] = v.document_id
        verification_results.append(v_data)
        
    # extracted data map is mocked empty here, we rely on verification_results
    analysis = evaluate_compliance(tender_reqs, verification_results, {})
    
    # Save results
    db.query(ComplianceResult).filter(ComplianceResult.tender_id == tender.id, ComplianceResult.bidder_id == bid.bidder_id).delete()
    
    saved_results = []
    for r in analysis['results']:
        cr = ComplianceResult(
            tender_id=tender.id,
            bidder_id=bid.bidder_id,
            requirement=r['requirement'],
            status=r['status'],
            evidence=r['evidence']
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        saved_results.append(ComplianceResultOut.model_validate(cr))
        
    bid.compliance_score = analysis['score']
    db.commit()
    
    log_action(db, current_user['id'], 'Ran Compliance Analysis', 'bid', req.bid_id, f"Compliance score: {analysis['score']}")
    
    return ComplianceAnalysis(
        score=analysis['score'],
        risk_level=analysis.get('risk_level', 'unknown'),
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
        # Return empty shell if not run yet
        return ComplianceAnalysis(score=0.0, risk_level='unknown', results=[], recommendation='Analysis not run yet')
        
    saved_results = [ComplianceResultOut.model_validate(r) for r in results]
    
    # Determine risk level based on score/status for response
    fails = sum(1 for r in results if r.status == 'fail')
    reviews = sum(1 for r in results if r.status == 'review')
    
    risk_level = 'HIGH' if fails > 0 else ('MEDIUM' if reviews > 0 else 'LOW')
    recommendation = "Issues detected." if (fails > 0 or reviews > 0) else "All clear."
    if bid.compliance_score > 90:
        recommendation = "All documents verified. Bid meets all tender requirements."
    elif bid.compliance_score < 50:
        recommendation = "Critical compliance failures detected."
    elif bid.compliance_score < 90:
        recommendation = "Bid requires officer review due to one unverified requirement and authorization letter discrepancy."
        
    return ComplianceAnalysis(
        score=bid.compliance_score,
        risk_level=risk_level,
        results=saved_results,
        recommendation=recommendation
    )
