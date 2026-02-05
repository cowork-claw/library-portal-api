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
    # and 'app_v2.routes.papers.search_papers'

    with patch("app_v2.routes.papers.run_in_threadpool") as mock_run_in_threadpool, \
         patch("app_v2.routes.papers.search_papers") as mock_search_papers:

        # Configure the mock to return a dummy list so the endpoint continues
        # run_in_threadpool is async-ish when awaited.

        mock_run_in_threadpool.side_effect = None # Reset

        # Create an async mock wrapper
        async def async_return(*args, **kwargs):
            return [{
                "file_name": "test_paper.pdf",
                "course_code": "TEST101",
                "paper_type": "Test",
                "year": 2024
            }]

        mock_run_in_threadpool.side_effect = async_return

        headers = {"X-API-Key": "test-key"}
        response = client.get("/api/papers?search=testquery", headers=headers)

        assert response.status_code == 200

        # Verify run_in_threadpool was called
        assert mock_run_in_threadpool.called

        # Verify arguments: first arg should be the function search_papers
        call_args = mock_run_in_threadpool.call_args
        assert call_args is not None

        func_arg = call_args[0][0]
        # In the route: await run_in_threadpool(search_papers, results, search)

        # Since we patched search_papers in the route file, the first arg should be that mock
        assert func_arg == mock_search_papers

        # Verify the search query was passed as the 3rd argument (results is 2nd)
        assert call_args[0][2] == "testquery"
