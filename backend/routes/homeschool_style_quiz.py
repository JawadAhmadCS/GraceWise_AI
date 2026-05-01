import os
import re
import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request

from models import db, HomeschoolStyleSubmission
from services.homeschool_style_quiz import (
    calculate_result,
    get_public_quiz_payload,
    is_valid_answer_payload,
)
from services.systeme_service import push_quiz_lead_to_systeme
from services.email_service import send_homeschool_style_result_email


homeschool_style_quiz_bp = Blueprint("homeschool_style_quiz", __name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _frontend_base_url():
    return (os.environ.get("FRONTEND_BASE_URL") or "http://localhost:5500").rstrip("/")


def _build_result_payload(submission):
    return {
        "result_key": submission.result_key,
        "result_title": submission.result_title,
        "result_summary": submission.result_summary,
        "score_breakdown": submission.score_breakdown,
        "strengths": calculate_result(submission.answers).get("strengths", []),
    }


@homeschool_style_quiz_bp.route("/homeschool-style/questions", methods=["GET"])
def get_homeschool_style_questions():
    return jsonify(get_public_quiz_payload()), 200


@homeschool_style_quiz_bp.route("/homeschool-style/submit", methods=["POST"])
def submit_homeschool_style_answers():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers", {})
    metadata = data.get("metadata", {}) or {}

    if not is_valid_answer_payload(answers):
        return jsonify({"message": "Please answer every question."}), 400

    result = calculate_result(answers)

    submission = HomeschoolStyleSubmission(
        submission_token=secrets.token_urlsafe(32),
        answers=answers,
        score_breakdown=result["score_breakdown"],
        result_key=result["result_key"],
        result_title=result["result_title"],
        result_summary=result["result_summary"],
        utm_source=(metadata.get("utm_source") or "")[:120] or None,
        utm_medium=(metadata.get("utm_medium") or "")[:120] or None,
        utm_campaign=(metadata.get("utm_campaign") or "")[:120] or None,
    )

    db.session.add(submission)
    db.session.commit()

    return jsonify({
        "message": "Answers received.",
        "submission_token": submission.submission_token,
        "next_step": "email_capture",
    }), 201


@homeschool_style_quiz_bp.route("/homeschool-style/capture-lead", methods=["POST"])
def capture_homeschool_style_lead():
    data = request.get_json(silent=True) or {}

    submission_token = (data.get("submission_token") or "").strip()
    email = (data.get("email") or "").strip().lower()
    metadata = data.get("metadata", {}) or {}

    if not submission_token:
        return jsonify({"message": "submission_token is required."}), 400

    if not email or not EMAIL_REGEX.match(email):
        return jsonify({"message": "Please provide a valid email address."}), 400

    submission = HomeschoolStyleSubmission.query.filter_by(submission_token=submission_token).first()
    if not submission:
        return jsonify({"message": "Quiz submission not found."}), 404

    submission.email = email
    submission.lead_captured_at = submission.lead_captured_at or datetime.utcnow()
    submission.utm_source = submission.utm_source or ((metadata.get("utm_source") or "")[:120] or None)
    submission.utm_medium = submission.utm_medium or ((metadata.get("utm_medium") or "")[:120] or None)
    submission.utm_campaign = submission.utm_campaign or ((metadata.get("utm_campaign") or "")[:120] or None)

    result_payload = _build_result_payload(submission)

    sync_status, sync_response = push_quiz_lead_to_systeme(
        email=email,
        result_payload=result_payload,
        metadata={
            "submission_token": submission.submission_token,
            "utm_source": submission.utm_source,
            "utm_medium": submission.utm_medium,
            "utm_campaign": submission.utm_campaign,
            "quiz": "homeschool_style",
        },
    )
    submission.systeme_sync_status = sync_status
    submission.systeme_sync_response = (sync_response or "")[:10000]

    db.session.commit()

    send_homeschool_style_result_email(email, result_payload)

    redirect_url = f"{_frontend_base_url()}/homeschool-quiz-result.html?token={submission.submission_token}"

    return jsonify({
        "message": "Result sent successfully.",
        "redirect_url": redirect_url,
        "systeme_sync_status": sync_status,
    }), 200


@homeschool_style_quiz_bp.route("/homeschool-style/result", methods=["GET"])
def get_homeschool_style_result():
    submission_token = (request.args.get("token") or "").strip()
    if not submission_token:
        return jsonify({"message": "Missing token."}), 400

    submission = HomeschoolStyleSubmission.query.filter_by(submission_token=submission_token).first()
    if not submission:
        return jsonify({"message": "Result not found."}), 404

    if not submission.email:
        return jsonify({"message": "Result is locked until email is submitted."}), 403

    return jsonify({
        "result": submission.to_result_dict(),
    }), 200
