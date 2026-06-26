import re


def test_smoke():
    import complexity_guard

    # Don't pin a literal version here — that's how the __version__ drift went
    # unnoticed. Just assert it's a well-formed semver; test_version_guard.py
    # enforces that it matches the manifests.
    assert re.fullmatch(r"\d+\.\d+\.\d+", complexity_guard.__version__)
