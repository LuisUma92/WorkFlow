local ls = require("luasnip")
local s = ls.snippet
local t = ls.text_node
local i = ls.insert_node
local f = ls.function_node

local function today() return os.date("%Y-%m-%d") end
local function id_prefix() return os.date("%Y%m%d") .. "-" end

return {
	s({ trig = "fn.", wordTrig = true, name = "Fleeting note frontmatter" }, {
		t("---"),
		t({ "", "id: " }), f(id_prefix, {}), i(1, "slug"),
		t({ "", "title: " }), i(2, ""),
		t({ "", "aliases: []" }),
		t({ "", "type: fleeting" }),
		t({ "", "created: " }), f(today, {}),
		t({ "", "tags: []" }),
		t({ "", "---" }),
		t({ "", "" }),
		i(0),
	}),

	s({ trig = "pn.", wordTrig = true, name = "Permanent note frontmatter" }, {
		t("---"),
		t({ "", "id: " }), f(id_prefix, {}), i(1, "slug"),
		t({ "", "title: " }), i(2, ""),
		t({ "", "aliases: []" }),
		t({ "", "type: permanent" }),
		t({ "", "created: " }), f(today, {}),
		t({ "", "tags: []" }),
		t({ "", "concepts: []" }),
		t({ "", "main_topic: " }), i(3, ""),
		t({ "", "discipline_area: " }), i(4, ""),
		t({ "", "references: []" }),
		t({ "", "exercises: []" }),
		t({ "", "images: []" }),
		t({ "", "---" }),
		t({ "", "" }),
		t({ "", "## Summary" }),
		t({ "", "" }),
		t({ "", "## Key ideas" }),
		t({ "", "" }),
		t({ "", "## Connections" }),
		t({ "", "" }),
		i(0),
	}),

	s({ trig = "ln.", wordTrig = true, name = "Literature note frontmatter" }, {
		t("---"),
		t({ "", "id: " }), f(id_prefix, {}), i(1, "slug"),
		t({ "", "title: " }), i(2, ""),
		t({ "", "aliases: []" }),
		t({ "", "type: literature" }),
		t({ "", "bibkey: " }), i(3, ""),
		t({ "", "created: " }), f(today, {}),
		t({ "", "tags: []" }),
		t({ "", "concepts: []" }),
		t({ "", "references: []" }),
		t({ "", "exercises: []" }),
		t({ "", "images: []" }),
		t({ "", "---" }),
		t({ "", "" }),
		t({ "", "## Key ideas" }),
		t({ "", "" }),
		t({ "", "## Chapter notes" }),
		t({ "", "" }),
		t({ "", "## Questions raised" }),
		t({ "", "" }),
		i(0),
	}),
}
