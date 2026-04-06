-- lua/workflow/statusline.lua
local M = {}

function M.component(get_client)
  return function()
    local server = require("workflow.server")
    return server.status_text(get_client())
  end
end

return M
