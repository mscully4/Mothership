from dataclasses import dataclass


@dataclass(frozen=True)
class MothershipEvent:
    _id: str
    title: str
    dt: str
    room: str
    ticket_availability: str
    url: str

    def make_event_notification_message(self) -> str:
        return "\n".join(
            [
                "New Mothership Event:\n",
                f"Title: {self.title}",
                f"Datetime: {self.dt}",
                f"Room: {self.room}",
                f"Url: {self.url}",
            ]
        )
