import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "healo.db"


def load_tables():
    conn = sqlite3.connect(DB_PATH)

    patients = pd.read_sql_query("SELECT * FROM patients", conn)
    messages = pd.read_sql_query("SELECT * FROM message_logs", conn)
    responses = pd.read_sql_query("SELECT * FROM responses", conn)

    conn.close()
    return patients, messages, responses


def prepare_data(patients, messages, responses):
    messages["sent_at"] = pd.to_datetime(messages["sent_at"])
    responses["received_at"] = pd.to_datetime(responses["received_at"])

    messages["date"] = messages["sent_at"].dt.date
    responses["date"] = responses["received_at"].dt.date

    return patients, messages, responses


def compute_daily_features(patients, messages, responses):
    all_days = []

    for patient_id in patients["id"].tolist():
        patient_msgs = messages[messages["patient_id"] == patient_id].copy()
        patient_resps = responses[responses["patient_id"] == patient_id].copy()

        if patient_msgs.empty:
            continue

        patient_msgs = patient_msgs.sort_values("sent_at")
        patient_resps = patient_resps.sort_values("received_at")

        daily = patient_msgs.groupby("date").agg(
            messages_sent=("id", "count")
        ).reset_index()

        resp_daily = patient_resps.groupby("date").agg(
            responses_received=("id", "count"),
            avg_reply_latency_seconds=("reply_latency_seconds", "mean")
        ).reset_index()

        merged = daily.merge(resp_daily, on="date", how="left")
        merged["responses_received"] = merged["responses_received"].fillna(0)
        merged["avg_reply_latency_seconds"] = merged["avg_reply_latency_seconds"].fillna(0)

        merged["replied_today"] = (merged["responses_received"] > 0).astype(int)
        merged["missed_today"] = (merged["replied_today"] == 0).astype(int)

        streaks = []
        streak = 0
        for replied in merged["replied_today"]:
            if replied == 1:
                streak += 1
            else:
                streak = 0
            streaks.append(streak)

        merged["reply_streak"] = streaks
        merged["skip_rate_so_far"] = merged["missed_today"].expanding().mean()

        merged["day_of_week"] = pd.to_datetime(merged["date"]).dt.day_name()
        merged["is_weekend"] = merged["day_of_week"].isin(["Saturday", "Sunday"]).astype(int)

        weekend_skip = []
        for i in range(len(merged)):
            subset = merged.iloc[: i + 1]
            weekend_rows = subset[subset["is_weekend"] == 1]
            if len(weekend_rows) == 0:
                weekend_skip.append(0)
            else:
                weekend_skip.append(weekend_rows["missed_today"].mean())

        merged["weekend_skip_rate"] = weekend_skip
        merged["patient_id"] = patient_id

        all_days.append(merged)

    if not all_days:
        return pd.DataFrame()

    feature_df = pd.concat(all_days, ignore_index=True)
    return feature_df


def add_dropout_label(feature_df):
    feature_df = feature_df.sort_values(["patient_id", "date"]).copy()
    feature_df["dropout_risk_label"] = "Low"

    for patient_id in feature_df["patient_id"].unique():
        patient_rows = feature_df[feature_df["patient_id"] == patient_id].copy()

        for i in range(len(patient_rows)):
            future_window = patient_rows.iloc[i + 1 : i + 8]
            if len(future_window) >= 3:
                missed_ratio = future_window["missed_today"].mean()

                if missed_ratio >= 0.7:
                    label = "High"
                elif missed_ratio >= 0.4:
                    label = "Medium"
                else:
                    label = "Low"

                feature_df.loc[patient_rows.index[i], "dropout_risk_label"] = label

    return feature_df


def main():
    patients, messages, responses = load_tables()
    patients, messages, responses = prepare_data(patients, messages, responses)

    feature_df = compute_daily_features(patients, messages, responses)

    if feature_df.empty:
        print("No message/response data available yet.")
        return

    feature_df = add_dropout_label(feature_df)
    feature_df.to_csv("features_dataset.csv", index=False)

    print("Feature pipeline complete.")
    print(f"Saved features_dataset.csv with {len(feature_df)} rows.")
    print(feature_df.head())


if __name__ == "__main__":
    main()