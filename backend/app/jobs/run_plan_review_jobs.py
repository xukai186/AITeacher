"""Run pending PlanReview jobs.

Example crontab (every minute):
  * * * * * cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.run_plan_review_jobs --once
"""

from __future__ import annotations

import argparse
import time

from app.database import SessionLocal
from app.services.plan_review_jobs import PlanReviewJobRunner


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true", help="Run once and exit")
    p.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between loops")
    p.add_argument("--limit", type=int, default=50, help="Max jobs per loop")
    args = p.parse_args()

    runner = PlanReviewJobRunner()
    while True:
        db = SessionLocal()
        try:
            ran = runner.run_pending(db, limit=args.limit)
            db.commit()
        finally:
            db.close()

        if args.once:
            return 0
        if ran == 0:
            time.sleep(args.sleep)


if __name__ == "__main__":
    raise SystemExit(main())

