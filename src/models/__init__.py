import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MothershipEvent:
    date: str
    title: str
    time: str
    room: str
    ticket_type: str

    def make_hash(self) -> str:
        data = ":".join([self.date, self.title, self.time, self.room, self.ticket_type])
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def make_event_notification_message(self) -> str:
        return "\n".join(
            [
                "New Mothership Event:\n",
                f"Title: {self.title}",
                f"Date: {self.date}",
                f"Time: {self.time}",
                f"Room: {self.room}",
            ]
        )
