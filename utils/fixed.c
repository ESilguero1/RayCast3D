/* fixed.c
 * RayCast3D Fixed-Point Math Library
 * Lookup tables and utility functions
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507
 *
 * Contains precomputed sine and reciprocal lookup tables
 * for fast fixed-point trigonometry and division.
 */

#include "fixed.h"

// Sine lookup table for 0 to 90 degrees (256 entries)
// Values are Q16.16 fixed-point, computed as sin(i * 90 / 255) * 65536
// We only store 0-90 degrees and use symmetry for other quadrants
const fixed_t sin_table[SIN_TABLE_SIZE] = {
    0, 402, 804, 1206, 1608, 2010, 2412, 2814,
    3216, 3617, 4019, 4420, 4821, 5222, 5623, 6023,
    6424, 6824, 7224, 7623, 8022, 8421, 8820, 9218,
    9616, 10014, 10411, 10808, 11204, 11600, 11996, 12391,
    12785, 13180, 13573, 13966, 14359, 14751, 15143, 15534,
    15924, 16314, 16703, 17091, 17479, 17867, 18253, 18639,
    19024, 19409, 19792, 20175, 20557, 20939, 21320, 21699,
    22078, 22457, 22834, 23210, 23586, 23961, 24335, 24708,
    25080, 25451, 25821, 26190, 26558, 26925, 27291, 27656,
    28020, 28383, 28745, 29106, 29466, 29824, 30182, 30538,
    30893, 31248, 31600, 31952, 32303, 32652, 33000, 33347,
    33692, 34037, 34380, 34721, 35062, 35401, 35738, 36075,
    36410, 36744, 37076, 37407, 37736, 38064, 38391, 38716,
    39040, 39362, 39683, 40002, 40320, 40636, 40951, 41264,
    41576, 41886, 42194, 42501, 42806, 43110, 43412, 43713,
    44011, 44308, 44604, 44898, 45190, 45480, 45769, 46056,
    46341, 46624, 46906, 47186, 47464, 47741, 48015, 48288,
    48559, 48828, 49095, 49361, 49624, 49886, 50146, 50404,
    50660, 50914, 51166, 51417, 51665, 51911, 52156, 52398,
    52639, 52878, 53114, 53349, 53581, 53812, 54040, 54267,
    54491, 54714, 54934, 55152, 55368, 55582, 55794, 56004,
    56212, 56418, 56621, 56823, 57022, 57219, 57414, 57607,
    57798, 57986, 58172, 58356, 58538, 58718, 58896, 59071,
    59244, 59415, 59583, 59750, 59914, 60075, 60235, 60392,
    60547, 60700, 60851, 60999, 61145, 61288, 61429, 61568,
    61705, 61839, 61971, 62101, 62228, 62353, 62476, 62596,
    62714, 62830, 62943, 63054, 63162, 63268, 63372, 63473,
    63572, 63668, 63763, 63854, 63944, 64031, 64115, 64197,
    64277, 64354, 64429, 64501, 64571, 64639, 64704, 64766,
    64827, 64884, 64940, 64993, 65043, 65091, 65137, 65180,
    65220, 65259, 65294, 65328, 65358, 65387, 65413, 65436,
    65457, 65476, 65492, 65505, 65516, 65525, 65531, 65535
};

