"""Payment provider abstraction + Safaricom Daraja implementation.

Safety rules enforced here:
* Sandbox calls never move real money.
* Production calls are refused unless `settings.live_money_allowed` is true
  (LIVE_PAYMENTS_ENABLED + COMPLIANCE_SIGNOFF_REF + DARAJA_ENV=production).
* This module never reports a payment as successful by itself. Success is
  only recorded by the callback handlers in services/mythic.py.
"""
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from ..config import settings


class ProviderError(Exception):
    pass


class LiveMoneyDisabled(ProviderError):
    pass


@dataclass
class StkResult:
    checkout_request_id: str
    merchant_request_id: str


@dataclass
class B2CResult:
    conversation_id: str


class PaymentProvider(ABC):
    @abstractmethod
    def stk_push(self, phone: str, amount: int, reference: str, description: str) -> StkResult: ...

    @abstractmethod
    def b2c_payout(self, phone: str, amount: int, reference: str, remarks: str) -> B2CResult: ...

    @abstractmethod
    def stk_status(self, checkout_request_id: str) -> dict: ...


class DarajaProvider(PaymentProvider):
    def __init__(self):
        self.base = ("https://api.safaricom.co.ke" if settings.DARAJA_ENV == "production"
                     else "https://sandbox.safaricom.co.ke")

    def _guard(self):
        if settings.DARAJA_ENV == "production" and not settings.live_money_allowed:
            raise LiveMoneyDisabled(
                "Live transactions are disabled until legal and provider compliance sign-off is recorded.")

    def _token(self) -> str:
        r = httpx.get(f"{self.base}/oauth/v1/generate?grant_type=client_credentials",
                      auth=(settings.DARAJA_CONSUMER_KEY, settings.DARAJA_CONSUMER_SECRET), timeout=20)
        r.raise_for_status()
        return r.json()["access_token"]

    def _post(self, path: str, payload: dict) -> dict:
        self._guard()
        try:
            r = httpx.post(f"{self.base}{path}", json=payload, timeout=30,
                           headers={"Authorization": f"Bearer {self._token()}"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"Provider request failed: {e}") from e
        return r.json()

    def _password(self, ts: str) -> str:
        return base64.b64encode(f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{ts}".encode()).decode()

    def stk_push(self, phone, amount, reference, description):
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        data = self._post("/mpesa/stkpush/v1/processrequest", {
            "BusinessShortCode": settings.DARAJA_SHORTCODE,
            "Password": self._password(ts), "Timestamp": ts,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount, "PartyA": phone, "PartyB": settings.DARAJA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": f"{settings.PUBLIC_BASE_URL}/api/mythic/callbacks/{settings.CALLBACK_SECRET}/stk",
            "AccountReference": reference[:12], "TransactionDesc": description[:13],
        })
        if str(data.get("ResponseCode")) != "0":
            raise ProviderError(data.get("ResponseDescription", "STK push rejected"))
        return StkResult(data["CheckoutRequestID"], data["MerchantRequestID"])

    def stk_status(self, checkout_request_id):
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return self._post("/mpesa/stkpushquery/v1/query", {
            "BusinessShortCode": settings.DARAJA_SHORTCODE, "Password": self._password(ts),
            "Timestamp": ts, "CheckoutRequestID": checkout_request_id})

    def b2c_payout(self, phone, amount, reference, remarks):
        base = f"{settings.PUBLIC_BASE_URL}/api/mythic/callbacks/{settings.CALLBACK_SECRET}"
        data = self._post("/mpesa/b2c/v3/paymentrequest", {
            "OriginatorConversationID": reference,
            "InitiatorName": settings.DARAJA_INITIATOR_NAME,
            "SecurityCredential": settings.DARAJA_SECURITY_CREDENTIAL,
            "CommandID": "BusinessPayment", "Amount": amount,
            "PartyA": settings.DARAJA_SHORTCODE, "PartyB": phone,
            "Remarks": remarks[:100], "QueueTimeOutURL": f"{base}/b2c-timeout",
            "ResultURL": f"{base}/b2c-result", "Occasion": reference[:100],
        })
        if str(data.get("ResponseCode")) != "0":
            raise ProviderError(data.get("ResponseDescription", "B2C rejected"))
        return B2CResult(data.get("OriginatorConversationID", reference))


_provider: PaymentProvider | None = None


def get_provider() -> PaymentProvider:
    global _provider
    if _provider is None:
        _provider = DarajaProvider()
    return _provider


def set_provider(p: PaymentProvider | None):
    """Used by tests to inject a stub. Never called by application code."""
    global _provider
    _provider = p
