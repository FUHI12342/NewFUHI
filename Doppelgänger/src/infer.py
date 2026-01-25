import torch
import torch.nn as nn
import librosa
import numpy as np
import sounddevice as sd
import queue
import threading
import time

class VoiceConverter(nn.Module):
    def __init__(self, input_dim=40, hidden_dim=128, output_dim=40):
        super(VoiceConverter, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

def load_model(model_path):
    model = VoiceConverter()
    model.load_state_dict(torch.load(model_path))
    model.eval()
    return model

def audio_callback(indata, outdata, frames, time, status, q, model):
    # 入力オーディオを処理
    audio = indata[:, 0]  # モノラル
    mfcc = librosa.feature.mfcc(y=audio, sr=16000, n_mfcc=40)
    mfcc_tensor = torch.tensor(mfcc, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        converted_mfcc = model(mfcc_tensor)

    # MFCCをオーディオに逆変換（簡易）
    converted_audio = librosa.feature.inverse.mfcc_to_audio(converted_mfcc.squeeze(0).numpy(), sr=16000)

    # 出力バッファに合わせる
    outdata[:, 0] = converted_audio[:frames]

def realtime_voice_change(model_path):
    model = load_model(model_path)

    q = queue.Queue()

    with sd.Stream(callback=lambda indata, outdata, frames, time, status: audio_callback(indata, outdata, frames, time, status, q, model),
                   samplerate=16000, channels=1, blocksize=1024):
        print("Voice changer running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("Stopped.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Model path")
    args = parser.parse_args()

    realtime_voice_change(args.model)