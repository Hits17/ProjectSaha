"""
Custom Prometheus business metrics for Saha. Exposed at /metrics (mounted in main.py).
Defined once at import time so the default registry isn't double-populated.
"""

from prometheus_client import Counter, Histogram

# --- Marketplace activity ---
searches_total = Counter("saha_searches_total", "Semantic searches executed")
search_zero_results_total = Counter(
    "saha_search_zero_results_total", "Searches that returned no matching listings"
)
listings_published_total = Counter("saha_listings_published_total", "Listings published to the marketplace")
materials_created_total = Counter(
    "saha_materials_created_total", "Raw material listings created (secondary marketplace)"
)

# --- Social ---
communities_created_total = Counter(
    "saha_communities_created_total", "IP R&D communities created"
)
community_messages_total = Counter(
    "saha_community_messages_total", "Messages posted in community chat"
)

# --- Deal funnel ---
proposals_created_total = Counter("saha_proposals_created_total", "Proposals created")
transactions_created_total = Counter(
    "saha_transactions_created_total", "Transactions created from accepted proposals"
)
transactions_completed_total = Counter(
    "saha_transactions_completed_total", "Transactions completed (funds disbursed)"
)
reviews_created_total = Counter("saha_reviews_created_total", "Post-transaction reviews submitted")

# --- Money ---
deal_value_usd = Histogram(
    "saha_deal_value_usd",
    "Distribution of transaction deal values (USD)",
    buckets=(1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000),
)
disbursed_usd_total = Counter(
    "saha_disbursed_usd_total", "Cumulative USD disbursed to IP holders"
)
commission_usd_total = Counter(
    "saha_commission_usd_total", "Cumulative Saha commission collected (USD)"
)

# ── Social feed ──────────────────────────────────────────────────────────────
posts_created_total = Counter("saha_posts_created_total", "Feed posts created")
post_votes_total = Counter("saha_post_votes_total", "Votes cast on posts and comments")
