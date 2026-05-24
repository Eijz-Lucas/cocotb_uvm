module add_one (
    input logic clk,
    input logic rst_n,
    input logic en,

    input logic [7:0] addr,
    input logic [7:0] len,

    // RAM interface
    output logic [7:0] ram_addr,
    input  logic [7:0] ram_rdata,

    // FIFO interface
    output logic       fifo_write_en,
    output logic [7:0] fifo_write_data
);

    //========================
    // 控制信号
    //========================
    logic       busy;
    logic [7:0] cnt;
    logic [7:0] base_addr;
    logic [7:0] len_latched;

    //========================
    // busy 控制
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) busy <= 0;
        else if (en) busy <= 1;
        else if (busy && cnt == len_latched) busy <= 0;
    end

    //========================
    // 计数器
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) cnt <= 0;
        else if (en) cnt <= 0;
        else if (busy) cnt <= cnt + 1;
    end

    //========================
    // 起始地址锁存
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            base_addr   <= 0;
            len_latched <= 0;
        end else if (en) begin
            base_addr   <= addr;
            len_latched <= len;
        end
    end

    //========================
    // 连续地址生成（关键点）
    //========================
    assign ram_addr = base_addr + cnt;

    //========================
    // FIFO 写（流式）
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fifo_write_en   <= 0;
            fifo_write_data <= 0;
        end else begin
            fifo_write_en <= 0;

            if (busy && cnt < len_latched) begin
                fifo_write_en   <= 1;
                fifo_write_data <= ram_rdata + 1;
            end
        end
    end

endmodule