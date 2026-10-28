import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from mysql.connector import Error

from db_connection import get_connection


# --------------------------------------------------
# 1. PROJECT SETTINGS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SNAPSHOT_AT = datetime(2026, 10, 26, 0, 0, 0)


# These are synthetic assumptions, not real customer
# behavior or measured campaign performance.
DELIVERY_RATE = 0.95
OPEN_RATE = 0.60
CLICK_RATE = 0.30


# --------------------------------------------------
# 2. LOAD PROJECT CONFIGURATION
# --------------------------------------------------

def load_config():
    """Load the project's fixed random seed."""

    config_path = (
        PROJECT_ROOT
        / "config"
        / "project_config.json"
    )

    with open(config_path, "r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# 3. GENERATE MESSAGE INTERACTION EVENTS
# --------------------------------------------------

def generate_message_interactions():

    config = load_config()

    seed = config["project"]["random_seed"]

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # ------------------------------------------
        # STEP A: LOAD SUCCESSFUL MESSAGE SENDS
        # ------------------------------------------

        cursor.execute("""
            SELECT
                send_id,
                attempted_at
            FROM send_attempts
            WHERE send_status = 'SENT'
            ORDER BY send_id
        """)

        sent_messages = cursor.fetchall()

        if not sent_messages:
            raise ValueError(
                "No successful sends found. "
                "Generate campaign enrollments first."
            )

        # ------------------------------------------
        # STEP B: LOAD EXISTING EVENTS
        # ------------------------------------------

        cursor.execute("""
            SELECT
                send_id,
                event_type
            FROM message_events
        """)

        existing_events = {
            (row[0], row[1])
            for row in cursor.fetchall()
        }

        # ------------------------------------------
        # STEP C: PREPARE NEW EVENTS
        # ------------------------------------------

        new_events = []

        event_counts = {
            "DELIVERED": 0,
            "OPENED": 0,
            "CLICKED": 0,
        }

        skipped_existing = 0
        skipped_snapshot = 0

        for send_id, attempted_at in sent_messages:

            # Derive a stable per-send seed.
            # This makes the same send produce the same
            # synthetic outcome when the script is rerun.

            send_number = int(
                send_id.rsplit("-", 1)[1]
            )

            rng = random.Random(
                seed + send_number + 900000
            )

            # --------------------------------------
            # Determine synthetic delivery outcome
            # --------------------------------------

            delivered = rng.random() < DELIVERY_RATE

            opened = (
                delivered
                and rng.random() < OPEN_RATE
            )

            clicked = (
                opened
                and rng.random() < CLICK_RATE
            )

            # --------------------------------------
            # Generate events in chronological order
            # --------------------------------------

            delivery_time = attempted_at + timedelta(
                minutes=rng.randint(1, 10)
            )

            open_time = delivery_time + timedelta(
                minutes=rng.randint(1, 60),
                hours=rng.randint(0, 23),
            )

            click_time = open_time + timedelta(
                minutes=rng.randint(1, 10)
            )

            proposed_events = []

            if delivered:
                proposed_events.append(
                    (
                        "DELIVERED",
                        delivery_time,
                        {
                            "source": "SYNTHETIC_GENERATOR",
                            "assumed_delivery_rate": DELIVERY_RATE,
                        },
                    )
                )

            if opened:
                proposed_events.append(
                    (
                        "OPENED",
                        open_time,
                        {
                            "source": "SYNTHETIC_GENERATOR",
                            "assumed_open_rate": OPEN_RATE,
                        },
                    )
                )

            if clicked:
                proposed_events.append(
                    (
                        "CLICKED",
                        click_time,
                        {
                            "source": "SYNTHETIC_GENERATOR",
                            "assumed_click_rate": CLICK_RATE,
                        },
                    )
                )

            # --------------------------------------
            # Add only missing events
            # --------------------------------------

            for event_type, event_time, details in proposed_events:

                event_key = (send_id, event_type)

                # Do not create duplicate event types
                # for the same send.
                if event_key in existing_events:
                    skipped_existing += 1
                    continue

                # Keep generated events within the snapshot.
                if event_time > SNAPSHOT_AT:
                    skipped_snapshot += 1
                    continue

                provider_event_id = (
                    f"SYNTH-{send_id}-{event_type}"
                )

                event_details = json.dumps(
                    details,
                    separators=(",", ":"),
                )

                new_events.append(
                    (
                        send_id,
                        event_type,
                        event_time,
                        provider_event_id,
                        event_details,
                    )
                )

                # Protect against duplicates within this run.
                existing_events.add(event_key)

                event_counts[event_type] += 1

        # ------------------------------------------
        # STEP D: INSERT NEW EVENTS
        # ------------------------------------------

        if new_events:

            cursor.executemany(
                """
                INSERT INTO message_events
                (
                    send_id,
                    event_type,
                    event_at,
                    provider_event_id,
                    event_details
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                new_events,
            )

        connection.commit()

        # ------------------------------------------
        # STEP E: DISPLAY RESULTS
        # ------------------------------------------

        print("\n" + "=" * 50)
        print("MESSAGE INTERACTION GENERATION COMPLETED")
        print("=" * 50)

        print(f"Random seed: {seed}")
        print(f"Successful sends examined: {len(sent_messages):,}")

        print("\nNew events generated:")

        for event_type, count in event_counts.items():
            print(f"{event_type}: {count:,}")

        print(f"Total new events: {len(new_events):,}")
        print(f"Existing events skipped: {skipped_existing:,}")
        print(f"Events beyond snapshot skipped: {skipped_snapshot:,}")

        print("\nActual message event totals:")

        cursor.execute("""
            SELECT
                event_type,
                COUNT(*) AS total_events
            FROM message_events
            GROUP BY event_type
            ORDER BY event_type
        """)

        for event_type, total in cursor.fetchall():
            print(f"{event_type}: {total:,}")

        print("=" * 50)

    except (Error, ValueError, OSError, KeyError):
        if connection is not None and connection.is_connected():
            connection.rollback()

        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 4. SCRIPT ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Generate synthetic delivery, open, "
            "and click events for sent messages."
        )
    )

    args = parser.parse_args()

    try:
        generate_message_interactions()

    except (Error, ValueError, OSError, KeyError) as error:
        print(f"\nInteraction generation failed: {error}")
        raise SystemExit(1)