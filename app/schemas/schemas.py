from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional
import json as _json

class LoginRequest(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserOut

class TenderCreate(BaseModel):
    title: str
    department: str
    requirements: dict

class TenderOut(BaseModel):
    id: int
    tender_id: str
    title: str
    department: str
    requirements: dict
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator('requirements', mode='before')
    @classmethod
    def parse_requirements(cls, v):
        if isinstance(v, str):
            return _json.loads(v)
        return v

class BidOut(BaseModel):
    id: int
    bid_id: str
    bidder_id: int
    tender_id: int
    status: str
    risk_level: str
    compliance_score: float
    created_at: datetime
    bidder_name: str = ''
    company_name: str = ''
    model_config = ConfigDict(from_attributes=True)

class DocumentOut(BaseModel):
    id: int
    document_type: str
    file_path: str
    upload_date: datetime
    model_config = ConfigDict(from_attributes=True)

class ExtractedDataOut(BaseModel):
    id: int
    document_id: int
    field_name: str
    field_value: str
    confidence: float
    model_config = ConfigDict(from_attributes=True)

class VerificationOut(BaseModel):
    id: int
    document_id: int
    document: str = ''
    extracted: str = ''
    source: str
    status: str
    matched_data: Optional[dict] = None
    verified_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator('matched_data', mode='before')
    @classmethod
    def parse_matched_data(cls, v):
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except (ValueError, TypeError):
                return None
        return v

class ComplianceResultOut(BaseModel):
    id: int
    requirement: str
    status: str
    evidence: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ComplianceAnalysis(BaseModel):
    score: float
    risk_level: str
    results: list[ComplianceResultOut]
    recommendation: str

class RiskResultOut(BaseModel):
    id: int
    risk_level: str
    finding: str
    recommendation: str
    model_config = ConfigDict(from_attributes=True)

class DecisionRequest(BaseModel):
    bid_id: str
    decision: str
    comments: str

class DecisionOut(BaseModel):
    id: int
    decision: str
    comments: str
    timestamp: datetime
    officer_name: str = ''
    model_config = ConfigDict(from_attributes=True)

class AuditLogOut(BaseModel):
    id: int
    action: str
    entity: str
    entity_id: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None
    user_name: str = ''
    model_config = ConfigDict(from_attributes=True)
