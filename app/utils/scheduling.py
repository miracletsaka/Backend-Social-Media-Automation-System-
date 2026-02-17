import calendar
import math

def posts_in_month(target_month: str, posts_per_week: int) -> int:
    """
    Calculate how many posts should be generated for a month.

    Example:
      target_month = "2026-01"
      posts_per_week = 3
      → returns ~12–15 depending on month length
    """
    if not target_month or not posts_per_week:
        return 0

    y, m = [int(x) for x in target_month.split("-")]
    days = calendar.monthrange(y, m)[1]
    weeks = math.ceil(days / 7)

    return max(1, weeks * posts_per_week)
