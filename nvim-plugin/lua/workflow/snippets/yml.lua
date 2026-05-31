local ls = require("luasnip")
local s = ls.snippet
local sa = ls.extend_decorator.apply(ls.snippet, {}) --[[@as function]]
-- local sn = ls.snippet_node
-- local isn = ls.indent_snippet_node
local t = ls.text_node
local i = ls.insert_node
local f = ls.function_node
-- local c = ls.choice_node
-- local d = ls.dynamic_node
local r = ls.restore_node
-- local events = require("luasnip.util.events")
-- local ai = require("luasnip.nodes.absolute_indexer")
-- local extras = require("luasnip.extras")
-- local l = extras.lambda
-- local rep = extras.rep
-- local p = extras.partial
-- local m = extras.match
-- local n = extras.nonempty
-- local dl = extras.dynamic_lambda
-- local fmt = require("luasnip.extras.fmt").fmt
-- local fmta = require("luasnip.extras.fmt").fmta
-- local conds = require("luasnip.extras.expand_conditions")
-- local postfix = require("luasnip.extras.postfix").postfix
-- local types = require("luasnip.util.types")
-- local parse = require("luasnip.util.parser").parse_snippet
-- local ms = ls.multi_snippet
-- local k = require("luasnip.nodes.key_indexer").new_key
-- set a higher priority (defaults to 0 for most snippets)
-- local snip = ls.parser.parse_snippet(
--   { trig = "mk", name = "Math", condition = not_math, priority = 10 },
--   "$ ${1:${TM_SELECTED_TEXT}} $$0"
-- )

return {
	s({
		trig = "wf.",
		wordTrig = false,
		name = "Workflow import file skeleton",
	}, {
		t("discipline_area_code: "),
		i(1, "0000AA"),
		t({ "", "topics:" }),
		t({ "", "  - name: " }),
		i(2),
		t({ "", "    serial: " }),
		i(3, "1"),
		t({ "", "    contents:" }),
		t({ "", "      - name: " }),
		i(4),
		t({ "", "        concepts:" }),
		i(0),
	}),
	s({
		trig = "tl.",
		wordTrig = false,
		name = "Topic list",
		snippetType = "autosnippet",
	}, {
		t("- name: "),
		i(1),
		t({ "", "  serial: " }),
		i(2),
		t({ "", "  contents:" }),
		i(0),
	}),
	s({
		trig = "ci.",
		wordTrig = false,
		name = "Contents list",
		snippetType = "autosnippet",
	}, {
		t({ "", "- name: " }),
		i(1),
		t({ "", "  concepts:" }),
		i(0),
	}),
	s({
		trig = "nc.",
		wordTrig = false,
		name = "Concept item",
		snippetType = "autosnippet",
	}, {
		t({ "", "- code: " }),
		i(1),
		t({ "", "  label: " }),
		i(2),
		t({ "", "  domain: " }),
		i(3),
		t({ "", "  description: " }),
		i(4),
		t({ "", "  parent_code: " }),
		i(0),
	}),
}
