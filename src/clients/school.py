"""学校情報クライアント

子供たちの学校・保育園情報を管理します。
データはpersonal.gitリポジトリのYAMLファイルに保存されます。
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from ..utils.logger import get_logger

logger = get_logger(__name__)

# デフォルトのデータファイルパス
DEFAULT_SCHOOL_DATA_PATH = "docs/personal/data/school.yml"


@dataclass
class SchoolInfo:
    """学校情報"""

    id: str
    name: str
    school_type: str
    child: str
    contact: dict[str, str]
    hours: dict[str, str]
    events: list[dict[str, Any]]
    required_items: dict[str, list[str]]
    holidays: dict[str, Any]
    notes: str = ""


class SchoolClient:
    """学校情報クライアント

    YAMLファイルから学校情報を読み込みます。
    データの永続化はYAMLファイルで行います。
    """

    def __init__(self, data_path: Optional[str] = None):
        """初期化

        Args:
            data_path: データファイルのパス（省略時はデフォルト）
        """
        self.data_path = Path(data_path or DEFAULT_SCHOOL_DATA_PATH)
        self.schools: list[SchoolInfo] = []
        self.notes: list[dict[str, str]] = []
        self._load_data()

        logger.info(
            "School client initialized",
            schools_count=len(self.schools),
            data_path=str(self.data_path),
        )

    def _load_data(self) -> None:
        """YAMLファイルからデータを読み込み"""
        if not self.data_path.exists():
            logger.warning(f"School data file not found: {self.data_path}")
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # 学校情報を読み込み
            for school_data in data.get("schools", []):
                school = SchoolInfo(
                    id=school_data.get("id", ""),
                    name=school_data.get("name", "（未設定）"),
                    school_type=school_data.get("type", ""),
                    child=school_data.get("child", ""),
                    contact=school_data.get("contact", {}),
                    hours=school_data.get("hours", {}),
                    events=school_data.get("events", []),
                    required_items=school_data.get("required_items", {}),
                    holidays=school_data.get("holidays", {}),
                    notes=school_data.get("notes", ""),
                )
                self.schools.append(school)

            # メモを読み込み
            self.notes = data.get("notes", [])

            logger.info(f"Loaded {len(self.schools)} school(s) from file")

        except Exception as e:
            logger.error(f"Failed to load school data: {e}")

    def reload(self) -> None:
        """データを再読み込み"""
        self.schools = []
        self.notes = []
        self._load_data()

    def get_school(self, school_id: str) -> Optional[SchoolInfo]:
        """学校情報を取得

        Args:
            school_id: 学校ID

        Returns:
            SchoolInfo または None
        """
        for school in self.schools:
            if school.id == school_id:
                return school
        return None

    def get_school_by_child(self, child: str) -> Optional[SchoolInfo]:
        """子供で学校情報を検索

        Args:
            child: 子供の名称（お嬢様、坊ちゃま等）

        Returns:
            SchoolInfo または None
        """
        for school in self.schools:
            if child in school.child:
                return school
        return None

    def list_schools(self) -> list[SchoolInfo]:
        """全学校情報を取得"""
        return self.schools.copy()

    def get_upcoming_events(self, days: int = 30) -> list[dict]:
        """今後のイベントを取得

        Args:
            days: 何日先まで取得するか

        Returns:
            イベントリスト
        """
        today = datetime.now()
        current_year = today.year
        upcoming = []

        for school in self.schools:
            for event in school.events:
                if not event.get("date"):
                    continue

                # MM-DD形式の日付をパース
                date_str = event["date"]
                try:
                    if len(date_str) == 5:  # MM-DD
                        event_date = datetime.strptime(
                            f"{current_year}-{date_str}", "%Y-%m-%d"
                        )
                        # 過去の日付なら来年にする
                        if event_date < today:
                            event_date = datetime.strptime(
                                f"{current_year + 1}-{date_str}", "%Y-%m-%d"
                            )
                    else:  # YYYY-MM-DD
                        event_date = datetime.strptime(date_str, "%Y-%m-%d")

                    # 期間内のイベントを追加
                    diff = (event_date - today).days
                    if 0 <= diff <= days:
                        upcoming.append(
                            {
                                "name": event["name"],
                                "date": event_date.strftime("%Y-%m-%d"),
                                "days_until": diff,
                                "school": school.name or school.school_type,
                                "child": school.child,
                                "notes": event.get("notes", ""),
                            }
                        )

                except ValueError:
                    continue

        # 日付順でソート
        upcoming.sort(key=lambda x: x["date"])
        return upcoming

    def get_required_items(
        self,
        school_id: Optional[str] = None,
        item_type: str = "daily",
    ) -> dict[str, list[str]]:
        """持ち物リストを取得

        Args:
            school_id: 学校ID（省略時は全校）
            item_type: アイテムタイプ（daily, weekly, special）

        Returns:
            学校ごとの持ち物リスト
        """
        result = {}

        for school in self.schools:
            if school_id and school.id != school_id:
                continue

            school_key = school.name or school.school_type
            items = school.required_items.get(item_type, [])
            if items:
                result[school_key] = items

        return result

    def format_school_info(self, school: SchoolInfo) -> str:
        """学校情報をフォーマット"""
        lines = [f"【{school.school_type}情報】"]

        if school.name:
            lines.append(f"名称: {school.name}")

        lines.append(f"対象: {school.child}")

        # 開園時間
        if school.hours:
            open_time = school.hours.get("open", "")
            close_time = school.hours.get("close", "")
            if open_time and close_time:
                lines.append(f"開園時間: {open_time}〜{close_time}")
            ext_close = school.hours.get("extended_close", "")
            if ext_close:
                lines.append(f"延長保育: 〜{ext_close}")

        # 連絡先
        if school.contact:
            phone = school.contact.get("phone", "")
            if phone:
                lines.append(f"電話: {phone}")

        return "\n".join(lines)

    def format_upcoming_events(self, days: int = 30) -> str:
        """今後のイベントをフォーマット"""
        events = self.get_upcoming_events(days)

        if not events:
            return f"今後{days}日以内の学校行事はございません。"

        lines = [f"【今後の学校行事（{days}日以内）】"]

        for event in events:
            date = datetime.strptime(event["date"], "%Y-%m-%d")
            date_str = date.strftime("%m/%d(%a)")

            if event["days_until"] == 0:
                days_str = "本日"
            elif event["days_until"] == 1:
                days_str = "明日"
            else:
                days_str = f"あと{event['days_until']}日"

            line = f"- {date_str} {event['name']} ({event['child']}) [{days_str}]"
            if event.get("notes"):
                line += f" ※{event['notes']}"
            lines.append(line)

        return "\n".join(lines)

    def format_required_items(
        self,
        item_type: str = "daily",
        school_id: Optional[str] = None,
    ) -> str:
        """持ち物リストをフォーマット"""
        items = self.get_required_items(school_id, item_type)

        type_names = {
            "daily": "毎日の持ち物",
            "weekly": "週ごとの持ち物",
            "special": "特別な持ち物",
        }
        type_name = type_names.get(item_type, item_type)

        if not items:
            return f"{type_name}の登録がございません。"

        lines = [f"【{type_name}】"]

        for school, item_list in items.items():
            lines.append(f"\n■ {school}")
            for item in item_list:
                lines.append(f"  - {item}")

        return "\n".join(lines)
