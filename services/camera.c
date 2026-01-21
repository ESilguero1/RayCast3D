/* camera.c
 * RayCast3D Camera Module
 * First-person camera state and control
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Direction convention: X increases RIGHT, Y increases DOWN on GUI map.
 * (0, -1) = facing UP (toward row 0), (0, 1) = facing DOWN.
 */

#include "camera.h"
#include "graphics.h"
#include "../utils/fixed.h"

/*---------------------------------------------------------------------------
 * Private Constants
 *---------------------------------------------------------------------------*/

/* FOV ratio in Q16.16 fixed-point: 0.66 * 65536 = 43253
 * This determines the field of view width relative to height */
#define CAMERA_FOV_RATIO_FIXED 43253

/* Minimum length for direction normalization (0.01 in fixed-point) */
#define CAMERA_MIN_DIR_LENGTH 655

/*---------------------------------------------------------------------------
 * Private Variables
 *---------------------------------------------------------------------------*/

/* Camera state (all values in Q16.16 fixed-point) */
static Camera CameraState = {
    .posX = 12 << 16,      /* 12.0 - center of default map */
    .posY = 12 << 16,      /* 12.0 */
    .dirX = 0,             /* 0.0 */
    .dirY = -(1 << 16),    /* -1.0 (facing UP toward row 0) */
    .planeX = 43253,       /* 0.66 (perpendicular to direction) */
    .planeY = 0            /* 0.0 */
};

void Camera_SetPosition(double x, double y) {
    CameraState.posX = FLOAT_TO_FIXED(x);
    CameraState.posY = FLOAT_TO_FIXED(y);
}

void Camera_SetDirection(double dirX, double dirY) {
    // Convert to fixed-point
    fixed_t fx = FLOAT_TO_FIXED(dirX);
    fixed_t fy = FLOAT_TO_FIXED(dirY);

    // Normalize direction vector using fixed-point
    // len = sqrt(x^2 + y^2) - use integer sqrt approximation
    fixed_t lenSq = fixed_mul(fx, fx) + fixed_mul(fy, fy);

    // Fast integer square root (Newton-Raphson)
    if (lenSq > 0) {
        fixed_t len = lenSq;
        fixed_t x = lenSq;
        // 4 iterations of Newton-Raphson for sqrt
        x = (x + fixed_div(lenSq, x)) >> 1;
        x = (x + fixed_div(lenSq, x)) >> 1;
        x = (x + fixed_div(lenSq, x)) >> 1;
        x = (x + fixed_div(lenSq, x)) >> 1;
        len = x;

        if (len > CAMERA_MIN_DIR_LENGTH) {
            CameraState.dirX = fixed_div(fx, len);
            CameraState.dirY = fixed_div(fy, len);
        }
    }

    // Calculate perpendicular camera plane with FOV ratio 0.66
    // Plane is perpendicular to direction using (-y, x) rotation (90° counter-clockwise)
    CameraState.planeX = -fixed_mul(CameraState.dirY, CAMERA_FOV_RATIO_FIXED);
    CameraState.planeY = fixed_mul(CameraState.dirX, CAMERA_FOV_RATIO_FIXED);
}

void Camera_GetDirection(double* dirX, double* dirY) {
    *dirX = FIXED_TO_FLOAT(CameraState.dirX);
    *dirY = FIXED_TO_FLOAT(CameraState.dirY);
}

void Camera_Move(double forward, double strafe) {
    fixed_t fwd = FLOAT_TO_FIXED(forward);
    fixed_t str = FLOAT_TO_FIXED(strafe);

    // Move forward/backward along direction vector
    fixed_t newX = CameraState.posX + fixed_mul(CameraState.dirX, fwd);
    fixed_t newY = CameraState.posY + fixed_mul(CameraState.dirY, fwd);

    // Strafe (move perpendicular to direction)
    newX += fixed_mul(CameraState.planeX, str);
    newY += fixed_mul(CameraState.planeY, str);

    // No collision detection - up to the user!!
    CameraState.posX = newX;
    CameraState.posY = newY;
}

void Camera_Rotate(double degrees) {
    // Convert degrees to fixed-point radians (negate for correct screen-space rotation)
    fixed_t radians = FLOAT_TO_FIXED(-degrees * 3.14159265358979 / 180.0);

    // Use fixed-point sin/cos lookup
    fixed_t cosA = fixed_cos(radians);
    fixed_t sinA = fixed_sin(radians);

    // Rotate direction vector
    fixed_t oldDirX = CameraState.dirX;
    CameraState.dirX = fixed_mul(CameraState.dirX, cosA) - fixed_mul(CameraState.dirY, sinA);
    CameraState.dirY = fixed_mul(oldDirX, sinA) + fixed_mul(CameraState.dirY, cosA);

    // Re-normalize direction vector to prevent drift
    // Without this, repeated rotations cause the vector length to drift from 1.0
    fixed_t lenSq = fixed_mul(CameraState.dirX, CameraState.dirX) + fixed_mul(CameraState.dirY, CameraState.dirY);
    if (lenSq > 0 && lenSq != FIXED_ONE) {
        fixed_t len = fixed_sqrt(lenSq);
        if (len > 0) {
            CameraState.dirX = fixed_div(CameraState.dirX, len);
            CameraState.dirY = fixed_div(CameraState.dirY, len);
        }
    }

    // Recalculate plane from normalized direction (ensures perpendicularity and correct FOV)
    // Plane is perpendicular to direction using (-y, x) rotation (90° counter-clockwise)
    // This matches the initial camera state: dir=(0,-1) → plane=(0.66, 0)
    CameraState.planeX = -fixed_mul(CameraState.dirY, CAMERA_FOV_RATIO_FIXED);
    CameraState.planeY = fixed_mul(CameraState.dirX, CAMERA_FOV_RATIO_FIXED);
}

const Camera* Camera_Get(void) {
    return &CameraState;
}
