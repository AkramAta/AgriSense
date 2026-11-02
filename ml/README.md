# Machine Learning Subsystem - AgriSense

Contains the end-to-end machine learning pipeline for tomato foliar pathology classification:

### 1. Model Architecture & Interactive Notebooks
- **[`model.py`](model.py)**: Standalone Python module containing the `AgriSenseTomatoCNN` PyTorch model class, Keras/TensorFlow equivalent builder, layer summary table generator, and test forward pass. Run directly with `python ml/model.py`.
- **[`tomato_disease_detection.ipynb`](tomato_disease_detection.ipynb)** (also in **[`notebooks/tomato_disease_detection.ipynb`](notebooks/tomato_disease_detection.ipynb)**): Full interactive Jupyter Notebook covering EDA, data augmentation, CNN architecture, training loop, validation metrics, INT8 quantization, and C header generation.

### 2. Scripts
- `scripts/download_dataset.py`: Fetch and filter the 8-class tomato subset from PlantVillage.
- `scripts/train.py`: Full PyTorch 4-block compact CNN training loop with data augmentation.
- `scripts/convert_tflite.py`: Post-training INT8 quantization and C-array (`model_data.h`) generation.
- `scripts/export_c_array.py`: Utility to dump `.tflite` to a flat C byte array.

### 3. Exported Model Weights
- `models/tomato_cnn.pt`: PyTorch checkpoint (~249 KB, 61,032 parameters).
- `models/model_quant_int8.tflite`: INT8 quantized TFLite model (~64.8 KB).
- `models/model_data.h`: Flash-resident C byte array for ESP32 / TFLite Micro.
- `models/training_metadata.json`: Quantization scales, zero points, and input/output tensors.
- `models/eval_metrics.json`: Validation accuracy and per-class classification metrics.

