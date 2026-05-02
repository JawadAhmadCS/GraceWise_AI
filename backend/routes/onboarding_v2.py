from datetime import datetime
import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, User, FamilyProfile, OnboardingSession, OnboardingAnswer
from utils.access_control import get_effective_tier
from utils.admin_roles import is_superadmin
from services.onboarding_v2_service import (
    SECTION_KEYS,
    apply_answer_to_profile,
    build_question_prompt,
    calculate_progress,
    extract_answer_with_ai,
    get_applicable_questions,
    get_next_question,
    index_answers_by_field,
    list_questions,
    load_question_bank,
    save_question_bank,
    get_question_bank_path,
)


onboarding_v2_bp = Blueprint("onboarding_v2", __name__)


def _get_user():
    user_id = get_jwt_identity()
    if isinstance(user_id, str):
        user_id = int(user_id)
    return User.query.get(user_id)


def _require_paid_tier(user):
    tier = get_effective_tier(user)
    if tier == "free":
        return False, jsonify({"message": "Active subscription required before onboarding"}), 403
    return True, tier, None


def _require_superadmin(user):
    if not user or not user.is_admin:
        return False, jsonify({"message": "Admin access required"}), 403
    if not is_superadmin(user):
        return False, jsonify({"message": "Superadmin access required"}), 403
    return True, None, None


def _get_or_create_profile(user_id):
    profile = FamilyProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = FamilyProfile(user_id=user_id)
        db.session.add(profile)
        db.session.flush()
    return profile


def _get_or_create_session(user_id, question_bank_version):
    session = (
        OnboardingSession.query
        .filter_by(user_id=user_id, status="active")
        .order_by(OnboardingSession.id.desc())
        .first()
    )
    if not session:
        session = OnboardingSession(
            user_id=user_id,
            status="active",
            question_bank_version=question_bank_version,
        )
        db.session.add(session)
        db.session.flush()
    return session


def _question_map(question_bank):
    return {q["id"]: q for q in list_questions(question_bank)}


def _fetch_answers(user_id):
    return OnboardingAnswer.query.filter_by(user_id=user_id).all()


def _sync_session_progress(session, question_bank, answer_map):
    progress = calculate_progress(question_bank, answer_map)
    next_question = get_next_question(question_bank, answer_map)

    session.total_required = progress["required_total"]
    session.completed_required = progress["required_completed"]
    session.current_question_id = next_question["id"] if next_question else None

    if progress["is_complete"] and session.status != "completed":
        session.status = "completed"
        session.completed_at = datetime.utcnow()

    return progress, next_question


def _serialize_progress_with_sections(question_bank, answer_map):
    overall = calculate_progress(question_bank, answer_map)
    section_stats = {}

    for section_key in SECTION_KEYS:
        section_questions = [q for q in get_applicable_questions(question_bank, answer_map) if q["section"] == section_key]
        required = [q for q in section_questions if q.get("required")]
        completed = 0
        for q in required:
            value = answer_map.get(q["field"])
            if value not in (None, "", []):
                completed += 1

        percent = int((completed / len(required)) * 100) if required else 100
        section_stats[section_key] = {
            "required_total": len(required),
            "required_completed": completed,
            "percent": percent,
            "is_complete": completed >= len(required),
        }

    return {
        "overall": overall,
        "sections": section_stats,
    }


def _upsert_answer(user_id, session_id, question, raw_message, normalized_value, answer_source="text", is_valid=True, needs_follow_up=False):
    answer = OnboardingAnswer.query.filter_by(user_id=user_id, question_id=question["id"]).first()
    if not answer:
        answer = OnboardingAnswer(
            user_id=user_id,
            session_id=session_id,
            question_id=question["id"],
            section_key=question["section"],
            field_key=question["field"],
        )
        db.session.add(answer)

    answer.session_id = session_id
    answer.answer_text = raw_message
    answer.normalized_value = normalized_value
    answer.answer_source = answer_source
    answer.is_valid = is_valid
    answer.needs_follow_up = needs_follow_up

    return answer


@onboarding_v2_bp.route("/question-bank", methods=["GET"])
@jwt_required()
def get_question_bank():
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    try:
        question_bank = load_question_bank()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    return jsonify({
        "version": question_bank.get("version"),
        "sections": question_bank.get("sections", []),
        "questions": question_bank.get("questions", []),
    }), 200


@onboarding_v2_bp.route("/admin/question-bank", methods=["GET"])
@jwt_required()
def admin_get_question_bank():
    user = _get_user()
    allowed, error_response, status_code = _require_superadmin(user)
    if not allowed:
        return error_response, status_code

    try:
        question_bank = load_question_bank()
        path = get_question_bank_path()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    return jsonify({
        "path": str(path),
        "question_bank": question_bank,
    }), 200


