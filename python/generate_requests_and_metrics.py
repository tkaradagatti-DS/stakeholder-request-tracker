"""
generate_requests_and_metrics.py

Creates a synthetic stakeholder request log and produces SLA/backlog metrics + charts.
Designed as a junior analyst portfolio project (safe synthetic data).

Run:
  pip install -r python/requirements.txt
  python python/generate_requests_and_metrics.py
"""
from __future__ import annotations

from pathlib import Path
import datetime as dt
import random

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"
IMG = ROOT / "images"

RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
IMG.mkdir(parents=True, exist_ok=True)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

TEAMS = ["Operations","Finance","Marketing","Sales","HR","Customer Support","Training"]
REQUEST_TYPES = ["KPI Report","Data Extract","Dashboard Update","Data Quality Issue","One-off Analysis","Automation Request","Access/Permissions"]
PRIORITIES = ["Low","Medium","High","Urgent"]
CHANNELS = ["Email","Teams","Jira","In person"]

# SLA targets (business days)
SLA_DAYS = {"Urgent": 2, "High": 5, "Medium": 10, "Low": 15}


def add_business_days(start_date: dt.date, days: int) -> dt.date:
    """Adds business days (Mon–Fri) to a date."""
    d = start_date
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    while remaining > 0:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            remaining -= 1
    return d


def make_ids(prefix: str, n: int, width: int = 5) -> list[str]:
    return [f"{prefix}{str(i).zfill(width)}" for i in range(1, n + 1)]


def generate_requests(n: int = 240) -> pd.DataFrame:
    start = dt.date(2024, 1, 1)
    end = dt.date(2025, 12, 31)
    date_range_days = (end - start).days

    request_ids = make_ids("REQ-", n, width=5)
    rows = []

    # helps generate realistic completion probability based on age
    for rid in request_ids:
        req_date = start + dt.timedelta(days=int(np.random.randint(0, date_range_days + 1)))
        team = random.choices(TEAMS, weights=[18, 14, 16, 12, 8, 18, 14], k=1)[0]
        rtype = random.choices(REQUEST_TYPES, weights=[20, 18, 16, 14, 12, 10, 10], k=1)[0]
        priority = random.choices(PRIORITIES, weights=[30, 45, 18, 7], k=1)[0]

        due_date = add_business_days(req_date, SLA_DAYS[priority])

        age_days = (end - req_date).days
        close_prob = min(0.95, 0.25 + age_days / 500)

        if random.random() < close_prob:
            status = "Done"
            base = {"Urgent": 3, "High": 7, "Medium": 12, "Low": 18}[priority]
            completion_bdays = max(1, int(np.random.normal(loc=base, scale=3)))
            completed = add_business_days(req_date, completion_bdays)
            if completed > end:
                completed = end
        else:
            status = random.choice(["Open", "In Progress"])
            completed = None

        est_hours = max(
            0.5,
            round(
                np.random.normal(
                    loc={
                        "KPI Report": 3,
                        "Data Extract": 1.5,
                        "Dashboard Update": 4,
                        "Data Quality Issue": 2.5,
                        "One-off Analysis": 5,
                        "Automation Request": 6,
                        "Access/Permissions": 1,
                    }[rtype],
                    scale=1.2,
                ),
                1,
            ),
        )

        act_hours = (
            max(0.25, round(est_hours * np.random.normal(loc=1.05, scale=0.25), 1))
            if status == "Done"
            else np.nan
        )

        rows.append(
            {
                "request_id": rid,
                "request_date": req_date.isoformat(),
                "requester_team": team,
                "request_type": rtype,
                "priority": priority,
                "channel": random.choice(CHANNELS),
                "due_date": due_date.isoformat(),
                "status": status,
                "completed_date": completed.isoformat() if completed else "",
                "estimated_hours": est_hours,
                "actual_hours": "" if pd.isna(act_hours) else act_hours,
            }
        )

    return pd.DataFrame(rows)


def enrich(df_req: pd.DataFrame) -> pd.DataFrame:
    df = df_req.copy()
    df["request_date"] = pd.to_datetime(df["request_date"])
    df["due_date"] = pd.to_datetime(df["due_date"])
    df["completed_date"] = pd.to_datetime(df["completed_date"], errors="coerce")

    df["is_closed"] = df["status"].eq("Done")
    df["turnaround_days_calendar"] = (df["completed_date"] - df["request_date"]).dt.days

    today = pd.Timestamp(dt.date(2025, 12, 31))
    df["age_days_calendar"] = np.where(
        df["is_closed"], df["turnaround_days_calendar"], (today - df["request_date"]).dt.days
    )

    df["sla_target_bdays"] = df["priority"].map(SLA_DAYS)
    df["sla_breached"] = np.where(df["is_closed"], df["completed_date"] > df["due_date"], False)
    df["month"] = df["request_date"].dt.to_period("M").dt.to_timestamp()

    return df


