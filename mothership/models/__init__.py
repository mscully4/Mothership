from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class MothershipEvent:
    title: str
    dt: str
    time: str
    room: str

    def make_hash(self) -> str:
        data = ":".join([self.title, self.dt, self.time, self.room])
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def make_event_notification_message(self) -> str:
        return "\n".join(
            [
                "New Mothership Event:\n",
                f"Title: {self.title}",
                f"Date: {self.dt}",
                f"Time: {self.time}",
                f"Room: {self.room}",
            ]
        )
