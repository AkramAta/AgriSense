/**
 * Host-Side C++ Unit Tests for AgriSense Vision Logic
 * Tests RGB565 decoding, INT8 quantization, downsampling, and dequantization.
 */

#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>
#include "../vision_node/vision_logic.h"

using namespace agrisense;

void test_rgb565_decoding() {
    std::cout << "[TEST] Running test_rgb565_decoding..." << std::endl;
    uint8_t r, g, b;

    // Pure Red: 0xF800 -> high=0xF8, low=0x00
    decodeRgb565(0xF8, 0x00, r, g, b);
    assert(r >= 250);
    assert(g == 0);
    assert(b == 0);

    // Pure Green: 0x07E0 -> high=0x07, low=0xE0
    decodeRgb565(0x07, 0xE0, r, g, b);
    assert(r == 0);
    assert(g >= 250);
    assert(b == 0);

    // Pure Blue: 0x001F -> high=0x00, low=0x1F
    decodeRgb565(0x00, 0x1F, r, g, b);
    assert(r == 0);
    assert(g == 0);
    assert(b >= 250);

    // White: 0xFFFF -> high=0xFF, low=0xFF
    decodeRgb565(0xFF, 0xFF, r, g, b);
    assert(r == 255);
    assert(g == 255);
    assert(b == 255);

    // Black: 0x0000
    decodeRgb565(0x00, 0x00, r, g, b);
    assert(r == 0 && g == 0 && b == 0);
    std::cout << "  -> PASS\n";
}

void test_quantization_and_dequantization() {
    std::cout << "[TEST] Running test_quantization_and_dequantization..." << std::endl;
    // Input scale: 1.0 / 255.0, zero point: -128
    float inScale = 1.0f / 255.0f;
    int32_t inZeroPoint = -128;

    int8_t q0 = quantizeRgbChannel(0, inScale, inZeroPoint);
    assert(q0 == -128);

    int8_t q255 = quantizeRgbChannel(255, inScale, inZeroPoint);
    assert(q255 == 127);

    int8_t q128 = quantizeRgbChannel(128, inScale, inZeroPoint);
    assert(q128 >= -1 && q128 <= 1);

    // Output dequantization
    // 8 classes: simulate logits where index 4 has highest value
    int8_t outputTensor[8] = {-128, -128, -128, -100, 100, -128, -128, -128};
    float outScale = 1.0f / 256.0f;
    int32_t outZeroPoint = -128;

    uint8_t topIdx = 0;
    float confidence = 0.0f;
    dequantizeTopPrediction(outputTensor, 8, outScale, outZeroPoint, topIdx, confidence);

    assert(topIdx == 4);
    assert(confidence > 0.85f);
    assert(!isPredictionHealthy(topIdx)); // Index 4 is Septoria leaf spot
    assert(isPredictionHealthy(7));       // Index 7 is healthy

    std::cout << "  -> PASS (Top class: " << TOMATO_CLASS_NAMES[topIdx] << ", conf: " << confidence << ")\n";
}

void test_frame_downsampling() {
    std::cout << "[TEST] Running test_frame_downsampling..." << std::endl;
    int srcW = 160;
    int srcH = 120;
    std::vector<uint8_t> srcRgb565(srcW * srcH * 2, 0);

    // Fill with green color (0x07E0)
    for (size_t i = 0; i < srcRgb565.size(); i += 2) {
        srcRgb565[i] = 0x07;
        srcRgb565[i + 1] = 0xE0;
    }

    std::vector<int8_t> dstTensor(96 * 96 * 3, 0);
    float inScale = 1.0f / 255.0f;
    int32_t inZeroPoint = -128;

    preprocessFrameRgb565ToInt8(
        srcRgb565.data(), srcW, srcH,
        dstTensor.data(), 96,
        inScale, inZeroPoint
    );

    // Check first pixel: R should be -128, G should be 127, B should be -128
    assert(dstTensor[0] == -128); // R
    assert(dstTensor[1] >= 120);  // G
    assert(dstTensor[2] == -128); // B
    std::cout << "  -> PASS\n";
}

int main() {
    std::cout << "========================================\n";
    std::cout << "AgriSense Vision Logic Test Suite\n";
    std::cout << "========================================\n";

    test_rgb565_decoding();
    test_quantization_and_dequantization();
    test_frame_downsampling();

    std::cout << "========================================\n";
    std::cout << "All Vision Logic Unit Tests PASSED!\n";
    std::cout << "========================================\n";
    return 0;
}

