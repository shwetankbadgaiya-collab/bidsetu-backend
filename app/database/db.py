import json
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, User, Tender, Bidder, Bid, Document, ExtractedData, Verification, ComplianceResult, RiskResult, OfficerDecision, AuditLog
import hashlib

DATABASE_URL = "sqlite:///./bidsetu.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_password_hash(password: str) -> str:
    salt = "bidsetu_secure_salt_2026"
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return get_password_hash(plain_password) == hashed_password

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

def seed_data():
    db = SessionLocal()
    
    # Only seed if users table is empty
    if db.query(User).first():
        db.close()
        return

    # Seed Users
    officer = User(name='Priya Sharma', email='officer@bidsetu.gov.in', password_hash=get_password_hash('demo1234'), role='officer')
    admin = User(name='Rajesh Kumar', email='admin@bidsetu.gov.in', password_hash=get_password_hash('admin1234'), role='admin')
    db.add_all([officer, admin])
    db.commit()

    # Seed Tenders
    tender = Tender(
        tender_id='TDR-2026-014', 
        title='Supply of IT Equipment for District Office', 
        department='Ministry of Electronics & IT', 
        requirements=json.dumps({"gst_valid": True, "udyam_valid": True, "pan_required": True, "authorization_required": True, "min_experience_years": 3}),
        created_at=datetime.now(timezone.utc)
    )
    db.add(tender)
    db.commit()

    # Seed Bidders
    bidder1 = Bidder(name='Vikram Mehta', company_name='ABC Pvt Ltd', gstin='23ABCDE1234F1Z5', pan='ABCDE1234F', udyam_number='UDYAM-XX-00-0000001')
    bidder2 = Bidder(name='Sunita Reddy', company_name='TechServe Solutions', gstin='27FGHIJ5678K2Z3', pan='FGHIJ5678K', udyam_number='UDYAM-MH-01-0000042')
    bidder3 = Bidder(name='Amit Patel', company_name='Global Infra Corp', gstin='07KLMNO9012P3Z8', pan='KLMNO9012P', udyam_number='UDYAM-DL-02-0000099')
    db.add_all([bidder1, bidder2, bidder3])
    db.commit()

    # Seed Bids
    bid1 = Bid(bid_id='BID001', bidder_id=bidder2.id, tender_id=tender.id, status='qualified', risk_level='low', compliance_score=96.0, created_at=datetime.now(timezone.utc))
    bid2 = Bid(bid_id='BID002', bidder_id=bidder3.id, tender_id=tender.id, status='disqualified', risk_level='high', compliance_score=45.0, created_at=datetime.now(timezone.utc))
    bid3 = Bid(bid_id='BID003', bidder_id=bidder1.id, tender_id=tender.id, status='pending_review', risk_level='medium', compliance_score=82.0, created_at=datetime.now(timezone.utc))
    bid4 = Bid(bid_id='BID004', bidder_id=bidder1.id, tender_id=tender.id, status='pending', risk_level='low', compliance_score=0.0, created_at=datetime.now(timezone.utc))
    db.add_all([bid1, bid2, bid3, bid4])
    db.commit()

    # Seed Documents and Data for Bidder 1 (REVIEW)
    doc_types = ['gst_certificate', 'udyam_certificate', 'pan_card', 'authorization_letter', 'declaration']
    for doc_type in doc_types:
        doc = Document(bidder_id=bidder1.id, tender_id=tender.id, document_type=doc_type, file_path=f"/uploads/b1_{doc_type}.pdf", upload_date=datetime.now(timezone.utc))
        db.add(doc)
    db.commit()
    
    # Mock extracted data for bidder 1
    # GST
    db.add(ExtractedData(document_id=1, field_name='gstin', field_value='23ABCDE1234F1Z5', confidence=0.96))
    db.add(Verification(document_id=1, source='GST Portal', status='verified', matched_data=json.dumps({"gstin": "23ABCDE1234F1Z5", "status": "ACTIVE"}), verified_at=datetime.now(timezone.utc)))
    # Udyam
    db.add(Verification(document_id=2, source='Udyam Portal', status='verified', matched_data=json.dumps({}), verified_at=datetime.now(timezone.utc)))
    # PAN
    db.add(Verification(document_id=3, source='PAN Authority', status='matched', matched_data=json.dumps({}), verified_at=datetime.now(timezone.utc)))
    # Auth
    db.add(Verification(document_id=4, source='Document Analysis', status='review', matched_data=json.dumps({"issue": "company name variation ABC Private Limited vs ABC Pvt Ltd"}), verified_at=datetime.now(timezone.utc)))
    
    # Compliance for Bidder 1
    db.add(ComplianceResult(tender_id=tender.id, bidder_id=bidder1.id, requirement='gst_valid', status='pass', evidence='GST Portal Verified'))
    db.add(ComplianceResult(tender_id=tender.id, bidder_id=bidder1.id, requirement='min_experience_years', status='fail', evidence='missing'))
    db.add(RiskResult(bidder_id=bidder1.id, risk_level='MEDIUM', finding='One unverified requirement and authorization letter discrepancy.', recommendation='Bid requires officer review due to one unverified requirement and authorization letter discrepancy.'))

    # Seed Documents and Data for Bidder 2 (QUALIFY)
    for doc_type in doc_types:
        doc = Document(bidder_id=bidder2.id, tender_id=tender.id, document_type=doc_type, file_path=f"/uploads/b2_{doc_type}.pdf", upload_date=datetime.now(timezone.utc))
        db.add(doc)
    db.commit()
    # Mock data for bidder 2 - all good
    db.add(Verification(document_id=6, source='GST Portal', status='verified', matched_data=json.dumps({"status": "ACTIVE"}), verified_at=datetime.now(timezone.utc)))
    db.add(ComplianceResult(tender_id=tender.id, bidder_id=bidder2.id, requirement='all', status='pass', evidence='All documents verified.'))
    db.add(RiskResult(bidder_id=bidder2.id, risk_level='LOW', finding='All clear', recommendation='All documents verified. Bid meets all tender requirements.'))
    db.add(OfficerDecision(bidder_id=bidder2.id, officer_id=officer.id, bid_id=bid1.id, decision='qualify', comments='Looks good', timestamp=datetime.now(timezone.utc)))

    # Seed Documents and Data for Bidder 3 (DISQUALIFY)
    for doc_type in doc_types:
        doc = Document(bidder_id=bidder3.id, tender_id=tender.id, document_type=doc_type, file_path=f"/uploads/b3_{doc_type}.pdf", upload_date=datetime.now(timezone.utc))
        db.add(doc)
    db.commit()
    # Mock data for bidder 3 - bad
    db.add(Verification(document_id=11, source='GST Portal', status='mismatch', matched_data=json.dumps({"document_gstin": "07KLMNO9012P3Z8", "gov_gstin": "07KLMNX9999P3Z8"}), verified_at=datetime.now(timezone.utc)))
    db.add(Verification(document_id=12, source='Udyam Portal', status='expired', matched_data=json.dumps({}), verified_at=datetime.now(timezone.utc)))
    db.add(Verification(document_id=15, source='Declaration', status='missing', matched_data=json.dumps({}), verified_at=datetime.now(timezone.utc)))
    db.add(ComplianceResult(tender_id=tender.id, bidder_id=bidder3.id, requirement='gst_valid', status='fail', evidence='GSTIN mismatch'))
    db.add(RiskResult(bidder_id=bidder3.id, risk_level='HIGH', finding='Critical compliance failures', recommendation='Critical compliance failures detected. GSTIN mismatch with government records. Udyam certificate expired. Declaration document missing.'))

    # Audit Logs
    db.add(AuditLog(user_id=1, action='System Seed', entity='system', entity_id='sys', timestamp=datetime.now(timezone.utc), details='Initial data seeded'))

    db.commit()
    db.close()
