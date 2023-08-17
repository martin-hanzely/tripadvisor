import os

import pytest
import requests

import tripadvisor.service as tripadvisor


class _InvalidTripadvisorService(tripadvisor.TripadvisorService):
    """
    Mock Tripadvisor service raising HTTPError in all API calls.
    """
    def _api_call(self, *args, **kwargs):
        raise requests.exceptions.HTTPError


class TestTripadvisorService:
    """
    Integration tests for Tripadvisor API service with real data.
    """
    _location_id: int = 247957  # Occidental Punta Cana.
    _location_id_no_reviews: int = 12889941  # Hotel Orios Primorsko.

    @pytest.fixture
    def tripadvisor_service_credentials(self) -> dict[str, str]:
        """
        Real credentials for integration tests.
        """
        api_url = os.getenv("TRIPADVISOR_API_URL")
        api_key = os.getenv("TRIPADVISOR_API_KEY")
        default_language_code = os.getenv("TRIPADVISOR_DEFAULT_LANGUAGE_CODE")

        if not any((api_url, api_key, default_language_code)):
            raise ValueError("Invalid service configuration.")

        return {
            "api_url": api_url,
            "api_key": api_key,
            "default_language_code": default_language_code,
        }

    @pytest.fixture
    def tripadvisor_service(self, tripadvisor_service_credentials) -> tripadvisor.TripadvisorService:
        """
        Service fixture.
        """
        return tripadvisor.TripadvisorService(**tripadvisor_service_credentials)

    @pytest.fixture
    def invalid_tripadvisor_service(self, tripadvisor_service_credentials) -> tripadvisor.TripadvisorService:
        """
        Erroneous service fixture.
        """
        return _InvalidTripadvisorService(**tripadvisor_service_credentials)

    # region All data available
    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_lat_long(self, tripadvisor_service):
        lat, long = tripadvisor_service.get_lat_long(self._location_id)
        assert (lat and long) is not None

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_hotel_reviews_details(self, tripadvisor_service):
        review_details = tripadvisor_service.get_hotel_reviews_details(self._location_id)
        assert isinstance(review_details, tripadvisor.ReviewsDataClass)

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_reviews_list(self, tripadvisor_service):
        reviews_list = tripadvisor_service.get_reviews_list(self._location_id)
        assert reviews_list is not None
        for review in reviews_list:
            assert isinstance(review, tripadvisor.SingleReview)
    # endregion

    # region No reviews available
    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_lat_long__no_reviews(self, tripadvisor_service):
        lat, long = tripadvisor_service.get_lat_long(self._location_id_no_reviews)
        assert (lat and long) is not None

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_hotel_reviews_details__no_reviews(self, tripadvisor_service):
        review_details = tripadvisor_service.get_hotel_reviews_details(self._location_id_no_reviews)
        assert review_details is None

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_reviews_list__no_reviews(self, tripadvisor_service):
        reviews_list = tripadvisor_service.get_reviews_list(self._location_id_no_reviews)
        assert reviews_list is not None
        assert len(reviews_list) == 0
    # endregion

    # region Http error
    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_lat_long__http_error(self, invalid_tripadvisor_service):
        lat, long = invalid_tripadvisor_service.get_lat_long(self._location_id)
        assert (lat and long) is not None

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_hotel_reviews_details__http_error(self, invalid_tripadvisor_service):
        review_details = invalid_tripadvisor_service.get_hotel_reviews_details(self._location_id)
        assert review_details is None

    @pytest.mark.django_db  # Required for use of the cache framework.
    def test_get_reviews_list__http_error(self, invalid_tripadvisor_service):
        reviews_list = invalid_tripadvisor_service.get_reviews_list(self._location_id)
        assert reviews_list is not None
        assert len(reviews_list) == 0
    # endregion
