from pathlib import Path

from django.conf import settings

from rss_reader.use_cases.rss.dtos import RequestResult


def get_fixtures_dir() -> Path:
    return settings.BASE_DIR / "tests" / "data_files"


def get_fixture_path(fixture_name: str) -> Path:
    return get_fixtures_dir() / fixture_name


def get_rss_response_content(file_name) -> str:
    file_path = get_fixture_path(Path("feeds") / file_name)
    with open(file_path) as f:
        content = f.read()

    return content


def get_new_request_result(
    url: str, file_name: str, status=200, headers=None
) -> RequestResult:
    if headers is None:
        headers = {}

    content = get_rss_response_content(file_name)

    return RequestResult(
        url=url,
        headers=headers,
        status=status,
        content=content,
        error_message="",
    )
