import torch
import torch.nn as nn
import librosa
import numpy as np
from torch.utils.data import Dataset, DataLoader
import os

class VoiceDataset(Dataset):
    def __init__(self, source_wav, target_wav, segment_length=16000):  # 1秒@16kHz
        self.source_audio = librosa.load(source_wav, sr=16000)[0]
        self.target_audio = librosa.load(target_wav, sr=16000)[0]
        self.segment_length = segment_length
        self.num_segments = min(len(self.source_audio), len(self.target_audio)) // segment_length

    def __len__(self):
        return self.num_segments

    def __getitem__(self, idx):
        start = idx * self.segment_length
        end = start + self.segment_length
        source_seg = self.source_audio[start:end]
        target_seg = self.target_audio[start:end]

        # MFCC特徴抽出
        source_mfcc = librosa.feature.mfcc(y=source_seg, sr=16000, n_mfcc=40)
        target_mfcc = librosa.feature.mfcc(y=target_seg, sr=16000, n_mfcc=40)

        return torch.tensor(source_mfcc, dtype=torch.float32), torch.tensor(target_mfcc, dtype=torch.float32)

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

def train_model(source_wav, target_wav, model_path, epochs=100, batch_size=32):
    dataset = VoiceDataset(source_wav, target_wav)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = VoiceConverter()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for source_batch, target_batch in dataloader:
            optimizer.zero_grad()
            output = model(source_batch.view(batch_size, -1, 40))  # Adjust shape
            loss = criterion(output, target_batch.view(batch_size, -1, 40))
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss / len(dataloader)}")

    torch.save(model.state_dict(), model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source voice WAV file")
    parser.add_argument("--target", required=True, help="Target voice WAV file")
    parser.add_argument("--model", required=True, help="Output model path")
    args = parser.parse_args()

    train_model(args.source, args.target, args.model)