"""Job provider adapters: Greenhouse, Lever, Naukri, Wellfound, LinkedIn."""

from worker.providers.base import FormField, FormFillResult, JobProvider
from worker.providers.greenhouse import GreenhouseProvider

__all__ = [
    "FormField",
    "FormFillResult",
    "GreenhouseProvider",
    "JobProvider",
]
