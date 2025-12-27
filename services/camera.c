/* camera.c
 * Camera state and control functions
 * Uses fixed-point math for performance on embedded systems
 */

#include "camera.h"
#include "graphics.h"
#include "../utils/fixed.h"

// FOV ratio in fixed-point: 0.66 * 65536 = 43253
#define FIXED_FOV_RATIO 43253

// Camera state (owned by this module)
// Direction convention: X increases RIGHT, Y increases DOWN on GUI map
// (0, -1) = facing UP (toward row 0), (-1, 0) = facing LEFT (toward col 0)
// All values in Q16.16 fixed-point
static Camera camera = {
    .posX = 12 << 16,      // 12.0
    .posY = 12 << 16,      // 12.0
    .dirX = -(1 << 16),      // -1.0
    .dirY = 0,             // 0.0
    .planeX = 0,           // 0.0
    .planeY = 43253        // 0.66
};

void Camera_SetPosition(double x, double y) {
    camera.posX = FLOAT_TO_FIXED(x);
    camera.posY = FLOAT_TO_FIXED(y);
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

        if (len > 655) {  // > 0.01 in fixed-point
            camera.dirX = fixed_div(fx, len);
            camera.dirY = fixed_div(fy, len);
        }
    }

    // Calculate perpendicular camera plane with FOV ratio 0.66
    // Plane is perpendicular to direction using (y, -x) rotation (90° clockwise)
    camera.planeX = fixed_mul(camera.dirY, FIXED_FOV_RATIO);
    camera.planeY = -fixed_mul(camera.dirX, FIXED_FOV_RATIO);
}

void Camera_GetDirection(double* dirX, double* dirY) {
    *dirX = FIXED_TO_FLOAT(camera.dirX);
    *dirY = FIXED_TO_FLOAT(camera.dirY);
}

void Camera_Move(double forward, double strafe) {
    fixed_t fwd = FLOAT_TO_FIXED(forward);
    fixed_t str = FLOAT_TO_FIXED(strafe);

    // Move forward/backward along direction vector
    fixed_t newX = camera.posX + fixed_mul(camera.dirX, fwd);
    fixed_t newY = camera.posY + fixed_mul(camera.dirY, fwd);

    // Strafe (move perpendicular to direction)
    newX += fixed_mul(camera.planeX, str);
    newY += fixed_mul(camera.planeY, str);

    // No collision detection - up to the user!!
    camera.posX = newX;
    camera.posY = newY;
}

void Camera_Rotate(double degrees) {
    // Convert degrees to fixed-point radians
    fixed_t radians = FLOAT_TO_FIXED(degrees * 3.14159265358979 / 180.0);

    // Use fixed-point sin/cos lookup
    fixed_t cosA = fixed_cos(radians);
    fixed_t sinA = fixed_sin(radians);

    // Rotate direction vector
    fixed_t oldDirX = camera.dirX;
    camera.dirX = fixed_mul(camera.dirX, cosA) - fixed_mul(camera.dirY, sinA);
    camera.dirY = fixed_mul(oldDirX, sinA) + fixed_mul(camera.dirY, cosA);

    // Re-normalize direction vector to prevent drift
    // Without this, repeated rotations cause the vector length to drift from 1.0
    fixed_t lenSq = fixed_mul(camera.dirX, camera.dirX) + fixed_mul(camera.dirY, camera.dirY);
    if (lenSq > 0 && lenSq != FIXED_ONE) {
        fixed_t len = fixed_sqrt(lenSq);
        if (len > 0) {
            camera.dirX = fixed_div(camera.dirX, len);
            camera.dirY = fixed_div(camera.dirY, len);
        }
    }

    // Recalculate plane from normalized direction (ensures perpendicularity and correct FOV)
    // Plane is perpendicular to direction using (y, -x) rotation (90° clockwise)
    // This matches the initial camera state: dir=(-1,0) → plane=(0, 0.66)
    camera.planeX = fixed_mul(camera.dirY, FIXED_FOV_RATIO);
    camera.planeY = -fixed_mul(camera.dirX, FIXED_FOV_RATIO);
}

const Camera* Camera_Get(void) {
    return &camera;
}
