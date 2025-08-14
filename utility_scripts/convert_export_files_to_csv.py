"""Convert the Firebase export files into a CSV file."""

import re
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

import typer
import polars as pl

PREV_MATCHING_PATTERN = re.compile(r"(?:[\s(（]+|^)prev[\s)）]+", re.IGNORECASE)


def main(
    export_path: Path = typer.Argument(
        ..., help="The path to the folder holding Firebase export files for a conversation ID."
    ),
    user_id: str = typer.Argument(..., help="The user ID to which this conversation ID belongs."),
    timezone: str = typer.Option("Asia/Taipei", help="The timezone to use for the timestamps."),
    output_path: Path = typer.Argument(Path("."), help="The path to the output CSV file."),
):
    timezone_obj = ZoneInfo(timezone)

    rows = []
    for file_path in export_path.glob("*.json"):
        with file_path.open() as f:
            data = json.load(f)
        for field, value in data.items():
            if field == "month" or not isinstance(value, dict):
                continue
            for timestamp, content in value.items():
                dt = datetime.fromtimestamp(int(timestamp), timezone_obj)
                if PREV_MATCHING_PATTERN.match(content):
                    date = dt.date() + timedelta(days=-1)
                else:
                    date = dt.date()
                rows.append(
                    {
                        "date": date,
                        "create_time": dt.isoformat(),
                        "update_time": dt.isoformat(),
                        "content": PREV_MATCHING_PATTERN.sub(r"", content).strip(),
                        # "content": content,
                    }
                )
    df = pl.DataFrame(rows)
    df = df.with_columns(pl.lit(user_id, dtype=pl.Utf8).alias("user_id")).sort("date")
    df.write_csv(f"{user_id}.csv")
    print(f"Wrote {df.shape[0]} rows into {output_path}/{user_id}.csv")


if __name__ == "__main__":
    typer.run(main)
