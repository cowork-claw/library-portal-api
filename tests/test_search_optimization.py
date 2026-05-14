import importlib
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# Setup client fixture similar to integration tests
@pytest.fixture(scope="module")
def client():
    os.environ["LIBRARY_PORTAL_ENVIRONMENT"] = "production"
    os.environ["LIBRARY_PORTAL_API_KEY"] = "test-key"

    import config.config_v2 as config_module

    importlib.reload(config_module)
    import app_v2.main as main_module

    importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client


def test_search_is_offloaded_to_threadpool(client):
    """
    Verify that search_papers is called via run_in_threadpool
    to prevent blocking the event loop.
    """
    # We mock run_in_threadpool where it is used in app_v2/routes/papers.py
    # We also mock search_papers to ensure we don't actually run a search and just verify the call.

    # Note: We need to patch 'app_v2.routes.papers.run_in_threadpool'
    # and 'app_v2.routes.papers.paper_index.search'

    with (
        patch("app_v2.routes.papers.run_in_threadpool") as mock_run_in_threadpool,
        patch("app_v2.routes.papers.paper_index.search") as mock_search,
    ):
        # Configure the mock to return a dummy list so the endpoint continues
        # run_in_threadpool is async-ish when awaited.

        mock_run_in_threadpool.side_effect = None  # Reset

        # Create an async mock wrapper
        async def async_return(*args, **kwargs):
            # return URLs
            return ["http://example.com/test_paper.pdf"]

        mock_run_in_threadpool.side_effect = async_return

        # Also need to ensure _get_by_urls returns valid paper objects
        with patch("app_v2.routes.papers.paper_index._get_by_urls") as mock_get_by_urls:
            mock_get_by_urls.return_value = [
                {
                    "file_name": "test_paper.pdf",
                    "course_code": "TEST101",
                    "paper_type": "Test",
                    "year": 2024,
                }
            ]

            headers = {"X-API-Key": "test-key"}
            response = client.get("/api/papers?search=testquery", headers=headers)

            assert response.status_code == 200

            # Verify run_in_threadpool was called
            assert mock_run_in_threadpool.called

            # Verify arguments: first arg should be the function paper_index.search
            call_args = mock_run_in_threadpool.call_args
            assert call_args is not None

            func_arg = call_args[0][0]
            # In the route: await run_in_threadpool(paper_index.search, search)

            assert func_arg == mock_search

            # Verify the search query was passed as the 2nd argument
            assert call_args[0][1] == "testquery"
