from app.core.calculation import calculate_commission, calculate_management_share


def test_calculate_commission_exact():
    # 18.000 -> 10% adalah 1.800 persis
    assert calculate_commission(18000) == 1800


def test_calculate_commission_rounded_up():
    # 18.005 -> 10% adalah 1800.5 -> pembulatan ke atas jadi 1801
    assert calculate_commission(18005) == 1801
    # 10.001 -> 1000.1 -> 1001
    assert calculate_commission(10001) == 1001


def test_calculate_commission_zero_or_negative():
    assert calculate_commission(0) == 0
    assert calculate_commission(-500) == 0


def test_calculate_management_share():
    omzet = 18000
    comm = calculate_commission(omzet)
    share = calculate_management_share(omzet, comm)
    assert share == 16200
    assert share + comm == omzet
