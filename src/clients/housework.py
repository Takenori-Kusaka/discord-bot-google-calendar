"""家事記録クライアント

家事タスクと住宅メンテナンス記録を管理します。
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HouseworkTask:
    """家事タスク"""

    id: str
    name: str
    category: str
    last_done: str = ""
    interval_days: int = 0  # 0 = 繰り返しなし
    next_due: str = ""
    note: str = ""
    done_by: str = ""

    def __post_init__(self):
        # next_dueを計算
        if self.last_done and self.interval_days > 0 and not self.next_due:
            last = datetime.fromisoformat(self.last_done)
            next_date = last + timedelta(days=self.interval_days)
            self.next_due = next_date.isoformat()


# カテゴリ一覧
HOUSEWORK_CATEGORIES = [
    "掃除",
    "洗濯",
    "料理",
    "買い出し",
    "ゴミ出し",
    "整理整頓",
    "住宅メンテナンス",
    "家電メンテナンス",
    "庭・外回り",
    "その他",
]

# デフォルトの家事タスク
DEFAULT_TASKS = [
    {
        "name": "エアコンフィルター掃除",
        "category": "家電メンテナンス",
        "interval_days": 90,
    },
    {"name": "換気扇掃除", "category": "掃除", "interval_days": 180},
    {"name": "浴室カビ取り", "category": "掃除", "interval_days": 30},
    {"name": "トイレ掃除", "category": "掃除", "interval_days": 7},
    {"name": "洗濯機槽洗浄", "category": "家電メンテナンス", "interval_days": 30},
    {"name": "冷蔵庫掃除", "category": "家電メンテナンス", "interval_days": 90},
    {"name": "窓拭き", "category": "掃除", "interval_days": 90},
    {"name": "布団干し", "category": "洗濯", "interval_days": 14},
    {"name": "排水口掃除", "category": "掃除", "interval_days": 14},
    {"name": "火災報知器点検", "category": "住宅メンテナンス", "interval_days": 365},
]


class HouseworkClient:
    """家事記録クライアント

    JSONファイルで家事タスクを永続化します。
    """

    def __init__(self, data_dir: str = "data"):
        """初期化

        Args:
            data_dir: データ保存ディレクトリ
        """
        self.data_dir = Path(data_dir)
        self.housework_file = self.data_dir / "housework.json"

        # データディレクトリを作成
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # タスクを読み込み
        self.tasks: dict[str, HouseworkTask] = {}
        self._load_tasks()

        logger.info(
            "Housework client initialized",
            tasks_count=len(self.tasks),
        )

    def _load_tasks(self) -> None:
        """タスクをファイルから読み込み"""
        if self.housework_file.exists():
            try:
                with open(self.housework_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for task_data in data:
                        task = HouseworkTask(**task_data)
                        self.tasks[task.id] = task
                logger.info(f"Loaded {len(self.tasks)} housework tasks from file")
            except Exception as e:
                logger.error(f"Failed to load housework tasks: {e}")
                self.tasks = {}
        else:
            # 初回起動時はデフォルトタスクを作成
            self._create_default_tasks()

    def _create_default_tasks(self) -> None:
        """デフォルトタスクを作成"""
        for task_def in DEFAULT_TASKS:
            task_id = str(uuid.uuid4())[:8]
            task = HouseworkTask(
                id=task_id,
                name=task_def["name"],
                category=task_def["category"],
                interval_days=task_def["interval_days"],
            )
            self.tasks[task_id] = task

        self._save_tasks()
        logger.info(f"Created {len(DEFAULT_TASKS)} default housework tasks")

    def _save_tasks(self) -> None:
        """タスクをファイルに保存"""
        try:
            with open(self.housework_file, "w", encoding="utf-8") as f:
                data = [asdict(task) for task in self.tasks.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.tasks)} housework tasks to file")
        except Exception as e:
            logger.error(f"Failed to save housework tasks: {e}")

    def add_task(
        self,
        name: str,
        category: str = "その他",
        interval_days: int = 0,
        note: str = "",
    ) -> HouseworkTask:
        """タスクを追加

        Args:
            name: タスク名
            category: カテゴリ
            interval_days: 繰り返し間隔（日数）
            note: メモ

        Returns:
            追加されたHouseworkTask
        """
        task_id = str(uuid.uuid4())[:8]

        task = HouseworkTask(
            id=task_id,
            name=name,
            category=category,
            interval_days=interval_days,
            note=note,
        )

        self.tasks[task_id] = task
        self._save_tasks()

        logger.info(
            "Housework task added",
            id=task_id,
            name=name,
            category=category,
        )

        return task

    def mark_done(
        self,
        task_id: str,
        done_by: str = "",
        done_at: Optional[datetime] = None,
    ) -> Optional[HouseworkTask]:
        """タスクを完了としてマーク

        Args:
            task_id: タスクID
            done_by: 完了者
            done_at: 完了日時（省略時は現在時刻）

        Returns:
            更新されたタスク（見つからない場合はNone）
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        done_time = done_at or datetime.now()
        task.last_done = done_time.isoformat()
        task.done_by = done_by

        # 次回予定日を更新
        if task.interval_days > 0:
            next_date = done_time + timedelta(days=task.interval_days)
            task.next_due = next_date.isoformat()

        self._save_tasks()

        logger.info(f"Housework task marked done: {task.name}")
        return task

    def mark_done_by_name(
        self,
        name: str,
        done_by: str = "",
    ) -> Optional[HouseworkTask]:
        """タスク名で完了としてマーク

        Args:
            name: タスク名（部分一致）
            done_by: 完了者

        Returns:
            更新されたタスク（見つからない場合はNone）
        """
        name_lower = name.lower()
        for task_id, task in self.tasks.items():
            if name_lower in task.name.lower():
                return self.mark_done(task_id, done_by)
        return None

    def delete_task(self, task_id: str) -> bool:
        """タスクを削除

        Args:
            task_id: タスクID

        Returns:
            削除成功したかどうか
        """
        if task_id not in self.tasks:
            return False

        del self.tasks[task_id]
        self._save_tasks()

        logger.info(f"Housework task deleted: {task_id}")
        return True

    def list_tasks(
        self,
        category: Optional[str] = None,
        due_only: bool = False,
    ) -> list[HouseworkTask]:
        """タスク一覧を取得

        Args:
            category: カテゴリでフィルタ
            due_only: 期限切れのみ表示

        Returns:
            タスクリスト
        """
        tasks = list(self.tasks.values())

        # カテゴリでフィルタ
        if category:
            tasks = [t for t in tasks if t.category == category]

        # 期限切れのみ
        if due_only:
            now = datetime.now().isoformat()
            tasks = [t for t in tasks if t.next_due and t.next_due <= now]

        # ソート（次回予定日順、未設定は最後）
        def sort_key(t):
            if t.next_due:
                return (0, t.next_due)
            elif t.last_done:
                return (1, t.last_done)
            else:
                return (2, t.name)

        tasks.sort(key=sort_key)

        return tasks

    def get_task(self, task_id: str) -> Optional[HouseworkTask]:
        """タスクを取得"""
        return self.tasks.get(task_id)

    def get_overdue_tasks(self) -> list[HouseworkTask]:
        """期限切れタスクを取得"""
        return self.list_tasks(due_only=True)

    def format_task(self, task: HouseworkTask) -> str:
        """タスクを読みやすい形式でフォーマット"""
        result = f"[{task.id}] {task.name}"
        if task.interval_days > 0:
            result += f" (毎{task.interval_days}日)"
        return result

    def format_list(
        self,
        category: Optional[str] = None,
        due_only: bool = False,
    ) -> str:
        """タスク一覧を読みやすい形式でフォーマット"""
        tasks = self.list_tasks(category, due_only)

        if not tasks:
            if due_only:
                return "期限切れの家事タスクはございません。素晴らしいですね！"
            if category:
                return f"{category}の家事タスクは登録されておりません。"
            return "家事タスクは登録されておりません。"

        if due_only:
            lines = ["【期限切れの家事タスク】"]
        else:
            lines = ["【家事タスク一覧】"]

        # カテゴリごとにグループ化
        current_category = None
        now = datetime.now()

        for task in tasks:
            if task.category != current_category:
                current_category = task.category
                lines.append(f"\n■ {current_category}")

            # タスク情報を構築
            task_str = f"  - {task.name}"

            # 繰り返し情報
            if task.interval_days > 0:
                if task.interval_days == 7:
                    task_str += " [毎週]"
                elif task.interval_days == 14:
                    task_str += " [隔週]"
                elif task.interval_days == 30:
                    task_str += " [毎月]"
                elif task.interval_days == 90:
                    task_str += " [3ヶ月毎]"
                elif task.interval_days == 180:
                    task_str += " [半年毎]"
                elif task.interval_days == 365:
                    task_str += " [毎年]"
                else:
                    task_str += f" [{task.interval_days}日毎]"

            # 最終実行日
            if task.last_done:
                last = datetime.fromisoformat(task.last_done)
                days_ago = (now - last).days
                if days_ago == 0:
                    task_str += " ※本日実施"
                elif days_ago == 1:
                    task_str += " ※昨日実施"
                else:
                    task_str += f" ※{days_ago}日前"

            # 期限切れ警告
            if task.next_due:
                next_date = datetime.fromisoformat(task.next_due)
                if next_date < now:
                    days_overdue = (now - next_date).days
                    task_str += f" ⚠️期限{days_overdue}日超過"

            task_str += f" [{task.id}]"
            lines.append(task_str)

        lines.append(f"\n合計: {len(tasks)}件")

        return "\n".join(lines)

    def get_categories(self) -> list[str]:
        """利用可能なカテゴリ一覧を取得"""
        return HOUSEWORK_CATEGORIES.copy()
