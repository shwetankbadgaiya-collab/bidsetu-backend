import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database.db import get_db
from app.models.models import Document, ExtractedData, Verification, Bid, Bidder
from app.schemas.schemas import VerificationOut
from app.services.audit import log_action
from app.services.verification import verify_document
from app.routes.auth import get_current_user

router = APIRouter()

class RunVerificationRequest(BaseModel):
    bid_id: str

DOC_NAME_MAP = {
    'gst_certificate': 'GST Certificate',
    'udyam_certificate': 'Udyam Certificate',
    'pan_card': 'PAN Card',
    'authorization_letter': 'Authorization Letter',
    'declaration': 'Declaration'
}

def format_extracted_summary(doc_type: str, extracted_map: dict, bidder: Bidder) -> str:
    if doc_type == 'gst_certificate':
        return f"GSTIN: {extracted_map.get('gstin', bidder.gstin if bidder else '')}"
    elif doc_type == 'udyam_certificate':
        return f"Udyam: {extracted_map.get('udyam_number', bidder.udyam_number if bidder else '')}"
    elif doc_type == 'pan_card':
        return f"PAN: {extracted_map.get('pan_number', bidder.pan if bidder else '')}"
    elif doc_type == 'authorization_letter':
        return f"Company: {extracted_map.get('authorized_company', bidder.company_name if bidder else '')}"
    elif doc_type == 'declaration':
        return f"Declared by: {extracted_map.get('declarant', bidder.name if bidder else '')}"
    return "Document provided"

@router.post("/run", response_model=List[VerificationOut])
def run_verification(req: RunVerificationRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    bid = db.query(Bid).filter(Bid.bid_id == req.bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    bidder = db.query(Bidder).filter(Bidder.id == bid.bidder_id).first()
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    
    results = []
    
    for doc in documents:
        extracted_data_records = db.query(ExtractedData).filter(ExtractedData.document_id == doc.id).all()
        extracted_data_map = {e.field_name: e.field_value for e in extracted_data_records}
        
        # Add basic bidder info to help with matching
        if bidder:
            extracted_data_map['company_name'] = bidder.company_name
            if 'gstin' not in extracted_data_map and bidder.gstin:
                extracted_data_map['gstin'] = bidder.gstin
            if 'udyam_number' not in extracted_data_map and bidder.udyam_number:
                extracted_data_map['udyam_number'] = bidder.udyam_number
            if 'pan_number' not in extracted_data_map and bidder.pan:
                extracted_data_map['pan_number'] = bidder.pan
        
        verify_result = verify_document(doc.document_type, extracted_data_map)
        
        source_map = {
            'gst_certificate': 'GST Portal',
            'udyam_certificate': 'Udyam Portal',
            'pan_card': 'PAN Authority',
            'authorization_letter': 'Document Analysis',
            'declaration': 'Document Analysis'
        }
        
        status = verify_result.get('verification', 'pending')
        matched_data = verify_result
        
        # Remove old verification for this document if any
        db.query(Verification).filter(Verification.document_id == doc.id).delete()
        
        ver_record = Verification(
            document_id=doc.id,
            source=source_map.get(doc.document_type, 'System'),
            status=status,
            matched_data=json.dumps(matched_data)
        )
        db.add(ver_record)
        db.commit()
        db.refresh(ver_record)
        
        out = VerificationOut.model_validate(ver_record)
        out.document = DOC_NAME_MAP.get(doc.document_type, doc.document_type)
        out.extracted = format_extracted_summary(doc.document_type, extracted_data_map, bidder)
        out.matched_data = matched_data
        results.append(out)
        
    log_action(db, current_user['id'], 'Ran Verification', 'bid', req.bid_id, f"Ran verification for bid {req.bid_id}")
    return results

@router.get("/{bid_id}", response_model=List[VerificationOut])
def get_verification_results(bid_id: str, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
        
    bidder = db.query(Bidder).filter(Bidder.id == bid.bidder_id).first()
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    doc_map = {d.id: d for d in documents}
    
    verifications = db.query(Verification).filter(Verification.document_id.in_(doc_map.keys())).all()
    
    results = []
    for v in verifications:
        doc = doc_map.get(v.document_id)
        doc_type = doc.document_type if doc else ''
        extracted_data_records = db.query(ExtractedData).filter(ExtractedData.document_id == v.document_id).all()
        extracted_data_map = {e.field_name: e.field_value for e in extracted_data_records}
        
        out = VerificationOut.model_validate(v)
        out.document = DOC_NAME_MAP.get(doc_type, doc_type or 'Document')
        out.extracted = format_extracted_summary(doc_type, extracted_data_map, bidder)
        out.matched_data = json.loads(v.matched_data) if v.matched_data else {}
        results.append(out)
        
    return results
