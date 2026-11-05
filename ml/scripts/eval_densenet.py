import json
import os
import sys
import torch
from torchvision import datasets, transforms

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ml.scripts.train_densenet import TomatoDenseNet121
from ml.scripts.train import compute_evaluation_matrix

val_dir = os.path.join(ROOT_DIR, "ml", "dataset", "tomato", "val")
classes = sorted(os.listdir(val_dir))

tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])
val_ds = datasets.ImageFolder(val_dir, transform=tf)
val_loader = torch.utils.data.DataLoader(val_ds, batch_size=64, shuffle=False)

model = TomatoDenseNet121(num_classes=len(classes), pretrained=False)
model_path = os.path.join(ROOT_DIR, "ml", "models", "tomato_densenet121.pt")
model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
model.eval()

targets, preds = [], []
with torch.no_grad():
    for x, y in val_loader:
        out = model(x)
        targets.extend(y.numpy().tolist())
        preds.extend(out.argmax(dim=1).numpy().tolist())

metrics = compute_evaluation_matrix(targets, preds, classes)
metrics["model_architecture"] = "DenseNet-121 Pretrained Transfer Learning"
metrics["total_validation_samples"] = len(val_ds)
metrics["best_weights_path"] = model_path

metrics_file = os.path.join(ROOT_DIR, "ml", "models", "densenet_metrics.json")
with open(metrics_file, "w") as f:
    json.dump(metrics, f, indent=2)

acc = metrics["overall_accuracy"] * 100
f1 = metrics["macro_f1"] * 100
print(f"DenseNet-121 Evaluation Complete!")
print(f"Overall Accuracy: {acc:.2f}%")
print(f"Macro F1 Score:   {f1:.2f}%")

