#include <stdint.h>

#include <generated/csr.h>

#if defined(CSR_DISPLAY_BASE) || defined(CSR_TM1638_BASE)

uint32_t hex2seg(uint16_t value);
void display_hex(uint32_t value);
void display_bcd(uint32_t value);

uint32_t hex2seg(uint16_t value)
{
    // Lookup table for 0-F matching bit pattern: dp g f e d c b a
    // dp = 0 for all digits
    static const uint8_t hex_seg_table[16] = {
        0x3F, // 0: .0111111 (a,b,c,d,e,f)
        0x06, // 1: .0000110 (b,c)
        0x5B, // 2: .1011011 (a,b,d,e,g)
        0x4F, // 3: .1001111 (a,b,c,d,g)
        0x66, // 4: .1100110 (b,c,f,g)
        0x6D, // 5: .1101101 (a,c,d,f,g)
        0x7D, // 6: .1111101 (a,c,d,e,f,g)
        0x07, // 7: .0000111 (a,b,c)
        0x7F, // 8: .1111111 (a,b,c,d,e,f,g)
        0x6F, // 9: .1101111 (a,b,c,d,f,g)
        0x77, // A: .1110111 (a,b,c,e,f,g)
        0x7C, // b: .1111100 (c,d,e,f,g)
        0x39, // C: .0111001 (a,d,e,f)
        0x5E, // d: .1011110 (b,c,d,e,g)
        0x79, // E: .1111001 (a,d,e,f,g)
        0x71  // F: .1110001 (a,e,f,g)
    };

    uint32_t result = 0;

    // Extract individual nibbles (4 bits each) from the 16-bit value
    uint8_t digit0 = (value >> 12) & 0x0F; // Most significant hex digit
    uint8_t digit1 = (value >> 8)  & 0x0F;
    uint8_t digit2 = (value >> 4)  & 0x0F;
    uint8_t digit3 = value         & 0x0F; // Least significant hex digit

    // Pack mapped bytes into the 32-bit result
    result |= ((uint32_t)hex_seg_table[digit3]) << 24;
    result |= ((uint32_t)hex_seg_table[digit2]) << 16;
    result |= ((uint32_t)hex_seg_table[digit1]) << 8;
    result |= ((uint32_t)hex_seg_table[digit0]);

    return result;
}

void display_hex(uint32_t value)
{
#ifdef CSR_DISPLAY_BASE
    	display_value_write(hex2seg((value & 0xff) << 8) );
#endif
#ifdef CSR_TM1638_BASE
       	tm1638_digits_0_3_write(hex2seg(value >> 16));
    	tm1638_digits_4_7_write(hex2seg(value & 0xffff));
#endif
}

void display_bcd(uint32_t value)
{
    if (value > 99999999) {
        value = 0xFFFFFFFF; // Error indicator
    }
    uint32_t bcd_result = 0;
    // Process all 8 possible digits from right (LSB) to left (MSB)
    for (int i = 0; i < 8; i++) {
        // Extract the lowest decimal digit
        uint32_t digit = value % 10;
        
        // Shift the digit into its corresponding 4-bit slot and combine
        bcd_result |= (digit << (i * 4));
        
        // Move to the next decimal digit
        value /= 10;
    }
    display_hex(bcd_result);
}


#endif
