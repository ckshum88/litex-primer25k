#include <stdio.h>
#include <generated/csr.h>

void calc(void);
void display_sum(int);

void calc(void)
{
	uint8_t input;
    int sum;
    int value;
    uint8_t operation;
    uint8_t ready;

    printf("Set value using dip switches. Push buttons for operations: clear, add, subtract, load\n");
    printf("sum = 0\n");

    sum = 0;
    display_sum(sum);
    ready = 1;
    while( !buttons_in_read() ) {
		input = pmod_btn_in_read();
        operation = input >> 4;
        if( ready == 1 && operation > 0 ) {
            ready = 0;
            value = input & 0xf;
            switch( operation ) {
                case 8:
                    sum = 0;
                    printf("sum = 0\n");
                    break;
                case 4:
                    sum += value;
                    printf("sum + %d = %d", value, sum);
                    if( sum >= 100 ) {
                        sum %= 100;
                        printf(" (wrapped around to sum = %d)\n", sum);
                    } else printf("\n");
                    break;
                case 2:
                    sum -= value;
                    if( sum < 0 ) {
                        sum = 0;
                        printf("sum < 0 (reset to sum = 0)\n");
                    } else printf("sum - %d = %d\n", value, sum);
                    break;
                case 1:
                    sum = value;
                    printf("sum = %d\n", value);
                    break;
            }
            display_sum(sum);
        }
        else if (operation == 0) ready = 1;
		busy_wait(50);
	}
}

void display_sum(int n)
{
    uint32_t bcd = ((n / 10) << 4) | (n % 10);
    display_value_write(bcd);
    display_write_write(1);
}