#!/usr/bin/env python3
"""
AgriSense - Post-Training INT8 Quantization and TFLite Export
Performs representative dataset calibration, builds a valid TFLite FlatBuffer model
with INT8 tensor quantization, outputs model_quant_int8.tflite (~70 KB),
training_metadata.json, and exports C byte array (model_data.h).
"""

import argparse
import json
import os
import struct
from pathlib import Path
from typing import Dict, List, Tuple

import flatbuffers
import numpy as np
import torch
import torch.nn as nn
from PIL import Image

import ai_edge_litert.schema_py_generated as schema
from train import AgriSenseTomatoCNN


def get_quant_params(min_val: float, max_val: float, narrow_range: bool = False) -> Tuple[float, int]:
    """Calculate scale and zero_point for INT8 quantization [-128, 127]."""
    if min_val > 0.0:
        min_val = 0.0
    if max_val < 0.0:
        max_val = 0.0
    if max_val == min_val:
        return 1.0, 0

    qmin = -128
    qmax = 127
    scale = (max_val - min_val) / float(qmax - qmin)
    zero_point = int(round(qmin - min_val / scale))
    zero_point = max(qmin, min(qmax, zero_point))
    return float(scale), int(zero_point)


def quantize_tensor_int8(tensor: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    q = np.round(tensor / scale) + zero_point
    return np.clip(q, -128, 127).astype(np.int8)


def quantize_weights_per_tensor(weights: np.ndarray) -> Tuple[np.ndarray, float, int]:
    """Symmetric INT8 weight quantization [-127, 127]."""
    max_val = float(np.max(np.abs(weights)))
    scale = max_val / 127.0 if max_val > 1e-7 else 1.0
    zero_point = 0
    q = np.round(weights / scale)
    q = np.clip(q, -127, 127).astype(np.int8)
    return q, float(scale), zero_point


def quantize_bias(bias: np.ndarray, in_scale: float, weight_scale: float) -> np.ndarray:
    """Quantize bias to INT32 with scale = in_scale * weight_scale."""
    b_scale = in_scale * weight_scale
    if b_scale == 0.0:
        b_scale = 1.0
    q = np.round(bias / b_scale)
    return np.clip(q, -2147483648, 2147483647).astype(np.int32)


def run_representative_calibration(
    model: nn.Module, dataset_dir: Path, num_samples: int = 32
) -> Dict[str, Tuple[float, float]]:
    """Calibrate activation dynamic ranges across representative leaf samples."""
    print(f"[AgriSense Quant] Calibrating activation ranges across {num_samples} samples...")
    model.eval()

    ranges = {
        "input": [0.0, 1.0],
        "conv1": [0.0, 0.0],
        "pool1": [0.0, 0.0],
        "conv2": [0.0, 0.0],
        "pool2": [0.0, 0.0],
        "conv3": [0.0, 0.0],
        "pool3": [0.0, 0.0],
        "conv4": [0.0, 0.0],
        "pool4": [0.0, 0.0],
        "gap": [0.0, 0.0],
        "fc": [0.0, 0.0],
        "softmax": [0.0, 1.0],
    }

    # Hooks to record min/max activations
    def update_range(name: str, tensor: torch.Tensor):
        c_min = float(tensor.min().item())
        c_max = float(tensor.max().item())
        ranges[name][0] = min(ranges[name][0], c_min)
        ranges[name][1] = max(ranges[name][1], c_max)

    val_imgs = list((dataset_dir / "val").glob("*/*.jpg"))
    if not val_imgs:
        val_imgs = list((dataset_dir / "train").glob("*/*.jpg"))

    samples = val_imgs[:num_samples] if len(val_imgs) >= num_samples else val_imgs

    with torch.no_grad():
        for p in samples:
            img = Image.open(p).convert("RGB").resize((96, 96))
            arr = np.array(img, dtype=np.float32) / 255.0
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)  # [1, 3, 96, 96]
            update_range("input", t)

            c1 = model.block1[0](t)
            r1 = model.block1[1](c1)
            p1 = model.block1[2](r1)
            update_range("conv1", r1)
            update_range("pool1", p1)

            c2 = model.block2[0](p1)
            r2 = model.block2[1](c2)
            p2 = model.block2[2](r2)
            update_range("conv2", r2)
            update_range("pool2", p2)

            c3 = model.block3[0](p2)
            r3 = model.block3[1](c3)
            p3 = model.block3[2](r3)
            update_range("conv3", r3)
            update_range("pool3", p3)

            c4 = model.block4[0](p3)
            r4 = model.block4[1](c4)
            p4 = model.block4[2](r4)
            update_range("conv4", r4)
            update_range("pool4", p4)

            gap = model.gap(p4)
            flat = torch.flatten(gap, 1)
            update_range("gap", flat)

            fc = model.classifier(flat)
            update_range("fc", fc)

    # Ensure nonzero span
    for k in ranges:
        if ranges[k][1] <= ranges[k][0]:
            ranges[k][1] = ranges[k][0] + 1.0

    return {k: (ranges[k][0], ranges[k][1]) for k in ranges}


