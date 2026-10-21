from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, session

from database import add_audit_log, get_active_candidates, get_db
from thermal_printer import print_vvpat_slip

voting_bp = Blueprint("voting", __name__, url_prefix="/voting")


def admin_required():
    return bool(session.get("admin_id"))


@voting_bp.route("/admin")
def voter_home():
    if not admin_required():
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))

    return render_template(
        "voting.html",
        candidates=get_active_candidates()
    )


@voting_bp.route("/cast", methods=["POST"])
def cast_vote():
    if not admin_required():
        return jsonify({"success": False, "message": "Administrator login required."}), 401

    verified_voter_id = session.get("verified_voter_id")
    if not verified_voter_id:
        return jsonify({
            "success": False,
            "message": "Scan and verify a voter QR code first."
        }), 400

    if not session.get("verified_voter_photo_captured"):
        return jsonify({
            "success": False,
            "message": "Capture the verified voter's photo before casting the vote."
        }), 400

    data = request.get_json(silent=True) or {}
    candidate_id = str(data.get("candidate_id", "")).strip()

    if not candidate_id:
        return jsonify({
            "success": False,
            "message": "Select a candidate."
        }), 400

    conn = get_db()

    try:
        voter = conn.execute(
            "SELECT voter_id,name,has_voted FROM voters WHERE voter_id=?",
            (verified_voter_id,),
        ).fetchone()

        candidate = conn.execute(
            """
            SELECT id,candidate_id,name,symbol,party
            FROM candidates
            WHERE candidate_id=? AND status='Active'
            """,
            (candidate_id,),
        ).fetchone()

        if not voter:
            conn.rollback()
            session.pop("verified_voter_id", None)
            session.pop("verified_voter_photo_captured", None)
            return jsonify({
                "success": False,
                "message": "Verified voter no longer exists."
            }), 404

        if voter["has_voted"]:
            conn.rollback()
            session.pop("verified_voter_id", None)
            session.pop("verified_voter_photo_captured", None)
            return jsonify({
                "success": False,
                "message": "This voter has already voted."
            }), 409

        if not candidate:
            conn.rollback()
            return jsonify({
                "success": False,
                "message": "Candidate not found or inactive."
            }), 404

        conn.execute(
            "INSERT INTO votes(candidate_id,voter_id) VALUES(?,?)",
            (candidate["id"], voter["voter_id"]),
        )

        conn.execute(
            "UPDATE voters SET has_voted=1 WHERE voter_id=? AND has_voted=0",
            (voter["voter_id"],),
        )

        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            conn.rollback()
            return jsonify({
                "success": False,
                "message": "Vote was not recorded because the voter status changed."
            }), 409

        conn.commit()

    except Exception as exc:
        conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Unable to record vote: {exc}"
        }), 500
    finally:
        conn.close()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print_result = print_vvpat_slip(
        voter_id=voter["voter_id"],
        candidate_id=candidate["candidate_id"],
        candidate_name=candidate["name"],
        timestamp=timestamp,
    )

    add_audit_log(
        "VOTE_CAST",
        f"Vote cast for {candidate['name']} ({candidate['candidate_id']}) after QR and photo verification.",
        voter["voter_id"],
    )

    add_audit_log(
        "VVPAT_PRINTED" if print_result["success"] else "VVPAT_PRINT_PENDING",
        print_result["message"],
        voter["voter_id"],
    )

    session.pop("verified_voter_id", None)
    session.pop("verified_voter_photo_captured", None)

    return jsonify({
        "success": True,
        "message": "Vote recorded successfully.",
        "voter_name": voter["name"],
        "candidate_name": candidate["name"],
        "vvpat": print_result,
    })
