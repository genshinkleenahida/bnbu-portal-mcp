"""Every tool, written once: the MCP server registers these functions and the CLI turns them into commands."""
from pathlib import Path

from . import evaluation, notices, textinfo
from .client import ISpace, ISpaceError
from .portal import Portal

_client = _portal = None


def client() -> ISpace:
    global _client
    _client = _client or ISpace()
    return _client


def portal() -> Portal:
    global _portal
    _portal = _portal or Portal()
    return _portal


# ---- iSpace ----
def site_info() -> dict:
    """Site info, the logged-in user, and the web-service functions the token may call."""
    return client().site_info()


def list_courses() -> list[dict]:
    """Enrolled iSpace courses."""
    return client().courses()


def course_contents(courseid: int) -> list[dict]:
    """Sections, activities and files of a course (file URLs go to download_file)."""
    return client().course_contents(courseid)


def list_assignments(courseids: list[int] | None = None) -> list[dict]:
    """Assignments with due dates (UTC+8); all enrolled courses by default."""
    return client().assignments(courseids)


def submission_status(assignid: int) -> dict:
    """Submission and grading status of one assignment."""
    return client().submission_status(assignid)


def upcoming_deadlines(days: int = 14, include_overdue: bool = False) -> list[dict]:
    """Assignments due within `days` days, soonest first."""
    return client().upcoming_deadlines(days, include_overdue)


def download_file(fileurl: str, dest_dir: str = "") -> dict:
    """Download an iSpace file URL (iSpace host only) to dest_dir (default ~/Downloads/ispace)."""
    return client().download_file(fileurl, dest_dir)


def announcements(courseids: list[int] | None = None, per_forum: int = 20, max_chars: int = 2000) -> list[dict]:
    """Announcements and forum posts as plain text, newest first (max_chars per post, 0 = no limit)."""
    return textinfo.announcements(client(), courseids, per_forum, max_chars)


def course_text(courseids: list[int] | None = None, max_chars: int = 2000) -> list[dict]:
    """Text on course pages: section summaries, labels, pages, activity descriptions (exam time/scope often live here)."""
    return textinfo.course_text(client(), courseids, max_chars)


def notifications(limit: int = 20, kind: str = "notifications") -> list[dict]:
    """iSpace notifications (kind='notifications') or direct messages (kind='conversations'). Marks nothing as read."""
    return textinfo.notifications(client(), limit, kind)


def search_text(keywords: list[str] | None = None, courseids: list[int] | None = None, messages: bool = True) -> list[dict]:
    """Search announcements, course text and messages; no keywords = exam-related words (English and Chinese)."""
    return textinfo.search_text(client(), keywords, courseids, messages)


def new_notices(mark_seen: bool = True) -> dict:
    """Notices not shown before (first run: last 7 days). mark_seen keeps them from showing again."""
    return notices.new_notices(client(), mark_seen)


def mark_notices_seen() -> dict:
    """Treat all current notices as seen."""
    return notices.mark_notices_seen(client())


# ---- MIS and portal ----
def mis_timetable(semester_id: str = "") -> dict:
    """MIS class timetable (current semester unless a semester id is given)."""
    return portal().mis_timetable(semester_id)


def mis_grades(academic_year_id: str = "") -> dict:
    """MIS grades and GPA (current academic year unless an id is given)."""
    return portal().mis_grades(academic_year_id)


def mis_evaluations() -> list[dict]:
    """Teaching & Learning Evaluation sections and their status. An empty list means none is listed right now."""
    return portal().mis_evaluations()


def oa_services() -> list[dict]:
    """Applications in the BNBU portal Services Center."""
    return portal().oa_services()


def leave_list(limit: int = 20) -> list[dict]:
    """Your Leave Application requests, newest first."""
    return portal().leave_list(limit)


def leave_detail(request_id: str) -> dict:
    """One of your leave requests (id from leave_list)."""
    return portal().leave_detail(request_id)


def leave_form() -> dict:
    """Fields of a blank leave form (read-only; leave requests are never submitted)."""
    return portal().leave_form()


# ---- write tools ----
def upload_and_save_submission(assignid: int, file_paths: list[str]) -> dict:
    """Save one or more local files as a single submission draft (not yet submitted for grading)."""
    paths = [Path(p).expanduser() for p in file_paths]
    for p in paths:
        if not p.is_file():
            raise ISpaceError(f"File not found: {p}")
    return client().upload_and_save_submission(assignid, [str(p) for p in paths])


def submit_for_grading(assignid: int) -> dict:
    """Submit an assignment for grading (usually irreversible)."""
    return client().submit_for_grading(assignid)


def _evaluate(course: str | None, comment: str) -> dict:
    secs = portal().mis_evaluations()
    if course:
        secs = [s for s in secs if course == s["section_id"] or course.lower() in f"{s['course']} {s['instructor']}".lower()]
        if not secs:
            raise ISpaceError(f"No evaluation matches '{course}'. See mis_evaluations.")
    pending = [s for s in secs if s["status"] == "pending"]
    if course and len(pending) != 1:
        raise ISpaceError("Already evaluated (it cannot be refilled)." if not pending else
                          "More than one match: " + "; ".join(f"{s['course']} ({s['instructor']})" for s in pending))
    results = []
    for s in pending:
        p = evaluation.build_plan(evaluation.parse_form(portal().mis_get(
            "/mis/student/te/question.do", {"sectionId": s["section_id"]})), comment)
        if not p["problems"]:
            portal().mis_post("/mis/student/te/submit.do", {"sectionId": s["section_id"]}, p["payload"])
        results.append({"course": s["course"], "submitted": not p["problems"], "problems": p["problems"]})
    return {"results": results, "still_pending": sum(s["status"] == "pending" for s in portal().mis_evaluations())}


def mis_evaluate(course: str, comment: str = "") -> dict:
    """Fill in the MIS evaluation of ONE course (name, instructor or section id) with the highest option for every rating question."""
    return _evaluate(course, comment)


def mis_evaluate_all(comment: str = "") -> dict:
    """Fill in every pending MIS evaluation the same way as mis_evaluate."""
    return _evaluate(None, comment)


READ = [site_info, list_courses, course_contents, list_assignments, submission_status, upcoming_deadlines,
        download_file, announcements, course_text, notifications, search_text, new_notices, mark_notices_seen,
        mis_timetable, mis_grades, mis_evaluations, oa_services, leave_list, leave_detail, leave_form]
WRITE = [upload_and_save_submission, submit_for_grading, mis_evaluate, mis_evaluate_all]
