/* fastmath.h
 * RayCast3D Fast Math Utility
 * Taylor series approximations for trigonometry
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507
 *
 * Provides fast floating-point sin/cos using Taylor series.
 * For most rendering, use fixed.h functions instead.
 */

#ifndef FASTMATH_H_
#define FASTMATH_H_

/*---------------------------------------------------------------------------
 * Constants
 *---------------------------------------------------------------------------*/

#define FASTMATH_PI 3.14159265358979323846
#define FASTMATH_DEG_TO_RAD (FASTMATH_PI / 180.0)

/*---------------------------------------------------------------------------
 * Fast Trigonometry Functions
 *---------------------------------------------------------------------------*/

/* Fast sine using Taylor series
 * Inputs: x - angle in radians
 * Returns: approximate sine value */
double FastMath_Sin(double x);

/* Fast cosine using Taylor series
 * Inputs: x - angle in radians
 * Returns: approximate cosine value */
double FastMath_Cos(double x);

#endif /* FASTMATH_H_ */
