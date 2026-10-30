#ifndef VISION_LOGIC_H_
#define VISION_LOGIC_H_

#include <cstdint>
#include <cmath>
#include <algorithm>

namespace agrisense {

// Canonical 8 Tomato Disease Classes
static const char* const TOMATO_CLASS_NAMES[8] = {
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___healthy"
};

/**
 * Decodes a big-endian RGB565 16-bit word into standard RGB888 components.
 * Format: [R4 R3 R2 R1 R0 | G5 G4 G3 G2 G1 G0 | B4 B3 B2 B1 B0]
 */
inline void decodeRgb565(uint8_t highByte, uint8_t lowByte, uint8_t& outR, uint8_t& outG, uint8_t& outB) {
    uint16_t pixel = (static_cast<uint16_t>(highByte) << 8) | static_cast<uint16_t>(lowByte);
    // 5-bit Red
    uint8_t r5 = (pixel >> 11) & 0x1F;
    outR = static_cast<uint8_t>((r5 * 527 + 23) >> 6); // Fast exact (r5 * 255) / 31

    // 6-bit Green
    uint8_t g6 = (pixel >> 5) & 0x3F;
    outG = static_cast<uint8_t>((g6 * 259 + 33) >> 6); // Fast exact (g6 * 255) / 63

    // 5-bit Blue
    uint8_t b5 = pixel & 0x1F;
    outB = static_cast<uint8_t>((b5 * 527 + 23) >> 6); // Fast exact (b5 * 255) / 31
}

/**
 * Quantizes an 8-bit channel value [0, 255] into an INT8 tensor element [-128, 127]
 * given affine quantization scale and zero point.
 */
inline int8_t quantizeRgbChannel(uint8_t val888, float scale, int32_t zeroPoint) {
    float norm = static_cast<float>(val888) / 255.0f; // Scale to [0.0, 1.0]
    float q = (norm / scale) + static_cast<float>(zeroPoint);
    int32_t rounded = static_cast<int32_t>(std::round(q));
    return static_cast<int8_t>(std::max<int32_t>(-128, std::min<int32_t>(127, rounded)));
}

/**
 * Downsamples and converts an RGB565 image buffer to a 96x96 RGB INT8 tensor.
 */
inline void preprocessFrameRgb565ToInt8(
    const uint8_t* srcBuffer,
    int srcWidth,
    int srcHeight,
    int8_t* dstTensor,
    int dstSize,
    float inputScale,
    int32_t inputZeroPoint
) {
    // Bilinear or nearest-neighbor stride sampling
    for (int dstY = 0; dstY < dstSize; ++dstY) {
        int srcY = (dstY * srcHeight) / dstSize;
        for (int dstX = 0; dstX < dstSize; ++dstX) {
            int srcX = (dstX * srcWidth) / dstSize;
            int srcIdx = (srcY * srcWidth + srcX) * 2;

            uint8_t r888, g888, b888;
            decodeRgb565(srcBuffer[srcIdx], srcBuffer[srcIdx + 1], r888, g888, b888);

            int dstIdx = (dstY * dstSize + dstX) * 3;
            dstTensor[dstIdx]     = quantizeRgbChannel(r888, inputScale, inputZeroPoint);
            dstTensor[dstIdx + 1] = quantizeRgbChannel(g888, inputScale, inputZeroPoint);
            dstTensor[dstIdx + 2] = quantizeRgbChannel(b888, inputScale, inputZeroPoint);
        }
    }
}

/**
 * Dequantizes output INT8 probabilities and finds the top predicted class index and confidence.
 */
inline void dequantizeTopPrediction(
    const int8_t* outputTensor,
    size_t numClasses,
    float outputScale,
    int32_t outputZeroPoint,
    uint8_t& outClassIndex,
    float& outConfidence
) {
    outClassIndex = 0;
    outConfidence = -1.0f;

    for (size_t i = 0; i < numClasses; ++i) {
        float prob = (static_cast<float>(outputTensor[i]) - static_cast<float>(outputZeroPoint)) * outputScale;
        prob = std::max(0.0f, std::min(1.0f, prob));
        if (prob > outConfidence) {
            outConfidence = prob;
            outClassIndex = static_cast<uint8_t>(i);
        }
    }
}

/**
 * Classifies whether a predicted class index corresponds to a healthy leaf or disease.
 */
inline bool isPredictionHealthy(uint8_t classIndex) {
    return classIndex == 7; // Tomato___healthy is index 7
}

} // namespace agrisense

#endif // VISION_LOGIC_H_

