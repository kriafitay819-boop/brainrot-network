-- Generates the install/ snippets for every inventory from shared/items.lua
--   lua5.4 fivem/tools/generate_install.lua

local ROOT = (arg and arg[0] and arg[0]:match('^(.*)/tools/')) or 'fivem'
ROOT = ROOT .. '/urban_cavemining/'

dofile(ROOT .. 'shared/items.lua')

local USE_EXPORT = {
    goldpan = 'urban_cavemining.useGoldpan',
    mining_helmet = 'urban_cavemining.useHelmet',
}

local function q(s) return (s:gsub("'", "\\'")) end

local function write(path, text)
    local f = assert(io.open(ROOT .. path, 'w'))
    f:write(text)
    f:close()
    print('wrote ' .. path)
end

-- ox_inventory (data/items.lua) --------------------------------------------
local ox = {
    '-- urban_cavemining items for ox_inventory',
    '-- Paste inside the return { ... } table of ox_inventory/data/items.lua',
    '-- Images: copy install/images/*.png to ox_inventory/web/images/',
    '',
}
for _, name in ipairs(ItemOrder) do
    local item = Items[name]
    ox[#ox + 1] = ("['%s'] = {"):format(name)
    ox[#ox + 1] = ("    label = '%s',"):format(q(item.label))
    ox[#ox + 1] = ("    weight = %d,"):format(item.weight)
    ox[#ox + 1] = "    stack = true,"
    ox[#ox + 1] = "    close = true,"
    ox[#ox + 1] = ("    description = '%s',"):format(q(item.desc))
    if USE_EXPORT[name] then
        ox[#ox + 1] = ("    client = { export = '%s' },"):format(USE_EXPORT[name])
    end
    ox[#ox + 1] = '},'
    ox[#ox + 1] = ''
end
write('install/ox_inventory_items.lua', table.concat(ox, '\n'))

-- qb-core (shared/items.lua) -------------------------------------------------
local qb = {
    '-- urban_cavemining items for qb-core',
    '-- Paste inside QBShared.Items = { ... } in qb-core/shared/items.lua',
    '-- Images: copy install/images/*.png to qb-inventory/html/images/',
    '',
}
for _, name in ipairs(ItemOrder) do
    local item = Items[name]
    qb[#qb + 1] = ("%s = { name = '%s', label = '%s', weight = %d, type = 'item', image = '%s.png', unique = false, useable = %s, shouldClose = true, combinable = nil, description = '%s' },")
        :format(name, name, q(item.label), item.weight, name, tostring(item.usable == true), q(item.desc))
end
write('install/qb_items.lua', table.concat(qb, '\n') .. '\n')

-- ESX (SQL) ------------------------------------------------------------------
local sql = {
    '-- urban_cavemining items for es_extended (run once on your database)',
    'INSERT IGNORE INTO `items` (`name`, `label`, `weight`, `rare`, `can_remove`) VALUES',
}
local rows = {}
for _, name in ipairs(ItemOrder) do
    local item = Items[name]
    local kg = math.max(1, math.ceil(item.weight / 1000))
    rows[#rows + 1] = ("    ('%s', '%s', %d, 0, 1)"):format(name, q(item.label), kg)
end
sql[#sql + 1] = table.concat(rows, ',\n') .. ';'
write('install/esx_items.sql', table.concat(sql, '\n') .. '\n')
