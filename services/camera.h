/* camera.h
 * Camera state and control functions
 * Uses fixed-point math for performance on embedded systems
 */

#ifndef CAMERA_H_
#define CAMERA_H_

#include <stdint.h>
#include "../utils/fixed.h"

// Camera state structure (all values in Q16.16 fixed-point)
typedef struct {
    fixed_t posX;
    fixed_t posY;
    fixed_t dirX;
    fixed_t dirY;
    fixed_t planeX;
    fixed_t planeY;
} Camera;

// Camera control functions (accept double for API compatibility, convert internally)
void Camera_SetPosition(double x, double y);
void Camera_SetDirection(double dirX, double dirY);
void Camera_GetDirection(double* dirX, double* dirY);
void Camera_Move(double forward, double strafe);
void Camera_Rotate(double degrees);
const Camera* Camera_Get(void);

#endif /* CAMERA_H_ */
