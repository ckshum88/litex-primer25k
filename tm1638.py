from migen import *
from litex.soc.interconnect.csr import *

class TM1638(Module, AutoCSR):
    def __init__(self, platform, pads, clk_divider=50):
        # 1. Memory-Mapped Registers remain exactly the same
        self.digits_0_3 = CSRStorage(32, description="Packed control for Digits 0-3")
        self.digits_4_7 = CSRStorage(32, description="Packed control for Digits 4-7")
        self.led_data   = CSRStorage(8,  description="8 Discrete LEDs bitmask")
        self.buttons    = CSRStatus(32,  description="Read-only matrix keyboard status")

        platform.add_source("tm1638_hw_ctrl.v")

        # 2. Flatten and concatenate the two 32-bit registers into a single 64-bit Migen signal
        # Migen's Cat() joins components starting from the LSB up to the MSB
        digit_data_flat_sig = Signal(64)
        self.comb += digit_data_flat_sig.eq(Cat(self.digits_0_3.storage, self.digits_4_7.storage))

        # 3. Connect to the modified Verilog module using the unified flat port
        self.specials += Instance("tm1638_hw_ctrl",
            p_CLK_DIVIDER = clk_divider,
            
            i_clk         = ClockSignal("sys"),
            i_rst         = ResetSignal("sys"), 
            
            # Map the clean flat 64-bit vector pin
            i_digit_data_flat = digit_data_flat_sig,
            
            i_led_data    = self.led_data.storage,
            o_buttons_out = self.buttons.status,
            
            o_tm_stb      = pads.stb,
            o_tm_clk      = pads.clk,
            io_tm_dio     = pads.dio
        )
