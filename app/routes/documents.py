import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List

from app.database.db import get_db
from app.models.models import Document, ExtractedData, Bidder
from app.schemas.schemas import DocumentOut, ExtractedDataOut
from app.services.audit import log_action
from app.services.ocr import mock_ocr_extract
from app.routes.auth import get_current_user

router = APIRouter()

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    bidder_id: int = Form(1),
    tender_id: int = Form(1),
    document_type: str = Form("gst_certificate"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_path = os.path.join(UPLOAD_DIR, f"{bidder_id}_{document_type}_{file.filename}")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    doc = Document(
        bidder_id=bidder_id,
        tender_id=tender_id,
        document_type=document_type,
        file_path=file_path
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    log_action(db, 1, 'Uploaded Document', 'document', str(doc.id), f"Uploaded {document_type} for bidder {bidder_id}")
    
    return doc

from pydantic import BaseModel
class ProcessRequest(BaseModel):
    document_id: int | None = None
    bidder_id: int | None = None
    tender_id: int | None = None

@router.post("/process", response_model=List[ExtractedDataOut])
def process_documents(req: ProcessRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    docs_to_process = []
    if req.document_id:
        doc = db.query(Document).filter(Document.id == req.document_id).first()
        if doc: docs_to_process.append(doc)
    elif req.bidder_id and req.tender_id:
        docs_to_process = db.query(Document).filter(Document.bidder_id == req.bidder_id, Document.tender_id == req.tender_id).all()
        
    results = []
    for doc in docs_to_process:
        bidder = db.query(Bidder).filter(Bidder.id == doc.bidder_id).first()
        bidder_data = {
            'gstin': bidder.gstin,
            'company_name': bidder.company_name,
            'pan': bidder.pan,
            'name': bidder.name,
            'udyam_number': bidder.udyam_number,
            'bidder_id': bidder.id
        } if bidder else {}
        
        extracted = mock_ocr_extract(doc.document_type, doc.file_path, bidder_data)
        
        for item in extracted:
            ed = ExtractedData(
                document_id=doc.id,
                field_name=item['field_name'],
                field_value=item['field_value'],
                confidence=item['confidence']
            )
            db.add(ed)
            db.commit()
            db.refresh(ed)
            results.append(ed)
            
        log_action(db, current_user['id'], 'Processed Document OCR', 'document', str(doc.id), f"Extracted data for {doc.document_type}")
        
    return results

@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    extracted = db.query(ExtractedData).filter(ExtractedData.document_id == document_id).all()
    
    return {
        "document": DocumentOut.model_validate(doc),
        "extracted_data": [ExtractedDataOut.model_validate(e) for e in extracted]
    }
