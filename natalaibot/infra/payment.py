from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    is_paid: bool
    payment_id: str | None = None


class PaymentService:
    async def request_payment(self, telegram_user_id: int) -> PaymentResult:
        return PaymentResult(is_paid=True, payment_id=f"stub-{telegram_user_id}")
