"""
Student Management System with Analytics & ML Result Predictor
Subject: Python for Data Science (BE05000231) - PBL3 Mini Project

Beyond-syllabus topics used:
  1. Streamlit        -> web application UI
  2. Plotly           -> interactive charts
  3. PBKDF2 hashing   -> secure admin login (hashlib + salt)
  4. fpdf2            -> auto-generated PDF report cards (grade + rank)
  5. Excel export     -> openpyxl via Pandas
"""
import hashlib
import io
import os
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

DB = "students.db"
PASS_MARK = 40
FEATURES = ["attendance", "internal_marks", "assignment_score"]


# ----------------------------- Database layer -----------------------------
def conn():
    return sqlite3.connect(DB)


def hash_pw(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 100_000
    ).hex()
    return salt, digest


def init_db():
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS students(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                department TEXT,
                semester INTEGER,
                attendance REAL,
                internal_marks REAL,
                assignment_score REAL,
                final_marks REAL)"""
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt TEXT, pw_hash TEXT)"
        )
        if not c.execute("SELECT 1 FROM users").fetchone():
            salt, h = hash_pw("admin123")
            c.execute("INSERT INTO users VALUES(?,?,?)", ("admin", salt, h))


def check_login(username, password):
    with conn() as c:
        row = c.execute(
            "SELECT salt, pw_hash FROM users WHERE username=?", (username,)
        ).fetchone()
    return bool(row) and hash_pw(password, row[0])[1] == row[1]


def load_df():
    with conn() as c:
        return pd.read_sql("SELECT * FROM students", c)


def add_student(rec):
    try:
        with conn() as c:
            c.execute(
                """INSERT INTO students(roll_no,name,email,department,semester,
                   attendance,internal_marks,assignment_score,final_marks)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                rec,
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_student(sid, rec):
    with conn() as c:
        c.execute(
            """UPDATE students SET name=?,email=?,department=?,semester=?,
               attendance=?,internal_marks=?,assignment_score=?,final_marks=?
               WHERE id=?""",
            (*rec, sid),
        )


def delete_student(sid):
    with conn() as c:
        c.execute("DELETE FROM students WHERE id=?", (sid,))


def load_sample_data(n=60):
    rng = np.random.default_rng(42)
    depts = ["CE", "IT", "ME", "EC", "EE"]
    added = 0
    for i in range(n):
        att = float(rng.integers(40, 100))
        internal = float(rng.integers(10, 100))
        assign = float(rng.integers(10, 100))
        final = float(
            np.clip(0.15 * att + 0.45 * internal + 0.30 * assign + rng.normal(0, 8), 0, 100)
        )
        ok = add_student(
            (f"S{1000 + i}", f"Student {i + 1}", f"student{i + 1}@mail.com",
             depts[i % 5], int(rng.integers(1, 9)), att, internal, assign, round(final, 1))
        )
        added += ok
    return added


# ------------------------------- Pages ------------------------------------
def page_dashboard(df):
    st.header("📊 Analytics Dashboard")
    if df.empty:
        st.info("No data yet. Add students or load sample data from the sidebar.")
        return
    df = df.copy()
    df["result"] = np.where(df["final_marks"] >= PASS_MARK, "Pass", "Fail")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total students", len(df))
    c2.metric("Average marks", f"{df['final_marks'].mean():.1f}")
    c3.metric("Pass %", f"{(df['result'] == 'Pass').mean() * 100:.1f}%")
    c4.metric("Avg attendance", f"{df['attendance'].mean():.1f}%")

    st.subheader("Descriptive statistics")
    st.dataframe(df[FEATURES + ["final_marks"]].describe().round(2))

    a, b = st.columns(2)
    a.plotly_chart(px.histogram(df, x="final_marks", nbins=15, title="Marks distribution"),
                   use_container_width=True)
    b.plotly_chart(px.box(df, x="department", y="final_marks", color="department",
                          title="Marks by department"), use_container_width=True)
    c, d = st.columns(2)
    c.plotly_chart(px.scatter(df, x="attendance", y="final_marks", color="result",
                              trendline="ols" if len(df) > 2 else None,
                              title="Attendance vs Marks"), use_container_width=True)
    d.plotly_chart(px.pie(df, names="result", title="Pass / Fail ratio", hole=0.4),
                   use_container_width=True)

    st.subheader("🏆 Top 5 students")
    st.dataframe(df.sort_values("final_marks", ascending=False).head(5)[
        ["roll_no", "name", "department", "final_marks"]], hide_index=True)


def student_form(defaults=None, key="add"):
    d = defaults or {}
    with st.form(key):
        c1, c2 = st.columns(2)
        roll = c1.text_input("Roll No", d.get("roll_no", ""), disabled=bool(defaults))
        name = c2.text_input("Name", d.get("name", ""))
        email = c1.text_input("Email", d.get("email", ""))
        depts = ["CE", "IT", "ME", "EC", "EE"]
        dept = c2.selectbox("Department", depts,
                            index=depts.index(d["department"]) if d.get("department") in depts else 0)
        sem = c1.number_input("Semester", 1, 8, int(d.get("semester", 1)))
        att = c2.number_input("Attendance %", 0.0, 100.0, float(d.get("attendance", 75.0)))
        internal = c1.number_input("Internal marks", 0.0, 100.0, float(d.get("internal_marks", 50.0)))
        assign = c2.number_input("Assignment score", 0.0, 100.0, float(d.get("assignment_score", 50.0)))
        final = st.number_input("Final marks", 0.0, 100.0, float(d.get("final_marks", 50.0)))
        ok = st.form_submit_button("Save")
    return ok, roll, name, email, dept, sem, att, internal, assign, final


