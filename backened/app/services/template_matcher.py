import json
import os
from sqlalchemy.orm import Session
from app.db.models import ConfigurationTask
from app.services.excel_service import extract_column_headers


def auto_match_template(uploaded_file_path: str, db: Session, threshold: float = 0.7):
    """
    Automatically match the uploaded file to a task template based on column headers.
    
    Args:
        uploaded_file_path: Path to the uploaded Excel file
        db: Database session
        threshold: Minimum match score (0.0 to 1.0) to consider a match
    
    Returns:
        tuple: (matched_task, match_score) or (None, best_score)
    """
    # Extract columns from uploaded file
    uploaded_columns = extract_column_headers(uploaded_file_path)
    uploaded_columns_set = set(uploaded_columns)
    
    # Get all active templates
    templates = db.query(ConfigurationTask).filter(
        ConfigurationTask.is_active == True
    ).all()
    
    if not templates:
        return None, 0.0
    
    best_match = None
    best_score = 0.0
    
    for template in templates:
        try:
            expected_columns = json.loads(template.expected_columns)
        except:
            continue
        
        expected_columns_set = set(expected_columns)
        
        if not expected_columns_set:
            continue
        
        # Calculate match score: percentage of expected columns found in uploaded file
        matched_columns = uploaded_columns_set & expected_columns_set
        score = len(matched_columns) / len(expected_columns_set)
        
        # Also check if uploaded columns contain all expected columns (perfect match)
        if expected_columns_set.issubset(uploaded_columns_set):
            score = 1.0
        
        if score > best_score:
            best_score = score
            best_match = template
    
    # Only return match if score meets threshold
    if best_match and best_score >= threshold:
        return best_match, round(best_score * 100, 1)
    else:
        return None, round(best_score * 100, 1)


def get_all_templates(db: Session):
    """
    Get all active templates for manual selection fallback.
    """
    templates = db.query(ConfigurationTask).filter(
        ConfigurationTask.is_active == True
    ).all()
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "expected_columns": json.loads(t.expected_columns) if t.expected_columns else [],
            "template_filename": t.template_filename,
        }
        for t in templates
    ]


def get_match_summary(uploaded_columns: list, expected_columns: list):
    """
    Get a summary of what matched and what's missing.
    """
    uploaded_set = set(uploaded_columns)
    expected_set = set(expected_columns)
    
    matched = uploaded_set & expected_set
    missing = expected_set - uploaded_set
    extra = uploaded_set - expected_set
    
    return {
        "matched_columns": list(matched),
        "missing_columns": list(missing),
        "extra_columns": list(extra),
        "match_count": len(matched),
        "expected_count": len(expected_set),
    }