"""
High cardinality strategy for multi-line charts.

When the number of unique transactions exceeds a threshold,
keeps only the Top-N by P95 and aggregates the rest into a
single 'Resto (avg)' series.
"""
import pandas as pd
from typing import List, Optional, Tuple

THRESHOLD = 15
TOP_N = 10


def apply_top_n_aggregation(
    dataframes: List[pd.DataFrame],
    summary_df: pd.DataFrame,
    threshold: int = THRESHOLD,
    top_n: int = TOP_N,
) -> Tuple[List[pd.DataFrame], Optional[str]]:
    """
    Filter response_times_by_label sub-DataFrames to Top-N by P95.

    Args:
        dataframes: List of sub-DataFrames, each with columns
                    ['timestamp', 'value', 'label'].
        summary_df: Summary DataFrame with columns ['label', 'p95'].
        threshold:  Minimum number of labels to activate aggregation.
        top_n:      Number of top labels to keep individually.

    Returns:
        Tuple of:
        - Filtered list of DataFrames (top_n individual + 1 aggregated 'Resto').
        - Title suffix string like 'Top 10 de 45 transacciones' or None
          if no aggregation was needed.
    """
    if len(dataframes) <= threshold:
        return dataframes, None

    # Rank labels by P95 descending
    if 'p95' not in summary_df.columns or 'label' not in summary_df.columns:
        return dataframes, None

    ranked = summary_df.nlargest(top_n, 'p95')
    top_labels = set(ranked['label'].tolist())

    top_dfs = []
    rest_dfs = []

    for sub_df in dataframes:
        if len(sub_df) == 0:
            continue
        lbl = sub_df['label'].iloc[0]
        if lbl in top_labels:
            top_dfs.append(sub_df)
        else:
            rest_dfs.append(sub_df)

    # Build aggregated 'Resto' series (average of all non-top labels)
    if rest_dfs:
        combined = pd.concat(rest_dfs, ignore_index=True)
        rest_count = len(rest_dfs)
        rest_agg = (
            combined
            .groupby('timestamp', as_index=False)
            .agg(value=('value', 'mean'))
        )
        rest_agg['label'] = f'Resto ({rest_count} transacciones)'
        top_dfs.append(rest_agg)

    total = len(dataframes)
    title_suffix = f'Top {len(top_dfs) - (1 if rest_dfs else 0)} de {total} transacciones'

    return top_dfs, title_suffix
