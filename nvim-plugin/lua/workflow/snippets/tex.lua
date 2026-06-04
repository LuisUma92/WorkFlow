local ls = require("luasnip")
local s = ls.snippet
local f = ls.function_node

local base = vim.fn.expand("~/01-U/workflow/templates/")

local function tpl(filename)
	return f(function()
		local path = base .. filename
		if vim.fn.filereadable(path) == 0 then
			return { "% [workflow] template not found: " .. path }
		end
		return vim.fn.readfile(path)
	end, {})
end

return {
	s({ trig = "tpl.partial", name = "Partial exam (PN-YYYY-IIIC)" }, { tpl("PN-YYYY-IIIC.tex") }),
	s({ trig = "tpl.proposal", name = "Partial proposal" }, { tpl("PartialPropousal.tex") }),
	s({ trig = "tpl.main", name = "Main document (00AA)" }, { tpl("00AA.tex") }),
	s({ trig = "tpl.exEssey", name = "Book exercise (C00S00P000)" }, { tpl("book-TDEC00S00P000.tex") }),
	s({ trig = "tpl.exMultichoice", name = "Book exercise (C00S00P000)" }, { tpl("book-TSUC00S00P000.tex") }),
	s({ trig = "tpl.lect", name = "Lecture article ficha" }, { tpl("lect.tex") }),
}
