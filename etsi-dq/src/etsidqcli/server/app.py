"""FastAPI server."""
from __future__ import annotations
from typing import Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from etsidqcli.server import db
from etsidqcli.core import MetricRegistry
import etsidqcli.metrics  # noqa

class CreateUserReq(BaseModel):
    name: str
    org: str = ""

class MetricScoreIn(BaseModel):
    score: float
    grade: str
    passed: bool

class SubmitReq(BaseModel):
    api_key: str
    dataset_name: str = "unknown"
    dataset_hash: str = ""
    overall_score: float
    overall_grade: str
    metrics: dict[str, MetricScoreIn]
    profile: dict[str, Any] = {}

def create_app():
    app = FastAPI(title="ETSI Data Quality Server", version="0.2.0")

    @app.get("/health")
    def health(): return {"status": "ok"}

    @app.get("/api/metrics")
    def list_metrics(): return {"metrics": MetricRegistry.list_all()}

    @app.post("/api/users")
    def create_user(body: CreateUserReq):
        u = db.create_user(body.name, body.org)
        return {"user_id": u["user_id"], "api_key": u["api_key"], "message": f"Run: etsi-dq auth set-key {u['api_key']}"}

    @app.post("/api/reports/submit")
    def submit(body: SubmitReq):
        user = db.get_user_by_key(body.api_key)
        if not user: raise HTTPException(401, "Invalid API key")
        report = db.create_report(user["id"], body.dataset_name, body.dataset_hash, body.overall_score, body.overall_grade, {k: v.model_dump() for k, v in body.metrics.items()}, body.profile)
        cert = db.issue_certificate(report["report_id"], user["id"])
        return {"status": "submitted", "report_id": report["report_id"], "certificate_key": cert["certificate_key"], "issued_at": cert["issued_at"], "verify_url": f"/api/certificates/{cert['certificate_key']}/verify"}

    @app.get("/api/reports")
    def get_reports(api_key: str = Query(...)):
        user = db.get_user_by_key(api_key)
        if not user: raise HTTPException(401, "Invalid API key")
        reports = db.get_reports_by_user(user["id"])
        return {"user": user["name"], "total": len(reports), "reports": [{"report_id": r["id"], "dataset_name": r["dataset_name"], "overall_score": r["overall_score"], "overall_grade": r["overall_grade"], "created_at": r["created_at"]} for r in reports]}

    @app.get("/api/certificates/{cert_key}/verify")
    def verify(cert_key: str):
        r = db.verify_certificate(cert_key)
        if not r: raise HTTPException(404, "Certificate not found")
        return {"valid": r["status"] == "valid", "certificate_key": cert_key, "evaluated_by": r["user_name"], "organization": r["org"], "dataset": r["dataset_name"], "overall_score": r["overall_score"], "overall_grade": r["overall_grade"], "evaluated_at": r["evaluated_at"], "issued_at": r["issued_at"]}

    @app.get("/api/certificates/{cert_key}/pdf")
    def download_pdf(cert_key: str):
        r = db.verify_certificate(cert_key)
        if not r: raise HTTPException(404, "Certificate not found")
        import json
        from etsidqcli.report.pdf_certificate import generate_certificate
        metrics = json.loads(r["metrics_json"]) if isinstance(r["metrics_json"], str) else r["metrics_json"]
        path = generate_certificate(certificate_key=cert_key, user_name=r["user_name"], organization=r["org"], dataset_name=r["dataset_name"], overall_score=r["overall_score"], overall_grade=r["overall_grade"], metrics=metrics, evaluated_at=r["evaluated_at"], issued_at=r["issued_at"], verify_url=f"/api/certificates/{cert_key}/verify")
        return FileResponse(path, media_type="application/pdf", filename=f"certificate_{cert_key}.pdf")

    return app
