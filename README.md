# litex-primer25k

Experiments with LiteX/Migen on the Sipeed Tang Primer 25K FPGA board
(`GW5A-LV25MG121NC1/I0`). The design uses a VexRiscv softcore, optional SDRAM,
PMOD LEDs/buttons, and a two-digit seven-segment display peripheral.

## SoC

The LiteX target is [sipeed_tang_primer_25k.py](sipeed_tang_primer_25k.py).
It defines the clock/reset generator, VexRiscv SoC, optional SDRAM controller,
GPIO peripherals, and the custom seven-segment display CSR.

Build the gateware with SDRAM support:

```sh
./sipeed_tang_primer_25k.py --with-sdram --build
```

Upload the generated SRAM bitstream:

```sh
openfpgaloader -b tangprimer25k build/sipeed_tang_primer_25k/gateware/sipeed_tang_primer_25k.fs
```

The custom display peripheral exposes two CSRs:

- `display_value`: stores the packed display value.
- `display_write`: strobes the stored value out to the display registers.

## Firmware

The standalone firmware lives in [firmware](firmware/) and builds against the
LiteX-generated headers and libraries under `build/`.

Build the firmware:

```sh
make -C firmware
```

Load the firmware over the LiteX serial bridge after the SoC bitstream is
running:

```sh
litex_term /dev/ttyUSBX --kernel firmware/firmware.bin
```

Replace `/dev/ttyUSBX` with the serial device for the board, for example
`/dev/tty.usbserial-*` on macOS.

The firmware provides a small UART console with commands such as `help`,
`reboot`, `led`, `pmod`, `helloc`, and `display <value>`. The `display`
command converts a decimal value from `0` to `99` into packed BCD, writes it
with `display_value_write()`, then strobes it with `display_write_write()`.
