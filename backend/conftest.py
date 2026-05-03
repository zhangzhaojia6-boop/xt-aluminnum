from pathlib import Path


def pytest_configure(config):
    """Keep pytest cache inside the backend tree on Windows runners."""
    cache_dir = Path(config.rootpath) / ".pytest_cache"
    cache = getattr(config, "cache", None)
    if cache is not None:
        cache._cachedir = cache_dir