// Reciprocal lookup table for fast division
// Maps values from 0.25 to 4.0 (in steps) to their reciprocals
// Index 0 = 1/0.25 = 4.0, Index 255 = 1/4.0 = 0.25
// Stored as Q16.16: recip_table[i] = 65536 / (0.25 + i * (4.0 - 0.25) / 255)
const fixed_t recip_table[RECIP_TABLE_SIZE] = {
    262144, 259553, 257018, 254538, 252110, 249734, 247407, 245129,
    242897, 240712, 238570, 236472, 234416, 232401, 230425, 228489,
    226590, 224728, 222901, 221110, 219352, 217628, 215936, 214276,
    212647, 211048, 209479, 207939, 206427, 204943, 203486, 202055,
    200651, 199271, 197917, 196586, 195279, 193996, 192734, 191495,
    190278, 189082, 187907, 186753, 185618, 184503, 183407, 182330,
    181271, 180231, 179207, 178201, 177212, 176239, 175283, 174342,
    173417, 172507, 171612, 170731, 169865, 169012, 168173, 167348,
    166535, 165736, 164949, 164174, 163412, 162661, 161922, 161195,
    160479, 159774, 159079, 158396, 157722, 157059, 156406, 155763,
    155129, 154505, 153890, 153285, 152688, 152100, 151521, 150950,
    150387, 149833, 149286, 148748, 148217, 147693, 147177, 146668,
    146166, 145671, 145183, 144702, 144227, 143759, 143297, 142841,
    142391, 141948, 141510, 141078, 140652, 140231, 139816, 139406,
    139001, 138602, 138207, 137818, 137433, 137053, 136678, 136308,
    135942, 135580, 135223, 134870, 134521, 134177, 133837, 133500,
    133168, 132839, 132514, 132193, 131876, 131562, 131252, 130945,
    130642, 130342, 130046, 129753, 129463, 129176, 128893, 128612,
    128335, 128061, 127789, 127521, 127255, 126993, 126733, 126476,
    126221, 125970, 125721, 125474, 125230, 124989, 124750, 124514,
    124280, 124049, 123820, 123593, 123369, 123147, 122927, 122710,
    122495, 122282, 122071, 121862, 121656, 121451, 121249, 121048,
    120850, 120654, 120459, 120267, 120076, 119888, 119701, 119516,
    119333, 119152, 118972, 118795, 118619, 118445, 118272, 118102,
    117933, 117766, 117600, 117436, 117274, 117113, 116954, 116796,
    116640, 116486, 116333, 116181, 116031, 115883, 115736, 115590,
    115446, 115303, 115162, 115022, 114883, 114746, 114610, 114475,
    114342, 114210, 114079, 113950, 113822, 113695, 113569, 113445,
    113322, 113200, 113079, 112959, 112841, 112724, 112608, 112493,
    112379, 112266, 112155, 112044, 111935, 111826, 111719, 111613,
    111508, 111404, 111300, 111198, 111097, 110997, 110898, 110800,
    110703, 110607, 110511, 110417, 110324, 110231, 110140, 110049
};

void Fixed_Init(void) {
    // Tables are const, no runtime initialization needed
    // This function exists for future extensibility
}

// Fast sine using lookup table
// Input: angle in fixed-point radians
// Output: sine value in fixed-point (-1.0 to 1.0 range)
fixed_t fixed_sin(fixed_t angle) {
    // Normalize angle to [0, 2*PI)
    while (angle < 0) angle += FIXED_2PI;
    while (angle >= FIXED_2PI) angle -= FIXED_2PI;

    // Determine quadrant and get table index
    // Each quadrant is PI/2 = 102944 in fixed-point
    int quadrant = (angle * 4) / FIXED_2PI;  // 0-3
    fixed_t phase = angle - (quadrant * FIXED_PI_HALF);

    // Scale phase to table index (0-255)
    int index = (phase * (SIN_TABLE_SIZE - 1)) / FIXED_PI_HALF;
    if (index < 0) index = 0;
    if (index >= SIN_TABLE_SIZE) index = SIN_TABLE_SIZE - 1;

    fixed_t value;
    switch (quadrant) {
        case 0:  // 0 to PI/2: sin increases 0 to 1
            value = sin_table[index];
            break;
        case 1:  // PI/2 to PI: sin decreases 1 to 0
            value = sin_table[SIN_TABLE_SIZE - 1 - index];
            break;
        case 2:  // PI to 3*PI/2: sin decreases 0 to -1
            value = -sin_table[index];
            break;
        case 3:  // 3*PI/2 to 2*PI: sin increases -1 to 0
        default:
            value = -sin_table[SIN_TABLE_SIZE - 1 - index];
            break;
    }

    return value;
}

// Fast cosine: cos(x) = sin(x + PI/2)
fixed_t fixed_cos(fixed_t angle) {
    return fixed_sin(angle + FIXED_PI_HALF);
}

