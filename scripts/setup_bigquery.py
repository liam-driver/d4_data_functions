"""
One-time infrastructure setup: creates d4_reporting dataset and funnel_data table.
Run after the GCP project, service account, and secrets.json are in place.

Usage:
    python scripts/setup_bigquery.py
"""
import json
import sys
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account

SECRETS_PATH = Path(__file__).parent.parent / "storage" / "secrets.json"
DATASET_ID = "d4_reporting"
TABLE_ID = "funnel_data"


def load_credentials() -> service_account.Credentials:
    with open(SECRETS_PATH) as f:
        secrets = json.load(f)
    sa = secrets["google_service_account"]
    return service_account.Credentials.from_service_account_info(
        sa,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    ), sa["project_id"]


def create_dataset(client: bigquery.Client, project_id: str) -> bigquery.Dataset:
    dataset_ref = bigquery.DatasetReference(project_id, DATASET_ID)
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "europe-west2"
    dataset = client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset {project_id}.{DATASET_ID} ready.")
    return dataset


SCHEMA = [
    bigquery.SchemaField("client_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("account_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("week_number_iso", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("month", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("year", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("ad_platform", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("ad_channel", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("channel", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("campaign", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("sessions", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("impressions", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("clicks", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("cost", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("conversions", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("transactions", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("transaction_revenue", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("search_impression_share", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("total_eligible_impression_share", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("total_absolute_top_impression_share", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("views", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("hooks", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("holds", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("website", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("department", "STRING", mode="NULLABLE"),
]


def create_table(client: bigquery.Client, project_id: str) -> bigquery.Table:
    table_ref = bigquery.TableReference(
        bigquery.DatasetReference(project_id, DATASET_ID), TABLE_ID
    )
    table = bigquery.Table(table_ref, schema=SCHEMA)

    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="date",
    )
    table.clustering_fields = ["client_name", "account_type"]

    table = client.create_table(table, exists_ok=True)
    print(f"Table {project_id}.{DATASET_ID}.{TABLE_ID} ready.")
    print(f"  Partitioned by: date (DAY)")
    print(f"  Clustered by:   client_name, account_type")
    return table


def main():
    credentials, project_id = load_credentials()
    client = bigquery.Client(project=project_id, credentials=credentials)

    print(f"Connected to GCP project: {project_id}")
    create_dataset(client, project_id)
    create_table(client, project_id)
    print("\nBigQuery infrastructure setup complete.")


if __name__ == "__main__":
    main()
