ST = 

clean_build-%:
	@rm -rf ./builds/sim_build_$*
	@rm -f ./builds/results_$*.xml ./builds/.st_mode_$*

ctb-%:
	$(eval SIM_TOP := $*)
	@echo "======= cocotb SIM_TOP = $(SIM_TOP) ======="
	@mkdir -p ./builds
	@LAST_ST=$$(cat ./builds/.st_mode_$(SIM_TOP) 2>/dev/null || echo "NONE"); \
	if [ "$$LAST_ST" != "$(ST)" ]; then \
		if [ "$$LAST_ST" != "NONE" ]; then \
			echo "========================================================="; \
			echo " 🔄 Detect [$(SIM_TOP)] sim mode has been changed (ST: $$LAST_ST -> $(ST))"; \
			echo " 🧹 Cleaning up and rebuilding"; \
			echo "========================================================="; \
			$(MAKE) clean_build-$(SIM_TOP); \
		fi; \
		echo "$(ST)" > ./builds/.st_mode_$(SIM_TOP); \
	fi
	@# 3. 调用底层的 cocotb makefile
	$(MAKE) -f examples/cosim_test/tb/ctb.mk SIM_TOP=$(SIM_TOP) ST=$(ST)
