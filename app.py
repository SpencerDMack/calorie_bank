from __future__ import annotations

import datetime as dt
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database as db

st.set_page_config(page_title="Calorie Bank", layout="wide")


db.create_tables()


st.title("Calorie Bank")

# Sidebar: Profile setup
st.sidebar.header("Profile Setup")
profile = db.get_profile()

activity_options = [
    ("Sedentary (1.2) - little or no exercise", 1.2),
    ("Light (1.375) - light exercise 1-3 days/week", 1.375),
    ("Moderate (1.55) - moderate exercise 3-5 days/week", 1.55),
    ("Very Active (1.725) - hard exercise 6-7 days/week", 1.725),
]

if profile:
    default_age = int(profile["age"])
    default_gender = profile["gender"]
    default_height = float(profile["height_cm"])
    default_weight = float(profile["weight_lbs"])
    default_activity = float(profile["activity_level"])
    default_goal_type = profile.get("goal_type") or "Lose"
    default_target_weight = (
        float(profile["target_weight_lbs"])
        if profile.get("target_weight_lbs") is not None
        else default_weight
    )
else:
    default_age = 30
    default_gender = "Male"
    default_height = 170.0
    default_weight = 170.0
    default_activity = 1.2
    default_goal_type = "Lose"
    default_target_weight = default_weight

age = st.sidebar.number_input("Age", min_value=10, max_value=120, value=default_age, step=1)

if default_gender.lower() == "female":
    gender_index = 1
else:
    gender_index = 0

gender = st.sidebar.selectbox("Gender", ["Male", "Female"], index=gender_index)

# Unit system toggle (affects both height and weight)
unit_system = st.sidebar.radio("Units", ["Imperial", "Metric"], horizontal=True)

if unit_system == "Metric":
    default_height_cm = int(round(default_height))
    default_weight_kg = round(calc.lbs_to_kg(default_weight), 1)
    default_target_kg = int(round(calc.lbs_to_kg(default_target_weight)))
    height_cm = st.sidebar.number_input(
        "Height (cm)", min_value=100, max_value=250, value=default_height_cm, step=1
    )
    weight_kg = st.sidebar.number_input(
        "Weight (kg)", min_value=35.0, max_value=250.0, value=default_weight_kg, step=0.1
    )
    weight_lbs = calc.kg_to_lbs(weight_kg)
else:
    total_inches = int(round(default_height / 2.54))
    default_feet = total_inches // 12
    default_inches = total_inches % 12
    feet_col, inch_col = st.sidebar.columns(2)
    height_feet = feet_col.number_input(
        "Height (ft)", min_value=3, max_value=8, value=default_feet, step=1
    )
    height_inches = inch_col.number_input(
        "Height (in)", min_value=0, max_value=11, value=default_inches, step=1
    )
    height_cm = calc.feet_in_to_cm(height_feet, height_inches)
    weight_lbs = st.sidebar.number_input(
        "Weight (lbs)", min_value=80.0, max_value=500.0, value=round(default_weight, 1), step=0.1
    )

st.sidebar.subheader("Goal")
goal_type = st.sidebar.selectbox("Goal Type", ["Lose", "Gain"], index=0 if default_goal_type == "Lose" else 1)
if unit_system == "Metric":
    target_weight_kg = st.sidebar.number_input(
        "Target Weight (kg)", min_value=35, max_value=250, value=default_target_kg, step=1
    )
    target_weight_lbs = calc.kg_to_lbs(target_weight_kg)
else:
    target_weight_lbs = st.sidebar.number_input(
        "Target Weight (lbs)", min_value=80, max_value=500, value=int(round(default_target_weight)), step=1
    )

activity_labels = [label for label, _ in activity_options]
activity_values = [value for _, value in activity_options]
if default_activity in activity_values:
    activity_index = activity_values.index(default_activity)
else:
    activity_index = 0

activity_label = st.sidebar.selectbox("Activity Level", activity_labels, index=activity_index)
activity_multiplier = dict(activity_options)[activity_label]

if st.sidebar.button("Save Profile"):
    weight_kg = calc.lbs_to_kg(weight_lbs)
    bmr = calc.bmr_mifflin_st_jeor(weight_kg, height_cm, int(age), gender)
    maintenance = calc.maintenance_calories(bmr, activity_multiplier)
    db.save_profile(
        int(age),
        gender,
        height_cm,
        weight_lbs,
        activity_multiplier,
        maintenance,
        goal_type,
        target_weight_lbs,
    )
    db.update_all_daily_balances(maintenance)
    st.sidebar.success("Profile saved.")
    profile = db.get_profile()
    st.rerun()


