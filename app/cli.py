"""Command line: python -m app.cli <command>

  init-db                      create tables
  create-admin EMAIL           create an admin user (prints a temporary password)
  seed-demo                    load clearly-labelled demo stores, products and history
  seed-prospects               add real stores to approach (admin-only outreach list)
  import-csv FILE [--retailer SLUG]
  run-feeds                    import every active retailer's feed URL / permitted feed
  check-alerts                 email price alerts that hit their target
  run-jobs                     run-feeds + check-alerts (use from cron)
  scheduler                    loop forever: feeds every 6 h, alerts every hour
"""
import argparse
import secrets
import sys

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Retailer, User
from .security import hash_password


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    a = sub.add_parser("create-admin"); a.add_argument("email"); a.add_argument("--password")
    sub.add_parser("seed-demo")
    sub.add_parser("seed-prospects")
    i = sub.add_parser("import-csv"); i.add_argument("file"); i.add_argument("--retailer")
    for c in ("run-feeds", "check-alerts", "run-jobs", "scheduler"):
        sub.add_parser(c)
    args = ap.parse_args(argv)
    init_db()

    if args.cmd == "init-db":
        print("database ready")
    elif args.cmd == "create-admin":
        with SessionLocal() as db:
            if db.scalar(select(User).where(User.email == args.email.lower())):
                sys.exit("user already exists")
            pw = args.password or secrets.token_urlsafe(12)
            db.add(User(email=args.email.lower(), role="admin", password_hash=hash_password(pw), name="Admin"))
            db.commit()
        print(f"admin created: {args.email}\npassword: {pw}\nYou'll set up two-step verification at first login.")
    elif args.cmd == "seed-demo":
        from .demo import seed
        with SessionLocal() as db:
            print(seed(db))
    elif args.cmd == "seed-prospects":
        from .prospects import seed_prospects
        with SessionLocal() as db:
            print(seed_prospects(db))
    elif args.cmd == "import-csv":
        from .importer import import_csv_text
        with SessionLocal() as db:
            r = db.scalar(select(Retailer).where(Retailer.slug == args.retailer)) if args.retailer else None
            run = import_csv_text(db, open(args.file, encoding="utf-8-sig").read(), source="cli", retailer=r,
                                  filename=args.file)
            print(f"import #{run.id}: {run.rows_ok} ok, {run.rows_review} review, {run.rows_rejected} rejected")
            for rj in run.rejects[:20]:
                print(f"  row {rj.row_number}: {rj.reasons}")
    else:
        from . import jobs
        if args.cmd == "scheduler":
            jobs.scheduler(SessionLocal)
        with SessionLocal() as db:
            if args.cmd in ("run-feeds", "run-jobs"):
                jobs.run_all_feeds(db)
            if args.cmd in ("check-alerts", "run-jobs"):
                jobs.check_alerts(db)


if __name__ == "__main__":
    main()
