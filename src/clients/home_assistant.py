"""Home Assistant クライアント

Home Assistant REST APIを使用してスマートホームデバイスを制御します。
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..utils.logger import get_logger

logger = get_logger(__name__)


# デバイス定義
LIGHTS = {
    "書斎": "light.shu_zhai",
    "リビング": "light.rihinku",
    "寝室": "light.qin_shi",
    "子供部屋": "light.zi_gong_bu_wu",
    "廊下": "light.lang_xia",
}

CLIMATE = {
    "書斎": "climate.shu_zhai_noeakon_shu_zhai",
    "リビング": "climate.rihinkunoeakon_rihinku",
    "寝室": "climate.qin_shi_noeakon_remo",
    "子供部屋": "climate.zi_gong_bu_wu_noeakon_lang_xia",
}

SENSORS = {
    "書斎_温度": "sensor.temperature_sensor_shu_zhai",
    "リビング_温度": "sensor.temperature_sensor_rihinku",
    "寝室_温度": "sensor.temperature_sensor_remo",
    "子供部屋_温度": "sensor.temperature_sensor_lang_xia",
    "書斎_湿度": "sensor.humidity_sensor_shu_zhai",
    "リビング_湿度": "sensor.humidity_sensor_rihinku",
    "寝室_湿度": "sensor.humidity_sensor_remo",
    "子供部屋_湿度": "sensor.humidity_sensor_lang_xia",
}

SPEAKERS = {
    "書斎": "media_player.shu_zhai_nohea",
    "リビング": "media_player.shu_zhai_hetuto_hou_you",
    "子供部屋": "media_player.kodomo_heya",
}

CIRCULATORS = {
    "書斎": "button.send_signal_shu_zhai_nosakiyureta",
    "リビング": "button.send_signal_rihinkunosakiyureta",
    "寝室": "button.send_signal_qin_shi_nosakiyureta",
    "子供部屋": "button.send_signal_sakiyureta",
}


@dataclass
class SensorReading:
    """センサー読み取り値"""

    room: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None


@dataclass
class DeviceState:
    """デバイス状態"""

    entity_id: str
    state: str
    attributes: dict[str, Any]


class HomeAssistantClient:
    """Home Assistant REST API クライアント"""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """初期化

        Args:
            url: Home Assistant URL (例: http://192.168.68.79:8123)
            token: Long-lived access token
        """
        self.url = url or os.environ.get("HOME_ASSISTANT_URL", "http://192.168.68.79:8123")
        self.token = token or os.environ.get("HOME_ASSISTANT_TOKEN", "")

        if not self.token:
            logger.warning("Home Assistant token not configured")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Home Assistant client initialized",
            url=self.url,
            has_token=bool(self.token),
        )

    async def _call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: Optional[dict] = None,
    ) -> bool:
        """サービスを呼び出し

        Args:
            domain: ドメイン (light, climate, etc.)
            service: サービス名 (turn_on, turn_off, etc.)
            entity_id: エンティティID
            data: 追加データ

        Returns:
            成功したかどうか
        """
        if not self.token:
            logger.error("Home Assistant token not configured")
            return False

        url = f"{self.url}/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id}
        if data:
            payload.update(data)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(
                        f"Service called: {domain}.{service}",
                        entity_id=entity_id,
                    )
                    return True
                else:
                    logger.error(
                        f"Service call failed: {response.status_code}",
                        response=response.text,
                    )
                    return False

        except Exception as e:
            logger.error(f"Failed to call service: {e}")
            return False

    async def _get_state(self, entity_id: str) -> Optional[DeviceState]:
        """エンティティの状態を取得

        Args:
            entity_id: エンティティID

        Returns:
            DeviceState または None
        """
        if not self.token:
            logger.error("Home Assistant token not configured")
            return None

        url = f"{self.url}/api/states/{entity_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return DeviceState(
                        entity_id=data["entity_id"],
                        state=data["state"],
                        attributes=data.get("attributes", {}),
                    )
                else:
                    logger.error(f"Failed to get state: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return None

    # ========== 照明制御 ==========

    async def light_on(self, room: str) -> bool:
        """照明をONにする

        Args:
            room: 部屋名 (書斎, リビング, 寝室, 子供部屋, 廊下)

        Returns:
            成功したかどうか
        """
        entity_id = LIGHTS.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        return await self._call_service("light", "turn_on", entity_id)

    async def light_off(self, room: str) -> bool:
        """照明をOFFにする

        Args:
            room: 部屋名

        Returns:
            成功したかどうか
        """
        entity_id = LIGHTS.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        return await self._call_service("light", "turn_off", entity_id)

    async def get_light_state(self, room: str) -> Optional[str]:
        """照明の状態を取得

        Args:
            room: 部屋名

        Returns:
            "on" or "off" or None
        """
        entity_id = LIGHTS.get(room)
        if not entity_id:
            return None

        state = await self._get_state(entity_id)
        return state.state if state else None

    # ========== エアコン制御 ==========

    async def climate_on(
        self,
        room: str,
        temperature: Optional[int] = None,
        mode: str = "cool",
    ) -> bool:
        """エアコンをONにする

        Args:
            room: 部屋名
            temperature: 設定温度
            mode: モード (cool, heat, dry, fan_only)

        Returns:
            成功したかどうか
        """
        entity_id = CLIMATE.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        data = {"hvac_mode": mode}
        if temperature:
            data["temperature"] = temperature

        return await self._call_service("climate", "set_hvac_mode", entity_id, data)

    async def climate_off(self, room: str) -> bool:
        """エアコンをOFFにする

        Args:
            room: 部屋名

        Returns:
            成功したかどうか
        """
        entity_id = CLIMATE.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        return await self._call_service(
            "climate", "set_hvac_mode", entity_id, {"hvac_mode": "off"}
        )

    async def set_temperature(self, room: str, temperature: int) -> bool:
        """エアコンの温度を設定

        Args:
            room: 部屋名
            temperature: 設定温度

        Returns:
            成功したかどうか
        """
        entity_id = CLIMATE.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        return await self._call_service(
            "climate", "set_temperature", entity_id, {"temperature": temperature}
        )

    async def get_climate_state(self, room: str) -> Optional[dict]:
        """エアコンの状態を取得

        Args:
            room: 部屋名

        Returns:
            状態情報のdict または None
        """
        entity_id = CLIMATE.get(room)
        if not entity_id:
            return None

        state = await self._get_state(entity_id)
        if not state:
            return None

        return {
            "state": state.state,
            "temperature": state.attributes.get("temperature"),
            "current_temperature": state.attributes.get("current_temperature"),
            "hvac_mode": state.attributes.get("hvac_mode"),
        }

    # ========== センサー ==========

    async def get_room_sensors(self, room: str) -> Optional[SensorReading]:
        """部屋のセンサー値を取得

        Args:
            room: 部屋名

        Returns:
            SensorReading または None
        """
        temp_key = f"{room}_温度"
        humid_key = f"{room}_湿度"

        temp_entity = SENSORS.get(temp_key)
        humid_entity = SENSORS.get(humid_key)

        temperature = None
        humidity = None

        if temp_entity:
            state = await self._get_state(temp_entity)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    temperature = float(state.state)
                except ValueError:
                    pass

        if humid_entity:
            state = await self._get_state(humid_entity)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    humidity = float(state.state)
                except ValueError:
                    pass

        return SensorReading(room=room, temperature=temperature, humidity=humidity)

    async def get_all_sensors(self) -> list[SensorReading]:
        """全部屋のセンサー値を取得

        Returns:
            SensorReadingのリスト
        """
        rooms = ["書斎", "リビング", "寝室", "子供部屋"]
        readings = []

        for room in rooms:
            reading = await self.get_room_sensors(room)
            if reading:
                readings.append(reading)

        return readings

    # ========== TTS音声通知 ==========

    async def speak(self, message: str, room: str = "リビング") -> bool:
        """TTS音声通知を送信

        Args:
            message: メッセージ
            room: 部屋名 (書斎, リビング, 子供部屋)

        Returns:
            成功したかどうか
        """
        speaker = SPEAKERS.get(room, SPEAKERS["リビング"])

        if not self.token:
            logger.error("Home Assistant token not configured")
            return False

        url = f"{self.url}/api/services/tts/speak"
        payload = {
            "entity_id": "tts.google_translate_en_com",
            "media_player_entity_id": speaker,
            "message": message,
            "language": "ja",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(f"TTS sent to {room}: {message[:50]}...")
                    return True
                else:
                    logger.error(f"TTS failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send TTS: {e}")
            return False

    # ========== サーキュレーター ==========

    async def toggle_circulator(self, room: str) -> bool:
        """サーキュレーターをトグル

        Args:
            room: 部屋名

        Returns:
            成功したかどうか
        """
        entity_id = CIRCULATORS.get(room)
        if not entity_id:
            logger.error(f"Unknown room: {room}")
            return False

        return await self._call_service("button", "press", entity_id)

    # ========== ユーティリティ ==========

    def get_available_rooms(self) -> dict[str, list[str]]:
        """利用可能な部屋一覧を取得"""
        return {
            "照明": list(LIGHTS.keys()),
            "エアコン": list(CLIMATE.keys()),
            "センサー": ["書斎", "リビング", "寝室", "子供部屋"],
            "スピーカー": list(SPEAKERS.keys()),
            "サーキュレーター": list(CIRCULATORS.keys()),
        }

    def format_sensor_readings(self, readings: list[SensorReading]) -> str:
        """センサー読み取り値をフォーマット"""
        if not readings:
            return "センサー情報を取得できませんでした。"

        lines = ["【室内環境】"]
        for r in readings:
            temp_str = f"{r.temperature:.1f}°C" if r.temperature is not None else "---"
            humid_str = f"{r.humidity:.0f}%" if r.humidity is not None else "---"
            lines.append(f"- {r.room}: {temp_str} / {humid_str}")

        return "\n".join(lines)
