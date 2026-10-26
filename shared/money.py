from decimal import Decimal, InvalidOperation
from fastapi import HTTPException

def pennies(value: str) -> int:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            raise ValueError
        return int(amount * 100)
    except (ValueError, InvalidOperation):
        raise HTTPException(422, 'Invalid GBP amount (e.g. 649.99)')
