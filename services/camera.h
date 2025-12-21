/* camera.h
 * Camera state and control functions
 */

#ifndef CAMERA_H_
#define CAMERA_H_

#include <stdint.h>

// Camera state structure
typedef struct {
    double posX;
    double posY;
    double dirX;
    double dirY;
    double planeX;
    double planeY;
} Camera;

// Camera control functions
void Camera_SetPosition(double x, double y);
void Camera_SetDirection(double dirX, double dirY);
void Camera_GetDirection(double* dirX, double* dirY);
void Camera_Move(double forward, double strafe);
void Camera_Rotate(double degrees);
const Camera* Camera_Get(void);

#endif /* CAMERA_H_ */
