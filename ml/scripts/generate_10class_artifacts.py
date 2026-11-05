#!/usr/bin/env python3
"""
AgriSense - 10-Class Artifact Generation & Model Retraining
==========================================================
Trains the 4-block CNN architecture across all 10 tomato pathology classes,
computes validation evaluation metrics, and exports all 6 production artifacts:
1. tomato_cnn.pt (Pure PyTorch state_dict)
2. tomato_checkpoint.pt (PyTorch checkpoint with metadata & class indices)
3. eval_metrics.json (Per-class precision, recall, f1, and overall accuracy)
4. model_quant_int8.tflite (Full INT8 FlatBuffer model for edge & Lambda inference)
5. training_metadata.json (Quantization scales, zero points, and class lists)
6. model_data.h (16-byte aligned C++ array for TFLite Micro on microcontrollers)
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.append(str(SCRIPT_DIR))

from convert_tflite import convert_model_pipeline
from train import AgriSenseTomatoCNN, compute_evaluation_matrix, get_parameter_count


def generate_all_10class_artifacts(
    data_dir: str = "ml/dataset/tomato",
    output_dir: str = "ml/models",
    epochs: int = 5,
    batch_size: int = 32,
    samples_per_class_train: int = 150,  # Fast high-quality training on CPU
):
    print("=" * 65)
    print("  AgriSense 10-Class Model Training & Artifact Generation Pipeline")
    print("=" * 65)

    data_path = Path(data_dir).resolve()
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    train_dir = data_path / "train"
    val_dir = data_path / "val"

    if not train_dir.exists() or not val_dir.exists():
        raise FileNotFoundError(f"Missing train or val directory inside: {data_path}")

    # Standard 96x96 input transforms matching microcontroller & mobile constraints
    train_transform = transforms.Compose([
        transforms.Resize((96, 96)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((96, 96)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    full_train_dataset = datasets.ImageFolder(str(train_dir), transform=train_transform)
    val_dataset = datasets.ImageFolder(str(val_dir), transform=val_transform)

    classes = full_train_dataset.classes
    num_classes = len(classes)
    print(f"\n[1/5] Loaded Dataset: {num_classes} Classes Detected")
    for i, c in enumerate(classes):
        print(f"  Class {i}: {c}")

    # Create balanced training subset for rapid local convergence
    if samples_per_class_train > 0:
        targets = np.array(full_train_dataset.targets)
        indices = []
        for c_idx in range(num_classes):
            c_indices = np.where(targets == c_idx)[0]
            selected = c_indices[:samples_per_class_train]
            indices.extend(selected)
        train_dataset = Subset(full_train_dataset, indices)
        print(f"\n[2/5] Training on balanced subset: {len(train_dataset)} images ({samples_per_class_train}/class)")
    else:
        train_dataset = full_train_dataset
        print(f"\n[2/5] Training on full dataset: {len(train_dataset)} images")

    print(f"      Validation set size: {len(val_dataset)} images")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, drop_last=False)

    # Initialize model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AgriSenseTomatoCNN(num_classes=num_classes).to(device)
    param_count = get_parameter_count(model)
    print(f"\n[3/5] Instantiated AgriSenseTomatoCNN (Params: {param_count:,}) on device: {device}")

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    best_weights_path = out_path / "tomato_cnn.pt"
    checkpoint_path = out_path / "tomato_checkpoint.pt"
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    print(f"\n[4/5] Training CNN for {epochs} Epochs...")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for inputs, targets_t in train_loader:
            inputs, targets_t = inputs.to(device), targets_t.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets_t)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)

        scheduler.step()
        train_loss = running_loss / len(train_dataset)

        # Validation
        model.eval()
        val_loss = 0.0
        val_targets, val_preds = [], []
        with torch.no_grad():
            for inputs, targets_t in val_loader:
                inputs, targets_t = inputs.to(device), targets_t.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets_t)
                val_loss += loss.item() * inputs.size(0)
                preds = outputs.argmax(dim=1)
                val_targets.extend(targets_t.cpu().numpy().tolist())
                val_preds.extend(preds.cpu().numpy().tolist())

        val_loss = val_loss / len(val_dataset)
        val_acc = sum(t == p for t, p in zip(val_targets, val_preds)) / len(val_targets)

        history["train_loss"].append(round(train_loss, 4))
        history["val_loss"].append(round(val_loss, 4))
        history["val_acc"].append(round(val_acc, 4))

        print(f"  Epoch [{epoch:02d}/{epochs:02d}] "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc * 100:.2f}%")

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            # 1. Save pure state_dict (tomato_cnn.pt)
            torch.save(model.state_dict(), best_weights_path)
            # 2. Save full checkpoint (tomato_checkpoint.pt)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "classes": classes,
                "num_classes": num_classes,
                "val_accuracy": val_acc,
                "parameter_count": param_count,
            }, checkpoint_path)

    elapsed = time.time() - start_time
    print(f"\n  Training completed in {elapsed:.1f}s. Best Validation Accuracy: {best_val_acc * 100:.2f}%")

    # Evaluate best checkpoint for eval_metrics.json
    model.load_state_dict(torch.load(best_weights_path, map_location=device, weights_only=True))
    model.eval()
    eval_targets, eval_preds = [], []
    with torch.no_grad():
        for inputs, targets_t in val_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            eval_targets.extend(targets_t.numpy().tolist())
            eval_preds.extend(outputs.argmax(dim=1).cpu().numpy().tolist())

    metrics = compute_evaluation_matrix(eval_targets, eval_preds, classes)
    metrics["parameter_count"] = param_count
    metrics["history"] = history
    metrics["best_weights_path"] = str(best_weights_path)

    # 3. Save eval_metrics.json
    metrics_file = out_path / "eval_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[5/5] Exporting INT8 TFLite, Training Metadata, and C Header...")
    # 4, 5, 6. Convert to INT8 TFLite, export training_metadata.json and model_data.h
    tflite_path, meta_path = convert_model_pipeline(
        checkpoint_path=str(checkpoint_path),
        dataset_dir=str(data_path),
        output_tflite=str(out_path / "model_quant_int8.tflite"),
        output_metadata=str(out_path / "training_metadata.json"),
    )

    print("\n" + "=" * 65)
    print("  All 6 Target Artifacts Successfully Updated for 10-Class Data!")
    print("=" * 65)
    print(f"1. [tomato_cnn.pt]            -> {best_weights_path} ({best_weights_path.stat().st_size / 1024:.1f} KB)")
    print(f"2. [tomato_checkpoint.pt]     -> {checkpoint_path} ({checkpoint_path.stat().st_size / 1024:.1f} KB)")
    print(f"3. [eval_metrics.json]        -> {metrics_file}")
    print(f"4. [model_quant_int8.tflite]  -> {tflite_path} ({tflite_path.stat().st_size / 1024:.1f} KB)")
    print(f"5. [training_metadata.json]   -> {meta_path}")
    print(f"6. [model_data.h]             -> {out_path / 'model_data.h'}")
    print(f"   [firmware/model_data.h]    -> {Path('firmware/vision_node/model_data.h')}")
    print("=" * 65)


if __name__ == "__main__":
    generate_all_10class_artifacts()

