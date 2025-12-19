/* fastmath.c
 * Fast math approximations for RayCast3D
 */

#include "fastmath.h"

// Taylor series approximation for sin
// Accurate for small angles, normalized to [-PI, PI]
double fast_sin(double x) {
    // Normalize to [-PI, PI]
    while (x > PI) x -= 2 * PI;
    while (x < -PI) x += 2 * PI;

    // Taylor series: sin(x) = x - x^3/6 + x^5/120 - x^7/5040
    double x2 = x * x;
    double x3 = x2 * x;
    double x5 = x3 * x2;
    double x7 = x5 * x2;

    return x - (x3 / 6.0) + (x5 / 120.0) - (x7 / 5040.0);
}

// cos(x) = sin(x + PI/2)
double fast_cos(double x) {
    return fast_sin(x + PI / 2.0);
}
