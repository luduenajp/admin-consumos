from __future__ import annotations

from datetime import date


def to_year_month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def add_months(year_month: str, months: int) -> str:
    year_s, month_s = year_month.split("-")
    year = int(year_s)
    month = int(month_s)

    month0 = (year * 12) + (month - 1)
    month0 += months

    new_year = month0 // 12
    new_month = (month0 % 12) + 1
    return f"{new_year:04d}-{new_month:02d}"
