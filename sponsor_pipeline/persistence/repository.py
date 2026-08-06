from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sponsor_pipeline.models import (
    Company,
    CompanySize,
    ContactMethod,
    ContactMethodType,
    ContactPerson,
    ContactRole,
    DiscoverySource,
    Evidence,
    LeadStatus,
    OutreachProspect,
    Priority,
    SponsorMotivation,
    SponsorReport,
    SponsorScore,
    SponsorTier,
)


class SponsorRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """
        Yield a connection for a single unit of work, then close it.

        Note: sqlite3.Connection's own context manager protocol only
        commits/rolls back the transaction on exit — it does NOT close
        the connection. Since every repository method opened a fresh
        connection via _connect(), that meant a new, never-closed
        connection was leaked on every single call. Wrapping it here
        keeps every existing call site (`with self._connect() as conn:`)
        working unchanged while making sure the connection is actually
        closed once the transaction is done.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    website TEXT,
                    industry TEXT,
                    company_size TEXT,
                    discovery_sources TEXT,
                    status TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS scores (
                    company_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                );
                CREATE TABLE IF NOT EXISTS reports (
                    company_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                );
                CREATE TABLE IF NOT EXISTS contacts (
                    id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                """
            )

    def save_company(self, company: Company) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO companies (id, name, website, industry, company_size, discovery_sources, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    website=excluded.website,
                    industry=excluded.industry,
                    company_size=excluded.company_size,
                    discovery_sources=excluded.discovery_sources,
                    status=excluded.status
                """,
                (
                    company.id,
                    company.name,
                    company.website,
                    company.industry,
                    company.company_size.value,
                    json.dumps([s.value for s in company.discovery_sources]),
                    company.status.value,
                    company.created_at.isoformat(),
                ),
            )

    def save_score(self, score: SponsorScore) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scores (company_id, data) VALUES (?, ?)
                ON CONFLICT(company_id) DO UPDATE SET data=excluded.data
                """,
                (score.company.id, json.dumps(_score_to_dict(score))),
            )

    def save_report(self, report: SponsorReport) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (company_id, data) VALUES (?, ?)
                ON CONFLICT(company_id) DO UPDATE SET data=excluded.data
                """,
                (report.company_id, json.dumps(_report_to_dict(report))),
            )

    def save_contact(self, contact: ContactPerson) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO contacts (id, company_id, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data=excluded.data
                """,
                (contact.id, contact.company_id, json.dumps(_contact_to_dict(contact))),
            )

    def save_evidence(self, company_id: str, evidence: list[Evidence]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM evidence WHERE company_id = ?", (company_id,))
            for item in evidence:
                conn.execute(
                    "INSERT INTO evidence (company_id, data) VALUES (?, ?)",
                    (company_id, json.dumps(_evidence_to_dict(item))),
                )

    def get_companies(self, status: LeadStatus | None = None) -> list[Company]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM companies WHERE status = ? ORDER BY created_at",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM companies ORDER BY created_at"
                ).fetchall()
        return [_row_to_company(row) for row in rows]

    def get_score(self, company_id: str) -> SponsorScore | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM scores WHERE company_id = ?", (company_id,)
            ).fetchone()
        return _dict_to_score(json.loads(row["data"])) if row else None

    def get_scores(self) -> list[SponsorScore]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM scores").fetchall()
        return [_dict_to_score(json.loads(row["data"])) for row in rows]

    def get_report(self, company_id: str) -> SponsorReport | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM reports WHERE company_id = ?", (company_id,)
            ).fetchone()
        return _dict_to_report(json.loads(row["data"])) if row else None

    def get_contacts(self, company_id: str) -> list[ContactPerson]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM contacts WHERE company_id = ? ORDER BY json_extract(data, '$.relevance_score') DESC",
                (company_id,),
            ).fetchall()
        return [_dict_to_contact(json.loads(row["data"])) for row in rows]

    def get_outreach_ready(self) -> list[OutreachProspect]:
        prospects: list[OutreachProspect] = []
        for company in self.get_companies(LeadStatus.OUTREACH_READY):
            score = self.get_score(company.id)
            report = self.get_report(company.id)
            contacts = self.get_contacts(company.id)
            if score and report and contacts:
                primary = contacts[0]
                prospects.append(
                    OutreachProspect(
                        company=company,
                        report=report,
                        score=score,
                        primary_contact=primary,
                        contact_methods=primary.contact_methods,
                    )
                )
        return prospects


def _score_to_dict(score: SponsorScore) -> dict:
    return {
        "company_id": score.company.id,
        "company_name": score.company.name,
        "company_website": score.company.website,
        "company_industry": score.company.industry,
        "overall_score": score.overall_score,
        "confidence": score.confidence,
        "explanation": score.explanation,
        "key_strengths": score.key_strengths,
        "potential_weaknesses": score.potential_weaknesses,
        "recommended_outreach_angle": score.recommended_outreach_angle,
        "recommended_contact_role": score.recommended_contact_role,
        "motivations": [m.value for m in score.motivations],
        "criterion_scores": {
            k: {
                "score": v.score,
                "reasoning": v.reasoning,
                "supporting_evidence": v.supporting_evidence,
            }
            for k, v in score.criterion_scores.items()
        },
        "scored_at": score.scored_at.isoformat(),
    }


