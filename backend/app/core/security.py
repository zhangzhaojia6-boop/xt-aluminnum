from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.pdf', '.png', '.jpg', '.jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_upload(file: UploadFile) -> None:
    if file.filename:
        ext = PurePosixPath(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f'不支持的文件类型: {ext}')
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(400, '文件大小超过 10MB 限制')
