import secrets

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import generate_password_hash

from database import (
    get_db,
    get_all_voters,
    get_voter,
    delete_voter,
    add_audit_log
)


voters_bp = Blueprint(
    "voters",
    __name__
)


def admin_required():

    return "admin_id" in session


# ======================================================
# VOTER LIST
# ======================================================

@voters_bp.route("/voters")
def list_voters():

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    voters = get_all_voters()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    if search:

        voters = [
            voter
            for voter in voters
            if search in voter["voter_id"].lower()
            or search in voter["name"].lower()
            or (
                voter["department"]
                and search in voter["department"].lower()
            )
        ]

    return render_template(
        "voters.html",
        voters=voters,
        search=search
    )


# ======================================================
# ADD VOTER
# ======================================================

@voters_bp.route(
    "/voters/add",
    methods=["GET", "POST"]
)
def add_voter():

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    if request.method == "POST":

        voter_id = request.form.get(
            "voter_id",
            ""
        ).strip()

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        # ==============================================
        # VALIDATION
        # ==============================================

        if not voter_id or not name:

            flash(
                "Voter ID and name are required.",
                "error"
            )

            return redirect(
                url_for("voters.add_voter")
            )

        # ==============================================
        # GENERATE TEMPORARY CREDENTIALS
        # ==============================================

        username = (
            "VOTER_" +
            voter_id.upper()
        )

        temporary_password = (
            secrets.token_urlsafe(8)
        )

        password_hash = (
            generate_password_hash(
                temporary_password
            )
        )

        # ==============================================
        # GENERATE UNIQUE QR TOKEN
        # ==============================================

        qr_token = secrets.token_urlsafe(
            24
        )

        conn = get_db()

        try:

            conn.execute(
                """
                INSERT INTO voters
                (
                    voter_id,
                    name,
                    email,
                    department,
                    username,
                    password_hash,
                    qr_token
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    voter_id,
                    name,
                    email,
                    department,
                    username,
                    password_hash,
                    qr_token
                )
            )

            conn.commit()

            # ==========================================
            # AUDIT LOG
            # ==========================================

            add_audit_log(
                "VOTER_ADDED",
                f"Voter {voter_id} was registered.",
                voter_id
            )

            # ==========================================
            # STORE CREDENTIALS FOR ONE-TIME DISPLAY
            # ==========================================

            session[
                "generated_credentials"
            ] = {

                "voter_id": voter_id,

                "username": username,

                "password": temporary_password
            }

            return redirect(
                url_for(
                    "voters.credentials"
                )
            )

        except Exception as e:

            conn.rollback()

            if "UNIQUE constraint" in str(e):

                flash(
                    "Voter ID or generated username already exists.",
                    "error"
                )

            else:

                flash(
                    f"Unable to add voter: {str(e)}",
                    "error"
                )

        finally:

            conn.close()

        return redirect(
            url_for(
                "voters.list_voters"
            )
        )

    return render_template(
        "add_voter.html"
    )


# ======================================================
# DISPLAY TEMPORARY CREDENTIALS
# ======================================================

@voters_bp.route(
    "/voters/credentials"
)
def credentials():

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    credentials = session.pop(
        "generated_credentials",
        None
    )

    if credentials is None:

        flash(
            "No temporary credentials available.",
            "error"
        )

        return redirect(
            url_for(
                "voters.list_voters"
            )
        )

    return render_template(
        "voter_credentials.html",
        credentials=credentials
    )


# ======================================================
# VIEW VOTER QR CODE
# ======================================================

@voters_bp.route(
    "/voters/qr/<voter_id>"
)
def view_qr(voter_id):

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    voter = get_voter(
        voter_id
    )

    if voter is None:

        flash(
            "Voter not found.",
            "error"
        )

        return redirect(
            url_for(
                "voters.list_voters"
            )
        )

    return render_template(
        "voter_qr.html",
        voter=voter
    )


# ======================================================
# EDIT VOTER
# ======================================================

@voters_bp.route(
    "/voters/edit/<voter_id>",
    methods=["GET", "POST"]
)
def edit_voter(voter_id):

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    voter = get_voter(
        voter_id
    )

    if voter is None:

        flash(
            "Voter not found.",
            "error"
        )

        return redirect(
            url_for(
                "voters.list_voters"
            )
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        if not name:

            flash(
                "Name is required.",
                "error"
            )

            return redirect(
                url_for(
                    "voters.edit_voter",
                    voter_id=voter_id
                )
            )

        conn = get_db()

        conn.execute(
            """
            UPDATE voters
            SET name = ?,
                email = ?,
                department = ?
            WHERE voter_id = ?
            """,
            (
                name,
                email,
                department,
                voter_id
            )
        )

        conn.commit()
        conn.close()

        add_audit_log(
            "VOTER_UPDATED",
            f"Voter {voter_id} was updated.",
            voter_id
        )

        flash(
            "Voter updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "voters.list_voters"
            )
        )

    return render_template(
        "edit_voter.html",
        voter=voter
    )


# ======================================================
# DELETE VOTER
# ======================================================

@voters_bp.route(
    "/voters/delete/<voter_id>",
    methods=["POST"]
)
def remove_voter(voter_id):

    if not admin_required():

        return redirect(
            url_for("auth.login")
        )

    success, message = delete_voter(
        voter_id
    )

    if success:

        add_audit_log(
            "VOTER_DELETED",
            f"Voter {voter_id} was deleted.",
            voter_id
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
        url_for(
            "voters.list_voters"
        )
    )