def compute_outputs(df: pd.DataFrame) -> None:
    # overall
    overall = pd.DataFrame(
        [
            {
                "total_requests": len(df),
                "closed_requests": int(df["is_closed"].sum()),
                "open_requests": int((~df["is_closed"]).sum()),
                "breached_requests": int(df.loc[df["is_closed"], "sla_breached"].sum()),
                "breach_rate_closed": round(
                    df.loc[df["is_closed"], "sla_breached"].mean() * 100, 2
                )
                if df["is_closed"].any()
                else 0,
                "avg_turnaround_days_closed": round(
                    df.loc[df["is_closed"], "turnaround_days_calendar"].mean(), 2
                )
                if df["is_closed"].any()
                else 0,
            }
        ]
    )

    # team metrics
    team_metrics = (
        df[df["is_closed"]]
        .groupby("requester_team")
        .agg(
            closed_requests=("request_id", "count"),
            breach_rate=("sla_breached", lambda s: round(s.mean() * 100, 2)),
            avg_turnaround_days=("turnaround_days_calendar", "mean"),
        )
        .reset_index()
    )
    team_metrics["avg_turnaround_days"] = team_metrics["avg_turnaround_days"].round(2)

    # backlog aging
    open_df = df[~df["is_closed"]].copy()
    bins = [-1, 7, 14, 30, 60, 9999]
    labels = ["0-7 days", "8-14 days", "15-30 days", "31-60 days", "60+ days"]
    open_df["age_bucket"] = pd.cut(open_df["age_days_calendar"], bins=bins, labels=labels)
    backlog_buckets = (
        open_df.groupby(["requester_team", "age_bucket"])
        .size()
        .reset_index(name="open_requests")
    )

    # breach by month
    breach_month = (
        df[df["is_closed"]]
        .groupby("month")
        .agg(breached=("sla_breached", "sum"), closed=("request_id", "count"))
        .reset_index()
    )
    breach_month["breach_rate"] = (breach_month["breached"] / breach_month["closed"] * 100).round(2)

    # write outputs
    overall.to_csv(OUT / "sla_summary.csv", index=False)
    team_metrics.sort_values("closed_requests", ascending=False).to_csv(
        OUT / "team_sla_metrics.csv", index=False
    )
    backlog_buckets.to_csv(OUT / "backlog_age_buckets.csv", index=False)
    breach_month.to_csv(OUT / "monthly_breach_rate.csv", index=False)

    # charts (use defaults to keep it simple)
    # 1) breach rate line
    fig = plt.figure()
    plt.plot(breach_month["month"], breach_month["breach_rate"], marker="o")
    plt.title("Monthly SLA Breach Rate (Closed Requests)")
    plt.ylabel("Breach rate (%)")
    plt.xlabel("Month")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(IMG / "sla_breach_rate.png", dpi=160)
    plt.close(fig)

    # 2) backlog by team stacked bar
    pivot = backlog_buckets.pivot_table(
        index="requester_team", columns="age_bucket", values="open_requests", aggfunc="sum", fill_value=0
    )
    ax = pivot.plot(kind="bar", stacked=True)
    ax.set_title("Open Requests by Team (Aging Buckets)")
    ax.set_ylabel("Open requests")
    ax.set_xlabel("Team")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.gcf().savefig(IMG / "backlog_by_team.png", dpi=160)
    plt.close("all")

    # 3) avg turnaround by priority
    priority_turn = (
        df[df["is_closed"]]
        .groupby("priority")["turnaround_days_calendar"]
        .mean()
        .reindex(PRIORITIES)
    )
    fig = plt.figure()
    priority_turn.plot(kind="bar")
    plt.title("Average Turnaround (Closed Requests)")
    plt.ylabel("Days (calendar)")
    plt.xlabel("Priority")
    plt.xticks(rotation=0)
    plt.tight_layout()
    fig.savefig(IMG / "avg_turnaround_by_priority.png", dpi=160)
    plt.close(fig)

    # 4) simple workflow graphic (text)
    fig = plt.figure(figsize=(8, 2.4))
    plt.axis("off")
    plt.text(0.02, 0.55, "Requests Log (CSV)", fontsize=12, va="center")
    plt.text(0.30, 0.55, "→  SLA + Aging Metrics", fontsize=12, va="center")
    plt.text(0.62, 0.55, "→  Outputs (CSV/DB)", fontsize=12, va="center")
    plt.text(0.86, 0.55, "→  Dashboard", fontsize=12, va="center")
    plt.title("Workflow", y=0.95)
    plt.tight_layout()
    fig.savefig(IMG / "workflow.png", dpi=160)
    plt.close(fig)


def main() -> None:
    df_req = generate_requests(n=240)
    df_req.to_csv(RAW / "requests.csv", index=False)

    df = enrich(df_req)
    df.to_csv(OUT / "requests_enriched.csv", index=False)

    compute_outputs(df)
    print("✅ Done. Outputs written to:", OUT)
    print("✅ Charts written to:", IMG)


if __name__ == "__main__":
    main()
