Utils = {}

function L(key, ...)
    local lang = Locales[Config.Locale] or Locales.en
    local str = lang[key] or Locales.en[key] or key
    if select('#', ...) > 0 then
        return str:format(...)
    end
    return str
end

function Utils.itemLabel(name)
    local item = Items[name]
    if not item then return name end
    if Config.Locale == 'he' and item.he then return item.he end
    return item.label
end

function Utils.debug(...)
    if Config.Debug then
        print('^3[urban_cavemining]^7', ...)
    end
end

-- "2x Iron Ore, 1x Coal"
function Utils.needsText(needs)
    local parts = {}
    for item, amount in pairs(needs) do
        parts[#parts + 1] = ('%dx %s'):format(amount, Utils.itemLabel(item))
    end
    table.sort(parts)
    return table.concat(parts, ', ')
end

--- Level from total XP. Returns level, xpForThisLevel, xpForNextLevel (nil at max)
function Utils.levelFromXp(xp)
    local levels = Config.Levels.xp
    local level = 1
    for i = 1, #levels do
        if xp >= levels[i] then level = i end
    end
    return level, levels[level], levels[level + 1]
end

function Utils.swingTime(tool, level)
    local base = Config.Tools[tool].swingTime
    if not Config.Levels.enabled then return base end
    local bonus = math.min(0.5, (level - 1) * Config.Levels.speedPerLevel)
    return math.floor(base * (1.0 - bonus))
end

function Utils.oreVariants(oreType)
    local ore = Config.Ores[oreType]
    return ore and ore.props[Config.PropSet] or {}
end

-- deterministic tilt so every client sees the same rotation for a slot
function Utils.slotTilt(slotId)
    local p = Config.PropPlacement[Config.PropSet]
    local span = p.tiltMax - p.tiltMin
    return p.tiltMin + ((slotId * 37) % (span + 1))
end

function Utils.toolLabels(tools)
    local parts = {}
    for i = 1, #tools do parts[#parts + 1] = Utils.itemLabel(tools[i]) end
    return table.concat(parts, ' / ')
end
