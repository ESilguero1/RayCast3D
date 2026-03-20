/**
 * @file fixed.h
 * @brief Q16.16 fixed-point math library for RayCast3D.
 *
 * Provides fixed-point arithmetic, conversion macros, trigonometric
 * functions (via lookup table), reciprocal approximation, and square root
 * for real-time 3D rendering on the MSPM0G3507.
 *
 * Format: 16-bit integer, 16-bit fractional (Q16.16).
 * Range: -32768.0 to +32767.99998, precision ~0.00002.
 *
 * @author Elijah Silguero
 * @date   December 2025 (created), January 2026 (modified)
 */

#ifndef FIXED_H_
#define FIXED_H_

#include <stdint.h>

/**
 * @defgroup Fixed Fixed-Point Math
 * @brief Q16.16 fixed-point arithmetic, trigonometry, and utilities.
 * @{
 */

/** @brief Signed Q16.16 fixed-point type. */
typedef int32_t fixed_t;

/*---------------------------------------------------------------------------
 * Constants
 *---------------------------------------------------------------------------*/

#define FIXED_SHIFT 16                     /**< Number of fractional bits.          */
#define FIXED_ONE   (1 << FIXED_SHIFT)     /**< 1.0 in fixed-point (65536).         */
#define FIXED_HALF  (1 << (FIXED_SHIFT-1)) /**< 0.5 in fixed-point (32768).         */

#define FIXED_PI            205887      /**< pi * 65536.          */
#define FIXED_2PI           411775      /**< 2*pi * 65536.        */
#define FIXED_PI_HALF       102944      /**< pi/2 * 65536.        */
#define FIXED_DEG_TO_RAD      1144      /**< (pi/180) * 65536.    */
#define FIXED_LARGE     0x7FFFFFFF      /**< Sentinel for parallel-ray cases (INT32_MAX). */

/*---------------------------------------------------------------------------
 * Conversion Macros
 *---------------------------------------------------------------------------*/

#define INT_TO_FIXED(x)     ((fixed_t)((x) << FIXED_SHIFT))  /**< Integer  -> fixed. */
#define FIXED_TO_INT(x)     ((int32_t)((x) >> FIXED_SHIFT))  /**< Fixed    -> integer (truncates). */
#define FLOAT_TO_FIXED(x)   ((fixed_t)((x) * FIXED_ONE))     /**< Float    -> fixed. */
#define FIXED_TO_FLOAT(x)   ((double)(x) / FIXED_ONE)        /**< Fixed    -> double. */
#define FIXED_FRAC(x)       ((x) & (FIXED_ONE - 1))          /**< Fractional part (useful for texture coords). */

/*---------------------------------------------------------------------------
 * Lookup Tables
 *---------------------------------------------------------------------------*/

#define SIN_TABLE_SIZE   256  /**< Entries covering 0-90 degrees.          */
#define RECIP_TABLE_SIZE 256  /**< Reciprocal entries for ~0.004 to 4.0.   */

extern const fixed_t Fixed_SinTable[SIN_TABLE_SIZE];   /**< Quarter-wave sine LUT.  */
extern const fixed_t Fixed_RecipTable[RECIP_TABLE_SIZE]; /**< Reciprocal LUT.        */

/*---------------------------------------------------------------------------
 * Inline Arithmetic
 *---------------------------------------------------------------------------*/

/**
 * @brief Multiply two fixed-point values.
 *
 * Uses a 64-bit intermediate to avoid overflow.
 *
 * @param a First operand (Q16.16).
 * @param b Second operand (Q16.16).
 * @return  Product in Q16.16.
 */
static inline fixed_t Fixed_Mul(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a * b) >> FIXED_SHIFT);
}

/**
 * @brief Divide two fixed-point values.
 *
 * Uses a 64-bit intermediate to maintain precision.
 *
 * @param a Numerator (Q16.16).
 * @param b Denominator (Q16.16). Must not be zero.
 * @return  Quotient in Q16.16.
 */
static inline fixed_t Fixed_Div(fixed_t a, fixed_t b) {
    return (fixed_t)(((int64_t)a << FIXED_SHIFT) / b);
}

/**
 * @brief Absolute value of a fixed-point number.
 * @param x Input value (Q16.16).
 * @return  |x| in Q16.16.
 */
static inline fixed_t Fixed_Abs(fixed_t x) {
    return (x < 0) ? -x : x;
}

/**
 * @brief Floor — round toward negative infinity.
 * @param x Input value (Q16.16).
 * @return  Largest integer (in Q16.16) <= x.
 */
static inline fixed_t Fixed_Floor(fixed_t x) {
    return x & ~(FIXED_ONE - 1);
}

/**
 * @brief Ceiling — round toward positive infinity.
 * @param x Input value (Q16.16).
 * @return  Smallest integer (in Q16.16) >= x.
 */
static inline fixed_t Fixed_Ceil(fixed_t x) {
    return (x + FIXED_ONE - 1) & ~(FIXED_ONE - 1);
}

/*---------------------------------------------------------------------------
 * Trigonometric Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Fast sine via quarter-wave lookup table.
 * @param angle Angle in fixed-point radians (Q16.16).
 * @return  sin(angle) in Q16.16.
 */
fixed_t Fixed_Sin(fixed_t angle);

/**
 * @brief Fast cosine via quarter-wave lookup table.
 * @param angle Angle in fixed-point radians (Q16.16).
 * @return  cos(angle) in Q16.16.
 */
fixed_t Fixed_Cos(fixed_t angle);

/*---------------------------------------------------------------------------
 * Reciprocal Approximation
 *---------------------------------------------------------------------------*/

/**
 * @brief Fast reciprocal (1/x) with linear interpolation.
 *
 * Valid for positive values roughly in [0.004, 4.0].
 *
 * @param x Positive fixed-point value (Q16.16).
 * @return  1/x in Q16.16.
 */
fixed_t Fixed_Recip(fixed_t x);

/**
 * @brief Fast reciprocal for larger values (up to ~32).
 * @param x Positive fixed-point value (Q16.16).
 * @return  1/x in Q16.16.
 */
fixed_t Fixed_RecipLarge(fixed_t x);

/*---------------------------------------------------------------------------
 * Miscellaneous
 *---------------------------------------------------------------------------*/

/**
 * @brief Fixed-point square root (Newton-Raphson).
 * @param x Non-negative input (Q16.16).
 * @return  sqrt(x) in Q16.16.
 */
fixed_t Fixed_Sqrt(fixed_t x);

/** @} */

#endif /* FIXED_H_ */
