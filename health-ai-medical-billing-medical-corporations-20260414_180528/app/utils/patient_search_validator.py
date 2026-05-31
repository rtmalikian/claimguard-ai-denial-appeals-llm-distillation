"""
Patient search validation to ensure safe patient identification.
Requires minimum 3 identifiers to prevent medical errors.
"""

from typing import Optional
from datetime import date
from pydantic import BaseModel, field_validator


class PatientSearchCriteria(BaseModel):
    """Validated search criteria requiring minimum 3 identifiers."""

    patient_id: Optional[int] = None
    mrn: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None

    @field_validator("mrn", "first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    def count_identifiers(self) -> int:
        """Count how many identifiers are provided."""
        count = 0
        if self.patient_id is not None:
            count += 1
        if self.mrn:
            count += 1
        if self.first_name:
            count += 1
        if self.last_name:
            count += 1
        if self.date_of_birth:
            count += 1
        return count

    def get_missing_identifiers(self) -> list[str]:
        """Return list of missing identifiers."""
        missing = []
        if not self.mrn:
            missing.append("mrn")
        if not self.first_name:
            missing.append("first_name")
        if not self.last_name:
            missing.append("last_name")
        if not self.date_of_birth:
            missing.append("date_of_birth")
        return missing

    def validate_safe_search(self) -> tuple[bool, str]:
        """
        Validate that enough identifiers are provided for safe search.
        Returns (is_valid, error_message).
        """
        count = self.count_identifiers()

        if count < 3:
            missing = self.get_missing_identifiers()
            return False, (
                f"Safe patient search requires at least 3 identifiers. "
                f"Provided {count}. Please include: MRN, Date of Birth, and/or Last Name. "
                f"Missing: {', '.join(missing) if missing else 'at least 2 more fields'}"
            )

        return True, ""


def validate_patient_search(
    mrn: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    patient_id: Optional[int] = None,
) -> tuple[bool, str]:
    """
    Validate patient search criteria for safety.

    In medical settings, we require minimum 3 identifiers to prevent
    selecting the wrong patient, which could lead to medical errors.

    Args:
        mrn: Medical Record Number (strongest identifier)
        first_name: Patient's first name
        last_name: Patient's last name
        date_of_birth: Patient's date of birth
        patient_id: Internal patient ID

    Returns:
        tuple of (is_valid, error_message)
    """
    criteria = PatientSearchCriteria(
        mrn=mrn,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        patient_id=patient_id,
    )
    return criteria.validate_safe_search()
