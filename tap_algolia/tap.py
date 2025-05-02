"""Algolia tap class."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from singer_sdk import Tap
from singer_sdk import typing as th  # JSON schema typing helpers

from tap_algolia import streams


class TapAlgolia(Tap):
    """Algolia tap class."""

    name = "tap-algolia"

    config_jsonschema = th.PropertiesList(
        # Algolia Analytics API credentials
        th.Property(
            "application_id",
            th.StringType(nullable=False),
            required=True,
            title="Application ID",
            description="The Algolia Application ID (X-Algolia-Application-Id header)",
        ),
        th.Property(
            "api_key",
            th.StringType(nullable=False),
            required=True,
            secret=True,
            title="API Key",
            description="The Algolia API Key with analytics permissions (X-Algolia-API-Key header)",
        ),
        
        # Indices to sync
        th.Property(
            "indices",
            th.ArrayType(th.StringType(nullable=False), nullable=False),
            required=True,
            title="Indices",
            description="Algolia indices to sync analytics data for",
        ),
        
        # Region and date range
        th.Property(
            "region",
            th.StringType(nullable=False),
            default="us",
            title="Region",
            description="Algolia region (us or eu)",
            examples=["us", "eu"],
        ),
        th.Property(
            "start_date",
            th.DateTimeType(nullable=True),
            description="The earliest record date to sync (defaults to 30 days ago)",
        ),
        th.Property(
            "end_date",
            th.DateTimeType(nullable=True),
            description="The latest record date to sync (defaults to today)",
        ),
        
        # Optional parameters
        th.Property(
            "include_click_analytics",
            th.BooleanType(nullable=True),
            default=True,
            title="Include Click Analytics",
            description="Whether to include click analytics metrics (CTR, position)",
        ),
        th.Property(
            "tags",
            th.StringType(nullable=True),
            title="Tags Filter",
            description="Optional tag filters for metrics (e.g. 'device:mobile')",
        ),
        th.Property(
            "date_window_size",
            th.IntegerType(nullable=True),
            default=30,
            title="Date Window Size",
            description="Number of days to include in each API request (max 30)",
        ),
        th.Property(
            "user_agent",
            th.StringType(nullable=True),
            description=(
                "A custom User-Agent header to send with each request. Default is "
                "'<tap_name>/<tap_version>'"
            ),
        ),
    ).to_dict()

    def discover_streams(self) -> list[streams.AlgoliaAnalyticsStream]:
        """Return a list of discovered streams.

        Returns:
            A list of discovered streams.
        """
        # Validate configuration
        if not self.config.get("indices"):
            self.logger.critical("No indices specified in config - at least one index is required")
            raise ValueError("No indices specified in configuration. At least one index is required.")
            
        # Initialize our Analytics API streams
        analytics_streams: List[streams.AlgoliaAnalyticsStream] = [
            streams.UsersCountStream(self),
            streams.TopSearchesStream(self),
            streams.SearchesCountStream(self),
            streams.NoResultsRateStream(self),
            streams.ClickThroughRateStream(self),
            streams.NoClickRateStream(self),
        ]
        
        return analytics_streams
    
    def get_starting_dates(self, config):
        """Calculate start and end dates based on config or defaults.
        
        Args:
            config: Tap configuration.
            
        Returns:
            Tuple of (start_date, end_date) as strings in YYYY-MM-DD format.
        """
        # Get end date from config or use today
        if config.get("end_date"):
            end_date = datetime.strptime(config["end_date"], "%Y-%m-%d").date()
        else:
            end_date = datetime.now().date()
            
        # Get start date from config or use default window
        if config.get("start_date"):
            start_date = datetime.strptime(config["start_date"], "%Y-%m-%d").date()
        else:
            window_size = config.get("date_window_size", 30)
            start_date = end_date - timedelta(days=window_size)
            
        return start_date.isoformat(), end_date.isoformat()


if __name__ == "__main__":
    TapAlgolia.cli()
