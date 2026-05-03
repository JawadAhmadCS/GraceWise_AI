from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Child, DevotionalProgress, Planner, Quiz, QuizResult, Notification, AiSession, AiChatMessage, HomeschoolStyleSubmission
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from utils.access_control import get_effective_tier, get_tool_access, tier_required

dashboard_bp = Blueprint("dashboard", __name__)

def get_user_id():
    """Get user_id from JWT token and convert to int"""
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    return user_id


@dashboard_bp.route("/student/tool-access", methods=["GET"])
@jwt_required()
def student_tool_access():
    """Expose tier-based dashboard tool permissions for frontend rendering."""
    user = User.query.get(get_user_id())
    if not user:
        return jsonify({"message": "User not found"}), 404

    return jsonify(
        {
            "effective_tier": get_effective_tier(user),
            "subscription_tier": user.subscription_tier,
            "subscription_status": user.subscription_status,
            "onboarding_completed": bool(user.onboarding_completed),
            "tool_access": get_tool_access(user),
        }
    ), 200

# add routes related to dashboard summaries here
@dashboard_bp.route("/summary", methods=["GET"])
@jwt_required()
def dashboard_summary():
    """Get dashboard statistics for admin"""
    # Get current admin's details
    user_id = get_user_id()
    current_user = User.query.get(user_id)

    if not current_user or not current_user.is_admin:
        return jsonify({"message": "Admin access required"}), 403

    admin_name = current_user.first_name if current_user else "Admin"
    
    total_users = User.query.count()
    
    # Get active users (logged in within last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = User.query.filter(
        User.is_active == True,
        User.last_login != None,
        User.last_login >= thirty_days_ago
    ).count()
    
    # Sleeping users = registered & active but haven't logged in within 30 days
    sleeping_users = total_users - active_users
    
    # Additional stats
    total_children = Child.query.count()
    completed_devotionals = DevotionalProgress.query.count()
    active_planners = Planner.query.count()
    
    # Calculate real growth percentages by comparing with previous month
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    
    # Users created this month vs last month
    users_this_month = User.query.filter(User.created_at >= thirty_days_ago).count()
    users_last_month = User.query.filter(
        User.created_at >= sixty_days_ago,
        User.created_at < thirty_days_ago
    ).count()
    total_users_growth = round(((users_this_month - users_last_month) / max(users_last_month, 1)) * 100)
    
    # Active users this month vs last month
    active_last_month = User.query.filter(
        User.is_active == True,
        User.last_login != None,
        User.last_login >= sixty_days_ago,
        User.last_login < thirty_days_ago
    ).count()
    active_users_growth = round(((active_users - active_last_month) / max(active_last_month, 1)) * 100)

    return jsonify({
        "admin_name": admin_name,
        "total_users": total_users,
        "total_users_growth": total_users_growth,
        "active_users": active_users,
        "active_users_growth": active_users_growth,
        "sleeping_users": sleeping_users,
        "completed_devotionals": completed_devotionals,
        "active_planners": active_planners
    })


