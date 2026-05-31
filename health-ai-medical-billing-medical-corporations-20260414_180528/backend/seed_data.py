"""
Architected by Raphael Malikian | Palmdale, California
📧 rtmalikian@gmail.com | 🔗 https://github.com/rtmalikian

Questions, comments, support, donations, or healthcare problem solutions? Reach out!
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal

DENIAL_PATTERNS = [
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
            " office visit - excessive time documented",
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
            " opinion - no additional testing recommended",
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

APPEAL_LETTER_TEMPLATES = [
    {
        "appeal_type": "medical_necessity",
        "template": """
        Date: {date}
        
        RE: Appeal for Claim #{claim_id}
        Patient: {patient_name}
        Date of Service: {service_date}
        
        Dear Appeals Reviewer:
        
        This letter serves as a formal appeal for the denial of claim #{claim_id} for 
        {procedure_description} performed on {service_date}.
        
        The claim was denied for reason: {denial_reason}
        
        We believe this denial should be overturned based on the following:
        
        1. MEDICAL NECESSITY DOCUMENTATION:
        {medical_necessity_details}
        
        2. SUPPORTING CLINICAL EVIDENCE:
        {clinical_evidence}
        
        3. RELEVANT PAYER POLICY:
        {payer_policy_reference}
        
        4. ALTERNATIVE TREATMENTS TRIED:
        {alternative_treatments}
        
        We respectfully request reconsideration of this denial and full reimbursement 
        for the services rendered. Please contact our office if additional information 
        is required.
        
        Sincerely,
        {provider_name}
        {credentials}
        """,
    },
    {
        "appeal_type": "coding_error",
        "template": """
        Date: {date}
        
        RE: Correction Request for Claim #{claim_id}
        
        We are writing to request correction of the coding error identified in the 
        denial of claim #{claim_id}.
        
        ORIGINAL DENIAL REASON: {denial_reason}
        
        CORRECT INFORMATION:
        - Correct Diagnosis Code: {correct_icd}
        - Correct Procedure Code: {correct_cpt}
        - Supporting Documentation: {documentation_attached}
        
        The error occurred due to {error_cause}. We have attached corrected 
        documentation and respectfully request the claim be reprocessed.
        
        Thank you for your consideration.
        
        {provider_name}
        """,
    },
    {
        "appeal_type": "timely_filing",
        "template": """
        Date: {date}
        
        RE: Request for Extension - Claim #{claim_id}
        
        We are appealing the timely filing denial for claim #{claim_id}.
        
        The claim was submitted on {original_submission_date} but was returned 
        for additional information. The requested information was provided on 
        {info_provided_date}, which was within {days} days of the request.
        
        We request an exception to the timely filing deadline based on:
        {extenuating_circumstances}
        
        We have attached documentation supporting our request and are committed 
        to timely submission of all claims.
        
        {provider_name}
        """,
    },
]

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
        "procedure_codes": ["97140", "97010"],
    },
]


if __name__ == "__main__":
    import sys

    print("ClaimGuard AI - Seed Data")
    print("=" * 40)
    print(f"\n{len(DENIAL_PATTERNS)} denial patterns loaded")
    print(f"{len(APPEAL_LETTER_TEMPLATES)} appeal templates loaded")
    print(f"{len(SAMPLE_CLAIMS)} sample claims loaded")

    print("\n=== Sample Denial Pattern ===")
    print(json.dumps(DENIAL_PATTERNS[0], indent=2))

    print("\n=== Sample Claim ===")
    print(json.dumps(SAMPLE_CLAIMS[0], indent=2))
