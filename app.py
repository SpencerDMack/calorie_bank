from __future__ import annotations

import datetime as dt
import math

import numpy as np
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
    ("Little or no exercise", 1.2),
    ("Light exercise 1-3 days/week", 1.375),
    ("Moderate exercise 3-5 days/week", 1.55),
    ("Hard exercise 6-7 days/week", 1.725),
]

if profile:
    default_name = profile.get("name") or ""
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
    default_name = ""
    default_age = 30
    default_gender = "Male"
    default_height = 170.0
    default_weight = 170.0
    default_activity = 1.2
    default_goal_type = "Lose"
    default_target_weight = default_weight

name = st.sidebar.text_input("Name", value=default_name)
age = st.sidebar.number_input("Age", min_value=10, max_value=120, value=default_age, step=1)

if default_gender.lower() == "female":
    gender_index = 1
else:
    gender_index = 0

gender = st.sidebar.selectbox("Gender", ["Male", "Female"], index=gender_index)

# Height and weight (Imperial only)
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
    "Starting Weight (lbs)",
    min_value=80.0,
    max_value=500.0,
    value=round(default_weight, 1),
    step=0.1,
    format="%.1f",
)

st.sidebar.subheader("Goal")
goal_type = st.sidebar.selectbox("Goal Type", ["Lose", "Gain"], index=0 if default_goal_type == "Lose" else 1)
target_weight_lbs = st.sidebar.number_input(
    "Target Weight (lbs)",
    min_value=80,
    max_value=500,
    value=int(round(default_target_weight)),
    step=1,
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
    cleaned_name = name.strip() or None
    weight_kg = calc.lbs_to_kg(weight_lbs)
    bmr = calc.bmr_mifflin_st_jeor(weight_kg, height_cm, int(age), gender)
    maintenance = calc.maintenance_calories(bmr, activity_multiplier)
    db.save_profile(
        cleaned_name,
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

tab_dashboard, tab_entries, tab_simulation = st.tabs(["Dashboard", "Entries", "Simulation"])

with tab_dashboard:
    display_name = (profile.get("name") or "").strip()
    if display_name:
        st.markdown(f"### Welcome back, {display_name}!")
    else:
        st.markdown("### Welcome back!")
    # Pull logs
    logs_df = db.get_daily_logs()
    if not logs_df.empty:
        logs_df = logs_df.sort_values("date")
        running_balance = float(logs_df["running_balance"].iloc[-1])
    else:
        running_balance = 0.0

    estimated_weight = calc.estimated_weight(starting_weight, running_balance)
    bank_balance = running_balance if goal_type == "Lose" else -running_balance

    # Goal progress
    target_weight = (
        float(profile["target_weight_lbs"])
        if profile.get("target_weight_lbs") is not None
        else starting_weight
    )
    goal_calories = abs(starting_weight - target_weight) * 3500.0
    remaining_calories = max(0.0, goal_calories - max(0.0, bank_balance))
    avg_daily_progress = None
    if not logs_df.empty:
        recent_df = logs_df.copy()
        recent_df["date"] = pd.to_datetime(recent_df["date"]).dt.date
        last_date = recent_df["date"].max()
        month_start = last_date - dt.timedelta(days=29)
        recent = recent_df[
            (recent_df["date"] >= month_start) & (recent_df["date"] <= last_date)
        ]
        if goal_type == "Lose":
            daily_progress = recent["daily_balance"]
        else:
            daily_progress = -recent["daily_balance"]
        avg_daily_progress = float(daily_progress.mean())
    total_weight_change = abs(starting_weight - target_weight)
    current_weight_change = abs(starting_weight - estimated_weight)
    weight_progress = 0.0 if total_weight_change == 0 else min(1.0, current_weight_change / total_weight_change)
    if logs_df.empty or bank_balance <= 0:
        weight_progress = 0.0

    days_left = None
    estimated_days_total = None
    if goal_calories == 0:
        days_left = 0
        estimated_days_total = 0
    elif avg_daily_progress is None:
        days_left = None
        estimated_days_total = None
    elif avg_daily_progress <= 0:
        days_left = None
        estimated_days_total = None
    else:
        days_left = max(0, math.ceil(remaining_calories / avg_daily_progress))
        estimated_days_total = max(1, math.ceil(goal_calories / avg_daily_progress))

    left_col, right_col = st.columns([2, 1])

    if goal_calories == 0:
        days_text = "0"
    elif avg_daily_progress is None:
        days_text = "Need more data"
    elif avg_daily_progress <= 0:
        days_text = "Not on track"
    else:
        days_text = f"{days_left}"

    with left_col:
        st.subheader("Goal Progress")
        if goal_type == "Lose" and target_weight >= starting_weight:
            st.warning("Goal type is set to Lose, but target weight is not lower than starting weight.")
        if goal_type == "Gain" and target_weight <= starting_weight:
            st.warning("Goal type is set to Gain, but target weight is not higher than starting weight.")

        st.caption(f"Target Weight: {target_weight:,.1f} lbs ({goal_type})")
        if estimated_days_total and estimated_days_total > 0:
            segments = int(estimated_days_total)
            progress_ratio = (
                0
                if estimated_days_total == 0
                else (estimated_days_total - days_left) / estimated_days_total
            )
            filled_segments = int(math.floor(progress_ratio * segments))
            filled_segments = max(0, min(segments, filled_segments))

            segment_blocks = []
            for idx in range(segments):
                is_filled = idx < filled_segments
                color = "forestgreen" if is_filled else "#E0E0E0"
                segment_blocks.append(
                    f"<span style='width:6px; height:12px; background:{color}; border-radius:0;'></span>"
                )

            bar_html = (
                "<div style='display:flex; align-items:center; gap:2px; overflow-x:auto; padding-bottom:4px;'>"
                f"{''.join(segment_blocks)}"
                "</div>"
            )
            st.markdown(bar_html, unsafe_allow_html=True)
            st.caption(f"Weight progress: {weight_progress:.0%}")
        else:
            st.progress(weight_progress, text=f"Weight progress: {weight_progress:.0%}")

        st.metric("Estimated days to goal", days_text)
        if goal_calories > 0 and avg_daily_progress is not None and avg_daily_progress > 0:
            st.caption("Based on your average over the last 30 days.")

    with right_col:
        st.subheader("Profile Summary")
        col1, col2 = st.columns(2)
        col1.metric("Maintenance Calories", f"{maintenance:,.0f}")
        col2.metric("Starting Weight (lbs)", f"{starting_weight:,.1f}")
        col3, col4 = st.columns(2)
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

        # Daily entry
        st.subheader("Today's Entry")

        if st.session_state.pop("entry_saved", False):
            st.success("Entry saved.")
            goal_adjusted = float(st.session_state.pop("last_goal_adjusted", 0.0))
            change_color = "forestgreen" if goal_adjusted >= 0 else "firebrick"
            st.markdown(
                f"<div style='font-weight:700; color:{change_color};'>"
                f"Today's calorie bank change: {goal_adjusted:,.0f}"
                "</div>",
                unsafe_allow_html=True,
            )

        today = dt.date.today()

        if goal_type == "Lose":
            pre_fill_calories = int(math.floor(maintenance / 1000.0) * 1000)
        else:
            pre_fill_calories = int(math.ceil(maintenance / 1000.0) * 1000)
        pre_fill_note = ""

        with st.form("daily_entry_form"):
            entry_date = st.date_input(
                "Date",
                value=today,
                format="MM/DD/YYYY",
            )
            calories_consumed = st.number_input(
                "Calories consumed",
                min_value=0,
                max_value=10000,
                value=pre_fill_calories,
                step=1,
            )
            entry_note = st.text_area("Note (optional)", value=pre_fill_note, height=90)
            submitted = st.form_submit_button("Save Entry")

        if submitted:
            daily_bal = calc.daily_balance(maintenance, calories_consumed)
            cleaned_entry_note = entry_note.strip() or None
            db.upsert_daily_log(
                entry_date.isoformat(), calories_consumed, daily_bal, cleaned_entry_note
            )
            db.update_running_balances()
            st.session_state["entry_saved"] = True
            st.session_state["last_goal_adjusted"] = daily_bal if goal_type == "Lose" else -daily_bal
            st.rerun()

        st.subheader("Weekly Win")
        weekly_logs = db.get_daily_logs()
        if weekly_logs.empty:
            st.info("Log at least one day to see your weekly summary.")
        else:
            weekly_df = weekly_logs.copy()
            weekly_df["date"] = pd.to_datetime(weekly_df["date"]).dt.date
            first_log_date = weekly_df["date"].min()
            last_log_date = weekly_df["date"].max()
            week_starts = []
            current_week = first_log_date
            while current_week <= last_log_date:
                week_starts.append(current_week)
                current_week += dt.timedelta(days=7)
            default_index = len(week_starts) - 1
            current_week_start = week_starts[default_index]
            def _format_week_label(d: dt.date) -> str:
                prefix = "Current - " if d == current_week_start else ""
                return (
                    f"{prefix}{d.strftime('%b %d, %Y')} - "
                    f"{(d + dt.timedelta(days=6)).strftime('%b %d, %Y')}"
                )
            week_start = st.selectbox(
                "Week",
                week_starts,
                index=default_index,
                format_func=_format_week_label,
            )
            week_end_display = week_start + dt.timedelta(days=6)
            weekly_df = weekly_df[
                (weekly_df["date"] >= week_start) & (weekly_df["date"] <= week_end_display)
            ]

            if weekly_df.empty:
                st.info("No entries in the selected week yet.")
            else:
                if goal_type == "Lose":
                    summary_label = "Weekly deficit"
                    goal_adjusted = weekly_df["daily_balance"]
                    on_goal_days = int((weekly_df["daily_balance"] >= 0).sum())
                else:
                    summary_label = "Weekly surplus"
                    goal_adjusted = -weekly_df["daily_balance"]
                    on_goal_days = int((weekly_df["daily_balance"] <= 0).sum())

                total_goal = float(goal_adjusted.sum())
                avg_cals = float(weekly_df["calories_consumed"].mean())
                logged_days = int(weekly_df["date"].nunique())

                win_col1, win_col2, win_col3 = st.columns(3)
                win_col1.metric(summary_label, f"{total_goal:,.0f}")
                win_col2.metric("Avg calories", f"{avg_cals:,.0f}")
                win_col3.metric("On-goal days", f"{on_goal_days}/7")
                st.caption(
                    f"Week of {week_start.strftime('%b %d')} - {week_end_display.strftime('%b %d')}. "
                    f"Logged {logged_days} of 7 days."
                )

    # Refresh logs after entry
    logs_df = db.get_daily_logs()

    with left_col:
        if not logs_df.empty:
            logs_df = logs_df.sort_values("date")
            logs_df["date"] = pd.to_datetime(logs_df["date"])
            logs_df["estimated_weight"] = (
                starting_weight - (logs_df["running_balance"] / 3500.0)
            ).round(1)

            st.subheader("Progress Over Time")
            if "show_weekly_slope" not in st.session_state:
                st.session_state["show_weekly_slope"] = False
            st.toggle("Show weekly slope", key="show_weekly_slope")
            show_weekly_slope = st.session_state["show_weekly_slope"]

            fig_weight = go.Figure()
            if not show_weekly_slope:
                fig_weight.add_trace(
                    go.Scatter(
                        x=logs_df["date"],
                        y=logs_df["estimated_weight"],
                        customdata=logs_df["calories_consumed"],
                        mode="lines+markers",
                        marker=dict(size=8),
                        line=dict(width=2),
                        name="Estimated Weight (lbs)",
                        hovertemplate=(
                            "Date: %{x|%b %d, %Y}"
                            "<br>Weight: %{y:.1f} lbs"
                            "<br>Calories: %{customdata:.0f}"
                            "<extra></extra>"
                        ),
                    )
                )

            if show_weekly_slope and len(logs_df) >= 2:
                slope_df = logs_df.copy()
                slope_df["date_only"] = slope_df["date"].dt.date
                first_log_date = slope_df["date_only"].min()

                def week_start_for(date_val: dt.date) -> dt.date:
                    return first_log_date + dt.timedelta(
                        days=((date_val - first_log_date).days // 7) * 7
                    )

                slope_df["week_start"] = slope_df["date_only"].apply(week_start_for)

                for _, group in slope_df.groupby("week_start"):
                    if len(group) < 2:
                        continue
                    group = group.sort_values("date")
                    x_vals = group["date_only"].apply(lambda d: d.toordinal()).to_numpy()
                    y_vals = group["estimated_weight"].to_numpy()
                    slope, intercept = np.polyfit(x_vals, y_vals, 1)
                    slope_week = slope * 7
                    x0 = x_vals.min()
                    x1 = x_vals.max()
                    y0 = slope * x0 + intercept
                    y1 = slope * x1 + intercept
                    d0 = group["date_only"].min()
                    d1 = group["date_only"].max()
                    max_rate = 2.0
                    abs_rate = abs(slope_week)
                    intensity = min(abs_rate / max_rate, 1.0)
                    if abs_rate < 0.02:
                        line_color = "rgba(255,255,255,0.9)"
                    else:
                        is_good = slope_week < 0 if goal_type == "Lose" else slope_week > 0
                        target = (46, 125, 50) if is_good else (198, 40, 40)
                        r = int(255 + (target[0] - 255) * intensity)
                        g = int(255 + (target[1] - 255) * intensity)
                        b = int(255 + (target[2] - 255) * intensity)
                        line_color = f"rgba({r},{g},{b},0.9)"
                    fig_weight.add_trace(
                        go.Scatter(
                            x=[d0, d1],
                            y=[y0, y1],
                            mode="lines",
                            line=dict(color=line_color, width=3),
                            showlegend=False,
                            hovertemplate=f"Slope: {slope_week:+.2f} lbs/week<extra></extra>",
                        )
                    )
                    fig_weight.add_trace(
                        go.Scatter(
                            x=[d1],
                            y=[y1],
                            mode="markers",
                            marker=dict(size=6, color=line_color),
                            showlegend=False,
                            hovertemplate=f"Slope: {slope_week:+.2f} lbs/week<extra></extra>",
                        )
                    )
            # Highlight global and weekly min/max points
            if not show_weekly_slope:
                highlight_df = logs_df.dropna(
                    subset=["estimated_weight", "calories_consumed"]
                ).copy()
                if not highlight_df.empty:
                    first_log_date = highlight_df["date"].dt.date.min()
                    last_log_date = highlight_df["date"].dt.date.max()
                    week_end = last_log_date
                    days_since_start = (week_end - first_log_date).days
                    if days_since_start < 0:
                        week_start = first_log_date
                    else:
                        week_start = first_log_date + dt.timedelta(
                            days=(days_since_start // 7) * 7
                        )
                    week_end_display = week_start + dt.timedelta(days=6)

                    global_min_idx = highlight_df["estimated_weight"].idxmin()
                    global_max_idx = highlight_df["estimated_weight"].idxmax()

                    weekly_mask = (
                        (highlight_df["date"].dt.date >= week_start)
                        & (highlight_df["date"].dt.date <= week_end_display)
                    )
                    weekly_df = highlight_df[weekly_mask]
                    weekly_min_idx = (
                        weekly_df["estimated_weight"].idxmin() if not weekly_df.empty else None
                    )
                    weekly_max_idx = (
                        weekly_df["estimated_weight"].idxmax() if not weekly_df.empty else None
                    )

                    highlights: dict[int, dict] = {}

                    def add_highlight(idx: int | None, label: str, color: str, priority: int, symbol: str) -> None:
                        if idx is None:
                            return
                        row = highlight_df.loc[idx]
                        entry = highlights.get(idx)
                        if entry is None:
                            highlights[idx] = {
                                "x": row["date"],
                                "y": row["estimated_weight"],
                                "calories": row["calories_consumed"],
                                "labels": [label],
                                "priority": priority,
                                "color": color,
                            }
                            return
                        entry["labels"].append(label)
                        if priority < entry["priority"]:
                            entry["priority"] = priority
                            entry["color"] = color

                    if global_min_idx == global_max_idx:
                        add_highlight(
                            global_min_idx,
                            "Highest/Lowest Weight",
                            "mediumpurple",
                            0,
                            "circle",
                        )
                    else:
                        add_highlight(global_min_idx, "Lowest Weight", "royalblue", 0, "circle")
                        add_highlight(global_max_idx, "Highest Weight", "goldenrod", 0, "circle")

                    if (
                        weekly_min_idx == weekly_max_idx
                        and weekly_min_idx is not None
                        and weekly_min_idx not in {global_min_idx, global_max_idx}
                    ):
                        add_highlight(
                            weekly_min_idx,
                            "Week Min/Max",
                            "seagreen",
                            1,
                            "circle",
                        )
                    else:
                        if weekly_min_idx not in {global_min_idx, global_max_idx}:
                            add_highlight(weekly_min_idx, "Weekly Min", "seagreen", 1, "circle")
                        if weekly_max_idx not in {global_min_idx, global_max_idx}:
                            add_highlight(weekly_max_idx, "Weekly Max", "darkorange", 1, "circle")

                    for entry in highlights.values():
                        label_text = " / ".join(entry["labels"])
                        fig_weight.add_trace(
                            go.Scatter(
                                x=[entry["x"]],
                                y=[entry["y"]],
                                mode="markers+text",
                                marker=dict(
                                    size=8,
                                    color=entry["color"],
                                    symbol="circle",
                                ),
                                text=[f"<b>{label_text}</b>"],
                                textposition="top center",
                                showlegend=False,
                                customdata=[entry["calories"]],
                                hovertemplate=(
                                    "Date: %{x|%b %d, %Y}"
                                    "<br>Weight: %{y:.1f} lbs"
                                    "<br>Calories: %{customdata:.0f}"
                                    f"<br>{label_text}"
                                    "<extra></extra>"
                                ),
                            )
                        )
            fig_weight.update_layout(
                yaxis_title="Estimated Weight (lbs)",
                margin=dict(l=40, r=40, t=40, b=40),
                hovermode="closest",
                dragmode=False,
                showlegend=False,
            )
            tick_vals = logs_df["date"]
            tick_text = [d.strftime("%b %d, %Y") for d in tick_vals]
            fig_weight.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=tick_text)
            st.plotly_chart(
                fig_weight,
                use_container_width=True,
                config={"displayModeBar": False, "scrollZoom": False},
            )
        else:
            st.info("No logs yet. Add your first entry to see progress.")

        st.subheader("Weekly Check-ins")
        if logs_df.empty:
            st.info("Log at least one entry to enable weekly check-ins.")
        else:
            first_log_date = pd.to_datetime(logs_df["date"]).min().date()
            last_log_date = pd.to_datetime(logs_df["date"]).max().date()
            end_date = last_log_date
            week_dates = []
            current_week = first_log_date + dt.timedelta(days=7)
            while current_week <= end_date:
                week_dates.append(current_week)
                current_week += dt.timedelta(days=7)

            if not week_dates:
                next_checkin = first_log_date + dt.timedelta(days=7)
                st.info(f"First check-in unlocks on {next_checkin.isoformat()}.")
            else:

                logs_for_weeks = logs_df.copy()
                logs_for_weeks["date"] = pd.to_datetime(logs_for_weeks["date"]).dt.date
                running_series = (
                    logs_for_weeks.sort_values("date")
                    .set_index("date")["running_balance"]
                    .reindex(pd.Index(week_dates, name="date"), method="ffill")
                    .fillna(0.0)
                )
                predicted_lbs = starting_weight - (running_series / 3500.0)

                checkins_df = pd.DataFrame(
                    {
                        "week_start": week_dates,
                        "predicted_lbs": predicted_lbs.values,
                    }
                )
                actuals_df = db.get_weekly_checkins()
                if not actuals_df.empty:
                    actuals_df["date"] = pd.to_datetime(actuals_df["date"]).dt.date
                    checkins_df = checkins_df.merge(
                        actuals_df, left_on="week_start", right_on="date", how="left"
                    ).drop(columns=["date"])
                else:
                    checkins_df["actual_weight_lbs"] = pd.NA

                checkins_df["predicted"] = checkins_df["predicted_lbs"]
                checkins_df["actual"] = checkins_df["actual_weight_lbs"]
                weight_unit = "lbs"

                checkins_df["diff"] = checkins_df["actual"] - checkins_df["predicted"]
                display_df = checkins_df[["week_start", "predicted", "actual", "diff"]].copy()
                display_df["predicted"] = pd.to_numeric(
                    display_df["predicted"], errors="coerce"
                ).round(1)
                display_df["actual"] = pd.to_numeric(display_df["actual"], errors="coerce").round(1)
                display_df["diff"] = pd.to_numeric(display_df["diff"], errors="coerce").round(1)

                edited_checkins = st.data_editor(
                    display_df,
                    use_container_width=True,
                    num_rows="fixed",
                    disabled=["week_start", "predicted", "diff"],
                    column_config={
                        "week_start": st.column_config.DateColumn(
                            "Week Start", format="MM/DD/YYYY"
                        ),
                        "predicted": st.column_config.NumberColumn(
                            f"Predicted ({weight_unit})", format="%.1f"
                        ),
                        "actual": st.column_config.NumberColumn(
                            f"Actual ({weight_unit})", min_value=0.0, step=0.1, format="%.1f"
                        ),
                        "diff": st.column_config.NumberColumn(
                            f"Difference ({weight_unit})", format="%.1f"
                        ),
                    },
                )

                if st.button("Save Check-ins"):
                    for _, row in edited_checkins.iterrows():
                        date_val = row.get("week_start")
                        if isinstance(date_val, dt.datetime):
                            date_val = date_val.date()
                        if not isinstance(date_val, dt.date):
                            continue
                        date_str = date_val.isoformat()
                        actual_val = row.get("actual")
                        if pd.isna(actual_val):
                            db.delete_weekly_checkin(date_str)
                            continue
                        actual_lbs = float(actual_val)
                        db.upsert_weekly_checkin(date_str, actual_lbs)

                    st.success("Weekly check-ins updated.")
                    st.rerun()

with tab_entries:
    st.subheader("All Entries")
    logs_df = db.get_daily_logs()
    if logs_df.empty:
        st.info("No entries to show yet.")
    else:
        logs_df = logs_df.sort_values("date")
        editor_df = logs_df[["date", "calories_consumed", "note"]].copy()
        editor_df["date"] = pd.to_datetime(editor_df["date"]).dt.date
        editor_df["calories_consumed"] = editor_df["calories_consumed"].round().astype(int)
        editor_df["note"] = editor_df["note"].fillna("").astype(str)
        editor_df["delete"] = False

        edited_df = st.data_editor(
            editor_df,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "date": st.column_config.DateColumn("Date", format="MM/DD/YYYY"),
                "calories_consumed": st.column_config.NumberColumn(
                    "Calories Consumed", min_value=0, max_value=10000, step=1
                ),
                "note": st.column_config.TextColumn("Note"),
                "delete": st.column_config.CheckboxColumn("Delete"),
            },
        )

        def apply_edits(df: pd.DataFrame, original_df: pd.DataFrame) -> None:
            original_df = original_df.copy()
            original_df["date"] = pd.to_datetime(original_df["date"]).dt.date
            original_map = {}
            for _, row in original_df.iterrows():
                original_map[row["date"]] = (
                    int(round(row["calories_consumed"])),
                    None if pd.isna(row.get("note")) else str(row.get("note")),
                )
            restores: list[tuple[str, int, str | None]] = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if pd.isna(date_val):
                    continue
                if isinstance(date_val, dt.datetime):
                    date_val = date_val.date()
                if isinstance(date_val, dt.date):
                    date_str = date_val.isoformat()
                elif isinstance(date_val, str) and date_val.strip():
                    date_str = pd.to_datetime(date_val).date().isoformat()
                else:
                    continue

                date_key = pd.to_datetime(date_str).date()
                prev = original_map.get(date_key)
                prev_cals = prev[0] if prev else None
                prev_note = prev[1] if prev else None
                note_val = row.get("note")
                if pd.isna(note_val):
                    note_val = None
                else:
                    note_val = str(note_val).strip() or None

                if row.get("delete") == True:
                    if prev_cals is not None:
                        restores.append((date_str, int(prev_cals), prev_note))
                    db.delete_daily_log(date_str)
                    continue
                if pd.isna(row.get("calories_consumed")):
                    continue
                calories = int(round(row["calories_consumed"]))
                if prev_cals is not None and (
                    calories != int(prev_cals) or note_val != prev_note
                ):
                    restores.append((date_str, int(prev_cals), prev_note))
                daily_bal = calc.daily_balance(maintenance, calories)
                db.upsert_daily_log(date_str, calories, daily_bal, note_val)
            db.update_running_balances()
            st.session_state["last_change_restore"] = restores
            st.success("Entries updated.")
            st.rerun()

        delete_count = int(edited_df["delete"].fillna(False).sum())
        if delete_count > 0:
            st.warning(f"{delete_count} entries marked for deletion.")
        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button("Save Changes"):
                apply_edits(edited_df, logs_df)
        with action_cols[1]:
            if st.session_state.get("last_change_restore"):
                if st.button("Undo Last Change"):
                    for date_str, calories, note_val in st.session_state["last_change_restore"]:
                        daily_bal = calc.daily_balance(maintenance, calories)
                        db.upsert_daily_log(date_str, calories, daily_bal, note_val)
                    db.update_running_balances()
                    st.session_state["last_change_restore"] = []
                    st.success("Last change undone.")
                    st.rerun()

with tab_simulation:
    st.subheader("Simulation")
    st.caption("Adjust calories and see how your timeline to goal changes.")

    logs_df_sim = db.get_daily_logs()
    if not logs_df_sim.empty:
        logs_df_sim = logs_df_sim.sort_values("date")
        running_balance_sim = float(logs_df_sim["running_balance"].iloc[-1])
    else:
        running_balance_sim = 0.0

    current_estimated_weight = calc.estimated_weight(starting_weight, running_balance_sim)

    weight_basis = st.radio(
        "Starting point",
        ["Current estimated weight", "Starting weight"],
        horizontal=True,
    )
    if weight_basis == "Current estimated weight":
        sim_start_weight = current_estimated_weight
    else:
        sim_start_weight = starting_weight

    target_weight_sim = (
        float(profile["target_weight_lbs"])
        if profile.get("target_weight_lbs") is not None
        else starting_weight
    )

    sim_start_date = st.date_input("Start date", value=dt.date.today())
    if goal_type == "Lose":
        sim_default_calories = int(math.floor(maintenance / 1000.0) * 1000)
    else:
        sim_default_calories = int(math.ceil(maintenance / 1000.0) * 1000)

    sim_calories = st.number_input(
        "Planned daily calories",
        min_value=0,
        max_value=12000,
        value=sim_default_calories,
        step=50,
    )

    daily_balance_sim = calc.daily_balance(maintenance, float(sim_calories))
    if goal_type == "Lose":
        daily_progress = daily_balance_sim
        pace_label = "Estimated weekly loss"
    else:
        daily_progress = -daily_balance_sim
        pace_label = "Estimated weekly gain"

    goal_calories_sim = abs(sim_start_weight - target_weight_sim) * 3500.0

    if goal_calories_sim == 0:
        st.info("You're already at your goal weight.")
    elif daily_progress <= 0:
        st.warning("At this intake, you're not on track for your goal.")
    else:
        est_days = max(1, math.ceil(goal_calories_sim / daily_progress))
        if est_days > 365:
            st.warning("At this intake, you're not on track for your goal.")
        else:
            finish_date = sim_start_date + dt.timedelta(days=est_days)
            weekly_change = (daily_progress * 7) / 3500.0
            change_unit = "lbs"

            sim_col1, sim_col2, sim_col3 = st.columns(3)
            sim_col1.metric("Estimated days to goal", f"{est_days}")
            sim_col2.metric("Estimated finish date", finish_date.strftime("%b %d, %Y"))
            sim_col3.metric(pace_label, f"{weekly_change:,.2f} {change_unit}")


