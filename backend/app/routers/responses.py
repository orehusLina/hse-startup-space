from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from .. import schemas, serializers
from ..deps import DB, CurrentUser
from ..models import Post, Response

router = APIRouter(prefix="/api/responses", tags=["responses"])


def _lock_response(db: DB, response_id: int) -> Response:
    # Row lock serialises "author decides" vs "applicant withdraws" on the same response.
    response = db.scalar(select(Response).where(Response.id == response_id).with_for_update())
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Отклик не найден")
    return response


@router.post("/{response_id}/withdraw", response_model=schemas.SentResponseOut)
def withdraw(response_id: int, db: DB, user: CurrentUser):
    response = _lock_response(db, response_id)
    if response.applicant_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Отклик не найден")
    if response.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Отозвать можно только отклик на рассмотрении")
    response.status = "withdrawn"
    db.commit()
    db.refresh(response)
    return serializers.sent_response(response)


@router.post("/{response_id}/decision", response_model=schemas.ReceivedResponseOut)
def decide(response_id: int, data: schemas.DecisionIn, db: DB, user: CurrentUser):
    response = _lock_response(db, response_id)
    post = db.get(Post, response.post_id)
    if post.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Решение принимает только автор публикации")
    if response.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "По этому отклику уже есть решение")
    if post.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Публикация закрыта")
    response.status = data.status
    response.author_note = data.note
    response.decided_at = datetime.now(UTC)
    db.commit()
    db.refresh(response)
    return serializers.received_response(response)
