-- Framework / inventory bridge (server). Everything the rest of the resource
-- needs from qbx_core, qb-core, es_extended, ox_inventory or qb-inventory goes through here.

Bridge = {}

local function running(name)
    local state = GetResourceState(name)
    return state == 'started' or state == 'starting'
end

local framework = Config.Framework
if framework == 'auto' then
    if running('qbx_core') then framework = 'qbx'
    elseif running('qb-core') then framework = 'qb'
    elseif running('es_extended') then framework = 'esx'
    else framework = 'standalone' end
end

local inventory = Config.Inventory
if inventory == 'auto' then
    if running('ox_inventory') then inventory = 'ox'
    elseif framework == 'esx' then inventory = 'esx'
    else inventory = 'qb' end
end

Bridge.framework = framework
Bridge.inventory = inventory

local QBCore, ESX
if framework == 'qb' then
    QBCore = exports['qb-core']:GetCoreObject()
elseif framework == 'esx' then
    ESX = exports.es_extended:getSharedObject()
end

print(('^2[urban_cavemining]^7 framework: ^3%s^7 | inventory: ^3%s^7'):format(framework, inventory))

--──────────────────────────────── players ────────────────────────────────

local function getPlayer(src)
    if framework == 'qbx' then return exports.qbx_core:GetPlayer(src) end
    if framework == 'qb' then return QBCore.Functions.GetPlayer(src) end
    if framework == 'esx' then return ESX.GetPlayerFromId(src) end
    return nil
end

function Bridge.getIdentifier(src)
    local player = getPlayer(src)
    if framework == 'qbx' or framework == 'qb' then
        return player and player.PlayerData.citizenid
    elseif framework == 'esx' then
        return player and player.identifier
    end
    return GetPlayerIdentifierByType(src, 'license')
end

function Bridge.getJob(src)
    local player = getPlayer(src)
    if not player then return nil end
    if framework == 'qbx' or framework == 'qb' then
        return player.PlayerData.job and player.PlayerData.job.name
    elseif framework == 'esx' then
        return player.job and player.job.name
    end
    return nil
end

function Bridge.hasJob(src)
    if not Config.Job then return true end
    return Bridge.getJob(src) == Config.Job
end

function Bridge.jobExists(name, grade)
    if framework == 'qbx' then
        local ok, job = pcall(function() return exports.qbx_core:GetJob(name) end)
        return ok and job ~= nil
    elseif framework == 'qb' then
        return QBCore.Shared.Jobs[name] ~= nil
    elseif framework == 'esx' then
        if ESX.DoesJobExist then return ESX.DoesJobExist(name, grade or 0) end
        return true
    end
    return false
end

--- Replaces the player's job (police -> miner etc.)
function Bridge.setJob(src, name, grade)
    grade = grade or 0
    local player = getPlayer(src)
    if not player then return false end
    if framework == 'qbx' then
        local ok = pcall(function() exports.qbx_core:SetJob(src, name, grade) end)
        if not ok and player.Functions and player.Functions.SetJob then
            ok = player.Functions.SetJob(name, grade)
        end
        return ok and true or false
    elseif framework == 'qb' then
        return player.Functions.SetJob(name, grade) and true or false
    elseif framework == 'esx' then
        player.setJob(name, grade)
        return true
    end
    return false
end

--──────────────────────────────── money ──────────────────────────────────

local function esxAccount()
    return Config.PayWith == 'bank' and 'bank' or 'money'
end

function Bridge.getMoney(src)
    local player = getPlayer(src)
    if not player then return 0 end
    if framework == 'qbx' or framework == 'qb' then
        return player.PlayerData.money[Config.PayWith] or 0
    elseif framework == 'esx' then
        local account = player.getAccount(esxAccount())
        return account and account.money or 0
    end
    return 0
end

function Bridge.addMoney(src, amount, reason)
    local player = getPlayer(src)
    if not player or amount <= 0 then return false end
    if framework == 'qbx' then
        return exports.qbx_core:AddMoney(src, Config.PayWith, amount, reason)
    elseif framework == 'qb' then
        return player.Functions.AddMoney(Config.PayWith, amount, reason)
    elseif framework == 'esx' then
        player.addAccountMoney(esxAccount(), amount, reason)
        return true
    end
    return false
