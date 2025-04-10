# signals/signal_combiners.py

import pandas as pd

def combine_signals_and(entries1: pd.Series, exits1: pd.Series,
                        entries2: pd.Series, exits2: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Combines two sets of signals using logical AND for entries.
    Exits if *either* original exit signal is True.

    Args:
        entries1: Boolean Series for first entry signal.
        exits1: Boolean Series for first exit signal.
        entries2: Boolean Series for second entry signal.
        exits2: Boolean Series for second exit signal.

    Returns:
        A tuple containing combined entries and exits Series.
    """
    # Align indices if necessary (should be automatic if generated from same price data)
    entries1, entries2 = entries1.align(entries2, fill_value=False)
    exits1, exits2 = exits1.align(exits2, fill_value=False)

    # Combine entries with AND
    combined_entries = entries1 & entries2

    # Combine exits with OR (exit if either strategy signals exit)
    combined_exits = exits1 | exits2

    # Optional: Clean combined signals
    # combined_entries, combined_exits = combined_entries.vbt.signals.clean(combined_exits)

    print("Signals combined using AND logic for entries.")
    return combined_entries, combined_exits


def combine_signals_or(entries1: pd.Series, exits1: pd.Series,
                       entries2: pd.Series, exits2: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Combines two sets of signals using logical OR for entries.
    Exits if *both* original exit signals are True (or adjust logic as needed).

    Args:
        entries1: Boolean Series for first entry signal.
        exits1: Boolean Series for first exit signal.
        entries2: Boolean Series for second entry signal.
        exits2: Boolean Series for second exit signal.

    Returns:
        A tuple containing combined entries and exits Series.
    """
    # Align indices
    entries1, entries2 = entries1.align(entries2, fill_value=False)
    exits1, exits2 = exits1.align(exits2, fill_value=False)

    # Combine entries with OR
    combined_entries = entries1 | entries2

    # Combine exits with AND (example: exit only if both strategies signal exit)
    # Adjust this logic based on desired behavior (e.g., exit if EITHER exits -> exits1 | exits2)
    combined_exits = exits1 & exits2

    # Optional: Clean combined signals
    # combined_entries, combined_exits = combined_entries.vbt.signals.clean(combined_exits)

    print("Signals combined using OR logic for entries.")
    return combined_entries, combined_exits