from collections import Counter

STYLE_PROFILES = {
    "classical": {
        "title": "The Classical Guide",
        "summary": "You thrive with structure, deep learning, and clear academic progression. You likely enjoy using trusted curricula and helping your child build strong foundations over time.",
        "strengths": [
            "You value mastery and consistency.",
            "You are intentional about academic rigor.",
            "You create dependable rhythms for your family.",
        ],
    },
    "charlotte_mason": {
        "title": "The Gentle Narrator",
        "summary": "You lean toward rich books, short focused lessons, and heart-level learning. You want education to shape both character and curiosity.",
        "strengths": [
            "You nurture wonder and attention.",
            "You prioritize meaningful conversations.",
            "You blend academics with beauty and nature.",
        ],
    },
    "unit_study": {
        "title": "The Integrative Explorer",
        "summary": "You love connecting subjects around shared themes and real-life projects. Your style is creative, cross-disciplinary, and engaging for multiple ages.",
        "strengths": [
            "You make learning feel connected and practical.",
            "You are strong at project-based teaching.",
            "You naturally adapt to family-wide learning.",
        ],
    },
    "unschooling": {
        "title": "The Interest-Led Mentor",
        "summary": "You trust natural curiosity and prioritize intrinsic motivation. You guide your child through real-world learning, conversation, and choice.",
        "strengths": [
            "You build ownership and confidence.",
            "You reduce pressure and preserve joy.",
            "You are responsive to each child's unique pace.",
        ],
    },
    "eclectic": {
        "title": "The Flexible Curator",
        "summary": "You blend methods based on season, child, and subject. You are practical, adaptive, and focused on what truly works in your home.",
        "strengths": [
            "You are highly adaptable.",
            "You personalize learning with wisdom.",
            "You balance structure and flexibility well.",
        ],
    },
}

