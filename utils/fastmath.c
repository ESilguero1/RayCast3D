/* fastmath.c
 * RayCast3D Fast Math Utility
 * Taylor series approximations for trigonometry
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507
 */

#include "fastmath.h"

/*---------------------------------------------------------------------------
 * Public Functions
 *---------------------------------------------------------------------------*/

double FastMath_Sin(double x) {
    /* Normalize to [-PI, PI] */
    while (x > FASTMATH_PI) {
        x -= 2 * FASTMATH_PI;
    }
    while (x < -FASTMATH_PI) {
        x += 2 * FASTMATH_PI;
    }

    /* Taylor series: sin(x) = x - x^3/6 + x^5/120 - x^7/5040 */
    double x2 = x * x;
    double x3 = x2 * x;
    double x5 = x3 * x2;
    double x7 = x5 * x2;

    return x - (x3 / 6.0) + (x5 / 120.0) - (x7 / 5040.0);
}

double FastMath_Cos(double x) {
    /* cos(x) = sin(x + PI/2) */
    return FastMath_Sin(x + FASTMATH_PI / 2.0);
}
