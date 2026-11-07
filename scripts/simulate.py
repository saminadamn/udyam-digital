"""Move an order through states from the command line, the same way the admin simulator does.

  python scripts/simulate.py list
  python scripts/simulate.py UD-2611-0004 --to INSTALLED
  python scripts/simulate.py UD-2611-0004 --late 30 --scan     # make the current step 30 h overdue, then run the SLA job once
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import or_, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.escalations import sla  # noqa: E402
from app.models import Order  # noqa: E402
from app.orders import simulator  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("order", help="order id, display id, or 'list'")
p.add_argument("--to", dest="to_state")
p.add_argument("--late", type=float, default=0, help="hours overdue")
p.add_argument("--scan", action="store_true", help="run the SLA scan once afterwards")
a = p.parse_args()

with SessionLocal() as db:
    if a.order == "list":
        for o in db.scalars(select(Order).order_by(Order.created_at.desc()).limit(20)):
            print(f"{o.display_id}  {o.state:<15} due {o.state_due_at or '-'}")
        sys.exit(0)
    o = db.scalar(select(Order).where(or_(Order.id == a.order, Order.display_id == a.order)))
    if not o:
        sys.exit(f"no order {a.order}")
    if a.to_state or a.late:
        print(json.dumps(simulator.advance(db, o, a.to_state, a.late, "simulator:cli"), indent=1))
    if a.scan:
        print(json.dumps(sla.scan(db), indent=1))
