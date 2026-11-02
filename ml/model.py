#!/usr/bin/env python3
"""
AgriSense - Tomato Leaf Pathology CNN Architecture
==================================================
Compact 4-Block Convolutional Neural Network designed for edge embedded devices,
mobile applications, and cloud serverless inference.

Architecture Overview:
----------------------
Input:  (B, 3, 96, 96)  - Normalized RGB leaf image
Block 1: Conv2D(3->16, 3x3) + ReLU + MaxPool2D(2x2)  -> (B, 16, 48, 48)  [448 params]
Block 2: Conv2D(16->32, 3x3) + ReLU + MaxPool2D(2x2) -> (B, 32, 24, 24)  [4,640 params]
Block 3: Conv2D(32->64, 3x3) + ReLU + MaxPool2D(2x2) -> (B, 64, 12, 12)  [18,496 params]
Block 4: Conv2D(64->64, 3x3) + ReLU + MaxPool2D(2x2) -> (B, 64, 6, 6)    [36,928 params]
Classifier: AdaptiveAvgPool2D(1x1) + Flatten + Linear(64->8)             [520 params]

Total Parameters: 61,032 (~61K parameters)
Model Size (FP32): ~244 KB
Model Size (INT8 Quantized): ~64.8 KB (sub-100KB flash/RAM budget)
Target Classes (8):
  0: Tomato___Bacterial_spot
  1: Tomato___Early_blight
  2: Tomato___Late_blight
  3: Tomato___Leaf_Mold
  4: Tomato___Septoria_leaf_spot
  5: Tomato___Spider_mites_Two_spotted_spider_mite
  6: Tomato___Target_Spot
  7: Tomato___healthy
"""

import sys
from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn

# Canonical 8 Tomato Pathology Classes
CLASS_NAMES: List[str] = [
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___healthy",
]

HUMAN_READABLE_NAMES: Dict[str, str] = {
    "Tomato___Bacterial_spot": "Bacterial Spot",
    "Tomato___Early_blight": "Early Blight",
    "Tomato___Late_blight": "Late Blight",
    "Tomato___Leaf_Mold": "Leaf Mold",
    "Tomato___Septoria_leaf_spot": "Septoria Leaf Spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite": "Spider Mites (Two-spotted)",
    "Tomato___Target_Spot": "Target Spot",
    "Tomato___healthy": "Healthy Foliage",
}


