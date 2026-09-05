import random
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.db import get_db
from app.models.models import Bid, Bidder, Tender, Document, ExtractedData, Verification, ComplianceResult, RiskResult
from app.schemas.schemas import BidOut, BidCreate
from app.services.audit import log_action
from app.services.compliance import evaluate_compliance
from app.services.risk import assess_risk
from app.services.ocr import mock_ocr_extract
from app.services.verification import verify_document
from app.routes.auth import get_current_user

router = APIRouter()

DEMO_BIDDER_TEMPLATES = [
    {"name": "Vikram Mehta", "company_name": "ABC Pvt Ltd", "gstin": "23ABCDE1234F1Z5", "pan": "ABCDE1234F", "udyam_number": "UDYAM-XX-00-0000001"},
    {"name": "Sunita Reddy", "company_name": "TechServe Solutions", "gstin": "27FGHIJ5678K2Z3", "pan": "FGHIJ5678K", "udyam_number": "UDYAM-MH-01-0000042"},
    {"name": "Amit Patel", "company_name": "Global Infra Corp", "gstin": "07KLMNO9012P3Z8", "pan": "KLMNO9012P", "udyam_number": "UDYAM-DL-02-0000099"},
    {"name": "Rahul Verma", "company_name": "Apex Dynamics Ltd", "gstin": "29AABCT1332L1ZX", "pan": "AABCT1332L", "udyam_number": "UDYAM-KA-03-0000128"},
    {"name": "Neha Sharma", "company_name": "CyberNet Systems", "gstin": "06AAACC4455M1Z9", "pan": "AAACC4455M", "udyam_number": "UDYAM-HR-04-0000551"},
]

def auto_setup_bid_pipeline(db: Session, bid: Bid, bidder: Bidder, tender: Tender):
    """Automatically create documents, OCR extraction, verification, compliance, and risk for a newly created bid."""
    doc_types = ['gst_certificate', 'udyam_certificate', 'pan_card', 'authorization_letter', 'declaration']
    
    # 1. Create Documents if none exist
    existing_docs = db.query(Document).filter(Document.bidder_id == bidder.id, Document.tender_id == tender.id).all()
    if not existing_docs:
        for dtype in doc_types:
            doc = Document(
                bidder_id=bidder.id,
                tender_id=tender.id,
                document_type=dtype,
                file_path=f"/uploads/b_{bidder.id}_{dtype}.pdf",
                upload_date=datetime.now(timezone.utc)
            )
            db.add(doc)
        db.commit()
        existing_docs = db.query(Document).filter(Document.bidder_id == bidder.id, Document.tender_id == tender.id).all()

    # 2. Process OCR & Verification
    bidder_data = {
        'gstin': bidder.gstin,
        'company_name': bidder.company_name,
        'pan': bidder.pan,
        'name': bidder.name,
        'udyam_number': bidder.udyam_number,
        'bidder_id': bidder.id
    }
    
    source_map = {
        'gst_certificate': 'GST Portal',
        'udyam_certificate': 'Udyam Portal',
        'pan_card': 'PAN Authority',
        'authorization_letter': 'Document Analysis',
        'declaration': 'Document Analysis'
    }

    ver_results_for_comp = []
    for doc in existing_docs:
        # Check if extracted data exists
        exts = db.query(ExtractedData).filter(ExtractedData.document_id == doc.id).all()
        if not exts:
            extracted_items = mock_ocr_extract(doc.document_type, doc.file_path, bidder_data)
            for item in extracted_items:
                ed = ExtractedData(
                    document_id=doc.id,
                    field_name=item['field_name'],
                    field_value=item['field_value'],
                    confidence=item['confidence']
                )
                db.add(ed)
            db.commit()
            exts = db.query(ExtractedData).filter(ExtractedData.document_id == doc.id).all()
            
        ext_map = {e.field_name: e.field_value for e in exts}
        ext_map.update(bidder_data)
        
        # Run verification
        v_check = verify_document(doc.document_type, ext_map)
        status = v_check.get('verification', 'verified')
        if status == 'matched':
            status = 'verified'
        
        # Save verification record if not exists
        v_rec = db.query(Verification).filter(Verification.document_id == doc.id).first()
        if not v_rec:
            v_rec = Verification(
                document_id=doc.id,
                source=source_map.get(doc.document_type, 'System'),
                status=status,
                matched_data=json.dumps(v_check),
                verified_at=datetime.now(timezone.utc)
            )
            db.add(v_rec)
            db.commit()
            
        v_data = v_check.copy()
        v_data['verification'] = status
        v_data['document_id'] = doc.id
        ver_results_for_comp.append(v_data)

    # 3. Evaluate Compliance
    tender_reqs = json.loads(tender.requirements) if tender.requirements else {}
    comp_eval = evaluate_compliance(tender_reqs, ver_results_for_comp, {})
    
    # Save compliance results
    db.query(ComplianceResult).filter(ComplianceResult.tender_id == tender.id, ComplianceResult.bidder_id == bidder.id).delete()
    for r in comp_eval['results']:
        cr = ComplianceResult(
            tender_id=tender.id,
            bidder_id=bidder.id,
            requirement=r['requirement'],
            status=r['status'],
            evidence=r['evidence']
        )
        db.add(cr)
    
    bid.compliance_score = comp_eval['score']
    
    # 4. Assess Risk
    comp_list = [{'status': r['status'], 'requirement': r['requirement']} for r in comp_eval['results']]
    risk_eval = assess_risk(ver_results_for_comp, comp_list)
    
    db.query(RiskResult).filter(RiskResult.bidder_id == bidder.id).delete()
    rr = RiskResult(
        bidder_id=bidder.id,
        risk_level=risk_eval['risk_level'],
        finding=json.dumps(risk_eval['findings']),
        recommendation=risk_eval['recommendation']
    )
    db.add(rr)
    bid.risk_level = risk_eval['risk_level'].lower()
    
    if bid.compliance_score >= 90:
        bid.status = 'qualified'
    elif bid.compliance_score < 60:
        bid.status = 'disqualified'
    else:
        bid.status = 'pending_review'
        
    db.commit()

