/**
 * @file      camera.h
 * @brief     RayCast3D Camera Module - First-person camera state and control
 *
 * @author    Elijah Silguero
 * @date      December 2025
 *
 * Manages camera position, direction, and view plane using
 * Q16.16 fixed-point math for efficient raycasting.
 */

/**
 * @defgroup Camera Camera
 * @brief First-person camera position, direction, and movement.
 *
 * The Camera module manages the player's viewpoint in the world.
 * It stores position, a normalized direction vector, and a perpendicular
 * camera plane that determines the field of view. All state is stored
 * internally as Q16.16 fixed-point, but the public API accepts doubles
 * for convenience. The direction vector is automatically re-normalized
 * after each rotation to prevent fixed-point drift.
 *
 * @note The camera does not perform collision detection. Use
 *       Map_GetValue() to check for walls before calling Camera_Move().
 *
 * @{
 */

#ifndef CAMERA_H_
#define CAMERA_H_

#include <stdint.h>
#include "../utils/fixed.h"

/*---------------------------------------------------------------------------
 * Types
 *---------------------------------------------------------------------------*/

/**
 * @brief Camera state structure (all values in Q16.16 fixed-point).
 *
 * Contains the player's position in the tile grid, a unit-length
 * direction vector indicating where the camera faces, and a camera
 * plane vector perpendicular to the direction that defines the
 * field of view. The plane's magnitude controls the FOV width
 * (default 0.66, giving roughly a 66-degree horizontal FOV).
 *
 * Access via Camera_Get(). Do not modify directly — use the
 * Camera_Set / Camera_Move / Camera_Rotate functions instead.
 */
typedef struct {
    fixed_t posX;    /**< World X position (column, in tile coordinates) */
    fixed_t posY;    /**< World Y position (row, in tile coordinates) */
    fixed_t posZ;    /**< Vertical position in world units, Q16.16 (0.5 = eye level, 0 = floor, 1 = ceiling) */
    fixed_t dirX;    /**< Direction vector X component (unit length) */
    fixed_t dirY;    /**< Direction vector Y component (unit length) */
    fixed_t planeX;  /**< Camera plane X (perpendicular to direction, controls FOV) */
    fixed_t planeY;  /**< Camera plane Y (perpendicular to direction, controls FOV) */
} Camera;

/*---------------------------------------------------------------------------
 * Camera Control Functions
 * Accept double for API convenience, convert to fixed-point internally
 *---------------------------------------------------------------------------*/

/**
 * @brief Set camera world position.
 *
 * Places the camera at the given tile coordinates. Coordinates correspond
 * to the map grid — for example, (12.5, 8.0) places the camera at the
 * center of column 12, top edge of row 8.
 *
 * @param x  World X coordinate (column)
 * @param y  World Y coordinate (row)
 */
void Camera_SetPosition(double x, double y);

/**
 * @brief Set camera facing direction.
 *
 * The vector (dirX, dirY) is normalized internally, so any non-zero
 * magnitude is acceptable. The camera plane (FOV) is recalculated
 * automatically to stay perpendicular to the new direction.
 *
 * @param dirX  Direction vector X component
 * @param dirY  Direction vector Y component
 */
void Camera_SetDirection(double dirX, double dirY);

/**
 * @brief Get the current camera direction as doubles.
 *
 * Useful for computing movement vectors or performing collision
 * checks before calling Camera_Move().
 *
 * @param[out] dirX  Pointer to receive direction X component
 * @param[out] dirY  Pointer to receive direction Y component
 */
void Camera_GetDirection(double* dirX, double* dirY);

/**
 * @brief Move camera relative to its facing direction.
 *
 * Forward/backward movement is along the direction vector. Strafing
 * is along the camera plane (perpendicular to direction). No collision
 * detection is performed — check Map_GetValue() before calling.
 *
 * @param forward  Movement along direction (positive = forward, negative = backward)
 * @param strafe   Movement perpendicular to direction (positive = right, negative = left)
 */
void Camera_Move(double forward, double strafe);

/**
 * @brief Rotate camera by a specified angle.
 *
 * Rotates the direction vector and recalculates the camera plane.
 * The direction vector is re-normalized after rotation to prevent
 * fixed-point precision drift.
 *
 * @param degrees  Rotation angle in degrees (positive = clockwise)
 */
void Camera_Rotate(double degrees);

/**
 * @brief Set camera vertical elevation (Z position).
 *
 * Controls the camera's height in the world. The default elevation
 * of 0.5 places the viewpoint at eye level (midway between floor and
 * ceiling). Increasing it simulates jumping; decreasing it simulates
 * crouching. The lower bound is clamped to 0.02 to prevent floor
 * distance math from collapsing to zero.
 *
 * When the camera elevation changes, walls shift vertically on screen
 * in a perspective-correct way (nearby walls shift more than distant
 * ones). Floor and ceiling distances are also adjusted so textured
 * surfaces remain consistent.
 *
 * Values above 1.0 are allowed and work correctly when no ceiling
 * texture is active (solid sky color). If a ceiling texture is
 * enabled, keep posZ below 1.0 to avoid rendering artifacts.
 *
 * @param z  Height in world units (0.0 = floor, 0.5 = eye level, 1.0 = ceiling)
 */
void Camera_SetElevation(double z);

/**
 * @brief Get the current camera elevation.
 * @return Current Z position as a double (0.5 = default eye level)
 */
double Camera_GetElevation(void);

/**
 * @brief Get read-only access to the full camera state.
 *
 * Returns a pointer to the internal Camera struct containing position,
 * direction, and camera plane in Q16.16 fixed-point. The pointer remains
 * valid until the next Camera_* call.
 *
 * @return Pointer to the internal Camera structure
 */
const Camera* Camera_Get(void);

#endif /* CAMERA_H_ */