def _dict_to_score(data: dict) -> SponsorScore:
    from datetime import datetime

    from sponsor_pipeline.models import Company, CriterionScore

    company = Company(
        id=data["company_id"],
        name=data.get("company_name", ""),
        website=data.get("company_website", ""),
        industry=data.get("company_industry", ""),
    )
    criterion_scores = {
        k: CriterionScore(
            criterion_key=k,
            score=float(v["score"]),
            reasoning=str(v.get("reasoning", "")),
            supporting_evidence=list(v.get("supporting_evidence", [])),
        )
        for k, v in data.get("criterion_scores", {}).items()
    }

    return SponsorScore(
        company=company,
        criterion_scores=criterion_scores,
        overall_score=float(data.get("overall_score", 0.0)),
        confidence=str(data.get("confidence", "medium")),
        explanation=str(data.get("explanation", "")),
        key_strengths=list(data.get("key_strengths", [])),
        potential_weaknesses=list(data.get("potential_weaknesses", [])),
        recommended_outreach_angle=str(data.get("recommended_outreach_angle", "")),
        recommended_contact_role=str(data.get("recommended_contact_role", "")),
        motivations=[SponsorMotivation(v) for v in data.get("motivations", [])],
        scored_at=datetime.fromisoformat(data["scored_at"]),
    )


def _report_to_dict(report: SponsorReport) -> dict:
    return {
        "company_id": report.company_id,
        "priority": report.priority.value,
        "description": report.description,
        "products_and_services": report.products_and_services,
        "recent_launches": report.recent_launches,
        "past_sponsorship_evidence": report.past_sponsorship_evidence,
        "hires_interns_new_grads": report.hires_interns_new_grads,
        "hires_in_canada": report.hires_in_canada,
        "waterloo_alumni_present": report.waterloo_alumni_present,
        "has_devrel_or_recruiting_staff": report.has_devrel_or_recruiting_staff,
        "best_sponsor_angle": report.best_sponsor_angle,
        "suggested_tier": report.suggested_tier.value,
        "generated_at": report.generated_at.isoformat(),
    }


def _dict_to_report(data: dict) -> SponsorReport:
    from datetime import datetime

    return SponsorReport(
        company_id=data["company_id"],
        priority=Priority(data["priority"]),
        description=data.get("description", ""),
        products_and_services=data.get("products_and_services", ""),
        recent_launches=data.get("recent_launches", []),
        past_sponsorship_evidence=data.get("past_sponsorship_evidence", ""),
        hires_interns_new_grads=bool(data.get("hires_interns_new_grads")),
        hires_in_canada=bool(data.get("hires_in_canada")),
        waterloo_alumni_present=bool(data.get("waterloo_alumni_present")),
        has_devrel_or_recruiting_staff=bool(data.get("has_devrel_or_recruiting_staff")),
        best_sponsor_angle=data.get("best_sponsor_angle", ""),
        suggested_tier=SponsorTier(data.get("suggested_tier", "silver")),
        generated_at=datetime.fromisoformat(data["generated_at"]),
    )


def _contact_to_dict(contact: ContactPerson) -> dict:
    return {
        "id": contact.id,
        "company_id": contact.company_id,
        "full_name": contact.full_name,
        "title": contact.title,
        "role_category": contact.role_category.value,
        "relevance_score": contact.relevance_score,
        "selection_rationale": contact.selection_rationale,
        "contact_methods": [
            {
                "type": m.type.value,
                "value": m.value,
                "source_url": m.source_url,
                "confidence": m.confidence,
                "is_public": m.is_public,
            }
            for m in contact.contact_methods
        ],
    }


def _dict_to_contact(data: dict) -> ContactPerson:
    methods = [
        ContactMethod(
            type=ContactMethodType(m["type"]),
            value=m["value"],
            source_url=m["source_url"],
            confidence=m.get("confidence", 0.5),
            is_public=m.get("is_public", True),
        )
        for m in data.get("contact_methods", [])
    ]
    return ContactPerson(
        id=data["id"],
        company_id=data["company_id"],
        full_name=data["full_name"],
        title=data.get("title", ""),
        role_category=ContactRole(data.get("role_category", "other")),
        relevance_score=data.get("relevance_score", 0.0),
        selection_rationale=data.get("selection_rationale", ""),
        contact_methods=methods,
    )


def _evidence_to_dict(item: Evidence) -> dict:
    return {
        "category": item.category.value,
        "description": item.description,
        "source_url": item.source_url,
        "extracted_at": item.extracted_at.isoformat(),
    }


def _row_to_company(row: sqlite3.Row) -> Company:
    from datetime import datetime

    return Company(
        id=row["id"],
        name=row["name"],
        website=row["website"] or "",
        industry=row["industry"] or "",
        company_size=CompanySize(row["company_size"] or "unknown"),
        discovery_sources=[
            DiscoverySource(v) for v in json.loads(row["discovery_sources"] or "[]")
        ],
        status=LeadStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
