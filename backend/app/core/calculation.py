import math


def calculate_commission(omzet: int) -> int:
    """Calculate 10% commission rounded UP to the nearest whole Rupiah per report."""
    if omzet <= 0:
        return 0
    return math.ceil(omzet * 0.10)


def calculate_management_share(omzet: int, commission: int) -> int:
    """Calculate management's share of revenue (remaining omzet after commission)."""
    return max(0, omzet - commission)
