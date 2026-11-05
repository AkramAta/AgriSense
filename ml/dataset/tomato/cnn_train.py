#!/usr/bin/env python3
"""
AgriSense - Tomato Leaf Pathology CNN Training & TFLite Quantization Pipeline
=============================================================================
Trains a convolutional neural network on the 10-class PlantVillage Tomato Dataset
and exports the trained model to both Keras format and quantized INT8 TFLite for
embedded and mobile deployment.

Dataset Classes (10):
- Tomato___Bacterial_spot
- Tomato___Early_blight
- Tomato___healthy
- Tomato___Late_blight
- Tomato___Leaf_Mold
- Tomato___Septoria_leaf_spot
- Tomato___Spider_mites Two-spotted_spider_mite
- Tomato___Target_Spot
- Tomato___Tomato_mosaic_virus
- Tomato___Tomato_Yellow_Leaf_Curl_Virus
"""

import argparse
import json
import os
import sys
import numpy as np


def build_model(input_shape=(128, 128, 3), num_classes=10):
    """Constructs the AgriSense 3-Block CNN Architecture."""
    import tensorflow as tf
    from tensorflow.keras import layers, models

    model = models.Sequential([
        layers.Input(shape=input_shape),

        # Block 1
        layers.Conv2D(32, (3, 3), padding='same', activation='relu', name='conv1'),
        layers.MaxPooling2D(pool_size=(2, 2), name='pool1'),

        # Block 2
        layers.Conv2D(16, (3, 3), padding='same', activation='relu', name='conv2'),
        layers.MaxPooling2D(pool_size=(2, 2), name='pool2'),

        # Block 3
        layers.Conv2D(8, (3, 3), padding='same', activation='relu', name='conv3'),
        layers.MaxPooling2D(pool_size=(2, 2), name='pool3'),

        # Dense Classification Head
        layers.Flatten(name='flatten'),
        layers.Dense(128, activation='relu', name='fc1'),
        layers.Dropout(0.5, name='dropout'),
        layers.Dense(num_classes, activation='softmax', name='predictions')
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model


def export_quantized_tflite(model, val_generator, output_tflite_path, num_calibration_steps=50):
    """Exports model to INT8 Quantized TFLite using a representative dataset."""
    import tensorflow as tf

    print(f"\n[AgriSense ML] Generating INT8 Quantized TFLite model -> {output_tflite_path}")

    def representative_dataset():
        batches_seen = 0
        for images, _ in val_generator:
            for i in range(images.shape[0]):
                single_img = np.expand_dims(images[i], axis=0).astype(np.float32)
                yield [single_img]
                batches_seen += 1
                if batches_seen >= num_calibration_steps:
                    return

    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    try:
        tflite_quant_model = converter.convert()
        with open(output_tflite_path, 'wb') as f:
            f.write(tflite_quant_model)
        size_kb = len(tflite_quant_model) / 1024.0
        print(f"[AgriSense ML] Quantization Success! Output footprint: {size_kb:.2f} KB")
    except Exception as e:
        print(f"[AgriSense ML] Full integer quantization fallback: {e}")
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
        converter.inference_input_type = tf.float32
        converter.inference_output_type = tf.float32
        tflite_model = converter.convert()
        with open(output_tflite_path, 'wb') as f:
            f.write(tflite_model)
        size_kb = len(tflite_model) / 1024.0
        print(f"[AgriSense ML] Saved standard TFLite model: {size_kb:.2f} KB")


def train_pipeline(args):
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
    from tensorflow.keras.preprocessing.image import ImageDataGenerator

    # Validate directory structure
    train_dir = os.path.join(args.dataset_dir, 'train')
    val_dir = os.path.join(args.dataset_dir, 'val')

    if not os.path.isdir(train_dir) or not os.path.isdir(val_dir):
        print(f"[Error] Dataset directory must contain 'train' and 'val' subfolders: {args.dataset_dir}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    img_size = (args.img_size, args.img_size)

    # Data Generators with domain-specific leaf augmentation
    print(f"[AgriSense ML] Loading training dataset from: {train_dir}")
    train_datagen = ImageDataGenerator(
        rescale=1.0 / 255.0,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True,
        rotation_range=20,
        fill_mode='nearest'
    )

    val_datagen = ImageDataGenerator(rescale=1.0 / 255.0)

    train_generator = train_datagen.flow_from_directory(
        train_dir,
        target_size=img_size,
        batch_size=args.batch_size,
        class_mode='categorical'
    )

    val_generator = val_datagen.flow_from_directory(
        val_dir,
        target_size=img_size,
        batch_size=args.batch_size,
        class_mode='categorical',
        shuffle=False
    )

    class_indices = train_generator.class_indices
    num_classes = len(class_indices)
    print(f"\n[AgriSense ML] Detected {num_classes} classes: {list(class_indices.keys())}")

    # Save class indices JSON
    class_map_file = os.path.join(args.output_dir, 'tomato_class_indices.json')
    with open(class_map_file, 'w') as f:
        json.dump(class_indices, f, indent=2)
    print(f"[AgriSense ML] Class indices written to: {class_map_file}")

    # Build and compile model
    model = build_model(input_shape=(args.img_size, args.img_size, 3), num_classes=num_classes)
    model.summary()

    # Callbacks
    best_model_path = os.path.join(args.output_dir, 'tomato_cnn_10class_best.keras')
    callbacks = [
        ModelCheckpoint(best_model_path, monitor='val_accuracy', save_best_only=True, verbose=1),
        EarlyStopping(monitor='val_loss', patience=6, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1)
    ]

    # Model Training
    print(f"\n[AgriSense ML] Beginning training for up to {args.epochs} epochs...")
    history = model.fit(
        train_generator,
        epochs=args.epochs,
        validation_data=val_generator,
        callbacks=callbacks
    )

    # Save Final Keras Model
    final_keras_path = os.path.join(args.output_dir, 'tomato_cnn_10class_final.keras')
    model.save(final_keras_path)
    print(f"\n[AgriSense ML] Trained model successfully saved to: {final_keras_path}")

    # Save weights file (replaces legacy keras_potato_trained_model_weights.h5)
    weights_path = os.path.join(args.output_dir, 'tomato_cnn_weights.h5')
    model.save_weights(weights_path)
    print(f"[AgriSense ML] Model weights saved to: {weights_path}")

    # Export INT8 Quantized TFLite model
    tflite_path = os.path.join(args.output_dir, 'tomato_cnn_10class_int8.tflite')
    export_quantized_tflite(model, val_generator, tflite_path)

    # Print final evaluation metrics
    val_loss, val_acc = model.evaluate(val_generator, verbose=0)
    print(f"\n=======================================================")
    print(f"Final Validation Loss:     {val_loss:.4f}")
    print(f"Final Validation Accuracy: {val_acc * 100:.2f}%")
    print(f"Artifacts saved in:        {args.output_dir}")
    print(f"=======================================================\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AgriSense Tomato CNN 10-Class Training Pipeline")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output = os.path.abspath(os.path.join(script_dir, "..", "models"))

    parser.add_argument('--dataset-dir', type=str, default=script_dir,
                        help="Path containing 'train' and 'val' subdirectories (default: script dir)")
    parser.add_argument('--output-dir', type=str, default=default_output,
                        help="Directory to save trained models and TFLite files")
    parser.add_argument('--epochs', type=int, default=20,
                        help="Maximum training epochs (default: 20)")
    parser.add_argument('--batch-size', type=int, default=64,
                        help="Batch size (default: 64)")
    parser.add_argument('--img-size', type=int, default=128,
                        help="Input image resolution in pixels (default: 128)")

    args = parser.parse_args()
    train_pipeline(args)
