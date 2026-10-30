# AgriSense Machine Learning Dataset & Quantization Specifications

## 1. PlantVillage Tomato Subset Overview

The AgriSense vision model is trained on the curated 8-class tomato foliar pathology subset from the PlantVillage dataset:

| Index | Class Identifier | Pathogen Type | Primary Foliar Symptoms |
|:------|:-----------------|:--------------|:------------------------|
| **0** | `Tomato___Bacterial_spot` | Bacterium (*Xanthomonas*) | Small, water-soaked dark brown spots with chlorotic yellow halos. |
| **1** | `Tomato___Early_blight` | Fungus (*Alternaria solani*) | Concentric target-board rings on lower mature foliage. |
| **2** | `Tomato___Late_blight` | Oomycete (*Phytophthora infestans*) | Large water-soaked necrotic lesions with white underleaf sporulation. |
| **3** | `Tomato___Leaf_Mold` | Fungus (*Passalora fulva*) | Pale chlorotic spots on top leaf surface; olive-green velvety mold below. |
| **4** | `Tomato___Septoria_leaf_spot` | Fungus (*Septoria lycopersici*) | Circular greyish-white lesions (1-3mm) with distinct dark margins and black pycnidia. |
| **5** | `Tomato___Spider_mites_Two_spotted_spider_mite` | Arachnid (*Tetranychus urticae*) | Fine yellow-white stippling and webbing under hot, dry conditions. |
| **6** | `Tomato___Target_Spot` | Fungus (*Corynespora casiicola*) | Dark brown circular lesions with concentric rings across the entire canopy. |
| **7** | `Tomato___healthy` | Healthy Control | Uniform green chlorophyl, intact margins, zero necrotic spots. |

---

## 2. Preprocessing & Data Augmentation Pipeline

Images are resized to $96 \times 96 \times 3$ RGB to match the edge microcontroller input tensor constraints.

```
Raw Image (Any resolution)
    │
    ▼
Lanczos / Bilinear Resizing -> (96 x 96 RGB)
    │
    ▼
Data Augmentations (Train Split Only):
  - RandomHorizontalFlip(p=0.5)
  - RandomVerticalFlip(p=0.2)
  - RandomRotation(degrees=15)
  - ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15)
    │
    ▼
Float Normalization -> [0.0, 1.0]
    │
    ▼
INT8 Quantization Calibration
```

---

## 3. Post-Training INT8 Full-Integer Quantization

To enable zero-dynamic-allocation execution on the ESP32-CAM and fast CPU evaluation in AWS Lambda, the PyTorch model is post-training quantized to 8-bit integers using a representative calibration dataset.

### Quantization Formulas

1. **Affine Activation Quantization (Asymmetric):**
   $$S = \frac{\max(x) - \min(x)}{q_{\max} - q_{\min}} = \frac{\max(x) - \min(x)}{255}$$
   $$Z = \text{round}\left( q_{\min} - \frac{\min(x)}{S} \right) = \text{round}\left( -128 - \frac{\min(x)}{S} \right)$$
   $$q = \text{clip}\left( \text{round}\left( \frac{x}{S} \right) + Z, -128, 127 \right)$$

2. **Symmetric Weight Quantization (Per-Tensor):**
   $$S_w = \frac{\max(|W|)}{127.0}$$
   $$Z_w = 0$$
   $$W_{\text{int8}} = \text{clip}\left( \text{round}\left( \frac{W}{S_w} \right), -127, 127 \right)$$

3. **Bias Quantization (INT32):**
   $$S_b = S_{\text{input}} \times S_w$$
   $$B_{\text{int32}} = \text{round}\left( \frac{B}{S_b} \right)$$

### Model Artifact Metrics

- **Parameter Count:** 61,032 weights and biases (~61K parameters)
- **Original FP32 Size:** ~245 KB
- **Quantized INT8 TFLite Model:** ~64.8 KB (73.5% footprint reduction)
- **PSRAM Working Arena:** ~250 KB
