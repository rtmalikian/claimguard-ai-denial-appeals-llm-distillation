"""
Architected by Raphael Malikian | Palmdale, California
📧 rtmalikian@gmail.com | 🔗 https://github.com/rtmalikian

Questions, comments, support, donations, or healthcare problem solutions? Reach out!
"""

import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm import sessionmaker
from app.db.database import engine
from app.models import Claim
from datetime import datetime, timedelta
import random


SAMPLE_CLAIMS = [
    {
        "patient_id": 1,
        "provider_id": 1,
        "claim_data": {
            "service_date": "2024-01-15",
            "amount": 250.00,
            "description": "Office visit - established patient",
        },
        "diagnosis_codes": ["I10", "E78.5"],
        "procedure_codes": ["99214"],
        "status": "submitted",
        "denial_prediction": 0.12,
        "denial_confidence": 0.72,
    },
    {
        "patient_id": 2,
        "provider_id": 1,
        "claim_data": {
            "service_date": "2024-01-18",
            "amount": 450.00,
            "description": "Office visit - new patient",
        },
        "diagnosis_codes": ["M54.5"],
        "procedure_codes": ["99204"],
        "status": "submitted",
        "denial_prediction": 0.35,
        "denial_confidence": 0.78,
    },
    {
        "patient_id": 3,
        "provider_id": 2,
        "claim_data": {
            "service_date": "2024-01-20",
            "amount": 125.00,
            "description": "Physical therapy",
        },
        "diagnosis_codes": ["M25.561"],
        "procedure_codes": ["97140"],
        "status": "denied",
        "denial_prediction": 0.65,
        "denial_confidence": 0.82,
    },
    {
        "patient_id": 4,
        "provider_id": 2,
        "claim_data": {
            "service_date": "2024-01-22",
            "amount": 1800.00,
            "description": "MRI - lumbar spine",
        },
        "diagnosis_codes": ["M54.5", "M48.0"],
        "procedure_codes": ["72148"],
        "status": "submitted",
        "denial_prediction": 0.22,
        "denial_confidence": 0.68,
    },
    {
        "patient_id": 5,
        "provider_id": 3,
        "claim_data": {
            "service_date": "2024-01-25",
            "amount": 3500.00,
            "description": "Cardiac stress test",
        },
        "diagnosis_codes": ["I25.10"],
        "procedure_codes": ["78428"],
        "status": "denied",
        "denial_prediction": 0.78,
        "denial_confidence": 0.85,
    },
    {
        "patient_id": 1,
        "provider_id": 3,
        "claim_data": {
            "service_date": "2024-01-28",
            "amount": 890.00,
            "description": "Colonoscopy with polyp removal",
        },
        "diagnosis_codes": ["K59.00", "K63.5"],
        "procedure_codes": ["45385"],
        "status": "submitted",
        "denial_prediction": 0.15,
        "denial_confidence": 0.71,
    },
    {
        "patient_id": 2,
        "provider_id": 1,
        "claim_data": {
            "service_date": "2024-02-01",
            "amount": 150.00,
            "description": "Lab work - lipid panel",
        },
        "diagnosis_codes": ["E78.5"],
        "procedure_codes": ["83718"],
        "status": "submitted",
        "denial_prediction": 0.08,
        "denial_confidence": 0.65,
    },
    {
        "patient_id": 3,
        "provider_id": 2,
        "claim_data": {
            "service_date": "2024-02-05",
            "amount": 2200.00,
            "description": "Sleep study - in lab",
        },
        "diagnosis_codes": ["G47.33"],
        "procedure_codes": ["95810"],
        "status": "denied",
        "denial_prediction": 0.82,
        "denial_confidence": 0.88,
    },
    {
        "patient_id": 4,
        "provider_id": 1,
        "claim_data": {
            "service_date": "2024-02-08",
            "amount": 320.00,
            "description": "Mental health visit",
        },
        "diagnosis_codes": ["F32.9"],
        "procedure_codes": ["90837"],
        "status": "submitted",
        "denial_prediction": 0.45,
        "denial_confidence": 0.75,
    },
    {
        "patient_id": 5,
        "provider_id": 3,
        "claim_data": {
            "service_date": "2024-02-10",
            "amount": 4500.00,
            "description": "Cataract surgery",
        },
        "diagnosis_codes": ["H25.10"],
        "procedure_codes": ["66984"],
        "status": "submitted",
        "denial_prediction": 0.18,
        "denial_confidence": 0.70,
    },
]


def seed_claims():
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(Claim).count()
        if existing > 0:
            print(f"Deleting {existing} existing claims...")
            db.query(Claim).delete()
            db.commit()

        now = datetime.utcnow()

        for i, claim_data in enumerate(SAMPLE_CLAIMS):
            days_ago = (i * 3) % 30  # Distribute across last 30 days
            submission_date = now - timedelta(days=days_ago)

            claim = Claim(
                patient_id=claim_data["patient_id"],
                provider_id=claim_data["provider_id"],
                claim_data=claim_data["claim_data"],
                diagnosis_codes=claim_data["diagnosis_codes"],
                procedure_codes=claim_data["procedure_codes"],
                status=claim_data["status"],
                submission_date=submission_date,
                created_at=submission_date,
                denial_prediction=claim_data["denial_prediction"],
                denial_confidence=claim_data["denial_confidence"],
                denial_reasons=[
                    {
                        "reason": f"Pattern match {i + 1}",
                        "severity": random.choice(["low", "medium", "high"]),
                    }
                ],
                recommendations=[
                    {
                        "action": "Review documentation",
                        "description": "Ensure complete records",
                        "priority": "medium",
                    }
                ],
            )
            db.add(claim)

        db.commit()
        print(f"✓ Seeded {len(SAMPLE_CLAIMS)} sample claims")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_claims()
