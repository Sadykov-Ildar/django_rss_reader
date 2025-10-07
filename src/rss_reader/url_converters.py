from datetime import datetime


class DateTimeConverter:
    regex = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"  # Matches YYYY-MM-DD HH:MM:SSformat

    def to_python(self, value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")

    def to_url(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")
