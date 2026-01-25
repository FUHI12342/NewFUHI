import torch
import torch.onnx
import tensorrt as trt
import onnxruntime as ort
import numpy as np

class VoiceConverter(torch.nn.Module):
    def __init__(self, input_dim=40, hidden_dim=128, output_dim=40):
        super(VoiceConverter, self).__init__()
        self.encoder = torch.nn.Sequential(
            torch.nn.Linear(input_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU()
        )
        self.decoder = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

def export_to_onnx(model_path, onnx_path):
    model = VoiceConverter()
    model.load_state_dict(torch.load(model_path))
    model.eval()

    dummy_input = torch.randn(1, 40, 40)  # Batch, Time, MFCC

    torch.onnx.export(model, dummy_input, onnx_path, input_names=['input'], output_names=['output'],
                      dynamic_axes={'input': {0: 'batch_size', 1: 'time'}, 'output': {0: 'batch_size', 1: 'time'}})
    print(f"ONNX model exported to {onnx_path}")

def optimize_with_tensorrt(onnx_path, trt_path):
    TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, TRT_LOGGER)

    with open(onnx_path, 'rb') as model:
        if not parser.parse(model.read()):
            print('ERROR: Failed to parse the ONNX file.')
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            return

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30)  # 1GB

    serialized_engine = builder.build_serialized_network(network, config)
    with open(trt_path, 'wb') as f:
        f.write(serialized_engine)
    print(f"TensorRT engine saved to {trt_path}")

def load_trt_engine(trt_path):
    TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
    with open(trt_path, 'rb') as f, trt.Runtime(TRT_LOGGER) as runtime:
        engine = runtime.deserialize_cuda_engine(f.read())
    return engine

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="PyTorch model path")
    parser.add_argument("--onnx", required=True, help="ONNX output path")
    parser.add_argument("--trt", required=True, help="TensorRT output path")
    args = parser.parse_args()

    export_to_onnx(args.model, args.onnx)
    optimize_with_tensorrt(args.onnx, args.trt)