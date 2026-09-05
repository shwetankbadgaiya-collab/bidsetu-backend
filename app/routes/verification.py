import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database.db import get_db
from app.models.models import Document, ExtractedData, Verification, Bid, Bidder, Tender
from app.schemas.schemas import VerificationOut
from app.services.audit import log_action
from app.services.verification import verify_document
from app.services.ocr import mock_ocr_extract
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
    
    # If no documents exist yet, create default set for this bid
    if not documents:
        doc_types = ['gst_certificate', 'udyam_certificate', 'pan_card', 'authorization_letter', 'declaration']
        for dtype in doc_types:
            doc = Document(
                bidder_id=bid.bidder_id,
                tender_id=bid.tender_id,
                document_type=dtype,
                file_path=f"/uploads/b_{bid.bidder_id}_{dtype}.pdf",
                upload_date=datetime.now(timezone.utc)
            )
            db.add(doc)
        db.commit()
        documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    
    results = []
    source_map = {
        'gst_certificate': 'GST Portal',
        'udyam_certificate': 'Udyam Portal',
        'pan_card': 'PAN Authority',
        'authorization_letter': 'Document Analysis',
        'declaration': 'Document Analysis'
    }
    
    for doc in documents:
        exts = db.query(ExtractedData).filter(ExtractedData.document_id == doc.id).all()
        if not exts:
            bidder_data = {
                'gstin': bidder.gstin if bidder else '',
                'company_name': bidder.company_name if bidder else '',
                'pan': bidder.pan if bidder else '',
                'name': bidder.name if bidder else '',
                'udyam_number': bidder.udyam_number if bidder else '',
                'bidder_id': bidder.id if bidder else 1
            }
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
            
        extracted_data_map = {e.field_name: e.field_value for e in exts}
        if bidder:
            extracted_data_map['company_name'] = bidder.company_name
            extracted_data_map['gstin'] = bidder.gstin
            extracted_data_map['udyam_number'] = bidder.udyam_number
            extracted_data_map['pan_number'] = bidder.pan
            
        verify_result = verify_document(doc.document_type, extracted_data_map)
        status = verify_result.get('verification', 'verified')
        if status == 'matched':
            status = 'verified'
            
        # Delete old verification if exists
        db.query(Verification).filter(Verification.document_id == doc.id).delete()
        ver_record = Verification(
            document_id=doc.id,
            source=source_map.get(doc.document_type, 'System'),
            status=status,
            matched_data=json.dumps(verify_result),
            verified_at=datetime.now(timezone.utc)
        )
        db.add(ver_record)
        db.commit()
        db.refresh(ver_record)
        
        out = VerificationOut.model_validate(ver_record)
        out.document = DOC_NAME_MAP.get(doc.document_type, doc.document_type)
        out.extracted = format_extracted_summary(doc.document_type, extracted_data_map, bidder)
        out.matched_data = verify_result
        results.append(out)
        
    user_id = current_user.get('id', 1) if isinstance(current_user, dict) else 1
    log_action(db, user_id, 'Ran Verification', 'bid', req.bid_id, f"Ran verification for bid {req.bid_id}")
    return results

@router.get("/{bid_id}", response_model=List[VerificationOut])
def get_verification_results(bid_id: str, db: Session = Depends(get_db)):
    bid = db.query(Bid).filter(Bid.bid_id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail=f"Bid {bid_id} not found")
        
    bidder = db.query(Bidder).filter(Bidder.id == bid.bidder_id).first()
    documents = db.query(Document).filter(Document.bidder_id == bid.bidder_id, Document.tender_id == bid.tender_id).all()
    
    # If no documents/verifications exist yet for this bid, auto-run verification
    if not documents:
        req = RunVerificationRequest(bid_id=bid_id)
        return run_verification(req, db, current_user={'id': 1})
        
    doc_map = {d.id: d for d in documents}
    verifications = db.query(Verification).filter(Verification.document_id.in_(doc_map.keys())).all()
    
    if not verifications:
        req = RunVerificationRequest(bid_id=bid_id)
        return run_verification(req, db, current_user={'id': 1})
        
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
