from datetime import datetime
from models import db


class OnboardingSession(db.Model):
    __tablename__ = "onboarding_session"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    status = db.Column(db.String(20), default="active", nullable=False)  # active | completed | paused
    question_bank_version = db.Column(db.String(40), nullable=True)

    current_question_id = db.Column(db.String(120), nullable=True)
    last_question_id = db.Column(db.String(120), nullable=True)

    total_required = db.Column(db.Integer, default=0, nullable=False)
    completed_required = db.Column(db.Integer, default=0, nullable=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "question_bank_version": self.question_bank_version,
            "current_question_id": self.current_question_id,
            "last_question_id": self.last_question_id,
            "total_required": self.total_required,
            "completed_required": self.completed_required,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
