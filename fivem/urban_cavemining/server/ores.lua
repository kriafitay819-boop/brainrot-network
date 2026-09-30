-- Server-authoritative ore spots: the server decides what ore sits on each spot,
-- how much HP it has left, who broke it and when it grows back. Clients only draw it.

Ores = {}

local slots = {}      -- id -> { id, coords = vec4, ore, variant, hp, maxHp, depleted, respawnAt }
local sessions = {}   -- src -> { slot, tool, swing, lastHit }

local oreNames = {}
for name in pairs(Config.Ores) do oreNames[#oreNames + 1] = name end
table.sort(oreNames)

local function weightedOre()
    local total = 0
    for i = 1, #oreNames do total = total + Config.Ores[oreNames[i]].weight end
    local roll = math.random() * total
    for i = 1, #oreNames do
        roll = roll - Config.Ores[oreNames[i]].weight
        if roll <= 0 then return oreNames[i] end
    end
    return oreNames[#oreNames]
end

local function reroll(slot)
    slot.ore = weightedOre()
    local variants = Utils.oreVariants(slot.ore)
    slot.variant = math.random(1, math.max(1, #variants))
    slot.maxHp = Config.Ores[slot.ore].hp
    slot.hp = slot.maxHp
    slot.depleted = false
    slot.respawnAt = nil
end

local function public(slot)
    return {
        id = slot.id,
        coords = slot.coords,
        ore = slot.ore,
        variant = slot.variant,
        hp = slot.hp,
        maxHp = slot.maxHp,
        depleted = slot.depleted,
    }
end

function Ores.snapshot()
    local list = {}
    for _, slot in pairs(slots) do list[#list + 1] = public(slot) end
    table.sort(list, function(a, b) return a.id < b.id end)
    return list
end

local function broadcast(slot)
    TriggerClientEvent('urban_cavemining:client:oreUpdate', -1, public(slot))
end

--──────────────────────────────── positions ──────────────────────────────

local POSITIONS_FILE = 'data/positions.json'

function Ores.loadPositions()
    local raw = LoadResourceFile(GetCurrentResourceName(), POSITIONS_FILE)
    if raw then
        local ok, data = pcall(json.decode, raw)
        if ok and type(data) == 'table' and #data > 0 then
            local list = {}
            for i = 1, #data do
                local p = data[i]
                list[i] = vec4(p.x + 0.0, p.y + 0.0, p.z + 0.0, (p.w or 0.0) + 0.0)
            end
            return list, true
        end
    end
    return Locations.OrePositions, false
end

function Ores.positions()
    local list = {}
    for i = 1, #slots do list[i] = slots[i].coords end
    return list
end

function Ores.savePositions(list)
    local out = {}
    for i = 1, #list do
        local c = list[i]
        out[i] = { x = math.floor(c.x * 100 + 0.5) / 100, y = math.floor(c.y * 100 + 0.5) / 100,
                   z = math.floor(c.z * 100 + 0.5) / 100, w = math.floor(c.w * 100 + 0.5) / 100 }
    end
    SaveResourceFile(GetCurrentResourceName(), POSITIONS_FILE, json.encode(out, { indent = true }), -1)
end

function Ores.rebuild(positions)
    slots = {}
    sessions = {}
    for i = 1, #positions do
        slots[i] = { id = i, coords = positions[i] }
        reroll(slots[i])
    end
    TriggerClientEvent('urban_cavemining:client:allOres', -1, Ores.snapshot())
end

function Ores.respawnAll()
    for _, slot in pairs(slots) do reroll(slot) end
    TriggerClientEvent('urban_cavemining:client:allOres', -1, Ores.snapshot())
end

CreateThread(function()
    local positions, custom = Ores.loadPositions()
    Ores.rebuild(positions)
    print(('^2[urban_cavemining]^7 %d ore spots loaded (%s)'):format(#positions, custom and 'data/positions.json' or 'default K4MB1 layout'))
end)

lib.callback.register('urban_cavemining:getOres', function()
    return Ores.snapshot()
end)

--──────────────────────────────── respawn ────────────────────────────────

CreateThread(function()
    while true do
        Wait(5000)
        local now = os.time()
        for _, slot in pairs(slots) do
            if slot.depleted and slot.respawnAt and now >= slot.respawnAt then
                reroll(slot)
                broadcast(slot)
            end
        end
    end
end)

--──────────────────────────────── mining ─────────────────────────────────

local function bestTool(src, allowed)
    local allowedSet = {}
    for i = 1, #allowed do allowedSet[allowed[i]] = true end
    for i = 1, #Config.ToolOrder do
        local tool = Config.ToolOrder[i]
        if allowedSet[tool] and Bridge.count(src, tool) > 0 then
            local consumes = Config.Tools[tool].consumes
            if not consumes or Bridge.count(src, consumes.item) > 0 then
                return tool
            end
        end
    end
    return nil
end

local function reward(src, slot)
    local ore = Config.Ores[slot.ore]
    local multiplier = 1
    if Config.Levels.enabled then
        local chance = (Server.getLevel(src) - 1) * Config.Levels.doubleDropPerLevel
        if math.random() < chance then multiplier = 2 end
    end
    for i = 1, #ore.rewards do
        local r = ore.rewards[i]
        Server.give(src, r.item, math.random(r.min, r.max) * multiplier)
    end
    local bonus = Config.StoneBonus
    if bonus and math.random(100) <= bonus.chance then
        Server.give(src, bonus.item, math.random(bonus.min, bonus.max))
    end
    Server.addXp(src, ore.xp or 0)
end

local function deplete(slot)
    slot.depleted = true
    slot.hp = 0
    slot.respawnAt = os.time() + math.random(Config.Respawn.min, Config.Respawn.max)
    broadcast(slot)
end

lib.callback.register('urban_cavemining:startMining', function(src, slotId)
    local slot = slots[slotId]
    if not slot then return false end
    if not Bridge.hasJob(src) then return false, L('wrong_job') end
    if slot.depleted then return false, L('depleted') end
    if not Server.near(src, slot.coords) then return false, L('too_far') end

    local ore = Config.Ores[slot.ore]
    local level = Server.getLevel(src)
    if Config.Levels.enabled and level < (ore.minLevel or 1) then
        return false, L('need_level', ore.minLevel)
    end

    local tool = bestTool(src, ore.tools)
    if not tool then return false, L('no_tool', Utils.toolLabels(ore.tools)) end

    local swing = Utils.swingTime(tool, level)
    sessions[src] = { slot = slotId, tool = tool, swing = swing, lastHit = GetGameTimer() }

    return { tool = tool, swing = swing, hp = slot.hp, maxHp = slot.maxHp, ore = slot.ore }
end)

lib.callback.register('urban_cavemining:hit', function(src, slotId)
    local session = sessions[src]
    if not session or session.slot ~= slotId then return false end

    local now = GetGameTimer()
    if now - session.lastHit < session.swing * 0.8 then
        -- faster than the progress bar allows: ignore the hit
        return false
    end
    session.lastHit = now

    local slot = slots[slotId]
    if not slot or slot.depleted then
        sessions[src] = nil
        return { done = true }
    end
    if not Server.near(src, slot.coords) or Bridge.count(src, session.tool) < 1 then
        sessions[src] = nil
        return false
    end

    local tool = Config.Tools[session.tool]
    local result = {}

    if tool.consumes then
        if Bridge.count(src, tool.consumes.item) < 1 then
            sessions[src] = nil
            Bridge.notify(src, L('need_drillbit'), 'error')
            return { stop = true }
        end
        if math.random(100) <= tool.consumes.chance then
            Bridge.removeItem(src, tool.consumes.item, 1)
            Bridge.notify(src, L('bit_broke'), 'error')
        end
    end

    slot.hp = slot.hp - tool.power
    result.hp = math.max(0, slot.hp)
    result.maxHp = slot.maxHp

    if slot.hp <= 0 then
        sessions[src] = nil
        deplete(slot)
        reward(src, slot)
        result.done = true
    end

    if tool.breakChance > 0 and math.random(100) <= tool.breakChance then
        Bridge.removeItem(src, session.tool, 1)
        Bridge.notify(src, L('tool_broke', Utils.itemLabel(session.tool)), 'error')
        sessions[src] = nil
        result.stop = true
    end

    return result
end)

RegisterNetEvent('urban_cavemining:server:stopMining', function()
    sessions[source] = nil
end)

AddEventHandler('playerDropped', function()
    sessions[source] = nil
end)

--──────────────────────────────── admin: reset ───────────────────────────

lib.addCommand(Config.Admin.resetCommand, {
    help = 'Respawn every ore in the mining cave',
    restricted = Config.Admin.group,
}, function(source)
    Ores.respawnAll()
    if source > 0 then Bridge.notify(source, L('reset_done'), 'success') end
end)
