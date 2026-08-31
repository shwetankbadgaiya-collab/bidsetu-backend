# MOCK GOVERNMENT SOURCE APIs — Simulates GST, Udyam, PAN, EPFO verification portals
# These are behind a service interface so real APIs can be substituted later.

class VerificationAdapter:
    """Base adapter interface. Swap with real API adapters in production."""
    def verify(self, data: dict) -> dict:
        raise NotImplementedError

class MockGSTAdapter(VerificationAdapter):
    """Simulates GST Portal verification."""
    MOCK_GST_DATABASE = {
        '23ABCDE1234F1Z5': {'gstin': '23ABCDE1234F1Z5', 'status': 'ACTIVE', 'company': 'ABC Pvt Ltd', 'registration_date': '2019-04-01'},
        '27FGHIJ5678K2Z3': {'gstin': '27FGHIJ5678K2Z3', 'status': 'ACTIVE', 'company': 'TechServe Solutions', 'registration_date': '2018-06-15'},
        '07KLMNX9999P3Z8': {'gstin': '07KLMNX9999P3Z8', 'status': 'ACTIVE', 'company': 'Global Infrastructure Corp', 'registration_date': '2017-01-10'},
    }
    
    def verify(self, data: dict) -> dict:
        gstin = data.get('gstin', '')
        if gstin in self.MOCK_GST_DATABASE:
            return {**self.MOCK_GST_DATABASE[gstin], 'verification': 'matched'}
        
        # Try partial match / check for mismatch
        for k, v in self.MOCK_GST_DATABASE.items():
            comp_name = data.get('company_name', '').lower()
            if comp_name and comp_name in v['company'].lower():
                return {**v, 'verification': 'mismatch', 'expected_gstin': k, 'provided_gstin': gstin}
        
        return {'gstin': gstin, 'status': 'NOT_FOUND', 'verification': 'not_found'}

class MockUdyamAdapter(VerificationAdapter):
    MOCK_UDYAM_DATABASE = {
        'UDYAM-XX-00-0000001': {'udyam_number': 'UDYAM-XX-00-0000001', 'status': 'ACTIVE', 'enterprise': 'ABC Pvt Ltd', 'category': 'Micro'},
        'UDYAM-MH-01-0000042': {'udyam_number': 'UDYAM-MH-01-0000042', 'status': 'ACTIVE', 'enterprise': 'TechServe Solutions', 'category': 'Small'},
        'UDYAM-DL-02-0000099': {'udyam_number': 'UDYAM-DL-02-0000099', 'status': 'EXPIRED', 'enterprise': 'Global Infra Corp', 'category': 'Medium', 'expiry_date': '2025-12-31'},
    }
    
    def verify(self, data: dict) -> dict:
        udyam = data.get('udyam_number', '')
        if udyam in self.MOCK_UDYAM_DATABASE:
            entry = self.MOCK_UDYAM_DATABASE[udyam]
            status = 'verified' if entry['status'] == 'ACTIVE' else entry['status'].lower()
            return {**entry, 'verification': status}
        return {'udyam_number': udyam, 'status': 'NOT_FOUND', 'verification': 'not_found'}

class MockPANAdapter(VerificationAdapter):
    MOCK_PAN_DATABASE = {
        'ABCDE1234F': {'pan': 'ABCDE1234F', 'name': 'Vikram Mehta', 'status': 'VALID'},
        'FGHIJ5678K': {'pan': 'FGHIJ5678K', 'name': 'Sunita Reddy', 'status': 'VALID'},
        'KLMNO9012P': {'pan': 'KLMNO9012P', 'name': 'Amit Patel', 'status': 'VALID'},
    }
    
    def verify(self, data: dict) -> dict:
        pan = data.get('pan_number', '')
        if pan in self.MOCK_PAN_DATABASE:
            return {**self.MOCK_PAN_DATABASE[pan], 'verification': 'matched'}
        return {'pan': pan, 'status': 'NOT_FOUND', 'verification': 'not_found'}

class MockEPFOAdapter(VerificationAdapter):
    def verify(self, data: dict) -> dict:
        return {'status': 'REGISTERED', 'company': data.get('company_name', ''), 'employees': 25, 'verification': 'verified'}

def get_verification_service(document_type: str) -> VerificationAdapter:
    """Factory function — swap adapters here for real APIs."""
    adapters = {
        'gst_certificate': MockGSTAdapter(),
        'udyam_certificate': MockUdyamAdapter(),
        'pan_card': MockPANAdapter(),
    }
    return adapters.get(document_type)

def verify_document(document_type: str, extracted_data: dict) -> dict:
    """Main entry point for verification."""
    adapter = get_verification_service(document_type)
    if adapter:
        return adapter.verify(extracted_data)
    
    # For documents without gov sources (authorization, declaration), return document-level review
    if document_type == 'authorization_letter':
        auth_company = extracted_data.get('authorized_company', '')
        company = extracted_data.get('company_name', '')
        if auth_company and company and auth_company.lower() != company.lower():
             return {'status': 'document_review', 'verification': 'review', 'issue': f"company name variation {auth_company} vs {company}"}
        
    return {'status': 'document_review', 'verification': 'manual_review_required'}