// Fast reciprocal for values in range ~0.25 to 4.0
// Returns FIXED_LARGE for values too close to zero
fixed_t fixed_recip(fixed_t x) {
    if (x == 0) return FIXED_LARGE;

    int negative = 0;
    if (x < 0) {
        negative = 1;
        x = -x;
    }

    // Table covers 0.25 to 4.0 (16384 to 262144 in Q16.16)
    // Values outside this range need special handling
    if (x < 16384) {
        // x < 0.25: result would be > 4.0, use division
        fixed_t result = fixed_div(FIXED_ONE, x);
        return negative ? -result : result;
    }

    if (x > 262144) {
        // x > 4.0: result would be < 0.25, use scaled lookup
        // For x in range 4-32, divide x by 8, lookup, then divide result by 8
        if (x <= 2097152) {  // x <= 32.0
            fixed_t scaled = x >> 3;  // Divide by 8
            int index = ((scaled - 16384) * (RECIP_TABLE_SIZE - 1)) / (262144 - 16384);
            if (index < 0) index = 0;
            if (index >= RECIP_TABLE_SIZE) index = RECIP_TABLE_SIZE - 1;
            fixed_t result = recip_table[index] >> 3;  // Divide result by 8
            return negative ? -result : result;
        }
        // x > 32: very small result, use division
        fixed_t result = fixed_div(FIXED_ONE, x);
        return negative ? -result : result;
    }

    // Map x from [0.25, 4.0] to index [0, 255]
    int index = ((x - 16384) * (RECIP_TABLE_SIZE - 1)) / (262144 - 16384);
    if (index < 0) index = 0;
    if (index >= RECIP_TABLE_SIZE) index = RECIP_TABLE_SIZE - 1;

    fixed_t result = recip_table[index];
    return negative ? -result : result;
}

// Reciprocal for larger values (used in raycasting for perpWallDist)
// Handles the range needed for SCREEN_HEIGHT / perpWallDist calculation
fixed_t fixed_recip_large(fixed_t x) {
    if (x == 0) return FIXED_LARGE;

    // Guard against near-zero values that would overflow int32 when computing reciprocal
    // If |x| < 256 (~0.004 in fixed-point), then 1/x > 256 which overflows Q16.16
    // This prevents the "random brown vertical line" bug in raycasting
    if (x > -256 && x < 256) return (x >= 0) ? FIXED_LARGE : -FIXED_LARGE;

    // For raycasting, we typically need 1/x where x is 0.1 to 32+
    // Use division for accuracy in the critical path
    return fixed_div(FIXED_ONE, x);
}

// Fast fixed-point square root using Newton-Raphson iteration
// Input: x in Q16.16 format (must be non-negative)
// Output: sqrt(x) in Q16.16 format
fixed_t fixed_sqrt(fixed_t x) {
    if (x <= 0) return 0;

    // Initial guess: shift right by 8 (approximate sqrt by halving exponent)
    // For Q16.16, this gives a reasonable starting point
    fixed_t guess = x;

    // Find a good initial guess by bit-shifting
    // Count leading zeros and divide exponent by 2
    if (x >= (16 << 16)) {
        guess = 4 << 16;  // sqrt(16) = 4
    } else if (x >= (4 << 16)) {
        guess = 2 << 16;  // sqrt(4) = 2
    } else if (x >= (1 << 16)) {
        guess = 1 << 16;  // sqrt(1) = 1
    } else if (x >= (1 << 14)) {
        guess = 1 << 15;  // sqrt(0.25) = 0.5
    } else {
        guess = 1 << 14;  // Small values
    }

    // Newton-Raphson: x_new = (x_old + n/x_old) / 2
    // 4 iterations is usually enough for Q16.16 precision
    guess = (guess + fixed_div(x, guess)) >> 1;
    guess = (guess + fixed_div(x, guess)) >> 1;
    guess = (guess + fixed_div(x, guess)) >> 1;
    guess = (guess + fixed_div(x, guess)) >> 1;

    return guess;
}
