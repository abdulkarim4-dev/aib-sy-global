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
    def test_store_registration_requires_recipient_phone_and_shipping_address(self):
        address = {
            "country": "تركيا",
            "province": "أنقرة",
            "region": "كيجي أورن",
            "district": "إتليك",
            "address_line1": "شارع الاختبار 10",
            "address_line2": "الطابق الأول",
        }
        with self.assertRaises(Exception):
            aib.StoreRegisterPayload(full_name="اسم المستلم",email="buyer@example.com",password="StrongPass123")
        with self.assertRaises(Exception):
            aib.StoreRegisterPayload(full_name="اسم المستلم",phone_country_code="+90",phone_number="5321234567",email="buyer@example.com",password="StrongPass123")
        payload=aib.StoreRegisterPayload(full_name="اسم المستلم",phone_country_code="+90",phone_number="5321234567",shipping_address_data=address,email="buyer@example.com",password="StrongPass123")
        self.assertEqual(payload.phone_country_code,"+90")
        self.assertEqual(aib._store_phone_e164(payload.phone_country_code,payload.phone_number),"+905321234567")
        self.assertTrue(aib._store_address_complete(payload.shipping_address_data))

    def test_store_phone_removes_trunk_zero_and_respects_e164_maximum_length(self):
        self.assertEqual(aib._store_phone_e164("+963", "0912345678"), "+963912345678")
        self.assertEqual(aib._store_phone_e164("+90", "05321234567"), "+905321234567")
        self.assertEqual(aib._store_phone_e164("+963", "123456789012"), "+963123456789012")
        with self.assertRaises(aib.HTTPException):
            aib._store_phone_e164("+963", "1234567890123")
        with self.assertRaises(aib.HTTPException):
            aib._store_phone_e164("+123", "+963912345678")

    def test_store_phone_inputs_show_country_specific_guidance(self):
        source = (ROOT / "frontend" / "shop.html").read_text(encoding="utf-8")
        self.assertIn("option.dataset.countryName=row.arabic", source)
        self.assertIn("input.placeholder=countryName?'رقم محلي لـ '+countryName+' بعد '+dialCode", source)
        self.assertIn("input.setAttribute('aria-description',guidance)", source)
        self.assertIn(".replace(/^0+/, '')", source)
        self.assertIn("input.maxLength=max", source)
        self.assertNotIn("input.placeholder='9 1 2 3 4 5 6 7 8'", source)
        self.assertNotIn("store-phone-length-hint", source)

    def test_all_store_phone_fields_share_complete_international_dial_code_list(self):
        import json
        import re
        source = (ROOT / "frontend" / "shop.html").read_text(encoding="utf-8")
        match = re.search(r"const AIB_COUNTRY_DIAL_CODES=(\[.*?\]);", source, re.S)
        self.assertIsNotNone(match)
        countries = json.loads(match.group(1))
        self.assertGreaterEqual(len(countries), 230)
        self.assertEqual(len({row["code"] for row in countries}), len(countries))
        self.assertIn({"name": "Germany", "code": "DE", "dial": "+49"}, countries)
        self.assertIn({"name": "Turkey", "code": "TR", "dial": "+90"}, countries)
        self.assertIn({"name": "Cayman Islands", "code": "KY", "dial": "+1345"}, countries)
        self.assertIn("Intl.DisplayNames(['ar'],{type:'region'})", source)
        for element_id in ("storePhoneCountry", "storeRequiredRecipientDial", "aibProfileDial", "coDial"):
            self.assertIn(element_id, source)

    def test_store_signup_cannot_skip_recipient_or_address_steps(self):
        source = (ROOT / "frontend" / "shop.html").read_text(encoding="utf-8")
        self.assertIn('id="storeFullName" type="text"', source)
        self.assertIn('id="storeRecipientPhone" type="tel"', source)
        self.assertIn('id="storeSignupAddressField"', source)
        self.assertIn("shipping_address_data:pendingStoreRegistrationAddress", source)
        self.assertIn("!pendingStoreRegistrationAddress", source)
        self.assertIn("storeAuthMode==='register'", source)
        self.assertIn("closeButton.hidden=reg", source)

    def test_existing_store_accounts_complete_address_then_recipient_in_sequence(self):
        source = (ROOT / "frontend" / "shop.html").read_text(encoding="utf-8")
        self.assertIn('id="storeRequiredProfileWizard"', source)
        self.assertIn('id="storeRequiredAddressCard"', source)
        self.assertIn('id="storeRequiredRecipientCard"', source)
        self.assertIn('id="storeRequiredRecipientForm"', source)
        self.assertIn("if(addressCard)addressCard.hidden=!addressMissing", source)
        self.assertIn("if(recipientCard)recipientCard.hidden=addressMissing||!phoneMissing", source)
        self.assertIn("openStoreAddressModal(true)", source)
        self.assertIn("saveRequiredStoreRecipient", source)
        self.assertIn("'/store/auth/profile'", source)
        self.assertIn("renderStoreRequiredProfileWizard()", source)
        self.assertIn("closeButton.hidden=addressMissing||phoneMissing", source)
        self.assertIn("settings.hidden=addressMissing||phoneMissing", source)
        self.assertIn("!isStoreAddressComplete(storeCustomer.shipping_address_data)||!storeCustomer.phone_number", source)

    def test_all_application_invoices_use_only_the_aib_issuer_identity(self):
        source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn("const invoiceBrand='default'", source)
        self.assertIn("const invoiceCompanyLogo='/aib-logo.png?v=20261113-aib2'", source)
        self.assertIn("companyProfile=await api('/company-profile')", source)
        self.assertNotIn("userInvoiceProfile=await api('/my-profile')", source)
        self.assertNotIn("invoiceBrand=me?.role==='owner'?", source)
        self.assertIn("me?.role!=='owner'?'user-invoice':'owner-invoice'", source)
        self.assertIn("'/aib-logo.png?v=20261113-aib2'", source)
        self.assertIn("مجموعة AIB التجارية", source)

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
        product = SimpleNamespace(active=True, is_store_visible=True, images=[f"data:image/png;base64,{encoded}"])
        fake_session = SimpleNamespace(get=lambda model, product_id: product)
        response = aib.get_public_product_image(101, 0, fake_session)
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.body, raw)

    def test_public_product_image_handler_rejects_invalid_index(self):
        product = SimpleNamespace(active=True, is_store_visible=True, images=["data:image/png;base64,aW1hZ2U="])
        fake_session = SimpleNamespace(get=lambda model, product_id: product)
        with self.assertRaises(aib.HTTPException) as caught:
            aib.get_public_product_image(101, 1, fake_session)
        self.assertEqual(caught.exception.status_code, 404)


    def test_storefront_category_asset_is_served_from_allowlist(self):
        response = aib.public_store_asset("aib-tourist-cars.jpg")
        self.assertEqual(response.media_type, "image/jpeg")
        self.assertTrue(Path(response.path).is_file())

    def test_storefront_category_asset_rejects_unlisted_files(self):
        with self.assertRaises(aib.HTTPException) as caught:
            aib.public_store_asset("../app.py")
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


    def test_public_search_loads_catalogue_before_ranking_products(self):
        import inspect

        source = inspect.getsource(aib.public_products)
        catalogue_load = source.index("store_categories,latest_purchase=latest_store_catalog_data(s)")
        ranking_use = source.index("explicit=store_categories.get(product.sku,{})")
        self.assertLess(catalogue_load, ranking_use)

    def test_public_search_keeps_arabic_terms_and_engine_codes(self):
        self.assertEqual(
            aib._normalize_public_search_query("محرك N 63"),
            "محرك N 63",
        )
        self.assertEqual(
            aib._public_search_terms("محرك N 63"),
            ["محرك", "N", "63"],
        )
        self.assertEqual(
            aib._normalize_public_search_query("['مكينة N63']"),
            "مكينة N63",
        )

    def test_public_search_splits_multi_word_queries_and_unwraps_list_queries(self):
        self.assertEqual(
            aib._normalize_public_search_query("['BMW TwinPower Turbo engine cover']"),
            "BMW TwinPower Turbo engine cover",
        )
        self.assertEqual(
            aib._public_search_terms("BMW TwinPower Turbo engine cover"),
            ["BMW", "TwinPower", "Turbo", "engine", "cover"],
        )

    def test_public_search_escapes_sql_like_wildcards(self):
        self.assertEqual(aib._public_search_like_pattern("N20_100%"), "%N20!_100!%%")


    def test_store_phone_guidance_changes_with_selected_country(self):
        shop = (ROOT / "frontend" / "shop.html").read_text(encoding="utf-8")
        self.assertIn("option.dataset.countryName=row.arabic", shop)
        self.assertIn("input.placeholder=countryName?'رقم محلي لـ '+countryName+' بعد '+dialCode", shop)
        self.assertIn("input.setAttribute('aria-description',guidance)", shop)
        self.assertNotIn("input.placeholder='9 1 2 3 4 5 6 7 8'", shop)


if __name__ == "__main__":
    unittest.main()