def build_tflite_model(
    model: nn.Module,
    calib_ranges: Dict[str, Tuple[float, float]],
    classes: List[str],
) -> Tuple[bytes, Dict]:
    """Construct a full INT8 TFLite model FlatBuffer adhering to schema v3."""
    builder = flatbuffers.Builder(1024 * 128)

    # Extract weights from PyTorch model
    state = model.state_dict()
    # Conv weights: PyTorch [out, in, H, W] -> TFLite [out, H, W, in]
    w1 = state["block1.0.weight"].numpy().transpose(0, 2, 3, 1)
    b1 = state["block1.0.bias"].numpy()

    w2 = state["block2.0.weight"].numpy().transpose(0, 2, 3, 1)
    b2 = state["block2.0.bias"].numpy()

    w3 = state["block3.0.weight"].numpy().transpose(0, 2, 3, 1)
    b3 = state["block3.0.bias"].numpy()

    w4 = state["block4.0.weight"].numpy().transpose(0, 2, 3, 1)
    b4 = state["block4.0.bias"].numpy()

    # FC weights: PyTorch [out, in] -> TFLite [out, in]
    w_fc = state["classifier.weight"].numpy()
    b_fc = state["classifier.bias"].numpy()

    # Calculate quantization parameters for activations
    act_quant = {}
    for name, (rmin, rmax) in calib_ranges.items():
        scale, zp = get_quant_params(rmin, rmax)
        act_quant[name] = (scale, zp)

    # Quantize weights and biases
    q_w1, s_w1, z_w1 = quantize_weights_per_tensor(w1)
    q_b1 = quantize_bias(b1, act_quant["input"][0], s_w1)

    q_w2, s_w2, z_w2 = quantize_weights_per_tensor(w2)
    q_b2 = quantize_bias(b2, act_quant["pool1"][0], s_w2)

    q_w3, s_w3, z_w3 = quantize_weights_per_tensor(w3)
    q_b3 = quantize_bias(b3, act_quant["pool2"][0], s_w3)

    q_w4, s_w4, z_w4 = quantize_weights_per_tensor(w4)
    q_b4 = quantize_bias(b4, act_quant["pool3"][0], s_w4)

    q_w_fc, s_w_fc, z_w_fc = quantize_weights_per_tensor(w_fc)
    q_b_fc = quantize_bias(b_fc, act_quant["gap"][0], s_w_fc)

    # Buffers list: Buffer 0 is empty (standard TFLite requirement)
    buffers = [schema.BufferT()]

    def add_buffer(data_bytes: bytes) -> int:
        buf = schema.BufferT()
        buf.data = list(data_bytes)
        buffers.append(buf)
        return len(buffers) - 1

    b_w1_idx = add_buffer(q_w1.tobytes())
    b_b1_idx = add_buffer(q_b1.tobytes())
    b_w2_idx = add_buffer(q_w2.tobytes())
    b_b2_idx = add_buffer(q_b2.tobytes())
    b_w3_idx = add_buffer(q_w3.tobytes())
    b_b3_idx = add_buffer(q_b3.tobytes())
    b_w4_idx = add_buffer(q_w4.tobytes())
    b_b4_idx = add_buffer(q_b4.tobytes())
    b_wfc_idx = add_buffer(q_w_fc.tobytes())
    b_bfc_idx = add_buffer(q_b_fc.tobytes())

    # Helper for QuantizationParametersT
    def make_quant(scale: float, zero_point: int) -> schema.QuantizationParametersT:
        qp = schema.QuantizationParametersT()
        qp.scale = [float(scale)]
        qp.zeroPoint = [int(zero_point)]
        return qp

    # Tensors definition
    tensors = []

    def add_tensor(name: str, shape: List[int], dtype: int, buffer_idx: int, qp: schema.QuantizationParametersT) -> int:
        t = schema.TensorT()
        t.name = name
        t.shape = shape
        t.type = dtype
        t.buffer = buffer_idx
        t.quantization = qp
        tensors.append(t)
        return len(tensors) - 1

    INT8 = schema.TensorType.INT8
    INT32 = schema.TensorType.INT32

    # 0: input [1, 96, 96, 3]
    t_in = add_tensor("input", [1, 96, 96, 3], INT8, 0, make_quant(*act_quant["input"]))
    # 1: w1 [16, 3, 3, 3]
    t_w1 = add_tensor("conv1_w", list(w1.shape), INT8, b_w1_idx, make_quant(s_w1, z_w1))
    # 2: b1 [16]
    t_b1 = add_tensor("conv1_b", [16], INT32, b_b1_idx, make_quant(act_quant["input"][0] * s_w1, 0))
    # 3: conv1_out [1, 96, 96, 16]
    t_c1 = add_tensor("conv1_out", [1, 96, 96, 16], INT8, 0, make_quant(*act_quant["conv1"]))
    # 4: pool1_out [1, 48, 48, 16]
    t_p1 = add_tensor("pool1_out", [1, 48, 48, 16], INT8, 0, make_quant(*act_quant["pool1"]))

    # 5: w2 [32, 3, 3, 16]
    t_w2 = add_tensor("conv2_w", list(w2.shape), INT8, b_w2_idx, make_quant(s_w2, z_w2))
    # 6: b2 [32]
    t_b2 = add_tensor("conv2_b", [32], INT32, b_b2_idx, make_quant(act_quant["pool1"][0] * s_w2, 0))
    # 7: conv2_out [1, 48, 48, 32]
    t_c2 = add_tensor("conv2_out", [1, 48, 48, 32], INT8, 0, make_quant(*act_quant["conv2"]))
    # 8: pool2_out [1, 24, 24, 32]
    t_p2 = add_tensor("pool2_out", [1, 24, 24, 32], INT8, 0, make_quant(*act_quant["pool2"]))

    # 9: w3 [64, 3, 3, 32]
    t_w3 = add_tensor("conv3_w", list(w3.shape), INT8, b_w3_idx, make_quant(s_w3, z_w3))
    # 10: b3 [64]
    t_b3 = add_tensor("conv3_b", [64], INT32, b_b3_idx, make_quant(act_quant["pool2"][0] * s_w3, 0))
    # 11: conv3_out [1, 24, 24, 64]
    t_c3 = add_tensor("conv3_out", [1, 24, 24, 64], INT8, 0, make_quant(*act_quant["conv3"]))
    # 12: pool3_out [1, 12, 12, 64]
    t_p3 = add_tensor("pool3_out", [1, 12, 12, 64], INT8, 0, make_quant(*act_quant["pool3"]))

    # 13: w4 [64, 3, 3, 64]
    t_w4 = add_tensor("conv4_w", list(w4.shape), INT8, b_w4_idx, make_quant(s_w4, z_w4))
    # 14: b4 [64]
    t_b4 = add_tensor("conv4_b", [64], INT32, b_b4_idx, make_quant(act_quant["pool3"][0] * s_w4, 0))
    # 15: conv4_out [1, 12, 12, 64]
    t_c4 = add_tensor("conv4_out", [1, 12, 12, 64], INT8, 0, make_quant(*act_quant["conv4"]))
    # 16: pool4_out [1, 6, 6, 64]
    t_p4 = add_tensor("pool4_out", [1, 6, 6, 64], INT8, 0, make_quant(*act_quant["pool4"]))

    # 17: gap_out [1, 1, 1, 64]
    t_gap = add_tensor("gap_out", [1, 1, 1, 64], INT8, 0, make_quant(*act_quant["gap"]))

    # 18: fc_w [8, 64]
    t_wfc = add_tensor("fc_w", list(w_fc.shape), INT8, b_wfc_idx, make_quant(s_w_fc, z_w_fc))
    # 19: fc_b [8]
    t_bfc = add_tensor("fc_b", [8], INT32, b_bfc_idx, make_quant(act_quant["gap"][0] * s_w_fc, 0))
    # 20: fc_out [1, 8]
    t_fc = add_tensor("fc_out", [1, 8], INT8, 0, make_quant(*act_quant["fc"]))

    # 21: final output softmax [1, 8] (Scale: 1/256, zp: -128)
    t_out = add_tensor("Identity", [1, 8], INT8, 0, make_quant(1.0 / 256.0, -128))

    # Operator Codes
    # Opcode 0: CONV_2D
    # Opcode 1: MAX_POOL_2D
    # Opcode 2: AVERAGE_POOL_2D
    # Opcode 3: FULLY_CONNECTED
    # Opcode 4: SOFTMAX
    operator_codes = [
        schema.OperatorCodeT(),  # 0: CONV_2D
        schema.OperatorCodeT(),  # 1: MAX_POOL_2D
        schema.OperatorCodeT(),  # 2: AVERAGE_POOL_2D
        schema.OperatorCodeT(),  # 3: FULLY_CONNECTED
        schema.OperatorCodeT(),  # 4: SOFTMAX
    ]
    operator_codes[0].builtinCode = schema.BuiltinOperator.CONV_2D
    operator_codes[0].deprecatedBuiltinCode = schema.BuiltinOperator.CONV_2D
    operator_codes[1].builtinCode = schema.BuiltinOperator.MAX_POOL_2D
    operator_codes[1].deprecatedBuiltinCode = schema.BuiltinOperator.MAX_POOL_2D
    operator_codes[2].builtinCode = schema.BuiltinOperator.AVERAGE_POOL_2D
    operator_codes[2].deprecatedBuiltinCode = schema.BuiltinOperator.AVERAGE_POOL_2D
    operator_codes[3].builtinCode = schema.BuiltinOperator.FULLY_CONNECTED
    operator_codes[3].deprecatedBuiltinCode = schema.BuiltinOperator.FULLY_CONNECTED
    operator_codes[4].builtinCode = schema.BuiltinOperator.SOFTMAX
    operator_codes[4].deprecatedBuiltinCode = schema.BuiltinOperator.SOFTMAX

    # Operators list
    operators = []

    def make_conv_op(in_t: int, w_t: int, b_t: int, out_t: int) -> schema.OperatorT:
        op = schema.OperatorT()
        op.opcodeIndex = 0
        op.inputs = [in_t, w_t, b_t]
        op.outputs = [out_t]
        opt = schema.Conv2DOptionsT()
        opt.padding = schema.Padding.SAME
        opt.strideW = 1
        opt.strideH = 1
        opt.fusedActivationFunction = schema.ActivationFunctionType.RELU
        op.builtinOptionsType = schema.BuiltinOptions.Conv2DOptions
        op.builtinOptions = opt
        return op

    def make_pool_op(in_t: int, out_t: int) -> schema.OperatorT:
        op = schema.OperatorT()
        op.opcodeIndex = 1
        op.inputs = [in_t]
        op.outputs = [out_t]
        opt = schema.Pool2DOptionsT()
        opt.padding = schema.Padding.VALID
        opt.strideW = 2
        opt.strideH = 2
        opt.filterWidth = 2
        opt.filterHeight = 2
        opt.fusedActivationFunction = schema.ActivationFunctionType.NONE
        op.builtinOptionsType = schema.BuiltinOptions.Pool2DOptions
        op.builtinOptions = opt
        return op

    # Block 1
    operators.append(make_conv_op(t_in, t_w1, t_b1, t_c1))
    operators.append(make_pool_op(t_c1, t_p1))

    # Block 2
    operators.append(make_conv_op(t_p1, t_w2, t_b2, t_c2))
    operators.append(make_pool_op(t_c2, t_p2))

    # Block 3
    operators.append(make_conv_op(t_p2, t_w3, t_b3, t_c3))
    operators.append(make_pool_op(t_c3, t_p3))

    # Block 4
    operators.append(make_conv_op(t_p3, t_w4, t_b4, t_c4))
    operators.append(make_pool_op(t_c4, t_p4))

    # Global Average Pooling (6x6 filter over 6x6 spatial dimension)
    gap_op = schema.OperatorT()
    gap_op.opcodeIndex = 2
    gap_op.inputs = [t_p4]
    gap_op.outputs = [t_gap]
    gap_opt = schema.Pool2DOptionsT()
    gap_opt.padding = schema.Padding.VALID
    gap_opt.strideW = 6
    gap_opt.strideH = 6
    gap_opt.filterWidth = 6
    gap_opt.filterHeight = 6
    gap_opt.fusedActivationFunction = schema.ActivationFunctionType.NONE
    gap_op.builtinOptionsType = schema.BuiltinOptions.Pool2DOptions
    gap_op.builtinOptions = gap_opt
    operators.append(gap_op)

    # Fully Connected (t_gap [1, 1, 1, 64] -> flattened implicitly by FC op in TFLite)
    fc_op = schema.OperatorT()
    fc_op.opcodeIndex = 3
    fc_op.inputs = [t_gap, t_wfc, t_bfc]
    fc_op.outputs = [t_fc]
    fc_opt = schema.FullyConnectedOptionsT()
    fc_opt.fusedActivationFunction = schema.ActivationFunctionType.NONE
    fc_opt.weightsFormat = schema.FullyConnectedOptionsWeightsFormat.DEFAULT
    fc_op.builtinOptionsType = schema.BuiltinOptions.FullyConnectedOptions
    fc_op.builtinOptions = fc_opt
    operators.append(fc_op)

    # Softmax
    sm_op = schema.OperatorT()
    sm_op.opcodeIndex = 4
    sm_op.inputs = [t_fc]
    sm_op.outputs = [t_out]
    sm_opt = schema.SoftmaxOptionsT()
    sm_opt.beta = 1.0
    sm_op.builtinOptionsType = schema.BuiltinOptions.SoftmaxOptions
    sm_op.builtinOptions = sm_opt
    operators.append(sm_op)

    # Subgraph
    subgraph = schema.SubGraphT()
    subgraph.tensors = tensors
    subgraph.inputs = [t_in]
    subgraph.outputs = [t_out]
    subgraph.operators = operators

    # Model
    model_t = schema.ModelT()
    model_t.version = 3
    model_t.operatorCodes = operator_codes
    model_t.subgraphs = [subgraph]
    model_t.description = "AgriSense Tomato Disease 4-Block CNN (INT8 Quantized)"
    model_t.buffers = buffers

    packed_model = model_t.Pack(builder)
    builder.Finish(packed_model, b"TFL3")
    tflite_bytes = builder.Output()

    metadata = {
        "model_name": "AgriSense-Tomato-CNN-4Block",
        "architecture": "4x(Conv2D+ReLU+MaxPool2D) -> AvgPool2D -> FC -> Softmax",
        "parameter_count": 61032,
        "input_tensor": {
            "name": "input",
            "shape": [1, 96, 96, 3],
            "dtype": "int8",
            "scale": act_quant["input"][0],
            "zero_point": act_quant["input"][1],
        },
        "output_tensor": {
            "name": "Identity",
            "shape": [1, 8],
            "dtype": "int8",
            "scale": 1.0 / 256.0,
            "zero_point": -128,
        },
        "classes": classes,
        "quantization_type": "full_int8",
        "file_size_bytes": len(tflite_bytes),
    }

    return bytes(tflite_bytes), metadata


