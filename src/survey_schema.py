"""Schema of the two input tables: survey responses and Google reviews.

Single source of truth for column names, types and valid ranges. The sample
data generator and the tests both read from here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # "id", "datetime", "date", "rating", "text" or "bool"
    required: bool = True
    min_value: int | None = None
    max_value: int | None = None


# Rating questions can be skipped by the diner, so they are not required.
SURVEY_RESPONSES = (
    Column("response_id", "id"),
    Column("submitted_at", "datetime"),
    Column("rating_overall", "rating", required=False, min_value=1, max_value=5),
    Column("rating_food", "rating", required=False, min_value=1, max_value=5),
    Column("rating_service", "rating", required=False, min_value=1, max_value=5),
    Column("rating_ambience", "rating", required=False, min_value=1, max_value=5),
    Column("rating_value", "rating", required=False, min_value=1, max_value=5),
    Column("would_recommend", "rating", required=False, min_value=0, max_value=10),
    Column("positives", "text", required=False),
    Column("complaints", "text", required=False),
    Column("suggestions", "text", required=False),
)

GOOGLE_REVIEWS = (
    Column("review_id", "id"),
    Column("review_date", "date"),
    Column("rating", "rating", min_value=1, max_value=5),
    Column("text", "text", required=False),
    Column("owner_replied", "bool"),
    Column("owner_reply_date", "date", required=False),
)


def column_names(table: tuple[Column, ...]) -> list[str]:
    return [column.name for column in table]
