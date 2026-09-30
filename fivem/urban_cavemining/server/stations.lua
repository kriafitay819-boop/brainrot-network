-- Shop, buyer, smelter, stone cracking, jewel bench, stone washing and gold panning.
-- Every action is validated here: distance to the station, items, money and timing.

local STATION_RANGE = 6.0
local MAX_BATCH = 20

--──────────────────────────────── shop ───────────────────────────────────

lib.callback.register('urban_cavemining:buy', function(src, index, amount)
    local entry = Config.Shop[index]
    amount = math.floor(tonumber(amount) or 0)
    if not entry or amount < 1 or amount > 50 then return false end
    if not Server.near(src, Locations.Shop.coords, STATION_RANGE) then return false, L('too_far') end
    if entry.minLevel and Server.getLevel(src) < entry.minLevel then
        return false, L('locked_level', entry.minLevel)
    end
    local total = entry.price * amount
    if Bridge.getMoney(src) < total then return false, L('not_enough_money') end
    if not Bridge.canCarry(src, entry.item, amount) then return false, L('inventory_full') end
    if not Bridge.removeMoney(src, total, 'cave-mining-shop') then return false, L('not_enough_money') end
    Bridge.addItem(src, entry.item, amount)
    return true, L('bought', amount, Utils.itemLabel(entry.item), total)
end)

--──────────────────────────────── buyer ──────────────────────────────────

lib.callback.register('urban_cavemining:sell', function(src, item, amount)
    local price = Config.Buyer.prices[item]
    amount = math.floor(tonumber(amount) or 0)
    if not price or amount < 1 then return false end
    if not Server.near(src, Locations.Buyer.coords, STATION_RANGE) then return false, L('too_far') end
    local have = Bridge.count(src, item)
    if have < 1 then return false, L('nothing_to_sell') end
    amount = math.min(amount, have)
    if not Bridge.removeItem(src, item, amount) then return false, L('nothing_to_sell') end
    local total = price * amount
    Bridge.addMoney(src, total, 'cave-mining-buyer')
    return true, L('sold', amount, Utils.itemLabel(item), total)
end)

--──────────────────────────────── recipes (smelt / cut / craft) ──────────

local recipeStations = {
    smelt = { list = Config.Smelting.recipes,  where = Locations.Smelters,     time = Config.Smelting.time },
    cut   = { list = Config.JewelCutting.cut,   where = Locations.JewelCutting, time = Config.JewelCutting.time,
              drillbit = Config.JewelCutting.needsDrillbit and Config.JewelCutting.drillbitBreakChance or nil,
              failChance = Config.JewelCutting.failChance },
    craft = { list = Config.JewelCutting.craft, where = Locations.JewelCutting, time = Config.JewelCutting.time },
}

lib.callback.register('urban_cavemining:beginRecipe', function(src, stationKey, index, amount)
    local station = recipeStations[stationKey]
    local recipe = station and station.list[index]
    amount = math.floor(tonumber(amount) or 0)
    if not recipe or amount < 1 or amount > (Config.Smelting.maxBatch or MAX_BATCH) then return false end
    if not Bridge.hasJob(src) then return false, L('wrong_job') end
    if not Server.nearAny(src, station.where, STATION_RANGE) then return false, L('too_far') end
    if not Server.hasAll(src, recipe.needs, amount) then return false, L('not_enough') end
    if station.drillbit and Bridge.count(src, 'drillbit') < 1 then return false, L('need_drillbit') end

    local duration = station.time * amount
    if not Server.begin(src, 'recipe', { station = stationKey, index = index, amount = amount }, duration) then
        return false, L('busy')
    end
    return duration
end)

lib.callback.register('urban_cavemining:finishRecipe', function(src)
    local data = Server.finish(src, 'recipe')
    if not data then return false end
    local station = recipeStations[data.station]
    local recipe = station.list[data.index]
    if not Server.nearAny(src, station.where, STATION_RANGE) then return false, L('too_far') end

    local made = 0
    for _ = 1, data.amount do
        if station.drillbit and Bridge.count(src, 'drillbit') < 1 then
            Bridge.notify(src, L('need_drillbit'), 'error')
            break
        end
        if not Server.takeAll(src, recipe.needs, 1) then break end

        local shattered = station.failChance and math.random(100) <= station.failChance
        if shattered then
            Bridge.notify(src, L('gem_shattered'), 'error')
        else
            made = made + (recipe.amount or 1)
        end

        if station.drillbit and math.random(100) <= station.drillbit then
            Bridge.removeItem(src, 'drillbit', 1)
            Bridge.notify(src, L('bit_broke'), 'error')
        end
    end

    if made > 0 then
        Server.give(src, recipe.result, made)
        Server.addXp(src, math.ceil(made * 1.5))
    end
    return true
end)

