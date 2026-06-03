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

	-- biblatex blocks for `:WorkflowBibImport`. The cite key becomes `bibkey`
	-- on import; fields below all map to BibEntry columns. NOTE: the importer
	-- silently ignores any field it does not recognise (no warning), so keep
	-- these field names in sync with importer.py's field sets.
	s({ trig = "bib.book", wordTrig = true, name = "biblatex @book block" }, {
		t("```bib"),
		t({ "", "@book{" }), i(1, "key"), t(","),
		t({ "", "  author    = {" }), i(2, ""), t("}," ),
		t({ "", "  title     = {" }), i(3, ""), t("}," ),
		t({ "", "  year      = {" }), i(4, ""), t("}," ),
		t({ "", "  publisher = {" }), i(5, ""), t("}," ),
		t({ "", "  location  = {" }), i(6, ""), t("}," ),
		t({ "", "  edition   = {" }), i(7, ""), t("}," ),
		t({ "", "}" }),
		t({ "", "```" }),
		t({ "", "" }),
		i(0),
	}),

	s({ trig = "bib.article", wordTrig = true, name = "biblatex @article block" }, {
		t("```bib"),
		t({ "", "@article{" }), i(1, "key"), t(","),
		t({ "", "  author  = {" }), i(2, ""), t("}," ),
		t({ "", "  title   = {" }), i(3, ""), t("}," ),
		t({ "", "  journal = {" }), i(4, ""), t("}," ),
		t({ "", "  year    = {" }), i(5, ""), t("}," ),
		t({ "", "  volume  = {" }), i(6, ""), t("}," ),
		t({ "", "  number  = {" }), i(7, ""), t("}," ),
		t({ "", "  pages   = {" }), i(8, ""), t("}," ),
		t({ "", "  doi     = {" }), i(9, ""), t("}," ),
		t({ "", "}" }),
		t({ "", "```" }),
		t({ "", "" }),
		i(0),
	}),

	s({ trig = "bib.techreport", wordTrig = true, name = "biblatex @techreport block" }, {
		t("```bib"),
		t({ "", "@techreport{" }), i(1, "key"), t(","),
		t({ "", "  author      = {" }), i(2, ""), t("}," ),
		t({ "", "  title       = {" }), i(3, ""), t("}," ),
		t({ "", "  institution = {" }), i(4, ""), t("}," ),
		t({ "", "  year        = {" }), i(5, ""), t("}," ),
		t({ "", "  number      = {" }), i(6, ""), t("}," ),
		t({ "", "  url         = {" }), i(7, ""), t("}," ),
		t({ "", "}" }),
		t({ "", "```" }),
		t({ "", "" }),
		i(0),
	}),

	s({ trig = "bib.online", wordTrig = true, name = "biblatex @online block" }, {
		t("```bib"),
		t({ "", "@online{" }), i(1, "key"), t(","),
		t({ "", "  author       = {" }), i(2, ""), t("}," ),
		t({ "", "  title        = {" }), i(3, ""), t("}," ),
		t({ "", "  organization = {" }), i(4, ""), t("}," ),
		t({ "", "  year         = {" }), i(5, ""), t("}," ),
		t({ "", "  url          = {" }), i(6, ""), t("}," ),
		t({ "", "  urldate      = {" }), f(today, {}), t("}," ),
		t({ "", "}" }),
		t({ "", "```" }),
		t({ "", "" }),
		i(0),
	}),
}
