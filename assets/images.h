#ifndef IMAGES_H_
#define IMAGES_H_

#include <stdint.h>

// Sprite image structure - contains pointer, dimensions, and transparent color
typedef struct {
    const uint16_t* data;
    int width;
    int height;
    uint16_t transparent;  // Auto-detected transparent color
} SpriteImage;

// Clean, user-friendly macros (PRIMARY - use these!)
// No need to specify dimensions or transparent color - all auto-detected!
#define AddSprite(x, y, sprite, scale) \
    Sprite_Add(x, y, (sprite).data, (sprite).width, (sprite).height, scale, (sprite).transparent)

#define AddFGSprite(sprite, x, y, scale) \
    Graphics_ForegroundSprite((sprite).data, x, y, (sprite).width, (sprite).height, scale, (sprite).transparent)

#endif /* IMAGES_H_ */