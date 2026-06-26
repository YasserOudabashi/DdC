"""Reset rate-limiter storage between every test to avoid 429 cross-test interference."""
import pytest
from app.security import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter._storage.reset()
    yield
    limiter._storage.reset()
