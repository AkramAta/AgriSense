# Machine Learning Subsystem

Contains dataset curation, model training, INT8 quantization, and C array conversion:
- `scripts/download_dataset.py`: Fetch and filter the 8-class tomato subset from PlantVillage.
- `scripts/train.py`: 4-block compact CNN architecture with data augmentation.
- `scripts/convert_tflite.py`: Post-training INT8 quantization and C-array (`model_data.h`) generation.
- `models/`: Exported `.tflite` model and `training_metadata.json`.
