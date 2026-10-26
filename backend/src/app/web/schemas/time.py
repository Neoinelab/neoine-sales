from datetime import date

from pydantic import BaseModel

from app.application.time.get_server_time import ServerTimeView
from app.web.schemas.server_datetime import ServerDateTime


class ServerTimeResponse(BaseModel):
    now: ServerDateTime
    today: date

    @classmethod
    def from_view(cls, view: ServerTimeView) -> ServerTimeResponse:
        return cls(now=view.now, today=view.today)
