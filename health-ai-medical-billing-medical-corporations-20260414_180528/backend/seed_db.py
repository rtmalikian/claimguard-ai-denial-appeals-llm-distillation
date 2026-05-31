"""
Architected by Raphael Malikian | Palmdale, California
📧 rtmalikian@gmail.com | 🔗 https://github.com/rtmalikian

Questions, comments, support, donations, or healthcare problem solutions? Reach out!
"""

import json
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm import Session
from app.db.database import engine, Base
from app.models import DenialPattern, Patient, Provider


def seed_denial_patterns(db: Session):
    patterns = [
        {
            "icd_code": "Z00.00",
            "cpt_code": "99213",
            "payer_id": "MEDICARE",
            "denial_rate": 0.08,
            "common_reasons": [
                "Established patient visit - documentation insufficient",
                "Medical necessity not established",
                "Level of service mismatch",
            ],
            "recommendation": "Ensure detailed documentation of chief complaint and history of present illness",
        },
        {
            "icd_code": "M54.5",
            "cpt_code": "97140",
            "payer_id": "MEDICARE",
            "denial_rate": 0.15,
            "common_reasons": [
                "Modalities combined - bundling issue",
                "Prior authorization missing",
                "Maintenance therapy not covered",
            ],
            "recommendation": "Verify payer policy on combination therapies; obtain prior auth",
        },
        {
            "icd_code": "E11.9",
            "cpt_code": "83036",
            "payer_id": "MEDICARE",
            "denial_rate": 0.05,
            "common_reasons": [
                "Test included in global surgical package",
                "Duplicate service",
                "Frequency limit exceeded",
            ],
            "recommendation": "Check frequency limits and bundling rules",
        },
        {
            "icd_code": "I10",
            "cpt_code": "99214",
            "payer_id": "BCBS",
            "denial_rate": 0.12,
            "common_reasons": [
                "Office visit - excessive time documented",
                "Diagnosis code doesn't support visit level",
                "Preventive service combined with problem visit",
            ],
            "recommendation": "Match visit level to medical decision making complexity",
        },
        {
            "icd_code": "J45.909",
            "cpt_code": "94010",
            "payer_id": "AETNA",
            "denial_rate": 0.18,
            "common_reasons": [
                "Test not medically necessary",
                "Procedure included in another service",
                "Experimental/investigational",
            ],
            "recommendation": "Document clinical indication for pulmonary function testing",
        },
        {
            "icd_code": "M25.561",
            "cpt_code": "20610",
            "payer_id": "UNITEDHEALTH",
            "denial_rate": 0.22,
            "common_reasons": [
                "Injection - wrong site",
                "More units billed than medically necessary",
                "Unlisted procedure requires manual review",
            ],
            "recommendation": "Document exact injection site; verify dosage guidelines",
        },
        {
            "icd_code": "L90.0",
            "cpt_code": "17110",
            "payer_id": "CIGNA",
            "denial_rate": 0.35,
            "common_reasons": [
                "Cosmetic procedure - not medically necessary",
                "Pre-authorization required",
                "Global period not met",
            ],
            "recommendation": "Obtain prior auth; document medical necessity for lesion removal",
        },
        {
            "icd_code": "F32.9",
            "cpt_code": "90837",
            "payer_id": "MEDICARE",
            "denial_rate": 0.25,
            "common_reasons": [
                "Mental health visit - frequency exceeded",
                "Therapist credentials not eligible",
                "Supervision documentation missing",
            ],
            "recommendation": "Verify therapist credentials; document medical necessity clearly",
        },
        {
            "icd_code": "K21.0",
            "cpt_code": "43260",
            "payer_id": "MEDICARE",
            "denial_rate": 0.45,
            "common_reasons": [
                "ERCP - facility requirement not met",
                "Medical necessity not documented",
                "Unplanned readmission within 30 days",
            ],
            "recommendation": "Document strict medical necessity for ERCP vs diagnostic",
        },
        {
            "icd_code": "N39.0",
            "cpt_code": "51701",
            "payer_id": "MEDICAID",
            "denial_rate": 0.28,
            "common_reasons": [
                "Catheterization - not separately billable",
                "Wrong place of service",
                "Provider not eligible for this service",
            ],
            "recommendation": "Verify catheter insertion is separate from another procedure",
        },
        {
            "icd_code": "S06.5",
            "cpt_code": "99478",
            "payer_id": "MEDICARE",
            "denial_rate": 0.32,
            "common_reasons": [
                "Critical care - overlapping services",
                "Time documented not sufficient",
                "Concurrent care with another provider not justified",
            ],
            "recommendation": "Document continuous minute-by-minute critical care time",
        },
        {
            "icd_code": "H25.10",
            "cpt_code": "66984",
            "payer_id": "MEDICARE",
            "denial_rate": 0.15,
            "common_reasons": [
                "Cataract surgery - IOL not medically necessary",
                "Second eye within 90 days - clinical review",
                "Vision improvement not documented",
            ],
            "recommendation": "Document visual acuity and functional impairment",
        },
        {
            "icd_code": "Z96.1",
            "cpt_code": "V43.1",
            "payer_id": "MEDICARE",
            "denial_rate": 0.55,
            "common_reasons": [
                "Prosthetic - previous same device covered",
                "Not first prosthetic device",
                "Repair vs replacement documentation needed",
            ],
            "recommendation": "Document loss/damage; justify replacement necessity",
        },
        {
            "icd_code": "M50.13",
            "cpt_code": "63048",
            "payer_id": "MEDICARE",
            "denial_rate": 0.42,
            "common_reasons": [
                "Spinal surgery - fusion not medically necessary",
                "Adjacent levels not documented",
                "Post-surgical care included in global",
            ],
            "recommendation": "Document failed conservative treatment; obtain prior auth",
        },
        {
            "icd_code": "E78.5",
            "cpt_code": "83718",
            "payer_id": "BCBS",
            "denial_rate": 0.10,
            "common_reasons": [
                "Lipid panel - frequency limit exceeded",
                "Screening vs monitoring - code mismatch",
                "Panel broken into individual tests",
            ],
            "recommendation": "Check annual screening limits; use appropriate diagnosis",
        },
        {
            "icd_code": "J44.1",
            "cpt_code": "99223",
            "payer_id": "MEDICARE",
            "denial_rate": 0.14,
            "common_reasons": [
                "New patient visit - patient seen within 3 years",
                "Split/shared service - physician not present",
                "Critical care overlapped with hospital visit",
            ],
            "recommendation": "Verify new vs established patient status",
        },
        {
            "icd_code": "R51",
            "cpt_code": "99244",
            "payer_id": "AETNA",
            "denial_rate": 0.20,
            "common_reasons": [
                "Consultation - referring provider not documented",
                "Second opinion - no additional testing recommended",
                "Transfer of care vs consultation",
            ],
            "recommendation": "Ensure documentation shows request for consultation opinion",
        },
        {
            "icd_code": "I25.10",
            "cpt_code": "78428",
            "payer_id": "MEDICARE",
            "denial_rate": 0.38,
            "common_reasons": [
                "Cardiac stress test - insufficient symptoms",
                "Test not specific for diagnosis",
                "Previous normal test within 12 months",
            ],
            "recommendation": "Document anginal symptoms; show failed conservative care",
        },
        {
            "icd_code": "M79.3",
            "cpt_code": "20552",
            "payer_id": "CIGNA",
            "denial_rate": 0.17,
            "common_reasons": [
                "Trigger point injection - more than 3 sites",
                "Same day service with evaluation",
                "Unlisted code requires manual review",
            ],
            "recommendation": "Limit injections per session per policy",
        },
        {
            "icd_code": "G47.33",
            "cpt_code": "95810",
            "payer_id": "MEDICARE",
            "denial_rate": 0.52,
            "common_reasons": [
                "Sleep study - home sleep test sufficient",
                "In-lab study not medically necessary",
                "Apnea hypopnea index not met",
            ],
            "recommendation": "Start with home sleep test; document symptom severity",
        },
        {
            "icd_code": "K59.00",
            "cpt_code": "45378",
            "payer_id": "UNITEDHEALTH",
            "denial_rate": 0.25,
            "common_reasons": [
                "Colonoscopy - screening vs diagnostic",
                "Polyp removal - separate from screening",
                "Repeat procedure within recommended interval",
            ],
            "recommendation": "Use correct diagnosis for screening vs diagnostic",
        },
    ]

    existing = db.query(DenialPattern).count()
    if existing > 0:
        print(f"Already seeded: {existing} denial patterns exist")
        return

    for p in patterns:
        pattern = DenialPattern(
            icd_code=p["icd_code"],
            cpt_code=p["cpt_code"],
            payer_id=p["payer_id"],
            denial_rate=p["denial_rate"],
            common_reasons=p["common_reasons"],
            recommendation=p["recommendation"],
        )
        db.add(pattern)

    db.commit()
    print(f"✓ Seeded {len(patterns)} denial patterns")


