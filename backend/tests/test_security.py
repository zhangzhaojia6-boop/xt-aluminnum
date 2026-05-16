from pathlib import PurePosixPath
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.security import validate_upload


def _mock_file(filename: str, size: int | None = None) -> MagicMock:
    f = MagicMock()
    f.filename = filename
    f.size = size
    return f


def test_validate_upload_allows_xlsx():
    validate_upload(_mock_file('data.xlsx', 1024))


def test_validate_upload_allows_csv():
    validate_upload(_mock_file('report.csv', 500))


def test_validate_upload_rejects_exe():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload(_mock_file('malware.exe', 1024))
    assert exc_info.value.status_code == 400


def test_validate_upload_rejects_oversized():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload(_mock_file('big.xlsx', 20 * 1024 * 1024))
    assert exc_info.value.status_code == 400
