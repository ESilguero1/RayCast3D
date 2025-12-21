/* camera.c
 * Camera state and control functions
 */

#include <math.h>
#include "camera.h"
#include "graphics.h"
#include "../utils/fastmath.h"

// Camera state (owned by this module)
static Camera camera = {
    .posX = 12.0,
    .posY = 12.0,
    .dirX = -1.0,
    .dirY = 0.0,
    .planeX = 0.0,
    .planeY = 0.66
};

void Camera_SetPosition(double x, double y) {
    camera.posX = x;
    camera.posY = y;
}

void Camera_SetDirection(double dirX, double dirY) {
    // Normalize direction vector
    double len = sqrt(dirX * dirX + dirY * dirY);
    if (len > 0.0001) {
        camera.dirX = dirX / len;
        camera.dirY = dirY / len;
    }

    // Calculate perpendicular camera plane with FOV ratio 0.66
    // Plane is perpendicular to direction: rotate 90 degrees
    camera.planeX = -camera.dirY * 0.66;
    camera.planeY = camera.dirX * 0.66;
}

void Camera_GetDirection(double* dirX, double* dirY) {
    *dirX = camera.dirX;
    *dirY = camera.dirY;
}

void Camera_Move(double forward, double strafe) {
    // Move forward/backward along direction vector
    double newX = camera.posX + camera.dirX * forward;
    double newY = camera.posY + camera.dirY * forward;

    // Strafe (move perpendicular to direction)
    newX += camera.planeX * strafe;
    newY += camera.planeY * strafe;

    // Simple collision detection - only move if not hitting a wall
    if (worldMap[(int)newX][(int)camera.posY] == 0) {
        camera.posX = newX;
    }
    if (worldMap[(int)camera.posX][(int)newY] == 0) {
        camera.posY = newY;
    }
}

void Camera_Rotate(double degrees) {
    double radians = degrees * DEG_TO_RAD;
    double cosA = fast_cos(radians);
    double sinA = fast_sin(radians);

    // Rotate direction vector
    double oldDirX = camera.dirX;
    camera.dirX = camera.dirX * cosA - camera.dirY * sinA;
    camera.dirY = oldDirX * sinA + camera.dirY * cosA;

    // Rotate camera plane (must rotate same amount to maintain FOV)
    double oldPlaneX = camera.planeX;
    camera.planeX = camera.planeX * cosA - camera.planeY * sinA;
    camera.planeY = oldPlaneX * sinA + camera.planeY * cosA;
}

const Camera* Camera_Get(void) {
    return &camera;
}
