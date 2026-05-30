from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from rag.db.session import get_db
from rag.evaluation.ragas_pipeline import EvaluationSample, run_evaluation

router = APIRouter(prefix="/eval", tags=["evaluation"])


class EvalSampleRequest(BaseModel):
    question: str
    ground_truth: str


@router.post("/run")
async def run_eval(
    samples: list[EvalSampleRequest],
    db: AsyncSession = Depends(get_db),
) -> dict:
    eval_samples = [EvaluationSample(s.question, s.ground_truth) for s in samples]
    result = await run_evaluation(eval_samples, db)
    return {
        "faithfulness": result.faithfulness,
        "answer_relevancy": result.answer_relevancy,
        "context_recall": result.context_recall,
    }
