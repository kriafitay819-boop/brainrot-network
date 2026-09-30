Config = {}

--──────────────────────────────────────────────────────────────────────────────
--  GENERAL
--──────────────────────────────────────────────────────────────────────────────
Config.Locale    = 'he'      -- 'he' | 'en'
Config.Debug     = false     -- draws zones + prints

Config.Framework = 'auto'    -- 'auto' | 'qbx' | 'qb' | 'esx' | 'standalone'
Config.Inventory = 'auto'    -- 'auto' | 'ox' | 'qb' | 'esx'   ('qb' also covers ps-/lj-inventory)
Config.Target    = 'auto'    -- 'auto' | 'ox' | 'qb' | 'none'  ('none' = [E] prompts from ox_lib)

Config.Job       = nil       -- e.g. 'miner' to restrict mining + stations to one job. nil = everyone
Config.PayWith   = 'cash'    -- 'cash' | 'bank' (shop purchases + buyer payouts)

-- Ore prop set:
--   'k4mb1'   -> the ore / crystal props shipped with the K4MB1 "Cave Mining" MLO (k4mb1-caveprops)
--   'vanilla' -> base-game rocks, works without any streamed props
Config.PropSet = 'k4mb1'

Config.StreamDistance   = 75.0   -- ore props are created client-side inside this range
Config.InteractDistance = 2.4    -- how close you must be to an ore to mine it
Config.ServerMaxDistance = 6.0   -- server-side sanity check (anti-exploit)

Config.Respawn = { min = 240, max = 480 }   -- seconds until a depleted ore regrows (re-rolled type)

--──────────────────────────────────────────────────────────────────────────────
--  MINING LEVELS  (stored per character with resource KVP - no SQL needed)
--──────────────────────────────────────────────────────────────────────────────
Config.Levels = {
    enabled = true,
    -- total XP required to reach level N (index = level)
    xp = { 0, 120, 300, 560, 920, 1400, 2050, 2900, 4000, 5500 },
    speedPerLevel      = 0.04,   -- each level above 1 = 4% faster swings
    doubleDropPerLevel = 0.03,   -- each level above 1 = +3% chance for double rewards
}

--──────────────────────────────────────────────────────────────────────────────
--  TOOLS
--──────────────────────────────────────────────────────────────────────────────
-- power      = damage per swing (ore hp is below)
-- swingTime  = ms per swing (before level bonus)
-- breakChance= % chance per swing to lose the tool
-- consumes   = item used up by chance each swing
Config.Tools = {
    pickaxe = {
        power = 1, swingTime = 1700, breakChance = 2,
        anim = { dict = 'melee@large_wpn@streamed_core', clip = 'ground_attack_on_spot', flag = 1 },
        prop = { model = 'prop_tool_pickaxe', bone = 57005, pos = vec3(0.09, 0.03, -0.02), rot = vec3(-78.0, 13.0, 28.0) },
        sound = nil,
    },
    miningdrill = {
        power = 2, swingTime = 2400, breakChance = 0,
        consumes = { item = 'drillbit', chance = 10 },
        anim = { dict = 'anim@heists@fleeca_bank@drilling', clip = 'drill_straight_idle', flag = 1 },
        prop = { model = 'hei_prop_heist_drill', bone = 57005, pos = vec3(0.14, 0.0, -0.01), rot = vec3(90.0, -90.0, 180.0) },
        sound = { name = 'Drill', set = 'DLC_HEIST_FLEECA_SOUNDSET', banks = { 'DLC_HEIST_FLEECA_SOUNDSET', 'DLC_MPHEIST\\HEIST_FLEECA_DRILL', 'DLC_MPHEIST\\HEIST_FLEECA_DRILL_2' } },
    },
    mininglaser = {
        power = 4, swingTime = 2900, breakChance = 0,
        anim = { dict = 'anim@heists@fleeca_bank@drilling', clip = 'drill_straight_idle', flag = 1 },
        prop = { model = 'ch_prop_laserdrill_01a', bone = 57005, pos = vec3(0.14, 0.0, -0.01), rot = vec3(90.0, -90.0, 180.0) },
        sound = { name = 'Pass', set = 'dlc_xm_silo_laser_hack_sounds', banks = { 'dlc_xm_silo_laser_hack_sounds' } },
        laser = true,    -- draws a red beam to the ore
    },
}
-- best tool first: when a player has several, the best allowed one is used
Config.ToolOrder = { 'mininglaser', 'miningdrill', 'pickaxe' }

