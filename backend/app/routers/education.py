from fastapi import APIRouter

from app.schemas import ok
from app.services.education import TOPICS

router = APIRouter(prefix="/api/v1/education", tags=["education"])


@router.get("/topics")
def list_topics():
    return ok([{"id": k, **v} for k, v in TOPICS.items()])
