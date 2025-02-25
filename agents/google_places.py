import os
import json
import logging
from typing import Dict, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

class GooglePlacesClient:
    """Google Places APIを使用して場所の緯度経度を取得するクライアント"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        if not self.api_key or not self.search_engine_id:
            raise ValueError("GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID are required")
        
        self.default_location = {
            "name": "木津川市",
            "latitude": 34.712,
            "longitude": 135.844
        }
    
    def search_location(self, query: str) -> Dict[str, float]:
        """場所の検索を行い、緯度経度を返す"""
        try:
            # Google Custom Search APIを使用して場所を検索
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': f"{query} 緯度 経度",
                'num': 1
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            results = response.json()
            
            if 'items' not in results:
                logger.warning(f"No results found for query: {query}")
                return self.default_location
            
            # 検索結果から緯度経度を抽出
            snippet = results['items'][0].get('snippet', '')
            coordinates = self._extract_coordinates(snippet)
            
            if coordinates:
                return {
                    "name": query,
                    "latitude": coordinates[0],
                    "longitude": coordinates[1]
                }
            else:
                logger.warning(f"Could not extract coordinates from: {snippet}")
                return self.default_location
            
        except Exception as e:
            logger.error(f"Error searching location: {str(e)}", exc_info=True)
            return self.default_location
    
    def _extract_coordinates(self, text: str) -> Optional[Tuple[float, float]]:
        """テキストから緯度経度を抽出"""
        try:
            # テキストから緯度経度っぽい数値のペアを探す
            import re
            pattern = r'(\d+\.\d+)[^\d]+(\d+\.\d+)'
            matches = re.findall(pattern, text)
            
            if matches:
                lat, lon = matches[0]
                return float(lat), float(lon)
            return None
            
        except Exception as e:
            logger.error(f"Error extracting coordinates: {str(e)}", exc_info=True)
            return None