QUESTIONS = [
    {
        "id": "q1",
        "question": "When planning your homeschool week, what feels most natural?",
        "options": [
            {"key": "q1_a", "text": "A clear schedule with specific subjects each day", "style": "classical"},
            {"key": "q1_b", "text": "Short meaningful lessons with books and narration", "style": "charlotte_mason"},
            {"key": "q1_c", "text": "A theme everyone can explore in different ways", "style": "unit_study"},
            {"key": "q1_d", "text": "Following the child's interests as they unfold", "style": "unschooling"},
            {"key": "q1_e", "text": "Mixing structure and flexibility based on the day", "style": "eclectic"},
        ],
    },
    {
        "id": "q2",
        "question": "What is your ideal role during learning time?",
        "options": [
            {"key": "q2_a", "text": "Instructor with a clear lesson plan", "style": "classical"},
            {"key": "q2_b", "text": "Guide who sparks reflection and discussion", "style": "charlotte_mason"},
            {"key": "q2_c", "text": "Facilitator of projects and hands-on discovery", "style": "unit_study"},
            {"key": "q2_d", "text": "Mentor who supports child-led exploration", "style": "unschooling"},
            {"key": "q2_e", "text": "Coach who adjusts approach as needed", "style": "eclectic"},
        ],
    },
    {
        "id": "q3",
        "question": "How do you usually choose curriculum?",
        "options": [
            {"key": "q3_a", "text": "Comprehensive, proven programs with progression", "style": "classical"},
            {"key": "q3_b", "text": "Living books and rich ideas over worksheets", "style": "charlotte_mason"},
            {"key": "q3_c", "text": "Resources that can connect across subjects", "style": "unit_study"},
            {"key": "q3_d", "text": "Minimal curriculum, mostly real-life learning", "style": "unschooling"},
            {"key": "q3_e", "text": "Different tools for different children/subjects", "style": "eclectic"},
        ],
    },
    {
        "id": "q4",
        "question": "When your child resists a lesson, what is your first instinct?",
        "options": [
            {"key": "q4_a", "text": "Keep the expectation but adjust pacing", "style": "classical"},
            {"key": "q4_b", "text": "Pause and reconnect through conversation", "style": "charlotte_mason"},
            {"key": "q4_c", "text": "Shift to a creative or practical activity", "style": "unit_study"},
            {"key": "q4_d", "text": "Let interest lead and revisit later", "style": "unschooling"},
            {"key": "q4_e", "text": "Try a different method entirely", "style": "eclectic"},
        ],
    },
    {
        "id": "q5",
        "question": "What does a successful homeschool day look like to you?",
        "options": [
            {"key": "q5_a", "text": "Core subjects completed with solid understanding", "style": "classical"},
            {"key": "q5_b", "text": "Deep ideas discussed and habits nurtured", "style": "charlotte_mason"},
            {"key": "q5_c", "text": "Meaningful project progress with family collaboration", "style": "unit_study"},
            {"key": "q5_d", "text": "Child highly engaged in self-directed learning", "style": "unschooling"},
            {"key": "q5_e", "text": "We adapted and still moved forward", "style": "eclectic"},
        ],
    },
    {
        "id": "q6",
        "question": "How do you feel about testing and assessments?",
        "options": [
            {"key": "q6_a", "text": "Useful for tracking mastery and gaps", "style": "classical"},
            {"key": "q6_b", "text": "Prefer narration, observation, and discussion", "style": "charlotte_mason"},
            {"key": "q6_c", "text": "Prefer project outputs over traditional tests", "style": "unit_study"},
            {"key": "q6_d", "text": "Mostly unnecessary for daily learning", "style": "unschooling"},
            {"key": "q6_e", "text": "Use whichever method fits the context", "style": "eclectic"},
        ],
    },
    {
        "id": "q7",
        "question": "Which environment helps your child learn best?",
        "options": [
            {"key": "q7_a", "text": "Consistent routine with predictable blocks", "style": "classical"},
            {"key": "q7_b", "text": "Calm rhythm with books, nature, and reflection", "style": "charlotte_mason"},
            {"key": "q7_c", "text": "Interactive spaces for experiments and projects", "style": "unit_study"},
            {"key": "q7_d", "text": "Real-world settings and everyday experiences", "style": "unschooling"},
            {"key": "q7_e", "text": "A mix depending on mood and goals", "style": "eclectic"},
        ],
    },
    {
        "id": "q8",
        "question": "When introducing a new topic, you usually start with:",
        "options": [
            {"key": "q8_a", "text": "Definitions, sequence, and core concepts", "style": "classical"},
            {"key": "q8_b", "text": "A compelling story or great book", "style": "charlotte_mason"},
            {"key": "q8_c", "text": "A hands-on challenge or mini project", "style": "unit_study"},
            {"key": "q8_d", "text": "Questions your child already has", "style": "unschooling"},
            {"key": "q8_e", "text": "Whatever approach fits that topic best", "style": "eclectic"},
        ],
    },
    {
        "id": "q9",
        "question": "What is your biggest homeschool priority this season?",
        "options": [
            {"key": "q9_a", "text": "Academic depth and skill progression", "style": "classical"},
            {"key": "q9_b", "text": "Character formation and love of learning", "style": "charlotte_mason"},
            {"key": "q9_c", "text": "Integrated learning that feels meaningful", "style": "unit_study"},
            {"key": "q9_d", "text": "Autonomy, confidence, and curiosity", "style": "unschooling"},
            {"key": "q9_e", "text": "Sustainable rhythms that actually work", "style": "eclectic"},
        ],
    },
    {
        "id": "q10",
        "question": "How do you make curriculum decisions when life gets busy?",
        "options": [
            {"key": "q10_a", "text": "Preserve core sequence and trim extras", "style": "classical"},
            {"key": "q10_b", "text": "Focus on essential books and habits", "style": "charlotte_mason"},
            {"key": "q10_c", "text": "Consolidate into one strong unit or project", "style": "unit_study"},
            {"key": "q10_d", "text": "Lean into organic learning opportunities", "style": "unschooling"},
            {"key": "q10_e", "text": "Pivot quickly and mix what serves us", "style": "eclectic"},
        ],
    },
]


def get_public_quiz_payload():
    return {
        "quiz_key": "homeschool_style",
        "title": "What Is Your Homeschool Style?",
        "description": "Answer 10 quick questions to discover your dominant homeschool style.",
        "questions": [
            {
                "id": q["id"],
                "question": q["question"],
                "options": [{"key": opt["key"], "text": opt["text"]} for opt in q["options"]],
            }
            for q in QUESTIONS
        ],
    }


def calculate_result(answer_map):
    style_counts = Counter({key: 0 for key in STYLE_PROFILES.keys()})

    for question in QUESTIONS:
        qid = question["id"]
        selected = answer_map.get(qid)
        for option in question["options"]:
            if option["key"] == selected:
                style_counts[option["style"]] += 1
                break

    sorted_styles = sorted(
        style_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_style = sorted_styles[0][0]
    second_style = sorted_styles[1][0] if len(sorted_styles) > 1 else top_style

    top_profile = STYLE_PROFILES[top_style]
    second_profile = STYLE_PROFILES[second_style]

    result_summary = (
        f"Primary style: {top_profile['title']}. "
        f"Secondary influence: {second_profile['title']}. "
        f"{top_profile['summary']}"
    )

    return {
        "result_key": top_style,
        "result_title": top_profile["title"],
        "result_summary": result_summary,
        "strengths": top_profile["strengths"],
        "score_breakdown": dict(style_counts),
    }


def is_valid_answer_payload(answer_map):
    if not isinstance(answer_map, dict):
        return False

    for question in QUESTIONS:
        qid = question["id"]
        if qid not in answer_map:
            return False
        valid_keys = {option["key"] for option in question["options"]}
        if answer_map[qid] not in valid_keys:
            return False

    return True
