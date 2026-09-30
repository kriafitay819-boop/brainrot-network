-- urban_cavemining: miner job for qb-core
-- Paste inside QBShared.Jobs = { ... } in qb-core/shared/jobs.lua
-- Labels are shown in the HUD - change them to English if your server uses English.

miner = {
    label = 'כורה',                      -- Miner
    defaultDuty = true,
    offDutyPay = false,
    grades = {
        ['0'] = { name = 'כורה מתחיל', payment = 60 },               -- Apprentice
        ['1'] = { name = 'כורה', payment = 90 },                     -- Miner
        ['2'] = { name = 'כורה בכיר', payment = 120 },               -- Senior miner
        ['3'] = { name = 'מנהל המכרה', isboss = true, payment = 160 }, -- Mine manager
    },
},