def page_add():
    st.header("➕ Add Student")
    ok, roll, name, email, dept, sem, att, internal, assign, final = student_form(key="add")
    if ok:
        if not roll.strip() or not name.strip():
            st.error("Roll No and Name are required.")
        elif add_student((roll.strip(), name.strip(), email, dept, sem, att, internal, assign, final)):
            st.success(f"Added {name}.")
        else:
            st.error("Roll No already exists.")


def page_manage(df):
    st.header("🗂️ Manage Students")
    if df.empty:
        st.info("No students yet.")
        return
    q = st.text_input("🔍 Search by name or roll no")
    view = df[df["name"].str.contains(q, case=False) | df["roll_no"].str.contains(q, case=False)] if q else df
    dept = st.multiselect("Filter by department", sorted(df["department"].dropna().unique()))
    if dept:
        view = view[view["department"].isin(dept)]
    sort_col = st.selectbox("Sort by", ["roll_no", "name", "final_marks", "attendance"])
    st.dataframe(view.sort_values(sort_col), hide_index=True, use_container_width=True)

    st.subheader("Edit / Delete")
    pick = st.selectbox("Select student", df["roll_no"] + " - " + df["name"])
    row = df[df["roll_no"] == pick.split(" - ")[0]].iloc[0]
    ok, _, name, email, dept_, sem, att, internal, assign, final = student_form(row.to_dict(), "edit")
    if ok:
        update_student(int(row["id"]), (name, email, dept_, sem, att, internal, assign, final))
        st.success("Updated. Refresh the table by interacting with the page.")
    if st.button("🗑️ Delete this student"):
        delete_student(int(row["id"]))
        st.warning("Deleted.")
        st.rerun()


def grade_of(m):
    for cut, g in [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C"), (40, "D")]:
        if m >= cut:
            return g
    return "F"


def make_report_card(row, rank, total):
    """Create a PDF report card in memory and return its bytes."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, "Student Report Card", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 12)
    lines = [
        ("Roll No", row["roll_no"]), ("Name", row["name"]),
        ("Department", row["department"]), ("Semester", int(row["semester"])),
        ("Attendance", f"{row['attendance']:.1f}%"),
        ("Internal marks", f"{row['internal_marks']:.1f}"),
        ("Assignment score", f"{row['assignment_score']:.1f}"),
        ("Final marks", f"{row['final_marks']:.1f}"),
        ("Grade", grade_of(row["final_marks"])),
        ("Class rank", f"{rank} of {total}"),
        ("Result", "PASS" if row["final_marks"] >= PASS_MARK else "FAIL"),
    ]
    for label, value in lines:
        pdf.cell(60, 10, label, border=1)
        pdf.cell(0, 10, str(value), border=1, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def page_report(df):
    st.header("🎓 Grades, Ranks & Report Card")
    if df.empty:
        st.info("No students yet.")
        return
    df = df.copy()
    df["grade"] = df["final_marks"].apply(grade_of)
    df["rank"] = df["final_marks"].rank(ascending=False, method="min").astype(int)

    order = ["A+", "A", "B+", "B", "C", "D", "F"]
    counts = df["grade"].value_counts().reindex(order, fill_value=0).reset_index()
    counts.columns = ["grade", "students"]
    st.plotly_chart(px.bar(counts, x="grade", y="students", color="grade",
                           title="Grade distribution"), use_container_width=True)

    st.subheader("Leaderboard")
    st.dataframe(df.sort_values("rank")[["rank", "roll_no", "name", "department",
                                         "final_marks", "grade"]], hide_index=True,
                 use_container_width=True)

    st.subheader("Download report card")
    pick = st.selectbox("Select student", df["roll_no"] + " - " + df["name"], key="rc")
    row = df[df["roll_no"] == pick.split(" - ")[0]].iloc[0]
    c1, c2 = st.columns(2)
    c1.metric("Grade", row["grade"])
    c2.metric("Class rank", f"{row['rank']} / {len(df)}")
    st.download_button("📄 Download PDF report card",
                       make_report_card(row, row["rank"], len(df)),
                       f"{row['roll_no']}_report_card.pdf", "application/pdf")


def page_export(df):
    st.header("📥 Export Reports")
    if df.empty:
        st.info("Nothing to export.")
        return
    st.download_button("Download CSV", df.to_csv(index=False), "students.csv", "text/csv")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Students")
    st.download_button("Download Excel", buf.getvalue(), "students.xlsx")


# ------------------------------- Main -------------------------------------
def main():
    st.set_page_config("Student Management System", "🎓", layout="wide")
    init_db()

    if not st.session_state.get("auth"):
        st.title("🎓 Student Management System")
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if check_login(u, p):
                    st.session_state["auth"] = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        st.caption("Default login: admin / admin123")
        return

    st.sidebar.title("🎓 SMS")
    page = st.sidebar.radio("Menu", ["Dashboard", "Add Student", "Manage Students",
                                     "Report Card", "Export"])
    if st.sidebar.button("Load 60 sample students"):
        st.sidebar.success(f"Added {load_sample_data()} students.")
    if st.sidebar.button("Logout"):
        st.session_state["auth"] = False
        st.rerun()

    df = load_df()
    {"Dashboard": lambda: page_dashboard(df), "Add Student": page_add,
     "Manage Students": lambda: page_manage(df), "Report Card": lambda: page_report(df),
     "Export": lambda: page_export(df)}[page]()


if __name__ == "__main__":
    main()
