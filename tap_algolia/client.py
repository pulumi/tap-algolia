"""REST client handling, including AlgoliaStream base class."""

from __future__ import annotations

import decimal
import typing as t
from datetime import date, timedelta
from importlib import resources
from typing import Any, ClassVar, Dict, Iterable, List, Optional

from singer_sdk.authenticators import APIKeyAuthenticator
from singer_sdk.helpers.jsonpath import extract_jsonpath
from singer_sdk.pagination import BaseAPIPaginator  # noqa: TC002
from singer_sdk.streams import RESTStream

if t.TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Context


# TODO: Delete this is if not using json files for schema definition
SCHEMAS_DIR = resources.files(__package__) / "schemas"


class AlgoliaStream(RESTStream):
    """Algolia stream class."""

    # Update this value if necessary or override `parse_response`.
    records_jsonpath = "$[*]"

    # Update this value if necessary or override `get_new_paginator`.
    next_page_token_jsonpath = "$.next_page"  # noqa: S105

    @property
    def url_base(self) -> str:
        """Return the API URL root, configurable via tap settings."""
        # TODO: hardcode a value here, or retrieve it from self.config
        return "https://api.mysample.com"

    @property
    def authenticator(self) -> APIKeyAuthenticator:
        """Return a new authenticator object.

        Returns:
            An authenticator instance.
        """
        return APIKeyAuthenticator.create_for_stream(
            self,
            key="x-api-key",
            value=self.config.get("auth_token", ""),
            location="header",
        )

    @property
    def http_headers(self) -> dict:
        """Return the http headers needed.

        Returns:
            A dictionary of HTTP headers.
        """
        # If not using an authenticator, you may also provide inline auth headers:
        # headers["Private-Token"] = self.config.get("auth_token")  # noqa: ERA001
        return {}

    def get_new_paginator(self) -> BaseAPIPaginator:
        """Create a new pagination helper instance.

        If the source API can make use of the `next_page_token_jsonpath`
        attribute, or it contains a `X-Next-Page` header in the response
        then you can remove this method.

        If you need custom pagination that uses page numbers, "next" links, or
        other approaches, please read the guide: https://sdk.meltano.com/en/v0.25.0/guides/pagination-classes.html.

        Returns:
            A pagination helper instance.
        """
        return super().get_new_paginator()

    def get_url_params(
        self,
        context: Context | None,  # noqa: ARG002
        next_page_token: t.Any | None,  # noqa: ANN401
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

    def prepare_request_payload(
        self,
        context: Context | None,  # noqa: ARG002
        next_page_token: t.Any | None,  # noqa: ARG002, ANN401
    ) -> dict | None:
        """Prepare the data payload for the REST API request.

        By default, no payload will be sent (return None).

        Args:
            context: The stream context.
            next_page_token: The next page index or value.

        Returns:
            A dictionary with the JSON body for a POST requests.
        """
        # TODO: Delete this method if no payload is required. (Most REST APIs.)
        return None

    def parse_response(self, response: requests.Response) -> t.Iterable[dict]:
        """Parse the response and return an iterator of result records.

        Args:
            response: The HTTP ``requests.Response`` object.

        Yields:
            Each record from the source.
        """
        # TODO: Parse response body and return a set of records.
        yield from extract_jsonpath(
            self.records_jsonpath,
            input=response.json(parse_float=decimal.Decimal),
        )

    def post_process(
        self,
        row: dict,
        context: Context | None = None,  # noqa: ARG002
    ) -> dict | None:
        """As needed, append or transform raw data to match expected structure.

        Args:
            row: An individual record from the stream.
            context: The stream context.

        Returns:
            The updated record dictionary, or ``None`` to skip the record.
        """
        # TODO: Delete this method if not needed.
        return row


class AlgoliaAnalyticsStream(RESTStream):
    """Base class for Algolia Analytics API streams."""

    # Default date range for lookback if not in state
    default_date_window: ClassVar[int] = 30
    
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
            
        # Add pagination parameters if provided
        if next_page_token:
            params["offset"] = next_page_token
            
        # Default limit if not specified
        if "limit" not in params and hasattr(self, "limit"):
            params["limit"] = getattr(self, "limit")
            
        return params

    def get_next_page_token(
        self, response: requests.Response, previous_token: Any | None
    ) -> Any | None:
        """Return token for pagination or None if pagination is finished.

        Args:
            response: API response object.
            previous_token: Previous pagination token.

        Returns:
            The next pagination token (offset) or None if no more pages.
        """
        # This is a simple offset-based implementation for endpoints that support pagination
        offset = 0 if previous_token is None else previous_token
        data = response.json(parse_float=decimal.Decimal)
        
        # Get the endpoint path to determine the response structure
        path = response.request.url.split('?')[0]
        
        # Extract records based on stream type, looking at the records_jsonpath
        records = []
        
        if "/2/users/count" in path:
            # Users count endpoint has dates array
            records = data.get("dates", [])
        elif "/2/searches/count" in path:
            # Searches count endpoint has dates array
            records = data.get("dates", [])
        elif "/2/searches" in path:
            # Top searches endpoint
            records = data.get("searches", [])
        
        # If we got a full page of results, return next offset
        limit = getattr(self, "limit", 1000)
        if len(records) >= limit:
            return offset + limit
            
        # Otherwise, no more pages
        return None

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
            
        # Determine the endpoint from the path
        path = url_parts[0]
        
        # Handle different response formats based on endpoint
        if "/2/users/count" in path:
            # Users count has a dates array
            for date_record in data.get("dates", []):
                if isinstance(date_record, dict):
                    record = dict(date_record)
                    record["index_name"] = index_name
                    record.update(context)
                    yield record
                    
        elif "/2/searches/count" in path:
            # Searches count endpoint with dates array
            for day in data.get("dates", []):
                if isinstance(day, dict):
                    record = dict(day)
                    record["index_name"] = index_name
                    record.update(context)
                    yield record
                    
        elif "/2/searches" in path:
            # Top searches endpoint returns searches array
            for search in data.get("searches", []):
                if isinstance(search, dict):
                    record = dict(search)
                    record["index_name"] = index_name
                    record.update(context)
                    yield record