@onboarding_v2_bp.route("/admin/question-bank", methods=["PUT"])
@jwt_required()
def admin_update_question_bank():
    user = _get_user()
    allowed, error_response, status_code = _require_superadmin(user)
    if not allowed:
        return error_response, status_code

    payload = request.get_json(silent=True) or {}
    question_bank = payload.get("question_bank")
    if not isinstance(question_bank, dict):
        return jsonify({"message": "question_bank object is required"}), 400

    try:
        result = save_question_bank(question_bank, updated_by=user.email)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"message": f"Failed to save question bank: {exc}"}), 500

    return jsonify({
        "message": "Onboarding question bank saved successfully",
        "result": result,
    }), 200


@onboarding_v2_bp.route("/session/start", methods=["POST"])
@jwt_required()
def start_session():
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    allowed, tier_or_response, maybe_status = _require_paid_tier(user)
    if not allowed:
        return tier_or_response, maybe_status
    tier = tier_or_response

    try:
        question_bank = load_question_bank()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    profile = _get_or_create_profile(user.id)
    answers = _fetch_answers(user.id)
    answer_map = index_answers_by_field(answers)

    session = _get_or_create_session(user.id, question_bank.get("version"))
    progress, next_question = _sync_session_progress(session, question_bank, answer_map)

    profile.profile_version = question_bank.get("version")
    profile.onboarding_progress = _serialize_progress_with_sections(question_bank, answer_map)

    if progress["is_complete"]:
        user.onboarding_completed = True

    db.session.commit()

    return jsonify({
        "tier": tier,
        "session": session.to_dict(),
        "progress": profile.onboarding_progress,
        "assistant_message": build_question_prompt(next_question) if next_question else "Great work. Your onboarding is complete.",
        "current_question": next_question,
    }), 200


@onboarding_v2_bp.route("/session", methods=["GET"])
@jwt_required()
def get_current_session():
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    try:
        question_bank = load_question_bank()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    session = (
        OnboardingSession.query
        .filter_by(user_id=user.id)
        .order_by(OnboardingSession.id.desc())
        .first()
    )

    answers = _fetch_answers(user.id)
    answer_map = index_answers_by_field(answers)
    progress = _serialize_progress_with_sections(question_bank, answer_map)

    next_question = get_next_question(question_bank, answer_map)

    return jsonify({
        "session": session.to_dict() if session else None,
        "progress": progress,
        "current_question": next_question,
        "assistant_message": build_question_prompt(next_question) if next_question else "Great work. Your onboarding is complete.",
    }), 200


@onboarding_v2_bp.route("/session/message", methods=["POST"])
@jwt_required()
def submit_message():
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    allowed, tier_or_response, maybe_status = _require_paid_tier(user)
    if not allowed:
        return tier_or_response, maybe_status

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    answer_source = (data.get("answer_source") or "text").strip().lower()
    explicit_question_id = (data.get("question_id") or "").strip()

    if not user_message:
        return jsonify({"message": "message is required"}), 400

    try:
        question_bank = load_question_bank()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    profile = _get_or_create_profile(user.id)
    session = _get_or_create_session(user.id, question_bank.get("version"))

    answers = _fetch_answers(user.id)
    answer_map = index_answers_by_field(answers)
    question_by_id = _question_map(question_bank)

    current_question = None
    if explicit_question_id:
        current_question = question_by_id.get(explicit_question_id)
    if not current_question:
        current_question = get_next_question(question_bank, answer_map)

    if not current_question:
        user.onboarding_completed = True
        session.status = "completed"
        session.completed_at = session.completed_at or datetime.utcnow()
        db.session.commit()
        return jsonify({
            "message": "Onboarding already complete.",
            "session": session.to_dict(),
            "progress": profile.onboarding_progress or {},
        }), 200

    extraction = extract_answer_with_ai(current_question, user_message)
    normalized_value = extraction.get("normalized_value")
    needs_follow_up = bool(extraction.get("needs_follow_up"))

    _upsert_answer(
        user_id=user.id,
        session_id=session.id,
        question=current_question,
        raw_message=user_message,
        normalized_value=normalized_value,
        answer_source="voice" if answer_source == "voice" else "text",
        is_valid=not needs_follow_up,
        needs_follow_up=needs_follow_up,
    )

    if not needs_follow_up:
        apply_answer_to_profile(profile, current_question, normalized_value)

    db.session.flush()

    latest_answers = _fetch_answers(user.id)
    answer_map = index_answers_by_field(latest_answers)
    progress, next_question = _sync_session_progress(session, question_bank, answer_map)

    session.last_question_id = current_question["id"]

    profile.profile_version = question_bank.get("version")
    profile.onboarding_progress = _serialize_progress_with_sections(question_bank, answer_map)

    if progress["is_complete"]:
        user.onboarding_completed = True

    db.session.commit()

    if needs_follow_up:
        assistant_message = extraction.get("follow_up_prompt") or "Could you clarify that answer for me?"
        current_return_question = current_question
    else:
        assistant_message = build_question_prompt(next_question) if next_question else "Great work. Your onboarding is complete."
        current_return_question = next_question

    return jsonify({
        "saved": not needs_follow_up,
        "saved_question_id": current_question["id"],
        "normalized_value": normalized_value,
        "needs_follow_up": needs_follow_up,
        "assistant_message": assistant_message,
        "current_question": current_return_question,
        "session": session.to_dict(),
        "progress": profile.onboarding_progress,
    }), 200