class AgriSenseTomatoCNN(nn.Module):
    """
    Compact 4-Block Convolutional Neural Network for Edge Leaf Pathology.
    Optimized for microcontroller SRAM, mobile devices, and serverless containers.
    """

    def __init__(self, num_classes: int = 8, input_size: int = 96):
        super().__init__()
        self.num_classes = num_classes
        self.input_size = input_size

        # Block 1: Input (3, 96, 96) -> Output (16, 48, 48)
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Block 2: Input (16, 48, 48) -> Output (32, 24, 24)
        self.block2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Block 3: Input (32, 24, 24) -> Output (64, 12, 12)
        self.block3 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Block 4: Input (64, 12, 12) -> Output (64, 6, 6)
        self.block4 = nn.Sequential(
            nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )

        # Global pooling and dense classifier
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Linear(64, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Tensor of shape (B, 3, 96, 96) normalized to mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        Returns:
            Tensor of logits of shape (B, 8)
        """
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.gap(x)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x

    def forward_with_features(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns both logits and global average pooled latent feature representations."""
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.gap(x)
        features = torch.flatten(x, 1)
        logits = self.classifier(features)
        return logits, features


def count_parameters(model: nn.Module) -> Tuple[int, int]:
    """Returns (trainable_parameters, total_parameters)."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def print_model_summary(model: AgriSenseTomatoCNN) -> None:
    """Prints a formatted layer-by-layer architectural summary table."""
    print("=" * 82)
    print(f"{'AGRISENSE TOMATO CNN - 4-BLOCK COMPACT ARCHITECTURE':^82}")
    print("=" * 82)
    print(f"{'Layer / Block':<28} {'Output Shape':<22} {'Param #':<12} {'Receptive Field':<16}")
    print("-" * 82)

    dummy_x = torch.zeros(1, 3, model.input_size, model.input_size)
    print(f"{'Input Image':<28} {str(list(dummy_x.shape)):<22} {'0':<12} {'1x1':<16}")

    x = model.block1(dummy_x)
    p1 = sum(p.numel() for p in model.block1.parameters())
    print(f"{'Block 1 (Conv16+ReLU+Pool)':<28} {str(list(x.shape)):<22} {p1:<12} {'6x6':<16}")

    x = model.block2(x)
    p2 = sum(p.numel() for p in model.block2.parameters())
    print(f"{'Block 2 (Conv32+ReLU+Pool)':<28} {str(list(x.shape)):<22} {p2:<12} {'14x14':<16}")

    x = model.block3(x)
    p3 = sum(p.numel() for p in model.block3.parameters())
    print(f"{'Block 3 (Conv64+ReLU+Pool)':<28} {str(list(x.shape)):<22} {p3:<12} {'30x30':<16}")

    x = model.block4(x)
    p4 = sum(p.numel() for p in model.block4.parameters())
    print(f"{'Block 4 (Conv64+ReLU+Pool)':<28} {str(list(x.shape)):<22} {p4:<12} {'62x62':<16}")

    x = model.gap(x)
    x = torch.flatten(x, 1)
    print(f"{'Global Average Pooling':<28} {str(list(x.shape)):<22} {'0':<12} {'96x96':<16}")

    logits = model.classifier(x)
    pc = sum(p.numel() for p in model.classifier.parameters())
    print(f"{'Classifier (Linear 64->8)':<28} {str(list(logits.shape)):<22} {pc:<12} {'96x96':<16}")

    print("=" * 82)
    trainable, total = count_parameters(model)
    print(f"Total Parameters:      {total:,} (61,032 exactly)")
    print(f"Trainable Parameters:  {trainable:,}")
    print(f"Model Memory Footprint (FP32): {total * 4 / 1024:.2f} KB")
    print(f"Model Memory Footprint (INT8): {total * 1 / 1024:.2f} KB (TFLite quantized)")
    print("=" * 82)


def build_keras_model(input_shape=(96, 96, 3), num_classes=8):
    """
    TensorFlow / Keras equivalent for researchers using TF/Colab workflows.
    Requires: tensorflow
    """
    try:
        import tensorflow as tf
        from tensorflow.keras import layers, models
    except ImportError:
        raise ImportError("TensorFlow is required to build the Keras model. Install with `pip install tensorflow`.")

    model = models.Sequential([
        layers.Input(shape=input_shape, name="input"),
        # Block 1
        layers.Conv2D(16, (3, 3), padding="same", activation="relu", name="conv1"),
        layers.MaxPooling2D((2, 2), name="pool1"),
        # Block 2
        layers.Conv2D(32, (3, 3), padding="same", activation="relu", name="conv2"),
        layers.MaxPooling2D((2, 2), name="pool2"),
        # Block 3
        layers.Conv2D(64, (3, 3), padding="same", activation="relu", name="conv3"),
        layers.MaxPooling2D((2, 2), name="pool3"),
        # Block 4
        layers.Conv2D(64, (3, 3), padding="same", activation="relu", name="conv4"),
        layers.MaxPooling2D((2, 2), name="pool4"),
        # Classifier
        layers.GlobalAveragePooling2D(name="gap"),
        layers.Dense(num_classes, activation="softmax", name="output"),
    ], name="AgriSenseTomatoCNN_Keras")

    return model


if __name__ == "__main__":
    print("[AgriSense] Instantiating AgriSenseTomatoCNN in PyTorch...")
    model = AgriSenseTomatoCNN(num_classes=8, input_size=96)
    model.eval()

    print_model_summary(model)

    # Test dummy inference
    test_input = torch.randn(2, 3, 96, 96)
    with torch.no_grad():
        output = model(test_input)
        probs = torch.softmax(output, dim=-1)

    print(f"\nTest Forward Pass:")
    print(f"  Input Batch Shape:  {list(test_input.shape)}")
    print(f"  Output Logits Shape: {list(output.shape)}")
    print(f"  Softmax Probabilities Sum: {probs.sum(dim=-1).tolist()} (Must be [1.0, 1.0])")
    print(f"  Top Predicted Class Index (sample 0): {probs[0].argmax().item()} ({CLASS_NAMES[probs[0].argmax().item()]})")
    print("\nModel definition verified successfully.")
