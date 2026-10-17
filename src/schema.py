"""Schema of the input table: Google reviews.

Single source of truth for column names, types and valid ranges. The importer,
the sample data generator and the tests all read from here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # "id", "date", "rating", "text" or "bool"
    required: bool = True
    min_value: int | None = None
    max_value: int | None = None


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
