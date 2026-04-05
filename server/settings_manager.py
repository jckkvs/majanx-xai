import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """アプリケーション設定スキーマ"""
    
    # AI設定
    ai_model_path: str = Field(default="server/mortal/weights/mortal.pth", description="Mortal重みファイルパス")
    use_mortal: bool = Field(default=True, description="Mortal AIを使用する")
    use_gpu: bool = Field(default=True, description="GPU推論を使用")
    
    # 解説設定
    explanation_detail: str = Field(default="medium", description="解説詳細度: simple/medium/detailed")
    show_top3: bool = Field(default=True, description="上位3候補を表示")
    show_metrics: bool = Field(default=True, description="攻守メーターを表示")
    
    # 音声設定
    voice_enabled: bool = Field(default=False, description="音声解説を有効化")
    voice_engine: str = Field(default="pyttsx3", description="TTSエンジン: pyttsx3/gtts/coqui")
    voice_rate: int = Field(default=180, ge=100, le=300, description="発話速度")
    voice_volume: float = Field(default=0.8, ge=0.0, le=1.0, description="音量")
    
    # 表示設定
    theme: str = Field(default="dark", description="テーマ: dark/light")
    tile_design: str = Field(default="traditional", description="牌デザイン: traditional/modern/minimal")
    show_red_dora: bool = Field(default=True, description="赤ドラを強調表示")
    
    # 外部連携設定
    screen_capture_enabled: bool = Field(default=False, description="画面認識を有効化")
    capture_roi: Dict[str, int] = Field(default_factory=lambda: {"top": 0, "left": 0, "width": 1920, "height": 1080})
    capture_fps: int = Field(default=12, ge=5, le=30, description="キャプチャFPS")
    
    # 牌譜設定
    auto_save_replay: bool = Field(default=True, description="対局を自動保存")
    replay_save_path: str = Field(default="replays/", description="牌譜保存先")
    
    class Config:
        json_schema_extra = {
            "example": {
                "use_mortal": True,
                "voice_enabled": False,
                "theme": "dark"
            }
        }

class SettingsManager:
    """設定の永続化と管理"""
    
    SETTINGS_FILE = Path("config/settings.json")
    
    def __init__(self):
        self.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()
    
    def _load(self) -> Settings:
        """設定ファイルからロード"""
        if self.SETTINGS_FILE.exists():
            try:
                with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return Settings(**data)
            except Exception as e:
                print(f"[Settings] 読み込みエラー: {e}, デフォルトを使用")
        return Settings()
    
    def save(self):
        """設定をファイルに保存"""
        with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings.model_dump(), f, ensure_ascii=False, indent=2)
    
    def get(self) -> Dict[str, Any]:
        """設定を辞書で取得"""
        return self.settings.model_dump()
    
    def update(self, **kwargs):
        """設定を更新・保存"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()
    
    def get_ai_config(self) -> Dict:
        """AI関連設定のみ取得"""
        return {
            "weight_path": self.settings.ai_model_path,
            "use_gpu": self.settings.use_gpu
        }
    
    def get_voice_config(self) -> Dict:
        """音声関連設定のみ取得"""
        return {
            "enabled": self.settings.voice_enabled,
            "engine": self.settings.voice_engine,
            "rate": self.settings.voice_rate,
            "volume": self.settings.voice_volume
        }
    
    def get_display_config(self) -> Dict:
        """表示関連設定のみ取得"""
        return {
            "theme": self.settings.theme,
            "tile_design": self.settings.tile_design,
            "show_red_dora": self.settings.show_red_dora
        }
