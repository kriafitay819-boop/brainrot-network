-- In-game ore spot editor. /caveeditor toggles it for admins; every change is
-- written to data/positions.json, which overrides the default K4MB1 layout.

local ACE = 'command.' .. Config.Admin.editorCommand

local function allowed(src)
    return IsPlayerAceAllowed(src, ACE)
end

lib.addCommand(Config.Admin.editorCommand, {
    help = 'Toggle the mining cave ore spot editor',
    restricted = Config.Admin.group,
}, function(source)
    if source <= 0 then return end
    TriggerClientEvent('urban_cavemining:client:toggleEditor', source)
end)

RegisterNetEvent('urban_cavemining:server:editorAdd', function(coords)
    local src = source
    if not allowed(src) then return Bridge.notify(src, L('no_permission'), 'error') end
    if type(coords) ~= 'vector4' and type(coords) ~= 'table' then return end
    local positions = Ores.positions()
    positions[#positions + 1] = vec4(coords.x + 0.0, coords.y + 0.0, coords.z + 0.0, (coords.w or 0.0) + 0.0)
    Ores.savePositions(positions)
    Ores.rebuild(positions)
    Bridge.notify(src, L('editor_added', #positions), 'success')
end)

RegisterNetEvent('urban_cavemining:server:editorRemove', function(slotId)
    local src = source
    if not allowed(src) then return Bridge.notify(src, L('no_permission'), 'error') end
    local positions = Ores.positions()
    if not positions[slotId] then return end
    table.remove(positions, slotId)
    Ores.savePositions(positions)
    Ores.rebuild(positions)
    Bridge.notify(src, L('editor_removed', slotId), 'success')
    Bridge.notify(src, L('editor_saved', #positions), 'inform')
end)
