Client = {
    ores = {},      -- id -> slot data from the server (+ streamed flag)
    props = {},     -- id -> { entity, model }
    inCave = false,
    busy = false,
    xp = 0,
}

local blips = {}

--──────────────────────────────── props ──────────────────────────────────

local function loadModel(model)
    local hash = type(model) == 'number' and model or GetHashKey(model)
    if not IsModelInCdimage(hash) then
        Utils.debug(('model %s is not streamed (is k4mb1-caveprops started?)'):format(model))
        return nil
    end
    local ok = pcall(lib.requestModel, hash, 10000)
    return ok and hash or nil
end
Client.loadModel = loadModel

local function spawnOreProp(id, model, coords)
    local hash = loadModel(model)
    if not hash then return nil end
    local place = Config.PropPlacement[Config.PropSet]
    local entity = CreateObjectNoOffset(hash, coords.x, coords.y, coords.z + place.z, false, false, false)
    SetEntityRotation(entity, -Utils.slotTilt(id) + 0.0, 0.0, coords.w + 0.0, 2, false)
    FreezeEntityPosition(entity, true)
    SetEntityInvincible(entity, true)
    SetModelAsNoLongerNeeded(hash)
    return entity
end

local function deleteSlotProp(id)
    local prop = Client.props[id]
    if prop and DoesEntityExist(prop.entity) then DeleteEntity(prop.entity) end
    Client.props[id] = nil
end

local function currentModel(slot)
    local variants = Utils.oreVariants(slot.ore)
    local variant = variants[slot.variant] or variants[1]
    if not variant then return nil end
    if slot.depleted then return variant.empty end
    return variant.full
end

--──────────────────────────────── zones ──────────────────────────────────

local function zoneName(id) return 'urban_cavemining_ore_' .. id end

local function addSlotZone(id)
    local slot = Client.ores[id]
    if not slot then return end
    Bridge.addZone(zoneName(id), slot.coords.xyz, 1.3, {
        {
            name = 'urban_cavemining_mine',
            label = L('target_mine', L('ore_' .. slot.ore)),
            icon = 'fas fa-hammer',
            canInteract = function()
                local s = Client.ores[id]
                return not Client.busy and s ~= nil and not s.depleted
            end,
            onSelect = function() Mining.start(id) end,
        },
    })
end

local function streamIn(id)
    local slot = Client.ores[id]
    if not slot then return end
    slot.streamed = true
    deleteSlotProp(id)
    local model = currentModel(slot)
    if model then
        local entity = spawnOreProp(id, model, slot.coords)
        if entity then Client.props[id] = { entity = entity, model = model } end
    end
    addSlotZone(id)
end

local function streamOut(id)
    local slot = Client.ores[id]
    if slot then slot.streamed = false end
    deleteSlotProp(id)
    Bridge.removeZone(zoneName(id))
end

local function clearAll()
    for id in pairs(Client.ores) do streamOut(id) end
    Client.ores = {}
end

--──────────────────────────────── sync ───────────────────────────────────

local function setAll(list)
    clearAll()
    for i = 1, #list do
        local slot = list[i]
        slot.streamed = false
        Client.ores[slot.id] = slot
    end
end

RegisterNetEvent('urban_cavemining:client:allOres', function(list)
    setAll(list or {})
end)

RegisterNetEvent('urban_cavemining:client:oreUpdate', function(slot)
    local old = Client.ores[slot.id]
    local wasStreamed = old and old.streamed
    slot.streamed = false
    Client.ores[slot.id] = slot
    if wasStreamed then streamIn(slot.id) end
end)

RegisterNetEvent('urban_cavemining:client:xp', function(total, gained)
    Client.xp = total
    if gained and gained > 0 then
        lib.notify({ description = L('xp_gain', gained), type = 'inform', icon = 'star', duration = 2000 })
    end
end)

--──────────────────────────────── streaming loop ─────────────────────────

CreateThread(function()
    -- initial state (retry until the server side is ready)
    for _ = 1, 20 do
        local list = lib.callback.await('urban_cavemining:getOres', false)
        if list then setAll(list) break end
        Wait(1500)
    end
    Client.xp = lib.callback.await('urban_cavemining:getXp', false) or 0

    local center = Locations.Cave.center
    while true do
        local pos = GetEntityCoords(cache.ped)
        Client.inCave = #(pos - center) <= Locations.Cave.radius

        if Client.inCave then
            for id, slot in pairs(Client.ores) do
                local dist = #(pos - slot.coords.xyz)
                if dist <= Config.StreamDistance then
                    if not slot.streamed then streamIn(id) end
                elseif slot.streamed and dist > Config.StreamDistance + 5.0 then
                    streamOut(id)
                end
            end
            Wait(1000)
        else
            for id, slot in pairs(Client.ores) do
                if slot.streamed then streamOut(id) end
            end
            Wait(2500)
        end
    end
end)

--──────────────────────────────── crystal glow ───────────────────────────

CreateThread(function()
    while true do
        local sleep = 1500
        if Client.inCave then
            sleep = 0
            for _, slot in pairs(Client.ores) do
                local light = slot.streamed and not slot.depleted and Config.Ores[slot.ore].light
                if light then
                    local c = slot.coords
                    DrawLightWithRange(c.x, c.y, c.z + 0.2, light.r, light.g, light.b, 3.0, 2.5)
                end
            end
        end
        Wait(sleep)
    end
end)

--──────────────────────────────── blips ──────────────────────────────────

local function makeBlip(coords, sprite, color, scale, label)
    local blip = AddBlipForCoord(coords.x, coords.y, coords.z)
    SetBlipSprite(blip, sprite)
    SetBlipColour(blip, color)
    SetBlipScale(blip, scale or 0.8)
    SetBlipAsShortRange(blip, true)
    BeginTextCommandSetBlipName('STRING')
    AddTextComponentSubstringPlayerName(label)
    EndTextCommandSetBlipName(blip)
    blips[#blips + 1] = blip
    return blip
end

CreateThread(function()
    local b = Locations.Cave.blip
    if b.enabled then makeBlip(b.coords, b.sprite, b.color, b.scale, L('blip_cave')) end
    for i = 1, #Locations.WaterSpots do
        local spot = Locations.WaterSpots[i]
        makeBlip(spot.coords, spot.sprite, spot.color, 0.7, L('blip_' .. spot.label))
    end
end)

--──────────────────────────────── level command ──────────────────────────

function Client.levelText()
    local level, _, nextXp = Utils.levelFromXp(Client.xp)
    if nextXp then return L('level_info', level, Client.xp, nextXp) end
    return L('level_max', level, Client.xp)
end

RegisterCommand('mininglevel', function()
    Client.xp = lib.callback.await('urban_cavemining:getXp', false) or Client.xp
    Bridge.notify(Client.levelText(), 'inform')
end, false)

--──────────────────────────────── cleanup ────────────────────────────────

AddEventHandler('onResourceStop', function(name)
    if name ~= GetCurrentResourceName() then return end
    clearAll()
    for i = 1, #blips do RemoveBlip(blips[i]) end
end)