if not profile:
    st.info("Set up your profile in the sidebar to begin logging calories.")
    st.stop()

maintenance = float(profile["maintenance_calories"])
starting_weight = float(profile["weight_lbs"])
goal_type = profile.get("goal_type") or "Lose"

tab_dashboard, tab_entries = st.tabs(["Dashboard", "Entries"])

with tab_dashboard:
    # Pull logs
    logs_df = db.get_daily_logs()
    if not logs_df.empty:
        logs_df = logs_df.sort_values("date")
        running_balance = float(logs_df["running_balance"].iloc[-1])
    else:
        running_balance = 0.0

    estimated_weight = calc.estimated_weight(starting_weight, running_balance)
    bank_balance = running_balance if goal_type == "Lose" else -running_balance

    # Profile summary metrics
    st.subheader("Profile Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Maintenance Calories", f"{maintenance:,.0f}")
    col2.metric("Starting Weight (lbs)", f"{starting_weight:,.1f}")
    col3.metric("Estimated Current Weight (lbs)", f"{estimated_weight:,.1f}")
    balance_color = "forestgreen" if bank_balance >= 0 else "firebrick"
    col4.markdown(
        f"""
        <div style="font-size:0.9rem; color:white;">Calorie Bank Balance</div>
        <div style="font-size:2rem; font-weight:700; color:{balance_color};">
            {bank_balance:,.0f}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Balance increases when you align with your goal: deficit for Lose, surplus for Gain."
    )

    # Goal progress
    target_weight = (
        float(profile["target_weight_lbs"])
        if profile.get("target_weight_lbs") is not None
        else starting_weight
    )
    # Streak: consecutive logged days meeting goal
    streak_days = 0
    if not logs_df.empty:
        streak_df = logs_df.copy()
        streak_df["date"] = pd.to_datetime(streak_df["date"]).dt.date
        streak_df = streak_df.sort_values("date")
        if goal_type == "Lose":
            streak_df["goal_met"] = streak_df["daily_balance"] >= 0
        else:
            streak_df["goal_met"] = streak_df["daily_balance"] <= 0

        last_row = streak_df.iloc[-1]
        if last_row["goal_met"]:
            streak_days = 1
            current_date = last_row["date"]
            for _, row in streak_df.iloc[:-1].iloc[::-1].iterrows():
                expected_date = current_date - dt.timedelta(days=1)
                if row["date"] != expected_date or not row["goal_met"]:
                    break
                streak_days += 1
                current_date = row["date"]
    goal_calories = abs(starting_weight - target_weight) * 3500.0
    remaining_calories = max(0.0, goal_calories - max(0.0, bank_balance))
    avg_daily_progress = None
    if not logs_df.empty:
        recent = logs_df.tail(7)
        if goal_type == "Lose":
            daily_progress = recent["daily_balance"]
        else:
            daily_progress = -recent["daily_balance"]
        avg_daily_progress = float(daily_progress.mean())
    total_weight_change = abs(starting_weight - target_weight)
    current_weight_change = abs(starting_weight - estimated_weight)
    weight_progress = 0.0 if total_weight_change == 0 else min(1.0, current_weight_change / total_weight_change)

    st.subheader("Goal Progress")
    st.caption(f"Target Weight: {target_weight:,.1f} lbs ({goal_type})")
    if goal_type == "Lose" and target_weight >= starting_weight:
        st.warning("Goal type is set to Lose, but target weight is not lower than starting weight.")
    if goal_type == "Gain" and target_weight <= starting_weight:
        st.warning("Goal type is set to Gain, but target weight is not higher than starting weight.")
    prog_col, streak_col = st.columns([3, 1])
    with prog_col:
        st.progress(weight_progress, text=f"Weight progress: {weight_progress:.0%}")
    with streak_col:
        st.metric("On-goal streak (days)", f"{streak_days}")
    if goal_calories == 0:
        st.metric("Estimated days to goal", "0")
    elif avg_daily_progress is None:
        st.metric("Estimated days to goal", "Need more data")
    elif avg_daily_progress <= 0:
        st.metric("Estimated days to goal", "Not on track")
    else:
        days_left = max(0, math.ceil(remaining_calories / avg_daily_progress))
        st.metric("Estimated days to goal", f"{days_left}")
        st.caption("Based on your average over the last 7 entries.")

    # Daily entry
    st.subheader("Today's Entry")

    today = dt.date.today()

    existing_today_log = db.get_log_by_date(today.isoformat())
    pre_fill_calories = int(round(existing_today_log["calories_consumed"])) if existing_today_log else 0

    with st.form("daily_entry_form"):
        entry_date = st.date_input("Date", value=today)
        calories_consumed = st.number_input(
            "Calories consumed",
            min_value=0,
            max_value=10000,
            value=pre_fill_calories,
            step=1,
        )
        submitted = st.form_submit_button("Save Entry")

    if submitted:
        daily_bal = calc.daily_balance(maintenance, calories_consumed)
        db.upsert_daily_log(entry_date.isoformat(), calories_consumed, daily_bal)
        db.update_running_balances()
        st.success("Entry saved.")
        goal_adjusted = daily_bal if goal_type == "Lose" else -daily_bal
        change_color = "forestgreen" if goal_adjusted >= 0 else "firebrick"
        st.markdown(
            f"<div style='font-weight:700; color:{change_color};'>"
            f"Today's calorie bank change: {goal_adjusted:,.0f}"
            "</div>",
            unsafe_allow_html=True,
        )

    # Refresh logs after entry
    logs_df = db.get_daily_logs()

    if not logs_df.empty:
        logs_df = logs_df.sort_values("date")
        logs_df["date"] = pd.to_datetime(logs_df["date"])
        logs_df["estimated_weight"] = starting_weight - (logs_df["running_balance"] / 3500.0)

        st.subheader("Progress Over Time")

        fig_weight = go.Figure()
        fig_weight.add_trace(
            go.Scatter(
                x=logs_df["date"],
                y=logs_df["estimated_weight"],
                mode="lines+markers",
                name="Estimated Weight (lbs)",
            )
        )
        if total_weight_change > 0:
            for pct in [0.25, 0.5, 0.75]:
                milestone_weight = starting_weight + (target_weight - starting_weight) * pct
                fig_weight.add_hline(
                    y=milestone_weight,
                    line_dash="dot",
                    line_color="rgba(120,120,120,0.6)",
                    annotation_text=f"{int(pct * 100)}%",
                    annotation_position="top right",
                )
        fig_weight.update_layout(
            yaxis_title="Estimated Weight (lbs)",
            margin=dict(l=40, r=40, t=40, b=40),
        )
        tick_vals = logs_df["date"]
        tick_text = [d.strftime("%b %d, %Y") for d in tick_vals]
        fig_weight.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=tick_text)
        st.plotly_chart(fig_weight, use_container_width=True)
    else:
        st.info("No logs yet. Add your first entry to see progress.")

with tab_entries:
    st.subheader("All Entries")
    logs_df = db.get_daily_logs()
    if logs_df.empty:
        st.info("No entries to show yet.")
    else:
        logs_df = logs_df.sort_values("date")
        editor_df = logs_df[["date", "calories_consumed"]].copy()
        editor_df["calories_consumed"] = editor_df["calories_consumed"].round().astype(int)
        editor_df["delete"] = False

        edited_df = st.data_editor(
            editor_df,
            use_container_width=True,
            num_rows="fixed",
            disabled=["date"],
            column_config={
                "date": st.column_config.TextColumn("Date"),
                "calories_consumed": st.column_config.NumberColumn(
                    "Calories Consumed", min_value=0, max_value=10000, step=1
                ),
                "delete": st.column_config.CheckboxColumn("Delete"),
            },
        )

        def apply_edits(df: pd.DataFrame) -> None:
            for _, row in df.iterrows():
                date_str = row["date"]
                if row.get("delete"):
                    db.delete_daily_log(date_str)
                    continue
                calories = int(round(row["calories_consumed"]))
                daily_bal = calc.daily_balance(maintenance, calories)
                db.upsert_daily_log(date_str, calories, daily_bal)
            db.update_running_balances()
            st.success("Entries updated.")
            st.rerun()

        if st.button("Save Changes"):
            has_delete = bool(edited_df["delete"].any())
            if has_delete:
                st.session_state["pending_edits"] = edited_df.to_dict("records")
                st.session_state["show_delete_confirm"] = True
            else:
                apply_edits(edited_df)

        if st.session_state.get("show_delete_confirm"):
            pending_records = st.session_state.get("pending_edits", [])
            pending_df = pd.DataFrame(pending_records) if pending_records else pd.DataFrame()
            delete_count = int(pending_df["delete"].sum()) if not pending_df.empty else 0
            st.warning(f"This will permanently delete {delete_count} entries.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("Confirm delete"):
                    st.session_state.pop("show_delete_confirm", None)
                    st.session_state.pop("pending_edits", None)
                    apply_edits(pending_df)
            with col_cancel:
                if st.button("Cancel"):
                    st.session_state.pop("show_delete_confirm", None)
                    st.session_state.pop("pending_edits", None)
