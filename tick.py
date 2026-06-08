from migen import *

# Goals:
# - understand Migen's Modules/IOs
# - understand Migen's syntax
# - simulate a module

# Tick ---------------------------------------------------------------------------------------------

class Tick(Module):
    def __init__(self, sys_clk_freq, period):
        # Module's interface
        self.enable = Signal(reset=1) # input
        self.ce     = Signal()        # output

        # # #

        counter_preload = int(period*sys_clk_freq - 1)
        counter = Signal(max=int(period*sys_clk_freq - 1))

        # Combinatorial assignments
        self.comb += self.ce.eq(counter == 0)

        # Synchronous assignments
        self.sync += [
            If(~self.enable | self.ce,
                counter.eq(counter_preload)
            ).Else(
                counter.eq(counter - 1)
            )
        ]
