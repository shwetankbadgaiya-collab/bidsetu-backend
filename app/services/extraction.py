def extract_fields(ocr_results: list[dict]) -> dict:
    """Transform raw OCR results into a structured field map."""
    return {item['field_name']: item['field_value'] for item in ocr_results}
