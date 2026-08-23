from __future__ import annotations

from dataclasses import dataclass, asdict

from . import b2_client, pricing
from .config import Config


@dataclass
class BucketStats:
    name: str
    file_count: int
    current_bytes: int
    total_bytes_incl_versions: int
    estimated_monthly_cost: float

    def to_dict(self) -> dict:
        return asdict(self)


def _bucket_stats(auth: b2_client.AuthContext, bucket: b2_client.Bucket, include_all_versions: bool) -> BucketStats:
    file_count = 0
    current_bytes = 0
    for entry in b2_client.iter_file_names(auth, bucket.bucket_id):
        file_count += 1
        current_bytes += entry.content_length

    if include_all_versions:
        total_bytes = sum(
            entry.content_length
            for entry in b2_client.iter_file_versions(auth, bucket.bucket_id)
        )
    else:
        total_bytes = current_bytes

    return BucketStats(
        name=bucket.bucket_name,
        file_count=file_count,
        current_bytes=current_bytes,
        total_bytes_incl_versions=total_bytes,
        estimated_monthly_cost=pricing.estimate_monthly_cost(total_bytes),
    )


def collect(config: Config) -> list[BucketStats]:
    auth = b2_client.authorize(config.application_key_id, config.application_key)
    buckets = b2_client.list_buckets(auth)
    return [
        _bucket_stats(auth, bucket, config.include_all_versions)
        for bucket in buckets
    ]


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def format_table(bucket_stats: list[BucketStats], fetched_at: str | None = None) -> str:
    headers = ("Bucket", "Files", "Current size", "Size incl. versions", "Est. $/month")
    rows = [
        (
            b.name,
            str(b.file_count),
            human_size(b.current_bytes),
            human_size(b.total_bytes_incl_versions),
            f"${b.estimated_monthly_cost:.2f}",
        )
        for b in bucket_stats
    ]

    total_files = sum(b.file_count for b in bucket_stats)
    total_current = sum(b.current_bytes for b in bucket_stats)
    total_all = sum(b.total_bytes_incl_versions for b in bucket_stats)
    total_cost = sum(b.estimated_monthly_cost for b in bucket_stats)
    rows.append((
        "TOTAL",
        str(total_files),
        human_size(total_current),
        human_size(total_all),
        f"${total_cost:.2f}",
    ))

    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))]

    def fmt_row(cols: tuple) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))

    lines = [fmt_row(headers), "  ".join("-" * w for w in widths)]
    lines.extend(fmt_row(r) for r in rows[:-1])
    lines.append("  ".join("-" * w for w in widths))
    lines.append(fmt_row(rows[-1]))

    if fetched_at:
        lines.append("")
        lines.append(f"(as of {fetched_at}; cost is a storage-only estimate, not a bill)")
    else:
        lines.append("")
        lines.append("(cost is a storage-only estimate, not a bill)")

    return "\n".join(lines)
