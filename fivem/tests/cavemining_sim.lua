-- Offline simulation of urban_cavemining's server logic.
-- Stubs the FiveM / ox_lib / qbx_core / ox_inventory APIs, loads the real
-- shared + server files in manifest order and plays through every system.
--
--   lua5.4 fivem/tests/cavemining_sim.lua
--
-- Exits non-zero on the first failed check.

local ROOT = (arg and arg[0] and arg[0]:match('^(.*)/tests/')) or 'fivem'
ROOT = ROOT .. '/urban_cavemining/'

--──────────────────────────────── vectors ────────────────────────────────
local vmeta = {}
local function mk(x, y, z, w)
    return setmetatable({ x = x, y = y, z = z, w = w }, vmeta)
end
vmeta.__index = function(v, key)
    if key == 'xyz' then return mk(v.x, v.y, v.z) end
end
vmeta.__sub = function(a, b) return mk(a.x - b.x, a.y - b.y, (a.z or 0) - (b.z or 0)) end
vmeta.__len = function(v) return math.sqrt(v.x * v.x + v.y * v.y + (v.z or 0) ^ 2) end
function vec3(x, y, z) return mk(x, y, z) end
function vec4(x, y, z, w) return mk(x, y, z, w) end
vector3, vector4 = vec3, vec4

--──────────────────────────────── clocks + threads ───────────────────────
local gameTimer, osClock = 0, 1000000
function GetGameTimer() return gameTimer end
local realTime = os.time
os.time = function(t) if t then return realTime(t) end return osClock end

