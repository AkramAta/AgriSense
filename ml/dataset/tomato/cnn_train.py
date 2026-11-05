#!/usr/bin/env python3
"""
AgriSense - 10-Class Tomato Leaf Disease CNN Training & TFLite Quantization Pipeline
===================================================================================
High-Accuracy training pipeline for the 10-class PlantVillage Tomato Dataset.
Trains the 4-block CNN architecture with data augmentation, AdamW, Cosine Annealing,
and Label Smoothing to achieve maximum validation accuracy.
Exports all required project model artifacts:

Target Output Artifacts:
1. ml/models/tomato_cnn.pt             (Pure PyTorch state_dict weights)
2. ml/models/tomato_checkpoint.pt      (PyTorch checkpoint with metadata & classes)
3. ml/models/eval_metrics.json         (Evaluation confusion matrix & accuracy)
4. ml/models/model_quant_int8.tflite   (Quantized INT8 FlatBuffer model)
5. ml/models/training_metadata.json    (Input/output tensor specs & class map)
6. ml/models/model_data.h              (16-byte aligned C header for TFLite Micro)
7. firmware/vision_node/model_data.h   (Edge firmware C header)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# Resolve project directories
SCRIPT_DIR = Path(__file__).parent.resolve()
ML_DIR = SCRIPT_DIR.parent.parent.resolve()
ROOT_DIR = ML_DIR.parent.resolve()
MODELS_DIR = ML_DIR / "models"
FIRMWARE_VISION_DIR = ROOT_DIR / "firmware" / "vision_node"
SCRIPTS_DIR = ML_DIR / "scripts"

for p in [str(ROOT_DIR), str(ML_DIR), str(SCRIPTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ml.scripts.train import AgriSenseTomatoCNN, compute_evaluation_matrix, get_parameter_count
from ml.scripts.convert_tflite import convert_model_pipeline


def run_training_pipeline(args):
    dataset_path = Path(args.dataset_dir).resolve()
    train_dir = dataset_path / "train"
    val_dir = dataset_path / "val"

    if not train_dir.exists() or not val_dir.exists():
        print(f"[Error] Dataset directory must contain 'train' and 'val' subdirectories: {dataset_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  AgriSense High-Accuracy 10-Class CNN Pipeline")
    print("=" * 65)

    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Subset
    from torchvision import datasets, transforms

    print(f"[AgriSense ML] Active Training Backend: PyTorch ({torch.__version__})")

    train_transform = transforms.Compose([
        transforms.Resize((args.img_size, args.img_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomRotation(degrees=20),
        transforms.RandomAffine(degrees=0, translate=(0.06, 0.06), scale=(0.94, 1.06)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.03),
        transforms.ToTensor(),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((args.img_size, args.img_size)),
        transforms.ToTensor(),
    ])

    full_train_dataset = datasets.ImageFolder(str(train_dir), transform=train_transform)
    val_dataset = datasets.ImageFolder(str(val_dir), transform=val_transform)

    classes = full_train_dataset.classes
    num_classes = len(classes)
    print(f"\n[1/4] Discovered {num_classes} Classes from Directory:")
    for idx, c in enumerate(classes):
        print(f"  [{idx}] {c}")

    # Training subset selection (0 = full 10,000 images)
    if args.samples_per_class > 0:
        targets = np.array(full_train_dataset.targets)
        subset_indices = []
        for c_idx in range(num_classes):
            matches = np.where(targets == c_idx)[0]
            subset_indices.extend(matches[:args.samples_per_class])
        train_dataset = Subset(full_train_dataset, subset_indices)
        print(f"\n[2/4] Training set: {len(train_dataset)} images ({args.samples_per_class}/class)")
    else:
        train_dataset = full_train_dataset
        print(f"\n[2/4] Training set: {len(train_dataset)} images (full 10,000 image dataset)")

    print(f"      Validation set: {len(val_dataset)} images")

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        drop_last=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available()
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        drop_last=False,
        num_workers=0
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AgriSenseTomatoCNN(num_classes=num_classes).to(device)
    total_params = get_parameter_count(model)
    print(f"      Architecture: AgriSenseTomatoCNN ({total_params:,} parameters)")

    # Label smoothing regularizes confidence and improves out-of-sample accuracy
    criterion = nn.CrossEntropyLoss(label_smoothing=0.06)
    optimizer = optim.AdamW(model.parameters(), lr=0.0025, weight_decay=3e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=5e-6)

    best_val_acc = 0.0
    weights_path = output_dir / "tomato_cnn.pt"
    checkpoint_path = output_dir / "tomato_checkpoint.pt"
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    print(f"\n[3/4] Training model for {args.epochs} epochs with Label Smoothing & CosineAnnealing...")
    start_t = time.time()

    for epoch in range(1, args.epochs + 1):
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

        curr_lr = optimizer.param_groups[0]["lr"]
        print(f"  Epoch [{epoch:02d}/{args.epochs:02d}] "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc * 100:.2f}% | LR: {curr_lr:.6f}")

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            # 1. Pure state_dict (tomato_cnn.pt)
            torch.save(model.state_dict(), weights_path)
            # 2. Checkpoint with metadata (tomato_checkpoint.pt)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "classes": classes,
                "num_classes": num_classes,
                "val_accuracy": val_acc,
                "parameter_count": total_params,
            }, checkpoint_path)

    train_duration = time.time() - start_t
    print(f"\n  Finished training in {train_duration:.1f}s | Best Val Acc: {best_val_acc * 100:.2f}%")

    # 3. Compute final evaluation metrics across all validation images
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    model.eval()
    eval_targets, eval_preds = [], []
    with torch.no_grad():
        for inputs, targets_t in val_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            eval_targets.extend(targets_t.numpy().tolist())
            eval_preds.extend(outputs.argmax(dim=1).cpu().numpy().tolist())

    metrics = compute_evaluation_matrix(eval_targets, eval_preds, classes)
    metrics["parameter_count"] = total_params
    metrics["history"] = history
    metrics["best_weights_path"] = str(weights_path)

    metrics_file = output_dir / "eval_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    # 4, 5, 6. Quantize to INT8 TFLite with 100 calibration samples, export metadata and C header
    print(f"\n[4/4] Generating INT8 TFLite FlatBuffer (100 calibration samples), Metadata, and C Array...")
    tflite_path, meta_path = convert_model_pipeline(
        checkpoint_path=str(checkpoint_path),
        dataset_dir=str(dataset_path),
        output_tflite=str(output_dir / "model_quant_int8.tflite"),
        output_metadata=str(output_dir / "training_metadata.json"),
        num_samples=100,
    )

    print("\n" + "=" * 65)
    print("  All AgriSense Model Artifacts Successfully Updated!")
    print("=" * 65)
    print(f"1. [tomato_cnn.pt]            -> {weights_path}")
    print(f"2. [tomato_checkpoint.pt]     -> {checkpoint_path}")
    print(f"3. [eval_metrics.json]        -> {metrics_file}")
    print(f"4. [model_quant_int8.tflite]  -> {tflite_path}")
    print(f"5. [training_metadata.json]   -> {meta_path}")
    print(f"6. [model_data.h]             -> {output_dir / 'model_data.h'}")
    print(f"   [firmware/model_data.h]    -> {FIRMWARE_VISION_DIR / 'model_data.h'}")
    print("=" * 65 + "\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train AgriSense CNN on 10-class PlantVillage dataset.")
    parser.add_argument('--dataset-dir', type=str, default=str(SCRIPT_DIR),
                        help="Path containing 'train' and 'val' subdirectories")
    parser.add_argument('--output-dir', type=str, default=str(MODELS_DIR),
                        help="Project models output directory (default: ml/models)")
    parser.add_argument('--epochs', type=int, default=16,
                        help="Number of training epochs (default: 16)")
    parser.add_argument('--batch-size', type=int, default=64,
                        help="Batch size (default: 64)")
    parser.add_argument('--img-size', type=int, default=96,
                        help="Input resolution in pixels (default: 96)")
    parser.add_argument('--samples-per-class', type=int, default=0,
                        help="Training samples per class (default: 0 for all 10,000 images)")

    args = parser.parse_args()
    run_training_pipeline(args)