@onboarding_v2_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    profile = _get_or_create_profile(user.id)

    try:
        question_bank = load_question_bank()
        answers = _fetch_answers(user.id)
        answer_map = index_answers_by_field(answers)
        profile.onboarding_progress = _serialize_progress_with_sections(question_bank, answer_map)
        profile.profile_version = question_bank.get("version")
        db.session.commit()
    except Exception:
        pass

    return jsonify({
        "profile": profile.to_dict(),
    }), 200


@onboarding_v2_bp.route("/profile/section/<string:section_key>", methods=["PATCH"])
@jwt_required()
def patch_profile_section(section_key):
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    if section_key not in SECTION_KEYS:
        return jsonify({"message": "Invalid section key"}), 400

    payload = request.get_json(silent=True) or {}
    section_data = payload.get("data")

    if section_data is None:
        return jsonify({"message": "data is required"}), 400

    profile = _get_or_create_profile(user.id)

    if not isinstance(section_data, dict):
        return jsonify({"message": "section data must be an object"}), 400

    setattr(profile, section_key, section_data)

    try:
        question_bank = load_question_bank()
        question_by_field = {q["field"]: q for q in list_questions(question_bank) if q["section"] == section_key}
        session = _get_or_create_session(user.id, question_bank.get("version"))

        if isinstance(section_data, dict):
            for field_key, value in section_data.items():
                q = question_by_field.get(field_key)
                if not q:
                    continue
                _upsert_answer(
                    user_id=user.id,
                    session_id=session.id,
                    question=q,
                    raw_message=json.dumps(value),
                    normalized_value=value,
                    answer_source="text",
                    is_valid=True,
                    needs_follow_up=False,
                )

        db.session.flush()
        answers = _fetch_answers(user.id)
        answer_map = index_answers_by_field(answers)
        progress, _ = _sync_session_progress(session, question_bank, answer_map)

        profile.onboarding_progress = _serialize_progress_with_sections(question_bank, answer_map)
        profile.profile_version = question_bank.get("version")

        if progress["is_complete"]:
            user.onboarding_completed = True

    except Exception:
        pass

    db.session.commit()

    return jsonify({
        "message": "Section updated successfully",
        "profile": profile.to_dict(),
    }), 200


@onboarding_v2_bp.route("/answers/<string:question_id>", methods=["PATCH"])
@jwt_required()
def patch_answer(question_id):
    user = _get_user()
    if not user:
        return jsonify({"message": "User not found"}), 404

    payload = request.get_json(silent=True) or {}
    value = payload.get("value")

    try:
        question_bank = load_question_bank()
    except Exception as exc:
        return jsonify({"message": f"Question bank error: {exc}"}), 500

    question = _question_map(question_bank).get(question_id)
    if not question:
        return jsonify({"message": "Question not found"}), 404

    profile = _get_or_create_profile(user.id)
    session = _get_or_create_session(user.id, question_bank.get("version"))

    _upsert_answer(
        user_id=user.id,
        session_id=session.id,
        question=question,
        raw_message=json.dumps(value),
        normalized_value=value,
        answer_source="text",
        is_valid=True,
        needs_follow_up=False,
    )

    apply_answer_to_profile(profile, question, value)

    db.session.flush()
    answers = _fetch_answers(user.id)
    answer_map = index_answers_by_field(answers)

    progress, next_question = _sync_session_progress(session, question_bank, answer_map)
    profile.onboarding_progress = _serialize_progress_with_sections(question_bank, answer_map)
    profile.profile_version = question_bank.get("version")

    if progress["is_complete"]:
        user.onboarding_completed = True

    db.session.commit()

    return jsonify({
        "message": "Answer updated",
        "current_question": next_question,
        "session": session.to_dict(),
        "profile": profile.to_dict(),
    }), 200
