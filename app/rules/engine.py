RULES = {
    'gst_valid': {
        'description': 'GST Registration must be active', 
        'check': lambda v: v.get('gst_status') == 'ACTIVE' and v.get('verification') == 'matched'
    },
    'udyam_valid': {
        'description': 'Udyam Registration must be active', 
        'check': lambda v: v.get('udyam_status') == 'ACTIVE'
    },
    'pan_required': {
        'description': 'PAN Card must be valid and matched', 
        'check': lambda v: v.get('status') == 'VALID'
    },
    'authorization_required': {
        'description': 'Authorization letter must be verified', 
        'check': lambda v: v.get('verification') != 'manual_review_required'
    },
    'min_experience_years': {
        'description': 'Minimum experience requirement', 
        'check': lambda v: v.get('experience_years', 0) >= v.get('required_years', 3)
    },
}

def evaluate_rule(rule_name: str, verification_data: dict) -> tuple[str, str]:
    """Returns (status, evidence_description)"""
    if rule_name not in RULES:
        return 'fail', 'Rule not found'
        
    rule = RULES[rule_name]
    try:
        if rule['check'](verification_data):
            return 'pass', rule['description'] + ' met'
        return 'fail', rule['description'] + ' failed'
    except Exception as e:
        return 'fail', f"Error evaluating rule: {str(e)}"
