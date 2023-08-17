from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urljoin

import requests


class CacheProtocol(Protocol):
    """
    Minimalistic cache protocol compatible with Django cache framework.
    """
    def get(self, key: str) -> Any: ...

    def set(self, key: str, value: Any, timeout: int) -> None: ...


class TripadvisorServiceError(Exception):
    """
    Base exception for Tripadvisor service.
    """


@dataclass
class SingleReview:
    """
    Single review written by single user.
    """
    published_date: datetime.date
    rating_image_url: str
    text: str
    title: str
    username: str
    trip_type: str


@dataclass
class Subrating:
    """
    Rating of a certain location feature.
    """
    localized_name: str
    rating_image_url: int


@dataclass
class ReviewsDataClass:
    """
    Reviews data summary for a location.
    """
    rating_image_url: str
    num_reviews: int
    ranking_string: str
    web_url: str
    subratings: list[Subrating] = field(default_factory=list)


class TripadvisorService:
    """
    Connection service for Tripadvisor Content API.
    """
    _api_url: str  # Trailing slash required.
    _api_key: str
    _default_language_code: str
    _cache: CacheProtocol | None = None
    _cache_timeout: int = 86_400  # 24 hours as recommended by docs.

    def __init__(
            self,
            *,
            api_url: str,
            api_key: str,
            default_language_code: str,
            cache: CacheProtocol | None = None
    ) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._default_language_code = default_language_code
        self._cache = cache

    def get_lat_long(self, location_id: int) -> tuple[float, float]:
        """
        Returns latitude and longitude as tuple.
        """
        try:
            location_data = self._get_location_details(location_id)
        except TripadvisorServiceError:
            return 0.0, 0.0  # Do not break the whole app if Tripadvisor API is down.

        return float(location_data["latitude"]), float(location_data["longitude"])

    def get_hotel_reviews_details(self, location_id: int) -> ReviewsDataClass | None:
        """
        Returns reviews detail data as ReviewsDataClass or None if any data is missing.
        """
        try:
            location_data = self._get_location_details(location_id)
        except TripadvisorServiceError:
            return None

        ranking_data = location_data.get("ranking_data", {"ranking_string": ""})
        subratings = [
                Subrating(
                    localized_name=subrating["localized_name"],
                    rating_image_url=rating_image_url,
                )
                for subrating in location_data.get("subratings", {}).values()
                if (rating_image_url := subrating.get("rating_image_url"))
            ]

        try:
            return ReviewsDataClass(
                rating_image_url=location_data["rating_image_url"],
                num_reviews=location_data["num_reviews"],
                ranking_string=ranking_data["ranking_string"],
                web_url=location_data["web_url"],
                subratings=subratings,
            )
        except KeyError:
            return None

    def get_reviews_list(self, location_id: int) -> list[SingleReview]:
        """
        Returns reviews detail data as ReviewsDataClass.
        """
        try:
            reviews = self._get_reviews(location_id)["data"]
        except TripadvisorServiceError:
            return []

        return [
            SingleReview(
                published_date=datetime.date.fromisoformat(review["published_date"][:10]),
                rating_image_url=rating_image_url,
                text=review["text"],
                title=review["title"],
                username=review["user"]["username"],
                trip_type=review.get("trip_type", "Neznámy"),
            )
            for review in reviews
            if (rating_image_url := review.get("rating_image_url"))
        ]

    def _get_location_details(self, location_id: int) -> dict[str, Any]:
        """
        Returns either cached or fresh location details from
        https://api.content.tripadvisor.com/api/v1/location/{locationId}/details.
        """
        try:
            return self._api_call(
                cache_key=f"tripadvisor_detail_cache_{location_id}",
                url_path=f"{location_id}/details",
            )
        except requests.exceptions.HTTPError as e:
            raise TripadvisorServiceError from e

    def _get_reviews(self, location_id: int) -> dict[str, Any]:
        """
        Returns either cached or fresh location reviews from
        https://api.content.tripadvisor.com/api/v1/location/{locationId}/reviews.
        """
        try:
            return self._api_call(
                cache_key=f"tripadvisor_reviews_cache_{location_id}",
                url_path=f"{location_id}/reviews",
            )
        except requests.exceptions.HTTPError as e:
            raise TripadvisorServiceError from e

    def _api_call(self, cache_key: str, url_path: str) -> dict[str, Any]:
        """
        Generic api call. Caches new data.
        """
        cache = self._cache
        if cache is not None:
            result = cache.get(cache_key)
            if result is not None:  # Cache hit.
                return result

        response = requests.get(
            urljoin(self._api_url, url_path),
            params={
                "key": self._api_key,
                "language": self._default_language_code,
            },
            timeout=60,
        )
        response.raise_for_status()  # Raise exception if response status is not OK.
        json_data = response.json()

        # Populate cache.
        if cache is not None:
            cache.set(cache_key, json_data, timeout=self._cache_timeout)

        # Return requested value.
        return json_data
