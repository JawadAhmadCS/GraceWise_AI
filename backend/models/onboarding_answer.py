from datetime import datetime
from models import db


class OnboardingAnswer(db.Model):
    __tablename__ = "onboarding_answer"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("onboarding_session.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    question_id = db.Column(db.String(120), nullable=False, index=True)
    section_key = db.Column(db.String(80), nullable=False)
    field_key = db.Column(db.String(120), nullable=False)

    answer_text = db.Column(db.Text, nullable=True)
    normalized_value = db.Column(db.JSON, nullable=True)

    answer_source = db.Column(db.String(20), default="text", nullable=False)  # text | voice
    is_valid = db.Column(db.Boolean, default=True, nullable=False)
    needs_follow_up = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "question_id", name="uq_onboarding_answer_user_question"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "question_id": self.question_id,
            "section_key": self.section_key,
            "field_key": self.field_key,
            "answer_text": self.answer_text,
            "normalized_value": self.normalized_value,
            "answer_source": self.answer_source,
            "is_valid": self.is_valid,
            "needs_follow_up": self.needs_follow_up,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
