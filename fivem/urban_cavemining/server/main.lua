Server = {}

local RESOURCE = GetCurrentResourceName()

--──────────────────────────────── helpers ────────────────────────────────

function Server.near(src, coords, maxDistance)
    local ped = GetPlayerPed(src)
    if not ped or ped == 0 then return false end
    local pos = GetEntityCoords(ped)
    return #(pos - vec3(coords.x, coords.y, coords.z)) <= (maxDistance or Config.ServerMaxDistance)
end

function Server.nearAny(src, list, maxDistance)
    for i = 1, #list do
        local coords = list[i].coords or list[i]
        if Server.near(src, coords, maxDistance) then return true end
    end
    return false
end

--- Cumulative loot roll: each entry has its own % chance, at most one entry wins
function Server.rollLoot(loot)
    local roll = math.random() * 100.0
    local acc = 0.0
    for i = 1, #loot do
        local entry = loot[i]
        acc = acc + entry.chance
        if roll < acc then
            return entry.item, math.random(entry.min, entry.max)
        end
    end
    return nil, 0
end

function Server.give(src, item, amount)
    if amount <= 0 then return true end
    if not Bridge.canCarry(src, item, amount) then
        Bridge.notify(src, L('inventory_full'), 'error')
        return false
    end
    if Bridge.addItem(src, item, amount) then
        Bridge.notify(src, L('received', amount, Utils.itemLabel(item)), 'success')
        return true
    end
    return false
end

function Server.hasAll(src, needs, multiplier)
    multiplier = multiplier or 1
    for item, amount in pairs(needs) do
        if Bridge.count(src, item) < amount * multiplier then return false end
    end
    return true
end

function Server.takeAll(src, needs, multiplier)
    multiplier = multiplier or 1
    if not Server.hasAll(src, needs, multiplier) then return false end
    for item, amount in pairs(needs) do
        if not Bridge.removeItem(src, item, amount * multiplier) then return false end
    end
    return true
end

--──────────────────────────────── XP / levels ────────────────────────────

local function xpKey(src)
    local id = Bridge.getIdentifier(src)
    return id and ('xp:' .. id) or nil
end

function Server.getXp(src)
    local key = xpKey(src)
    if not key then return 0 end
    return GetResourceKvpInt(key)
end

function Server.getLevel(src)
    if not Config.Levels.enabled then return #Config.Levels.xp end
    return (Utils.levelFromXp(Server.getXp(src)))
end

function Server.addXp(src, amount)
    if not Config.Levels.enabled or amount == 0 then return end
    local key = xpKey(src)
    if not key then return end
    local before = GetResourceKvpInt(key)
    local after = math.max(0, before + amount)
    SetResourceKvpInt(key, after)
    TriggerClientEvent('urban_cavemining:client:xp', src, after, amount)
    local oldLevel = Utils.levelFromXp(before)
    local newLevel = Utils.levelFromXp(after)
    if newLevel > oldLevel then
        Bridge.notify(src, L('level_up', newLevel), 'success')
    end
end

lib.callback.register('urban_cavemining:getXp', function(src)
    return Server.getXp(src)
end)

--──────────────────────────────── timed actions ──────────────────────────
-- A timed action (smelting, cutting, washing...) is started on the server,
-- the client plays the progress bar, then asks the server to finish it.
-- The server refuses to finish early, so no item can be made faster than the timer.

local pending = {}

function Server.begin(src, kind, data, duration)
    if pending[src] then return false end
    pending[src] = {
        kind = kind,
        data = data,
        readyAt = GetGameTimer() + math.floor(duration * 0.85),
    }
    return true
end

function Server.finish(src, kind)
    local action = pending[src]
    pending[src] = nil
    if not action or action.kind ~= kind then return nil end
    if GetGameTimer() < action.readyAt then return nil end
    return action.data
end

RegisterNetEvent('urban_cavemining:server:cancel', function()
    pending[source] = nil
end)

AddEventHandler('playerDropped', function()
    pending[source] = nil
end)

--──────────────────────────────── inventory lookups ──────────────────────

lib.callback.register('urban_cavemining:getCounts', function(src, list)
    local counts = {}
    if type(list) ~= 'table' then return counts end
    for i = 1, math.min(#list, 80) do
        local name = list[i]
        if Items[name] then counts[name] = Bridge.count(src, name) end
    end
    return counts
end)

--──────────────────────────────── usable items (qb / esx) ────────────────

Bridge.registerUsable('goldpan', 'urban_cavemining:client:useGoldpan')
Bridge.registerUsable(Config.Headlamp.item, 'urban_cavemining:client:useHelmet')

--──────────────────────────────── admin: xp ──────────────────────────────

lib.addCommand(Config.Admin.xpCommand, {
    help = 'Give (or take) mining XP',
    params = {
        { name = 'target', type = 'playerId', help = 'Player server id' },
        { name = 'amount', type = 'number', help = 'XP amount (negative to remove)' },
    },
    restricted = Config.Admin.group,
}, function(source, args)
    Server.addXp(args.target, args.amount)
    if source > 0 then Bridge.notify(source, L('xp_set', args.amount, args.target), 'success') end
end)

Server.resource = RESOURCE
