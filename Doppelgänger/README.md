# Doppelgänger Voice Changer

リアルタイム声コピーAIボイスチェンジャー for Jetson Orin/Nano.

## 環境要件

- NVIDIA Jetson (JetPack 6.x, CUDA 12.x, TensorRT対応)
- Python 3.10+
- torch (Jetson wheel)
- onnxruntime-gpu
- sounddevice/PyAudio

## インストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. モデル学習

ターゲット声のWAVファイルからモデルを学習。

```bash
python voice_changer.py train --source source.wav --target target.wav --model model.pth
```

### 2. モデル最適化 (TensorRT)

学習済みモデルをONNX/TensorRTで最適化。

```bash
python voice_changer.py optimize --model model.pth --onnx model.onnx --trt model.trt
```

### 3. リアルタイム推論

マイク入力からリアルタイムで声変換。

```bash
python voice_changer.py infer --model model.pth
```

## プロジェクト構造

- `src/train.py`: モデル学習スクリプト
- `src/infer.py`: リアルタイム推論スクリプト
- `src/optimize.py`: TensorRT最適化スクリプト
- `voice_changer.py`: CLIメインスクリプト
- `requirements.txt`: 依存関係

## 注意

- 学習には十分な長さのWAVファイルが必要。
- リアルタイム処理は<100ms遅延を目指す。
- Jetson GPUで高速推論。