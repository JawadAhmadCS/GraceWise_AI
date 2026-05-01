from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models
from models.user import User
from models.child import Child
from models.devotional import Devotional
from models.devotional_progress import DevotionalProgress
from models.planner import Planner
from models.curriculum import Curriculum
from models.module import Module
from models.lesson import Lesson
from models.quiz import Quiz
from models.quiz_result import QuizResult
from models.notification import Notification
from models.ai_session import AiSession
from models.ai_chat_message import AiChatMessage
from models.app_setting import AppSetting
from models.onboarding_profile import OnboardingProfile
from models.password_reset_token import PasswordResetToken
from models.homeschool_style_submission import HomeschoolStyleSubmission
from models.family_profile import FamilyProfile
from models.onboarding_session import OnboardingSession
from models.onboarding_answer import OnboardingAnswer

__all__ = ['db', 'User', 'Child', 'Devotional', 'DevotionalProgress', 'Planner', 'Curriculum', 'Module', 'Lesson', 'Quiz', 'QuizResult', 'Notification', 'AiSession', 'AiChatMessage', 'AppSetting', 'OnboardingProfile', 'PasswordResetToken', 'HomeschoolStyleSubmission', 'FamilyProfile', 'OnboardingSession', 'OnboardingAnswer']
