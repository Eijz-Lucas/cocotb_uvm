module single_port_ram #(
    parameter ADDR_WIDTH = 8,  // 地址宽度
    parameter DATA_WIDTH = 8   // 数据宽度
) (
    input  logic                  clk,
    input  logic                  we,     // 写使能
    input  logic [ADDR_WIDTH-1:0] addr,   // 地址
    input  logic [DATA_WIDTH-1:0] wdata,  // 写数据
    output logic [DATA_WIDTH-1:0] rdata   // 读数据
);

    // RAM 存储体
    logic [DATA_WIDTH-1:0] mem[0:(1<<ADDR_WIDTH)-1]/* verilator public_flat_rw */;
    // 同步写
    always_ff @(posedge clk) begin
        if (we) begin
            mem[addr] <= wdata;  // 写
        end

    end

    assign rdata = mem[addr];  // 异步读

endmodule
