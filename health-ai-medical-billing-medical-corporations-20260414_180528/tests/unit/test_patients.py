import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from datetime import date, datetime
from app.main import app
from app.core.security import create_access_token
from app.db.database import get_db


AUTH_HEADERS = {
    "Authorization": f"Bearer {create_access_token({'sub': '1', 'email': 'admin@example.test', 'role': 'admin'})}"
}


def get_mock_db(mock_db):
    try:
        yield mock_db
    finally:
        pass


class TestCreatePatient:
    def test_create_patient_success(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()

        mock_db.refresh = mock_refresh

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/patients/",
                headers=AUTH_HEADERS,
                json={
                    "mrn": "MRN-TEST-001",
                    "first_name": "John",
                    "last_name": "Doe",
                    "date_of_birth": "1990-01-15",
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["mrn"] == "MRN-TEST-001"
            assert data["first_name"] == "John"
            assert data["last_name"] == "Doe"
            assert data["date_of_birth"] == "1990-01-15"
        finally:
            app.dependency_overrides.clear()

    def test_create_patient_duplicate_mrn(self):
        mock_db = MagicMock()
        mock_existing = MagicMock()
        mock_existing.mrn = "MRN-TEST-001"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/patients/",
                headers=AUTH_HEADERS,
                json={"mrn": "MRN-TEST-001", "first_name": "John", "last_name": "Doe"},
            )
            assert response.status_code == 400
            assert "MRN already exists" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_create_patient_minimal(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def mock_refresh(obj):
            obj.id = 2
            obj.created_at = datetime.utcnow()

        mock_db.refresh = mock_refresh

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/patients/",
                headers=AUTH_HEADERS,
                json={"mrn": "MRN-TEST-002"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["mrn"] == "MRN-TEST-002"
        finally:
            app.dependency_overrides.clear()

    def test_create_patient_rejects_future_dob_safely(self):
        mock_db = MagicMock()

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/patients/",
                headers=AUTH_HEADERS,
                json={
                    "mrn": "MRN-TEST-003",
                    "first_name": "Future",
                    "last_name": "Synthetic",
                    "date_of_birth": "2999-01-15",
                },
            )
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert detail["error_code"] == "invalid_patient_demographics"
            assert detail["issues"][0]["field"] == "date_of_birth"
            assert detail["issues"][0]["safe_context"]["raw_field_value_included"] is False
            assert "2999" not in str(detail)
            mock_db.query.assert_not_called()
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()


class TestListPatients:
    def test_list_patients_empty(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/", headers=AUTH_HEADERS)
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_list_patients_with_results(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = None
        mock_patient.created_at = datetime.utcnow()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [mock_patient]

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/", headers=AUTH_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["mrn"] == "MRN-TEST-001"
        finally:
            app.dependency_overrides.clear()

    def test_list_patients_filter_by_first_name(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/?first_name=John", headers=AUTH_HEADERS)
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_patients_filter_by_last_name(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/?last_name=Smith", headers=AUTH_HEADERS)
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_patients_filter_by_dob(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/?dob=1990-01-15", headers=AUTH_HEADERS)
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_patients_with_pagination(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.limit.return_value.all.return_value = []

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/?skip=10&limit=50", headers=AUTH_HEADERS)
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestGetPatient:
    def test_get_patient_found(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = None
        mock_patient.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/1", headers=AUTH_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["mrn"] == "MRN-TEST-001"
        finally:
            app.dependency_overrides.clear()

    def test_get_patient_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/999", headers=AUTH_HEADERS)
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestGetPatientByMrn:
    def test_get_patient_by_mrn_found(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = None
        mock_patient.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/mrn/MRN-TEST-001", headers=AUTH_HEADERS)
            assert response.status_code == 200
            data = response.json()
            assert data["mrn"] == "MRN-TEST-001"
        finally:
            app.dependency_overrides.clear()

    def test_get_patient_by_mrn_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/v1/patients/mrn/INVALID", headers=AUTH_HEADERS)
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestUpdatePatient:
    def test_update_patient_success(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = None
        mock_patient.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/v1/patients/1",
                headers=AUTH_HEADERS,
                json={
                    "mrn": "MRN-TEST-001",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "date_of_birth": "1985-06-20",
                },
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_update_patient_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/v1/patients/999",
                headers=AUTH_HEADERS,
                json={"mrn": "MRN-TEST-001", "first_name": "Jane"},
            )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_update_patient_mrn_conflict(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.deleted_at = None

        mock_existing = MagicMock()
        mock_existing.id = 2
        mock_existing.mrn = "MRN-TEST-002"

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_patient,
            mock_existing,
        ]

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/v1/patients/1",
                headers=AUTH_HEADERS,
                json={"mrn": "MRN-TEST-002", "first_name": "Jane"},
            )
            assert response.status_code == 400
            assert "MRN already in use" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_update_patient_rejects_future_dob_safely(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = None
        mock_patient.created_at = datetime.utcnow()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/v1/patients/1",
                headers=AUTH_HEADERS,
                json={
                    "mrn": "MRN-TEST-001",
                    "first_name": "Future",
                    "last_name": "Synthetic",
                    "date_of_birth": "2999-01-15",
                },
            )
            assert response.status_code == 400
            detail = response.json()["detail"]
            assert detail["error_code"] == "invalid_patient_demographics"
            assert detail["issues"][0]["field"] == "date_of_birth"
            assert detail["issues"][0]["safe_context"]["raw_field_value_included"] is False
            assert "2999" not in str(detail)
            mock_db.commit.assert_not_called()
        finally:
            app.dependency_overrides.clear()


class TestDeletePatient:
    def test_delete_patient_success(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.claims = []
        mock_patient.deleted_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.delete("/api/v1/patients/1", headers=AUTH_HEADERS)
            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()

    def test_delete_patient_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.delete("/api/v1/patients/999", headers=AUTH_HEADERS)
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_patient_with_claims(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.deleted_at = None
        mock_claim = MagicMock()
        mock_claim.deleted_at = None
        mock_patient.claims = [mock_claim]

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.delete("/api/v1/patients/1", headers=AUTH_HEADERS)
            assert response.status_code == 204
            assert mock_patient.deleted_at is not None
            assert mock_claim.deleted_at is not None
        finally:
            app.dependency_overrides.clear()


class TestRestorePatient:
    def test_restore_patient_success(self):
        mock_db = MagicMock()
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.mrn = "MRN-TEST-001"
        mock_patient.first_name = "John"
        mock_patient.last_name = "Doe"
        mock_patient.date_of_birth = date(1990, 1, 15)
        mock_patient.deleted_at = datetime.utcnow()
        mock_patient.deleted_by_user_id = 1
        mock_patient.deletion_reason = "synthetic retention review"
        mock_patient.created_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_patient

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/v1/patients/1/restore", headers=AUTH_HEADERS)
            assert response.status_code == 200
            assert response.json()["deleted_at"] is None
            assert mock_patient.deleted_at is None
        finally:
            app.dependency_overrides.clear()
