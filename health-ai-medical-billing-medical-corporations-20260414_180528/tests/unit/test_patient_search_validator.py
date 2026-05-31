import pytest
from datetime import date
from app.utils.patient_search_validator import (
    PatientSearchCriteria,
    validate_patient_search,
)


class TestPatientSearchValidator:
    def test_three_identifiers_valid(self):
        criteria = PatientSearchCriteria(
            mrn="MRN-001",
            first_name="John",
            last_name="Doe",
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is True
        assert error == ""

    def test_four_identifiers_valid(self):
        criteria = PatientSearchCriteria(
            mrn="MRN-001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 15),
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is True
        assert error == ""

    def test_two_identifiers_invalid(self):
        criteria = PatientSearchCriteria(
            first_name="John",
            last_name="Doe",
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is False
        assert "3 identifiers" in error
        assert "mrn" in error
        assert "date_of_birth" in error

    def test_one_identifier_invalid(self):
        criteria = PatientSearchCriteria(
            last_name="Doe",
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is False
        assert "at least 3 identifiers" in error

    def test_no_identifiers_invalid(self):
        criteria = PatientSearchCriteria()

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is False

    def test_mrn_plus_dob_plus_lastname_valid(self):
        criteria = PatientSearchCriteria(
            mrn="MRN-123",
            date_of_birth=date(1985, 6, 20),
            last_name="Smith",
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is True

    def test_patient_id_plus_two_others_valid(self):
        criteria = PatientSearchCriteria(
            patient_id=1,
            first_name="Jane",
            last_name="Doe",
        )

        is_valid, error = criteria.validate_safe_search()

        assert is_valid is True

    def test_count_identifiers(self):
        criteria = PatientSearchCriteria(
            mrn="MRN-001",
            first_name="John",
        )

        assert criteria.count_identifiers() == 2

    def test_get_missing_identifiers(self):
        criteria = PatientSearchCriteria(
            mrn="MRN-001",
        )

        missing = criteria.get_missing_identifiers()
        assert "first_name" in missing
        assert "last_name" in missing
        assert "date_of_birth" in missing

    def test_strip_whitespace(self):
        criteria = PatientSearchCriteria(
            first_name="  John  ",
            last_name="  Doe  ",
            mrn="MRN-001",
        )

        assert criteria.first_name == "John"
        assert criteria.last_name == "Doe"


class TestValidatePatientSearchFunction:
    def test_validate_function_valid(self):
        is_valid, error = validate_patient_search(
            mrn="MRN-001",
            first_name="John",
            last_name="Doe",
        )

        assert is_valid is True
        assert error == ""

    def test_validate_function_invalid(self):
        is_valid, error = validate_patient_search(
            first_name="John",
        )

        assert is_valid is False
        assert "3 identifiers" in error

    def test_validate_function_minimum_three(self):
        is_valid, error = validate_patient_search(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 15),
        )

        assert is_valid is True

    def test_validate_with_patient_id(self):
        is_valid, error = validate_patient_search(
            patient_id=1,
            last_name="Smith",
        )

        assert is_valid is False
        assert "at least 3" in error

    def test_validate_with_patient_id_plus_two(self):
        is_valid, error = validate_patient_search(
            patient_id=1,
            last_name="Smith",
            date_of_birth=date(1985, 1, 1),
        )

        assert is_valid is True
