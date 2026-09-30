fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'urban_cavemining'
author 'URBAN RP'
description 'Full cave mining system for the K4MB1 Cave Mining MLO (Davis Quartz quarry)'
version '1.0.0'

dependencies {
    'ox_lib',
}

shared_scripts {
    '@ox_lib/init.lua',
    'config.lua',
    'shared/locations.lua',
    'shared/items.lua',
    'locales/en.lua',
    'locales/he.lua',
    'shared/utils.lua',
}

client_scripts {
    'bridge/client.lua',
    'client/main.lua',
    'client/mining.lua',
    'client/stations.lua',
    'client/water.lua',
    'client/headlamp.lua',
    'client/footsteps.lua',
    'client/editor.lua',
}

server_scripts {
    'bridge/server.lua',
    'server/main.lua',
    'server/ores.lua',
    'server/stations.lua',
    'server/editor.lua',
}
