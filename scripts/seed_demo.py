from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import init_db
from app.schemas import EventCreate, QuestionCreate
from app.service import create_event, create_question, open_lobby


def main() -> None:
    init_db()
    event = create_event(
        EventCreate(
            title="LivePulse 데모 세미나",
            description="QR로 참여하고 실시간으로 결과를 확인해 보세요.",
        )
    )
    create_question(
        event["id"],
        QuestionCreate(
            text="오늘 가장 기대되는 세션은 무엇인가요?",
            type="SINGLE",
            options=["제품 전략", "AI 활용", "고객 사례", "네트워킹"],
            chart_type="BAR",
        ),
    )
    create_question(
        event["id"],
        QuestionCreate(
            text="오늘 행사에 얼마나 만족하시나요?",
            type="RATING",
            min_label="매우 불만족",
            max_label="매우 만족",
        ),
    )
    create_question(
        event["id"],
        QuestionCreate(
            text="다음 행사에서 가장 다루고 싶은 주제는?",
            type="SINGLE",
            options=["신기술", "실무 사례", "조직문화", "커리어"],
            chart_type="PIE",
        ),
    )
    open_lobby(event["id"])
    print("데모 행사를 생성했습니다.")
    print(f"관리 화면: http://localhost:8000/host/{event['id']}")
    print(f"참가 화면: http://localhost:8000/e/{event['code']}")
    print(f"발표 화면: http://localhost:8000/present/{event['presentation_token']}")


if __name__ == "__main__":
    main()
