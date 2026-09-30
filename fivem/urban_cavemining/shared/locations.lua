-- Everything positional for the K4MB1 "Cave Mining" MLO
-- MLO origin (from K4MB1): 2889.014, 2664.655, 41.72483 - Davis Quartz quarry, east of Sandy Shores.
-- Ore spots can be edited in-game with /caveeditor (saved to data/positions.json, which
-- then overrides Locations.OrePositions).

Locations = {}

Locations.Cave = {
    center = vec3(2889.014, 2664.655, 41.72483),
    radius = 175.0,      -- "inside the mine" radius (ore streaming, headlamp onlyInCave, foot dust)
    -- mine portal in the quarry wall (x, y, z, heading looking INTO the cave).
    -- Stand in the opening in-game and run /cavecoords to get your exact value.
    entrance = vec4(2937.98, 2744.81, 43.28, 102.0),
    blip = {
        enabled = true,
        sprite  = 527, color = 81, scale = 0.85,   -- placed on the entrance
    },
}

-- mine foreman outside the portal (take / quit the miner job)
Locations.Foreman = {
    coords   = vec4(2944.2, 2748.6, 43.25, 280.0),
    model    = 's_m_y_construct_02',
    scenario = 'WORLD_HUMAN_CLIPBOARD',
}

Locations.Shop = {
    coords   = vec4(2908.8, 2643.6, 43.26, 328.32),
    model    = 'g_m_m_chemwork_01',
    scenario = 'WORLD_HUMAN_CLIPBOARD',
}

Locations.Buyer = {
    coords   = vec4(2917.79, 2646.26, 43.17, 6.14),
    model    = 's_m_y_construct_01',
    scenario = 'WORLD_HUMAN_CLIPBOARD',
}

Locations.Smelters = {
    { coords = vec3(2921.81, 2653.42, 43.15), glow = true },
}

Locations.Cracking = {
    { coords = vec4(2914.9, 2650.78, 43.08, 231.77),  prop = 'prop_vertdrill_01' },
    { coords = vec4(2914.61, 2649.06, 43.19, 272.74), prop = 'prop_vertdrill_01' },
}

Locations.JewelCutting = {
    { coords = vec4(2917.45, 2654.24, 43.03, 229.61), prop = 'gr_prop_gr_speeddrill_01c' },
    { coords = vec4(2919.89, 2656.36, 43.15, 199.99), prop = 'gr_prop_gr_speeddrill_01c' },
}

-- Suggested water spots for stone washing / gold panning (any water works, these just get blips)
Locations.WaterSpots = {
    { label = 'washing', coords = vec3(907.06, 4377.66, 30.28), sprite = 467, color = 3 },   -- Alamo Sea shore
    { label = 'panning', coords = vec3(-1410.58, 2005.91, 59.4), sprite = 467, color = 5 },  -- Tongva vineyard stream
}

-- 35 ore spots inside the cave (x, y, z, heading)
Locations.OrePositions = {
    -- entrance tunnel
    vec4(2906.33, 2736.05, 43.85, 30.0),
    vec4(2906.98, 2732.64, 43.47, 210.42),
    vec4(2895.62, 2718.17, 44.25, 90.59),
    vec4(2909.86, 2707.41, 44.63, 90.57),
    -- main chamber
    vec4(2930.71, 2693.23, 46.09, 240.69),
    vec4(2909.24, 2692.78, 47.27, 125.55),
    vec4(2908.31, 2695.83, 46.5, 25.8),
    vec4(2903.37, 2676.71, 45.94, 290.38),
    vec4(2890.67, 2679.4, 45.05, 120.51),
    vec4(2892.67, 2701.3, 49.89, 270.39),
    vec4(2876.93, 2707.35, 49.4, 10.29),
    vec4(2900.65, 2684.42, 47.24, 33.73),
    vec4(2878.67, 2686.09, 47.72, 170.0),
    -- upper west gallery
    vec4(2866.0, 2677.71, 47.3, 230.85),
    vec4(2859.24, 2668.93, 45.27, 270.51),
    vec4(2858.36, 2663.24, 45.0, 250.02),
    vec4(2864.22, 2665.22, 48.21, 140.18),
    vec4(2868.6, 2669.71, 47.88, 5.38),
    -- workshop side
    vec4(2888.64, 2634.32, 42.04, 190.17),
    vec4(2879.55, 2650.2, 43.89, 0.79),
    vec4(2896.12, 2648.21, 40.65, 320.66),
    -- far west crystal chamber
    vec4(2808.16, 2650.5, 38.2, 40.41),
    vec4(2792.43, 2640.55, 39.45, 125.72),
    vec4(2793.02, 2632.56, 39.91, 70.98),
    vec4(2799.6, 2629.83, 40.89, 180.92),
    vec4(2812.67, 2633.02, 40.79, 160.98),
    -- deep south shaft
    vec4(2817.65, 2590.74, 32.64, 121.44),
    vec4(2835.04, 2600.4, 34.93, 215.07),
    vec4(2837.77, 2605.3, 35.40, 300.09),
    vec4(2819.55, 2606.31, 38.08, 59.71),
    vec4(2823.73, 2611.07, 38.3, 49.71),
    vec4(2827.98, 2611.26, 34.15, 40.74),
    -- lower east tunnel
    vec4(2873.53, 2634.1, 39.42, 95.0),
    vec4(2871.89, 2642.97, 39.05, 80.0),
    vec4(2848.97, 2624.63, 36.58, 150.0),
}
