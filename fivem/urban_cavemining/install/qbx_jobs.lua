-- urban_cavemining: miner job for qbx_core
-- Paste inside the return { ... } table of qbx_core/shared/jobs.lua
-- Labels are shown in the HUD - change them to English if your server uses English.

['miner'] = {
    label = 'כורה',                      -- Miner
    defaultDuty = true,
    offDutyPay = false,
    grades = {
        [0] = { name = 'כורה מתחיל', payment = 60 },                               -- Apprentice
        [1] = { name = 'כורה', payment = 90 },                                     -- Miner
        [2] = { name = 'כורה בכיר', payment = 120 },                               -- Senior miner
        [3] = { name = 'מנהל המכרה', isboss = true, bankAuth = true, payment = 160 }, -- Mine manager
    },
},
