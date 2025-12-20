#!/usr/bin/env python3
import argparse
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from train import train_model
from infer import realtime_voice_change
from optimize import export_to_onnx, optimize_with_tensorrt

def main():
    parser = argparse.ArgumentParser(description="Doppelgänger Voice Changer")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Train command
    train_parser = subparsers.add_parser('train', help='Train voice conversion model')
    train_parser.add_argument('--source', required=True, help='Source voice WAV file')
    train_parser.add_argument('--target', required=True, help='Target voice WAV file')
    train_parser.add_argument('--model', required=True, help='Output model path (.pth)')

    # Infer command
    infer_parser = subparsers.add_parser('infer', help='Run real-time voice conversion')
    infer_parser.add_argument('--model', required=True, help='Model path (.pth)')

    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize model with TensorRT')
    optimize_parser.add_argument('--model', required=True, help='PyTorch model path (.pth)')
    optimize_parser.add_argument('--onnx', required=True, help='ONNX output path')
    optimize_parser.add_argument('--trt', required=True, help='TensorRT output path')

    args = parser.parse_args()

    if args.command == 'train':
        train_model(args.source, args.target, args.model)
    elif args.command == 'infer':
        realtime_voice_change(args.model)
    elif args.command == 'optimize':
        export_to_onnx(args.model, args.onnx)
        optimize_with_tensorrt(args.onnx, args.trt)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()