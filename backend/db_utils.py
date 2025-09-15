import mysql.connector
from config import DB_CONFIG
import pandas as pd
from config import DB_CONFIG
from datetime import timedelta

def check_user(username, password):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)  # ✅ dict cursor
    cursor.execute("SELECT * FROM users WHERE username=%s AND userpassword=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def insert_data(particular_name, date, mu, rate):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    particular_id = get_or_create_particular(particular_name)

    cursor.execute("""
        INSERT INTO data (particular_id, date, mu, rate)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE mu=VALUES(mu), rate=VALUES(rate)
    """, (particular_id, date, float(mu), float(rate)))

    conn.commit()
    cursor.close()
    conn.close()

def insert_log(username, action, details=None):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO log (username, action, details) VALUES (%s, %s, %s)",
        (username, action, details)
    )
    conn.commit()
    cursor.close()
    conn.close()



def get_data_by_range(start_date, end_date):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, p.name, d.date, d.mu, d.rate
        FROM data d
        JOIN particulars p ON d.particular_id = p.id
        WHERE d.date BETWEEN %s AND %s
        ORDER BY p.name, d.date
    """, (start_date, end_date))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_data_by_date(start_date):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, p.pname, d.date, d.mu, d.rate
        FROM data d
        JOIN particulars p ON d.particular_id = p.id
        WHERE d.date=%s
        ORDER BY p.id
    """, [start_date])
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def update_data(row_id, mu, rate):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE data SET mu=%s, rate=%s WHERE id=%s",
        (float(mu), float(rate), int(row_id))
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_or_create_particular(particular_name):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Look for pname instead of name
    cursor.execute("SELECT id FROM particulars WHERE pname=%s", (particular_name,))
    result = cursor.fetchone()

    if result:
        particular_id = result[0]
    else:
        cursor.execute("INSERT INTO particulars (pname) VALUES (%s)", (particular_name,))
        conn.commit()
        particular_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return particular_id



def get_moving_average(window_size: int, target_date: str):
    """
    For a given target date, compute the moving average using the previous N days.
    If any of those required dates is missing, return warning and skip calculation.
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT d.date, d.mu, d.rate, p.pname AS particular
        FROM data d
        JOIN particulars p ON d.particular_id = p.id
        WHERE d.date <= %s
        ORDER BY d.date, p.pname
    """, (target_date,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return {}, [target_date]

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    target_datetime = pd.to_datetime(target_date)

    # Required dates = strictly the N previous days (not including target date)
    required_dates = [(target_datetime - timedelta(days=i)).normalize() for i in range(1, window_size + 1)]
    required_dates = list(reversed(required_dates))  # oldest → newest

    result = {}
    missing_dates = []

    for pname, group in df.groupby("particular"):
        group = group.sort_values("date").copy()

        # Extract rows only for required dates
        sub = group[group["date"].isin(required_dates)]

        # Check if all required dates are present
        if len(sub) != window_size:
            # Figure out which dates are missing
            available = set(sub["date"].dt.normalize())
            for d in required_dates:
                if d not in available and d.strftime("%Y-%m-%d") not in missing_dates:
                    missing_dates.append(d.strftime("%Y-%m-%d"))
            # Skip calculation for this particular
            result[pname] = {"mu_avg": None, "rate_avg": None}
        else:
            mu_avg = sub["mu"].mean()
            rate_avg = sub["rate"].mean()
            result[pname] = {"mu_avg": float(mu_avg), "rate_avg": float(rate_avg)}

    return result, sorted(missing_dates)
