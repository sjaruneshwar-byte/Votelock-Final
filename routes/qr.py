import secrets
import base64
import binascii
import re
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, session

from database import add_audit_log, get_active_candidates, get_db

qr_bp = Blueprint("qr", __name__, url_prefix="/qr")


def admin_required():
    return bool(session.get("admin_id"))


@qr_bp.route("/scanner")
def scanner():
    if not admin_required():
        return jsonify({"success": False, "message": "Administrator login required."}), 401

    return render_template(
        "voter_qr_scanner.html",
        candidates=get_active_candidates(),
    )


@qr_bp.route("/verify", methods=["POST"])
def verify_qr():
    if not admin_required():
        return jsonify({"success": False, "message": "Administrator login required."}), 401

    data = request.get_json(silent=True) or {}
    qr_token = str(data.get("qr_token", "")).strip()

    if not qr_token:
        return jsonify({"success": False, "message": "No QR token received."}), 400

    conn = get_db()
    voter = conn.execute(
        """
        SELECT voter_id, name, email, department, has_voted, image_path
        FROM voters
        WHERE qr_token=?
        """,
        (qr_token,),
    ).fetchone()
    conn.close()

    if voter is None:
        session.pop("verified_voter_id", None)
        session.pop("verified_voter_photo_captured", None)
        return jsonify({
            "success": False,
            "message": "Invalid QR code. Voter record was not found."
        }), 404

    if voter["has_voted"]:
        session.pop("verified_voter_id", None)
        session.pop("verified_voter_photo_captured", None)

        add_audit_log(
            "QR_REJECTED_ALREADY_VOTED",
            f"QR scan rejected because voter {voter['voter_id']} has already voted.",
            voter["voter_id"],
        )

        return jsonify({
            "success": False,
            "already_voted": True,
            "message": "This voter has already voted. A second vote is not permitted.",
            "voter": dict(voter),
        }), 409

    session["verified_voter_id"] = voter["voter_id"]
    session["verified_voter_photo_captured"] = False

    add_audit_log(
        "QR_VERIFIED",
        f"Administrator verified QR for voter {voter['voter_id']}.",
        voter["voter_id"],
    )

    return jsonify({
        "success": True,
        "message": "Voter verified successfully.",
        "voter": dict(voter),
    })


@qr_bp.route("/capture-photo", methods=["POST"])
def capture_photo():
    if not admin_required():
        return jsonify({"success": False, "message": "Administrator login required."}), 401

    voter_id = session.get("verified_voter_id")
    if not voter_id:
        return jsonify({
            "success": False,
            "message": "Verify a voter QR code before capturing a photo."
        }), 400

    data = request.get_json(silent=True) or {}
    image_data = str(data.get("image", "")).strip()

    match = re.match(r"^data:image/jpeg;base64,(.+)$", image_data)
    if not match:
        return jsonify({
            "success": False,
            "message": "Invalid photo format. Please capture the photo again."
        }), 400

    try:
        image_bytes = base64.b64decode(match.group(1), validate=True)
    except (binascii.Error, ValueError):
        return jsonify({
            "success": False,
            "message": "Photo data could not be decoded."
        }), 400

    # Keep the capture intentionally small for a lightweight lab system.
    if not image_bytes or len(image_bytes) > 5 * 1024 * 1024:
        return jsonify({
            "success": False,
            "message": "Photo size is invalid."
        }), 400

    upload_dir = Path(__file__).resolve().parent.parent / "static" / "uploads" / "voters"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{voter_id}_{secrets.token_hex(8)}.jpg"
    file_path = upload_dir / filename

    try:
        file_path.write_bytes(image_bytes)

        conn = get_db()
        conn.execute(
            "UPDATE voters SET image_path=? WHERE voter_id=?",
            (f"uploads/voters/{filename}", voter_id),
        )
        conn.commit()
        conn.close()

        session["verified_voter_photo_captured"] = True

        add_audit_log(
            "VOTER_PHOTO_CAPTURED",
            f"Administrator captured the polling-station photo for voter {voter_id}.",
            voter_id,
        )

        return jsonify({
            "success": True,
            "message": "Voter photo captured successfully.",
            "image_url": f"/static/uploads/voters/{filename}",
        })

    except Exception as exc:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

        return jsonify({
            "success": False,
            "message": f"Unable to save voter photo: {exc}"
        }), 500


@qr_bp.route("/clear", methods=["POST"])
def clear_verified_voter():
    if not admin_required():
        return jsonify({"success": False, "message": "Administrator login required."}), 401

    session.pop("verified_voter_id", None)
    session.pop("verified_voter_photo_captured", None)

    return jsonify({"success": True})
