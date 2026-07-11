from migen import *
from tick import Tick
from litex.soc.interconnect.csr import *

# _SevenSegmentDisplay -----------------------------------------------------------------------------

class _SevenSegmentDisplay(Module):
    def __init__(self, sys_clk_freq, cs_period=0.001):
        # Module's interface
        self.values = Array(Signal(7) for _ in range(2))  # input

        self.cs      = Signal()  # output (defaults to 1 bit)
        self.abcdefg = Signal(7) # output

        # # #

        # Create a tick every cs_period
        tick = Tick(sys_clk_freq, cs_period)
        self.submodules += tick

        # Toggle cs bit signals to alternate seven segments
        cs = Signal()
        
        # Synchronous assignment: Toggle display selection on every tick clock enable
        self.sync += [
            If(tick.ce,
                cs.eq(~cs)
            )
        ]
        
        # Combinatorial assignment for output
        self.comb += self.cs.eq(cs)

        # Map the active display to the corresponding input segments
        self.comb += Case(cs, {
            0: self.abcdefg.eq(self.values[0]),
            1: self.abcdefg.eq(self.values[1]),
        })


# SevenSegmentDisplay ------------------------------------------------------------------------------

class SevenSegmentDisplay(Module, AutoCSR):
    def __init__(self, sys_clk_freq):
        self.value = CSRStorage(16)

        self.cs      = Signal()  # output
        self.abcdefg = Signal(7) # output

        # # #

        # Create _SevenSegmentDisplay module
        display = _SevenSegmentDisplay(sys_clk_freq)
        self.submodules += display

        # Connect internal display outputs to top-level outputs and drive inputs combinationally
        self.comb += [
            self.cs.eq(display.cs),
            self.abcdefg.eq(display.abcdefg),
            
            # Driven combinationally so the internal Case statement reacts instantly
            display.values[0].eq(self.value.storage[0:7]),  # Bits 0 to 6 (7 bits)
            display.values[1].eq(self.value.storage[8:15]), # Bits 8 to 14 (7 bits)
        ]