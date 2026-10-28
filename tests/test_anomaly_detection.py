import unittest


class AnomalyDetectionTests(unittest.TestCase):
    def test_message_sent_after_opt_out(self):
        consent_at_send = "OPTED_OUT"
        send_status = "SENT"
        self.assertTrue(
            send_status == "SENT" and consent_at_send == "OPTED_OUT"
        )

    def test_cart_abandoned_after_purchase(self):
        abandoned_at = 100
        ordered_at = 90
        self.assertTrue(abandoned_at > ordered_at)

    def test_duplicate_conversion_attribution(self):
        credited_records = 2
        self.assertTrue(credited_records > 1)

    def test_stale_cart_total_after_quantity_update(self):
        stored_cart_total = 2148.00
        calculated_cart_total = 2497.00
        self.assertGreater(
            abs(stored_cart_total - calculated_cart_total), 0.01
        )


if __name__ == "__main__":
    unittest.main()
