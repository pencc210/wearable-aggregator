import requests
import streamlit as st
from datetime import date, timedelta

BASE_URL = "https://worker-health-aggregator.onrender.com"

st.set_page_config(page_title="Worker Health Dashboard", layout="wide")
st.title("Worker Health — Company Aggregate Dashboard")
st.caption("Aggregated bucket counts only (no individual data).")

# --------------------------
# Helpers
# --------------------------
def fetch_counts(day_str: str):
    url = f"{BASE_URL}/counts/{day_str}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def totals_for_metric(day_data, metric, keys):
    m = day_data.get(metric, {})
    total = sum(safe_int(m.get(k, 0)) for k in keys)
    return total

def pct(part, whole):
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 1)

def show_metric_block(day_data, metric, expected_keys, title):
    st.subheader(title)
    counts = day_data.get(metric, {})

    rows = []
    total = 0
    for k in expected_keys:
        v = safe_int(counts.get(k, 0))
        rows.append({"Bucket": k, "Count": v})
        total += v

    st.write(f"Total submissions counted: **{total}**")

    # Counts table
    st.table(rows)

    # Percentage table
    if total > 0:
        perc_rows = [{"Bucket": k, "Percent (%)": pct(safe_int(counts.get(k, 0)), total)} for k in expected_keys]
        st.markdown("**Distribution (% of workforce):**")
        st.table(perc_rows)

    # Chart (counts)
    st.markdown("**Counts chart:**")
    st.bar_chart({row["Bucket"]: row["Count"] for row in rows})

def trend_total(days_list, metric):
    trend = {}
    for ds in days_list:
        try:
            dd = fetch_counts(ds)
            metric_map = dd.get(metric, {})
            trend[ds] = sum(safe_int(v) for v in metric_map.values())
        except Exception:
            trend[ds] = 0
    return trend

# --------------------------
# Controls (top)
# --------------------------
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    d = st.date_input("Select day", value=date.today())
with col2:
    last_days = st.selectbox("Trend window", ["7 days", "14 days", "30 days"], index=0)
with col3:
    st.write("")

days_n = {"7 days": 7, "14 days": 14, "30 days": 30}[last_days]
days = [(d - timedelta(days=i)).isoformat() for i in range(days_n)]
days.reverse()

day_str = d.isoformat()

# --------------------------
# Server status (optional)
# --------------------------
with st.expander("Server status"):
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=20)
        st.write("Health response:", r.json())
    except Exception as e:
        st.error(f"Health check failed: {e}")

# --------------------------
# Fetch selected day
# --------------------------
try:
    data = fetch_counts(day_str)
except Exception as e:
    st.error(f"Failed to fetch counts for {day_str}: {e}")
    st.stop()

if not data:
    st.info("No data for this day (or the server restarted).")
    st.caption("Note: on this hosting tier, counts can reset after server restarts (no guaranteed persistent disk).")
    st.stop()

# --------------------------
# Bucket definitions (interpretation)
# You can adjust these later if you change bucket meanings.
# --------------------------
P_KEYS = ["P0", "P1", "P2", "P3", "P4"]
L_KEYS = ["L0", "L1", "L2", "L3", "L4"]
B_KEYS = ["B0", "B1", "B2", "B3"]
C_KEYS = ["C0", "C1", "C2", "C3", "C4"]

# "Executive" groupings (simple, interpretable)
# Posture: higher risk = P3 + P4
P_HIGH = ["P3", "P4"]

# Light (dim): "meaningfully underlit" = L2+ (>= 60 min/day under 300 lux)
L_UNDERLIT = ["L2", "L3", "L4"]

# Very bright: "high bright exposure" = B2 + B3 (>= 60 min/day >=1000 lux)
B_TOO_BRIGHT = ["B2", "B3"]

# Breaks: "good compliance" = C3 + C4 (>= 75% acknowledged)
C_GOOD = ["C3", "C4"]

