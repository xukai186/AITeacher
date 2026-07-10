"""Refresh 7-day tactical plans on month start for students with active roadmaps.

Example crontab (1st of month, 00:10 org local time):
  10 0 1 * * cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.monthly_tactical_refresh
"""

from __future__ import annotations

import json
import sys

from app.database import SessionLocal
from app.services.roadmap_monthly_refresh import RoadmapMonthlyRefreshService


def main() -> int:
    db = SessionLocal()
    try:
        result = RoadmapMonthlyRefreshService().run(db)
        db.commit()
        print(
            json.dumps(
                {
                    "target_date": result.target_date.isoformat(),
                    "students_processed": result.students_processed,
                    "students_refreshed": result.students_refreshed,
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
