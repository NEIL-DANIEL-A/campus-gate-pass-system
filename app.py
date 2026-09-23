"""
Campus Gate Pass System
Main Flask Application.
Notifies Admin via AWS SNS whenever a new student gate pass request is submitted.
"""

import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g
from dotenv import load_dotenv

import sns_utils

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "campus-gate-pass-secret-demo-key")

# Vercel serverless only allows writes in /tmp
if os.getenv("VERCEL"):
    DATABASE = "/tmp/gate_pass.db"
else:
    DATABASE = os.path.join(os.path.dirname(__file__), "gate_pass.db")


def get_db():
    """Opens a new database connection per request if none exists."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the SQLite schema."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gate_passes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                reason TEXT NOT NULL,
                out_time TEXT NOT NULL,
                return_time TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.commit()


@app.route("/", methods=["GET", "POST"])
def index():
    """Student gate pass request form."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        reason = request.form.get("reason", "").strip()
        out_time = request.form.get("out_time", "").strip()
        return_time = request.form.get("return_time", "").strip()
        email = request.form.get("email", "").strip()

        if not all([name, reason, out_time, return_time, email]):
            flash("All fields are required. Please complete the form.", "warning")
            return render_template(
                "index.html",
                name=name,
                reason=reason,
                out_time=out_time,
                return_time=return_time,
                email=email,
            )

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO gate_passes (name, reason, out_time, return_time, email, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (name, reason, out_time, return_time, email),
        )
        db.commit()
        pass_id = cursor.lastrowid

        # Publish SNS alert to Admin
        sns_result = sns_utils.notify_admin_new_request(
            pass_id=pass_id,
            name=name,
            reason=reason,
            out_time=out_time,
            return_time=return_time,
            email=email,
        )

        flash(
            f"Gate pass #{pass_id} submitted! [SNS: {sns_result.get('message', 'Admin notified')}]",
            "success",
        )
        return redirect(url_for("status", pass_id=pass_id))

    return render_template("index.html")


@app.route("/status/<int:pass_id>", methods=["GET"])
def status(pass_id):
    """Student pass status lookup page."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM gate_passes WHERE id = ?", (pass_id,))
    gate_pass = cursor.fetchone()

    if not gate_pass:
        flash(f"Gate Pass #{pass_id} was not found.", "danger")
        return redirect(url_for("index"))

    return render_template("status.html", gate_pass=gate_pass)


@app.route("/admin", methods=["GET"])
def admin():
    """Admin dashboard listing pending and processed passes."""
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM gate_passes WHERE status = 'pending' ORDER BY id DESC")
    pending_passes = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM gate_passes WHERE status != 'pending' ORDER BY id DESC LIMIT 15"
    )
    processed_passes = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM gate_passes WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM gate_passes WHERE status = 'approved'")
    approved_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM gate_passes WHERE status = 'rejected'")
    rejected_count = cursor.fetchone()[0]

    return render_template(
        "admin.html",
        pending_passes=pending_passes,
        processed_passes=processed_passes,
        stats={
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
        },
    )


@app.route("/admin/approve/<int:pass_id>", methods=["POST"])
def admin_approve(pass_id):
    """Approves a pass."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM gate_passes WHERE id = ?", (pass_id,))
    gate_pass = cursor.fetchone()

    if not gate_pass:
        flash(f"Gate Pass #{pass_id} does not exist.", "danger")
        return redirect(url_for("admin"))

    cursor.execute("UPDATE gate_passes SET status = 'approved' WHERE id = ?", (pass_id,))
    db.commit()

    flash(f"Gate Pass #{pass_id} for {gate_pass['name']} has been APPROVED.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/reject/<int:pass_id>", methods=["POST"])
def admin_reject(pass_id):
    """Rejects a pass with a reason."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM gate_passes WHERE id = ?", (pass_id,))
    gate_pass = cursor.fetchone()

    if not gate_pass:
        flash(f"Gate Pass #{pass_id} does not exist.", "danger")
        return redirect(url_for("admin"))

    rejection_reason = request.form.get("reason", "").strip() or "Denied by administrator."

    cursor.execute(
        "UPDATE gate_passes SET status = 'rejected', rejection_reason = ? WHERE id = ?",
        (rejection_reason, pass_id),
    )
    db.commit()

    flash(f"Gate Pass #{pass_id} for {gate_pass['name']} was REJECTED.", "info")
    return redirect(url_for("admin"))


# Initialize SQLite table on load
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
