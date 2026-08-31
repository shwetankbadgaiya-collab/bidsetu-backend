# MOCK OCR SERVICE — Returns realistic structured data for demonstration

def mock_ocr_extract(document_type: str, file_path: str, bidder_data: dict = None) -> list[dict]:
    """Simulate OCR extraction. Returns list of {field_name, field_value, confidence}."""
    if not bidder_data:
        bidder_data = {}
        
    gstin = bidder_data.get('gstin', '23ABCDE1234F1Z5')
    company_name = bidder_data.get('company_name', 'ABC Pvt Ltd')
    pan = bidder_data.get('pan', 'ABCDE1234F')
    name = bidder_data.get('name', 'Vikram Mehta')
    udyam_number = bidder_data.get('udyam_number', 'UDYAM-XX-00-0000001')
    bidder_id = bidder_data.get('bidder_id')

    # DISQUALIFY case modifications (Bidder 3)
    if bidder_id == 3:
        if document_type == 'gst_certificate':
            gstin = '07KLMNO9012P3Z8' # Document has different GSTIN than Gov Source (07KLMNX9999P3Z8)
        
    if document_type == 'gst_certificate':
        return [
            {'field_name': 'gstin', 'field_value': gstin, 'confidence': 0.96},
            {'field_name': 'company_name', 'field_value': company_name, 'confidence': 0.94},
            {'field_name': 'registration_date', 'field_value': '2019-04-01', 'confidence': 0.91},
            {'field_name': 'gst_status', 'field_value': 'ACTIVE', 'confidence': 0.98}
        ]
    elif document_type == 'udyam_certificate':
        return [
            {'field_name': 'udyam_number', 'field_value': udyam_number, 'confidence': 0.95},
            {'field_name': 'enterprise_name', 'field_value': company_name, 'confidence': 0.93},
            {'field_name': 'date_of_registration', 'field_value': '2020-07-15', 'confidence': 0.90},
            {'field_name': 'udyam_status', 'field_value': 'ACTIVE', 'confidence': 0.97}
        ]
    elif document_type == 'pan_card':
        return [
            {'field_name': 'pan_number', 'field_value': pan, 'confidence': 0.97},
            {'field_name': 'name', 'field_value': name, 'confidence': 0.95}
        ]
    elif document_type == 'authorization_letter':
        return [
            {'field_name': 'authorized_company', 'field_value': company_name, 'confidence': 0.88},
            {'field_name': 'authorized_signatory', 'field_value': name, 'confidence': 0.85}
        ]
    elif document_type == 'declaration':
        return [
            {'field_name': 'declarant', 'field_value': name, 'confidence': 0.92},
            {'field_name': 'declaration_date', 'field_value': '2026-08-15', 'confidence': 0.90}
        ]
    else:
        return []
