"""Stream type classes for tap-algolia."""

from __future__ import annotations

import typing as t
from datetime import date, datetime, timedelta
from importlib import resources
from typing import ClassVar, Dict, List, Optional

from singer_sdk import typing as th  # JSON Schema typing helpers

from tap_algolia.client import AlgoliaAnalyticsStream

# TODO: Delete this is if not using json files for schema definition
SCHEMAS_DIR = resources.files(__package__) / "schemas"

# Algolia Analytics API Streams

class UsersCountStream(AlgoliaAnalyticsStream):
    """Stream for user count metrics from Algolia Analytics API."""

    name = "users_count"
    path_template = "/2/users/count"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Number of users on this date"),
        
        # Date information
        th.Property("date", th.StringType, description="Date of the metric (YYYY-MM-DD)"),
        th.Property("start_date", th.StringType, description="Start date of the data window (YYYY-MM-DD)"),
        th.Property("end_date", th.StringType, description="End date of the data window (YYYY-MM-DD)"),
    ).to_dict()


class SearchesCountStream(AlgoliaAnalyticsStream):
    """Stream for total search count metrics from Algolia Analytics API."""
    
    name = "searches_count"
    path_template = "/2/searches/count"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Number of searches on this date"),
        
        # Date information
        th.Property("date", th.StringType, description="Date of the metric (YYYY-MM-DD)"),
        th.Property("start_date", th.StringType, description="Start date of the data window (YYYY-MM-DD)"),
        th.Property("end_date", th.StringType, description="End date of the data window (YYYY-MM-DD)"),
    ).to_dict()


