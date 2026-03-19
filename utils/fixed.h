/**
 * @file      fixed.h
 * @brief     RayCast3D Fixed-Point Math Library (Q16.16)
 *
 * @author    Elijah Silguero
 * @date      December 2025
 * @hardware  MSPM0G3507
 *
 * Range: -32768.0 to +32767.99998 with precision ~0.00002
 * Includes lookup tables for fast sin/cos and reciprocal.
 */

#ifndef FIXED_H_
#define FIXED_H_

#include <stdint.h>

/** Fixed-point type: Q16.16 format */
typedef int32_t fixed_t;

/** Number of fractional bits */
#define FIXED_SHIFT 16
/** 1.0 in fixed-point = 65536 */
#define FIXED_ONE   (1 << FIXED_SHIFT)
/** 0.5 in fixed-point = 32768 */
#define FIXED_HALF  (1 << (FIXED_SHIFT-1))

/** @name Conversion macros
 * @{ */
#define INT_TO_FIXED(x)     ((fixed_t)((x) << FIXED_SHIFT))
#define FIXED_TO_INT(x)     ((int32_t)((x) >> FIXED_SHIFT))
#define FLOAT_TO_FIXED(x)   ((fixed_t)((x) * FIXED_ONE))
#define FIXED_TO_FLOAT(x)   ((double)(x) / FIXED_ONE)
/** @} */

/** Get fractional part (for texture coordinates) */
#define FIXED_FRAC(x)       ((x) & (FIXED_ONE - 1))

/**
 * @brief Fixed-point multiplication: (a * b) >> 16
 *
 * Uses 64-bit intermediate to avoid overflow.
 */
static inline fixed_t fixed_mul(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a * b) >> FIXED_SHIFT);
}

/**
 * @brief Fixed-point division: (a << 16) / b
 *
 * Uses 64-bit intermediate to maintain precision.
 */
static inline fixed_t fixed_div(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a << FIXED_SHIFT) / b);
}

/** @brief Fast absolute value */
static inline fixed_t fixed_abs(fixed_t x) {
    return (x < 0) ? -x : x;
}

/** @brief Fixed-point floor (round toward negative infinity) */
static inline fixed_t fixed_floor(fixed_t x) {
    return x & ~(FIXED_ONE - 1);
}

/** @brief Fixed-point ceiling */
static inline fixed_t fixed_ceil(fixed_t x) {
    return (x + FIXED_ONE - 1) & ~(FIXED_ONE - 1);
}

/** @name Fixed-point constants
 * @{ */
#define FIXED_PI        205887      /**< PI * 65536 */
#define FIXED_2PI       411775      /**< 2*PI * 65536 */
#define FIXED_PI_HALF   102944      /**< PI/2 * 65536 */
#define FIXED_DEG_TO_RAD  1144      /**< (PI/180) * 65536 */
/** @} */

/** Very large value (replaces 1e30 for when ray is parallel to axis) */
#define FIXED_LARGE     0x7FFFFFFF

/** @name Lookup table sizes
 * @{ */
#define SIN_TABLE_SIZE  256         /**< 256 entries for 0-90 degrees */
#define RECIP_TABLE_SIZE 256        /**< Reciprocal table for 0.0 to ~4.0 */
/** @} */

extern const fixed_t sin_table[SIN_TABLE_SIZE];
extern const fixed_t recip_table[RECIP_TABLE_SIZE];

/**
 * @brief Fast sine using lookup table
 * @param angle  Angle in fixed-point radians
 * @return Sine value in fixed-point (-1.0 to 1.0 range)
 */
fixed_t fixed_sin(fixed_t angle);

/**
 * @brief Fast cosine using lookup table
 * @param angle  Angle in fixed-point radians
 * @return Cosine value in fixed-point (-1.0 to 1.0 range)
 */
fixed_t fixed_cos(fixed_t angle);

/**
 * @brief Fast reciprocal (1/x) using lookup table with linear interpolation
 *
 * Only valid for positive values in range ~0.004 to 4.0.
 *
 * @param x  Fixed-point value
 * @return 1/x in fixed-point
 */
fixed_t fixed_recip(fixed_t x);

/**
 * @brief Fast reciprocal for larger values (up to ~32)
 * @param x  Fixed-point value
 * @return 1/x in fixed-point
 */
fixed_t fixed_recip_large(fixed_t x);

/**
 * @brief Fast fixed-point square root using Newton-Raphson
 * @param x  Input value in Q16.16
 * @return Square root in Q16.16
 */
fixed_t fixed_sqrt(fixed_t x);

#endif /* FIXED_H_ */
