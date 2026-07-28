from app import entitlements


def test_quota_limit_free_is_daily_limit():
    assert entitlements.quota_limit("free") == entitlements.FREE_DAILY_CASE_LIMIT


def test_quota_limit_premium_is_monthly_agent_limit():
    assert entitlements.quota_limit("premium") == entitlements.PREMIUM_MONTHLY_AGENT_LIMIT


def test_is_over_quota_false_below_limit():
    assert entitlements.is_over_quota(entitlements.FREE_DAILY_CASE_LIMIT - 1, "free") is False


def test_is_over_quota_true_at_limit():
    # >= limit, not > limit — the Nth case (0-indexed count == limit) is
    # the one that gets rejected.
    assert entitlements.is_over_quota(entitlements.FREE_DAILY_CASE_LIMIT, "free") is True


def test_is_over_quota_true_above_limit():
    assert entitlements.is_over_quota(entitlements.FREE_DAILY_CASE_LIMIT + 1, "free") is True


def test_history_limit_free_is_one():
    assert entitlements.history_limit("free", "user") == 1


def test_history_limit_premium_is_unlimited():
    assert entitlements.history_limit("premium", "user") is None


def test_history_limit_admin_is_unlimited_even_on_free_tier():
    # role bypass wins regardless of the account's own tier.
    assert entitlements.history_limit("free", "admin") is None


def test_history_limit_support_follows_tier_like_a_normal_user():
    # 'support' has no special behavior yet — scoped for future use.
    assert entitlements.history_limit("free", "support") == 1


def test_locked_features_free_is_nonempty():
    features = entitlements.locked_features("free")
    assert features == entitlements.LOCKED_FEATURES_FREE
    assert len(features) > 0


def test_locked_features_premium_is_none():
    assert entitlements.locked_features("premium") is None
