// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD
//
// Modified by Alfred Shum (https://github.com/ckshum88) on 11/7/2026

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>

extern void helloc(void);
extern void calc(void);
extern void display_hex(uint32_t value);
char *get_token(char **str);

/*-----------------------------------------------------------------------*/
/* Uart                                                                  */
/*-----------------------------------------------------------------------*/

static char *readstr(void)
{
	char c[2];
	static char s[64];
	static int ptr = 0;

	if(readchar_nonblock()) {
		c[0] = getchar();
		c[1] = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					fputs("\x08 \x08", stdout);
				}
				break;
			case 0x07:
				break;
			case '\r':
			case '\n':
				s[ptr] = 0x00;
				fputs("\n", stdout);
				ptr = 0;
				return s;
			default:
				if(ptr >= (sizeof(s) - 1))
					break;
				fputs(c, stdout);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}

	return NULL;
}

char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

static void prompt(void)
{
	printf("\e[92;1mlitex-firmware\e[0m> ");
}

/*-----------------------------------------------------------------------*/
/* Help                                                                  */
/*-----------------------------------------------------------------------*/

static void help(void)
{
	puts("\nLiteX minimal demo app built "__DATE__" "__TIME__"\n");
	puts("Available commands:");
	puts("help               - Show this command");
	puts("reboot             - Reboot CPU");
#ifdef CSR_LEDS_BASE
	puts("led                - Led demo");
#endif
#if defined(CSR_DISPLAY_BASE) || defined(CSR_TM1638_BASE)
	puts("display <value>    - Show hex value on seven segment display");
#endif
	puts("helloc             - Hello C");
	puts("calc               - Calculate with PMODs");
}

/*-----------------------------------------------------------------------*/
/* Commands                                                              */
/*-----------------------------------------------------------------------*/

static void reboot_cmd(void)
{
	ctrl_reset_write(1);
}

static void helloc_cmd(void)
{
	printf("Hello C demo...\n");
	helloc();
}

#ifdef CSR_LEDS_BASE
static void led_cmd(void)
{
	int i;
	printf("Led demo...\n");

	printf("Counter mode...\n");
	for(i=0; i<32; i++) {
		leds_out_write(i);
		busy_wait(100);
	}

	printf("Shift mode...\n");
	for(i=0; i<4; i++) {
		leds_out_write(1<<i);
		busy_wait(200);
	}
	for(i=0; i<4; i++) {
		leds_out_write(1<<(3-i));
		busy_wait(200);
	}

	printf("Dance mode...\n");
	for(i=0; i<4; i++) {
		leds_out_write(0x55);
		busy_wait(200);
		leds_out_write(0xaa);
		busy_wait(200);
	}
}
#endif

#if defined(CSR_DISPLAY_BASE) || defined(CSR_TM1638_BASE)
static void display_cmd(char *args)
{
	char *token;
	char *endptr;
	uint32_t value;

	printf("Display demo...\n");
	token = get_token(&args);
	if(token[0] == 0) {
		printf("Usage: display <value>\n");
		return;
	}

	value = strtoul(token, &endptr, 0);
	if((endptr == token) || (*endptr != 0) || (value > 0xffffffff)) {
		printf("Invalid display value: %s\n", token);
		printf("Usage: display <value>\n");
		return;
	}

	display_hex(value);
}

#ifdef CSR_PMOD_BTN_BASE
static void calc_cmd(void)
{
	printf("Calc demo...\n");
	calc();
}
#endif

#endif

/* Console service / Main                                                */
/*-----------------------------------------------------------------------*/

static void console_service(void)
{
	char *str;
	char *token;

	str = readstr();
	if(str == NULL) return;
	token = get_token(&str);
	if(strcmp(token, "help") == 0)
		help();
	else if(strcmp(token, "reboot") == 0)
		reboot_cmd();
	else if(strcmp(token, "helloc") == 0)
		helloc_cmd();
#ifdef CSR_LEDS_BASE
	else if(strcmp(token, "led") == 0)
		led_cmd();
#endif
#if defined(CSR_DISPLAY_BASE) || defined(CSR_TM1638_BASE)
	else if(strcmp(token, "display") == 0)
		display_cmd(str);
#ifdef CSR_PMOD_BTN_BASE
	else if(strcmp(token, "calc") == 0)
		calc_cmd();
#endif
#endif
	prompt();
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();

	help();
	prompt();

	while(1) {
		console_service();
	}

 	return 0;
}
