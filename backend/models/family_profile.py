from datetime import datetime
from models import db


class FamilyProfile(db.Model):
    __tablename__ = "family_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)

    family_profile = db.Column(db.JSON, nullable=False, default=dict)
    child_profiles = db.Column(db.JSON, nullable=False, default=dict)
    education_homeschool_plan = db.Column(db.JSON, nullable=False, default=dict)
    special_needs_learning_support = db.Column(db.JSON, nullable=False, default=dict)
    schedule_meal_planning = db.Column(db.JSON, nullable=False, default=dict)
    goals_preferences = db.Column(db.JSON, nullable=False, default=dict)

    onboarding_progress = db.Column(db.JSON, nullable=False, default=dict)
    profile_version = db.Column(db.String(40), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "family_profile": self.family_profile or {},
            "child_profiles": self.child_profiles or {},
            "education_homeschool_plan": self.education_homeschool_plan or {},
            "special_needs_learning_support": self.special_needs_learning_support or {},
            "schedule_meal_planning": self.schedule_meal_planning or {},
            "goals_preferences": self.goals_preferences or {},
            "onboarding_progress": self.onboarding_progress or {},
            "profile_version": self.profile_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
