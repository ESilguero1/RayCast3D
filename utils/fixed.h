/* fixed.h
 * RayCast3D Fixed-Point Math Library
 * Q16.16 format: 16 bits integer, 16 bits fractional
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507
 *
 * Range: -32768.0 to +32767.99998 with precision ~0.00002
 * Includes lookup tables for fast sin/cos and reciprocal.
 */

#ifndef FIXED_H_
#define FIXED_H_

#include <stdint.h>

// Fixed-point type: Q16.16 format
typedef int32_t fixed_t;

// Number of fractional bits
#define FIXED_SHIFT 16
#define FIXED_ONE   (1 << FIXED_SHIFT)      // 1.0 in fixed-point = 65536
#define FIXED_HALF  (1 << (FIXED_SHIFT-1))  // 0.5 in fixed-point = 32768

// Conversion macros
#define INT_TO_FIXED(x)     ((fixed_t)((x) << FIXED_SHIFT))
#define FIXED_TO_INT(x)     ((int32_t)((x) >> FIXED_SHIFT))
#define FLOAT_TO_FIXED(x)   ((fixed_t)((x) * FIXED_ONE))
#define FIXED_TO_FLOAT(x)   ((double)(x) / FIXED_ONE)

// Get fractional part (for texture coordinates)
#define FIXED_FRAC(x)       ((x) & (FIXED_ONE - 1))

// Fixed-point multiplication: (a * b) >> 16
// Uses 64-bit intermediate to avoid overflow
static inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a * b) >> FIXED_SHIFT);
}

// Fixed-point division: (a << 16) / b
// Uses 64-bit intermediate to maintain precision
static inline fixed_t fixed_div(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a << FIXED_SHIFT) / b);
}

// Fast absolute value
static inline fixed_t fixed_abs(fixed_t x) {
    return (x < 0) ? -x : x;
}

// Fixed-point floor (round toward negative infinity)
static inline fixed_t fixed_floor(fixed_t x) {
    return x & ~(FIXED_ONE - 1);
}

// Fixed-point ceiling
static inline fixed_t fixed_ceil(fixed_t x) {
    return (x + FIXED_ONE - 1) & ~(FIXED_ONE - 1);
}

// Constants in fixed-point
#define FIXED_PI        205887      // PI * 65536 = 3.14159... * 65536
#define FIXED_2PI       411775      // 2*PI * 65536
#define FIXED_PI_HALF   102944      // PI/2 * 65536
#define FIXED_DEG_TO_RAD  1144      // (PI/180) * 65536 = 0.01745... * 65536

// Very large value (replaces 1e30 for when ray is parallel to axis)
#define FIXED_LARGE     0x7FFFFFFF  // Max positive int32

// Lookup table declarations (defined in fixed.c)
#define SIN_TABLE_SIZE  256  // 256 entries for 0-90 degrees
#define RECIP_TABLE_SIZE 256 // Reciprocal table for 0.0 to ~4.0

extern const fixed_t sin_table[SIN_TABLE_SIZE];
extern const fixed_t recip_table[RECIP_TABLE_SIZE];

// Fast sine using lookup table (input in fixed-point radians)
fixed_t fixed_sin(fixed_t angle);

// Fast cosine using lookup table
fixed_t fixed_cos(fixed_t angle);

// Fast reciprocal (1/x) using lookup table with linear interpolation
// Only valid for positive values in range ~0.004 to 4.0
fixed_t fixed_recip(fixed_t x);

// Fast reciprocal for larger values (up to ~32)
fixed_t fixed_recip_large(fixed_t x);

// Initialize lookup tables (call once at startup)
void Fixed_Init(void);

// Fast fixed-point square root using Newton-Raphson
// Input and output are both Q16.16
fixed_t fixed_sqrt(fixed_t x);

#endif /* FIXED_H_ */
