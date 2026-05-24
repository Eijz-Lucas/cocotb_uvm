# This file is public domain, it can be freely copied without restrictions.
# SPDX-License-Identifier: CC0-1.0

# Makefile

# default
SIM ?= verilator
TOPLEVEL_LANG ?= verilog
SIM_TOP ?= top

VERILOG_SOURCES += $(shell ./utils/expand_list.sh ./test/rtl/$(SIM_TOP).f)
# use VHDL_SOURCES for VHDL files

# default args
EXTRA_ARGS += --trace --trace-fst --trace-structs
ifeq ($(ST),1)
EXTRA_ARGS += +define+ST
endif

# COCOTB_TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
COCOTB_TOPLEVEL = $(SIM_TOP)

# COCOTB_TEST_MODULES is the basename of the Python test file(s)
COCOTB_TEST_MODULES = test.tb.test_$(SIM_TOP)
COCOTB_RESULTS_FILE = builds/results_$(SIM_TOP).xml
SIM_BUILD = builds/sim_build_$(SIM_TOP)
export PYTHONPATH := $(abspath src):$(PYTHONPATH)

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
