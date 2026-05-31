import pytest
from unittest.mock import patch, MagicMock
from app.db.database import get_db, init_db, engine, SessionLocal, Base


class TestDatabaseConnection:
    def test_engine_exists(self):
        assert engine is not None
        assert str(engine.url) is not None

    def test_session_local_exists(self):
        assert SessionLocal is not None

    def test_base_exists(self):
        assert Base is not None

    def test_engine_has_pool(self):
        assert engine.pool is not None

    def test_engine_url(self):
        url = str(engine.url)
        assert url is not None
        assert len(url) > 0


class TestGetDb:
    def test_get_db_generator(self):
        mock_session = MagicMock()

        with patch("app.db.database.SessionLocal", return_value=mock_session):
            generator = get_db()
            db = next(generator)

            assert db == mock_session
            mock_session.close.assert_not_called()

    def test_get_db_closes_on_exit(self):
        mock_session = MagicMock()

        with patch("app.db.database.SessionLocal", return_value=mock_session):
            generator = get_db()
            db = next(generator)
            try:
                next(generator)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()


class TestInitDb:
    @patch("app.db.database.Base.metadata.create_all")
    @patch("app.models.Patient")
    @patch("app.models.Provider")
    @patch("app.models.Claim")
    @patch("app.models.DenialPattern")
    @patch("app.models.AuditLog")
    def test_init_db_creates_tables(self, *mocks):
        with patch("app.db.database.engine", MagicMock()):
            init_db()

    @patch("app.db.database.Base.metadata.create_all")
    def test_init_db_calls_create_all(self, mock_create_all):
        mock_engine = MagicMock()
        mock_create_all.return_value = None

        with patch("app.db.database.engine", mock_engine):
            with patch("app.models.Patient"):
                with patch("app.models.Provider"):
                    with patch("app.models.Claim"):
                        with patch("app.models.DenialPattern"):
                            with patch("app.models.AuditLog"):
                                init_db()

                                mock_create_all.assert_called_once_with(bind=mock_engine)
