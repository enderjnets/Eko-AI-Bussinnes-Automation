"""Custom exceptions for Eko AI Business Automation."""


class EkoAIException(Exception):
    """Base exception for all Eko AI errors."""
    pass


class LeadNotFoundException(EkoAIException):
    """Raised when a lead is not found."""
    pass


class InvalidTransitionException(EkoAIException):
    """Raised when an invalid pipeline transition is attempted."""
    pass


class ComplianceException(EkoAIException):
    """Raised when a compliance rule is violated (TCPA, CAN-SPAM, etc.)."""
    pass


class EmailDeliveryException(EkoAIException):
    """Raised when email delivery fails."""
    pass


class DiscoveryException(EkoAIException):
    """Raised when discovery fails."""
    pass
