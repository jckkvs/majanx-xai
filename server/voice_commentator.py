import queue
import threading
import re
from typing import Optional, List
from pathlib import Path

class VoiceCommentator:
    """
    解説文を音声出力するTTSマネージャー
    - 非同期キュー処理で対戦をブロックしない
    - 日本語TTS対応（pyttsx3 / gTTS / Coqui TTS）
    - 解説の重要度に応じて発話優先度を制御
    """
    
    # 発話優先度レベル
    PRIORITY = {
        "high": 0,    # 推奨打牌・和了・放銃警告
        "medium": 1,  # 攻守判断・局面解説
        "low": 2      # 統計情報・補足説明
    }
    
    def __init__(
        self,
        engine: str = "pyttsx3",  # "pyttsx3" / "gtts" / "coqui"
        rate: int = 180,          # 発話速度（文字/分）
        volume: float = 0.8,      # 音量 0.0-1.0
        enabled: bool = True
    ):
        self.enabled = enabled
        self.rate = rate
        self.volume = volume
        self.queue = queue.PriorityQueue()
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        
        # TTSエンジン初期化
        self.tts = self._init_tts_engine(engine)
        
        # 発話履歴（重複防止）
        self.recent_phrases: List[str] = []
        self.max_history = 10
        
    def _init_tts_engine(self, engine: str):
        """TTSエンジンを初期化"""
        if engine == "pyttsx3":
            return self._init_pyttsx3()
        elif engine == "gtts":
            return self._init_gtts()
        elif engine == "coqui":
            return self._init_coqui()
        else:
            print(f"[Voice] 未知のエンジン: {engine}, pyttsx3を使用します")
            return self._init_pyttsx3()
    
    def _init_pyttsx3(self):
        """pyttsx3（オフライン・高速）を初期化"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            engine.setProperty('volume', self.volume)
            
            # 日本語音声の設定（環境依存）
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'ja' in voice.id.lower() or 'japanese' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    print(f"[Voice] 日本語音声を使用: {voice.name}")
                    break
                    
            return engine
        except ImportError:
            print("[Voice] pyttsx3がインストールされていません: pip install pyttsx3")
            return None
        except Exception as e:
            print(f"[Voice] pyttsx3初期化エラー: {e}")
            return None
    
    def _init_gtts(self):
        """gTTS（オンライン・高品質）を初期化"""
        try:
            from gtts import gTTS
            import pygame
            pygame.mixer.init()
            return {"type": "gtts", "pygame": pygame}
        except ImportError:
            print("[Voice] gTTSまたはpygameがインストールされていません")
            return None
    
    def _init_coqui(self):
        """Coqui TTS（ローカル・高品質）を初期化"""
        try:
            from TTS.api import TTS
            tts = TTS(model_name="tts_models/ja/kokoro/tacotron2-DDC", progress_bar=False)
            return {"type": "coqui", "engine": tts}
        except ImportError:
            print("[Voice] Coqui TTSがインストールされていません: pip install TTS")
            return None
    
    def start(self):
        """音声出力スレッドを開始"""
        if not self.enabled or not self.tts:
            return
            
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._process_queue, daemon=True)
        self.thread.start()
        print("[Voice] \u2705 音声出力スレッド開始")
    
    def stop(self):
        """音声出力スレッドを停止"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("[Voice] \u23F9 音声出力スレッド停止")
    
    def speak(
        self, 
        text: str, 
        priority: str = "medium",
        immediate: bool = False
    ):
        """
        解説文を音声キューに追加
        
        Args:
            text: 発話するテキスト
            priority: "high" / "medium" / "low"
            immediate: キューをスキップして即時発話するか
        """
        if not self.enabled or not self.tts:
            return
            
        # 重複発話の防止
        if self._is_duplicate(text):
            return
            
        # 重要キーワードで優先度自動調整
        if any(kw in text for kw in ["推奨", "和了", "放銃", "リーチ", "危険"]):
            priority = "high"
            
        priority_val = self.PRIORITY.get(priority, 1)
        
        if immediate:
            self._speak_now(text)
        else:
            self.queue.put((priority_val, text))
    
    def _is_duplicate(self, text: str) -> bool:
        """直近の発話と重複していないかチェック"""
        # 簡易的な重複チェック（完全一致＋部分一致）
        text_clean = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        
        for recent in self.recent_phrases:
            if text_clean in recent or recent in text_clean:
                return True
                
        # 履歴に追加
        self.recent_phrases.append(text_clean)
        if len(self.recent_phrases) > self.max_history:
            self.recent_phrases.pop(0)
            
        return False
    
    def _process_queue(self):
        """キューから順に音声出力を処理（バックグラウンドスレッド）"""
        while self.is_running:
            try:
                priority, text = self.queue.get(timeout=1.0)
                self._speak_now(text)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Voice] キュー処理エラー: {e}")
    
    def _speak_now(self, text: str):
        """即時発話実行"""
        if not self.tts:
            return
            
        try:
            # 牌の読み方を補正（例: "5s" -> "5索"）
            text = self._normalize_mahjong_text(text)
            
            if isinstance(self.tts, dict) and self.tts.get("type") == "gtts":
                self._speak_gtts(text)
            elif isinstance(self.tts, dict) and self.tts.get("type") == "coqui":
                self._speak_coqui(text)
            else:
                self._speak_pyttsx3(text)
                
        except Exception as e:
            print(f"[Voice] 発話エラー: {e}")
    
    def _normalize_mahjong_text(self, text: str) -> str:
        """麻雀用語の読み方を補正"""
        replacements = {
            '1m': '1萬', '2m': '2萬', '3m': '3萬', '4m': '4萬', '5m': '5萬',
            '6m': '6萬', '7m': '7萬', '8m': '8萬', '9m': '9萬',
            '1p': '1筒', '2p': '2筒', '3p': '3筒', '4p': '4筒', '5p': '5筒',
            '6p': '6筒', '7p': '7筒', '8p': '8筒', '9p': '9筒',
            '1s': '1索', '2s': '2索', '3s': '3索', '4s': '4索', '5s': '5索',
            '6s': '6索', '7s': '7索', '8s': '8索', '9s': '9索',
            '1z': '東', '2z': '南', '3z': '西', '4z': '北',
            '5z': '白', '6z': '發', '7z': '中',
            'リーチ': '立直', 'チー': '吃', 'ポン': '碰', 'カン': '槓',
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text
    
    def _speak_pyttsx3(self, text: str):
        """pyttsx3で発話"""
        self.tts.say(text)
        self.tts.runAndWait()
    
    def _speak_gtts(self, text: str):
        """gTTSで発話（一時ファイル経由）"""
        from gtts import gTTS
        import tempfile
        import os
        
        tts = gTTS(text=text, lang='ja')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            temp_path = f.name
        tts.save(temp_path)
        
        # pygameで再生
        self.tts["pygame"].mixer.music.load(temp_path)
        self.tts["pygame"].mixer.music.play()
        while self.tts["pygame"].mixer.music.get_busy():
            self.tts["pygame"].time.Clock().tick(10)
            
        os.unlink(temp_path)
    
    def _speak_coqui(self, text: str):
        """Coqui TTSで発話"""
        tts_engine = self.tts["engine"]
        output = tts_engine.tts(text=text)
        import sounddevice as sd
        import numpy as np
        sd.play(np.array(output), samplerate=22050)
        sd.wait()
    
    def update_settings(self, **kwargs):
        """設定を動的に更新"""
        if 'enabled' in kwargs:
            self.enabled = kwargs['enabled']
            if self.enabled and not self.is_running:
                self.start()
            elif not self.enabled:
                self.stop()
        if 'rate' in kwargs and hasattr(self.tts, 'setProperty'):
            self.tts.setProperty('rate', kwargs['rate'])
        if 'volume' in kwargs and hasattr(self.tts, 'setProperty'):
            self.tts.setProperty('volume', kwargs['volume'])
