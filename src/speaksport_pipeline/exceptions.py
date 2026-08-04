class SpeakSportError(Exception):
    """Base exception for actionable pipeline failures."""


class ConfigurationError(SpeakSportError):
    """Raised when project or facility configuration is invalid."""


class ReferenceError(SpeakSportError):
    """Raised when a versioned reference is missing or has changed unexpectedly."""


class ProviderError(SpeakSportError):
    """Raised when a remote provider returns an actionable failure."""


class BudgetExceededError(ProviderError):
    """Raised when a configured inference budget would be exceeded."""
