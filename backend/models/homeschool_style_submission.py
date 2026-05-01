from datetime import datetime
from models import db


class HomeschoolStyleSubmission(db.Model):
    __tablename__ = "homeschool_style_submission"

    id = db.Column(db.Integer, primary_key=True)
    submission_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True, index=True)

    answers = db.Column(db.JSON, nullable=False)
    score_breakdown = db.Column(db.JSON, nullable=False)

    result_key = db.Column(db.String(50), nullable=False)
    result_title = db.Column(db.String(200), nullable=False)
    result_summary = db.Column(db.Text, nullable=False)

    lead_captured_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    systeme_sync_status = db.Column(db.String(30), default="pending", nullable=False)
    systeme_sync_response = db.Column(db.Text, nullable=True)

    utm_source = db.Column(db.String(120), nullable=True)
    utm_medium = db.Column(db.String(120), nullable=True)
    utm_campaign = db.Column(db.String(120), nullable=True)

    def to_result_dict(self):
        return {
            "result_key": self.result_key,
            "result_title": self.result_title,
            "result_summary": self.result_summary,
            "score_breakdown": self.score_breakdown,
            "completed_at": self.lead_captured_at.isoformat() if self.lead_captured_at else None,
        }
