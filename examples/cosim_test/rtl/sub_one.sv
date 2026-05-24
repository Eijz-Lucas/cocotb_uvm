module sub_one (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         en,

    input  logic [7:0]  len,

    // FIFO Read interface (异步读)
    output logic         fifo_read_en,
    input  logic [7:0]  fifo_read_data,

    // FIFO Write interface
    output logic         fifo_write_en,
    output logic [7:0]  fifo_write_data
);

    //========================
    // 控制信号
    //========================
    logic        busy;
    logic [7:0]  cnt;
    logic [7:0]  len_latch;

    //========================
    // 长度锁存
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            len_latch <= 0;
        else if (en)
            len_latch <= len;
    end

    //========================
    // busy 控制
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            busy <= 0;
        else if (en)
            busy <= 1;
        else if (busy && cnt == len_latch)
            busy <= 0;
    end

    //========================
    // 计数器
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            cnt <= 0;
        else if (en)
            cnt <= 0;
        else if (busy && cnt < len_latch)
            cnt <= cnt + 1;
    end

    //========================
    // FIFO 读控制
    //========================
    // 当处于 busy 状态并且未读完 len 个数据时，持续拉高读使能
    assign fifo_read_en = busy && (cnt < len_latch);

    //========================
    // FIFO 写控制（结果减一再写回）
    //========================
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fifo_write_en   <= 0;
            fifo_write_data <= 0;
        end else begin
            // 因为是异步读，fifo_read_en 为高的当拍 fifo_read_data 就已有效
            // 可以直接在同一个时钟沿采样数据减一并交给写模块
            if (fifo_read_en) begin
                fifo_write_en   <= 1;
                fifo_write_data <= fifo_read_data - 1;
            end else begin
                fifo_write_en   <= 0;
            end
        end
    end

endmodule