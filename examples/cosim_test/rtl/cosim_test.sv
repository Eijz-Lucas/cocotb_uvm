module cosim_test #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 8
) (
`ifdef ST
    input logic clk,
    input logic rst_n,

    // add_one
    input logic       en_add,
    input logic [7:0] addr_add,
    input logic [7:0] len_add,

    // sub_one
    input logic       en_sub,
    input logic [7:0] len_sub,

    // ram
    input logic       we,
    input logic [7:0] wdata,
    input logic [7:0] addr,

    // FIFO
    input  logic       fifo_read_en,
    output logic [7:0] fifo_read_data
`else
    input  logic       clk,
    input  logic       rst_n
`endif
);

`ifdef ST
    logic       fifo_write_en_add;
    logic [7:0] fifo_write_data_add;
    logic [7:0] ram_addr_add;
    logic [7:0] ram_rdata_add;

    add_one u_add_one (
        .clk            (clk),
        .rst_n          (rst_n),
        .en             (en_add),
        .addr           (addr_add),
        .len            (len_add),
        .ram_addr       (ram_addr_add),
        .ram_rdata      (ram_rdata_add),
        .fifo_write_en  (fifo_write_en_add),
        .fifo_write_data(fifo_write_data_add)
    );

    logic       fifo_write_en_sub;
    logic [7:0] fifo_write_data_sub;
    logic       fifo_read_en_sub;
    logic [7:0] fifo_read_data_sub;
    assign fifo_read_data = fifo_read_data_sub;

    sub_one u_sub_one (
        .clk            (clk),
        .rst_n          (rst_n),
        .en             (en_sub),
        .len            (len_sub),
        .fifo_read_en   (fifo_read_en_sub),
        .fifo_read_data (fifo_read_data_sub),
        .fifo_write_en  (fifo_write_en_sub),
        .fifo_write_data(fifo_write_data_sub)
    );

    sy_fifo #(
        .DW(8),
        .AW(4)
    ) u_sy_fifo (
        .clk            (clk),
        .rst_n          (rst_n),
        .fifo_write_en  (fifo_write_en_add | fifo_write_en_sub),
        .fifo_write_data(fifo_write_data_add | fifo_write_data_sub),
        .fifo_write_full(),
        .fifo_read_en   (fifo_read_en | fifo_read_en_sub),
        .fifo_read_data (fifo_read_data_sub),
        .fifo_read_empty()
    );

    single_port_ram #(
        .ADDR_WIDTH(8),
        .DATA_WIDTH(8)
    ) u_single_port_ram (
        .clk  (clk),
        .we   (we),
        .addr (ram_addr_add | addr),
        .wdata(wdata),
        .rdata(ram_rdata_add)
    );
`else
    add_one u_add_one (
        .clk            (clk),
        .rst_n          (rst_n),
        .en             (),
        .addr           (),
        .len            (),
        .ram_addr       (),
        .ram_rdata      (),
        .fifo_write_en  (),
        .fifo_write_data()
    );

    sub_one u_sub_one (
        .clk            (clk),
        .rst_n          (rst_n),
        .en             (),
        .len            (),
        .fifo_read_en   (),
        .fifo_read_data (),
        .fifo_write_en  (),
        .fifo_write_data()
    );
`endif

endmodule
