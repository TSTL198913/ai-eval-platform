from src.exceptions import (
    BasePlatformError,
    ContractValidationError,
    DomainLogicError,
    InfrastructureError,
)


def test_exception_codes():
    assert ContractValidationError().code == "CONTRACT_ERROR"
    assert DomainLogicError().code == "DOMAIN_ERROR"
    assert InfrastructureError().code == "INFRA_ERROR"


def test_custom_message_preserved():
    err = DomainLogicError("adapter missing")
    assert err.message == "adapter missing"
    assert str(err) == "adapter missing"


def test_base_platform_error_default_code():
    err = BasePlatformError("generic")
    assert err.code == "INTERNAL_ERROR"
