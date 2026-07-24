from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Feedback
from app.db.session import get_db_session
from app.models.schemas import FeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("")
async def submit_feedback(
    req: FeedbackRequest, session: AsyncSession = Depends(get_db_session)
) -> dict:
    row = Feedback(request_id=req.request_id, rating=req.rating, comment=req.comment)
    session.add(row)
    await session.commit()
    return {"status": "recorded"}
