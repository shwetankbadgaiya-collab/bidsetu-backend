def evaluate_compliance(tender_requirements: dict, verification_results: list, extracted_data_map: dict) -> dict:
    """Evaluate bid compliance against tender requirements.
    Returns: {score: float, results: [{requirement, status, evidence}], recommendation: str}
    """
    results = []
    
    # helper to find verification by source or doc type mapping
    def get_verification(key: str):
        mapping = {
            'gst': ['GST Portal', 'gst_certificate'],
            'udyam': ['Udyam Portal', 'udyam_certificate'],
            'pan': ['PAN Authority', 'pan_card'],
            'auth': ['Document Analysis', 'authorization_letter']
        }
        sources = mapping.get(key, [])
        for v in verification_results:
            # We don't have source string here easily if it's merged, but we have verification status and keys
            if key == 'gst' and ('gstin' in v or v.get('expected_gstin')): return v
            if key == 'udyam' and 'udyam_number' in v: return v
            if key == 'pan' and 'pan' in v: return v
            if key == 'auth' and (v.get('verification') == 'review' or v.get('verification') == 'manual_review_required' or v.get('authorized_company')): return v
        return None

    pass_count = 0
    total_reqs = 0
    review_count = 0
    
    # Rule 1
    if tender_requirements.get('gst_valid'):
        total_reqs += 1
        v = get_verification('gst')
        if v:
            if v.get('status') == 'ACTIVE' and v.get('verification') == 'matched':
                results.append({'requirement': 'gst_valid', 'status': 'pass', 'evidence': 'GST Portal Verified'})
                pass_count += 1
            elif v.get('verification') == 'mismatch':
                results.append({'requirement': 'gst_valid', 'status': 'fail', 'evidence': 'GSTIN mismatch with government records'})
            else:
                results.append({'requirement': 'gst_valid', 'status': 'fail', 'evidence': 'GST status not active'})
        else:
            results.append({'requirement': 'gst_valid', 'status': 'fail', 'evidence': 'Missing GST verification'})

    # Rule 2
    if tender_requirements.get('udyam_valid'):
        total_reqs += 1
        v = get_verification('udyam')
        if v:
            if v.get('status') == 'ACTIVE':
                results.append({'requirement': 'udyam_valid', 'status': 'pass', 'evidence': 'Udyam verified active'})
                pass_count += 1
            elif v.get('status') == 'EXPIRED':
                results.append({'requirement': 'udyam_valid', 'status': 'fail', 'evidence': 'Udyam certificate expired'})
            else:
                results.append({'requirement': 'udyam_valid', 'status': 'fail', 'evidence': f"Udyam status: {v.get('status')}"})
        else:
            results.append({'requirement': 'udyam_valid', 'status': 'fail', 'evidence': 'Missing Udyam verification'})

    # Rule 3
    if tender_requirements.get('pan_required'):
        total_reqs += 1
        v = get_verification('pan')
        if v:
            if v.get('verification') == 'matched':
                results.append({'requirement': 'pan_required', 'status': 'pass', 'evidence': 'PAN matched'})
                pass_count += 1
            else:
                results.append({'requirement': 'pan_required', 'status': 'fail', 'evidence': 'PAN verification failed'})
        else:
            results.append({'requirement': 'pan_required', 'status': 'fail', 'evidence': 'Missing PAN verification'})

    # Rule 4
    if tender_requirements.get('authorization_required'):
        total_reqs += 1
        v = get_verification('auth')
        if v:
            if v.get('verification') == 'review':
                results.append({'requirement': 'authorization_required', 'status': 'review', 'evidence': v.get('issue', 'Manual review required')})
                review_count += 1
            elif v.get('verification') == 'manual_review_required':
                results.append({'requirement': 'authorization_required', 'status': 'pass', 'evidence': 'Document provided'})
                pass_count += 1
            else:
                results.append({'requirement': 'authorization_required', 'status': 'fail', 'evidence': 'Verification failed'})
        else:
            results.append({'requirement': 'authorization_required', 'status': 'fail', 'evidence': 'Missing authorization'})
            
    # Rule 5
    if tender_requirements.get('min_experience_years'):
        total_reqs += 1
        results.append({'requirement': 'min_experience_years', 'status': 'fail', 'evidence': 'missing experience evidence'})

    if total_reqs == 0:
        score = 100.0
    else:
        score = ((pass_count + (review_count * 0.5)) / total_reqs) * 100

    fails = sum(1 for r in results if r['status'] == 'fail')
    reviews = sum(1 for r in results if r['status'] == 'review')
    
    if fails > 0:
        recommendation = "Critical compliance failures detected."
        risk_level = "HIGH"
    elif reviews > 0:
        recommendation = "Bid requires officer review due to some unverified requirements."
        risk_level = "MEDIUM"
    else:
        recommendation = "All documents verified. Bid meets all tender requirements."
        risk_level = "LOW"
        
    return {
        'score': round(score, 1),
        'results': results,
        'risk_level': risk_level,
        'recommendation': recommendation
    }
