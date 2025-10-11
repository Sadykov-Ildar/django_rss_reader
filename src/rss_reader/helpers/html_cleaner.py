import re

_class_pattern = re.compile(r'(?s)class="(.*?)"')

def clean_html(content: str) -> str:
    content = re.sub(_class_pattern, "", content)

    return content