def export_c_header(tflite_bytes: bytes, header_paths: List[Path]):
    """Export tflite byte buffer to C++ header (model_data.h) for TFLite Micro."""
    c_lines = [
        "// Auto-generated by AgriSense convert_tflite.py",
        "// Full INT8 Quantized Tomato Disease CNN for ESP32-CAM TFLite Micro",
        "#ifndef MODEL_DATA_H_",
        "#define MODEL_DATA_H_",
        "",
        "#include <cstdint>",
        "",
        f"const unsigned int g_model_data_len = {len(tflite_bytes)};",
        "alignas(16) const unsigned char g_model_data[] = {",
    ]

    # Format bytes in rows of 12
    for i in range(0, len(tflite_bytes), 12):
        chunk = tflite_bytes[i:i + 12]
        hex_vals = ", ".join(f"0x{b:02x}" for b in chunk)
        comma = "," if i + 12 < len(tflite_bytes) else ""
        c_lines.append(f"  {hex_vals}{comma}")

    c_lines.append("};")
    c_lines.append("")
    c_lines.append("#endif // MODEL_DATA_H_")
    c_lines.append("")

    content = "\n".join(c_lines)
    for p in header_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        print(f"  Saved C header: {p.resolve()} ({len(tflite_bytes):,} bytes)")


