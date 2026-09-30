-- Single source of truth for every item this resource uses.
-- label = inventory label (English), he = Hebrew label shown in the menus when Config.Locale = 'he'
-- The install/ folder has ready-made snippets generated from this list.

Items = {
    -- tools
    pickaxe        = { label = 'Pickaxe',            he = 'מכוש',                weight = 2500, usable = false, desc = 'A sturdy pickaxe for breaking ore.' },
    miningdrill    = { label = 'Mining Drill',       he = 'מקדחת כרייה',          weight = 4000, usable = false, desc = 'Mines faster, eats drill bits.' },
    drillbit       = { label = 'Drill Bit',          he = 'ראש מקדחה',            weight = 250,  usable = false, desc = 'Replacement bit for drills and cutting benches.' },
    mininglaser    = { label = 'Mining Laser',       he = 'לייזר כרייה',          weight = 5000, usable = false, desc = 'Industrial laser that cuts through crystal.' },
    goldpan        = { label = 'Gold Pan',           he = 'מחבת זהב',             weight = 700,  usable = true,  desc = 'Stand in water and use it to pan for gold or wash stone.' },
    mining_helmet  = { label = 'Mining Helmet',      he = 'קסדת כורים',           weight = 800,  usable = true,  desc = 'Hard hat with a head lamp. Use to toggle the lamp.' },

    -- raw
    stone          = { label = 'Stone',              he = 'אבן',                  weight = 1000, desc = 'Raw stone. Crack it or wash it for loot.' },
    coal           = { label = 'Coal',               he = 'פחם',                  weight = 500,  desc = 'Fuel for the smelter.' },
    copperore      = { label = 'Copper Ore',         he = 'עפרת נחושת',           weight = 1000, desc = 'Unrefined copper.' },
    ironore        = { label = 'Iron Ore',           he = 'עפרת ברזל',            weight = 1000, desc = 'Unrefined iron.' },
    tinore         = { label = 'Tin Ore',            he = 'עפרת בדיל',            weight = 1000, desc = 'Unrefined tin.' },
    leadore        = { label = 'Lead Ore',           he = 'עפרת עופרת',           weight = 1000, desc = 'Unrefined lead.' },
    bauxite        = { label = 'Bauxite',            he = 'בוקסיט',               weight = 1000, desc = 'Aluminium ore.' },
    goldore        = { label = 'Gold Ore',           he = 'עפרת זהב',             weight = 1000, desc = 'Rock streaked with gold.' },
    goldnugget     = { label = 'Gold Nugget',        he = 'גוש זהב',              weight = 200,  desc = 'A small nugget of gold.' },

    -- uncut gems
    uncut_ruby     = { label = 'Uncut Ruby',         he = 'אודם לא מלוטש',        weight = 300,  desc = 'Rough red crystal.' },
    uncut_emerald  = { label = 'Uncut Emerald',      he = 'ברקת לא מלוטשת',       weight = 300,  desc = 'Rough green crystal.' },
    uncut_sapphire = { label = 'Uncut Sapphire',     he = 'ספיר לא מלוטש',        weight = 300,  desc = 'Rough blue crystal.' },
    uncut_diamond  = { label = 'Uncut Diamond',      he = 'יהלום לא מלוטש',       weight = 300,  desc = 'A rough diamond.' },

    -- refined
    copper         = { label = 'Copper Ingot',       he = 'מטיל נחושת',           weight = 500,  desc = 'Smelted copper.' },
    iron           = { label = 'Iron Ingot',         he = 'מטיל ברזל',            weight = 500,  desc = 'Smelted iron.' },
    tin            = { label = 'Tin Ingot',          he = 'מטיל בדיל',            weight = 500,  desc = 'Smelted tin.' },
    lead           = { label = 'Lead Ingot',         he = 'מטיל עופרת',           weight = 500,  desc = 'Smelted lead.' },
    aluminum       = { label = 'Aluminium Ingot',    he = 'מטיל אלומיניום',       weight = 300,  desc = 'Smelted aluminium.' },
    steel          = { label = 'Steel Ingot',        he = 'מטיל פלדה',            weight = 600,  desc = 'Iron and carbon, forged together.' },
    bronze         = { label = 'Bronze Ingot',       he = 'מטיל ארד',             weight = 500,  desc = 'Copper and tin alloy.' },
    goldingot      = { label = 'Gold Ingot',         he = 'מטיל זהב',             weight = 600,  desc = 'A bar of pure gold.' },

    -- cut gems
    ruby           = { label = 'Ruby',               he = 'אודם',                 weight = 100,  desc = 'A polished ruby.' },
    emerald        = { label = 'Emerald',            he = 'ברקת',                 weight = 100,  desc = 'A polished emerald.' },
    sapphire       = { label = 'Sapphire',           he = 'ספיר',                 weight = 100,  desc = 'A polished sapphire.' },
    diamond        = { label = 'Diamond',            he = 'יהלום',                weight = 100,  desc = 'A polished diamond.' },

    -- jewellery
    gold_ring         = { label = 'Gold Ring',         he = 'טבעת זהב',          weight = 100, desc = 'Plain gold band.' },
    goldchain         = { label = 'Gold Chain',        he = 'שרשרת זהב',         weight = 200, desc = 'Heavy gold chain.' },
    ruby_ring         = { label = 'Ruby Ring',         he = 'טבעת אודם',         weight = 100, desc = 'Gold ring set with a ruby.' },
    emerald_ring      = { label = 'Emerald Ring',      he = 'טבעת ברקת',         weight = 100, desc = 'Gold ring set with an emerald.' },
    sapphire_ring     = { label = 'Sapphire Ring',     he = 'טבעת ספיר',         weight = 100, desc = 'Gold ring set with a sapphire.' },
    diamond_ring      = { label = 'Diamond Ring',      he = 'טבעת יהלום',        weight = 100, desc = 'Gold ring set with a diamond.' },
    ruby_necklace     = { label = 'Ruby Necklace',     he = 'שרשרת אודם',        weight = 200, desc = 'Gold chain with a ruby pendant.' },
    emerald_necklace  = { label = 'Emerald Necklace',  he = 'שרשרת ברקת',        weight = 200, desc = 'Gold chain with an emerald pendant.' },
    sapphire_necklace = { label = 'Sapphire Necklace', he = 'שרשרת ספיר',        weight = 200, desc = 'Gold chain with a sapphire pendant.' },
    diamond_necklace  = { label = 'Diamond Necklace',  he = 'שרשרת יהלום',       weight = 200, desc = 'Gold chain with a diamond pendant.' },
    ruby_earring      = { label = 'Ruby Earrings',     he = 'עגילי אודם',        weight = 50,  desc = 'A pair of ruby earrings.' },
    emerald_earring   = { label = 'Emerald Earrings',  he = 'עגילי ברקת',        weight = 50,  desc = 'A pair of emerald earrings.' },
    sapphire_earring  = { label = 'Sapphire Earrings', he = 'עגילי ספיר',        weight = 50,  desc = 'A pair of sapphire earrings.' },
    diamond_earring   = { label = 'Diamond Earrings',  he = 'עגילי יהלום',       weight = 50,  desc = 'A pair of diamond earrings.' },
}

-- stable order for the install generators / menus
ItemOrder = {
    'pickaxe', 'miningdrill', 'drillbit', 'mininglaser', 'goldpan', 'mining_helmet',
    'stone', 'coal', 'copperore', 'ironore', 'tinore', 'leadore', 'bauxite', 'goldore', 'goldnugget',
    'uncut_ruby', 'uncut_emerald', 'uncut_sapphire', 'uncut_diamond',
    'copper', 'iron', 'tin', 'lead', 'aluminum', 'steel', 'bronze', 'goldingot',
    'ruby', 'emerald', 'sapphire', 'diamond',
    'gold_ring', 'goldchain',
    'ruby_ring', 'emerald_ring', 'sapphire_ring', 'diamond_ring',
    'ruby_necklace', 'emerald_necklace', 'sapphire_necklace', 'diamond_necklace',
    'ruby_earring', 'emerald_earring', 'sapphire_earring', 'diamond_earring',
}
