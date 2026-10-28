import getpass
import unittest

import mysql.connector


TEST_DATABASE = "abandoned_cart_test_db"


class TestAnomalySQL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Connect only to the isolated test database.
        Recreate the small sample tables used by these tests.
        """

        password = getpass.getpass("Enter your MySQL password: ")

        cls.connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password=password,
            database=TEST_DATABASE,
        )

        cls.cursor = cls.connection.cursor()

        # Safety guard: never allow these tests to run on another database.
        cls.cursor.execute("SELECT DATABASE()")
        current_database = cls.cursor.fetchone()[0]

        if current_database != TEST_DATABASE:
            cls.cursor.close()
            cls.connection.close()
            raise RuntimeError(
                f"Safety check failed. Expected {TEST_DATABASE}, "
                f"but connected to {current_database}."
            )

        # These are test tables in the isolated test database only.
        cls.cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

        tables = [
            "attributions",
            "cart_lines",
            "orders",
            "carts",
            "send_attempts",
            "consent_events",
            "customers",
        ]

        for table in tables:
            cls.cursor.execute(f"DROP TABLE IF EXISTS `{table}`")

        cls.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # ---------------------------------------------------------
        # Create minimal tables for the four anomaly tests
        # ---------------------------------------------------------

        cls.cursor.execute("""
            CREATE TABLE customers (
                customer_id VARCHAR(20) PRIMARY KEY
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE consent_events (
                event_id VARCHAR(20) PRIMARY KEY,
                customer_id VARCHAR(20) NOT NULL,
                channel VARCHAR(20) NOT NULL,
                consent_status VARCHAR(20) NOT NULL,
                event_at DATETIME NOT NULL
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE send_attempts (
                send_id VARCHAR(20) PRIMARY KEY,
                customer_id VARCHAR(20) NOT NULL,
                channel VARCHAR(20) NOT NULL,
                sent_at DATETIME NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE carts (
                cart_id VARCHAR(20) PRIMARY KEY,
                customer_id VARCHAR(20) NOT NULL,
                cart_total DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) NOT NULL,
                abandoned_at DATETIME NULL
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE cart_lines (
                line_id VARCHAR(20) PRIMARY KEY,
                cart_id VARCHAR(20) NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                line_status VARCHAR(20) NOT NULL
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE orders (
                order_id VARCHAR(20) PRIMARY KEY,
                customer_id VARCHAR(20) NOT NULL,
                cart_id VARCHAR(20) NOT NULL,
                order_total DECIMAL(10, 2) NOT NULL,
                order_status VARCHAR(20) NOT NULL,
                ordered_at DATETIME NOT NULL
            )
        """)

        cls.cursor.execute("""
            CREATE TABLE attributions (
                attribution_id VARCHAR(20) PRIMARY KEY,
                order_id VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL
            )
        """)

        # ---------------------------------------------------------
        # Insert sample customers
        # ---------------------------------------------------------

        cls.cursor.executemany(
            """
            INSERT INTO customers (customer_id)
            VALUES (%s)
            """,
            [
                ("C1",),
                ("C2",),
            ],
        )

        # ---------------------------------------------------------
        # Anomaly 1: message sent after opt-out
        #
        # C1 opts out at 10:00 and receives a message at 11:00.
        # C2 is a normal control record.
        # ---------------------------------------------------------

        cls.cursor.executemany(
            """
            INSERT INTO consent_events (
                event_id,
                customer_id,
                channel,
                consent_status,
                event_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (
                    "CE1",
                    "C1",
                    "SMS",
                    "OPT_IN",
                    "2026-10-01 09:00:00",
                ),
                (
                    "CE2",
                    "C1",
                    "SMS",
                    "OPT_OUT",
                    "2026-10-10 10:00:00",
                ),
                (
                    "CE3",
                    "C2",
                    "EMAIL",
                    "OPT_IN",
                    "2026-10-01 09:00:00",
                ),
            ],
        )

        cls.cursor.executemany(
            """
            INSERT INTO send_attempts (
                send_id,
                customer_id,
                channel,
                sent_at,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (
                    "S1",
                    "C1",
                    "SMS",
                    "2026-10-10 11:00:00",
                    "SENT",
                ),
                (
                    "S2",
                    "C2",
                    "EMAIL",
                    "2026-10-10 11:00:00",
                    "SENT",
                ),
            ],
        )

        # ---------------------------------------------------------
        # Anomaly 2: cart marked abandoned after purchase
        #
        # CART1 is abandoned at noon, but its order was placed
        # at 11:00 on the same day.
        # ---------------------------------------------------------

        cls.cursor.executemany(
            """
            INSERT INTO carts (
                cart_id,
                customer_id,
                cart_total,
                status,
                abandoned_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (
                    "CART1",
                    "C1",
                    100.00,
                    "ABANDONED",
                    "2026-10-12 12:00:00",
                ),
                (
                    "CART2",
                    "C2",
                    20.00,
                    "ACTIVE",
                    None,
                ),
            ],
        )

        cls.cursor.execute(
            """
            INSERT INTO orders (
                order_id,
                customer_id,
                cart_id,
                order_total,
                order_status,
                ordered_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                "O1",
                "C1",
                "CART1",
                100.00,
                "PAID",
                "2026-10-12 11:00:00",
            ),
        )

        # ---------------------------------------------------------
        # Anomaly 3: duplicate conversion attribution
        #
        # The same order has two CREDITED attribution records.
        # ---------------------------------------------------------

        cls.cursor.executemany(
            """
            INSERT INTO attributions (
                attribution_id,
                order_id,
                status
            )
            VALUES (%s, %s, %s)
            """,
            [
                ("A1", "O1", "CREDITED"),
                ("A2", "O1", "CREDITED"),
            ],
        )

        # ---------------------------------------------------------
        # Anomaly 4: stale cart total
        #
        # CART2 stores 20.00, but its active cart line totals 30.00.
        # CART1 has no cart lines, so it should not be flagged by
        # this particular stale-total test.
        # ---------------------------------------------------------

        cls.cursor.execute(
            """
            INSERT INTO cart_lines (
                line_id,
                cart_id,
                quantity,
                unit_price,
                line_status
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                "L1",
                "CART2",
                2,
                15.00,
                "ACTIVE",
            ),
        )

        cls.connection.commit()

    @classmethod
    def tearDownClass(cls):
        """Close the test database connection."""

        if hasattr(cls, "cursor") and cls.cursor:
            cls.cursor.close()

        if hasattr(cls, "connection") and cls.connection.is_connected():
            cls.connection.close()

    def test_message_sent_after_opt_out(self):
        """Detect messages sent after the customer's latest opt-out."""

        self.cursor.execute("""
            SELECT s.send_id
            FROM send_attempts AS s
            WHERE s.status = 'SENT'
              AND EXISTS (
                  SELECT 1
                  FROM consent_events AS optout
                  WHERE optout.customer_id = s.customer_id
                    AND optout.channel = s.channel
                    AND optout.consent_status = 'OPT_OUT'
                    AND optout.event_at <= s.sent_at
                    AND NOT EXISTS (
                        SELECT 1
                        FROM consent_events AS later_consent
                        WHERE later_consent.customer_id =
                              optout.customer_id
                          AND later_consent.channel = optout.channel
                          AND later_consent.event_at > optout.event_at
                          AND later_consent.event_at <= s.sent_at
                          AND later_consent.consent_status = 'OPT_IN'
                    )
              )
            ORDER BY s.send_id
        """)

        self.assertEqual(
            [row[0] for row in self.cursor.fetchall()],
            ["S1"],
        )

    def test_cart_abandoned_after_purchase(self):
        """Detect carts abandoned after an order was placed."""

        self.cursor.execute("""
            SELECT c.cart_id
            FROM carts AS c
            JOIN orders AS o
              ON o.cart_id = c.cart_id
            WHERE c.status = 'ABANDONED'
              AND c.abandoned_at IS NOT NULL
              AND o.ordered_at < c.abandoned_at
            ORDER BY c.cart_id
        """)

        self.assertEqual(
            [row[0] for row in self.cursor.fetchall()],
            ["CART1"],
        )

    def test_duplicate_conversion_attribution(self):
        """Detect orders with more than one credited attribution."""

        self.cursor.execute("""
            SELECT order_id
            FROM attributions
            WHERE status = 'CREDITED'
            GROUP BY order_id
            HAVING COUNT(*) > 1
            ORDER BY order_id
        """)

        self.assertEqual(
            [row[0] for row in self.cursor.fetchall()],
            ["O1"],
        )

    def test_stale_cart_total_after_quantity_update(self):
        """Detect cart totals that differ from active cart-line totals."""

        self.cursor.execute("""
            SELECT c.cart_id
            FROM carts AS c
            JOIN (
                SELECT
                    cart_id,
                    SUM(quantity * unit_price) AS calculated_total
                FROM cart_lines
                WHERE line_status = 'ACTIVE'
                GROUP BY cart_id
            ) AS line_totals
              ON line_totals.cart_id = c.cart_id
            WHERE ABS(
                c.cart_total - line_totals.calculated_total
            ) > 0.01
            ORDER BY c.cart_id
        """)

        self.assertEqual(
            [row[0] for row in self.cursor.fetchall()],
            ["CART2"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)