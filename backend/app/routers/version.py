import os

from fastapi import APIRouter


router = APIRouter(tags=['version'])


@router.get('/versionz')
def versionz() -> dict[str, str | None]:
    return {
        'datahub_sha': os.getenv('BUILD_SHA'),
        'hermes_sha': os.getenv('HERMES_BUILD_SHA'),
    }
