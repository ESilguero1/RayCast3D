/**
 * @file      camera.h
 * @brief     RayCast3D Camera Module - First-person camera state and control
 *
 * @author    Elijah Silguero
 * @date      December 2025
 * @hardware  MSPM0G3507 with ST7735 LCD
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

/** Camera state structure (all values in Q16.16 fixed-point) */
typedef struct {
    fixed_t posX;    /**< World X position */
    fixed_t posY;    /**< World Y position */
    fixed_t dirX;    /**< Direction vector X component */
    fixed_t dirY;    /**< Direction vector Y component */
    fixed_t planeX;  /**< Camera plane X (perpendicular to direction) */
    fixed_t planeY;  /**< Camera plane Y (perpendicular to direction) */
} Camera;

/*---------------------------------------------------------------------------
 * Camera Control Functions
 * Accept double for API convenience, convert to fixed-point internally
 *---------------------------------------------------------------------------*/

/**
 * @brief Set camera world position
 * @param x  World X coordinate
 * @param y  World Y coordinate
 */
void Camera_SetPosition(double x, double y);

/**
 * @brief Set camera facing direction (will be normalized)
 * @param dirX  Direction vector X component
 * @param dirY  Direction vector Y component
 */
void Camera_SetDirection(double dirX, double dirY);

/**
 * @brief Get current camera direction
 * @param[out] dirX  Pointer to receive direction X component
 * @param[out] dirY  Pointer to receive direction Y component
 */
void Camera_GetDirection(double* dirX, double* dirY);

/**
 * @brief Move camera relative to its facing direction
 * @param forward  Movement along direction (positive = forward)
 * @param strafe   Movement perpendicular to direction (positive = right)
 */
void Camera_Move(double forward, double strafe);

/**
 * @brief Rotate camera by specified angle
 * @param degrees  Rotation angle (positive = clockwise)
 */
void Camera_Rotate(double degrees);

/**
 * @brief Get read-only access to camera state
 * @return Pointer to internal camera structure
 */
const Camera* Camera_Get(void);

#endif /* CAMERA_H_ */
