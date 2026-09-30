Mining = {}

local function hitEffect(coords, heading)
    lib.requestNamedPtfxAsset('core')
    UseParticleFxAssetNextCall('core')
    StartParticleFxNonLoopedAtCoord('ent_dst_rocks', coords.x, coords.y, coords.z, 0.0, 0.0, heading or 0.0, 0.8, false, false, false)
end

local function loadBanks(sound)
    if not sound or not sound.banks then return end
    for i = 1, #sound.banks do RequestAmbientAudioBank(sound.banks[i], false) end
end

local function releaseBanks(sound)
    if not sound or not sound.banks then return end
    for i = 1, #sound.banks do ReleaseNamedScriptAudioBank(sound.banks[i]) end
end

--- red beam from the laser to the ore while mining with the mining laser
local function laserThread(state, target)
    CreateThread(function()
        local tick = 0
        while state.active do
            local hand = GetPedBoneCoords(cache.ped, 57005, 0.25, 0.0, 0.0)
            DrawLine(hand.x, hand.y, hand.z, target.x, target.y, target.z, 255, 20, 20, 255)
            DrawLightWithRange(target.x, target.y, target.z, 255, 30, 30, 2.5, 6.0)
            tick = tick + 1
            if tick % 20 == 0 then
                lib.requestNamedPtfxAsset('core')
                UseParticleFxAssetNextCall('core')
                StartParticleFxNonLoopedAtCoord('muz_railgun', target.x, target.y, target.z, 0.0, 0.0, 0.0, 0.4, false, false, false)
            end
            Wait(0)
        end
    end)
end

--- dust every ~0.7s while the progress bar is running
local function dustThread(state, target, heading)
    CreateThread(function()
        while state.active do
            hitEffect(target, heading)
            Wait(700)
        end
    end)
end

function Mining.start(id)
    if Client.busy then return Bridge.notify(L('busy'), 'error') end
    local slot = Client.ores[id]
    if not slot or slot.depleted then return Bridge.notify(L('depleted'), 'error') end

    local info, err = lib.callback.await('urban_cavemining:startMining', false, id)
    if not info then
        if err then Bridge.notify(err, 'error') end
        return
    end

    Client.busy = true
    local ped = cache.ped
    local tool = Config.Tools[info.tool]
    local target = vec3(slot.coords.x, slot.coords.y, slot.coords.z + 0.3)
    local oreLabel = L('ore_' .. info.ore)

    TaskTurnPedToFaceCoord(ped, target.x, target.y, target.z, 700)
    Wait(700)
    local heading = GetEntityHeading(ped) - 180.0

    local soundId
    if tool.sound then
        loadBanks(tool.sound)
        soundId = GetSoundId()
        PlaySoundFromEntity(soundId, tool.sound.name, ped, tool.sound.set, true, 0)
    end

    local hp, maxHp = info.hp, info.maxHp
    while true do
        local state = { active = true }
        if tool.laser then laserThread(state, target) end
        dustThread(state, target, heading)

        local percent = math.floor((1.0 - hp / maxHp) * 100)
        local finished = lib.progressBar({
            duration = info.swing,
            label = L('mining_progress', oreLabel, percent),
            useWhileDead = false,
            canCancel = true,
            disable = { move = true, car = true, combat = true, sprint = true },
            anim = tool.anim,
            prop = tool.prop,
        })
        state.active = false

        if not finished then
            TriggerServerEvent('urban_cavemining:server:stopMining')
            Bridge.notify(L('mining_stopped'), 'inform')
            break
        end

        local result = lib.callback.await('urban_cavemining:hit', false, id)
        if not result then break end
        hitEffect(target, heading)
        if result.done or result.stop then break end
        hp = result.hp or hp
    end

    if soundId then
        StopSound(soundId)
        ReleaseSoundId(soundId)
        releaseBanks(tool.sound)
    end
    ClearPedTasks(ped)
    Client.busy = false
end
