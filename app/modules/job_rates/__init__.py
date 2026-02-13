"""Job rates (operations) module - product operations with rate and sequence."""

from app.modules.job_rates.models import JobRate
from app.modules.job_rates.router import router

__all__ = ["JobRate", "router"]
