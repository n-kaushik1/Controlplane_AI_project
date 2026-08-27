import json
import os
import threading
from typing import Any, Dict, List


class FeedbackStore:

    def __init__(
        self,
        file_path: str = (
            "logs/feedback.jsonl"
        ),
    ):

        self.file_path = file_path

        self._lock = threading.Lock()

        directory = os.path.dirname(
            self.file_path
        )

        if directory:

            os.makedirs(
                directory,
                exist_ok=True
            )

    # =========================================================
    # SAVE FEEDBACK
    # =========================================================

    def save(
        self,
        feedback: Dict[str, Any]
    ) -> Dict[str, Any]:

        with self._lock:

            with open(
                self.file_path,
                "a",
                encoding="utf-8"
            ) as file:

                file.write(
                    json.dumps(
                        feedback,
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

        return feedback

    # =========================================================
    # READ FEEDBACK
    # =========================================================

    def read_all(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:

        if not os.path.exists(
            self.file_path
        ):

            return []

        records = []

        try:

            with open(
                self.file_path,
                "r",
                encoding="utf-8"
            ) as file:

                for line in file:

                    line = line.strip()

                    if not line:
                        continue

                    try:

                        records.append(
                            json.loads(line)
                        )

                    except json.JSONDecodeError:

                        continue

        except OSError:

            return []

        return records[-limit:]

    # =========================================================
    # FEEDBACK SUMMARY
    # =========================================================

    def summary(self) -> Dict[str, Any]:

        records = self.read_all(
            limit=100000
        )

        total = len(records)

        approved = sum(
            1
            for record in records
            if record.get(
                "final_decision"
            ) == "ALLOW"
        )

        blocked = sum(
            1
            for record in records
            if record.get(
                "final_decision"
            ) == "BLOCK"
        )

        edited = sum(
            1
            for record in records
            if record.get(
                "final_decision"
            ) == "EDIT"
        )

        return {
            "total": total,
            "approved": approved,
            "blocked": blocked,
            "edited": edited,
        }