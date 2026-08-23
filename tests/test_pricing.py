from b2_stats import pricing


def test_zero_bytes_is_free():
    assert pricing.estimate_monthly_cost(0) == 0.0


def test_one_tb_costs_six_dollars():
    one_tb = 1000 * 1024**3  # pricing is per GiB, priced against a decimal TB
    cost = pricing.estimate_monthly_cost(one_tb)
    assert cost == round(6.0, 4)


def test_cost_scales_linearly():
    small = pricing.estimate_monthly_cost(10 * 1024**3)
    large = pricing.estimate_monthly_cost(100 * 1024**3)
    assert round(large / small, 2) == 10.0
