import os

from fastapi import APIRouter, Response


router = APIRouter(tags=['version'])


@router.get('/versionz')
def versionz(response: Response) -> dict[str, str | None]:
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return {
        'datahub_sha': os.getenv('BUILD_SHA'),
        'hermes_sha': os.getenv('HERMES_BUILD_SHA'),
    }
