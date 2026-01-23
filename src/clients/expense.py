"""家計簿クライアント

支出・収入を記録し、家計管理をサポートします。
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
class ExpenseRecord:
    """支出/収入レコード"""

    id: str
    amount: int  # 金額（円）
    category: str
    description: str = ""
    date: str = ""  # YYYY-MM-DD
    record_type: str = "expense"  # expense or income
    payment_method: str = ""  # 現金, クレジット, 電子マネー等
    created_at: str = ""

    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


# カテゴリ一覧
EXPENSE_CATEGORIES = [
    "食費",
    "日用品",
    "交通費",
    "医療費",
    "教育費",
    "娯楽費",
    "衣服費",
    "通信費",
    "水道光熱費",
    "住居費",
    "保険料",
    "子供関連",
    "その他",
]

INCOME_CATEGORIES = [
    "給与",
    "副業",
    "児童手当",
    "その他収入",
]

PAYMENT_METHODS = [
    "現金",
    "クレジットカード",
    "デビットカード",
    "電子マネー",
    "QRコード決済",
    "銀行振込",
]


class ExpenseClient:
    """家計簿クライアント

    JSONファイルで支出・収入を永続化します。
    """

    def __init__(self, data_dir: str = "data"):
        """初期化

        Args:
            data_dir: データ保存ディレクトリ
        """
        self.data_dir = Path(data_dir)
        self.expense_file = self.data_dir / "expenses.json"

        # データディレクトリを作成
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # レコードを読み込み
        self.records: dict[str, ExpenseRecord] = {}
        self._load_records()

        logger.info(
            "Expense client initialized",
            records_count=len(self.records),
        )

    def _load_records(self) -> None:
        """レコードをファイルから読み込み"""
        if self.expense_file.exists():
            try:
                with open(self.expense_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for record_data in data:
                        record = ExpenseRecord(**record_data)
                        self.records[record.id] = record
                logger.info(f"Loaded {len(self.records)} expense records from file")
            except Exception as e:
                logger.error(f"Failed to load expense records: {e}")
                self.records = {}

    def _save_records(self) -> None:
        """レコードをファイルに保存"""
        try:
            with open(self.expense_file, "w", encoding="utf-8") as f:
                data = [asdict(record) for record in self.records.values()]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.records)} expense records to file")
        except Exception as e:
            logger.error(f"Failed to save expense records: {e}")

    def _guess_category(self, description: str) -> str:
        """説明文からカテゴリを推測"""
        desc_lower = description.lower()

        # カテゴリ判定ルール
        food_keywords = [
            "スーパー",
            "コンビニ",
            "ランチ",
            "夕食",
            "食事",
            "レストラン",
            "カフェ",
            "弁当",
            "外食",
        ]
        daily_keywords = ["ドラッグストア", "100均", "ホームセンター", "日用品"]
        transport_keywords = ["電車", "バス", "タクシー", "ガソリン", "駐車場", "高速"]
        medical_keywords = ["病院", "薬局", "医療", "クリニック", "歯科"]
        education_keywords = ["塾", "習い事", "教材", "学校", "保育園", "幼稚園"]
        entertainment_keywords = ["映画", "遊園地", "ゲーム", "本", "漫画", "趣味"]
        clothing_keywords = ["服", "靴", "アパレル", "ユニクロ", "GU"]
        utility_keywords = ["電気", "ガス", "水道", "光熱費"]
        child_keywords = ["おむつ", "ミルク", "ベビー", "子供", "キッズ", "おもちゃ"]

        if any(kw in desc_lower for kw in food_keywords):
            return "食費"
        elif any(kw in desc_lower for kw in daily_keywords):
            return "日用品"
        elif any(kw in desc_lower for kw in transport_keywords):
            return "交通費"
        elif any(kw in desc_lower for kw in medical_keywords):
            return "医療費"
        elif any(kw in desc_lower for kw in education_keywords):
            return "教育費"
        elif any(kw in desc_lower for kw in entertainment_keywords):
            return "娯楽費"
        elif any(kw in desc_lower for kw in clothing_keywords):
            return "衣服費"
        elif any(kw in desc_lower for kw in utility_keywords):
            return "水道光熱費"
        elif any(kw in desc_lower for kw in child_keywords):
            return "子供関連"
        else:
            return "その他"

    def add_expense(
        self,
        amount: int,
        description: str = "",
        category: Optional[str] = None,
        date: Optional[str] = None,
        payment_method: str = "",
    ) -> ExpenseRecord:
        """支出を記録

        Args:
            amount: 金額
            description: 説明
            category: カテゴリ（省略時は自動判定）
            date: 日付（YYYY-MM-DD形式、省略時は今日）
            payment_method: 支払い方法

        Returns:
            追加されたExpenseRecord
        """
        record_id = str(uuid.uuid4())[:8]

        # カテゴリを自動判定
        if not category:
            category = self._guess_category(description)

        record = ExpenseRecord(
            id=record_id,
            amount=amount,
            category=category,
            description=description,
            date=date or datetime.now().strftime("%Y-%m-%d"),
            record_type="expense",
            payment_method=payment_method,
        )

        self.records[record_id] = record
        self._save_records()

        logger.info(
            "Expense recorded",
            id=record_id,
            amount=amount,
            category=category,
        )

        return record

    def add_income(
        self,
        amount: int,
        description: str = "",
        category: str = "その他収入",
        date: Optional[str] = None,
    ) -> ExpenseRecord:
        """収入を記録

        Args:
            amount: 金額
            description: 説明
            category: カテゴリ
            date: 日付（YYYY-MM-DD形式、省略時は今日）

        Returns:
            追加されたExpenseRecord
        """
        record_id = str(uuid.uuid4())[:8]

        record = ExpenseRecord(
            id=record_id,
            amount=amount,
            category=category,
            description=description,
            date=date or datetime.now().strftime("%Y-%m-%d"),
            record_type="income",
        )

        self.records[record_id] = record
        self._save_records()

        logger.info(
            "Income recorded",
            id=record_id,
            amount=amount,
            category=category,
        )

        return record

    def delete_record(self, record_id: str) -> bool:
        """レコードを削除

        Args:
            record_id: レコードID

        Returns:
            削除成功したかどうか
        """
        if record_id not in self.records:
            return False

        del self.records[record_id]
        self._save_records()

        logger.info(f"Expense record deleted: {record_id}")
        return True

    def get_records(
        self,
        record_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[ExpenseRecord]:
        """レコードを取得

        Args:
            record_type: expense or income
            category: カテゴリでフィルタ
            start_date: 開始日
            end_date: 終了日

        Returns:
            レコードリスト
        """
        records = list(self.records.values())

        # タイプでフィルタ
        if record_type:
            records = [r for r in records if r.record_type == record_type]

        # カテゴリでフィルタ
        if category:
            records = [r for r in records if r.category == category]

        # 日付でフィルタ
        if start_date:
            records = [r for r in records if r.date >= start_date]
        if end_date:
            records = [r for r in records if r.date <= end_date]

        # 日付でソート（新しい順）
        records.sort(key=lambda x: x.date, reverse=True)

        return records

    def get_monthly_summary(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> dict:
        """月次サマリーを取得

        Args:
            year: 年（省略時は今年）
            month: 月（省略時は今月）

        Returns:
            サマリー情報
        """
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        # 月の開始日と終了日
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        records = self.get_records(start_date=start_date, end_date=end_date)

        # 集計
        total_expense = 0
        total_income = 0
        expense_by_category: dict[str, int] = {}

        for record in records:
            if record.record_type == "expense":
                total_expense += record.amount
                if record.category not in expense_by_category:
                    expense_by_category[record.category] = 0
                expense_by_category[record.category] += record.amount
            else:
                total_income += record.amount

        return {
            "year": year,
            "month": month,
            "total_expense": total_expense,
            "total_income": total_income,
            "balance": total_income - total_expense,
            "expense_by_category": expense_by_category,
            "record_count": len(records),
        }

    def format_summary(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> str:
        """月次サマリーをフォーマット"""
        summary = self.get_monthly_summary(year, month)

        lines = [f"【{summary['year']}年{summary['month']}月の家計簿】"]
        lines.append("")
        lines.append(f"収入合計: ¥{summary['total_income']:,}")
        lines.append(f"支出合計: ¥{summary['total_expense']:,}")

        balance = summary["balance"]
        if balance >= 0:
            lines.append(f"収支: +¥{balance:,}")
        else:
            lines.append(f"収支: -¥{abs(balance):,}")

        if summary["expense_by_category"]:
            lines.append("")
            lines.append("【カテゴリ別支出】")
            # 金額順でソート
            sorted_cats = sorted(
                summary["expense_by_category"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for cat, amount in sorted_cats:
                lines.append(f"  - {cat}: ¥{amount:,}")

        return "\n".join(lines)

    def format_recent_records(self, limit: int = 10) -> str:
        """最近のレコードをフォーマット"""
        records = self.get_records()[:limit]

        if not records:
            return "記録がございません。"

        lines = [f"【最近の記録（{len(records)}件）】"]

        for record in records:
            type_mark = "📤" if record.record_type == "expense" else "📥"
            lines.append(
                f"{type_mark} {record.date} ¥{record.amount:,} "
                f"[{record.category}] {record.description} [{record.id}]"
            )

        return "\n".join(lines)

    def get_expense_categories(self) -> list[str]:
        """支出カテゴリ一覧を取得"""
        return EXPENSE_CATEGORIES.copy()

    def get_income_categories(self) -> list[str]:
        """収入カテゴリ一覧を取得"""
        return INCOME_CATEGORIES.copy()