# ==================== STUDENT DASHBOARD ====================
@dashboard_bp.route("/student/stats", methods=["GET"])
@tier_required("plan")
def student_dashboard_stats():
    """Get student dashboard statistics"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Total Quiz Attempts (regular quizzes + homeschool style quiz by matched email)
        regular_quiz_attempts = QuizResult.query.filter_by(user_id=user_id).count()
        homeschool_attempts = 0
        if user.email:
            homeschool_attempts = (
                HomeschoolStyleSubmission.query
                .filter(
                    func.lower(HomeschoolStyleSubmission.email) == user.email.lower(),
                    HomeschoolStyleSubmission.lead_captured_at.isnot(None),
                )
                .count()
            )
        total_quiz_attempts = regular_quiz_attempts + homeschool_attempts
        
        # Average Score from Quizzes
        quiz_results = QuizResult.query.filter_by(user_id=user_id).all()
        average_score = 0
        if quiz_results:
            total_score = sum(result.score for result in quiz_results)
            average_score = round(total_score / len(quiz_results), 2)
        
        # Total Hours Spent (estimated: 0.5 hours per quiz + 1 hour per AI chat session)
        # Assuming average quiz duration is 30 min and AI chat average is 1 hour
        quiz_hours = total_quiz_attempts * 0.5
        ai_chat_hours = 0  # This would come from a chat session tracking if available
        total_hours_spent = round(quiz_hours + ai_chat_hours, 2)
        
        # Ranking among all students
        # Calculate average score for each user and rank them
        user_scores = db.session.query(
            QuizResult.user_id,
            func.avg(QuizResult.score).label('avg_score')
        ).group_by(QuizResult.user_id).all()
        
        user_rankings = sorted(user_scores, key=lambda x: x[1], reverse=True)
        ranking = 1
        for idx, (uid, score) in enumerate(user_rankings):
            if uid == user_id:
                ranking = idx + 1
                break
        
        total_students_ranked = len(user_rankings)
        
        return jsonify({
            "total_quiz_attempts": total_quiz_attempts,
            "average_score": average_score,
            "total_hours_spent": total_hours_spent,
            "ranking": ranking,
            "total_students_ranked": total_students_ranked
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Error fetching student stats: {str(e)}"}), 500


@dashboard_bp.route("/student/notifications", methods=["GET"])
@tier_required("plan")
def student_notifications():
    """Get notifications for current student"""
    try:
        user_id = get_user_id()
        
        # Get latest 10 notifications
        notifications = Notification.query.filter_by(user_id=user_id).order_by(
            Notification.created_at.desc()
        ).limit(10).all()
        
        return jsonify({
            "notifications": [notif.to_dict() for notif in notifications],
            "unread_count": Notification.query.filter_by(user_id=user_id, is_read=False).count()
        }), 200
        
    except Exception as e:
        return jsonify({"message": f"Error fetching notifications: {str(e)}"}), 500


@dashboard_bp.route("/student/notifications/<int:notification_id>/mark-read", methods=["PUT"])
@tier_required("plan")
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        user_id = get_user_id()
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        
        if not notification:
            return jsonify({"message": "Notification not found"}), 404
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({"message": "Notification marked as read"}), 200
        
    except Exception as e:
        return jsonify({"message": f"Error marking notification: {str(e)}"}), 500


@dashboard_bp.route("/student/notifications/mark-all-read", methods=["PUT"])
@tier_required("plan")
def mark_all_notifications_read():
    """Mark all notifications as read for the current user"""
    try:
        user_id = get_user_id()
        
        # Update all unread notifications for this user
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
        
        return jsonify({"message": "All notifications marked as read"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error marking all notifications: {str(e)}"}), 500


# ==================== STUDENT PROGRESS ====================
@dashboard_bp.route("/student/progress", methods=["GET"])
@tier_required("plan")
def student_progress_summary():
    """Get dynamic progress data for the student progress page"""
    try:
        user_id = get_user_id()
        user = User.query.get(user_id)

        if not user:
            return jsonify({"message": "User not found"}), 404

        regular_quiz_attempts = QuizResult.query.filter_by(user_id=user_id).count()
        homeschool_submissions = []
        if user.email:
            homeschool_submissions = (
                HomeschoolStyleSubmission.query
                .filter(
                    func.lower(HomeschoolStyleSubmission.email) == user.email.lower(),
                    HomeschoolStyleSubmission.lead_captured_at.isnot(None),
                )
                .order_by(HomeschoolStyleSubmission.lead_captured_at.desc(), HomeschoolStyleSubmission.created_at.desc())
                .all()
            )
        homeschool_attempts = len(homeschool_submissions)
        quiz_attempts = regular_quiz_attempts + homeschool_attempts
        quiz_results = QuizResult.query.filter_by(user_id=user_id).order_by(QuizResult.completed_at.desc()).all()

        average_score = 0
        best_score = 0
        if quiz_results:
            total_score = sum(result.score for result in quiz_results)
            average_score = round(total_score / len(quiz_results), 2)
            best_score = round(max(result.score for result in quiz_results), 2)

        ai_sessions = AiSession.query.filter_by(user_id=user_id).all()
        ai_minutes = sum(session.duration_minutes for session in ai_sessions)
        ai_hours = round(ai_minutes / 60, 2) if ai_minutes else 0

        quiz_hours = quiz_attempts * 0.5
        total_study_hours = round(quiz_hours + ai_hours, 2)

        subject_performance = db.session.query(
            Quiz.title.label('subject'),
            func.avg(QuizResult.score).label('avg_score')
        ).join(Quiz, Quiz.id == QuizResult.quiz_id).filter(
            QuizResult.user_id == user_id
        ).group_by(Quiz.title).order_by(func.avg(QuizResult.score).desc()).limit(6).all()

        subject_data = [
            {
                "subject": subject,
                "average_score": round(avg_score, 2) if avg_score is not None else 0
            }
            for subject, avg_score in subject_performance
        ]

        recent_quiz_activities = db.session.query(
            Quiz.title,
            QuizResult.score,
            QuizResult.completed_at
        ).join(Quiz, Quiz.id == QuizResult.quiz_id).filter(
            QuizResult.user_id == user_id
        ).order_by(QuizResult.completed_at.desc()).limit(6).all()

        activity_data = [
            {
                "title": title,
                "score": round(score, 2) if score is not None else 0,
                "completed_at": completed_at.isoformat() if completed_at else None
            }
            for title, score, completed_at in recent_quiz_activities
        ]

        homeschool_activity_data = []
        for submission in homeschool_submissions[:6]:
            breakdown = submission.score_breakdown or {}
            total_points = sum((breakdown or {}).values())
            top_points = max((breakdown or {}).values()) if breakdown else 0
            score_percent = round((top_points / total_points) * 100, 2) if total_points > 0 else 0
            homeschool_activity_data.append({
                "title": "Homeschool Style Quiz",
                "score": score_percent,
                "completed_at": (
                    submission.lead_captured_at.isoformat()
                    if submission.lead_captured_at
                    else (submission.created_at.isoformat() if submission.created_at else None)
                ),
            })

        activity_data = sorted(
            activity_data + homeschool_activity_data,
            key=lambda item: item.get("completed_at") or "",
            reverse=True,
        )[:6]

        return jsonify({
            "quiz_attempts": quiz_attempts,
            "average_score": average_score,
            "best_score": best_score,
            "study_hours": total_study_hours,
            "ai_session_count": len(ai_sessions),
            "subject_performance": subject_data,
            "recent_activities": activity_data
        }), 200

    except Exception as e:
        return jsonify({"message": f"Error fetching progress: {str(e)}"}), 500


# ==================== AI SESSION TRACKING ====================
@dashboard_bp.route("/student/ai-sessions", methods=["GET"])
@tier_required("plan")
def list_ai_sessions():
    """List user's AI sessions with a preview for chat history panel"""
    try:
        user_id = get_user_id()
        limit = request.args.get("limit", 40, type=int)
        limit = max(1, min(limit, 100))

        sessions = (
            AiSession.query
            .filter_by(user_id=user_id)
            .order_by(AiSession.updated_at.desc(), AiSession.started_at.desc())
            .limit(limit)
            .all()
        )

        session_items = []
        for session in sessions:
            messages = (
                AiChatMessage.query
                .filter_by(session_id=session.id, user_id=user_id)
                .order_by(AiChatMessage.turn_index.asc(), AiChatMessage.id.asc())
                .all()
            )

            first_user_msg = next((m.content for m in messages if m.role == "user"), "")
            last_msg = messages[-1].content if messages else ""

            title = (session.title or "").strip()
            if not title:
                base = first_user_msg or (
                    f"Lesson: {session.lesson_name}" if session.chat_type == "lesson" and session.lesson_name else "New chat"
                )
                title = (base[:60] + "...") if len(base) > 60 else base

            session_items.append({
                "id": session.id,
                "chat_type": session.chat_type,
                "title": title,
                "lesson_id": session.lesson_id,
                "lesson_name": session.lesson_name,
                "lesson_desc": session.lesson_desc,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "duration_minutes": session.duration_minutes,
                "messages_count": len(messages),
                "last_message_preview": (last_msg[:80] + "...") if len(last_msg) > 80 else last_msg
            })

        return jsonify({"sessions": session_items}), 200
    except Exception as e:
        return jsonify({"message": f"Error listing sessions: {str(e)}"}), 500


