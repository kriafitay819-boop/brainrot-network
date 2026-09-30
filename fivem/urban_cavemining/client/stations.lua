-- Peds, benches and every menu: shop, buyer, smelter, stone cracking, jewel bench.

Stations = {}

local spawned = { peds = {}, props = {} }
local GROUND = 1.03

local ANIM_SMELT = { dict = 'amb@prop_human_parking_meter@male@idle_a', clip = 'idle_a', flag = 1 }
local ANIM_BENCH = { dict = 'anim@amb@machinery@speed_drill@', clip = 'operate_02_hi_amy_skater_01', flag = 1 }
local DISABLE    = { move = true, car = true, combat = true, sprint = true }

--──────────────────────────────── helpers ────────────────────────────────

local function counts(list)
    return lib.callback.await('urban_cavemining:getCounts', false, list) or {}
end

local function needsList(needs, list)
    list = list or {}
    for item in pairs(needs) do list[#list + 1] = item end
    return list
end

local function maxCraftable(needs, have)
    local max = 20
    for item, amount in pairs(needs) do
        max = math.min(max, math.floor((have[item] or 0) / amount))
    end
    return max
end

local function askAmount(max, default)
    if max < 1 then return nil end
    if max == 1 then return 1 end
    local input = lib.inputDialog(L('amount'), {
        { type = 'slider', label = L('amount'), min = 1, max = max, default = default or max, step = 1 },
    })
    return input and tonumber(input[1]) or nil
end

local function level()
    return (Utils.levelFromXp(Client.xp))
end

--- effect runs while the progress bar is on screen
local function withEffect(effect)
    local state = { active = true }
    if effect then CreateThread(function() effect(state) end) end
    return state
end

local function runTimed(beginName, finishName, args, label, anim, effect)
    if Client.busy then return Bridge.notify(L('busy'), 'error') end
    local duration, err = lib.callback.await(beginName, false, table.unpack(args))
    if not duration then
        if err then Bridge.notify(err, 'error') end
        return
    end
    Client.busy = true
    local state = withEffect(effect)
    local finished = lib.progressBar({
        duration = duration,
        label = label,
        useWhileDead = false,
        canCancel = true,
        disable = DISABLE,
        anim = anim,
    })
    state.active = false
    if finished then
        local ok, finishErr = lib.callback.await(finishName, false)
        if not ok and finishErr then Bridge.notify(finishErr, 'error') end
    else
        TriggerServerEvent('urban_cavemining:server:cancel')
        Bridge.notify(L('cancelled'), 'inform')
    end
    ClearPedTasks(cache.ped)
    Client.busy = false
end
Stations.runTimed = runTimed

local function benchDust(coords)
    return function(state)
        local soundId = GetSoundId()
        RequestAmbientAudioBank('DLC_HEIST_FLEECA_SOUNDSET', false)
        PlaySoundFromCoord(soundId, 'Drill', coords.x, coords.y, coords.z, 'DLC_HEIST_FLEECA_SOUNDSET', false, 4.5, false)
        while state.active do
            lib.requestNamedPtfxAsset('core')
            UseParticleFxAssetNextCall('core')
            StartParticleFxNonLoopedAtCoord('ent_dst_rocks', coords.x, coords.y, coords.z - 0.3, 0.0, 0.0, 0.0, 0.25, false, false, false)
            Wait(800)
        end
        StopSound(soundId)
        ReleaseSoundId(soundId)
    end
end

local function furnaceGlow(coords)
    return function(state)
        while state.active do
            DrawLightWithRange(coords.x, coords.y, coords.z + 0.5, 255, 110, 20, 5.0, 8.0)
            Wait(0)
        end
    end
end

--──────────────────────────────── shop ───────────────────────────────────

function Stations.openShop()
    local options = {}
    local myLevel = level()
    for i, entry in ipairs(Config.Shop) do
        local locked = Config.Levels.enabled and entry.minLevel and myLevel < entry.minLevel
        options[#options + 1] = {
            title = Utils.itemLabel(entry.item),
            description = locked and L('locked_level', entry.minLevel) or L('price_each', entry.price),
            icon = locked and 'lock' or 'cart-shopping',
            disabled = locked or false,
            onSelect = function()
                local amount = askAmount(10, 1)
                if not amount then return end
                local ok, message = lib.callback.await('urban_cavemining:buy', false, i, amount)
                if message then Bridge.notify(message, ok and 'success' or 'error') end
            end,
        }
    end
    options[#options + 1] = { title = Client.levelText(), icon = 'star', readOnly = true }
    lib.registerContext({ id = 'urban_cavemining_shop', title = L('shop_title'), options = options })
    lib.showContext('urban_cavemining_shop')
end

--──────────────────────────────── buyer ──────────────────────────────────

local function sellItem(item, have, price)
    local menuId = 'urban_cavemining_sell_item'
    lib.registerContext({
        id = menuId,
        title = Utils.itemLabel(item),
        menu = 'urban_cavemining_buyer',
        options = {
            {
                title = L('sell_all', have, have * price),
                icon = 'sack-dollar',
                onSelect = function()
                    local ok, message = lib.callback.await('urban_cavemining:sell', false, item, have)
                    if message then Bridge.notify(message, ok and 'success' or 'error') end
                end,
            },
            {
                title = L('sell_some'),
                icon = 'hashtag',
                onSelect = function()
                    local input = lib.inputDialog(Utils.itemLabel(item), {
                        { type = 'number', label = L('amount'), min = 1, max = have, default = 1 },
                    })
                    local amount = input and tonumber(input[1])
                    if not amount then return end
                    local ok, message = lib.callback.await('urban_cavemining:sell', false, item, amount)
                    if message then Bridge.notify(message, ok and 'success' or 'error') end
                end,
            },
        },
    })
    lib.showContext(menuId)
end

function Stations.openBuyer()
    local all = {}
    for _, cat in ipairs(Config.Buyer.categories) do
        for _, item in ipairs(cat.items) do all[#all + 1] = item end
    end
    local have = counts(all)

    local root = {}
    for _, cat in ipairs(Config.Buyer.categories) do
        local rows, total = {}, 0
        for _, item in ipairs(cat.items) do
            local count = have[item] or 0
            local price = Config.Buyer.prices[item] or 0
            if count > 0 and price > 0 then
                total = total + count * price
                rows[#rows + 1] = {
                    title = ('%s  x%d'):format(Utils.itemLabel(item), count),
                    description = L('price_each', price),
                    icon = 'coins',
                    onSelect = function() sellItem(item, count, price) end,
                }
            end
        end
        if #rows > 0 then
            local subId = 'urban_cavemining_buyer_' .. cat.key
            lib.registerContext({ id = subId, title = L('category_' .. cat.key), menu = 'urban_cavemining_buyer', options = rows })
            root[#root + 1] = {
                title = L('category_' .. cat.key),
                description = ('$%d'):format(total),
                icon = 'box-open',
                menu = subId,
            }
        end
    end
    if #root == 0 then return Bridge.notify(L('nothing_to_sell'), 'error') end
    lib.registerContext({ id = 'urban_cavemining_buyer', title = L('buyer_title'), options = root })
    lib.showContext('urban_cavemining_buyer')
end

--──────────────────────────────── recipe menus ───────────────────────────

local function recipeOptions(stationKey, list, have, labelKey, anim, effect, parent)
    local options = {}
    for i, recipe in ipairs(list) do
        local max = maxCraftable(recipe.needs, have)
        local amountText = (recipe.amount or 1) > 1 and (' x' .. recipe.amount) or ''
        options[#options + 1] = {
            title = Utils.itemLabel(recipe.result) .. amountText,
            description = L('needs', Utils.needsText(recipe.needs)),
            icon = max > 0 and 'fire' or 'ban',
            disabled = max < 1,
            onSelect = function()
                local amount = askAmount(max, 1)
                if not amount then return end
                runTimed('urban_cavemining:beginRecipe', 'urban_cavemining:finishRecipe', { stationKey, i, amount },
                    L(labelKey, Utils.itemLabel(recipe.result)), anim, effect)
            end,
        }
    end
    return options
end

function Stations.openSmelter(coords)
    local items = {}
    for _, recipe in ipairs(Config.Smelting.recipes) do needsList(recipe.needs, items) end
    local have = counts(items)
    lib.registerContext({
        id = 'urban_cavemining_smelter',
        title = L('smelter_title'),
        options = recipeOptions('smelt', Config.Smelting.recipes, have, 'smelting', ANIM_SMELT, furnaceGlow(coords)),
    })
    lib.showContext('urban_cavemining_smelter')
end

function Stations.openJewelBench(coords)
    local items = { 'drillbit' }
    for _, recipe in ipairs(Config.JewelCutting.cut) do needsList(recipe.needs, items) end
    for _, recipe in ipairs(Config.JewelCutting.craft) do needsList(recipe.needs, items) end
    local have = counts(items)

    local cutOptions = recipeOptions('cut', Config.JewelCutting.cut, have, 'cutting', ANIM_BENCH, benchDust(coords))
    if Config.JewelCutting.needsDrillbit and (have.drillbit or 0) < 1 then
        for i = 1, #cutOptions do
            cutOptions[i].disabled = true
            cutOptions[i].description = L('need_drillbit')
        end
    end

    lib.registerContext({ id = 'urban_cavemining_cut', title = L('cut_section'), menu = 'urban_cavemining_jewel', options = cutOptions })
    lib.registerContext({ id = 'urban_cavemining_craft', title = L('craft_section'), menu = 'urban_cavemining_jewel',
        options = recipeOptions('craft', Config.JewelCutting.craft, have, 'crafting', ANIM_BENCH, benchDust(coords)) })
    lib.registerContext({
        id = 'urban_cavemining_jewel',
        title = L('cut_title'),
        options = {
            { title = L('cut_section'),   icon = 'gem',  menu = 'urban_cavemining_cut' },
            { title = L('craft_section'), icon = 'ring', menu = 'urban_cavemining_craft' },
        },
    })
    lib.showContext('urban_cavemining_jewel')
end

function Stations.openCracking(coords)
    local have = counts({ Config.Cracking.input, 'drillbit' })
    local stones = math.min(20, have[Config.Cracking.input] or 0)
    local noBit = Config.Cracking.needsDrillbit and (have.drillbit or 0) < 1
    local disabled = stones < 1 or noBit

    local function crack(amount)
        runTimed('urban_cavemining:beginLoot', 'urban_cavemining:finishLoot', { 'crack', amount },
            L('cracking'), ANIM_BENCH, benchDust(coords))
    end

    lib.registerContext({
        id = 'urban_cavemining_crack',
        title = L('crack_title'),
        options = {
            {
                title = ('%s x1'):format(Utils.itemLabel(Config.Cracking.input)),
                description = noBit and L('need_drillbit') or L('you_have', have[Config.Cracking.input] or 0),
                icon = 'hammer', disabled = disabled,
                onSelect = function() crack(1) end,
            },
            {
                title = ('%s x%d'):format(Utils.itemLabel(Config.Cracking.input), stones),
                icon = 'layer-group', disabled = disabled or stones < 2,
                onSelect = function() crack(stones) end,
            },
            {
                title = L('amount'),
                icon = 'hashtag', disabled = disabled or stones < 2,
                onSelect = function()
                    local amount = askAmount(stones, 1)
                    if amount then crack(amount) end
                end,
            },
        },
    })
    lib.showContext('urban_cavemining_crack')
end

--──────────────────────────────── world setup ────────────────────────────

local function spawnPed(data)
    local hash = Client.loadModel(data.model)
    if not hash then return nil end
    local c = data.coords
    local ped = CreatePed(4, hash, c.x, c.y, c.z - GROUND, c.w, false, true)
    SetEntityInvincible(ped, true)
    FreezeEntityPosition(ped, true)
    SetBlockingOfNonTemporaryEvents(ped, true)
    if data.scenario then TaskStartScenarioInPlace(ped, data.scenario, 0, true) end
    SetModelAsNoLongerNeeded(hash)
    return ped
end

local function spawnBench(data)
    local hash = Client.loadModel(data.prop)
    if not hash then return nil end
    local c = data.coords
    local obj = CreateObjectNoOffset(hash, c.x, c.y, c.z - GROUND, false, false, false)
    SetEntityHeading(obj, c.w)
    FreezeEntityPosition(obj, true)
    SetModelAsNoLongerNeeded(hash)
    return obj
end

local function createWorld()
    -- shop ped
    local shopPed = spawnPed(Locations.Shop)
    if shopPed then
        spawned.peds.shop = shopPed
        Bridge.addEntity('urban_cavemining_shop', shopPed, {
            { label = L('target_shop'), icon = 'fas fa-store', onSelect = Stations.openShop },
            { label = L('target_level'), icon = 'fas fa-star', onSelect = function()
                Client.xp = lib.callback.await('urban_cavemining:getXp', false) or Client.xp
                Bridge.notify(Client.levelText(), 'inform')
            end },
        })
    end

    -- buyer ped
    local buyerPed = spawnPed(Locations.Buyer)
    if buyerPed then
        spawned.peds.buyer = buyerPed
        Bridge.addEntity('urban_cavemining_buyer', buyerPed, {
            { label = L('target_buyer'), icon = 'fas fa-sack-dollar', onSelect = Stations.openBuyer },
        })
    end

    -- smelters
    for i, smelter in ipairs(Locations.Smelters) do
        Bridge.addZone('urban_cavemining_smelter_' .. i, smelter.coords, 1.5, {
            { label = L('target_smelt'), icon = 'fas fa-fire',
              canInteract = function() return not Client.busy end,
              onSelect = function() Stations.openSmelter(smelter.coords) end },
        })
    end

    -- stone cracking benches
    for i, bench in ipairs(Locations.Cracking) do
        spawned.props[#spawned.props + 1] = spawnBench(bench)
        Bridge.addZone('urban_cavemining_crack_' .. i, bench.coords.xyz, 1.0, {
            { label = L('target_crack'), icon = 'fas fa-hammer',
              canInteract = function() return not Client.busy end,
              onSelect = function() Stations.openCracking(bench.coords) end },
        })
    end

    -- jewel benches
    for i, bench in ipairs(Locations.JewelCutting) do
        spawned.props[#spawned.props + 1] = spawnBench(bench)
        Bridge.addZone('urban_cavemining_jewel_' .. i, bench.coords.xyz, 1.0, {
            { label = L('target_cut'), icon = 'fas fa-gem',
              canInteract = function() return not Client.busy end,
              onSelect = function() Stations.openJewelBench(bench.coords) end },
        })
    end
end

local function destroyWorld()
    for name, ped in pairs(spawned.peds) do
        Bridge.removeEntity('urban_cavemining_' .. name, ped)
        if DoesEntityExist(ped) then DeleteEntity(ped) end
    end
    for _, obj in pairs(spawned.props) do
        if obj and DoesEntityExist(obj) then DeleteEntity(obj) end
    end
    for i = 1, #Locations.Smelters do Bridge.removeZone('urban_cavemining_smelter_' .. i) end
    for i = 1, #Locations.Cracking do Bridge.removeZone('urban_cavemining_crack_' .. i) end
    for i = 1, #Locations.JewelCutting do Bridge.removeZone('urban_cavemining_jewel_' .. i) end
    spawned = { peds = {}, props = {} }
end

-- only build the workshop while someone is near it
local workshop = lib.points.new({
    coords = Locations.Shop.coords.xyz,
    distance = 90.0,
})

function workshop:onEnter() createWorld() end
function workshop:onExit() destroyWorld() end

-- smelter ambience: a warm glow in the foundry while you are close
CreateThread(function()
    while true do
        local sleep = 1500
        local pos = GetEntityCoords(cache.ped)
        for _, smelter in ipairs(Locations.Smelters) do
            if smelter.glow and #(pos - smelter.coords) < 25.0 then
                sleep = 0
                local c = smelter.coords
                DrawLightWithRange(c.x, c.y, c.z, 255, 90, 10, 4.0, 3.0)
            end
        end
        Wait(sleep)
    end
end)

AddEventHandler('onResourceStop', function(name)
    if name == GetCurrentResourceName() then destroyWorld() end
end)