local threads = {}
function CreateThread(fn)
    local co = coroutine.create(fn)
    threads[#threads + 1] = { co = co, wake = gameTimer }
end
Citizen = { CreateThread = CreateThread }
function Wait(ms) coroutine.yield(ms or 0) end
local function tick(ms)
    gameTimer = gameTimer + (ms or 0)
    for _, t in ipairs(threads) do
        if coroutine.status(t.co) ~= 'dead' and gameTimer >= t.wake then
            local ok, delay = coroutine.resume(t.co)
            if not ok then error(delay) end
            t.wake = gameTimer + (delay or 0)
        end
    end
end

--──────────────────────────────── natives / runtime ──────────────────────
local events, clientEvents, kvp = {}, {}, {}
function GetCurrentResourceName() return 'urban_cavemining' end
function GetResourceState(name)
    if name == 'qbx_core' or name == 'ox_inventory' or name == 'ox_lib' then return 'started' end
    return 'missing'
end
function RegisterNetEvent(name, fn) if fn then events[name] = fn end end
function AddEventHandler(name, fn) events[name] = fn end
function TriggerClientEvent(name, target, ...) clientEvents[#clientEvents + 1] = { name = name, target = target, args = { ... } } end
function GetResourceKvpInt(key) return kvp[key] or 0 end
function SetResourceKvpInt(key, value) kvp[key] = value end
function IsPlayerAceAllowed() return true end
function GetPlayerIdentifierByType(src) return 'license:' .. src end
local saved = {}
function LoadResourceFile(_, path) return saved[path] or '[]' end
function SaveResourceFile(_, path, data) saved[path] = data return true end
json = {
    encode = function() return '[]' end,
    decode = function(s) return {} end,
}

local positions = {}
function GetPlayerPed(src) return src end
function GetEntityCoords(ped) return positions[ped] end

--──────────────────────────────── ox_lib ─────────────────────────────────
local callbacks, commands = {}, {}
lib = {
    callback = { register = function(name, fn) callbacks[name] = fn end },
    addCommand = function(name, _, fn) commands[name] = fn end,
}

--──────────────────────────────── qbx_core + ox_inventory ────────────────
local inv, money, jobs = {}, {}, {}
local function bag(src) inv[src] = inv[src] or {} return inv[src] end
exports = {
    qbx_core = {
        GetPlayer = function(_, src)
            money[src] = money[src] or { cash = 0, bank = 0 }
            return { PlayerData = { citizenid = 'CID' .. src, job = { name = jobs[src] or 'police' }, money = money[src] } }
        end,
        GetJob = function(_, name) return (name == 'miner' or name == 'unemployed') and { label = name } or nil end,
        SetJob = function(_, src, name, grade) jobs[src] = name end,
        AddMoney = function(_, src, kind, amount) money[src][kind] = money[src][kind] + amount return true end,
        RemoveMoney = function(_, src, kind, amount)
            if money[src][kind] < amount then return false end
            money[src][kind] = money[src][kind] - amount
            return true
        end,
        CreateUseableItem = function() end,
    },
    ox_inventory = {
        GetItemCount = function(_, src, item) return bag(src)[item] or 0 end,
        CanCarryItem = function() return true end,
        AddItem = function(_, src, item, amount) bag(src)[item] = (bag(src)[item] or 0) + amount return true end,
        RemoveItem = function(_, src, item, amount)
            local b = bag(src)
            if (b[item] or 0) < amount then return false end
            b[item] = b[item] - amount
            return true
        end,
    },
}
setmetatable(exports, { __call = function() end })

--──────────────────────────────── load resource ──────────────────────────
local files = {
    'config.lua', 'shared/locations.lua', 'shared/items.lua', 'locales/en.lua', 'locales/he.lua', 'shared/utils.lua',
    'bridge/server.lua', 'server/main.lua', 'server/ores.lua', 'server/stations.lua', 'server/editor.lua',
}
local realPrint = print
print = function(...) end
for _, f in ipairs(files) do
    local chunk, err = loadfile(ROOT .. f)
    if not chunk then error(err) end
    chunk()
    if f == 'config.lua' then
        -- deterministic run: no random tool / gem breakage (stations copy these at load)
        Config.JewelCutting.failChance = 0
        Config.JewelCutting.drillbitBreakChance = 0
        Config.Cracking.drillbitBreakChance = 0
    end
end
print = realPrint
Config.Locale = 'en'

--──────────────────────────────── test helpers ───────────────────────────
local passed = 0
local function check(cond, message)
    if not cond then
        realPrint('FAIL: ' .. message)
        os.exit(1)
    end
    passed = passed + 1
end
local function call(name, src, ...) return callbacks[name](src, ...) end
local function standAt(src, c) positions[src] = vec3(c.x, c.y, c.z) end

tick(0)   -- runs the loader threads

--──────────────────────────────── config integrity ───────────────────────
local function itemExists(name) return Items[name] ~= nil end
for name, ore in pairs(Config.Ores) do
    for _, r in ipairs(ore.rewards) do check(itemExists(r.item), 'ore reward item ' .. r.item) end
    for _, tool in ipairs(ore.tools) do check(Config.Tools[tool] and itemExists(tool), 'ore tool ' .. tool) end
    check(#ore.props.k4mb1 > 0 and #ore.props.vanilla > 0, 'ore props for ' .. name)
    check(Locales.en['ore_' .. name] and Locales.he['ore_' .. name], 'ore label ' .. name)
end
for _, list in ipairs({ Config.Smelting.recipes, Config.JewelCutting.cut, Config.JewelCutting.craft }) do
    for _, r in ipairs(list) do
        check(itemExists(r.result), 'recipe result ' .. r.result)
        for item in pairs(r.needs) do check(itemExists(item), 'recipe input ' .. item) end
    end
end
for _, loot in ipairs({ Config.Cracking.loot, Config.Washing.loot, Config.Panning.loot }) do
    for _, e in ipairs(loot) do check(itemExists(e.item), 'loot item ' .. e.item) end
end
for item in pairs(Config.Buyer.prices) do check(itemExists(item), 'buyer item ' .. item) end
for _, cat in ipairs(Config.Buyer.categories) do
    for _, item in ipairs(cat.items) do check(Config.Buyer.prices[item], 'buyer price for ' .. item) end
end
for _, e in ipairs(Config.Shop) do check(itemExists(e.item), 'shop item ' .. e.item) end
local ordered = {}
for _, name in ipairs(ItemOrder) do ordered[name] = true end
for name in pairs(Items) do check(ordered[name], 'ItemOrder has ' .. name) end
for key in pairs(Locales.en) do check(Locales.he[key], 'hebrew locale key ' .. key) end
for key in pairs(Locales.he) do check(Locales.en[key], 'english locale key ' .. key) end

-- every L('key') used in the code exists
for _, f in ipairs({ 'client/main.lua', 'client/mining.lua', 'client/stations.lua', 'client/water.lua', 'client/headlamp.lua',
                     'client/editor.lua', 'bridge/client.lua', 'bridge/server.lua', 'server/main.lua', 'server/ores.lua',
                     'server/stations.lua', 'server/editor.lua' }) do
    local src = io.open(ROOT .. f):read('a')
    for key in src:gmatch("L%('([%w_]+)'%s*[,)]") do check(Locales.en[key], ('locale key %s used in %s'):format(key, f)) end
end

--──────────────────────────────── ores ───────────────────────────────────
local snapshot = call('urban_cavemining:getOres', 1)
check(#snapshot == #Locations.OrePositions, 'all ore spots spawned')
for _, s in ipairs(snapshot) do check(Config.Ores[s.ore] and s.hp == s.maxHp and not s.depleted, 'spot ' .. s.id .. ' valid') end

-- levels
check(Utils.levelFromXp(0) == 1, 'level 1 at 0 xp')
check(Utils.levelFromXp(300) == 3, 'level 3 at 300 xp')
check(Utils.levelFromXp(999999) == #Config.Levels.xp, 'max level')

-- find a coal/copper/iron spot a level-1 pickaxe can mine
local function findSpot(pred)
    for _, s in ipairs(call('urban_cavemining:getOres', 1)) do if pred(s) then return s end end
end
Ores.respawnAll()
local spot = findSpot(function(s) return s.ore == 'coal' or s.ore == 'copper' or s.ore == 'iron' end)
for _ = 1, 50 do
    if spot then break end
    Ores.respawnAll()
    spot = findSpot(function(s) return s.ore == 'coal' or s.ore == 'copper' or s.ore == 'iron' end)
end
check(spot, 'found a basic ore spot')

local P = 1
standAt(P, spot.coords)
local ok, err = call('urban_cavemining:startMining', P, spot.id)
check(ok == false and err:find('Pickaxe'), 'no tool -> error mentions pickaxe')

bag(P).pickaxe = 1
Config.Tools.pickaxe.breakChance = 0
local info = call('urban_cavemining:startMining', P, spot.id)
check(type(info) == 'table' and info.tool == 'pickaxe', 'mining starts with pickaxe')
check(call('urban_cavemining:hit', P, spot.id) == false, 'instant hit is rejected (anti speed-hack)')

local done = false
for _ = 1, 20 do
    tick(info.swing)
    local r = call('urban_cavemining:hit', P, spot.id)
    check(r, 'hit accepted after a full swing')
    if r.done then done = true break end
end
check(done, 'ore breaks')
local reward = Config.Ores[spot.ore].rewards[1]
check((bag(P)[reward.item] or 0) >= reward.min, 'received ' .. reward.item)
check(kvp['xp:CID1'] == Config.Ores[spot.ore].xp, 'xp stored per character')
local after = call('urban_cavemining:getOres', P)[spot.id]
check(after.depleted, 'spot is depleted after mining')
local ok2, err2 = call('urban_cavemining:startMining', P, spot.id)
check(ok2 == false and err2 == L('depleted'), 'cannot mine a depleted spot')

-- respawn
osClock = osClock + Config.Respawn.max + 1
tick(5000)
check(not call('urban_cavemining:getOres', P)[spot.id].depleted, 'spot respawns')

-- distance check
positions[P] = vec3(0, 0, 0)
local ok3, err3 = call('urban_cavemining:startMining', P, spot.id)
check(ok3 == false and err3 == L('too_far'), 'too far is rejected')

-- level gate + tool gate on crystals
local crystal
for _ = 1, 200 do
    crystal = findSpot(function(s) return s.ore == 'ruby' or s.ore == 'emerald' or s.ore == 'sapphire' end)
    if crystal then break end
    Ores.respawnAll()
end
check(crystal, 'found a crystal spot')
standAt(P, crystal.coords)
local ok4, err4 = call('urban_cavemining:startMining', P, crystal.id)
check(ok4 == false and err4 == L('need_level', 5), 'crystal needs level 5')
kvp['xp:CID1'] = Config.Levels.xp[5]
local ok5, err5 = call('urban_cavemining:startMining', P, crystal.id)
check(ok5 == false and err5:find('Mining Drill'), 'crystal needs a power tool')
bag(P).miningdrill = 1
local ok6, err6 = call('urban_cavemining:startMining', P, crystal.id)
check(ok6 == false and err6:find('Mining Drill'), 'drill without bits is not usable')
bag(P).drillbit = 50
Config.Tools.miningdrill.consumes.chance = 0
local info2 = call('urban_cavemining:startMining', P, crystal.id)
check(info2 and info2.tool == 'miningdrill', 'drill is picked over pickaxe')
check(info2.swing < Config.Tools.miningdrill.swingTime, 'level bonus speeds up swings')
repeat
    tick(info2.swing)
    local r = call('urban_cavemining:hit', P, crystal.id)
    check(r, 'drill hit accepted')
until r.done
check((bag(P)['uncut_' .. crystal.ore] or 0) >= 1, 'received uncut gem')

--──────────────────────────────── smelter ────────────────────────────────
local S = 2
standAt(S, Locations.Smelters[1].coords)
bag(S).copperore, bag(S).coal = 4, 2
local dur = call('urban_cavemining:beginRecipe', S, 'smelt', 1, 2)
check(dur == Config.Smelting.time * 2, 'smelting duration')
check(call('urban_cavemining:finishRecipe', S) == false, 'finishing early is rejected')
check((bag(S).copperore or 0) == 4, 'early finish takes nothing')
dur = call('urban_cavemining:beginRecipe', S, 'smelt', 1, 2)
tick(dur)
check(call('urban_cavemining:finishRecipe', S) == true, 'smelting finishes')
check(bag(S).copper == 2 and bag(S).copperore == 0 and bag(S).coal == 0, 'smelted 2 copper')
local okT, errT = call('urban_cavemining:beginRecipe', S, 'smelt', 1, 1)
check(okT == false and errT == L('not_enough'), 'not enough ore')

--──────────────────────────────── jewel bench ────────────────────────────
standAt(S, Locations.JewelCutting[1].coords)
bag(S).uncut_ruby, bag(S).drillbit = 3, 5
dur = call('urban_cavemining:beginRecipe', S, 'cut', 1, 3)
tick(dur)
call('urban_cavemining:finishRecipe', S)
check(bag(S).ruby == 3, 'cut 3 rubies')
bag(S).goldingot = 1
local ringIndex
for i, r in ipairs(Config.JewelCutting.craft) do if r.result == 'ruby_ring' then ringIndex = i end end
dur = call('urban_cavemining:beginRecipe', S, 'craft', ringIndex, 1)
tick(dur)
call('urban_cavemining:finishRecipe', S)
check(bag(S).ruby_ring == 1 and bag(S).ruby == 2 and bag(S).goldingot == 0, 'crafted a ruby ring')

--──────────────────────────────── cracking ───────────────────────────────
standAt(S, Locations.Cracking[1].coords)
bag(S).stone = 10
local okC, errC = call('urban_cavemining:beginLoot', S, 'crack', 11)
check(okC == false and errC == L('not_enough'), 'cannot crack more stone than you have')
dur = call('urban_cavemining:beginLoot', S, 'crack', 10)
tick(dur)
check(call('urban_cavemining:finishLoot', S) == true, 'cracking finishes')
check(bag(S).stone == 0, 'all stone used')

-- washing needs the pan, panning is a single action
bag(S).stone = 3
local okW, errW = call('urban_cavemining:beginLoot', S, 'wash', 3)
check(okW == false and errW:find('Gold Pan'), 'washing needs a gold pan')
bag(S).goldpan = 1
dur = call('urban_cavemining:beginLoot', S, 'wash', 3)
tick(dur)
call('urban_cavemining:finishLoot', S)
check(bag(S).stone == 0, 'washed 3 stone')
dur = call('urban_cavemining:beginLoot', S, 'pan', 5)
check(dur == Config.Panning.time, 'panning is always one pan')

--──────────────────────────────── shop + buyer ───────────────────────────
standAt(S, Locations.Shop.coords)
exports.qbx_core:GetPlayer(S)
money[S].cash = 100
local okB, errB = call('urban_cavemining:buy', S, 1, 1)
check(okB == false and errB == L('not_enough_money'), 'shop checks money')
money[S].cash = 1000
local laserIndex
for i, e in ipairs(Config.Shop) do if e.item == 'mininglaser' then laserIndex = i end end
local okL, errL = call('urban_cavemining:buy', S, laserIndex, 1)
check(okL == false and errL == L('locked_level', 6), 'laser is level locked')
local okP = call('urban_cavemining:buy', S, 1, 2)
check(okP == true and bag(S).pickaxe == 2 and money[S].cash == 1000 - Config.Shop[1].price * 2, 'bought 2 pickaxes')

local okFar = call('urban_cavemining:sell', S, 'ruby_ring', 1)
check(okFar == false, 'buyer checks distance')
standAt(S, Locations.Buyer.coords)
local cash = money[S].cash
local okS = call('urban_cavemining:sell', S, 'ruby_ring', 5)
check(okS == true and bag(S).ruby_ring == 0 and money[S].cash == cash + Config.Buyer.prices.ruby_ring, 'sold ring (amount clamped)')

--──────────────────────────────── job center ─────────────────────────────
local J = 3
standAt(J, vec3(0, 0, 0))
local okF = call('urban_cavemining:takeJob', J)
check(okF == false, 'job center checks distance')
standAt(J, Locations.Foreman.coords)
check(Bridge.getJob(J) == 'police', 'player starts as police')
local okJ, msgJ = call('urban_cavemining:takeJob', J)
check(okJ == true and msgJ == L('job_taken') and Bridge.getJob(J) == 'miner', 'police -> miner')
local okA, msgA = call('urban_cavemining:takeJob', J)
check(okA == false and msgA == L('already_miner'), 'cannot take the job twice')
Config.Job = 'miner'
check(Bridge.hasJob(J), 'miner passes the job gate')
local okQ = call('urban_cavemining:quitJob', J)
check(okQ == true and Bridge.getJob(J) == 'unemployed', 'quit the mine')
check(not Bridge.hasJob(J), 'job gate blocks after quitting')
Config.Job = nil
local saveJC = Config.JobCenter.job
Config.JobCenter.job = 'astronaut'
local okM, msgM = call('urban_cavemining:takeJob', J)
check(okM == false and msgM == L('job_missing'), 'missing job is reported')
Config.JobCenter.job = saveJC

--──────────────────────────────── editor ─────────────────────────────────
source = S
local before = #Ores.positions()
events['urban_cavemining:server:editorAdd'](vec4(2900.0, 2700.0, 45.0, 90.0))
check(#Ores.positions() == before + 1, 'editor adds a spot')
events['urban_cavemining:server:editorRemove'](before + 1)
check(#Ores.positions() == before, 'editor removes a spot')
check(saved['data/positions.json'], 'editor saves positions.json')

realPrint(('OK - %d checks passed'):format(passed))
