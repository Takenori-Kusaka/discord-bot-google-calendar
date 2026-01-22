"""買い物リストクライアント

家族共有の買い物リストを管理します。
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ShoppingItem:
    """買い物アイテム"""

    id: str
    name: str
    quantity: str = ""
    category: str = "その他"
    added_by: str = ""
    added_at: str = ""
    note: str = ""
    completed: bool = False

    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now().isoformat()


# カテゴリ一覧
CATEGORIES = [
    "食品",
    "野菜・果物",
    "肉・魚",
    "乳製品",
    "飲料",
    "調味料",
    "日用品",
    "洗剤・衛生用品",
    "ベビー用品",
    "医薬品",
    "その他",
]


class ShoppingListClient:
    """買い物リストクライアント

    JSONファイルで買い物リストを永続化します。
    """

    def __init__(self, data_dir: str = "data"):
        """初期化

        Args:
            data_dir: データ保存ディレクトリ
        """
        self.data_dir = Path(data_dir)
        self.shopping_file = self.data_dir / "shopping_list.json"

        # データディレクトリを作成
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 買い物リストを読み込み
        self.items: dict[str, ShoppingItem] = {}
        self._load_items()

        logger.info(
            "Shopping list client initialized",
            items_count=len(self.items),
        )

    def _load_items(self) -> None:
        """買い物リストをファイルから読み込み"""
        if self.shopping_file.exists():
            try:
                with open(self.shopping_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_data in data:
                        item = ShoppingItem(**item_data)
                        self.items[item.id] = item
                logger.info(f"Loaded {len(self.items)} shopping items from file")
            except Exception as e:
                logger.error(f"Failed to load shopping list: {e}")
                self.items = {}

    def _save_items(self) -> None:
        """買い物リストをファイルに保存"""
        try:
            with open(self.shopping_file, "w", encoding="utf-8") as f:
                # 未完了のアイテムのみ保存（完了済みは削除）
                data = [asdict(item) for item in self.items.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.items)} shopping items to file")
        except Exception as e:
            logger.error(f"Failed to save shopping list: {e}")

    def _guess_category(self, name: str) -> str:
        """商品名からカテゴリを推測"""
        name_lower = name.lower()

        # カテゴリ判定ルール
        food_keywords = ["米", "パン", "パスタ", "麺", "豆腐", "納豆", "卵", "たまご"]
        vegetable_keywords = [
            "野菜",
            "果物",
            "にんじん",
            "人参",
            "玉ねぎ",
            "たまねぎ",
            "キャベツ",
            "レタス",
            "トマト",
            "りんご",
            "バナナ",
            "みかん",
        ]
        meat_keywords = [
            "肉",
            "豚",
            "牛",
            "鶏",
            "魚",
            "鮭",
            "さけ",
            "マグロ",
            "えび",
            "いか",
        ]
        dairy_keywords = ["牛乳", "ミルク", "チーズ", "ヨーグルト", "バター"]
        drink_keywords = ["水", "お茶", "ジュース", "コーヒー", "紅茶", "ビール", "酒"]
        seasoning_keywords = [
            "醤油",
            "味噌",
            "塩",
            "砂糖",
            "油",
            "酢",
            "マヨネーズ",
            "ケチャップ",
            "ソース",
            "だし",
        ]
        daily_keywords = [
            "ティッシュ",
            "トイレットペーパー",
            "ラップ",
            "アルミホイル",
            "ゴミ袋",
        ]
        cleaning_keywords = [
            "洗剤",
            "シャンプー",
            "石鹸",
            "歯磨き",
            "ハンドソープ",
            "柔軟剤",
        ]
        baby_keywords = ["おむつ", "オムツ", "ミルク", "離乳食", "ベビー"]
        medicine_keywords = ["薬", "絆創膏", "マスク", "体温計", "湿布"]

        if any(kw in name_lower for kw in vegetable_keywords):
            return "野菜・果物"
        elif any(kw in name_lower for kw in meat_keywords):
            return "肉・魚"
        elif any(kw in name_lower for kw in dairy_keywords):
            return "乳製品"
        elif any(kw in name_lower for kw in drink_keywords):
            return "飲料"
        elif any(kw in name_lower for kw in seasoning_keywords):
            return "調味料"
        elif any(kw in name_lower for kw in cleaning_keywords):
            return "洗剤・衛生用品"
        elif any(kw in name_lower for kw in daily_keywords):
            return "日用品"
        elif any(kw in name_lower for kw in baby_keywords):
            return "ベビー用品"
        elif any(kw in name_lower for kw in medicine_keywords):
            return "医薬品"
        elif any(kw in name_lower for kw in food_keywords):
            return "食品"
        else:
            return "その他"

    def add_item(
        self,
        name: str,
        quantity: str = "",
        category: Optional[str] = None,
        note: str = "",
        added_by: str = "",
    ) -> ShoppingItem:
        """買い物アイテムを追加

        Args:
            name: 商品名
            quantity: 数量
            category: カテゴリ（省略時は自動判定）
            note: メモ
            added_by: 追加者

        Returns:
            追加されたShoppingItem
        """
        item_id = str(uuid.uuid4())[:8]

        # カテゴリを自動判定
        if not category:
            category = self._guess_category(name)

        item = ShoppingItem(
            id=item_id,
            name=name,
            quantity=quantity,
            category=category,
            note=note,
            added_by=added_by,
        )

        self.items[item_id] = item
        self._save_items()

        logger.info(
            "Shopping item added",
            id=item_id,
            name=name,
            category=category,
        )

        return item

    def remove_item(self, item_id: str) -> bool:
        """買い物アイテムを削除

        Args:
            item_id: アイテムID

        Returns:
            削除成功したかどうか
        """
        if item_id not in self.items:
            return False

        del self.items[item_id]
        self._save_items()

        logger.info(f"Shopping item removed: {item_id}")
        return True

    def remove_item_by_name(self, name: str) -> Optional[ShoppingItem]:
        """商品名で買い物アイテムを削除

        Args:
            name: 商品名（部分一致）

        Returns:
            削除されたアイテム（見つからなければNone）
        """
        name_lower = name.lower()
        for item_id, item in list(self.items.items()):
            if name_lower in item.name.lower():
                del self.items[item_id]
                self._save_items()
                logger.info(f"Shopping item removed by name: {item.name}")
                return item
        return None

    def mark_completed(self, item_id: str) -> bool:
        """買い物アイテムを完了にする

        Args:
            item_id: アイテムID

        Returns:
            成功したかどうか
        """
        if item_id not in self.items:
            return False

        self.items[item_id].completed = True
        self._save_items()
        return True

    def list_items(self, category: Optional[str] = None) -> list[ShoppingItem]:
        """買い物リストを取得

        Args:
            category: カテゴリでフィルタ（省略時は全件）

        Returns:
            買い物アイテムリスト
        """
        items = list(self.items.values())

        # 完了済みは除外
        items = [item for item in items if not item.completed]

        # カテゴリでフィルタ
        if category:
            items = [item for item in items if item.category == category]

        # カテゴリでソート
        items.sort(
            key=lambda x: (
                CATEGORIES.index(x.category) if x.category in CATEGORIES else 999,
                x.name,
            )
        )

        return items

    def get_item(self, item_id: str) -> Optional[ShoppingItem]:
        """アイテムを取得

        Args:
            item_id: アイテムID

        Returns:
            ShoppingItemまたはNone
        """
        return self.items.get(item_id)

    def clear_completed(self) -> int:
        """完了済みアイテムを削除

        Returns:
            削除されたアイテム数
        """
        completed_ids = [
            item_id for item_id, item in self.items.items() if item.completed
        ]
        for item_id in completed_ids:
            del self.items[item_id]

        if completed_ids:
            self._save_items()

        return len(completed_ids)

    def format_item(self, item: ShoppingItem) -> str:
        """アイテムを読みやすい形式でフォーマット"""
        result = f"[{item.id}] {item.name}"
        if item.quantity:
            result += f" ({item.quantity})"
        return result

    def format_list(self, category: Optional[str] = None) -> str:
        """買い物リストを読みやすい形式でフォーマット"""
        items = self.list_items(category)

        if not items:
            if category:
                return f"{category}の買い物リストは空でございます。"
            return "買い物リストは空でございます。"

        lines = ["【買い物リスト】"]

        # カテゴリごとにグループ化
        current_category = None
        for item in items:
            if item.category != current_category:
                current_category = item.category
                lines.append(f"\n■ {current_category}")

            item_str = f"  - {item.name}"
            if item.quantity:
                item_str += f" ({item.quantity})"
            if item.note:
                item_str += f" ※{item.note}"
            item_str += f" [{item.id}]"
            lines.append(item_str)

        lines.append(f"\n合計: {len(items)}品")

        return "\n".join(lines)

    def get_categories(self) -> list[str]:
        """利用可能なカテゴリ一覧を取得"""
        return CATEGORIES.copy()
