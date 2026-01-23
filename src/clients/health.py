"""健康記録クライアント

家族の健康状態、通院記録、薬の情報を管理します。
データはpersonal.gitリポジトリのYAMLファイルに保存されます。
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from ..utils.logger import get_logger

logger = get_logger(__name__)

# デフォルトのデータファイルパス
DEFAULT_HEALTH_DATA_PATH = "docs/personal/data/health.yml"


@dataclass
class HealthRecord:
    """健康記録"""

    id: str
    date: str
    person: str
    record_type: str  # symptom, hospital, medicine, checkup
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class FamilyMember:
    """家族メンバーの健康情報"""

    name: str
    allergies: list[str] = field(default_factory=list)
    chronic_conditions: list[str] = field(default_factory=list)
    regular_medicines: list[dict[str, str]] = field(default_factory=list)
    hospitals: list[dict[str, str]] = field(default_factory=list)


class HealthClient:
    """健康記録クライアント

    YAMLファイルから健康情報を読み込み、記録の追加・参照を行います。
    """

    def __init__(self, data_path: Optional[str] = None):
        """初期化

        Args:
            data_path: データファイルのパス（省略時はデフォルト）
        """
        self.data_path = Path(data_path or DEFAULT_HEALTH_DATA_PATH)
        self.family_members: dict[str, FamilyMember] = {}
        self.records: list[HealthRecord] = []
        self._load_data()

        logger.info(
            "Health client initialized",
            members_count=len(self.family_members),
            records_count=len(self.records),
            data_path=str(self.data_path),
        )

    def _load_data(self) -> None:
        """YAMLファイルからデータを読み込み"""
        if not self.data_path.exists():
            logger.warning(f"Health data file not found: {self.data_path}")
            self._create_default_file()
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # 家族メンバー情報を読み込み
            for member_data in data.get("family_members", []):
                member = FamilyMember(
                    name=member_data.get("name", ""),
                    allergies=member_data.get("allergies", []),
                    chronic_conditions=member_data.get("chronic_conditions", []),
                    regular_medicines=member_data.get("regular_medicines", []),
                    hospitals=member_data.get("hospitals", []),
                )
                self.family_members[member.name] = member

            # 健康記録を読み込み
            for record_data in data.get("records", []):
                record = HealthRecord(
                    id=record_data.get("id", ""),
                    date=record_data.get("date", ""),
                    person=record_data.get("person", ""),
                    record_type=record_data.get("type", ""),
                    description=record_data.get("description", ""),
                    details=record_data.get("details", {}),
                    notes=record_data.get("notes", ""),
                )
                self.records.append(record)

            logger.info(
                f"Loaded {len(self.family_members)} family member(s) and "
                f"{len(self.records)} record(s) from file"
            )

        except Exception as e:
            logger.error(f"Failed to load health data: {e}")

    def _create_default_file(self) -> None:
        """デフォルトのデータファイルを作成"""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        default_data = {
            "family_members": [
                {
                    "name": "旦那様",
                    "allergies": [],
                    "chronic_conditions": [],
                    "regular_medicines": [],
                    "hospitals": [],
                },
                {
                    "name": "奥様",
                    "allergies": [],
                    "chronic_conditions": [],
                    "regular_medicines": [],
                    "hospitals": [],
                },
                {
                    "name": "お嬢様",
                    "allergies": [],
                    "chronic_conditions": [],
                    "regular_medicines": [],
                    "hospitals": [],
                },
            ],
            "records": [],
        }

        with open(self.data_path, "w", encoding="utf-8") as f:
            yaml.dump(default_data, f, allow_unicode=True, default_flow_style=False)

        # 再読み込み
        self._load_data()
        logger.info(f"Created default health data file: {self.data_path}")

    def _save_data(self) -> None:
        """データをYAMLファイルに保存"""
        data = {
            "family_members": [
                {
                    "name": m.name,
                    "allergies": m.allergies,
                    "chronic_conditions": m.chronic_conditions,
                    "regular_medicines": m.regular_medicines,
                    "hospitals": m.hospitals,
                }
                for m in self.family_members.values()
            ],
            "records": [
                {
                    "id": r.id,
                    "date": r.date,
                    "person": r.person,
                    "type": r.record_type,
                    "description": r.description,
                    "details": r.details,
                    "notes": r.notes,
                }
                for r in self.records
            ],
        }

        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        logger.info("Health data saved")

    def reload(self) -> None:
        """データを再読み込み"""
        self.family_members = {}
        self.records = []
        self._load_data()

    def add_record(
        self,
        person: str,
        record_type: str,
        description: str,
        details: Optional[dict] = None,
        notes: str = "",
        date: Optional[str] = None,
    ) -> HealthRecord:
        """健康記録を追加

        Args:
            person: 対象者
            record_type: 記録タイプ（symptom, hospital, medicine, checkup）
            description: 説明
            details: 詳細情報
            notes: メモ
            date: 日付（省略時は今日）

        Returns:
            追加した記録
        """
        record_date = date or datetime.now().strftime("%Y-%m-%d")
        record_id = f"{record_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        record = HealthRecord(
            id=record_id,
            date=record_date,
            person=person,
            record_type=record_type,
            description=description,
            details=details or {},
            notes=notes,
        )
        self.records.append(record)
        self._save_data()

        logger.info(
            "Added health record",
            record_id=record_id,
            person=person,
            record_type=record_type,
        )
        return record

    def get_member_info(self, person: str) -> Optional[FamilyMember]:
        """家族メンバーの健康情報を取得

        Args:
            person: 対象者名

        Returns:
            FamilyMember または None
        """
        # 完全一致
        if person in self.family_members:
            return self.family_members[person]

        # 部分一致
        for name, member in self.family_members.items():
            if person in name or name in person:
                return member

        return None

    def get_recent_records(
        self,
        person: Optional[str] = None,
        record_type: Optional[str] = None,
        days: int = 30,
    ) -> list[HealthRecord]:
        """最近の健康記録を取得

        Args:
            person: 対象者（省略時は全員）
            record_type: 記録タイプ（省略時は全タイプ）
            days: 何日前までの記録を取得するか

        Returns:
            記録リスト
        """
        cutoff = datetime.now()
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        result = []
        for record in self.records:
            # 日付フィルタ
            if record.date < cutoff_str:
                continue

            # 対象者フィルタ
            if person and person not in record.person and record.person not in person:
                continue

            # タイプフィルタ
            if record_type and record.record_type != record_type:
                continue

            result.append(record)

        # 日付の新しい順でソート
        result.sort(key=lambda r: r.date, reverse=True)
        return result

    def format_member_info(self, member: FamilyMember) -> str:
        """家族メンバー情報をフォーマット"""
        lines = [f"【{member.name}の健康情報】"]

        # アレルギー
        if member.allergies:
            lines.append(f"アレルギー: {', '.join(member.allergies)}")
        else:
            lines.append("アレルギー: なし")

        # 持病
        if member.chronic_conditions:
            lines.append(f"持病: {', '.join(member.chronic_conditions)}")

        # 常用薬
        if member.regular_medicines:
            lines.append("\n定期服用薬:")
            for med in member.regular_medicines:
                name = med.get("name", "")
                timing = med.get("timing", "")
                lines.append(f"  - {name}" + (f" ({timing})" if timing else ""))

        # かかりつけ病院
        if member.hospitals:
            lines.append("\nかかりつけ病院:")
            for hosp in member.hospitals:
                name = hosp.get("name", "")
                dept = hosp.get("department", "")
                lines.append(f"  - {name}" + (f" ({dept})" if dept else ""))

        return "\n".join(lines)

    def format_recent_records(
        self,
        person: Optional[str] = None,
        record_type: Optional[str] = None,
        days: int = 30,
    ) -> str:
        """最近の健康記録をフォーマット"""
        records = self.get_recent_records(person, record_type, days)

        if not records:
            msg = f"過去{days}日間の健康記録はございません。"
            if person:
                msg = f"{person}の" + msg
            return msg

        type_names = {
            "symptom": "症状",
            "hospital": "通院",
            "medicine": "服薬",
            "checkup": "健診",
        }

        title = f"【過去{days}日間の健康記録】"
        if person:
            title = f"【{person}の過去{days}日間の健康記録】"

        lines = [title]

        for record in records:
            type_name = type_names.get(record.record_type, record.record_type)
            date = datetime.strptime(record.date, "%Y-%m-%d")
            date_str = date.strftime("%m/%d(%a)")

            line = f"\n■ {date_str} [{type_name}] {record.person}"
            lines.append(line)
            lines.append(f"  {record.description}")

            # 詳細情報
            if record.details:
                if record.record_type == "symptom":
                    temp = record.details.get("temperature")
                    if temp:
                        lines.append(f"  体温: {temp}℃")
                elif record.record_type == "hospital":
                    hosp = record.details.get("hospital")
                    if hosp:
                        lines.append(f"  病院: {hosp}")
                    diagnosis = record.details.get("diagnosis")
                    if diagnosis:
                        lines.append(f"  診断: {diagnosis}")

            if record.notes:
                lines.append(f"  ※{record.notes}")

        return "\n".join(lines)

    def add_symptom(
        self,
        person: str,
        symptom: str,
        temperature: Optional[float] = None,
        notes: str = "",
    ) -> HealthRecord:
        """症状を記録

        Args:
            person: 対象者
            symptom: 症状
            temperature: 体温
            notes: メモ

        Returns:
            追加した記録
        """
        details = {}
        if temperature:
            details["temperature"] = temperature

        return self.add_record(
            person=person,
            record_type="symptom",
            description=symptom,
            details=details,
            notes=notes,
        )

    def add_hospital_visit(
        self,
        person: str,
        hospital: str,
        reason: str,
        diagnosis: str = "",
        prescription: str = "",
        next_visit: str = "",
        notes: str = "",
    ) -> HealthRecord:
        """通院記録を追加

        Args:
            person: 対象者
            hospital: 病院名
            reason: 受診理由
            diagnosis: 診断結果
            prescription: 処方薬
            next_visit: 次回予約
            notes: メモ

        Returns:
            追加した記録
        """
        details = {
            "hospital": hospital,
        }
        if diagnosis:
            details["diagnosis"] = diagnosis
        if prescription:
            details["prescription"] = prescription
        if next_visit:
            details["next_visit"] = next_visit

        return self.add_record(
            person=person,
            record_type="hospital",
            description=reason,
            details=details,
            notes=notes,
        )
