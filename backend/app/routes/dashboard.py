from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..auth import current_membership
from ..utils import maturity_level

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Client request: a department with fewer than five people who completed the
# diagnostic must not be shown separately, and its risks must not be exposed.
SMALL_GROUP_MIN_RESPONDENTS = 5


@router.get("")
def org_dashboard(org_id: int, m: models.Membership = Depends(current_membership), db: Session = Depends(get_db)):
    if m.role != "admin":
        raise HTTPException(403, "Admins only")
    if org_id != m.org_id:
        raise HTTPException(403, "Not your organization")

    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    members = db.query(models.Membership).filter_by(org_id=org_id).all()
    departments = []
    all_flags = {}
    other = {"employees": 0, "responded": 0, "scores": []}

    for dept in org.departments:
        dept_members = [x for x in members if x.department_id == dept.id]
        scores = []
        dept_flags = {}
        responded = 0
        for dm in dept_members:
            rows = db.query(models.Response).filter_by(membership_id=dm.id).all()
            if rows:
                responded += 1
            for r in rows:
                if r.score is not None:
                    scores.append(r.score)
                for f in r.flags or []:
                    dept_flags[f] = dept_flags.get(f, 0) + 1

        if responded < SMALL_GROUP_MIN_RESPONDENTS:
            other["employees"] += len(dept_members)
            other["responded"] += responded
            other["scores"].extend(scores)
            continue

        avg = sum(scores) / len(scores) if scores else None
        departments.append({
            "department": dept.name,
            "employees": len(dept_members),
            "responded": responded,
            "average_score": round(avg, 2) if avg is not None else None,
            "level": maturity_level(avg),
        })
        for flag, count in dept_flags.items():
            all_flags[flag] = all_flags.get(flag, 0) + count

    if other["responded"]:
        avg = sum(other["scores"]) / len(other["scores"]) if other["scores"] else None
        departments.append({
            "department": "Other teams",
            "employees": other["employees"],
            "responded": other["responded"],
            "average_score": round(avg, 2) if avg is not None else None,
            "level": maturity_level(avg),
        })

    return {
        "organization": org.name,
        "departments": departments,
        "top_risks": sorted(all_flags.items(), key=lambda kv: -kv[1])[:5],
    }
