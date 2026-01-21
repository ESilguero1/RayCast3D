/* camera.h
 * RayCast3D Camera Module
 * First-person camera state and control
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Manages camera position, direction, and view plane using
 * Q16.16 fixed-point math for efficient raycasting.
 */

#ifndef CAMERA_H_
#define CAMERA_H_

#include <stdint.h>
#include "../utils/fixed.h"

/*---------------------------------------------------------------------------
 * Types
 *---------------------------------------------------------------------------*/

/* Camera state structure (all values in Q16.16 fixed-point) */
typedef struct {
    fixed_t posX;    /* World X position */
    fixed_t posY;    /* World Y position */
    fixed_t dirX;    /* Direction vector X component */
    fixed_t dirY;    /* Direction vector Y component */
    fixed_t planeX;  /* Camera plane X (perpendicular to direction) */
    fixed_t planeY;  /* Camera plane Y (perpendicular to direction) */
} Camera;

/*---------------------------------------------------------------------------
 * Camera Control Functions
 * Accept double for API convenience, convert to fixed-point internally
 *---------------------------------------------------------------------------*/

/* Set camera world position
 * Inputs: x, y - world coordinates */
void Camera_SetPosition(double x, double y);

/* Set camera facing direction (will be normalized)
 * Inputs: dirX, dirY - direction vector components */
void Camera_SetDirection(double dirX, double dirY);

/* Get current camera direction
 * Outputs: dirX, dirY - pointers to receive direction vector */
void Camera_GetDirection(double* dirX, double* dirY);

/* Move camera relative to its facing direction
 * Inputs: forward - movement along direction (positive = forward)
 *         strafe - movement perpendicular (positive = right) */
void Camera_Move(double forward, double strafe);

/* Rotate camera by specified angle
 * Inputs: degrees - rotation angle (positive = clockwise) */
void Camera_Rotate(double degrees);

/* Get read-only access to camera state
 * Returns: pointer to internal camera structure */
const Camera* Camera_Get(void);

#endif /* CAMERA_H_ */
