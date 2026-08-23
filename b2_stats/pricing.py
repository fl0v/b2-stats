"""Estimated cost math for B2 storage.

B2's native API has no billing endpoint, so this is an ESTIMATE based on
Backblaze's published storage pricing, applied to the bytes actually stored
(as counted by b2_client). It intentionally ignores download/egress and
Class A/B/C transaction charges, since none of that is retrievable from the
API this tool uses — for a backup-style bucket (write once, rarely
download), storage is the dominant and most stable cost component anyway.

Source: https://www.backblaze.com/cloud-storage/pricing (checked 2026-08-23)
  Storage: $6.00 per TB per month == $0.006 per GB-month
"""
from __future__ import annotations

GB = 1024 ** 3
PRICE_PER_GB_MONTH = 6.00 / 1000  # $6/TB/month


def estimate_monthly_cost(total_bytes: int) -> float:
    gb = total_bytes / GB
    return round(gb * PRICE_PER_GB_MONTH, 4)
