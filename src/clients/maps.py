"""Google Maps APIクライアント（ルート検索・移動時間取得）"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

import aiohttp

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TravelMode(Enum):
    """移動手段"""

    DRIVING = "driving"  # 車
    WALKING = "walking"  # 徒歩
    BICYCLING = "bicycling"  # 自転車
    TRANSIT = "transit"  # 公共交通機関


@dataclass
class TravelInfo:
    """移動情報"""

    origin: str
    destination: str
    mode: TravelMode
    duration_seconds: int
    duration_text: str
    distance_meters: int
    distance_text: str
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    summary: Optional[str] = None  # 主要ルート（例: 国道24号線経由）

    @property
    def duration_minutes(self) -> int:
        """移動時間（分）"""
        return self.duration_seconds // 60

    def format_for_description(self) -> str:
        """カレンダー説明用にフォーマット"""
        lines = [
            f"【移動情報】",
            f"出発地: {self.origin}",
            f"移動時間: {self.duration_text}（{self.mode_japanese}）",
            f"距離: {self.distance_text}",
        ]
        if self.summary:
            lines.append(f"ルート: {self.summary}")
        return "\n".join(lines)

    @property
    def mode_japanese(self) -> str:
        """移動手段の日本語表記"""
        mode_map = {
            TravelMode.DRIVING: "車",
            TravelMode.WALKING: "徒歩",
            TravelMode.BICYCLING: "自転車",
            TravelMode.TRANSIT: "公共交通機関",
        }
        return mode_map.get(self.mode, "車")


class GoogleMapsClient:
    """Google Maps APIクライアント"""

    DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

    def __init__(
        self,
        api_key: str,
        home_address: str,
        timezone: str = "Asia/Tokyo",
    ):
        """初期化

        Args:
            api_key: Google Maps APIキー
            home_address: 自宅住所（デフォルトの出発地）
            timezone: タイムゾーン
        """
        self.api_key = api_key
        self.home_address = home_address
        self.timezone = timezone
        logger.info(
            "Google Maps client initialized",
            home_address=home_address[:20] + "...",
        )

    async def get_travel_info(
        self,
        destination: str,
        origin: Optional[str] = None,
        mode: TravelMode = TravelMode.DRIVING,
        departure_time: Optional[datetime] = None,
    ) -> Optional[TravelInfo]:
        """移動情報を取得

        Args:
            destination: 目的地（住所または場所名）
            origin: 出発地（省略時は自宅）
            mode: 移動手段
            departure_time: 出発時刻（省略時は現在時刻）

        Returns:
            TravelInfo: 移動情報、取得失敗時はNone
        """
        origin = origin or self.home_address

        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode.value,
            "language": "ja",
            "key": self.api_key,
        }

        # 公共交通機関の場合は出発時刻を指定
        if mode == TravelMode.TRANSIT and departure_time:
            params["departure_time"] = int(departure_time.timestamp())

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.DIRECTIONS_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(
                            "Google Maps API error",
                            status=response.status,
                            destination=destination,
                        )
                        return None

                    data = await response.json()

            if data.get("status") != "OK":
                logger.warning(
                    "Google Maps API returned non-OK status",
                    status=data.get("status"),
                    error_message=data.get("error_message"),
                    destination=destination,
                )
                return None

            # 最初のルートを取得
            route = data["routes"][0]
            leg = route["legs"][0]

            travel_info = TravelInfo(
                origin=leg["start_address"],
                destination=leg["end_address"],
                mode=mode,
                duration_seconds=leg["duration"]["value"],
                duration_text=leg["duration"]["text"],
                distance_meters=leg["distance"]["value"],
                distance_text=leg["distance"]["text"],
                summary=route.get("summary"),
            )

            logger.info(
                "Travel info retrieved",
                destination=destination[:30],
                duration=travel_info.duration_text,
                distance=travel_info.distance_text,
            )

            return travel_info

        except aiohttp.ClientError as e:
            logger.error(
                "Network error while fetching travel info",
                error=str(e),
                destination=destination,
            )
            return None
        except (KeyError, IndexError) as e:
            logger.error(
                "Failed to parse Google Maps response",
                error=str(e),
                destination=destination,
            )
            return None

    async def get_travel_time_text(
        self,
        destination: str,
        origin: Optional[str] = None,
        mode: TravelMode = TravelMode.DRIVING,
    ) -> str:
        """移動時間のテキストを取得（簡易版）

        Args:
            destination: 目的地
            origin: 出発地（省略時は自宅）
            mode: 移動手段

        Returns:
            str: 移動時間テキスト（例: "車で約25分"）、取得失敗時はエラーメッセージ
        """
        travel_info = await self.get_travel_info(
            destination=destination,
            origin=origin,
            mode=mode,
        )

        if travel_info:
            return f"{travel_info.mode_japanese}で{travel_info.duration_text}（{travel_info.distance_text}）"
        else:
            return "移動時間を取得できませんでした"

    async def get_multi_mode_travel_info(
        self,
        destination: str,
        origin: Optional[str] = None,
    ) -> dict[TravelMode, Optional[TravelInfo]]:
        """複数の移動手段での移動情報を取得

        Args:
            destination: 目的地
            origin: 出発地（省略時は自宅）

        Returns:
            dict: 移動手段ごとの移動情報
        """
        results = {}
        for mode in [TravelMode.DRIVING, TravelMode.TRANSIT]:
            results[mode] = await self.get_travel_info(
                destination=destination,
                origin=origin,
                mode=mode,
            )
        return results

    def format_travel_summary(
        self,
        travel_info: dict[TravelMode, Optional[TravelInfo]],
    ) -> str:
        """複数移動手段の要約をフォーマット

        Args:
            travel_info: 移動手段ごとの移動情報

        Returns:
            str: フォーマットされた要約
        """
        lines = ["【自宅からの移動時間】"]

        driving = travel_info.get(TravelMode.DRIVING)
        if driving:
            lines.append(f"🚗 車: {driving.duration_text}（{driving.distance_text}）")

        transit = travel_info.get(TravelMode.TRANSIT)
        if transit:
            lines.append(f"🚃 公共交通機関: {transit.duration_text}")

        if len(lines) == 1:
            lines.append("移動情報を取得できませんでした")

        return "\n".join(lines)
