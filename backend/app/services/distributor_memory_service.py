"""
Adaptive Distributor Memory (ADM) Service

This service solves a core problem in automated invoice parsing: while different
distributors use vastly different billing software, a SINGLE distributor almost
always uses the exact same software, resulting in a perfectly stable column
layout (e.g. "PRODUCT", "PACK", "QTY", "RATE") month after month. The pipeline
should not re-guess this layout from scratch every time.

Design Principle (Lightweight, Incremental Learning):
Do not introduce any deep learning framework, neural network, or external ML
training pipeline. A single distributor typically produces only 10-100 bills a
year, which is far too little data for a deep model and would be an engineering
mismatch. Instead, we use a simple, fully-explainable, incrementally-updated
statistical model: a per-distributor stored header-signature (a fuzzy string
template) plus simple per-field running accuracy counters. Every update is an
O(1) increment on confirm, not a retraining pass.

Important: This system only ever LEARNS FROM CONFIRMED bills (never from a
bill still pending review), ensuring it never reinforces an unreviewed mistake.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from app import models
from app.services.bill_parser import _clean_token
from app.core.logging import get_logger

logger = get_logger(__name__)


def normalize_header_token(text: str) -> str:
    """Cleans a header token exactly as bill_parser does."""
    return _clean_token(text)


def get_template_for_distributor(db: Session, tenant_id: int, distributor_id: int) -> Optional[Dict[str, Any]]:
    """Returns the stored template for a distributor, if it exists."""
    template = db.query(models.DistributorBillTemplate).filter(
        models.DistributorBillTemplate.tenant_id == tenant_id,
        models.DistributorBillTemplate.distributor_id == distributor_id
    ).first()

    if not template:
        return None

    return {
        "header_signature": json.loads(template.header_signature),
        "column_field_map": json.loads(template.column_field_map),
        "sample_count": template.sample_count
    }


def match_header_row_against_template(header_tokens: List[str], stored_signature: List[str], min_match_ratio: float = 0.7) -> bool:
    """
    Compares the current bill's detected header row tokens against a stored template.
    Two signatures match if at least min_match_ratio proportion of tokens correspond.
    """
    if not header_tokens or not stored_signature:
        return False
        
    current_joined = " ".join(header_tokens)
    stored_joined = " ".join(stored_signature)
    
    # fuzz.token_sort_ratio returns a score 0-100
    score = fuzz.token_sort_ratio(current_joined, stored_joined)
    
    return (score / 100.0) >= min_match_ratio


def get_field_accuracy_summary(db: Session, tenant_id: int, distributor_id: int) -> Dict[str, Any]:
    """Returns confidence metrics for a given distributor."""
    template = db.query(models.DistributorBillTemplate).filter(
        models.DistributorBillTemplate.tenant_id == tenant_id,
        models.DistributorBillTemplate.distributor_id == distributor_id
    ).first()
    
    if not template or template.sample_count == 0:
        return {
            "overall_confidence_pct": None,
            "sample_count": 0,
            "low_confidence_fields": [],
            "status": "not_learned"
        }
        
    accuracies = db.query(models.DistributorFieldAccuracy).filter(
        models.DistributorFieldAccuracy.tenant_id == tenant_id,
        models.DistributorFieldAccuracy.distributor_id == distributor_id
    ).all()
    
    total_fields_seen = sum(a.times_total for a in accuracies)
    total_corrections = sum(a.times_corrected for a in accuracies)
    
    if total_fields_seen > 0:
        overall_confidence_pct = max(0.0, min(100.0, 100.0 * (1.0 - (total_corrections / total_fields_seen))))
    else:
        overall_confidence_pct = 100.0
        
    overall_confidence_pct = round(overall_confidence_pct, 2)
    
    low_confidence_fields = []
    for acc in accuracies:
        if acc.times_total >= 3 and (acc.times_corrected / acc.times_total) > 0.3:
            low_confidence_fields.append(acc.field_name)
            
    if template.sample_count < 5:
        status = "learning"
    elif overall_confidence_pct >= 85:
        status = "confident"
    else:
        status = "needs_attention"
        
    return {
        "overall_confidence_pct": overall_confidence_pct,
        "sample_count": template.sample_count,
        "low_confidence_fields": low_confidence_fields,
        "status": status
    }


def learn_from_confirmed_bill(db: Session, tenant_id: int, distributor_id: int, header_tokens: List[str], column_field_map: Dict[str, str], field_corrections: Dict[str, bool]) -> None:
    """
    Called once per confirmed bill to increment accuracy counters and update/reinforce the template.
    """
    template = db.query(models.DistributorBillTemplate).filter(
        models.DistributorBillTemplate.tenant_id == tenant_id,
        models.DistributorBillTemplate.distributor_id == distributor_id
    ).first()
    
    now = datetime.now(timezone.utc)
    
    if template is None:
        new_template = models.DistributorBillTemplate(
            tenant_id=tenant_id,
            distributor_id=distributor_id,
            header_signature=json.dumps(header_tokens),
            column_field_map=json.dumps(column_field_map),
            sample_count=1,
            last_confirmed_at=now
        )
        db.add(new_template)
    else:
        stored_signature = json.loads(template.header_signature)
        if match_header_row_against_template(header_tokens, stored_signature):
            template.sample_count += 1
            template.last_confirmed_at = now
        else:
            logger.info(f"Distributor {distributor_id} layout drifted. Resetting template.")
            template.header_signature = json.dumps(header_tokens)
            template.column_field_map = json.dumps(column_field_map)
            template.sample_count = 1
            template.last_confirmed_at = now

    # Upsert field accuracy records
    accuracies = db.query(models.DistributorFieldAccuracy).filter(
        models.DistributorFieldAccuracy.tenant_id == tenant_id,
        models.DistributorFieldAccuracy.distributor_id == distributor_id
    ).all()
    
    acc_map = {a.field_name: a for a in accuracies}
    
    for field_name, was_corrected in field_corrections.items():
        if field_name in acc_map:
            acc = acc_map[field_name]
            acc.times_total += 1
            if was_corrected:
                acc.times_corrected += 1
            acc.updated_at = now
        else:
            new_acc = models.DistributorFieldAccuracy(
                tenant_id=tenant_id,
                distributor_id=distributor_id,
                field_name=field_name,
                times_total=1,
                times_corrected=1 if was_corrected else 0,
                updated_at=now
            )
            db.add(new_acc)
            
    db.flush()