--──────────────────────────────────────────────────────────────────────────────
--  ORES  (what can spawn on the 35 ore spots inside the cave)
--──────────────────────────────────────────────────────────────────────────────
-- weight   = spawn weight (higher = more common)
-- hp       = total tool power needed to break it
-- minLevel = mining level needed
-- tools    = tools that can mine it
-- rewards  = items given when it breaks
-- props    = { full = model while it has ore, empty = model after it was mined (nil = disappears) }
local ALL_TOOLS  = { 'pickaxe', 'miningdrill', 'mininglaser' }
local POWER_TOOLS = { 'miningdrill', 'mininglaser' }

Config.Ores = {
    coal = {
        weight = 30, hp = 3, xp = 3, minLevel = 1, tools = ALL_TOOLS,
        rewards = { { item = 'coal', min = 2, max = 4 } },
        props = {
            k4mb1   = { { full = 'k4mb1_coal2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    copper = {
        weight = 26, hp = 4, xp = 4, minLevel = 1, tools = ALL_TOOLS,
        rewards = { { item = 'copperore', min = 1, max = 3 } },
        props = {
            k4mb1   = { { full = 'k4mb1_copperore', empty = 'k4mb1_emptyore' }, { full = 'k4mb1_copperore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    iron = {
        weight = 24, hp = 4, xp = 4, minLevel = 1, tools = ALL_TOOLS,
        rewards = { { item = 'ironore', min = 1, max = 3 } },
        props = {
            k4mb1   = { { full = 'k4mb1_ironore', empty = 'k4mb1_emptyore' }, { full = 'k4mb1_ironore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    tin = {
        weight = 18, hp = 4, xp = 5, minLevel = 2, tools = ALL_TOOLS,
        rewards = { { item = 'tinore', min = 1, max = 3 } },
        props = {
            k4mb1   = { { full = 'k4mb1_tinore', empty = 'k4mb1_emptyore' }, { full = 'k4mb1_tinore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    lead = {
        weight = 15, hp = 5, xp = 5, minLevel = 2, tools = ALL_TOOLS,
        rewards = { { item = 'leadore', min = 1, max = 3 } },
        props = {
            k4mb1   = { { full = 'k4mb1_leadore', empty = 'k4mb1_emptyore' }, { full = 'k4mb1_leadore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    bauxite = {
        weight = 12, hp = 5, xp = 6, minLevel = 3, tools = ALL_TOOLS,
        rewards = { { item = 'bauxite', min = 1, max = 3 } },
        props = {
            k4mb1   = { { full = 'k4mb1_bauxiteore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    gold = {
        weight = 7, hp = 6, xp = 10, minLevel = 4, tools = ALL_TOOLS,
        rewards = { { item = 'goldore', min = 1, max = 2 } },
        props = {
            k4mb1   = { { full = 'k4mb1_goldore', empty = 'k4mb1_emptyore' }, { full = 'k4mb1_goldore2', empty = 'k4mb1_emptyore2' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
    },
    ruby = {
        weight = 3, hp = 8, xp = 18, minLevel = 5, tools = POWER_TOOLS,
        rewards = { { item = 'uncut_ruby', min = 1, max = 2 } },
        props = {
            k4mb1   = { { full = 'k4mb1_crystalred', empty = 'k4mb1_crystalempty' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
        light = { r = 255, g = 40, b = 40 },
    },
    emerald = {
        weight = 3, hp = 8, xp = 18, minLevel = 5, tools = POWER_TOOLS,
        rewards = { { item = 'uncut_emerald', min = 1, max = 2 } },
        props = {
            k4mb1   = { { full = 'k4mb1_crystalgreen', empty = 'k4mb1_crystalempty' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
        light = { r = 40, g = 255, b = 90 },
    },
    sapphire = {
        weight = 3, hp = 8, xp = 18, minLevel = 5, tools = POWER_TOOLS,
        rewards = { { item = 'uncut_sapphire', min = 1, max = 2 } },
        props = {
            k4mb1   = { { full = 'k4mb1_crystalblue', empty = 'k4mb1_crystalempty' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
        light = { r = 50, g = 110, b = 255 },
    },
    diamond = {
        weight = 1, hp = 12, xp = 35, minLevel = 7, tools = { 'mininglaser' },
        rewards = { { item = 'uncut_diamond', min = 1, max = 1 } },
        props = {
            k4mb1   = { { full = 'k4mb1_diamond' } },
            vanilla = { { full = 'cs_x_rubweec', empty = 'prop_rock_5_a' } },
        },
        light = { r = 220, g = 240, b = 255 },
    },
}

-- every broken ore can also drop raw stone (for the cracking bench / washing)
Config.StoneBonus = { item = 'stone', chance = 60, min = 1, max = 2 }

-- how the props sit in the rock face. K4MB1 ore props are wall pieces, so they
-- are tilted into the wall like in the MLO preview.
Config.PropPlacement = {
    k4mb1   = { z = -0.23, tiltMin = 60, tiltMax = 100 },
    vanilla = { z = 0.07,  tiltMin = 60, tiltMax = 100 },
}

--──────────────────────────────────────────────────────────────────────────────
--  STATIONS
--──────────────────────────────────────────────────────────────────────────────
Config.Smelting = {
    time = 5000,           -- ms per item
    maxBatch = 20,
    recipes = {
        { result = 'copper',    amount = 1, needs = { copperore = 2, coal = 1 } },
        { result = 'iron',      amount = 1, needs = { ironore = 2, coal = 1 } },
        { result = 'tin',       amount = 1, needs = { tinore = 2, coal = 1 } },
        { result = 'lead',      amount = 1, needs = { leadore = 2, coal = 1 } },
        { result = 'aluminum',  amount = 1, needs = { bauxite = 3, coal = 1 } },
        { result = 'steel',     amount = 1, needs = { iron = 2, coal = 2 } },
        { result = 'bronze',    amount = 2, needs = { copper = 3, tin = 1 } },
        { result = 'goldingot', amount = 1, needs = { goldore = 3, coal = 1 } },
        { result = 'goldingot', amount = 1, needs = { goldnugget = 5 } },
    },
}

Config.Cracking = {
    time = 4500,
    input = 'stone',
    needsDrillbit = true,       -- a drill bit is needed (and may break)
    drillbitBreakChance = 15,
    rolls = 1,                  -- how many loot rolls per stone
    loot = {                    -- chance in %, checked top to bottom, first hit wins
        { item = 'uncut_diamond',  chance = 1,  min = 1, max = 1 },
        { item = 'uncut_ruby',     chance = 3,  min = 1, max = 1 },
        { item = 'uncut_emerald',  chance = 3,  min = 1, max = 1 },
        { item = 'uncut_sapphire', chance = 3,  min = 1, max = 1 },
        { item = 'goldore',        chance = 8,  min = 1, max = 1 },
        { item = 'copperore',      chance = 22, min = 1, max = 2 },
        { item = 'ironore',        chance = 22, min = 1, max = 2 },
        { item = 'coal',           chance = 25, min = 1, max = 2 },
    },
}

Config.Washing = {           -- stone washing: use the gold pan while standing in water
    time = 6000,
    input = 'stone',
    loot = {
        { item = 'uncut_diamond',  chance = 2,  min = 1, max = 1 },
        { item = 'uncut_ruby',     chance = 5,  min = 1, max = 1 },
        { item = 'uncut_emerald',  chance = 5,  min = 1, max = 1 },
        { item = 'uncut_sapphire', chance = 5,  min = 1, max = 1 },
        { item = 'goldnugget',     chance = 12, min = 1, max = 2 },
    },
}

Config.Panning = {           -- gold panning: use the gold pan while standing in water
    time = 8000,
    loot = {
        { item = 'goldnugget', chance = 30, min = 1, max = 3 },
        { item = 'stone',      chance = 20, min = 1, max = 1 },
    },
}

Config.JewelCutting = {
    time = 7000,
    needsDrillbit = true,
    drillbitBreakChance = 10,
    failChance = 8,         -- % chance to shatter the gem while cutting
    cut = {
        { result = 'ruby',     needs = { uncut_ruby = 1 } },
        { result = 'emerald',  needs = { uncut_emerald = 1 } },
        { result = 'sapphire', needs = { uncut_sapphire = 1 } },
        { result = 'diamond',  needs = { uncut_diamond = 1 } },
    },
    craft = {
        { result = 'gold_ring',  needs = { goldingot = 1 } },
        { result = 'goldchain',  needs = { goldingot = 2 } },
        -- gem jewellery is generated below for every gem
    },
}
for _, gem in ipairs({ 'ruby', 'emerald', 'sapphire', 'diamond' }) do
    local craft = Config.JewelCutting.craft
    craft[#craft + 1] = { result = gem .. '_ring',     needs = { [gem] = 1, goldingot = 1 } }
    craft[#craft + 1] = { result = gem .. '_necklace', needs = { [gem] = 1, goldchain = 1 } }
    craft[#craft + 1] = { result = gem .. '_earring',  needs = { [gem] = 2, goldingot = 1 } }
end

--──────────────────────────────────────────────────────────────────────────────
--  SHOP + BUYER
--──────────────────────────────────────────────────────────────────────────────
Config.Shop = {
    { item = 'pickaxe',       price = 150 },
    { item = 'mining_helmet', price = 250 },
    { item = 'goldpan',       price = 90 },
    { item = 'drillbit',      price = 60 },
    { item = 'miningdrill',   price = 1400, minLevel = 3 },
    { item = 'mininglaser',   price = 8500, minLevel = 6 },
}

Config.Buyer = {
    -- price per unit
    prices = {
        stone = 4, coal = 10,
        copperore = 16, ironore = 18, tinore = 20, leadore = 20, bauxite = 24, goldore = 60, goldnugget = 45,
        copper = 45, iron = 50, tin = 55, lead = 55, aluminum = 80, steel = 140, bronze = 95, goldingot = 260,
        uncut_ruby = 180, uncut_emerald = 180, uncut_sapphire = 180, uncut_diamond = 420,
        ruby = 420, emerald = 420, sapphire = 420, diamond = 950,
        gold_ring = 380, goldchain = 650,
        ruby_ring = 900, emerald_ring = 900, sapphire_ring = 900, diamond_ring = 1700,
        ruby_necklace = 1250, emerald_necklace = 1250, sapphire_necklace = 1250, diamond_necklace = 2200,
        ruby_earring = 1150, emerald_earring = 1150, sapphire_earring = 1150, diamond_earring = 2400,
    },
    -- order of the categories in the sell menu
    categories = {
        { key = 'raw',     items = { 'stone', 'coal', 'copperore', 'ironore', 'tinore', 'leadore', 'bauxite', 'goldore', 'goldnugget' } },
        { key = 'metal',   items = { 'copper', 'iron', 'tin', 'lead', 'aluminum', 'steel', 'bronze', 'goldingot' } },
        { key = 'gems',    items = { 'uncut_ruby', 'uncut_emerald', 'uncut_sapphire', 'uncut_diamond', 'ruby', 'emerald', 'sapphire', 'diamond' } },
        { key = 'jewelry', items = { 'gold_ring', 'goldchain', 'ruby_ring', 'emerald_ring', 'sapphire_ring', 'diamond_ring',
                                     'ruby_necklace', 'emerald_necklace', 'sapphire_necklace', 'diamond_necklace',
                                     'ruby_earring', 'emerald_earring', 'sapphire_earring', 'diamond_earring' } },
    },
}

--──────────────────────────────────────────────────────────────────────────────
--  HEADLAMP  (mining helmet item)
--──────────────────────────────────────────────────────────────────────────────
Config.Headlamp = {
    item = 'mining_helmet',
    prop = { model = 'prop_hard_hat_01', bone = 31086, pos = vec3(0.12, 0.0, 0.0), rot = vec3(0.0, 90.0, 180.0) },
    color = { r = 255, g = 236, b = 200 },
    distance = 30.0, brightness = 9.0, roundness = 4.0, radius = 22.0, falloff = 30.0,
    onlyInCave = false,
}

--──────────────────────────────────────────────────────────────────────────────
--  FOOT DUST  (sand / dirt kicked up by every footstep inside the mine)
--──────────────────────────────────────────────────────────────────────────────
Config.FootDust = {
    enabled = true,
    asset = 'core',
    effects = { 'bang_sand', 'bang_dirt' },   -- one is picked per step
    scale = 0.38,                             -- walking; running / sprinting scale up
    requireInterior = false,                  -- true = only inside an MLO interior (e.g. the K4MB1 cave)
}

--──────────────────────────────────────────────────────────────────────────────
--  ADMIN
--──────────────────────────────────────────────────────────────────────────────
Config.Admin = {
    group = 'group.admin',       -- ace group allowed to use the commands below
    editorCommand = 'caveeditor', -- place / remove ore spots in-game (saved to data/positions.json)
    resetCommand  = 'cavereset',  -- respawn every ore now
    xpCommand     = 'cavexp',     -- /cavexp [id] [amount]
    coordsCommand = 'cavecoords', -- prints + copies your position (use it to set the entrance / spots)
}
