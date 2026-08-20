-- lua/workflow/tex_macros.lua
-- Pure-Lua extraction and expansion of LaTeX path macros.
--
-- Deliberately no Neovim API calls here: everything is string in / string out,
-- so the whole surface is unit-testable without a buffer.  The Neovim-facing
-- glue (buffer + .sty scanning, includeexpr wrapper) lives in tex_paths.lua.
--
-- Only *simple textual* definitions are supported — a macro that takes
-- arguments is not a path and is skipped on purpose.

local M = {}

-- Definition forms we recognize.  `name` and `value` are the capture indices.
-- Argument-taking forms (`\newcommand{\F}[1]{…}`) fail to match because `%s*{`
-- demands the body brace immediately after the name.
local macro_patterns = {
	-- \def\FOO{bar}
	"\\def\\([%a@]+)%s*{([^}]*)}",
	-- \newcommand{\FOO}{bar} / \renewcommand / \providecommand
	"\\newcommand%s*{\\([%a@]+)}%s*{([^}]*)}",
	"\\renewcommand%s*{\\([%a@]+)}%s*{([^}]*)}",
	"\\providecommand%s*{\\([%a@]+)}%s*{([^}]*)}",
	-- \newcommand\FOO{bar} (brace-less name form)
	"\\newcommand%s*\\([%a@]+)%s*{([^}]*)}",
	"\\renewcommand%s*\\([%a@]+)%s*{([^}]*)}",
	"\\providecommand%s*\\([%a@]+)%s*{([^}]*)}",
}

-- Expansion is a fixed-point loop; cap it so a self-referential definition
-- (`\def\A{\A/x}`, usually a typo) can never hang the editor.
local MAX_EXPANSION_PASSES = 16

-- Drop the LaTeX comment tail of a line: everything from the first `%` that is
-- not escaped as `\%`.  Without this, a commented-out redefinition is read as
-- a real one (see share/latex/templates/TNN.tex:251).
function M.strip_comments(line)
	local i = 1
	while i <= #line do
		local c = line:sub(i, i)
		if c == "\\" then
			i = i + 2 -- skip the escaped character, whatever it is
		elseif c == "%" then
			return line:sub(1, i - 1)
		else
			i = i + 1
		end
	end
	return line
end

-- Scan lines for path macro definitions.
-- Returns { ["\\FSfolder"] = "/home/luis/…", … }.
--
-- FIRST definition wins: a duplicate \newcommand is a LaTeX error, and the
-- first one is what a successful compile actually used.
function M.scan_macros(lines)
	local macros = {}
	for _, raw in ipairs(lines) do
		local line = M.strip_comments(raw)
		for _, pattern in ipairs(macro_patterns) do
			local pos = 1
			while true do
				local s, e, name, value = line:find(pattern, pos)
				if not s then
					break
				end
				local key = "\\" .. name
				if macros[key] == nil then
					macros[key] = value
				end
				pos = e + 1
			end
		end
	end
	return macros
end

-- Expand every known macro in `str` until it stops changing.
--
-- Substitution is anchored with a `%f[^%a@]` frontier so a control word only
-- matches at its real end: without it, `\FSfolder` would also rewrite the
-- prefix of `\FSfolderTwo` and silently corrupt the path.
function M.expand(str, macros)
	-- Deterministic order so repeated runs give identical output.
	local names = {}
	for name in pairs(macros) do
		names[#names + 1] = name
	end
	table.sort(names)

	for _ = 1, MAX_EXPANSION_PASSES do
		local previous = str
		for _, name in ipairs(names) do
			local value = macros[name]
			str = str:gsub(vim.pesc(name) .. "%f[^%a@]", function()
				return value
			end)
		end
		if str == previous then
			break
		end
	end
	return str
end

return M