def seed_providers(db: Session):
    existing = db.query(Provider).count()
    if existing > 0:
        print(f"Already seeded: {existing} providers exist")
        return

    providers = [
        Provider(npi="1234567890", name="Dr. Sarah Johnson", specialty="Family Medicine"),
        Provider(npi="2345678901", name="Dr. Michael Chen", specialty="Internal Medicine"),
        Provider(npi="3456789012", name="Dr. Emily Rodriguez", specialty="Cardiology"),
    ]

    for p in providers:
        db.add(p)

    db.commit()
    print(f"✓ Seeded {len(providers)} providers")


def seed_patients(db: Session):
    existing = db.query(Patient).count()
    if existing > 0:
        print(f"Already seeded: {existing} patients exist")
        return

    patients = [
        Patient(mrn="MRN001"),
        Patient(mrn="MRN002"),
        Patient(mrn="MRN003"),
        Patient(mrn="MRN004"),
        Patient(mrn="MRN005"),
    ]

    for p in patients:
        db.add(p)

    db.commit()
    print(f"✓ Seeded {len(patients)} patients")


def main():
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print("Seeding ClaimGuard AI database...")
        print("=" * 40)

        seed_denial_patterns(db)
        seed_providers(db)
        seed_patients(db)

        print("\n✓ Database seeding complete!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
