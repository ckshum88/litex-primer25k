module tm1638_hw_ctrl #(
    parameter CLK_DIVIDER = 50 // e.g., 50MHz / 50 = 1MHz SPI operational clock
)(
    input  wire        clk,        // System Clock
    input  wire        rst,        // Active High Reset
    
    // Core functional interface (Flattened to keep Gowin parser happy)
    input  wire [63:0] digit_data_flat, 
    input  wire [7:0]  led_data,                
    output reg  [31:0] buttons_out,             
    
    // Physical TM1638 Pins
    output reg         tm_stb,
    output reg         tm_clk,
    inout  wire        tm_dio
);

    // FSM States
    localparam STATE_IDLE       = 3'd0,
               STATE_INIT_CMD   = 3'd1,
               STATE_WRITE_ADR  = 3'd2,
               STATE_WRITE_DAT  = 3'd3,
               STATE_READ_CMD   = 3'd4,
               STATE_READ_DAT   = 3'd5,
               STATE_DISP_CMD   = 3'd6;

    reg [2:0] state;
    reg [7:0] clk_cnt;
    reg       spi_tick; // Generated pulse at the desired SPI clock frequency

    // Serialization tracking registers
    reg [3:0] bit_cnt;   // Tracks 0 to 7 bits per byte
    reg [4:0] byte_idx;  // Tracks RAM array bytes (0 to 15)
    reg [7:0] shift_reg; // Active output shift register

    // Bidirectional DIO pin handling
    reg       dio_out;
    reg       dio_oe;    // 1 = Output Active, 0 = High Impedance Input Mode
    assign    tm_dio = dio_oe ? dio_out : 1'bZ;

    // Reconstruct and mix 8 segments and 8 LEDs into the 16-byte display map
    reg [7:0] display_ram [0:15];
    integer i;
    always @(*) begin
        for (i = 0; i < 8; i = i + 1) begin
            display_ram[i*2]   = digit_data_flat[(i*8) +: 8]; 
            display_ram[i*2+1] = {7'b0, led_data[i]}; // Standard module LED alignment
        end
    end

    // --- Clock Generator (Produces a single 'spi_tick' pulse every half-period) ---
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            clk_cnt  <= 8'd0;
            spi_tick <= 1'b0;
        end else if (clk_cnt == (CLK_DIVIDER/2) - 1) begin
            clk_cnt  <= 8'd0;
            spi_tick <= 1'b1;
        end else begin
            clk_cnt  <= clk_cnt + 8'd1;
            spi_tick <= 1'b0;
        end
    end

    // --- Master Protocol Execution Control Loop ---
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state       <= STATE_IDLE;
            tm_stb      <= 1'b1;
            tm_clk      <= 1'b1;
            dio_oe      <= 1'b1;
            dio_out     <= 1'b1;
            bit_cnt     <= 4'd0;
            byte_idx    <= 5'd0;
            shift_reg   <= 8'd0;
            buttons_out <= 32'd0;
        end else if (spi_tick) begin
            case (state)

                STATE_IDLE: begin
                    tm_stb    <= 1'b1;
                    tm_clk    <= 1'b1;
                    bit_cnt   <= 4'd0;
                    byte_idx  <= 5'd0;
                    state     <= STATE_INIT_CMD;
                    shift_reg <= 8'h40; // Command 1: Data Mode Set (0x40 = Write, Auto-Increment)
                end

                STATE_INIT_CMD: begin // Serialising Command 0x40
                    tm_stb <= 1'b0;
                    dio_oe <= 1'b1;
                    if (tm_clk) begin
                        // Falling Edge: Setup data bit (LSB First)
                        tm_clk  <= 1'b0;
                        dio_out <= shift_reg[0];
                    end else begin
                        // Rising Edge: TM1638 latches data
                        tm_clk    <= 1'b1;
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_cnt == 4'd7) begin
                            bit_cnt   <= 4'd0;
                            tm_stb    <= 1'b1; // Strobe must toggle between distinct commands
                            state     <= STATE_WRITE_ADR;
                            shift_reg <= 8'hC0; // Command 2: Display Address Set (0xC0 = Starting Base)
                        end else begin
                            bit_cnt   <= bit_cnt + 4'd1;
                        end
                    end
                end

                STATE_WRITE_ADR: begin // Serialising Starting Address Command (0xC0)
                    tm_stb <= 1'b0;
                    if (tm_clk) begin
                        tm_clk  <= 1'b0;
                        dio_out <= shift_reg[0];
                    end else begin
                        tm_clk    <= 1'b1;
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_cnt == 4'd7) begin
                            bit_cnt   <= 4'd0;
                            state     <= STATE_WRITE_DAT;
                            shift_reg <= display_ram[0]; // Fetch first byte buffer row
                        end else begin
                            bit_cnt   <= bit_cnt + 4'd1;
                        end
                    end
                end

                STATE_WRITE_DAT: begin // Burst-writing all 16 memory blocks sequentially
                    if (tm_clk) begin
                        tm_clk  <= 1'b0;
                        dio_out <= shift_reg[0];
                    end else begin
                        tm_clk    <= 1'b1;
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_cnt == 4'd7) begin
                            bit_cnt <= 4'd0;
                            if (byte_idx == 5'd15) begin
                                tm_stb    <= 1'b1; // End of burst update payload stream
                                byte_idx  <= 5'd0;
                                state     <= STATE_READ_CMD;
                                shift_reg <= 8'h42; // Command 3: Data Mode Set (0x42 = Read Keys Matrix Mode)
                            end else begin
                                byte_idx  <= byte_idx + 5'd1;
                                shift_reg <= display_ram[byte_idx + 5'd1];
                            end
                        end else begin
                            bit_cnt   <= bit_cnt + 4'd1;
                        end
                    end
                end

                STATE_READ_CMD: begin // Serialising Key Reading Command Request (0x42)
                    tm_stb <= 1'b0;
                    dio_oe <= 1'b1;
                    if (tm_clk) begin
                        tm_clk  <= 1'b0;
                        dio_out <= shift_reg[0];
                    end else begin
                        tm_clk    <= 1'b1;
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_cnt == 4'd7) begin
                            bit_cnt  <= 4'd0;
                            byte_idx <= 5'd0;
                            dio_oe   <= 1'b0; // Switch DIO Pin to High-Z Input Mode
                            state    <= STATE_READ_DAT;
                        end else begin
                            bit_cnt  <= bit_cnt + 4'd1;
                        end
                    end
                end

                STATE_READ_DAT: begin // Capturing 4 bytes of asynchronous keyboard register state
                    if (tm_clk) begin
                        // Falling Edge: TM1638 shifts out next bit
                        tm_clk <= 1'b0;
                    end else begin
                        // Rising Edge: Sample stable incoming input bit data
                        tm_clk <= 1'b1;
                        buttons_out[(byte_idx * 8) + bit_cnt] <= tm_dio;
                        if (bit_cnt == 4'd7) begin
                            bit_cnt <= 4'd0;
                            if (byte_idx == 5'd3) begin // 4 bytes completely read
                                tm_stb    <= 1'b1;
                                byte_idx  <= 5'd0;
                                dio_oe    <= 1'b1; // Safe reversion back to driving mode output
                                state     <= STATE_DISP_CMD;
                                shift_reg <= 8'h8F; // Command 4: Turn Display ON with Full Brightness (0x8F)
                            end else begin
                                byte_idx  <= byte_idx + 5'd1;
                            end
                        end else begin
                            bit_cnt <= bit_cnt + 4'd1;
                        end
                    end
                end

                STATE_DISP_CMD: begin // Serialising Screen Output Regulation State (0x8F)
                    tm_stb <= 1'b0;
                    if (tm_clk) begin
                        tm_clk  <= 1'b0;
                        dio_out <= shift_reg[0];
                    end else begin
                        tm_clk    <= 1'b1;
                        shift_reg <= {1'b0, shift_reg[7:1]};
                        if (bit_cnt == 4'd7) begin
                            bit_cnt <= 4'd0;
                            tm_stb  <= 1'b1; 
                            state   <= STATE_IDLE; // Cycle finishes seamlessly; restart next pass loop
                        end else begin
                            bit_cnt <= bit_cnt + 4'd1;
                        end
                    end
                end

                default: state <= STATE_IDLE;
            endcase
        end
    end

endmodule
