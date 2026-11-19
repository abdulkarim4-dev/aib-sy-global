import base64
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app as aib


class AIBRegressionTests(unittest.TestCase):
    def test_invoice_branding_keeps_owner_and_user_identities_separate(self):
        source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn("me?.role!=='owner'?'user-invoice':'owner-invoice'", source)
        self.assertIn('#print .head>.brandblock:before{content:"AIB  |  TRADING GROUP"', source)
        self.assertIn("#print .user-invoice .head>.brandblock:before", source)
        self.assertIn("#print .user-invoice .head>.brandblock:after", source)
        self.assertIn("content:none!important", source)
        self.assertIn("invoiceBrand=me?.role==='owner'?'default'", source)

    def test_invoice_logo_and_payment_qr_assets_are_real_png_files(self):
        assets = (
            ROOT / "frontend" / "file_00000000d68c81f490ddf34ada4cb0b8.png",
            ROOT / "frontend" / "sham_cash_qr.png",
        )
        for asset in assets:
            self.assertTrue(asset.is_file(), f"Missing asset: {asset.name}")
            data = asset.read_bytes()
            self.assertGreater(len(data), 100)
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertGreater(int.from_bytes(data[16:20], "big"), 0)
            self.assertGreater(int.from_bytes(data[20:24], "big"), 0)

    def test_public_product_image_handler_decodes_supported_data_uri(self):
        raw = b"image-bytes-for-route-test"
        encoded = base64.b64encode(raw).decode("ascii")
        product = SimpleNamespace(active=True, images=[f"data:image/png;base64,{encoded}"])
        fake_session = SimpleNamespace(get=lambda model, product_id: product)
        response = aib.get_public_product_image(101, 0, fake_session)
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.body, raw)

    def test_public_product_image_handler_rejects_invalid_index(self):
        product = SimpleNamespace(active=True, images=["data:image/png;base64,aW1hZ2U="])
        fake_session = SimpleNamespace(get=lambda model, product_id: product)
        with self.assertRaises(aib.HTTPException) as caught:
            aib.get_public_product_image(101, 1, fake_session)
        self.assertEqual(caught.exception.status_code, 404)

    def test_gmail_smtp_sender_builds_and_submits_message(self):
        captured = {}

        class FakeSMTP:
            def __init__(self, host, port, timeout):
                captured["connection"] = (host, port, timeout)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def ehlo(self):
                captured["ehlo"] = captured.get("ehlo", 0) + 1

            def starttls(self):
                captured["tls"] = True

            def login(self, username, password):
                captured["login"] = (username, password)

            def send_message(self, message):
                captured["message"] = message

        names = ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from")
        previous = {name: getattr(aib.settings, name) for name in names}
        try:
            aib.settings.smtp_host = "smtp.test.invalid"
            aib.settings.smtp_port = 587
            aib.settings.smtp_user = "ci-sender@example.test"
            aib.settings.smtp_password = "ci-only-password"
            aib.settings.smtp_from = "AIB CI <ci-sender@example.test>"
            with patch.object(aib.smtplib, "SMTP", FakeSMTP):
                aib.send_aib_email(
                    "ci-recipient@example.test",
                    "AIB SMTP test",
                    "This is an isolated CI message.",
                )
        finally:
            for name, value in previous.items():
                setattr(aib.settings, name, value)

        self.assertEqual(captured["connection"], ("smtp.test.invalid", 587, 25))
        self.assertTrue(captured["tls"])
        self.assertEqual(captured["login"], ("ci-sender@example.test", "ci-only-password"))
        self.assertEqual(captured["message"]["To"], "ci-recipient@example.test")
        self.assertEqual(captured["message"]["Subject"], "AIB SMTP test")
        self.assertIn("isolated CI message", captured["message"].get_content())

    def test_store_password_reset_request_and_confirmation(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        email = f"ci-reset-{uuid4().hex}@example.test"
        new_password = "NewStrongPass123"
        captured = {}

        with TestClient(aib.app) as client:
            with aib.SessionLocal() as session:
                customer = aib.StoreCustomer(
                    email=email,
                    full_name="AIB CI Customer",
                    password_hash=aib.password_hash.hash("OldStrongPass123"),
                    cart=[],
                    active=True,
                )
                session.add(customer)
                session.commit()
                customer_id = customer.id

            try:
                with patch.object(
                    aib,
                    "send_verification_email",
                    side_effect=lambda recipient, code: captured.update(
                        {"recipient": recipient, "code": code}
                    ),
                ), patch.object(aib, "notify_account_change"):
                    request_response = client.post(
                        "/store/auth/password-reset/request",
                        json={"email": email},
                    )
                    self.assertEqual(request_response.status_code, 200)
                    self.assertTrue(request_response.json().get("ok"))
                    self.assertEqual(captured.get("recipient"), email)
                    self.assertRegex(captured.get("code", ""), r"^\d{6}$")

                    unknown_response = client.post(
                        "/store/auth/password-reset/request",
                        json={"email": f"unknown-{uuid4().hex}@example.test"},
                    )
                    self.assertEqual(unknown_response.status_code, 200)
                    self.assertEqual(unknown_response.json(), request_response.json())

                    confirm_response = client.post(
                        "/store/auth/password-reset/confirm",
                        json={
                            "email": email,
                            "code": captured["code"],
                            "new_password": new_password,
                        },
                    )
                    self.assertEqual(confirm_response.status_code, 200)
                    self.assertTrue(confirm_response.json().get("ok"))

                with aib.SessionLocal() as session:
                    saved = session.scalar(
                        select(aib.StoreCustomer).where(aib.StoreCustomer.id == customer_id)
                    )
                    self.assertTrue(aib.password_hash.verify(new_password, saved.password_hash))
                    remaining = session.scalar(
                        select(aib.func.count()).select_from(aib.StorePasswordReset).where(
                            aib.StorePasswordReset.customer_id == customer_id
                        )
                    )
                    self.assertEqual(remaining, 0)
            finally:
                with aib.SessionLocal() as session:
                    session.query(aib.StorePasswordReset).filter_by(customer_id=customer_id).delete()
                    session.query(aib.StoreCustomer).filter_by(id=customer_id).delete()
                    session.commit()


if __name__ == "__main__":
    unittest.main()
