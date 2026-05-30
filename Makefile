.PHONY: test-plugin

test-plugin:
	nvim --headless --noplugin -u nvim-plugin/tests/plenary/minimal_init.lua \
	  -c "PlenaryBustedDirectory nvim-plugin/tests/plenary/ { minimal_init = 'nvim-plugin/tests/plenary/minimal_init.lua' }"
