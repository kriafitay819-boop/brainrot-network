-- Gold pan: stand in shallow water, use the pan, then wash stone or pan for gold.

local ANIM_WATER = { dict = 'amb@world_human_bum_wash@male@low@idle_a', clip = 'idle_a', flag = 1 }

local function inShallowWater()
    local ped = cache.ped
    if IsPedSwimming(ped) or IsPedInAnyVehicle(ped, false) then return false end
    if IsEntityInWater(ped) then return true end
    local pos = GetEntityCoords(ped)
    local found, height = GetWaterHeight(pos.x, pos.y, pos.z)
    return found and height >= pos.z - 1.2 and height <= pos.z + 0.3
end

local function splash(state)
    lib.requestNamedPtfxAsset('core')
    UseParticleFxAssetNextCall('core')
    local fx = StartParticleFxLoopedOnEntity('water_splash_veh_out', cache.ped, 0.0, 0.8, -0.3, 0.0, 0.0, 0.0, 1.5, false, false, false)
    while state.active do Wait(100) end
    StopParticleFxLooped(fx, false)
end

local function openPan()
    if Client.busy then return Bridge.notify(L('busy'), 'error') end
    if not inShallowWater() then return Bridge.notify(L('not_in_water'), 'error') end

    local have = lib.callback.await('urban_cavemining:getCounts', false, { Config.Washing.input }) or {}
    local stones = math.min(20, have[Config.Washing.input] or 0)

    lib.registerContext({
        id = 'urban_cavemining_pan',
        title = L('water_title'),
        options = {
            {
                title = L('pan_gold'),
                icon = 'water',
                onSelect = function()
                    Stations.runTimed('urban_cavemining:beginLoot', 'urban_cavemining:finishLoot', { 'pan', 1 },
                        L('panning'), ANIM_WATER, splash)
                end,
            },
            {
                title = L('wash_stone', stones),
                icon = 'gem',
                disabled = stones < 1,
                onSelect = function()
                    local amount = stones
                    if stones > 1 then
                        local input = lib.inputDialog(L('amount'), {
                            { type = 'slider', label = L('amount'), min = 1, max = stones, default = stones, step = 1 },
                        })
                        amount = input and tonumber(input[1])
                    end
                    if not amount then return end
                    Stations.runTimed('urban_cavemining:beginLoot', 'urban_cavemining:finishLoot', { 'wash', amount },
                        L('washing'), ANIM_WATER, splash)
                end,
            },
        },
    })
    lib.showContext('urban_cavemining_pan')
end

-- qb / esx usable item
RegisterNetEvent('urban_cavemining:client:useGoldpan', openPan)

-- ox_inventory: items.lua -> client = { export = 'urban_cavemining.useGoldpan' }
exports('useGoldpan', function()
    openPan()
end)
