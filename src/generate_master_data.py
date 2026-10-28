import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


# Project root and configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "project_config.json"


FIRST_NAMES = [
    "Aarav", "Aadhya", "Arjun", "Diya", "Ishaan",
    "Kavya", "Lakshmi", "Meera", "Nila", "Rahul",
    "Riya", "Sai", "Sneha", "Varun", "Vikram",
]

LAST_NAMES = [
    "Kumar", "Sharma", "Patel", "Reddy", "Iyer",
    "Rao", "Nair", "Gupta", "Singh", "Das",
]

DEVICES = ["MOBILE", "DESKTOP", "TABLET", "OTHER"]


def load_config():
    """Read project settings from the JSON configuration file."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def random_datetime(rng, start, end):
    """Return a deterministic random datetime between start and end."""
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randint(0, seconds))


def make_customer_id(number):
    return f"CUS-{number:06d}"


def make_session_id(number):
    return f"SES-2026-{number:06d}"


def insert_in_batches(cursor, sql, records, batch_size=1000):
    """Insert records in batches to avoid excessively large queries."""
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        cursor.executemany(sql, batch)


def generate_master_data(mode):
    config = load_config()

    seed = config["project"]["random_seed"]
    rng = random.Random(seed)

    # The number of master customers is aligned with the cart target.
    target_customers = config["data_generation"][mode]["target_carts"]

    # Use a fixed historical range so the same seed produces the same data.
    start_date = datetime(2026, 1, 1, 0, 0, 0)
    end_date = datetime(2026, 8, 1, 0, 0, 0)

    customers = []
    sessions = []
    consent_records = []

    for number in range(1, target_customers + 1):
        customer_id = make_customer_id(number)

        created_at = random_datetime(rng, start_date, end_date)
        updated_at = created_at + timedelta(
            minutes=rng.randint(0, 60 * 24 * 30)
        )

        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)

        customers.append(
            (
                customer_id,
                first_name,
                last_name,
                f"{customer_id.lower()}@example.com",
                f"+91{7000000000 + number:010d}",
                "IN",
                created_at,
                updated_at,
            )
        )

        # Create one session for each customer.
        session_start = created_at + timedelta(
            days=rng.randint(1, 30),
            minutes=rng.randint(0, 1439),
        )
        last_activity = session_start + timedelta(
            minutes=rng.randint(1, 120)
        )
        session_end = last_activity + timedelta(
            minutes=rng.randint(1, 30)
        )

        sessions.append(
            (
                make_session_id(number),
                customer_id,
                rng.choice(DEVICES),
                session_start,
                last_activity,
                session_end,
                "ENDED",
            )
        )

        # Create a consent history for both communication channels.
        for channel in ("EMAIL", "SMS"):
            opt_in_at = created_at + timedelta(
                minutes=rng.randint(1, 120)
            )
            opt_in_recorded_at = opt_in_at + timedelta(minutes=1)

            consent_records.append(
                (
                    customer_id,
                    channel,
                    "OPTED_IN",
                    opt_in_at,
                    opt_in_recorded_at,
                    "SYNTHETIC_SEED",
                    "Initial synthetic consent record",
                )
            )

            # Some customers later withdraw consent.
            if rng.random() < 0.15:
                opt_out_at = opt_in_at + timedelta(
                    days=rng.randint(10, 60)
                )
                opt_out_recorded_at = opt_out_at + timedelta(minutes=1)

                consent_records.append(
                    (
                        customer_id,
                        channel,
                        "OPTED_OUT",
                        opt_out_at,
                        opt_out_recorded_at,
                        "SYNTHETIC_SEED",
                        "Synthetic consent withdrawal",
                    )
                )

    connection = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # 1. Insert customers first because they are parent records.
        customer_sql = """
            INSERT IGNORE INTO customers
            (
                customer_id, first_name, last_name, email, phone,
                country_code, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        insert_in_batches(cursor, customer_sql, customers)
        connection.commit()

        # 2. Insert sessions after customers exist.
        session_sql = """
            INSERT IGNORE INTO sessions
            (
                session_id, customer_id, device_type,
                started_at, last_activity_at, ended_at, session_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        insert_in_batches(cursor, session_sql, sessions)
        connection.commit()

        # 3. Read existing consent events so reruns do not duplicate them.
        cursor.execute("""
            SELECT customer_id, channel, consent_status, effective_at
            FROM consent_events
        """)

        existing_consent = {
            (
                row[0],
                row[1],
                row[2],
                row[3].replace(microsecond=0),
            )
            for row in cursor.fetchall()
        }

        consent_sql = """
            INSERT INTO consent_events
            (
                customer_id, channel, consent_status,
                effective_at, recorded_at, source, reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        new_consent_records = []

        for record in consent_records:
            consent_key = (
                record[0],
                record[1],
                record[2],
                record[3].replace(microsecond=0),
            )

            if consent_key not in existing_consent:
                new_consent_records.append(record)
                existing_consent.add(consent_key)

        insert_in_batches(cursor, consent_sql, new_consent_records)
        connection.commit()

        # 4. Report the actual counts in the database.
        for table in ("customers", "sessions", "consent_events"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count:,} total rows")

        print(f"\nMode: {mode}")
        print(f"Random seed: {seed}")
        print(f"Customers requested: {target_customers:,}")
        print(f"New consent events inserted: {len(new_consent_records):,}")
        print("Master-data generation completed successfully.")

        cursor.close()

    except Error:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate deterministic customer, consent and session data."
    )

    parser.add_argument(
        "mode",
        choices=["starter", "full"],
        nargs="?",
        default="starter",
        help="Use starter or full dataset configuration.",
    )

    args = parser.parse_args()

    try:
        generate_master_data(args.mode)
    except (Error, OSError, ValueError, KeyError) as error:
        print(f"Generation failed: {error}")
        raise SystemExit(1)