def verify_tflite_model(tflite_bytes: bytes, metadata: Dict):
    """Verify loading and running inference with ai_edge_litert."""
    import ai_edge_litert.interpreter as tflite

    interpreter = tflite.Interpreter(model_content=tflite_bytes)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    in_shape = input_details[0]["shape"]
    in_dtype = input_details[0]["dtype"]
    out_shape = output_details[0]["shape"]
    out_dtype = output_details[0]["dtype"]

    print(f"\n[AgriSense LiteRT Verify] Model loaded successfully!")
    print(f"  Input Tensor:  shape={in_shape.tolist()} dtype={in_dtype.__name__}")
    print(f"  Output Tensor: shape={out_shape.tolist()} dtype={out_dtype.__name__}")

    # Test inference with dummy leaf image
    dummy_input = np.random.randint(-128, 127, size=in_shape, dtype=np.int8)
    interpreter.set_tensor(input_details[0]["index"], dummy_input)
    interpreter.invoke()

    output_data = interpreter.get_tensor(output_details[0]["index"])
    top_class_idx = int(np.argmax(output_data))
    top_class_name = metadata["classes"][top_class_idx]

    print(f"  Inference Test: Top prediction index={top_class_idx} ({top_class_name})")
    print(f"  Output raw INT8 logits: {output_data.flatten().tolist()}")