@dashboard_bp.route("/student/ai-sessions/<int:session_id>/messages", methods=["GET"])
@tier_required("plan")
def get_ai_session_messages(session_id):
    """Get all chat messages for one AI session"""
    try:
        user_id = get_user_id()
        session = AiSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            return jsonify({"message": "Session not found"}), 404

        messages = (
            AiChatMessage.query
            .filter_by(session_id=session_id, user_id=user_id)
            .order_by(AiChatMessage.turn_index.asc(), AiChatMessage.id.asc())
            .all()
        )

        return jsonify({
            "session": session.to_dict(),
            "messages": [m.to_dict() for m in messages]
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error loading session messages: {str(e)}"}), 500


@dashboard_bp.route("/student/ai-sessions/<int:session_id>", methods=["PUT"])
@tier_required("plan")
def rename_ai_session(session_id):
    """Rename one AI session (chat title)"""
    try:
        user_id = get_user_id()
        session = AiSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            return jsonify({"message": "Session not found"}), 404

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"message": "Title is required"}), 400
        if len(title) > 255:
            return jsonify({"message": "Title is too long (max 255 chars)"}), 400

        session.title = title
        session.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({"message": "Session renamed", "session": session.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error renaming session: {str(e)}"}), 500


@dashboard_bp.route("/student/ai-sessions/<int:session_id>", methods=["DELETE"])
@tier_required("plan")
def delete_ai_session(session_id):
    """Delete one AI session and all associated messages"""
    try:
        user_id = get_user_id()
        session = AiSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            return jsonify({"message": "Session not found"}), 404

        AiChatMessage.query.filter_by(session_id=session_id, user_id=user_id).delete(synchronize_session=False)
        db.session.delete(session)
        db.session.commit()

        return jsonify({"message": "Session deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error deleting session: {str(e)}"}), 500


@dashboard_bp.route("/student/ai-sessions/start", methods=["POST"])
@tier_required("plan")
def start_ai_session():
    """Start a new AI assistant session"""
    try:
        user_id = get_user_id()
        data = request.get_json(silent=True) or {}
        chat_type = (data.get("chat_type") or "general").strip().lower()
        if chat_type not in ("general", "lesson"):
            chat_type = "general"

        raw_lesson_id = data.get("lesson_id")
        lesson_id = None
        if raw_lesson_id not in (None, ""):
            try:
                lesson_id = int(raw_lesson_id)
            except (TypeError, ValueError):
                lesson_id = None
        lesson_name = (data.get("lesson_name") or "").strip() or None
        lesson_desc = (data.get("lesson_desc") or "").strip() or None
        title = (data.get("title") or "").strip() or None

        if chat_type == "lesson" and not title and lesson_name:
            title = f"Lesson: {lesson_name}"

        session = AiSession(
            user_id=user_id,
            chat_type=chat_type,
            title=title,
            lesson_id=lesson_id,
            lesson_name=lesson_name,
            lesson_desc=lesson_desc
        )
        db.session.add(session)
        db.session.commit()
        return jsonify({
            "session_id": session.id,
            "started_at": session.started_at.isoformat(),
            "session": session.to_dict()
        }), 201
    except Exception as e:
        return jsonify({"message": f"Error starting AI session: {str(e)}"}), 500


@dashboard_bp.route("/student/ai-sessions/<int:session_id>/end", methods=["POST"])
@tier_required("plan")
def end_ai_session(session_id):
    """End an AI assistant session and compute duration"""
    try:
        user_id = get_user_id()
        session = AiSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            return jsonify({"message": "Session not found"}), 404

        session.ended_at = datetime.utcnow()
        duration = session.ended_at - session.started_at
        session.duration_minutes = max(int(duration.total_seconds() / 60), 1)
        db.session.commit()

        return jsonify({
            "session_id": session.id,
            "duration_minutes": session.duration_minutes,
            "ended_at": session.ended_at.isoformat()
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error ending AI session: {str(e)}"}), 500
