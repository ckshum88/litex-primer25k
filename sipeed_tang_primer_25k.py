#!/usr/bin/env python3

#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2023 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause
#
# Modified by Alfred Shum (https://github.com/ckshum88) on 7/6/2026

from migen import *

from litex.gen import *

from litex.build.io import DDROutput

from litex.soc.cores.clock.gowin_gw5a import GW5APLL
from litex.soc.integration.soc import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser
from litex.soc.cores.gpio import GPIOIn
from litex.soc.cores.video import VideoGowinHDMIPHY

from litedram.modules import AS4C32M16, W9825G6KH6
from litedram.phy import GENSDRPHY, HalfRateGENSDRPHY

from pmod_dt import SevenSegmentDisplay
from tm1638 import TM1638

from platforms import sipeed_tang_primer_25k

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, 
        with_sdram=False, 
        sdram_rate="1:2",
        with_video_pll = False,
        ):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()
        self.cd_por = ClockDomain()

        if with_sdram:
            if sdram_rate == "1:2":
                self.cd_sys2x    = ClockDomain()
                self.cd_sys2x_ps = ClockDomain()
            else:
                self.cd_sys_ps = ClockDomain()

        # # #

        # Clk/Rst
        clk50 = platform.request("clk50")
        rst = platform.request("btn_n", 0)
        self.comb += self.rst.eq(rst)

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += [
            self.cd_por.clk.eq(clk50),
            por_done.eq(por_count == 0),
        ]
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.pll = pll = GW5APLL(devicename=platform.devicename, device=platform.device)
        self.comb += pll.reset.eq(~por_done | self.rst)
        pll.register_clkin(clk50, 50e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

        # Video Clock
        if with_video_pll:
            self.cd_hdmi   = ClockDomain()
            self.cd_hdmi5x = ClockDomain()
            pll.create_clkout(self.cd_hdmi5x, 125e6, margin=1e-3)
            self.specials += Instance("CLKDIV",
                p_DIV_MODE = "5",
                i_HCLKIN   = self.cd_hdmi5x.clk,
                i_RESETN   = 1, # Disable reset signal.
                i_CALIB    = 0, # No calibration.
                o_CLKOUT   = self.cd_hdmi.clk
            )

        # SDRAM clock
        if with_sdram:
            if sdram_rate == "1:2":
                pll.create_clkout(self.cd_sys2x,    2*sys_clk_freq)
                pll.create_clkout(self.cd_sys2x_ps, 2*sys_clk_freq, phase=180)
                sdram_clk = ClockSignal("sys2x_ps")
            else:
                pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=90)
                sdram_clk = ClockSignal("sys_ps")
            self.specials += DDROutput(1, 0, platform.request("sdram_clock"), sdram_clk)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, toolchain="gowin", sys_clk_freq=50e6,
        with_spi_flash  = False,
        with_led_chaser = True,
        with_buttons    = True,
        with_sdram      = False,
        sdram_model     = "sipeed",
        sdram_rate      = "1:2",
        with_display    = False,
        display_type    = "pmod",
        with_video_terminal  = False,
        with_video_colorbars = False,
        **kwargs):

        platform = sipeed_tang_primer_25k.Platform(toolchain=toolchain)

        assert not with_sdram or (sdram_model in ["sipeed", "mister"])
        assert not with_display or (display_type in ["pmod", "tm1638"])

        if with_sdram:
            platform.add_extension({
                "sipeed": sipeed_tang_primer_25k.sipeedSDRAM(),
                "mister": sipeed_tang_primer_25k.misterSDRAM}[sdram_model]
            )

        # CRG --------------------------------------------------------------------------------------
        self.crg = _CRG(platform, sys_clk_freq,
            with_sdram, 
            sdram_rate,
            with_video_pll = with_video_terminal or with_video_colorbars,
        )

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Tang Primer 25K", **kwargs)

        # SDR SDRAM --------------------------------------------------------------------------------
        if with_sdram and not self.integrated_main_ram_size:
            module_cls = {
                "sipeed": W9825G6KH6,
                "mister": AS4C32M16}[sdram_model]
            if sdram_rate == "1:2":
                sdrphy_cls = HalfRateGENSDRPHY
            else:
                sdrphy_cls = GENSDRPHY
            self.sdrphy = sdrphy_cls(platform.request("sdram"), sys_clk_freq)
            self.add_sdram("sdram",
                phy           = self.sdrphy,
                module        = module_cls(sys_clk_freq, sdram_rate),
                l2_cache_size = kwargs.get("l2_size", 8192)
            )

        # SPI Flash --------------------------------------------------------------------------------
        if with_spi_flash:
            from litespi.modules import W25Q64FV as SpiFlashModule
            from litespi.opcodes import SpiNorFlashOpCodes as Codes
            self.add_spi_flash(mode="1x", module=SpiFlashModule(Codes.READ_1_1_1))

        # Video ------------------------------------------------------------------------------------
        if with_video_terminal or with_video_colorbars:
            platform.add_extension(sipeed_tang_primer_25k.pmod_hdmi())
            hdmi_pads = platform.request("hdmi")
            self.videophy = VideoGowinHDMIPHY(hdmi_pads, clock_domain="hdmi")
            if with_video_colorbars:
                self.add_video_colorbars(phy=self.videophy, timings="640x480@60Hz", clock_domain="hdmi")
            if with_video_terminal:
                self.add_video_terminal(phy=self.videophy, timings="640x480@75Hz", clock_domain="hdmi")

        # Leds -------------------------------------------------------------------------------------
        if with_led_chaser:
            if (not with_video_terminal) and (not with_video_colorbars):
                platform.add_extension(sipeed_tang_primer_25k.pmod_led())
                led_pads = platform.request_all("pmod_led")
            else:
                led_pads = platform.request_all("led")
            self.leds = LedChaser(
                pads         = led_pads,
                sys_clk_freq = sys_clk_freq,
                polarity     = 1
            )

        # Buttons ----------------------------------------------------------------------------------
        if with_buttons:
            self.buttons = GPIOIn(pads=platform.request("btn_n", 1))

            platform.add_extension(sipeed_tang_primer_25k.pmod_btn())
            self.pmod_btn = GPIOIn(pads=~platform.request_all("pmod_btn"))

        # Displays ------------------------------------------------------------------------------------
        if with_display:
            # SevenSegmentDisplay
            if display_type == "pmod":
                platform.add_extension(sipeed_tang_primer_25k.pmod_dt())
                display_pads=platform.request("display")
                self.submodules.display = SevenSegmentDisplay(sys_clk_freq)
                self.comb += [
                    display_pads.cs.eq(~self.display.cs),
                    display_pads.abcdefg.eq(~self.display.abcdefg)
                ]

            # tm1638
            if display_type == "tm1638":
                platform.add_extension(sipeed_tang_primer_25k.tm1638_io())
                tm1638_pads = platform.request("tm1638")
                self.tm1638 = TM1638(platform, tm1638_pads, clk_divider=50)
                
# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=sipeed_tang_primer_25k.Platform, description="LiteX SoC on Tang Primer 25K.")
    parser.add_target_argument("--flash",            action="store_true",      help="Flash bitstream.")
    parser.add_target_argument("--sys-clk-freq",     default=50e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--with-spi-flash",   action="store_true",      help="Enable memory-mapped SPI flash.")
    
    # Memory.
    parser.add_target_argument("--with-sdram",       action="store_true",      help="Enable optional SDRAM module.")
    parser.add_target_argument("--sdram-model",      default="sipeed",
        choices=[
            "sipeed",
            "mister"
    ], help="SDRAM module model.")
    
    # Display.
    parser.add_target_argument("--with-display",      action="store_true",      help="Enable seven segment display module.")
    parser.add_target_argument("--display-type",      default="pmod",
        choices=[
            "pmod",
            "tm1638"
    ], help="Display module type.")
    
    # Video.
    viopts = parser.target_group.add_mutually_exclusive_group()
    viopts.add_argument("--with-video-colorbars",   action="store_true", help="Enable Video ColoBars (HDMI).")
    viopts.add_argument("--with-video-terminal",    action="store_true", help="Enable Video Terminal (HDMI).")
    args = parser.parse_args()

    soc = BaseSoC(
        toolchain      = args.toolchain,
        sys_clk_freq   = args.sys_clk_freq,
        with_video_colorbars   = args.with_video_colorbars,
        with_video_terminal    = args.with_video_terminal,
        with_spi_flash = args.with_spi_flash,
        with_sdram     = args.with_sdram,
        sdram_model    = args.sdram_model,
        with_display   = args.with_display,
        display_type   = args.display_type,
        **parser.soc_argdict
    )
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

if __name__ == "__main__":
    main()