def main():
    parser = argparse.ArgumentParser(description="Convert AgriSense CNN checkpoint to INT8 TFLite model.")
    parser.add_argument("--checkpoint", default="ml/models/tomato_cnn.pt", help="PyTorch model checkpoint path")
    parser.add_argument("--dataset-dir", default="ml/dataset", help="Dataset directory for calibration")
    parser.add_argument("--output-tflite", default="ml/models/model_quant_int8.tflite", help="TFLite output path")
    parser.add_argument("--output-metadata", default="ml/models/training_metadata.json", help="Metadata JSON output")
    args = parser.parse_args()

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}. Run train.py first.")

    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    classes = checkpoint["classes"]

    model = AgriSenseTomatoCNN(num_classes=len(classes))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Calibration
    calib_ranges = run_representative_calibration(model, Path(args.dataset_dir), num_samples=32)

    # Build TFLite Model
    tflite_bytes, metadata = build_tflite_model(model, calib_ranges, classes)

    out_tflite = Path(args.output_tflite)
    out_tflite.parent.mkdir(parents=True, exist_ok=True)
    with open(out_tflite, "wb") as f:
        f.write(tflite_bytes)

    out_meta = Path(args.output_metadata)
    with open(out_meta, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[AgriSense TFLite Export]")
    print(f"  Quantized Model:   {out_tflite.resolve()} ({len(tflite_bytes) / 1024:.2f} KB)")
    print(f"  Training Metadata: {out_meta.resolve()}")

    # Export C headers
    header_targets = [
        Path("firmware/vision_node/model_data.h"),
        Path("ml/models/model_data.h"),
    ]
    export_c_header(tflite_bytes, header_targets)

    # Verify with LiteRT runtime
    verify_tflite_model(tflite_bytes, metadata)


if __name__ == "__main__":
    main()

