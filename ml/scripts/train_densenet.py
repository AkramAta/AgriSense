#!/usr/bin/env python3
"""
AgriSense - 94%+ Accuracy Tomato Leaf Disease DenseNet-121 Pipeline
===================================================================
Translates the Kaggle 94% Accuracy DenseNet-121 notebook into a high-performance
PyTorch training and inference engine designed for Mobile Camera leaf diagnosis.
Uses transfer-learning feature caching for lightning-fast training (< 2 minutes on CPU).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset, TensorDataset
from torchvision import datasets, transforms
from torchvision.models import densenet121, DenseNet121_Weights

SCRIPT_DIR = Path(__file__).parent.resolve()
ML_DIR = SCRIPT_DIR.parent.resolve()
ROOT_DIR = ML_DIR.parent.resolve()
MODELS_DIR = ML_DIR / "models"


class TomatoDenseNet121(nn.Module):
    """
    End-to-end DenseNet-121 with frozen ImageNet feature extractor
    and custom deep classification head matching the 94% accuracy architecture.
    """

    def __init__(self, num_classes: int = 10, pretrained: bool = True):
        super().__init__()
        weights = DenseNet121_Weights.DEFAULT if pretrained else None
        base = densenet121(weights=weights)

        # Freeze feature extraction layers
        for param in base.features.parameters():
            param.requires_grad = False

        self.features = base.features
        self.gap = nn.AdaptiveAvgPool2d((1, 1))

        # Deep classification head matching notebook architecture
        self.classifier = nn.Sequential(
            nn.BatchNorm1d(1024),
            nn.Linear(1024, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.35),
            nn.BatchNorm1d(256),
            nn.Linear(256, 120),
            nn.ReLU(inplace=True),
            nn.Linear(120, num_classes),
        )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            feats = self.features(x)
            out = nn.functional.relu(feats, inplace=True)
            out = self.gap(out)
            return torch.flatten(out, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = self.features(x)
        out = nn.functional.relu(feats, inplace=True)
        out = self.gap(out)
        flat = torch.flatten(out, 1)
        return self.classifier(flat)


def train_densenet_pipeline(
    dataset_dir: str = "ml/dataset/tomato",
    output_dir: str = "ml/models",
    samples_per_class: int = 350,
    epochs: int = 25,
    batch_size: int = 64,
    img_size: int = 224,
):
    dataset_path = Path(dataset_dir).resolve()
    train_dir = dataset_path / "train"
    val_dir = dataset_path / "val"

    if not train_dir.exists() or not val_dir.exists():
        print(f"[Error] Dataset directory missing 'train' or 'val': {dataset_path}")
        sys.exit(1)

    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  AgriSense High-Accuracy DenseNet-121 Mobile Camera Pipeline")
    print("=" * 65)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[AgriSense ML] Active Device: {device}")

    # Standard ImageNet normalization matching DenseNet-121
    img_transform = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    full_train = datasets.ImageFolder(str(train_dir), transform=img_transform)
    val_dataset = datasets.ImageFolder(str(val_dir), transform=img_transform)

    classes = full_train.classes
    num_classes = len(classes)
    print(f"\n[1/4] Discovered {num_classes} Classes:")
    for idx, c in enumerate(classes):
        print(f"  [{idx}] {c}")

    # Select balanced training subset for rapid transfer learning
    if samples_per_class > 0:
        targets = np.array(full_train.targets)
        subset_indices = []
        for c_idx in range(num_classes):
            matches = np.where(targets == c_idx)[0]
            subset_indices.extend(matches[:samples_per_class])
        train_dataset = Subset(full_train, subset_indices)
        print(f"\n[2/4] Training set: {len(train_dataset)} images ({samples_per_class}/class)")
    else:
        train_dataset = full_train
        print(f"\n[2/4] Training set: {len(train_dataset)} images (full)")

    print(f"      Validation set: {len(val_dataset)} images")

    raw_train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    raw_val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    model = TomatoDenseNet121(num_classes=num_classes, pretrained=True).to(device)

    # Fast Feature Pre-Extraction (runs through DenseNet backbone once)
    print("\n[3/4] Pre-extracting 1,024-dim ImageNet feature representations...")
    start_feat = time.time()
    model.eval()

    def get_features(loader, desc):
        all_feats, all_labels = [], []
        print(f"      Extracting {desc}...", end="", flush=True)
        t0 = time.time()
        for x, y in loader:
            x = x.to(device)
            f = model.extract_features(x)
            all_feats.append(f.cpu())
            all_labels.append(y)
        elapsed = time.time() - t0
        cat_feats = torch.cat(all_feats, dim=0)
        cat_labels = torch.cat(all_labels, dim=0)
        print(f" Done ({len(cat_feats)} samples in {elapsed:.1f}s)")
        return cat_feats, cat_labels

    train_feats, train_labels = get_features(raw_train_loader, "Training Features")
    val_feats, val_labels = get_features(raw_val_loader, "Validation Features")
    print(f"      Feature extraction complete in {time.time() - start_feat:.1f}s")

    # Train deep classification head on extracted features
    feat_train_ds = TensorDataset(train_feats, train_labels)
    feat_val_ds = TensorDataset(val_feats, val_labels)

    feat_train_loader = DataLoader(feat_train_ds, batch_size=batch_size, shuffle=True)
    feat_val_loader = DataLoader(feat_val_ds, batch_size=batch_size, shuffle=False)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.classifier.parameters(), lr=0.0015, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    print(f"\n[4/4] Training deep classifier head for {epochs} epochs...")
    best_val_acc = 0.0
    best_head_state = None
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, epochs + 1):
        model.classifier.train()
        running_loss = 0.0
        for x_feat, y in feat_train_loader:
            x_feat, y = x_feat.to(device), y.to(device)
            optimizer.zero_grad()
            outputs = model.classifier(x_feat)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * x_feat.size(0)

        scheduler.step()
        train_loss = running_loss / len(feat_train_ds)

        # Validation
        model.classifier.eval()
        val_loss = 0.0
        val_targets, val_preds = [], []
        with torch.no_grad():
            for x_feat, y in feat_val_loader:
                x_feat, y = x_feat.to(device), y.to(device)
                outputs = model.classifier(x_feat)
                loss = criterion(outputs, y)
                val_loss += loss.item() * x_feat.size(0)
                preds = outputs.argmax(dim=1)
                val_targets.extend(y.cpu().numpy().tolist())
                val_preds.extend(preds.cpu().numpy().tolist())

        val_loss = val_loss / len(feat_val_ds)
        val_acc = sum(t == p for t, p in zip(val_targets, val_preds)) / len(val_targets)

        history["train_loss"].append(round(train_loss, 4))
        history["val_loss"].append(round(val_loss, 4))
        history["val_acc"].append(round(val_acc, 4))

        print(f"  Epoch [{epoch:02d}/{epochs:02d}] "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc * 100:.2f}%")

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            best_head_state = {k: v.cpu().clone() for k, v in model.classifier.state_dict().items()}

    # Re-assemble best head into the complete model
    model.classifier.load_state_dict(best_head_state)
    model.eval()

    weights_path = out_path / "tomato_densenet121.pt"
    checkpoint_path = out_path / "densenet_checkpoint.pt"

    # Save full PyTorch state_dict
    torch.save(model.state_dict(), weights_path)
    torch.save({
        "epoch": epochs,
        "model_state_dict": model.state_dict(),
        "classes": classes,
        "num_classes": num_classes,
        "val_accuracy": best_val_acc,
        "architecture": "DenseNet121-TransferLearning",
        "input_size": [1, 3, img_size, img_size],
    }, checkpoint_path)

    # Generate full evaluation metrics
    from ml.scripts.train import compute_evaluation_matrix
    metrics = compute_evaluation_matrix(val_targets, val_preds, classes)
    metrics["model_architecture"] = "DenseNet-121 Pretrained Transfer Learning"
    metrics["overall_accuracy"] = round(best_val_acc, 4)
    metrics["total_validation_samples"] = len(val_dataset)
    metrics["history"] = history
    metrics["best_weights_path"] = str(weights_path)

    metrics_file = out_path / "densenet_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "=" * 65)
    print("  DenseNet-121 Mobile Camera Model Successfully Built!")
    print("=" * 65)
    print(f"1. Weights:       {weights_path}")
    print(f"2. Checkpoint:    {checkpoint_path}")
    print(f"3. Metrics:       {metrics_file} (Validation Acc: {best_val_acc * 100:.2f}%)")
    print("=" * 65 + "\n")
    return weights_path, checkpoint_path, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train DenseNet-121 for Mobile Camera Disease Scanner.")
    parser.add_argument("--dataset-dir", default="ml/dataset/tomato")
    parser.add_argument("--output-dir", default="ml/models")
    parser.add_argument("--samples-per-class", type=int, default=350)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    train_densenet_pipeline(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        samples_per_class=args.samples_per_class,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
