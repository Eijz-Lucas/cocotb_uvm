// ========================================================================================================== //
//                               Copyright 2022 Deepcreatic Technologies Co.Ltd                               //
//                                            All rights reserved                                             //
// ---------------------------------------------------------------------------------------------------------- //
// Module Full Name: sy_fifo
// File Name: design/module/ARCIP/rtl/sy_fifo.v
// Author: 皮雳  @author: Arcvektor
// Create Date: 2022年5月26日
// version: 0.2
// Function Description: 同步FIFO,具有空满、将空将满、报错功能，只支持2的N次幂深度，宽度不限
// Modified By: 皮雳
// Modified Date: 2022年5月30日18:14:13 ver 0.1
//                2022年7月28日13:38:19 ver 0.2
// Description: 初步完成代码 ver 0.1
//              将满功能正确，覆盖率完成，增添文档注释 ver 0.2
// ========================================================================================================== //

// ===============================宏定义声明===============================
// `define OUT_RAM          // 开启此宏后，FIFO读写RAM信号将成为IO信号
// `define AEMPTY 1         // 开启此宏后，FIFO拥有将空信号及其相关逻辑
// `define AFULL 1          // 开启此宏后，FIFO拥有将满信号及其相关逻辑
// `define ERROR_REPORT 1   // 开启此宏后，FIFO拥有报错信号及其相关逻辑 
// `define FPGA 1           // 上板时请开启此宏，并使用板上资源替换伪双口RAM
// =======================================================================

// ===============================================模块声明=============================================== //
module sy_fifo
#(
    // ---------------开启此宏后，FIFO拥有将满信号及其相关逻辑---------------
    `ifdef AFULL                                
    parameter               WS = 1          ,   // 将满水线
    `endif
    // ---------------开启此宏后，FIFO拥有将空信号及其相关逻辑---------------
    `ifdef AEMPTY                               
    parameter               RS = 0          ,   // 将空水线
    `endif
    // -----------------------------普通参数------------------------------
    parameter               DW = 160        ,   // FIFO宽度
    parameter               AW = 4          ,   // FIFO地址宽度
    parameter               DP = 1 << AW        // FIFO深度，只支持2的N次幂深度
)
(
    // -------------------------------外部信号-------------------------------
    input                   clk                 ,   // 时钟信号
    input                   rst_n               ,   // 异步低有效复位信号 
    // -------------------------------报错信号-------------------------------
    `ifdef ERROR_REPORT                             // 开启此宏后，FIFO拥有报错信号及其相关逻辑 
    output reg              fifo_write_err      ,   // FIFO写错误信号
    output reg              fifo_read_err       ,   // FIFO读错误信号
    `endif
    // -------------------------------将满信号(`AFULL)-------------------------------
    `ifdef AFULL                                    // 开启此宏后，FIFO拥有将满信号及其相关逻辑
    output                  fifo_write_afull    ,   // FIFO将满信号
    `endif
    // -------------------------------将空信号(`AEMPTY)-------------------------------
    `ifdef AEMPTY                                   // 开启此宏后，FIFO拥有将空信号及其相关逻辑
    output                  fifo_read_aempty    ,   // FIFO将空信号
    `endif
    // -------------------------------读写RAM信号-------------------------------
    `ifdef OUT_RAM
    output      [DW-1:0]    xin                 ,   // 写RAM信号
    output      [AW-1:0]    addr1               ,   // 读RAM地址
    output      [AW-1:0]    addr2               ,   // 写RAM地址
    output                  re                  ,   // 读RAM使能
    output                  we                  ,   // 写RAM使能
    input       [AW-1:0]    dout                ,   // 读到的RAM数据
    `endif
    // -------------------------------写通道基本信号-------------------------------
    input                   fifo_write_en       ,   // FIFO写使能
    input       [DW-1:0]    fifo_write_data     ,   // FIFO写数据
    output                  fifo_write_full     ,   // FIFO满信号
    // -------------------------------读通道基本信号-------------------------------
    input                   fifo_read_en        ,   // FIFO读使能
    output      [DW-1:0]    fifo_read_data      ,   // FIFO读数据
    output                  fifo_read_empty         // FIFO空信号
         
);
// ========================================================================================================== //

// ===============================寄存器声明===============================
reg [AW:0]          fifo_write_addr         ;   // FIFO读地址,高位作空满判断
reg [AW:0]          fifo_read_addr          ;   // FIFO写地址,高位作空满判断
// =======================================================================

