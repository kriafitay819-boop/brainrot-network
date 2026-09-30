-- Mining helmet: use the item to wear the hard hat and toggle its head lamp.
-- The beam follows the camera and casts shadows, so the cave feels properly dark.

local lamp = { on = false, hat = nil }
local cfg = Config.Headlamp

local function removeHat()
    if lamp.hat and DoesEntityExist(lamp.hat) then DeleteEntity(lamp.hat) end
    lamp.hat = nil
end

local function attachHat()
    removeHat()
    local hash = Client.loadModel(cfg.prop.model)
    if not hash then return end
    local ped = cache.ped
    local pos = GetEntityCoords(ped)
    local hat = CreateObject(hash, pos.x, pos.y, pos.z + 0.5, true, true, false)
    AttachEntityToEntity(hat, ped, GetPedBoneIndex(ped, cfg.prop.bone),
        cfg.prop.pos.x, cfg.prop.pos.y, cfg.prop.pos.z,
        cfg.prop.rot.x, cfg.prop.rot.y, cfg.prop.rot.z,
        true, true, false, true, 1, true)
    SetModelAsNoLongerNeeded(hash)
    lamp.hat = hat
end

local function beamDirection()
    local rot = GetGameplayCamRot(2)
    local pitch, yaw = math.rad(rot.x), math.rad(rot.z)
    return vec3(-math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch))
end

local function lampLoop()
    CreateThread(function()
        local shadowId = 7101
        local checkAt = 0
        while lamp.on do
            local ped = cache.ped
            if not cfg.onlyInCave or Client.inCave then
                local head = GetPedBoneCoords(ped, 31086, 0.15, 0.0, 0.0)
                local dir = beamDirection()
                DrawSpotLightWithShadow(head.x, head.y, head.z, dir.x, dir.y, dir.z,
                    cfg.color.r, cfg.color.g, cfg.color.b,
                    cfg.distance, cfg.brightness, cfg.roundness, cfg.radius, cfg.falloff, shadowId)
            end

            -- turn off if the helmet left the inventory
            if GetGameTimer() > checkAt then
                checkAt = GetGameTimer() + 5000
                CreateThread(function()
                    local have = lib.callback.await('urban_cavemining:getCounts', false, { cfg.item }) or {}
                    if (have[cfg.item] or 0) < 1 and lamp.on then
                        lamp.on = false
                        removeHat()
                        Bridge.notify(L('headlamp_off'), 'inform')
                    end
                end)
            end
            Wait(0)
        end
    end)
end

local function toggle()
    lamp.on = not lamp.on
    if lamp.on then
        attachHat()
        lampLoop()
        Bridge.notify(L('headlamp_on'), 'success')
    else
        removeHat()
        Bridge.notify(L('headlamp_off'), 'inform')
    end
end

RegisterNetEvent('urban_cavemining:client:useHelmet', toggle)

exports('useHelmet', function()
    toggle()
end)

AddEventHandler('onResourceStop', function(name)
    if name == GetCurrentResourceName() then
        lamp.on = false
        removeHat()
    end
end)
