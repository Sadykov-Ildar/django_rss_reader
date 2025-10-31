from pathlib import Path
from urllib.parse import urlparse

import aiofiles
from aiohttp import ClientResponse
from django.conf import settings


async def save_image(file_path, response: ClientResponse):
    async with aiofiles.open(file_path, mode="wb") as f:
        async for chunk in response.content.iter_chunked(8192):
            await f.write(chunk)


def get_favicon_name_from_url(url):
    parsed_url = urlparse(url)
    base_name = parsed_url.netloc.replace("/", "_").replace(".", "_")
    image_name = parsed_url.path.replace("/", "__")
    path = base_name + image_name
    filename = Path("favicons") / Path(path)
    return filename


def get_image_file_path(image_name):
    return settings.MEDIA_ROOT / image_name
