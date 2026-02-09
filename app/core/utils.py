"""Core utility functions for the application"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Union


def calculate_due_date(invoice_date: date, days: int = 15) -> date:
    """
    Calculate due date by adding specified days to invoice date.

    Args:
        invoice_date: The invoice date
        days: Number of days to add (default: 15)

    Returns:
        date: The calculated due date
    """
    return invoice_date + timedelta(days=days)


def amount_to_words(amount: Union[Decimal, float, int]) -> str:
    """
    Convert a numeric amount to Indian English words.
    """

    # Normalize to Decimal and round to 2 places
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Handle negative values explicitly
    if amount < 0:
        return "MINUS " + amount_to_words(abs(amount))

    rupees = int(amount)
    paise = int((amount - Decimal(rupees)) * 100)

    if rupees == 0 and paise == 0:
        return "ZERO RUPEES ONLY"

    rupees_words = _number_to_words(rupees)

    result = f"{rupees_words} RUPEE" if rupees == 1 else f"{rupees_words} RUPEES"

    if paise > 0:
        paise_words = _number_to_words(paise)
        result += f" AND {paise_words} PAISE"

    result += " ONLY"

    return result


def _number_to_words(n: int) -> str:
    """
    Convert a number (0-999,999,999) to words.

    Args:
        n: Number to convert (up to 999 million)

    Returns:
        str: Number in words
    """
    if n == 0:
        return "ZERO"

    # Define word arrays
    ones = [
        "",
        "ONE",
        "TWO",
        "THREE",
        "FOUR",
        "FIVE",
        "SIX",
        "SEVEN",
        "EIGHT",
        "NINE",
        "TEN",
        "ELEVEN",
        "TWELVE",
        "THIRTEEN",
        "FOURTEEN",
        "FIFTEEN",
        "SIXTEEN",
        "SEVENTEEN",
        "EIGHTEEN",
        "NINETEEN",
    ]

    tens = [
        "",
        "",
        "TWENTY",
        "THIRTY",
        "FORTY",
        "FIFTY",
        "SIXTY",
        "SEVENTY",
        "EIGHTY",
        "NINETY",
    ]

    def _convert_chunk(num: int) -> str:
        """Convert a number less than 1000 to words."""
        if num == 0:
            return ""
        elif num < 20:
            return ones[num]
        elif num < 100:
            return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
        else:
            hundred_part = ones[num // 100] + " HUNDRED"
            remainder = num % 100
            if remainder > 0:
                return hundred_part + " AND " + _convert_chunk(remainder)
            return hundred_part

    # Handle Indian numbering system (lakh, crore)
    if n >= 10000000:  # Crores
        crores = n // 10000000
        remainder = n % 10000000
        result = _convert_chunk(crores) + " CRORE"
        if remainder > 0:
            result += " " + _number_to_words(remainder)
        return result
    elif n >= 100000:  # Lakhs
        lakhs = n // 100000
        remainder = n % 100000
        result = _convert_chunk(lakhs) + " LAKH"
        if remainder > 0:
            result += " " + _number_to_words(remainder)
        return result
    elif n >= 1000:  # Thousands
        thousands = n // 1000
        remainder = n % 1000
        result = _convert_chunk(thousands) + " THOUSAND"
        if remainder > 0:
            result += " " + _convert_chunk(remainder)
        return result
    else:
        return _convert_chunk(n)


def format_invoice_date(date_obj: date) -> str:
    """
    Format a date object for invoice display.

    Args:
        date_obj: The date to format

    Returns:
        str: Formatted date (e.g., "05-Feb-2026")
    """
    return date_obj.strftime("%d-%b-%Y")
