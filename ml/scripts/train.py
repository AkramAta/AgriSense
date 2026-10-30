#!/usr/bin/env python3
"""
AgriSense - 4-Block Compact CNN Training & Evaluation
Architecture: 4 Conv-ReLU-Pool Blocks + Global Average Pooling + Linear Classifier.
Parameter count: exactly 61,032 (~61K parameters), designed for edge microcontrollers.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


class AgriSenseTomatoCNN(nn.Module):
    """
    Compact 4-Block Convolutional Neural Network designed for edge microcontrollers.
    Target footprint: ~61K parameters, sub-250KB RAM usage on ESP32-CAM.
    """

    def __init__(self, num_classes: int = 8):
        super().__init__()
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

        # Classifier: (64, 6, 6) -> (64, 1, 1) -> (8)
        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Linear(64, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.gap(x)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x


def get_parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def create_data_loaders(
    data_dir: str, batch_size: int = 16
) -> Tuple[DataLoader, DataLoader, List[str]]:
    data_path = Path(data_dir)
    train_dir = data_path / "train"
    val_dir = data_path / "val"

    if not train_dir.exists() or not val_dir.exists():
        raise FileNotFoundError(f"Dataset splits missing in {data_path}. Run download_dataset.py first.")

    train_transform = transforms.Compose([
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_dataset = datasets.ImageFolder(str(train_dir), transform=train_transform)
    val_dataset = datasets.ImageFolder(str(val_dir), transform=val_transform)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, drop_last=False)

    return train_loader, val_loader, train_dataset.classes


def compute_evaluation_matrix(
    all_targets: List[int], all_preds: List[int], classes: List[str]
) -> Dict:
    num_classes = len(classes)
    matrix = np.zeros((num_classes, num_classes), dtype=int)
    for t, p in zip(all_targets, all_preds):
        matrix[t, p] += 1

    per_class_metrics = {}
    total_samples = len(all_targets)
    correct_total = 0

    for i, c_name in enumerate(classes):
        tp = matrix[i, i]
        fp = matrix[:, i].sum() - tp
        fn = matrix[i, :].sum() - tp
        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        correct_total += tp

        per_class_metrics[c_name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": int(matrix[i, :].sum()),
        }

    overall_accuracy = float(correct_total / total_samples) if total_samples > 0 else 0.0
    macro_f1 = float(np.mean([m["f1_score"] for m in per_class_metrics.values()]))

    return {
        "overall_accuracy": round(overall_accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "total_test_samples": total_samples,
        "confusion_matrix": matrix.tolist(),
        "per_class": per_class_metrics,
        "classes": classes,
    }


def train_model(
    data_dir: str = "ml/dataset",
    output_dir: str = "ml/models",
    epochs: int = 12,
    batch_size: int = 16,
    lr: float = 0.001,
) -> Dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[AgriSense Train] Using compute device: {device}")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, classes = create_data_loaders(data_dir, batch_size=batch_size)
    model = AgriSenseTomatoCNN(num_classes=len(classes)).to(device)

    total_params = get_parameter_count(model)
    print(f"[AgriSense Architecture] Parameter Count: {total_params:,} parameters")

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    best_weights_path = out_path / "tomato_cnn.pt"

    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)

        scheduler.step()
        train_loss = running_loss / len(train_loader.dataset)

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_targets, val_preds = [], []
        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                val_loss += loss.item() * inputs.size(0)
                preds = outputs.argmax(dim=1)
                val_targets.extend(targets.cpu().numpy().tolist())
                val_preds.extend(preds.cpu().numpy().tolist())

        val_loss = val_loss / len(val_loader.dataset)
        val_acc = sum(t == p for t, p in zip(val_targets, val_preds)) / len(val_targets)

        history["train_loss"].append(round(train_loss, 4))
        history["val_loss"].append(round(val_loss, 4))
        history["val_acc"].append(round(val_acc, 4))

        print(
            f"Epoch [{epoch:02d}/{epochs:02d}] "
            f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc * 100:.2f}%"
        )

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "classes": classes,
                "num_classes": len(classes),
                "val_accuracy": val_acc,
                "parameter_count": total_params,
            }, best_weights_path)

    # Load best checkpoint for final evaluation matrix
    best_checkpoint = torch.load(best_weights_path, map_location=device, weights_only=False)
    model.load_state_dict(best_checkpoint["model_state_dict"])
    model.eval()

    eval_targets, eval_preds = [], []
    with torch.no_grad():
        for inputs, targets in val_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            eval_targets.extend(targets.numpy().tolist())
            eval_preds.extend(outputs.argmax(dim=1).cpu().numpy().tolist())

    metrics = compute_evaluation_matrix(eval_targets, eval_preds, classes)
    metrics["parameter_count"] = total_params
    metrics["history"] = history
    metrics["best_weights_path"] = str(best_weights_path)

    metrics_file = out_path / "eval_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[AgriSense Evaluation] Final Validation Accuracy: {metrics['overall_accuracy'] * 100:.2f}%")
    print(f"  Macro F1: {metrics['macro_f1']:.4f}")
    print(f"  Saved best model checkpoint to: {best_weights_path}")
    print(f"  Saved evaluation metrics to:    {metrics_file}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train AgriSense 4-block CNN for tomato disease classification.")
    parser.add_argument("--data-dir", default="ml/dataset", help="Dataset root directory containing train/ and val/")
    parser.add_argument("--output-dir", default="ml/models", help="Model checkpoints and metrics output directory")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Training batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Initial learning rate")
    args = parser.parse_args()

    train_model(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )


if __name__ == "__main__":
    main()