@router.post("/", response_model=BidOut)
def create_bid(bid_in: BidCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 1. Resolve Tender
    tender = None
    if isinstance(bid_in.tender_id, int):
        tender = db.query(Tender).filter(Tender.id == bid_in.tender_id).first()
    elif isinstance(bid_in.tender_id, str):
        tender = db.query(Tender).filter(Tender.tender_id == bid_in.tender_id).first()
        if not tender and bid_in.tender_id.isdigit():
            tender = db.query(Tender).filter(Tender.id == int(bid_in.tender_id)).first()
            
    if not tender:
        # Fallback to latest tender
        tender = db.query(Tender).order_by(Tender.id.desc()).first()
        if not tender:
            raise HTTPException(status_code=404, detail="No tender available")

    # 2. Resolve or Create Bidder
    bidder_id = bid_in.bidder_id or 1
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if not bidder:
        # Create a realistic demo bidder deterministically
        tmpl = DEMO_BIDDER_TEMPLATES[(tender.id) % len(DEMO_BIDDER_TEMPLATES)]
        bidder = Bidder(
            name=tmpl['name'],
            company_name=tmpl['company_name'],
            gstin=tmpl['gstin'],
            pan=tmpl['pan'],
            udyam_number=tmpl['udyam_number']
        )
        db.add(bidder)
        db.commit()
        db.refresh(bidder)

    # 3. Generate unique Bid ID
    bid_id = bid_in.bid_id
    if not bid_id:
        existing_count = db.query(Bid).count()
        bid_id = f"BID{existing_count + 101:03d}"
        
    # Check if this bid already exists
    db_bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not db_bid:
        db_bid = Bid(
            bid_id=bid_id,
            bidder_id=bidder.id,
            tender_id=tender.id,
            status='pending',
            risk_level='medium',
            compliance_score=0.0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(db_bid)
        db.commit()
        db.refresh(db_bid)

    # Auto setup pipeline data so compliance & verification work immediately
    auto_setup_bid_pipeline(db, db_bid, bidder, tender)
    
    user_id = current_user.get('id', 1) if isinstance(current_user, dict) else 1
    log_action(db, user_id, 'Created Bid', 'bid', bid_id, f"Created bid {bid_id} for {bidder.company_name} on {tender.tender_id}")

    bid_out = BidOut.model_validate(db_bid)
    bid_out.bidder_name = bidder.name
    bid_out.company_name = bidder.company_name
    bid_out.tender_code = tender.tender_id
    bid_out.tender_title = tender.title
    return bid_out

@router.get("/", response_model=List[BidOut])
def get_bids(tender_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Bid, Bidder, Tender).join(Bidder, Bid.bidder_id == Bidder.id).join(Tender, Bid.tender_id == Tender.id)
    if tender_id:
        if tender_id.isdigit():
            query = query.filter(Bid.tender_id == int(tender_id))
        else:
            query = query.filter(Tender.tender_id == tender_id)
            
    query = query.order_by(Bid.id.desc())
    results = []
    for bid, bidder, tender in query.all():
        bid_out = BidOut.model_validate(bid)
        bid_out.bidder_name = bidder.name
        bid_out.company_name = bidder.company_name
        bid_out.tender_code = tender.tender_id
        bid_out.tender_title = tender.title
        results.append(bid_out)
    return results

@router.get("/{bid_id}", response_model=BidOut)
def get_bid(bid_id: str, db: Session = Depends(get_db)):
    result = db.query(Bid, Bidder, Tender).join(Bidder, Bid.bidder_id == Bidder.id).join(Tender, Bid.tender_id == Tender.id).filter(Bid.bid_id == bid_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Bid {bid_id} not found")
    
    bid, bidder, tender = result
    bid_out = BidOut.model_validate(bid)
    bid_out.bidder_name = bidder.name
    bid_out.company_name = bidder.company_name
    bid_out.tender_code = tender.tender_id
    bid_out.tender_title = tender.title
    return bid_out
