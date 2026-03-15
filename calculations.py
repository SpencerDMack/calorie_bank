# Calculations for Calorie Bank
from __future__ import annotations


def lbs_to_kg(weight_lbs: float) -> float:
    return weight_lbs * 0.45359237


def kg_to_lbs(weight_kg: float) -> float:
    return weight_kg / 0.45359237


def feet_in_to_cm(feet: float, inches: float) -> float:
    total_inches = feet * 12 + inches
    return total_inches * 2.54


def bmr_mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    gender_norm = gender.strip().lower()
    if gender_norm == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def maintenance_calories(bmr: float, activity_multiplier: float) -> float:
    return bmr * activity_multiplier


def daily_balance(maintenance: float, calories_consumed: float) -> float:
    return maintenance - calories_consumed


def weight_change_lbs(running_balance: float) -> float:
    return running_balance / 3500


def estimated_weight(start_weight_lbs: float, running_balance: float) -> float:
    return start_weight_lbs - weight_change_lbs(running_balance)


def weekly_deficit_target() -> float:
    return 3500.0


def recommended_calories_today(maintenance: float, week_deficit_so_far: float, days_remaining: int) -> float:
    if days_remaining <= 0:
        return maintenance
    remaining_deficit = weekly_deficit_target() - week_deficit_so_far
    recommended_daily_deficit = remaining_deficit / days_remaining
    return maintenance - recommended_daily_deficit