class TopSearchesStream(AlgoliaAnalyticsStream):
    """Stream for top searches from Algolia Analytics API."""

    name = "top_searches"
    path_template = "/2/searches"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    
    # Include click analytics data
    include_click_analytics = True
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        th.Property("search", th.StringType, description="Search query text"),
        
        # Basic metrics
        th.Property("count", th.IntegerType, description="Number of times query was run"),
        th.Property("nbHits", th.IntegerType, description="Number of hits for this search query"),
        th.Property("trackedSearchCount", th.IntegerType, description="Number of tracked searches"),
        
        # Click analytics metrics
        th.Property("clickCount", th.IntegerType, description="Number of clicks"),
        th.Property("clickThroughRate", th.NumberType, description="Click-through rate (0.0-1.0)"),
        th.Property("conversionCount", th.IntegerType, description="Number of conversions"),
        th.Property("conversionRate", th.NumberType, description="Conversion rate (0.0-1.0)"),
        th.Property("averageClickPosition", th.NumberType, description="Average position clicked in result list"),
        
        # Click positions detail
        th.Property("clickPositions", th.ArrayType(th.ObjectType(
            th.Property("position", th.ArrayType(th.IntegerType), description="Position range [start, end]"),
            th.Property("clickCount", th.IntegerType, description="Clicks in this position range")
        )), description="Detailed click positions"),
        
        # Date information (added by tap)
        th.Property("date", th.StringType, description="Date of the metric (YYYY-MM-DD)"),
        th.Property("start_date", th.StringType, description="Start date of the data window (YYYY-MM-DD)"),
        th.Property("end_date", th.StringType, description="End date of the data window (YYYY-MM-DD)"),
    ).to_dict()
    
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
        
        # Add click analytics parameter
        params["clickAnalytics"] = "true"
        
        # Add revenue analytics parameter
        params["revenueAnalytics"] = "false"
        
        # Add sorting parameters
        params["orderBy"] = "searchCount"
        params["direction"] = "desc"
        
        # Add pagination parameters
        params["limit"] = self.limit
        if next_page_token:
            params["offset"] = next_page_token
        else:
            params["offset"] = 0
            
        # Log the parameters for debugging
        self.logger.info(f"Top searches request parameters: {params}")
            
        return params
        
    def get_records(self, context):
        """Get a day-by-day extract of search data.
        
        Instead of getting the default range of data (e.g., 30 days) in one request,
        we'll make separate requests for each day to get daily data.
        
        Args:
            context: The stream context.
            
        Yields:
            Records with daily granularity.
        """
        # Get the date range from context or config
        end_date = date.today()
        start_date = end_date - timedelta(days=self.default_date_window)
        
        # Get state and check for bookmarks using the Singer SDK state mechanism
        # Try different approaches to get the state, for robustness
        try:
            # More detailed logging of the state for debugging
            bookmark_state = self.get_context_state(context)
            if bookmark_state:
                self.logger.info(f"Found bookmark state keys: {list(bookmark_state.keys()) if isinstance(bookmark_state, dict) else 'No keys available'}")
            
            # Try to get replication key value
            replication_key_value = None
            
            # Method 1: Direct from start timestamp
            if self.replication_key and context and context.get("start_timestamp"):
                replication_key_value = context["start_timestamp"]
                self.logger.info(f"Found replication key value from start_timestamp: {replication_key_value}")
                
            # Method 2: From Singer state mechanism
            if not replication_key_value:
                replication_key_value = self.get_starting_replication_key_value(context)
                if replication_key_value:
                    self.logger.info(f"Found replication key value from get_starting_replication_key_value: {replication_key_value}")
            
            # Method 3: From deeper bookmark structure
            if not replication_key_value and bookmark_state and isinstance(bookmark_state, dict):
                if "bookmarks" in bookmark_state and isinstance(bookmark_state["bookmarks"], dict):
                    stream_bookmark = bookmark_state["bookmarks"].get(self.name, {})
                    if isinstance(stream_bookmark, dict) and "replication_key_value" in stream_bookmark:
                        replication_key_value = stream_bookmark["replication_key_value"]
                        self.logger.info(f"Found replication key value from bookmark structure: {replication_key_value}")
            
            if replication_key_value:
                try:
                    last_date = datetime.strptime(replication_key_value, "%Y-%m-%d").date()
                    # Start from the day after the last processed date
                    start_date = last_date + timedelta(days=1)
                    self.logger.info(f"Resuming extraction from {start_date.isoformat()} (last state: {last_date.isoformat()})")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid bookmark date format: {e}. Starting from default window.")
                    
        except Exception as e:
            self.logger.warning(f"Error while retrieving state: {e}. Starting from default window.")
        
        # Override with context dates if provided
        if context and "start_date" in context:
            try:
                start_date = datetime.strptime(context["start_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid start_date format in context: {context['start_date']}. Using {start_date}.")
        
        if context and "end_date" in context:
            try:
                end_date = datetime.strptime(context["end_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid end_date format in context: {context['end_date']}. Using {end_date}.")
            
        # Skip if start date is after end date
        if start_date > end_date:
            self.logger.info(f"Start date {start_date.isoformat()} is after end date {end_date.isoformat()}, skipping extraction")
            return
            
        # Calculate date range
        delta = end_date - start_date
        self.logger.info(f"Date range for extraction: {start_date.isoformat()} to {end_date.isoformat()} ({delta.days + 1} days)")
        
        # Track latest date for state management
        latest_date = None
        
        # Iterate through each day in the range
        for i in range(delta.days + 1):
            current_date = start_date + timedelta(days=i)
            
            # Create a new context with the specific day
            day_context = {
                "start_date": current_date.isoformat(),
                "end_date": current_date.isoformat(),
                "date": current_date.isoformat(),
            }
            
            # If there was a context provided, copy any other values
            if context:
                for key, value in context.items():
                    if key not in ["start_date", "end_date", "date", "state"]:
                        day_context[key] = value
            
            # Get records for this specific day
            self.logger.info(f"Getting top searches for date: {current_date.isoformat()}")
            
            # Update latest date
            latest_date = current_date
            
            # Use the normal REST stream logic to get records
            record_count = 0
            for record in super().get_records(day_context):
                # Add the date to the record - this field will be used by Singer for state tracking
                # because it matches our replication_key
                record["date"] = current_date.isoformat()
                record_count += 1
                yield record
                
            self.logger.info(f"Processed {record_count} records for {current_date.isoformat()}")
            
        # Write state at the end of processing - we'll just pass the date in the last record
        # The Singer SDK will automatically track the latest value of the replication_key field
        # as records are emitted, so we don't need to explicitly update the state
        
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
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Total number of searches on this date"),
        th.Property("noResultCount", th.IntegerType, description="Number of searches with no results"),
        th.Property("rate", th.NumberType, description="No results rate (0.0-1.0)"),
        
        # Date information
        th.Property("date", th.DateType, description="Date of the metric"),
        th.Property("start_date", th.DateType, description="Start date of the data window"),
        th.Property("end_date", th.DateType, description="End date of the data window"),
    ).to_dict()
    
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
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
            
        # Log the parameters for debugging
        self.logger.info(f"No results rate request parameters: {params}")
            
        return params
        
        
class ClickThroughRateStream(AlgoliaAnalyticsStream):
    """Stream for click-through rate metrics from Algolia Analytics API."""
    
    name = "click_through_rate"
    path_template = "/2/clicks/clickThroughRate"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        
        # Metrics
        th.Property("clickCount", th.IntegerType, description="Number of clicks"),
        th.Property("trackedSearchCount", th.IntegerType, description="Number of tracked searches"),
        th.Property("rate", th.NumberType, description="Click-through rate (0.0-1.0)"),
        
        # Date information
        th.Property("date", th.DateType, description="Date of the metric"),
        th.Property("start_date", th.DateType, description="Start date of the data window"),
        th.Property("end_date", th.DateType, description="End date of the data window"),
    ).to_dict()
    
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
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
            
        # Log the parameters for debugging
        self.logger.info(f"Click-through rate request parameters: {params}")
            
        return params


