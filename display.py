from migen import *

from tick import Tick

from litex.soc.interconnect.csr import *

# _SevenSegment ------------------------------------------------------------------------------------

class _SevenSegment(Module):
    def __init__(self):
        # Module's interface
        self.value   = value   = Signal(4)  # input
        self.abcdefg = abcdefg = Signal(7)  # output

        # # #

        # value to abcd segments dictionary.
        # Here we create a table to translate each of the 16 possible input
        # values to abdcefg segments control.
        cases = {
          0x0: abcdefg.eq(0b0111111),
          0x1: abcdefg.eq(0b0000110),
          0x2: abcdefg.eq(0b1011011),
          0x3: abcdefg.eq(0b1001111),
          0x4: abcdefg.eq(0b1100110),
          0x5: abcdefg.eq(0b1101101),
          0x6: abcdefg.eq(0b1111101),
          0x7: abcdefg.eq(0b0000111),
          0x8: abcdefg.eq(0b1111111),
          0x9: abcdefg.eq(0b1101111),
          0xa: abcdefg.eq(0b1110111),
          0xb: abcdefg.eq(0b1111100),
          0xc: abcdefg.eq(0b0111001),
          0xd: abcdefg.eq(0b1011110),
          0xe: abcdefg.eq(0b1111001),
          0xf: abcdefg.eq(0b1110001),
        }

        # Combinatorial assignment
        self.comb += Case(value, cases)

# _SevenSegmentDisplay -----------------------------------------------------------------------------

class _SevenSegmentDisplay(Module):
    def __init__(self, sys_clk_freq, cs_period=0.001):
        # Module's interface
        self.values = Array(Signal(4) for i in range(2))  # input

        self.cs      = Signal(1) # output
        self.abcdefg = Signal(7) # output

        # # #

        # Create our seven segment controller
        seven_segment = _SevenSegment()
        self.submodules += seven_segment
        self.comb += self.abcdefg.eq(seven_segment.abcdefg)

        # Create a tick every cs_period
        tick = Tick(sys_clk_freq, cs_period)
        self.submodules += tick

        # Toggle cs bit signals to alternate seven segments
        # cycle 0 : 0b0
        # cycle 1 : 0b1
        cs = Signal(1, reset=0b0)
        # Synchronous assignment
        self.sync += [
            If(tick.ce,     # At the next tick:
                cs.eq(~cs)       # toggle bit value
            )
        ]
        # Combinatorial assignment
        self.comb += self.cs.eq(cs)

        # cs to value selection.
        # Here we create a table to translate each of the 6 cs possible values
        # to input value selection.
        cases = {
            0b0 : seven_segment.value.eq(self.values[0]),
            0b1 : seven_segment.value.eq(self.values[1]),
        }
        # Combinatorial assignment
        self.comb += Case(self.cs, cases)

# SevenSegmentDisplay ------------------------------------------------------------------------------

class SevenSegmentDisplay(Module, AutoCSR):
    def __init__(self, sys_clk_freq):
        self.value = CSRStorage(8)
        self.write = CSR()

        self.cs      = Signal(1) # output
        self.abcdefg = Signal(7) # output

        # # #

        # Create _SevenSegmentDisplay module
        display = _SevenSegmentDisplay(sys_clk_freq)
        self.submodules += display # pyright: ignore[reportOperatorIssue]
        self.comb += [
            self.cs.eq(display.cs),
            self.abcdefg.eq(display.abcdefg)
        ]

        self.sync += [
            # When CPU access write CSR
            If(self.write.re,
                # Select which value to update based on sel register
                display.values[0].eq(self.value.storage[4:8]),
                display.values[1].eq(self.value.storage[0:4]),
            )
        ]