--──────────────────────────────── loot actions (crack / wash / pan) ──────

local lootActions = {
    crack = {
        time = Config.Cracking.time, input = Config.Cracking.input, loot = Config.Cracking.loot,
        rolls = Config.Cracking.rolls or 1, where = Locations.Cracking,
        drillbit = Config.Cracking.needsDrillbit and Config.Cracking.drillbitBreakChance or nil,
    },
    wash = {
        time = Config.Washing.time, input = Config.Washing.input, loot = Config.Washing.loot,
        rolls = 1, tool = 'goldpan',
    },
    pan = {
        time = Config.Panning.time, loot = Config.Panning.loot, rolls = 1, tool = 'goldpan', single = true,
    },
}

lib.callback.register('urban_cavemining:beginLoot', function(src, key, amount)
    local action = lootActions[key]
    amount = math.floor(tonumber(amount) or 0)
    if not action or amount < 1 or amount > MAX_BATCH then return false end
    if action.single then amount = 1 end
    if not Bridge.hasJob(src) then return false, L('wrong_job') end
    if action.where and not Server.nearAny(src, action.where, STATION_RANGE) then return false, L('too_far') end
    if action.tool and Bridge.count(src, action.tool) < 1 then return false, L('no_tool', Utils.itemLabel(action.tool)) end
    if action.input and Bridge.count(src, action.input) < amount then return false, L('not_enough') end
    if action.drillbit and Bridge.count(src, 'drillbit') < 1 then return false, L('need_drillbit') end

    local duration = action.time * amount
    if not Server.begin(src, 'loot', { key = key, amount = amount }, duration) then return false, L('busy') end
    return duration
end)

lib.callback.register('urban_cavemining:finishLoot', function(src)
    local data = Server.finish(src, 'loot')
    if not data then return false end
    local action = lootActions[data.key]
    if action.where and not Server.nearAny(src, action.where, STATION_RANGE) then return false, L('too_far') end

    local found = {}
    local anything = false
    for _ = 1, data.amount do
        if action.drillbit and Bridge.count(src, 'drillbit') < 1 then
            Bridge.notify(src, L('need_drillbit'), 'error')
            break
        end
        if action.input and not Bridge.removeItem(src, action.input, 1) then break end

        for _ = 1, action.rolls do
            local item, count = Server.rollLoot(action.loot)
            if item then
                found[item] = (found[item] or 0) + count
                anything = true
            end
        end

        if action.drillbit and math.random(100) <= action.drillbit then
            Bridge.removeItem(src, 'drillbit', 1)
            Bridge.notify(src, L('bit_broke'), 'error')
        end
    end

    for item, count in pairs(found) do Server.give(src, item, count) end
    if not anything then Bridge.notify(src, L('found_nothing'), 'inform') end
    Server.addXp(src, data.amount)
    return true
end)

--──────────────────────────────── job center (foreman) ───────────────────

lib.callback.register('urban_cavemining:takeJob', function(src)
    local jc = Config.JobCenter
    if not jc.enabled then return false end
    if not Server.near(src, Locations.Foreman.coords, STATION_RANGE) then return false, L('too_far') end
    if Bridge.getJob(src) == jc.job then return false, L('already_miner') end
    if not Bridge.jobExists(jc.job, jc.grade) then return false, L('job_missing') end
    if not Bridge.setJob(src, jc.job, jc.grade) then return false, L('job_failed') end
    return true, L('job_taken')
end)

lib.callback.register('urban_cavemining:quitJob', function(src)
    local jc = Config.JobCenter
    if not jc.enabled then return false end
    if not Server.near(src, Locations.Foreman.coords, STATION_RANGE) then return false, L('too_far') end
    if Bridge.getJob(src) ~= jc.job then return false, L('not_miner') end
    if not Bridge.setJob(src, jc.quitJob, jc.quitGrade) then return false, L('job_failed') end
    return true, L('job_quit')
end)
