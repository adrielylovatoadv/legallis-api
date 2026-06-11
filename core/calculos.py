"""Funções de cálculo jurídico — correção monetária e juros."""
from datetime import date


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def next_month(year: int, month: int):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def iter_months(start: date, end: date):
    cy, cm = start.year, start.month
    ey, em = end.year, end.month
    while (cy, cm) < (ey, em):
        yield cy, cm
        cy, cm = next_month(cy, cm)


def get_correction_index(year: int, month: int, indices: dict) -> float:
    key = month_key(year, month)
    if (year < 2024) or (year == 2024 and month <= 8):
        val = indices.get("inpc", {}).get(key)
    else:
        val = indices.get("ipcae", {}).get(key)
    return val if val is not None else 0.0


def get_tjsp_factor(key: str, indices: dict):
    y, m = int(key[:4]), int(key[5:7])
    if (y < 2024) or (y == 2024 and m <= 8):
        return indices.get("tjsp_inpc", {}).get(key)
    else:
        return indices.get("tjsp_14905", {}).get(key)


def calc_correcao_tjsp(value: float, date_start: date, date_end: date, indices: dict) -> tuple:
    k_start = month_key(date_start.year, date_start.month)
    k_end   = month_key(date_end.year,   date_end.month)
    f_start = get_tjsp_factor(k_start, indices)
    f_end   = get_tjsp_factor(k_end,   indices)
    if f_start and f_end and f_start > 0:
        fator = f_end / f_start
        meses = sum(1 for _ in iter_months(date_start, date_end))
        return round(value * fator, 2), round(fator, 6), meses
    # fallback: INPC mês a mês
    cf, meses = 1.0, 0
    for y, m in iter_months(date_start, date_end):
        cf *= 1.0 + get_correction_index(y, m, indices) / 100.0
        meses += 1
    return round(value * cf, 2), round(cf, 6), meses


def get_interest_rate(year: int, month: int, indices: dict) -> float:
    if (year, month) <= (2002, 12):
        return 0.5
    elif (year, month) <= (2024, 8):
        return 1.0
    else:
        val = indices.get("selic", {}).get(month_key(year, month))
        return val if val is not None else 1.0


def calculate_charge(value: float, date_charge: date, date_calc: date,
                     indices: dict, tribunal: str = "TJMG") -> dict:
    if date_charge >= date_calc:
        return {"corrected": value, "correction_factor": 1.0, "interest_pct": 0.0,
                "interest_value": 0.0, "total": value, "months": 0}

    is_tjsp = "TJSP" in tribunal
    if is_tjsp:
        corrected, correction_factor, months_count = calc_correcao_tjsp(
            value, date_charge, date_calc, indices)
        total_interest_pct = sum(
            get_interest_rate(y, m, indices)
            for y, m in iter_months(date_charge, date_calc))
    else:
        correction_factor, total_interest_pct, months_count = 1.0, 0.0, 0
        for year, month in iter_months(date_charge, date_calc):
            correction_factor *= 1.0 + get_correction_index(year, month, indices) / 100.0
            total_interest_pct += get_interest_rate(year, month, indices)
            months_count += 1
        corrected = value * correction_factor

    interest_value = corrected * total_interest_pct / 100.0
    return {
        "corrected": round(corrected, 2),
        "correction_factor": round(correction_factor, 6),
        "interest_pct": round(total_interest_pct, 4),
        "interest_value": round(interest_value, 2),
        "total": round(corrected + interest_value, 2),
        "months": months_count,
    }