class NoClickRateStream(AlgoliaAnalyticsStream):
    """Stream for no-click rate metrics from Algolia Analytics API."""
    
    name = "no_click_rate"
    path_template = "/2/searches/noClickRate"
    primary_keys: ClassVar[List[str]] = ["index_name", "date"]
    replication_key = "date"
    records_jsonpath = "$.dates[*]"  # Path to the daily breakdown data
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Total number of tracked searches"),
        th.Property("noClickCount", th.IntegerType, description="Number of searches without clicks"),
        th.Property("rate", th.NumberType, description="No-click rate (0.0-1.0)"),
        
        # Date information
        th.Property("date", th.DateType, description="Date of the metric"),
        th.Property("start_date", th.DateType, description="Start date of the data window"),
        th.Property("end_date", th.DateType, description="End date of the data window"),
    ).to_dict()
    
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
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
            
        # Log the parameters for debugging
        self.logger.info(f"No-click rate request parameters: {params}")
            
        return params


class NoResultsSearchesStream(AlgoliaAnalyticsStream):
    """Stream for search queries that returned no results from Algolia Analytics API."""
    
    name = "no_results_searches"
    path_template = "/2/searches/noResults"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        th.Property("search", th.StringType, description="Search query text"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Number of times query was run with no results"),
        th.Property("withFilterCount", th.IntegerType, description="Number of times query was run with filters"),
        
        # Date information (added by tap)
        th.Property("date", th.StringType, description="Date of the metric (YYYY-MM-DD)"),
        th.Property("start_date", th.StringType, description="Start date of the data window (YYYY-MM-DD)"),
        th.Property("end_date", th.StringType, description="End date of the data window (YYYY-MM-DD)"),
    ).to_dict()
    
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
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
        
        # Add pagination parameters
        params["limit"] = self.limit
        if next_page_token:
            params["offset"] = next_page_token
        else:
            params["offset"] = 0
            
        # Log the parameters for debugging
        self.logger.info(f"No results searches request parameters: {params}")
            
        return params
        
    def get_records(self, context):
        """Get a day-by-day extract of no-results search data.
        
        Instead of getting the default range of data (e.g., 30 days) in one request,
        we'll make separate requests for each day to get daily data.
        
        Args:
            context: The stream context.
            
        Yields:
            Records with daily granularity.
        """
        # Get the date range from context or config
        end_date = date.today()
        start_date = end_date - timedelta(days=self.default_date_window)
        
        # Get state and check for bookmarks using the Singer SDK state mechanism
        # Try different approaches to get the state, for robustness
        try:
            # More detailed logging of the state for debugging
            bookmark_state = self.get_context_state(context)
            if bookmark_state:
                self.logger.info(f"Found bookmark state keys: {list(bookmark_state.keys()) if isinstance(bookmark_state, dict) else 'No keys available'}")
            
            # Try to get replication key value
            replication_key_value = None
            
            # Method 1: Direct from start timestamp
            if self.replication_key and context and context.get("start_timestamp"):
                replication_key_value = context["start_timestamp"]
                self.logger.info(f"Found replication key value from start_timestamp: {replication_key_value}")
                
            # Method 2: From Singer state mechanism
            if not replication_key_value:
                replication_key_value = self.get_starting_replication_key_value(context)
                if replication_key_value:
                    self.logger.info(f"Found replication key value from get_starting_replication_key_value: {replication_key_value}")
            
            # Method 3: From deeper bookmark structure
            if not replication_key_value and bookmark_state and isinstance(bookmark_state, dict):
                if "bookmarks" in bookmark_state and isinstance(bookmark_state["bookmarks"], dict):
                    stream_bookmark = bookmark_state["bookmarks"].get(self.name, {})
                    if isinstance(stream_bookmark, dict) and "replication_key_value" in stream_bookmark:
                        replication_key_value = stream_bookmark["replication_key_value"]
                        self.logger.info(f"Found replication key value from bookmark structure: {replication_key_value}")
            
            if replication_key_value:
                try:
                    last_date = datetime.strptime(replication_key_value, "%Y-%m-%d").date()
                    # Start from the day after the last processed date
                    start_date = last_date + timedelta(days=1)
                    self.logger.info(f"Resuming extraction from {start_date.isoformat()} (last state: {last_date.isoformat()})")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid bookmark date format: {e}. Starting from default window.")
                    
        except Exception as e:
            self.logger.warning(f"Error while retrieving state: {e}. Starting from default window.")
        
        # Override with context dates if provided
        if context and "start_date" in context:
            try:
                start_date = datetime.strptime(context["start_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid start_date format in context: {context['start_date']}. Using {start_date}.")
        
        if context and "end_date" in context:
            try:
                end_date = datetime.strptime(context["end_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid end_date format in context: {context['end_date']}. Using {end_date}.")
            
        # Skip if start date is after end date
        if start_date > end_date:
            self.logger.info(f"Start date {start_date.isoformat()} is after end date {end_date.isoformat()}, skipping extraction")
            return
            
        # Calculate date range
        delta = end_date - start_date
        self.logger.info(f"Date range for extraction: {start_date.isoformat()} to {end_date.isoformat()} ({delta.days + 1} days)")
        
        # Track latest date for state management
        latest_date = None
        
        # Iterate through each day in the range
        for i in range(delta.days + 1):
            current_date = start_date + timedelta(days=i)
            
            # Create a new context with the specific day
            day_context = {
                "start_date": current_date.isoformat(),
                "end_date": current_date.isoformat(),
                "date": current_date.isoformat(),
            }
            
            # If there was a context provided, copy any other values
            if context:
                for key, value in context.items():
                    if key not in ["start_date", "end_date", "date", "state"]:
                        day_context[key] = value
            
            # Get records for this specific day
            self.logger.info(f"Getting no-results searches for date: {current_date.isoformat()}")
            
            # Update latest date
            latest_date = current_date
            
            # Use the normal REST stream logic to get records
            record_count = 0
            for record in super().get_records(day_context):
                # Add the date to the record - this field will be used by Singer for state tracking
                # because it matches our replication_key
                record["date"] = current_date.isoformat()
                record_count += 1
                yield record
                
            self.logger.info(f"Processed {record_count} records for {current_date.isoformat()}")
            
        # Write state at the end of processing - we'll just pass the date in the last record
        # The Singer SDK will automatically track the latest value of the replication_key field
        # as records are emitted, so we don't need to explicitly update the state


class NoClicksSearchesStream(AlgoliaAnalyticsStream):
    """Stream for search queries that received no clicks from Algolia Analytics API."""
    
    name = "no_clicks_searches"
    path_template = "/2/searches/noClicks"
    primary_keys: ClassVar[List[str]] = ["index_name", "search", "date"]
    replication_key = "date"  # Using date field for state management
    records_jsonpath = "$.searches[*]"  # Path to the search records in response
    
    # Pagination parameters
    limit = 1000
    
    # Default lookback window for replication (30 days)
    default_date_window: ClassVar[int] = 30
    
    schema = th.PropertiesList(
        # Identifiers
        th.Property("index_name", th.StringType, description="The Algolia index name"),
        th.Property("search", th.StringType, description="Search query text"),
        
        # Metrics
        th.Property("count", th.IntegerType, description="Number of times query was run without clicks"),
        th.Property("nbHits", th.IntegerType, description="Number of hits returned for this search query"),
        
        # Date information (added by tap)
        th.Property("date", th.StringType, description="Date of the metric (YYYY-MM-DD)"),
        th.Property("start_date", th.StringType, description="Start date of the data window (YYYY-MM-DD)"),
        th.Property("end_date", th.StringType, description="End date of the data window (YYYY-MM-DD)"),
    ).to_dict()
    
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
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
        
        # Add pagination parameters
        params["limit"] = self.limit
        if next_page_token:
            params["offset"] = next_page_token
        else:
            params["offset"] = 0
            
        # Log the parameters for debugging
        self.logger.info(f"No clicks searches request parameters: {params}")
            
        return params
        
    def get_records(self, context):
        """Get a day-by-day extract of no-clicks search data.
        
        Instead of getting the default range of data (e.g., 30 days) in one request,
        we'll make separate requests for each day to get daily data.
        
        Args:
            context: The stream context.
            
        Yields:
            Records with daily granularity.
        """
        # Get the date range from context or config
        end_date = date.today()
        start_date = end_date - timedelta(days=self.default_date_window)
        
        # Get state and check for bookmarks using the Singer SDK state mechanism
        # Try different approaches to get the state, for robustness
        try:
            # More detailed logging of the state for debugging
            bookmark_state = self.get_context_state(context)
            if bookmark_state:
                self.logger.info(f"Found bookmark state keys: {list(bookmark_state.keys()) if isinstance(bookmark_state, dict) else 'No keys available'}")
            
            # Try to get replication key value
            replication_key_value = None
            
            # Method 1: Direct from start timestamp
            if self.replication_key and context and context.get("start_timestamp"):
                replication_key_value = context["start_timestamp"]
                self.logger.info(f"Found replication key value from start_timestamp: {replication_key_value}")
                
            # Method 2: From Singer state mechanism
            if not replication_key_value:
                replication_key_value = self.get_starting_replication_key_value(context)
                if replication_key_value:
                    self.logger.info(f"Found replication key value from get_starting_replication_key_value: {replication_key_value}")
            
            # Method 3: From deeper bookmark structure
            if not replication_key_value and bookmark_state and isinstance(bookmark_state, dict):
                if "bookmarks" in bookmark_state and isinstance(bookmark_state["bookmarks"], dict):
                    stream_bookmark = bookmark_state["bookmarks"].get(self.name, {})
                    if isinstance(stream_bookmark, dict) and "replication_key_value" in stream_bookmark:
                        replication_key_value = stream_bookmark["replication_key_value"]
                        self.logger.info(f"Found replication key value from bookmark structure: {replication_key_value}")
            
            if replication_key_value:
                try:
                    last_date = datetime.strptime(replication_key_value, "%Y-%m-%d").date()
                    # Start from the day after the last processed date
                    start_date = last_date + timedelta(days=1)
                    self.logger.info(f"Resuming extraction from {start_date.isoformat()} (last state: {last_date.isoformat()})")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid bookmark date format: {e}. Starting from default window.")
                    
        except Exception as e:
            self.logger.warning(f"Error while retrieving state: {e}. Starting from default window.")
        
        # Override with context dates if provided
        if context and "start_date" in context:
            try:
                start_date = datetime.strptime(context["start_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid start_date format in context: {context['start_date']}. Using {start_date}.")
        
        if context and "end_date" in context:
            try:
                end_date = datetime.strptime(context["end_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid end_date format in context: {context['end_date']}. Using {end_date}.")
            
        # Skip if start date is after end date
        if start_date > end_date:
            self.logger.info(f"Start date {start_date.isoformat()} is after end date {end_date.isoformat()}, skipping extraction")
            return
            
        # Calculate date range
        delta = end_date - start_date
        self.logger.info(f"Date range for extraction: {start_date.isoformat()} to {end_date.isoformat()} ({delta.days + 1} days)")
        
        # Track latest date for state management
        latest_date = None
        
        # Iterate through each day in the range
        for i in range(delta.days + 1):
            current_date = start_date + timedelta(days=i)
            
            # Create a new context with the specific day
            day_context = {
                "start_date": current_date.isoformat(),
                "end_date": current_date.isoformat(),
                "date": current_date.isoformat(),
            }
            
            # If there was a context provided, copy any other values
            if context:
                for key, value in context.items():
                    if key not in ["start_date", "end_date", "date", "state"]:
                        day_context[key] = value
            
            # Get records for this specific day
            self.logger.info(f"Getting no-clicks searches for date: {current_date.isoformat()}")
            
            # Update latest date
            latest_date = current_date
            
            # Use the normal REST stream logic to get records
            record_count = 0
            for record in super().get_records(day_context):
                # Add the date to the record - this field will be used by Singer for state tracking
                # because it matches our replication_key
                record["date"] = current_date.isoformat()
                record_count += 1
                yield record
                
            self.logger.info(f"Processed {record_count} records for {current_date.isoformat()}")
            
        # Write state at the end of processing - we'll just pass the date in the last record
        # The Singer SDK will automatically track the latest value of the replication_key field
        # as records are emitted, so we don't need to explicitly update the state