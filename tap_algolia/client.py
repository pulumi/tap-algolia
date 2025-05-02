"""REST client handling, including AlgoliaStream base class."""

from __future__ import annotations

import decimal
import typing as t
from datetime import date, datetime, timedelta
from importlib import resources
from typing import Any, ClassVar, Dict, Iterable, List, Optional

from singer_sdk.authenticators import APIKeyAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseOffsetPaginator
from singer_sdk.streams import RESTStream

if t.TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Context


# Schema directory for JSON schema files
SCHEMAS_DIR = resources.files(__package__) / "schemas"


class AlgoliaStream(RESTStream):
    """Base Algolia stream class."""

    # Default records extraction jsonpath
    records_jsonpath = "$[*]"

    # Default pagination token jsonpath
    next_page_token_jsonpath = "$.next_page"

    @property
    def url_base(self) -> str:
        """Return the API URL root, configurable via tap settings."""
        # Default to US Algolia API
        return "https://www.algolia.com/api"

    @property
    def authenticator(self) -> APIKeyAuthenticator:
        """Return a new authenticator object.

        Returns:
            An authenticator instance.
        """
        return APIKeyAuthenticator.create_for_stream(
            self,
            key="X-Algolia-API-Key",
            value=self.config.get("api_key", ""),
            location="header",
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        return {
            "X-Algolia-Application-Id": self.config.get("application_id", ""),
            "Content-Type": "application/json",
        }

    def get_new_paginator(self) -> BaseOffsetPaginator:
        """Create a new offset-based pagination helper instance.
        
        The Algolia Analytics API uses offset/limit pagination.
        
        Returns:
            A BaseOffsetPaginator configured for Algolia Analytics API.
        """
        return BaseOffsetPaginator(
            start_value=0,
            page_size=getattr(self, "limit", 1000),  # Use the stream's limit attribute or default to 1000
            increment=getattr(self, "limit", 1000),  # Page size determines increment
        )

    def get_url_params(
        self,
        context: Context | None,
        next_page_token: t.Any | None,
    ) -> dict[str, t.Any]:
        """Return a dictionary of values to be used in URL parameterization.

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary of URL query parameters.
        """
        params: dict = {}
        if next_page_token:
            params["page"] = next_page_token
        if self.replication_key:
            params["sort"] = "asc"
            params["order_by"] = self.replication_key
        return params

    def parse_response(self, response: requests.Response) -> t.Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args:
            response: The HTTP ``requests.Response`` object.

        Yields:
            Each record from the source.
        """
        yield from extract_jsonpath(
            self.records_jsonpath,
            input=response.json(parse_float=decimal.Decimal),
        )


class AlgoliaAnalyticsStream(RESTStream):
    """Base class for Algolia Analytics API streams."""

    # Default date range for lookback if not in state
    default_date_window: ClassVar[int] = 30
    
    # No next_page_token_jsonpath by default; streams will set this if needed
    next_page_token_jsonpath = None
    
    def get_replication_key_value(self, value):
        """
        Return the replication value as a string for consistent comparisons in state.
        
        Args:
            value: The value from the record.
            
        Returns:
            The standardized replication key value as a string.
        """
        if not value:
            return None
        # Convert dates to string format if they aren't already
        if isinstance(value, (date, datetime)):
            return value.isoformat().split('T')[0]  # Get just the YYYY-MM-DD part
        return str(value)
    
    @property
    def path(self) -> str:
        """Return the path template without any replacements.
        
        The v2 API uses query parameters for indexes, not path parameters.
        
        Returns:
            The path template.
        """
        if not hasattr(self, "path_template"):
            # Fallback in case no path_template exists
            return "/2/searches"
            
        return self.path_template

    @property
    def url_base(self) -> str:
        """Return the Analytics API URL root for the configured region.

        Returns:
            The base URL for the Analytics API.
        """
        region = self.config.get("region", "us").lower()
        if region == "eu":
            return "https://analytics.de.algolia.com"
        return "https://analytics.us.algolia.com"  # Default to US

    @property
    def authenticator(self) -> APIKeyAuthenticator:
        """Return a new authenticator object for Algolia Analytics API.

        Returns:
            An authenticator instance with appropriate headers.
        """
        # Use the API key authenticator with the API key header
        return APIKeyAuthenticator.create_for_stream(
            self,
            key="X-Algolia-API-Key",
            value=self.config.get("api_key", ""),
            location="header",
        )
        
    @property
    def http_headers(self) -> dict:
        """Return the http headers needed for Algolia.

        Returns:
            A dictionary of HTTP headers.
        """
        # Add the Application ID header which is also required for authentication
        return {
            "X-Algolia-Application-Id": self.config.get("application_id", ""),
        }

    def get_url_params(
        self,
        context: dict | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Return URL parameters for the Analytics API request.

        Args:
            context: The stream context.
            next_page_token: Pagination token (offset for Analytics API).

        Returns:
            URL query parameters including date range and optional pagination.
        """
        params: dict = {}
        
        # Add index parameter - REQUIRED for Analytics API V2
        # Get index from context or config
        index = None
        if context:
            index = context.get("index")
        if not index:
            indices = self.config.get("indices", [])
            if indices:
                index = indices[0]
            else:
                raise ValueError("No index specified in config or context")
                
        # Add index parameter - required for all Analytics API calls
        params["index"] = index
        
        # Add date range parameters
        if context and "start_date" in context:
            params["startDate"] = context["start_date"]
            params["endDate"] = context["end_date"]
        else:
            # Default to last 30 days if no specific dates provided
            end_date = date.today()
            start_date = end_date - timedelta(days=self.default_date_window)
            params["startDate"] = start_date.isoformat()
            params["endDate"] = end_date.isoformat()
            
        # Add clickAnalytics parameter for streams that support it
        if getattr(self, "include_click_analytics", False):
            params["clickAnalytics"] = "true"
        
        # Add tags parameter if provided in the config
        tags = self.config.get("tags")
        if tags:
            params["tags"] = tags
            
        # Handle pagination
        # Get pagination limit from stream or use default
        limit = getattr(self, "limit", 1000)
        params["limit"] = limit
        
        # Add offset for pagination
        if next_page_token:
            params["offset"] = next_page_token
        else:
            params["offset"] = 0
            
        # Log the parameters for debugging
        self.logger.info(f"{self.name} request parameters: {params}")
            
        return params

    # We don't need get_next_page_token anymore since we're using BaseOffsetPaginator
    # The paginator will handle offset calculation based on the API response size

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        """Parse Analytics API response and add index name and date info.

        Args:
            response: The HTTP response object.

        Yields:
            Records from the response with additional context.
        """
        data = response.json(parse_float=decimal.Decimal)
        
        # Get URL parameters to determine index
        url_parts = response.request.url.split('?', 1)
        url_params = {}
        if len(url_parts) > 1:
            param_str = url_parts[1]
            for p in param_str.split('&'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    url_params[k] = v
        
        # Get index name from URL parameters
        index_name = url_params.get('index', 'unknown')
        
        # Context for date ranges
        context = {}
        if "startDate" in url_params:
            context["start_date"] = url_params["startDate"]
        if "endDate" in url_params:
            context["end_date"] = url_params["endDate"]
            
        # Use jsonpath to extract the records using the stream's defined records_jsonpath
        for record in extract_jsonpath(self.records_jsonpath, data):
            if isinstance(record, dict):
                # Make a copy of the record to avoid modifying the original
                enriched_record = dict(record)
                
                # Add index_name if not present
                if "index_name" not in enriched_record:
                    enriched_record["index_name"] = index_name
                
                # Add date range context
                enriched_record.update(context)
                
                yield enriched_record
                
    def get_records(self, context: Dict | None = None) -> Iterable[Dict]:
        """Get records using the Analytics API with date range support.
        
        Instead of getting a large date range in one request, this method
        makes daily requests for better control and error handling.
        
        Args:
            context: Stream context object, can contain start_date and end_date.
            
        Yields:
            Records for the stream.
        """
        # Get end date (default is today)
        end_date = date.today()
        
        # Get start date (default is N days before end date)
        start_date = end_date - timedelta(days=self.default_date_window)
        
        # Check if we have a previous bookmark in state
        if self.replication_key:
            # Get the last processed date from state
            replication_value = self.get_starting_replication_key_value(context)
            if replication_value:
                try:
                    # Parse the date from the replication value
                    last_date = datetime.strptime(replication_value, "%Y-%m-%d").date()
                    # Start from the day after the last processed date
                    start_date = last_date + timedelta(days=1)
                    self.logger.info(f"Resuming from {start_date.isoformat()} (last state: {last_date.isoformat()})")
                except (ValueError, TypeError):
                    self.logger.info(f"Could not parse replication value: {replication_value}, using default window")
                    
        # Override with context dates if provided
        if context and "start_date" in context:
            try:
                start_date = datetime.strptime(context["start_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid start_date format in context: {context['start_date']}")
        
        if context and "end_date" in context:
            try:
                end_date = datetime.strptime(context["end_date"], "%Y-%m-%d").date()
            except ValueError:
                self.logger.warning(f"Invalid end_date format in context: {context['end_date']}")
            
        # Skip if start date is after end date
        if start_date > end_date:
            self.logger.info(f"Start date {start_date.isoformat()} is after end date {end_date.isoformat()}, skipping extraction")
            return
            
        # Calculate date range
        delta = end_date - start_date
        self.logger.info(f"Date range for extraction: {start_date.isoformat()} to {end_date.isoformat()} ({delta.days + 1} days)")
        
        # Process each day in the range
        for i in range(delta.days + 1):
            current_date = start_date + timedelta(days=i)
            
            # Create a context for this specific day
            day_context = {
                "start_date": current_date.isoformat(),
                "end_date": current_date.isoformat(),
                "date": current_date.isoformat(),
            }
            
            # Copy other values from the original context
            if context:
                for key, value in context.items():
                    if key not in ["start_date", "end_date", "date", "state"]:
                        day_context[key] = value
            
            # Log current day being processed
            self.logger.info(f"Processing day: {current_date.isoformat()}")
            
            # Get records for this day using the REST stream logic with retry logic
            max_retries = 5
            retry_count = 0
            retry_delay = 1  # seconds
            
            while retry_count < max_retries:
                try:
                    # Get records for this day using the REST stream logic
                    record_count = 0
                    for record in super().get_records(day_context):
                        # Ensure date field is present and is a string
                        if "date" not in record:
                            record["date"] = current_date.isoformat()
                        elif not isinstance(record["date"], str):
                            record["date"] = record["date"].isoformat() if hasattr(record["date"], "isoformat") else str(record["date"])
                        
                        record_count += 1
                        yield record
                    
                    # Log successful processing
                    self.logger.info(f"Processed {record_count} records for {current_date.isoformat()}")
                    
                    # Break out of retry loop on success
                    break
                    
                except ConnectionResetError as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Exponential backoff
                        sleep_time = retry_delay * (2 ** (retry_count - 1))
                        self.logger.warning(
                            f"Connection reset when processing {current_date.isoformat()}. "
                            f"Retrying in {sleep_time} seconds... (Attempt {retry_count}/{max_retries})"
                        )
                        import time
                        time.sleep(sleep_time)
                    else:
                        self.logger.error(
                            f"Failed to process {current_date.isoformat()} after {max_retries} attempts. "
                            f"Last error: {str(e)}"
                        )
                        # Re-raise the exception after max retries
                        raise
                except Exception as e:
                    self.logger.error(f"Error processing {current_date.isoformat()}: {str(e)}")
                    raise