-- lua/workflow/telescope/init.lua
-- Telescope extension registration for WorkFlow pickers

local has_telescope, telescope = pcall(require, "telescope")

if not has_telescope then
  return {}
end

return telescope.register_extension({
  exports = {
    evaluations = require("workflow.telescope.evaluations").picker,
    items = require("workflow.telescope.items").picker,
    courses = require("workflow.telescope.courses").picker,
  },
})
