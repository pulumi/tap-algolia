"""Stream type classes for tap-algolia."""

from __future__ import annotations

import typing as t
from datetime import date, datetime, timedelta
from typing import ClassVar, Dict, List, Optional

from tap_algolia.client import AlgoliaAnalyticsStream
from tap_algolia.schemas import load_schema

# Algolia Analytics API Streams

class UsersCountStream(AlgoliaAnalyticsStream):
    """Stream for user count metrics from Algolia Analytics API."""

    name = "users_count"
    path_template = "/2/users/count"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    next_page_token_jsonpath = None  # No pagination token from response
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = load_schema("users_count")


class SearchesCountStream(AlgoliaAnalyticsStream):
    """Stream for total search count metrics from Algolia Analytics API."""
    
    name = "searches_count"
    path_template = "/2/searches/count"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    next_page_token_jsonpath = None  # No pagination token from response
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = load_schema("searches_count")


class TopSearchesStream(AlgoliaAnalyticsStream):
    """Stream for top searches from Algolia Analytics API."""

    name = "top_searches"
    path_template = "/2/searches"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    next_page_token_jsonpath = None  # No pagination token from response, we use offset
    
    # Include click analytics data
    include_click_analytics = True
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = load_schema("top_searches")
    
    def get_url_params(
        self,
        context: dict | None,
        next_page_token: t.Any | None,
    ) -> dict[str, t.Any]:
        """Return URL parameters for the Analytics API request.

        Args:
            context: The stream context.
            next_page_token: Pagination token (offset for Analytics API).

        Returns:
            URL query parameters including date range and optional pagination.
        """
        params = super().get_url_params(context, next_page_token)
        
        # Add revenue analytics parameter
        params["revenueAnalytics"] = "false"
        
        # Add sorting parameters
        params["orderBy"] = "searchCount"
        params["direction"] = "desc"
        
        return params
        
    def validate_response(self, response: t.Any) -> None:
        """Log API response details for debugging."""
        self.logger.info(f"Top searches response status: {response.status_code}")
        if response.status_code != 200:
            self.logger.info(f"Top searches error response: {response.text}")
        else:
            # Try to log summary of the response
            try:
                data = response.json()
                if isinstance(data, dict):
                    self.logger.info(f"Top searches response keys: {data.keys()}")
                elif isinstance(data, list):
                    self.logger.info(f"Top searches response is a list with {len(data)} items")
                    if data and isinstance(data[0], dict):
                        self.logger.info(f"First item keys: {data[0].keys()}")
            except Exception as e:
                self.logger.info(f"Error parsing response: {e}")
                
        # Call parent validation
        super().validate_response(response)


class NoResultsRateStream(AlgoliaAnalyticsStream):
    """Stream for no results rate metrics from Algolia Analytics API."""
    
    name = "no_results_rate"
    path_template = "/2/searches/noResultRate"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = load_schema("no_results_rate")
        
        
class ClickThroughRateStream(AlgoliaAnalyticsStream):
    """Stream for click-through rate metrics from Algolia Analytics API."""
    
    name = "click_through_rate"
    path_template = "/2/clicks/clickThroughRate"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = load_schema("click_through_rate")


class NoClickRateStream(AlgoliaAnalyticsStream):
    """Stream for no-click rate metrics from Algolia Analytics API."""
    
    name = "no_click_rate"
    path_template = "/2/searches/noClickRate"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = load_schema("no_click_rate")


class NoResultsSearchesStream(AlgoliaAnalyticsStream):
    """Stream for search queries that returned no results from Algolia Analytics API."""
    
    name = "no_results_searches"
    path_template = "/2/searches/noResults"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    next_page_token_jsonpath = None  # No pagination token from response, we use offset
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = load_schema("no_results_searches")


class NoClicksSearchesStream(AlgoliaAnalyticsStream):
    """Stream for search queries that received no clicks from Algolia Analytics API."""
    
    name = "no_clicks_searches"
    path_template = "/2/searches/noClicks"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    next_page_token_jsonpath = None  # No pagination token from response, we use offset
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = load_schema("no_clicks_searches")