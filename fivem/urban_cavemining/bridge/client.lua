-- Target bridge (client): ox_target, qb-target, or ox_lib [E] prompts when no target resource exists.
-- Every interaction in the resource is an "option list":
--   { label = 'text', icon = 'fas fa-x', onSelect = function() end, canInteract = function() return true end }

Bridge = {}

local function running(name)
    local state = GetResourceState(name)
    return state == 'started' or state == 'starting'
end

local target = Config.Target
if target == 'auto' then
    if running('ox_target') then target = 'ox'
    elseif running('qb-target') then target = 'qb'
    else target = 'none' end
end
Bridge.target = target

local zones = {}        -- name -> handle
local points = {}       -- name -> lib.points object (target = 'none')
local zoneCount = 0

local function toOx(options, distance)
    local out = {}
    for i = 1, #options do
        local opt = options[i]
        out[i] = {
            name = opt.name or ('urban_cavemining_' .. i),
            label = opt.label,
            icon = opt.icon,
            distance = distance,
            canInteract = opt.canInteract,
            onSelect = function() opt.onSelect() end,
        }
    end
    return out
end

local function toQb(options)
    local out = {}
    for i = 1, #options do
        local opt = options[i]
        out[i] = {
            label = opt.label,
            icon = opt.icon,
            canInteract = opt.canInteract,
            action = function() opt.onSelect() end,
        }
    end
    return out
end

-- [E] prompt fallback ------------------------------------------------------

local shownText

local function visibleOptions(options)
    local list = {}
    for i = 1, #options do
        local opt = options[i]
        if not opt.canInteract or opt.canInteract() then
            list[#list + 1] = opt
        end
    end
    return list
end

local function openOptionMenu(list)
    if #list == 1 then return list[1].onSelect() end
    local menuOptions = {}
    for i = 1, #list do
        menuOptions[i] = { title = list[i].label, icon = list[i].icon, onSelect = list[i].onSelect }
    end
    lib.registerContext({ id = 'urban_cavemining_prompt', title = L('blip_cave'), options = menuOptions })
    lib.showContext('urban_cavemining_prompt')
end

local function addPoint(name, coords, distance, options)
    local point = lib.points.new({ coords = coords, distance = distance })
    function point:nearby()
        if self.currentDistance > distance then return end
        local list = visibleOptions(options)
        if #list == 0 then
            if shownText == name then lib.hideTextUI() shownText = nil end
            return
        end
        local text = #list == 1 and ('[E] ' .. list[1].label) or ('[E] ' .. L('blip_cave'))
        if shownText ~= name then
            lib.showTextUI(text, { position = 'left-center', icon = list[1].icon })
            shownText = name
        end
        if IsControlJustReleased(0, 38) then
            lib.hideTextUI()
            shownText = nil
            openOptionMenu(list)
        end
    end
    function point:onExit()
        if shownText == name then lib.hideTextUI() shownText = nil end
    end
    points[name] = point
end

--──────────────────────────────── API ────────────────────────────────────

--- Sphere interaction at a position
function Bridge.addZone(name, coords, radius, options, distance)
    distance = distance or Config.InteractDistance
    Bridge.removeZone(name)
    if target == 'ox' then
        zones[name] = exports.ox_target:addSphereZone({
            coords = coords,
            radius = radius,
            debug = Config.Debug,
            options = toOx(options, distance),
        })
    elseif target == 'qb' then
        exports['qb-target']:AddCircleZone(name, coords, radius, {
            name = name, debugPoly = Config.Debug, useZ = true,
        }, { options = toQb(options), distance = distance })
        zones[name] = name
    else
        addPoint(name, coords, distance + radius, options)
    end
    zoneCount = zoneCount + 1
end

function Bridge.removeZone(name)
    if zones[name] then
        if target == 'ox' then
            exports.ox_target:removeZone(zones[name])
        elseif target == 'qb' then
            exports['qb-target']:RemoveZone(name)
        end
        zones[name] = nil
    end
    if points[name] then
        points[name]:remove()
        if shownText == name then lib.hideTextUI() shownText = nil end
        points[name] = nil
    end
end

--- Interaction on a spawned entity (peds)
function Bridge.addEntity(name, entity, options, distance)
    distance = distance or 2.5
    if target == 'ox' then
        exports.ox_target:addLocalEntity(entity, toOx(options, distance))
    elseif target == 'qb' then
        exports['qb-target']:AddTargetEntity(entity, { options = toQb(options), distance = distance })
    else
        addPoint(name, GetEntityCoords(entity), distance, options)
    end
end

function Bridge.removeEntity(name, entity)
    if target == 'ox' then
        if DoesEntityExist(entity) then exports.ox_target:removeLocalEntity(entity) end
    elseif target == 'qb' then
        if DoesEntityExist(entity) then exports['qb-target']:RemoveTargetEntity(entity) end
    end
    if points[name] then
        points[name]:remove()
        points[name] = nil
    end
end

function Bridge.notify(message, kind)
    lib.notify({ title = L('blip_cave'), description = message, type = kind or 'inform', icon = 'gem' })
end
