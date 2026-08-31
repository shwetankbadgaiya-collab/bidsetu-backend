def assess_risk(verification_results: list, compliance_results: list) -> dict:
    """Calculate risk level based on findings."""
    risk_score = 0
    findings = []
    
    # Process verifications
    for v in verification_results:
        status = v.get('verification')
        if status == 'mismatch':
            risk_score += 3
            findings.append("Data mismatch detected")
        elif status == 'expired':
            risk_score += 2
            findings.append("Expired certificate detected")
        elif status == 'review' or status == 'manual_review_required':
            risk_score += 1
            findings.append("Document requires manual review")
        elif status == 'not_found' or status == 'missing':
            risk_score += 2
            findings.append("Missing required document or unverified source")
            
    # Process compliance
    for c in compliance_results:
        if c['status'] == 'fail':
            risk_score += 2
            findings.append(f"Failed compliance requirement: {c['requirement']}")
        elif c['status'] == 'review':
            risk_score += 1
            
    # Remove duplicates
    findings = list(set(findings))
    if not findings:
        findings = ["All clear"]
            
    if risk_score <= 2:
        risk_level = "LOW"
        recommendation = "All documents verified. Bid meets all tender requirements."
    elif risk_score <= 5:
        risk_level = "MEDIUM"
        recommendation = "Bid requires officer review due to one unverified requirement and authorization letter discrepancy."
    else:
        risk_level = "HIGH"
        recommendation = "Critical compliance failures detected. GSTIN mismatch with government records. Udyam certificate expired. Declaration document missing."
        
    return {
        'risk_level': risk_level,
        'risk_score': risk_score,
        'findings': findings,
        'recommendation': recommendation
    }
