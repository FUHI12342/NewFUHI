# booking/services/basket_analysis.py
"""Market basket analysis — association rules from order data.

Uses a pure-Python implementation of association rule mining.
If mlxtend is available, uses Apriori; otherwise falls back to
brute-force pairwise analysis (sufficient for typical restaurant menus).
"""
import logging
from collections import defaultdict
from datetime import timedelta
from itertools import combinations

from django.db.models import F
from django.utils import timezone

from booking.models import OrderItem

logger = logging.getLogger(__name__)


def analyze_basket(scope=None, days=90, min_support=0.01, min_confidence=0.1, top_n=20):
    """Compute association rules from order transactions.

    Args:
        scope: dict filter kwargs for OrderItem (e.g. {'order__store': store})
        days: lookback period
        min_support: minimum support threshold
        min_confidence: minimum confidence threshold
        top_n: max number of rules to return

    Returns:
        dict with 'rules', 'total_transactions', 'method'
    """
    if scope is None:
        scope = {}
    since = timezone.now() - timedelta(days=days)

    # Build transactions: group products by order_id
    items = (
        OrderItem.objects
        .filter(order__created_at__gte=since, **scope)
        .values('order_id', 'product__name')
    )

    transactions = defaultdict(set)
    for item in items:
        transactions[item['order_id']].add(item['product__name'])

    # Filter to orders with 2+ items
    baskets = [t for t in transactions.values() if len(t) >= 2]
    total = len(baskets)

    if total < 3:
        return {'rules': [], 'total_transactions': total, 'method': 'none'}

    try:
        rules = _try_mlxtend(baskets, min_support, min_confidence, top_n)
        if rules is not None:
            return {'rules': rules, 'total_transactions': total, 'method': 'apriori'}
    except Exception as e:
        logger.debug(f"mlxtend not available: {e}")

    # Fallback: pairwise analysis
    rules = _pairwise_analysis(baskets, total, min_support, min_confidence, top_n)
    return {'rules': rules, 'total_transactions': total, 'method': 'pairwise'}


def _try_mlxtend(baskets, min_support, min_confidence, top_n):
    """Try to use mlxtend Apriori algorithm."""
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
        import pandas as pd
    except ImportError:
        return None

    te = TransactionEncoder()
    te_ary = te.fit(baskets).transform(baskets)
    df = pd.DataFrame(te_ary, columns=te.columns_)

    frequent = apriori(df, min_support=min_support, use_colnames=True)
    if frequent.empty:
        return []

    rules_df = association_rules(frequent, metric='confidence', min_threshold=min_confidence)
    if rules_df.empty:
        return []

    rules_df = rules_df.sort_values('lift', ascending=False).head(top_n)

    rules = []
    for _, row in rules_df.iterrows():
        rules.append({
            'antecedent': list(row['antecedents']),
            'consequent': list(row['consequents']),
            'support': round(float(row['support']), 4),
            'confidence': round(float(row['confidence']), 4),
            'lift': round(float(row['lift']), 3),
        })
    return rules


def _pairwise_analysis(baskets, total, min_support, min_confidence, top_n):
    """Pure-Python pairwise association rule mining."""
    # Count individual item frequency
    item_count = defaultdict(int)
    pair_count = defaultdict(int)

    for basket in baskets:
        items = sorted(basket)
        for item in items:
            item_count[item] += 1
        for a, b in combinations(items, 2):
            pair_count[(a, b)] += 1

    rules = []
    for (a, b), count in pair_count.items():
        support = count / total
        if support < min_support:
            continue

        # A → B
        conf_ab = count / item_count[a] if item_count[a] > 0 else 0
        lift_ab = conf_ab / (item_count[b] / total) if item_count[b] > 0 else 0
        if conf_ab >= min_confidence:
            rules.append({
                'antecedent': [a],
                'consequent': [b],
                'support': round(support, 4),
                'confidence': round(conf_ab, 4),
                'lift': round(lift_ab, 3),
            })

        # B → A
        conf_ba = count / item_count[b] if item_count[b] > 0 else 0
        lift_ba = conf_ba / (item_count[a] / total) if item_count[a] > 0 else 0
        if conf_ba >= min_confidence:
            rules.append({
                'antecedent': [b],
                'consequent': [a],
                'support': round(support, 4),
                'confidence': round(conf_ba, 4),
                'lift': round(lift_ba, 3),
            })

    # Sort by lift descending, then confidence
    rules.sort(key=lambda r: (-r['lift'], -r['confidence']))
    return rules[:top_n]
