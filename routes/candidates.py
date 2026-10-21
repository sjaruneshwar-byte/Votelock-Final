from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from database import (
    get_db,
    get_all_candidates,
    get_candidate,
    delete_candidate,
    add_audit_log
)


# ============================================================
# CANDIDATES BLUEPRINT
# ============================================================

candidates_bp = Blueprint(
    "candidates",
    __name__,
    url_prefix="/candidates"
)


def admin_required():
    return "admin_id" in session


# ============================================================
# LIST CANDIDATES
# ============================================================

@candidates_bp.route("/")
def list_candidates():

    if not admin_required():
        return redirect(url_for("auth.login"))

    candidates = get_all_candidates()

    return render_template(
        "candidates/list.html",
        candidates=candidates
    )


# ============================================================
# ADD CANDIDATE
# ============================================================

@candidates_bp.route("/add", methods=["GET", "POST"])
def add_candidate():

    if not admin_required():
        return redirect(url_for("auth.login"))

    if request.method == "POST":

        candidate_id = request.form.get(
            "candidate_id",
            ""
        ).strip()

        name = request.form.get(
            "name",
            ""
        ).strip()

        symbol = request.form.get(
            "symbol",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not candidate_id:

            flash(
                "Candidate ID is required.",
                "error"
            )

            return redirect(
                url_for("candidates.add_candidate")
            )


        if not name:

            flash(
                "Candidate name is required.",
                "error"
            )

            return redirect(
                url_for("candidates.add_candidate")
            )


        # ----------------------------------------------------
        # INSERT CANDIDATE
        # ----------------------------------------------------

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO candidates
                (
                    candidate_id,
                    name,
                    symbol,
                    description
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    name,
                    symbol,
                    description
                )
            )

            conn.commit()

            # ------------------------------------------------
            # AUDIT LOG
            # ------------------------------------------------

            add_audit_log(
                "CANDIDATE_ADDED",
                f"Candidate {name} ({candidate_id}) was added."
            )

            flash(
                "Candidate added successfully.",
                "success"
            )

        except Exception as e:

            conn.rollback()

            if "UNIQUE constraint failed" in str(e):

                flash(
                    "Candidate ID already exists.",
                    "error"
                )

            else:

                flash(
                    f"Unable to add candidate: {str(e)}",
                    "error"
                )

        finally:

            conn.close()


        return redirect(
            url_for("candidates.list_candidates")
        )


    return render_template(
        "candidates/add.html"
    )


# ============================================================
# DELETE CANDIDATE
# ============================================================

@candidates_bp.route(
    "/delete/<candidate_id>",
    methods=["POST"]
)
def remove_candidate(candidate_id):

    if not admin_required():
        return redirect(url_for("auth.login"))

    success, message = delete_candidate(
        candidate_id
    )

    if success:

        add_audit_log(
            "CANDIDATE_DELETED",
            f"Candidate {candidate_id} was removed."
        )

        flash(
            message,
            "success"
        )

    else:

        flash(
            message,
            "error"
        )


    return redirect(
        url_for("candidates.list_candidates")
    )


# ============================================================
# CANDIDATE DETAILS
# ============================================================

@candidates_bp.route(
    "/<candidate_id>"
)
def candidate_details(candidate_id):

    if not admin_required():
        return redirect(url_for("auth.login"))

    candidate = get_candidate(
        candidate_id
    )

    if candidate is None:

        flash(
            "Candidate not found.",
            "error"
        )

        return redirect(
            url_for("candidates.list_candidates")
        )


    return render_template(
        "candidates/details.html",
        candidate=candidate
    )