// ========================================================================================================== //
//                               Copyright 2022 Deepcreatic Technologies Co.Ltd                               //
//                                            All rights reserved                                             //
// ---------------------------------------------------------------------------------------------------------- //
// Module Full Name: simple_dual_ram
// File Name: design/module/Cache/rtl/simple_dual_ram.v
// Author: 皮雳  @author: Arcvektor
// Create Date: 2022年5月17日
// version: 0.1
// Function Description: AIPU中Cache使用的伪双口RAM(仅供原型验证，上FPGA后使用IP资源替换)
// Modified By: 皮雳
// Modified Date: 2022年5月20日13:04:47
// Description: 初步完成代码
// ========================================================================================================== //
module simple_dual_ram
#(
    parameter       DW = 256            ,       // RAM位宽
    parameter       AW = 12             ,       // RAM地址长度
    parameter       DP = 1 << AW                // RAM深度
)
(
    input                   clk         ,       // RAM时钟
    input                   rst_n       ,       // RAM复位
	input       [DW-1:0]    xin         ,       // RAM待写入数据
	input       [AW-1:0]    addr1       ,       // RAM读地址
    input       [AW-1:0]    addr2       ,       // RAM写地址
	input                   re          ,       // RAM读使能
	input                   we          ,       // RAM写使能
	output reg  [DW-1:0]    dout                // RAM输出寄存器
);


// -------------------------------mem声明-------------------------------
reg [DW-1:0] mem [DP-1:0]   ;	            // 根据宽深定义RAM

// -------------------------------主要时序逻辑-------------------------------
always@(posedge clk) begin
        // 1读2写
        // 同时读写相同地址时不做bypass，读取旧数据
    if (we) begin
        mem[addr2] <= xin;
    end
end

always@(*) begin
    dout = mem[addr1];
end

endmodule