# Compute totals for day
total_P = totals_for_metric(data, "P", P_KEYS)
total_L = totals_for_metric(data, "L", L_KEYS)
total_B = totals_for_metric(data, "B", B_KEYS)
total_C = totals_for_metric(data, "C", C_KEYS)

# Use a single "submission count" for top KPI:
# Ideally all metrics have same total. We’ll take the max to be safe.
total_submissions = max(total_P, total_L, total_B, total_C)

# Compute KPI rates
p_high_count = sum(safe_int(data.get("P", {}).get(k, 0)) for k in P_HIGH)
l_under_count = sum(safe_int(data.get("L", {}).get(k, 0)) for k in L_UNDERLIT)
b_bright_count = sum(safe_int(data.get("B", {}).get(k, 0)) for k in B_TOO_BRIGHT)
c_good_count = sum(safe_int(data.get("C", {}).get(k, 0)) for k in C_GOOD)

p_high_pct = pct(p_high_count, total_P if total_P > 0 else total_submissions)
l_under_pct = pct(l_under_count, total_L if total_L > 0 else total_submissions)
b_bright_pct = pct(b_bright_count, total_B if total_B > 0 else total_submissions)
c_good_pct = pct(c_good_count, total_C if total_C > 0 else total_submissions)

# --------------------------
# Tabs
# --------------------------
tab_home, tab_posture, tab_light, tab_breaks = st.tabs(["Home", "Posture", "Light", "Breaks"])

with tab_home:
    st.subheader(f"Executive summary — {day_str}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total submissions", f"{total_submissions}")
    c2.metric("Higher posture risk (P3+P4)", f"{p_high_pct}%")
    c3.metric("Underlit (L2+)", f"{l_under_pct}%")
    c4.metric("Very bright (B2+B3)", f"{b_bright_pct}%")
    c5.metric("Good break compliance (C3+C4)", f"{c_good_pct}%")

    st.markdown("### Quick interpretation")
    st.write(
        "- **Higher posture risk (P3+P4)**: share of submissions in the most concerning posture buckets.\n"
        "- **Underlit (L2+)**: share of submissions with sustained time under recommended light threshold (per your bucket definition).\n"
        "- **Very bright (B2+B3)**: share with prolonged very bright exposure (potential glare/visual discomfort).\n"
        "- **Good break compliance (C3+C4)**: share with high acknowledgement of break reminders."
    )

    st.markdown("### Trends (total submissions received)")
    st.line_chart(trend_total(days, "P"))

    st.caption(
        "Note: On this hosting tier, counts may reset after server restarts (no guaranteed persistent disk). "
        "Production solution: Postgres or managed DB."
    )

with tab_posture:
    show_metric_block(data, "P", P_KEYS, "Posture risk buckets (P)")
    st.markdown("### Trend (total posture submissions)")
    st.line_chart(trend_total(days, "P"))

    st.markdown("### Key KPI")
    st.write(f"**Higher posture risk (P3+P4): {p_high_pct}%** ({p_high_count}/{total_P if total_P>0 else total_submissions})")

with tab_light:
    st.markdown("## Light exposure")

    show_metric_block(data, "L", L_KEYS, "Insufficient light exposure buckets (L)")
    st.write(f"**Underlit (L2+): {l_under_pct}%** ({l_under_count}/{total_L if total_L>0 else total_submissions})")
    st.line_chart(trend_total(days, "L"))

    st.divider()

    show_metric_block(data, "B", B_KEYS, "Very bright exposure buckets (B)")
    st.write(f"**Very bright (B2+B3): {b_bright_pct}%** ({b_bright_count}/{total_B if total_B>0 else total_submissions})")
    st.line_chart(trend_total(days, "B"))

with tab_breaks:
    show_metric_block(data, "C", C_KEYS, "Break compliance buckets (C)")
    st.markdown("### Key KPI")
    st.write(f"**Good break compliance (C3+C4): {c_good_pct}%** ({c_good_count}/{total_C if total_C>0 else total_submissions})")

    st.markdown("### Trend (total break submissions)")
    st.line_chart(trend_total(days, "C"))