// ===============================元件例化与连线===============================
// 上板时请开启FPGA宏，并使用板上资源替换此伪双口RAM
// -------------------------------伪双口RAM连线-------------------------------
`ifndef OUT_RAM
`ifndef FPGA
    simple_dual_ram #(
        .DW                 (DW)                        ,
        .AW                 (AW)                        ,
        .DP                 (DP)                 
    )
    u_ram
    (
        .clk                (clk)                       ,
        .rst_n              (rst_n)                     ,
        .xin                (fifo_write_data)           ,
        .addr1              (fifo_read_addr[AW-1:0])    ,
        .addr2              (fifo_write_addr[AW-1:0])   ,
        .re                 (fifo_read_en)              ,
        .we                 (fifo_write_en)             ,
        .dout               (fifo_read_data)             
    );
`endif
`else

    assign xin              = fifo_write_data;
    assign addr1            = fifo_read_addr[AW-1:0];
    assign addr2            = fifo_write_addr[AW-1:0];
    assign re               = fifo_read_en;
    assign we               = fifo_write_en;
    assign fifo_read_data   = dout;


`endif 
// ===========================================================================

// ================================主要时序逻辑================================
// --------------------------------读时序逻辑-------------------------------
always@(posedge clk or negedge rst_n) begin
    if(~rst_n) begin
        fifo_read_addr <= 'b0;
    end else begin
        if (fifo_read_en && ~fifo_read_empty) begin
            fifo_read_addr <= fifo_read_addr + 1'b1;
        end   
    end
end
// --------------------------------写时序逻辑-------------------------------
always@(posedge clk or negedge rst_n) begin
    if(~rst_n) begin
        fifo_write_addr <= 'b0;
    end else begin
        if (fifo_write_en && ~fifo_write_full) begin
            fifo_write_addr <= fifo_write_addr + 1'b1;
        end   
    end
end
// --------------------------------读时序纠错逻辑-------------------------------
`ifdef ERROR_REPORT
    always@(posedge clk or negedge rst_n) begin
        if(~rst_n) begin
            fifo_read_err <= 'b0;
        end else begin
            // 空状态被读，读指针不会动，拉高读错误信号
            if (fifo_read_empty && fifo_read_en) begin
                fifo_read_err <= 'b1;
            end
        end
    end
`endif
// --------------------------------写时序纠错逻辑-------------------------------
`ifdef ERROR_REPORT
    always@(posedge clk or negedge rst_n) begin
        if(~rst_n) begin
            fifo_write_err <= 'b0;
        end else begin
            // 满状态被写，写指针不会动，拉高写错误信号
            if (fifo_write_full && fifo_write_en) begin
                fifo_write_err <= 'b1;
            end
        end
    end
`endif
// ===========================================================================

// ================================主要组合逻辑================================
// --------------------------------连线声明--------------------------------
// 这只是为了让后面看起来简洁一点
wire [AW-1:0] waddr;
wire [AW-1:0] raddr;
assign waddr = fifo_write_addr[AW-1:0];
assign raddr = fifo_read_addr[AW-1:0] ;
// --------------------------------FIFO空满判断--------------------------------
// 满状态下普通地址位相同，扩展地址位相反，空状态下所有地址位均相同
assign fifo_write_full  = (fifo_write_addr == {~(fifo_read_addr[AW]),raddr});
assign fifo_read_empty = (fifo_write_addr == fifo_read_addr);
// --------------------------------FIFO将满判断--------------------------------
// 将满状态有两种可能：
// 扩展地址位相反，则raddr的普通地址位超前于waddr，此时可直接作减法并与写水线判断
// 扩展地址位相同，则waddr的普通地址位超前于raddr，此时强行令raddr扩展地址为1，waddr扩展地址为0作减法并与写水线判断
`ifdef AFULL
assign fifo_write_afull  = (fifo_write_addr[AW] ^^ fifo_read_addr[AW]) ? ((raddr-waddr) < WS+1): (({1'b1,raddr} - {1'b0,waddr}) < WS+1);
`endif
// --------------------------------FIFO将空判断--------------------------------
// 将空状态有两种可能：
// 扩展地址位相反，则raddr的普通地址位超前于waddr，此时强行令raddr扩展地址为0，waddr扩展地址为1作减法并与写水线判断
// 扩展地址位相同，则waddr的普通地址位超前于raddr，此时可直接作减法并与写水线判断
`ifdef AEMPTY
assign fifo_read_aempty = (fifo_write_addr[AW] ^^ fifo_read_addr[AW]) ? (({1'b1,waddr} - {1'b0,raddr}) < RS+1 ) : ((waddr-raddr) < RS+1 );
`endif
// ===========================================================================

endmodule
