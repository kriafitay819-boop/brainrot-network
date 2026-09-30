-- Sand / dirt kicked up by every footstep inside the mine.
-- Works with any cave map; the MLO's own collision material (SAND_LOOSE) adds footprints on top.

local cfg = Config.FootDust
if not cfg or not cfg.enabled then return end

local FOOT_BONES = { 14201, 52301 }   -- SKEL_L_Foot, SKEL_R_Foot

local function stepInterval(ped)
    if IsPedSprinting(ped) then return 230, 1.6 end
    if IsPedRunning(ped) then return 290, 1.3 end
    if IsPedWalking(ped) then return 420, 1.0 end
    return nil
end

CreateThread(function()
    local foot = 1
    while true do
        local sleep = 800
        local ped = cache.ped
        local active = Client.inCave
            and not cache.vehicle
            and not IsPedSwimming(ped)
            and not IsEntityInWater(ped)
            and (not cfg.requireInterior or GetInteriorFromEntity(ped) ~= 0)

        if active then
            local interval, mult = stepInterval(ped)
            if interval then
                local pos = GetPedBoneCoords(ped, FOOT_BONES[foot], 0.0, 0.0, 0.0)
                foot = foot == 1 and 2 or 1
                lib.requestNamedPtfxAsset(cfg.asset)
                UseParticleFxAssetNextCall(cfg.asset)
                local effect = cfg.effects[math.random(#cfg.effects)]
                StartParticleFxNonLoopedAtCoord(effect, pos.x, pos.y, pos.z - 0.05, 0.0, 0.0, math.random(0, 359) + 0.0,
                    cfg.scale * mult, false, false, false)
                sleep = interval
            else
                sleep = 150
            end
        end
        Wait(sleep)
    end
end)
