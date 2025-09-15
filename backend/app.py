#Importing libraries
from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import init_db
from db_utils import check_user, insert_data, get_data_by_range,update_data, get_data_by_date, insert_log, get_moving_average
import os
import mysql.connector
from config import DB_CONFIG

import pandas as pd
from flask import send_file
import io



#Path to frontend templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "frontend", "templates")
app = Flask(__name__, template_folder=TEMPLATE_DIR,static_folder=os.path.join(BASE_DIR, "frontend", "static"),static_url_path="/static" ) # URL path for browser)
app.secret_key = "supersecret"

# Initialize tables if not exist
init_db()

#routing to respective pages

@app.route("/export", methods=["POST"])
def export():
    if "table" not in session:  # store last generated table in session
        flash("No table available to export!", "danger")
        return redirect(url_for("dashboard"))

    table = session["table"]

    # Build dataframe in same format as dashboard
    data = []
    for p in table["particulars"]:
        row = [p]
        for d in table["dates"]:
            row.append(table["data"][p][d]["mu"])
            row.append(table["data"][p][d]["rate"])
        data.append(row)

    # Build column headers
    cols = ["Particular"]
    for d in table["dates"]:
        cols.extend([f"{d} MU", f"{d} Rate"])

    df = pd.DataFrame(data, columns=cols)

    # Export to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dashboard")

    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name="dashboard.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


#login page routing
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = check_user(username, password)
        if user:
            session["user"] = user["username"]
            session["role"] = user["userrole"] 
            if user["userrole"] == "admin":
                return redirect(url_for("insert"))
            else:
                return redirect(url_for("dashboard"))
            
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/insert", methods=["GET", "POST"])
def insert():
    if "user" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, pname FROM particulars ORDER BY id")
    particulars = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == "POST":
        date = request.form.get("date")

        for p in particulars:
            mu = request.form.get(f"mu_{p['id']}") or "0"
            rate = request.form.get(f"rate_{p['id']}") or "0"

            if mu and rate:  # only insert if values given
                insert_data(p["pname"], date, mu, rate)
        insert_log(session["user"], "insert",f"Inserted for {date}")


        flash("Data has been successfully inserted!", "success")
        return redirect(url_for("insert"))

    return render_template("insert.html", particulars=particulars)


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    table = None
    if request.method == "GET" and "view_all" in request.args:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)


        query = """
            SELECT d.date, d.mu, d.rate, p.pname AS particular
            FROM data d
            JOIN particulars p ON d.particular_id = p.id
            ORDER BY d.date, p.pname
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if rows:
            # unique sorted dates
            dates = sorted(set(row["date"].strftime("%Y-%m-%d") for row in rows))
            # unique sorted particulars
            particulars = sorted(set(row["particular"] for row in rows))

            # structure: {particular: {date: {"mu": val, "rate": val}}}
            data = {p: {d: {"mu": "", "rate": ""} for d in dates} for p in particulars}

            for row in rows:
                date_str = row["date"].strftime("%Y-%m-%d")
                data[row["particular"]][date_str] = {
                    "mu": row["mu"],
                    "rate": row["rate"],
                }

            table = {
                "dates": dates,
                "particulars": particulars,
                "data": data,
            }
            session["table"] = table  # save for export
        else:
            session.pop("table", None)
    


    # build table same way as before...
    # ---- Moving Average ----
    average_data = {}
    missing_dates = []
    selected_window = None
    selected_date = None

    if request.method == "POST" and "moving_avg" in request.form:
        selected_window = int(request.form.get("moving_avg_days"))
        selected_date = request.form.get("date")
        average_data, missing_dates = get_moving_average(selected_window, selected_date)

    if request.method == "POST" and "date_range" in request.form:
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT d.date, d.mu, d.rate, p.pname AS particular
            FROM data d
            JOIN particulars p ON d.particular_id = p.id
            WHERE d.date BETWEEN %s AND %s
            ORDER BY d.date, p.pname
        """
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if rows:
            # unique sorted dates
            dates = sorted(set(row["date"].strftime("%Y-%m-%d") for row in rows))
            # unique sorted particulars
            particulars = sorted(set(row["particular"] for row in rows))

            # structure: {particular: {date: {"mu": val, "rate": val}}}
            data = {p: {d: {"mu": "", "rate": ""} for d in dates} for p in particulars}

            for row in rows:
                date_str = row["date"].strftime("%Y-%m-%d")
                data[row["particular"]][date_str] = {
                    "mu": row["mu"],
                    "rate": row["rate"],
                }

            table = {
                "dates": dates,
                "particulars": particulars,
                "data": data,
            }
            session["table"] = table  # save for export
        else:
            session.pop("table", None)

    # ---- Always fetch logs ----
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT logid, username, action, details, datetime FROM log ORDER BY datetime DESC LIMIT 100")
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    print("Logs fetched:", logs)

    return render_template(
    "dashboard.html",
    table=table,
    logs=logs,
    average_data=average_data,
    selected_window=selected_window,
    selected_date=selected_date,
    missing_dates=missing_dates,
)


@app.route("/edit", methods=["GET", "POST"])
def edit():
    if "user" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    
    rows = []
    selected_date = ""

    if request.method == "POST":
        selected_date = request.form.get("date")

        # 1️⃣ Add new particular
        if "add_particular" in request.form:
            new_pname = request.form.get("new_pname")
            if new_pname:
                conn = mysql.connector.connect(**DB_CONFIG)
                cursor = conn.cursor()

                # Insert into particulars
                cursor.execute("INSERT INTO particulars (pname) VALUES (%s)", (new_pname,))
                insert_log(session["user"], "new_particular", f"Added particular '{new_pname}'")

                conn.commit()
                new_particular_id = cursor.lastrowid

                # Get all distinct dates already present in data
                cursor.execute("SELECT DISTINCT date FROM data")
                all_dates = cursor.fetchall()

                # Insert rows with default 0.0 mu, rate for each date
                for (d,) in all_dates:
                    cursor.execute(
                        "INSERT INTO data (particular_id, date, mu, rate) VALUES (%s, %s, %s, %s)",
                        (new_particular_id, d, 0.0, 0.0)
                        
                    )
                    


                conn.commit()
                cursor.close()
                conn.close()
                flash(f"New particular '{new_pname}' added successfully with default values!", "success")
            return redirect(url_for("edit"))

        # 2️⃣ Fetch rows for selected date
        elif "fetch_date" in request.form and selected_date:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT d.id, p.pname, d.mu, d.rate
                FROM data d
                JOIN particulars p ON d.particular_id = p.id
                WHERE d.date = %s
                ORDER BY p.pname
            """, (selected_date,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

        # 3️⃣ Update rows
        elif "update_data" in request.form:
            for key, value in request.form.items():
                if key.startswith("mu_"):
                    row_id = key.split("_")[1]
                    mu = value
                    rate = request.form.get(f"rate_{row_id}")
                    update_data(row_id, mu, rate)
            insert_log(session["user"], "edit", f"Edited data for {selected_date}")
            flash("Data has been successfully updated!", "success")
            return redirect(url_for("edit"))

    return render_template("edit.html", rows=rows, selected_date=selected_date)


#Logout page routing
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
