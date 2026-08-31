from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    email = Column(String(100), unique=True)
    password_hash = Column(String(255))
    role = Column(String(20), default='officer')
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Tender(Base):
    __tablename__ = 'tenders'
    id = Column(Integer, primary_key=True)
    tender_id = Column(String(50), unique=True)
    title = Column(String(200))
    department = Column(String(200))
    requirements = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Bidder(Base):
    __tablename__ = 'bidders'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    company_name = Column(String(200))
    gstin = Column(String(15))
    pan = Column(String(10))
    udyam_number = Column(String(30))

class Bid(Base):
    __tablename__ = 'bids'
    id = Column(Integer, primary_key=True)
    bid_id = Column(String(20), unique=True)
    bidder_id = Column(Integer, ForeignKey('bidders.id'))
    tender_id = Column(Integer, ForeignKey('tenders.id'))
    status = Column(String(30), default='pending')
    risk_level = Column(String(20), default='low')
    compliance_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    bidder_id = Column(Integer, ForeignKey('bidders.id'))
    tender_id = Column(Integer, ForeignKey('tenders.id'))
    document_type = Column(String(50))
    file_path = Column(String(500))
    upload_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ExtractedData(Base):
    __tablename__ = 'extracted_data'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'))
    field_name = Column(String(100))
    field_value = Column(String(500))
    confidence = Column(Float)

class Verification(Base):
    __tablename__ = 'verifications'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'))
    source = Column(String(100))
    status = Column(String(30))
    matched_data = Column(Text)
    verified_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ComplianceResult(Base):
    __tablename__ = 'compliance_results'
    id = Column(Integer, primary_key=True)
    tender_id = Column(Integer, ForeignKey('tenders.id'))
    bidder_id = Column(Integer, ForeignKey('bidders.id'))
    requirement = Column(String(100))
    status = Column(String(30))
    evidence = Column(Text)

class RiskResult(Base):
    __tablename__ = 'risk_results'
    id = Column(Integer, primary_key=True)
    bidder_id = Column(Integer, ForeignKey('bidders.id'))
    risk_level = Column(String(20))
    finding = Column(Text)
    recommendation = Column(Text)

class OfficerDecision(Base):
    __tablename__ = 'officer_decisions'
    id = Column(Integer, primary_key=True)
    bidder_id = Column(Integer, ForeignKey('bidders.id'))
    officer_id = Column(Integer, ForeignKey('users.id'))
    bid_id = Column(Integer, ForeignKey('bids.id'), nullable=True)
    decision = Column(String(30))
    comments = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(200))
    entity = Column(String(100))
    entity_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(Text)
