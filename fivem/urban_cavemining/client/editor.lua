-- Admin ore spot editor (/caveeditor). Aim at a rock face:
--   [E] add a spot   [G] remove the nearest spot   [SCROLL] rotate   [BACKSPACE] exit

local editing = false
local heading = 0.0

local function text3d(coords, text)
    SetDrawOrigin(coords.x, coords.y, coords.z, 0)
    SetTextScale(0.32, 0.32)
    SetTextFont(4)
    SetTextCentre(true)
    SetTextOutline()
    BeginTextCommandDisplayText('STRING')
    AddTextComponentSubstringPlayerName(text)
    EndTextCommandDisplayText(0.0, 0.0)
    ClearDrawOrigin()
end

local function nearestSlot(point, maxDistance)
    local bestId, bestDist = nil, maxDistance
    for id, slot in pairs(Client.ores) do
        local dist = #(point - slot.coords.xyz)
        if dist < bestDist then bestId, bestDist = id, dist end
    end
    return bestId
end

local function editorLoop()
    local place = Config.PropPlacement[Config.PropSet]
    lib.showTextUI(L('editor_help'), { position = 'top-center', icon = 'pen-ruler' })
    while editing do
        DisableControlAction(0, 14, true)
        DisableControlAction(0, 15, true)
        DisableControlAction(0, 16, true)
        DisableControlAction(0, 17, true)
        DisableControlAction(0, 24, true)

        -- existing spots
        for id, slot in pairs(Client.ores) do
            local c = slot.coords
            DrawMarker(28, c.x, c.y, c.z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.25, 0.25,
                slot.depleted and 120 or 40, slot.depleted and 120 or 200, 60, 140, false, false, 2, false, nil, nil, false)
            text3d(vec3(c.x, c.y, c.z + 0.45), ('#%d %s'):format(id, slot.ore))
        end

        local hit, _, endCoords = lib.raycast.cam(1 | 16, 4, 25.0)
        if hit then
            if IsDisabledControlJustPressed(0, 15) or IsControlJustPressed(0, 241) then heading = (heading + 15.0) % 360.0 end
            if IsDisabledControlJustPressed(0, 14) or IsControlJustPressed(0, 242) then heading = (heading - 15.0) % 360.0 end

            DrawMarker(28, endCoords.x, endCoords.y, endCoords.z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.3, 0.3,
                255, 200, 0, 170, false, false, 2, false, nil, nil, false)
            local rad = math.rad(heading)
            DrawLine(endCoords.x, endCoords.y, endCoords.z,
                endCoords.x - math.sin(rad) * 0.8, endCoords.y + math.cos(rad) * 0.8, endCoords.z, 255, 200, 0, 255)
            text3d(vec3(endCoords.x, endCoords.y, endCoords.z + 0.35), ('%.1f°'):format(heading))

            if IsControlJustPressed(0, 38) then
                TriggerServerEvent('urban_cavemining:server:editorAdd',
                    vec4(endCoords.x, endCoords.y, endCoords.z - place.z, heading))
            elseif IsControlJustPressed(0, 47) then
                local id = nearestSlot(endCoords, 3.0)
                if id then TriggerServerEvent('urban_cavemining:server:editorRemove', id) end
            end
        end

        if IsControlJustPressed(0, 177) then
            editing = false
        end
        Wait(0)
    end
    lib.hideTextUI()
    Bridge.notify(L('editor_off'), 'inform')
end

RegisterNetEvent('urban_cavemining:client:toggleEditor', function()
    editing = not editing
    if editing then
        Bridge.notify(L('editor_on'), 'success')
        CreateThread(editorLoop)
    end
end)

RegisterNetEvent('urban_cavemining:client:printCoords', function()
    local pos = GetEntityCoords(cache.ped)
    local text = ('vec4(%.2f, %.2f, %.2f, %.1f)'):format(pos.x, pos.y, pos.z, GetEntityHeading(cache.ped))
    print('[urban_cavemining] ' .. text)
    lib.setClipboard(text)
    Bridge.notify(L('coords_copied', text), 'success')
end)
