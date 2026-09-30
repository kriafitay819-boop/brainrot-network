-- urban_cavemining items for ox_inventory
-- Paste inside the return { ... } table of ox_inventory/data/items.lua
-- Images: copy install/images/*.png to ox_inventory/web/images/

['pickaxe'] = {
    label = 'Pickaxe',
    weight = 2500,
    stack = true,
    close = true,
    description = 'A sturdy pickaxe for breaking ore.',
},

['miningdrill'] = {
    label = 'Mining Drill',
    weight = 4000,
    stack = true,
    close = true,
    description = 'Mines faster, eats drill bits.',
},

['drillbit'] = {
    label = 'Drill Bit',
    weight = 250,
    stack = true,
    close = true,
    description = 'Replacement bit for drills and cutting benches.',
},

['mininglaser'] = {
    label = 'Mining Laser',
    weight = 5000,
    stack = true,
    close = true,
    description = 'Industrial laser that cuts through crystal.',
},

['goldpan'] = {
    label = 'Gold Pan',
    weight = 700,
    stack = true,
    close = true,
    description = 'Stand in water and use it to pan for gold or wash stone.',
    client = { export = 'urban_cavemining.useGoldpan' },
},

['mining_helmet'] = {
    label = 'Mining Helmet',
    weight = 800,
    stack = true,
    close = true,
    description = 'Hard hat with a head lamp. Use to toggle the lamp.',
    client = { export = 'urban_cavemining.useHelmet' },
},

['stone'] = {
    label = 'Stone',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Raw stone. Crack it or wash it for loot.',
},

['coal'] = {
    label = 'Coal',
    weight = 500,
    stack = true,
    close = true,
    description = 'Fuel for the smelter.',
},

['copperore'] = {
    label = 'Copper Ore',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Unrefined copper.',
},

['ironore'] = {
    label = 'Iron Ore',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Unrefined iron.',
},

['tinore'] = {
    label = 'Tin Ore',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Unrefined tin.',
},

['leadore'] = {
    label = 'Lead Ore',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Unrefined lead.',
},

['bauxite'] = {
    label = 'Bauxite',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Aluminium ore.',
},

['goldore'] = {
    label = 'Gold Ore',
    weight = 1000,
    stack = true,
    close = true,
    description = 'Rock streaked with gold.',
},

['goldnugget'] = {
    label = 'Gold Nugget',
    weight = 200,
    stack = true,
    close = true,
    description = 'A small nugget of gold.',
},

['uncut_ruby'] = {
    label = 'Uncut Ruby',
    weight = 300,
    stack = true,
    close = true,
    description = 'Rough red crystal.',
},

['uncut_emerald'] = {
    label = 'Uncut Emerald',
    weight = 300,
    stack = true,
    close = true,
    description = 'Rough green crystal.',
},

['uncut_sapphire'] = {
    label = 'Uncut Sapphire',
    weight = 300,
    stack = true,
    close = true,
    description = 'Rough blue crystal.',
},

['uncut_diamond'] = {
    label = 'Uncut Diamond',
    weight = 300,
    stack = true,
    close = true,
    description = 'A rough diamond.',
},

['copper'] = {
    label = 'Copper Ingot',
    weight = 500,
    stack = true,
    close = true,
    description = 'Smelted copper.',
},

['iron'] = {
    label = 'Iron Ingot',
    weight = 500,
    stack = true,
    close = true,
    description = 'Smelted iron.',
},

['tin'] = {
    label = 'Tin Ingot',
    weight = 500,
    stack = true,
    close = true,
    description = 'Smelted tin.',
},

['lead'] = {
    label = 'Lead Ingot',
    weight = 500,
    stack = true,
    close = true,
    description = 'Smelted lead.',
},

['aluminum'] = {
    label = 'Aluminium Ingot',
    weight = 300,
    stack = true,
    close = true,
    description = 'Smelted aluminium.',
},

['steel'] = {
    label = 'Steel Ingot',
    weight = 600,
    stack = true,
    close = true,
    description = 'Iron and carbon, forged together.',
},

['bronze'] = {
    label = 'Bronze Ingot',
    weight = 500,
    stack = true,
    close = true,
    description = 'Copper and tin alloy.',
},

['goldingot'] = {
    label = 'Gold Ingot',
    weight = 600,
    stack = true,
    close = true,
    description = 'A bar of pure gold.',
},

['ruby'] = {
    label = 'Ruby',
    weight = 100,
    stack = true,
    close = true,
    description = 'A polished ruby.',
},

['emerald'] = {
    label = 'Emerald',
    weight = 100,
    stack = true,
    close = true,
    description = 'A polished emerald.',
},

['sapphire'] = {
    label = 'Sapphire',
    weight = 100,
    stack = true,
    close = true,
    description = 'A polished sapphire.',
},

['diamond'] = {
    label = 'Diamond',
    weight = 100,
    stack = true,
    close = true,
    description = 'A polished diamond.',
},

['gold_ring'] = {
    label = 'Gold Ring',
    weight = 100,
    stack = true,
    close = true,
    description = 'Plain gold band.',
},

['goldchain'] = {
    label = 'Gold Chain',
    weight = 200,
    stack = true,
    close = true,
    description = 'Heavy gold chain.',
},

['ruby_ring'] = {
    label = 'Ruby Ring',
    weight = 100,
    stack = true,
    close = true,
    description = 'Gold ring set with a ruby.',
},

['emerald_ring'] = {
    label = 'Emerald Ring',
    weight = 100,
    stack = true,
    close = true,
    description = 'Gold ring set with an emerald.',
},

['sapphire_ring'] = {
    label = 'Sapphire Ring',
    weight = 100,
    stack = true,
    close = true,
    description = 'Gold ring set with a sapphire.',
},

['diamond_ring'] = {
    label = 'Diamond Ring',
    weight = 100,
    stack = true,
    close = true,
    description = 'Gold ring set with a diamond.',
},

['ruby_necklace'] = {
    label = 'Ruby Necklace',
    weight = 200,
    stack = true,
    close = true,
    description = 'Gold chain with a ruby pendant.',
},

['emerald_necklace'] = {
    label = 'Emerald Necklace',
    weight = 200,
    stack = true,
    close = true,
    description = 'Gold chain with an emerald pendant.',
},

['sapphire_necklace'] = {
    label = 'Sapphire Necklace',
    weight = 200,
    stack = true,
    close = true,
    description = 'Gold chain with a sapphire pendant.',
},

['diamond_necklace'] = {
    label = 'Diamond Necklace',
    weight = 200,
    stack = true,
    close = true,
    description = 'Gold chain with a diamond pendant.',
},

['ruby_earring'] = {
    label = 'Ruby Earrings',
    weight = 50,
    stack = true,
    close = true,
    description = 'A pair of ruby earrings.',
},

['emerald_earring'] = {
    label = 'Emerald Earrings',
    weight = 50,
    stack = true,
    close = true,
    description = 'A pair of emerald earrings.',
},

['sapphire_earring'] = {
    label = 'Sapphire Earrings',
    weight = 50,
    stack = true,
    close = true,
    description = 'A pair of sapphire earrings.',
},

['diamond_earring'] = {
    label = 'Diamond Earrings',
    weight = 50,
    stack = true,
    close = true,
    description = 'A pair of diamond earrings.',
},
