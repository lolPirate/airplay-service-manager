from flask import Blueprint, current_app, jsonify, render_template, request

from .controller import SessionSpec, UxPlayController

bp = Blueprint("main", __name__)


def controller() -> UxPlayController:
    return current_app.extensions["uxplay_controller"]


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/healthz")
def healthz():
    return jsonify(ok=True)


@bp.get("/api/session")
def session_status():
    return jsonify(controller().status())


@bp.get("/api/display")
def display_status():
    try:
        return jsonify(controller().display_status())
    except RuntimeError as exc:
        return jsonify(ok=False, error=str(exc)), 503


@bp.put("/api/display")
def rotate_display():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, error="Expected a JSON object with a mode"), 400
    try:
        return jsonify(controller().set_display_mode(payload.get("mode")))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(ok=False, error=str(exc)), 503


@bp.put("/api/session")
def start_or_replace_session():
    try:
        spec = SessionSpec.from_payload(request.get_json(silent=True))
        result = controller().start(spec)
        return jsonify(result)
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(ok=False, error=str(exc)), 503


@bp.delete("/api/session")
def stop_session():
    return jsonify(controller().stop())