end

function Bridge.removeMoney(src, amount, reason)
    local player = getPlayer(src)
    if not player then return false end
    if Bridge.getMoney(src) < amount then return false end
    if framework == 'qbx' then
        return exports.qbx_core:RemoveMoney(src, Config.PayWith, amount, reason)
    elseif framework == 'qb' then
        return player.Functions.RemoveMoney(Config.PayWith, amount, reason)
    elseif framework == 'esx' then
        player.removeAccountMoney(esxAccount(), amount, reason)
        return true
    end
    return false
end

--──────────────────────────────── items ──────────────────────────────────

function Bridge.count(src, item)
    if inventory == 'ox' then
        return exports.ox_inventory:GetItemCount(src, item) or 0
    end
    local player = getPlayer(src)
    if not player then return 0 end
    if inventory == 'esx' then
        local invItem = player.getInventoryItem(item)
        return invItem and invItem.count or 0
    end
    -- qb / ps / lj inventories keep items on PlayerData
    local total = 0
    for _, slot in pairs(player.PlayerData.items or {}) do
        if slot and slot.name == item then
            total = total + (slot.amount or slot.count or 0)
        end
    end
    return total
end

function Bridge.canCarry(src, item, amount)
    if inventory == 'ox' then
        return exports.ox_inventory:CanCarryItem(src, item, amount)
    end
    if inventory == 'esx' then
        local player = getPlayer(src)
        if player and player.canCarryItem then return player.canCarryItem(item, amount) end
        return true
    end
    if running('qb-inventory') then
        local ok, result = pcall(function() return exports['qb-inventory']:CanAddItem(src, item, amount) end)
        if ok and result ~= nil then return result end
    end
    return true
end

local function qbItemBox(src, item, action, amount)
    if not QBCore then return end
    local shared = QBCore.Shared.Items[item]
    if not shared then return end
    TriggerClientEvent('qb-inventory:client:ItemBox', src, shared, action, amount)
    TriggerClientEvent('inventory:client:ItemBox', src, shared, action, amount)
end

function Bridge.addItem(src, item, amount, metadata)
    if amount <= 0 then return true end
    if inventory == 'ox' then
        local success = exports.ox_inventory:AddItem(src, item, amount, metadata)
        return success and true or false
    end
    local player = getPlayer(src)
    if not player then return false end
    if inventory == 'esx' then
        player.addInventoryItem(item, amount)
        return true
    end
    local ok = player.Functions.AddItem(item, amount, false, metadata)
    if ok then qbItemBox(src, item, 'add', amount) end
    return ok
end

function Bridge.removeItem(src, item, amount)
    if amount <= 0 then return true end
    if Bridge.count(src, item) < amount then return false end
    if inventory == 'ox' then
        return exports.ox_inventory:RemoveItem(src, item, amount) and true or false
    end
    local player = getPlayer(src)
    if not player then return false end
    if inventory == 'esx' then
        player.removeInventoryItem(item, amount)
        return true
    end
    local ok = player.Functions.RemoveItem(item, amount)
    if ok then qbItemBox(src, item, 'remove', amount) end
    return ok
end

--──────────────────────────────── usable items ───────────────────────────
-- ox_inventory: items call client exports (see install/ox_inventory_items.lua)
-- qb / esx: registered here and forwarded to the client

function Bridge.registerUsable(item, clientEvent)
    if inventory == 'ox' then return end
    if framework == 'qb' then
        QBCore.Functions.CreateUseableItem(item, function(source)
            TriggerClientEvent(clientEvent, source)
        end)
    elseif framework == 'qbx' then
        exports.qbx_core:CreateUseableItem(item, function(source)
            TriggerClientEvent(clientEvent, source)
        end)
    elseif framework == 'esx' then
        ESX.RegisterUsableItem(item, function(source)
            TriggerClientEvent(clientEvent, source)
        end)
    end
end

--──────────────────────────────── notify ─────────────────────────────────

function Bridge.notify(src, message, kind)
    TriggerClientEvent('ox_lib:notify', src, {
        title = L('blip_cave'),
        description = message,
        type = kind or 'inform',
        icon = 'gem',
    })
end
