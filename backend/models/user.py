from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from utils.access_control import get_effective_tier, has_active_subscription, tier_level
from utils.admin_roles import is_superadmin


class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, nullable=True)
    subscription_tier = db.Column(db.String(20), default="free", nullable=False)
    subscription_status = db.Column(db.String(30), default="inactive", nullable=False)
    stripe_customer_id = db.Column(db.String(120), nullable=True, unique=True)
    stripe_subscription_id = db.Column(db.String(120), nullable=True, unique=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    onboarding_completed = db.Column(db.Boolean, default=False, nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def effective_tier(self):
        return get_effective_tier(self)

    @property
    def subscription_active(self):
        return has_active_subscription(self)

    def has_tier(self, tier_name):
        return tier_level(self.effective_tier) >= tier_level(tier_name)
    
    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'is_superadmin': is_superadmin(self),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'effective_tier': self.effective_tier,
            'subscription_active': self.subscription_active,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'onboarding_completed': bool(self.onboarding_completed),
        }
