"""Run daily next-day task generation (intended for cron at 00:05 org local time).

Example crontab:
  5 0 * * * cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.daily_task_generation
"""

from __future__ import annotations

import json
import sys

from app.database import SessionLocal
from app.services.daily_task_generation import DailyTaskGenerationService


def main() -> int:
    db = SessionLocal()
    try:
        result = DailyTaskGenerationService().run(db)
        print(
            json.dumps(
                {
                    "target_date": result.target_date.isoformat(),
                    "subjects_processed": result.subjects_processed,
                    "subjects_failed": result.subjects_failed,
                    "total_created": result.total_created,
                    "total_skipped": result.total_skipped,
                },
                ensure_ascii=False,
            )
        )
        return 1 if result.subjects_failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
